"""Local confirmation through the ordinary chat, approval and task HTTP routes."""

import socket
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, server
from icarus_memory.providers import Reply, ToolCall
from tests.test_conversation_retraction import _close_app


TOOL = 'aufgabe_erledigt'
TITLE = 'LINDENBOGEN-46 Materialliste archivieren'
TOKEN = 'synthetic-task-owner'


class SyntheticProvider:
    name = model = 'synthetic'
    is_local = True
    is_remote = False

    def __init__(self):
        self.calls = []
        self.arguments = None

    def complete(self, messages, tools):
        self.calls.append(messages)
        if self.arguments is not None:
            arguments, self.arguments = self.arguments, None
            assert TOOL in str(tools)
            return Reply(tool_calls=[ToolCall('synthetic-call', TOOL, arguments)])
        return Reply(text='Synthetische Antwort.')


@pytest.fixture
def session(monkeypatch):
    def no_connect(*args, **kwargs):
        raise AssertionError('Synthetic task approval must not connect to a socket.')

    monkeypatch.setattr(socket.socket, 'connect', no_connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', no_connect)
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', TOKEN)
    monkeypatch.setenv('KINGFISHER_MCP_TUER', '0')
    provider = SyntheticProvider()
    monkeypatch.setattr(server, 'provider_from_env', lambda: provider)
    app = server.create_app(SelfModelStore(MemoryBackend(), subject_id='synthetic'))
    app.state.agent._saetze = False
    client = TestClient(app, headers={'X-Icarus-Token': TOKEN})
    try:
        yield app, client, provider
    finally:
        client.close()
        _close_app(app)


def read(response, expected=200):
    assert response.status_code == expected, response.text
    return response.json()


def new_task(client):
    task = read(client.post('/api/v1/tasks', json={'title': TITLE}), 201)
    return task['id'], f"/api/v1/tasks/{task['id']}"


def ask(client, provider, arguments):
    conversation = read(client.post('/api/v1/conversations', json={}), 201)['conversation']['id']
    url = f'/api/v1/conversations/{conversation}'
    provider.arguments = arguments
    return url, read(client.post(url + '/messages', json={
        'message': 'Sag nur Hallo.', 'answer_mode': 'chat',
    }), 201)


def pending(client, provider, identifier, *, level='confirm'):
    url, response = ask(client, provider, {'id': identifier})
    action, = response['action_requests']
    assert (action['state'], action['level'], action['action_class']) == ('pending', level, 'write_local')
    assert TITLE in action['dry_run'] and identifier in action['dry_run']
    assert TITLE not in str(response['messages'][-1]['metadata']['approvals'])
    return f"{url}/approvals/{action['id']}"


def history(client, path):
    return read(client.get(path + '/history'))['items']


def resolve(client, path, *, granted=True, confirmation=None):
    return read(client.post(path, json={'granted': granted, 'confirmation': confirmation}))


@pytest.mark.parametrize('reject_first', [False, True])
def test_default_chat_stays_open_until_a_fresh_grant(session, reject_first):
    app, client, provider = session
    identifier, path = new_task(client)
    approval = pending(client, provider, identifier)
    assert read(client.get(path))['status'] == 'open'
    assert [event['kind'] for event in history(client, path)] == ['created']
    confirmation = None
    if reject_first:
        assert resolve(client, approval, granted=False)['action_requests'][0]['state'] == 'rejected'
        assert read(client.get(path))['status'] == 'open'
        approval = pending(client, provider, identifier, level='confirm_strict')
        assert read(client.post(approval, json={'granted': True}), 409)
        confirmation = TOOL
    before = len(provider.calls)
    assert resolve(client, approval, confirmation=confirmation)['action_requests'][0]['state'] == 'approved'
    assert len(provider.calls) == before  # no model recap
    task = read(client.get(path))
    event, _ = history(client, path)
    assert task['status'] == 'done'
    assert event['kind'] == 'user_confirmed_completion'
    assert event['actor_id'] is None and event['after']['done_at'] == task['done_at']
    assert read(client.post(approval, json={'granted': True, 'confirmation': confirmation}), 409)
    assert len(history(client, path)) == 2
    assert app.state.claims.all_claims() == []
    conversation = approval.split('/approvals/')[0]
    read(client.post(conversation + '/messages', json={'message': 'Sag Danke.', 'answer_mode': 'chat'}), 201)
    assert 'Erledigung der Aufgabe bestätigt.' not in str(provider.calls[-1])
    assert TITLE not in str(provider.calls[-1])


@pytest.mark.parametrize('change', ['edit', 'edit-aba', 'complete-reopen', 'drop', 'replace', 'execution-time'])
def test_pending_confirmation_cannot_complete_changed_task(session, monkeypatch, change):
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.tasks import TaskStore

    app, client, provider = session
    if change == 'replace':
        source = Provenance(source_type=SourceType.USER_STATED)
        task = app.state.tasks.from_suggestion('synthetic-reuse', TITLE, source, angelegt={'art': 'automatisch'})
        identifier, path = task.id, f'/api/v1/tasks/{task.id}'
    else:
        identifier, path = new_task(client)
    approval = pending(client, provider, identifier)
    if change.startswith('edit'):
        read(client.patch(path, json={'title': 'Neue synthetische Aufgabe'}))
        if change == 'edit-aba':
            read(client.patch(path, json={'title': TITLE}))
    elif change == 'complete-reopen':
        app.state.tasks.complete(identifier)
        read(client.post(path + '/reopen'))
    elif change == 'drop':
        read(client.post(path + '/drop'))
    elif change == 'replace':
        app.state.tasks.anlage_entfernen(identifier)
        assert app.state.tasks.from_suggestion('synthetic-reuse', TITLE, source).id == identifier
    else:
        original_transaction = app.state.tasks._transaction

        @contextmanager
        def change_before_begin():
            assert not app.state.agent.policy.pending()
            # Commit an independent writer after the grant, before the completion transaction.
            writer = TaskStore(app.state.tasks._path)
            try:
                writer.edit(identifier, title='Parallele synthetische Änderung')
            finally:
                writer.close()
            with original_transaction():
                yield

        monkeypatch.setattr(app.state.tasks, '_transaction', change_before_begin)

    result = resolve(client, approval)
    assert result['action_requests'][0]['state'] == 'rejected'
    assert 'inzwischen geändert' in result['messages'][-1]['content']
    assert read(client.get(path))['status'] == ('dropped' if change == 'drop' else 'open')
    assert all(event['kind'] != 'user_confirmed_completion' for event in history(client, path))
    assert app.state.audit.entries(1)[0]['outcome'] == 'refused'


@pytest.mark.parametrize('source', ['legacy', 'mail'])
def test_direct_done_appends_one_confirmation_to_existing_completion(session, source):
    from datetime import datetime

    from messlatte.uhr import eingefrorene_zeit

    app, client, _ = session
    identifier, path = new_task(client)
    older = datetime.fromisoformat('2026-09-24T13:05:00+00:00')
    later = datetime.fromisoformat('2026-09-24T14:05:00+00:00')
    with eingefrorene_zeit(older):
        if source == 'legacy':
            app.state.tasks.complete(identifier)
        else:
            app.state.tasks.post_erledigen(identifier, {'episode_id': 'synthetic-mail'})
    old, created = history(client, path)
    assert old['kind'] == ('completed' if source == 'legacy' else 'post_completed')
    with eingefrorene_zeit(later):
        completed = read(client.post(path + '/done'))
        assert completed['status'] == 'done'
        assert datetime.fromisoformat(completed['done_at']) == older
        confirmation, *prior = history(client, path)
        assert confirmation['kind'] == 'user_confirmed_completion'
        assert confirmation['actor_id'] is None
        assert datetime.fromisoformat(confirmation['recorded_at']) == later
        assert prior == [old, created]
        assert read(client.post(path + '/done')) == completed
        # The legacy HTTP button is also an authenticated direct user action.
        assert read(client.post(f'/tasks/{identifier}/done')) == completed
        read(client.patch(path, json={'title': 'Titel später angepasst'}))
        assert read(client.post(path + '/done'))['done_at'] == completed['done_at']
        assert sum(row['kind'] == 'user_confirmed_completion' for row in history(client, path)) == 1
        read(client.post(path + '/reopen'))
        assert read(client.post(f'/tasks/{identifier}/done'))['status'] == 'done'
    assert sum(row['kind'] == 'user_confirmed_completion' for row in history(client, path)) == 2


def test_model_cannot_forge_snapshot_or_confirmation_even_with_standing_permission(session):
    _, client, provider = session
    identifier, path = new_task(client)
    forged = {'id': identifier, 'snapshot': {'id': identifier, 'sequence': 1}, 'confirmed': True}
    _, response = ask(client, provider, forged)
    assert not response['action_requests']
    assert read(client.get(path))['status'] == 'open'
    read(client.post('/rules', json={
        'name': 'Synthetische Dauerregel', 'tool': TOOL, 'stufe': 'notify', 'passt_auf': {'id': identifier},
    }), 201)
    _, response = ask(client, provider, forged)
    assert not response['action_requests']
    assert read(client.get(path))['status'] == 'open'

    _, response = ask(client, provider, {'id': identifier})
    assert not response['action_requests']
    assert read(client.get(path))['status'] == 'done'
    assert history(client, path)[0]['kind'] == 'completed'


def test_mcp_preview_hides_task_title_but_local_approval_shows_it(session, monkeypatch):
    from icarus_memory.mcp import PREFIX, Bridge, Server

    _, client, _ = session
    identifier, path = new_task(client)
    monkeypatch.setenv('KINGFISHER_MCP_TUER', '1')
    external = read(client.post(f'/tools/{TOOL}', json={'id': identifier}))
    action, = external['approvals']
    assert not external['ok'] and identifier in action['dry_run']
    assert TITLE not in str(external)
    assert action['arguments'] == {'id': identifier}
    assert 'snapshot' not in str(external) and 'sequence' not in str(external)
    assert read(client.get(path))['status'] == 'open'
    bridge = Server(Bridge('http://testserver', None, client=client))
    listing = bridge.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                             'params': {'name': f'{PREFIX}freigaben', 'arguments': {'local_preview': True}}})
    assert identifier in str(listing['result']) and TITLE not in str(listing['result'])
    assert 'snapshot' not in str(listing) and 'sequence' not in str(listing)
    local, = read(client.get('/approvals', params={'local_preview': True}))
    assert local['id'] == action['id']
    assert TITLE in local['dry_run'] and identifier in local['dry_run']
    assert 'snapshot' not in str(local) and 'sequence' not in str(local)
    assert resolve(client, '/approvals/' + local['id'])['approval_outcome'] == 'approved'
    assert history(client, path)[0]['kind'] == 'user_confirmed_completion'


