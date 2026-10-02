"""Ordner ohne Mac-Helfer: im Browser wählen, vom Sidecar selbst lesen (Fremdprobe, Befund 6).

Mit Docker und Browser (Startweg aus der README) gibt es weder den Auswahldialog des Mac noch den Mac-Helfer, der die
Dateien eines Ordners an den Sidecar schickt. Früher stand dann auch für den Vorgabeordner „Bitte wähle den Ordner im
Fenster, das sich auf deinem Mac geöffnet hat“, und es geschah nichts.

Jetzt geht es auch im Browser:

* **Bekannte Orte** (`bekannte_orte`): der Vorgabeordner im eigenen Dokumente-Ordner (nur, wenn der Sidecar nicht im
  Container läuft; dort wäre es nicht der Ordner des Nutzers) und die Ordner, die ein Techniker für Kingfisher
  eingebunden hat (`KINGFISHER_ORDNER`, durch `:` getrennt, etwa `/ordner` im Container), samt ihrer Unterordner.
  Angezeigt wird nur, was es gibt und was lesbar ist; der Vorgabeordner darf noch fehlen, er wird beim Klick angelegt.
* **Cloud-Ordner** (`cloud_orte`, M4): OneDrive, Google Drive und iCloud Drive liegen auf dem Mac als Ordner
  (`~/Library/CloudStorage/OneDrive-*`, `~/Library/CloudStorage/GoogleDrive-*`, `~/Library/Mobile Documents/
  com~apple~CloudDocs`). Was es davon gibt, steht als Vorschlag zum Anklicken da, mit lesbarem Namen („OneDrive
  (Hochschule)“). Gelesen wird erst, was der Mensch anklickt; die Dateien bleiben, wo sie sind. Eine Datei, die nur in
  der Cloud liegt (auf dem Mac ohne lokalen Inhalt), wird nicht heruntergeladen, sondern übersprungen. Im Container
  sieht Kingfisher diese Ordner nicht; ein Techniker kann sie einbinden (`KINGFISHER_ORDNER`), dann tragen sie
  denselben lesbaren Namen.
* **Ordner durchsehen** (`unterordner`, Fremdprobe 2, Befund 30): statt einen Pfad zu tippen, klickt man sich vom
  Benutzerordner (bzw. von den eingebundenen Ordnern) aus durch die Unterordner, wie in einem Auswahldialog. Gezeigt
  werden nur Namen von Ordnern, nie Dateien, und nur unterhalb dieser Wurzeln; versteckte Ordner und Verweise nicht.
* **Eigene Eingabe** (`pruefe_ordner`): ein getippter Pfad wird geprüft (da, ein Ordner, kein Verweis, lesbar), und die
  Antwort ist ein Satz.
* **Lesen** (`lesen`): derselbe Weg in den Bestand wie beim Mac-Helfer (`folder_sync.py`: begin, files, finish), nur
  dass der Sidecar die Dateien selbst liest, einmal sofort und dann etwa einmal pro Minute.

Die Sicherheitszusage bleibt: Gelesen wird nur ein Ordner, den der Mensch eben ausgewählt hat (Klick auf einen Ort
oder auf „Diesen Ordner verwenden“). Nichts wird von selbst freigegeben, auch nicht ein eingebundener Ordner.
"""
from __future__ import annotations

import hashlib
import os
import stat
import time
from collections.abc import Mapping
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
MAX_DATEIEN = 2000
MAX_ORTE = 24
VORGABE_TEILE = ('Documents', 'Kingfisher')
"""Unter dem Benutzerverzeichnis; dahinter der Name des Ordners (`Transkripte`, `Dokumente`)."""


class OrdnerFehler(Exception):
    """Der Ordner lässt sich nicht verwenden. `satz` ist für den Nutzer."""

    def __init__(self, satz: str) -> None:
        super().__init__(satz)
        self.satz = satz


def im_container() -> bool:
    return Path('/.dockerenv').exists() or bool(os.environ.get('container'))


def kurz(pfad: Path, home: Path | None = None) -> str:
    """Der Pfad, wie ein Mensch ihn liest: `~/Documents/Kingfisher/Transkripte` statt des vollen Pfads."""
    home = home or Path.home()
    try:
        return '~/' + str(pfad.relative_to(home)) if pfad != home else '~'
    except ValueError:
        return str(pfad)


def vorgabe_ordner(name: str, home: Path | None = None) -> Path:
    return Path(home or Path.home()).joinpath(*VORGABE_TEILE, name)


def _lesbar(pfad: Path) -> bool:
    try:
        info = os.lstat(pfad)
        return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and os.access(pfad, os.R_OK | os.X_OK)
    except OSError:
        return False


