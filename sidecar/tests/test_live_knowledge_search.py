"""Derived semantic vectors must refresh without becoming source authority."""
from .test_context_identity import core
from .test_knowledge_search import Embedder
from .test_knowledge_time import change_source


def live(core, *, limit=512):
    from icarus_memory.knowledge_search import RefreshingKnowledgeSearch
    embedder = Embedder()
    search = RefreshingKnowledgeSearch(embedder, limit=limit)
    core[0]._knowledge_search = search
    return search, embedder


def test_new_claim_is_searchable_and_unchanged_vectors_are_reused(core):
    agent, _, episodes, claims, accept = core
    first, _ = accept('project:first', 'Der Zuschuss wurde bewilligt.')
    search, embedder = live(core)
    first_result, _ = search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    assert [row.id for row in first_result] == [first.id]
    initial_calls = len(embedder.calls)
    search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    assert len(embedder.calls) == initial_calls + 1  # query only, no repeat document embedding
    second, _ = accept('project:second', 'Ein weiterer Zuschuss wurde bewilligt.')
    result, metadata = search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    assert {row.id for row in result} == {first.id, second.id}
    assert metadata['semantic_coverage'] == 'complete'


def test_changed_metadata_refreshes_and_withdrawal_removes_cached_row(core):
    _, _, episodes, claims, accept = core
    claim, source = accept('project:grant', 'Zuschuss bewilligt.')
    search, embedder = live(core)
    search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    change_source(episodes, source.id, source_ref='synthetic:changed')
    result, metadata = search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    assert [row.id for row in result] == [claim.id]
    assert len(embedder.calls) == 4  # each changed projection rebuilt once, two queries
    episodes.ignore(source.id)
    result, _ = search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    assert result == []
    assert search.cached_count == 0


def test_limit_is_visible_and_embedding_failure_keeps_lexical_recall(core):
    _, _, episodes, claims, accept = core
    for index in range(4): accept('project:p'+str(index), 'Atlas Zuschuss '+str(index))
    search, embedder = live(core, limit=2)
    _, metadata = search.search_context('Atlas', claims, episodes.support_snapshot)
    assert metadata['semantic_coverage'] == 'partial'
    assert metadata['semantic_inventory_total'] == 4
    embedder.error = True
    results, metadata = search.search_context('Atlas', claims, episodes.support_snapshot)
    assert len(results) == 4
    assert metadata['semantic_status'] == 'unavailable'


def test_remote_answer_path_never_initializes_live_vectors(core):
    agent, provider, episodes, claims, accept = core
    accept('project:p', 'SECRET local record')
    search, embedder = live(core)
    provider.is_local = False
    assert agent.answer_memory('SECRET?').context['items'] == []
    assert embedder.calls == []


def test_mixed_embedding_dimensions_cannot_mix_cached_spaces(core):
    _, _, episodes, claims, accept = core
    accept('project:first', 'Atlas Zuschuss eins.')
    search, embedder = live(core)
    search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    accept('project:second', 'Atlas Zuschuss zwei.')
    embedder.embed = lambda texts: [[1.0, 0.0] if text == 'Finanzierung?' else [1.0, 0.0, 0.0] for text in texts]
    results, metadata = search.search_context('Finanzierung?', claims, episodes.support_snapshot)
    assert results == []
    assert metadata['semantic_status'] == 'unavailable'
