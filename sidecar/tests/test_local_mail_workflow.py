"""Synthetische Offline-Mail: Quellenbindung, ausdrückliche Übernahme und Fehler."""
from datetime import datetime, timezone
from types import SimpleNamespace
import json
import threading
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalStore
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from icarus_memory.workspace_views import WorkspaceViews
from icarus_memory.providers import Reply, ProviderError

@pytest.fixture
def env(tmp_path, monkeypatch):
    from icarus_memory import local_mail_workflow as workflow
    app = FastAPI()
    stores = [EpisodeStore(tmp_path/'episodes.sqlite3'), ProposalStore(tmp_path/'proposals.sqlite3'),
              TaskStore(tmp_path/'tasks.json'), WorkspaceStore(tmp_path/'workspace.sqlite3'), WorkspaceViews(tmp_path/'views.sqlite3')]
    for key, value in zip(('episodes','proposals','tasks','workspace','workspace_views'), stores):
        setattr(app.state,key,value)
    app.state.conversation_lock = threading.Lock()
    app.state.settings = SimpleNamespace(mail_accounts=[], mail_sync_status={})
    app.state.mail = SimpleNamespace(message=lambda *_: pytest.fail('provider read'))
    calls=[]
    def complete(messages, **kwargs):
        calls.append(messages)
        content=json.loads(messages[-1]['content'])
        if 'passages' in content:
            return Reply(text=json.dumps({'passages':[0], 'tasks':[]}))
        if 'candidates' in content:
            return Reply(text=json.dumps({'reviews':[{'id':i,'kind':'request_to_recipient','title_supported':True} for i,_ in enumerate(content['candidates'])]}))
        return Reply(text=json.dumps({'items':[{'title':'Belege prüfen','quote':content['body']}]}))
    provider=SimpleNamespace(name='test',model='local',base_url='local',is_local=True,complete_json=complete)
    monkeypatch.setattr(workflow,'_provider',lambda _:provider)
    monkeypatch.setattr(workflow.local_model_guard,'VerifiedLocalProvider',lambda p,**_:p)
    monkeypatch.setattr(workflow.local_model_guard,'verify_local_model',lambda p: SimpleNamespace(name='local',digest='a'*64))
    workflow.register(app,[])
    source=app.state.episodes.record(EpisodeKind.MESSAGE,'Belege','Bitte prüfe die Belege.',Provenance(source_type=SourceType.EMAIL),occurred_at=datetime(2020,1,1,tzinfo=timezone.utc),participants=['Anna'])[0]
    with TestClient(app) as client:
        yield app,client,source,calls,provider
    for store in stores:
        if hasattr(store,'close'): store.close()

def root(source): return f'/api/v1/local-mail/{source.id}/workflow'
def prepare(client,source):
    response=client.post(root(source)+'/prepare',json={})
    assert response.status_code==200,response.text
    return response.json()
def accept_payload(result,item,**kwargs):
    return {'fingerprint':result['fingerprint'],'source_digest':result['source_digest'],'title':'Belege prüfen',**kwargs}

def test_get_never_calls_model_or_provider_and_preparation_reuses_result(env):
    app,client,source,calls,_=env
    initial=client.get(root(source))
    assert initial.status_code==200
    assert initial.json()['status']=='unprepared' and calls==[]
    result=prepare(client,source)
    assert result['quotes']==[source.body] and len(result['items'])==1
    count=len(calls)
    assert client.get(root(source)).json()['quotes']==[source.body]
    assert prepare(client,source)['quotes']==[source.body] and len(calls)==count
    assert len(app.state.episodes.all_episodes())==1

