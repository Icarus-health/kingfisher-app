"""A full subscription must not make historical events look current."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import CalendarCollection, ICalendarSubscription, NamedCalendar
from tests.test_multi_integrations import _client


UTC = timezone.utc
NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def subscription():
    # The real ICS reader intentionally retains all dates for memory ingestion.
    text = '\n'.join([
        'BEGIN:VCALENDAR',
        'BEGIN:VEVENT', 'UID:old', 'SUMMARY:Archive', 'DTSTART:20200103T100000Z', 'DTEND:20200103T110000Z', 'END:VEVENT',
        'BEGIN:VEVENT', 'UID:current', 'SUMMARY:Current', 'DTSTART:20300103T100000Z', 'DTEND:20300103T110000Z', 'END:VEVENT',
        'BEGIN:VEVENT', 'UID:later', 'SUMMARY:Later', 'DTSTART:20300303T100000Z', 'DTEND:20300303T110000Z', 'END:VEVENT',
        'END:VCALENDAR',
    ])
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=text))
    return ICalendarSubscription('https://calendar.example.test/all.ics', transport=transport)


@pytest.mark.parametrize('params', [
    {'days': 7},
    {'from': '2030-01-01T00:00:00Z', 'until': '2030-01-08T00:00:00Z', 'tz': 'Europe/Berlin'},
    {'year_view': True},
])
def test_full_ical_feed_is_bounded_in_default_explicit_and_year_views(tmp_path, monkeypatch, params):
    monkeypatch.setattr('icarus_memory.server.datetime', FrozenDateTime)
    reader = subscription()
    client = _client(tmp_path, monkeypatch)
    client.app.state.calendar = CalendarCollection([NamedCalendar('feed', 'Feed', reader)])
    result = client.get('/api/v1/calendar', params=params)
    assert result.status_code == 200
    expected = ['feed:current', 'feed:later'] if params.get('year_view') else ['feed:current']
    assert [x['uid'] for x in result.json()['items']] == expected
    assert result.json()['errors'] == []
    # Filtering the display must not prune the original source used by memory.
    assert [x.uid for x in reader.events()] == ['old', 'current', 'later']


def test_dashboard_does_not_present_far_future_subscription_events_as_upcoming(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.server.datetime', FrozenDateTime)
    client = _client(tmp_path, monkeypatch)
    client.app.state.calendar = CalendarCollection([NamedCalendar('feed', 'Feed', subscription())])
    result = client.get('/dashboard', params={'days': 7, 'post': False})
    assert result.status_code == 200
    assert [x['uid'] for x in result.json()['calendar']['items']] == ['feed:current']
    assert result.json()['calendar']['error'] is None


def test_display_uses_overlap_exclusive_end_and_reports_unusable_dates(tmp_path, monkeypatch):
    def event(uid, start, end):
        return Event(uid, uid, start, end)
    start = datetime(2030, 1, 1, tzinfo=UTC)
    end = datetime(2030, 1, 8, tzinfo=UTC)
    items = [
        event('ongoing', start-timedelta(hours=1), start+timedelta(hours=1)),
        event('ends-at-boundary', start-timedelta(hours=1), start),
        event('starts-at-boundary', end, end+timedelta(hours=1)),
        event('no-end', start+timedelta(days=1), None),
        event('point', start+timedelta(days=2), start+timedelta(days=2)),
        event('offset', datetime.fromisoformat('2030-01-08T00:30:00+01:00'), datetime.fromisoformat('2030-01-08T01:30:00+01:00')),
        event('unknown', None, None),
        event('naive', datetime(2030, 1, 4), datetime(2030, 1, 4, 1)),
        event('reversed', start+timedelta(days=4), start+timedelta(days=3)),
    ]
    class Reader:
        last_errors = {}
        def events(self, **kwargs):
            return items
    client = _client(tmp_path, monkeypatch)
    client.app.state.calendar = Reader()
    response = client.get('/api/v1/calendar', params={'from': start.isoformat(), 'until': end.isoformat()})
    assert response.status_code == 200
    result = response.json()
    assert [x['uid'] for x in result['items']] == ['ongoing', 'no-end', 'point', 'offset']
    assert result['errors'] == []
    assert len(result['warnings']) == 1
    assert '3' in result['warnings'][0]
    # Undated unrelated entries must not make a missing event look like a failed source.
    assert client.get('/api/v1/calendar/preparation', params={'uid': 'missing', 'start': start.isoformat()}).status_code == 404
    assert len(items) == 9 and items[6].start is None  # no source mutation


def test_all_day_ics_dates_follow_requested_local_days_across_dst(tmp_path, monkeypatch):
    from zoneinfo import ZoneInfo
    zone = ZoneInfo('Europe/Berlin')
    first = datetime(2030, 10, 27, tzinfo=zone)
    until = datetime(2030, 10, 28, tzinfo=zone)
    items = [
        Event('previous-day', 'Previous', datetime(2030, 10, 26, tzinfo=UTC), datetime(2030, 10, 27, tzinfo=UTC), all_day=True),
        Event('requested-day', 'Requested', datetime(2030, 10, 27, tzinfo=UTC), None, all_day=True),
        Event('next-day', 'Next', datetime(2030, 10, 28, tzinfo=UTC), datetime(2030, 10, 29, tzinfo=UTC), all_day=True),
    ]
    class Reader:
        last_errors = {}
        def events(self, **kwargs):
            return items
    client = _client(tmp_path, monkeypatch)
    client.app.state.calendar = Reader()
    # Browser sends UTC boundaries alongside its named zone, including the DST change.
    response = client.get('/api/v1/calendar', params={
        'from': first.astimezone(UTC).isoformat(), 'until': until.astimezone(UTC).isoformat(), 'tz': 'Europe/Berlin'})
    assert response.status_code == 200
    assert [x['uid'] for x in response.json()['items']] == ['requested-day']
    assert response.json()['errors'] == []
    assert items[0].end == datetime(2030, 10, 27, tzinfo=UTC)


def test_dashboard_keeps_recent_followups_and_missing_end_warnings(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.server.datetime', FrozenDateTime)
    items = [
        Event('recent', 'Recent', NOW-timedelta(hours=3), NOW-timedelta(hours=2), attendees=['guest@example.test']),
        Event('ancient', 'Ancient', NOW-timedelta(days=50), NOW-timedelta(days=49), attendees=['guest@example.test']),
        Event('current-day', 'All day', NOW.replace(hour=0), None, all_day=True),
        Event('unknown', 'Unknown', None, None),
    ]
    class Reader:
        last_errors = {}
        def events(self, **kwargs):
            return items
    client = _client(tmp_path, monkeypatch)
    client.app.state.calendar = Reader()
    response = client.get('/dashboard', params={'days': 7, 'post': False})
    assert response.status_code == 200
    result = response.json()['calendar']
    assert [x['uid'] for x in result['items']] == ['current-day']
    assert [x['uid'] for x in result['nachzubereiten']] == ['recent']
    assert result['error'] is None
    assert len(result['warnings']) == 1 and '1' in result['warnings'][0]
    morning = client.get('/api/v1/morning-briefing', params={'post': False}).json()
    assert not any(x['section'] == 'calendar' for x in morning['partial_failures'])


@pytest.mark.parametrize('end_minute', [15, 30])
def test_timed_event_across_repeated_dst_hour_is_not_reversed_or_a_point(tmp_path, monkeypatch, end_minute):
    from zoneinfo import ZoneInfo
    zone = ZoneInfo('Europe/Berlin')
    event = Event('fold', 'Repeated hour',
                  datetime(2030, 10, 27, 2, 30, tzinfo=zone, fold=0),
                  datetime(2030, 10, 27, 2, end_minute, tzinfo=zone, fold=1))
    class Reader:
        last_errors = {}
        def events(self, **kwargs):
            return [event]
    client = _client(tmp_path, monkeypatch)
    client.app.state.calendar = Reader()
    response = client.get('/api/v1/calendar', params={
        'from': '2030-10-27T01:00:00Z', 'until': '2030-10-27T01:10:00Z', 'tz': 'Europe/Berlin'})
    assert response.status_code == 200
    assert [x['uid'] for x in response.json()['items']] == ['fold']
    assert response.json()['errors'] == []
