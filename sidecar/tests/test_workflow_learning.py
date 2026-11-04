"""Wiederholte eigene Arbeitskorrekturen ergeben nur belegte inaktive Vorschläge."""
import json

import pytest
from fastapi.testclient import TestClient
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from tests.test_procedure_runtime import Local, agent
from tests.test_procedures import spec
from tests.test_conversation_retraction import _close_app

CORRECTION = 'Bitte zuerst Anlass und Empfänger prüfen, danach den Entwurf gegenlesen.'


@pytest.fixture
def flow(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    p = Local()
    def complete(messages, tools):
        p.seen.append(messages)
        data = json.loads(messages[-1]['content'])
        ids = [item['id'] for item in data['corrections']]
        p.during()
        return Reply(text=json.dumps({'kind':'workflow', 'supporting_ids':ids,
            'reason':'Drei eigene Korrekturen verlangen denselben Prüfschritt.', 'spec':spec()}))
    p.complete = complete
    app = create_app(agent=agent(tmp_path, p)); client = TestClient(app)
    yield app, client, p
    client.close(); _close_app(app)


def feedback(flow, nr, *, correction=CORRECTION, workflow=True, question=None):
    app, client, _ = flow
    conv = app.state.conversations.create(f'Künstlicher Vorgang {nr}')
    app.state.conversations.add_message(conv.id, 'user', question or f'Schreibe eine Mail für die Zunft zum Anlass {nr}.')
    reply = app.state.conversations.add_message(conv.id, 'assistant', 'Künstlicher Entwurf')
    response = client.post('/api/v1/rueckmeldungen', json={'conversation_id':conv.id,
        'message_id':reply.id, 'art':'sonstiges', 'richtig':correction, 'arbeitsweise':workflow})
    assert response.status_code == 201, response.text
    return response.json(), {'conversation_id':conv.id,'message_id':reply.id,'art':'sonstiges',
        'richtig':correction,'arbeitsweise':workflow}


def test_three_corrections_propose_once_without_activation_and_bind_sources(flow):
    app, client, p = flow
    first, _ = feedback(flow, 1); second, _ = feedback(flow, 2)
    assert first['lernen']['status'] == second['lernen']['status'] == 'collecting'
    assert not p.seen and not app.state.procedures.items()
    third, body = feedback(flow, 3)
    assert third['lernen']['status'] == 'proposed'
    item = app.state.procedures.get(third['lernen']['proposal_id'])
    assert item['state'] == 'pending' and len(item['sources']) == 3
    assert not app.state.procedures.select('Schreibe eine Zunftmail.', area='mail')['contextual']
    repeated = client.post('/api/v1/rueckmeldungen', json=body).json()
    assert repeated['lernen']['proposal_id'] == item['id'] and len(p.seen) == 1
    assert client.post(f"/api/v1/procedures/{item['id']}/accept").status_code == 200
    assert app.state.procedures.select('Schreibe eine Zunftmail.', area='mail')['contextual']
    assert not app.state.procedures.select('Schreibe eine private Urlaubsmail.', area='mail')['contextual']
    # Die ausdrückliche Kennzeichnung kann zurückgenommen werden: auch aktive Ableitungen veralten.
    client.post('/api/v1/rueckmeldungen', json={**body,'arbeitsweise':False})
    assert not app.state.procedures.get(item['id'])['current']
    assert not app.state.procedures.select('Schreibe eine Zunftmail.', area='mail')['contextual']


@pytest.mark.parametrize('correction,marked', [('Alexander heißt Alex.',True),
    ('Die Frist ist am 24. Dezember.',True),('Alex bitte duzen.',True),(CORRECTION,False)])
def test_facts_style_and_unmarked_notes_do_not_trigger_model(flow, correction, marked):
    for n in range(3): feedback(flow,n,correction=correction,workflow=marked)
    assert not flow[2].seen and not flow[0].state.procedures.items()


def test_same_task_repeated_does_not_count_as_learning_evidence(flow):
    for n in range(3): feedback(flow,n,question='Schreibe eine Mail für die Zunft.')
    assert not flow[2].seen and not flow[0].state.procedures.items()


def test_private_countercase_is_not_used_to_support_club_workflow(flow):
    feedback(flow,1); feedback(flow,2)
    last, _ = feedback(flow,3,question='Schreibe eine private Mail zur Urlaubsplanung.')
    assert last['lernen']['status'] != 'proposed' and not flow[0].state.procedures.items()


def test_rejected_proposal_does_not_return_from_the_same_evidence(flow):
    feedback(flow,1); feedback(flow,2); third, body = feedback(flow,3)
    identifier = third['lernen']['proposal_id']
    flow[1].post(f'/api/v1/procedures/{identifier}/reject')
    again = flow[1].post('/api/v1/rueckmeldungen',json=body).json()
    assert again['lernen']['status'] == 'dismissed' and len(flow[2].seen) == 1
    assert len(flow[0].state.procedures.items()) == 1


@pytest.mark.parametrize('change',['permission','model','correction'])
def test_changed_input_or_provider_during_model_never_creates_proposal(flow, change):
    app, _, p = flow
    first, body = feedback(flow,1); feedback(flow,2)
    def during():
        if change == 'permission': p.is_local = False
        elif change == 'model': p.model = 'other'
        else: app.state.rueckmeldungen.melden(frage=first['meldung']['frage'],antwort='Künstlicher Entwurf',
            art='sonstiges',nachricht_id=body['message_id'],gespraech_id=body['conversation_id'],richtig='Geändert')
    p.during = during
    result, _ = feedback(flow,3)
    assert result['lernen']['status'] != 'proposed' and not app.state.procedures.items()


def test_cloud_provider_is_never_used_for_corrections(flow):
    flow[2].is_local = False
    for n in range(3): result,_ = feedback(flow,n)
    assert result['lernen']['status'] == 'local_required'
    assert not flow[2].seen and not flow[0].state.procedures.items()


def test_source_retraction_invalidates_derived_workflow(flow):
    from tests.test_source_answers_http import _upload
    app, client, _ = flow
    source = _upload(client, 'Künstliche Ablaufgrundlage')
    conv = app.state.conversations.create('Quelle und Korrektur')
    app.state.conversations.add_message(conv.id,'user','Schreibe eine Mail für die Zunft zum ersten Anlass.')
    reply = app.state.conversations.add_message(conv.id,'assistant','Entwurf',metadata={'context':{
        'source_links':[{'episode_id':source,'label':'Künstliche Quelle'}]}})
    client.post('/api/v1/rueckmeldungen',json={'conversation_id':conv.id,'message_id':reply.id,
        'art':'sonstiges','richtig':CORRECTION,'arbeitsweise':True})
    feedback(flow,2); result,_ = feedback(flow,3)
    identifier = result['lernen']['proposal_id']
    app.state.episodes.ignore(source)
    assert client.post(f'/api/v1/procedures/{identifier}/accept').status_code == 409


def test_migration_preserves_legacy_notes_and_restart_preserves_review_result(tmp_path):
    import sqlite3
    from icarus_memory.rueckmeldung import Rueckmeldungen, _migrieren
    path=tmp_path/'notes.sqlite3'
    conn=sqlite3.connect(path); _migrieren(conn)
    conn.execute("INSERT INTO rueckmeldung(id,erstellt,frage,antwort,art,nachricht_id) VALUES ('old',1,'Frage','Antwort','falsch','m')")
    conn.execute('PRAGMA user_version=1'); conn.commit(); conn.close()
    store=Rueckmeldungen(path)
    assert store.hole('old')['workflow']=={} and store.hole('old')['antwort']=='Antwort'
    store.save_workflow_result('key',{'status':'no_pattern'}); store.close()
    store=Rueckmeldungen(path)
    assert store.workflow_result('key') == {'status':'no_pattern'}
    assert store.hole('old')['antwort']=='Antwort'
    store.close()


def test_three_new_corrections_can_propose_revision_without_changing_active_version(flow):
    app, client, p = flow
    for n in range(3): result,_=feedback(flow,n)
    old=result['lernen']['proposal_id']; client.post(f'/api/v1/procedures/{old}/accept')
    original=p.complete
    def revise(messages, tools):
        response=original(messages,tools); data=json.loads(response.text)
        data['spec']['steps']=['Zuerst Zuständigkeit prüfen, danach den Entwurf gegenlesen.']
        return Reply(text=json.dumps(data))
    p.complete=revise
    for n in range(3,6): result,_=feedback(flow,n,correction='Bitte zuerst Zuständigkeit prüfen, danach den Entwurf gegenlesen.')
    assert result['lernen']['proposal_id'] != old
    assert app.state.procedures.get(old)['state']=='active'
    assert app.state.procedures.get(result['lernen']['proposal_id'])['state']=='pending'


def test_review_shows_own_corrections_and_hides_them_after_withdrawal(flow):
    app, client, _=flow
    for n in range(3): result,body=feedback(flow,n)
    identifier=result['lernen']['proposal_id']
    detail=client.get(f'/api/v1/procedures/{identifier}').json()
    assert len(detail['corrections'])==3
    assert all(item['correction']==CORRECTION and item['conversation_id'] for item in detail['corrections'])
    client.post('/api/v1/rueckmeldungen',json={**body,'arbeitsweise':False})
    assert client.get(f'/api/v1/procedures/{identifier}').json()['corrections']==[]
