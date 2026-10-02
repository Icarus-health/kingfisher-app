"""Synthetic M1b regressions for authoritative profile input lineage."""
from datetime import datetime, timedelta, timezone
import pytest
from tests.test_context import _knowledge_agent, ExternalCapturingProvider
from icarus_memory.model import Kind, Provenance, SourceType, Status, Sensitivity
from icarus_memory.providers import Reply, ToolCall

AT = datetime(2026, 9, 14, tzinfo=timezone.utc)


def setup_profile(tmp_path, monkeypatch, **kwargs):
    clock = [AT]
    for module in ('model', 'context', 'currency', 'store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now', lambda: clock[0])
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    assertion = agent._store.record('Synthetic preference: Filterkaffee.', Kind.PREFERENCE,
        Provenance(SourceType.USER_STATED, source_ref='synthetic:profile'), at=AT, **kwargs)
    def answer(messages, tools):
        provider.messages.append(messages)
        return Reply(text='OLD_PROFILE_DERIVATION')
    provider.complete = answer
    return agent, provider, assertion, clock


def saved(turn):
    return [{'role':'user','content':'Filterkaffee?'},
            {'role':'assistant','content':turn.reply,'context':turn.context}]


@pytest.mark.parametrize('reload', [False, True])
@pytest.mark.parametrize('change', ['expiry', 'retract'])
def test_profile_invalidity_removes_old_derived_input(tmp_path, monkeypatch, reload, change):
    agent, provider, assertion, clock = setup_profile(tmp_path, monkeypatch, expires_at=AT+timedelta(hours=1))
    first = agent.send('Filterkaffee?')
    if reload:
        agent = agent.scoped(provider, frozenset())
        agent.load_history(saved(first))
    if change == 'expiry':
        clock[0] += timedelta(hours=2)  # no status-materializing usable() call
    else:
        agent._store.retract(assertion.id)
    next_turn = agent.send('Continue')
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    assert next_turn.context['self_model_history_reset']
    assert first.reply == 'OLD_PROFILE_DERIVATION'


def test_profile_expiry_during_call_blocks_prior_only_input_and_tools(tmp_path, monkeypatch):
    from icarus_memory.context import ContextPacket
    agent, provider, assertion, clock = setup_profile(tmp_path, monkeypatch, expires_at=AT+timedelta(hours=1))
    agent.send('Filterkaffee?')
    monkeypatch.setattr(agent, 'context_packet', lambda _: (ContextPacket('',clock[0],(),0), 'No new profile input'))
    def changing(*args):
        clock[0] += timedelta(hours=2)
        return Reply(text='EXPIRED_REPLY', tool_calls=[ToolCall('x','unused',{})])
    provider.complete = changing
    monkeypatch.setattr(agent, '_handle', lambda *args: pytest.fail('Expired tool executed'))
    result = agent.send('Continue')
    assert result.context['invalidated']
    assert result.context['self_model_inputs'] == {}
    assert result.reply != 'EXPIRED_REPLY'


def test_profile_fingerprint_comes_from_rendered_object_not_later_lookup(tmp_path, monkeypatch):
    agent, provider, assertion, clock = setup_profile(tmp_path, monkeypatch)
    original = agent.context_packet
    def racing(query):
        packet, text = original(query)
        changed = agent._store._backend.get(assertion.id)
        changed.sensitivity = Sensitivity.SENSITIVE  # allowed mutable classification, still locally shareable
        agent._store._backend.put(changed)
        return packet, text
    monkeypatch.setattr(agent, 'context_packet', racing)
    result = agent.send('Filterkaffee?')
    assert result.context['invalidated']
    assert provider.messages == []


