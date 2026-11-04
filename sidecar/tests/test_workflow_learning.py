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
# Unveränderte Form der zweiten echten Qwen-Probe: nominale Trigger und ein
# Positivbeispiel, das unser Router nicht als tatsächlichen Mailauftrag erkennt.
QWEN_NOMINAL_SPEC = {'name':'zunft-mail-erstellung', 'title':'Vorgehen zur Erstellung von Mails für die Zunft',
    'description':'Dieser Ablauf regelt die Erstellung von Mails für die Zunft, um Fehlsendungen zu vermeiden.',
    'area':'mail', 'triggers':['Erstellung einer Mail für die Zunft','Entwurf einer Mail für die Zunft','Schreiben einer Mail für die Zunft'],
    'steps':['Prüfe den Anlass der Mail.','Prüfe die Empfänger der Mail.','Schreibe den Entwurf der Mail.','Gegenlese den Entwurf.'],
    'positive':'Nutzerauftrag zur Erstellung einer Mail für die Zunft.',
    'negative':'Auftrag zur Erstellung einer Mail für eine andere Organisation.'}


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


@pytest.mark.parametrize('change',['accept','revoke'])
def test_skill_catalog_changes_during_synthesis_invalidate_old_draft(flow,change):
    app,_,p=flow; store=app.state.procedures
    old=store.accept(store.propose(spec())['id'])
    feedback(flow,1); feedback(flow,2)
    def during():
        if change=='revoke': store.revoke(old['id'])
        else: store.accept(store.propose({**spec(),'steps':['Vor dem Entwurf immer Zuständigkeit prüfen.']})['id'])
    p.during=during
    result,_=feedback(flow,3)
    assert result['lernen']['status']!='proposed'
    assert not [item for item in store.items() if item['request_key'].startswith('corrections-v1:')]


def test_conversation_readback_preserves_workflow_consent_and_proposal_without_model(flow):
    app,client,p=flow
    for n in range(3): result,body=feedback(flow,n)
    identifier=result['lernen']['proposal_id']; calls=len(p.seen)
    messages=client.get('/api/v1/conversations/'+body['conversation_id']).json()['messages']
    saved=next(m for m in messages if m['id']==body['message_id'])['metadata']['workflow_feedback']
    assert saved['arbeitsweise'] is True and saved['richtig']==CORRECTION
    assert saved['lernen']['proposal_id']==identifier
    assert len(p.seen)==calls
    client.post('/api/v1/rueckmeldungen',json={**body,'arbeitsweise':False})
    messages=client.get('/api/v1/conversations/'+body['conversation_id']).json()['messages']
    assert next(m for m in messages if m['id']==body['message_id'])['metadata']['workflow_feedback']['arbeitsweise'] is False


def test_withdraw_by_identifier_preserves_note_and_invalidates_proposal_idempotently(flow):
    app,client,p=flow
    for n in range(3): result,body=feedback(flow,n)
    identifier=result['meldung']['id']; proposal=result['lernen']['proposal_id']; calls=len(p.seen)
    note=app.state.rueckmeldungen.hole(identifier)
    for _ in range(2):
        assert client.post(f'/api/v1/rueckmeldungen/{identifier}/arbeitsweise-zuruecknehmen').status_code==200
    after=app.state.rueckmeldungen.hole(identifier)
    assert after['richtig']==note['richtig'] and after['frage']==note['frage'] and after['workflow']=={}
    assert client.post(f'/api/v1/procedures/{proposal}/accept').status_code==409
    assert client.post('/api/v1/rueckmeldungen/missing/arbeitsweise-zuruecknehmen').status_code==404
    assert len(p.seen)==calls


def test_withdrawn_conversation_evidence_is_not_rehydrated_as_feedback_text(flow):
    app,client,_=flow
    result,body=feedback(flow,1)
    # Nachträglich geänderte Quellenbindung macht die ursprüngliche Lernableitung ungültig.
    app.state.conversations.replace_source_lineage(body['message_id'],[{'episode_id':'missing-source'}])
    messages=client.get('/api/v1/conversations/'+body['conversation_id']).json()['messages']
    saved=next(m for m in messages if m['id']==body['message_id'])['metadata']['workflow_feedback']
    assert saved['richtig']=='' and saved['arbeitsweise'] is True
    assert saved['lernen']['status']=='changed'


