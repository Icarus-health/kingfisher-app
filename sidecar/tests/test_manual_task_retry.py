"""An uncertain manual save must be safe to retry without duplicate tasks."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app

@pytest.fixture
def setup(tmp_path,monkeypatch):
 monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
 app=create_app(SelfModelStore(MemoryBackend(),subject_id='synthetic'))
 client=TestClient(app)
 project=client.post('/api/v1/projects',json={'name':'Synthetic'}).json()['id']
 payload={'request_id':str(uuid4()),'title':'Review report','due':'2026-10-12T09:00:00Z',
          'project_id':project,'notes':'Keep this note','tags':['explicit','synthetic']}
 return app,client,payload

@pytest.mark.parametrize('path',['/api/v1/tasks','/tasks'])
def test_lost_response_replay_saves_once_with_all_explicit_fields(setup,path):
 app,client,payload=setup
 first=client.post(path,json=payload);retry=client.post(path,json=payload)
 assert first.status_code==retry.status_code==201
 assert retry.json()['id']==first.json()['id']
 assert len(app.state.tasks.all_tasks())==1
 assert retry.json()['notes']==payload['notes'] and retry.json()['tags']==payload['tags']
 assert retry.json()['due'] is not None and retry.json()['project_id']==payload['project_id']


def test_retry_after_restart_returns_current_edited_and_done_task(setup):
 app,client,payload=setup
 first=client.post('/api/v1/tasks',json=payload).json()
 app.state.tasks.edit(first['id'],title='Explicitly changed after save')
 app.state.tasks.complete(first['id'])
 restarted=create_app(SelfModelStore(MemoryBackend(),subject_id='synthetic'))
 with TestClient(restarted) as new_client:retry=new_client.post('/api/v1/tasks',json=payload)
 assert retry.status_code==201 and retry.json()['id']==first['id']
 assert retry.json()['title']=='Explicitly changed after save' and retry.json()['status']=='done'
 assert len(restarted.state.tasks.all_tasks())==1

@pytest.mark.parametrize('change',[{'title':'Changed'},{'notes':'Changed'},{'tags':['different']},
 {'due':'2026-10-13T09:00:00Z'},{'project_id':None}])
def test_committed_request_cannot_be_rebound(setup,change):
 app,client,payload=setup
 first=client.post('/api/v1/tasks',json=payload).json()
 retry=client.post('/api/v1/tasks',json={**payload,**change})
 assert retry.status_code==409
 assert app.state.tasks.get(first['id']).title==payload['title']
 assert len(app.state.tasks.all_tasks())==1


def test_equivalent_due_instant_reuses_request_and_new_attempt_is_distinct(setup):
 app,client,payload=setup
 first=client.post('/api/v1/tasks',json=payload).json()
 retry=client.post('/api/v1/tasks',json={**payload,'due':'2026-10-12T11:00:00+02:00'}).json()
 assert retry['id']==first['id']
 distinct=client.post('/api/v1/tasks',json={**payload,'request_id':str(uuid4())}).json()
 assert distinct['id']!=first['id'] and len(app.state.tasks.all_tasks())==2


def test_failed_retry_binding_rolls_back_task_and_history(setup):
 app,client,payload=setup
 with app.state.tasks._conn:
  app.state.tasks._conn.execute("CREATE TRIGGER fail_binding BEFORE INSERT ON task_requests BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
 response=TestClient(app,raise_server_exceptions=False).post('/api/v1/tasks',json=payload)
 assert response.status_code==500
 assert app.state.tasks.all_tasks()==[]
 assert app.state.tasks._conn.execute('SELECT count(*) FROM task_events').fetchone()[0]==0
 with app.state.tasks._conn:app.state.tasks._conn.execute('DROP TRIGGER fail_binding')
 retry=client.post('/api/v1/tasks',json=payload)
 assert retry.status_code==201 and len(app.state.tasks.all_tasks())==1


def test_invalid_request_and_legacy_omission(setup):
 app,client,payload=setup
 assert client.post('/api/v1/tasks',json={**payload,'request_id':'invalid'}).status_code==422
 legacy={k:v for k,v in payload.items() if k!='request_id'}
 first=client.post('/api/v1/tasks',json=legacy).json();second=client.post('/api/v1/tasks',json=legacy).json()
 assert first['id']!=second['id'] and len(app.state.tasks.all_tasks())==2


@pytest.mark.parametrize('path',['/api/v1/tasks','/tasks'])
def test_goal_link_survives_retry_and_invalid_goal_cannot_create_another_task(setup,path):
 app,client,payload=setup
 goal=client.post('/api/v1/assertions',json={'statement':'Synthetic goal','kind':'goal',
     'provenance':{'source_type':'user_stated'}}).json()
 linked={**payload,'goal_id':goal['id']}
 first=client.post(path,json=linked);retry=client.post(path,json=linked)
 assert first.status_code==retry.status_code==201
 assert retry.json()['id']==first.json()['id'] and retry.json()['goal_id']==goal['id']
 assert client.post(path,json={**linked,'goal_id':None}).status_code==409
 assert client.post('/api/v1/goals/'+goal['id']+'/finish',json={'outcome':'achieved'}).status_code==200
 assert client.post(path,json=linked).status_code==409
 assert client.post(path,json={**linked,'request_id':str(uuid4())}).status_code==409
 assert len(app.state.tasks.all_tasks())==1
 assert client.get('/api/v1/tasks/'+first.json()['id']).json()['goal_id']==goal['id']
