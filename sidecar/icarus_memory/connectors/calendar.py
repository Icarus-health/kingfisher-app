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

import hashlib
import heapq
import logging
import math
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from functools import cached_property
from typing import Any, Iterator, NamedTuple

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
    """iCalendar bricht lange Zeilen um; Fortsetzungen beginnen mit Leerzeichen."""
    return re.sub(r"\r?\n[ \t]", "", text)


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


def _kennung(zeit: _Zeit, beginn: _Zeit) -> str:
    """Eine RECURRENCE-ID als Text, in der Form des Serienbeginns: Datum, Ortszeit ohne Zone oder UTC.

    Daraus wird die Kennung des Einzeltermins (`UID#…`). Sie hängt am
    ursprünglichen Beginn, nicht am tatsächlichen: Ein verschobener Termin
    behält sie und ist im Gedächtnis eine neue Fassung, kein neuer Termin. Die
    UTC-Form ist dieselbe, die ein CalDAV-Server beim Ausklappen schreibt.
    """
    if beginn.ganztags:
        tag = zeit.moment.date() if zeit.ganztags else zeit.moment.astimezone(user_timezone() or timezone.utc).date()
        return f"{tag:%Y%m%d}"
    if beginn.schwebend:
        ortszeit = zeit.moment if zeit.schwebend else zeit.moment.astimezone(beginn.moment.tzinfo)
        return f"{ortszeit:%Y%m%dT%H%M%S}"
    return f"{zeit.moment.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"


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


def _komponenten(ical: str) -> list[_Komponente]:
    """Die VEVENTs des Textes. Zeilen eingebetteter Komponenten (Erinnerungen, VALARM) gehören nicht dazu."""
    ergebnis = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold(ical), re.DOTALL):
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
"""Eine Serie mit mehr Terminen am Tag (im Mittel ab ihrem ersten Termin, mit
einem Spielraum von `PUFFER_DICHTE`) ist zu dicht, etwa jede Minute. Sie bleibt
wie eine unlesbare Regel ihr erster Termin, mit einem Hinweis im Protokoll,
statt die ganze Quelle mit einem Fehler zu kippen. Gemessen wird die Dichte,
nicht die Zahl seit Serienbeginn: Eine stündliche Serie kippt nicht nach
Jahren von selbst, und Anzeige und Gedächtnis entscheiden gleich."""

PUFFER_DICHTE = 1000

MAX_SCHRITTE_JE_SERIE = 1_000_000
"""So viele Wiederholungen rechnet das Ausklappen einer Serie höchstens durch,
vom ersten Termin bis zum Ende des Fensters (rund 2,5 s). Halbstündlich reicht
das 57 Jahre, stündlich 114; darüber gilt die Serie ebenfalls als zu dicht.
Gekürzt wird nie: Ein gekürzter Abschnitt sähe für das Gedächtnis aus wie
gelöschte Termine."""


class _ZuDicht(Exception):
    """Eine Serie wiederholt sich zu dicht, um sie auszuklappen (`DICHTE_JE_TAG`)."""


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
_FEINER_ALS_MONAT = ("WEEKLY", "DAILY", "HOURLY", "MINUTELY", "SECONDLY")
_SEKUNDEN_JE_SCHRITT = {"DAILY": 86400, "HOURLY": 3600, "MINUTELY": 60, "SECONDLY": 1}
_ZYKLUS_JAHRE = 400
"""Nach 400 Jahren wiederholt sich der gregorianische Kalender genau: Daten, Wochentage, Schalttage und
Kalenderwochen (146.097 Tage sind 20.871 Wochen)."""


def _zahlen(wert: str) -> list[int]:
    try:
        return [int(teil) for teil in wert.split(",") if teil.strip()]
    except ValueError:
        return []  # dateutil lehnt den Wert ohnehin ab


