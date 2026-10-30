"""Mac-lokale HTTP-Probe: eingefrorene künstliche Mails, bestehendes Qwen9B, keine privaten Quellen."""
import os,sys,json,time,subprocess,re,urllib.request
from pathlib import Path
from datetime import datetime
R=Path(__file__).parent;REPO=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-quality-20261019');OLD=REPO.parent/'hermes-comparison-20261030'
os.environ.update(ICARUS_DATA_DIR=str(R/'live-data'),KINGFISHER_TIMEZONE='Europe/Berlin',KINGFISHER_UPDATE_URL='',ICARUS_MEMORY_SEMANTIC='0')
sys.path.insert(0,str(REPO/'sidecar'))
from fastapi.testclient import TestClient
from icarus_memory import secrets
secrets.Keychain._detect=lambda self:'none'
from icarus_memory.server import create_app
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance,SourceType
from icarus_memory.kontakte import fuer_mail
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.providers import OpenAICompatible
from tests.test_conversation_retraction import _close_app
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def ollama(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:11434'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with opener.open(req,timeout=180) as f:return json.load(f)
def pressure():
 level=int(subprocess.check_output(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True));free=int(re.search(r'free percentage: (\d+)%',subprocess.check_output(['/usr/bin/memory_pressure','-Q'],text=True))[1]);return {'level':level,'free_percent':free}
assert ollama('/api/ps')['models']==[],'Do not displace another model'
inner=OpenAICompatible('kingfisher-qwen3.5:9b-32k',api_key='ollama',base_url='http://127.0.0.1:11434/v1');inner._verified_local_transport=True
class Meter:
 def __init__(self):self.calls=0;self.samples=[]
 def __getattr__(self,k):return getattr(inner,k)
 def before(self):
  p=pressure();self.samples.append(p);assert p['level']<=2 and p['free_percent']>=25,p
  assert all(m['name']=='kingfisher-qwen3.5:9b-32k' for m in ollama('/api/ps')['models']);self.calls+=1
 def complete_json(self,*args,**kwargs):self.before();return inner.complete_json(*args,**kwargs)
 def complete(self,*args,**kwargs):self.before();return inner.complete(*args,**kwargs)
meter=Meter();app=create_app();app.state.scheduler.stop();app.state.hintergrund.pausieren(True);app.state.settings.schedule.enabled=False;app.state.settings.schedule.with_model=False
app.state.agent._provider=meter;app.state.agent._frage_anbieter=lambda:None;app.state.agent._working_memory_search=None
cat=json.loads((OLD/'catalog.json').read_text());old=json.loads((OLD/'evidence/kingfisher-intake.json').read_text());classifications={s['key']:s['refs'] for s in old['sources']};ids={};wm=WorkingMemoryStore(app.state.episodes)
try:
 for s in cat['sources']:
  source='synthetic-person-fix:'+s['key'];sender=f"{s['name']} <{s['address']}>";at=datetime.fromisoformat(s['occurred_at'])
  e,_=app.state.episodes.record(EpisodeKind.MESSAGE,s['title'],s['body'],Provenance(SourceType.EMAIL,source,datetime.fromisoformat(cat['clock'])),occurred_at=at,participants=[sender,s['to']],contacts=fuer_mail(sender,[{'adresse':s['to'],'name':'','rolle':'an'}],eigene=[cat['owner']['address']]),source_key=source)
  app.state.episodes.advance_source_head(source,None,e.id);ids[s['key']]=e.id
  assert wm.commit(wm._snapshot(e.id),[{k:r[k] for k in ('start','end','kind')} for r in classifications[s['key']]],model='replay-of-recorded-Qwen-classification')
 client=TestClient(app);cid=client.post('/api/v1/conversations',json={}).json()['conversation']['id'];base=f'/api/v1/conversations/{cid}'
 st=time.perf_counter();r=client.post(base+'/messages',json={'message':'Welche Frist hat Alex?','answer_mode':'auto'});assert r.status_code==201,r.text
 first=r.json();pending=first['context']['meaning_choice'];assert first['context']['answer_contract']['status']=='meaning_choice';assert meter.calls==0
 options=pending['options'];assert len(options)==3,options
 print('Before-choice: three identities, no model call',round(time.perf_counter()-st,3),flush=True)
 i=next(i for i,o in enumerate(options) if ids['deadline-change'] in o['ids']);st=time.perf_counter()
 r=client.post(base+'/messages',json={'message':options[i]['label'],'clarification_choice':i});assert r.status_code==201,r.text
 result=r.json();context=result['context'];answer=context['working_answer'];reply=result['messages'][-1]['content']
 assert answer['meaning_scope']['chosen'] is True
 assert ids['deadline-change'] in {ref['episode_id'] for ref in answer['refs']}
 assert '4. November 2026' in reply and '18 Uhr' in reply,reply
 result={'synthetic_only':True,'data_set':'same frozen ten mails and recorded Qwen classification spans','initial_question':'Welche Frist hat Alex?','initial_status':first['context']['answer_contract']['status'],'initial_model_calls':0,'choices':options,'after_explicit_choice':{'reply':reply,'seconds':round(time.perf_counter()-st,3),'calls':meter.calls,'source_keys':[k for k,v in ids.items() if v in {ref['episode_id'] for ref in answer['refs']}]},'pressure':meter.samples,'private_data_accessed':False,'bulk_import_started':False}
 (R/'probe-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
finally:
 _close_app(app)
 loaded=ollama('/api/ps')['models']
 if len(loaded)==1 and loaded[0]['name']=='kingfisher-qwen3.5:9b-32k':ollama('/api/generate',{'model':loaded[0]['name'],'keep_alive':0})
 print('After probe:',pressure(),flush=True)
