"""Synthetische Originale: tatsächlicher Versand, eingefrorene Zeit und Veröffentlichung."""
import copy
import json
import sys
from pathlib import Path
from datetime import timedelta

import pytest

from tests.test_context_identity import core, AT
from icarus_memory import knowledge_context
from icarus_memory.providers import ProviderError, Reply

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from memory_probe_support import RecordingProvider


def change_source(episodes, identifier, **fields):
    with episodes._lock, episodes._conn:
        document = json.loads(episodes._conn.execute('SELECT document FROM episodes WHERE id=?', (identifier,)).fetchone()[0])
        for key, value in fields.items():
            if key == 'source_ref':
                document['provenance'][key] = value
            else:
                document[key] = value
                if key in {'occurred_at', 'recorded_at'}:
                    episodes._conn.execute(f'UPDATE episodes SET {key}=? WHERE id=?', (value, identifier))
        episodes._conn.execute('UPDATE episodes SET document=? WHERE id=?', (json.dumps(document), identifier))


def captured(recorder):
    return [json.loads(line[14:]) for line in recorder.calls[-1]['request']['messages'][1]['content'].splitlines()
            if line.startswith('- [knowledge] ')]


def test_actual_recorder_preserves_semantics_and_three_distinct_times(core):
    agent, provider, episodes, _, accept = core
    claim, episode = accept('person:alex', 'Alex Winter arbeitet am Atlas.', until=AT + timedelta(days=10))
    change_source(episodes, episode.id, occurred_at='2020-03-01T09:30:00+02:00', recorded_at='2026-09-12T11:00:00+02:00')
    expected = {'format': 'knowledge-context-v3', 'assertion_id': 'claim:' + claim.id,
        'statement': 'Alex Winter arbeitet am Atlas.', 'subject_ref': 'person:alex', 'target_ref': None, 'scope_ref': None,
        'predicate': 'observed_email', 'value': 'Alex Winter arbeitet am Atlas.',
        'claim_created_at': '2026-09-14T09:00:00+00:00', 'valid_from': None, 'valid_until': '2026-09-24T09:00:00+00:00',
        'primary_evidence': {'episode_id': episode.id, 'digest': episode.digest, 'source_type': 'email',
            'source_ref': 'synthetic:1', 'occurred_at': '2020-03-01T07:30:00+00:00', 'recorded_at': '2026-09-12T09:00:00+00:00'}}
    recorder = RecordingProvider(provider)
    agent._provider = recorder
    turn = agent.send('Was macht Alex Winter?')
    row = captured(recorder)[0]
    assert {key: value for key, value in row.items() if key != 'reason'} == expected
    assert turn.context['items'][0]['knowledge_projection'] == row
    assert turn.context['items'][0]['evidence_at_basis'] == 'occurred_at'
    assert turn.context['knowledge_claim_lineage_version'] == 2
    assert set(turn.context['knowledge_inputs']) == {claim.id}


@pytest.mark.parametrize('field,value', [('occurred_at', '2021-01-01T00:00:00+00:00'), ('recorded_at', '2026-09-10T00:00:00+00:00'), ('source_ref', 'synthetic:changed')])
@pytest.mark.parametrize('window', ['before', 'during', 'error'])
def test_metadata_races_suppress_provider_or_returned_answer(core, monkeypatch, field, value, window):
    agent, provider, episodes, claims, accept = core
    _, source = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    revision = claims.revision
    if window == 'before':
        original = agent.context_packet
        def context(query):
            result = original(query)
            change_source(episodes, source.id, **{field: value})
            return result
        monkeypatch.setattr(agent, 'context_packet', context)
    else:
        def complete(messages, tools):
            change_source(episodes, source.id, **{field: value})
            if window == 'error':
                raise ProviderError('synthetic failure')
            return Reply(text='STALE ANSWER')
        monkeypatch.setattr(provider, 'complete', complete)
    turn = agent.send('Was macht Alex Winter?')
    assert claims.revision == revision
    assert turn.context.get('invalidated') is True
    assert 'STALE ANSWER' not in turn.reply
    assert turn.context['items'] == []
    if window == 'before':
        assert provider.calls == []


