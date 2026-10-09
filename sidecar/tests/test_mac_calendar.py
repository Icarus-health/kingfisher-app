from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from icarus_memory.mac_calendar import MacCalendar, WorkerUpdate
from icarus_memory.connectors.calendar import CalendarError


def update(generation, **kwargs):
    return WorkerUpdate(generation=generation, status='granted',
                        calendars=[{'id': 'private', 'name': 'Privat'}], **kwargs)


def event():
    at = datetime.now(timezone.utc)
    return dict(uid='occurrence-1', summary='Synthetischer Termin', start=at.isoformat(),
                end=(at + timedelta(hours=1)).isoformat(), source_id='private')


def connected(tmp_path):
    cal = MacCalendar(tmp_path / 'calendar.sqlite3')
    state = cal.enable()
    cal.update(update(state['generation']))
    state = cal.select(['private'])
    cal.update(update(state['generation'], events=[event()]))
    return cal, state


def test_selection_persistence_and_disconnect_race(tmp_path):
    cal, state = connected(tmp_path)
    assert len(MacCalendar(cal.path).events()) == 1
    cal.disconnect()
    with pytest.raises(HTTPException) as error:
        cal.update(update(state['generation'], events=[event()]))
    assert error.value.status_code == 409
    assert cal.read()['events'] == []
    assert cal.events() == []


def test_no_unselected_or_naive_event(tmp_path):
    cal, state = connected(tmp_path)
    for change in ({'source_id': 'other'}, {'start': '2026-09-07T10:00:00'}):
        with pytest.raises(HTTPException):
            cal.update(update(state['generation'], events=[dict(event(), **change)]))
    assert len(cal.events()) == 1


