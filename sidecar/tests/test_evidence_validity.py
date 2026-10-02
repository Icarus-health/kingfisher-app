"""M1 synthetic regressions through digest collection and actual Agent payloads."""
import json
from datetime import timedelta
from unittest.mock import patch
import pytest
from tests.test_context import _knowledge_agent, AT
from tests.test_person_digests import setup, endpoint
from icarus_memory.graph import person_id
from icarus_memory.person_digest_context import collect
from icarus_memory.proposals import Evidence
from icarus_memory.providers import Reply


def digest_claim(app, episode):
    p, _ = app.state.knowledge_service.propose(subject_ref=person_id('Ada'), predicate='note',
        value=episode.body, statement=episode.body, rationale='Synthetic',
        evidence=[Evidence(episode.id, episode.body, episode.digest)])
    return app.state.knowledge_service.accept(p.id, supersedes=[])


def test_archived_digest_retains_sources_and_cached_output(monkeypatch):
    app, client, provider, episode = setup(monkeypatch)
    digest_claim(app, episode)
    first = client.post(endpoint(), json={}).json()
    app.state.episodes.mark_consolidated(episode.id)
    app.state.episodes.archive_before(episode.reference_time() + timedelta(days=1))
    assert client.get(endpoint()).json()['digest'] == first['digest']
    assert {s['status'] for s in collect(app, person_id('Ada'))['sources']} == {'observed', 'confirmed'}


@pytest.mark.parametrize('change', ['quote', 'empty_quote', 'digest', 'ignore', 'missing', 'summary'])
def test_digest_invalid_evidence_invalidates_cache(monkeypatch, change):
    from icarus_memory.episodes import EpisodeKind
    app, client, provider, episode = setup(monkeypatch)
    claim = digest_claim(app, episode)
    # Shared source never enters raw observations, only the exact-identity claim.
    episode.participants = ['Ada', 'Bea']; app.state.episodes._put(episode)
    assert client.post(endpoint(), json={}).json()['status'] == 'ready'
    if change == 'ignore': app.state.episodes.ignore(episode.id)
    elif change == 'missing':
        with app.state.episodes._conn:
            app.state.episodes._conn.execute('DELETE FROM episodes WHERE id=?', (episode.id,))
    elif change == 'empty_quote':
        # Persisted content is immutable; simulate corrupt read material without
        # weakening the store's integrity trigger.
        original = app.state.claims.by_reference
        def corrupted(*args, **kwargs):
            found = original(*args, **kwargs)
            for value in found:
                value.evidence = [Evidence(episode.id, '   ', episode.digest)]
            return found
        monkeypatch.setattr(app.state.claims, 'by_reference', corrupted)
    else:
        if change == 'quote': episode.body = 'Synthetic changed text without quote'
        if change == 'digest': episode.digest = 'different'
        if change == 'summary': episode.kind = EpisodeKind.SUMMARY
        app.state.episodes._put(episode)
    result = client.get(endpoint())
    assert result.status_code == 200
    assert result.json()['digest'] is None
    assert not any(s['ref'] == f'claim:{claim.id}' for s in collect(app, person_id('Ada'))['sources'])


def accept_expiring(agent, episodes, tmp_path, text, dependencies=(), until=None):
    from icarus_memory.claims import KnowledgeService
    from icarus_memory.proposals import ProposalStore
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    service = KnowledgeService(proposals=ProposalStore(tmp_path / 'expiry-proposals.db'),
                               claims=agent._knowledge, episodes=episodes)
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetic', text,
        Provenance(source_type=SourceType.CHAT, source_ref='synthetic:' + text), at=AT)
    proposal, _ = service.propose(subject_ref=person_id(text), predicate='note', value=text,
        statement=text, rationale='Synthetic', evidence=[Evidence(source.id,text,source.digest)],
        depends_on=list(dependencies), valid_until=until, at=AT)
    return service.accept(proposal.id, supersedes=[], at=AT), source


