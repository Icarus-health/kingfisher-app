import json
import pytest
from fastapi.testclient import TestClient

from icarus_memory.server import create_app
from tests.test_procedure_runtime import agent, Local
from tests.test_procedures import spec

REQUEST = 'Schreibe eine Mail für die Zunft.'


@pytest.fixture
def flow(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = Local(); app = create_app(agent=agent(tmp_path, p)); client = TestClient(app)
    store = app.state.procedures
    a = store.accept(store.propose(spec())['id'])
    b = store.accept(store.propose({**spec(), 'name':'zunft-kurz','title':'Kurze Zunftmail',
        'steps':['Anlass prüfen, dann kurz formulieren.']})['id'])
    conversation = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    return app, client, p, store, a, b, conversation


def ask(flow):
    app, c, p, _, a, b, conversation = flow
    result = c.post(f'/api/v1/conversations/{conversation}/messages', json={'message':REQUEST})
    assert result.status_code == 201, result.text
    assert not p.seen, 'Auch das Fragenmodell darf vor der Ablaufwahl nicht aufgerufen werden'
    pending = result.json()['messages'][-1]['metadata']['context']['procedure_choice']
    assert {x['id'] for x in pending['options']} == {a['id'], b['id'], 'core'}
    return pending


def choose(flow, offered, identifier, **extra):
    option = next(item for item in offered['options'] if item['id'] == identifier)
    return flow[1].post(f'/api/v1/conversations/{flow[-1]}/messages', json={
        'message':option['label'], 'procedure_choice':{'token':offered['token'],'id':identifier}, **extra})


def test_agent_stops_at_conflict_before_model(flow):
    app, _, p, *_ = flow
    turn = app.state.agent.send(REQUEST)
    assert not p.seen
    assert turn.context['procedure_choice'] and not turn.approvals


def test_http_choice_resumes_original_request_and_is_not_a_new_fact(flow):
    app, _, p, store, a, _, _ = flow
    offered = ask(flow)
    result = choose(flow, offered, a['id'])
    assert result.status_code == 201, result.text
    assert result.json()['messages'][-1]['content'] == 'Prüfantwort'
    assert len(p.seen) == 1
    assert p.seen[-1][-1]['role'] == 'user' and p.seen[-1][-1]['content'] == REQUEST
    assert 'gegenlesen' in p.seen[-1][0]['content'] and 'kurz formulieren' not in p.seen[-1][0]['content']
    picked = result.json()['messages'][-2]
    assert picked['metadata']['memory_lookup_only'] is True
    assert choose(flow, offered, a['id']).status_code == 409
    assert len(p.seen) == 1 and len(store.select(REQUEST, area='mail')['conflicts']) == 2


@pytest.mark.parametrize('change',['skill','provider','provider_model','permission','routing','source','later_message','other_conversation','label','expired'])
def test_choice_is_bound_to_current_conversation_sources_and_model(flow, change):
    app, c, p, store, a, _, conversation = flow
    offered = ask(flow)
    if change == 'skill': store.revoke(a['id'])
    elif change == 'provider': app.state.agent._provider = Local()
    elif change == 'provider_model': p.model = 'different'
    elif change == 'permission': p._verified_local_permitted = lambda: False
    elif change == 'routing': app.state.settings.routing_enabled = True
    elif change == 'source':
        source = next(ep for ep in app.state.episodes.all_episodes() if ep.body == REQUEST)
        app.state.episodes.ignore(source.id)
    elif change == 'later_message':
        app.state.conversations.add_message(conversation, 'user', 'Anderer Auftrag')
    elif change == 'other_conversation':
        other = c.post('/api/v1/conversations', json={}).json()['conversation']['id']
        flow = (*flow[:-1], other)
    elif change == 'expired': app.state.procedure_choices[offered['token']]['created'] -= 601
    result = choose(flow, offered, a['id'], **({'message':'Fremder Auftrag'} if change == 'label' else {}))
    assert result.status_code == 409, result.text
    assert not p.seen


def test_explicit_basic_choice_and_conflicting_choice_fields(flow):
    offered = ask(flow)
    assert choose(flow, offered, 'core', clarification_choice=0).status_code == 422
    result = choose(flow, offered, 'core')
    assert result.status_code == 201
    assert 'gegenlesen' not in json.dumps(flow[2].seen)


def test_revocation_during_chosen_generation_discards_reply(flow):
    _, _, p, store, a, _, _ = flow
    offered = ask(flow)
    p.during = lambda: store.revoke(a['id'])
    result = choose(flow, offered, a['id'])
    assert result.status_code == 201
    assert result.json()['messages'][-1]['content'] != 'Prüfantwort'
    assert result.json()['messages'][-1]['metadata']['context']['invalidated'] is True


def test_original_source_withdrawal_stays_bound_after_memory_revision_resets_history(flow, monkeypatch):
    app, _, p, _, a, _, _ = flow
    offered = ask(flow)
    original = next(ep for ep in app.state.episodes.all_episodes() if ep.body == REQUEST)
    old_revision = app.state.claims.revision
    monkeypatch.setattr(type(app.state.claims), 'revision', property(lambda _: old_revision + 1))
    p.during = lambda: app.state.episodes.ignore(original.id)
    result = choose(flow, offered, a['id'])
    assert result.status_code == 201
    answer = result.json()['messages'][-1]
    assert answer['content'] != 'Prüfantwort'
    assert len(p.seen) == 1
    stored = app.state.conversations.messages(flow[-1])[-1]
    assert original.id in {entry['episode_id'] for entry in stored.metadata['conversation_source_lineage']}
    reread = flow[1].get(f'/api/v1/conversations/{flow[-1]}').json()
    assert reread['messages'][-1]['content'] != 'Prüfantwort'


def test_pending_choice_never_schedules_background_model_work(flow, monkeypatch):
    from types import SimpleNamespace
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory import hintergrund_cloud
    app = flow[0]
    queued = []
    app.state.settings.schedule.enabled = True
    app.state.settings.schedule.with_model = True
    app.state.scheduler = SimpleNamespace(request_working_memory=queued.append)
    monkeypatch.setattr(hintergrund_cloud, 'einordnung_moeglich', lambda *args: True)
    ask(flow)
    original = next(ep for ep in app.state.episodes.all_episodes() if ep.body == REQUEST)
    assert queued == []
    working = WorkingMemoryStore(app.state.episodes)
    assert not working._eligible(working._snapshot(original.id))
