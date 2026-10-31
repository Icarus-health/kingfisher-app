"""Echter Agent-/HTTP-Weg, mit künstlicher Nutzereingabe und lokalem Antwortdouble."""
import json
import pytest
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.policy import Policy
from icarus_memory.providers import Reply
from icarus_memory.procedures import ProcedureStore
from icarus_memory.server import create_app
from tests.test_procedures import spec


class Local:
    is_local = True
    name = 'synthetic'
    model = 'synthetic-local'
    def __init__(self):
        self.seen = []
        self.during = lambda: None
    def complete(self, messages, tools):
        self.seen.append(messages)
        self.during()
        return Reply(text='Prüfantwort')


def agent(tmp_path, provider=None):
    return Agent(store=SelfModelStore(MemoryBackend(), subject_id='test'),
        policy=Policy(), audit=AuditLog(tmp_path / 'audit.sqlite3'), tools={}, provider=provider or Local())


def test_selected_procedure_is_in_actual_prompt_and_revocation_clears_history(tmp_path):
    a = agent(tmp_path)
    a._procedures = ProcedureStore(tmp_path / 'procedures.sqlite3')
    candidate = a._procedures.propose(spec())
    a._procedures.accept(candidate['id'])
    first = a.send('Schreibe eine Mail für die Zunft.')
    assert candidate['id'] in [ref['id'] for ref in first.context['procedures']['refs']]
    assert 'gegenlesen' in a.provider.seen[-1][0]['content']
    a._procedures.revoke(candidate['id'])
    second = a.send('Schreibe eine Mail für die Zunft.')
    assert 'gegenlesen' not in json.dumps(a.provider.seen[-1])
    assert len([m for m in a.provider.seen[-1] if m['role'] == 'assistant']) == 0
    assert second.context['procedures']['history_reset'] is True


def test_changed_procedure_during_generation_discards_output(tmp_path):
    a = agent(tmp_path)
    a._procedures = ProcedureStore(tmp_path / 'procedures.sqlite3')
    candidate = a._procedures.propose(spec())
    a._procedures.accept(candidate['id'])
    a.provider.during = lambda: a._procedures.revoke(candidate['id'])
    turn = a.send('Schreibe eine Mail für die Zunft.')
    assert turn.reply != 'Prüfantwort'
    assert turn.context['invalidated'] is True


def test_cloud_never_receives_personal_procedure(tmp_path):
    p = Local()
    p.is_local = False
    a = agent(tmp_path, p)
    a._procedures = ProcedureStore(tmp_path / 'procedures.sqlite3')
    a._procedures.accept(a._procedures.propose(spec())['id'])
    a.send('Schreibe eine Mail für die Zunft.')
    assert 'gegenlesen' not in json.dumps(p.seen)