def test_revocation_and_staleness(tmp_path):
    cal, state = connected(tmp_path)
    cal.change(lambda s: s.update(synced_at=(datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()))
    with pytest.raises(CalendarError):
        cal.events()
    cal.update(WorkerUpdate(generation=state['generation'], status='denied'))
    assert cal.read()['events'] == []


def test_empty_selection_never_imports_all(tmp_path):
    cal, state = connected(tmp_path)
    state = cal.select([])
    with pytest.raises(HTTPException):
        cal.update(update(state['generation'], events=[event()]))
    assert cal.events() == []


def test_api_authentication(monkeypatch):
    from icarus_memory.server import create_app, TOKEN_ENV
    monkeypatch.setenv(TOKEN_ENV, 'synthetic-calendar-test-token')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/mac-calendar').status_code == 401
        assert client.post('/api/v1/mac-calendar/worker', json={}).status_code == 401
        assert client.get('/api/v1/mac-calendar', headers={'X-Icarus-Token': 'synthetic-calendar-test-token'}).status_code == 200


def test_calendar_overview_retains_partial_results(monkeypatch):
    from icarus_memory.server import create_app, TOKEN_ENV
    from icarus_memory.connectors.calendar import Event
    monkeypatch.setenv(TOKEN_ENV, 'synthetic-calendar-test-token')
    app = create_app()
    class Reader:
        last_errors = {'unavailable': 'Quelle nicht erreichbar'}
        def events(self, days):
            assert days == 7
            return [Event(uid='test', summary='Testtermin', start=None, end=None)]
    with TestClient(app) as client:
        app.state.calendar = Reader()
        headers = {'X-Icarus-Token': 'synthetic-calendar-test-token'}
        assert client.get('/api/v1/calendar').status_code == 401
        data = client.get('/api/v1/calendar', headers=headers).json()
        assert data['items'][0]['summary'] == 'Testtermin'
        assert data['errors'] == ['Quelle nicht erreichbar']
        assert client.get('/api/v1/calendar?days=100', headers=headers).status_code == 422


def test_year_requires_complete_snapshot(tmp_path):
    cal, state = connected(tmp_path)
    start = datetime(datetime.now().year, 1, 1, tzinfo=timezone.utc)
    finish = start.replace(year=start.year + 1)
    days = (finish - start).days
    with pytest.raises(CalendarError, match='angefragten Zeitraum'):
        cal.events(days=days, at=start)
    body = update(state['generation'], events=[event()], range_from=start, range_to=finish)
    cal.update(body)
    assert len(cal.events(days=days, at=start)) == 1


def test_short_period_outside_known_snapshot_coverage_is_not_silently_empty(tmp_path):
    cal, state = connected(tmp_path)
    covered_from = datetime(2026, 10, 1, tzinfo=timezone.utc)
    covered_to = datetime(2026, 11, 1, tzinfo=timezone.utc)
    cal.update(update(state['generation'], events=[], range_from=covered_from, range_to=covered_to))

    with pytest.raises(CalendarError, match='angefragten Zeitraum'):
        cal.events(days=7, at=datetime(2026, 12, 1, tzinfo=timezone.utc))


def test_participants_survive_snapshot_restart_and_disappear_on_disconnect(tmp_path):
    cal, state = connected(tmp_path)
    cal.update(update(state['generation'], events=[dict(event(), attendees=['Alex <alex@example.invalid>'])]))
    restored = MacCalendar(cal.path)
    assert restored.events()[0].to_dict()['attendees'] == ['Alex <alex@example.invalid>']
    # Alte Worker-Snapshots bleiben kompatibel; keine Teilnehmer werden erraten.
    cal.update(update(state['generation'], events=[event()]))
    assert restored.events()[0].attendees == []
    cal.disconnect()
    assert restored.events() == []


def test_participant_payload_is_bounded():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        update(1, events=[dict(event(), attendees=['x' * 4097])])
    with pytest.raises(ValidationError):
        update(1, events=[dict(event(), attendees=['Alex'] * 1001)])


def test_persisted_zulu_and_offset_times_are_readable(tmp_path):
    cal, state = connected(tmp_path)
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    def persisted(s):
        s['seen_at'] = start.isoformat().replace('+00:00', 'Z')
        s['synced_at'] = s['seen_at']
        s['range_from'] = (start - timedelta(days=1)).isoformat()
        s['range_to'] = (start + timedelta(days=8)).isoformat()
        s['events'][0]['start'] = s['seen_at']
        s['events'][0]['end'] = end.astimezone(timezone(timedelta(hours=2))).isoformat()
    cal.change(persisted)
    restored = MacCalendar(cal.path)
    assert restored.public()['online']
    item = restored.events(at=start)[0]
    assert item.start == start
    assert item.end == end


def test_changed_and_deleted_events_replace_snapshot_without_duplicates(tmp_path):
    cal, state = connected(tmp_path)
    changed = dict(event(), summary='Geänderter Termin')
    cal.update(update(state['generation'], events=[changed]))
    cal.update(update(state['generation'], events=[changed]))
    restored = MacCalendar(cal.path)
    assert len(restored.events()) == 1
    assert restored.events()[0].summary == 'Geänderter Termin'
    cal.update(update(state['generation'], events=[]))
    assert restored.events() == []
    cal.update(update(state['generation'], events=[]))
    assert MacCalendar(cal.path).events() == []


def test_explicit_period_requires_known_snapshot_coverage(tmp_path):
    cal, _ = connected(tmp_path)
    with pytest.raises(CalendarError, match='angefragten Zeitraum'):
        cal.events(days=7, at=datetime(1999, 1, 1, tzinfo=timezone.utc))


def test_os_permission_revocation_removes_memory_source_authority(tmp_path):
    from icarus_memory.calendar_memory import quelle_fuer_mac
    cal, state = connected(tmp_path)
    source = quelle_fuer_mac('private')
    assert cal.freigegeben(source)
    cal.update(WorkerUpdate(generation=state['generation'], status='denied'))
    assert not cal.freigegeben(source)
