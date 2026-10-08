"""A literal original quote must still concern the explicitly requested case."""
import copy
import json

import pytest

from icarus_memory.providers import Reply
from icarus_memory.working_memory_answers import prepare, render, _fresh
from tests.test_memory_project_names import stores, _source


class SelectAll:
    is_local = True

    def complete_json(self, messages, **kwargs):
        rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': 'source_reports',
                                      'ids': [row['id'] for row in rows]}))


@pytest.mark.parametrize('body', [
    'Nachricht: Vera Noll liefert, Veit Noll prüft die Ware.',
    'Auftrag ZX-92: Veit Noll prüft die Ware.',
    'Auftrag ZX-29X: Veit Noll prüft die Ware.',
])
def test_wrong_original_is_not_an_answer_to_an_explicit_case(stores, body):
    episodes, claims = stores
    _source(episodes, body)
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29?', episodes, claims, SelectAll(),
                     semantic_search=None)
    text, links, status = render(answer, episodes, claims)
    assert status == 'working_unknown'
    assert not links and 'Veit Noll' not in text


def test_generic_competitor_is_excluded_but_correct_source_survives(stores):
    episodes, claims = stores
    wanted = _source(episodes, 'Auftrag ZX-29: Lene Kühn prüft die Ware.')
    _source(episodes, 'Nachricht: Veit Noll prüft die Ware.')
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29?', episodes, claims, SelectAll(),
                     semantic_search=None)
    text, links, status = render(answer, episodes, claims)
    assert status == 'working_reports'
    assert {link['episode_id'] for link in links} == {wanted.id}
    assert 'Lene Kühn' in text and 'Veit Noll' not in text


def test_original_subject_can_supply_the_reference(stores):
    episodes, claims = stores
    source = _source(episodes, 'Lene Kühn prüft die Ware.', title='Auftrag ZX-29')
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29?', episodes, claims, SelectAll(),
                     semantic_search=None)
    assert [ref['episode_id'] for ref in answer['refs']] == [source.id]
    assert render(answer, episodes, claims)[2] == 'working_reports'


def test_user_project_assignment_can_supply_the_reference(stores):
    episodes, claims = stores
    episodes._working_project_name = lambda identifier: 'ZX-29'
    source = _source(episodes, 'Lene Kühn prüft die Ware.', project='project-opaque')
    answer = prepare('Wer prüft die Ware im Projekt ZX-29?', episodes, claims, SelectAll(),
                     projects=[('project-opaque', 'ZX-29')], semantic_search=None)
    assert [ref['episode_id'] for ref in answer['refs']] == [source.id]
    assert _fresh(json.loads(json.dumps(answer)), episodes, claims)


def test_comparison_keeps_separate_references(stores):
    episodes, claims = stores
    one = _source(episodes, 'Auftrag ZX-29: Lene Kühn prüft die Ware.')
    two = _source(episodes, 'Auftrag ZX-92: Veit Noll prüft die Ware.')
    answer = prepare('Wer prüft die Ware in Auftrag ZX-29 und Auftrag ZX-92?',
                     episodes, claims, SelectAll(), semantic_search=None)
    assert {ref['episode_id'] for ref in answer['refs']} == {one.id, two.id}


def test_independent_unscoped_subquestion_does_not_lose_its_source(stores):
    episodes, claims = stores
    one = _source(episodes, 'Auftrag ZX-29: Lene Kühn prüft die Ware.')
    two = _source(episodes, 'Der Urlaub ist am 18. Dezember.')
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29 und wann ist der Urlaub?',
                     episodes, claims, SelectAll(), semantic_search=None)
    assert {ref['episode_id'] for ref in answer['refs']} == {one.id, two.id}


def test_parallel_topics_without_repeated_question_word_are_not_globally_filtered(stores):
    episodes, claims = stores
    one = _source(episodes, 'Auftrag ZX-29: Lene Kühn prüft die Ware.')
    two = _source(episodes, 'Der Urlaub ist am 18. Dezember.')
    answer = prepare('Was ist zu Auftrag ZX-29 und Urlaub bekannt?',
                     episodes, claims, SelectAll(), semantic_search=None)
    assert {ref['episode_id'] for ref in answer['refs']} == {one.id, two.id}


def test_search_expansion_cannot_invent_a_reference_constraint(stores):
    episodes, claims = stores
    source = _source(episodes, 'Veit Noll prüft die Ware.')
    answer = prepare('Wer prüft die Ware?', episodes, claims, SelectAll(),
                     retrieval_query='Wer prüft die Ware im Auftrag ZX-29?', semantic_search=None)
    assert [ref['episode_id'] for ref in answer['refs']] == [source.id]


