"""Component ablation: local Hindsight-used ranker on unchanged German originals."""
import json,time,statistics,os
from pathlib import Path
import onnxruntime as ort,psutil
from flashrank import Ranker,RerankRequest
ROOT=Path(os.environ['KINGFISHER_HINDSIGHT_BENCH_DIR']).resolve()
catalog=json.loads((ROOT/'catalog.json').read_text())
start=time.monotonic()
ranker=Ranker(model_name='ms-marco-MultiBERT-L-12',cache_dir=str(ROOT/'reranker'),max_length=256,log_level='WARNING')
# This ablation bounds CPU threads; does not alter Hindsight's service or Kingfisher.
options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.enable_cpu_mem_arena=False
ranker.session=ort.InferenceSession(str(ranker.model_dir/'flashrank-MultiBERT-L12_Q.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
load=time.monotonic()-start
passages=[{'id':s['id'],'text':s['text']} for s in catalog['sources']]
results=[]
for case in catalog['cases']:
    start=time.monotonic()
    ranked=ranker.rerank(RerankRequest(query=case['question'],passages=passages))
    elapsed=time.monotonic()-start
    order=[r['id'] for r in ranked]
    expected=set(case['required_source_ids'])
    result={'id':case['id'],'seconds':round(elapsed,4),'ranked_ids':order,'scores':{r['id']:float(r['score']) for r in ranked},'top3_has_all_required_history':expected<=set(order[:3]),'top5_has_all_required_history':expected<=set(order[:5]),'top1_has_any_required':bool(expected.intersection(order[:1])) if expected else None}
    results.append(result)
out={'component':'same multilingual FlashRank reranker on unchanged originals','load_seconds':round(load,4),'max_length':256,'threads':2,'rss_mib':round(psutil.Process().memory_info().rss/1024**2,1),'results':results,'warning':'Reordering only. No deletion or confidence threshold, no response/abstention guarantee, no product integration.'}
(ROOT/'original-reranker-ablation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'load_seconds':out['load_seconds'],'rss_mib':out['rss_mib'],'cases':len(results),'median_seconds':round(statistics.median(r['seconds'] for r in results),4),'top3_history_complete':sum(r['top3_has_all_required_history'] for r in results),'top5_history_complete':sum(r['top5_has_all_required_history'] for r in results),'top1_hit_cases':sum(r['top1_has_any_required'] is True for r in results)}))