def test_missing_event_time_is_null_and_equivalent_offset_keeps_history(core):
    agent, provider, episodes, _, accept = core
    _, source = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    recorder = RecordingProvider(provider); agent._provider = recorder
    first = agent.send('Was macht Alex Winter?')
    assert captured(recorder)[0]['primary_evidence']['occurred_at'] is None
    assert first.context['items'][0]['evidence_at_basis'] == 'recorded_at'
    change_source(episodes, source.id, recorded_at='2026-09-14T11:00:00+02:00')
    second = agent.send('Und weiter?')
    assert not second.context['knowledge_history_reset']


def test_huge_utf8_candidate_does_not_hide_smaller_rows(core):
    agent, provider, _, _, accept = core
    for index in range(6):
        accept(f'person:big{index}', 'Alex Winter ' + '界' * 4000 + str(index))
    small, _ = accept('person:small', 'Alex Winter hat Zeit.')
    recorder = RecordingProvider(provider); agent._provider = recorder
    turn = agent.send('Was macht Alex Winter?')
    assert [row['assertion_id'] for row in captured(recorder)] == ['claim:' + small.id]
    assert turn.context['knowledge_retrieval']['payload_omitted'] == 6
    assert turn.context['knowledge_retrieval']['truncated'] is True


@pytest.mark.parametrize('cleared', [False, True])
def test_changed_context_rejects_pending_approval_before_action(core, monkeypatch, cleared):
    from tests.test_agent import make_agent
    from icarus_memory.providers import ToolCall
    base, _, episodes, claims, accept = core
    _, source = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    sent = []
    agent = make_agent(base._store, base._audit,
        Reply(text='OLD', tool_calls=[ToolCall('x', 'mail_senden', {'to':'synthetic@example.org', 'subject':'S', 'body':'B'})]),
        Reply(text='executed'), sink=lambda row: (sent.append(row), 'sent')[1])
    agent._knowledge = claims; agent._episodes = episodes
    agent._snapshot_provider = episodes.support_snapshot
    agent.provider.is_local = True
    approval = agent.send('Was macht Alex Winter?').approvals[0]
    change_source(episodes, source.id, source_ref='synthetic:withdrawn')
    if cleared:
        agent.reset()
    turn = agent.resolve(approval.id, True, 'synthetic@example.org')
    assert sent == []
    assert turn.context['invalidated']
    assert turn.used_tools == []


@pytest.mark.parametrize('reload', [False, True])
@pytest.mark.parametrize('source_kind', ['primary', 'secondary', 'ancestor'])
def test_generation_continuity_cannot_be_laundered_into_old_history(core, reload, source_kind):
    from icarus_memory.proposals import Evidence
    agent, provider, episodes, _, accept = core
    parent, ancestor = accept('person:basis', 'Eine eigenständige Grundlage.')
    _, secondary = accept('person:second', 'Ein ergänzender Originalbeleg.')
    claim, primary = accept('person:alex', 'Alex Winter arbeitet am Atlas.', depends_on=[parent.id],
                            extra_evidence=[Evidence(secondary.id, secondary.body, secondary.digest)])
    first = agent.send('Was macht Alex Winter?')
    entry = copy.deepcopy(first.context['knowledge_inputs'][claim.id])
    assert set(entry['source_generations']) == {primary.id, secondary.id, ancestor.id}
    source = {'primary': primary, 'secondary': secondary, 'ancestor': ancestor}[source_kind]
    episodes.ignore(source.id); episodes.reopen(source.id)
    if reload:
        agent = agent.scoped(provider, frozenset())
        agent.load_history([{'role': 'user', 'content':'Was macht Alex Winter?'},
                            {'role':'assistant', 'content':'OLD_DERIVATION', 'context':first.context}])
    else:
        agent._history[-1]['content'] = 'OLD_DERIVATION'
    second = agent.send('Weiter?')
    assert second.context['knowledge_history_reset']
    assert 'OLD_DERIVATION' not in str(provider.calls[-1])
    assert first.context['knowledge_inputs'][claim.id] == entry
    third = agent.send('Noch weiter?')
    assert not third.context['knowledge_history_reset']


