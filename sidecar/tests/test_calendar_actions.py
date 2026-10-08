"""Offline safety checks for the Google calendar action ledger."""
import json
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from icarus_memory import config
from icarus_memory.calendar_actions import CalendarActions, ActionError
from icarus_memory.google_oauth import SCOPES
from icarus_memory.calendar_action_routes import install_routes


class Keys:
    def __init__(self): self.values = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value


class Provider:
    def __init__(self):
        self.writes = []
        self.events = {}
        self.role = 'owner'
        self.fail_after_create = False

    def calendar(self, source, key): return {'id': source.url, 'accessRole': self.role}
    def event(self, source, key, event_id): return self.events.get(event_id)
    def create(self, source, key, body, updates):
        self.writes.append(('create', body['id'], updates))
        self.events[body['id']] = {**body, 'etag': '"v1"'}
        if self.fail_after_create: raise OSError('response lost')
        return self.events[body['id']]
    def patch(self, source, key, event_id, etag, body, updates):
        self.writes.append(('patch', event_id, etag, updates))
        self.events[event_id] = {**self.events[event_id], **body, 'etag': '"v2"'}
        return self.events[event_id]
    def delete(self, source, key, event_id, etag, updates):
        self.writes.append(('delete', event_id, etag, updates))
        self.events.pop(event_id)


def action_service(tmp_path):
    keys, provider = Keys(), Provider()
    source = config.CalendarSourceSettings(id='calendar-one', label='Work', kind='google',
        user='a@example.com', url='a@example.com')
    settings = SimpleNamespace(calendar_sources=[source])
    key = config.integration_secret_name('calendar', source.id)
    keys.set(key, json.dumps({'client_id': 'c', 'refresh_token': 'r', 'grant_id': 'grant-one', 'kind': 'calendar_write', 'scope': ' '.join(SCOPES['calendar_write'])}))
    oauth = SimpleNamespace(keychain=keys)
    service = CalendarActions(tmp_path/'actions.sqlite3', lambda: settings, oauth, provider)
    return service, settings, keys, provider