def test_normal_external_profile_history_is_also_revalidated(tmp_path, monkeypatch):
    agent, _, assertion, _ = setup_profile(tmp_path, monkeypatch)
    provider = ExternalCapturingProvider()
    provider.complete = lambda messages, tools: (provider.messages.append(messages), Reply(text='EXTERNAL_PROFILE'))[1]
    agent._provider = provider
    agent.send('Filterkaffee?')
    agent._store.retract(assertion.id)
    turn = agent.send('Continue')
    assert 'EXTERNAL_PROFILE' not in str(provider.messages[-1])
    assert turn.context['history_egress'] == 'external'


def test_profile_current_cards_filter_but_keep_message_history(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    agent, provider, assertion, _ = setup_profile(tmp_path, monkeypatch)
    app = create_app(agent._store, agent=agent, episodes=agent._episodes, knowledge=agent._knowledge)
    conversation = app.state.conversations.create('Synthetic profile')
    client = TestClient(app)
    url = f'/api/v1/conversations/{conversation.id}'
    first = client.post(url+'/messages',json={'message':'Filterkaffee?'}).json()
    assert any(item['assertion_id'] == assertion.id for item in first['context']['items'])
    agent._store.retract(assertion.id)
    current = client.get(url).json()
    assert current['context']['items'] == []
    assert current['messages'][-1]['content'] == 'OLD_PROFILE_DERIVATION'
    assert app.state.conversations.messages(conversation.id)[-1].metadata['context']['items']


def test_missing_profile_marker_is_not_verified_empty(tmp_path, monkeypatch):
    agent, provider, _, _ = setup_profile(tmp_path, monkeypatch)
    agent.load_history([{'role':'assistant','content':'UNKNOWN_PROFILE', 'context':{
        'items':[], 'knowledge_claim_lineage_version':1, 'knowledge_claim_ids':[]}}])
    turn = agent.send('New question')
    assert 'UNKNOWN_PROFILE' not in str(provider.messages[-1])
    assert turn.context['self_model_history_reset']


@pytest.mark.parametrize('interval', ['expired', 'future'])
def test_expired_dispute_is_not_selected_as_live_context(tmp_path, monkeypatch, interval):
    agent, _, assertion, clock = setup_profile(tmp_path, monkeypatch, expires_at=AT+timedelta(hours=1))
    changed = agent._store._backend.get(assertion.id)
    changed.status = Status.DISPUTED
    agent._store._backend.put(changed)
    if interval == 'expired': clock[0] += timedelta(hours=2)
    else:
        changed.valid_from = AT+timedelta(minutes=10)
        agent._store._backend.put(changed)
    packet, _ = agent.context_packet('Filterkaffee?')
    assert not packet.items


@pytest.mark.parametrize('state', ['current', 'disputed', 'outdated'])
def test_stable_qualified_profile_history_survives_reload(tmp_path, monkeypatch, state):
    agent, provider, assertion, clock = setup_profile(tmp_path, monkeypatch)
    if state == 'disputed':
        other = agent._store.record('Synthetic alternative Kaffee.',Kind.PREFERENCE,
            Provenance(SourceType.USER_STATED), at=AT)
        agent._store.dispute(assertion.id, other.id, at=AT)
    if state == 'outdated': clock[0] += timedelta(days=1200)
    first = agent.send('Filterkaffee?')
    item = next(i for i in first.context['items'] if i['assertion_id'] == assertion.id)
    assert item['state'] == state
    assert first.context['self_model_inputs'][assertion.id] == item['self_model_input']
    assert assertion.statement not in str(first.context['self_model_inputs'])
    agent.load_history(saved(first))
    second = agent.send('Continue')
    assert 'OLD_PROFILE_DERIVATION' in str(provider.messages[-1])
    assert not second.context['self_model_history_reset']


@pytest.mark.parametrize('change', ['currency', 'sensitivity', 'missing', 'future', 'redacted', 'superseded', 'content'])
def test_profile_state_changes_invalidate_all_prior_inputs(tmp_path, monkeypatch, change):
    agent, provider, assertion, clock = setup_profile(tmp_path, monkeypatch)
    agent.send('Filterkaffee?')
    if change == 'currency': clock[0] += timedelta(days=366)
    elif change == 'missing': del agent._store._backend._data[assertion.id]
    elif change == 'content': agent._store._backend._data[assertion.id].statement = 'Synthetic corrupt read state'
    elif change == 'redacted': agent._store.redact(assertion.id)
    elif change == 'superseded':
        agent._store.record('Synthetic correction.', Kind.PREFERENCE, Provenance(SourceType.USER_STATED),
                            supersedes=[assertion.id],at=clock[0])
    else:
        changed = agent._store.get(assertion.id)
        if change == 'future': changed.valid_from = AT+timedelta(days=1)
        else: changed.sensitivity = Sensitivity.SENSITIVE
        agent._store._backend.put(changed)
    result = agent.send('Continue')
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    assert result.context['self_model_history_reset']


def test_persisted_profile_reset_survives_new_sqlite_store_and_agent(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    from icarus_memory import SelfModelStore, SqliteBackend
    agent, provider, _, clock = setup_profile(tmp_path, monkeypatch)
    path = tmp_path/'profile.db'
    agent._store = SelfModelStore(SqliteBackend(path), 'synthetic')
    assertion = agent._store.record('Synthetic preference Filterkaffee.',Kind.PREFERENCE,
        Provenance(SourceType.USER_STATED), at=AT, expires_at=AT+timedelta(hours=1))
    app = create_app(agent._store,agent=agent,knowledge=agent._knowledge,episodes=agent._episodes)
    cid = app.state.conversations.create('Synthetic persisted profile').id
    client = TestClient(app); url=f'/api/v1/conversations/{cid}'
    assert client.post(url+'/messages',json={'message':'Filterkaffee?'}).status_code == 201
    clock[0] += timedelta(hours=2)
    assert agent._store.get(assertion.id).status is Status.ACTIVE
    reopened = SelfModelStore(SqliteBackend(path),'synthetic')
    fresh = agent.scoped(provider,frozenset()); fresh._store = reopened
    app2 = create_app(reopened,agent=fresh,knowledge=agent._knowledge,episodes=agent._episodes)
    client2=TestClient(app2)
    assert client2.get(url).json()['context']['items'] == []
    assert client2.post(url+'/messages',json={'message':'Fresh question'}).status_code == 201
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    messages=app2.state.conversations.messages(cid)
    assert messages[1].content=='OLD_PROFILE_DERIVATION'
    assert messages[-1].metadata['context']['self_model_history_reset']
    provider.complete=lambda messages,tools:(provider.messages.append(messages),Reply(text='NEW_VALID_ANSWER'))[1]
    assert client2.post(url+'/messages',json={'message':'Continue'}).status_code == 201
    assert not app2.state.conversations.messages(cid)[-1].metadata['context']['self_model_history_reset']


def test_claim_card_checks_original_source_liveness(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    agent,provider,episodes,accept = _knowledge_agent(tmp_path)
    claim,source=accept('Kranz leitet Atlas.')
    app=create_app(agent._store,agent=agent,knowledge=agent._knowledge,episodes=episodes)
    cid=app.state.conversations.create('Synthetic claim').id
    client=TestClient(app); url=f'/api/v1/conversations/{cid}'
    first=client.post(url+'/messages',json={'message':'Kranz Atlas?'}).json()
    assert any(item['assertion_id']==f'claim:{claim.id}' for item in first['context']['items'])
    episodes.ignore(source.id)  # no ClaimStore status materialization
    current=client.get(url).json()
    assert current['context']['items']==[]
    assert app.state.conversations.messages(cid)[-1].metadata['context']['items']


@pytest.mark.parametrize('corrupt', ['missing', 'bad_version', 'hash', 'state', 'bounds', 'incomplete'])
def test_invalid_profile_metadata_never_certifies_empty_history(tmp_path, monkeypatch, corrupt):
    agent,provider,assertion,_=setup_profile(tmp_path,monkeypatch)
    first=agent.send('Filterkaffee?')
    context=first.context
    if corrupt=='missing': context.pop('self_model_lineage_version')
    elif corrupt=='bad_version': context['self_model_lineage_version']=True
    elif corrupt=='hash': context['self_model_inputs'][assertion.id]['fingerprint']='not-a-hash'
    elif corrupt=='state': context['self_model_inputs'][assertion.id]['state']='unqualified'
    elif corrupt=='bounds': context['self_model_inputs']={f'synthetic:{i}':context['self_model_inputs'][assertion.id] for i in range(129)}
    else: context['self_model_inputs']={}
    agent.load_history(saved(first))
    turn=agent.send('Fresh')
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    assert turn.context['self_model_history_reset']


def test_profile_approval_followup_preserves_reset_metadata(tmp_path, monkeypatch):
    from tests.test_agent import make_agent
    base,_,assertion,clock=setup_profile(tmp_path,monkeypatch,expires_at=AT+timedelta(hours=1))
    agent=make_agent(base._store,base._audit,
        Reply(text='OLD_PROFILE_DERIVATION',tool_calls=[ToolCall('x','mail_senden',
            {'to':'synthetic@example.org','subject':'S','body':'B'})]), Reply(text='Completed'),
        sink=lambda _: 'Synthetic success')
    pending=agent.send('Filterkaffee?').approvals[0]
    clock[0]+=timedelta(hours=2)
    result=agent.resolve(pending.id,True,'synthetic@example.org')
    assert result.context['self_model_history_reset']
    assert result.context['self_model_inputs']=={}
    assert result.notices
    assert 'OLD_PROFILE_DERIVATION' not in str(agent.provider.seen[-1])


def test_profile_mutation_during_provider_error_returns_reset(tmp_path, monkeypatch):
    from icarus_memory.providers import ProviderError
    agent,provider,assertion,_=setup_profile(tmp_path,monkeypatch)
    def fail(*args):
        agent._store.retract(assertion.id)
        raise ProviderError('Synthetic failure')
    provider.complete=fail
    result=agent.send('Filterkaffee?')
    assert result.context['invalidated']
    assert result.context['self_model_history_reset']
    assert result.context['self_model_inputs']=={}


def test_calendar_boundary_clears_profile_roots_before_rebuild(tmp_path, monkeypatch):
    agent,provider,assertion,_=setup_profile(tmp_path,monkeypatch)
    first=agent.send('Filterkaffee?')
    agent._store.retract(assertion.id)
    current=agent.send('Fresh question')
    current.context['calendar_history_reset']=True
    current.context['self_model_history_reset']=False
    history=saved(first)+[{'role':'user','content':'Fresh question'},
        {'role':'assistant','content':'CURRENT_ANSWER','context':current.context}]
    agent.load_history(history)
    assert agent._history_self_model_inputs=={}
    third=agent.send('Continue')
    assert 'CURRENT_ANSWER' in str(provider.messages[-1])
    assert not third.context['self_model_history_reset']
    agent.reset()
    assert agent._history_self_model_inputs=={}


def test_profile_validation_bounds_point_reads(tmp_path, monkeypatch):
    from icarus_memory import self_model_history
    agent,_,assertion,_=setup_profile(tmp_path,monkeypatch)
    from icarus_memory.self_model_basis import FrozenBuild
    assessment=FrozenBuild(agent._store,at=AT,max_sensitivity=Sensitivity.NORMAL).assess(assertion)
    entry=self_model_history.capture(assessment,AT)
    reads=[]
    original=agent._store.get
    monkeypatch.setattr(agent._store,'get',lambda key:(reads.append(key),original(key))[1])
    monkeypatch.setattr(agent._store,'alles',lambda:pytest.fail('Profile history scanned the whole store'))
    assert self_model_history.available({assertion.id:entry},agent._store,at=AT)
    assert reads==[assertion.id]
    reads.clear()
    assert not self_model_history.available({str(i):entry for i in range(129)},agent._store,at=AT)
    assert reads==[]