@pytest.mark.parametrize('reload', [False, True])
@pytest.mark.parametrize('parent', [False, True])
def test_expired_input_cannot_return_via_history(tmp_path, reload, parent):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    basis, _ = accept_expiring(agent, episodes, tmp_path, 'Die Grundlage wurde bestätigt.', until=AT+timedelta(hours=1) if parent else None)
    claim, _ = accept_expiring(agent, episodes, tmp_path, 'Kranz leitet Atlas.', [basis.id] if parent else [], until=None if parent else AT+timedelta(hours=1))
    def answer(messages, tools):
        provider.messages.append(messages)
        return Reply(text='DERIVED_PRIVATE_FACT')
    provider.complete = answer
    with patch('icarus_memory.knowledge_context.now', return_value=AT):
        first = agent.send('Was macht Kranz?')
    history = [{'role':'user','content':'Was macht Kranz?'},
               {'role':'assistant','content':first.reply,'context':first.context}]
    if reload:
        agent = agent.scoped(provider, frozenset())
        agent.load_history(history)
    with patch('icarus_memory.knowledge_context.now', return_value=AT+timedelta(hours=2)):
        second = agent.send('Weiter?')
    assert 'DERIVED_PRIVATE_FACT' not in str(provider.messages[-1])
    assert second.context['knowledge_history_reset'] is True
    assert second.context['knowledge_claim_lineage_version'] == 2
    assert second.context['knowledge_claim_ids'] == []
    assert history[1]['content'] == 'DERIVED_PRIVATE_FACT'


def test_expiry_during_provider_blocks_answer_and_returned_tool(tmp_path):
    from icarus_memory.providers import ToolCall
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, _ = accept_expiring(agent, episodes, tmp_path, 'Kranz leitet Atlas.', until=AT+timedelta(hours=1))
    with patch('icarus_memory.knowledge_context.now', return_value=AT) as clock:
        agent.send('Was macht Kranz?')
        def answer(messages, tools):
            clock.return_value = AT+timedelta(hours=2)
            return Reply(text='EXPIRED_ANSWER', tool_calls=[ToolCall(id='x',name='forbidden',arguments={})])
        provider.complete = answer
        agent._knowledge_context_items = lambda _: ()  # expired root only exists in OLD context
        agent._handle = lambda *args: pytest.fail('stale tool executed')
        turn = agent.send('Weiter?')
    assert turn.context['invalidated'] is True
    assert turn.context['knowledge_claim_ids'] == []
    assert turn.reply != 'EXPIRED_ANSWER'


def test_unknown_legacy_lineage_is_not_verified_empty(tmp_path):
    agent, provider, _, _ = _knowledge_agent(tmp_path)
    agent.load_history([{'role':'user','content':'old-question'},
                        {'role':'assistant','content':'UNVERIFIED_FACT','context':{'items':[]}}])
    turn = agent.send('fresh-question')
    assert 'UNVERIFIED_FACT' not in str(provider.messages[-1])
    assert 'fresh-question' in str(provider.messages[-1])
    assert turn.context['knowledge_history_reset'] is True


