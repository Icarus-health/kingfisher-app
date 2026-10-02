"""Hybrid candidates must pass the real Agent's canonical evidence boundary."""
import math
import httpx

import pytest

from icarus_memory.knowledge_search import HybridKnowledgeSearch, fuse_rankings, unit_vector
from tests.test_context import _knowledge_agent


class Embedder:
    is_local = True
    model_key = 'synthetic-model:immutable-weights'

    def __init__(self):
        self.calls = []
        self.error = False

    def embed(self, texts):
        self.calls.append(list(texts))
        if self.error:
            raise RuntimeError('synthetic unavailable endpoint')
        return [[1.0, 0.0] for _ in texts]


def prepared(tmp_path, text='Der Zuschuss wurde bewilligt.'):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept(text)
    embedder = Embedder()
    search = HybridKnowledgeSearch.prepare(agent._knowledge, episodes.support_snapshot, [claim.id], embedder)
    agent._knowledge_search = search
    return agent, provider, episodes, accept, claim, source, embedder


def test_paraphrase_without_common_tokens_reaches_actual_provider(tmp_path):
    agent, provider, _, _, claim, _, _ = prepared(tmp_path)
    turn = agent.send('Finanzierungsentscheidung?')
    assert [i['assertion_id'] for i in turn.context['items']] == ['claim:' + claim.id]
    assert claim.statement in str(provider.messages[-1])
    assert turn.context['knowledge_retrieval']['ranking_mode'] == 'hybrid'
    assert turn.context['knowledge_retrieval']['semantic_scope'] == 'explicit_snapshot'
    assert 'ausgewählte Aussagen' in str(provider.messages[-1])


def test_default_path_stays_lexical_and_scoped_agent_keeps_opt_in(tmp_path):
    agent, provider, _, _, claim, _, embedder = prepared(tmp_path)
    search = agent._knowledge_search
    agent._knowledge_search = None
    assert agent.send('Finanzierungsentscheidung?').context['items'] == []
    assert len(embedder.calls) == 1
    agent._knowledge_search = search
    scoped = agent.scoped(provider, frozenset())
    assert scoped.send('Finanzierungsentscheidung?').context['items'][0]['assertion_id'] == 'claim:' + claim.id


@pytest.mark.parametrize('change', ['ignore', 'retract', 'delete'])
def test_stale_vectors_never_restore_withdrawn_evidence(tmp_path, change):
    agent, provider, episodes, _, claim, source, _ = prepared(tmp_path)
    if change == 'ignore':
        episodes.ignore(source.id)
    elif change == 'retract':
        agent._knowledge.retract(claim.id, reason='synthetic withdrawal')
    else:
        with episodes._conn:
            episodes._conn.execute('DELETE FROM episodes WHERE id=?', (source.id,))
    turn = agent.send('Finanzierungsentscheidung?')
    assert turn.context['items'] == []
    assert claim.statement not in str(provider.messages[-1])
    assert turn.context['knowledge_retrieval']['semantic_stale'] == 1


def test_invalid_dependency_is_checked_even_without_query_overlap(tmp_path):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    root, source = accept('Die Grundlage liegt vor.')
    claim, _ = accept('Der Zuschuss wurde bewilligt.', [root.id])
    agent._knowledge_search = HybridKnowledgeSearch.prepare(agent._knowledge, episodes.support_snapshot, [claim.id], Embedder())
    episodes.ignore(source.id)
    assert agent.send('Finanzierungsentscheidung?').context['items'] == []
    assert claim.statement not in str(provider.messages[-1])


def test_remote_answer_provider_never_invokes_embedding(tmp_path):
    agent, provider, _, _, claim, _, embedder = prepared(tmp_path)
    provider.is_local = False
    assert agent.send('Finanzierungsentscheidung?').context['items'] == []
    assert len(embedder.calls) == 1
    assert claim.statement not in str(provider.messages[-1])


