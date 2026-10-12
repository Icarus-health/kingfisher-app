"""Validation for explicitly bounded calendar API requests."""

from datetime import datetime, time, timedelta, timezone, tzinfo
from collections.abc import Iterable
from .connectors.calendar import Event
from .datumstext import iso_lesen_streng

MAX_CALENDAR_WINDOW = timedelta(days=400)


def display_events(events: Iterable[Event], start: datetime, end: datetime, *, zone: tzinfo | None = None) -> tuple[list[Event], int]:
    """Bound a reading projection, retaining the full subscription for memory.

    A missing end or equal start/end denotes a point at the known start. Dates
    without a timezone, missing starts and reversed intervals cannot establish
    membership in a current window; count them for an explicit display warning.
    All-day values are civil dates in the requested zone, even when the ICS
    reader represents DATE fields with UTC timestamps. Only comparisons change.
    """
    visible, unknown = [], 0
    calendar_zone = zone or start.tzinfo
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    for event in events:
        begins, ends = event.start, event.end
        if (begins is None or begins.utcoffset() is None
                or (ends is not None and ends.utcoffset() is None)):
            unknown += 1
            continue
        if event.all_day:
            civil_end = ends.date() if ends is not None else begins.date() + timedelta(days=1)
            if civil_end <= begins.date():
                unknown += 1
                continue
            begins = datetime.combine(begins.date(), time.min, calendar_zone)
            ends = datetime.combine(civil_end, time.min, calendar_zone)
        begins = begins.astimezone(timezone.utc)
        ends = ends.astimezone(timezone.utc) if ends is not None else None
        if ends is not None and ends < begins:
            unknown += 1
            continue
        if ends is None or ends == begins:
            include = start <= begins < end
        else:
            include = ends > start and begins < end
        if include:
            visible.append(event)
    return visible, unknown


def display_warning(unknown: int) -> str:
    return f'{unknown} Kalendereinträge ohne eindeutige Zeitangabe werden in diesem Zeitraum nicht angezeigt.'


def parse_calendar_window(from_value: str, until_value: str) -> tuple[datetime, datetime]:
    """Parse an ISO timestamp range and require aware, increasing bounds of at most 400 days."""
    try:
        start = iso_lesen_streng(from_value.strip())
        end = iso_lesen_streng(until_value.strip())
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Kalendergrenzen müssen ISO-Zeitstempel sein.") from exc

    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("Kalendergrenzen müssen eine Zeitzone enthalten.")
    if end <= start:
        raise ValueError("Das Kalenderende muss nach dem Beginn liegen.")
    if end - start > MAX_CALENDAR_WINDOW:
        raise ValueError("Der Kalenderzeitraum darf höchstens 400 Tage umfassen.")
    return start, end