@pytest.mark.parametrize('repaired',[True,False])
@pytest.mark.parametrize('incomplete',[None,QWEN_NOMINAL_SPEC])
def test_real_qwen_workflow_without_spec_gets_one_bounded_completion(flow,repaired,incomplete):
    app,_,p=flow
    from icarus_memory.providers import _JSON_DEADLINE
    deadlines=[]
    original=p.complete
    def complete(messages,tools):
        deadlines.append(_JSON_DEADLINE.get())
        answer=original(messages,tools)
        if len(p.seen)==1 or not repaired:
            data=json.loads(answer.text);data['spec']=incomplete
            return Reply(text=json.dumps(data))
        return answer
    p.complete=complete
    for n in range(3): result,_=feedback(flow,n)
    assert len(p.seen)==2
    assert deadlines[0] is not None and deadlines[0]==deadlines[1]
    assert result['lernen']['status']==('proposed' if repaired else 'unavailable')
    assert p.seen[0][-1]==p.seen[1][-1], 'Originalbelege bleiben unverändert'
    assert 'spec' in p.seen[1][0]['content'] and 'null' in p.seen[1][0]['content']
    assert len(app.state.procedures.items())==int(repaired)


def test_missing_spec_never_retries_after_permission_change(flow):
    app,_,p=flow;original=p.complete
    def complete(messages,tools):
        answer=original(messages,tools);data=json.loads(answer.text);data['spec']=None
        p.is_local=False
        return Reply(text=json.dumps(data))
    p.complete=complete
    for n in range(3):result,_=feedback(flow,n)
    assert len(p.seen)==1 and result['lernen']['status']=='unavailable'
    assert not app.state.procedures.items()


@pytest.mark.parametrize('corrections',[
    ['Prüfe die Frist: Abgabe ist am 7. November 2026, nicht am 8. November.',
     'Prüfe den Namen: Der Empfänger heißt Alex Berger, nicht Alex Winter.',
     'Prüfe den Termin: Die Sitzung findet am 12. November um 18 Uhr statt.'],
    ['Prüfe den Namen: Der Empfänger heißt Alex Berger, nicht Alex Winter.']*3,
    ['Prüfe die Frist: Abgabe ist morgen, nicht heute.']*3,
    ['Prüfe die Abgabefrist: morgen statt heute.']*3,
    ['Prüfe den Anlass der Mail.', 'Prüfe die Rechnungsnummer.', 'Prüfe die Anfahrt.'],
])
def test_concrete_or_unrelated_corrections_cannot_be_synthesized_into_workflow(flow,corrections):
    for n,text in enumerate(corrections):result,_=feedback(flow,n,correction=text)
    assert result['lernen']['status'] != 'proposed'
    assert not flow[2].seen, 'Ohne wiederholtes Verfahrensmerkmal keine Modellsynthese'
    assert not flow[0].state.procedures.items()


@pytest.mark.parametrize('detail',[
    'Prüfe die Frist: Abgabe ist am 7. November 2026.',
    'Prüfe den Namen: Der Empfänger heißt Alex Berger.',
    'Prüfe den Empfänger: alex@example.invalid.',
])
def test_synthesized_concrete_facts_never_become_a_workflow(flow,detail):
    original=flow[2].complete
    def complete(messages,tools):
        answer=original(messages,tools);data=json.loads(answer.text)
        data['spec']['steps']=[detail]
        return Reply(text=json.dumps(data))
    flow[2].complete=complete
    for n in range(3):result,_=feedback(flow,n)
    assert result['lernen']['status']=='unavailable'
    assert not flow[0].state.procedures.items()


def test_repeated_workflow_with_generic_numeric_check_remains_eligible(flow):
    for n in range(3):result,_=feedback(flow,n,correction='Bitte mindestens 2 Belege prüfen und danach vergleichen.')
    assert result['lernen']['status']=='proposed'


@pytest.mark.parametrize('state',['pending','active'])
def test_legacy_factual_skill_is_not_reused_accepted_or_selected(flow,monkeypatch,state):
    from icarus_memory import procedures
    from icarus_memory.workflow_learning import PREFIX,dependency,review,_hash
    app,client,p=flow;p.is_local=False;records=[]
    for n in range(3):
        result,_=feedback(flow,n);records.append(result['meldung'])
    sources={PREFIX+r['id']:dependency(app,PREFIX+r['id']) for r in records}
    key='corrections-v1:'+_hash(sources)
    # Alter persistierter Stand, damals noch ohne Inhaltsgrenze.
    with monkeypatch.context() as previous:
        previous.setattr(procedures,'has_concrete_values',lambda data:False,raising=False)
        old=app.state.procedures.propose({**spec(), 'steps':['Der Empfänger heißt Alex Berger.']},
            sources=sources,request_key=key)
        if state=='active':app.state.procedures.accept(old['id'])
    app.state.rueckmeldungen.save_workflow_result(key,{'status':'proposed','proposal_id':old['id']})
    p.is_local=True
    result=review(app,records[-1])
    assert result.get('proposal_id')!=old['id'] or result['status']=='changed'
    assert app.state.procedures.get(old['id'])['current'] is False
    assert client.post('/api/v1/procedures/'+old['id']+'/accept').status_code==409
    assert not app.state.procedures.select('Schreibe eine Mail für die Zunft.',area='mail')['contextual']
    assert 'Alex Berger' in app.state.procedures.export(old['id']), 'Historie bleibt erhalten'
