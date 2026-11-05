"""Authenticated recall with an independently inventoried synthetic mailbox."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory.config import MailAccountSettings
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_intake import Intake
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _conversation
from tests.test_task_completion_confirmation import read

ACCOUNT = 'synthetic-unopened-account'
SUBJECT = 'Bericht zur Bogenpresse BP-726'
ORIGINAL = 'Bogenpresse BP-726: Der Probelauf ist nur nach der Freigabe möglich.'
QUESTION = 'Bis wann muss der Probelauf der Bogenpresse BP-726 stattfinden?'


class Mailbox:
    def __init__(self):
        self.body_requests = []
        self.release = False
        self.generation = '71'

    def inventory_page(self, folder, after_uid=0, before_uid=None, limit=100, uidvalidity=None):
        assert folder == 'INBOX'
        if uidvalidity and uidvalidity != self.generation:
            from icarus_memory.connectors.mail import MailboxGenerationChanged
            raise MailboxGenerationChanged('synthetic generation reset')
        upper = 3 if before_uid is None else min(before_uid, 3)
        end = min(upper, after_uid + limit)
        return {'folder': folder, 'uidvalidity': self.generation, 'upper_uid': upper,
                'uids': list(range(after_uid + 1, end + 1)), 'next_uid': end, 'done': end >= upper}

    def message_in_folder(self, folder, uid):
        self.body_requests.append(uid)
        if self.release and uid in {'71.1', '71.2'}:
            body = 'Technischer Hinweis: Die Förderleitung bleibt unverändert.'
            return Message(uid, 'Förderleitung', 'writer@example.invalid', None, body, False, body=body)
        if uid == '71.2':
            raise OSError('synthetic-private-provider-error')
        assert uid == '71.3', 'Recall cannot fetch an inventoried mail body.'
        return Message(uid, SUBJECT, 'writer@example.invalid', datetime(2026, 9, 2, tzinfo=timezone.utc),
                       ORIGINAL, False, body=ORIGINAL)


@pytest.fixture
def intake_session(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    app.state.agent._saetze = False
    app.state.agent._working_memory_search = None
    box = Mailbox()
    settings = app.state.settings
    settings.mail_accounts = [MailAccountSettings(id=ACCOUNT, label='Synthetic',
        imap_host='synthetic.example.invalid', user='synthetic-private-account@example.invalid')]
    settings.schedule.mail_accounts = [ACCOUNT]
    settings.schedule.enabled = True
    app.state.mail = SimpleNamespace(reader_for=lambda _: box)
    intake = Intake(app.state.episodes)
    try:
        intake.start(ACCOUNT, ['INBOX'])
        captured, = intake.step(ACCOUNT, box, batch=2)
        store = WorkingMemoryStore(app.state.episodes)
        snapshot, = store.pending(episode_ids=[captured])
        assert store.commit(snapshot, [{'start': 0, 'end': len(snapshot.episode.body), 'kind': 'conditional'}],
                            model='synthetic')
        calls = []

        def select(messages, *, max_tokens, schema):
            data = json.loads(messages[-1]['content'])
            assert 'sources' in data, data
            calls.append(messages)
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [data['sources'][0]['id']]}))

        monkeypatch.setattr(provider, 'complete_json', select, raising=False)
        yield app, client, intake, box, calls, captured
    finally:
        client.close()
        _close_app(app)


def test_incomplete_intake_is_disclosed_alongside_supported_answer(intake_session, monkeypatch):
    app, client, intake, box, calls, captured = intake_session
    with TestClient(app) as unauthenticated:
        assert unauthenticated.get('/api/v1/mail/intake').status_code == 401
    folder, = read(client.get('/api/v1/mail/intake'))['accounts'][0]['folders']
    assert folder['inventory_complete'] and (folder['captured'], folder['pending'], folder['failed']) == (1, 1, 1)
    def forbidden_status(*args, **kwargs):
        pytest.fail('Recall must not call the intake dashboard or connector.')

    monkeypatch.setattr(Intake, 'status', forbidden_status)
    monkeypatch.setattr(app.state.mail, 'reader_for', forbidden_status)
    url = '/api/v1/conversations/' + _conversation(client)
    posted = read(client.post(url + '/messages', json={'message': QUESTION, 'answer_mode': 'memory_evidence'}), 201)
    message = posted['messages'][-1]
    context = message['metadata']['context']
    saved = app.state.conversations.messages(url.rsplit('/', 1)[-1])[-1].to_dict()
    db_changes = intake.db.total_changes
    reopened = read(client.get(url))
    print(json.dumps({'intake': {k: folder[k] for k in ('inventory_complete', 'total', 'captured', 'pending', 'failed')},
                      'posted': message, 'context': posted['context'], 'stored': saved,
                      'reopened': reopened['messages'][-1], 'model_calls': len(calls),
                      'connector_body_requests': box.body_requests}, ensure_ascii=False, default=str))
    assert context['answer_contract']['status'] == 'working_reports'
    assert context['source_links'][0]['episode_id'] == captured
    assert ORIGINAL in message['content']
    assert 'keine Frist' not in message['content']
    assert box.body_requests == ['71.3', '71.2'] and len(calls) == 1
    assert intake.db.total_changes == db_changes
    assert reopened['messages'][-1] == message
    note = context['mail_intake_notice']
    assert 'Mailaufnahme' in note and 'nicht alle gefundenen Mails sind eingelesen' in note
    assert message['content'].endswith(note) and posted['context']['mail_intake_notice'] == note
    assert 'mail_intake_notice' not in str(saved)
    assert ACCOUNT not in note
    for private in ('synthetic-private-account', 'synthetic-private-provider-error', '71.1', '71.2'):
        assert private not in str(calls) and private not in str(note)


def test_capture_and_analysis_are_distinguished_on_readback(intake_session):
    app, client, intake, box, calls, _ = intake_session
    url = '/api/v1/conversations/' + _conversation(client)
    posted = read(client.post(url + '/messages', json={'message': QUESTION, 'answer_mode': 'memory_evidence'}), 201)
    assert 'nicht alle gefundenen Mails sind eingelesen' in posted['context']['mail_intake_notice']
    box.release = True
    intake.retry(ACCOUNT)
    captured = intake.step(ACCOUNT, box)
    assert len(captured) == 2
    status = intake.status(ACCOUNT)['folders'][0]
    assert (status['pending'], status['failed']) == (0, 0)
    analysis = read(client.get(url))['messages'][-1]
    assert 'noch nicht eingeordnet' in analysis['metadata']['context']['mail_intake_notice']
    store = WorkingMemoryStore(app.state.episodes)
    for source_id in captured:
        source, = store.pending(episode_ids=[source_id])
        assert store.commit(source, [{'start': 0, 'end': len(source.episode.body), 'kind': 'fact'}], model='synthetic')
    reviewed = read(client.get(url))['messages'][-1]
    assert 'mail_intake_notice' not in reviewed['metadata']['context']
    assert 'vollständig' not in reviewed['content'] and ORIGINAL in reviewed['content']
    app.state.settings.mail_accounts[0].enabled = False
    assert 'nicht verlässlich prüfen' in read(client.get(url))['context']['mail_intake_notice']
    app.state.settings.mail_accounts[0].enabled = True
    box.generation = '72'
    assert intake.step(ACCOUNT, box) == []
    assert 'nicht verlässlich prüfen' in read(client.get(url))['context']['mail_intake_notice']
    assert len(calls) == 1


@pytest.mark.parametrize('unknown_inventory', ['unstarted_archive', 'disabled_account'])
def test_known_analysis_gap_survives_other_unverified_inventory(intake_session, monkeypatch, unknown_inventory):
    app, client, intake, box, calls, original_id = intake_session
    box.release = True
    intake.retry(ACCOUNT)
    unclassified = intake.step(ACCOUNT, box)
    assert len(unclassified) == 2
    if unknown_inventory == 'unstarted_archive':
        assert intake.ergaenzen(ACCOUNT, ['Archive']) == ['Archive']
        folders = {folder['folder']: folder for folder in intake.status(ACCOUNT)['folders']}
        assert not folders['Archive']['inventory_complete']
    else:
        app.state.settings.mail_accounts.append(MailAccountSettings(
            id='synthetic-disabled', imap_host='synthetic.example.invalid',
            user='disabled@example.invalid', enabled=False))
        folders = {folder['folder']: folder for folder in intake.status(ACCOUNT)['folders']}
    inbox = folders['INBOX']
    assert (inbox['inventory_complete'], inbox['captured'], inbox['analyzed']) == (True, 3, 1)
    assert (inbox['pending'], inbox['failed']) == (0, 0)

    def forbid_intake_work(*args, **kwargs):
        pytest.fail('Conversation must not call intake maintenance or a mail connector.')

    monkeypatch.setattr(Intake, 'status', forbid_intake_work)
    monkeypatch.setattr(Intake, 'step', forbid_intake_work)
    monkeypatch.setattr(app.state.mail, 'reader_for', forbid_intake_work)
    body_requests = list(box.body_requests)
    url = '/api/v1/conversations/' + _conversation(client)
    posted = read(client.post(url + '/messages', json={'message': QUESTION, 'answer_mode': 'memory_evidence'}), 201)
    changes = intake.db.total_changes
    reopened = read(client.get(url))
    assert intake.db.total_changes == changes
    assert box.body_requests == body_requests and len(calls) == 1
    for payload in (posted, reopened):
        message = payload['messages'][-1]
        context = message['metadata']['context']
        assert context['answer_contract']['status'] == 'working_reports'
        assert context['source_links'][0]['episode_id'] == original_id
        assert ORIGINAL in message['content']
        notice = context['mail_intake_notice']
        assert notice == payload['context']['mail_intake_notice']
        assert 'noch nicht eingeordnet' in notice
        assert message['content'].endswith(notice)


def test_failed_write_retry_uses_same_local_projection_but_literal_and_saved_task_stay_scoped(intake_session, monkeypatch):
    app, client, _, box, calls, _ = intake_session
    url = '/api/v1/conversations/' + _conversation(client)
    write = app.state.conversations.add_message
    with monkeypatch.context() as patch:
        def fail_assistant(*args, **kwargs):
            if 'working_answer' in kwargs.get('metadata', {}).get('context', {}):
                raise RuntimeError('synthetic storage error')
            return write(*args, **kwargs)
        patch.setattr(app.state.conversations, 'add_message', fail_assistant)
        failed = read(client.post(url + '/messages', json={'message': QUESTION, 'answer_mode': 'memory_evidence'}), 201)
    failure = failed['messages'][-1]
    assert failure['status'] == 'error' and 'mail_intake_notice' not in str(failure)
    retried = read(client.post(f"{url}/messages/{failure['id']}/retry"), 201)
    assert retried['context']['mail_intake_notice']
    assert [m['content'] for m in retried['messages'] if m['role'] == 'user'] == [QUESTION]
    literal = read(client.post(url + '/messages', json={'message': 'Suche in meinen Quellen nach "BP-726".'}), 201)
    assert 'source_answer' in literal['messages'][-1]['metadata']['context']
    assert 'mail_intake_notice' not in literal['messages'][-1]['metadata']['context']
    task = read(client.post('/api/v1/tasks', json={'title': 'Kunstprüfung der Messlehre'}), 201)
    saved = read(client.post(url + '/messages', json={'message': f"Wie ist der Status der Aufgabe {task['id']}?"}), 201)
    assert saved['context']['task_link']['id'] == task['id']
    assert 'mail_intake_notice' not in saved['context']
    assert len(calls) == 2 and box.body_requests == ['71.3', '71.2']


def test_unverifiable_intake_does_not_block_grounded_recall(intake_session, monkeypatch):
    from icarus_memory import mail_intake

    _, client, _, box, calls, _ = intake_session
    url = '/api/v1/conversations/' + _conversation(client)
    with monkeypatch.context() as patch:
        patch.setattr(mail_intake, '_RECALL_STATUS_OPCODE_BUDGET', 1)
        patch.setattr(mail_intake, '_RECALL_STATUS_PROGRESS_STEPS', 1)
        posted = read(client.post(url + '/messages', json={'message': QUESTION, 'answer_mode': 'memory_evidence'}), 201)
    assert 'nicht verlässlich prüfen' in posted['context']['mail_intake_notice']
    assert ORIGINAL in posted['messages'][-1]['content']
    assert 'nicht alle gefundenen Mails sind eingelesen' in read(client.get(url))['context']['mail_intake_notice']
    assert len(calls) == 1 and box.body_requests == ['71.3', '71.2']


def test_enabled_mcp_still_has_no_intake_notice_in_context(intake_session, monkeypatch):
    from icarus_memory.mcp import Bridge, PREFIX, Server

    _, client, _, box, _, _ = intake_session
    monkeypatch.setenv('KINGFISHER_MCP_TUER', '1')
    url = '/api/v1/conversations/' + _conversation(client)
    posted = read(client.post(url + '/messages', json={'message': QUESTION, 'answer_mode': 'memory_evidence'}), 201)
    note = posted['context']['mail_intake_notice']
    bridge = Server(Bridge('http://testserver', None, client=client))
    tools = bridge.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result']['tools']
    assert not any('intake' in item['name'] or 'conversation' in item['name'] for item in tools)
    result = bridge.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                            'params': {'name': PREFIX + 'kontext', 'arguments': {}}})
    assert 'result' in result and note not in str(result) and ACCOUNT not in str(result)
    assert box.body_requests == ['71.3', '71.2']