def test_historical_suggestion_has_no_inferred_due_owner_and_joint_project_is_idempotent(env):
    app,client,source,_,_=env
    result=prepare(client,source); item=result['items'][0]
    assert item['review_required'] is True and result['temporal_status']=='old'
    payload=accept_payload(result,item,new_project_name='Belege')
    url=root(source)+f"/tasks/{item['id']}/accept"
    saved=client.post(url,json=payload)
    assert saved.status_code==200,saved.text
    task=saved.json()
    assert task['due'] is None and not task['wartet_auf'] and task['project_id']
    again=client.post(url,json={**payload,'title':'Nicht überschreiben'})
    assert again.json()==task and len(app.state.tasks.all_tasks())==1
    assert len(app.state.workspace.projects())==1

def test_excluded_source_and_changed_user_context_invalidate_preparation(env):
    app,client,source,_,_=env
    result=prepare(client,source); item=result['items'][0]
    app.state.episodes.ignore(source.id)
    assert client.get(root(source)).status_code==409
    assert client.post(root(source)+f"/tasks/{item['id']}/accept",json=accept_payload(result,item)).status_code==409
    assert app.state.tasks.all_tasks()==[]

def test_source_context_changed_during_model_call_cannot_publish(env):
    app,client,source,_,provider=env
    original=provider.complete_json
    def changed(*args,**kwargs):
        reply=original(*args,**kwargs)
        app.state.episodes.ignore(source.id)
        return reply
    provider.complete_json=changed
    assert client.post(root(source)+'/prepare',json={}).status_code==409
    assert app.state.workspace_views.count('saved_mail_briefing')==0
    assert app.state.tasks.all_tasks()==[]

def test_failed_model_retry_keeps_original_and_creates_no_task(env):
    app,client,source,_,provider=env
    provider.complete_json=lambda *_a,**_k: (_ for _ in ()).throw(ProviderError('failed'))
    response=client.post(root(source)+'/prepare',json={})
    assert response.status_code==200 and response.json()['status']=='unavailable'
    assert app.state.episodes.get(source.id).body==source.body
    assert app.state.tasks.all_tasks()==[]

def test_strict_cache_and_dismissal_validation(env):
    app,_,_,_,_=env
    views=app.state.workspace_views
    assert views.put('organisation_group_dismissal','f'*64,{'dismissed':True},0)['data']=={'dismissed':True}
    for identifier,data in [('F'*64,{'dismissed':True}),('f'*64,{'dismissed':False}),('a'*64,{'dismissed':True,'secret':'x'})]:
        with pytest.raises(ValueError): views.put('organisation_group_dismissal',identifier,data,0)

def test_user_reassignment_invalidates_prepared_view_and_old_confirmation(env):
    app,client,source,calls,_=env
    result=prepare(client,source); item=result['items'][0]
    project=app.state.workspace.add_project('Anderes Projekt',Provenance(source_type=SourceType.USER_STATED))
    app.state.episodes.link_project(source.id,project.id)
    fresh=client.get(root(source)).json()
    assert fresh['status']=='unprepared' and fresh['quotes']==[]
    assert fresh['fingerprint']!=result['fingerprint']
    assert client.post(root(source)+f"/tasks/{item['id']}/accept",json=accept_payload(result,item)).status_code==409
    assert app.state.tasks.all_tasks()==[]

def test_closed_project_rejected_in_joint_confirmation(env):
    from icarus_memory.workspace import ProjectStatus
    app,client,source,_,_=env
    project=app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    result=prepare(client,source);item=result['items'][0]
    app.state.workspace.update_project(project.id,status=ProjectStatus.DONE)
    response=client.post(root(source)+f"/tasks/{item['id']}/accept",json=accept_payload(result,item,project_id=project.id))
    assert response.status_code==409,response.text
    assert app.state.tasks.all_tasks()==[]
    assert client.get(root(source)).json()['projects']==[]

