"""Konkurrierende bestätigte Abläufe klären, bevor ein lokaler Entwurf entsteht."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from icarus_memory.procedures import ProcedureStore
from tests.test_mail_reply_suggestions import Mail, Provider, make_client
from tests.test_procedures import spec

URL = '/api/v1/messages/a%3A1.1/reply-suggestion'
REQUEST = 'Schreibe eine Mail für die Zunft.'


@pytest.fixture
def flow(tmp_path):
    class Capture(Provider):
        def __init__(self): self.seen = []; self.during = lambda: None
        def complete_json(self, messages):
            self.seen.append(messages); self.during()
            return SimpleNamespace(text='{"body":"Künstlicher Entwurf"}', tool_calls=[])
    p = Capture(); app, client = make_client(provider=p)
    stamps = {'a':'v1','b':'v1'}
    store = ProcedureStore(tmp_path / 'procedures.sqlite3', dependency=stamps.get)
    app.state.procedures = store
    a = store.accept(store.propose(spec(), sources={'a':'v1'})['id'])
    b = store.accept(store.propose({**spec(), 'name':'zunft-kurz', 'title':'Kurze Zunftmail',
        'steps':['Anlass prüfen, danach kurz formulieren.']}, sources={'b':'v1'})['id'])
    yield app, client, p, store, a, b, stamps
    store.close()


def ask(flow):
    _, client, p, _, a, b, _ = flow
    response = client.post(URL, json={'instruction':REQUEST})
    assert response.status_code == 200, response.text
    assert not p.seen, 'Bei konkurrierenden Abläufen noch kein Modellaufruf'
    result = response.json()
    assert 'body' not in result
    offered = result['procedure_choice']
    assert {x['id'] for x in offered['options']} == {a['id'],b['id'],'core'}
    assert all('steps' not in x for x in offered['options'])
    return offered


def choose(flow, offered, identifier):
    return flow[1].post(URL, json={'instruction':REQUEST,
        'procedure_choice':{'token':offered['token'], 'id':identifier}})


def test_conflict_asks_before_model_and_one_choice_is_used_once(flow):
    _, _, p, store, a, b, _ = flow
    offered = ask(flow)
    result = choose(flow, offered, a['id'])
    assert result.status_code == 200, result.text
    assert result.json()['body'] == 'Künstlicher Entwurf'
    assert len(p.seen) == 1
    assert 'gegenlesen' in json.dumps(p.seen) and 'kurz formulieren' not in json.dumps(p.seen)
    assert choose(flow, offered, a['id']).status_code == 409
    assert len(p.seen) == 1
    assert store.get(b['id'])['state'] == 'active'
    p.seen.clear(); ask(flow)  # Keine dauerhafte Auswahl.


def test_explicit_basic_choice_uses_no_personal_procedure(flow):
    offered = ask(flow)
    assert choose(flow, offered, 'core').status_code == 200
    assert 'gegenlesen' not in json.dumps(flow[2].seen)
    assert 'kurz formulieren' not in json.dumps(flow[2].seen)


@pytest.mark.parametrize('change', ['mail','account','instruction','provider','provider_model','permission','mail_provider','source','revoke','version','unknown','expired','restart'])
def test_stale_or_foreign_choice_never_reaches_model(flow, change):
    app, client, p, store, a, _, stamps = flow
    offered = ask(flow)
    instruction = REQUEST; identifier = a['id']
    if change == 'mail': app.state.mail.item = replace(app.state.mail.item, body='Geändert')
    elif change == 'account': app.state.mail.item = replace(app.state.mail.item, account_id='other')
    elif change == 'instruction': instruction = 'Schreibe eine andere Mail für die Zunft.'
    elif change == 'provider': app.state.agent.provider = Provider()
    elif change == 'provider_model': p.model = 'different-model'
    elif change == 'permission': p._verified_local_permitted = lambda: False
    elif change == 'mail_provider': app.state.mail = Mail()
    elif change == 'source': stamps['a'] = 'v2'
    elif change == 'revoke': store.revoke(a['id'])
    elif change == 'version': store.accept(store.propose({**spec(), 'steps':['Anlass prüfen, dann sachlich schreiben.']})['id'])
    elif change == 'expired': app.state.procedure_choices[offered['token']]['created'] -= 601
    elif change == 'restart': app.state.procedure_choices.clear()
    else: identifier = 'unknown'
    response = client.post(URL, json={'instruction':instruction,
        'procedure_choice':{'token':offered['token'],'id':identifier}})
    assert response.status_code == 409, response.text
    assert not p.seen


def test_private_request_remains_unaffected(flow):
    result = flow[1].post(URL, json={'instruction':'Schreibe eine private Urlaubsmail.'})
    assert result.status_code == 200 and 'body' in result.json()
    assert len(flow[2].seen) == 1 and 'gegenlesen' not in json.dumps(flow[2].seen)


def test_chosen_procedure_withdrawn_during_model_discards_draft(flow):
    _, _, p, store, a, _, _ = flow
    offered = ask(flow)
    p.during = lambda: store.revoke(a['id'])
    result = choose(flow, offered, a['id'])
    assert result.status_code == 409 and 'body' not in result.json()
