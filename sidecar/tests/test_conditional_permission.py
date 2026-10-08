"""A conditional permission is neither an unconditional permission nor a completed event."""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import satzpruefung_modell, working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_satzantwort import Skript, nr
from tests.test_satzpruefung_modell import Pruefer

RULE = 'Bei M-731 darf Material erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden.'
ABSENCE = 'Die Freigabe liegt noch nicht vor.'
SOURCE = RULE + ' ' + ABSENCE
PARAPHRASE = 'Material aus M-731 darf erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden.'


def check(sentence, source=SOURCE, other=None):
    sources = {'1': Beleg('1', source)}
    if other:
        sources['2'] = Beleg('2', other)
    return satz_pruefen(Satz(sentence, tuple(sources)), sources)


def test_literal_permission_does_not_assert_that_approval_exists():
    assert check(RULE).bestanden


@pytest.mark.parametrize('sentence', [
    'Material aus M-731 darf versandt werden.',
    'Material aus M-731 wurde versandt.',
    'Material aus M-731 ist versandt worden.',
    'Die Lagerleitung darf Material aus M-731 verschicken.',
    'Die Lagerleitung kann Material versenden.',
    'Material darf raus.',
    'Material ist raus.',
    'Es darf raus.',
    'Es ist raus.',
    'Material aus M-731 darf nach Freigabe versandt werden.',
    'Bei M-731 darf Material erst nach Freigabe durch die Lagerleitung versandt werden.',
    'Bei M-731 darf Material erst nach schriftlicher Freigabe versandt werden.',
    'Bei M-731 darf Material vor schriftlicher Freigabe durch die Lagerleitung versandt werden.',
    'Bei M-731 darf Material ohne schriftliche Freigabe durch die Lagerleitung versandt werden.',
    'Bei M-713 darf Material erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden.',
    'Die Freigabe liegt vor.',
])
def test_condition_cannot_be_removed_reversed_or_turned_into_a_completed_event(sentence):
    assert not check(sentence).bestanden


def test_no_negative_status_is_needed_to_protect_a_conditional_rule():
    assert not check('Material aus M-731 wurde versandt.', RULE).bestanden
    assert not check('Material aus M-731 darf versandt werden.', RULE).bestanden


def test_when_clause_is_preserved_as_one_rule():
    source = 'Bei M-731 darf Material erst versandt werden, wenn die schriftliche Freigabe vorliegt.'
    assert check(source, source).bestanden
    assert not check('Bei M-731 darf Material versandt werden.', source).bestanden
    assert not check('Bei M-731 wurde Material versandt.', source).bestanden


def test_additional_condition_is_not_silently_dropped():
    source = RULE[:-1] + ', wenn die Abnahme bestätigt ist.'
    assert not check(RULE, source).bestanden


@pytest.mark.parametrize('modal', ['dürfen', 'duerfen'])
def test_plural_permission_is_also_conditional(modal):
    source = f'Pakete {modal} erst nach Freigabe versandt werden.'
    assert check(source, source).bestanden
    assert not check(f'Pakete {modal} versandt werden.', source).bestanden


@pytest.mark.parametrize(('subject', 'changed'), [('Masse', 'Maße'), ('Lager', 'Läger')])
def test_literal_comparison_preserves_distinct_lexical_characters(subject, changed):
    source = f'Die {subject} darf erst nach Freigabe versandt werden.'
    assert not check(f'Die {changed} darf erst nach Freigabe versandt werden.', source).bestanden


def test_explicit_completed_event_is_not_inferred_from_the_rule():
    event = 'Material aus M-731 wurde versandt.'
    assert check(event, RULE + ' ' + event).bestanden


def test_full_rule_cannot_hide_a_separate_prohibition():
    assert not check(RULE, SOURCE + ' Material darf nicht versandt werden.').bestanden


def test_availability_exception_never_crosses_source_boundaries():
    assert not check(RULE, RULE, ABSENCE).bestanden


