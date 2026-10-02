"""Broader word candidates must preserve evidence, bounds and old databases."""
import hashlib
from contextlib import closing

from icarus_memory import EpisodeStore
from icarus_memory.working_memory_store import WorkingMemoryStore
from .test_working_memory_store import source
from .test_context_identity import core


def remember(episodes, text, **kwargs):
    episode = source(episodes, text, **kwargs)
    memory = WorkingMemoryStore(episodes)
    assert memory.commit(episodes.support_snapshot(episode.id),
        [{'start': 0, 'end': len(text), 'kind': 'conditional'}], model='synthetic')
    return episode


def ids(memory, query, **kwargs):
    return [ref['episode_id'] for ref in memory.search(query, **kwargs)['refs']]


def test_head_words_find_compounds_in_both_required_sources(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.db')) as episodes:
        first = remember(episodes, 'Der Prüftermin ist nur nach schriftlicher Freigabe verbindlich.')
        second = remember(episodes, 'Der Keramikversand darf erst nach drei gegengezeichneten Messwerten erfolgen.')
        memory = WorkingMemoryStore(episodes)
        assert set(ids(memory, 'Was muss vor Termin und Versand noch passieren?')) == {first.id, second.id}
        assert ids(memory, 'Termine') == [first.id]
        assert ids(memory, 'Versand') == [second.id]


def test_literal_match_ranks_before_compound_candidate_and_bounds_are_visible(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.db')) as episodes:
        compound = remember(episodes, 'Der Liefertermin bleibt offen.')
        exact = remember(episodes, 'Der Termin bleibt offen.')
        memory = WorkingMemoryStore(episodes)
        assert ids(memory, 'Termin') == [exact.id, compound.id]
        assert ids(memory, 'Termin', limit=1) == [exact.id]
        assert memory.search('Termin', limit=1)['truncated'] is True


def test_compound_suffix_is_not_an_identity_alias_or_general_substring(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.db')) as episodes:
        remember(episodes, 'Reporter und Terminologie haben hier keine Frist.')
        remember(episodes, 'Es fehlen vier Pakete.', title='Bergmann')
        memory = WorkingMemoryStore(episodes)
        assert ids(memory, 'Report') == []
        assert ids(memory, 'Termin') == []
        assert ids(memory, 'Anna') == []
        assert ids(memory, 'man') == []


def test_compound_search_revalidates_withdrawal_and_detects_new_candidates(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.db')) as episodes:
        first = remember(episodes, 'Der Liefertermin ist offen.')
        memory = WorkingMemoryStore(episodes)
        before = memory.candidate_signature('Termin')
        second = remember(episodes, 'Der Prüftermin ist abgesagt.')
        assert before != memory.candidate_signature('Termin')
        episodes.ignore(first.id)
        assert ids(memory, 'Termin') == [second.id]
        memory.dismiss(second.id)
        assert ids(memory, 'Termin') == []


def test_compound_lookup_reaches_old_source_beyond_recent_inventory(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.db')) as episodes:
        first = remember(episodes, 'Der Beratungstermin bleibt offen.')
        for index in range(510):
            remember(episodes, f'Allgemeine Nachricht Nummer {index}.')
        assert ids(WorkingMemoryStore(episodes), 'Termin') == [first.id]


def test_suffix_expansion_is_bounded_and_does_not_index_short_person_fragments():
    from icarus_memory.working_memory_words import candidate_words, query_words
    assert candidate_words('Johanna Anna 123456789') == set()
    assert candidate_words('X' * 65) == set()
    words = candidate_words('Abc' + 'd' * 61)
    assert len(words) <= 19
    assert query_words({'mann', 'anna', 'x' * 25, '123456'}) == set()


def test_ignored_literal_rows_do_not_consume_compound_search_budget(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.working_memory_store.SEARCH_BUDGET', 3)
    with closing(EpisodeStore(tmp_path / 'episodes.db')) as episodes:
        for index in range(3):
            retired = remember(episodes, f'Der Termin {index} ist offen.')
            episodes.ignore(retired.id)
        active = remember(episodes, 'Der Liefertermin ist bedingt.')
        memory = WorkingMemoryStore(episodes)
        assert ids(memory, 'Termin') == [active.id]
        signature = memory.candidate_signature('Termin')
        retired = remember(episodes, 'Ein weiterer Termin ist abgesagt.')
        episodes.ignore(retired.id)
        assert memory.candidate_signature('Termin') == signature


def test_old_database_gets_compound_candidates_without_model_or_source_changes(tmp_path, monkeypatch):
    from icarus_memory import episodes as module
    from icarus_memory.lexical import terms_v1

    path = tmp_path / 'episodes.db'
    # Stand vor Migration 8 nachbilden: gespeicherte Schlüssel nur für wörtliche Begriffe.
    from icarus_memory.working_memory_store import hex_key
    from tests.working_memory_legacy import downgrade_terms
    with closing(EpisodeStore(path)) as episodes:
        original = remember(episodes, 'Der Prüftermin ist erst nach Freigabe verbindlich.')
        saved = episodes.get(original.id).to_dict()
        old_ref = WorkingMemoryStore(episodes).search('Prüftermin')['refs'][0]
        literals = {hex_key(hashlib.sha256(term.encode()).hexdigest())
                    for term in terms_v1(original.title + ' ' + original.body)}
        with episodes.transaction():
            rows = episodes._conn.execute('SELECT term,item FROM working_memory_terms').fetchall()
            for row in rows:
                if row['term'] not in literals:
                    episodes._conn.execute('DELETE FROM working_memory_terms WHERE term=? AND item=?', tuple(row))
        assert ids(WorkingMemoryStore(episodes), 'Termin') == []
        downgrade_terms(episodes._conn, 7)
    with closing(EpisodeStore(path)) as reopened:
        memory = WorkingMemoryStore(reopened)
        assert ids(memory, 'Termin') == [original.id]
        assert memory.pending() == []
        assert reopened.get(original.id).to_dict() == saved
        assert memory.resolve(old_ref) is not None
        assert all(type(row[0]) is int for row in reopened._conn.execute('SELECT term FROM working_memory_terms'))


def test_normal_question_uses_both_compound_sources_and_full_conditions(core, tmp_path, monkeypatch):
    from .test_source_answers_http import _api, _ask, _conversation, _upload
    from .test_working_memory_flow import classifier, run_working
    from .test_conversation_retraction import _close_app
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    texts = [
        'Der Prüftermin ist nur nach schriftlicher Freigabe verbindlich.',
        'Der Keramikversand darf erst nach drei gegengezeichneten Messwerten erfolgen.',
    ]
    try:
        sources = {_upload(client, body) for body in texts}
        run_working(app)
        answer = _ask(client, _conversation(client), 'Was muss vor Termin und Versand noch passieren?')
        assert all(body in answer['content'] for body in texts)
        context = answer['metadata']['context']
        assert context['answer_contract']['status'] == 'working_reports'
        assert {link['episode_id'] for link in context['source_links']} == sources
    finally:
        client.close()
        _close_app(app)
