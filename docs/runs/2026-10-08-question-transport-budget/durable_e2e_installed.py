"""Synthetic real-model diagnostic through the installed durable retrieval service."""
import sys,json,time,tempfile,hashlib,os
from pathlib import Path
import icarus_memory
from icarus_memory.agent import Agent
from icarus_memory.working_memory_semantic_service import SemanticService
import inspect
assert '/site-packages/' in inspect.getfile(Agent)
assert '/site-packages/' in inspect.getfile(SemanticService)
installed_files={c.__name__: {'path':inspect.getfile(c),'sha256':hashlib.sha256(Path(inspect.getfile(c)).read_bytes()).hexdigest()} for c in (Agent,SemanticService)}
sys.path.insert(0,'/repo/scripts')
import probe_working_memory_paraphrase as catalog_support
from probe_working_memory_end_to_end import local_provider,Meter,answer_with_trace,evaluate
from icarus_memory import MemoryBackend,SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.policy import Policy
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.working_memory_semantic_service import SemanticService
from icarus_memory.hintergrund import als_hintergrund
from icarus_memory import working_memory_answers
catalog_support.CATALOG=Path(sys.argv[1]);output=Path(sys.argv[2]);limit=int(sys.argv[3])
assert not output.exists()
model='gemma3:1b-it-qat';provider=Meter(local_provider(model,'http://127.0.0.1:11434/v1'))
report={'synthetic_only':True,'model':model,'code_version':os.environ.get('KINGFISHER_FASSUNG'),'catalog_sha256':catalog_support.catalog_digest(),
 'import_evidence':installed_files,'retrieval':'installed SemanticService / DurableSemanticIndex; real local bge-m3','quotes':True,
 'ingestion':'deterministic synthetic indexing; not real ingestion quality','rows':[],'completed':False,'prose_review':'required'}
def save():
 tmp=output.with_suffix('.new');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');tmp.replace(output)
with tempfile.TemporaryDirectory() as directory:
 catalog,episodes,store,alias=catalog_support.build(directory)
 claims=ClaimStore(Path(directory)/'claims.sqlite3');audit=AuditLog(Path(directory)/'audit.sqlite3')
 factory=lambda:LocalEmbedder(timeout=30,keep_alive='15s',verify_weights=True)
 service=SemanticService(episodes,factory);saved=None
 try:
  for n in range(20):
   with als_hintergrund():result=service.index_batch()
   coverage=service.coverage();report['index_coverage']=coverage;save()
   print('index',result.ok,coverage,flush=True)
   if not result.ok:raise RuntimeError('Real embedding batch failed')
   if coverage.get('indexed')==len(catalog['sources']) and coverage.get('pending')==0:break
  else:raise RuntimeError('Index preparation incomplete')
  for item in catalog['questions'][:limit]:
   semantic_calls=[]
   class ObservedSearch:
    def search_with_status(self,*args,**kwargs):
     r=service.search_with_status(*args,**kwargs)
     semantic_calls.append({'status':r.status,'refs':[dict(ref) for ref in r.refs]});return r
   agent=Agent(SelfModelStore(MemoryBackend(),'synthetic'),Policy(),audit,{},provider=provider,episodes=episodes,knowledge=claims)
   agent._frage_anbieter=lambda:provider;agent._saetze=False;agent._working_memory_search=ObservedSearch()
   calls=provider.calls;start=time.monotonic()
   with service.request():turn,trace=answer_with_trace(agent,item['q'])
   trace['semantic_enabled']=True;trace['semantic_calls']=semantic_calls
   row=evaluate(item,turn,alias,trace);outcomes=provider.outcomes(calls)
   row.update(seconds=round(time.monotonic()-start,3),calls=provider.calls-calls,provider_errors=outcomes['failed'],provider_pending=outcomes['pending'],model_outputs=provider.outputs(calls))
   row['selection_pass'] &= not(row['provider_errors'] or row['provider_pending'])
   report['rows'].append(row);save()
   print(len(report['rows']),item['type'],row['status'],row['shown_sources'],row['seconds'],row['provider_errors'],flush=True)
   answer=turn.context.get('working_answer')
   if saved is None and answer and answer.get('refs') and row['status']=='working_reports':saved=answer
  if saved:
   for identifier in {r['episode_id'] for r in saved['refs']}:episodes.ignore(identifier)
   text,links,status=working_memory_answers.render(saved,episodes,claims)
   report['withdrawal']={'checked':True,'pass':status=='working_unavailable' and not links,'status':status,'answer':text}
  else:report['withdrawal']={'checked':False,'pass':False}
  report['completed']=True;report['partial_catalog']=len(report['rows'])!=len(catalog['questions'])
 except BaseException as e:
  report['runtime_error']=type(e).__name__+': '+str(e);raise
 finally:
  save();service.close();audit.close();claims.close();episodes.close()