def _zaehlen(pfad: Path, endungen: frozenset[str] | set[str], grenze: int = 500) -> int:
    anzahl = 0
    try:
        for wurzel, ordner, dateien in os.walk(pfad, followlinks=False):
            ordner[:] = [o for o in ordner if not o.startswith('.')]
            anzahl += sum(1 for d in dateien if not d.startswith('.') and Path(d).suffix.lower() in endungen)
            if anzahl >= grenze:
                return anzahl
    except OSError:
        return anzahl
    return anzahl


#: macOS-Kennzeichen einer Datei, deren Inhalt nur in der Cloud liegt (SF_DATALESS): Lesen würde sie herunterladen.
NUR_IN_DER_CLOUD = 0x40000000
_GOOGLE_ABLAGE = ('My Drive', 'Meine Ablage')


def cloud_name(pfad: Path) -> tuple[str, str] | None:
    """(Dienst, lesbarer Name) eines synchronisierten Cloud-Ordners, sonst None. Rein, nur am Namen."""
    teile = pfad.parts
    for nummer, teil in enumerate(teile):
        if teil.startswith('OneDrive'):
            zusatz = teil[len('OneDrive'):].lstrip('-– ').strip()
            return 'onedrive', f'OneDrive ({zusatz})' if zusatz else 'OneDrive'
        if teil.startswith('GoogleDrive-'):
            konto = teil[len('GoogleDrive-'):]
            rest = teile[nummer + 1:]
            return 'google_drive', f'Google Drive ({konto})' + (f', {rest[0]}' if rest and rest[0] not in _GOOGLE_ABLAGE else '')
        if teil == 'com~apple~CloudDocs' or teil == 'iCloud Drive':
            return 'icloud', 'iCloud Drive'
    return None


def cloud_orte(home: Path | None = None) -> list[Path]:
    """Die synchronisierten Cloud-Ordner im Benutzerverzeichnis, die es gibt und die lesbar sind (Mac)."""
    home = Path(home or Path.home())
    gefunden: list[Path] = []
    speicher = home / 'Library' / 'CloudStorage'
    try:
        eintraege = sorted(speicher.iterdir()) if _lesbar(speicher) else []
    except OSError:
        eintraege = []
    for eintrag in eintraege:
        if eintrag.name.startswith('OneDrive') and _lesbar(eintrag):
            gefunden.append(eintrag)
        elif eintrag.name.startswith('GoogleDrive-') and _lesbar(eintrag):
            ablage = next((eintrag / n for n in _GOOGLE_ABLAGE if _lesbar(eintrag / n)), eintrag)
            gefunden.append(ablage)
    icloud = home / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
    if _lesbar(icloud):
        gefunden.append(icloud)
    return gefunden


def cloud_hinweis(orte: list[dict], container: bool) -> str:
    """Ein ehrlicher Satz, wenn kein Cloud-Ordner zum Anklicken da ist; sonst leer."""
    if any(o.get('cloud') for o in orte):
        return ''
    if container:
        return ('Kingfisher läuft hier in einem Container und sieht OneDrive, Google Drive und iCloud Drive auf deinem '
                'Rechner nicht. Ein Techniker kann einen dieser Ordner einbinden; dann steht er hier zum Anklicken.')
    return 'Auf diesem Rechner hat Kingfisher keinen Ordner von OneDrive, Google Drive oder iCloud Drive gefunden.'


def bekannte_orte(name: str, endungen: frozenset[str] | set[str], *, home: Path | None = None,
                  umgebung: Mapping[str, str] | None = None, container: bool | None = None) -> list[dict]:
    """Orte zum Anklicken. Nur, was es gibt und was lesbar ist; der Vorgabeordner darf fehlen (er wird angelegt)."""
    umgebung = os.environ if umgebung is None else umgebung
    container = im_container() if container is None else container
    orte: list[dict] = []
    if not container:
        vorgabe = vorgabe_ordner(name, home)
        da = _lesbar(vorgabe)
        if da or not vorgabe.exists():
            orte.append({'pfad': str(vorgabe), 'name': kurz(vorgabe, home), 'da': da, 'vorgabe': True,
                         'dateien': _zaehlen(vorgabe, endungen) if da else 0})
        # Cloud-Ordner nur als Vorschlag: Freigegeben wird erst, was der Mensch anklickt.
        for pfad in cloud_orte(home):
            dienst, lesbar = cloud_name(pfad) or ('', kurz(pfad, home))
            orte.append({'pfad': str(pfad), 'name': lesbar, 'da': True, 'vorgabe': False, 'cloud': dienst,
                         'dateien': _zaehlen(pfad, endungen)})
    for roh in (umgebung.get('KINGFISHER_ORDNER') or '').split(os.pathsep):
        wurzel = Path(roh.strip()).expanduser() if roh.strip() else None
        if wurzel is None or not wurzel.is_absolute() or not _lesbar(wurzel):
            continue
        kandidaten = [wurzel]
        try:
            kandidaten += sorted(p for p in wurzel.iterdir() if not p.name.startswith('.') and _lesbar(p))
        except OSError:
            pass
        for pfad in kandidaten:
            if len(orte) >= MAX_ORTE:
                break
            if any(o['pfad'] == str(pfad) for o in orte):
                continue
            dienst, lesbar = cloud_name(pfad) or ('', kurz(pfad, home))
            orte.append({'pfad': str(pfad), 'name': lesbar, 'da': True, 'vorgabe': False, 'cloud': dienst,
                         'dateien': _zaehlen(pfad, endungen)})
    return orte


