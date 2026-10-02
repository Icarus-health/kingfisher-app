"""Synthetic parent-basis tests against actual Agent provider inputs."""
from datetime import timedelta
import pytest
from icarus_memory.model import Kind, Provenance, SourceType, Sensitivity, Status
from icarus_memory.providers import Reply
from tests.test_profile_history import setup_profile, saved, AT


def setup_basis(tmp_path, monkeypatch, kind=Kind.STATE, **kwargs):
    agent, provider, unrelated, clock = setup_profile(tmp_path, monkeypatch)
    agent._store.retract(unrelated.id)
    parent = agent._store.record('Budgetannahme.', Kind.STATE,
        Provenance(SourceType.USER_STATED), at=AT, **kwargs)
    child = agent._store.record('ORION ist finanziert.', kind,
        Provenance(SourceType.INFERENCE), derived_from=[parent.id], at=AT)
    return agent, provider, agent._store._backend._data[parent.id], agent._store._backend._data[child.id], clock


@pytest.mark.parametrize('reload', [False, True])
@pytest.mark.parametrize('change', ['retract', 'expiry', 'dispute', 'future', 'supersede', 'missing', 'sensitivity'])
def test_unselected_parent_invalidates_fresh_and_prior_inference(tmp_path, monkeypatch, reload, change):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, expires_at=AT+timedelta(hours=1))
    first = agent.send('ORION?')
    assert [i['assertion_id'] for i in first.context['items']] == [child.id]
    if reload:
        agent = agent.scoped(provider, frozenset())
        agent.load_history(saved(first))
    if change == 'retract': agent._store.retract(parent.id)
    elif change == 'expiry': clock[0] += timedelta(hours=2)
    elif change == 'missing': del agent._store._backend._data[parent.id]
    elif change == 'supersede':
        agent._store.record('Neue Grundlage.', Kind.STATE, Provenance(SourceType.USER_STATED),
                            at=AT, supersedes=[parent.id])
    else:
        changed = agent._store.get(parent.id)
        if change == 'dispute': changed.status = Status.DISPUTED
        if change == 'future': changed.valid_from = AT+timedelta(days=1)
        if change == 'sensitivity': changed.sensitivity = Sensitivity.SPECIAL_CATEGORY
        agent._store._backend.put(changed)
        if change == 'sensitivity': agent._max_sensitivity = Sensitivity.NORMAL
    turn = agent.send('ORION?')
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    assert child.statement not in str(provider.messages[-1])
    assert turn.context['self_model_history_reset']
    assert not turn.context['items']
    agent.reset()
    fresh = agent.send('ORION?')
    assert not fresh.context['items']
    assert child.statement not in str(provider.messages[-1])


def test_decision_basis_review_is_stable_across_followup_and_reload(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.DECISION)
    first = agent.send('ORION?')
    agent._store.retract(parent.id)
    reviewed = agent.send('ORION?')
    item = reviewed.context['items'][0]
    assert item['assertion_id'] == child.id
    assert item['basis']['state'] == 'review'
    assert 'Grundlage prüfen' in str(provider.messages[-1])
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    agent.load_history(saved(reviewed))
    followup = agent.send('ORION?')
    assert not followup.context['self_model_history_reset']
    assert 'OLD_PROFILE_DERIVATION' in str(provider.messages[-1])
    assert agent._store.get(child.id).status is Status.ACTIVE
    assert first.context['self_model_lineage_version'] == 3


def test_parent_change_during_provider_completion_invalidates_answer(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    def change(messages, tools):
        provider.messages.append(messages)
        agent._store.retract(parent.id)
        return Reply(text='STALE_DERIVATION')
    provider.complete = change
    turn = agent.send('ORION?')
    assert turn.context['invalidated']
    assert turn.reply != 'STALE_DERIVATION'


def test_grandparent_and_shared_diamond_capture_once(tmp_path, monkeypatch):
    from icarus_memory.self_model_basis import FrozenBuild
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    other = agent._store.record('Zwischenannahme.', Kind.STATE, Provenance(SourceType.INFERENCE),
                                derived_from=[parent.id], at=AT)
    child.derived_from.append(other.id)
    reads = []
    original = agent._store.get
    monkeypatch.setattr(agent._store, 'get', lambda key: (reads.append(key), original(key))[1])
    build = FrozenBuild(agent._store, at=AT, max_sensitivity=Sensitivity.NORMAL,
        support_build=agent._support_resolver.build(at=AT, local=True, max_sensitivity=Sensitivity.NORMAL))
    assert build.assess(child) is not None
    assert reads.count(parent.id) == 1
    first = agent.send('ORION?')
    assert len(first.context['items']) == 1
    agent._store.retract(parent.id)
    second = agent.send('ORION?')
    assert not second.context['items']
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])


