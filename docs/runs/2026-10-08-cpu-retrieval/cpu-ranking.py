import sys, json, math, time, hashlib, urllib.request
from pathlib import Path
catalog_path=Path(sys.argv[1]); catalog=json.loads(catalog_path.read_text())
base='http://127.0.0.1:11434'
def request(path, payload=None):
    body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    req=urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=150) as r: return json.load(r)
tags=request('/api/tags')
model=next(m for m in tags['models'] if m['name']=='bge-m3:latest')
assert len(model['digest'])==64 and not model.get('remote_host') and not model.get('remote_model')
inputs=[{'kind':'source','id':s['id'],'text':s['title']+': '+s['text']} for s in catalog['sources']]
inputs += [{'kind':q['type'],'q':q['q'],'expect':q['expect'],'text':q['q']} for q in catalog['questions']]
started=time.monotonic(); vectors=[]
for offset in range(0,len(inputs),8):
    batch=inputs[offset:offset+8]
    result=request('/api/embed',{'model':'bge-m3:latest','input':[i['text'] for i in batch],
        'keep_alive':'2m','options':{'num_gpu':0,'num_thread':2,'num_ctx':2048}})
    found=result['embeddings']; assert len(found)==len(batch)
    for v in found:
        assert len(v)==1024 and all(math.isfinite(x) for x in v)
        norm=math.sqrt(sum(x*x for x in v)); assert norm>0
        vectors.append([x/norm for x in v])
    print(f'embedded {len(vectors)}/{len(inputs)}',file=sys.stderr,flush=True)
source_vectors={i['id']:v for i,v in zip(inputs,vectors) if i['kind']=='source'}
rows=[]
for item,vector in zip(inputs,vectors):
    if item['kind']=='source': continue
    scores=sorted(((sum(a*b for a,b in zip(vector,v)),sid) for sid,v in source_vectors.items()),reverse=True)
    expected=set(item['expect'])
    rows.append({'q':item['q'],'type':item['kind'],'expect':sorted(expected),
        'ranked_sources':[[sid,round(score,6)] for score,sid in scores],
        'expected_ranks':{sid:next(i+1 for i,(_,s) in enumerate(scores) if s==sid) for sid in expected},
        'threshold_hits':[sid for score,sid in scores if score>=.55]})
print(json.dumps({'synthetic_only':True,'runtime':'isolated Linux arm64 CPU;2 cores;6GiB;read-only installed weights;no cloud',
    'ollama_version':request('/api/version')['version'],'model':model['name'],'model_digest':model['digest'],
    'catalog_sha256':hashlib.sha256(catalog_path.read_bytes()).hexdigest(),'inputs':len(inputs),
    'seconds':round(time.monotonic()-started,3),'rows':rows},ensure_ascii=False,indent=2))
