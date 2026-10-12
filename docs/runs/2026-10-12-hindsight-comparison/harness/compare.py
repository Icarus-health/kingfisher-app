"""Synthetic harness export. `reflect` is bounded to the first two cases."""
import sys,json,time,threading,hashlib,statistics,os
from pathlib import Path
from datetime import datetime
import httpx,psutil
ROOT=Path(os.environ['KINGFISHER_HINDSIGHT_BENCH_DIR']).resolve()
REPO=Path(os.environ['KINGFISHER_REPO']).resolve()
sys.path.insert(0,str(REPO/'sidecar'))
from icarus_memory.episodes import EpisodeStore,EpisodeKind
from icarus_memory.claims import ClaimStore
from icarus_memory.model import Provenance,SourceType
from icarus_memory.providers import OpenAICompatible,Reply
from icarus_memory.local_model_guard import VerifiedLocalProvider,verify_local_model
from icarus_memory.working_memory_worker import run,Zwischenstand
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_semantic import WorkingMemorySemantic
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory import working_memory_answers as wa

CAT=json.loads((ROOT/'catalog.json').read_text())
BANK='kf-main-'+hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest()[:8]
HTTP=httpx.Client(base_url='http://127.0.0.1:18935',timeout=240,trust_env=False)
EVENTS=ROOT/'results.jsonl'
def event(data):
    with EVENTS.open('a') as f:f.write(json.dumps(data,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in data.items() if k not in ('answer','response','prompt')},ensure_ascii=False),flush=True)
def phase(name):(ROOT/'phase.txt').write_text(name)
def call(method,path,data=None):
    r=HTTP.request(method,path,json=data)
    r.raise_for_status();return r.json()
def prefix(path):return '/v1/default/banks/'+BANK+path
def existing(kind,identifier):
    if not EVENTS.exists():return None
    return next((r for r in [json.loads(l) for l in EVENTS.read_text().splitlines()] if r.get('kind')==kind and r.get('id')==identifier),None)

provider=OpenAICompatible('kingfisher-qwen3.5:9b-32k',base_url='http://127.0.0.1:18934/v1')
provider._client=lambda timeout:httpx.Client(timeout=timeout,trust_env=False)
identity=verify_local_model(provider)
event({'kind':'metadata','id':'runtime','kingfisher_commit':'f75ccadadf4de9de88c3784cea6770c98fab955f','hindsight_version':'0.10.3','qwen_digest':identity.digest,'corpus_sha256':hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest(),'sources':len(CAT['sources']),'cases':len(CAT['cases']),'synthetic_only':True})
episodes=EpisodeStore(ROOT/'kingfisher-episodes.sqlite3');claims=ClaimStore(ROOT/'kingfisher-knowledge.sqlite3')
store=WorkingMemoryStore(episodes)
ids={}
for source in CAT['sources']:
    ep,_=episodes.record(kind=EpisodeKind.DOCUMENT,title=source['title'],body=source['text'],provenance=Provenance(source_type=SourceType.DOCUMENT,source_ref='synthetic:'+source['id'],captured_at=datetime.fromisoformat(source['recorded_at'])),occurred_at=datetime.fromisoformat(source['occurred_at']) if source['occurred_at'] else None,at=datetime.fromisoformat(source['recorded_at']),source_key='synthetic:'+source['id'])
    head=episodes.source_head('synthetic:'+source['id'])
    if head!=ep.id:episodes.advance_source_head('synthetic:'+source['id'],head,ep.id)
    ids[source['id']]=ep.id
inverse={value:key for key,value in ids.items()}
(ROOT/'synthetic-id-map.json').write_text(json.dumps(ids,indent=2)+'\n')
if 'intake' in sys.argv:
    for source in CAT['sources']:
        sid=source['id']
        if not existing('kingfisher_intake',sid):
            phase('kingfisher_intake:'+sid);start=time.monotonic()
            result=run(episodes,VerifiedLocalProvider(provider),threading.RLock(),source_ids=[ids[sid]],limit=1,stand=Zwischenstand())
            event({'kind':'kingfisher_intake','id':sid,'seconds':round(time.monotonic()-start,4),'ok':result.ok,'state':store.source_state(ids[sid]),'detail':result.detail})
        if not existing('hindsight_intake',sid):
            phase('hindsight_intake:'+sid);start=time.monotonic()
            item={'content':source['text'],'document_id':sid,'metadata':{'original_id':sid,'synthetic':'true','recorded_at':source['recorded_at']},'context':'Künstliche Originalquelle '+sid+'. Quellenzeit '+str(source['occurred_at'])+'. Erfassungszeit '+source['recorded_at']+'. Quelle berichtet; keine unabhängig bestätigten Fakten. Datum der Quelle ist nicht automatisch Datum der berichteten Ereignisse.'}
            if source['occurred_at']:item['timestamp']=source['occurred_at']
            try:
                response=call('POST',prefix('/memories'),{'items':[item],'async':False})
                event({'kind':'hindsight_intake','id':sid,'seconds':round(time.monotonic()-start,4),'ok':True,'response':response})
            except Exception as e:
                event({'kind':'hindsight_intake','id':sid,'seconds':round(time.monotonic()-start,4),'ok':False,'error':str(e)[:800]})
    sys.exit(0)