@pytest.mark.parametrize('kind', [Kind.STATE, Kind.DECISION, Kind.GOAL])
@pytest.mark.parametrize('failure', ['missing', 'cycle', 'cap', 'protected'])
def test_incomplete_or_protected_graph_withholds_whole_candidate(tmp_path, monkeypatch, kind, failure):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=kind)
    if failure == 'missing': parent.derived_from = ['synthetic:missing']
    elif failure == 'cycle': parent.derived_from = [child.id]
    elif failure == 'protected': parent.sensitivity = Sensitivity.SPECIAL_CATEGORY
    else:
        previous = parent
        for number in range(128):
            ancestor = agent._store.record(f'Basis {number}.', Kind.STATE,
                                          Provenance(SourceType.USER_STATED), at=AT)
            previous.derived_from = [ancestor.id]
            previous = agent._store._backend._data[ancestor.id]
    agent._max_sensitivity = Sensitivity.NORMAL
    turn = agent.send('ORION?')
    assert not turn.context['items']
    assert turn.context['basis_omitted']
    assert child.statement not in str(provider.messages[-1])
    assert parent.id not in str(provider.messages[-1])


def test_real_goal_finish_reopen_edges_remain_supported(tmp_path, monkeypatch):
    from icarus_memory.goals import finish, reopen
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.GOAL)
    # Real user goal with no supporting premise ambiguity.
    child.provenance.source_type = SourceType.USER_STATED
    child.derived_from = []
    child.provenance.source_type = SourceType.USER_STATED
    completion = finish(agent._store, child.id, 'achieved')
    first = agent.send('ORION?')
    assert first.context['items'][0]['assertion_id'] == completion.id
    assert first.context['items'][0]['basis']['state'] == 'supported'
    reopened = reopen(agent._store, completion.id)
    next_turn = agent.send('ORION?')
    assert next_turn.context['items'][0]['assertion_id'] == reopened.id
    assert next_turn.context['items'][0]['basis']['state'] == 'supported'
    complete_again = finish(agent._store, reopened.id, 'stopped')
    third = agent.send('ORION?')
    assert third.context['items'][0]['assertion_id'] == complete_again.id
    assert third.context['items'][0]['basis']['state'] == 'supported'


@pytest.mark.parametrize('damage', ['reciprocal', 'kind', 'typed', 'extra_protected', 'extra_invalid', 'expired'])
def test_goal_near_matches_do_not_get_blanket_exemption(tmp_path, monkeypatch, damage):
    from icarus_memory.goals import finish
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.GOAL)
    child.derived_from = []
    child.provenance.source_type = SourceType.USER_STATED
    completion = finish(agent._store, child.id, 'achieved')
    child = agent._store._backend._data[child.id]
    completion = agent._store._backend._data[completion.id]
    if damage == 'reciprocal': child.superseded_by = 'wrong'
    if damage == 'kind': child.kind = Kind.STATE
    if damage == 'typed': completion.structured['goal_id'] = 'wrong'
    if damage == 'expired': child.expires_at = AT-timedelta(seconds=1)
    if damage.startswith('extra_'):
        completion.derived_from.append(parent.id)
        if damage == 'extra_protected': parent.sensitivity = Sensitivity.SPECIAL_CATEGORY
        else: agent._store.retract(parent.id)
    agent._max_sensitivity = Sensitivity.NORMAL
    turn = agent.send('ORION?')
    if damage == 'extra_protected': assert not turn.context['items']
    else: assert turn.context['items'][0]['basis']['state'] == 'review'


def test_snapshot_parent_cannot_change_between_assessment_and_metadata(tmp_path, monkeypatch):
    from icarus_memory import self_model_history
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    captured = []
    original = self_model_history.capture
    def change(assessment, at):
        parent.provenance.verbatim = 'changed nested content'
        parent.derived_from.append('missing')
        result = original(assessment, at)
        captured.append(result)
        return result
    monkeypatch.setattr(self_model_history, 'capture', change)
    turn = agent.send('ORION?')
    assert turn.context['invalidated']
    assert provider.messages == []
    assert captured and 'changed nested content' not in str(captured)


def test_legacy_root_only_lineage_is_not_upgraded(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    first = agent.send('ORION?')
    first.context['self_model_lineage_version'] = 1
    agent.load_history(saved(first))
    turn = agent.send('ORION?')
    assert turn.context['self_model_history_reset']
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])


