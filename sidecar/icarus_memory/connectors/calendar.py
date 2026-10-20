"""Kalender über CalDAV, und der iCalendar-Leser dazu (auch für Abos, `collections.py`).

Wie bei Mail bewusst das offene Protokoll statt Anbieter-APIs: CalDAV
funktioniert mit iCloud, Nextcloud, Fastmail, Radicale und Google. Kein OAuth,
keine Schnittstelle, die in zwei Jahren abgekündigt wird.

Der iCalendar-Leser deckt ab, was Anzeige, Gedächtnis und Anlegen brauchen:
Zeitpunkt samt Zeitzone (`zeitzonen.py`), Titel, Ort, Teilnehmer, Notiz,
Absagen (`STATUS:CANCELLED` fehlt) und Serien. Serien werden im gelesenen
Zeitfenster ausgeklappt (`parse_events`); die Regeln rechnet `dateutil.rrule`,
hier stehen nur Ausnahmen (EXDATE, geänderte Einzeltermine per RECURRENCE-ID),
Kennungen und Grenzen.

Auch bei CalDAV wird hier ausgeklappt, nicht mit `<C:expand>` auf dem Server:
Server setzen das nicht einheitlich um, und RFC 4791 (9.6.5) lässt dem ersten
Termin einer ausgeklappten Serie sogar die RECURRENCE-ID offen. Die Kennung
eines Einzeltermins, an der das Gedächtnis Änderungen erkennt, soll nicht davon
abhängen, welcher Server ihn liefert. Kommt trotzdem schon Ausgeklapptes an,
wird es als Einzeltermine derselben Serie gelesen.

Was fehlt: Zeitzonen, die nur in der Datei als VTIMEZONE beschrieben sind (ihr
Name ist weder IANA noch in der Outlook-Tabelle; sie gelten als unbekannt),
`RANGE=THISANDFUTURE` (ein geänderter Termin gilt nur für sich), EXRULE
(von RFC 5545 gestrichen) und Aufgaben (VTODO).
"""

from __future__ import annotations

import codecs
import hashlib
import heapq
import logging
import math
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from functools import cached_property, lru_cache
from itertools import islice
from typing import Any, Callable, Iterator, NamedTuple

import httpx
from dateutil.rrule import rrulestr

from ..model import user_timezone
from . import zeitzonen

logger = logging.getLogger(__name__)


class CalendarError(Exception):
    pass


@dataclass
class CalendarConfig:
    url: str
    username: str
    password: str

    @classmethod
    def from_env(cls, env: dict[str, str]) -> CalendarConfig | None:
        url = env.get("ICARUS_CALDAV_URL")
        user = env.get("ICARUS_CALDAV_USER")
        password = env.get("ICARUS_CALDAV_PASSWORD")
        if not (url and user and password):
            return None
        return cls(url=url, username=user, password=password)


@dataclass
class Event:
    uid: str
    summary: str
    start: datetime | None
    end: datetime | None
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    all_day: bool = False
    source_id: str = ""
    source_label: str = ""
    notes: str = ""
    """Notiz des Termins. Nur fürs Gedächtnis; `to_dict` (Anzeige) gibt sie nicht heraus."""
    external_uid: str = ""
    """Provider/ICS identity for recognizing copies; never replaces the source-scoped UID."""
    source_copies: list[dict[str, str]] = field(default_factory=list)
    view_source_id: str = ""
    """Display filter/color identity only; never a provider or permission destination."""

    def to_dict(self) -> dict[str, Any]:
        def iso(v: datetime | None) -> str | None:
            return v.astimezone().isoformat() if v else None

        result = {
            "uid": self.uid,
            "summary": self.summary,
            "start": iso(self.start),
            "end": iso(self.end),
            "location": self.location,
            "attendees": list(self.attendees),
            "all_day": self.all_day,
        }
        if self.source_id:
            result["source_id"] = self.source_id
            result["source_label"] = self.source_label
        if self.source_copies:
            result["source_copies"] = [dict(copy) for copy in self.source_copies]
        if self.view_source_id:
            result["view_source_id"] = self.view_source_id
        return result


# -- iCalendar -------------------------------------------------------------


def _unfold(text: str) -> str:
    """iCalendar bricht lange Zeilen um; Fortsetzungen beginnen mit Leerzeichen (auch nach CR allein, altes Mac-Format)."""
    return re.sub(r"(?:\r\n|\r|\n)[ \t]", "", text)


_FALTUNG = re.compile(rb"(?:\r\n|\r|\n)[ \t]")
"""Dasselbe auf Bytes: vor dem Dekodieren entfalten, denn die Faltung darf mitten in einem Mehrbyte-Zeichen liegen."""


def _zeile(zeile: str) -> tuple[str, dict[str, str], str] | None:
    """Zerlegt eine Inhaltszeile in Name, Parameter und Wert (RFC 5545, 3.1).

    Doppelpunkt und Semikolon in Anführungszeichen gehören zum Parameterwert:
    Outlook schreibt etwa `TZID="(UTC+01:00) Amsterdam, Berlin, …"`, und ein
    Name kann `CN="Keller; Anna"` lauten. Ohne Doppelpunkt ist es keine Zeile.
    """
    teile: list[str] = []
    anfang, in_zitat = 0, False
    for stelle, zeichen in enumerate(zeile):
        if zeichen == '"':
            in_zitat = not in_zitat
        elif not in_zitat and zeichen in ";:":
            teile.append(zeile[anfang:stelle])
            anfang = stelle + 1
            if zeichen == ":":
                break
    else:
        return None
    name, *roh = teile
    parameter: dict[str, str] = {}
    for eintrag in roh:
        schluessel, _, wert = eintrag.partition("=")
        wert = wert.strip()
        if len(wert) >= 2 and wert[0] == wert[-1] == '"':
            wert = wert[1:-1]
        parameter[schluessel.strip().upper()] = wert
    return name.strip().upper(), parameter, zeile[anfang:].strip()


_DATUM = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_ZEITPUNKT = re.compile(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)$", re.IGNORECASE)


class _Zeit(NamedTuple):
    """Ein gelesener Zeitwert.

    `moment` trägt seine Zone, damit Dauer und Wiederholung in der Ortszeit des
    Termins rechnen: 09:00 bleibt über die Zeitumstellung 09:00.
    """

    moment: datetime
    ganztags: bool = False
    """Ein Datum ohne Uhrzeit, geführt als Mitternacht UTC."""
    schwebend: bool = False
    """Eine Uhrzeit ohne Zone („floating“), gelesen in der Zeitzone des Nutzers."""