def test_deep_dependency_digest_api_fails_closed_without_recursion(monkeypatch):
    app, client, provider, episode = setup(monkeypatch)
    claim = digest_claim(app, episode)
    rows = []
    for index in range(1100):
        d = claim.to_dict()
        d.update(id=f'deep:{index}', proposal_id=f'proposal:{index}',
                 depends_on=[f'deep:{index+1}'] if index < 1099 else [])
        rows.append((d['id'], d['proposal_id'], d['subject_ref'], d['predicate'], d['value'],
                     d['statement'], json.dumps(d['evidence']), 'active', d['created_at'], json.dumps(d)))
    with app.state.claims._conn:
        app.state.claims._conn.executemany('INSERT INTO knowledge_claims '
            '(id,proposal_id,subject_ref,predicate,value,statement,evidence,status,created_at,document) '
            'VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    result = client.get(endpoint())
    assert result.status_code == 200
    assert not app.state.claims.is_usable(app.state.claims.get('deep:0'))


@pytest.mark.parametrize('change', ['ignore', 'quote', 'digest', 'retract'])
def test_old_input_source_changes_reset_history_without_new_selection(tmp_path, change):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept('Kranz leitet Atlas.')
    first = agent.send('Was macht Kranz?')
    agent.load_history([{'role':'user','content':'old question'},
                        {'role':'assistant','content':'OLD_DERIVATION','context':first.context}])
    agent._knowledge_context_items = lambda _: ()
    if change == 'ignore': episodes.ignore(source.id)
    elif change == 'retract': agent._knowledge.retract(claim.id, reason='Synthetic correction')
    else:
        if change == 'quote': source.body = 'No matching evidence'
        else: source.digest = 'different'
        episodes._put(source)
    turn = agent.send('Fresh question')
    assert 'OLD_DERIVATION' not in str(provider.messages[-1])
    assert turn.context['knowledge_history_reset']
    assert turn.context['knowledge_claim_ids'] == []


def test_valid_history_retained_and_reset_is_persisted_boundary(tmp_path):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept('Kranz leitet Atlas.')
    first = agent.send('Was macht Kranz?')
    history = [{'role':'user','content':'original question'},
               {'role':'assistant','content':'VALID_ANSWER','context':first.context}]
    agent.load_history(history)
    with patch('icarus_memory.knowledge_context.now', return_value=AT+timedelta(days=100)):
        second = agent.send('Continue')
    assert 'VALID_ANSWER' in str(provider.messages[-1])
    assert not second.context['knowledge_history_reset']
    episodes.ignore(source.id)
    reset = agent.send('new-question')
    history += [{'role':'user','content':'new-question'},
                {'role':'assistant','content':'NEW_VALID_ANSWER','context':reset.context}]
    agent.load_history(history)
    third = agent.send('Continue again')
    assert 'NEW_VALID_ANSWER' in str(provider.messages[-1])
    assert 'VALID_ANSWER\'' not in str(provider.messages[-1]).replace('NEW_VALID_ANSWER', '')
    assert not third.context['knowledge_history_reset']
    assert agent._history_claim_ids == set()
    agent.reset()
    assert agent._history_claim_ids == set()


def test_server_persists_expiry_reset_and_keeps_displayed_conversation(tmp_path):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept_expiring(agent, episodes, tmp_path, 'Kranz leitet Atlas.', until=AT+timedelta(hours=1))
    def answer(messages, tools):
        provider.messages.append(messages)
        return Reply(text='STORED_DERIVATION' if len(provider.messages) == 1 else 'FRESH_ANSWER')
    provider.complete = answer
    app = create_app(agent._store, agent=agent, episodes=episodes, knowledge=agent._knowledge)
    conversation = app.state.conversations.create('Synthetic expiry')
    url = f'/api/v1/conversations/{conversation.id}/messages'
    client = TestClient(app)
    with patch('icarus_memory.knowledge_context.now', return_value=AT):
        assert client.post(url, json={'message':'Was macht Kranz?'}).status_code == 201
    with patch('icarus_memory.knowledge_context.now', return_value=AT+timedelta(hours=2)):
        assert client.post(url, json={'message':'Fresh question'}).status_code == 201
        assert 'STORED_DERIVATION' not in str(provider.messages[-1])
        saved = app.state.conversations.messages(conversation.id)
        assert saved[1].content == 'STORED_DERIVATION'
        assert saved[-1].metadata['context']['knowledge_history_reset']
        assert client.post(url, json={'message':'Continue'}).status_code == 201
        assert 'FRESH_ANSWER' in str(provider.messages[-1])
        assert not app.state.conversations.messages(conversation.id)[-1].metadata['context']['knowledge_history_reset']


@pytest.mark.parametrize('context', [None, {}, {'knowledge_claim_lineage_version': 1},
    {'knowledge_claim_lineage_version':True,'knowledge_claim_ids':[],'items':[]},
    {'self_model_lineage_version':3,'self_model_inputs':{},'knowledge_claim_lineage_version':1,'knowledge_claim_ids':[],'items':[{'assertion_id':'claim:missing'}]}])
def test_malformed_or_incomplete_lineage_omitted(tmp_path, context):
    agent, provider, _, _ = _knowledge_agent(tmp_path)
    agent.load_history([{'role':'assistant','content':'UNCERTIFIED','context':context}])
    turn = agent.send('Fresh')
    assert 'UNCERTIFIED' not in str(provider.messages[-1])
    assert turn.context['knowledge_history_reset']


def test_historical_mode_checks_all_ancestors_without_promoting_status(tmp_path):
    from icarus_memory.knowledge_context import evidence_chain_available
    agent, _, episodes, accept = _knowledge_agent(tmp_path)
    basis, source = accept('Synthetic basis')
    child, _ = accept('Kranz leitet Atlas.', [basis.id])
    agent._knowledge.retract(basis.id, reason='Synthetic withdrawal')
    assert not evidence_chain_available(child, agent._knowledge, episodes)
    assert evidence_chain_available(child, agent._knowledge, episodes, mode='historical')
    source.body = 'No original quote'
    episodes._put(source)
    assert not evidence_chain_available(child, agent._knowledge, episodes, mode='historical')


def test_resolve_propagates_lineage_reset_and_notices(tmp_path):
    from tests.test_agent import make_agent
    from icarus_memory.providers import ToolCall
    base, _, episodes, _ = _knowledge_agent(tmp_path)
    claim, _ = accept_expiring(base, episodes, tmp_path, 'Kranz leitet Atlas.', until=AT+timedelta(hours=1))
    sent = []
    agent = make_agent(base._store, base._audit,
        Reply(text='OLD_FACT', tool_calls=[ToolCall('x','mail_senden',{'to':'synthetic@example.org','subject':'Synthetic','body':'Synthetic'})]),
        Reply(text='Approved action summarized'), sink=lambda data: (sent.append(data), 'Synthetic success')[1])
    agent._knowledge = base._knowledge; agent._episodes = episodes; agent._snapshot_provider = episodes.support_snapshot; agent.provider.is_local = True
    with patch('icarus_memory.knowledge_context.now', return_value=AT):
        approval = agent.send('Was macht Kranz?').approvals[0]
    with patch('icarus_memory.knowledge_context.now', return_value=AT+timedelta(hours=2)):
        result = agent.resolve(approval.id, True, 'synthetic@example.org')
    assert sent == []
    assert result.context['knowledge_claim_lineage_version'] == 2
    assert result.context['knowledge_history_reset']
    assert result.context['knowledge_claim_ids'] == []
    assert result.notices
    assert result.context['invalidated']


def test_direct_calendar_and_errors_keep_reset_metadata(tmp_path, monkeypatch):
    from icarus_memory.providers import ProviderError
    agent, provider, _, _ = _knowledge_agent(tmp_path)
    legacy = [{'role':'assistant','content':'Unknown old fact','context':{}}]
    agent.load_history(legacy)
    agent._calendar_context = lambda: {'status':'available','events':[]}
    monkeypatch.setattr('icarus_memory.calendar_answers.answer', lambda *args: 'Direct calendar')
    direct = agent.send('Calendar')
    assert direct.context['knowledge_history_reset']
    assert direct.context['knowledge_claim_lineage_version'] == 2
    assert direct.notices
    agent._calendar_context = None
    agent.load_history(legacy)
    def fail(*args): raise ProviderError('Synthetic')
    provider.complete = fail
    error = agent.send('Fresh')
    assert error.context['knowledge_history_reset']
    assert error.context['knowledge_claim_ids'] == []
    assert error.notices


def test_loading_another_conversation_rebuilds_dependencies(tmp_path):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, _ = accept('Kranz leitet Atlas.')
    agent.send('Was macht Kranz?')
    assert claim.id in agent._history_claim_ids
    agent.load_history([{'role':'assistant','content':'OTHER_CONVERSATION',
        'context':{'items':[], 'self_model_lineage_version':3,'self_model_inputs':{},'knowledge_claim_lineage_version':1,'knowledge_claim_ids':[]}}])
    assert agent._history_claim_ids == set()
    turn = agent.send('Fresh')
    assert 'OTHER_CONVERSATION' in str(provider.messages[-1])
    assert not turn.context['knowledge_history_reset']


@pytest.mark.parametrize("reload", [False, True])
def test_approval_without_model_does_not_certify_local_result_for_egress(tmp_path, reload):
    from tests.test_agent import make_agent, ScriptedProvider
    from icarus_memory.providers import ToolCall
    base, _, _, _ = _knowledge_agent(tmp_path)
    agent = make_agent(base._store, base._audit,
        Reply(tool_calls=[ToolCall('x','mail_senden',{'to':'synthetic@example.org','subject':'S','body':'B'})]),
        sink=lambda _: 'LOCAL_RESULT')
    pending = agent.send('Synthetic request').approvals[0]
    agent._provider = None
    result = agent.resolve(pending.id, True, 'synthetic@example.org')
    assert result.context['history_egress'] == 'local_only'
    assert result.context['knowledge_claim_lineage_version'] == 2
    if reload:
        agent.load_history([{'role': 'assistant', 'content': result.reply,
                             'context': result.context}])
    external = ScriptedProvider(Reply(text='External follow-up'))
    agent._provider = external
    follow_up = agent.send('Continue externally')
    assert 'LOCAL_RESULT' not in str(external.seen)
    assert 'Continue externally' in str(external.seen)
    assert follow_up.context['history_omitted'] is True
    assert follow_up.notices
