"""Synthetic installed-package check; run only in ephemeral --network none container."""
from pathlib import Path
import hashlib, json, os
from dataclasses import asdict
from uuid import uuid4

expected=json.loads(Path('/proof/package-inputs.json').read_text())
import icarus_memory
package=Path(icarus_memory.__file__).resolve().parent
assert str(package)=='/usr/local/lib/python3.12/site-packages/icarus_memory'
actual={str(p.relative_to(package.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
assert actual==expected['python_files_sha256'], 'Python content mismatch'
ui=Path('/opt/kingfisher/ui')
actual_ui={str(p.relative_to(ui)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ui.rglob('*') if p.is_file()}
assert actual_ui==expected['ui_files_sha256'], 'UI content mismatch'
assert Path('/opt/kingfisher/VERSION').read_text().strip()==expected['version']
assert os.environ['KINGFISHER_FASSUNG']==expected['version']
assert os.environ['ICARUS_DATA_DIR']=='/data'
assert not any(Path('/data').iterdir()), 'requires a new empty tmpfs'
for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','LLM_API_KEY','ICARUS_PROVIDER','ICARUS_MODEL'):
    assert not os.environ.get(key), 'a provider was configured'
os.environ['KINGFISHER_UPDATE_URL']=''
os.environ['ICARUS_SIDECAR_TOKEN']='synthetic-package-check'
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
app=create_app(SelfModelStore(MemoryBackend(),subject_id='synthetic'))
client=TestClient(app)
assert app.state.agent.provider is None
for path in ('/api/v1/health/observations','/api/v1/mac-calendar','/api/v1/device/profile'):
    assert client.get(path).status_code==401, path
assert client.get('/health').json()=={'status':'ok'}
client.headers['x-icarus-token']='synthetic-package-check'
assert client.post('/api/v1/hintergrund/pause').status_code==200
root='/api/v1/health/observations'
payload=dict(request_id=str(uuid4()),subject='self',metric='Gewicht',value='072,50',unit='kg',observed_at='2023-07-02T09:30:00.000123Z',note='Künstlicher Pakettest')
response=client.post(root,json=payload);assert response.status_code==201,response.text
old=response.json();original=app.state.episodes.get(old['id']).body
replay=client.post(root,json=payload);assert replay.status_code==200 and replay.json()['id']==old['id']
changed={**payload,'request_id':str(uuid4()),'value':'71,8','expected_support_fingerprint':old['support_fingerprint']}
response=client.patch(f"{root}/{old['id']}",json=changed);assert response.status_code==200,response.text
new=response.json();assert new['id']!=old['id'] and new['observed_at']==payload['observed_at']
assert app.state.episodes.get(old['id']).body==original
assert not app.state.episodes.support_snapshot(old['id']).current()
assert client.patch(f"{root}/{old['id']}",json={**changed,'request_id':str(uuid4()),'value':'80'}).status_code==409
assert client.get(root).json()['items'][0]['id']==new['id']
assert {r['id']:r['status'] for r in client.get(f"{root}/{old['id']}/history").json()['items']}=={old['id']:'superseded',new['id']:'current'}
app2=create_app(SelfModelStore(MemoryBackend(),subject_id='synthetic'))
restarted=TestClient(app2);restarted.headers['x-icarus-token']='synthetic-package-check'
assert restarted.get(root).json()['items'][0]['id']==new['id']
assert restarted.post(f"/api/v1/episodes/{new['id']}/ignore").status_code==200
assert client.get(root).json()['items']==[]
assert {r['id']:r['status'] for r in client.get(f"{root}/{old['id']}/history").json()['items']}[new['id']]=='excluded'
assert app.state.episodes.get(old['id']).body==original
# Synthetic native worker route: never EventKit or the user's calendars.
cal='/api/v1/mac-calendar'
state=client.post(cal+'/connect').json()
calendars=[dict(id=str(i),name='Synthetic '+str(i)) for i in range(3)]
response=client.post(cal+'/worker',json=dict(generation=state['generation'],status='granted',calendars=calendars));assert response.status_code==200,response.text
state=client.put(cal+'/selection',json={'ids':['0','1','2']}).json()
assert state['selected']==['0','1','2']
response=client.post(cal+'/worker',json=dict(generation=state['generation'],status='granted',calendars=calendars,events=[]));assert response.status_code==200,response.text
assert client.get(cal).json()['memory_allowed'] is False
assert client.delete(cal).status_code==200
assert client.get(cal).json()['selected']==[]
# Reject the known oversized local model before settings/environment/model I/O.
profile=client.post('/api/v1/device/profile',json={'platform':'macos','chip':'Synthetic','memory_bytes':32*1024**3})
assert profile.status_code==200,profile.text
assert profile.json()['guidance']['model_budget_gb']==19.2
before=asdict(app.state.settings)
for path in ('/setup','/api/v1/setup'):
    response=client.put(path,json={'provider':'ollama','model':'qwen3.6:35b'})
    assert response.status_code==422,response.text
    assert asdict(app.state.settings)==before
    assert app.state.agent.provider is None
# Real static-serving contract; this does not render or drive a browser.
page=client.get('/wellbeing');assert page.status_code==200 and '<div id="root">' in page.text
assert client.get('/health').json()['status']=='ok'
print(json.dumps({'status':'passed','version':expected['version'],'python_files':len(actual),'ui_files':len(actual_ui),'synthetic_auth':True,'health_create_retry_correct_stale_history_restart_exclude':True,'calendar_route_selection_disconnect':True,'ram_aliases_reject_oversize':True,'wellbeing_served_health_preserved':True,'productive_mounts':False,'models_configured':False,'browser_rendered':False},sort_keys=True))
