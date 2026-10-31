import json
from datetime import datetime, timezone
import pytest
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _conversation, _ask
from tests.test_conversation_retraction import _close_app
from tests.test_source_selection_pages import Script
from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory import working_memory_answers as wma
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_analysis import _blocks

Q='Welche Angaben gelten?'

def seed(ep, participants=None):
    originals=[]
    for n in range(6):
        body='\n\n'.join(f'Angaben gelten für Kalkulation {n}, Absatz {i}: NICHT erledigt. '
                         +'Unveränderte künstliche Bedingung. '*18 for i in range(2))
        episode,_=ep.record(EpisodeKind.MESSAGE,f'Kalkulation {n}',body,
            Provenance(SourceType.EMAIL,source_ref=f'synthetic:{n}'),
            participants=participants if participants is not None else [f'Person {n} <person{n}@example.invalid>'],
            occurred_at=datetime(2026,10,31,tzinfo=timezone.utc))
        originals.append(episode)
        assert WorkingMemoryStore(ep).commit(ep.support_snapshot(episode.id),
            [{'start':s,'end':e,'kind':'fact'} for s,e in _blocks(body)],model='synthetic')
    return originals

@pytest.mark.parametrize('final_mode',['reports','person_union','scope_union'])
def test_paged_uncertainty_keeps_whole_union_through_saved_api_and_click(core,tmp_path,monkeypatch,final_mode):
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        originals=seed(ep)
        def reply(n,page):
            if n==1: return {'status':'source_reports','ids':[page[-1]['id']]}
            if n==2: return {'status':'needs_person_choice','ids':[page[-1]['id']]}
            return {'status':{'reports':'source_reports','person_union':'needs_person_choice',
                              'scope_union':'needs_project_choice'}[final_mode],
                    'ids':[page[0]['id']] if final_mode=='reports' else [r['id'] for r in page]}
        provider=Script(monkeypatch,reply)
        answer=wma.prepare(Q,ep,claims,provider,semantic_search=None)
        assert len(provider.calls)==3
        pages=[[r['id'] for r in rows] for rows,_ in provider.calls]
        expected='working_unclear' if final_mode in {'reports','person_union'} else 'working_selection_failed'
        text,links,status=wma.render(answer,ep,claims)
        assert status==expected
        if final_mode in {'reports','person_union'}:
            assert answer['uncertainty']=='person' and len(answer['refs'])==len(links)==2
            assert 'Welche der genannten Personen meinst du?' in text
        else:
            assert answer['refs']==links==[] and 'Bitte erneut fragen' in text
        conversation=_conversation(client)
        turn=app.state.agent._working_turn(Q,answer,model_called=True)
        app.state.conversations.add_message(conversation,'assistant',turn.reply,metadata={'context':turn.context})
        projected=client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert projected['metadata']['context']['answer_contract']['status']==expected
        assert projected['metadata']['context']['source_links']==links
        assert len(provider.calls)==3
        print(json.dumps({'mode':final_mode,'pages':pages,'answer':answer['status'],
                          'uncertainty':answer['uncertainty'],'api':expected,'links':len(links),
                          'text_chars':len(text),'choices':len(projected['metadata']['context'].get('clarification_choices',[]))}))
        if final_mode in {'reports','person_union'}:
            options=projected['metadata']['context']['clarification_choices']
            separate=_conversation(client)
            app.state.conversations.add_message(separate,'assistant',turn.reply,metadata={'context':turn.context})
            chosen=client.post(f'/api/v1/conversations/{separate}/messages',json={'message':options[0]['label'],'clarification_choice':0})
            assert chosen.status_code==201
            assert chosen.json()['messages'][-1]['metadata']['context']['answer_contract']['status']=='working_reports'
            assert len(provider.calls)==3
            ep.ignore(answer['refs'][-1]['episode_id'])
            withdrawn=client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
            assert withdrawn['metadata']['context']['answer_contract']['status']=='working_unavailable'
            assert withdrawn['metadata']['context']['source_links']==[]
            assert len(provider.calls)==3
        assert all(ep.get(e.id).body==e.body for e in originals)
    finally:
        client.close();_close_app(app)

