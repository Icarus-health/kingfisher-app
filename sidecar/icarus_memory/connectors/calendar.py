"""Kalender über CalDAV.

Wie bei Mail bewusst das offene Protokoll statt Anbieter-APIs: CalDAV
funktioniert mit iCloud, Nextcloud, Fastmail, Radicale und Google. Kein OAuth,
keine Schnittstelle, die in zwei Jahren abgekündigt wird.

Der iCalendar-Parser ist absichtlich klein gehalten und deckt das ab, was für
Anzeige und Anlegen nötig ist: Zeitpunkt, Titel, Ort, Teilnehmer. Ein
vollständiger RFC-5545-Parser samt Wiederholungsregeln ist ein eigenes Projekt;
was hier fehlt, ist unten benannt.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..model import user_timezone
from . import zeitzonen


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


def _parse_dt(value: str, params: dict[str, str]) -> tuple[datetime | None, bool]:
    """Liest DTSTART/DTEND (RFC 5545, 3.3.4 und 3.3.5). Gibt Zeitpunkt (in UTC) und Ganztags-Flag zurück.

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
            return datetime(*map(int, treffer.groups()), tzinfo=timezone.utc), True
        treffer = _ZEITPUNKT.match(value)
        if treffer is None:
            return None, False
        wandzeit = datetime(*map(int, treffer.groups()[:6]))
    except ValueError:
        return None, False
    if treffer.group(7):
        zone = timezone.utc
    elif params.get("TZID"):
        zone = zeitzonen.zone(params["TZID"]) or timezone.utc
    else:
        zone = user_timezone() or timezone.utc
    return wandzeit.replace(tzinfo=zone).astimezone(timezone.utc), False


def _text_aus_ical(wert: str) -> str:
    """Hebt die Maskierung eines iCalendar-Textwerts auf (\\n, \\, \\; und \\\\)."""
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), wert).strip()


def parse_events(ical: str) -> list[Event]:
    """Zieht VEVENT-Blöcke aus iCalendar-Text."""
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold(ical), re.DOTALL):
        fields: dict[str, tuple[str, str]] = {}
        attendees = []
        for line in block.strip().splitlines():
            zerlegt = _zeile(line)
            if zerlegt is None:
                continue
            name, params, value = zerlegt
            if name == "ATTENDEE":
                adresse = re.sub(r"(?i)^mailto:", "", value)
                anzeige = params.get("CN", "").strip()
                attendees.append(f"{anzeige} <{adresse}>" if anzeige and anzeige != adresse else adresse)
            else:
                fields[name] = (value, params)

        start, all_day = _parse_dt(*fields["DTSTART"]) if "DTSTART" in fields else (None, False)
        end, _ = _parse_dt(*fields["DTEND"]) if "DTEND" in fields else (None, False)

        events.append(Event(
            uid=fields.get("UID", (str(uuid.uuid4()), ""))[0],
            summary=_text_aus_ical(fields.get("SUMMARY", ("(ohne Titel)", ""))[0]),
            start=start,
            end=end,
            location=_text_aus_ical(fields.get("LOCATION", ("", ""))[0]),
            attendees=attendees,
            all_day=all_day,
            notes=_text_aus_ical(fields.get("DESCRIPTION", ("", ""))[0]),
            external_uid=fields.get("UID", ("", ""))[0],
        ))
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
        """Termine im Zeitfenster ab jetzt."""
        at = at or datetime.now(timezone.utc)
        body = _REPORT.format(
            start=at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            end=(at + timedelta(days=days)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        )
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

        return parse_events(response.text)

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
