"""German noun inflections are candidates, never aliases for canonical identity."""
import pytest
from tests.test_context import _knowledge_agent
from tests.test_claim_index import insert_claims, variants


@pytest.mark.parametrize(('stored','question'), [
    ('Atlasberichte liegen vor.', 'Atlasbericht?'),
    ('Der Atlasbericht liegt vor.', 'Atlasberichten?'),
    ('Server bleibt offline.', 'Servers?'),
    ('Verträge bleiben intern.', 'Vertrag?'),
    ('Entwurf bleibt intern.', 'Entwürfen?'),
    ('Rechnung liegt vor.', 'Rechnungen?'),
    ('Dokumente liegen vor.', 'Dokuments?'),
    ('Dateien liegen vor.', 'Datei?'),
    ('Aufgaben bleiben offen.', 'Aufgabe?'),
])
def test_noun_forms_reach_real_local_provider_with_original_source(tmp_path, stored, question):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept(stored)
    turn = agent.send(question)
    assert [i['assertion_id'] for i in turn.context['items']] == ['claim:' + claim.id]
    assert stored in str(provider.messages[-1])
    assert 'Wortform' in turn.context['items'][0]['reason']


@pytest.mark.parametrize(('stored','question'), [
    ('Martine', 'Martin'), ('Muller', 'Müller'), ('Anders', 'Ander'),
    ('Atlasberichte', 'Lindebericht'), ('Berichtsentwurf', 'Bericht'),
    ('Vertragsbruch', 'Vertrag'), ('Sommer', 'Somme'),
])
def test_names_accents_and_different_compounds_are_not_generic_stems(tmp_path, stored, question):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    accept(stored)
    assert agent.send(question).context['items'] == []
    assert stored not in str(provider.messages[-1])


@pytest.mark.parametrize(('literal', 'expanded'), [('Atlasbericht', 'Atlasberichte'), ('Bericht', 'Report')])
def test_exact_candidate_survives_many_newer_inflected_candidates(tmp_path, literal, expanded):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept(literal)
    insert_claims(agent._knowledge, variants(claim, 200, expanded))
    rows, meta = agent._knowledge.search_context(literal, limit=1)
    assert [c.id for c in rows] == [claim.id]
    assert meta['candidates_truncated'] and meta['truncated']
    turn = agent.send(literal)
    assert turn.context['items'][0]['assertion_id'] == 'claim:' + claim.id


@pytest.mark.parametrize('change', ['ignore', 'retract'])
def test_inflected_query_cannot_restore_withdrawn_original(tmp_path, change):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    claim, source = accept('Atlasberichte SECRET_WITHDRAWN')
    assert agent.send('Atlasbericht').context['items']
    if change == 'ignore': episodes.ignore(source.id)
    else: agent._knowledge.retract(claim.id, reason='synthetic withdrawal')
    turn = agent.send('Atlasbericht')
    assert turn.context['items'] == []
    assert 'SECRET_WITHDRAWN' not in str(provider.messages[-1])


def test_query_expansion_keeps_original_term_and_candidate_budgets(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    accept('zzatlasberichte')
    words = ['aa' + chr(97 + i // 26) + chr(97 + i % 26) + 'bericht' for i in range(80)]
    rows, meta = agent._knowledge.search_context(' '.join(words) + ' zzatlasbericht')
    assert not rows
    assert meta['query_terms_used'] == 64 and meta['query_terms_total'] == 81
    assert meta['word_forms_used'] == 256 and meta['query_truncated'] and meta['truncated']


def test_existing_index_and_canonical_bytes_work_after_reopen(tmp_path):
    from icarus_memory.claims import ClaimStore
    agent, _, _, accept = _knowledge_agent(tmp_path)
    claim, _ = accept('Atlasberichte liegen vor.')
    before = agent._knowledge._conn.execute('SELECT document FROM knowledge_claims WHERE id=?', (claim.id,)).fetchone()[0]
    other = ClaimStore(agent._knowledge._path)
    try:
        assert [c.id for c in other.search_context('Atlasbericht')[0]] == [claim.id]
        assert other._conn.execute('PRAGMA user_version').fetchone()[0] == 6
        assert other._conn.execute('SELECT document FROM knowledge_claims WHERE id=?', (claim.id,)).fetchone()[0] == before
    finally: other.close()


@pytest.mark.parametrize(('literal', 'expanded'), [('Atlasbericht', 'Atlasberichte'), ('Bericht', 'Report')])
def test_alternatives_cannot_exhaust_exact_claim_dependency_validation(tmp_path, monkeypatch, literal, expanded):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    foundation, source = accept('Freigabegrundlage')
    exact, _ = accept(literal, [foundation.id])
    insert_claims(agent._knowledge, variants(exact, 200, expanded))
    loads = []
    original = agent._knowledge.get
    def counted(identifier):
        loads.append(identifier)
        return original(identifier)
    monkeypatch.setattr(agent._knowledge, 'get', counted)
    turn = agent.send(literal)
    assert turn.context['items'][0]['assertion_id'] == 'claim:' + exact.id
    # At most 128 ranking reads plus 128 canonical chain-validation reads.
    assert len(loads) <= 256
    episodes.ignore(source.id)
    assert agent.send(literal).context['items'] == []
    assert 'Freigabegrundlage' not in str(provider.messages[-1])