@pytest.mark.parametrize('projection',['nichts','zitate'])
def test_unsuccessful_sentence_attempt_is_compact_but_original_remains_accessible(core,tmp_path,monkeypatch,projection):
    from tests.test_satzantwort import Skript
    app,client,api_provider=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        body='\n\n'.join(f'Allgemeine Formularinformation zur Kalkulation {i}: '
                         +'Die Freigabe liegt noch nicht vor. '*12 for i in range(12))
        source,_=ep.record(EpisodeKind.MESSAGE,'Kalkulation',body,Provenance(SourceType.EMAIL,source_ref='synthetic:long'))
        assert WorkingMemoryStore(ep).commit(ep.support_snapshot(source.id),
            [{'start':s,'end':e,'kind':'fact'} for s,e in _blocks(body)],model='synthetic')
        def reply(payload):
            key='originalstellen' if any('originalsaetze' in b for b in payload['belege']) else 'saetze'
            return {'status':'nichts_vorliegend' if projection=='nichts' else 'unklar',key:[]}
        provider=Skript(reply)
        api_provider.complete_json=provider.complete_json
        app.state.agent._working_memory_search=None
        app.state.agent._saetze=True
        conversation=_conversation(client)
        revision=claims.revision
        message=_ask(client,conversation,'Was ist zur Kalkulation bekannt?')
        calls=(len(provider.auswahlen),len(provider.satzanfragen))
        answer=message['metadata']['context']['working_answer']
        text,links,status=wma.render(answer,ep,claims)
        assert answer['satzantwort']['status']==projection
        assert status=='working_reports' and body not in text and links[0]['episode_id']==source.id
        assert len(text)<1000 and 'nicht verlässlich beantworten' in text
        assert message['content']==text and message['metadata']['context']['source_links']==links
        saved=client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert body not in saved['content'] and saved['metadata']['context']['source_links']==links
        assert len(saved['content'])<1000
        original=client.get(f'/api/v1/episodes/{source.id}')
        assert original.status_code==200 and original.json()['body']==body
        assert 'keine Information' not in saved['content']
        ep.ignore(source.id)
        withdrawn=client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert withdrawn['metadata']['context']['answer_contract']['status']=='working_unavailable'
        assert withdrawn['metadata']['context']['source_links']==[]
        assert ep.get(source.id).body==body and claims.revision==revision
        assert (len(provider.auswahlen),len(provider.satzanfragen))==calls
        print(json.dumps({'projection':projection,'body_chars':len(body),'api_chars':len(saved['content']),
                          'links':len(links),'selection_calls':len(provider.auswahlen),'sentence_calls':len(provider.satzanfragen)}))
    finally:
        client.close();_close_app(app)


def test_recovered_time_uncertainty_cannot_become_report_or_invent_a_date_question(core,tmp_path,monkeypatch):
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        seed(ep)  # All source dates are known; no unresolved relative date occurs.
        provider=Script(monkeypatch,lambda n,page:{
            'status':'needs_missing_time_reference' if n==2 else 'source_reports',
            'ids':[page[-1]['id']]})
        answer=wma.prepare(Q,ep,claims,provider,semantic_search=None)
        text,links,status=wma.render(answer,ep,claims)
        assert status=='working_selection_failed' and links==[]
        assert 'Von wann stammt' not in text
        assert len(provider.calls)==3
    finally:
        client.close();_close_app(app)


def test_only_unclear_page_with_known_time_cannot_become_report(core,tmp_path,monkeypatch):
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        seed(ep)  # Six dated sources; the second page finds nothing relevant.
        provider=Script(monkeypatch,lambda n,page:{
            'status':'needs_missing_time_reference' if n==1 else 'no_relevant_sources',
            'ids':[page[-1]['id']] if n==1 else []})
        answer=wma.prepare(Q,ep,claims,provider,semantic_search=None)
        text,links,status=wma.render(answer,ep,claims)
        assert len(provider.calls)==2
        assert status=='working_selection_failed' and links==[]
        assert answer['refs']==[] and 'Von wann stammt' not in text
    finally:
        client.close();_close_app(app)


