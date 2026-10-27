"""Eine Sicherung in der Oberfläche wiederherstellen (Persona-Prüfung, Paket P, D7, 27.10.2026).

Bis 1.0.29 entstand alle vier Stunden ein Schnappschuss (`scheduler`, `backup.snapshot_all`, Ordner `sicherungen` im
Datenordner), aber zurück kam man nur über `make zurueck-vor-update` oder einen Aufruf mit dem Namen, und danach stand
Kingfisher im Prüfmodus („historischer Sicherungsstand, nur Einsicht“). Hier der Weg für Menschen:

* **Zeigen statt tippen.** `liste` nennt die vorhandenen Sicherungen aus dem eigenen Ordner mit Zeitpunkt; gewählt wird
  in der Oberfläche, nie ein Pfad. `finden` nimmt nur Namen, wie Kingfisher sie selbst vergibt, nur unmittelbar im
  Sicherungsordner, keinen Verweis (Symlink) und keine Datei außerhalb.
* **Rückgängig.** Vor dem Wiederherstellen sichert Kingfisher den jetzigen Stand (`vor-wiederherstellung-…`, eigene
  Rotation, damit die regelmäßige Sicherung ihn nicht verdrängt). Der Hinweis danach bietet „Rückgängig“ an: Das ist das
  Wiederherstellen eben dieser Sicherung.
* **Atomar.** Erst wird die Sicherung geprüft (Manifest, Prüfsummen, `integrity_check`, Schema nicht neuer als dieser
  Code) und vollständig in einen Arbeitsordner kopiert. Dann legt ein Merkzettel (`wiederherstellung-laeuft.json`) fest,
  was ausgetauscht wird, und erst danach werden die Dateien umgehängt (`os.replace`). Bricht etwas ab, hängt
  `einspielen` alles zurück; bricht der ganze Vorgang ab (Strom, Absturz), tut es `nach_abbruch_aufraeumen` beim
  nächsten Start, bevor eine Ablage geöffnet wird. Der alte Stand gilt dann unverändert.
* **Kein Wiederaufleben alter Befugnisse.** Wiederhergestellt wird das Gedächtnis (`WIEDERHERGESTELLT`). Was Kingfisher
  darf und was es getan hat, bleibt auf dem heutigen Stand (`BLEIBT`): Einstellungen samt Einwilligungen, die
  Schlüsselablage, Dauerfreigaben (`regeln`), das Protokoll der Aktionen (`audit`), das Logbuch, ausstehende
  Kalenderaktionen und Cloud-Aufträge. Deshalb braucht dieser Weg keinen Prüfmodus: Eine alte Sicherung kann keine
  widerrufene Freigabe zurückbringen. (Der Weg über `/backups/restore` für den Rückweg nach einem Update bleibt, wie er
  ist, mit Prüfmodus.)
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backup import (BACKUP_DATA_FILES, SNAPSHOT_SET_PREFIX, SQLITE_DATA_FILES, UPDATE_SET_PREFIX, BackupError,
                     _copy_sqlite, _preflight_schema_versions, _read_snapshot_manifest, prune_all, snapshot_all,
                     verify_snapshot_set)

ORDNER = 'sicherungen'
VOR_WIEDERHERSTELLUNG = 'vor-wiederherstellung-'
#: So viele Sicherungen „vor dem Wiederherstellen“ bleiben (jede ist der Weg zurück eines Wiederherstellens).
VOR_WIEDERHERSTELLUNG_BEHALTEN = 5
JOURNAL = 'wiederherstellung-laeuft.json'
STAND = 'wiederherstellung.json'

#: Das Gedächtnis: kommt aus der Sicherung.
WIEDERHERGESTELLT = ('self-model.sqlite3', 'tasks.sqlite3', 'workspace.sqlite3', 'workspace-views.sqlite3',
                     'episodes.sqlite3', 'proposals.sqlite3', 'conversations.sqlite3', 'knowledge.sqlite3',
                     'mac-calendar.sqlite3', 'gespraeche.sqlite3', 'rueckmeldungen.sqlite3', 'lint.sqlite3')
#: Befugnisse und Protokolle: bleiben, wie sie heute sind.
BLEIBT = ('einstellungen.json', 'schluessel.icarus', 'regeln.sqlite3', 'audit.sqlite3', 'logbuch.sqlite3',
          'calendar-actions.sqlite3', 'cloud-memory-jobs.sqlite3')

_NAME = re.compile(r'(?:' + '|'.join(re.escape(p) for p in (SNAPSHOT_SET_PREFIX, UPDATE_SET_PREFIX,
                                                            VOR_WIEDERHERSTELLUNG))
                   + r')(\d{8}T\d{6}Z)(?:-\d{1,4})?')
_NEBEN = ('-wal', '-shm', '-journal')


class SicherungFehler(Exception):
    """Ein Satz für den Menschen; `status` für die Antwort."""

    def __init__(self, satz: str, status: int = 409) -> None:
        super().__init__(satz)
        self.status = status


def _art(name: str) -> str:
    if name.startswith(VOR_WIEDERHERSTELLUNG):
        return 'vor_wiederherstellung'
    if name.startswith(UPDATE_SET_PREFIX):
        return 'vor_update'
    return 'regelmaessig'


def liste(data_dir: Path) -> list[dict[str, Any]]:
    """Die wiederherstellbaren Sicherungen im eigenen Ordner, neueste zuerst; ohne Pfad."""
    ordner = Path(data_dir) / ORDNER
    if not ordner.is_dir() or ordner.is_symlink():
        return []
    eintraege = []
    for pfad in ordner.iterdir():
        if not _NAME.fullmatch(pfad.name) or pfad.is_symlink() or not pfad.is_dir():
            continue
        try:
            manifest = _read_snapshot_manifest(pfad)
        except BackupError:
            continue
        eintraege.append({'name': pfad.name, 'erstellt': str(manifest.get('created_at') or ''), 'art': _art(pfad.name),
                          'bytes': sum(k.stat().st_size for k in pfad.iterdir() if k.is_file())})
    return sorted(eintraege, key=lambda e: (e['erstellt'], e['name']), reverse=True)


def finden(data_dir: Path, name: str) -> Path:
    """Die Sicherung mit diesem Namen im eigenen Ordner; sonst `SicherungFehler`. Nie ein Pfad von außen."""
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise SicherungFehler('Diese Sicherung gibt es nicht. Bitte eine aus der Liste wählen.', 404)
    ordner = Path(data_dir) / ORDNER
    if ordner.is_symlink() or not ordner.is_dir():
        raise SicherungFehler('Diese Sicherung gibt es nicht. Bitte eine aus der Liste wählen.', 404)
    ziel = ordner / name
    if ziel.is_symlink() or not ziel.is_dir() or ziel.resolve().parent != ordner.resolve():
        raise SicherungFehler('Diese Sicherung gibt es nicht. Bitte eine aus der Liste wählen.', 404)
    if any(kind.is_symlink() for kind in ziel.iterdir()):
        raise SicherungFehler('Diese Sicherung enthält einen Verweis nach außen und wird nicht verwendet.')
    return ziel


def _jetzt(at: datetime | None) -> datetime:
    return at or datetime.now(timezone.utc)


def _schreiben(pfad: Path, daten: dict[str, Any]) -> None:
    vorlaeufig = pfad.with_name(pfad.name + '.neu')
    with open(vorlaeufig, 'w', encoding='utf-8') as datei:
        json.dump(daten, datei, ensure_ascii=False)
        datei.flush()
        os.fsync(datei.fileno())
    os.replace(vorlaeufig, pfad)
    try:
        fd = os.open(pfad.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def nach_abbruch_aufraeumen(data_dir: Path) -> bool:
    """Steht noch ein Merkzettel da, brach ein Wiederherstellen ab: alles zurückhängen. True, wenn etwas zu tun war."""
    data_dir = Path(data_dir)
    journal = data_dir / JOURNAL
    if not journal.exists():
        return False
    try:
        eintraege = json.loads(journal.read_text(encoding='utf-8')).get('dateien') or []
    except (OSError, ValueError):
        eintraege = []
    erlaubt = set(BACKUP_DATA_FILES) | {n + s for n in BACKUP_DATA_FILES for s in _NEBEN}
    for eintrag in reversed(eintraege):
        name, beiseite = str(eintrag.get('name') or ''), str(eintrag.get('beiseite') or '')
        if name not in erlaubt or Path(name).name != name or Path(beiseite).name != beiseite:
            continue
        ziel, alt = data_dir / name, data_dir / beiseite
        if beiseite and alt.exists():
            os.replace(alt, ziel)
        elif not beiseite and eintrag.get('neu') and ziel.exists():
            # Vorher gab es die Datei nicht: Was eingespielt wurde, gehört nicht zum alten Stand.
            ziel.unlink()
    for rest in data_dir.glob('.wiederherstellung-*.partial'):
        shutil.rmtree(rest, ignore_errors=True)
    journal.unlink(missing_ok=True)
    return True


def einspielen(sicherung: Path, data_dir: Path, *, at: datetime | None = None) -> list[str]:
    """Tauscht die Dateien des Gedächtnisses gegen die der Sicherung; alles oder nichts. Die eingespielten Namen."""
    data_dir = Path(data_dir)
    eintraege = [e for e in verify_snapshot_set(sicherung) if e['name'] in WIEDERHERGESTELLT]
    if not any(e['kind'] == 'sqlite' for e in eintraege):
        raise SicherungFehler('Diese Sicherung enthält kein Gedächtnis.')
    _preflight_schema_versions(eintraege)
    stempel = _jetzt(at).strftime('%Y%m%dT%H%M%SZ')
    arbeit = data_dir / f'.wiederherstellung-{stempel}.partial'
    if (data_dir / JOURNAL).exists() or arbeit.exists():
        raise SicherungFehler('Eine Wiederherstellung läuft bereits.')
    arbeit.mkdir(mode=0o700)
    journal: list[dict[str, Any]] = []
    try:
        # 1. Alles in den Arbeitsordner, geprüft. Bis hierher ist nichts verändert.
        for eintrag in eintraege:
            ziel = arbeit / eintrag['name']
            if eintrag['kind'] == 'sqlite':
                _copy_sqlite(eintrag['path'], ziel, immutable_source=True)
            else:
                shutil.copy2(eintrag['path'], ziel)
        neue = {e['name'] for e in eintraege}
        # 2. Der Merkzettel: was beiseitegelegt und was eingehängt wird. Erst danach wird umgehängt.
        plan = []
        for name in WIEDERHERGESTELLT:
            for teil in (name, *(name + s for s in _NEBEN)):
                vorhanden = (data_dir / teil).exists()
                if vorhanden or (teil == name and name in neue):
                    plan.append({'name': teil,
                                 'beiseite': f'.{teil}.vor-wiederherstellung-{stempel}' if vorhanden else '',
                                 'neu': teil == name and name in neue})
        _schreiben(data_dir / JOURNAL, {'stempel': stempel, 'dateien': plan})
        # 3. Umhängen. Jeder Schritt steht im Merkzettel, bevor er geschieht.
        for schritt in plan:
            ziel = data_dir / schritt['name']
            if schritt['beiseite']:
                os.replace(ziel, data_dir / schritt['beiseite'])
            journal.append(schritt)
            if schritt['neu']:
                os.replace(arbeit / schritt['name'], ziel)
    except BaseException:
        # Zurück zum alten Stand, dann den Merkzettel weg.
        nach_abbruch_aufraeumen(data_dir)
        shutil.rmtree(arbeit, ignore_errors=True)
        raise
    # 4. Fertig: Merkzettel zuerst weg (ab jetzt gilt der neue Stand), dann die beiseitegelegten Dateien.
    (data_dir / JOURNAL).unlink()
    for schritt in plan:
        if schritt['beiseite']:
            (data_dir / schritt['beiseite']).unlink(missing_ok=True)
    shutil.rmtree(arbeit, ignore_errors=True)
    return sorted(neue)


def wiederherstellen(data_dir: Path, name: str, *, at: datetime | None = None) -> dict[str, Any]:
    """Prüft, sichert den jetzigen Stand und spielt die Sicherung ein. Die Antwort sagt, welcher Stand jetzt gilt."""
    data_dir = Path(data_dir)
    sicherung = finden(data_dir, name)
    try:
        manifest = _read_snapshot_manifest(sicherung)
        verify_snapshot_set(sicherung)
    except BackupError as fehler:
        raise SicherungFehler('Diese Sicherung ist beschädigt oder unvollständig. Es wurde nichts verändert.') from fehler
    try:
        vorher = snapshot_all(data_dir, data_dir / ORDNER, keep=VOR_WIEDERHERSTELLUNG_BEHALTEN,
                              at=_jetzt(at), prefix=VOR_WIEDERHERSTELLUNG)
    except (BackupError, OSError) as fehler:
        raise SicherungFehler('Der jetzige Stand ließ sich nicht sichern, deshalb wurde nichts wiederhergestellt. '
                              'Ist genug Platz frei?') from fehler
    try:
        einspielen(sicherung, data_dir, at=at)
    except SicherungFehler:
        raise
    except BackupError as fehler:
        raise SicherungFehler(f'Nicht wiederhergestellt: {fehler} Es gilt weiter der bisherige Stand.') from fehler
    except OSError as fehler:
        raise SicherungFehler('Nicht wiederhergestellt; es gilt weiter der bisherige Stand. '
                              'Bitte prüfe, ob genug Platz frei ist.') from fehler
    stand = {'name': sicherung.name, 'stand': str(manifest.get('created_at') or ''), 'art': _art(sicherung.name),
             'am': _jetzt(at).astimezone().isoformat(timespec='seconds'), 'rueckgaengig': vorher.name}
    _schreiben(data_dir / STAND, stand)
    return stand


def zuletzt(data_dir: Path) -> dict[str, Any] | None:
    """Welcher Stand seit dem letzten Wiederherstellen gilt (für Einstellungen → Sicherung)."""
    try:
        daten = json.loads((Path(data_dir) / STAND).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return daten if isinstance(daten, dict) else None


__all__ = ['BLEIBT', 'JOURNAL', 'SicherungFehler', 'VOR_WIEDERHERSTELLUNG', 'WIEDERHERGESTELLT', 'einspielen',
           'finden', 'liste', 'nach_abbruch_aufraeumen', 'wiederherstellen', 'zuletzt']

_ = (SQLITE_DATA_FILES, prune_all)
