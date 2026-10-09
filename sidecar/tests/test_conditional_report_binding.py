"""Bedingte Berichte dürfen durch Formulierung oder alten Cache nicht unbedingte Zusagen werden."""
import copy
from datetime import datetime, timezone

import pytest

from icarus_memory import working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_satzantwort import Skript, nr

NOW = datetime(2026, 10, 9, 8, tzinfo=timezone.utc)
CASES = [
    ('Die Lieferung Orion erfolgt am 14. Oktober nach Freigabe.',
     'Die Lieferung Orion erfolgt am 14. Oktober.'),
    ('Die Lieferung Orion erfolgt am 14. Oktober unter der Voraussetzung, dass die Freigabe vorliegt.',
     'Die Lieferung Orion erfolgt am 14. Oktober.'),
    ('Die Lieferung Orion erfolgt am 14. Oktober vorbehaltlich der Freigabe.',
     'Die Lieferung Orion erfolgt am 14. Oktober.'),
    ('Vorausgesetzt, dass die Freigabe vorliegt, erfolgt die Lieferung Orion am 14. Oktober.',
     'Die Lieferung Orion erfolgt am 14. Oktober.'),
    ('Die Lieferung Orion erfolgt am 14. Oktober, sofern die Freigabe vorliegt.',
     'Die Lieferung Orion erfolgt am 14. Oktober.'),
    ('Wir liefern Orion am 14. Oktober, wenn die Freigabe vorliegt.',
     'Wir liefern Orion am 14. Oktober.'),
    ('Das Angebot Orion gilt bis 14. Oktober, falls die Freigabe vorliegt.',
     'Das Angebot Orion gilt bis 14. Oktober.'),
    ('Die Zahlung Orion wird bis zum 14. Oktober fällig, sobald die Abnahme abgeschlossen ist.',
     'Die Zahlung Orion wird bis zum 14. Oktober fällig.'),
]


@pytest.mark.parametrize('source,candidate', CASES)
def test_descriptive_condition_cannot_be_removed_at_sentence_gate(source, candidate):
    assert not satz_pruefen(Satz(candidate, ('1',)), {'1': Beleg('1', source, NOW)}).bestanden


@pytest.fixture
def memory(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    monkeypatch.setattr(answers, 'now', lambda: NOW)
    yield episodes, claims
    claims.close()
    episodes.close()


def recorded(memory, body):
    episodes, _ = memory
    source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Orion Original', body,
                               Provenance(SourceType.DOCUMENT), occurred_at=NOW)
    assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id),
        [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='synthetic')
    return source


def prepared(memory, text):
    return answers.prepare('Welche Angaben nennt die Quelle zu Orion?', *memory,
        Skript(lambda user: {'status': 'antwort', 'saetze': [
            {'text': text, 'belege': [nr(user, 'Orion Original')]}]}), saetze=True)


@pytest.mark.parametrize('source,candidate', CASES)
@pytest.mark.parametrize('phase', ['fresh', 'saved'])
def test_conditional_original_remains_visible_in_fresh_and_legacy_answer(memory, source, candidate, phase):
    episode = recorded(memory, source)
    if phase == 'fresh':
        answer = prepared(memory, candidate)
    else:
        answer = copy.deepcopy(prepared(memory, source))
        assert answer['satzantwort']['status'] == 'saetze'
        # Old persisted shape: same source binding, but a truncated generated sentence.
        answer['satzantwort']['saetze'][0]['roh'] = candidate
        answer['satzantwort']['saetze'][0]['text'] = candidate
    text, links, status = answers.render(answer, *memory)
    assert status == 'working_reports'
    assert source in text
    assert candidate not in text
    assert episode.id in {link['episode_id'] for link in links}
    assert answers.satz_struktur(answer, *memory) is None


@pytest.mark.parametrize('source,candidate', CASES)
def test_complete_conditional_original_can_still_answer(memory, source, candidate):
    recorded(memory, source)
    answer = prepared(memory, source)
    text, _, status = answers.render(answer, *memory)
    assert status == 'working_reports' and source in text
    assert answer['satzantwort']['status'] == 'saetze'
    assert answers.satz_struktur(answer, *memory) is not None


def test_condition_guard_does_not_restore_withdrawn_source(memory):
    source, _ = CASES[0]
    episode = recorded(memory, source)
    answer = prepared(memory, source)
    memory[0].ignore(episode.id)
    text, links, status = answers.render(answer, *memory)
    assert status == 'working_unavailable' and links == []
    assert source not in text


def test_unconditional_report_still_allows_existing_date_paraphrase():
    source = 'Die Lieferung Orion erfolgt am 14. Oktober 2026.'
    candidate = 'Die Lieferung Orion erfolgt am 14.10.2026.'
    assert satz_pruefen(Satz(candidate, ('1',)), {'1': Beleg('1', source, NOW)}).bestanden


def test_locative_vor_ort_does_not_prevent_date_paraphrase(memory):
    source = 'Die Lieferung Orion erfolgt vor Ort. Die Lieferung erfolgt am 14. Oktober 2026.'
    candidate = 'Die Lieferung erfolgt am 14.10.2026.'
    assert satz_pruefen(Satz(candidate, ('1',)), {'1': Beleg('1', source, NOW)}).bestanden
    recorded(memory, source)
    answer = prepared(memory, candidate)
    text, _, status = answers.render(answer, *memory)
    assert status == 'working_reports' and candidate in text
    assert answer['satzantwort']['status'] == 'saetze'


@pytest.mark.parametrize('source,candidate', CASES)
def test_model_can_select_complete_conditional_original_without_copying(memory, source, candidate):
    recorded(memory, source)
    provider = Skript(lambda user: {'status': 'antwort', 'originalstellen': [
        {'beleg': nr(user, 'Orion Original'), 'satz': 1}]})
    answer = answers.prepare('Welche Angaben nennt die Quelle zu Orion?', *memory, provider, saetze=True)
    text, _, status = answers.render(answer, *memory)
    assert status == 'working_reports' and source in text
    assert answer['satzantwort']['status'] == 'saetze'


@pytest.mark.parametrize('source', [
    'Vor allem die Lieferung Orion erfolgt am 14. Oktober 2026. Die Zahlung ist eingegangen.',
    'Die Lieferung Orion erfolgt am 14. Oktober 2026. Das prüfen wir vor allem.',
])
def test_function_words_are_not_nominal_conditions(memory, source):
    candidate = 'Die Lieferung Orion erfolgt am 14.10.2026.'
    assert satz_pruefen(Satz(candidate, ('1',)), {'1': Beleg('1', source, NOW)}).bestanden
    recorded(memory, source)
    answer = prepared(memory, candidate)
    text, _, status = answers.render(answer, *memory)
    assert status == 'working_reports' and candidate in text
    assert answer['satzantwort']['status'] == 'saetze'