def test_primary_is_first_not_earliest_and_all_quotes_are_checked(core, monkeypatch):
    from icarus_memory.proposals import Evidence
    from icarus_memory.knowledge_render import KnowledgeInputBuild
    agent, provider, episodes, claims, accept = core
    _, secondary = accept('person:second', 'Ein älterer Originalbeleg.')
    change_source(episodes, secondary.id, occurred_at='2001-01-01T00:00:00+00:00')
    claim, primary = accept('person:alex', 'Alex Winter arbeitet am Atlas.',
                            extra_evidence=[Evidence(secondary.id, secondary.body, secondary.digest)])
    recorder = RecordingProvider(provider); agent._provider = recorder
    agent.send('Was macht Alex Winter?')
    assert captured(recorder)[0]['primary_evidence']['episode_id'] == primary.id
    original = claims.get
    def corrupt(identifier):
        row = original(identifier)
        row.evidence.append(Evidence(primary.id, 'ABSENT SECOND QUOTE', primary.digest))
        return row
    monkeypatch.setattr(claims, 'get', corrupt)
    assert KnowledgeInputBuild(claims, episodes.support_snapshot).capture(claim.id) is None


def test_valid_interval_is_start_inclusive_end_exclusive(core, monkeypatch):
    agent, provider, _, _, accept = core
    claim, _ = accept('person:alex', 'Alex Winter arbeitet am Atlas.', since=AT, until=AT+timedelta(seconds=1))
    recorder = RecordingProvider(provider); agent._provider = recorder
    agent.send('Was macht Alex Winter?')
    row = captured(recorder)[0]
    assert row['valid_from'] == '2026-09-14T09:00:00+00:00'
    assert row['valid_until'] == '2026-09-14T09:00:01+00:00'
    monkeypatch.setattr(knowledge_context, 'now', lambda: AT+timedelta(seconds=1))
    turn = agent.send('Weiter?')
    assert turn.context['knowledge_history_reset']
    assert not captured(recorder)


def test_current_cards_omit_changed_capture_but_keep_historical_metadata(core, tmp_path, monkeypatch):
    from icarus_memory.server import create_app
    from fastapi.testclient import TestClient
    agent, _, episodes, claims, accept = core
    _, source = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'api'))
    app = create_app(agent=agent, knowledge=claims, episodes=episodes)
    cid = app.state.conversations.create('Synthetic time').id
    with TestClient(app) as client:
        url = f'/api/v1/conversations/{cid}'
        assert client.post(url+'/messages', json={'message':'Was macht Alex Winter?'}).status_code == 201
        before = client.get(url).json()
        captured_item = copy.deepcopy(before['context']['items'][0])
        change_source(episodes, source.id, recorded_at='2026-09-11T00:00:00+00:00')
        after = client.get(url).json()
        assert after['context']['items'] == []
        assert after['messages'][-1]['metadata']['context']['items'] == []
        assert after['messages'][-1]['metadata']['context']['answer_contract']['status'] == 'invalidated'
        # Preserve the audit record in storage while rechecking its presentation.
        stored = app.state.conversations.messages(cid)[-1]
        assert stored.metadata['context']['items'] == [captured_item]


def test_combined_utf8_budget_keeps_five_whole_rows_by_continuing(core):
    agent, provider, _, _, accept = core
    for index in range(5):
        accept(f'person:big{index}', 'Alex Winter Atlas ' + '界' * 1100 + str(index))
    small, _ = accept('person:small', 'Alex Winter hat Zeit.')
    recorder = RecordingProvider(provider); agent._provider = recorder
    turn = agent.send('Was macht Alex Winter Atlas?')
    rows = captured(recorder)
    lines = [line for line in recorder.calls[-1]['request']['messages'][1]['content'].splitlines() if line.startswith('- [knowledge] ')]
    assert len(rows) == 5
    assert small.id in turn.context['knowledge_inputs']
    assert all(len(line[14:].encode()) <= 8192 for line in lines)
    assert len('\n'.join(lines).encode()) <= 32768
    assert turn.context['knowledge_retrieval']['payload_omitted'] == 1


