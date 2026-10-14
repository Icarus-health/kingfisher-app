"""Echter create_app-Lockvertrag; Deadlocks scheitern begrenzt statt die Suite anzuhalten."""
import json
import threading
from types import SimpleNamespace
import pytest
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply, ProviderError
from icarus_memory.server import create_app
from icarus_memory.local_mail_workflow import SavedMailWorkflow, PrepareIn, AcceptIn


def bounded(call, timeout=2):
    """Der Daemon darf einen fehlerhaften echten Lock niemals die Suite blockieren lassen."""
    result=[];failed=[]
    def work():
        try: result.append(call())
        except BaseException as exc: failed.append(exc)
    thread=threading.Thread(target=work,daemon=True)
    thread.start();thread.join(timeout)
    assert not thread.is_alive(), 'Lokaler Mailablauf blockiert den nicht-reentranten Produktionslock.'
    if failed: raise failed[0]
    return result[0]


@pytest.fixture
def production(tmp_path,monkeypatch):
    from icarus_memory import local_mail_workflow as workflow
    monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
    app=create_app(SelfModelStore(MemoryBackend(),subject_id='synthetic-lock-test'))
    # Dies ist das von create_app tatsächlich angelegte Lock, kein Testersatz.
    assert type(app.state.conversation_lock) is type(threading.Lock())
    calls=[];failures={'project':False,'overview':False}
    project=app.state.workspace.add_project('Belege',Provenance(source_type=SourceType.USER_STATED))
    source=app.state.episodes.record(EpisodeKind.MESSAGE,'Belege','Bitte prüfe die Belege.',Provenance(source_type=SourceType.EMAIL))[0]
    def complete(messages,**kwargs):
        data=json.loads(messages[-1]['content']);calls.append(data)
        if 'passages' in data:
            if failures['overview']: raise ProviderError('synthetischer Fehler')
            return Reply(text=json.dumps({'passages':[0],'tasks':[]}))
        if 'projects' in data:
            if failures['project']: raise ProviderError('synthetischer Projektfehler')
            return Reply(text=json.dumps({'project_id':project.id,'new_project_name':None,'reason':'Belege prüfen','quote':source.body}))
        if 'candidates' in data:
            return Reply(text=json.dumps({'reviews':[{'id':0,'kind':'request_to_recipient','title_supported':True}]}))
        return Reply(text=json.dumps({'items':[{'title':'Belege prüfen','quote':source.body}]}))
    provider=SimpleNamespace(name='test',model='local',base_url='local',is_local=True,complete_json=complete)
    monkeypatch.setattr(workflow,'_provider',lambda _:provider)
    monkeypatch.setattr(workflow.local_model_guard,'VerifiedLocalProvider',lambda p,**_:p)
    monkeypatch.setattr(workflow.local_model_guard,'verify_local_model',lambda _:SimpleNamespace(name='local',digest='a'*64))
    def route(path):
        matches=[r.endpoint for r in app.routes if getattr(r,'path',None)==path]
        assert len(matches)==1,'create_app muss den Mailablauf genau einmal registrieren.'
        return matches[0]
    return app,source,provider,calls,failures,route


def test_real_create_app_initial_prepare_and_ready_cache_finish_with_nonreentrant_lock(production):
    app,source,provider,calls,_,route=production
    read=route('/api/v1/local-mail/{episode_id}/workflow')
    prepare=route('/api/v1/local-mail/{episode_id}/workflow/prepare')
    assert bounded(lambda:read(source.id))['status']=='unprepared'
    first=bounded(lambda:prepare(source.id,PrepareIn()))
    assert first['status']=='ready' and first['project_preparation_status']=='ready'
    count=len(calls)
    second=bounded(lambda:prepare(source.id,PrepareIn()))
    assert second['quotes']==first['quotes'] and len(calls)==count
    assert bounded(lambda:read(source.id))['items'][0]['id']==first['items'][0]['id']


def test_real_create_app_prepare_failure_and_project_retry_finish_with_nonreentrant_lock(production):
    app,source,provider,calls,failures,route=production
    prepare=route('/api/v1/local-mail/{episode_id}/workflow/prepare')
    failures['overview']=True
    assert bounded(lambda:prepare(source.id,PrepareIn()))['status']=='unavailable'
    failures['overview']=False;failures['project']=True
    first=bounded(lambda:prepare(source.id,PrepareIn()))
    assert first['status']=='ready' and first['project_preparation_status']=='unavailable'
    failures['project']=False
    overview_calls=sum('passages' in row for row in calls)
    assert bounded(lambda:prepare(source.id,PrepareIn()))['project_preparation_status']=='ready'
    assert sum('passages' in row for row in calls)==overview_calls


def test_real_create_app_accept_and_duplicate_finish_under_one_serialized_lock(production):
    app,source,provider,calls,_,route=production
    prepare=route('/api/v1/local-mail/{episode_id}/workflow/prepare')
    first=bounded(lambda:prepare(source.id,PrepareIn()))
    item=first['items'][0]
    accept=route('/api/v1/local-mail/{episode_id}/workflow/tasks/{proposal_id}/accept')
    body=AcceptIn(fingerprint=first['fingerprint'],source_digest=first['source_digest'],title='Belege prüfen',new_project_name='Prüfprojekt')
    saved=bounded(lambda:accept(source.id,item['id'],body))
    duplicate=bounded(lambda:accept(source.id,item['id'],body.model_copy(update={'title':'Nicht überschreiben'})))
    assert duplicate==saved
    assert len(app.state.tasks.all_tasks())==1
    assert len(app.state.workspace.projects())==2


def test_real_create_app_accept_still_checks_fingerprint_while_lock_is_held(production,monkeypatch):
    from icarus_memory.task_candidates import TaskCandidates
    app,source,provider,calls,_,route=production
    first=bounded(lambda:route('/api/v1/local-mail/{episode_id}/workflow/prepare')(source.id,PrepareIn()))
    original=TaskCandidates.accept
    def checked(self,*args,**kwargs):
        assert not app.state.conversation_lock.acquire(blocking=False), 'Globale Sperre muss bis zur gemeinsamen Annahme gehalten bleiben.'
        return original(self,*args,**kwargs)
    monkeypatch.setattr(TaskCandidates,'accept',checked)
    body=AcceptIn(fingerprint=first['fingerprint'],source_digest=first['source_digest'],title='Prüfen')
    assert bounded(lambda:route('/api/v1/local-mail/{episode_id}/workflow/tasks/{proposal_id}/accept')(source.id,first['items'][0]['id'],body))['title']=='Prüfen'