def test_foreign_commitments_and_cancelled_requests_are_not_current_own_tasks(env):
    app,client,source,_,provider=env
    original=provider.complete_json
    def foreign(messages,**kwargs):
        data=json.loads(messages[-1]['content'])
        if 'candidates' in data:
            return Reply(text=json.dumps({'reviews':[{'id':i,'kind':'other_person','title_supported':True} for i,_ in enumerate(data['candidates'])]}))
        return original(messages,**kwargs)
    provider.complete_json=foreign
    result=prepare(client,source)
    assert result['quotes']==[source.body] and result['items']==[]
    assert app.state.tasks.all_tasks()==[]

def test_interrupted_confirmation_recovers_task_and_project_without_rewriting(env,monkeypatch):
    app,client,source,_,_=env
    result=prepare(client,source);item=result['items'][0]
    original=app.state.proposals.accept
    monkeypatch.setattr(app.state.proposals,'accept',lambda *_a,**_k: (_ for _ in ()).throw(RuntimeError('abbruch')))
    url=root(source)+f"/tasks/{item['id']}/accept";payload=accept_payload(result,item,new_project_name='Prüfung')
    with pytest.raises(RuntimeError): client.post(url,json=payload)
    assert len(app.state.tasks.all_tasks())==1 and len(app.state.workspace.projects())==1
    monkeypatch.setattr(app.state.proposals,'accept',original)
    task=app.state.tasks.all_tasks()[0].to_dict()
    app.state.episodes.ignore(source.id)
    assert client.post(url,json={**payload,'title':'Nicht überschreiben'}).json()==task
    assert len(app.state.tasks.all_tasks())==1 and len(app.state.workspace.projects())==1

def test_failed_semantic_review_does_not_cache_success(env):
    app,client,source,_,provider=env
    original=provider.complete_json
    def fail_review(messages,**kwargs):
        if 'candidates' in json.loads(messages[-1]['content']): raise ProviderError('review failed')
        return original(messages,**kwargs)
    provider.complete_json=fail_review
    assert prepare(client,source)['status']=='unavailable'
    assert app.state.workspace_views.count('saved_mail_briefing')==0
    provider.complete_json=original
    assert prepare(client,source)['status']=='ready'

def test_background_limit_and_false_permission_do_not_touch_model(env):
    from icarus_memory.local_mail_workflow import prepare_background
    app,client,source,calls,provider=env
    assert prepare_background(app,provider,permitted=lambda:False)==0 and calls==[]
    assert prepare_background(app,provider,limit=1)==1
    count=len(calls)
    assert prepare_background(app,provider,limit=1)==0 and len(calls)==count

def test_guard_precedes_saved_source_reads():
    from fastapi import Depends,HTTPException
    from icarus_memory.local_mail_workflow import register
    app=FastAPI()
    def deny(): raise HTTPException(403,'denied')
    register(app,[Depends(deny)])
    with TestClient(app) as client:
        assert client.get('/api/v1/local-mail/x/workflow').status_code==403
        assert client.post('/api/v1/local-mail/x/workflow/prepare',json={}).status_code==403
        assert client.post('/api/v1/local-mail/x/workflow/tasks/v/accept',json={'title':'Prüfen','fingerprint':'a'*64,'source_digest':'sha256:'+'b'*64}).status_code==403

def test_cache_cannot_be_read_or_written_through_generic_view_api(tmp_path):
    from icarus_memory.workspace_views import register
    app=FastAPI();register(app,[],lambda:tmp_path)
    with TestClient(app) as client:
        for kind in ('saved_mail_briefing','organisation_group_dismissal'):
            url=f'/api/v1/workspace-view/{kind}/'+ 'f'*64
            assert client.get(url).status_code==422
            assert client.put(url,json={'revision':0,'data':{}}).status_code==422
            assert client.post(url+'/undo',json={'revision':0}).status_code==422
        overview=client.get('/api/v1/workspace-view').json()
        assert 'saved_mail_briefing' not in overview and 'organisation_group_dismissal' not in overview
    app.state.workspace_views.close()

