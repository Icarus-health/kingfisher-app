"""Rejected prose must not hide a selected source in a multi-source answer."""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort, satzpruefung_modell, working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_satzantwort import Skript, nr
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


def legacy_partial(sources):
    answer = prepare(sources, scripted())
    assert answer['satzantwort']['status'] == 'saetze'
    answer = json.loads(json.dumps(answer))
    # Old persisted answers contain all source refs but only surviving sentences.
    answer['satzantwort']['saetze'] = [row for row in answer['satzantwort']['saetze'] if row['roh'] == OLD_SENTENCE]
    assert len(answer['satzantwort']['saetze']) == 1
    answer['satzantwort']['verworfen'] = 1
    return answer


def test_saved_partial_comparison_restores_originals_without_another_model_call(sources):
    answer = legacy_partial(sources)
    assert_originals(answer, sources)


def test_source_withdrawal_still_blocks_saved_partial_comparison(sources):
    answer = legacy_partial(sources)
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


def test_rejection_without_losing_a_source_keeps_supported_prose(sources):
    answer = prepare(sources, scripted(extra='Die Abnahme ist am 24. Dezember 2035.'))
    assert answer['satzantwort']['verworfen'] == 1
    assert answer['satzantwort']['status'] == 'saetze'
    episodes, claims, _ = sources
    text, _, _ = answers.render(answer, episodes, claims)
    assert OLD_SENTENCE in text and NEW_SENTENCE in text and '2035' not in text


def test_unmentioned_source_without_rejection_does_not_change_existing_prose_policy(sources):
    def only_old(user):
        return {'status': 'antwort', 'saetze': [
            {'text': OLD_SENTENCE, 'belege': [nr(user, 'Erste Planung')]}]}
    answer = prepare(sources, Skript(only_old))
    assert answer['satzantwort']['verworfen'] == 0
    assert answer['satzantwort']['status'] == 'saetze'
