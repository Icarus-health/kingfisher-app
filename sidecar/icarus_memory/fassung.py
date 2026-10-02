"""Welche Fassung läuft, und gibt es eine neuere (docs/53-download-und-updates.md).

Kingfisher fragt einmal am Tag eine einzige Datei ab: das Manifest der neuesten Fassung (`latest.json`) auf der
Download-Seite. Das ist die ganze Verbindung nach außen, und sie trägt nichts über den Menschen: eine GET-Anfrage
ohne Kekse, ohne Kennung, ohne Fassungsnummer im Kopf, mit kurzer Zeitgrenze. Geht etwas schief, bleibt es still;
nur `geprueft_um` bleibt dann auf dem alten Stand. Installiert wird hier nichts. Das Angebot erscheint in der
Oberfläche, und erst ein Klick des Menschen startet das Update (in der Mac-App oder mit `make aktualisieren`).

Das Manifest wird streng geprüft, bevor es zählt: jede Angabe mit dem richtigen Typ, Fassungen nach SemVer
(`1.2.0`, ohne „v“ und ohne Zusätze), und das Bild muss `ghcr.io/icarus-health/kingfisher-app:<fassung>` heißen. Ein
Manifest, das ein anderes Bild nennt, wird verworfen, gleich wer es ausliefert.

Der Zustand (Schalter, letzte Prüfung, neuestes Manifest) liegt in `fassung.json` im Datenordner.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .atomic import write_text_atomic

logger = logging.getLogger(__name__)

#: Woher das Manifest kommt. Die Umgebungsvariable überschreibt das; leer gesetzt heißt: nie nachsehen.
URL_ENV = 'KINGFISHER_UPDATE_URL'
NEUESTE_URL = 'https://icarus-health.github.io/kingfisher-app/latest.json'
#: Die laufende Fassung, vom Docker-Bild gesetzt (Build-Arg gleichen Namens).
FASSUNG_ENV = 'KINGFISHER_FASSUNG'
ENTWICKLUNG = 'entwicklung'
#: Nur Bilder aus diesem Paket werden angeboten; der Tag muss die Fassung sein.
BILD_PRAEFIX = 'ghcr.io/icarus-health/kingfisher-app:'

ZEITGRENZE_S = 5.0
MAX_BYTES = 64 * 1024
MAX_HINWEISE = 20
MAX_HINWEIS_ZEICHEN = 300
#: Einmal am Tag. Nach einem Fehler erst in einer Stunde wieder, damit ein Ausfall keine Anfragen im Takt erzeugt.
ABSTAND = timedelta(days=1)
NACH_FEHLER_S = 3600.0
#: Nicht in der ersten Minute nach dem Start: Erst soll Kingfisher in Ruhe hochfahren.
ANLAUF_S = 60.0
DATEI = 'fassung.json'

_SEMVER = re.compile(r'(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})')
_FELDER = ('fassung', 'datum', 'image', 'dmg', 'hinweise', 'app_mindestens')


def semver(text: Any) -> tuple[int, int, int] | None:
    """`"1.2.0"` → `(1, 2, 0)`; alles andere (auch `"v1.2.0"`, `"1.2"`, `"1.2.0-rc1"`) → None."""
    if not isinstance(text, str):
        return None
    treffer = _SEMVER.fullmatch(text)
    return tuple(int(teil) for teil in treffer.groups()) if treffer else None  # type: ignore[return-value]


def neuer(kandidat: Any, gegen: Any) -> bool:
    """Ist `kandidat` eine echt neuere Fassung als `gegen`? Wer keine Fassungsnummer ist, ist nie neuer."""
    a, b = semver(kandidat), semver(gegen)
    return a is not None and b is not None and a > b


def laufende_fassung(umgebung: dict[str, str] | None = None, dateien: tuple[Path, ...] | None = None) -> str:
    """Die Fassung dieses Prozesses: aus dem Bild (`KINGFISHER_FASSUNG`), sonst aus der Datei `VERSION`.

    `VERSION` liegt in einer Arbeitskopie im Wurzelverzeichnis und im Bild unter `/opt/kingfisher/`. Ohne beides:
    `entwicklung` (dann gibt es nie ein Angebot, denn `entwicklung` ist keine Fassungsnummer).
    """
    wert = (os.environ if umgebung is None else umgebung).get(FASSUNG_ENV, '').strip()
    if wert:
        return wert
    for datei in dateien if dateien is not None else (Path(__file__).resolve().parents[2] / 'VERSION',
                                                      Path('/opt/kingfisher/VERSION')):
        try:
            inhalt = datei.read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if inhalt:
            return inhalt
    return ENTWICKLUNG


def manifest_url(umgebung: dict[str, str] | None = None) -> str:
    """Die Adresse des Manifests; leer heißt: nicht nachsehen."""
    umgebung = os.environ if umgebung is None else umgebung
    return umgebung[URL_ENV].strip() if URL_ENV in umgebung else NEUESTE_URL


def download_seite(url: str | None = None) -> str | None:
    """Die Download-Seite: das Verzeichnis, in dem `latest.json` liegt. Für den Satz „Lade die neue App …“."""
    url = manifest_url() if url is None else url
    if not url.endswith('/latest.json') or urlsplit(url).scheme != 'https':
        return None
    return url[:-len('latest.json')]


def _lokal(url: str) -> bool:
    return urlsplit(url).hostname in ('127.0.0.1', 'localhost', '::1')


def url_erlaubt(url: str) -> bool:
    """Nur HTTPS; unverschlüsselt allein an diesen Rechner (für Attrappen in Tests und Proben)."""
    teile = urlsplit(url)
    return bool(teile.hostname) and (teile.scheme == 'https' or (teile.scheme == 'http' and _lokal(url)))


def manifest_pruefen(roh: Any) -> dict[str, Any] | None:
    """Das Manifest, wenn jede Angabe stimmt; sonst None. Unbekannte Angaben fallen weg."""
    if not isinstance(roh, dict) or any(feld not in roh for feld in _FELDER):
        return None
    fassung, datum, bild, dmg, hinweise, app = (roh[feld] for feld in _FELDER)
    if semver(fassung) is None or semver(app) is None:
        return None
    if not isinstance(datum, str) or len(datum) != 10:
        return None
    try:
        date.fromisoformat(datum)
    except ValueError:
        return None
    if not isinstance(bild, str) or bild != BILD_PRAEFIX + fassung:
        return None
    if not isinstance(dmg, str) or urlsplit(dmg).scheme != 'https' or not urlsplit(dmg).hostname or len(dmg) > 500:
        return None
    if (not isinstance(hinweise, list) or len(hinweise) > MAX_HINWEISE
            or not all(isinstance(h, str) and h.strip() and len(h) <= MAX_HINWEIS_ZEICHEN for h in hinweise)):
        return None
    return {'fassung': fassung, 'datum': datum, 'image': bild, 'dmg': dmg,
            'hinweise': [h.strip() for h in hinweise], 'app_mindestens': app}


class _NurSicherWeiter(HTTPRedirectHandler):
    """Eine Weiterleitung nur auf eine erlaubte Adresse (kein Wechsel von HTTPS auf HTTP)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - Signatur der Standardbibliothek
        if not url_erlaubt(newurl) or (urlsplit(req.full_url).scheme == 'https' and urlsplit(newurl).scheme != 'https'):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def abrufen(url: str, zeitgrenze: float = ZEITGRENZE_S) -> dict[str, Any] | None:
    """Genau eine GET-Anfrage; das geprüfte Manifest oder None. Wirft nie.

    Ohne Kekse (kein Keksspeicher im Öffner), ohne Kennung (ein fester, allgemeiner Name statt
    `Python-urllib/3.x`, keine Fassung, kein Rechnername), ohne Anmeldedaten. Mehr als 64 KB werden nicht gelesen.
    """
    if not url_erlaubt(url):
        return None
    anfrage = Request(url, method='GET', headers={'User-Agent': 'Kingfisher', 'Accept': 'application/json'})
    try:
        with build_opener(_NurSicherWeiter()).open(anfrage, timeout=zeitgrenze) as antwort:
            if antwort.status != 200:
                return None
            rumpf = antwort.read(MAX_BYTES + 1)
        if len(rumpf) > MAX_BYTES:
            return None
        return manifest_pruefen(json.loads(rumpf.decode('utf-8')))
    except Exception:  # noqa: BLE001 - jeder Fehler ist still: kein Netz, Zeitgrenze, kaputtes JSON
        return None


