"""Rejected prose must not hide a selected source in a multi-source answer."""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort, satzpruefung_modell, working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_satzantwort import Skript, nr, verlinkte_originale
from tests.test_satzpruefung_modell import Pruefer

FIRST = 'Die Vor-Ort-Abnahme in Werkhalle Epsilon ist für den 12. Mai um 09:00 Uhr eingeplant.'
UPDATE = ('Aktualisierung: Die Vor-Ort-Abnahme in Werkhalle Epsilon wird vom 12. Mai um 09:00 Uhr '
          'auf den 19. Mai um 14:30 Uhr verschoben. Der alte Termin ist ersetzt.')
QUESTION = 'Welche Termine nennen die erste Planung und die spätere Änderungsnotiz zur Epsilon-Abnahme jeweils?'
OLD_SENTENCE = 'Die erste Planung nennt den 12. Mai um 09:00 Uhr.'
NEW_SENTENCE = 'Die Abnahme in Werkhalle Epsilon wurde auf den 19. Mai um 14:30 Uhr verschoben.'
REJECTED_NEW = 'Die spätere Änderungsnotiz nennt den 19. Mai um 14:30 Uhr.'


@pytest.fixture
def sources(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    ids = []
    for title, body in [('Erste Planung Werkhalle Epsilon', FIRST), ('Terminänderung Werkhalle Epsilon', UPDATE)]:
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, title, body, Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
            [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='synthetic')
        ids.append(episode.id)
    monkeypatch.setattr(answers, 'now', lambda: datetime(2026, 10, 8, tzinfo=timezone.utc))
    yield episodes, claims, ids
    claims.close(); episodes.close()


def scripted(second=NEW_SENTENCE, extra=None):
    def response(user):
        rows = [{'text': OLD_SENTENCE, 'belege': [nr(user, 'Erste Planung')]},
                {'text': second, 'belege': [nr(user, 'Terminänderung')]}]
        if extra:
            rows.append({'text': extra, 'belege': [nr(user, 'Terminänderung')]})
        return {'status': 'antwort', 'saetze': rows}
    return Skript(response)


def prepare(sources, provider, **kwargs):
    episodes, claims, _ = sources
    return answers.prepare(QUESTION, episodes, claims, provider, saetze=True, **kwargs)


def assert_originals(answer, sources):
    episodes, claims, ids = sources
    text, links, status = answers.render(answer, episodes, claims)
    assert status == 'working_reports'
    original = verlinkte_originale(answer, episodes, links)
    assert FIRST in original and UPDATE in original
    if answer['satzantwort']['status'] in {'nichts', 'zitate'}:
        assert FIRST not in text and UPDATE not in text and 'nicht verlässlich beantworten' in text
    else:  # Stored legacy prose that fails revalidation keeps its explicit original fallback.
        assert FIRST in text and UPDATE in text
    assert set(ids) <= {link['episode_id'] for link in links}
    assert answers.satz_struktur(answer, episodes, claims) is None


def test_lexical_rejection_cannot_leave_only_old_planning_visible(sources):
    answer = prepare(sources, scripted(REJECTED_NEW))
    assert answer['satzantwort']['verworfen'] == 1
    assert answer['satzantwort']['status'] == 'zitate'
    assert_originals(answer, sources)


def test_model_rejection_cannot_hide_the_second_selected_source(sources):
    gate = satzpruefung_modell.tor('an', Pruefer({'19. Mai': '{"urteil":"nein"}'}))
    answer = prepare(sources, scripted(), pruefung=gate)
    assert answer['satzantwort']['pruefung']['verworfen'] == 1
    assert answer['satzantwort']['status'] == 'zitate'
    assert_originals(answer, sources)


def legacy_partial(sources, rejected=1):
    answer = prepare(sources, scripted())
    assert answer['satzantwort']['status'] == 'saetze'
    answer = json.loads(json.dumps(answer))
    # Old persisted answers contain all source refs but only surviving sentences.
    answer['satzantwort']['saetze'] = [row for row in answer['satzantwort']['saetze'] if row['roh'] == OLD_SENTENCE]
    assert len(answer['satzantwort']['saetze']) == 1
    answer['satzantwort']['verworfen'] = rejected
    return answer


def test_saved_partial_comparison_restores_originals_without_another_model_call(sources):
    answer = legacy_partial(sources)
    assert_originals(answer, sources)


@pytest.mark.parametrize('rejected', [0, 1])
def test_source_withdrawal_still_blocks_saved_partial_comparison(sources, rejected):
    answer = legacy_partial(sources, rejected)
    episodes, claims, ids = sources
    episodes.ignore(ids[1])
    text, links, status = answers.render(answer, episodes, claims)
    assert status == 'working_unavailable' and links == []
    assert FIRST not in text and UPDATE not in text
    assert answers.satz_struktur(answer, episodes, claims) is None


def test_complete_comparison_keeps_supported_prose(sources):
    answer = prepare(sources, scripted())
    episodes, claims, ids = sources
    assert answer['satzantwort']['status'] == 'saetze'
    text, links, status = answers.render(answer, episodes, claims)
    assert OLD_SENTENCE in text and NEW_SENTENCE in text
    assert set(ids) <= {link['episode_id'] for link in links}
    assert answers.satz_struktur(answer, episodes, claims) is not None


def test_rejection_without_losing_a_source_still_uses_complete_originals(sources):
    answer = prepare(sources, scripted(extra='Die Abnahme ist am 24. Dezember 2035.'))
    assert answer['satzantwort']['verworfen'] == 1
    assert answer['satzantwort']['status'] == 'zitate'
    episodes, claims, _ = sources
    text, links, _ = answers.render(answer, episodes, claims)
    original = verlinkte_originale(answer, episodes, links)
    assert FIRST in original and UPDATE in original and '2035' not in text
    assert FIRST not in text and UPDATE not in text


def test_unmentioned_selected_source_without_rejection_restores_both_originals(sources):
    def only_old(user):
        return {'status': 'antwort', 'saetze': [
            {'text': OLD_SENTENCE, 'belege': [nr(user, 'Erste Planung')]}]}
    answer = prepare(sources, Skript(only_old))
    assert answer['satzantwort']['verworfen'] == 0
    assert answer['satzantwort']['status'] == 'zitate'
    assert_originals(answer, sources)


def test_sentence_abstention_cannot_hide_already_selected_originals(sources):
    provider = Skript(lambda user: {'status': 'nichts_vorliegend', 'saetze': []})
    answer = prepare(sources, provider)
    assert len(answer['refs']) == 2
    assert_originals(answer, sources)


def test_saved_sentence_abstention_keeps_originals_without_a_model_call(sources):
    provider = Skript(lambda user: {'status': 'nichts_vorliegend', 'saetze': []})
    answer = json.loads(json.dumps(prepare(sources, provider)))
    episodes, claims, ids = sources
    before = len(provider.auswahlen) + len(provider.satzanfragen)
    reopened = answers.project_message({'role': 'assistant', 'content': 'old empty display',
        'metadata': {'context': {'working_answer': answer}}}, episodes, claims)
    original = verlinkte_originale(answer, episodes, reopened['metadata']['context']['source_links'])
    assert FIRST in original and UPDATE in original
    assert FIRST not in reopened['content'] and UPDATE not in reopened['content']
    assert set(ids) <= {ref['episode_id'] for ref in reopened['metadata']['context']['source_links']}
    assert len(provider.auswahlen) + len(provider.satzanfragen) == before


def test_saved_partial_comparison_without_rejection_restores_both_originals(sources):
    provider = scripted()
    answer = prepare(sources, provider)
    assert answer['satzantwort']['status'] == 'saetze'
    answer = json.loads(json.dumps(answer))
    # Legacy answers can silently omit a selected source without any rejected sentence.
    answer['satzantwort']['saetze'] = [row for row in answer['satzantwort']['saetze'] if row['roh'] == OLD_SENTENCE]
    assert answer['satzantwort']['verworfen'] == 0
    assert_originals(answer, sources)
    episodes, claims, ids = sources
    before = len(provider.auswahlen) + len(provider.satzanfragen)
    reopened = answers.project_message({'role': 'assistant', 'content': 'stored display',
        'metadata': {'context': {'working_answer': answer}}}, episodes, claims)
    assert FIRST in reopened['content'] and UPDATE in reopened['content']
    assert set(ids) <= {ref['episode_id'] for ref in reopened['metadata']['context']['source_links']}
    assert 'satzantwort' not in reopened['metadata']['context']
    assert len(provider.auswahlen) + len(provider.satzanfragen) == before


def test_only_actually_selected_original_is_required_in_prose(sources):
    episodes, claims, ids = sources
    def only_new(user):
        return {'status': 'antwort', 'saetze': [
            {'text': NEW_SENTENCE, 'belege': [nr(user, 'Terminänderung')]}]}
    provider = Skript(only_new, auswahl=lambda user: [
        row['id'] for row in user['sources'] if row['title'] == 'Terminänderung Werkhalle Epsilon'])
    answer = prepare(sources, provider)
    assert len(provider.auswahlen[0]['sources']) == 2  # Search also finds the old original.
    assert [ref['episode_id'] for ref in answer['refs']] == [ids[1]]
    assert answer['satzantwort']['status'] == 'saetze'
    text, links, _ = answers.render(answer, episodes, claims)
    assert NEW_SENTENCE in text
    assert [link['episode_id'] for link in links] == [ids[1]]


def test_nonselected_context_evidence_does_not_force_quote_mode_without_rejection():
    """Additional file context is allowed to inform prose, without requiring a sentence for each row."""
    selected = satzantwort.AntwortBeleg(1, {}, 'Quelle', 'selected', '', '', 'Die Abnahme ist am 19. Mai.', None)
    context = satzantwort.AntwortBeleg(2, {}, 'Projektkontext', 'context', '', '', 'Die Halle ist blau.', None)
    sentence = satzantwort.GeprueftSatz('', 'Die Abnahme ist am 19. Mai.', (1,), True)
    assert not satzantwort._quelle_fehlt([sentence], [selected, context], 0)


def test_multiple_evidence_sections_of_the_same_selected_original_count_once():
    first = satzantwort.AntwortBeleg(1, {}, 'Quelle', 'selected', '', '', 'Die Abnahme ist am 19. Mai.', None)
    second = satzantwort.AntwortBeleg(2, {}, 'Quelle', 'selected', '', '', 'Die Halle ist blau.', None)
    sentence = satzantwort.GeprueftSatz('', 'Die Abnahme ist am 19. Mai.', (1,), True)
    assert not satzantwort._quelle_fehlt([sentence], [first, second], 0)
