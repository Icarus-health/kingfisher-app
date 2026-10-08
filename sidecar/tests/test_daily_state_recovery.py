"""New daily state survives restart and encrypted recovery without reactivating rights."""
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient

from icarus_memory import server
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.recovery_bundle import export_bundle, restore_bundle
from icarus_memory.secrets import Keychain, PASSPHRASE_ENV
from icarus_memory.tasks import TaskStore
from tests.test_conversation_retraction import _make_app, _close_app


DUE = '2030-10-15T12:00:00+00:00'
REMINDER = '2020-10-10T08:30:17+00:00'
STORE_PASSWORD = 'synthetic-daily-store-passphrase'
BUNDLE_PASSWORD = 'synthetic-daily-recovery-passphrase'
FAKE_KEY = 'synthetic-never-a-real-mistral-key'


def _candidate(app, subject, value):
    text = f'Synthetic source: {subject} has value {value}.'
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Synthetic recovery evidence', text,
        Provenance(source_type=SourceType.EMAIL, source_ref=f'synthetic:{subject}:{value}'),
    )
    proposal, _ = app.state.knowledge_service.propose(
        subject_ref=subject, predicate='synthetic_recovery_value', value=value,
        statement=text, rationale='Explicit synthetic evidence',
        evidence=[Evidence(episode.id, text, episode.digest)],
    )
    return proposal, episode


def _seed(data, monkeypatch):
    app = _make_app(data, monkeypatch)
    try:
        with TestClient(app) as client:
            old, _ = _candidate(app, 'person:recovery-chosen', 'old')
            old_claim = app.state.knowledge_service.accept(old.id, supersedes=[])
            new, source = _candidate(app, 'person:recovery-chosen', 'new')
            question = next(q for q in client.get('/api/v1/memory/questions').json()['items']
                            if q['subject_ref'] == 'person:recovery-chosen')
            choice = {'stand': question['stand'], 'proposal_id': new.id}
            resolved = client.post('/api/v1/memory/questions/'+question['id']+'/resolve', json=choice)
            assert resolved.status_code == 200
            new_claim_id = resolved.json()['claim']['id']
            for subject in ('person:recovery-pending', 'person:recovery-withdrawn'):
                baseline, _ = _candidate(app, subject, 'baseline')
                app.state.knowledge_service.accept(baseline.id, supersedes=[])
            pending, _ = _candidate(app, 'person:recovery-pending', 'undecided')
            withdrawn, withdrawn_source = _candidate(app, 'person:recovery-withdrawn', 'hidden')
            assert {q['subject_ref'] for q in client.get('/api/v1/memory/questions').json()['items']} == {
                'person:recovery-pending', 'person:recovery-withdrawn'}
            app.state.episodes.ignore(withdrawn_source.id)
            task_response = client.post('/api/v1/tasks', json={'title': 'Synthetic retained task', 'due': DUE})
            assert task_response.status_code == 201
            task = task_response.json()
            path = '/api/v1/tasks/'+task['id']
            assert client.post(path+'/warten', json={'name': 'Synthetic waiting person'}).status_code == 200
            assert client.patch(path, json={'remind_at': REMINDER, 'expected_remind_at': None}).status_code == 200
            assert any(item['id'] == task['id'] for item in client.get('/api/v1/tasks/reminders').json()['items'])
            state = dict(task_id=task['id'], old_claim_id=old_claim.id, new_claim_id=new_claim_id,
                         pending_id=pending.id, withdrawn_id=withdrawn.id,
                         withdrawn_source_id=withdrawn_source.id, source_id=source.id,
                         question_id=question['id'], choice=choice)
        Keychain(data_dir=data).set('MISTRAL_API_KEY', FAKE_KEY)
        return state
    finally:
        _close_app(app)


