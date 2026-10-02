"""Wegezeit: Wie lange dauert es von A zum Ort des Termins, und wann muss ich los?

Eine kleine Anbieter-Schnittstelle mit drei Wegen, in dieser Reihenfolge:

1. **Apple Karten** über den Mac-Helfer (`MacKarten`, Arbeiter
   `scripts/mac_maps_worker.py`, Swift-Teil `macos/RouteReader.swift`). Ohne
   Schlüssel, ohne Konto.
2. **Ein Kartendienst mit eigenem Schlüssel** (`OpenRouteService`, `GoogleRoutes`).
   Der Schlüssel kommt aus dem Schlüsselbund, nie aus dem Quelltext und nie ins Log.
3. **Nichts.** Dann gibt es keinen Zeitwert, sondern einen ehrlichen Satz:
   „Ort: …. Fahrzeit unbekannt.“

Was den Rechner verlässt: **zwei Adressen**, sonst nichts (kein Titel, keine
Teilnehmer, keine Uhrzeit des Termins), und nur mit der Einwilligung des Nutzers
(`Einstellung.aktiv`, Vorgabe aus). Ohne Einwilligung wird kein Anbieter auch nur
gefragt; das sichert `WegezeitDienst.auskunft` an genau einer Stelle.

Startpunkt ist der Ort des Termins davor, wenn es einen gibt (endet er vor dem
nächsten und liegt am selben Tag), sonst die Heimatadresse aus den Einstellungen.
Daraus wird „Losfahren um …“ mit Puffer.

Dieses Modul kennt weder Akten noch Kalender: Es bekommt Adressen und Zeiten und
liefert `Auskunft`. Die Verdrahtung steht in `wegezeit_routes.py`.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Protocol

import httpx

logger = logging.getLogger(__name__)

AUTO, OEPNV, FUSS = 'auto', 'oepnv', 'fuss'
VERKEHRSMITTEL = (AUTO, OEPNV, FUSS)
MITTEL_TEXT = {AUTO: 'mit dem Auto', OEPNV: 'mit Bus und Bahn', FUSS: 'zu Fuß'}

PUFFER_MIN = 10
"""Vorgabe: zehn Minuten Luft (Parken, Empfang, Verspätung). Bus und Bahn bekommen fünf mehr."""
MAX_FAHRZEIT_MIN = 12 * 60
"""Darüber ist es kein Weg zum Termin, sondern eine Reise oder ein Fehler des Dienstes."""
ZWISCHENSPEICHER_S = 20 * 60
FEHLER_MERKEN_S = 60
"""So lange gilt ein Fehlschlag als Antwort, damit das Briefing nicht bei jedem Aufruf erneut wartet."""
BUDGET_S = 3.0
"""Gesamtzeit, die ein Briefing-Aufruf höchstens auf Fahrzeiten wartet; der Rest wird im Hintergrund nachgeholt."""


class WegezeitFehler(Exception):
    """Der Anbieter konnte keine Fahrzeit liefern. Die Meldung enthält nie Schlüssel oder Adressen."""


class NichtUnterstuetzt(WegezeitFehler):
    """Der Anbieter kennt dieses Verkehrsmittel nicht; der nächste Anbieter darf es versuchen."""


@dataclass(frozen=True)
class Fahrzeit:
    minuten: int
    verkehrsmittel: str
    quelle: str
    """Wer die Zahl geliefert hat („Apple Karten“, „OpenRouteService“, „Google Routen“)."""


class Anbieter(Protocol):
    name: str

    def verfuegbar(self) -> bool: ...

    def fahrzeit(self, von: str, nach: str, verkehrsmittel: str, abfahrt: datetime | None) -> Fahrzeit: ...


# -- Einstellungen -----------------------------------------------------------


@dataclass
class Einstellung:
    """Was der Nutzer festgelegt hat. Vorgabe: aus, denn Adressen verlassen den Rechner."""

    aktiv: bool = False
    """„Fahrzeiten berechnen“. Nur damit dürfen Adressen an einen Kartendienst gehen."""
    heimat: str = ''
    verkehrsmittel: str = AUTO
    dienst: str = 'automatisch'
    """`automatisch`, `apple`, `openrouteservice` oder `google`."""
    puffer_min: int = PUFFER_MIN

    @classmethod
    def aus(cls, daten: dict[str, Any] | None) -> 'Einstellung':
        daten = daten if isinstance(daten, dict) else {}
        mittel = str(daten.get('verkehrsmittel') or AUTO)
        try:
            puffer = int(daten.get('puffer_min', PUFFER_MIN))
        except (TypeError, ValueError):
            puffer = PUFFER_MIN
        return cls(aktiv=daten.get('aktiv') is True, heimat=str(daten.get('heimat') or '').strip()[:300],
                   verkehrsmittel=mittel if mittel in VERKEHRSMITTEL else AUTO,
                   dienst=str(daten.get('dienst') or 'automatisch'), puffer_min=min(max(puffer, 0), 120))

    def to_dict(self) -> dict[str, Any]:
        return {'aktiv': self.aktiv, 'heimat': self.heimat, 'verkehrsmittel': self.verkehrsmittel,
                'dienst': self.dienst, 'puffer_min': self.puffer_min}


# -- Ort und Startpunkt ------------------------------------------------------

_ONLINE = re.compile(r'\b(online|zoom|teams|webex|google\s*meet|meet\.google|videocall|video-?konferenz|'
                     r'telefon(?:at|konferenz)?|call|virtuell|remote)\b|https?://', re.I)


def ist_online(ort: str) -> bool:
    """Ein Termin ohne Ort im Raum: Videokonferenz, Telefonat, Link."""
    return bool(_ONLINE.search(ort or ''))


def ort_bereinigt(ort: str | None) -> str:
    """Der Ort als eine Zeile ohne Doppelleerzeichen; leer, wenn es kein Ort ist."""
    text = ' '.join(str(ort or '').split())
    return '' if not text or ist_online(text) else text


# -- Rechnen mit Zeiten ------------------------------------------------------


def puffer_fuer(verkehrsmittel: str, einstellung: Einstellung) -> int:
    return einstellung.puffer_min + (5 if verkehrsmittel == OEPNV and einstellung.puffer_min else 0)


def losfahren_um(beginn: datetime, minuten: int, puffer: int) -> datetime:
    """Wann man losfahren muss: Beginn minus Fahrzeit minus Puffer, auf die volle Minute."""
    return (beginn - timedelta(minutes=minuten + puffer)).replace(second=0, microsecond=0)


# -- Anbieter: Kartendienste mit Schlüssel -----------------------------------

_DIENSTHOSTS = ('openrouteservice.org', 'googleapis.com')


class _LogFilter(logging.Filter):
    """httpx meldet jede Anfrage samt URL mit INFO. Adressen gehören nicht ins Protokoll."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            text = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        return not any(host in text for host in _DIENSTHOSTS)


