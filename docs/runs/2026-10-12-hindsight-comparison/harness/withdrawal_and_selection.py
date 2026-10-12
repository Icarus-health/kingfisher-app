import sys,json,time,hashlib,os
from pathlib import Path
import httpx
ROOT=Path(os.environ['KINGFISHER_HINDSIGHT_BENCH_DIR']).resolve()
REPO=Path(os.environ['KINGFISHER_REPO']).resolve()
sys.path.insert(0,str(REPO/'sidecar'))
from icarus_memory.episodes import EpisodeStore
from icarus_memory.claims import ClaimStore
from icarus_memory.providers import OpenAICompatible
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.working_memory_semantic import WorkingMemorySemantic
from icarus_memory import working_memory_answers as wa
cat=json.loads((ROOT/'catalog.json').read_text());ids=json.loads((ROOT/'synthetic-id-map.json').read_text());inverse={v:k for k,v in ids.items()}
bank='kf-main-'+hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest()[:8]
prefix='/v1/default/banks/'+bank
client=httpx.Client(base_url='http://127.0.0.1:18935',timeout=60,trust_env=False)
provider=OpenAICompatible('kingfisher-qwen3.5:9b-32k',base_url='http://127.0.0.1:18934/v1');provider._client=lambda timeout:httpx.Client(timeout=timeout,trust_env=False)
ep=EpisodeStore(ROOT/'kingfisher-episodes.sqlite3');cl=ClaimStore(ROOT/'kingfisher-knowledge.sqlite3')
embed=LocalEmbedder(base_url='http://127.0.0.1:18934',timeout=30,verify_weights=True).__enter__();semantic=WorkingMemorySemantic(embed)
raw=[];original=provider.complete_json

def traced(messages,**kwargs):
 reply=original(messages,**kwargs);raw.append({'request':json.loads(messages[-1]['content']),'reply':reply.text});return reply
provider.complete_json=traced
(ROOT/'phase.txt').write_text('kingfisher_selection_diagnosis')
q=next(c['question'] for c in cat['cases'] if c['id']=='withdrawn_commitment')
a=wa.prepare(q,ep,cl,provider,semantic_search=semantic)
trace={'question':q,'calls':raw.copy(),'selected_originals':[inverse[r['episode_id']] for r in a.get('refs',[])],'answer':wa.render(a,ep,cl)[0]}
(ROOT/'selection-diagnosis.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
print('diagnosis',trace['selected_originals'],flush=True)
raw.clear();q='Wie lautet der Aufbewahrungscode für das Testobjektiv?'
(ROOT/'phase.txt').write_text('source_withdrawal_before')
a=wa.prepare(q,ep,cl,provider,semantic_search=semantic)
before_text,_,before_mode=wa.render(a,ep,cl)
rb=client.post(prefix+'/memories/recall',json={'query':q,'budget':'mid','max_tokens':2048,'query_timestamp':cat['clock']});rb.raise_for_status()
before=rb.json();before_ids=sorted({r['document_id'] for r in before['results'] if r.get('document_id')})
assert 's19' in [inverse[r['episode_id']] for r in a.get('refs',[])],a
assert 's19' in before_ids
# Own artificial store only. Preserve the original Kingfisher text, revoke its evidence use.
ep.ignore(ids['s19']);old_text,_,old_mode=wa.render(a,ep,cl)
(ROOT/'phase.txt').write_text('source_withdrawal_after')
after=wa.prepare(q,ep,cl,provider,semantic_search=semantic)
after_ids=[inverse[r['episode_id']] for r in after.get('refs',[])] if after else []
removed=client.delete(prefix+'/documents/s19');removed.raise_for_status()
ra=client.post(prefix+'/memories/recall',json={'query':q,'budget':'mid','max_tokens':2048,'query_timestamp':cat['clock']});ra.raise_for_status();response=ra.json()
hs_after=sorted({r['document_id'] for r in response['results'] if r.get('document_id')})
out={'question':q,'kingfisher':{'before_status':a['status'],'before_source_ids':[inverse[r['episode_id']] for r in a.get('refs',[])],'before_answer':before_text,'old_answer_mode_after_withdrawal':old_mode,'old_answer_after_withdrawal':old_text,'fresh_status':after.get('status') if after else 'not_handled_by_this_memory_route','fresh_source_ids':after_ids,'original_retained':ep.get(ids['s19']).body==next(s['text'] for s in cat['sources'] if s['id']=='s19')},'hindsight':{'before_source_ids':before_ids,'delete_status_code':removed.status_code,'after_source_ids':hs_after,'recall_after':response},'synthetic_only':True}
(ROOT/'withdrawal-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert 's19' not in after_ids
assert '7342' not in old_text
assert 's19' not in hs_after
print(json.dumps({'withdrawal_pass':True,'kingfisher_old_mode':old_mode,'kingfisher_fresh_status':out['kingfisher']['fresh_status'],'original_retained':out['kingfisher']['original_retained'],'hindsight_delete_status':removed.status_code}),flush=True)
embed.__exit__();client.close()