def test_create_requires_preview_and_double_execution_is_single_write(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    draft = service.draft(kind='create', source_id='calendar-one', title='Team',
        start='2026-10-10T10:00:00+02:00', end='2026-10-10T11:00:00+02:00', send_updates='none')
    assert draft['status'] == 'draft' and draft['preview']['title'] == 'Team'
    assert draft['preview']['attendees'] == []
    first = service.execute(draft['id'], confirmed=True, stand=draft['stand'])
    second = CalendarActions(tmp_path/'actions.sqlite3', service.settings, service.oauth, provider).execute(draft['id'], confirmed=True, stand=draft['stand'])
    assert first['status'] == second['status'] == 'done'
    assert provider.writes == [('create', draft['provider_event_id'], 'none')]


def test_unknown_create_reconciles_same_provider_id_without_duplicate(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    draft = service.draft(kind='create', source_id='calendar-one', title='Team',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    provider.fail_after_create = True
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'uncertain'
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'done'
    assert len(provider.writes) == 1


def test_unknown_create_without_visible_event_does_not_post_again(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    draft = service.draft(kind='create', source_id='calendar-one', title='Team',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    def lost(*args):
        provider.writes.append(('create', draft['provider_event_id']))
        raise OSError('response lost')
    provider.create = lost
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'uncertain'
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'uncertain'
    assert provider.writes == [('create', draft['provider_event_id'])]


def test_changed_grant_blocks_existing_draft(tmp_path):
    service, _, keys, provider = action_service(tmp_path)
    draft = service.draft(kind='create', source_id='calendar-one', title='Team',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    keys.set(config.integration_secret_name('calendar', 'calendar-one'), json.dumps({
        'client_id': 'c', 'refresh_token': 'other', 'grant_id': 'grant-two', 'kind': 'calendar_write', 'scope': ' '.join(SCOPES['calendar_write'])}))
    with pytest.raises(ActionError): service.execute(draft['id'], confirmed=True, stand=draft['stand'])
    assert provider.writes == []


def test_refresh_token_rotation_does_not_invalidate_draft(tmp_path):
    service, _, keys, _ = action_service(tmp_path)
    draft = service.draft(kind='create', source_id='calendar-one', title='Team',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    key = config.integration_secret_name('calendar', 'calendar-one')
    rotated = json.loads(keys.get(key))
    rotated['refresh_token'] = 'rotated'
    keys.set(key, json.dumps(rotated))
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'done'


def test_removed_source_blocks_old_draft(tmp_path):
    service, settings, _, provider = action_service(tmp_path)
    draft = service.draft(kind='create', source_id='calendar-one', title='Team',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    settings.calendar_sources.clear()
    with pytest.raises(ActionError): service.execute(draft['id'], confirmed=True, stand=draft['stand'])
    assert provider.writes == []


def test_edit_binds_etag_and_unknown_does_not_retry(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    provider.events['evt'] = {'id': 'evt', 'etag': '"v1"', 'summary': 'Old',
        'start': {'dateTime': '2026-10-10T10:00:00Z'}, 'end': {'dateTime': '2026-10-10T11:00:00Z'},
        'attendees': [{'email': 'guest@example.com'}]}
    draft = service.draft(kind='edit', source_id='calendar-one', event_id='evt', title='New',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='all')
    assert draft['preview']['attendees'] == ['guest@example.com']
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'done'
    assert provider.writes == [('patch', 'evt', '"v1"', 'all')]


def test_edit_response_must_confirm_requested_event_and_fields(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    provider.events['evt'] = {'id': 'evt', 'etag': '"v1"', 'summary': 'Old',
        'start': {'dateTime': '2026-10-10T10:00:00Z'}, 'end': {'dateTime': '2026-10-10T11:00:00Z'}}
    provider.patch = lambda *args: {'id': 'other', 'summary': 'New',
        'start': {'dateTime': '2026-10-10T10:00:00Z'}, 'end': {'dateTime': '2026-10-10T11:00:00Z'}}
    draft = service.draft(kind='edit', source_id='calendar-one', event_id='evt', title='New',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'uncertain'


def test_ambiguous_edit_is_not_retried(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    provider.events['evt'] = {'id': 'evt', 'etag': '"v1"', 'summary': 'Old',
        'start': {'dateTime': '2026-10-10T10:00:00Z'}, 'end': {'dateTime': '2026-10-10T11:00:00Z'}}
    def lost(*args):
        provider.writes.append(('patch', 'evt'))
        raise OSError('response lost')
    provider.patch = lost
    draft = service.draft(kind='edit', source_id='calendar-one', event_id='evt', title='New',
        start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'uncertain'
    with pytest.raises(ActionError): service.execute(draft['id'], confirmed=True, stand=draft['stand'])
    assert len(provider.writes) == 1


def test_read_only_or_lost_access_never_writes(tmp_path):
    service, _, keys, provider = action_service(tmp_path)
    key = config.integration_secret_name('calendar', 'calendar-one')
    keys.set(key, json.dumps({'client_id': 'c', 'refresh_token': 'r',
        'kind': 'calendar', 'scope': ' '.join(SCOPES['calendar_write'])}))
    assert service.sources()['sources'][0]['can_write'] is False
    with pytest.raises(ActionError): service.draft(kind='create', source_id='calendar-one',
        title='Team', start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    keys.set(key, json.dumps({'client_id': 'c', 'refresh_token': 'r',
        'kind': 'calendar_write', 'scope': ' '.join(SCOPES['calendar_write'])}))
    provider.role = 'reader'
    with pytest.raises(ActionError): service.draft(kind='create', source_id='calendar-one',
        title='Team', start='2026-10-10T10:00:00Z', end='2026-10-10T11:00:00Z', send_updates='none')
    assert provider.writes == []


def test_locked_or_recurring_event_cannot_be_drafted(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    event = {'id': 'evt', 'etag': '"v1"', 'summary': 'Old',
        'start': {'dateTime': '2026-10-10T10:00:00Z'}, 'end': {'dateTime': '2026-10-10T11:00:00Z'}}
    provider.events['evt'] = {**event, 'locked': True}
    with pytest.raises(ActionError): service.draft(kind='cancel', source_id='calendar-one',
        event_id='evt', send_updates='none')
    provider.events['evt'] = {**event, 'recurrence': ['RRULE:FREQ=WEEKLY']}
    with pytest.raises(ActionError): service.draft(kind='edit', source_id='calendar-one',
        event_id='evt', title='New', start='2026-10-10T10:00:00Z',
        end='2026-10-10T11:00:00Z', send_updates='none')
    assert provider.writes == []


@pytest.mark.parametrize('start,end,title', [
    ('2026-10-10T10:00:00', '2026-10-10T11:00:00Z', 'Team'),
    ('2026-10-10T10:00:00Z', '2026-10-10T09:00:00Z', 'Team'),
    ('2026-10-10T10:00:00Z', '2026-10-10T11:00:00Z', '  '),
])
def test_invalid_event_never_writes(tmp_path, start, end, title):
    service, _, _, provider = action_service(tmp_path)
    with pytest.raises(ActionError):
        service.draft(kind='create', source_id='calendar-one', title=title,
            start=start, end=end, send_updates='none')
    assert provider.writes == []


def test_route_requires_guard_and_explicit_matching_confirmation(tmp_path):
    service, settings, keys, provider = action_service(tmp_path)
    app = FastAPI()
    app.state.settings = settings
    app.state.google_oauth = service.oauth
    def guard(x_icarus_token: str | None = Header(default=None)):
        if x_icarus_token != 'local-test': raise HTTPException(401)
    install_routes(app, [Depends(guard)], lambda: tmp_path, provider=provider)
    with TestClient(app) as client:
        assert client.get('/api/v1/calendar-actions/sources').status_code == 401
        headers = {'X-Icarus-Token': 'local-test'}
        created = client.post('/api/v1/calendar-actions/drafts', headers=headers, json={
            'kind': 'create', 'source_id': 'calendar-one', 'title': 'Team',
            'start': '2026-10-10T10:00:00Z', 'end': '2026-10-10T11:00:00Z',
            'send_updates': 'none'})
        assert created.status_code == 201
        draft = created.json()
        url = '/api/v1/calendar-actions/drafts/' + draft['id'] + '/execute'
        assert client.post(url, headers=headers, json={'confirmed': False, 'stand': draft['stand']}).status_code == 422
        assert client.post(url, headers=headers, json={'confirmed': True, 'stand': '0'*64}).status_code == 409
        assert provider.writes == []
        assert client.post(url, headers=headers, json={'confirmed': True, 'stand': draft['stand']}).json()['status'] == 'done'


@pytest.mark.parametrize('organizer', [None, {}, {'self': False, 'email':'other@example.com'}])
def test_cancel_requires_proven_organizer_copy(tmp_path, organizer):
    service, _, _, provider = action_service(tmp_path)
    provider.events['evt'] = {'id':'evt', 'etag':'"v1"', 'summary':'Invitation', 'organizer':organizer}
    with pytest.raises(ActionError, match='Organisator'):
        service.draft(kind='cancel', source_id='calendar-one', event_id='evt', send_updates='all')
    assert provider.writes == []


def test_owned_event_can_be_cancelled_once(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    provider.events['evt'] = {'id':'evt', 'etag':'"v1"', 'summary':'Own event', 'organizer':{'self':True}, 'attendees':[{'email':'guest@example.com'}]}
    draft = service.draft(kind='cancel', source_id='calendar-one', event_id='evt', send_updates='all')
    assert draft['preview']['attendees'] == ['guest@example.com']
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'done'
    assert service.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'done'
    assert provider.writes == [('delete', 'evt', '"v1"', 'all')]


def test_mismatched_provider_event_cannot_be_previewed(tmp_path):
    service, _, _, provider = action_service(tmp_path)
    provider.events['evt'] = {'id':'other', 'etag':'"v1"', 'summary':'Wrong', 'organizer':{'self':True}}
    with pytest.raises(ActionError):
        service.draft(kind='cancel', source_id='calendar-one', event_id='evt', send_updates='all')
    assert provider.writes == []


def test_main_application_installs_guarded_durable_calendar_workflow(tmp_path, monkeypatch):
    from icarus_memory.server import create_app, TOKEN_ENV
    monkeypatch.setenv(TOKEN_ENV, 'synthetic-action-token')
    fixture, _, _, provider = action_service(tmp_path)
    app = create_app()
    actions = app.state.calendar_actions
    actions.settings, actions.oauth, actions.provider = fixture.settings, fixture.oauth, provider
    headers = {'X-Icarus-Token':'synthetic-action-token'}
    with TestClient(app) as client:
        assert client.get('/api/v1/calendar-actions/sources').status_code == 401
        assert client.get('/api/v1/calendar-actions/sources', headers=headers).json()['sources'][0]['can_write'] is True
        draft = client.post('/api/v1/calendar-actions/drafts', headers=headers, json={
            'kind':'create', 'source_id':'calendar-one', 'title':'Explicit test',
            'start':'2026-11-01T10:00:00Z', 'end':'2026-11-01T11:00:00Z', 'send_updates':'none'}).json()
        assert provider.writes == []
        path = '/api/v1/calendar-actions/drafts/' + draft['id']
        assert client.post(path + '/execute', headers=headers, json={'confirmed':True, 'stand':draft['stand']}).json()['status'] == 'done'
        assert client.get(path, headers=headers).json()['status'] == 'done'
        assert len(provider.writes) == 1
    reopened = CalendarActions(actions.path, fixture.settings, fixture.oauth, provider)
    assert reopened.get(draft['id'])['status'] == 'done'
    assert reopened.execute(draft['id'], confirmed=True, stand=draft['stand'])['status'] == 'done'
    assert len(provider.writes) == 1
