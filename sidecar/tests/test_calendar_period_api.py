from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from icarus_memory.connectors.calendar import Event
from icarus_memory.server import create_app


class Calendar:
    last_errors = {}
    def __init__(self):
        self.calls = []
        self.items = [Event('series', 'Next year', datetime(2030, 1, 1, 10, tzinfo=timezone.utc), datetime(2030, 1, 1, 11, tzinfo=timezone.utc))]
    def events(self, days=7, at=None):
        self.calls.append((at, days))
        return [e for e in self.items if e.start < at + timedelta(days=days) and e.end > at]


def test_explicit_calendar_window_spans_year_boundary_and_reaches_preparation():
    app = create_app(); calendar = Calendar(); app.state.calendar = calendar
    with TestClient(app) as client:
        params = {'from': '2029-12-30T23:00:00Z', 'until': '2030-01-06T23:00:00Z', 'tz': 'Europe/Berlin'}
        response = client.get('/api/v1/calendar', params=params)
        assert response.status_code == 200
        result = response.json()
        assert [e['uid'] for e in result['items']] == ['series']
        assert datetime.fromisoformat(result['range_start']) == datetime(2029, 12, 30, 23, tzinfo=timezone.utc)
        assert calendar.calls[-1] == (datetime(2029, 12, 30, 23, tzinfo=timezone.utc), 7)
        start = calendar.items[0].start.isoformat()
        response = client.get('/api/v1/calendar/preparation', params={'uid': 'series', 'start': start})
        assert response.status_code == 200 and response.json()['event']['summary'] == 'Next year'
        assert client.get('/api/v1/calendar/zuordnung', params={'uid': 'series', 'start': start}).status_code == 200
        assert client.get('/api/v1/calendar/preparation', params={'uid': 'series', 'start': '2030-01-02T10:00:00Z'}).status_code == 404


def test_calendar_bounds_are_paired_aware_and_bounded():
    with TestClient(create_app()) as client:
        for params in ({'from': '2030-01-01T00:00:00Z'}, {'until': '2030-01-02T00:00:00Z'},
                       {'from': '2030-01-01', 'until': '2030-01-02'},
                       {'from': '2030-01-01T00:00:00Z', 'until': '2032-01-01T00:00:00Z'},
                       {'from': '2030-01-02T00:00:00Z', 'until': '2030-01-01T00:00:00Z'},
                       {'from': '2030-01-01T00:00:00Z', 'until': '2030-01-02T00:00:00Z', 'tz': 'Unknown/Zone'}):
            assert client.get('/api/v1/calendar', params=params).status_code == 422, params


def test_explicit_window_uses_device_dates_for_birthdays_across_clock_change(monkeypatch):
    captured = []
    def birthdays(claims, first, until):
        captured.append((first.isoformat(), until.isoformat()))
        return []
    monkeypatch.setattr('icarus_memory.wiederkehrendes.kalender_eintraege', birthdays)
    with TestClient(create_app()) as client:
        result = client.get('/api/v1/calendar', params={'from': '2026-09-30T22:00:00Z', 'until': '2026-10-31T23:00:00Z', 'tz': 'Europe/Berlin'})
        assert result.status_code == 200
    assert captured == [('2026-10-01', '2026-11-01')]


def test_legacy_preparation_rejects_ambiguous_series_without_start():
    app = create_app(); calendar = Calendar(); app.state.calendar = calendar
    at = datetime.now(timezone.utc).replace(month=6, day=1, hour=10, minute=0, second=0, microsecond=0)
    calendar.items = [Event('series', 'First', at, at + timedelta(hours=1)),
                      Event('series', 'Second', at + timedelta(days=7), at + timedelta(days=7, hours=1))]
    with TestClient(app) as client:
        assert client.get('/api/v1/calendar/preparation', params={'uid':'series'}).status_code == 409
        result = client.get('/api/v1/calendar/preparation', params={'uid':'series', 'start':at.isoformat()})
        assert result.status_code == 200 and result.json()['event']['summary'] == 'First'
