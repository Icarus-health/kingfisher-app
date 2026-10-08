from datetime import datetime, timezone

import pytest

from icarus_memory.calendar_window import parse_calendar_window


def test_parses_aware_iso_bounds_and_keeps_offsets():
    start, end = parse_calendar_window("2026-12-28T00:00:00+01:00", "2027-01-04T00:00:00+01:00")
    assert start == datetime.fromisoformat("2026-12-28T00:00:00+01:00")
    assert end == datetime.fromisoformat("2027-01-04T00:00:00+01:00")


@pytest.mark.parametrize(("start", "end"), [
    ("2026-01-01T00:00:00", "2026-01-02T00:00:00Z"),
    ("bad", "2026-01-02T00:00:00Z"),
    ("2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z"),
    ("2026-01-01T00:00:00Z", "2027-02-06T00:00:01Z"),
])
def test_rejects_naive_invalid_reversed_and_oversized_ranges(start, end):
    with pytest.raises(ValueError):
        parse_calendar_window(start, end)


def test_accepts_exactly_400_days():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2027, 2, 5, tzinfo=timezone.utc)
    assert parse_calendar_window(start.isoformat(), end.isoformat()) == (start, end)
