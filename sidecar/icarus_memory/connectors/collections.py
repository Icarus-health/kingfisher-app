"""Mehrere lokale, lesende Mail- und Kalenderquellen.

Die Sammlung vereinheitlicht ausschließlich das Lesen. Bei mehr als einem
Mailkonto gibt es absichtlich keinen stillen Standard für den Versand: Eine
Antwort muss später ein explizit gewähltes Absenderkonto mitbringen.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Protocol

import httpx

from .calendar import CalendarError, Event, parse_events
from .mail import MailError, Message


class MailReader(Protocol):
    def inbox(self, limit: int = 10, unread_only: bool = False) -> list[Message]: ...
    def message(self, uid: str) -> Message: ...


class CalendarReader(Protocol):
    def events(self, days: int = 7, at: datetime | None = None) -> list[Event]: ...


@dataclass(frozen=True)
class NamedMail:
    id: str
    label: str
    reader: MailReader
    can_send: bool = False
    sender: str = ""


@dataclass(frozen=True)
class NamedCalendar:
    id: str
    label: str
    reader: CalendarReader


class ICalendarSubscription:
    """Ein bewusst nur lesendes, HTTPS-basiertes iCalendar-Abo."""

    ganzer_zeitraum = True
    """Das Abo liefert immer die ganze Datei; das Gedächtnis liest sie deshalb nur einmal."""

    def __init__(self, url: str, transport: httpx.BaseTransport | None = None) -> None:
        self._url = url
        self._transport = transport
        """Nur für Tests und Proben (Attrappe statt Netz)."""

    def events(self, days: int = 7, at: datetime | None = None) -> list[Event]:
        if not self._url.startswith("https://"):
            raise CalendarError("iCalendar-Abonnements benötigen eine HTTPS-Adresse.")
        try:
            optionen = {"transport": self._transport} if self._transport is not None else {}
            with httpx.Client(timeout=30.0, follow_redirects=True, **optionen) as client:
                response = client.get(self._url, headers={"Accept": "text/calendar"})
                response.raise_for_status()
                if len(response.content) > 5_000_000:
                    raise CalendarError("Das iCalendar-Abo ist größer als 5 MB.")
        except httpx.HTTPError as exc:
            raise CalendarError(f"iCalendar-Abo nicht erreichbar: {exc}") from exc
        return parse_events(response.text)


class MailCollection:
    """Fasst mehrere Postfächer mit eindeutigen Nachrichtenkennungen zusammen."""

    def __init__(self, accounts: list[NamedMail]) -> None:
        self._accounts = {item.id: item for item in accounts}
        self.last_errors: dict[str, str] = {}

    @property
    def configured(self) -> bool:
        return bool(self._accounts)

    @property
    def can_send(self) -> bool:
        # Bei mehreren Konten ist "erstes Konto gewinnt" kein vertretbarer
        # Absender. Die spätere Versandoberfläche muss das Konto benennen.
        return len(self._accounts) == 1 and next(iter(self._accounts.values())).can_send

    def reader_for(self, account_id: str):
        account = self._accounts.get(account_id)
        if account is None:
            raise MailError("Dieses Mailkonto ist nicht verbunden.")
        return account.reader

    def inbox(self, limit: int = 10, unread_only: bool = False, account_id: str | None = None) -> list[Message]:
        messages: list[Message] = []
        self.last_errors = {}
        accounts = [self._accounts[account_id]] if account_id is not None else list(self._accounts.values())
        for account in accounts:
            try:
                for message in account.reader.inbox(limit=limit, unread_only=unread_only):
                    messages.append(replace(message, uid=f"{account.id}:{message.uid}", account_id=account.id, account_label=account.label))
            except Exception as exc:  # each personal source must fail independently
                self.last_errors[account.id] = str(exc)
        if not messages and self.last_errors and len(self.last_errors) == len(accounts):
            raise MailError("; ".join(self.last_errors.values()))
        return sorted(
            messages,
            key=lambda item: item.date or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:limit]

    def message(self, uid: str) -> Message:
        account_id, separator, remote_uid = uid.partition(":")
        account = self._accounts.get(account_id) if separator else None
        if account is None or not remote_uid:
            raise MailError("Die Nachricht gehört zu keinem eingerichteten Mailkonto.")
        message = account.reader.message(remote_uid)
        return replace(message, uid=uid, account_id=account.id, account_label=account.label)

    def can_send_from(self, account_id: str) -> bool:
        account = self._accounts.get(account_id)
        return bool(account and account.can_send)

    def sender_label(self, account_id: str = "") -> str:
        account = self._accounts.get(account_id) if account_id else next(iter(self._accounts.values())) if len(self._accounts) == 1 else None
        return f"{account.label} ({account.sender or account.id})" if account else "Kein eindeutiges Absenderkonto"

    def send(self, *args: str, account_id: str = "", **kwargs: str) -> str:
        account = self._accounts.get(account_id) if account_id else next(iter(self._accounts.values())) if len(self._accounts) == 1 else None
        if account is not None:
            sender = getattr(account.reader, "send", None)
            if account.can_send and callable(sender):
                return sender(*args, **kwargs)
        raise MailError(
            "Bei mehreren Mailkonten muss das Absenderkonto ausdrücklich gewählt werden."
        )


class CalendarCollection:
    """Fasst mehrere Kalenderquellen zusammen, ohne eine davon zu bevorzugen."""

    def __init__(self, sources: list[NamedCalendar]) -> None:
        self._sources = {item.id: item for item in sources}
        self.last_errors: dict[str, str] = {}

    @property
    def sources(self) -> list[NamedCalendar]:
        """Die eingebundenen Quellen, in Aufnahmereihenfolge."""
        return list(self._sources.values())

    def cache_revision(self):
        """Änderungen eines eingebetteten Mac-Lesers ohne Neubau erkennen."""
        return tuple((source.id, revision()) for source in self._sources.values()
                     if callable(revision := getattr(source.reader, 'cache_revision', None)))

    @property
    def configured(self) -> bool:
        return bool(self._sources)

    @property
    def can_create(self) -> bool:
        return False

    def create(self, *_: object, **__: object) -> str:
        raise CalendarError(
            "Bei mehreren Kalenderquellen muss ein Zielkalender ausdrücklich gewählt werden."
        )

    def events(self, days: int = 7, at: datetime | None = None) -> list[Event]:
        events: list[Event] = []
        self.last_errors = {}
        for source in self._sources.values():
            try:
                for event in source.reader.events(days=days, at=at):
                    # Leser dürfen dieselben zwischengespeicherten Objekte liefern.
                    label = (f"{source.label} · {event.source_label}"
                             if source.id == 'mac-calendar' and event.source_label else source.label)
                    events.append(replace(event, uid=f"{source.id}:{event.uid}",
                                          source_id=source.id, source_label=label, source_copies=[]))
            except Exception as exc:  # partial failures must not hide other calendars
                self.last_errors[source.id] = str(exc)
        if not events and self.last_errors and len(self.last_errors) == len(self._sources):
            raise CalendarError("; ".join(self.last_errors.values()))
        return sorted(
            _mirror_copies(events),
            key=lambda item: item.start or datetime.max.replace(tzinfo=timezone.utc),
        )


def _mirror_copies(events: list[Event]) -> list[Event]:
    """Reading projection only: explicit same external UID plus agreeing occurrence/details.

    No title/time heuristic, persistence change, or source deletion. Unknown,
    conflicting, recurring, and same-source entries remain individually visible.
    """
    groups: list[list[Event]] = []
    index: dict[tuple, list[int]] = {}
    for event in events:
        key = None
        if (event.external_uid and event.start and event.end
                and event.start.utcoffset() is not None and event.end.utcoffset() is not None):
            key = (event.external_uid, event.start, event.end, event.all_day,
                   event.summary, event.location, tuple(sorted(event.attendees)))
        eligible = next((i for i in index.get(key, [])
                         if event.source_id not in {e.source_id for e in groups[i]}), None) if key else None
        if eligible is not None:
            groups[eligible].append(event)
        else:
            if key:
                index.setdefault(key, []).append(len(groups))
            groups.append([event])
    result = []
    for group in groups:
        if len(group) == 1:
            result.append(group[0]); continue
        # Existing connected-feed assignments survive adding a Mac mirror.
        primary = next((e for e in group if e.source_id != 'mac-calendar'), group[0])
        copies = [dict(uid=e.uid, source_id=e.source_id, source_label=e.source_label) for e in group]
        result.append(replace(primary, source_copies=copies))
    return result


def event_uids(item: dict) -> list[str]:
    """Only references in the current authorized projection, primary first."""
    return list(dict.fromkeys(uid for uid in [item.get('uid'),
        *(copy.get('uid') for copy in item.get('source_copies') or [])] if isinstance(uid, str) and uid))


def event_copy(item: dict, uid: str) -> dict | None:
    """Resolve only references present in this fresh projection, retaining the requested source."""
    if item.get('uid') == uid:
        return item
    for copy in item.get('source_copies') or []:
        if copy.get('uid') == uid:
            return {**item, **copy}
    return None


__all__ = [
    "CalendarCollection",
    "ICalendarSubscription",
    "MailCollection",
    "NamedCalendar",
    "NamedMail",
]
