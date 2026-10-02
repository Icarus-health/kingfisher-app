"""One continuous synthetic memory week, local model only; no product mutations.

This probes evidence selection, not autonomous task/calendar execution or truth.
Days are ordered fixture stages, not elapsed wall-clock days. The existing
classification callback runs synchronously, so this is not a queue load test.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time


def grade(case, message, identifiers):
    context = message.get('metadata', {}).get('context', {})
    selected = {ref['episode_id'] for ref in context.get('working_answer', {}).get('refs', [])}
    content = message.get('content', '').casefold()
    return {
        'required_sources': {identifiers[k] for k in case['required']} <= selected,
        'allowed_sources': selected <= {identifiers[k] for k in case['allowed']},
        'status': context.get('answer_contract', {}).get('status') in case['status'],
        'required_text': all(t.casefold() in content for t in case.get('contains', [])),
        'forbidden_text': all(t.casefold() not in content for t in case.get('excludes', [])),
    }


def withdrawn_hidden(conversation, source_id, spans):
    """Check every displayed message and live source reference, not a full quote."""
    for message in conversation.get('messages', []):
        if any(span.casefold() in message.get('content', '').casefold() for span in spans):
            return False
        context = message.get('metadata', {}).get('context', {})
        if any(link.get('episode_id') == source_id for link in context.get('source_links', [])):
            return False
        refs = context.get('working_answer', {}).get('refs', [])
        unavailable = context.get('answer_contract', {}).get('status') == 'working_unavailable'
        if not unavailable and any(ref.get('episode_id') == source_id for ref in refs):
            return False
    return True


def run(model, fixture, output):
    keys = ['ICARUS_DATA_DIR', 'ICARUS_SIDECAR_TOKEN', 'ICARUS_MEMORY_SEMANTIC']
    previous = {key: os.environ.get(key) for key in keys}
    try:
        return _run(model, fixture, output)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run(model, fixture, output):
    # Deliberately no configurable cloud URL, credentials or model download.
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.proposals import ProposalStore
    from icarus_memory.policy import Policy
    from icarus_memory.providers import OpenAICompatible
    from icarus_memory.server import create_app, _wire_scheduler, Summarizer
    from icarus_memory.tools import build_registry

    from icarus_memory.local_model_guard import verify_local_model
    provider = OpenAICompatible(model, base_url='http://127.0.0.1:11434/v1')
    # Reuse the guard's no-proxy/no-redirect transport while retaining the raw
    # provider type expected by the app's own scheduled-provider wrapper.
    provider._verified_local_transport = True

    def weights():
        return verify_local_model(provider).digest

    raw = fixture.read_bytes()
    suite = json.loads(raw)
    if suite.get('synthetic_only') is not True:
        raise ValueError('Only an explicitly synthetic fixture is supported')
    # Never overwrite an earlier acceptance result.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write('{}\n')
    result = {'suite': suite['suite'], 'commit': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
              'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'model': model, 'weights': weights(),
              'synthetic_only': True, 'semantic': False, 'days': [], 'model_calls': [], 'finished': False}

    def save():
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')

    for method in ['complete', 'complete_json']:
        original = getattr(provider, method)
        def logged(*args, _method=method, _original=original, **kwargs):
            start = time.perf_counter()
            entry = {'method': _method, 'input': args[0]}
            result['model_calls'].append(entry)
            try:
                if weights() != result['weights']:
                    raise RuntimeError('Local model identity changed')
                reply = _original(*args, **kwargs)
                entry['output'] = reply.text
                return reply
            except Exception as exc:
                entry['error'] = type(exc).__name__+': '+str(exc)
                raise
            finally:
                entry['seconds'] = round(time.perf_counter()-start, 3)
                save()
        setattr(provider, method, logged)
    with tempfile.TemporaryDirectory(prefix='kingfisher-workweek-') as folder:
        root = Path(folder)
        os.environ['ICARUS_DATA_DIR'] = str(root/'runtime')
        os.environ['ICARUS_SIDECAR_TOKEN'] = 'synthetic-workweek'
        os.environ['ICARUS_MEMORY_SEMANTIC'] = ''
        episodes, claims = EpisodeStore(root/'episodes.sqlite3'), ClaimStore(root/'claims.sqlite3')
        proposals, audit = ProposalStore(root/'proposals.sqlite3'), AuditLog(root/'audit.sqlite3')
        agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='synthetic'), policy=Policy(), audit=audit,
                      tools={}, provider=provider, knowledge=claims, episodes=episodes, max_rounds=4)
        app = create_app(agent._store, agent=agent, audit=audit, proposals=proposals, episodes=episodes, knowledge=claims)
        agent._tools = build_registry(app.state.store, task_store=app.state.tasks, workspace=app.state.workspace, episodes=episodes)
        app.state.summarizer = Summarizer(episodes, provider=provider)
        _wire_scheduler(app)
        client = TestClient(app, headers={'X-Icarus-Token': 'synthetic-workweek'})
        identifiers, originals, history = {}, {}, []

        def request(method, path, data=None):
            response = client.request(method, path, **({'json': data} if data is not None else {}))
            response.raise_for_status()
            return response.json()

        try:
            for day in suite['days']:
                record = {'day': day['day'], 'ingestion': [], 'checks': {}, 'questions': []}
                result['days'].append(record)
                for source in day.get('sources', []):
                    key, body = source['key'], source['text']
                    response = request('POST', '/api/v1/sources/documents', {'filename': key+'.txt', 'body': body})
                    eid = response['id']; identifiers[key] = eid; originals[key] = body
                    job = app.state.scheduler._run_working_memory(True, source_ids=[eid])
                    record['ingestion'].append({'key': key, 'id': eid, 'detail': job.detail,
                        'state': request('GET', f'/api/v1/episodes/{eid}').get('memory_status')})
                if 'duplicate' in day:
                    key = day['duplicate']
                    duplicate = request('POST', '/api/v1/sources/documents', {'filename': key+'.txt', 'body': originals[key]})
                    record['checks']['duplicate_preserved_id'] = duplicate['id'] == identifiers[key] and not duplicate['created']
                if 'withdraw' in day:
                    key = day['withdraw']; request('POST', f'/api/v1/episodes/{identifiers[key]}/ignore')
                    affected = [(cid, keys) for cid, keys in history if key in keys]
                    record['checks']['withdrawal_has_prior_answer'] = bool(affected)
                    record['withdrawal_projections'] = [request('GET', f'/api/v1/conversations/{cid}') for cid, _ in affected]
                    record['checks']['withdrawn_history_hidden'] = all(withdrawn_hidden(c, identifiers[key], day['withdraw_spans']) for c in record['withdrawal_projections'])
                record['checks']['originals_preserved'] = all(episodes.get(identifiers[k]).body == body for k, body in originals.items())
                for case in day.get('questions', []):
                    q = {'id': case['id'], 'question': case['question']}; record['questions'].append(q)
                    start = time.perf_counter()
                    cid = request('POST','/api/v1/conversations',{})['conversation']['id']
                    response = request('POST',f'/api/v1/conversations/{cid}/messages',{'message':case['question'],'answer_mode':'auto'})['messages'][-1]
                    q.update(response=response, checks=grade(case,response,identifiers), seconds=round(time.perf_counter()-start,3))
                    q['passed'] = all(q['checks'].values())
                    selected = {r['episode_id'] for r in response.get('metadata',{}).get('context',{}).get('working_answer',{}).get('refs',[])}
                    history.append((cid,{k for k,v in identifiers.items() if v in selected}))
                    save(); print(day['day'],case['id'],q['passed'],q['checks'],flush=True)
                save()
            result['weights_unchanged'] = weights() == result['weights']
            result['finished'] = True
        except Exception as exc:
            result['error'] = type(exc).__name__+': '+str(exc)
            raise
        finally:
            save(); client.close(); app.state.scheduler.stop()
            for name in ['audit','tasks','workspace','episodes','proposals','conversations','claims','regeln']:
                close = getattr(getattr(app.state,name,None),'close',None)
                if callable(close): close()
    questions = [q for d in result['days'] for q in d['questions']]
    result['summary'] = {'passed': sum(q['passed'] for q in questions), 'total':len(questions),
        'integrity_passed':all(all(d['checks'].values()) for d in result['days']),
        'model_calls':len(result['model_calls']), 'model_seconds':round(sum(c['seconds'] for c in result['model_calls']),3)}
    save(); print(json.dumps(result['summary']),flush=True)
    return 0 if result['summary']['passed'] == len(questions) and result['summary']['integrity_passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='qwen3.5:4b')
    parser.add_argument('--fixture',type=Path,default=Path('docs/evaluations/memory-quality/workweek/scenario.json'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.model,args.fixture,args.output))
