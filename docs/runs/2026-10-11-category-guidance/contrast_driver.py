import json,copy,hashlib,time
from pathlib import Path
import httpx
import probe_category_quality as probe

GUIDANCE='Prüfe die Themen unabhängig von der Entitätenerkennung anhand der Beschreibungen in taxonomy. Eine fehlende Person oder andere Entität ist kein Grund, ein im Original belegtes Thema wegzulassen.'
class Guided(probe.Counted):
    def __init__(self,provider,guided):
        super().__init__(provider);self.guided=guided
    def complete_json(self,messages,**kwargs):
        if self.guided:
            messages=copy.deepcopy(messages);messages[0]['content']+='\n'+GUIDANCE
        return super().complete_json(messages,**kwargs)

cases,digest=probe.load_catalog()
holdout=probe.ROOT/'docs/runs/2026-10-11-category-guidance/holdout-cases.json'
holdout_bytes=holdout.read_bytes();extra=json.loads(holdout_bytes)['cases']
report={'scope':'synthetic_guidance_full_contrast','personal_data_used':False,
        'model':'kingfisher-qwen3.5:9b-32k','catalog_sha256':digest,
        'holdout_sha256':hashlib.sha256(holdout_bytes).hexdigest(),
        'product_category_sha256':hashlib.sha256((probe.ROOT/'sidecar/icarus_memory/memory_categories.py').read_bytes()).hexdigest(),
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'guidance':GUIDANCE,'arms':[],'completed':False}
out=Path('/private/tmp/kingfisher-category-guidance-full-20261011.json')
with out.open('x') as f, httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as c:
    for guided in [False,True]:
        show=c.post('http://127.0.0.1:11434/api/show',json={'model':report['model']});show.raise_for_status()
        metadata=show.json()
        assert metadata.get('details',{}).get('format')=='gguf'
        assert not metadata.get('remote_model') and not metadata.get('remote_host')
        assert any(x.split()==['num_ctx','32768'] for x in metadata['parameters'].splitlines())
        provider=Guided(probe.local_provider(report['model'],'http://127.0.0.1:11434/v1'),guided)
        arm={'guided':guided,'results':[]};report['arms'].append(arm)
        for dataset,rows in [('development',cases),('independent',extra)]:
            for case in rows:
                started=time.monotonic();result=probe.evaluate(provider,case)
                result.update(dataset=dataset,seconds=round(time.monotonic()-started,3))
                arm['results'].append(result);arm['calls']=provider.calls
                f.seek(0);json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n');f.truncate();f.flush()
                print(json.dumps({'guided':guided,'case':case['id'],'categories':result['categories'],'people':result['people'],'exact_pass':result['meets_requirements']}),flush=True)
                if result['failure_code']: raise RuntimeError('Product or provider failure; contrast stopped')
    report['completed']=True
    f.seek(0);json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n');f.truncate()