def _assert_retained_stores(data, state):
    tasks = TaskStore(data/'tasks.sqlite3')
    claims = ClaimStore(data/'knowledge.sqlite3')
    proposals = ProposalStore(data/'proposals.sqlite3')
    episodes = EpisodeStore(data/'episodes.sqlite3')
    try:
        task = tasks.get(state['task_id'])
        assert task.title == 'Synthetic retained task'
        assert task.status.value == 'open' and task.wartet_auf == 'Synthetic waiting person'
        assert task.due == datetime.fromisoformat(DUE)
        assert task.remind_at == datetime.fromisoformat(REMINDER)
        assert [item.id for item in tasks.reminders_due(datetime(2026, 10, 7, tzinfo=timezone.utc))] == [task.id]
        assert any(event['after'].get('remind_at') == task.remind_at.astimezone().isoformat()
                   for event in tasks.history(task.id))
        assert claims.get(state['old_claim_id']).status.value == 'superseded'
        assert claims.get(state['new_claim_id']).status.value == 'active'
        assert proposals.get(state['pending_id']).state.value == 'pending'
        assert proposals.get(state['withdrawn_id']).state.value == 'pending'
        assert episodes.usable_ids({state['source_id'], state['withdrawn_source_id']}) == {state['source_id']}
        assert Keychain(data_dir=data).get('MISTRAL_API_KEY') == FAKE_KEY
    finally:
        for store in (tasks, claims, proposals, episodes):
            store.close()


def test_restart_retains_decision_reminder_pending_question_and_source_withdrawal(tmp_path, monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, STORE_PASSWORD)
    data = tmp_path/'original'
    state = _seed(data, monkeypatch)
    _assert_retained_stores(data, state)
    app = _make_app(data, monkeypatch)
    try:
        with TestClient(app) as client:
            questions = client.get('/api/v1/memory/questions').json()['items']
            assert {q['subject_ref'] for q in questions} == {'person:recovery-pending'}
            replay = client.post('/api/v1/memory/questions/'+state['question_id']+'/resolve', json=state['choice'])
            assert replay.status_code == 409
            reminders = client.get('/api/v1/tasks/reminders').json()['items']
            assert [item['id'] for item in reminders] == [state['task_id']]
    finally:
        _close_app(app)


def test_encrypted_recovery_retains_daily_state_but_cannot_resume_old_actions(tmp_path, monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, STORE_PASSWORD)
    data = tmp_path/'original'
    state = _seed(data, monkeypatch)
    config = tmp_path/'synthetic.env'
    config.write_text(f'{PASSPHRASE_ENV}={STORE_PASSWORD}\n')
    bundle = export_bundle(data, config, tmp_path/'synthetic.kingfisher', BUNDLE_PASSWORD)
    assert STORE_PASSWORD not in bundle.read_text() and FAKE_KEY not in bundle.read_text()
    target = restore_bundle(bundle, tmp_path/'restored', BUNDLE_PASSWORD)
    assert (target/'settings.env').read_text() == config.read_text()
    _assert_retained_stores(target/'data', state)
    _assert_retained_stores(data, state)  # Restoring a copy never changes the original.

    monkeypatch.setenv('ICARUS_DATA_DIR', str(target/'data'))
    def forbidden(*args, **kwargs):
        raise AssertionError('Historical recovery must not start providers or load saved credentials')
    monkeypatch.setattr(server, '_build_agent', forbidden)
    monkeypatch.setattr(server, 'load_into_env', forbidden)
    with TestClient(server.create_app()) as client:
        status = client.get('/api/v1/recovery/status').json()
        assert status['mode'] == 'inspection' and status['operational'] is False
        records = client.get('/api/v1/recovery/records', params={'store': 'tasks.sqlite3'}).json()
        task = next(json.loads(item['document']) for item in records['items'] if item['id'] == state['task_id'])
        assert datetime.fromisoformat(task['remind_at']) == datetime.fromisoformat(REMINDER)
        assert client.patch('/api/v1/tasks/'+state['task_id'], json={'remind_at': None}).status_code == 423
        assert client.post('/api/v1/memory/questions/'+state['question_id']+'/resolve', json=state['choice']).status_code == 423
