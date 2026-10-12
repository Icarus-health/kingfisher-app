import hashlib,json,time
from pathlib import Path
import probe_category_quality as probe
catalog=probe.ROOT/'docs/runs/2026-10-11-category-guidance/holdout-cases.json'
raw=catalog.read_bytes()
provider=probe.Counted(probe.local_provider('kingfisher-qwen3.5:9b-32k','http://127.0.0.1:11434/v1'))
report={'scope':'synthetic_independent_cases_actual_product','personal_data_used':False,'model':'kingfisher-qwen3.5:9b-32k','holdout_sha256':hashlib.sha256(raw).hexdigest(),'product_category_sha256':hashlib.sha256((probe.ROOT/'sidecar/icarus_memory/memory_categories.py').read_bytes()).hexdigest(),'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':[],'completed':False}
with Path('/private/tmp/kingfisher-category-guidance-product-holdout-retry-20261011.json').open('x') as f:
    for case in json.loads(raw)['cases']:
        started=time.monotonic();result=probe.evaluate(provider,case)
        result['seconds']=round(time.monotonic()-started,3)
        report['results'].append(result);report['model_calls_attempted']=provider.calls
        f.seek(0);json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n');f.truncate();f.flush()
        print(json.dumps({'case':case['id'],'categories':result['categories'],'people':result['people'],'exact_pass':result['meets_requirements']}),flush=True)
        if result['failure_code']: raise RuntimeError('Product or provider failure')
    report['completed']=True
    report['cases_meeting_requirements']=sum(r['meets_requirements'] for r in report['results'])
    f.seek(0);json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n');f.truncate()
