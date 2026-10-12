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

eventfile=ROOT/'incremental-real-results.jsonl'
embed=LocalEmbedder(base_url='http://127.0.0.1:11434',timeout=30,verify_weights=True).__enter__()
semantic=WorkingMemorySemantic(embed);assert semantic.search_with_status(ep,'BioRegio').status=='ok';agent._working_memory_search=semantic
try:
 saved=json.loads((ROOT/'withdrawal-conversation.json').read_text())
 r=client.get('/api/v1/conversations/'+saved['conversation_id']);r.raise_for_status()
 assert '7342' not in r.json()['messages'][-1]['content']
 assert ep.get(saved['source_id']).state.value=='ignored'
 emit({'phase':'withdrawal_after_app_store_reopen','withdrawn_original_not_shown':True,'original_retained':True})
 question='Welche Frist gilt aktuell für den BioRegio-Förderantrag?'
 conversation=client.post('/api/v1/conversations',json={}).json()['conversation']['id']
 r=client.post(f'/api/v1/conversations/{conversation}/messages',json={'message':question,'answer_mode':'auto'});r.raise_for_status();before=r.json()['messages'][-1]
 assert '20.10.2026' in before['content']
 emit({'phase':'incremental_before','reply':before['content']})
 body='Für den BioRegio-Förderantrag gilt jetzt der 30.10.2026. Die zuvor genannte Frist vom 20.10.2026 ist ersetzt.'
 r=client.post('/episodes',json={'title':'Künstliche neue Frist nach Testaufnahme','body':body,'occurred_at':'2026-10-12T12:00:00+02:00','kind':'document'});r.raise_for_status();source=r.json()['id']
 result=run(ep,VerifiedLocalProvider(p),threading.RLock(),source_ids=[source],limit=1,stand=Zwischenstand());assert result.ok
 r=client.get('/api/v1/conversations/'+conversation);r.raise_for_status();old=r.json()['messages'][-1]
 assert '20.10.2026' not in old['content']
 emit({'phase':'incremental_saved_invalidated','reply':old['content']})
 fresh=client.post('/api/v1/conversations',json={}).json()['conversation']['id']
 r=client.post(f'/api/v1/conversations/{fresh}/messages',json={'message':question,'answer_mode':'auto'});r.raise_for_status();answer=r.json()['messages'][-1]
 assert '30.10.2026' in answer['content'] and any(x.get('episode_id')==source for x in answer['metadata']['context'].get('source_links',[]))
 assert ep.get(ids['s02']).body==next(x['text'] for x in cat['sources'] if x['id']=='s02')
 emit({'phase':'incremental_fresh','reply':answer['content'],'old_original_retained':True,'new_original_retained':ep.get(source).body==body})
finally:
 embed.__exit__();client.close();_close_persistent_state(app)
