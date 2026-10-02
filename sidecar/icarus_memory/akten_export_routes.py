"""Verdrahtung von „Akten als Ordner“ (M2): Einstellung, Schreiben, Übergabe an den Mac-Helfer.

Die Regeln für Inhalt und Dateien stehen in `akten_markdown.py`. Hier steht, wann und wohin geschrieben wird.

**Zwei Schritte, weil der Sidecar im Container läuft.** Er kann keinen Ordner auf dem Mac beschreiben und
soll es auch nicht können. Deshalb:

1. Der Sidecar erzeugt den Ordner atomar in seinem eigenen Datenbereich (`<Daten>/akten-export`).
2. Der Mac-Helfer (`scripts/mac_folder_worker.py --role akten`) holt ihn ab (`GET …/archiv`) und legt ihn im
   vom Nutzer gewählten Ordner als Unterordner `Kingfisher Akten` ab, ebenfalls atomar. Er ersetzt nur einen
   Ordner mit der Marke `.kingfisher-akten`, nie fremde Dateien.

Den Ordner wählt der Nutzer im Auswahldialog des Mac (Anfrage `POST …/ordner`, Antwort des Helfers
`POST …/worker`), nie getippt. Das Auswählen ist die Freigabe dieses einen Ordners.

Routen:

* `GET  /api/v1/akten/export`: Stand, Dateizahl, Ordner, Schalter, ob der Helfer sich meldet.
* `PUT  /api/v1/akten/export`: `aktiv`, `quellen` („Quellen mitschreiben“, Rohtext).
* `POST /api/v1/akten/export`: „Jetzt schreiben“.
* `POST /api/v1/akten/export/ordner`, `DELETE …/ordner/auswahl`, `DELETE …/ordner`: Ordner wählen, Wahl
  abbrechen, trennen (die Dateien auf dem Mac bleiben liegen).
* `POST …/worker`, `GET …/archiv`, `POST …/gespiegelt`: Protokoll des Mac-Helfers.

**Wann geschrieben wird:** nach jedem Nachführen der Akten (`akten_routes.nachfuehren` ruft `anstossen`), aber
nur bei eingeschaltetem Schalter und gewähltem Ordner, nur wenn sich im Bestand etwas geändert hat, höchstens
alle `DROSSEL_S` Sekunden und nie zweimal gleichzeitig. Auf Knopfdruck sofort.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from . import akten_markdown, config

#: Frühestens so viele Sekunden zwischen zwei selbsttätigen Läufen.
DROSSEL_S = 120.0
#: So lange wartet „Jetzt schreiben“ auf das Ende, bevor es „läuft noch“ meldet.
WARTEN_S = 10.0
#: So lange gilt eine Anfrage „Ordner wählen“, bis der Mac-Helfer geantwortet hat.
PICK_MINUTEN = 10
VORGABE = 'Dokumente/Kingfisher/Akten'
STAGING = 'akten-export'

#: Gemeinsame Zustände je App: Sperren, laufender Faden, Anfrage „Ordner wählen“, Meldung des Helfers.
_INIT = threading.Lock()


class EinstellungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    aktiv: bool | None = None
    quellen: bool | None = None


class OrdnerIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    modus: Literal['vorgabe', 'waehlen']


class WorkerIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    folder: str | None = Field(default=None, max_length=1000)
    picked: str | None = Field(default=None, max_length=64)
    cancelled: str | None = Field(default=None, max_length=64)


class GespiegeltIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paket: str = Field(max_length=64)
    dateien: int = Field(default=0, ge=0, le=10_000_000)
    fehler: str | None = Field(default=None, max_length=300)


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _fluechtig(app) -> dict[str, Any]:
    """Was nur im Speicher lebt: Sperren, Faden, Wahlanfrage, letzte Meldung des Helfers."""
    with _INIT:
        if getattr(app.state, 'akten_export_fluechtig', None) is None:
            app.state.akten_export_fluechtig = {
                'bau': threading.Lock(),        # nie zwei Läufe gleichzeitig
                'tausch': threading.RLock(),    # Austausch des Ordners und Packen des Archivs schließen sich aus
                'faden': None, 'timer': False, 'letzter_start': float('-inf'), 'nachstand': None,
                'pick_request': None, 'seen_at': None, 'fehler': None, 'spiegel_fehler': None}
        return app.state.akten_export_fluechtig


def _einstellung(app) -> dict[str, Any]:
    roh = app.state.settings.akten_export if isinstance(app.state.settings.akten_export, dict) else {}
    return {'aktiv': roh.get('aktiv') is True, 'quellen': roh.get('quellen') is True,
            'ordner': roh.get('ordner') if isinstance(roh.get('ordner'), str) and roh.get('ordner') else None,
            'stand': roh.get('stand') if isinstance(roh.get('stand'), dict) else None,
            'gespiegelt': roh.get('gespiegelt') if isinstance(roh.get('gespiegelt'), dict) else None}


def _speichern(app, data_dir, neu: dict[str, Any]) -> None:
    vorher = app.state.settings.akten_export
    app.state.settings.akten_export = neu
    try:
        config.save(data_dir(), app.state.settings)
    except Exception:
        app.state.settings.akten_export = vorher
        raise HTTPException(500, 'Die Einstellung konnte nicht gespeichert werden.') from None


def _frisch(wert: str | None, minuten: float) -> bool:
    if not wert:
        return False
    try:
        return _jetzt() - datetime.fromisoformat(wert) < timedelta(minutes=minuten)
    except ValueError:
        return False


def oeffentlich(app) -> dict[str, Any]:
    """Der Stand für die Oberfläche: nur Zahlen, Zeiten und der gewählte Ordner, nie Akteninhalt."""
    e, f = _einstellung(app), _fluechtig(app)
    pick = f['pick_request']
    stand = e['stand']
    gespiegelt = e['gespiegelt']
    angekommen = bool(stand and gespiegelt and gespiegelt.get('paket') == stand.get('paket'))
    return {
        'aktiv': e['aktiv'], 'quellen': e['quellen'], 'ordner': e['ordner'],
        'ordnername': akten_markdown.ORDNERNAME, 'vorgabe': VORGABE,
        'laeuft': f['bau'].locked(),
        'running': _frisch(f['seen_at'], 2),
        'pick_request': ({'id': pick['id'], 'modus': pick['modus']}
                         if pick and _frisch(pick.get('at'), PICK_MINUTEN) else None),
        'stand': ({'erzeugt_am': stand.get('erzeugt_am'), 'dateien': stand.get('dateien', 0),
                   'akten': stand.get('akten', 0), 'mit_quellen': bool(stand.get('mit_quellen')),
                   'uebersprungen': stand.get('uebersprungen', 0)} if stand else None),
        'gespiegelt': ({'am': gespiegelt.get('am'), 'dateien': gespiegelt.get('dateien', 0)}
                       if angekommen else None),
        'angekommen': angekommen,
        'fehler': f['fehler'] or (f['spiegel_fehler'] or {}).get('text'),
    }


# -- Schreiben --

def _paket(dateien: dict[str, str]) -> str:
    summe = hashlib.sha256()
    for pfad in sorted(dateien):
        summe.update(pfad.encode('utf-8') + b'\0' + dateien[pfad].encode('utf-8') + b'\0')
    return summe.hexdigest()[:32]


def staging(data_dir) -> Path:
    return Path(data_dir()) / STAGING


def lauf(app, data_dir, *, grund: str = 'auto') -> bool:
    """Ein Schreiblauf: Akten sammeln, Ordner bauen, atomar ablegen, Stand vermerken.

    Gibt False zurück, wenn schon ein Lauf läuft (nie zweimal gleichzeitig). Ändert sich nichts am Inhalt
    (gleiches Paket), wird nichts neu abgelegt und dem Helfer nichts Neues angeboten.
    """
    f = _fluechtig(app)
    if not f['bau'].acquire(blocking=False):
        return False
    try:
        e = _einstellung(app)
        f['letzter_start'] = time.monotonic()
        f['fehler'] = None
        try:
            from .akten_routes import bausteine
            from .lage_routes import lagen_von
            from . import __version__
            bezuege, akten = bausteine(app)
            jetzt = _jetzt()
            liste, letzte, uebersprungen = akten_markdown.sammeln(akten, bezuege, lagen_von(app), jetzt=jetzt)
            info, text = akten_markdown.quellen_lieferant(app.state.episodes)
            from .model import user_timezone
            stand_tag = jetzt.astimezone(user_timezone() or timezone.utc).date()
            dateien = akten_markdown.bauen(liste, stand=stand_tag, version=__version__, info=info,
                                           text=text if e['quellen'] else None, letzte=letzte)
            paket = _paket(dateien)
            vorher = e['stand'] or {}
            if vorher.get('paket') != paket or not staging(data_dir).is_dir():
                with f['tausch']:
                    akten_markdown.aufraeumen(staging(data_dir))
                    akten_markdown.schreiben(staging(data_dir), dateien)
                    neu = {'erzeugt_am': jetzt.isoformat(), 'paket': paket, 'dateien': len(dateien),
                           'akten': len(liste), 'mit_quellen': e['quellen'], 'uebersprungen': uebersprungen}
                    with app.state.conversation_lock:
                        aktuell = _einstellung(app)
                        _speichern(app, data_dir, {**_roh(aktuell), 'stand': neu})
                f['spiegel_fehler'] = None
            f['nachstand'] = bezuege.aenderungsstand()
        except Exception:  # noqa: BLE001 - Keine Akteninhalte in Meldungen; der nächste Lauf versucht es erneut.
            f['fehler'] = 'Die Akten konnten nicht als Ordner geschrieben werden. Ein neuer Versuch folgt.'
            return True
        return True
    finally:
        f['bau'].release()


def _roh(e: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in e.items() if v is not None}


def starten(app, data_dir, *, grund: str = 'auto') -> threading.Thread | None:
    """Startet einen Lauf im Hintergrund, falls keiner läuft. Gibt den Faden zurück (oder None)."""
    f = _fluechtig(app)
    if f['bau'].locked():
        return f['faden']
    faden = threading.Thread(target=lambda: lauf(app, data_dir, grund=grund), name='akten-export', daemon=True)
    f['faden'] = faden
    faden.start()
    return faden


def anstossen(app, data_dir) -> None:
    """Der Einbau bei `akten_routes.nachfuehren`: schreibt, wenn es an ist, etwas Neues da ist und die Drossel es erlaubt.

    Billig, wenn es aus ist (ein Blick in die Einstellung). Höchstens ein Lauf gleichzeitig und höchstens
    einer je `DROSSEL_S`; ein wegen der Drossel übergangener Anstoß wird nachgeholt (ein Zeitgeber, nie mehr).
    """
    e = _einstellung(app)
    if not (e['aktiv'] and e['ordner']):
        return
    f = _fluechtig(app)
    from .akten_routes import bausteine
    bezuege, _ = bausteine(app)
    if e['stand'] and f['nachstand'] == bezuege.aenderungsstand() and e['stand'].get('mit_quellen') == e['quellen']:
        return
    if f['bau'].locked():
        return
    rest = DROSSEL_S - (time.monotonic() - f['letzter_start'])
    if rest > 0:
        with _INIT:
            if f['timer']:
                return
            f['timer'] = True

        def nachholen() -> None:
            f['timer'] = False
            try:
                anstossen(app, data_dir)
            except Exception:  # noqa: BLE001 - der nächste Anstoß versucht es erneut
                pass
        zeitgeber = threading.Timer(rest + 0.5, nachholen)
        zeitgeber.daemon = True
        zeitgeber.start()
        return
    starten(app, data_dir)


# -- Archiv für den Helfer --

def archiv(app, data_dir) -> tuple[bytes, str] | None:
    """Der fertige Ordner als ZIP (feste Reihenfolge, feste Zeit) und sein Paket; None, wenn noch keiner da ist."""
    f = _fluechtig(app)
    with f['tausch']:
        stand = _einstellung(app)['stand']
        wurzel = staging(data_dir)
        if not stand or not wurzel.is_dir():
            return None
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for datei in sorted(p for p in wurzel.rglob('*') if p.is_file()):
                info = zipfile.ZipInfo(datei.relative_to(wurzel).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, datei.read_bytes())
        return puffer.getvalue(), stand['paket']


# -- Verdrahtung --

def register(app, guard, data_dir) -> None:
    from . import akten_routes
    _fluechtig(app)
    app.state.akten_export_anstossen = lambda: anstossen(app, data_dir)
    aufraeumen = staging(data_dir)
    akten_markdown.aufraeumen(aufraeumen)

    @app.get('/api/v1/akten/export', dependencies=guard)
    def export_stand() -> dict[str, Any]:
        return oeffentlich(app)

    @app.put('/api/v1/akten/export', dependencies=guard)
    def export_setzen(body: EinstellungIn) -> dict[str, Any]:
        neu_quellen = False
        with app.state.conversation_lock:
            e = _einstellung(app)
            if body.aktiv and not e['ordner']:
                raise HTTPException(409, 'Bitte zuerst einen Ordner wählen.')
            aenderung = {}
            if body.aktiv is not None:
                aenderung['aktiv'] = body.aktiv
            if body.quellen is not None:
                aenderung['quellen'] = body.quellen
                neu_quellen = body.quellen != e['quellen']
            _speichern(app, data_dir, {**_roh(e), **aenderung})
            einschalten = bool(body.aktiv and not e['aktiv'])
        if (einschalten or neu_quellen) and _einstellung(app)['ordner'] and _einstellung(app)['aktiv']:
            starten(app, data_dir, grund='schalter')
        return oeffentlich(app)

    @app.post('/api/v1/akten/export', dependencies=guard)
    def jetzt_schreiben() -> dict[str, Any]:
        """„Jetzt schreiben“: sofort einen Lauf; nach `WARTEN_S` Sekunden meldet die Antwort `laeuft`."""
        e = _einstellung(app)
        if not e['ordner']:
            raise HTTPException(409, 'Bitte zuerst einen Ordner wählen.')
        f = _fluechtig(app)
        f['spiegel_fehler'] = None
        # Auch ohne neue Inhalte neu anbieten: Wer drückt, will den Ordner frisch haben.
        with app.state.conversation_lock:
            if e['gespiegelt'] is not None:
                _speichern(app, data_dir, {**_roh(e), 'gespiegelt': None})
        akten_routes.nachfuehren(app, warten=False)
        faden = starten(app, data_dir, grund='knopf')
        if faden is not None:
            faden.join(timeout=WARTEN_S)
        return oeffentlich(app)

    @app.post('/api/v1/akten/export/ordner', dependencies=guard)
    def ordner_waehlen(body: OrdnerIn) -> dict[str, Any]:
        """Bittet den Mac-Helfer, den Auswahldialog zu zeigen (oder den Vorgabeordner anzulegen)."""
        f = _fluechtig(app)
        f['pick_request'] = {'id': uuid.uuid4().hex, 'modus': body.modus, 'at': _jetzt().isoformat()}
        return oeffentlich(app)

    @app.delete('/api/v1/akten/export/ordner/auswahl', dependencies=guard)
    def auswahl_abbrechen() -> dict[str, Any]:
        _fluechtig(app)['pick_request'] = None
        return oeffentlich(app)

    @app.delete('/api/v1/akten/export/ordner', dependencies=guard)
    def ordner_trennen() -> dict[str, Any]:
        """Trennt den Ordner und schaltet aus. Die Dateien auf dem Mac bleiben liegen; nichts wird gelöscht."""
        f = _fluechtig(app)
        with app.state.conversation_lock:
            e = _einstellung(app)
            _speichern(app, data_dir, {'quellen': e['quellen']})
        with f['tausch']:
            shutil.rmtree(staging(data_dir), ignore_errors=True)
        f.update(nachstand=None, pick_request=None, spiegel_fehler=None, fehler=None)
        return oeffentlich(app)

    @app.post('/api/v1/akten/export/worker', dependencies=guard)
    def worker(body: WorkerIn) -> dict[str, Any]:
        """Meldung des Mac-Helfers: lebt, hat (vielleicht) einen Ordner gewählt. Antwort: was er abholen soll."""
        f = _fluechtig(app)
        f['seen_at'] = _jetzt().isoformat()
        pick = f['pick_request']
        if body.cancelled and pick and pick.get('id') == body.cancelled:
            f['pick_request'] = pick = None
        wahl = bool(body.picked and pick and _frisch(pick.get('at'), PICK_MINUTEN) and pick.get('id') == body.picked)
        if wahl and body.folder and body.folder.startswith('/') and '\x00' not in body.folder:
            # Das Auswählen im Dialog ist die ausdrückliche Freigabe dieses einen Ordners.
            with app.state.conversation_lock:
                e = _einstellung(app)
                _speichern(app, data_dir, {**_roh(e), 'ordner': body.folder, 'aktiv': True, 'gespiegelt': None})
            f['pick_request'] = None
            f['spiegel_fehler'] = None
            f['nachstand'] = None
            starten(app, data_dir, grund='ordner')
        e = _einstellung(app)
        stand, gespiegelt = e['stand'], e['gespiegelt']
        offen = bool(e['aktiv'] and e['ordner'] and stand and (gespiegelt or {}).get('paket') != stand['paket']
                     and (f['spiegel_fehler'] or {}).get('paket') != stand['paket'])
        return {**oeffentlich(app), 'abholen': stand['paket'] if offen else None,
                'ordnername': akten_markdown.ORDNERNAME}

    @app.get('/api/v1/akten/export/archiv', dependencies=guard)
    def export_archiv() -> Response:
        """Der fertige Ordner als ZIP, für den Mac-Helfer. Das Paket steht im Kopf `X-Akten-Paket`."""
        gepackt = archiv(app, data_dir)
        if gepackt is None:
            raise HTTPException(404, 'Es gibt noch keinen fertigen Ordner.')
        daten, paket = gepackt
        return Response(daten, media_type='application/zip', headers={'X-Akten-Paket': paket})

    @app.post('/api/v1/akten/export/gespiegelt', dependencies=guard)
    def gespiegelt(body: GespiegeltIn) -> dict[str, Any]:
        """Der Helfer meldet: Ordner abgelegt (oder aus welchem Grund nicht). Eine veraltete Meldung zählt nicht."""
        f = _fluechtig(app)
        with app.state.conversation_lock:
            e = _einstellung(app)
            if not e['stand'] or e['stand'].get('paket') != body.paket:
                return oeffentlich(app)
            if body.fehler:
                f['spiegel_fehler'] = {'paket': body.paket, 'text': body.fehler}
            else:
                f['spiegel_fehler'] = None
                _speichern(app, data_dir, {**_roh(e), 'gespiegelt': {'am': _jetzt().isoformat(), 'paket': body.paket,
                                                                        'dateien': body.dateien}})
        return oeffentlich(app)


__all__ = ['DROSSEL_S', 'VORGABE', 'anstossen', 'archiv', 'lauf', 'oeffentlich', 'register', 'starten']