capture={}
original=provider.complete_json
def recorded(messages,**kwargs):
    capture['messages']=messages;return original(messages,**kwargs)
provider.complete_json=recorded
embedded=LocalEmbedder(base_url='http://127.0.0.1:18934',timeout=30,verify_weights=True).__enter__()
semantic=WorkingMemorySemantic(embedded)
phase('kingfisher_semantic_warmup');start=time.monotonic();warm=semantic.search_with_status(episodes,'BioRegio')
event({'kind':'semantic_warmup','id':'kingfisher','seconds':round(time.monotonic()-start,4),'status':warm.status})

class Capture:
    is_local=True
    name='capture'
    model='capture'
    def complete_json(self,messages,**kwargs):capture['messages']=messages;return Reply(text='{"status":"no_relevant_sources","ids":[]}')

SCHEMA={'type':'object','additionalProperties':False,'properties':{'status':{'type':'string','enum':['reports','unclear','unknown']},'source_ids':{'type':'array','items':{'type':'string'}},'answer':{'type':'string'}},'required':['status','source_ids','answer']}
for index,case in enumerate(CAT['cases']):
    cid=case['id'];q=case['question']
    if not existing('kingfisher_answer',cid):
        phase('kingfisher_retrieval:'+cid);start=time.monotonic();capture.clear()
        prepared=wa.prepare(q,episodes,claims,Capture(),semantic_search=semantic)
        retrieval=time.monotonic()-start
        messages=capture.get('messages',[])
        rows=json.loads(messages[-1]['content'])['sources'] if messages else []
        candidate_ids=[inverse.get(r['episode_id']) for r in prepared.get('basis',[])] if prepared else []
        phase('kingfisher_answer:'+cid);start=time.monotonic();capture.clear()
        try:
            answer=wa.prepare(q,episodes,claims,provider,semantic_search=semantic)
            if answer is None:
                text,links,mode=None,[],'not_handled_by_this_memory_route'
                answer={'status':'no_working_answer','refs':[],'basis':[],'semantic_search_status':semantic.status}
            else:text,links,mode=wa.render(answer,episodes,claims)
            chosen=sorted({inverse[r['episode_id']] for r in answer.get('refs',[])})
            candidate_ids=sorted({inverse[r['episode_id']] for r in answer.get('basis',[])})
            event({'kind':'kingfisher_answer','id':cid,'seconds':round(time.monotonic()-start,4),'retrieval_seconds':round(retrieval,4),'status':answer['status'],'source_ids':chosen,'candidate_source_ids':candidate_ids,'prompt_chars':sum(len(m['content']) for m in capture.get('messages',[])),'answer':text,'mode':mode,'semantic_status':answer.get('semantic_search_status')})
        except Exception as e:event({'kind':'kingfisher_answer','id':cid,'seconds':round(time.monotonic()-start,4),'error':type(e).__name__+': '+str(e)[:300]})
    if not existing('hindsight_recall',cid):
        phase('hindsight_recall:'+cid);start=time.monotonic()
        try:
            result=call('POST',prefix('/memories/recall'),{'query':q,'budget':'mid','max_tokens':2048,'trace':True,'query_timestamp':CAT['clock']})
            original_ids=sorted({r['document_id'] for r in result.get('results',[]) if r.get('document_id')})
            event({'kind':'hindsight_recall','id':cid,'seconds':round(time.monotonic()-start,4),'source_ids':original_ids,'fact_count':len(result.get('results',[])),'response':result})
        except Exception as e:event({'kind':'hindsight_recall','id':cid,'seconds':round(time.monotonic()-start,4),'error':str(e)[:800]})
    if 'reflect' in sys.argv and index < 2 and not existing('hindsight_reflect',cid):
        phase('hindsight_reflect:'+cid);start=time.monotonic()
        try:
            query=q+'\nAntworte auf Deutsch. Heute ist der 12.10.2026. Behandle Erinnerungen als Quellenberichte, nicht als unabhängig bestätigte Tatsachen. Beachte Absage, Bedingung, verschiedene Menschen und Quellenzeit. Bei fehlender Information unknown, bei entscheidender Mehrdeutigkeit unclear. Gib in source_ids die Original-Dokumentkennungen s01 bis s20 aus Metadaten document_id an; erfinde keine Belege. Keine Aktion ausführen.'
            result=call('POST',prefix('/reflect'),{'query':query,'budget':'low','max_tokens':512,'include':{'facts':{}},'response_schema':SCHEMA})
            data=result.get('structured_output') or {}
            event({'kind':'hindsight_reflect','id':cid,'seconds':round(time.monotonic()-start,4),'status':data.get('status'),'source_ids':data.get('source_ids',[]),'answer':data.get('answer') or result.get('text'),'response':result})
        except Exception as e:event({'kind':'hindsight_reflect','id':cid,'seconds':round(time.monotonic()-start,4),'error':str(e)[:800]})
embedded.__exit__();HTTP.close()