def test_parent_age_changes_signature_without_withdrawing_basis(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    parent.recorded_at = AT-timedelta(days=4)
    first = agent.send('ORION?')
    clock[0] += timedelta(days=4)  # parent becomes stale; selected root remains current
    second = agent.send('ORION?')
    assert second.context['self_model_history_reset']
    assert second.context['items'][0]['basis']['state'] == 'supported'
    before = first.context['self_model_inputs'][child.id]
    after = second.context['self_model_inputs'][child.id]
    assert before['fingerprint'] == after['fingerprint']
    assert before['basis_signature'] != after['basis_signature']


def test_review_constraint_is_data_not_binding_instruction(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.CONSTRAINT)
    child.provenance.source_type = SourceType.USER_STATED
    agent._store.retract(parent.id)
    turn = agent.send('ORION?')
    assert turn.context['items'][0]['basis']['state'] == 'review'
    packet, text = agent.context_packet('ORION?')
    assert 'Grundlage prüfen' in text
    assert 'Bindende Grenzen des Nutzers:' not in text


def test_current_api_hides_changed_basis_and_preserves_new_review_label(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.DECISION)
    app = create_app(agent._store, agent=agent, episodes=agent._episodes, knowledge=agent._knowledge)
    conversation = app.state.conversations.create('Synthetic basis')
    client = TestClient(app)
    url = f'/api/v1/conversations/{conversation.id}'
    first = client.post(url+'/messages', json={'message':'ORION?'}).json()
    assert len(first['context']['items']) == 1
    agent._store.retract(parent.id)
    current = client.get(url).json()
    assert not current['context']['items']
    assert current['messages'][-1]['content'] == 'OLD_PROFILE_DERIVATION'
    next_turn = client.post(url+'/messages', json={'message':'ORION?'}).json()
    assert next_turn['context']['items'][0]['basis']['state'] == 'review'
    assert 'Grundlage prüfen' in str(provider.messages[-1])
    assert client.get(url).json()['context']['items'][0]['basis']['state'] == 'review'


def test_one_build_budget_counts_roots_and_shared_ancestors_globally(tmp_path, monkeypatch):
    from icarus_memory.self_model_basis import FrozenBuild
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    other = agent._store.record('Zweite Ableitung.', Kind.STATE, Provenance(SourceType.INFERENCE),
                               derived_from=[parent.id], at=AT)
    build = FrozenBuild(agent._store, at=AT, max_sensitivity=Sensitivity.NORMAL,
        support_build=agent._support_resolver.build(at=AT, local=True, max_sensitivity=Sensitivity.NORMAL), node_limit=3)
    assert build.assess(child)
    assert build.assess(other)
    assert len(build.nodes) == 3
    extra = agent._store.record('Dritte Ableitung.', Kind.STATE, Provenance(SourceType.INFERENCE), at=AT)
    assert build.assess(extra) is None
    assert len(build.nodes) == 3


def test_freezes_mutable_resolver_result_before_reading_next_parent(tmp_path, monkeypatch):
    from icarus_memory.self_model_basis import FrozenBuild
    from icarus_memory import self_model_history
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.DECISION)
    other = agent._store.record('Andere Grundlage.', Kind.STATE, Provenance(SourceType.USER_STATED), at=AT)
    child.derived_from.append(other.id)
    def mutable_get(identifier):
        if identifier == other.id:
            parent.status = Status.RETRACTED
            parent.provenance.verbatim = 'changed nested data'
        return agent._store._backend._data.get(identifier)
    monkeypatch.setattr(agent._store, 'get', mutable_get)
    build = FrozenBuild(agent._store, at=AT, max_sensitivity=Sensitivity.NORMAL,
        support_build=agent._support_resolver.build(at=AT, local=True, max_sensitivity=Sensitivity.NORMAL))
    captured = build.assess(child)
    assert captured.basis['state'] == 'supported'
    assert build.nodes[parent.id].status is Status.ACTIVE
    assert build.nodes[parent.id].provenance.verbatim != 'changed nested data'
    entry = self_model_history.capture(captured, AT)
    assert not self_model_history.available({child.id:entry}, agent._store, at=AT, resolver=agent._support_resolver, local=True)


@pytest.mark.parametrize('root_state', ['disputed', 'outdated'])
def test_basis_review_keeps_explicit_root_state_qualification(tmp_path, monkeypatch, root_state):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch, kind=Kind.CONSTRAINT)
    child.provenance.source_type = SourceType.USER_STATED
    agent._store.retract(parent.id)
    if root_state == 'disputed': child.status = Status.DISPUTED
    else: clock[0] += timedelta(days=1200)
    packet, text = agent.context_packet('ORION?')
    assert packet.items[0].state == root_state
    assert 'Grundlage prüfen' in text
    assert ('widersprüchlich' if root_state == 'disputed' else 'nicht als aktuell') in text
    assert 'Bindende Grenzen des Nutzers:' not in text


