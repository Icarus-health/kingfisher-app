"""Disposable gateway with artificial originals only; never the personal server."""
from copy import copy
import json
import os
from pathlib import Path
import tempfile

from fastapi import FastAPI, HTTPException, Request
import httpx

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.procedures import ProcedureStore
from icarus_memory.harness_broker import Broker
from icarus_memory.harness_protocol import register
from icarus_memory.providers import OpenAICompatible
from icarus_memory.local_context_profile import verify_lifecycle

temporary = tempfile.TemporaryDirectory(prefix='kf-artificial-gateway-')
episodes = EpisodeStore(Path(temporary.name)/'sources.db')
skills = ProcedureStore(Path(temporary.name)/'skills.db')
def put(body):
    return episodes.record(EpisodeKind.DOCUMENT,'Künstliche Gedächtnisquelle',body,
                           Provenance(source_type=SourceType.DOCUMENT))[0]
source = put('Die künstliche Zugangskarte liegt in Fach A42.')
outside = put('Die Zugangskarte liegt im Safe Z99. Nicht für diesen Auftrag freigegeben.')
originals = {e.id:e.to_dict() for e in (source,outside)}
candidate = skills.propose(dict(name='kartenfundort',title='Fundort im Original prüfen',area='analysis',
    description='Fundort einer Zugangskarte anhand des Originals prüfen.',triggers=['zugangskarte'],
    steps=['Original mit kurzem wörtlichen Begriff suchen.','Fundort und Quellen-ID nennen.'],
    positive='Wo ist die Zugangskarte?',negative='Was ist morgen zu tun?'))
skills.accept(candidate['id'])
broker = Broker(episodes,skills)
model = 'kingfisher-qwen3.5:9b-8k'
os.environ['ICARUS_OLLAMA_8K_PROFILE'] = model
provider = OpenAICompatible(model,'artificial-local','http://host.docker.internal:11434/v1',
                            trusted_local_hosts=('host.docker.internal',))
identity = None
calls = []
tool_calls = []
original_invoke = broker.invoke
def invoke(token,name,args):
    result = original_invoke(token,name,args)
    tool_calls.append(dict(name=name,arguments=args))
    return result
broker.invoke = invoke
def infer(messages,tools,permitted):
    global identity
    local = copy(provider)
    local._verified_local_permitted = permitted
    local._request_payload = lambda p:{**p,'max_tokens':256,'temperature':0}
    current = verify_lifecycle(local)
    if identity is None: identity = current
    if current != identity: raise RuntimeError('ModelChanged')
    with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
        active = client.get('http://host.docker.internal:11434/api/ps')
        active.raise_for_status()
        if any(row.get('name') not in {model,'bge-m3:latest'} for row in active.json().get('models',[])):
            raise RuntimeError('OtherModelActive')
    row = dict(status='started',skills_automatic='Fundort im Original prüfen' in messages[0]['content'])
    calls.append(row)
    try:
        reply = local.complete(messages,tools)
        if verify_lifecycle(local) != identity: raise RuntimeError('ModelChanged')
        row['status']='complete'
        return reply
    except Exception as exc:
        row.update(status='failed',error=type(exc).__name__,detail=str(exc)[:300])
        raise

app = FastAPI()
register(app,broker,model=model,infer=infer)
used = False
@app.get('/health')
def health(): return dict(status='ok',synthetic_only=True)

@app.post('/control/pilot')
def pilot(request:Request):
    global used
    import secrets
    expected = os.environ['KF_GATEWAY_CONTROL_KEY']
    if not secrets.compare_digest(request.headers.get('Authorization',''),'Bearer '+expected):
        raise HTTPException(401,'Unauthorized')
    if used: raise HTTPException(409,'One bounded artificial pilot only')
    used = True
    grant = broker.issue('Wo liegt die Zugangskarte? Bitte mit Quelle.',area='analysis',sources=[source.id])
    try:
        with httpx.Client(timeout=115,trust_env=False,follow_redirects=False) as client:
            response = client.post('http://kingfisher-worker:3001/run',headers={
                'Authorization':'Bearer '+os.environ['KF_WORKER_SERVICE_KEY']},
                json=dict(token=grant['token'],request='Wo liegt die Zugangskarte? Bitte mit Quelle.'))
        result = response.json()
        text = result.get('text','')
        checks = dict(worker_complete=response.status_code==200 and result.get('status')=='complete',
            location_token_present='A42' in text,source_cited=source.id in text,
            outside_scope_excluded='Z99' not in text and outside.id not in text,
            originals_unchanged=all(episodes.get(i).to_dict()==old for i,old in originals.items()),
            skills_automatic=bool(calls) and all(c['skills_automatic'] for c in calls),
            real_scoped_search=any(c['name']=='memory_search' for c in tool_calls),
            current_before_return=broker.current(grant['token']))
        return dict(status='passed' if all(checks.values()) else 'failed',synthetic_only=True,
            semantic_review_required=True,checks=checks,answer=text,calls=calls,tool_calls=tool_calls,
            model_digest=identity.digest if identity else None)
    finally: broker.cancel(grant['id'])