def test_procedure_api_requires_token_and_does_not_apply_pending(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-token')
    app = create_app(agent=agent(tmp_path))
    c = TestClient(app)
    assert c.get('/api/v1/procedures').status_code == 401
    c.headers['X-Icarus-Token'] = 'synthetic-token'
    r = c.post('/api/v1/procedures', json={'spec':spec()})
    assert r.status_code == 201, r.text
    item = r.json()
    assert item['state'] == 'pending'
    assert 'markdown' not in c.get('/api/v1/procedures').json()['items'][0]
    assert c.post(f"/api/v1/procedures/{item['id']}/accept").status_code == 200
    assert app.state.agent._procedures.select('Schreibe eine Mail für die Zunft.', area='mail')['contextual']
    assert c.get(f"/api/v1/procedures/{item['id']}/export").text.startswith('---\n')


@pytest.mark.parametrize('instruction',[
    'Lerne diesen Ablauf: Für offizielle Zunftmails zuerst Anlass prüfen, dann knapp entwerfen. Private Urlaubsmails gehören nicht dazu.',
    'Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann den Entwurf gegenlesen.',
    'Merke dir für Zunftmails: zuerst Anlass prüfen, danach gegenlesen.',
    'Bitte bei Zunftmails ab jetzt erst den Anlass prüfen und anschließend gegenlesen.',
])
def test_explicit_learning_in_chat_proposes_but_does_not_activate_and_withdraws(tmp_path, monkeypatch,instruction):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = Local()
    def generate(messages, tools):
        p.seen.append(messages)
        return Reply(text=json.dumps(spec()))
    p.complete = generate
    app = create_app(agent=agent(tmp_path, p))
    c = TestClient(app)
    conversation = c.post('/api/v1/conversations', json={'title':'Künstliche Lernprobe'}).json()['conversation']
    result = c.post(f"/api/v1/conversations/{conversation['id']}/messages", json={
        'message':instruction})
    assert result.status_code == 201, result.text
    items = c.get('/api/v1/procedures').json()['items']
    assert len(items) == 1 and items[0]['state'] == 'pending'
    assert len(p.seen) == 1  # Kein zusätzliches Modell für Auswahl oder Bestätigung.
    assert not app.state.procedures.select('Schreibe eine Mail für die Zunft.', area='mail')['contextual']
    item = app.state.procedures.get(items[0]['id'])
    assert len(item['sources']) == 1
    source_id = next(iter(item['sources']))
    from icarus_memory.episodes import CHAT_LOOKUP_TAG
    from icarus_memory.task_review import current_task_context
    from icarus_memory.working_memory_store import WorkingMemoryStore
    assert CHAT_LOOKUP_TAG in app.state.episodes.get(source_id).tags
    assert current_task_context(app.state.episodes, source_id) is None
    working = WorkingMemoryStore(app.state.episodes)
    assert not working._eligible(working._snapshot(source_id))
    app.state.episodes.ignore(source_id)
    assert c.post(f"/api/v1/procedures/{item['id']}/accept").status_code == 409


def test_mail_text_never_starts_learning():
    from icarus_memory.procedure_routes import explicit_learning
    assert not explicit_learning('In der Mail steht: Lerne diesen Ablauf: …')
    assert not explicit_learning('Was bedeutet „Lerne diesen Ablauf“?')
    assert explicit_learning('Bitte lerne diesen Ablauf: Eingaben prüfen, dann entwerfen.')


@pytest.mark.parametrize('second_valid', [True, False])
def test_real_learning_route_repairs_once_and_keeps_result_inactive(tmp_path, monkeypatch, second_valid):
    from tests.test_procedure_model import BAD_TRIGGER_DRAFT, GOOD_TRIGGER_DRAFT
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = Local()
    outputs = iter([BAD_TRIGGER_DRAFT, GOOD_TRIGGER_DRAFT if second_valid else BAD_TRIGGER_DRAFT])
    def generate(messages, tools):
        p.seen.append(messages)
        return Reply(text=json.dumps(next(outputs)))
    p.complete = generate
    app = create_app(agent=agent(tmp_path, p)); c = TestClient(app)
    conversation = c.post('/api/v1/conversations', json={}).json()['conversation']['id']
    result = c.post(f'/api/v1/conversations/{conversation}/messages', json={'message':
        'Bei Zunftmails bitte künftig zuerst Anlass prüfen, dann den Entwurf gegenlesen.'})
    assert result.status_code == 201 and len(p.seen) == 2
    items = app.state.procedures.items()
    assert len(items) == int(second_valid)
    assert all(item['state'] == 'pending' for item in items)
    assert not app.state.procedures.select('Schreibe eine Zunftmail für die Zunft.', area='mail')['contextual']


@pytest.mark.parametrize('change', ['source','provider','role','permission','equivalent_provider'])
def test_learning_repair_rechecks_source_configuration_and_existing_permission(tmp_path, monkeypatch, change):
    from copy import copy
    from tests.test_procedure_model import BAD_TRIGGER_DRAFT, GOOD_TRIGGER_DRAFT
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = Local(); allowed = [True]
    p._verified_local_permitted = lambda: allowed[0]
    app = create_app(agent=agent(tmp_path, p)); c = TestClient(app)
    def generate(messages, tools):
        p.seen.append(messages)
        if len(p.seen) == 1:
            if change == 'source':
                source = next(ep for ep in app.state.episodes.all_episodes() if ep.body.startswith('Bei Zunftmails'))
                app.state.episodes.ignore(source.id)
            elif change == 'provider':
                app.state.agent._provider = copy(p); app.state.agent._provider.model = 'different-local'
            elif change == 'role':
                app.state.settings.model_roles = {'antwort':{'modell':'different-local'}}
            elif change == 'permission': allowed[0] = False
            else: app.state.agent._provider = copy(p)
            return Reply(text=json.dumps(BAD_TRIGGER_DRAFT))
        return Reply(text=json.dumps(GOOD_TRIGGER_DRAFT))
    p.complete = generate
    conversation = c.post('/api/v1/conversations', json={}).json()['conversation']['id']
    result = c.post(f'/api/v1/conversations/{conversation}/messages', json={'message':
        'Bei Zunftmails bitte künftig zuerst Anlass prüfen, dann den Entwurf gegenlesen.'})
    assert result.status_code == 201
    assert len(p.seen) == (2 if change == 'equivalent_provider' else 1)
    assert len(app.state.procedures.items()) == int(change == 'equivalent_provider')


@pytest.mark.parametrize('message',[
    'Schreibe eine Zunftmail. Prüfe zuerst den Anlass, dann den Entwurf.',
    'Schreibe Zunftmails künftig kürzer.',
    'Merke dir für Zunftmails: bitte freundlicher formulieren.',
    'Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann gegenlesen?',
    'Soll ich bei Zunftmails künftig zuerst den Anlass prüfen, dann gegenlesen?',
    'In der Mail steht: Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann gegenlesen.',
    '> Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann gegenlesen.',
    '„Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann gegenlesen.“',
    'Bitte fasse diesen Text zusammen:\nBei Zunftmails bitte künftig zuerst den Anlass prüfen, dann gegenlesen.',
    'Bei Zunftmails bitte künftig nicht zuerst den Anlass prüfen, sondern nur zusammenfassen.',
    'Merke dir für Alex: Er hat zuerst in Bonn und dann in Berlin gewohnt.',
    'Merke dir für Alex: zuerst wohnte er in Bonn, danach in Berlin.',
    'Bei Zunftmails steht künftig zuerst „Anlass prüfen“, dann „Entwurf gegenlesen“ im Text.',
    'Für Zunftmails gilt laut Handbuch künftig zuerst Anlass prüfen, dann Entwurf gegenlesen.',
    'Merke dir für den Kurs: zuerst lernen wir Dokumente prüfen, danach lernen wir Texte zusammenfassen.',
])
def test_style_facts_one_off_work_and_quoted_instructions_never_start_learning(message):
    from icarus_memory.procedure_routes import explicit_learning
    assert not explicit_learning(message)


def test_reported_workflow_uses_normal_http_route_and_creates_no_learning_proposal(tmp_path,monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
    p=Local();app=create_app(agent=agent(tmp_path,p));c=TestClient(app)
    conversation=c.post('/api/v1/conversations',json={}).json()['conversation']['id']
    message='Bei Zunftmails steht künftig zuerst „Anlass prüfen“, dann „Entwurf gegenlesen“ im Text.'
    result=c.post(f'/api/v1/conversations/{conversation}/messages',json={'message':message,'answer_mode':'chat'})
    assert result.status_code==201,result.text
    assert len(p.seen)==1
    assert 'Forme die ausdrückliche Arbeitsanweisung' not in json.dumps(p.seen,ensure_ascii=False)
    assert app.state.procedures.items()==[]
    episodes=[ep for ep in app.state.episodes.all_episodes() if ep.body==message]
    assert len(episodes)==1
    from icarus_memory.episodes import CHAT_LOOKUP_TAG
    assert CHAT_LOOKUP_TAG not in episodes[0].tags


def test_mail_draft_uses_selected_procedure_and_rechecks_after_model(tmp_path):
    from types import SimpleNamespace
    from tests.test_mail_reply_suggestions import make_client, Provider
    class Draft(Provider):
        def complete_json(self, messages):
            self.seen = messages
            return SimpleNamespace(text='{"body":"Ein künstlicher Entwurf."}', tool_calls=[])
    p = Draft()
    app, c = make_client(provider=p)
    app.state.procedures = ProcedureStore(tmp_path / 'procedures.sqlite3')
    candidate = app.state.procedures.propose(spec())
    app.state.procedures.accept(candidate['id'])
    result = c.post('/api/v1/messages/a%3A1.1/reply-suggestion', json={'instruction':'Schreibe eine Mail für die Zunft.'})
    assert result.status_code == 200, result.text
    assert 'gegenlesen' in json.dumps(p.seen)
    def changed(messages):
        app.state.procedures.revoke(candidate['id'])
        return SimpleNamespace(text='{"body":"Darf nicht ausgegeben werden."}', tool_calls=[])
    p.complete_json = changed
    assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion', json={'instruction':'Schreibe eine Mail für die Zunft.'}).status_code == 409


def test_revoked_procedure_does_not_execute_pending_tool(tmp_path):
    from icarus_memory.providers import ToolCall
    from icarus_memory.tools import build_registry
    a = agent(tmp_path)
    sent = []
    a._tools = build_registry(a._store, outward_sink=sent.append)
    a._procedures = ProcedureStore(tmp_path / 'procedures.sqlite3')
    item = a._procedures.propose(spec())
    a._procedures.accept(item['id'])
    a.provider.complete = lambda messages, tools: Reply(tool_calls=[ToolCall('call-1', 'mail_senden', {
        'to':'probe@example.invalid', 'subject':'Probe', 'body':'Künstlich'})])
    first = a.send('Schreibe eine Mail für die Zunft.')
    assert first.approvals and not sent
    a._procedures.revoke(item['id'])
    result = a.resolve(first.approvals[0].id, granted=True, confirmation='probe@example.invalid')
    assert result.approval_outcome == 'rejected' and not sent
    assert first.approvals[0].id not in a._approval_procedures


def test_procedure_reset_survives_three_http_turns(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = Local()
    def complete(messages, tools):
        p.seen.append(messages)
        return Reply(text='OLD_SKILL_DERIVED_SECRET' if len(p.seen) == 1 else 'Neuer Kontext.')
    p.complete = complete
    app = create_app(agent=agent(tmp_path, p))
    store = app.state.procedures
    item = store.propose(spec())
    store.accept(item['id'])
    c = TestClient(app)
    conv = c.post('/api/v1/conversations', json={}).json()['conversation']['id']
    endpoint = f'/api/v1/conversations/{conv}/messages'
    payload = {'message':'Schreibe eine Mail für die Zunft.', 'answer_mode':'chat'}
    assert c.post(endpoint, json=payload).status_code == 201
    store.revoke(item['id'])
    for _ in range(3):
        assert c.post(endpoint, json=payload).status_code == 201
        assert 'OLD_SKILL_DERIVED_SECRET' not in json.dumps(p.seen[-1])


def test_learning_uses_real_json_provider_budget_contract(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import httpx
    from icarus_memory.providers import OpenAICompatible
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = OpenAICompatible('synthetic-local', base_url='http://127.0.0.1:11434/v1')
    seen = []
    def transport(request):
        payload = json.loads(request.content)
        seen.append(payload)
        return httpx.Response(200, json={'done':True,'done_reason':'stop','message':{'content':json.dumps(spec())}})
    from icarus_memory.local_model_guard import LocalModelIdentity
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',lambda _:LocalModelIdentity('synthetic-local','a'*64))
    monkeypatch.setattr(p, '_ampel', nullcontext)
    monkeypatch.setattr(p, '_client', lambda timeout: httpx.Client(transport=httpx.MockTransport(transport)))
    app = create_app(agent=agent(tmp_path, p))
    c = TestClient(app)
    conv = c.post('/api/v1/conversations', json={}).json()['conversation']['id']
    result = c.post(f'/api/v1/conversations/{conv}/messages', json={
        'message':'Lerne diesen Ablauf: Bei Zunftmails Anlass prüfen, dann knapp entwerfen.'})
    assert result.status_code == 201
    assert len(app.state.procedures.items()) == 1
    assert len(seen) == 1 and seen[0]['options']['num_predict'] <= 1200 and seen[0]['options']['num_ctx'] == 8192


def test_loopback_cloud_model_never_receives_personal_procedures(tmp_path, monkeypatch):
    from icarus_memory.providers import OpenAICompatible, ProviderError
    p=OpenAICompatible('remote:cloud',base_url='http://127.0.0.1:11434/v1')
    seen=[]
    p.complete=lambda messages,tools:(seen.append(messages) or Reply(text='Antwort'))
    def unavailable(_):raise ProviderError('No local weights')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',unavailable)
    a=agent(tmp_path,p)
    a._procedures=ProcedureStore(tmp_path/'procedures.sqlite3')
    a._procedures.accept(a._procedures.propose(spec())['id'])
    a.send('Schreibe eine Mail für die Zunft.')
    assert 'gegenlesen' not in json.dumps(seen)


@pytest.mark.parametrize('mode',['chat','mail'])
def test_actual_personal_procedure_request_never_uses_environment_proxy(tmp_path, monkeypatch, mode):
    from contextlib import nullcontext
    import httpx
    from icarus_memory.providers import OpenAICompatible
    from icarus_memory.local_model_guard import LocalModelIdentity
    monkeypatch.setenv('HTTP_PROXY','http://synthetic-proxy.example.invalid:3128')
    monkeypatch.setenv('NO_PROXY','')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',lambda _:LocalModelIdentity('synthetic:9b','a'*64))
    p=OpenAICompatible('synthetic:9b',base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setattr(p,'_ampel',nullcontext)
    sent=[]
    def handle(transport, request):
        sent.append((type(transport._pool).__name__,json.loads(request.content)))
        content=json.dumps({'body':'Ein künstlicher Entwurf.'}) if mode == 'mail' else 'Antwort'
        return httpx.Response(200,json={'choices':[{'message':{'content':content}}]})
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',handle)
    procedures=ProcedureStore(tmp_path/'procedures.sqlite3')
    procedures.accept(procedures.propose(spec())['id'])
    if mode == 'chat':
        a=agent(tmp_path,p);a._procedures=procedures
        a.send('Schreibe eine Mail für die Zunft.')
    else:
        from tests.test_mail_reply_suggestions import make_client
        monkeypatch.setattr('icarus_memory.mail_reply_suggestions._mailhilfe_provider',lambda app:p)
        app,c=make_client(provider=p);app.state.procedures=procedures
        result=c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={'instruction':'Schreibe eine Mail für die Zunft.'})
        assert result.status_code == 200,result.text
    assert len(sent) == 1 and 'gegenlesen' in json.dumps(sent[0][1])
    assert sent[0][0] == 'ConnectionPool'