def test_remote_embedding_is_rejected_before_any_call(tmp_path):
    agent, _, episodes, accept = _knowledge_agent(tmp_path)
    claim, _ = accept('synthetic')
    embedder = Embedder()
    embedder.is_local = False
    with pytest.raises(ValueError, match='local'):
        HybridKnowledgeSearch.prepare(agent._knowledge, episodes.support_snapshot, [claim.id], embedder)
    assert embedder.calls == []


@pytest.mark.parametrize('failure', ['endpoint', 'model', 'locality', 'dimension', 'nan', 'zero'])
def test_embedding_failure_keeps_exact_lexical_fallback(tmp_path, failure):
    agent, _, _, _, claim, _, embedder = prepared(tmp_path)
    if failure == 'endpoint': embedder.error = True
    elif failure == 'model': embedder.model_key = 'changed-weights'
    elif failure == 'locality': embedder.is_local = False
    elif failure == 'dimension': embedder.embed = lambda texts: [[1.0]]
    elif failure == 'nan': embedder.embed = lambda texts: [[math.nan, 1.0]]
    elif failure == 'zero': embedder.embed = lambda texts: [[0.0, 0.0]]
    turn = agent.send('Zuschuss?')
    assert turn.context['items'][0]['assertion_id'] == 'claim:' + claim.id
    assert turn.context['knowledge_retrieval']['ranking_mode'] == 'lexical'
    assert turn.context['knowledge_retrieval']['semantic_status'] != 'ok'


def test_unrelated_vector_does_not_become_a_match(tmp_path):
    agent, _, _, _, _, _, embedder = prepared(tmp_path)
    embedder.embed = lambda texts: [[0.0, 1.0]]
    assert agent.send('Orangensaft?').context['items'] == []


def test_snapshot_bounds_and_unavailable_sources_make_no_embedding_call(tmp_path):
    agent, _, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept('synthetic')
    embedder = Embedder()
    with pytest.raises(ValueError):
        HybridKnowledgeSearch.prepare(agent._knowledge, episodes.support_snapshot, ['x'] * 129, embedder)
    assert not embedder.calls
    episodes.ignore(source.id)
    search = HybridKnowledgeSearch.prepare(agent._knowledge, episodes.support_snapshot, [claim.id], embedder)
    assert not embedder.calls
    found, meta = search.search_context('synthetic', agent._knowledge, episodes.support_snapshot)
    assert meta['semantic_snapshot_items'] == 0
    assert not embedder.calls


def test_consensus_outranks_single_channel_and_duplicates_do_not_vote_twice():
    assert fuse_rankings(['lexical', 'both', 'both'], ['semantic', 'both']) == ['both', 'lexical', 'semantic']


def test_source_change_during_query_embedding_is_rechecked(tmp_path):
    agent, provider, episodes, _, claim, source, embedder = prepared(tmp_path)
    def withdraw(texts):
        episodes.ignore(source.id)
        return [[1.0, 0.0]]
    embedder.embed = withdraw
    assert agent.send('Finanzierungsentscheidung?').context['items'] == []
    assert claim.statement not in str(provider.messages[-1])


def test_out_of_range_embedding_numbers_are_rejected():
    with pytest.raises(ValueError): unit_vector([10 ** 1000, 1])


def test_adapter_timeout_preserves_available_lexical_result(tmp_path):
    agent, _, _, _, claim, _, embedder = prepared(tmp_path)
    def timeout(texts): raise httpx.ReadTimeout('synthetic local timeout')
    embedder.embed = timeout
    assert agent.send('Zuschuss?').context['items'][0]['assertion_id'] == 'claim:' + claim.id


def test_short_query_can_use_semantics_without_lexical_tokens(tmp_path):
    agent, provider, _, _, claim, _, _ = prepared(tmp_path, 'Künstliche Intelligenz unterstützt die Entwürfe.')
    assert agent.send('KI?').context['items'][0]['assertion_id'] == 'claim:' + claim.id


def test_keyboard_interrupt_is_not_hidden_as_lexical_success(tmp_path):
    agent, _, _, _, _, _, embedder = prepared(tmp_path)
    def interrupted(texts): raise KeyboardInterrupt()
    embedder.embed = interrupted
    with pytest.raises(KeyboardInterrupt): agent.send('Zuschuss?')
