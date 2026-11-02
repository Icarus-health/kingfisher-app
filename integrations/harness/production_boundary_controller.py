"""Disposable original UI + separate broker listener, with artificial data only.

Used by the OS boundary probe. Inference is injected, NOT a quality benchmark.
Run Uvicorn with lifespan off: no application integrations/background jobs start.
"""
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.harness_broker import Broker
from icarus_memory.harness_protocol import register
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply, ToolCall
from icarus_memory.server import create_app

temporary = tempfile.TemporaryDirectory(prefix='kf-boundary-artificial-')
root = Path(temporary.name)
(root/'ui').mkdir()
(root/'ui'/'index.html').write_text('<html><body>Artificial UI boundary fixture</body></html>')
os.environ['ICARUS_UI_DIR'] = str(root/'ui')
os.environ['ICARUS_DATA_DIR'] = str(root/'data')
if not os.environ.get('ICARUS_SIDECAR_TOKEN') or not os.environ.get('KF_GATEWAY_CONTROL_KEY'):
    raise RuntimeError('Artificial fixture credentials missing')
app = create_app(SelfModelStore(MemoryBackend(), subject_id='artificial'))
episodes, skills = app.state.episodes, app.state.procedures
def put(text):
    return episodes.record(EpisodeKind.DOCUMENT, 'Artificial boundary source', text,
                           Provenance(source_type=SourceType.DOCUMENT))[0]
source = put('Die künstliche Zugangskarte liegt in Fach A42.')
outside = put('Die Zugangskarte liegt in Safe Z99. Außerhalb des Auftrags.')
originals = {e.id:e.to_dict() for e in (source,outside)}
skill = skills.propose(dict(name='originalfundort', title='Fundort im Original prüfen', area='analysis',
    description='Originalfundort einer Zugangskarte prüfen.', triggers=['zugangskarte'],
    steps=['Wörtlich suchen.', 'Fundort und Quelle nennen.'],
    positive='Wo liegt die Zugangskarte?', negative='Was steht morgen an?'))
skills.accept(skill['id'])
broker = Broker(episodes, skills)
worker_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
model = 'kingfisher-qwen3.5:9b-8k'
calls, tool_calls = [], []
mode = 'baseline'
started, release = threading.Event(), threading.Event()
grant = None
used = set()
original_invoke = broker.invoke
def invoke(token, name, arguments):
    result = original_invoke(token, name, arguments)
    tool_calls.append(name)
    return result
broker.invoke = invoke

def infer(messages, tools, permitted):
    calls.append({'skills_automatic':'Fundort im Original prüfen' in messages[0]['content']})
    if mode != 'baseline':
        started.set()
        if not release.wait(15):
            raise RuntimeError('Artificial coordination timeout')
    if not permitted():
        raise RuntimeError('Cancelled artificial request')
    evidence = [m.get('content','') for m in messages if m.get('role')=='tool']
    if not evidence:
        return Reply(tool_calls=[ToolCall('boundary-search','mcp__kingfisher__memory_search',
                                         {'query':'Zugangskarte'})],model=model)
    text = json.dumps(evidence, ensure_ascii=False)
    if 'A42' not in text or source.id not in text or outside.id in text or 'Z99' in text:
        raise RuntimeError('Artificial scope mismatch')
    return Reply(text='Die Zugangskarte liegt in Fach A42. Quelle: '+source.id,model=model)

register(worker_app, broker, model=model, infer=infer)
@worker_app.get('/health')
def worker_health():
    return {'status':'ok','synthetic_only':True}
threading.Thread(target=lambda:uvicorn.run(worker_app,host='0.0.0.0',port=8892,
    lifespan='off',log_level='warning',access_log=False),daemon=True).start()

def authorize(request):
    if not secrets.compare_digest(request.headers.get('Authorization',''),
                                  'Bearer '+os.environ['KF_GATEWAY_CONTROL_KEY']):
        raise HTTPException(401,'Unauthorized artificial fixture')

@app.get('/fixture/readiness')
def readiness():
    return {'status':'ok','synthetic_only':True}

@app.post('/fixture/pilot')
def pilot(request:Request):
    global mode,grant
    authorize(request)
    case = request.query_params.get('case','baseline')
    if case not in {'baseline','cancel','source_revoked'} or case in used:
        raise HTTPException(409,'One artificial run per case')
    used.add(case)
    mode=case;started.clear();release.clear()
    offset=len(calls)
    grant=broker.issue('Wo liegt die Zugangskarte? Bitte mit Quelle.',area='analysis',sources=[source.id])
    coordination={}
    def interrupt():
        if not started.wait(15):
            coordination['started']=False;release.set();return
        try:
            tick=time.monotonic()
            with httpx.Client(timeout=3,trust_env=False,follow_redirects=False) as local:
                response=local.get('http://127.0.0.1:8890/fixture/readiness')
            coordination.update(ui_responsive=response.status_code==200,
                                ui_seconds=round(time.monotonic()-tick,3))
            if case=='cancel':broker.cancel(grant['id'])
            else:episodes.ignore(source.id)
            coordination['interrupted']=True
        finally:release.set()
    if case!='baseline':threading.Thread(target=interrupt,daemon=True).start()
    control={'Authorization':'Bearer '+os.environ['KF_GATEWAY_CONTROL_KEY']}
    with httpx.Client(timeout=115,trust_env=False,follow_redirects=False) as client:
        health=client.get('http://kingfisher-gateway-control:8891/controller/health',headers=control)
        if health.status_code!=200:
            raise HTTPException(503,'Artificial proxy not initialized')
        response=client.post('http://kingfisher-gateway-control:8891/controller/run',headers=control,
            json={'token':grant['token'],'request':'Wo liegt die Zugangskarte? Bitte mit Quelle.'})
    result=response.json()
    text=result.get('text','')
    rows=calls[offset:]
    common=dict(synthetic_only=True,injected_model_only=True,live_semantic_verified=False,
                case=case,status=response.status_code,model_calls=len(rows),coordination=coordination)
    if case=='baseline':
        checks=dict(complete=response.status_code==200 and result.get('status')=='complete',
            scope='A42' in text and source.id in text and 'Z99' not in text and outside.id not in text,
            actual_search='memory_search' in tool_calls,
            automatic_skills=bool(rows) and all(r['skills_automatic'] for r in rows),
            originals_unchanged=all(episodes.get(i).to_dict()==d for i,d in originals.items()))
        common['text']=text
    else:
        checks=dict(result_withheld=response.status_code!=200 and not text,
            interrupted=coordination.get('interrupted') is True,
            ui_responsive=coordination.get('ui_responsive') is True and coordination.get('ui_seconds',99)<3,
            capability_revoked=not broker.current(grant['token']),
            original_bodies_unchanged=all(episodes.get(i).body==d['body'] for i,d in originals.items()))
    common.update(checks=checks,passed=all(checks.values()))
    broker.cancel(grant['id'])
    return common

# The ordinary app's final UI mount intentionally catches unknown URLs.
# Fixture-only control routes must precede it; no personal server uses this file.
app.router.routes[:] = ([route for route in app.router.routes
                        if getattr(route,'path','').startswith('/fixture/')]
                       + [route for route in app.router.routes
                          if not getattr(route,'path','').startswith('/fixture/')])