@pytest.mark.parametrize('change',['drop','add','different_uncertainty'])
def test_recovered_union_cannot_survive_changed_post_guard_result(core,tmp_path,monkeypatch,change):
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        seed(ep)
        provider=Script(monkeypatch,lambda n,page:{
            'status':'needs_person_choice' if n==2 else 'source_reports',
            'ids':[page[-1]['id']]})
        original=wma.working_memory_focus.adjust
        def changed(question,rows,ids,status):
            ids,status=original(question,rows,ids,status)
            if change=='drop': return ids[:-1],status
            if change=='add': return [*ids,'S1'],status
            return ids,'conflict'
        monkeypatch.setattr(wma.working_memory_focus,'adjust',changed)
        answer=wma.prepare(Q,ep,claims,provider,semantic_search=None)
        assert wma.render(answer,ep,claims)[2]=='working_selection_failed'
        assert answer['refs']==[] and len(provider.calls)==3
    finally:
        client.close();_close_app(app)


@pytest.mark.parametrize('attempt',[None,{'version':-1,'status':'zitate'}])
def test_unattempted_or_obsolete_sentence_mode_keeps_explicit_originals(core,tmp_path,monkeypatch,attempt):
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        seed(ep)
        provider=Script(monkeypatch,lambda n,page:{'status':'source_reports','ids':[page[-1]['id']]})
        answer=wma.prepare(Q,ep,claims,provider,semantic_search=None)
        if attempt is not None: answer['satzantwort']=attempt
        text,links,status=wma.render(answer,ep,claims)
        assert status=='working_reports' and links
        assert all(ep.get(link['episode_id']).body in text for link in links)
    finally:
        client.close();_close_app(app)


def test_compact_automatic_projection_never_hides_confirmed_claim_basis(core,tmp_path,monkeypatch):
    from icarus_memory import satzantwort
    from tests.test_satzantwort import Skript
    agent,_,_,_,accept=core
    claim,source=accept('person:synthetic','Angaben gelten zur Kalkulation: Die Freigabe fehlt.')
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep=app.state.episodes
        seed(ep)  # Automatic reports coexist with the separately confirmed claim.
        answer=wma.prepare('Welche Angaben gelten zur Kalkulation?',ep,app.state.claims,Skript(),semantic_search=None)
        assert answer['claim_basis']
        answer['satzantwort']={'version':satzantwort.SATZ_VERSION,'status':'zitate','grund':'Synthetischer alter Versuch'}
        text,links,_=wma.render(answer,app.state.episodes,app.state.claims,conflict_status=lambda _: 'clear')
        assert claim.statement in text and any(link['episode_id']==source.id for link in links)
        assert 'noch nicht verlässlich beantworten' not in text
    finally:
        client.close();_close_app(app)


@pytest.mark.parametrize('participants', [[], ['Robin <robin@example.invalid>']])
def test_person_uncertainty_without_distinguishing_choices_stays_compact(core,tmp_path,monkeypatch,participants):
    app,client,_=_api(core,tmp_path,monkeypatch)
    try:
        ep,claims=app.state.episodes,app.state.claims
        originals=seed(ep,participants=participants)
        provider=Script(monkeypatch,lambda n,page:{
            'status':'needs_person_choice' if n==2 else 'source_reports',
            'ids':[page[-1]['id']] if n<3 else [page[0]['id']]})
        answer=wma.prepare(Q,ep,claims,provider,semantic_search=None)
        assert answer['status']=='unclear' and answer['uncertainty']=='person'
        assert len(answer['refs'])==2 and wma.choices(answer,ep)==[]
        text,links,status=wma.render(answer,ep,claims)
        assert status=='working_unclear' and len(links)==2
        assert 'Welche der genannten Personen' not in text
        assert 'nicht verlässlich beantworten' in text and len(text)<1000
        assert all(e.body not in text for e in originals)
        conversation=_conversation(client)
        turn=app.state.agent._working_turn(Q,answer,model_called=True)
        app.state.conversations.add_message(conversation,'assistant',turn.reply,metadata={'context':turn.context})
        saved=client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert saved['content']==text and saved['metadata']['context']['source_links']==links
        assert 'clarification_choices' not in saved['metadata']['context']
        for source in originals:
            response=client.get(f'/api/v1/episodes/{source.id}')
            assert response.status_code==200 and response.json()['body']==source.body
        ep.ignore(answer['refs'][-1]['episode_id'])
        withdrawn=client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert withdrawn['metadata']['context']['answer_contract']['status']=='working_unavailable'
        assert withdrawn['metadata']['context']['source_links']==[]
        assert len(provider.calls)==3
    finally:
        client.close();_close_app(app)