def _erfuellbar(teile: dict[str, str], beginn: _Zeit) -> bool:
    """Ob eine Regel je einen Termin liefert und hier unterstützt ist.

    dateutil rechnet eine Regel, die nie trifft, bis ins Jahr 9999 durch, ohne
    einen Termin zu liefern: `FREQ=MINUTELY;BYMONTH=2;BYMONTHDAY=30` kostet
    Minuten je Aufruf. Deshalb vorher, und alles ohne Uhr, also bei jedem Abruf
    gleich:

    * **Nicht unterstützt** (wie eine unlesbare Regel): BYSETPOS und BYWEEKNO
      außer bei monatlichen und jährlichen Regeln (BYWEEKNO erlaubt RFC 5545 nur
      jährlich), und wöchentliche oder feinere Regeln mit Abstand (INTERVAL) und
      Monats- oder Datumsfilter. Ob die je treffen, hinge von der Phase des
      Abstands ab; Kalender schreiben solche Regeln nicht.
    * **Phase:** Eine tägliche oder feinere Regel, deren Abstand ganze Wochen
      sind, trifft nur den Wochentag ihres Beginns; eine monatliche mit Abstand
      nur Monate derselben Restklasse.
    * **Probe:** Kann ein Filter ins Leere greifen (Monatstag über 28, auch der
      vom Beginn übernommene, Jahrestag, Kalenderwoche, BYSETPOS, ab dem fünften
      Wochentag im Monat, ein gezählter Wochentag zusammen mit Monatstagen),
      rechnet dateutil die Regel über einen ganzen 400-Jahre-Zyklus, gelegt an
      dessen Ende vor dem Jahr 9999 (höchstens 800 Jahre). Was dort nie trifft,
      trifft nie. Tägliche und feinere Regeln prüft dabei eine jährliche Regel
      mit denselben Datumsfiltern.
    """
    freq = teile.get("FREQ", "").upper()
    intervall = int(teile.get("INTERVAL", "1"))
    tage = [teil.strip().upper() for teil in teile.get("BYDAY", "").split(",") if teil.strip()]
    gezaehlt = [tag[:-2] for tag in tage if tag[:-2] not in ("", "+")]
    datumsfilter = teile.keys() & {"BYMONTH", "BYMONTHDAY", "BYYEARDAY", "BYWEEKNO"}
    if freq in _FEINER_ALS_MONAT and ("BYSETPOS" in teile or "BYWEEKNO" in teile or (intervall > 1 and datumsfilter)):
        return False
    if freq == "MONTHLY" and "BYWEEKNO" in teile:
        return False
    if freq in _SEKUNDEN_JE_SCHRITT and tage and intervall * _SEKUNDEN_JE_SCHRITT[freq] % (7 * 86400) == 0:
        if _WOCHENTAGE[beginn.moment.weekday()] not in {tag[-2:] for tag in tage}:
            return False
    if freq == "MONTHLY" and intervall > 1 and "BYMONTH" in teile:
        rest = math.gcd(intervall, 12)
        if all((monat - beginn.moment.month) % rest for monat in _zahlen(teile["BYMONTH"])):
            return False
    monatstage = _zahlen(teile.get("BYMONTHDAY", ""))
    try:
        zaehlungen = [abs(int(zahl)) for zahl in gezaehlt]
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
        if (_ZYKLUS_JAHRE * (12 if freq == "MONTHLY" else 1)) % intervall:
            return True  # die Phase reicht über den Zyklus; dateutil endet dann nach höchstens 8000/INTERVAL Jahren
        probe = {name: inhalt for name, inhalt in teile.items() if name != "COUNT"}
    else:
        probe = {"FREQ": "YEARLY", **{name: teile[name] for name in ("BYMONTH", "BYMONTHDAY", "BYYEARDAY")
                                      if name in teile}}
        if tage:
            probe["BYDAY"] = ",".join(sorted({tag[-2:] for tag in tage}))
    wandzeit = beginn.moment.replace(tzinfo=None)
    jahr = wandzeit.year + _ZYKLUS_JAHRE * max(0, -(-(9200 - wandzeit.year) // _ZYKLUS_JAHRE))
    try:
        regel = rrulestr(";".join(f"{name}={inhalt}" for name, inhalt in probe.items()),
                         dtstart=wandzeit.replace(year=jahr))
        return next(iter(regel), None) is not None
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return False


def _regel(wert: str, beginn: _Zeit):
    """Eine RRULE ab `beginn` als `dateutil.rrule.rrule`, oder None, wenn sie unlesbar ist.

    Die Regel rechnet dateutil (RFC 5545, 3.3.10, samt BYSETPOS und WKST); hier
    wird nur vorbereitet: Zusätze (`X-…`) entfallen, UNTIL kommt in die Form
    des Beginns (`_regel_ende`).
    """
    teile, bis = [], None
    for teil in wert.split(";"):
        name, _, inhalt = teil.partition("=")
        name = name.strip().upper()
        if not name or name.startswith("X-"):
            continue
        if name == "UNTIL":
            bis = _regel_ende(inhalt.strip(), beginn)
            if bis is None:
                return None
            continue
        if name == "INTERVAL" and not (inhalt.strip().isdigit() and int(inhalt) > 0):
            return None  # nur positive Abstände (RFC 5545); 0 wiederholte denselben Termin ohne Ende
        teile.append(f"{name}={inhalt.strip()}")
    try:
        regelteile = dict(teil.split("=", 1) for teil in teile)
        if not _erfuellbar(regelteile, beginn):
            return None
        regel = rrulestr(";".join(teile), dtstart=beginn.moment)
        if bis is not None:
            regel = regel.replace(until=bis)
        if "COUNT" in regelteile and next(iter(regel), None) != beginn.moment:
            # RFC 5545, 3.3.10: DTSTART zählt als erster Termin, auch wenn er nicht zur Regel passt
            # (`_wiederholungen` nimmt ihn immer dazu); die Regel liefert dann einen weniger.
            regel = regel.replace(count=max(0, int(regelteile["COUNT"]) - 1))
        return regel
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return None


def _wiederholungen(serie: _Komponente, beginn: _Zeit, ab: datetime,
                    bis: datetime) -> Iterator[tuple[str, datetime]] | None:
    """(Kennung, Beginn) jeder Wiederholung von `ab` bis vor `bis`, ohne die ausgenommenen (EXDATE).

    DTSTART ist immer der erste Termin (RFC 5545, 3.8.5.3), RDATE fügt Termine
    hinzu. Gerechnet wird ab dem ersten Termin (die Grenze zählt jeden Schritt),
    eine Kennung aber nur ab `ab`. None, wenn eine Regel unlesbar ist.
    """
    regeln = [_regel(wert, beginn) for wert, _ in serie.alle("RRULE")]
    if any(regel is None for regel in regeln):
        return None
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
            elif zeit is not None:
                ohne.add(_kennung(zeit, beginn))

    def folge() -> Iterator[tuple[str, datetime]]:
        gesehen: set[str] = set()
        for schritt, moment in enumerate(heapq.merge(*regeln, sorted(dazu))):
            if moment >= bis:
                return
            if schritt >= MAX_SCHRITTE_JE_SERIE or schritt > PUFFER_DICHTE + DICHTE_JE_TAG * (
                    moment - beginn.moment).total_seconds() / 86400:
                raise _ZuDicht
            if moment < ab:
                continue
            kennung = _kennung(_Zeit(moment, beginn.ganztags, beginn.schwebend), beginn)
            if kennung in gesehen or kennung in ohne or moment.date() in ohne_tage:
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
        kennung = (_zeit_zur_serie(*termin.felder["RECURRENCE-ID"], beginn) if beginn
                   else _zeit(*termin.felder["RECURRENCE-ID"]))
        if kennung is None:
            if not termin.abgesagt:
                ergebnis.append(_termin(termin, uid))
            continue
        ersatz[_kennung(kennung, beginn or kennung)] = termin
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
        folge = _wiederholungen(serie, beginn, ab, bis) if beginn is not None else None
        try:
            treffer = None if folge is None else [
                (kennung, moment, schluss) for kennung, moment in folge
                if kennung not in ersatz
                and _beruehrt(moment, schluss := moment + dauer if dauer is not None else None, von, bis)]
        except (ValueError, TypeError, OverflowError):
            treffer = None  # manche unlesbare Regel fällt dateutil erst beim Rechnen auf
        except _ZuDicht:
            treffer = None
            logger.warning("Eine Terminserie wiederholt sich zu dicht (mehr als %s-mal am Tag); "
                           "sie erscheint nur mit ihrem ersten Termin.", DICHTE_JE_TAG)
        if treffer is None:
            # Kein lesbarer Beginn oder eine unlesbare Regel: wie bisher nur der erste Termin.
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


def parse_events(ical: str, von: datetime | None = None, bis: datetime | None = None) -> list[Event]:
    """Zieht die Termine aus iCalendar-Text.

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
    for termin in _komponenten(ical):
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
