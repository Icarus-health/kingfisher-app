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

eventfile=ROOT/'lifecycle-results.jsonl'
inverse={v:k for k,v in ids.items()}
embed=LocalEmbedder(base_url='http://127.0.0.1:11434',timeout=30,verify_weights=True).__enter__()
semantic=WorkingMemorySemantic(embed);assert semantic.search_with_status(ep,'BioRegio').status=='ok'
agent._working_memory_search=semantic
try:
 # Existing stored answer must remain accessible after an actual app/store reopen.
 old=json.loads((ROOT/'answers-sentences-before-fix.jsonl').read_text().splitlines()[1])
 r=client.get('/api/v1/conversations/'+old['conversation_id']);r.raise_for_status()
 answer=r.json()['messages'][-1]
 assert 'Angebotsliste' in answer['content'] and answer['metadata']['context']['source_links']
 emit({'phase':'reopen_pre_fix_selected_source','original_quote_preserved':True,'reply':answer['content']})
 conversation=client.post('/api/v1/conversations',json={}).json()['conversation']['id']
 r=client.post(f'/api/v1/conversations/{conversation}/messages',json={'message':cat['withdrawal']['question'],'answer_mode':'auto'});r.raise_for_status()
 answer=r.json()['messages'][-1]
 assert '7342' in answer['content']
 emit({'phase':'withdrawal_before','reply':answer['content'],'conversation_id':conversation})
 original=ep.get(ids['s19']).body
 r=client.post('/api/v1/episodes/'+ids['s19']+'/ignore');r.raise_for_status()
 assert ep.get(ids['s19']).body==original
 r=client.get('/api/v1/conversations/'+conversation);r.raise_for_status()
 answer=r.json()['messages'][-1]
 assert '7342' not in answer['content']
 emit({'phase':'withdrawal_saved_conversation','original_retained':True,'reply':answer['content']})
 fresh=client.post('/api/v1/conversations',json={}).json()['conversation']['id']
 r=client.post(f'/api/v1/conversations/{fresh}/messages',json={'message':cat['withdrawal']['question'],'answer_mode':'auto'});r.raise_for_status()
 answer=r.json()['messages'][-1]
 assert '7342' not in answer['content']
 assert not any(x.get('episode_id')==ids['s19'] for x in answer['metadata']['context'].get('source_links',[]))
 emit({'phase':'withdrawal_fresh_question','reply':answer['content'],'original_retained':True})
 (ROOT/'withdrawal-conversation.json').write_text(json.dumps({'conversation_id':conversation,'source_id':ids['s19']})+'\n')
finally:
 embed.__exit__();client.close();_close_persistent_state(app)