@pytest.mark.parametrize('corruption', ['duplicate', 'missing', 'wrong_version', 'extra_generation', 'changed_item', 'legacy_nonempty'])
def test_malformed_lineage_never_certifies_history(core, corruption):
    from icarus_memory import knowledge_history
    agent, provider, _, _, accept = core
    claim, _ = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    turn = agent.send('Was macht Alex Winter?')
    context = copy.deepcopy(turn.context)
    if corruption == 'duplicate': context['knowledge_claim_ids'].append(claim.id)
    elif corruption == 'missing': context['knowledge_inputs'] = {}
    elif corruption == 'wrong_version': context['knowledge_inputs'][claim.id]['version'] = True
    elif corruption == 'extra_generation': context['knowledge_inputs'][claim.id]['source_generations']['invented'] = 0
    elif corruption == 'changed_item': context['items'][0]['knowledge_projection']['value'] = 'wrong'
    else: context['knowledge_claim_lineage_version'] = 1
    agent.load_history([{'role':'assistant', 'content':'CORRUPTED_HISTORY', 'context':context}])
    fresh = agent.send('Fresh question')
    assert fresh.context['knowledge_history_reset']
    assert 'CORRUPTED_HISTORY' not in str(provider.calls[-1])


def test_injected_server_rejects_different_claim_store(core, tmp_path, monkeypatch):
    from icarus_memory.server import create_app
    from icarus_memory.claims import ClaimStore
    agent, _, _, _, _ = core
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'api'))
    other = ClaimStore(tmp_path / 'other.sqlite3')
    try:
        with pytest.raises(ValueError, match='Wissensspeicher'):
            create_app(agent=agent, knowledge=other)
    finally:
        other.close()


