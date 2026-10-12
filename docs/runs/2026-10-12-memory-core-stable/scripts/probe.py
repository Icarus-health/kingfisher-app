"""Real local-Qwen intake and authenticated conversation route; synthetic only."""
import os,sys,json,time,hashlib,threading,argparse
from pathlib import Path
ROOT=Path(os.environ['KINGFISHER_CORE_PROBE_DIR']).resolve()
REPO=Path(os.environ['KINGFISHER_CORE_REPO'])
sys.path.insert(0,str(REPO/'sidecar'))
for key in list(os.environ):
 if key.startswith(('ICARUS_','KINGFISHER_')) and key!='KINGFISHER_CORE_REPO':os.environ.pop(key)
os.environ['ICARUS_DATA_DIR']=str(ROOT/'data');os.environ['ICARUS_SIDECAR_TOKEN']='synthetic-owner-only'
from fastapi.testclient import TestClient
import httpx
from icarus_memory import MemoryBackend,SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.policy import Policy
from icarus_memory.providers import OpenAICompatible
from icarus_memory.local_model_guard import verify_local_model,VerifiedLocalProvider
from icarus_memory.working_memory_worker import run,Zwischenstand
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.working_memory_semantic import WorkingMemorySemantic
from icarus_memory.satzpruefung_modell import tor
from icarus_memory.server import create_app,_close_persistent_state

class Meter:
 def __init__(self,inner):
  self.inner=inner
  for key in ['name','model','is_local','base_url','entity_anchor_mode']:setattr(self,key,getattr(inner,key,None))
  self.events=[]
 def complete_json(self,messages,**kwargs):
  started=time.monotonic();kind='other'
  try:
   data=json.loads(messages[-1]['content']);kind='intake' if 'blocks' in data else 'selection' if 'sources' in data else 'question_or_sentence'
  except (ValueError,KeyError,TypeError):pass
  record={'kind':kind,'chars':sum(len(str(m.get('content',''))) for m in messages)};self.events.append(record)
  try:r=self.inner.complete_json(messages,**kwargs);record.update(seconds=round(time.monotonic()-started,4),ok=True,reply=r.text);return r
  except Exception as e:record.update(seconds=round(time.monotonic()-started,4),ok=False,error=type(e).__name__);raise
 def complete(self,messages,tools):return self.inner.complete(messages,tools)

args=argparse.ArgumentParser();args.add_argument('stage',choices=['intake','queries']);args.add_argument('--quotes',action='store_true');args.add_argument('--only',nargs='*');args=args.parse_args()
cat=json.loads((ROOT/'catalog.json').read_text());data=ROOT/'data';data.mkdir(exist_ok=True)
p=OpenAICompatible('kingfisher-qwen3.5:9b-32k',base_url='http://127.0.0.1:11434/v1',api_key='ollama');p._client=lambda timeout:httpx.Client(timeout=timeout,trust_env=False,follow_redirects=False)
identity=verify_local_model(p);p._verified_local_transport=True
meter=Meter(p)
ep=EpisodeStore(data/'episodes.sqlite3');cl=ClaimStore(data/'knowledge.sqlite3');audit=AuditLog(data/'audit.sqlite3')
agent=Agent(SelfModelStore(MemoryBackend(),'synthetic'),Policy(),audit,{},provider=meter,episodes=ep,knowledge=cl)
app=create_app(agent._store,agent=agent,audit=audit,episodes=ep,knowledge=cl)
client=TestClient(app,headers={'X-Icarus-Token':'synthetic-owner-only'})
# No lifecycle start or scheduler: only the explicitly invoked real product routes/jobs.
agent._frage_anbieter=lambda:meter;agent._saetze=not args.quotes;agent._pruefung=lambda:tor('an',meter)
eventfile=ROOT/('intake-results.jsonl' if args.stage=='intake' else 'answers-'+('quotes' if args.quotes else 'sentences')+'.jsonl')
def emit(row):
 with eventfile.open('a') as f:f.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k not in ('reply','context','model_events')},ensure_ascii=False),flush=True)
ids=json.loads((ROOT/'ids.json').read_text()) if (ROOT/'ids.json').exists() else {}
try:
 if args.stage=='intake':
  assert not ids,'Fresh synthetic intake only; no existing corpus overwrite'
  for s in cat['sources']:
   before=len(meter.events);started=time.monotonic()
   r=client.post('/episodes',json={'title':s['title'],'body':s['text'],'occurred_at':s['occurred_at'],'kind':'document'});r.raise_for_status();ids[s['id']]=r.json()['id']
   result=run(ep,VerifiedLocalProvider(p),threading.RLock(),source_ids=[ids[s['id']]],limit=1,stand=Zwischenstand())
   state=WorkingMemoryStore(ep).source_state(ids[s['id']])
   assert ep.get(ids[s['id']]).body==s['text']
   emit({'id':s['id'],'seconds':round(time.monotonic()-started,4),'ok':result.ok,'state':state,'original_retained':True,'detail':result.detail})
  (ROOT/'ids.json').write_text(json.dumps(ids,indent=2)+'\n')
  (ROOT/'intake-metadata.json').write_text(json.dumps({'synthetic_only':True,'model':identity.name,'model_digest':identity.digest,'catalog_sha256':hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest(),'progress':WorkingMemoryStore(ep).progress(),'transport':'loopback_only','route':'POST /episodes -> real working_memory_worker.run','classification':'actual local Qwen, not fixture annotations'},indent=2)+'\n')
 else:
  assert len(ids)==len(cat['sources'])
  inverse={v:k for k,v in ids.items()}
  embed=LocalEmbedder(base_url='http://127.0.0.1:11434',timeout=30,verify_weights=True).__enter__();semantic=WorkingMemorySemantic(embed)
  warm=semantic.search_with_status(ep,'BioRegio');assert warm.status=='ok',warm.status
  agent._working_memory_search=semantic
  for c in cat['cases']:
   if args.only and c['id'] not in args.only:continue
   conversation=client.post('/api/v1/conversations',json={}).json()['conversation']['id']
   before=len(meter.events);started=time.monotonic()
   response=client.post(f'/api/v1/conversations/{conversation}/messages',json={'message':c['question'],'answer_mode':'auto'});response.raise_for_status();answer=response.json()['messages'][-1];ctx=answer['metadata']['context'];working=ctx.get('working_answer',{})
   chosen=sorted({inverse[r['episode_id']] for r in working.get('refs',[]) if r['episode_id'] in inverse});shown=sorted({inverse[r['episode_id']] for r in ctx.get('source_links',[]) if r['episode_id'] in inverse})
   emit({'id':c['id'],'question':c['question'],'seconds':round(time.monotonic()-started,4),'status':ctx.get('answer_contract',{}).get('status'),'source_ids':chosen,'shown_source_ids':shown,'reply':answer['content'],'context':ctx,'model_events':meter.events[before:],'conversation_id':conversation})
  embed.__exit__()
finally:
 client.close();_close_persistent_state(app)
