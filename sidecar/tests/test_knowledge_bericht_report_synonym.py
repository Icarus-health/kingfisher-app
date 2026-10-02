"""'Bericht' <-> 'Report' is an explicit, closed query-time noun synonym.

Reproduces the reported failures independently reconstructed on main
(673c8f6): a question about 'Report' found nothing for a claim that only
says 'Bericht', and vice versa, even though both candidate search
(icarus_memory.claim_index.search) and the real Agent/ClaimStore/FTS
context-selection path were exercised. Checks the fix through the actual
delivered provider context (turn.context['items'] + provider.messages),
never a bare helper-function result, and that it does not widen into
compounds ('Reisebericht', 'Geschäftsbericht'), unrelated words
('Reporter') or the existing pure noun-inflection rules.
"""
from __future__ import annotations

import pytest

from tests.test_context import _knowledge_agent


def _delivered_ids(turn):
    return {item['assertion_id'] for item in turn.context['items']}


def test_report_query_matches_bericht_only_source_via_candidate_search_and_context(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept('Der Bericht ist ein Entwurf ohne Freigabe.')
    # Candidate search itself must already recognize the synonym, not just
    # the later context-selection step -- otherwise the claim would never
    # reach agent.send() as a candidate at all.
    found, _meta = agent._knowledge.search_context('Was steht im Report?')
    assert [row.id for row in found] == [claim.id]
    turn = agent.send('Was steht im Report?')
    assert _delivered_ids(turn) == {'claim:' + claim.id}
    assert claim.statement in str(provider.messages[-1])
    assert turn.context['items'][0]['reason'] == 'Passt zum Gespräch (Synonym): report'


def test_bericht_query_matches_report_only_source(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept('Der Report ist ein Entwurf ohne Freigabe.')
    turn = agent.send('Was steht im Bericht?')
    assert _delivered_ids(turn) == {'claim:' + claim.id}
    assert claim.statement in str(provider.messages[-1])
    assert turn.context['items'][0]['reason'] == 'Passt zum Gespräch (Synonym): bericht'


@pytest.mark.parametrize(('stored', 'question'), [
    ('Die Berichte sind fertig.', 'Was steht in den Reports?'),
    ('Die Reports sind fertig.', 'Was steht in den Berichten?'),
    ('Der Berichts-Entwurf wartet.', 'Gibt es einen Reports-Hinweis?'),
])
def test_plural_and_genitive_forms_cross_the_synonym_in_both_directions(tmp_path, stored, question):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept(stored)
    turn = agent.send(question)
    assert _delivered_ids(turn) == {'claim:' + claim.id}
    assert stored in str(provider.messages[-1])


def test_literal_match_and_synonym_match_both_survive_for_the_same_query(tmp_path):
    """Neither side crowds out the other when a query pulls in one claim
    matched literally and another matched only through the synonym."""
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    literal, _ = accept('Der Bericht liegt beim Empfang.')
    synonym, _ = accept('Der Report liegt im Archiv.')
    turn = agent.send('Wo finde ich den Bericht?')
    ids = _delivered_ids(turn)
    assert ids == {'claim:' + literal.id, 'claim:' + synonym.id}
    delivered = str(provider.messages[-1])
    assert literal.statement in delivered
    assert synonym.statement in delivered
    reasons = {item['assertion_id']: item['reason'] for item in turn.context['items']}
    assert '(Synonym)' not in reasons['claim:' + literal.id]
    assert '(Synonym)' in reasons['claim:' + synonym.id]


def test_foreign_topic_is_not_pulled_in_by_the_synonym(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    accept('Die Rechnung wurde bezahlt.')
    turn = agent.send('Was steht im Report?')
    assert turn.context['items'] == []


@pytest.mark.parametrize('stored', [
    'Der Reisebericht ist fertig.',
    'Der Geschäftsbericht liegt vor.',
])
def test_compound_bericht_heads_are_not_aliased_to_report(tmp_path, stored):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    accept(stored)
    turn = agent.send('Was steht im Report?')
    assert turn.context['items'] == []


def test_reporter_is_not_aliased_to_bericht_or_report_in_either_direction(tmp_path):
    # Two independent conversations: a shared Agent's history retains a
    # previously delivered claim across turns, which would otherwise be
    # indistinguishable from an actual synonym leak here.
    agent, provider, _, accept = _knowledge_agent(tmp_path / 'bericht-query')
    reporter, _ = accept('Der Reporter wartet vor der Tür.')
    bericht, _ = accept('Der Bericht liegt vor.')
    turn_for_bericht_query = agent.send('Wo ist der Bericht?')
    assert _delivered_ids(turn_for_bericht_query) == {'claim:' + bericht.id}

    agent2, provider2, _, accept2 = _knowledge_agent(tmp_path / 'reporter-query')
    reporter2, _ = accept2('Der Reporter wartet vor der Tür.')
    accept2('Der Bericht liegt vor.')
    turn_for_reporter_query = agent2.send('Wo ist der Reporter?')
    assert _delivered_ids(turn_for_reporter_query) == {'claim:' + reporter2.id}


def test_synonym_rule_does_not_widen_unrelated_existing_noun_form_matches(tmp_path):
    """A query about an unrelated existing NOUN_FORMS_V1 pair (Vertrag) must
    not accidentally also pull in a Bericht/Report claim, and vice versa."""
    # Two independent conversations, for the same history reason as above.
    agent, provider, _, accept = _knowledge_agent(tmp_path / 'vertrag-query')
    vertrag, _ = accept('Der Vertrag wurde unterschrieben.')
    accept('Der Bericht liegt vor.')
    vertrag_turn = agent.send('Was sagt der Vertrag?')
    assert _delivered_ids(vertrag_turn) == {'claim:' + vertrag.id}

    agent2, provider2, _, accept2 = _knowledge_agent(tmp_path / 'report-query')
    accept2('Der Vertrag wurde unterschrieben.')
    bericht, _ = accept2('Der Bericht liegt vor.')
    bericht_turn = agent2.send('Was steht im Report?')
    assert _delivered_ids(bericht_turn) == {'claim:' + bericht.id}


@pytest.mark.parametrize('change', ['ignore', 'retract'])
def test_source_matched_only_via_synonym_stays_excluded_once_withdrawn(tmp_path, change):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept('Der Bericht ist ein Entwurf ohne Freigabe. SECRET_WITHDRAWN')
    assert agent.send('Was steht im Report?').context['items']
    if change == 'ignore':
        episodes.ignore(source.id)
    else:
        agent._knowledge.retract(claim.id, reason='synthetic withdrawal')
    turn = agent.send('Was steht im Report?')
    assert turn.context['items'] == []
    assert 'SECRET_WITHDRAWN' not in str(provider.messages[-1])


def test_dependent_synonym_match_excluded_when_its_foundation_is_withdrawn(tmp_path):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    foundation, foundation_source = accept('Die Berichtsfreigabe wurde geprüft.')
    dependent, _ = accept('Der Report ist bestätigt.', [foundation.id])
    direct, _ = accept('Der Bericht liegt zur Ansicht bereit.')
    episodes.ignore(foundation_source.id)
    turn = agent.send('Was steht im Bericht?')
    ids = _delivered_ids(turn)
    assert 'claim:' + dependent.id not in ids
    assert ids == {'claim:' + direct.id}
    assert 'Berichtsfreigabe' not in str(provider.messages[-1])


@pytest.mark.parametrize(('question', 'stored', 'word_forms', 'synonyms'), [
    ('Bericht', 'Report', 0, 1),
    ('Bericht', 'Berichte', 1, 0),
    ('Bericht Vertrag', 'Reports Verträge', 1, 1),
])
def test_search_metadata_distinguishes_expansion_kinds(tmp_path, question, stored, word_forms, synonyms):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept(stored)
    found, meta = agent._knowledge.search_context(question)
    assert [row.id for row in found] == [claim.id]
    assert meta['word_form_candidates'] == word_forms
    assert meta['synonym_candidates'] == synonyms
    assert meta['word_forms_used'] == (8 if 'Vertrag' in question else 4)
    assert meta['synonyms_used'] == 2
    assert meta['synonym_version'] == 1


def test_oversized_synonym_candidate_does_not_hide_valid_source(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    normal, _ = accept('Der Bericht ist ein Entwurf ohne Freigabe.')
    huge, _ = accept('Ein weiterer Bericht: ' + 'X' * 8300)
    turn = agent.send('Report')
    assert _delivered_ids(turn) == {'claim:' + normal.id}
    assert normal.statement in str(provider.messages[-1])
    assert huge.statement not in str(provider.messages[-1])
    assert turn.context['knowledge_retrieval']['payload_omitted'] == 1


def test_synonym_metadata_excludes_truncation_lookahead(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    accept('Report zur Prüfung')
    accept('Reports zur Wartung')
    found, meta = agent._knowledge.search_context('Bericht', limit=1)
    assert len(found) == 1
    assert meta['candidates_truncated'] is True
    assert meta['synonym_candidates'] == 1
    assert meta['word_form_candidates'] == 0
