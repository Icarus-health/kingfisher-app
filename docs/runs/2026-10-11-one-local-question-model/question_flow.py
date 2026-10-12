"""Actual HTTP memory questions with one verified local model and synthetic originals.

Working interpretations are indexed deterministically: this qualifies retrieval/
selection/quote presentation, not model ingestion, categorization or embeddings.
The frozen control corpus predates this experiment. Personal settings are never read.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

REPO = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.path[:0] = [str(REPO / 'sidecar'), str(REPO / 'scripts')]
DATA = ROOT / 'synthetic-state'
DATA.mkdir()
os.environ.update(ICARUS_DATA_DIR=str(DATA), ICARUS_SIDECAR_TOKEN='synthetic-only',
                  ICARUS_MEMORY_SEMANTIC='0', KINGFISHER_DURABLE_MEMORY_SEARCH='0')

from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.agent_verdrahtung import verdrahte_speicher, verdrahte_zusaetze
from icarus_memory.audit import AuditLog
from icarus_memory.local_model_guard import VerifiedLocalProvider
from icarus_memory.policy import Policy
from icarus_memory.server import create_app
from icarus_memory.working_memory_store import WorkingMemoryStore
from probe_working_memory_end_to_end import Meter, evaluate, local_provider

corpus_path = REPO / 'docs/runs/2026-10-09-restored-memory-and-today/cos-closed/catalog.json'
corpus = json.loads(corpus_path.read_text())
assert corpus['synthetic'] and corpus['frozen_before_model_run']
holdout_path = REPO / 'docs/runs/2026-10-08-closed-model-memory/anchor-control-holdout-sources.json'
corpus['sources'].extend(json.loads(holdout_path.read_text()))
provider = Meter(VerifiedLocalProvider(local_provider('kingfisher-qwen3.5:9b-32k', 'http://127.0.0.1:11439/v1')))
report = dict(synthetic_only=True, corpus_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
              holdout_sha256=hashlib.sha256(holdout_path.read_bytes()).hexdigest(),
              model=provider.model, sentences=False, semantic_search=False,
              ingestion='product upload route via ASGI TestClient, deterministic full-original fact indexing; NOT model ingestion',
              scope='current product HTTP routes via ASGI TestClient (no TCP server), isolated fresh conversations, same model for understanding and selection',
              code_commit=os.environ['KINGFISHER_FASSUNG'], rows=[], completed=False)

def save():
    (ROOT / 'answers.new').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'answers.new').replace(ROOT / 'answers.json')

def open_app():
    audit = AuditLog(DATA / 'audit.sqlite3')
    agent = Agent(SelfModelStore(MemoryBackend(), 'synthetic'), Policy(), audit, {}, provider=provider)
    app = create_app(agent=agent, audit=audit)
    return app, TestClient(app, headers={'X-Icarus-Token': 'synthetic-only'})

def close_app(app, client):
    client.close()
    for name in ('semantic_search', 'mac_calendar', 'recovery_jobs', 'audit', 'tasks',
                 'workspace', 'episodes', 'proposals', 'conversations', 'claims', 'regeln'):
        close = getattr(getattr(app.state, name, None), 'close', None)
        if callable(close):
            close()

def question_agent(app):
    agent = Agent(SelfModelStore(MemoryBackend(), 'synthetic'), Policy(), app.state.audit, {},
                  provider=provider, episodes=app.state.episodes, knowledge=app.state.claims)
    verdrahte_speicher(app, agent)
    verdrahte_zusaetze(app, agent)
    agent._frage_anbieter = lambda: provider
    agent._saetze = False
    agent._pruefung = lambda: None
    app.state.agent = agent

app = client = None
try:
    app, client = open_app()
    alias = {}
    originals = {}
    store = WorkingMemoryStore(app.state.episodes)
    for source in corpus['sources']:
        r = client.post('/api/v1/sources/documents', json={'filename': source['title'] + '.txt', 'body': source['text']})
        r.raise_for_status()
        identifier = r.json()['id']
        assert app.state.episodes.get(identifier).body == source['text']
        snapshot = store.pending(episode_ids=[identifier])[0]
        assert store.commit(snapshot, [{'start': 0, 'end': len(source['text']), 'kind': 'fact'}], model='probe:deterministic')
        alias[identifier] = source['id']
        originals[identifier] = source['text']
    close_app(app, client)
    app = client = None
    app, client = open_app()
    report['reopened_before_questions'] = True
    saved = None
    for item in corpus['questions']:
        question_agent(app)
        r = client.post('/api/v1/conversations', json={})
        r.raise_for_status()
        cid = r.json()['conversation']['id']
        started, before = time.monotonic(), provider.calls
        r = client.post('/api/v1/conversations/' + cid + '/messages', json={'message': item['q'], 'answer_mode': 'memory_evidence'})
        r.raise_for_status()
        message = r.json()['messages'][-1]
        context = message['metadata'].get('context', {})
        row = evaluate(item, SimpleNamespace(context=context, reply=message['content']), alias)
        counts = provider.outcomes(before)
        row.update(id=item['id'], seconds=round(time.monotonic() - started, 3),
                   calls=provider.calls-before, model_outputs=provider.outputs(before),
                   provider_errors=counts['failed'], provider_pending=counts['pending'])
        row['selection_pass'] &= not (row['provider_errors'] or row['provider_pending'])
        report['rows'].append(row)
        if saved is None and row['status'] == 'working_reports' and context.get('working_answer', {}).get('refs'):
            saved = (cid, [ref['episode_id'] for ref in context['working_answer']['refs']])
        save()
        print(item['id'], row['status'], row['shown_sources'], row['seconds'], flush=True)
    report['originals_preserved'] = all(app.state.episodes.get(i).body == body for i, body in originals.items())
    if saved:
        close_app(app, client)
        app = client = None
        app, client = open_app()
        question_agent(app)
        cid, identifiers = saved
        before = provider.calls
        for identifier in set(identifiers):
            app.state.episodes.ignore(identifier)
        r = client.get('/api/v1/conversations/' + cid)
        r.raise_for_status()
        context = r.json()['messages'][-1]['metadata'].get('context', {})
        report['withdrawal_after_restart'] = dict(status=context.get('answer_contract', {}).get('status'),
            no_links=not context.get('source_links'), provider_calls=provider.calls-before,
            originals_preserved=all(app.state.episodes.get(i).body == originals[i] for i in identifiers))
    report['completed'] = True
except BaseException as exc:
    report['runtime_error'] = type(exc).__name__ + ': ' + str(exc)
    raise
finally:
    save()
    if app is not None:
        close_app(app, client)