MAX_UNTERORDNER = 300


def wurzeln(*, home: Path | None = None, umgebung: Mapping[str, str] | None = None,
            container: bool | None = None) -> list[Path]:
    """Von wo aus man Ordner durchsehen darf: der Benutzerordner (nicht im Container) und die eingebundenen Ordner."""
    umgebung = os.environ if umgebung is None else umgebung
    container = im_container() if container is None else container
    gefunden: list[Path] = []
    if not container:
        gefunden.append(Path(home or Path.home()))
    for roh in (umgebung.get('KINGFISHER_ORDNER') or '').split(os.pathsep):
        wurzel = Path(roh.strip()).expanduser() if roh.strip() else None
        if wurzel is not None and wurzel.is_absolute() and _lesbar(wurzel) and wurzel not in gefunden:
            gefunden.append(wurzel)
    return [w for w in gefunden if _lesbar(w)]


def unterordner(roh: str | None, *, home: Path | None = None, umgebung: Mapping[str, str] | None = None,
                container: bool | None = None) -> dict:
    """Die Unterordner eines Ordners zum Anklicken: `{pfad, name, oben, ordner: [{pfad, name}]}`.

    Ohne `roh` der Anfang: die eine Wurzel, oder bei mehreren die Wurzeln selbst (`pfad` leer). Nur unterhalb der
    Wurzeln; sonst `OrdnerFehler`. Gelesen werden nur Namen von Ordnern."""
    home = Path(home or Path.home())
    erlaubt = [w.resolve() for w in wurzeln(home=home, umgebung=umgebung, container=container)]
    if not erlaubt:
        raise OrdnerFehler('Kingfisher läuft hier in einem Container und sieht die Ordner deines Rechners nicht. '
                           'Ein Techniker kann einen Ordner für Kingfisher freigeben; dann lässt er sich hier auswählen.')

    def eintrag(pfad: Path) -> dict:
        dienst = cloud_name(pfad)
        return {'pfad': str(pfad), 'name': dienst[1] if dienst else (pfad.name or str(pfad))}

    if not (roh or '').strip():
        if len(erlaubt) > 1:
            return {'pfad': '', 'name': 'Orte', 'oben': None, 'ordner': [{'pfad': str(w), 'name': kurz(w, home)} for w in erlaubt]}
        roh = str(erlaubt[0])
    pfad = Path(str(roh).strip()).expanduser()
    if not pfad.is_absolute() or not _lesbar(pfad):
        raise OrdnerFehler(f'Den Ordner {kurz(pfad, home)} kann Kingfisher nicht öffnen.')
    pfad = pfad.resolve()
    wurzel = next((w for w in erlaubt if pfad == w or w in pfad.parents), None)
    if wurzel is None:
        raise OrdnerFehler('Diesen Ordner kann Kingfisher hier nicht anzeigen.')
    try:
        namen = sorted((e for e in os.scandir(pfad) if not e.name.startswith('.')), key=lambda e: e.name.lower())
    except OSError:
        raise OrdnerFehler(f'Kingfisher darf den Ordner {kurz(pfad, home)} nicht lesen.') from None
    ordner = [eintrag(Path(e.path)) for e in namen if _lesbar(Path(e.path))][:MAX_UNTERORDNER]
    oben = str(pfad.parent) if pfad != wurzel else ('' if len(erlaubt) > 1 else None)
    return {'pfad': str(pfad), 'name': kurz(pfad, home), 'oben': oben, 'ordner': ordner}