def test_previously_saved_wrong_selection_is_blocked_without_a_model(stores):
    episodes, claims = stores
    _source(episodes, 'Veit Noll prüft die Ware.')
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29?', episodes, claims, SelectAll(),
                     semantic_search=None)
    # Legacy snapshots from before the guard carry a valid but unrelated source.
    legacy = copy.deepcopy(answer)
    legacy.update(status='reports', uncertainty='none', refs=list(answer['basis']))
    assert not _fresh(legacy, episodes, claims)
    text, links, status = render(legacy, episodes, claims)
    assert status == 'working_unavailable'
    assert not links and 'Veit Noll' not in text


@pytest.mark.parametrize('label,asked,stored', [
    ('Ticket', 'AB-812', 'AB-812'),
    ('Vorgang', 'M731', 'M731'),
    ('Rechnung', 'INV/203', 'INV/203'),
    ('Fall', 'ab-812', 'AB-812'),
    ('Auftrag Nr.', 'AB‑812', 'AB-812'),
])
def test_reference_syntax_is_general_and_preserves_matching_sources(stores, label, asked, stored):
    episodes, claims = stores
    source = _source(episodes, f'{stored}: Lene Kühn prüft die Ware.')
    _source(episodes, 'Veit Noll prüft die Ware.')
    answer = prepare(f'Wer prüft die Ware für {label} {asked}?', episodes, claims, SelectAll(),
                     semantic_search=None)
    assert [ref['episode_id'] for ref in answer['refs']] == [source.id]
    assert _fresh(json.loads(json.dumps(answer)), episodes, claims)


def test_scope_helpers_cannot_restore_an_unbound_source(stores, monkeypatch):
    from icarus_memory import working_memory_projects
    episodes, claims = stores
    _source(episodes, 'Auftrag ZX-29: Lene Kühn prüft die Ware.')
    _source(episodes, 'Veit Noll prüft die Ware.')
    def restore_unbound(question, rows, ids, status):
        return [row['id'] for row in rows if 'Veit Noll' in row['context']], status
    monkeypatch.setattr(working_memory_projects, 'adjust', restore_unbound)
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29?', episodes, claims, SelectAll(),
                     semantic_search=None)
    text, links, status = render(answer, episodes, claims)
    assert status == 'working_unknown'
    assert not links and 'Veit Noll' not in text


def test_a_matching_id_does_not_promote_model_non_answerability(stores):
    episodes, claims = stores
    _source(episodes, 'Auftrag ZX-29: Lene Kühn liefert die Ware.')
    class NoAnswer(SelectAll):
        def complete_json(self, messages, **kwargs):
            return Reply(text=json.dumps({'status': 'no_relevant_sources', 'ids': []}))
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29?', episodes, claims, NoAnswer(),
                     semantic_search=None)
    assert render(answer, episodes, claims)[2] == 'working_unknown'
    assert not answer['refs']


@pytest.mark.parametrize('question', [
    'Wer prüft die Ware nicht im Auftrag ZX-29?',
    'Wer prüft die Ware im Auftrag ZX-29? Wann ist der Urlaub?',
    'Wann ist der Urlaub im Jahr 2026?',
])
def test_unparsed_or_independent_scopes_stay_with_the_selector(stores, question):
    episodes, claims = stores
    source = _source(episodes, 'Lene Kühn prüft die Ware vor dem Urlaub im Jahr 2026.')
    answer = prepare(question, episodes, claims, SelectAll(), semantic_search=None)
    assert [ref['episode_id'] for ref in answer['refs']] == [source.id]


def test_an_untyped_other_mail_number_cannot_replace_the_requested_case(stores):
    episodes, claims = stores
    _source(episodes, 'Mail AB-22: Veit Noll prüft die Ware.')
    answer = prepare('Wer prüft die Ware im Auftrag ZX-29 laut Mail AB-22?',
                     episodes, claims, SelectAll(), semantic_search=None)
    assert render(answer, episodes, claims)[2] == 'working_unknown'


def test_project_rename_revalidates_old_reference_binding(stores):
    episodes, claims = stores
    names = {'project-opaque': 'ZX-29'}
    episodes._working_project_name = names.__getitem__
    _source(episodes, 'Lene Kühn prüft die Ware.', project='project-opaque')
    answer = prepare('Wer prüft die Ware im Projekt ZX-29?', episodes, claims, SelectAll(),
                     projects=list(names.items()), semantic_search=None)
    assert _fresh(answer, episodes, claims)
    names['project-opaque'] = 'ZX-92'
    assert not _fresh(answer, episodes, claims)
    assert render(answer, episodes, claims)[2] == 'working_unavailable'


def test_plural_comparison_keeps_coordinated_reference_codes(stores):
    episodes, claims = stores
    one = _source(episodes, 'Auftrag ZX-29: Lene Kühn prüft die Ware.')
    two = _source(episodes, 'Auftrag ZX-92: Veit Noll prüft die Ware.')
    answer = prepare('Wer prüft die Ware in den Aufträgen ZX-29 und ZX-92?',
                     episodes, claims, SelectAll(), semantic_search=None)
    assert {ref['episode_id'] for ref in answer['refs']} == {one.id, two.id}