def _iso(jetzt: datetime) -> str:
    return jetzt.astimezone(timezone.utc).isoformat(timespec='seconds')


class Fassungspruefung:
    """Schalter, letzte Prüfung und neuestes Manifest; dazu der eine Abruf.

    `abruf` und `uhr` sind austauschbar, damit Tests ohne Netz und ohne Warten auskommen.
    """

    def __init__(self, datei: Path | Callable[[], Path], *, abruf: Callable[[str], dict | None] = abrufen,
                 uhr: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 monoton: Callable[[], float] = time.monotonic) -> None:
        self._datei = datei if callable(datei) else (lambda: datei)
        self._abruf = abruf
        self._uhr = uhr
        self._monoton = monoton
        self._lock = threading.Lock()
        #: Frühester nächster Versuch im Takt (nach dem Anlauf, nach einem Fehler eine Stunde später).
        self._naechster_versuch = monoton() + ANLAUF_S

    # -- Zustand --------------------------------------------------------------

    def _lesen(self) -> dict[str, Any]:
        try:
            roh = json.loads(self._datei().read_text(encoding='utf-8'))
        except (OSError, ValueError):
            roh = {}
        roh = roh if isinstance(roh, dict) else {}
        return {'pruefen': roh.get('pruefen') is not False,
                'geprueft_um': roh['geprueft_um'] if isinstance(roh.get('geprueft_um'), str) else None,
                'neueste': manifest_pruefen(roh.get('neueste'))}

    def _schreiben(self, zustand: dict[str, Any]) -> None:
        datei = self._datei()
        datei.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(datei, json.dumps(zustand, ensure_ascii=False, indent=1))

    def stand(self) -> dict[str, Any]:
        """Die Antwort von `GET /api/v1/fassung`."""
        with self._lock:
            zustand = self._lesen()
        fassung = laufende_fassung()
        neueste = zustand['neueste']
        verfuegbar = bool(neueste and neuer(neueste['fassung'], fassung))
        return {
            'fassung': fassung,
            'neueste': neueste,
            'update_verfuegbar': verfuegbar,
            # Die App meldet ihre eigene Fassung nicht. Sicher zu alt ist sie, wenn die neue Fassung eine App verlangt,
            # die neuer ist als alles, was hier je lief: Die App ist nie neuer als die Fassung, mit der sie kam.
            'app_update_noetig': bool(verfuegbar and neuer(neueste['app_mindestens'], fassung)),
            'geprueft_um': zustand['geprueft_um'],
            'pruefen': zustand['pruefen'],
            # Zusätzlich zur Schnittstelle: wohin der Satz „Lade die neue App …“ verweist.
            'download_seite': download_seite(),
        }

    def schalten(self, pruefen: bool) -> dict[str, Any]:
        with self._lock:
            zustand = self._lesen()
            zustand['pruefen'] = bool(pruefen)
            self._schreiben(zustand)
        return self.stand()

    @property
    def an(self) -> bool:
        with self._lock:
            return self._lesen()['pruefen']

    # -- Prüfen ---------------------------------------------------------------

    def jetzt_pruefen(self) -> bool:
        """Genau ein Abruf. True, wenn ein gültiges Manifest kam; sonst bleibt alles, wie es war."""
        url = manifest_url()
        manifest = self._abruf(url) if url else None
        with self._lock:
            if manifest is None:
                self._naechster_versuch = self._monoton() + NACH_FEHLER_S
                return False
            zustand = self._lesen()
            zustand.update(neueste=manifest, geprueft_um=_iso(self._uhr()))
            self._schreiben(zustand)
            self._naechster_versuch = self._monoton() + NACH_FEHLER_S
        return True

    def faellig(self) -> bool:
        if not manifest_url() or self._monoton() < self._naechster_versuch:
            return False
        with self._lock:
            zustand = self._lesen()
        if not zustand['pruefen']:
            return False
        if zustand['geprueft_um'] is None:
            return True
        try:
            zuletzt = datetime.fromisoformat(zustand['geprueft_um'])
        except ValueError:
            return True
        if zuletzt.tzinfo is None:
            zuletzt = zuletzt.replace(tzinfo=timezone.utc)
        return self._uhr() - zuletzt >= ABSTAND

    def im_takt(self) -> None:
        """Vom Zeitplan bei jedem Aufwachen gerufen: prüft, wenn es fällig ist. Wirft nie."""
        try:
            if self.faellig():
                self.jetzt_pruefen()
        except Exception:  # noqa: BLE001 - der Zeitplan darf daran nie scheitern
            logger.debug('Fassungsprüfung übersprungen', exc_info=True)


__all__ = ['ABSTAND', 'BILD_PRAEFIX', 'ENTWICKLUNG', 'FASSUNG_ENV', 'Fassungspruefung', 'NEUESTE_URL', 'URL_ENV',
           'abrufen', 'download_seite', 'laufende_fassung', 'manifest_pruefen', 'manifest_url', 'neuer', 'semver', 'url_erlaubt']