def pruefe_ordner(roh: str) -> Path:
    """Ein getippter oder angeklickter Pfad: da, ein Ordner, kein Verweis, lesbar. Sonst `OrdnerFehler` mit einem Satz."""
    text = (roh or '').strip()
    if not text:
        raise OrdnerFehler('Bitte gib den Ordner an.')
    pfad = Path(text).expanduser()
    if not pfad.is_absolute():
        raise OrdnerFehler('Bitte gib den ganzen Pfad an, zum Beispiel ~/Documents/Mitschriften.')
    try:
        info = os.lstat(pfad)
    except FileNotFoundError:
        raise OrdnerFehler(f'Den Ordner {kurz(pfad)} gibt es hier nicht.') from None
    except OSError:
        raise OrdnerFehler(f'Auf den Ordner {kurz(pfad)} kann Kingfisher nicht zugreifen.') from None
    if stat.S_ISLNK(info.st_mode):
        raise OrdnerFehler(f'{kurz(pfad)} ist nur ein Verweis auf einen anderen Ort. Bitte wähle den Ordner selbst.')
    if not stat.S_ISDIR(info.st_mode):
        raise OrdnerFehler(f'{kurz(pfad)} ist eine Datei, kein Ordner.')
    if not os.access(pfad, os.R_OK | os.X_OK):
        raise OrdnerFehler(f'Kingfisher darf den Ordner {kurz(pfad)} nicht lesen.')
    try:
        next(iter(os.scandir(pfad)), None)
    except OSError:
        raise OrdnerFehler(f'Kingfisher darf den Ordner {kurz(pfad)} nicht lesen.') from None
    return pfad.resolve(strict=True)


def root_id(pfad: Path) -> str:
    """Wie beim Mac-Helfer: Pfad, Gerät und Knoten. Wird der Ordner ausgetauscht, ändert sich die Kennung."""
    info = os.stat(pfad, follow_symlinks=False)
    return hashlib.sha256(f'{pfad}\0{info.st_dev}\0{info.st_ino}'.encode()).hexdigest()[:32]


def lesen(wurzel: Path, endungen: frozenset[str] | set[str]) -> dict:
    """Ein stabiles Abbild des Ordners: `dateien` (Name relativ, Inhalt, Änderungszeit), `gesehen`, `fehler`, `vollstaendig`.

    Versteckte Dateien und Ordner, Verweise und Dateien über 5 MiB werden übersprungen; eine Datei, die gerade noch
    geschrieben wird (jünger als zwei Sekunden), kommt beim nächsten Lauf.
    """
    dateien: list[tuple[str, bytes, float]] = []
    gesehen: list[str] = []
    fehler: list[str] = []
    try:
        for ort, ordner, namen in os.walk(wurzel, followlinks=False):
            ordner[:] = sorted(o for o in ordner if not o.startswith('.') and not os.path.islink(os.path.join(ort, o)))
            for name in sorted(namen):
                if name.startswith('.'):
                    continue
                pfad = Path(ort) / name
                relativ = str(pfad.relative_to(wurzel)).replace(os.sep, '/')
                try:
                    info = os.lstat(pfad)
                except OSError:
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                gesehen.append(relativ)
                if len(gesehen) > MAX_DATEIEN:
                    fehler.append('Der Ordner hat mehr als 2.000 Dateien.')
                    return {'dateien': dateien, 'gesehen': gesehen[:MAX_DATEIEN], 'fehler': fehler, 'vollstaendig': False}
                if pfad.suffix.lower() not in endungen:
                    continue
                if time.time() - info.st_mtime <= 2:
                    fehler.append(f'{relativ}: wird noch geschrieben; nächster Versuch folgt')
                    continue
                if getattr(info, 'st_flags', 0) & NUR_IN_DER_CLOUD:
                    fehler.append(f'{relativ}: liegt nur in der Cloud; Kingfisher lädt nichts herunter')
                    continue
                if info.st_size > MAX_BYTES:
                    fehler.append(f'{relativ}: überschreitet 5 MiB')
                    continue
                try:
                    dateien.append((relativ, pfad.read_bytes(), info.st_mtime))
                except OSError:
                    fehler.append(f'{relativ}: konnte nicht gelesen werden')
    except OSError:
        return {'dateien': dateien, 'gesehen': gesehen, 'fehler': fehler + ['Der Ordner ist nicht erreichbar.'],
                'vollstaendig': False}
    return {'dateien': dateien, 'gesehen': gesehen, 'fehler': fehler[:30], 'vollstaendig': not fehler}


__all__ = ['MAX_BYTES', 'MAX_DATEIEN', 'MAX_UNTERORDNER', 'unterordner', 'wurzeln', 'NUR_IN_DER_CLOUD', 'OrdnerFehler', 'bekannte_orte', 'cloud_hinweis', 'cloud_name',
           'cloud_orte', 'im_container', 'kurz', 'lesen', 'pruefe_ordner',
           'root_id', 'vorgabe_ordner']
