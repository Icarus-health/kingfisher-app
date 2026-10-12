"""Omitted changes must not silently leave a current commitment unqualified."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore

AT = datetime(2026, 9, 9, 9, tzinfo=timezone.utc)
QUESTION = 'Was ist der aktuelle Stand meiner Hilfe beim Herbstmarkt?'
PROMISE = 'Ich übernehme den Standdienst am Herbstmarkt am 20.09.2026; die Kinderbetreuung ist organisiert.'
WITHDRAWAL = 'Ich kann am 27.09.2026 doch nicht beim Herbstmarkt helfen; bitte meine Zusage streichen.'


class OmitChanges:
    is_local = True
    model = 'synthetic-selection-failure'

    def __init__(self):
        self.calls = 0

    def complete_json(self, messages, **kwargs):
        self.calls += 1
        rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': 'source_reports',
                                     'ids': [r['id'] for r in rows if r['kind'] == 'commitment']}))


@pytest.fixture
def memory(tmp_path):
    episodes, claims = EpisodeStore(tmp_path / 'episodes.sqlite3'), ClaimStore(tmp_path / 'claims.sqlite3')
    yield episodes, claims
    claims.close()
    episodes.close()


def add(episodes, text, kind, *, days=0, occurred=True, participants=(), project=None):
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Synthetische Quelle', text,
        Provenance(SourceType.DOCUMENT, source_ref=f'synthetic:{kind}:{days}:{text}'),
        at=AT + timedelta(days=10), occurred_at=AT + timedelta(days=days) if occurred else None,
        participants=list(participants), project_id=project)
    assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
        [{'start': 0, 'end': len(text), 'kind': kind}], model='synthetic')
    return episode


def ask(memory, question=QUESTION):
    episodes, claims = memory
    provider = OmitChanges()
    before = claims.revision
    answer = answers.prepare(question, episodes, claims, provider, semantic_search=None, saetze=False)
    assert provider.calls == 1  # Guard needs no repeated model call and no prose generation.
    assert claims.revision == before
    return answer


def test_dropped_withdrawal_is_retained_without_claiming_a_proven_relation(memory):
    episodes, claims = memory
    promise = add(episodes, PROMISE, 'commitment')
    withdrawal = add(episodes, WITHDRAWAL, 'status', days=3)
    answer = ask(memory)
    assert {r['episode_id'] for r in answer['refs']} == {promise.id, withdrawal.id}
    assert answer['status'] == 'unclear'
    assert answer['uncertainty'] == 'conflict'
    assert 'satzantwort' not in answer
    text, links, mode = answers.render(answer, episodes, claims)
    assert mode == 'working_unclear'
    assert WITHDRAWAL in text
    assert 'mögliche Änderung' in text
    assert 'Zusammengehörigkeit' in text
    assert 'Welche gilt' not in text  # Different statements need not describe the same duty.
    assert not answer.get('akten', {}).get('ueberholt')
    episodes.ignore(withdrawal.id)
    assert answers.render(answer, episodes, claims)[2] == 'working_unavailable'
    assert episodes.get(withdrawal.id).body == WITHDRAWAL


@pytest.mark.parametrize('text,kind', [
    ('Die Zusage für den Herbstmarkt ist zurückgezogen.', 'status'),
    ('Der Standdienst beim Herbstmarkt entfällt.', 'status'),
    ('Die Hilfe beim Herbstmarkt ist nicht mehr nötig.', 'status'),
    ('Der Herbstmarkt wird vom 20. auf den 27. September verschoben.', 'change'),
])
def test_current_question_keeps_an_omitted_explicit_change(memory, text, kind):
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    later = add(episodes, text, kind, days=3)
    assert later.id in {r['episode_id'] for r in ask(memory)['refs']}


@pytest.mark.parametrize('text', [
    'Bitte meine Zusage für den Herbstmarkt nicht streichen.',
    'Die Zusage für den Herbstmarkt ist nicht zurückgezogen.',
    'Der Standdienst beim Herbstmarkt entfällt nicht.',
    'Es gibt keine Absage für den Herbstmarkt.',
])
def test_negated_cancellation_does_not_trigger_a_change_question(memory, text):
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    add(episodes, text, 'status', days=3)
    answer = ask(memory)
    assert answer['status'] == 'reports'
    assert not answer.get('change_review')


@pytest.mark.parametrize('text', [
    'Der Standdienst beim Herbstmarkt entfällt nicht nur für mich, sondern für alle Helfer.',
    'Die Zusage beim Herbstmarkt ist nicht nur zurückgezogen, sondern auch organisatorisch überflüssig.',
    'Der Standdienst beim Herbstmarkt entfällt nicht bloß für mich, sondern für alle Helfer.',
    'Die Zusage beim Herbstmarkt ist nicht allein zurückgezogen, sondern auch erledigt.',
])
def test_additive_not_only_does_not_negate_an_explicit_cancellation(memory, text):
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    cancellation = add(episodes, text, 'status', days=3)
    answer = ask(memory)
    assert answer['status'] == 'unclear'
    assert cancellation.id in {ref['episode_id'] for ref in answer['refs']}


@pytest.mark.parametrize('question', [
    'Was hatte ich ursprünglich beim Herbstmarkt zugesagt?',
    'Was stand am 9. September 2026 in meiner Zusage für den Herbstmarkt?',
])
def test_historical_question_does_not_force_the_current_stand(memory, question):
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    add(episodes, WITHDRAWAL, 'status', days=3)
    answer = ask(memory, question)
    assert answer['status'] == 'reports'
    assert not answer.get('change_review')


def test_unknown_original_time_cannot_establish_a_later_withdrawal(memory):
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    withdrawal = add(episodes, WITHDRAWAL, 'status', days=3, occurred=False)
    answer = ask(memory)
    assert answer['status'] == 'unclear'
    assert withdrawal.id in {r['episode_id'] for r in answer['refs']}
    assert not answer.get('akten', {}).get('ueberholt')


def test_other_event_is_not_presented_as_withdrawing_this_promise(memory):
    episodes, _ = memory
    promise = add(episodes, PROMISE, 'commitment')
    add(episodes, 'Meine Zusage für den Sommermarkt bitte streichen.', 'status', days=3)
    answer = ask(memory)
    assert answer['status'] == 'reports'
    assert [r['episode_id'] for r in answer['refs']] == [promise.id]


def test_more_specific_event_qualifier_is_respected(memory):
    episodes, _ = memory
    promise = add(episodes, 'Ich helfe beim Herbstmarkt in Berlin.', 'commitment')
    add(episodes, 'Meine Zusage für den Herbstmarkt in Dresden bitte streichen.', 'status', days=3)
    answer = ask(memory, 'Was ist der aktuelle Stand meiner Hilfe beim Herbstmarkt in Berlin?')
    assert answer['status'] == 'reports'
    assert [r['episode_id'] for r in answer['refs']] == [promise.id]


def test_newer_recommitment_is_not_replaced_by_an_older_withdrawal(memory):
    episodes, _ = memory
    add(episodes, WITHDRAWAL, 'status')
    promise = add(episodes, PROMISE, 'commitment', days=3)
    answer = ask(memory)
    assert answer['status'] == 'reports'
    assert [r['episode_id'] for r in answer['refs']] == [promise.id]


def test_different_project_does_not_change_selected_commitment(memory):
    episodes, _ = memory
    promise = add(episodes, PROMISE, 'commitment', project='project-nord')
    add(episodes, WITHDRAWAL, 'status', days=3, project='project-sued')
    answer = ask(memory)
    assert answer['status'] == 'reports'
    assert [r['episode_id'] for r in answer['refs']] == [promise.id]


def test_conditional_statement_is_not_treated_as_a_withdrawal(memory):
    episodes, _ = memory
    promise = add(episodes, PROMISE, 'commitment')
    add(episodes, 'Falls die Betreuung nicht klappt, muss ich meine Zusage für den Herbstmarkt streichen.',
        'conditional', days=3)
    answer = ask(memory)
    assert answer['status'] == 'reports'
    assert [r['episode_id'] for r in answer['refs']] == [promise.id]


def test_two_duties_are_not_silently_merged_or_overwritten(memory):
    episodes, claims = memory
    promise = add(episodes, 'Ich übernehme den Standdienst beim Herbstmarkt.', 'commitment')
    poster = add(episodes, 'Meine separate Zusage für den Plakatdruck beim Herbstmarkt bitte streichen; '
                 'der Standdienst ist davon unabhängig.', 'status', days=3)
    answer = ask(memory)
    assert answer['status'] == 'unclear'
    assert {ref['episode_id'] for ref in answer['refs']} == {promise.id, poster.id}
    # Two statements are visible; no automatic relation, task cancellation or one-quote choice.
    assert not answer.get('akten', {}).get('ueberholt')
    assert answers.choices(answer, episodes) == []
    text = answers.render(answer, episodes, claims)[0]
    assert 'separate Zusage' in text and 'davon unabhängig' in text


def test_guard_honours_resolved_other_person_annotations():
    from icarus_memory.working_memory_changes import omitted
    rows = [
        {'id': 'S1', 'kind': 'commitment', 'context': PROMISE},
        {'id': 'S2', 'kind': 'status', 'context': WITHDRAWAL, 'andere_person': 'Alex Winter <other@example.invalid>'},
    ]
    assert omitted(QUESTION, rows, ['S1'], 'reports') == []


def test_guard_does_not_override_existing_person_or_project_questions():
    from icarus_memory.working_memory_changes import omitted
    rows = [{'id': 'S1', 'kind': 'commitment', 'context': PROMISE},
            {'id': 'S2', 'kind': 'status', 'context': WITHDRAWAL}]
    for status in ('person', 'scope', 'time', 'conflict', 'unknown'):
        assert omitted(QUESTION, rows, ['S1'], status) == []


def test_guard_uses_full_original_instead_of_the_short_model_excerpt(memory, monkeypatch):
    from icarus_memory import absatzauswahl
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    # The cancellation can live in a paragraph absent from the model excerpt.
    body = 'Herbstmarkt: weitere Informationen.\n\n' + 'Ein langer unwichtiger Abschnitt. ' * 100 + '\n\n' + WITHDRAWAL
    change = add(episodes, body, 'status', days=3)
    real = absatzauswahl.auszug

    def omit_clause(text, words, **kwargs):
        if text == body:
            return absatzauswahl.Auszug('Herbstmarkt: weitere Informationen.', 1, 3)
        return real(text, words, **kwargs)

    monkeypatch.setattr(absatzauswahl, 'auszug', omit_clause)
    answer = ask(memory)
    assert answer['status'] == 'unclear'
    assert change.id in {ref['episode_id'] for ref in answer['refs']}


def test_guard_prevents_prose_generation_after_incomplete_selection(memory, monkeypatch):
    episodes, claims = memory
    add(episodes, PROMISE, 'commitment')
    add(episodes, WITHDRAWAL, 'status', days=3)

    def must_not_generate(*args, **kwargs):
        pytest.fail('Incomplete current-state selection must remain original quotes')

    monkeypatch.setattr(answers.satzantwort, 'erzeugen', must_not_generate)
    provider = OmitChanges()
    answer = answers.prepare(QUESTION, episodes, claims, provider, semantic_search=None, saetze=True)
    assert answer['status'] == 'unclear' and provider.calls == 1


@pytest.mark.parametrize('question', [
    'Was ist heute der aktuelle Stand meiner Hilfe beim Herbstmarkt?',
    'Habe ich noch beim Herbstmarkt zugesagt?',
    'Habe ich beim Herbstmarkt aktuell verbindlich zugesagt?',
])
def test_original_cancellation_chain_survives_current_question_holdouts(memory, question):
    episodes, _ = memory
    add(episodes, PROMISE, 'commitment')
    add(episodes, 'Der Herbstmarkt findet nicht am 20., sondern am 27. September 2026 statt. '
        'Es ist derselbe Herbstmarkt.', 'change', days=2)
    withdrawal = add(episodes, WITHDRAWAL, 'status', days=3)
    answer = ask(memory, question)
    assert answer['status'] == 'unclear'
    assert withdrawal.id in {ref['episode_id'] for ref in answer['refs']}


def test_legacy_incomplete_selection_is_hidden_in_render_and_conversation(memory):
    import copy
    episodes, claims = memory
    promise = add(episodes, PROMISE, 'commitment')
    add(episodes, WITHDRAWAL, 'status', days=3)
    saved = copy.deepcopy(ask(memory))
    # Simulate the pre-patch answer: same sources, valid fingerprints, omitted withdrawal.
    saved['refs'] = [ref for ref in saved['basis'] if ref['episode_id'] == promise.id]
    saved.update(status='reports', uncertainty='none')
    saved.pop('change_review', None)
    text, links, mode = answers.render(saved, episodes, claims)
    assert mode == 'working_unavailable' and links == []
    assert PROMISE not in text
    projected = answers.project_message({'role': 'assistant', 'content': PROMISE,
        'metadata': {'context': {'working_answer': saved}}}, episodes, claims)
    assert projected['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
    assert PROMISE not in projected['content']
