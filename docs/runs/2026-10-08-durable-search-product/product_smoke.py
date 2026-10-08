"""Synthetic, netless installed-package HTTP flow; no Ollama or private data."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import httpx
from fastapi.testclient import TestClient
from icarus_memory import EpisodeStore, MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.hintergrund import als_hintergrund
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.policy import Policy
from icarus_memory.providers import Reply
from icarus_memory.server import create_app, _close_persistent_state
from icarus_memory.working_memory_store import WorkingMemoryStore

SOURCE = 'Die Zugangskarte liegt im Schrank neben dem Empfang.'
QUESTION = 'Wo finde ich den Ausweis zum Reinkommen?'

class Selector:
    name = model = 'synthetic-selector'
    is_local = True
    def complete(self, messages, tools):
        return Reply(text='Synthetische Antwort.')
    def complete_json(self, messages, **kwargs):
        rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status':'source_reports','ids':[row['id'] for row in rows]}))

seen = []
def respond(request):
    if request.url.path == '/api/tags':
        return httpx.Response(200, json={'models':[{'name':'synthetic:latest','digest':'a'*64,
            'size':100,'details':{'format':'gguf'}}]})
    if request.url.path == '/api/show':
        return httpx.Response(200, json={'details':{'format':'gguf'},'model_info':{
            'general.architecture':'bert','general.parameter_count':100},'capabilities':['embedding']})
    assert request.url.path == '/api/embed'
    payload = json.loads(request.content)
    seen.append(payload['input'])
    assert payload['keep_alive'] == '15s'
    return httpx.Response(200, json={'model':'synthetic:latest',
        'embeddings':[[1.,0.] for _ in payload['input']]})

def factory():
    return LocalEmbedder(model='synthetic:latest', keep_alive='15s', verify_weights=True,
                         transport=httpx.MockTransport(respond))

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    os.environ['ICARUS_DATA_DIR'] = folder
    os.environ['ICARUS_MEMORY_SEMANTIC'] = ''
    os.environ['KINGFISHER_DURABLE_MEMORY_SEARCH'] = '1'
    os.environ['ICARUS_SIDECAR_TOKEN'] = 'synthetic-only-owner'
    episodes = EpisodeStore(root/'episodes.sqlite3')
    claims = ClaimStore(root/'knowledge.sqlite3')
    audit = AuditLog(root/'audit.sqlite3')
    provider = Selector()
    agent = Agent(store=SelfModelStore(MemoryBackend(),subject_id='synthetic'),policy=Policy(),
        audit=audit,tools={},provider=provider,knowledge=claims,episodes=episodes,max_rounds=1)
    app = create_app(agent._store,agent=agent)
    client = TestClient(app,headers={'X-Icarus-Token':'synthetic-only-owner'})
    try:
        response = client.post('/api/v1/sources/documents',json={'filename':'synthetic.txt','body':SOURCE})
        assert response.status_code == 200, response.text
        identifier = response.json()['id']
        memory = WorkingMemoryStore(episodes)
        snapshot = memory.pending(episode_ids=[identifier])[0]
        assert memory.commit(snapshot,[{'start':0,'end':len(SOURCE),'kind':'fact'}],model='synthetic-classifier')
        service = app.state.semantic_search
        service._factory = factory
        with als_hintergrund():
            assert service.index_batch().ok
        assert len(seen) == 1 and SOURCE in seen[0][0]
        seen.clear()
        response = client.post('/api/v1/conversations',json={})
        assert response.status_code == 201
        conversation = response.json()['conversation']['id']
        response = client.post(f'/api/v1/conversations/{conversation}/messages',json={
            'message':QUESTION,'answer_mode':'auto'})
        assert response.status_code == 201, response.text
        answer = response.json()['messages'][-1]
        assert SOURCE in answer['content']
        assert seen == [[QUESTION]], seen
        before = len(seen)
        assert SOURCE in str(client.get(f'/api/v1/conversations/{conversation}').json())
        coverage = client.get('/api/v1/memory/coverage').json()['semantic_index']
        assert coverage['indexed'] == 1 and coverage['pending'] == 0
        assert len(seen) == before
        episodes.ignore(identifier)
        assert SOURCE not in str(client.get(f'/api/v1/conversations/{conversation}').json())
        assert len(seen) == before
        with sqlite3.connect(root/'episodes.sqlite3') as plain:
            assert plain.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
            assert not plain.execute("SELECT 1 FROM sqlite_master WHERE sql LIKE '%USING vec0%'").fetchone()
        print(json.dumps({'synthetic_only':True,'background_vectors':1,'query_embedding_inputs':1,
            'history_and_status_embedding_inputs':0,'withdrawal_passed':True,
            'original_sqlite_extension_free':True,'version':os.environ.get('KINGFISHER_FASSUNG')}))
    finally:
        client.close()
        _close_persistent_state(app)