def test_source_bound_project_hint_is_prepared_in_explicit_single_source_action(env):
    app,client,source,_,provider=env
    project=app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    original=provider.complete_json
    def project_hint(messages,**kwargs):
        data=json.loads(messages[-1]['content'])
        if 'projects' in data:
            return Reply(text=json.dumps({'project_id':project.id,'new_project_name':None,'reason':'Belege werden im Projekt geprüft.','quote':source.body}))
        return original(messages,**kwargs)
    provider.complete_json=project_hint
    result=prepare(client,source)
    assert result['items'][0]['project_suggestion']['project_id']==project.id
    assert app.state.workspace_views.count('project_hint')==1
    assert app.state.workspace.projects()[0].id==project.id
    assert app.state.tasks.all_tasks()==[]

def test_running_other_analysis_is_not_marked_successfully_prepared(env):
    app,client,source,_,provider=env
    # Derselbe vorhandene Lease verhindert doppelte konkurrierende Detektorarbeit.
    app.state.proposals.memory_analysis.acquire(source,provider,context=__import__('icarus_memory.task_review',fromlist=['current_task_context']).current_task_context(app.state.episodes,source.id))
    assert prepare(client,source)['status']=='unavailable'
    assert app.state.workspace_views.count('saved_mail_briefing')==0

def test_strict_cache_rejects_unknown_or_unbounded_shapes(env):
    app,_,_,_,_=env
    good={'fingerprint':'a'*64,'source_digest':'sha256:'+'b'*64,'status':'ready','quotes':['Bitte prüfen.']}
    for data in ({**good,'status':'evil'}, {**good,'quotes':['x']*4}, {**good,'quotes':['x'*1201]}, {**good,'extra':'secret'}, {**good,'fingerprint':'bad'}):
        with pytest.raises(ValueError): app.state.workspace_views.put('saved_mail_briefing','a'*64,data,0)

def test_replaced_original_version_cannot_be_confirmed(env):
    app,client,_,_,_=env
    original=app.state.episodes.record(EpisodeKind.MESSAGE,'Belege','Bitte prüfe alte Belege.',Provenance(source_type=SourceType.EMAIL),source_key='mail:test-version')[0]
    app.state.episodes.advance_source_head('mail:test-version',None,original.id)
    result=prepare(client,original);item=result['items'][0]
    changed=app.state.episodes.record(EpisodeKind.MESSAGE,'Belege','Bitte prüfe neue Belege.',Provenance(source_type=SourceType.EMAIL),source_key='mail:test-version')[0]
    app.state.episodes.advance_source_head('mail:test-version',original.id,changed.id)
    assert client.get(root(original)).status_code==409
    assert client.post(root(original)+f"/tasks/{item['id']}/accept",json=accept_payload(result,item)).status_code==409
    assert app.state.episodes.get(original.id).body=='Bitte prüfe alte Belege.'
    assert app.state.tasks.all_tasks()==[]

def test_model_configuration_switch_discards_result(env):
    app,client,source,_,provider=env
    original=provider.complete_json
    def switched(messages,**kwargs):
        result=original(messages,**kwargs);provider.model='different';return result
    provider.complete_json=switched
    assert client.post(root(source)+'/prepare',json={}).status_code==409
    assert app.state.workspace_views.count('saved_mail_briefing')==0
    assert app.state.tasks.all_tasks()==[]

def test_incomplete_original_produces_only_original_excerpts(env):
    app,client,_,calls,_=env
    source=app.state.episodes.record(EpisodeKind.MESSAGE,'Ausschnitt','Bitte prüfe die weiteren Belege.',Provenance(source_type=SourceType.EMAIL),tags=['source:truncated'])[0]
    result=prepare(client,source)
    assert result['status']=='incomplete' and result['quotes']==[source.body] and result['items']==[]
    assert len(calls)==1 and app.state.tasks.all_tasks()==[]

