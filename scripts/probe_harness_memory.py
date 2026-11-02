"""Actual SDK → local Qwen → scoped Kingfisher store; artificial sources only.

Requires the separately pinned SDK runtime and Node 24. No installation, private
database input, cloud key, personal application registration or role change.
"""
from copy import copy
import argparse
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time

from fastapi import FastAPI
import uvicorn

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.procedures import ProcedureStore
from icarus_memory.harness_broker import Broker
from icarus_memory.harness_protocol import register
from icarus_memory.harness_worker import run_synthetic_worker
from icarus_memory.providers import OpenAICompatible
from icarus_memory.local_context_profile import verify_lifecycle
from probe_intake_precision import _mac_resource_check


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',required=True)
    parser.add_argument('--runtime',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args(argv)
    report = dict(status='started',synthetic_only=True,personal_store_opened=False,
                  os_isolation_verified=False,calls=[],tool_calls=[])
    target = Path(args.output)
    with target.open('x') as stream: json.dump(report,stream)
    def save():
        with tempfile.NamedTemporaryFile(mode='w',dir=target.parent,delete=False) as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2)
            staging = stream.name
        os.replace(staging,target)
    started = time.monotonic()
    server = thread = grant = broker = None
    try:
        model = 'kingfisher-qwen3.5:9b-8k'
        os.environ['ICARUS_OLLAMA_8K_PROFILE'] = model
        _mac_resource_check(model)
        provider = OpenAICompatible(model,'artificial-local','http://127.0.0.1:11434/v1')
        identity = verify_lifecycle(provider)
        report['model_digest'] = identity.digest
        with tempfile.TemporaryDirectory(prefix='kf-scoped-synthetic-') as scratch:
            episodes = EpisodeStore(Path(scratch)/'episodes.sqlite3')
            procedures = ProcedureStore(Path(scratch)/'procedures.sqlite3')
            try:
                def put(body):
                    return episodes.record(EpisodeKind.DOCUMENT,'Künstliche Gedächtnisprobe',body,
                        Provenance(source_type=SourceType.DOCUMENT))[0]
                source = put('Die künstliche Zugangskarte liegt in Fach A42.')
                outside = put('Die Zugangskarte liegt im Safe Z99. Nicht für diesen Auftrag freigegeben.')
                originals = {e.id:e.digest for e in (source,outside)}
                candidate = procedures.propose(dict(name='kartenfundort',title='Fundort im Original prüfen',
                    area='analysis',description='Fundort einer Zugangskarte anhand des Originals prüfen.',
                    triggers=['zugangskarte'],steps=['Original mit einem wörtlichen Begriff suchen.',
                        'Fundort mit aktueller Quelle nennen; unbekannte Angaben offen lassen.'],
                    positive='Wo ist die Zugangskarte?',negative='Was ist morgen zu tun?'))
                procedures.accept(candidate['id'])
                broker = Broker(episodes,procedures)
                grant = broker.issue('Wo liegt die Zugangskarte? Bitte mit Quelle.',area='analysis',sources=[source.id])
                original_invoke = broker.invoke
                def invoke(token,name,arguments):
                    result = original_invoke(token,name,arguments)
                    report['tool_calls'].append(dict(name=name,arguments=arguments))
                    save()
                    return result
                broker.invoke = invoke
                def infer(messages,tools,permitted):
                    _mac_resource_check(model)
                    local = copy(provider)
                    local._verified_local_permitted = permitted
                    local._request_payload = lambda p:{**p,'max_tokens':256,'temperature':0}
                    if verify_lifecycle(local) != identity: raise RuntimeError('LocalModelChanged')
                    row = dict(status='started',skills_automatic='Fundort im Original prüfen' in messages[0]['content'],
                               tools=[t['name'] for t in tools])
                    report['calls'].append(row)
                    save()
                    try:
                        reply = local.complete(messages,tools)
                        if verify_lifecycle(local) != identity: raise RuntimeError('LocalModelChanged')
                        row['status']='complete'
                        return reply
                    except Exception as exc:
                        # Artificial input only; diagnostic stays in the explicitly requested local report.
                        row.update(status='failed',error=type(exc).__name__,detail=str(exc)[:500])
                        raise
                    finally: save()
                app = FastAPI()
                register(app,broker,model=model,infer=infer)
                listener = socket.socket()
                listener.bind(('127.0.0.1',0))
                server = uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
                thread = threading.Thread(target=server.run,kwargs=dict(sockets=[listener]),daemon=True)
                thread.start()
                until = time.monotonic()+5
                while not server.started and time.monotonic()<until: time.sleep(.02)
                if not server.started: raise RuntimeError('SyntheticListenerUnavailable')
                result = run_synthetic_worker(node=args.node,runtime=args.runtime,
                    origin='http://127.0.0.1:'+str(listener.getsockname()[1]),token=grant['token'],
                    request='Wo liegt die Zugangskarte? Bitte mit Quelle.',scratch=scratch)
                if not broker.current(grant['token']): raise RuntimeError('StaleResult')
                unchanged = all(episodes.get(identifier).digest == stamp for identifier,stamp in originals.items())
                text = result['text']
                # Token/source presence is a smoke oracle; inspect the actual sentence
                # before claiming semantic quality. A negated mention could pass it.
                checks = dict(location_token_present='A42' in text,source_cited=source.id in text,
                    private_scope_excluded='Z99' not in text and outside.id not in text,
                    actual_search=any(c['name']=='memory_search' for c in report['tool_calls']),
                    skills_automatic=bool(report['calls']) and all(c['skills_automatic'] for c in report['calls']),
                    originals_unchanged=unchanged)
                report.update(status='passed' if all(checks.values()) else 'failed',checks=checks,
                              answer=text,live_model_verified=True,semantic_review_required=True)
            finally:
                if grant: broker.cancel(grant['id'])
                if server: server.should_exit=True
                if thread: thread.join(5)
                procedures.close()
                episodes.close()
    except KeyboardInterrupt:
        report.update(status='interrupted',error='KeyboardInterrupt')
    except Exception as exc:
        report.update(status='failed',error=type(exc).__name__)
    report['seconds']=round(time.monotonic()-started,3)
    save()
    print(json.dumps({k:report[k] for k in ('status','seconds','checks','error') if k in report}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
