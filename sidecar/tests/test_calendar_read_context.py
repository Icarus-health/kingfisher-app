"""Read-only calendar previews require a current source authorization context."""
from datetime import datetime, timedelta, timezone

from icarus_memory.connectors.calendar import CalendarError, Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.mac_calendar import MacCalendar, WorkerUpdate
from tests.test_multi_integrations import _client

AT = datetime(2026, 11, 4, tzinfo=timezone.utc)
PARAMS = {'from': AT.isoformat(), 'until': (AT + timedelta(days=7)).isoformat()}


class Reader:
    def __init__(self, uid):
        self.uid, self.failed, self.on_read = uid, False, None
        self.items = [Event(uid, 'Künstlicher Termin', AT + timedelta(hours=10), AT + timedelta(hours=11))]

    def events(self, **kwargs):
        if self.on_read:
            self.on_read()
        if self.failed:
            raise CalendarError('Künstlicher Verbindungsausfall')
        return self.items


def setup_calendar(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    first, second = Reader('a'), Reader('b')
    client.app.state.calendar = CalendarCollection([
        NamedCalendar('a', 'Erster Kalender', first), NamedCalendar('b', 'Zweiter Kalender', second)])
    return client, first, second


def test_read_context_survives_provider_failure_but_empty_success_is_not_failure(tmp_path, monkeypatch):
    client, first, second = setup_calendar(tmp_path, monkeypatch)
    good = client.get('/api/v1/calendar', params=PARAMS).json()
    assert good['read_context'] and good['failed_sources'] == [] and good['read_at']
    first.failed = True
    failed = client.get('/api/v1/calendar', params=PARAMS).json()
    assert failed['read_context'] == good['read_context']
    assert failed['failed_sources'] == ['a']
    assert [r['uid'] for r in failed['items']] == ['b:b']
    second.failed = True
    both = client.get('/api/v1/calendar', params=PARAMS).json()
    assert both['read_context'] == good['read_context'] and set(both['failed_sources']) == {'a', 'b'}
    first.failed = second.failed = False
    first.items = second.items = []
    empty = client.get('/api/v1/calendar', params=PARAMS).json()
    assert empty['read_context'] == good['read_context'] and empty['failed_sources'] == []
    assert empty['items'] == []


def test_rebuilt_source_context_prevents_cached_rows_surviving_account_removal(tmp_path, monkeypatch):
    client, first, second = setup_calendar(tmp_path, monkeypatch)
    before = client.get('/api/v1/calendar', params=PARAMS).json()
    client.app.state.calendar = CalendarCollection([NamedCalendar('b', 'Zweiter Kalender', second)])
    second.failed = True
    after = client.get('/api/v1/calendar', params=PARAMS).json()
    assert before['read_context'] != after['read_context']
    assert after['failed_sources'] == ['b'] and after['items'] == []


def test_source_replacement_during_read_does_not_publish_retired_calendar(tmp_path, monkeypatch):
    client, first, second = setup_calendar(tmp_path, monkeypatch)
    first.on_read = lambda: setattr(client.app.state, 'calendar', None)
    response = client.get('/api/v1/calendar', params=PARAMS)
    assert response.status_code == 409
    assert 'Künstlicher Termin' not in response.text


def test_mac_selection_and_permission_change_invalidate_context_without_new_collection(tmp_path, monkeypatch):
    client, first, second = setup_calendar(tmp_path, monkeypatch)
    mac = MacCalendar(tmp_path / 'calendar-test.sqlite3')
    state = mac.enable()
    calendars = [{'id': 'private', 'name': 'Privat'}, {'id': 'work', 'name': 'Arbeit'}]
    mac.update(WorkerUpdate(generation=state['generation'], status='granted', calendars=calendars))
    mac.select(['private'])
    client.app.state.calendar = CalendarCollection([
        NamedCalendar('mac-calendar', 'Mac', mac), NamedCalendar('b', 'Zweiter Kalender', second)])
    before = client.get('/api/v1/calendar', params=PARAMS).json()['read_context']
    state = mac.select(['work'])
    after = client.get('/api/v1/calendar', params=PARAMS).json()['read_context']
    assert before != after
    mac.update(WorkerUpdate(generation=state['generation'], status='denied'))
    assert client.get('/api/v1/calendar', params=PARAMS).json()['read_context'] != after


def test_mac_authority_change_during_read_discards_response(tmp_path, monkeypatch):
    client, first, second = setup_calendar(tmp_path, monkeypatch)
    mac = MacCalendar(tmp_path / 'calendar-test.sqlite3')
    state = mac.enable()
    mac.update(WorkerUpdate(generation=state['generation'], status='granted', calendars=[{'id':'one','name':'Eins'}]))
    mac.select(['one'])
    client.app.state.calendar = CalendarCollection([
        NamedCalendar('mac-calendar', 'Mac', mac), NamedCalendar('b', 'Zweiter Kalender', second)])
    second.on_read = lambda: mac.select([])
    assert client.get('/api/v1/calendar', params=PARAMS).status_code == 409