def test_completion_policy_retains_taint_denial_and_explicit_overrides():
    from types import SimpleNamespace

    from icarus_memory.policy import ActionClass, ApprovalLevel, Policy

    write = ActionClass.WRITE_LOCAL
    assert Policy().decide(TOOL, write, {}).level is ApprovalLevel.CONFIRM
    assert Policy().decide('aufgabe_anlegen', write, {}).level is ApprovalLevel.NOTIFY
    rule = SimpleNamespace(name='Testregel', stufe='notify')
    assert Policy().decide(TOOL, write, {}, regel=rule, tainted=True).level is ApprovalLevel.CONFIRM_STRICT
    assert Policy().decide(TOOL, write, {}, constraints=[TOOL], regel=rule).denied
    assert Policy(levels={write: ApprovalLevel.DENY}).decide(TOOL, write, {}, regel=rule).denied
    assert Policy(overrides={TOOL: ApprovalLevel.DENY}).decide(TOOL, write, {}, regel=rule).denied
    explicit = Policy(overrides={TOOL: ApprovalLevel.NOTIFY})
    assert explicit.decide(TOOL, write, {}).level is ApprovalLevel.NOTIFY
    assert explicit.decide(TOOL, write, {}, tainted=True).level is ApprovalLevel.CONFIRM