@pytest.mark.parametrize('corruption', ['missing_basis', 'missing_signature', 'malformed_basis', 'item_mismatch'])
def test_malformed_dependency_metadata_cannot_certify_old_history(tmp_path, monkeypatch, corruption):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    turn = agent.send('ORION?')
    entry = turn.context['self_model_inputs'][child.id]
    if corruption == 'missing_basis': del entry['basis']
    elif corruption == 'missing_signature': del entry['basis_signature']
    elif corruption == 'malformed_basis': entry['basis']['version'] = True
    else: turn.context['items'][0]['basis'] = {'version':1, 'state':'review', 'reason':'changed'}
    agent.load_history(saved(turn))
    fresh = agent.send('ORION?')
    assert fresh.context['self_model_history_reset']
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])


@pytest.mark.parametrize('kind', [Kind.STATE, Kind.DECISION])
def test_persisted_parent_basis_revalidation_after_sqlite_restart(tmp_path, monkeypatch, kind):
    from fastapi.testclient import TestClient
    from icarus_memory import SelfModelStore, SqliteBackend
    from icarus_memory.server import create_app
    agent, provider, _, clock = setup_profile(tmp_path, monkeypatch)
    path = tmp_path / 'basis.sqlite'
    agent._store = SelfModelStore(SqliteBackend(path), 'synthetic')
    parent = agent._store.record('Budgetannahme.', Kind.STATE, Provenance(SourceType.USER_STATED), at=AT,
                                expires_at=AT+timedelta(hours=1))
    child = agent._store.record('ORION ist finanziert.', kind, Provenance(SourceType.INFERENCE),
                               derived_from=[parent.id], at=AT)
    app = create_app(agent._store, agent=agent, knowledge=agent._knowledge, episodes=agent._episodes)
    cid = app.state.conversations.create('Synthetic persistent basis').id
    url = f'/api/v1/conversations/{cid}'
    client = TestClient(app)
    first = client.post(url+'/messages', json={'message':'ORION?'}).json()
    assert [i['assertion_id'] for i in first['context']['items']] == [child.id]
    clock[0] += timedelta(hours=2)
    assert agent._store.get(parent.id).status is Status.ACTIVE  # clock-only change
    reopened = SelfModelStore(SqliteBackend(path), 'synthetic')
    fresh = agent.scoped(provider, frozenset())
    fresh._store = reopened
    app2 = create_app(reopened, agent=fresh, knowledge=agent._knowledge, episodes=agent._episodes)
    client2 = TestClient(app2)
    assert not client2.get(url).json()['context']['items']
    second = client2.post(url+'/messages', json={'message':'ORION?'}).json()
    assert second['context']['self_model_history_reset']
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    assert second['messages'][1]['content'] == 'OLD_PROFILE_DERIVATION'
    if kind is Kind.STATE: assert not second['context']['items']
    else: assert second['context']['items'][0]['basis']['state'] == 'review'
    third = client2.post(url+'/messages', json={'message':'ORION?'}).json()
    assert not third['context']['self_model_history_reset']


def test_only_grandparent_withdrawal_invalidates_selected_child(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    grandparent = agent._store.record('Vorbedingung.', Kind.STATE, Provenance(SourceType.USER_STATED), at=AT)
    parent.derived_from = [grandparent.id]
    parent.provenance.source_type = SourceType.INFERENCE
    first = agent.send('ORION?')
    assert [i['assertion_id'] for i in first.context['items']] == [child.id]
    agent._store.retract(grandparent.id)
    second = agent.send('ORION?')
    assert agent._store.get(parent.id).status is Status.ACTIVE
    assert not second.context['items']
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])


def test_parent_fingerprint_change_resets_history_without_declaring_child_false(tmp_path, monkeypatch):
    agent, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    first = agent.send('ORION?')
    parent.provenance.verbatim = 'Synthetic changed original read'
    second = agent.send('ORION?')
    assert second.context['self_model_history_reset']
    assert second.context['items'][0]['basis']['state'] == 'supported'
    assert 'OLD_PROFILE_DERIVATION' not in str(provider.messages[-1])
    assert first.context['self_model_inputs'][child.id]['fingerprint'] == second.context['self_model_inputs'][child.id]['fingerprint']


def test_approval_followup_revalidates_unselected_parent(tmp_path, monkeypatch):
    from tests.test_agent import make_agent
    from icarus_memory.providers import ToolCall
    base, provider, parent, child, clock = setup_basis(tmp_path, monkeypatch)
    agent = make_agent(base._store, base._audit,
        Reply(text='OLD_BASIS_ANSWER', tool_calls=[ToolCall('x', 'mail_senden',
              {'to':'synthetic@example.org', 'subject':'S', 'body':'B'})]), Reply(text='Completed'),
        sink=lambda _: 'Synthetic success')
    agent._support_resolver = base._support_resolver
    pending = agent.send('ORION?').approvals[0]
    base._store.retract(parent.id)
    result = agent.resolve(pending.id, True, 'synthetic@example.org')
    assert result.context['self_model_history_reset']
    assert result.context['self_model_inputs'] == {}
    assert 'OLD_BASIS_ANSWER' not in str(agent.provider.seen[-1])