def _zeit(value: str, params: dict[str, str]) -> _Zeit | None:
    """Liest einen DATE- oder DATE-TIME-Wert (RFC 5545, 3.3.4 und 3.3.5).

    * `…Z` ist UTC.
    * `TZID=…` ist die Uhrzeit in dieser Zone (`zeitzonen.zone`: IANA-Name oder
      Windows-Name aus Outlook). Ist der Name unbekannt, wird nicht geraten: Es
      bleibt bei der bisherigen Regel, die Uhrzeit gilt als UTC.
    * Ohne Zone („floating“) ist es die Ortszeit dessen, der den Kalender liest,
      also die Zeitzone des Nutzers (`KINGFISHER_TIMEZONE`).
    * Ein Datum (`VALUE=DATE`) ist ganztägig und wird wie bisher als Mitternacht
      UTC geführt; die Anzeige rechnet es nicht in eine andere Zone um.
    """
    value = value.strip()
    try:
        if treffer := _DATUM.match(value):
            return _Zeit(datetime(*map(int, treffer.groups()), tzinfo=timezone.utc), ganztags=True)
        treffer = _ZEITPUNKT.match(value)
        if treffer is None:
            return None
        wandzeit = datetime(*map(int, treffer.groups()[:6]))
    except ValueError:
        return None
    if treffer.group(7):
        return _Zeit(wandzeit.replace(tzinfo=timezone.utc))
    if params.get("TZID"):
        return _Zeit(wandzeit.replace(tzinfo=zeitzonen.zone(params["TZID"]) or timezone.utc))
    return _Zeit(wandzeit.replace(tzinfo=user_timezone() or timezone.utc), schwebend=True)


def _zeit_zur_serie(value: str, params: dict[str, str], beginn: _Zeit) -> _Zeit | None:
    """Ein Zeitwert, der sich auf eine Serie bezieht (EXDATE, RDATE, RECURRENCE-ID).

    Eine Uhrzeit ohne Zone gilt dabei in der Zone des Serienbeginns.
    """
    zeit = _zeit(value, params)
    if zeit is not None and zeit.schwebend and not (beginn.schwebend or beginn.ganztags):
        return _Zeit(zeit.moment.replace(tzinfo=beginn.moment.tzinfo))
    return zeit


def _kennung(zeit: _Zeit, beginn: _Zeit) -> str | None:
    """Eine RECURRENCE-ID als Text, in der Form des Serienbeginns: Datum, Ortszeit ohne Zone oder UTC.

    Daraus wird die Kennung des Einzeltermins (`UID#…`). Sie hängt am
    ursprünglichen Beginn, nicht am tatsächlichen: Ein verschobener Termin
    behält sie und ist im Gedächtnis eine neue Fassung, kein neuer Termin. Die
    UTC-Form ist dieselbe, die ein CalDAV-Server beim Ausklappen schreibt.
    None, wenn der Zeitpunkt umgerechnet jenseits des Jahres 9999 läge.
    """
    try:
        if beginn.ganztags:
            tag = (zeit.moment.date() if zeit.ganztags
                   else zeit.moment.astimezone(user_timezone() or timezone.utc).date())
            return f"{tag:%Y%m%d}"
        if beginn.schwebend:
            ortszeit = zeit.moment if zeit.schwebend else zeit.moment.astimezone(beginn.moment.tzinfo)
            return f"{ortszeit:%Y%m%dT%H%M%S}"
        return f"{zeit.moment.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"
    except OverflowError:
        return None


_DAUER = re.compile(r"^\+?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", re.IGNORECASE)


def _dauer(value: str) -> timedelta | None:
    """Eine DURATION (RFC 5545, 3.3.6) wie `PT1H30M` oder `P1D`; None, wenn sie unlesbar oder negativ ist."""
    treffer = _DAUER.match(value.strip())
    if treffer is None or not any(treffer.groups()):
        return None
    wochen, tage, stunden, minuten, sekunden = (int(teil or 0) for teil in treffer.groups())
    try:
        return timedelta(weeks=wochen, days=tage, hours=stunden, minutes=minuten, seconds=sekunden)
    except OverflowError:
        return None  # länger als Python darstellen kann (über 2,7 Millionen Jahre)


def _plus(moment: datetime, dauer: timedelta) -> datetime | None:
    """`moment + dauer`, oder None, wenn das Ergebnis jenseits des Jahres 9999 läge."""
    try:
        return moment + dauer
    except OverflowError:
        return None


def _ende(termin: "_Komponente", beginn: _Zeit | None) -> datetime | None:
    """Ende eines Termins (RFC 5545, 3.6.1): DTEND, sonst DTSTART plus DURATION.

    Fehlt beides, dauert ein ganztägiger Termin einen Tag, einer mit Uhrzeit
    endet, wo er beginnt. Ein unlesbares Ende bleibt unbekannt (None).
    """
    if "DTEND" in termin.felder:
        ende = _zeit(*termin.felder["DTEND"])
        return ende.moment if ende else None
    if beginn is None:
        return None
    if "DURATION" in termin.felder:
        dauer = _dauer(termin.wert("DURATION"))
        return _plus(beginn.moment, dauer) if dauer is not None else None
    return _plus(beginn.moment, timedelta(days=1) if beginn.ganztags else timedelta(0))


def _utc(moment: datetime | None) -> datetime | None:
    """In UTC; None, wenn das nicht mehr darstellbar ist (31.12.9999 abends westlich von UTC)."""
    try:
        return moment.astimezone(timezone.utc) if moment is not None else None
    except OverflowError:
        return None


def _text_aus_ical(wert: str) -> str:
    """Hebt die Maskierung eines iCalendar-Textwerts auf (\\n, \\, \\; und \\\\)."""
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), wert).strip()


_MEHRFACH = ("RRULE", "RDATE", "EXDATE")
"""Eigenschaften, die mehrmals vorkommen dürfen und alle zählen."""


