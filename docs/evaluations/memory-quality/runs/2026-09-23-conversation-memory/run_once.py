"""Synthetic HTTP capture plus real local classification/selection; no user data."""
import argparse
import json
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.backends import MemoryBackend
from icarus_memory.model import SourceType
from icarus_memory.policy import Policy
from icarus_memory.providers import OpenAICompatible, Reply
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from icarus_memory.working_memory_worker import run

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / 'expected.json').read_text())
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
OUTPUT = parser.parse_args().output
if OUTPUT.exists():
    raise SystemExit('Archived output already exists; use a new evidence directory.')
result = {'started_at': datetime.now().astimezone().isoformat(),
          'scope': EXPECTED['chat_acknowledgement'], 'sources': [], 'questions': [], 'calls': []}
real = OpenAICompatible('qwen3.5:4b', base_url='http://127.0.0.1:11434/v1')
assert real.is_local

def save():
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

class Provider:
    name, model, is_local = 'synthetic-chat-real-memory', real.model, True
    def complete(self, messages, tools):
        return Reply(text='Gesprächsbeitrag empfangen.')
    def complete_json(self, messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        start = time.perf_counter()
        call = {'kind': 'classification' if 'blocks' in data else 'selection',
                'question': data.get('question')}
        try:
            reply = real.complete_json(messages, max_tokens=max_tokens, schema=schema)
            call['text'] = reply.text
            return reply
        except Exception as error:
            call['error'] = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            call['seconds'] = round(time.perf_counter() - start, 3)
            result['calls'].append(call)
            save()

provider = Provider()

def build(folder):
    os.environ['ICARUS_DATA_DIR'] = str(folder)
    os.environ['ICARUS_SIDECAR_TOKEN'] = 'synthetic-local-owner'
    store = SelfModelStore(MemoryBackend(), subject_id='synthetic')
    audit = AuditLog(folder / 'audit.sqlite3')
    agent = Agent(store, Policy(), audit, {}, provider=provider, max_rounds=1)
    app = create_app(store, agent=agent, audit=audit)
    return app, TestClient(app, headers={'X-Icarus-Token': 'synthetic-local-owner'})

def close(app, client):
    client.close()
    for name in ('audit', 'tasks', 'workspace', 'episodes', 'proposals', 'conversations', 'claims', 'regeln', 'mac_calendar'):
        action = getattr(getattr(app.state, name, None), 'close', None)
        if callable(action):
            action()

def conversation(client):
    response = client.post('/api/v1/conversations', json={})
    response.raise_for_status()
    return response.json()['conversation']['id']

def post(client, conversation_id, text, mode='auto'):
    response = client.post(f'/api/v1/conversations/{conversation_id}/messages',
                           json={'message': text, 'answer_mode': mode})
    response.raise_for_status()
    return response.json()

with tempfile.TemporaryDirectory(prefix='kingfisher-conversation-qualification-') as folder:
    folder = Path(folder)
    app, client = build(folder)
    source_conversation = conversation(client)
    by_episode = {}
    def source(source_id):
        entry = next(item for item in EXPECTED['sources'] if item['id'] == source_id)
        payload = post(client, source_conversation, entry['text'], 'chat')
        user = next(item for item in reversed(payload['messages']) if item['role'] == 'user')
        from icarus_memory.conversation_memory import find
        episode = find(app.state.episodes, source_conversation, user['id'])
        assert episode is not None and episode.provenance.source_type is SourceType.CHAT
        by_episode[episode.id] = source_id
        status = run(app.state.episodes, provider, threading.Lock(), source_ids=[episode.id])
        result['sources'].append({'id': source_id, 'episode_id': episode.id,
                                  'created_at': user['created_at'], 'worker': status.to_dict()})
        save()
    def question(question_id):
        entry = next(item for item in EXPECTED['questions'] if item['id'] == question_id)
        cid = conversation(client)
        payload = post(client, cid, entry['text'])
        answer = payload['messages'][-1]
        prepared = answer.get('metadata', {}).get('context', {}).get('working_answer', {})
        selected = [by_episode.get(ref['episode_id'], 'other') for ref in prepared.get('refs', [])]
        result['questions'].append({'id': question_id, 'conversation_id': cid,
            'status': prepared.get('status'), 'selected_sources': selected, 'answer': answer['content'],
            'required_sources_present': set(entry['required_sources']) <= set(selected),
            'forbidden_sources_absent': not set(entry['forbidden_sources']) & set(selected),
            'required_text_present': all(text in answer['content'] for text in entry['required_text'])})
        save()
        return cid
    try:
        for sid in ('U1', 'U2', 'U3'):
            source(sid)
        question('Q1')
        question('Q2')
        close(app, client)
        app, client = build(folder)
        result['restart'] = True
        third = question('Q3')
        source('U4')
        question('Q4')
        calls_before_scan = len(result['calls'])
        run(app.state.episodes, provider, threading.Lock())
        result['lookup_only_turns_do_not_trigger_classification'] = len(result['calls']) == calls_before_scan
        result['card_answer_survives_background_scan'] = 'grünen Umschlag' in client.get(
            f'/api/v1/conversations/{third}').json()['messages'][-1]['content']
        u3 = next(eid for eid, sid in by_episode.items() if sid == 'U3')
        response = client.post(f'/api/v1/episodes/{u3}/ignore')
        response.raise_for_status()
        views = [client.get(f'/api/v1/conversations/{cid}').json() for cid in (third, source_conversation)]
        views.append(client.get('/api/v1/conversations').json())
        fresh = post(client, conversation(client), 'Wo liegt die Ersatzkarte für das Studio Nordstern?')
        result['withdrawal'] = {
            'old_and_list_payloads_hide_code': 'SYNTH-NACHTIGALL-826' not in json.dumps(views),
            'fresh_answer_hides_code': 'SYNTH-NACHTIGALL-826' not in fresh['messages'][-1]['content'],
            'original_preserved': 'SYNTH-NACHTIGALL-826' in app.state.episodes.get(u3).body,
        }
        result['claims_revision'] = app.state.claims.revision
        result['open_tasks'] = len(app.state.tasks.open_tasks(limit=None))
        result['finished_at'] = datetime.now().astimezone().isoformat()
        save()
    finally:
        close(app, client)
print(str(OUTPUT))