@pytest.mark.parametrize('field', ['evidence_at', 'evidence_at_basis', 'projection_extra', 'missing_predicate'])
def test_context_metadata_requires_exact_projection_shape_and_matching_legacy_fields(core, field):
    import hashlib
    from icarus_memory import knowledge_history
    agent, _, _, _, accept = core
    accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    item = agent.send('Was macht Alex Winter?').context['items'][0]
    if field == 'evidence_at': item[field] = '1999-01-01T00:00:00+00:00'
    elif field == 'evidence_at_basis': item[field] = 'unknown'
    else:
        projection = item['knowledge_projection']
        if field == 'projection_extra': projection['invented'] = 'field'
        else: del projection['predicate']
        semantic = {key:value for key,value in projection.items() if key not in {'reason','format'}}
        item['knowledge_input']['projection_sha256'] = hashlib.sha256(json.dumps(semantic,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    assert knowledge_history.from_items([item]) is None


def test_build_budgets_count_all_distinct_claims_and_sources_without_eviction(core):
    from dataclasses import replace
    from types import SimpleNamespace
    from icarus_memory.knowledge_render import KnowledgeInputBuild
    from icarus_memory.proposals import Evidence
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    _, _, episodes, _, accept = core
    template, primary = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    # Unabhängige synthetische Claimobjekte prüfen das Gesamtbudget über mehrere Wurzeln.
    rows = {f'node-{i}': replace(template, id=f'node-{i}', depends_on=[]) for i in range(129)}
    loads = []
    def get(identifier):
        loads.append(identifier)
        return rows[identifier]
    build = KnowledgeInputBuild(SimpleNamespace(get=get), episodes.support_snapshot)
    for i in range(128): assert build.capture(f'node-{i}') is not None
    assert build.capture('node-128') is None
    assert build.capture('node-0') is not None
    assert len(loads) == 128
    evidence = [Evidence(primary.id, primary.body, primary.digest)]
    for i in range(128):
        episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetic', f'Source {i}',
            Provenance(source_type=SourceType.EMAIL, source_ref=f'synthetic:source:{i}'), at=AT)
        evidence.append(Evidence(episode.id, episode.body, episode.digest))
    rows['all-sources'] = replace(template, id='all-sources', evidence=evidence[:-1])
    rows['too-many'] = replace(template, id='too-many', evidence=evidence)
    reads = []
    def snapshot(identifier):
        reads.append(identifier)
        return episodes.support_snapshot(identifier)
    build = KnowledgeInputBuild(SimpleNamespace(get=get), snapshot)
    assert build.capture('all-sources') is not None
    assert build.capture('too-many') is None
    assert build.capture('all-sources') is not None
    assert len(reads) == 128


def test_provider_metadata_mutation_blocks_returned_tools(core, monkeypatch):
    from tests.test_agent import make_agent
    from icarus_memory.providers import ToolCall
    base, _, episodes, claims, accept = core
    _, source = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    sent = []
    agent = make_agent(base._store, base._audit, Reply(text='Unused'), sink=lambda row: sent.append(row))
    agent._knowledge=claims; agent._episodes=episodes; agent._snapshot_provider=episodes.support_snapshot
    agent.provider.is_local=True
    def complete(messages, tools):
        change_source(episodes, source.id, recorded_at='2025-01-01T00:00:00+00:00')
        return Reply(text='STALE', tool_calls=[ToolCall('x','mail_senden', {'to':'synthetic@example.org','subject':'S','body':'B'})])
    monkeypatch.setattr(agent.provider,'complete',complete)
    turn=agent.send('Was macht Alex Winter?')
    assert turn.context['invalidated']
    assert not turn.approvals and not turn.used_tools and not sent
    assert agent.policy.pending() == []


@pytest.mark.parametrize('mutation_window,expected_outcome,expected_actions', [
    ('before_action', 'rejected', 0), ('during_followup', 'approved', 1),
])
def test_http_resolution_persists_actual_approval_outcome_independent_of_followup(
        core, tmp_path, monkeypatch, mutation_window, expected_outcome, expected_actions):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    from icarus_memory.providers import ToolCall
    from tests.test_agent import make_agent

    base, _, episodes, claims, accept = core
    _, source = accept('person:alex', 'Alex Winter arbeitet am Atlas.')
    sent = []
    agent = make_agent(base._store, base._audit,
        Reply(text='Bitte prüfen.', tool_calls=[ToolCall('x', 'mail_senden',
            {'to': 'synthetic@example.org', 'subject': 'S', 'body': 'B'})]),
        Reply(text='STALE_FOLLOWUP'), sink=lambda row: (sent.append(row), 'sent')[1])
    agent._knowledge = claims
    agent._episodes = episodes
    agent._snapshot_provider = episodes.support_snapshot
    agent.provider.is_local = True
    complete = agent.provider.complete
    calls = 0
    def mutate_during_followup(messages, tools):
        nonlocal calls
        calls += 1
        if calls == 2 and mutation_window == 'during_followup':
            change_source(episodes, source.id, source_ref='synthetic:changed-during-followup')
        return complete(messages, tools)
    monkeypatch.setattr(agent.provider, 'complete', mutate_during_followup)
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'api'))
    app = create_app(agent=agent, episodes=episodes, knowledge=claims)
    cid = app.state.conversations.create('Synthetic actual approval outcome').id
    with TestClient(app) as client:
        url = f'/api/v1/conversations/{cid}'
        proposed = client.post(url + '/messages', json={'message': 'Was macht Alex Winter?'})
        assert proposed.status_code == 201
        action = proposed.json()['action_requests'][0]
        if mutation_window == 'before_action':
            change_source(episodes, source.id, source_ref='synthetic:changed-before-action')
        result = client.post(url + f'/approvals/{action["id"]}',
                             json={'granted': True, 'confirmation': 'synthetic@example.org'})
        assert result.status_code == 200
        assert len(sent) == expected_actions
        for payload in (result.json(), client.get(url).json()):
            resolved = payload['messages'][-1]
            assert resolved['metadata']['context']['invalidated'] is True
            assert resolved['metadata']['approval_outcome'] == expected_outcome
            assert payload['action_requests'][0]['state'] == expected_outcome
            assert 'STALE_FOLLOWUP' not in resolved['content']
        persisted = app.state.conversations.messages(cid)[-1]
        assert persisted.metadata['approval_outcome'] == expected_outcome
        assert client.post(url + f'/approvals/{action["id"]}',
                           json={'granted': True, 'confirmation': 'synthetic@example.org'}).status_code == 409
        assert len(sent) == expected_actions
