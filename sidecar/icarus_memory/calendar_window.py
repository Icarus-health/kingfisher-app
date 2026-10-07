"""Validation for explicitly bounded calendar API requests."""

from datetime import datetime, timedelta

MAX_CALENDAR_WINDOW = timedelta(days=400)


def parse_calendar_window(from_value: str, until_value: str) -> tuple[datetime, datetime]:
    """Parse an ISO timestamp range and require aware, increasing bounds of at most 400 days."""
    try:
        start = datetime.fromisoformat(from_value.strip().replace("Z", "+00:00"))
        end = datetime.fromisoformat(until_value.strip().replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Kalendergrenzen müssen ISO-Zeitstempel sein.") from exc

    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("Kalendergrenzen müssen eine Zeitzone enthalten.")
    if end <= start:
        raise ValueError("Das Kalenderende muss nach dem Beginn liegen.")
    if end - start > MAX_CALENDAR_WINDOW:
        raise ValueError("Der Kalenderzeitraum darf höchstens 400 Tage umfassen.")
    return start, end
