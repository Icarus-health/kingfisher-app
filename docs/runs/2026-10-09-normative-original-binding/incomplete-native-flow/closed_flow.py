"""Synthetic actual HTTP intake, model worker, durable index and HTTP memory answers.
No application directory loaded; no background scheduler; existing local weights only.
Source selection and transport counts are automatic; independent content review required.
"""
import os,sys,json,time,hashlib,threading,inspect,httpx
from pathlib import Path
from types import SimpleNamespace
REPO=Path(sys.argv[1]).resolve();ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO/'sidecar'),str(REPO/'scripts')]
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend,SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.policy import Policy
from icarus_memory.audit import AuditLog
from icarus_memory.server import create_app
from icarus_memory.agent_verdrahtung import verdrahte_speicher,verdrahte_zusaetze
from icarus_memory.working_memory_worker import run,Zwischenstand
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.memory_categories import Categories,_interpret,_interpret_quotes
from icarus_memory.local_model_guard import VerifiedLocalProvider
from icarus_memory import working_memory_answers, working_memory_references, satzpruefung, satzantwort, akten_kontext
from icarus_memory.providers import OpenAICompatible
from icarus_memory.working_memory_semantic_service import SemanticService
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.hintergrund import als_hintergrund
from icarus_memory.satzpruefung_modell import tor
from probe_working_memory_end_to_end import Meter,local_provider,evaluate
CATALOG=ROOT/'catalog.json'
catalog=json.loads(CATALOG.read_text());assert catalog['synthetic'] and catalog['frozen_before_model_run']
DATA=ROOT/'synthetic-state';DATA.mkdir()
os.environ.update(ICARUS_DATA_DIR=str(DATA),ICARUS_SIDECAR_TOKEN='synthetic-owned-local-token',KINGFISHER_DURABLE_MEMORY_SEARCH='1',ICARUS_MEMORY_SEMANTIC='0')
provider=Meter(VerifiedLocalProvider(local_provider('qwen3.5:4b','http://127.0.0.1:11439/v1')))
report={'synthetic_only':True,'diagnostic_unload_every_four_sources':True,'production_memory_policy_verified':False,'catalog_sha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),'code_version':os.environ['KINGFISHER_FASSUNG'],'scope':'actual document upload HTTP; actual model worker and topic/entity suggestions; actual persisted semantic index; actual memory_evidence conversation HTTP; no automatic UI routing or screen test','model':'qwen3.5:4b','rows':[],'intake':[],'classification':[],'completed':False,'content_review':'pending independent review','code_files':{}}
report['holdout_sha256']=catalog['parent_holdout_catalog_sha256']
for obj in (Agent,run,SemanticService,create_app,_interpret,_interpret_quotes,OpenAICompatible,VerifiedLocalProvider,Meter,working_memory_answers.prepare,working_memory_references.wanted, satzpruefung.satz_pruefen, satzantwort.formulieren, akten_kontext.aufbauen):
 p=Path(inspect.getfile(obj));assert p.is_relative_to(REPO);report['code_files'][obj.__name__]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save():
 p=ROOT/'answers.new';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');p.replace(ROOT/'answers.json')
def open_app():
 audit=AuditLog(DATA/'audit.sqlite3');agent=Agent(SelfModelStore(MemoryBackend(),'synthetic'),Policy(),audit,{},provider=provider)
 app=create_app(agent=agent,audit=audit)
 previous=getattr(app.state,'semantic_search',None)
 if previous:previous.close()
 service=SemanticService(app.state.episodes,lambda:LocalEmbedder(base_url='http://127.0.0.1:11439',timeout=30,keep_alive='15s',verify_weights=True),permission_lock=app.state.conversation_lock)
 app.state.semantic_search=service
 client=TestClient(app,headers={'X-Icarus-Token':'synthetic-owned-local-token'})
 return app,client,service
def close_app(app,client,service):
 client.close();service.close()
 for name in ('mac_calendar','recovery_jobs','audit','tasks','workspace','episodes','proposals','conversations','claims','regeln'):
  close=getattr(getattr(app.state,name,None),'close',None)
  if callable(close):close()
def new_agent(app,service):
 agent=Agent(SelfModelStore(MemoryBackend(),'synthetic'),Policy(),app.state.audit,{},provider=provider,episodes=app.state.episodes,knowledge=app.state.claims)
 verdrahte_speicher(app,agent);verdrahte_zusaetze(app,agent)
 agent._frage_anbieter=lambda:provider;agent._saetze=True;agent._pruefung=lambda:tor('an',provider)
 calls=[]
 class ObservedSearch:
  def search_with_status(self,*args,**kwargs):
   r=service.search_with_status(*args,**kwargs);calls.append({'status':r.status,'refs':[dict(ref) for ref in r.refs]});return r
 agent._working_memory_search=ObservedSearch();app.state.agent=agent
 return agent,calls
def unload_between_packages():
 with httpx.Client(trust_env=False,timeout=20) as http:
  r=http.post('http://127.0.0.1:11439/api/generate',json={'model':'qwen3.5:4b','prompt':'','keep_alive':0});r.raise_for_status()
app=client=service=None
try:
 app,client,service=open_app();alias={};source_ids=[]
 for source in catalog['sources']:
  r=client.post('/api/v1/sources/documents',json={'filename':source['title']+'.txt','body':source['text']});r.raise_for_status();identifier=r.json()['id'];alias[identifier]=source['id'];source_ids.append(identifier)
  episode=app.state.episodes.get(identifier);assert episode.body==source['text']
  report['intake'].append({'id':source['id'],'episode_id':identifier,'digest':episode.digest,'original_sha256':hashlib.sha256(episode.body.encode()).hexdigest(),'occurred_at':str(episode.occurred_at),'http_status':r.status_code})
 save()
 store=WorkingMemoryStore(app.state.episodes);stand=Zwischenstand()
 for identifier in source_ids:
  before=provider.calls;start=time.monotonic()
  result=run(app.state.episodes,provider,app.state.conversation_lock,limit=1,source_ids=[identifier],stand=stand)
  def rows(table):
   cursor=app.state.episodes._conn.execute('SELECT * FROM '+table+' WHERE episode_id=?',(identifier,));names=[c[0] for c in cursor.description];return [dict(zip(names,row)) for row in cursor.fetchall()]
  records=rows('working_memory_items');status=rows('working_memory_sources')
  report['classification'].append({'id':alias[identifier],'job_ok':result.ok,'detail':result.detail,'seconds':round(time.monotonic()-start,3),'items':records,'state':status,'model_outputs':provider.outputs(before)})
  save();print('classified',alias[identifier],result.ok,flush=True)
  if len(report['classification']) % 4 == 0:unload_between_packages()
  if not result.ok:raise RuntimeError('Classification failure; retained evidence before answers')
 report['classification_progress']=store.progress();report['topic_entity_suggestions']=[];save()
 # Minimum named-person expectations frozen before this phase, derived only from originals.
 report['person_gold']={}
 categories=Categories(app.state.episodes)
 for identifier in source_ids:
  before=provider.calls;start=time.monotonic()
  result=categories.run(provider,limit=1,source_ids=[identifier],permission_lock=app.state.conversation_lock)
  def category_rows(table):
   cursor=app.state.episodes._conn.execute('SELECT * FROM '+table+' WHERE episode_id=?',(identifier,));names=[c[0] for c in cursor.description];return [dict(zip(names,row)) for row in cursor.fetchall()]
  entities=category_rows('memory_category_entities')
  body=app.state.episodes.get(identifier).body
  for entity in entities:entity['quote']=body[entity['start']:entity['end']]
  report['topic_entity_suggestions'].append({'id':alias[identifier],'job_ok':result.ok,'detail':result.detail,'seconds':round(time.monotonic()-start,3),'entities':entities,'topics':category_rows('memory_category_topics'),'state':category_rows('memory_category_sources'),'model_outputs':provider.outputs(before)})
  save();print('topics/entities',alias[identifier],result.ok,flush=True)
  if len(report['topic_entity_suggestions']) % 4 == 0:unload_between_packages()

 for _ in range(8):
  with als_hintergrund():indexed=service.index_batch()
  coverage=service.coverage();report['index_coverage']=coverage;save();print('indexed',indexed.ok,coverage,flush=True)
  if not indexed.ok:raise RuntimeError('Embedding batch failed')
  if coverage.get('indexed')==len(source_ids) and coverage.get('pending')==0 and coverage.get('source_pending')==0:break
 else:raise RuntimeError('Index incomplete')
 # Reopen every persisted store and service before querying, rather than using transient state.
 close_app(app,client,service);app=client=service=None
 app,client,service=open_app();report['reopened_before_questions']=True;save()
 saved_conversation=None
 for item in catalog['questions']:
  agent,semantic_calls=new_agent(app,service);captured=[];original=agent.answer_memory
  def observed(*args,**kwargs):
   turn=original(*args,**kwargs);captured.append(turn);return turn
  agent.answer_memory=observed
  conversation=client.post('/api/v1/conversations',json={});conversation.raise_for_status();cid=conversation.json()['conversation']['id']
  before=provider.calls;start=time.monotonic()
  response=client.post('/api/v1/conversations/'+cid+'/messages',json={'message':item['q'],'answer_mode':'memory_evidence'});response.raise_for_status()
  message=response.json()['messages'][-1];context=message['metadata'].get('context',{})
  projected=SimpleNamespace(context=context,reply=message['content'])
  trace={'semantic_enabled':True,'semantic_calls':semantic_calls,'http_status':response.status_code,'captured_turns':len(captured)}
  row=evaluate(item,projected,alias,trace);outcomes=provider.outcomes(before)
  row.update(id=item['id'],conversation_id=cid,seconds=round(time.monotonic()-start,3),model_outputs=provider.outputs(before),calls=provider.calls-before,provider_errors=outcomes['failed'],provider_pending=outcomes['pending'])
  row['selection_pass'] &= not(row['provider_errors'] or row['provider_pending'])
  row['working_answer']=context.get('working_answer',{})
  report['rows'].append(row);save();print(item['id'],row['status'],row['shown_sources'],row['seconds'],flush=True)
  if len(report['rows']) % 4 == 0:unload_between_packages()
  if saved_conversation is None and context.get('working_answer',{}).get('refs') and row['status']=='working_reports':saved_conversation=(cid,[ref['episode_id'] for ref in context['working_answer']['refs']])
 # Check all saved answers after real store/service close and reopen, with no inference.
 close_app(app,client,service);app=client=service=None
 app,client,service=open_app();new_agent(app,service)
 report['saved_answers_after_restart']=[]
 for prior in report['rows']:
  calls_before=provider.calls
  response=client.get('/api/v1/conversations/'+prior['conversation_id']);response.raise_for_status()
  message=response.json()['messages'][-1]
  report['saved_answers_after_restart'].append({'id':prior['id'],'answer':message['content'],'unchanged':message['content']==prior['answer'],'provider_calls':provider.calls-calls_before,'status':message['metadata'].get('context',{}).get('answer_contract',{}).get('status')})
 save()
 report['originals_preserved_before_withdrawal']=all(app.state.episodes.get(i).body==next(s['text'] for s in catalog['sources'] if s['id']==alias[i]) for i in source_ids)
 if saved_conversation:
  cid,identifiers=saved_conversation
  close_app(app,client,service);app=client=service=None
  app,client,service=open_app();new_agent(app,service)
  before=provider.calls
  for identifier in set(identifiers):app.state.episodes.ignore(identifier)
  r=client.get('/api/v1/conversations/'+cid);r.raise_for_status();message=r.json()['messages'][-1];context=message['metadata'].get('context',{});status=context.get('answer_contract',{}).get('status')
  report['withdrawal_after_restart']={'status':status,'pass':status=='working_unavailable' and not context.get('source_links'),'answer':message['content'],'provider_calls':provider.calls-before,'original_text_retained':all(app.state.episodes.get(i).body==next(s['text'] for s in catalog['sources'] if s['id']==alias[i]) for i in identifiers)}
 report['completed']=True
except BaseException as exc:
 report['runtime_error']=type(exc).__name__+': '+str(exc);raise
finally:
 save()
 if app is not None:close_app(app,client,service)
