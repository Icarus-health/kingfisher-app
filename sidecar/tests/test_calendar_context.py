from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.calendar_context import snapshot

AT = datetime(2026, 9, 13, 10, tzinfo=timezone.utc)


def state():
    return dict(enabled=True, selected=['work'], status='granted', error='',
                synced_at=AT.isoformat(), range_from=AT.isoformat(),
                range_to=(AT + timedelta(days=8)).isoformat(), events=[
                    dict(uid='meeting-1', summary='Mainz', start=(AT + timedelta(hours=1)).isoformat(),
                         end=(AT + timedelta(hours=2)).isoformat(), source_id='work',
                         source_label='Arbeit', location='Mainz', all_day=False, attendees=['A'])])


def test_snapshot_preserves_identity_time_and_source():
    result = snapshot(state(), at=AT)
    assert result['status'] == 'available'
    assert result['events'][0]['uid'] == 'meeting-1'
    assert result['events'][0]['source_id'] == 'work'
    assert result['synced_at'] == AT.isoformat()
    assert result['coverage'] == 'covered'


@pytest.mark.parametrize('change,status', [
    ({'enabled': False}, 'disabled'), ({'status': 'denied'}, 'unavailable'),
    ({'synced_at': (AT - timedelta(minutes=6)).isoformat()}, 'stale'),
    ({'synced_at': (AT + timedelta(minutes=1)).isoformat()}, 'stale'),
    ({'synced_at': None}, 'stale'), ({'error': 'secret-token'}, 'unavailable'),
])
def test_unusable_snapshot_never_exposes_events(change, status):
    raw = state(); raw.update(change)
    result = snapshot(raw, at=AT)
    assert result['status'] == status
    assert result['events'] == []
    assert 'secret-token' not in str(result)


def test_filter_window_selection_and_bound_payload():
    raw = state()
    event = raw['events'][0]
    raw['events'] = [{**event, 'uid': str(i), 'summary': 'x' * 10000} for i in range(30)]
    raw['events'] += [{**event, 'uid': 'foreign', 'source_id': 'private'},
                      {**event, 'uid': 'expired', 'end': (AT - timedelta(seconds=1)).isoformat()},
                      {**event, 'uid': 'naive', 'start': '2026-09-13T11:00:00'}]
    result = snapshot(raw, at=AT)
    assert len(result['events']) == 12
    assert result['truncated'] is True
    assert result['invalid_count'] > 0
    assert len(str(result)) < 20000
    assert 'foreign' not in str(result)


def test_missing_coverage_is_unknown_not_complete():
    raw = state(); raw.pop('range_to')
    assert snapshot(raw, at=AT)['coverage'] == 'unknown'


def test_real_app_wires_calendar_context_and_persists_snapshot(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.mac_calendar import WorkerUpdate
    from icarus_memory.providers import Reply
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    class Provider:
        is_local = True
        messages = []
        def complete(self, messages, tools):
            self.messages = messages
            return Reply(text='Meinst du deinen Termin in Mainz?')
    provider = Provider()
    app.state.agent._provider = provider
    cal = app.state.mac_calendar
    enabled = cal.enable()
    cal.update(WorkerUpdate(generation=enabled['generation'], status='granted',
                           calendars=[{'id': 'work', 'name': 'Arbeit'}]))
    selected = cal.select(['work'])
    now = datetime.now(timezone.utc)
    event = state()['events'][0]
    event.update(start=(now + timedelta(hours=1)).isoformat(), end=(now + timedelta(hours=2)).isoformat())
    cal.update(WorkerUpdate(generation=selected['generation'], status='granted',
                           calendars=[{'id': 'work', 'name': 'Arbeit'}], events=[event],
                           range_from=now, range_to=now + timedelta(days=8)))
    client = TestClient(app)
    conversation = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    result = client.post(f'/api/v1/conversations/{conversation}/messages', json={'message': 'Was ist mit Mainz?'})
    assert result.status_code == 201
    assert provider.messages == []
    stored = app.state.conversations.messages(conversation)[-1]
    assert stored.metadata['context']['calendar']['events'][0]['uid'] == 'meeting-1'
    assert stored.metadata['context']['history_egress'] == 'local_only'
    cal.disconnect()
    result = client.post(f'/api/v1/conversations/{conversation}/messages', json={'message': 'Und jetzt?'})
    assert result.status_code == 201
    assert 'meeting-1' not in str(provider.messages)
    assert 'Meinst du deinen Termin' not in str(provider.messages)


def test_worker_utc_z_timestamps_are_accepted():
    # EventKit snapshots use Pydantic JSON UTC timestamps, including Python 3.10.
    raw = state()
    raw['synced_at'] = raw['synced_at'].replace('+00:00', 'Z')
    raw['range_from'] = raw['range_from'].replace('+00:00', 'Z')
    raw['range_to'] = raw['range_to'].replace('+00:00', 'Z')
    for event in raw['events']:
        event['start'] = event['start'].replace('+00:00', 'Z')
        event['end'] = event['end'].replace('+00:00', 'Z')
    result = snapshot(raw, at=AT)
    assert result['status'] == 'available'
    assert result['coverage'] == 'covered'
    assert len(result['events']) == 1
