"""Einordnung begrenzt Auswahl, ersetzt aber keine Bestätigung oder Aktenwahl."""
import json

import pytest

from icarus_memory.procedures import ProcedureError, ProcedureStore, markdown, parse_markdown
from tests.test_procedures import spec


@pytest.mark.parametrize(('area', 'category'), [('mail', 'communication'), ('planning', 'planning'), ('analysis', 'research')])
def test_existing_requests_get_an_automatic_category_but_never_become_essential(tmp_path, area, category):
    store = ProcedureStore(tmp_path/'p.sqlite3')
    item = store.propose({**spec(), 'area': area})
    assert (item['category'], item['contexts'], item['tier']) == (category, [], 'contextual')
    assert store.select('Zunftmail vorbereiten', area=area)['contextual'] == []
    store.accept(item['id'])
    assert store.select('Zunftmail vorbereiten', area=area)['contextual'][0]['category'] == category


def test_legacy_header_and_markdown_are_not_rewritten_or_duplicated(tmp_path):
    path = tmp_path/'p.sqlite3'
    store = ProcedureStore(path)
    first = store.propose(spec())
    old = spec()
    raw = '---\n'+json.dumps(old, ensure_ascii=False, indent=2)+'\n---\n\n# Alte Fassung\n'
    store._conn.execute('UPDATE procedures SET header=?, body=? WHERE id=?',
        (json.dumps({k:v for k,v in old.items() if k!='steps'}), raw, first['id']))
    store._conn.commit()
    store.accept(first['id']); store.close()
    store = ProcedureStore(path)
    assert store.get(first['id'])['category'] == 'communication'
    assert store.export(first['id']) == raw
    assert store.select('Zunftmail vorbereiten', area='mail')['contextual']
    repeated = store.propose(spec(), request_key='different-request')
    assert repeated['id'] == first['id']
    assert len(store.items()) == 1
    assert parse_markdown(raw)['contexts'] == []


def test_context_restricts_even_a_matching_trigger_and_never_reads_quoted_or_negated_context(tmp_path):
    store = ProcedureStore(tmp_path/'p.sqlite3')
    item = store.propose({**spec(), 'triggers':['einladung'], 'contexts':['Zunft'],
        'positive':'Schreibe eine Einladung für die Zunft.', 'negative':'Schreibe eine Einladung für den Urlaub.'})
    store.accept(item['id'])
    for message in ('Schreibe eine Einladung.', 'Schreibe eine Einladung für Zukunft.',
                    'Schreibe eine Einladung.\nZitat: Zunft', 'Schreibe eine Einladung, nicht für die Zunft.'):
        assert not store.select(message, area='mail')['contextual']
    assert store.select('Schreibe eine Einladung für die Zunft.', area='mail')['contextual']
    assert not store.select('Schreibe eine Einladung für die Zunft.', area='analysis')['contextual']


def test_contexts_separate_procedures_and_multiple_matching_contexts_stay_a_conflict(tmp_path):
    store = ProcedureStore(tmp_path/'p.sqlite3')
    for name, context in [('zunftbrief','Zunft'), ('berufsbrief','Beruf')]:
        store.accept(store.propose({**spec(), 'name':name, 'contexts':[context], 'triggers':['einladung'],
            'positive':f'Einladung für {context} schreiben.', 'negative':'Einladung für Urlaub schreiben.'})['id'])
    chosen = store.select('Einladung für Beruf schreiben.', area='mail')
    assert [i['name'] for i in chosen['contextual']] == ['berufsbrief']
    assert chosen['conflicts'] == []
    conflict = store.select('Einladung für Beruf und Zunft schreiben.', area='mail')
    assert not conflict['contextual'] and len(conflict['conflicts']) == 2


@pytest.mark.parametrize('change', [{'category':'essential'}, {'tier':'essential'}, {'category':'unknown'},
    {'contexts':['x']}, {'contexts':['offiziell']}, {'contexts':['Zunft']*5}, {'contexts':'Zunft'},
    {'contexts':['Beruf']}])
def test_invalid_categories_contexts_and_nonmatching_positive_examples_are_rejected(tmp_path, change):
    store = ProcedureStore(tmp_path/'p.sqlite3')
    with pytest.raises(ProcedureError):
        store.propose({**spec(), **change})


