"""Consent-bound host-folder ingestion into the existing evidence stores.

The host worker chooses its fixed directory locally. HTTP can pause/resume it,
never instruct it to open a different path. Run IDs prevent stale commits.

Dieselbe Route bedient zwei Ordner (`Ordnerart`): den für Dokumente und den für
Mitschriften aus Meetings (`transkript_routes.py`). Der zweite ist kein dritter
Weg, sondern derselbe Weg mit eigener Einstellung und eigener Auswertung.

Ohne Mac-Helfer (Docker, Browser) wählt der Mensch den Ordner im Browser, und der
Sidecar liest ihn selbst (`ordner_lokal.py`, Fremdprobe Befund 6): `GET …/orte`
nennt bekannte Orte, `POST …/lokal` gibt den gewählten frei und liest ihn sofort,
danach etwa einmal pro Minute. Der Weg in den Bestand ist derselbe (begin, files,
finish); der Zustand trägt dann `lokal: true`.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import threading
import time
from copy import deepcopy
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from types import SimpleNamespace
import uuid

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config, logbuch
from .document_text import docx_text, pdf_text
from .episodes import EpisodeKind
from .model import Provenance, SourceType
from .source_versions import track_source, invalidate_with_corrections
from .transcript_preview import preview_transcript

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 512 * 1024
MAX_FILES = 2000
TAKT_S = 60
"""So oft liest der Sidecar einen im Browser gewählten Ordner selbst (Sekunden)."""
PICK_MINUTEN = 10
"""So lange gilt eine Anfrage „Ordner wählen“, bis der Mac-Helfer geantwortet hat."""
SUFFIXES = {'.md', '.markdown', '.txt', '.org', '.rst', '.csv', '.docx', '.pdf', '.srt', '.vtt'}


@dataclass(frozen=True)
class Ordnerart:
    """Welche Sorte Ordner eine Route bedient.

    Es gibt genau einen Weg vom Mac-Ordnerarbeiter in den Bestand. Der zweite
    Ordner (Mitschriften aus Meetings) ist dieselbe Route mit anderem Namen,
    eigener Einstellung und eigener Auswertung, keine zweite Bauweise.
    """

    prefix: str = '/api/v1/folder-sync'
    einstellung: str = 'folder_sync'
    schluessel: str = 'folder'
    herkunft: str = 'mac-folder'
    transkripte: bool = False
    vorgabe_name: str = 'Dokumente'
    """Name des Vorgabeordners unter `~/Documents/Kingfisher/` für den Weg im Browser."""


DOKUMENTE = Ordnerart()


def now():
    return datetime.now(timezone.utc)


def fresh(value, minutes):
    try:
        age = now() - datetime.fromisoformat(value.replace('Z', '+00:00'))
        return timedelta(0) <= age <= timedelta(minutes=minutes)
    except (ValueError, TypeError, AttributeError):
        return False


def filename(value, *, supported=True, suffixes=SUFFIXES):
    if (not value or len(value) > 1024 or any(c in value for c in ('\\', '\0', '\n', '\r'))
            or any(part in ('', '.', '..') for part in value.split('/'))
            or (supported and PurePosixPath(value).suffix.lower() not in suffixes)):
        raise HTTPException(422, 'Ungültiger oder nicht unterstützter Dateiname.')
    return value


def extract(name, data):
    suffix = PurePosixPath(name).suffix.lower()
    if len(data) > MAX_BYTES:
        raise ValueError('Die Datei überschreitet 5 MiB.')
    if suffix == '.docx':
        text = docx_text(data)
    elif suffix == '.pdf':
        result = pdf_text(data)
        text = result['body']
    else:
        if len(data) > MAX_TEXT:
            raise ValueError('Die Textdatei überschreitet 512 KiB.')
        text = data.decode('utf-8-sig')
        if suffix in {'.srt', '.vtt'}:
            text = preview_transcript(text, suffix[1:])['body']
    if not text.strip() or '\0' in text or len(text.encode('utf-8')) > MAX_TEXT:
        raise ValueError('Kein gültiger Text innerhalb der Grenze von 512 KiB.')
    return text


class WorkerIn(BaseModel):
    root_id: str | None = Field(default=None, min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    folder: str | None = Field(default=None, min_length=1, max_length=2048)
    picked: str | None = Field(default=None, max_length=64)
    """Kennung der Auswahlanfrage, auf die der Helfer mit diesem Ordner antwortet."""
    cancelled: str | None = Field(default=None, max_length=64)
    """Kennung einer Auswahlanfrage, die am Mac abgebrochen wurde."""


class SwitchIn(BaseModel):
    enabled: bool


class LokalIn(BaseModel):
    """Ein im Browser gewählter Ordner: ein bekannter Ort, ein getippter Pfad oder der Vorgabeordner."""
    pfad: str | None = Field(default=None, max_length=4096)
    vorgabe: bool = False


class RunIn(BaseModel):
    root_id: str
    generation: int


class CommitIn(RunIn):
    run_id: str


class FileIn(CommitIn):
    filename: str = Field(max_length=1024)
    content_base64: str = Field(max_length=7 * 1024 * 1024)
    modified: float | None = Field(default=None, ge=0, le=4102444800)
    """Änderungszeit der Datei (Sekunden seit 1970); bei Mitschriften ein schwaches Zeichen."""


class FinishIn(CommitIn):
    observed: list[str] = Field(max_length=MAX_FILES)
    errors: list[str] = Field(default_factory=list, max_length=30)
    complete: bool


def register_folder_routes(app, guard, data_dir, art: Ordnerart = DOKUMENTE):
    """Verdrahtet die Ordneraufnahme und gibt ihre Hilfsfunktionen für Erweiterungen zurück."""
    suffixes = SUFFIXES
    if art.transkripte:
        from . import transkript_eingang
        suffixes = transkript_eingang.SUFFIXES

    def state():
        return {'enabled': False, 'generation': 0, 'root_id': None, 'folder': None,
                'seen_at': None, 'synced_at': None, 'last_run': None, 'files': {}, 'missing': [], 'digests': {},
                **deepcopy(getattr(app.state.settings, art.einstellung))}

    def save(s):
        previous = getattr(app.state.settings, art.einstellung)
        setattr(app.state.settings, art.einstellung, deepcopy(s))
        try:
            config.save(data_dir(), app.state.settings)
        except Exception:
            setattr(app.state.settings, art.einstellung, previous)
            raise

    def public(*, summary=False):
        if summary:
            # Keep only small metadata. No deep copy of names, digests or the
            # complete file map, and no original-body lookup for each file.
            stored = getattr(app.state.settings, art.einstellung)
            keys = ('enabled', 'generation', 'root_id', 'folder', 'seen_at', 'synced_at',
                    'pick_request', 'lokal', 'helfer_at', 'getrennt')
            s = {'enabled': False, 'generation': 0,
                 **{key: deepcopy(stored[key]) for key in keys if key in stored}}
            last = stored.get('last_run')
            s['last_run'] = ({**{key: last.get(key, 0) for key in ('recorded', 'duplicates', 'changed', 'removed')},
                              'error_count': len(last.get('errors') or [])} if last else None)
            references = Counter((stored.get('files') or {}).values())
        else:
            s = state()
        pick = s.get('pick_request')
        result = {**{k: s.get(k) for k in ('enabled', 'generation', 'root_id', 'folder', 'seen_at', 'synced_at', 'last_run')},
                  'running': fresh(s.get('seen_at'), 2),
                  'lokal': bool(s.get('lokal')), 'helfer': fresh(s.get('helfer_at'), 2),
                  'getrennt': bool(s.get('getrennt')),
                  'pick_request': ({'id': pick['id'], 'modus': pick['modus']}
                                   if pick and fresh(pick.get('at'), PICK_MINUTEN) else None)}
        if summary:
            counts = {'recorded': sum(references.values()), 'active': 0, 'ignored': 0, 'unknown': sum(references.values())}
            identifiers = list(references)
            with app.state.episodes._lock:
                for start in range(0, len(identifiers), 500):
                    chunk = identifiers[start:start + 500]
                    rows = app.state.episodes._conn.execute(
                        f"SELECT id,state FROM episodes WHERE id IN ({','.join('?' for _ in chunk)})", chunk).fetchall()
                    for identifier, episode_state in rows:
                        amount = references[identifier]
                        counts['ignored' if episode_state == 'ignored' else 'active'] += amount
                        counts['unknown'] -= amount
            result['file_counts'] = counts
        else:
            result['files'] = [{'filename': name, 'id': eid, 'state': app.state.episodes.get(eid).state.value}
                               for name, eid in sorted(s['files'].items())]
        return result

    def permitted(body, *, run=False):
        s = state()
        if not s['enabled'] or s['root_id'] != body.root_id or s['generation'] != body.generation:
            raise HTTPException(409, 'Die Ordnerfreigabe wurde geändert. Aufnahme gestoppt.')
        if run and (s.get('run_id') != body.run_id or not fresh(s.get('started_at'), 15)):
            raise HTTPException(409, 'Dieser Aufnahmelauf ist nicht mehr gültig.')
        return s

    # Bei Mitschriften trägt der Ausschluss die Marke „entzogen:ordner“: Nur daran erkennt die
    # Aufnahme, dass dieselbe Datei nach erneuter Freigabe wieder gelten darf.
    grund = 'ordner' if art.transkripte else ''

    def entziehen(s):
        """Alle Quellen dieses Ordners entziehen (Ordner gewechselt oder getrennt)."""
        for eid in s['files'].values():
            invalidate_with_corrections(app.state.episodes, app.state.claims, eid)
            app.state.episodes.ignore(eid, grund=grund)

    @app.get(art.prefix, dependencies=guard)
    def get_state(summary: bool = False):
        with app.state.conversation_lock:
            return public(summary=summary)

    @app.post(art.prefix + '/worker', dependencies=guard)
    def worker(body: WorkerIn):
        with app.state.conversation_lock:
            s = state()
            pick = s.get('pick_request')
            if body.cancelled and pick and pick.get('id') == body.cancelled:
                s.pop('pick_request', None)
                pick = None
            s['helfer_at'] = now().isoformat()
            if body.root_id is None or body.folder is None:
                # Der Helfer lebt, hat aber keinen Ordner (noch nicht gewählt oder getrennt).
                if not art.transkripte:
                    raise HTTPException(422, 'Ordner fehlt.')
                s['seen_at'] = now().isoformat()
                save(s)
                return public()
            wahl = bool(body.picked and pick and fresh(pick.get('at'), PICK_MINUTEN) and pick.get('id') == body.picked)
            if s.get('lokal') and not wahl:
                # Der Ordner wurde im Browser gewählt; ein Helfer ändert ihn nur mit einer neuen Auswahl am Mac.
                save(s)
                return public()
            if s.get('getrennt') and not wahl:
                # Nach dem Trennen bietet der Helfer seinen alten Ordner nicht wieder an.
                s['seen_at'] = now().isoformat()
                save(s)
                return public()
            if s['root_id'] != body.root_id or s['folder'] != body.folder:
                entziehen(s)
                s = {'enabled': False, 'generation': s['generation'] + 1,
                     'root_id': body.root_id, 'folder': body.folder, 'files': {},
                     'synced_at': None, 'last_run': None, 'pick_request': s.get('pick_request')}
                if s['pick_request'] is None:
                    del s['pick_request']
            if wahl:
                # Das Auswählen im Dialog ist die ausdrückliche Freigabe dieses einen Ordners.
                s.update(enabled=True, generation=s['generation'] + 1, run_id=None, getrennt=False)
                s.pop('lokal', None)
                s.pop('pick_request', None)
            s['seen_at'] = now().isoformat()
            save(s)
            return public()

    @app.put(art.prefix, dependencies=guard)
    def configure(body: SwitchIn):
        with app.state.conversation_lock:
            s = state()
            if body.enabled and not s['root_id']:
                raise HTTPException(409, 'Bitte zuerst den lokalen Ordnerhelfer starten.')
            s.update(enabled=body.enabled, generation=s['generation'] + 1, run_id=None)
            save(s)
            return public()

    @app.post(art.prefix + '/run', dependencies=guard)
    def request_run():
        with app.state.conversation_lock:
            s = state()
            if not s['enabled']:
                raise HTTPException(409, 'Die Ordneraufnahme ist pausiert.')
            s.update(generation=s['generation'] + 1, run_id=None)
            save(s)
            lokal = bool(s.get('lokal'))
        if lokal:  # ohne Helfer liest der Sidecar selbst, sofort
            abgleichen()
        with app.state.conversation_lock:
            return public()

    @app.post(art.prefix + '/begin', dependencies=guard)
    def begin(body: RunIn):
        with app.state.conversation_lock:
            s = permitted(body)
            s.update(run_id=uuid.uuid4().hex, started_at=now().isoformat(),
                     current={'recorded': 0, 'duplicates': 0, 'changed': 0, 'removed': 0})
            save(s)
            return {'run_id': s['run_id']}

    @app.post(art.prefix + '/files', dependencies=guard)
    def import_file(body: FileIn):
        name = filename(body.filename, suffixes=suffixes)
        with app.state.conversation_lock:
            permitted(body, run=True)
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(422, 'Ungültige Dateiübertragung.') from exc
        digest = hashlib.sha256(data).hexdigest()
        with app.state.conversation_lock:
            s = permitted(body, run=True)
            if name in s['files'] and s['digests'].get(name) == digest:
                s['current']['duplicates'] += 1
                s['missing'] = [item for item in s['missing'] if item != name]
                save(s)
                return {'id': s['files'][name], 'created': False, 'changed': False}
        gelesen, text = None, ''
        try:
            if art.transkripte:
                geaendert = datetime.fromtimestamp(body.modified, timezone.utc) if body.modified else None
                gelesen = transkript_eingang.lesen(name, data, geaendert)
            else:
                text = extract(name, data)
        except (ValueError, UnicodeError) as exc:
            with app.state.conversation_lock:
                s = permitted(body, run=True)
                if name in s['files'] and s['digests'].get(name) != digest:
                    old = s['files'][name]
                    invalidate_with_corrections(app.state.episodes, app.state.claims, old)
                    app.state.episodes.ignore(old)
            raise HTTPException(422, str(exc)) from exc
        with app.state.conversation_lock:
            s = permitted(body, run=True)
            if name not in s['files'] and len(s['files']) >= MAX_FILES:
                raise HTTPException(422, 'Der Ordner überschreitet 2.000 Dateien.')
            key = f"{art.schluessel}:{body.root_id}:{name}"
            herkunft = Provenance(source_type=SourceType.DOCUMENT,
                                  source_ref=f"{art.herkunft}:{s['folder']}/{name}", captured_at=now())
            if gelesen is not None:
                episode, created = transkript_eingang.aufnehmen(app.state.episodes, gelesen, herkunft, key)
            else:
                episode, created = app.state.episodes.record(EpisodeKind.DOCUMENT, name, text, herkunft, source_key=key)
            changed = track_source(app.state.episodes, app.state.claims, key, episode)
            s['files'][name] = episode.id
            s['digests'][name] = digest
            s['missing'] = [item for item in s['missing'] if item != name]
            s['current']['recorded'] += int(created)
            if created:
                logbuch.vermerke('quellen', sorte='dokument' if gelesen is None else 'gespraech', anzahl=1)
            s['current']['duplicates'] += int(not created)
            s['current']['changed'] += int(changed)
            save(s)
            holen = getattr(app.state, 'zuordner_holen', None)
            if gelesen is not None and holen is not None:
                # Ein Fehler bei der Zuordnung darf die Aufnahme nicht kippen; der nächste Abgleich holt sie nach.
                try:
                    holen().vormerken(episode, gelesen.hinweise())
                except Exception:  # noqa: BLE001
                    logger.exception('Mitschrift %s konnte nicht zugeordnet werden', episode.id)
            return {'id': episode.id, 'created': created, 'changed': changed}

    @app.post(art.prefix + '/finish', dependencies=guard)
    def finish(body: FinishIn):
        observed = {filename(name, supported=False) for name in body.observed}
        if any(len(error) > 1200 for error in body.errors):
            raise HTTPException(422, 'Fehlermeldung zu lang.')
        with app.state.conversation_lock:
            s = permitted(body, run=True)
            if body.complete:
                for name, eid in list(s['files'].items()):
                    if name not in observed and name not in s['missing']:
                        invalidate_with_corrections(app.state.episodes, app.state.claims, eid)
                        app.state.episodes.ignore(eid, grund=grund)
                        s['missing'].append(name)
                        s['current']['removed'] += 1
            s['last_run'] = {**s['current'], 'errors': body.errors}
            if body.complete and not body.errors:
                s['synced_at'] = now().isoformat()
            s['run_id'] = None
            save(s)
            return public()

    # -- Ohne Mac-Helfer: im Browser wählen, selbst lesen (Befund 6) ----------------------------------------------
    from . import ordner_lokal

    def abgleichen() -> dict | None:
        """Liest einen im Browser gewählten Ordner einmal ein; derselbe Weg wie beim Helfer. `None`: nichts zu tun."""
        with app.state.conversation_lock:
            s = state()
        if not (s.get('lokal') and s.get('enabled') and s.get('folder')):
            return None
        wurzel = ordner_lokal.Path(s['folder'])
        try:
            kennung = ordner_lokal.root_id(wurzel)
        except OSError:
            kennung = None
        if kennung != s['root_id']:
            with app.state.conversation_lock:
                s = state()
                s['last_run'] = {'recorded': 0, 'duplicates': 0, 'changed': 0, 'removed': 0,
                                 'errors': ['Der Ordner ist nicht mehr da oder wurde ausgetauscht. Bitte wähle ihn erneut.']}
                save(s)
            return s['last_run']
        try:
            lauf = begin(RunIn(root_id=kennung, generation=s['generation']))['run_id']
        except HTTPException:
            return None
        abbild = ordner_lokal.lesen(wurzel, suffixes)
        fehler = list(abbild['fehler'])
        for name, daten, geaendert in abbild['dateien']:
            try:
                import_file(FileIn(root_id=kennung, generation=s['generation'], run_id=lauf, filename=name,
                                   content_base64=base64.b64encode(daten).decode(), modified=geaendert))
            except HTTPException as exc:
                if exc.status_code == 409:  # Freigabe inzwischen geändert: aufhören, nichts weiter lesen
                    return None
                fehler.append(f'{name}: {exc.detail}'[:300])
        try:
            finish(FinishIn(root_id=kennung, generation=s['generation'], run_id=lauf,
                            observed=abbild['gesehen'], errors=fehler[:30], complete=abbild['vollstaendig'] and not fehler))
        except HTTPException:
            return None
        with app.state.conversation_lock:
            s = state()
            s['seen_at'] = now().isoformat()
            save(s)
            return s.get('last_run')

    takt: dict = {}

    def takt_starten() -> None:
        """Etwa einmal pro Minute nachsehen, solange ein im Browser gewählter Ordner freigegeben ist."""
        faden = takt.get('faden')
        if faden is not None and faden.is_alive():
            return

        def laufen() -> None:
            while True:
                time.sleep(TAKT_S)
                try:
                    with app.state.conversation_lock:
                        weiter = bool(state().get('lokal'))
                    if not weiter:
                        return
                    abgleichen()
                except Exception:  # noqa: BLE001 - ein Fehler in einem Lauf darf den Takt nicht beenden
                    logger.exception('Ordner %s konnte nicht gelesen werden', art.einstellung)

        takt['faden'] = threading.Thread(target=laufen, name=f'ordner-{art.einstellung}', daemon=True)
        takt['faden'].start()

    @app.get(art.prefix + '/orte', dependencies=guard)
    def orte():
        """Orte zum Anklicken für den Weg im Browser; dazu, ob ein Helfer am Mac da ist (dann gilt dessen Dialog)."""
        with app.state.conversation_lock:
            s = state()
        orte = ordner_lokal.bekannte_orte(art.vorgabe_name, suffixes)
        container = ordner_lokal.im_container()
        return {'helfer': fresh(s.get('helfer_at'), 2), 'container': container, 'orte': orte,
                'cloud_hinweis': '' if art.transkripte else ordner_lokal.cloud_hinweis(orte, container)}

    @app.get(art.prefix + '/unterordner', dependencies=guard)
    def unterordner(pfad: str = ''):
        """Ordner durchsehen statt tippen (Fremdprobe 2, Befund 30): nur Namen von Unterordnern, nur unter den Wurzeln.
        Freigegeben wird damit nichts; das tut erst `POST …/lokal` mit dem angeklickten Ordner."""
        try:
            return ordner_lokal.unterordner(pfad or None)
        except ordner_lokal.OrdnerFehler as exc:
            return JSONResponse({'detail': exc.satz}, status_code=422)

    @app.post(art.prefix + '/lokal', dependencies=guard)
    def lokal_waehlen(body: LokalIn):
        """Gibt genau den Ordner frei, den der Mensch eben gewählt hat, und liest ihn sofort. Antwort mit einem Satz."""
        try:
            if body.vorgabe:
                if ordner_lokal.im_container():
                    raise ordner_lokal.OrdnerFehler('Kingfisher läuft hier in einem Container und sieht die Ordner deines '
                                                    'Rechners nicht. Wähle einen der Orte darunter.')
                ziel = ordner_lokal.vorgabe_ordner(art.vorgabe_name)
                try:
                    ziel.mkdir(parents=True, exist_ok=True)
                except OSError:
                    raise ordner_lokal.OrdnerFehler(f'Der Ordner {ordner_lokal.kurz(ziel)} ließ sich nicht anlegen.') from None
                pfad = ordner_lokal.pruefe_ordner(str(ziel))
            else:
                pfad = ordner_lokal.pruefe_ordner(body.pfad or '')
        except ordner_lokal.OrdnerFehler as exc:
            return JSONResponse({'detail': exc.satz}, status_code=422)
        kennung = ordner_lokal.root_id(pfad)
        with app.state.conversation_lock:
            s = state()
            if s['root_id'] != kennung or s['folder'] != str(pfad):
                entziehen(s)
                s = {**s, 'files': {}, 'digests': {}, 'missing': [], 'synced_at': None, 'last_run': None}
            s.update(root_id=kennung, folder=str(pfad), enabled=True, generation=s['generation'] + 1, run_id=None,
                     lokal=True, getrennt=False, seen_at=now().isoformat())
            s.pop('pick_request', None)
            save(s)
        lauf = abgleichen() or {}
        aufgenommen = int(lauf.get('recorded') or 0) + int(lauf.get('duplicates') or 0)
        satz = f'Freigegeben: {ordner_lokal.kurz(pfad)}. ' + (
            'Noch keine passenden Dateien darin; neue liest Kingfisher etwa einmal pro Minute.' if not aufgenommen
            else f'{aufgenommen} {"Datei" if aufgenommen == 1 else "Dateien"} gelesen; neue kommen etwa einmal pro Minute dazu.')
        takt_starten()
        with app.state.conversation_lock:
            return {**public(), 'satz': satz}

    try:
        if state().get('lokal') and state().get('enabled'):
            takt_starten()
    except Exception:  # noqa: BLE001 - ohne lesbaren Zustand gibt es nichts zu takten
        pass

    return SimpleNamespace(state=state, save=save, public=public, entziehen=entziehen, abgleichen=abgleichen)
