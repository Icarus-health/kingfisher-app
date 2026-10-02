"""A match built only from light-verb forms carries no relevance signal.

Reproduces the everyday-search-5 false positive ('Wo liegt die Zugangskarte?'
also returning an unrelated report note because both share the light verb
'liegt') and checks that the fix generalizes without over-suppressing
genuinely specific single-term matches, short/ambiguous queries, multi-source
retrievals, or experimental semantic hits. Uses the real Agent/ClaimStore/FTS
index end to end, never a substitute search; nothing here talks to a model or
the network.

An earlier version of this fix dropped any single-shared-term match once a
two-term match existed, regardless of which term was shared. That is wrong:
a single match on a specific noun ('zugangskarte') is solid evidence and must
survive next to a two-term match, while a single match on nothing but a light
verb ('liegt') is not — see
test_specific_single_term_match_survives_next_to_a_two_term_match below.
"""
from __future__ import annotations

import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.knowledge_search import HybridKnowledgeSearch
from icarus_memory.policy import Policy

from tests.test_context import CapturingProvider, _knowledge_agent


class _ConstantEmbedder:
    """Deterministic stand-in: identical vectors for any text, so every
    candidate trivially passes the cosine threshold. No network, no model."""
    is_local = True
    model_key = 'synthetic-model:immutable-weights'

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_shared_generic_word_does_not_pull_in_an_unrelated_match(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    relevant, _ = accept('Die Zugangskarte liegt im Schrank neben dem Empfang.')
    noise, _ = accept('Der Bericht ist als Entwurf gespeichert. Eine Freigabe liegt nicht vor.')
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert {item['assertion_id'] for item in turn.context['items']} == {'claim:' + relevant.id}
    delivered = str(provider.messages[-1])
    assert relevant.statement in delivered
    assert noise.statement not in delivered


def test_specific_single_term_match_survives_next_to_a_two_term_match(tmp_path):
    """A single-term match on a specific noun is not weak evidence just
    because some other candidate happens to share more terms. Dropping it
    would have been the too-aggressive behavior of an earlier version of
    this fix, which keyed off overlap size instead of term specificity."""
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    single_term, _ = accept('Die Zugangskarte befindet sich im Tresor.')
    two_term, _ = accept('Eine weitere Zugangskarte liegt im Schrank.')
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert {item['assertion_id'] for item in turn.context['items']} == {
        'claim:' + single_term.id, 'claim:' + two_term.id}
    delivered = str(provider.messages[-1])
    assert single_term.statement in delivered
    assert two_term.statement in delivered


@pytest.mark.parametrize(('query', 'first_text', 'second_text'), [
    ('Wo steht die Liege?', 'Die Liege befindet sich im Behandlungsraum.',
     'Eine zweite Liege steht im Keller.'),
    ('Wo stehen die Liegen?', 'Die Liegen befinden sich im Behandlungsraum.',
     'Weitere Liegen stehen im Keller.'),
])
def test_furniture_nouns_are_not_mistaken_for_light_verbs(tmp_path, query, first_text, second_text):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept(first_text)
    second, _ = accept(second_text)
    turn = agent.send(query)
    assert {item['assertion_id'] for item in turn.context['items']} == {
        'claim:' + first.id, 'claim:' + second.id}
    assert first.statement in str(provider.messages[-1])
    assert second.statement in str(provider.messages[-1])


def test_dependent_match_on_withdrawn_foundation_excluded_first_still_delivered(tmp_path):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    foundation, foundation_source = accept('Die Ausgabe der Zugangskarten wurde geprüft.')
    dependent, _ = accept('Eine weitere Zugangskarte liegt im Tresor.', [foundation.id])
    first, _ = accept('Die Zugangskarte befindet sich im Schrank.')
    episodes.ignore(foundation_source.id)
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert {item['assertion_id'] for item in turn.context['items']} == {'claim:' + first.id}
    assert first.statement in str(provider.messages[-1])
    assert dependent.statement not in str(provider.messages[-1])


def test_second_match_over_row_budget_first_valid_match_still_delivered(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Die Zugangskarte befindet sich im Schrank.')
    oversized, _ = accept('Eine weitere Zugangskarte liegt in einem Vermerk: ' + 'X' * 8300)
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert {item['assertion_id'] for item in turn.context['items']} == {'claim:' + first.id}
    assert turn.context['knowledge_retrieval']['payload_omitted'] == 1
    assert first.statement in str(provider.messages[-1])


def test_semantic_match_is_not_dropped_by_the_light_verb_lexical_rule(tmp_path):
    """A candidate whose only lexical overlap is the light verb 'liegt', but
    which is independently backed by the (synthetic) semantic search, must
    survive: the lexical light-verb rule and the semantic threshold are two
    separate gates, and passing the semantic one is enough on its own."""
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    specific, _ = accept('Die Zugangskarte liegt im Schrank.')
    semantic_only, _ = accept('Der Schlüssel liegt in der Lade.')
    search = HybridKnowledgeSearch.prepare(
        agent._knowledge, episodes.support_snapshot, [semantic_only.id], _ConstantEmbedder())
    agent._knowledge_search = search
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert turn.context['knowledge_retrieval']['ranking_mode'] == 'hybrid'
    assert {item['assertion_id'] for item in turn.context['items']} == {
        'claim:' + specific.id, 'claim:' + semantic_only.id}
    assert semantic_only.statement in str(provider.messages[-1])


def test_two_genuinely_matching_sources_both_survive_the_noise_filter(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Die Zugangskarte liegt im Schrank neben dem Empfang.')
    second, _ = accept('Eine zweite Zugangskarte liegt im Tresor am Empfang.')
    noise, _ = accept('Der Bericht ist als Entwurf gespeichert. Eine Freigabe liegt nicht vor.')
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert {item['assertion_id'] for item in turn.context['items']} == {
        'claim:' + first.id, 'claim:' + second.id}
    assert noise.statement not in str(provider.messages[-1])


def test_short_ambiguous_query_does_not_lose_every_hit(tmp_path):
    """Both notes match only on the query's one term; nothing distinguishes
    between them, so the filter must not remove either (no term is more
    generic than the query itself here)."""
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Der Bericht liegt im Ordner.')
    second, _ = accept('Ein weiterer Bericht liegt beim Sekretariat.')
    turn = agent.send('Bericht?')
    assert {item['assertion_id'] for item in turn.context['items']} == {
        'claim:' + first.id, 'claim:' + second.id}


def test_same_name_entries_keep_distinct_identity_after_filtering(tmp_path):
    """The noise filter must never be the thing that merges two same-name
    entries: whichever of them the query pulls in, each keeps its own
    subject_ref rather than collapsing onto a single shared identity."""
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    purchasing, _ = accept('Alex Winter im Einkauf ist unter einkauf@example.invalid erreichbar.')
    school, _ = accept('Alex Winter an der Schule ist unter schule@example.invalid erreichbar.')
    assert purchasing.subject_ref != school.subject_ref

    ambiguous = agent.send('Welche Adresse gehört zu Alex Winter?')
    ambiguous_ids = {item['assertion_id'] for item in ambiguous.context['items']}
    assert ambiguous_ids == {'claim:' + purchasing.id, 'claim:' + school.id}
    refs = {item['subject_ref'] for item in ambiguous.context['items']}
    assert refs == {purchasing.subject_ref, school.subject_ref}

    # 'Einkauf' still leaves school with a two-term match ('alex', 'winter'),
    # so both remain candidates here; the noise filter's job is dropping
    # single-term noise, not full name disambiguation. What matters for this
    # test is that neither entry's identity is affected by the other.
    specific = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    specific_items = {item['assertion_id']: item['subject_ref'] for item in specific.context['items']}
    assert specific_items['claim:' + purchasing.id] == purchasing.subject_ref
    assert specific_items['claim:' + school.id] == school.subject_ref


def test_withdrawn_source_stays_excluded_after_relevance_filtering(tmp_path):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    relevant, _ = accept('Die Zugangskarte liegt im Schrank neben dem Empfang.')
    withdrawn, source = accept('Eine widerrufene Zugangskarte liegt im Safe. SECRET_WITHDRAWN')
    episodes.ignore(source.id)
    turn = agent.send('Wo liegt die Zugangskarte?')
    assert {item['assertion_id'] for item in turn.context['items']} == {'claim:' + relevant.id}
    assert 'SECRET_WITHDRAWN' not in str(provider.messages[-1])


def test_relevance_filtering_works_after_reopening_existing_index(tmp_path):
    agent, _, episodes, accept = _knowledge_agent(tmp_path)
    relevant, _ = accept('Die Zugangskarte liegt im Schrank neben dem Empfang.')
    accept('Der Bericht ist als Entwurf gespeichert. Eine Freigabe liegt nicht vor.')

    reopened_claims = ClaimStore(agent._knowledge._path)
    reopened_episodes = EpisodeStore(episodes._path)
    try:
        reopened_provider = CapturingProvider()
        reopened_agent = Agent(
            store=SelfModelStore(MemoryBackend(), subject_id='synthetic'),
            policy=Policy(), audit=AuditLog(tmp_path / 'audit-reopened.sqlite3'),
            tools={}, provider=reopened_provider,
            knowledge=reopened_claims, episodes=reopened_episodes,
        )
        turn = reopened_agent.send('Wo liegt die Zugangskarte?')
        assert {item['assertion_id'] for item in turn.context['items']} == {'claim:' + relevant.id}
    finally:
        reopened_claims.close()
        reopened_episodes.close()