@dataclass
class _Komponente:
    """Ein VEVENT, in Eigenschaften zerlegt."""

    felder: dict[str, tuple[str, dict[str, str]]]
    """Je Eigenschaft das erste Vorkommen: Wert und Parameter."""
    teilnehmer: list[str]
    mehrfach: dict[str, list[tuple[str, dict[str, str]]]] = field(default_factory=dict)

    def wert(self, name: str, vorgabe: str = "") -> str:
        return self.felder.get(name, (vorgabe, {}))[0]

    @cached_property
    def texte(self) -> tuple[str, str, str]:
        """Titel, Ort und Notiz, einmal entmaskiert (eine Serie teilt sie mit allen Einzelterminen)."""
        return (_text_aus_ical(self.wert("SUMMARY", "(ohne Titel)")), _text_aus_ical(self.wert("LOCATION")),
                _text_aus_ical(self.wert("DESCRIPTION")))

    def alle(self, name: str) -> list[tuple[str, dict[str, str]]]:
        return self.mehrfach.get(name, [])

    @property
    def abgesagt(self) -> bool:
        return self.wert("STATUS").strip().upper() == "CANCELLED"

    @property
    def wiederholt(self) -> bool:
        return bool(self.alle("RRULE") or self.alle("RDATE"))

    @property
    def uid(self) -> str:
        """Die UID; fehlt sie, eine feste Ersatzkennung aus dem Inhalt.

        Ohne DTSTAMP, das Google bei jedem Abruf neu setzt: Bei unverändertem
        Termin bleibt die Kennung dieselbe (eine zufällige wäre bei jedem Abruf
        ein neuer Termin im Gedächtnis und der alte gelöscht).
        """
        if self.wert("UID"):
            return self.wert("UID")
        inhalt = repr((sorted((name, wert, sorted(params.items())) for name, (wert, params) in self.felder.items()
                              if name != "DTSTAMP"), self.teilnehmer))
        return "ohne-uid-" + hashlib.sha256(inhalt.encode()).hexdigest()[:16]


def ical_kodierung(kodierung: str | None) -> str:
    """Die Kodierung, mit der ein Kalender gelesen wird: die genannte, wenn Python sie kennt, sonst UTF-8."""
    try:
        return codecs.lookup(kodierung or "utf-8").name
    except LookupError:
        return "utf-8"


