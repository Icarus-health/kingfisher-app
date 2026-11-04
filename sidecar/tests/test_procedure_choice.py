"""Eine bestätigte Ablaufwahl gilt nur für den aktuellen Auftrag und Quellenstand."""
import pytest

from icarus_memory.procedures import ProcedureError, ProcedureStore
from tests.test_procedures import spec

REQUEST = 'Schreibe eine Mail für die Zunft.'


@pytest.fixture
def library(tmp_path):
    stamps = {'source-a': 'v1', 'source-b': 'v1'}
    store = ProcedureStore(tmp_path / 'procedures.sqlite3', dependency=stamps.get)
    first = store.accept(store.propose(spec(), sources={'source-a': 'v1'})['id'])
    second = store.accept(store.propose({**spec(), 'name': 'zunftmail-kurz', 'title': 'Kurze Zunftmail',
        'steps': ['Anlass prüfen. Anschließend kurz formulieren.']}, sources={'source-b': 'v1'})['id'])
    yield store, first, second, stamps
    store.close()


def offered(store, item):
    selected = store.select(REQUEST, area='mail')
    return {'id': item['id'], 'signature': selected['choice_signature']}


def test_conflict_offers_only_headers_before_any_procedure_body_is_loaded(library, monkeypatch):
    store, first, second, _ = library
    monkeypatch.setattr(store, 'get', lambda _: pytest.fail('Kein Kandidatentext vor der Auswahl'))
    selected = store.select(REQUEST, area='mail')
    assert not selected['contextual']
    assert {c['id'] for c in selected['choices']} == {first['id'], second['id']}
    assert all(set(c) == {'id', 'name', 'title', 'version'} for c in selected['choices'])
    assert len(selected['choice_signature']) == 64


def test_valid_choice_loads_only_selected_version_and_is_not_permanent(library):
    store, first, second, _ = library
    selected = store.select(REQUEST, area='mail', choice=offered(store, first))
    assert [item['id'] for item in selected['contextual']] == [first['id']]
    assert not selected['conflicts']
    assert 'gegenlesen' in selected['instructions'] and 'kurz formulieren' not in selected['instructions']
    assert store.current(selected)
    assert len(store.select(REQUEST, area='mail')['conflicts']) == 2
    assert store.get(second['id'])['state'] == 'active'


def test_explicit_basic_choice_keeps_both_procedures_active(library):
    store, first, second, _ = library
    choice = offered(store, first) | {'id': 'core'}
    selected = store.select(REQUEST, area='mail', choice=choice)
    assert not selected['contextual'] and not selected['conflicts']
    assert selected['essential'] and selected['builtin']
    assert selected['missing'] is False
    assert all(store.get(item['id'])['state'] == 'active' for item in (first, second))


@pytest.mark.parametrize('change', ['message', 'area', 'cloud', 'source', 'revoke', 'version', 'new_candidate'])
def test_choice_cannot_be_replayed_after_scope_or_candidate_changes(library, change):
    store, first, _, stamps = library
    choice = offered(store, first)
    args = {'area': 'mail', 'local': True}
    message = REQUEST
    if change == 'message': message = 'Schreibe eine kurze Mail für die Zunft.'
    elif change == 'area': args['area'] = 'analysis'
    elif change == 'cloud': args['local'] = False
    elif change == 'source': stamps['source-a'] = 'v2'
    elif change == 'revoke': store.revoke(first['id'])
    elif change == 'version':
        store.accept(store.propose({**spec(), 'steps': ['Zuerst Anlass prüfen. Danach sachlich entwerfen.']})['id'])
    else:
        store.accept(store.propose({**spec(), 'name': 'zunftmail-drei', 'title': 'Dritter Ablauf'})['id'])
    with pytest.raises(ProcedureError, match='Auswahl'):
        store.select(message, **args, choice=choice)


@pytest.mark.parametrize('invalid', [{'id': 'unknown'}, {'signature': 'wrong'}, {'id': True}, {'extra': 'value'}])
def test_unknown_or_malformed_choice_cannot_select_a_procedure(library, invalid):
    store, first, _, _ = library
    with pytest.raises(ProcedureError, match='Auswahl'):
        store.select(REQUEST, area='mail', choice=offered(store, first) | invalid)


def test_selected_source_withdrawal_still_invalidates_result(library):
    store, first, _, stamps = library
    selected = store.select(REQUEST, area='mail', choice=offered(store, first))
    del stamps['source-a']
    assert not store.current(selected)