def test_failed_project_hint_is_visible_and_retry_reuses_successful_source_work(env):
    app,client,source,calls,provider=env
    project=app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    original=provider.complete_json;project_calls=[]
    def retryable(messages,**kwargs):
        data=json.loads(messages[-1]['content'])
        if 'projects' in data:
            project_calls.append(data)
            if len(project_calls)==1: raise ProviderError('Projektprüfung fehlt')
            return Reply(text=json.dumps({'project_id':project.id,'new_project_name':None,'reason':'Belege prüfen','quote':source.body}))
        return original(messages,**kwargs)
    provider.complete_json=retryable
    first=prepare(client,source)
    assert first['status']=='ready'
    assert first['project_preparation_status']=='unavailable'
    source_calls=len(calls)
    listed=client.get(root(source)).json()
    assert listed['project_preparation_status']=='unprepared' and len(project_calls)==1
    second=prepare(client,source)
    assert second['items'][0]['project_suggestion']['project_id']==project.id
    assert second['project_preparation_status']=='ready'
    assert len(calls)==source_calls and len(project_calls)==2
    assert prepare(client,source)['project_preparation_status']=='ready'
    assert len(calls)==source_calls and len(project_calls)==2

def test_stale_project_hint_retries_only_hint_after_project_inventory_change(env):
    app,client,source,calls,provider=env
    first_project=app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    original=provider.complete_json;project_calls=[]
    def hints(messages,**kwargs):
        data=json.loads(messages[-1]['content'])
        if 'projects' in data:
            project_calls.append(data)
            return Reply(text=json.dumps({'project_id':first_project.id,'new_project_name':None,'reason':'Belege prüfen','quote':source.body}))
        return original(messages,**kwargs)
    provider.complete_json=hints
    first=prepare(client,source);source_calls=len(calls)
    app.state.workspace.add_project('Weiteres Projekt',Provenance(source_type=SourceType.USER_STATED))
    stale=client.get(root(source)).json()
    assert stale['status']=='ready' and stale['project_preparation_status']=='unprepared'
    assert stale['items'][0]['project_suggestion'] is None
    second=prepare(client,source)
    assert second['items'][0]['project_suggestion']['project_id']==first_project.id
    assert len(calls)==source_calls and len(project_calls)==2

def test_ambiguous_project_checkpoint_is_complete_without_repeated_model_work(env):
    app,client,source,calls,provider=env
    app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    original=provider.complete_json;hint_calls=[]
    def ambiguous(messages,**kwargs):
        data=json.loads(messages[-1]['content'])
        if 'projects' in data:
            hint_calls.append(data)
            return Reply(text=json.dumps({'project_id':None,'new_project_name':None,'reason':'Mehrdeutig','quote':source.body}))
        return original(messages,**kwargs)
    provider.complete_json=ambiguous
    first=prepare(client,source);count=len(calls)
    assert first['project_preparation_status']=='ready' and first['items'][0]['project_suggestion'] is None
    second=prepare(client,source)
    assert second['project_preparation_status']=='ready' and len(calls)==count and len(hint_calls)==1

def test_background_retries_failed_hint_within_permission_and_budget(env):
    from icarus_memory.local_mail_workflow import prepare_background
    app,client,source,calls,provider=env
    project=app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    original=provider.complete_json;hint_calls=[]
    def hints(messages,**kwargs):
        data=json.loads(messages[-1]['content'])
        if 'projects' in data:
            hint_calls.append(data)
            if len(hint_calls)==1: raise ProviderError('retry')
            return Reply(text=json.dumps({'project_id':project.id,'new_project_name':None,'reason':'Belege','quote':source.body}))
        return original(messages,**kwargs)
    provider.complete_json=hints
    assert prepare(client,source)['project_preparation_status']=='unavailable'
    count=len(calls)
    assert prepare_background(app,provider,limit=1,permitted=lambda:False)==0
    assert len(hint_calls)==1
    assert prepare_background(app,provider,limit=1)==1
    assert client.get(root(source)).json()['project_preparation_status']=='ready'
    assert len(hint_calls)==2 and len(calls)==count