for _name in ('httpx', 'httpcore'):
    logging.getLogger(_name).addFilter(_LogFilter())


class Geheimnis:
    """Ein Schlüssel, der sich nicht versehentlich ausgeben lässt (print, Log, Traceback)."""

    __slots__ = ('_wert',)

    def __init__(self, wert: str) -> None:
        self._wert = wert

    def __repr__(self) -> str:
        return 'Geheimnis(…)'

    __str__ = __repr__

    def offen(self) -> str:
        return self._wert


def _http_fehler(exc: Exception, dienst: str) -> WegezeitFehler:
    """Übersetzt eine Ausnahme in einen Satz ohne URL, Schlüssel und Adresse."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return WegezeitFehler(f'{dienst} lehnt den Schlüssel ab.')
        if code == 429:
            return WegezeitFehler(f'{dienst} ist gerade überlastet oder das Tageslimit ist erreicht.')
        return WegezeitFehler(f'{dienst} antwortet mit einem Fehler ({code}).')
    if isinstance(exc, httpx.TimeoutException):
        return WegezeitFehler(f'{dienst} antwortet nicht.')
    return WegezeitFehler(f'{dienst} ist gerade nicht erreichbar.')


class OpenRouteService:
    """OpenRouteService (openrouteservice.org): Adresse suchen, Route rechnen. Auto und zu Fuß, kein Bus und Bahn."""

    name = 'OpenRouteService'
    _PROFIL = {AUTO: 'driving-car', FUSS: 'foot-walking'}

    def __init__(self, schluessel: Callable[[], str | None], client: httpx.Client | None = None,
                 basis: str = 'https://api.openrouteservice.org') -> None:
        self._schluessel, self._client, self._basis = schluessel, client, basis

    def verfuegbar(self) -> bool:
        return bool(self._schluessel())

    def _get(self, pfad: str, params: dict[str, Any]) -> dict[str, Any]:
        schluessel = self._schluessel()
        if not schluessel:
            raise WegezeitFehler('Für OpenRouteService fehlt der Schlüssel.')
        client = self._client or httpx.Client(timeout=6.0)
        try:
            # Der Schlüssel steht im Kopf, nicht in der Adresse: Adressen landen in Protokollen, Köpfe nicht.
            antwort = client.get(self._basis + pfad, params=params, headers={'Authorization': schluessel})
            antwort.raise_for_status()
            return antwort.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise _http_fehler(exc, self.name) from None
        finally:
            if self._client is None:
                client.close()

    def _punkt(self, adresse: str) -> tuple[float, float]:
        daten = self._get('/geocode/search', {'text': adresse, 'size': 1})
        try:
            laenge, breite = daten['features'][0]['geometry']['coordinates'][:2]
            return float(laenge), float(breite)
        except (KeyError, IndexError, TypeError, ValueError):
            raise WegezeitFehler('Eine der Adressen hat der Kartendienst nicht gefunden.') from None

    def fahrzeit(self, von: str, nach: str, verkehrsmittel: str, abfahrt: datetime | None) -> Fahrzeit:
        profil = self._PROFIL.get(verkehrsmittel)
        if profil is None:
            raise NichtUnterstuetzt(f'{self.name} rechnet keine Fahrten mit Bus und Bahn.')
        a, b = self._punkt(von), self._punkt(nach)
        daten = self._get(f'/v2/directions/{profil}', {'start': f'{a[0]},{a[1]}', 'end': f'{b[0]},{b[1]}'})
        try:
            sekunden = float(daten['features'][0]['properties']['summary']['duration'])
        except (KeyError, IndexError, TypeError, ValueError):
            raise WegezeitFehler(f'{self.name} liefert keine Fahrzeit für diese Strecke.') from None
        return Fahrzeit(_minuten(sekunden), verkehrsmittel, self.name)


class GoogleRoutes:
    """Google Routes API: nimmt Adressen direkt an; Auto, Bus und Bahn, zu Fuß."""

    name = 'Google Routen'
    _MODUS = {AUTO: 'DRIVE', OEPNV: 'TRANSIT', FUSS: 'WALK'}

    def __init__(self, schluessel: Callable[[], str | None], client: httpx.Client | None = None,
                 url: str = 'https://routes.googleapis.com/directions/v2:computeRoutes') -> None:
        self._schluessel, self._client, self._url = schluessel, client, url

    def verfuegbar(self) -> bool:
        return bool(self._schluessel())

    def fahrzeit(self, von: str, nach: str, verkehrsmittel: str, abfahrt: datetime | None) -> Fahrzeit:
        schluessel = self._schluessel()
        if not schluessel:
            raise WegezeitFehler('Für Google Routen fehlt der Schlüssel.')
        koerper: dict[str, Any] = {'origin': {'address': von}, 'destination': {'address': nach},
                                   'travelMode': self._MODUS[verkehrsmittel]}
        if abfahrt is not None and abfahrt.tzinfo is not None and abfahrt > datetime.now(abfahrt.tzinfo):
            koerper['departureTime'] = abfahrt.astimezone().isoformat()
        client = self._client or httpx.Client(timeout=6.0)
        try:
            antwort = client.post(self._url, json=koerper, headers={
                'X-Goog-Api-Key': schluessel, 'X-Goog-FieldMask': 'routes.duration'})
            antwort.raise_for_status()
            daten = antwort.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise _http_fehler(exc, self.name) from None
        finally:
            if self._client is None:
                client.close()
        try:
            sekunden = float(str(daten['routes'][0]['duration']).rstrip('s'))
        except (KeyError, IndexError, TypeError, ValueError):
            raise WegezeitFehler(f'{self.name} findet keine Route zwischen den Adressen.') from None
        return Fahrzeit(_minuten(sekunden), verkehrsmittel, self.name)


def _minuten(sekunden: float) -> int:
    minuten = max(1, round(sekunden / 60))
    if minuten > MAX_FAHRZEIT_MIN:
        raise WegezeitFehler('Die Strecke ist zu weit für einen Weg zum Termin.')
    return minuten


# -- Anbieter: Apple Karten über den Mac-Helfer ------------------------------


@dataclass
class _Anfrage:
    id: str
    von: str
    nach: str
    verkehrsmittel: str
    abfahrt: str | None
    antwort: dict[str, Any] | None = None
    abgeholt: bool = False


class Briefkasten:
    """Anfragen des Sidecars an den Mac-Arbeiter und seine Antworten, nur im Speicher.

    Der Arbeiter fragt in kurzen Abständen nach (`offene`); jede Nachfrage gilt als
    Lebenszeichen. Ohne Lebenszeichen der letzten `ONLINE_S` Sekunden ist Apple
    Karten schlicht nicht da, und der Sidecar wartet gar nicht erst.
    """

    ONLINE_S = 45.0
    ANFRAGE_TTL_S = 60.0

    def __init__(self) -> None:
        self._bedingung = threading.Condition()
        self._anfragen: dict[str, _Anfrage] = {}
        self._gesehen: float | None = None
        self._geklopft: float | None = None

    def online(self) -> bool:
        with self._bedingung:
            return self._gesehen is not None and time.monotonic() - self._gesehen < self.ONLINE_S

    def klopfen(self) -> None:
        """Der Arbeiter fragt nach, auch ohne Einwilligung. Er bekommt dann nichts und gilt nicht als online; es heißt
        nur: Auf diesem Rechner gibt es Apple Karten, das Einschalten der Wegezeit würde rechnen können."""
        with self._bedingung:
            self._geklopft = time.monotonic()

    def angeklopft(self) -> bool:
        with self._bedingung:
            return self._geklopft is not None and time.monotonic() - self._geklopft < self.ONLINE_S

    def offene(self) -> list[dict[str, Any]]:
        """Für den Arbeiter: was noch keiner geholt hat. Zählt als Lebenszeichen."""
        with self._bedingung:
            self._gesehen = time.monotonic()
            self._aufraeumen()
            offen = [a for a in self._anfragen.values() if not a.abgeholt and a.antwort is None]
            for anfrage in offen:
                anfrage.abgeholt = True
            return [{'id': a.id, 'von': a.von, 'nach': a.nach, 'verkehrsmittel': a.verkehrsmittel,
                     'abfahrt': a.abfahrt} for a in offen]

    def beantworten(self, anfrage_id: str, *, minuten: int | None = None, fehler: str = '') -> bool:
        with self._bedingung:
            anfrage = self._anfragen.get(anfrage_id)
            if anfrage is None or anfrage.antwort is not None:
                return False
            anfrage.antwort = {'minuten': minuten, 'fehler': fehler[:200]}
            self._bedingung.notify_all()
            return True

    def fragen(self, von: str, nach: str, verkehrsmittel: str, abfahrt: datetime | None,
               warten_s: float) -> dict[str, Any] | None:
        anfrage = _Anfrage(uuid.uuid4().hex, von, nach, verkehrsmittel, abfahrt.isoformat() if abfahrt else None)
        ende = time.monotonic() + warten_s
        with self._bedingung:
            self._anfragen[anfrage.id] = anfrage
            try:
                while anfrage.antwort is None:
                    rest = ende - time.monotonic()
                    if rest <= 0:
                        return None
                    self._bedingung.wait(rest)
                return anfrage.antwort
            finally:
                self._anfragen.pop(anfrage.id, None)

    def _aufraeumen(self) -> None:
        # Anfragen entfernt `fragen` selbst; das hier fängt nur Reste eines abgebrochenen Aufrufs.
        if len(self._anfragen) > 100:
            self._anfragen.clear()


class MacKarten:
    """Apple Karten (MapKit, `MKDirections`) über den Mac-Helfer. Kennt Auto, Bus und Bahn, zu Fuß."""

    name = 'Apple Karten'

    def __init__(self, briefkasten: Briefkasten, warten_s: float = 12.0) -> None:
        self._briefkasten, self._warten_s = briefkasten, warten_s

    def verfuegbar(self) -> bool:
        return self._briefkasten.online()

    def fahrzeit(self, von: str, nach: str, verkehrsmittel: str, abfahrt: datetime | None) -> Fahrzeit:
        if not self._briefkasten.online():
            raise WegezeitFehler('Der Mac-Helfer für Apple Karten läuft gerade nicht.')
        antwort = self._briefkasten.fragen(von, nach, verkehrsmittel, abfahrt, self._warten_s)
        if antwort is None:
            raise WegezeitFehler('Apple Karten hat nicht rechtzeitig geantwortet.')
        if antwort.get('fehler') == 'nicht_unterstuetzt':
            raise NichtUnterstuetzt('Apple Karten rechnet dieses Verkehrsmittel nicht.')
        minuten = antwort.get('minuten')
        if not isinstance(minuten, int) or minuten <= 0:
            raise WegezeitFehler('Apple Karten findet keine Route zwischen den Adressen.')
        if minuten > MAX_FAHRZEIT_MIN:
            raise WegezeitFehler('Die Strecke ist zu weit für einen Weg zum Termin.')
        return Fahrzeit(minuten, verkehrsmittel, self.name)


# -- Auskunft ----------------------------------------------------------------

BERECHNET, AUS, OHNE_ORT, OHNE_START, OHNE_DIENST, FEHLER, WIRD_BERECHNET = (
    'berechnet', 'aus', 'ohne_ort', 'ohne_start', 'ohne_dienst', 'fehler', 'wird_berechnet')
_WARTET = '\0wartet'


@dataclass
class Auskunft:
    """Was über den Weg zum Termin bekannt ist, ehrlich in Worten.

    Ist `status` nicht `berechnet`, gibt es **keine** Zahl (`minuten` ist None).
    `hinweis` sagt, was der Nutzer mit einem Klick ändern könnte: `einwilligung`,
    `heimat` oder `dienst`.
    """

    status: str
    ort: str = ''
    satz: str = ''
    """Ein ganzer Satz für die Anzeige."""
    minuten: int | None = None
    verkehrsmittel: str | None = None
    quelle: str | None = None
    start: str = ''
    start_art: str = ''
    """`heimat` oder `vorheriger_termin`."""
    puffer_min: int | None = None
    losfahren: datetime | None = None
    knapp: str = ''
    """Nicht leer, wenn der Termin davor zu spät endet."""
    grund: str = ''
    hinweis: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {'status': self.status, 'ort': self.ort, 'satz': self.satz, 'minuten': self.minuten,
                'verkehrsmittel': self.verkehrsmittel, 'quelle': self.quelle, 'start': self.start,
                'start_art': self.start_art, 'puffer_min': self.puffer_min,
                'losfahren': self.losfahren.isoformat() if self.losfahren else None,
                'knapp': self.knapp, 'grund': self.grund, 'hinweis': self.hinweis}


def _uhr(zeit: datetime) -> str:
    return f'{zeit.hour}:{zeit.minute:02d} Uhr'


def _ohne_zahl(status: str, ort: str, grund: str, hinweis: str = '') -> Auskunft:
    """Kein Zeitwert. Der Satz sagt, was da ist (der Ort) und was fehlt (die Fahrzeit)."""
    satz = f'Ort: {ort}. Fahrzeit unbekannt.' if ort else 'Kein Ort im Termin.'
    return Auskunft(status=status, ort=ort, satz=satz, grund=grund, hinweis=hinweis)


class WegezeitDienst:
    """Die eine Stelle, an der entschieden wird: Einwilligung, Startpunkt, Anbieter, Zwischenspeicher, Satz."""

    def __init__(self, anbieter: dict[str, Anbieter], *, einstellung: Callable[[], Einstellung],
                 jetzt: Callable[[], float] = time.monotonic) -> None:
        self._anbieter = anbieter
        self._einstellung = einstellung
        self._jetzt = jetzt
        self._gemerkt: dict[tuple, tuple[float, Fahrzeit]] = {}
        self._fehlgeschlagen: dict[tuple, tuple[float, str]] = {}
        self._laufend: dict[tuple, Future] = {}
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='wegezeit')
        self._sperre = threading.Lock()

    def anbieter_in_reihenfolge(self, einstellung: Einstellung) -> list[Anbieter]:
        wunsch = einstellung.dienst
        if wunsch in self._anbieter:
            return [self._anbieter[wunsch]]
        return [self._anbieter[name] for name in ('apple', 'openrouteservice', 'google') if name in self._anbieter]

    def frist(self, sekunden: float = BUDGET_S) -> float:
        """Der Zeitpunkt (nach der Uhr des Dienstes), bis zu dem ein Aufruf höchstens auf Fahrzeiten wartet."""
        return self._jetzt() + sekunden

    def stand(self) -> dict[str, Any]:
        """Für die Einstellungen: was da ist, ohne etwas zu berechnen."""
        einstellung = self._einstellung()
        return {**einstellung.to_dict(),
                'dienste': {name: anbieter.verfuegbar() for name, anbieter in self._anbieter.items()}}

    def auskunft(self, ort: str | None, *, beginn: datetime, vorheriger: tuple[str, datetime] | None = None,
                 frist_bis: float | None = None) -> Auskunft:
        """Auskunft zum Weg zu `ort`. `vorheriger`: (Ort, Ende) des Termins davor am selben Tag.

        `frist_bis` (siehe `frist`): Was bis dahin nicht berechnet ist, kommt als „wird berechnet“ zurück,
        die Anfrage läuft im Hintergrund weiter, und der nächste Aufruf findet die Zahl im Zwischenspeicher.
        Ohne `frist_bis` wird gewartet, bis der Anbieter antwortet.
        """
        einstellung = self._einstellung()
        ziel = ort_bereinigt(ort)
        if not ziel:
            return Auskunft(status=OHNE_ORT, satz='Kein Ort im Termin.' if not (ort or '').strip()
                            else f'Ort: {" ".join(str(ort).split())}. Ohne Anfahrt.',
                            ort=' '.join(str(ort or '').split()))
        if not einstellung.aktiv:
            return _ohne_zahl(AUS, ziel, 'Die Berechnung von Fahrzeiten ist ausgeschaltet.', 'einwilligung')
        start, start_art, frei_ab = einstellung.heimat, 'heimat', None
        if vorheriger is not None and ort_bereinigt(vorheriger[0]) and vorheriger[1] <= beginn:
            start, start_art, frei_ab = ort_bereinigt(vorheriger[0]), 'vorheriger_termin', vorheriger[1]
        if not start:
            return _ohne_zahl(OHNE_START, ziel, 'Ich kenne deinen Startort nicht.', 'heimat')
        if _gleich(start, ziel):
            return Auskunft(status=OHNE_ORT, ort=ziel, satz=f'Ort: {ziel}. Du bist dann schon dort.',
                            start=start, start_art=start_art)
        anbieter = self.anbieter_in_reihenfolge(einstellung)
        if not any(a.verfuegbar() for a in anbieter):
            return _ohne_zahl(OHNE_DIENST, ziel, 'Es ist kein Kartendienst eingerichtet.', 'dienst')
        fahrzeit, grund = self._rechnen(anbieter, start, ziel, einstellung.verkehrsmittel, beginn, frist_bis)
        if fahrzeit is None and grund == _WARTET:
            return Auskunft(status=WIRD_BERECHNET, ort=ziel, satz=f'Ort: {ziel}. Fahrzeit wird berechnet.',
                            start=start, start_art=start_art)
        if fahrzeit is None:
            return _ohne_zahl(FEHLER, ziel, grund or 'Der Kartendienst liefert keine Fahrzeit.',
                              'dienst' if not grund else '')
        puffer = puffer_fuer(fahrzeit.verkehrsmittel, einstellung)
        los = losfahren_um(beginn, fahrzeit.minuten, puffer)
        wo = f' von {start}' if start_art == 'vorheriger_termin' else ''
        satz = (f'Ort: {ziel}. Fahrzeit etwa {fahrzeit.minuten} Minuten {MITTEL_TEXT[fahrzeit.verkehrsmittel]}{wo} '
                f'({fahrzeit.quelle}). Losfahren um {_uhr(los)}, mit {puffer} Minuten Puffer.')
        knapp = ''
        if frei_ab is not None and frei_ab > los:
            knapp = f'Der Termin davor endet erst um {_uhr(frei_ab)}. Das wird knapp.'
            satz += ' ' + knapp
        return Auskunft(status=BERECHNET, ort=ziel, satz=satz, minuten=fahrzeit.minuten,
                        verkehrsmittel=fahrzeit.verkehrsmittel, quelle=fahrzeit.quelle, start=start,
                        start_art=start_art, puffer_min=puffer, losfahren=los, knapp=knapp)

    def _rechnen(self, anbieter: list[Anbieter], von: str, nach: str, mittel: str,
                 abfahrt: datetime, frist_bis: float | None = None) -> tuple[Fahrzeit | None, str]:
        schluessel = (_norm(von), _norm(nach), mittel)
        with self._sperre:
            gemerkt = self._gemerkt.get(schluessel)
            if gemerkt and self._jetzt() - gemerkt[0] < ZWISCHENSPEICHER_S:
                return gemerkt[1], ''
            misserfolg = self._fehlgeschlagen.get(schluessel)
            if misserfolg and self._jetzt() - misserfolg[0] < FEHLER_MERKEN_S:
                return None, misserfolg[1]
            arbeit = self._laufend.get(schluessel)
            if arbeit is None:
                arbeit = self._laufend[schluessel] = self._pool.submit(self._anfragen, schluessel, anbieter, von, nach,
                                                                       mittel, abfahrt)
        try:
            return arbeit.result(timeout=None if frist_bis is None else max(0.0, frist_bis - self._jetzt()))
        except FutureTimeout:
            return None, _WARTET

    def _anfragen(self, schluessel: tuple, anbieter: list[Anbieter], von: str, nach: str, mittel: str,
                  abfahrt: datetime) -> tuple[Fahrzeit | None, str]:
        """Fragt die Anbieter der Reihe nach (im Hintergrund) und merkt Erfolg wie Fehlschlag."""
        try:
            grund = ''
            for a in anbieter:
                if not a.verfuegbar():
                    continue
                try:
                    fahrzeit = a.fahrzeit(von, nach, mittel, abfahrt)
                except NichtUnterstuetzt as exc:
                    grund = grund or str(exc)
                    continue
                except WegezeitFehler as exc:
                    grund = str(exc)
                    continue
                except Exception:  # noqa: BLE001 - ein Anbieter darf nie das Briefing kippen; kein Text, er könnte Adressen tragen
                    logger.warning('Wegezeit: Anbieter %s ist mit einem unerwarteten Fehler ausgefallen', a.name)
                    grund = f'{a.name} ist ausgefallen.'
                    continue
                with self._sperre:
                    self._gemerkt[schluessel] = (self._jetzt(), fahrzeit)
                    if len(self._gemerkt) > 200:
                        self._gemerkt.clear()
                return fahrzeit, ''
            with self._sperre:
                self._fehlgeschlagen[schluessel] = (self._jetzt(), grund)
                if len(self._fehlgeschlagen) > 200:
                    self._fehlgeschlagen.clear()
            return None, grund
        finally:
            with self._sperre:
                self._laufend.pop(schluessel, None)


def _norm(adresse: str) -> str:
    return ' '.join(adresse.casefold().split())


def _gleich(a: str, b: str) -> bool:
    return _norm(a) == _norm(b)


def vorheriger_termin(termine: list[dict[str, Any]], aktuell: dict[str, Any]) -> tuple[str, datetime] | None:
    """Ort und Ende des Termins direkt davor am selben Tag, wenn er einen Ort im Raum hat.

    `termine`: Termine als Wörterbücher mit `start`/`end` (ISO) und `location`; `aktuell`
    ist einer davon. Ganztägige Termine zählen nicht, ebenso keiner ohne Ort oder mit Videolink.
    """
    try:
        beginn = datetime.fromisoformat(str(aktuell.get('start')))
    except ValueError:
        return None
    kandidaten: list[tuple[datetime, str]] = []
    for termin in termine:
        if termin is aktuell or termin.get('all_day'):
            continue
        try:
            ende = datetime.fromisoformat(str(termin.get('end') or ''))
            start = datetime.fromisoformat(str(termin.get('start') or ''))
        except ValueError:
            continue
        if start >= beginn or ende.date() != beginn.date() or not ort_bereinigt(termin.get('location')):
            continue
        # Nur was sich nicht mit dem Termin überschneidet, ist „davor“; der Ende-Vergleich macht `auskunft`.
        kandidaten.append((ende, ort_bereinigt(termin.get('location'))))
    if not kandidaten:
        return None
    ende, ort = max(kandidaten, key=lambda paar: paar[0])
    return ort, ende


__all__ = ['Anbieter', 'Auskunft', 'Briefkasten', 'Einstellung', 'Fahrzeit', 'GoogleRoutes', 'MacKarten',
           'NichtUnterstuetzt', 'OpenRouteService', 'WegezeitDienst', 'WegezeitFehler', 'ist_online',
           'losfahren_um', 'ort_bereinigt', 'vorheriger_termin']