def test_absence_statement_itself_still_passes():
    assert check(ABSENCE).bestanden


@pytest.fixture
def memory(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Versandregel M-731', SOURCE,
                                Provenance(SourceType.DOCUMENT))
    assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
        [{'start': 0, 'end': len(SOURCE), 'kind': 'fact'}], model='synthetic')
    monkeypatch.setattr(answers, 'now', lambda: datetime(2026, 10, 8, tzinfo=timezone.utc))
    yield episodes, claims, episode.id
    claims.close()
    episodes.close()


def prepare(memory):
    def response(user):
        number = nr(user, 'Versandregel')
        return {'status': 'antwort', 'saetze': [
            {'text': PARAPHRASE, 'belege': [number]},
            {'text': ABSENCE, 'belege': [number]},
        ]}
    episodes, claims, _ = memory
    return answers.prepare('Welche Regel gilt für den Versand von Material aus M-731 und liegt die Freigabe vor?',
                           episodes, claims, Skript(response), saetze=True)


def assert_original(answer, memory):
    episodes, claims, episode_id = memory
    text, links, status = answers.render(answer, episodes, claims)
    assert status == 'working_reports'
    assert SOURCE in text
    assert episode_id in {link['episode_id'] for link in links}
    assert answers.satz_struktur(answer, episodes, claims) is None


def test_rejecting_a_rule_cannot_leave_only_its_absence_status_visible(memory):
    answer = prepare(memory)
    assert answer['satzantwort']['verworfen'] == 1
    assert answer['satzantwort']['status'] == 'zitate'
    assert_original(answer, memory)


def legacy_partial(memory):
    answer = prepare(memory)
    data = answer['satzantwort']
    # Recreate the old stored state: the rejected rule is gone, the same source
    # remains represented by only its availability status.
    data['status'] = 'saetze'
    data['saetze'] = [{'roh': ABSENCE, 'text': ABSENCE, 'belege': [1], 'vom_programm': False}]
    data['verworfen'] = 1
    return json.loads(json.dumps(answer))


def test_saved_partial_rule_answer_is_revalidated_without_a_model(memory):
    assert_original(legacy_partial(memory), memory)


def test_withdrawal_still_removes_saved_rule_and_status(memory):
    answer = legacy_partial(memory)
    episodes, claims, episode_id = memory
    episodes.ignore(episode_id)
    text, links, status = answers.render(answer, episodes, claims)
    assert status == 'working_unavailable' and links == []
    assert RULE not in text and ABSENCE not in text


def test_model_rejection_of_literal_rule_also_preserves_the_same_source_condition(memory):
    def response(user):
        number = nr(user, 'Versandregel')
        return {'status': 'antwort', 'saetze': [
            {'text': RULE, 'belege': [number]}, {'text': ABSENCE, 'belege': [number]}]}
    episodes, claims, _ = memory
    gate = satzpruefung_modell.tor('an', Pruefer({'versandt': '{"urteil":"nein"}'}))
    answer = answers.prepare('Welche Regel gilt für Material M-731 und liegt die Freigabe vor?',
                             episodes, claims, Skript(response), saetze=True, pruefung=gate)
    assert answer['satzantwort']['pruefung']['verworfen'] == 1
    assert_original(answer, memory)


def test_complete_literal_rule_and_status_remain_prose(memory):
    def response(user):
        number = nr(user, 'Versandregel')
        return {'status': 'antwort', 'saetze': [
            {'text': RULE, 'belege': [number]}, {'text': ABSENCE, 'belege': [number]}]}
    episodes, claims, _ = memory
    answer = answers.prepare('Welche Regel gilt für Material M-731 und liegt die Freigabe vor?',
                             episodes, claims, Skript(response), saetze=True)
    assert answer['satzantwort']['status'] == 'saetze'
    assert answer['satzantwort']['verworfen'] == 0
    assert answers.satz_struktur(answer, episodes, claims) is not None