_BOMS = ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"), (codecs.BOM_UTF8, "utf-8"),
         (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"))
"""Ein UTF-8-BOM heißt UTF-8, nicht `utf-8-sig`: Das ist nicht ASCII-kompatibel im Sinn von `ascii_kompatibel`
und zwänge zum Dekodieren der ganzen Datei. Das BOM selbst steht vor BEGIN:VCALENDAR und stört keinen Termin."""


def kodierung_der_daten(daten: bytes, angegeben: str | None) -> str:
    """Die Kodierung eines Kalenders: ein BOM am Anfang zählt vor dem Zeichensatz der Antwort (oft fehlt er)."""
    for bom, name in _BOMS:  # UTF-32 zuerst: sein BOM beginnt wie der von UTF-16
        if daten.startswith(bom):
            return name
    return ical_kodierung(angegeben)


def ascii_kompatibel(kodierung: str | None) -> bool:
    """Ob ASCII-Zeichen in dieser Kodierung ihre eigenen Bytes sind (UTF-8, Latin-1, …; nicht UTF-16 oder UTF-32)."""
    try:
        return "BEGIN:VEVENT".encode(ical_kodierung(kodierung)) == b"BEGIN:VEVENT"
    except UnicodeError:
        return False


def _bloecke(ical: str | bytes, kodierung: str) -> Iterator[str]:
    """Der Text jedes VEVENT, entfaltet.

    Bytes werden je Termin dekodiert, nicht als ganze Datei: Python hält einen
    Text mit einem einzigen Zeichen außerhalb von Latin-1 (etwa einem Emoji)
    mit vier Byte je Zeichen, ein 25-MB-Abo also mit 100 MB je Kopie.
    """
    if isinstance(ical, bytes):
        kodierung = kodierung_der_daten(ical, kodierung)
        if not ascii_kompatibel(kodierung):
            ical = ical.decode(kodierung, errors="replace")
        else:
            for treffer in re.finditer(rb"BEGIN:VEVENT(.*?)END:VEVENT", ical, re.DOTALL):
                yield _FALTUNG.sub(b"", treffer.group(1)).decode(kodierung, errors="replace")
            return
    for treffer in re.finditer(r"BEGIN:VEVENT(.*?)END:VEVENT", ical, re.DOTALL):
        yield _unfold(treffer.group(1))


def _komponenten(ical: str | bytes, kodierung: str = "utf-8") -> list[_Komponente]:
    """Die VEVENTs des Textes. Zeilen eingebetteter Komponenten (Erinnerungen, VALARM) gehören nicht dazu."""
    ergebnis = []
    for block in _bloecke(ical, kodierung):
        termin = _Komponente({}, [])
        tiefe = 0
        for line in block.strip().splitlines():
            zerlegt = _zeile(line)
            if zerlegt is None:
                continue
            name, params, value = zerlegt
            if name in ("BEGIN", "END"):
                tiefe = tiefe + 1 if name == "BEGIN" else max(0, tiefe - 1)
            elif tiefe:
                continue
            elif name == "ATTENDEE":
                adresse = re.sub(r"(?i)^mailto:", "", value)
                anzeige = params.get("CN", "").strip()
                termin.teilnehmer.append(f"{anzeige} <{adresse}>" if anzeige and anzeige != adresse else adresse)
            else:
                termin.felder.setdefault(name, (value, params))
                if name in _MEHRFACH:
                    termin.mehrfach.setdefault(name, []).append((value, params))
        ergebnis.append(termin)
    return ergebnis


# -- Serien ------------------------------------------------------------------

DICHTE_JE_TAG = 48
"""Mehr Termine am Tag hat keine Serie, die hier ausgeklappt wird (jede halbe
Stunde ist die Grenze). Gemessen wird über `PROBE_TERMINE` Termine ab dem Punkt,
von dem an gerechnet wird (`_zu_dicht`), also aus der Regel allein: gleich für
Anzeige und Gedächtnis und unabhängig davon, wie lange die Serie schon läuft."""

PROBE_TERMINE = 1000

MAX_SCHRITTE_JE_SERIE = 150_000
"""So viele Termine rechnet das Ausklappen einer Serie bis zum Ende des Fensters
höchstens durch. Gemessen wurden je nach Rechner 2,5 bis 7 µs je Schritt; die
Grenze hält eine Serie auch auf einem langsamen Rechner unter einer Sekunde.
Wöchentliche, tägliche und feinere Regeln ohne COUNT und ohne Datumsfilter
rechnen ab kurz vor dem Fenster (`_rechenbeginn`), nicht ab ihrem ersten Termin,
und erreichen die Grenze nie. Gekürzt wird nie: Ein gekürzter Abschnitt sähe
für das Gedächtnis aus wie gelöschte Termine."""

MAX_COUNT_UNTER_TAG = 2000
"""Stündliche und minütliche Regeln mit COUNT werden ab ihrem ersten Termin
gerechnet; höchstens so viele Termine (sonst wäre die Arbeit unbegrenzt)."""

MAX_PROBE_SCHRITTE = 100_000
"""Höchstens so viele Perioden darf die Probe auf Erfüllbarkeit (`_probe_voll`) rechnen."""


class _NichtAusgeklappt(Exception):
    """Eine Serie wird nicht ausgeklappt und bleibt ihr erster Termin; `satz` kommt ins Protokoll."""

    def __init__(self, satz: str) -> None:
        super().__init__(satz)
        self.satz = satz


_NIE = "Eine Terminserie trifft nach ihrer Regel nie"
_FORM = "Eine Terminserie hat eine Regel, die Kingfisher nicht ausklappt"
_DICHT = f"Eine Terminserie wiederholt sich zu dicht (mehr als {DICHTE_JE_TAG}-mal am Tag)"
_AUFWAND = "Eine Terminserie wäre zu aufwendig auszuklappen"
_UNLESBAR = "Eine Terminserie hat eine unlesbare Regel"


def _regel_ende(wert: str, beginn: _Zeit) -> datetime | None:
    """UNTIL einer Regel in der Form des Serienbeginns (das verlangt dateutil, und RFC 5545 auch).

    Kalender halten sich nicht immer daran. Ein Datum zählt mit seinem ganzen
    Tag; eine Ortszeit ohne Zone gilt in der Zone des Beginns; bei einer
    ganztägigen Serie zählt der Tag, auf den eine UTC-Grenze beim Nutzer fällt.
    """
    zeit = _zeit(wert, {})
    if zeit is None:
        return None
    if zeit.ganztags:
        return datetime.combine(zeit.moment.date(), time(23, 59, 59), beginn.moment.tzinfo)
    if zeit.schwebend:
        return zeit.moment.replace(tzinfo=beginn.moment.tzinfo)
    if beginn.ganztags:
        try:
            tag = zeit.moment.astimezone(user_timezone() or timezone.utc).date()
        except OverflowError:
            tag = date.max  # die Grenze fällt beim Nutzer schon ins Jahr 10000: kein Ende
        return datetime.combine(tag, time(23, 59, 59), timezone.utc)
    return zeit.moment


_WOCHENTAGE = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_UNTER_TAG = ("HOURLY", "MINUTELY", "SECONDLY")
_SEKUNDEN_JE_SCHRITT = {"DAILY": 86400, "HOURLY": 3600, "MINUTELY": 60, "SECONDLY": 1}
_DATUMSFILTER = frozenset({"BYMONTH", "BYMONTHDAY", "BYYEARDAY", "BYWEEKNO"})
_ZYKLUS_JAHRE = 400
"""Nach 400 Jahren wiederholt sich der gregorianische Kalender genau: Daten, Wochentage, Schalttage und
Kalenderwochen (146.097 Tage sind 20.871 Wochen)."""
_EINHEITEN_JE_ZYKLUS = {"YEARLY": 400, "MONTHLY": 4800, "WEEKLY": 20871, "DAILY": 146097}
_PERIODEN_JE_JAHR = {"YEARLY": 1, "MONTHLY": 12, "WEEKLY": 52.18, "DAILY": 365.25}


def _zahlen(wert: str) -> list[int]:
    try:
        return [int(teil) for teil in wert.split(",") if teil.strip()]
    except ValueError:
        return []  # dateutil lehnt den Wert ohnehin ab


def _anzahl(teile: dict[str, str], name: str, sonst: int) -> int:
    return len(_zahlen(teile[name])) or sonst if name in teile else sonst


def _wochentage(teile: dict[str, str]) -> list[str]:
    return [teil.strip().upper() for teil in teile.get("BYDAY", "").split(",") if teil.strip()]


@lru_cache(maxsize=512)
def _probe_trifft(regel: str, start: datetime) -> bool:
    """Ob dateutil für `regel` ab `start` überhaupt einen Termin findet (zwischengespeichert: ohne Uhr gleich)."""
    try:
        return next(iter(rrulestr(regel, dtstart=start)), None) is not None
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return False


def _probe_voll(teile: dict[str, str], beginn: _Zeit) -> bool | None:
    """Die Regel selbst, ohne COUNT, über mindestens einen ganzen 400-Jahre-Zyklus vor dem Jahr 9999.

    Der Beginn rückt um ganze Zyklen vor, so oft, dass auch die Phase von
    INTERVAL erhalten bleibt (der Zyklus mal `k`, bis INTERVAL in ihm aufgeht).
    Was dort nie trifft, trifft nie. None, wenn die Probe mehr als
    `MAX_PROBE_SCHRITTE` Perioden rechnen müsste (dann: nicht unterstützt).
    """
    freq = teile.get("FREQ", "").upper()
    intervall = int(teile.get("INTERVAL", "1"))
    einheiten = _EINHEITEN_JE_ZYKLUS.get(freq)
    if einheiten is None:
        return None
    jahre = _ZYKLUS_JAHRE * (intervall // math.gcd(intervall, einheiten))
    wandzeit = beginn.moment.replace(tzinfo=None)
    jahr = wandzeit.year + jahre * max(0, -(-(9999 - 2 * jahre - wandzeit.year) // jahre))
    if (9999 - jahr) * _PERIODEN_JE_JAHR[freq] / intervall > MAX_PROBE_SCHRITTE:
        return None
    regel = ";".join(f"{name}={inhalt}" for name, inhalt in teile.items() if name != "COUNT")
    return _probe_trifft(regel, wandzeit.replace(year=jahr))


def _erfuellbar(teile: dict[str, str], beginn: _Zeit) -> bool | None:
    """Ob eine Regel je einen Termin liefert (True, False), oder None, wenn sie hier nicht unterstützt ist.

    dateutil rechnet eine Regel, die nie trifft, bis ins Jahr 9999 durch, ohne
    einen Termin zu liefern: `FREQ=MINUTELY;BYMONTH=2;BYMONTHDAY=30` kostete
    Minuten je Aufruf. Deshalb vorher, alles ohne Uhr, also bei jedem Abruf
    gleich:

    * **Nicht unterstützt:** FREQ=SECONDLY; stündlich oder minütlich mit
      Datumsfilter oder BYSETPOS (dateutil rechnet dann je Tag bis zu 1.440
      Schritte ohne Treffer); BYWEEKNO außer jährlich (so RFC 5545). Kalender
      schreiben solche Regeln nicht.
    * **Phase:** Eine tägliche oder feinere Regel, deren Abstand ganze Wochen
      sind, trifft nur den Wochentag ihres Beginns; eine monatliche mit Abstand
      nur Monate derselben Restklasse.
    * **Ohne Probe erfüllbar:** wöchentlich oder täglich mit Abstand bis 28 Tage
      und nur BYMONTH (jeder Monat wird erreicht); wöchentlich oder täglich mit
      BYSETPOS ohne Datumsfilter, wenn eine Position innerhalb der Wochentage
      mal Uhrzeiten liegt.
    * **Probe:** Kann ein Filter sonst ins Leere greifen (Monatstag über 28, auch
      der vom Beginn übernommene, Jahrestag, Kalenderwoche, BYSETPOS, ab dem
      fünften Wochentag im Monat, ein gezählter Wochentag zusammen mit
      Monatstagen, Abstand mit Datumsfilter), rechnet dateutil die Regel über
      einen 400-Jahre-Zyklus (`_probe_voll`); wöchentliche und tägliche ohne
      Abstand prüft eine jährliche Regel mit denselben Datumsfiltern.
    """
    freq = teile.get("FREQ", "").upper()
    intervall = int(teile.get("INTERVAL", "1"))
    tage = _wochentage(teile)
    datumsfilter = teile.keys() & _DATUMSFILTER
    if freq == "SECONDLY" or (freq in _UNTER_TAG and (datumsfilter or "BYSETPOS" in teile)):
        return None
    if freq != "YEARLY" and "BYWEEKNO" in teile:
        return None
    if freq in _SEKUNDEN_JE_SCHRITT and tage and intervall * _SEKUNDEN_JE_SCHRITT[freq] % (7 * 86400) == 0:
        if _WOCHENTAGE[beginn.moment.weekday()] not in {tag[-2:] for tag in tage}:
            return False
    if freq == "MONTHLY" and intervall > 1 and "BYMONTH" in teile:
        rest = math.gcd(intervall, 12)
        if all((monat - beginn.moment.month) % rest for monat in _zahlen(teile["BYMONTH"])):
            return False
    if freq in ("WEEKLY", "DAILY"):
        if "BYSETPOS" in teile and not datumsfilter:
            groesse = ((len({tag[-2:] for tag in tage}) or 1) if freq == "WEEKLY" else 1) * math.prod(
                _anzahl(teile, name, 1) for name in ("BYHOUR", "BYMINUTE", "BYSECOND"))
            return any(1 <= abs(position) <= groesse for position in _zahlen(teile["BYSETPOS"]))
        schritt_tage = intervall * (7 if freq == "WEEKLY" else 1)
        if intervall > 1 and datumsfilter == {"BYMONTH"} and schritt_tage <= 28:
            return True
        if (intervall > 1 and datumsfilter) or "BYSETPOS" in teile:
            return _probe_voll(teile, beginn)
    monatstage = _zahlen(teile.get("BYMONTHDAY", ""))
    try:
        zaehlungen = [abs(int(tag[:-2])) for tag in tage if tag[:-2] not in ("", "+")]
    except ValueError:
        zaehlungen = [99]  # unlesbar: die Probe entscheidet (dateutil lehnt es ab)
    vom_beginn = not (tage or monatstage or {"BYYEARDAY", "BYWEEKNO"} & teile.keys()) and beginn.moment.day > 28
    leer_moeglich = ("BYYEARDAY" in teile or "BYWEEKNO" in teile or any(abs(tag) > 28 for tag in monatstage)
                     or (freq in ("MONTHLY", "YEARLY") and ("BYSETPOS" in teile or vom_beginn
                                                            or any(zahl > 4 for zahl in zaehlungen)
                                                            or (zaehlungen and monatstage))))
    if not leer_moeglich:
        return True
    if freq in ("MONTHLY", "YEARLY"):
        return _probe_voll(teile, beginn)
    probe = {"FREQ": "YEARLY", **{name: teile[name] for name in ("BYMONTH", "BYMONTHDAY", "BYYEARDAY")
                                  if name in teile}}
    if tage:
        probe["BYDAY"] = ",".join(sorted({tag[-2:] for tag in tage}))
    return _probe_voll(probe, beginn)


def _varianten(teile: dict[str, str]) -> list[dict[str, str]] | None:
    """Schlichte und gezählte Wochentage einer monatlichen oder jährlichen Regel als zwei Regeln.

    RFC 5545 vereinigt die BYDAY-Werte (`BYDAY=SA,-2FR`: jeder Samstag und der
    vorletzte Freitag); dateutil verlangte beides zugleich und fand fast nie
    einen Termin. Mit BYSETPOS lässt sich die Vereinigung nicht aufteilen
    (die Position gilt für die ganze Menge): None, nicht unterstützt.
    """
    tage = _wochentage(teile)
    gezaehlt = [tag for tag in tage if tag[:-2] not in ("", "+")]
    if teile.get("FREQ", "").upper() not in ("MONTHLY", "YEARLY") or not gezaehlt or len(gezaehlt) == len(tage):
        return [teile]
    if "BYSETPOS" in teile:
        return None
    schlicht = [tag for tag in tage if tag not in gezaehlt]
    return [{**teile, "BYDAY": ",".join(schlicht)}, {**teile, "BYDAY": ",".join(gezaehlt)}]


def _hoechstens_je_tag(teile: dict[str, str]) -> float:
    """Obergrenze der Termine je Tag aus der Form der Regel; nur darüber misst `_zu_dicht`."""
    freq = teile.get("FREQ", "").upper()
    intervall = int(teile.get("INTERVAL", "1"))
    stunden, minuten, sekunden = (_anzahl(teile, name, 0) for name in ("BYHOUR", "BYMINUTE", "BYSECOND"))
    if freq == "MINUTELY":
        return min(1440 / intervall, (stunden or 24) * (minuten or 60)) * (sekunden or 1)
    if freq == "HOURLY":
        return min(24 / intervall, stunden or 24) * (minuten or 1) * (sekunden or 1)
    tage, laenge = {"DAILY": (1, 1), "WEEKLY": (len({tag[-2:] for tag in _wochentage(teile)}) or 1, 7),
                    "MONTHLY": (31, 28), "YEARLY": (366, 365)}.get(freq, (math.inf, 1))
    je_periode = tage * (stunden or 1) * (minuten or 1) * (sekunden or 1)
    if "BYSETPOS" in teile:
        je_periode = min(je_periode, len(_zahlen(teile["BYSETPOS"])) or 1)
    return je_periode / (laenge * intervall)


def _rechenbeginn(teile: dict[str, str], beginn: _Zeit, ziel: datetime) -> datetime:
    """Von wo an dateutil rechnet: der Beginn, oder bei einer wöchentlichen, täglichen oder feineren Regel ohne
    COUNT, Datumsfilter und BYSETPOS kurz vor `ziel`.

    Solch eine Regel wiederholt sich genau nach der Periode aus Abstand und einer
    Woche (Uhrzeiten und Wochentage): Rückt ihr Beginn um ganze Perioden vor,
    liefert sie dieselben Termine. So hängt die Arbeit am Fenster, nicht am
    Alter der Serie; eine stündliche Serie seit 1990 kostet so viel wie eine
    von gestern. Gerückt wird in Ortszeit (eine 09:00-Serie bleibt 09:00).
    """
    freq = teile.get("FREQ", "").upper()
    einheit = {"WEEKLY": 7 * 86400, **_SEKUNDEN_JE_SCHRITT}.get(freq)
    if einheit is None or "COUNT" in teile or teile.keys() & (_DATUMSFILTER | {"BYSETPOS"}):
        return beginn.moment
    periode = math.lcm(int(teile.get("INTERVAL", "1")) * einheit, 7 * 86400)
    perioden = int((ziel - beginn.moment).total_seconds() // periode) - 1  # eine Periode Spielraum (Zeitumstellung)
    if perioden <= 0:
        return beginn.moment
    try:
        return beginn.moment + timedelta(seconds=perioden * periode)
    except OverflowError:
        return beginn.moment


def _zu_dicht(termine: Callable[[], Iterator[datetime]]) -> bool:
    """Ob die ersten `PROBE_TERMINE` + 1 Termine dichter liegen als `DICHTE_JE_TAG` am Tag."""
    erste = list(islice(termine(), PROBE_TERMINE + 1))
    return (len(erste) > PROBE_TERMINE
            and erste[-1] - erste[0] < timedelta(days=PROBE_TERMINE / DICHTE_JE_TAG))


def _regel(wert: str, beginn: _Zeit, ziel: datetime) -> Callable[[], Iterator[datetime]]:
    """Die Termine einer RRULE (aufsteigend, ab dem Rechenbeginn), als Fabrik für frische Durchläufe.

    Die Regel rechnet dateutil (RFC 5545, 3.3.10, samt BYSETPOS und WKST); hier
    wird vorbereitet und begrenzt: Zusätze (`X-…`) entfallen, UNTIL kommt in die
    Form des Beginns (`_regel_ende`), gemischte Wochentage werden vereinigt
    (`_varianten`), was nie trifft oder nicht unterstützt ist, wird vorher
    erkannt (`_erfuellbar`), zu dichte Serien gemessen (`_zu_dicht`). Wirft
    `_NichtAusgeklappt` mit dem Satz fürs Protokoll.
    """
    teile: dict[str, str] = {}
    bis = None
    for teil in wert.split(";"):
        name, _, inhalt = teil.partition("=")
        name, inhalt = name.strip().upper(), inhalt.strip()
        if not name or name.startswith("X-"):
            continue
        if name == "UNTIL":
            bis = _regel_ende(inhalt, beginn)
            if bis is None:
                raise _NichtAusgeklappt(_UNLESBAR)
            continue
        if name in ("INTERVAL", "COUNT") and not (inhalt.isdigit() and int(inhalt) > (0 if name == "INTERVAL" else -1)):
            raise _NichtAusgeklappt(_UNLESBAR)  # INTERVAL nur positiv (RFC 5545); 0 wiederholte ohne Ende
        teile[name] = inhalt
    freq = teile.get("FREQ", "").upper()
    anzahl = int(teile["COUNT"]) if "COUNT" in teile else None
    if freq in _UNTER_TAG and anzahl is not None and anzahl > MAX_COUNT_UNTER_TAG:
        raise _NichtAusgeklappt(_AUFWAND)
    varianten = _varianten(teile)
    if varianten is None:
        raise _NichtAusgeklappt(_FORM)
    try:
        pruefungen = [_erfuellbar(variante, beginn) for variante in varianten]
        if any(pruefung is None for pruefung in pruefungen):
            raise _NichtAusgeklappt(_FORM)
        varianten = [variante for variante, pruefung in zip(varianten, pruefungen) if pruefung]
        if not varianten:
            raise _NichtAusgeklappt(_NIE)
        start = _rechenbeginn(teile, beginn, ziel)
        regeln = []
        for variante in varianten:
            text = ";".join(f"{name}={inhalt}" for name, inhalt in variante.items()
                            if not (name == "COUNT" and len(varianten) > 1))
            regel = rrulestr(text, dtstart=start)
            regeln.append(regel.replace(until=bis) if bis is not None else regel)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        raise _NichtAusgeklappt(_UNLESBAR) from None

    def vereint() -> Iterator[datetime]:
        letzter = None
        for moment in heapq.merge(*regeln):
            if moment != letzter:
                letzter = moment
                yield moment

    termine: Callable[[], Iterator[datetime]] = (lambda: iter(regeln[0])) if len(regeln) == 1 else vereint
    if anzahl is not None and next(termine(), None) != beginn.moment:
        # RFC 5545, 3.3.10: DTSTART zählt als erster Termin, auch wenn er nicht zur Regel passt
        # (`_wiederholungen` nimmt ihn immer dazu); die Regel liefert dann einen weniger.
        anzahl -= 1
        if len(regeln) == 1:
            regeln[0] = regeln[0].replace(count=max(0, anzahl))
    if anzahl is not None and len(regeln) > 1:
        ungezaehlt = termine
        termine = lambda: islice(ungezaehlt(), max(0, anzahl))  # noqa: E731 - COUNT gilt für die Vereinigung
    if _hoechstens_je_tag(teile) > DICHTE_JE_TAG and _zu_dicht(termine):
        raise _NichtAusgeklappt(_DICHT)
    return termine


def _wiederholungen(serie: _Komponente, beginn: _Zeit, ab: datetime,
                    bis: datetime) -> Iterator[tuple[str, datetime]]:
    """(Kennung, Beginn) jeder Wiederholung von `ab` bis vor `bis`, ohne die ausgenommenen (EXDATE).

    DTSTART ist immer der erste Termin (RFC 5545, 3.8.5.3), RDATE fügt Termine
    hinzu. Eine Kennung bekommt erst, was ab `ab` beginnt. Wirft
    `_NichtAusgeklappt`, wenn eine Regel nicht ausgeklappt wird.
    """
    regeln = [_regel(wert, beginn, ab) for wert, _ in serie.alle("RRULE")]
    dazu = [beginn.moment]
    for wert, params in serie.alle("RDATE"):
        for teil in wert.split(","):
            zeit = _zeit_zur_serie(teil.split("/")[0], params, beginn)  # PERIOD: nur der Beginn
            if zeit is not None:
                dazu.append(zeit.moment)
    ohne, ohne_tage = set(), set()
    for wert, params in serie.alle("EXDATE"):
        for teil in wert.split(","):
            zeit = _zeit_zur_serie(teil, params, beginn)
            if zeit is not None and zeit.ganztags and not beginn.ganztags:
                ohne_tage.add(zeit.moment.date())  # ein ganzer Tag einer Serie mit Uhrzeit
            elif zeit is not None and (kennung := _kennung(zeit, beginn)) is not None:
                ohne.add(kennung)  # ein Wert jenseits des Jahres 9999 nimmt nichts heraus

    def folge() -> Iterator[tuple[str, datetime]]:
        gesehen: set[str] = set()
        for schritt, moment in enumerate(heapq.merge(*(termine() for termine in regeln), sorted(dazu))):
            if moment >= bis:
                return
            if schritt >= MAX_SCHRITTE_JE_SERIE:
                raise _NichtAusgeklappt(_AUFWAND)
            if moment < ab:
                continue
            kennung = _kennung(_Zeit(moment, beginn.ganztags, beginn.schwebend), beginn)
            if kennung is None or kennung in gesehen or kennung in ohne or moment.date() in ohne_tage:
                continue
            gesehen.add(kennung)
            yield kennung, moment

    return folge()


def _beruehrt(beginn: datetime, ende: datetime | None, von: datetime, bis: datetime) -> bool:
    """Der Termin überschneidet `von`..`bis`; einer ohne Dauer zählt, wenn er darin beginnt."""
    if beginn >= bis:
        return False
    return ende > von if ende is not None and ende > beginn else beginn >= von


def _termin(termin: _Komponente, uid: str, beginn: _Zeit | None = None, ende: datetime | None = None) -> Event:
    """Ein Event aus einer Komponente; `beginn` und `ende` setzen eine Wiederholung an ihre Stelle."""
    if beginn is None:
        beginn = _zeit(*termin.felder["DTSTART"]) if "DTSTART" in termin.felder else None
        ende = _ende(termin, beginn)
    titel, ort, notiz = termin.texte
    return Event(
        uid=uid,
        summary=titel,
        start=_utc(beginn.moment) if beginn else None,
        end=_utc(ende),
        location=ort,
        attendees=list(termin.teilnehmer),
        all_day=bool(beginn and beginn.ganztags),
        notes=notiz,
        external_uid=termin.wert("UID"),
    )


def _serie(serie: _Komponente | None, einzeln: list[_Komponente], uid: str,
           fenster: tuple[datetime, datetime] | None) -> list[Event]:
    """Die Termine einer Serie: Hauptkomponente `serie` und ihre geänderten Einzeltermine (`RECURRENCE-ID`)."""
    if serie is not None and serie.wiederholt and serie.abgesagt:
        return []  # eine abgesagte Serie sagt auch ihre verschobenen Termine ab
    beginn = _zeit(*serie.felder["DTSTART"]) if serie is not None and "DTSTART" in serie.felder else None
    ersatz: dict[str, _Komponente] = {}
    ergebnis: list[Event] = []
    for termin in einzeln:
        rid = (_zeit_zur_serie(*termin.felder["RECURRENCE-ID"], beginn) if beginn
               else _zeit(*termin.felder["RECURRENCE-ID"]))
        kennung = _kennung(rid, beginn or rid) if rid is not None else None
        if kennung is None:
            # Unlesbar oder jenseits des Jahres 9999: ein Termin für sich, die Serie bleibt.
            if not termin.abgesagt:
                ergebnis.append(_termin(termin, uid))
            continue
        ersatz[kennung] = termin
    if fenster is None:
        # Ohne Fenster nichts ausklappen: Die Serie bleibt ein Termin, wie bisher.
        if serie is not None and not serie.abgesagt:
            ergebnis.append(_termin(serie, uid))
        return ergebnis + [_termin(t, f"{uid}#{k}") for k, t in ersatz.items() if not t.abgesagt]
    von, bis = fenster
    if serie is not None and not serie.abgesagt:
        ende = _ende(serie, beginn)
        dauer = ende - beginn.moment if ende is not None and beginn is not None else None
        # Was vor `ab` beginnt, endet vor dem Fenster (ein Tag Spielraum für die Zeitumstellung).
        try:
            ab = von - (dauer if dauer is not None and dauer > timedelta(0) else timedelta(0)) - timedelta(days=1)
        except OverflowError:
            ab = datetime.min.replace(tzinfo=timezone.utc)
        treffer, satz = None, ""
        try:
            if beginn is not None:
                treffer = [(kennung, moment, schluss) for kennung, moment in _wiederholungen(serie, beginn, ab, bis)
                           if kennung not in ersatz
                           and _beruehrt(moment, schluss := moment + dauer if dauer is not None else None, von, bis)]
        except _NichtAusgeklappt as grund:
            satz = grund.satz
        except (ValueError, TypeError, OverflowError):
            satz = _UNLESBAR  # manche unlesbare Regel fällt dateutil erst beim Rechnen auf
        if treffer is None:
            # Kein lesbarer Beginn, oder die Regel wird nicht ausgeklappt: nur der erste Termin.
            if satz:
                logger.warning("%s; sie erscheint nur mit ihrem ersten Termin.", satz)
            ergebnis.append(_termin(serie, uid))
        else:
            ergebnis += [_termin(serie, f"{uid}#{kennung}", _Zeit(moment, beginn.ganztags, beginn.schwebend), schluss)
                         for kennung, moment, schluss in treffer]
    for kennung, termin in ersatz.items():
        if termin.abgesagt:
            continue
        einzel = _termin(termin, f"{uid}#{kennung}")
        if einzel.start is not None and _beruehrt(einzel.start, einzel.end, von, bis):
            ergebnis.append(einzel)
    return ergebnis


def _gruppe(uid: str, gruppe: list[_Komponente], fenster: tuple[datetime, datetime] | None) -> list[Event]:
    """Die Termine aller Komponenten mit derselben UID: Hauptkomponente(n) und geänderte Einzeltermine."""
    haupt = [t for t in gruppe if "RECURRENCE-ID" not in t.felder]
    einzeln = [t for t in gruppe if "RECURRENCE-ID" in t.felder]
    serie = next((t for t in haupt if t.wiederholt), None)
    if serie is None and einzeln and haupt:
        # Ein Termin ohne Regel, aber mit Einzelterminen: der erste Termin einer
        # Serie, die schon ein Server ausgeklappt hat (RFC 4791, 9.6.5).
        serie = haupt[0]
    ergebnis = [_termin(t, uid) for t in haupt if t is not serie and not t.abgesagt]
    if serie is not None or einzeln:
        ergebnis += _serie(serie, einzeln, uid, fenster)
    return ergebnis


def parse_events(ical: str | bytes, von: datetime | None = None, bis: datetime | None = None, *,
                 kodierung: str = "utf-8") -> list[Event]:
    """Zieht die Termine aus iCalendar-Text (oder seinen Bytes in `kodierung`, dann je Termin dekodiert).

    Abgesagte Termine (`STATUS:CANCELLED`) fehlen, wie bei Google und Microsoft:
    Für das Gedächtnis ist eine Absage damit eine entzogene Quelle.

    **Serien** (`RRULE`, `RDATE`, mit `EXDATE` und geänderten Einzelterminen per
    `RECURRENCE-ID`) werden nur mit Fenster ausgeklappt: Geliefert wird jeder
    Einzeltermin, der `von`..`bis` berührt, mit der Kennung `UID#<ursprünglicher
    Beginn>` (`_kennung`). Ohne Fenster bleibt eine Serie ein Termin, ihr
    erster, wie bisher; eine Serie ohne Ende hätte sonst keines. Termine ohne
    Wiederholung kommen unabhängig vom Fenster; das Filtern ist Sache des
    Aufrufers (Anzeige, Gedächtnis), so wie bisher.
    """
    fenster = (von, bis) if von is not None and bis is not None else None
    gruppen: dict[str, list[_Komponente]] = {}
    for termin in _komponenten(ical, kodierung):
        gruppen.setdefault(termin.uid, []).append(termin)
    events: list[Event] = []
    for uid, gruppe in gruppen.items():
        try:
            events += _gruppe(uid, gruppe, fenster)
        except (ValueError, OverflowError):
            # Ein Termin, der sich nicht rechnen lässt (etwa am Rand des Jahres 9999), fehlt allein;
            # er darf die anderen Termine der Quelle nicht mitnehmen.
            logger.warning("Ein Termin ließ sich nicht lesen und wurde übersprungen.")
    return sorted(events, key=lambda e: (e.start is None, e.start or datetime.max.replace(tzinfo=timezone.utc)))


def build_event(
    summary: str,
    start: datetime,
    end: datetime,
    location: str = "",
    attendees: list[str] | None = None,
    uid: str | None = None,
) -> tuple[str, str]:
    """Baut einen VEVENT. Gibt UID und iCalendar-Text zurück."""
    uid = uid or f"{uuid.uuid4()}@icarus"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Icarus//DE", "BEGIN:VEVENT",
        f"UID:{uid}", f"DTSTAMP:{stamp}",
        f"DTSTART:{start.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}",
        f"DTEND:{end.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}",
        f"SUMMARY:{summary}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    for attendee in attendees or []:
        lines.append(f"ATTENDEE;RSVP=TRUE:mailto:{attendee}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return uid, "\r\n".join(lines) + "\r\n"


# -- Zugriff ---------------------------------------------------------------

_REPORT = """<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><C:calendar-data/></D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{start}" end="{end}"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>"""


_CALDAV = "urn:ietf:params:xml:ns:caldav"


def _kalenderdaten(antwort: bytes) -> str:
    """Der iCalendar-Text aus einer CalDAV-Antwort (`multistatus`, RFC 4791, 9.6).

    Dort steht er als XML-Text: „&“ als `&amp;`, und manche Server schreiben
    jedes CR als `&#13;`. Aus dem Rohtext gelesen hießen Termine dann
    „Steuer &amp; Recht“, und Zeiten mit angehängtem `&#13;` waren unlesbar.
    Ist die Antwort kein XML, bleibt es beim Rohtext.
    """
    try:
        wurzel = ET.fromstring(antwort)
    except ET.ParseError:
        return antwort.decode("utf-8", errors="replace")
    return "\n".join(knoten.text or "" for knoten in wurzel.iter(f"{{{_CALDAV}}}calendar-data"))


class CalendarConnector:
    def __init__(self, config: CalendarConfig) -> None:
        self._config = config

    def _client(self) -> httpx.Client:
        return httpx.Client(
            auth=(self._config.username, self._config.password),
            timeout=30.0,
            follow_redirects=True,
        )

    def events(self, days: int = 7, at: datetime | None = None) -> list[Event]:
        """Termine im Zeitfenster ab jetzt; Serien ausgeklappt (`parse_events`)."""
        von = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        bis = von + timedelta(days=days)
        body = _REPORT.format(start=von.strftime("%Y%m%dT%H%M%SZ"), end=bis.strftime("%Y%m%dT%H%M%SZ"))
        try:
            with self._client() as client:
                response = client.request(
                    "REPORT", self._config.url,
                    headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
                    content=body.encode("utf-8"),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CalendarError(f"CalDAV-Zugriff fehlgeschlagen: {exc}") from exc

        # Der Server liefert jede Serie, die das Fenster berührt, als Ganzes (Regel und Ausnahmen);
        # ausgeklappt wird hier, auf demselben Weg wie beim Abo (siehe Modulbeschreibung).
        return parse_events(_kalenderdaten(response.content), von, bis)

    def create(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        location: str = "",
        attendees: list[str] | None = None,
    ) -> str:
        """Legt einen Termin an. Mit Gästen ist das außenwirksam — die
        Einstufung passiert in der Werkzeugschicht, nicht hier."""
        uid, ical = build_event(summary, start, end, location, attendees)
        url = self._config.url.rstrip("/") + f"/{uid}.ics"
        try:
            with self._client() as client:
                response = client.put(
                    url,
                    headers={"Content-Type": "text/calendar; charset=utf-8",
                             "If-None-Match": "*"},
                    content=ical.encode("utf-8"),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CalendarError(f"Termin konnte nicht angelegt werden: {exc}") from exc

        wann = start.astimezone().strftime("%d.%m.%Y um %H:%M")
        return f"Termin {summary!r} am {wann} angelegt."


__all__ = [
    "CalendarConfig",
    "CalendarConnector",
    "CalendarError",
    "Event",
    "build_event",
    "parse_events",
]