def test_learning_catalog_carries_small_classification_without_instruction_bodies(tmp_path):
    store = ProcedureStore(tmp_path/'p.sqlite3')
    store.propose({**spec(), 'contexts':['Zunft']})
    headers = store.learning_catalog('Lerne diesen Ablauf: Zunftmail prüfen.')
    assert headers[0]['category'] == 'communication' and headers[0]['contexts'] == ['Zunft']
    assert not any(key in headers[0] for key in ('steps','markdown','sources'))
    assert len(json.dumps(headers,ensure_ascii=False).encode()) <= 2400


def test_selection_only_reads_the_one_chosen_body_and_source_withdrawal_still_wins(tmp_path):
    stamps = {'source':'v1'}
    store = ProcedureStore(tmp_path/'p.sqlite3', dependency=stamps.get)
    first = store.propose({**spec(), 'contexts':['Zunft']}, sources=stamps.copy()); store.accept(first['id'])
    for i in range(12):
        row=store.propose({**spec(), 'name':f'other-{i}', 'area':'analysis'})
        store.accept(row['id'])
    seen=[]; get=store.get
    store.get=lambda key: (seen.append(key), get(key))[1]
    selected=store.select('Zunftmail für die Zunft vorbereiten', area='mail')
    assert seen == [first['id']]
    assert store.current(selected)
    del stamps['source']
    assert not store.current(selected)
    assert not store.select('Zunftmail vorbereiten', area='mail')['contextual']
    assert not store.select('Zunftmail vorbereiten', area='mail',local=False)['contextual']


def test_context_and_category_roundtrip_and_versioning(tmp_path):
    store=ProcedureStore(tmp_path/'p.sqlite3')
    item=store.propose({**spec(), 'category':'maintenance', 'contexts':['Zunft']})
    parsed=parse_markdown(store.export(item['id']))
    assert parsed['category']=='maintenance' and parsed['contexts']==['Zunft']
    store.accept(item['id'])
    revision=store.propose({**parsed,'contexts':[]})
    assert revision['version']==2 and revision['state']=='pending'
    assert store.select('Zunftmail für die Zunft vorbereiten', area='mail')['contextual'][0]['version']==1


def test_local_chat_learning_http_review_context_change_and_withdrawal(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.providers import Reply
    from icarus_memory.server import create_app
    from tests.test_procedure_runtime import Local, agent
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-category-token')
    provider=Local()
    drafted={**spec(), 'contexts':['Zunft'], 'category':'communication'}
    provider.complete=lambda messages, tools: (provider.seen.append(messages), Reply(text=json.dumps(drafted)))[1]
    app=create_app(agent=agent(tmp_path, provider))
    client=TestClient(app, headers={'X-Icarus-Token':'synthetic-category-token'})
    conv=client.post('/api/v1/conversations',json={'title':'Künstliche Lernprobe'}).json()['conversation']['id']
    learned=client.post(f'/api/v1/conversations/{conv}/messages',json={'message':
        'Lerne diesen Ablauf: Für Zunftmails zuerst Anlass prüfen, dann gegenlesen.'})
    assert learned.status_code==201
    listed=client.get('/api/v1/procedures').json()
    item=listed['items'][0]
    assert item['category']=='communication' and item['contexts']==['Zunft'] and item['tier']=='contextual'
    assert 'markdown' not in item and not app.state.procedures.select('Schreibe eine Zunftmail für die Zunft.',area='mail')['contextual']
    prompt=json.dumps(provider.seen[0],ensure_ascii=False)
    assert 'Kategorie' in prompt and 'contexts' in prompt
    assert client.post(f"/api/v1/procedures/{item['id']}/accept").status_code==200
    provider.complete=lambda messages, tools: (provider.seen.append(messages),Reply(text='Nur eine künstliche Antwort.'))[1]
    first=app.state.agent.send('Schreibe eine Zunftmail für die Zunft.')
    assert item['id'] in [r['id'] for r in first.context['procedures']['refs']]
    changed=app.state.agent.send('Schreibe eine private Mail.')
    assert item['id'] not in [r['id'] for r in changed.context['procedures']['refs']]
    assert changed.context['procedures']['history_reset'] is True
    assert 'gegenlesen' not in json.dumps(provider.seen[-1])
    source=next(iter(app.state.procedures.get(item['id'])['sources']))
    app.state.episodes.ignore(source)
    reopened=ProcedureStore(tmp_path/'procedures.sqlite3', dependency=app.state.procedures.dependency)
    try:
        assert not reopened.select('Schreibe eine Zunftmail für die Zunft.',area='mail')['contextual']
        assert reopened.get(item['id'])['current'] is False
    finally:
        reopened.close()
