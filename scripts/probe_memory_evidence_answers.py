#!/usr/bin/env python3
"""Bounded single-arm synthetic probe of Agent.answer_memory, never app config.

Six original development cases and all ten countercases, fixed before inference.
This is not a paired comparison or a semantic/production qualification.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
import time

import httpx
from icarus_memory.providers import OpenAICompatible
from memory_probe_fixtures import build_fixture, business_clock, case_hash
from memory_probe_support import RecordingProvider
from probe_memory_answer_contract import WireTransport, git
import probe_memory_pipeline as pipeline


def run(output_path, model, *, transport=None):
    git('diff', '--quiet'); git('diff', '--cached', '--quiet')
    selection=[]
    for selector in ('countercases-v1', 'development-v1'):
        cases,catalog=pipeline.load_catalog(selector)
        selection.extend((case,catalog) for case in cases.values()
                         if selector=='countercases-v1' or case['id'].endswith('-01'))
    if len(selection)!=16:
        raise ValueError('Expected the frozen 16-case development subset')
    report={'suite':'memory-evidence-answer-v1','status':'incomplete',
            'commit':git('rev-parse','HEAD').decode().strip(),'model':model,
            'semantic_qualification':False,'started_at':pipeline.timestamp(),
            'attempt_limit':16,'wall_seconds':1200,'content_retries':0,
            'manifest':[{'case_id':c['id'],'case_sha256':case_hash(c),'catalog':meta}
                        for c,meta in selection], 'attempts':[],
            'limitations':'Single arm, development subset, prepared claims, fixed business clock; '
                          'no extraction, holdout, paired causal comparison or user acceptance. '
                          'Calendar callback and conversation history are outside this explicit path.'}
    with Path(output_path).open('x',encoding='utf-8') as output:
        os.fchmod(output.fileno(),0o600)
        def save():
            report['unrun_cases']=[c['id'] for c,_ in selection
                                  if c['id'] not in {a['case_id'] for a in report['attempts']}]
            output.seek(0);json.dump(report,output,ensure_ascii=False,indent=2)
            output.truncate();output.flush();os.fsync(output.fileno())
        save()
        delegate=transport or httpx.HTTPTransport(retries=0,trust_env=False)
        wire=WireTransport(delegate)
        started=time.monotonic();failures=0
        try:
            with pipeline.bounded_transport(wire) as client, tempfile.TemporaryDirectory(prefix='kingfisher-evidence-synthetic-') as temp:
                report['metadata_before']=pipeline.metadata(client,model);save()
                provider=OpenAICompatible(model=model,api_key='synthetic-local-only',base_url=pipeline.BASE+'/v1')
                for index,(case,_) in enumerate(selection):
                    if time.monotonic()-started>=1200:
                        report['stop_reason']='wall_clock_budget';break
                    attempt={'case_id':case['id'],'question':case['question'],
                             'required':case['required'],'forbidden':case['forbidden'],
                             'status':'started'}
                    report['attempts'].append(attempt);save()
                    wire.requests=[]
                    recording=RecordingProvider(provider)
                    fixture=None
                    try:
                        fixture=build_fixture(case,Path(temp)/str(index),recording)
                        attempt.update(source_ids=fixture.source_ids,claim_ids=fixture.claim_ids,
                                       canonical_manifest=json.loads(fixture.expected_manifest))
                        with business_clock(case):
                            turn=fixture.agent.answer_memory(case['question'])
                        attempt.update(status='completed',turn=turn.to_dict())
                        failures=failures+1 if any(c['status']=='error' for c in recording.calls) else 0
                    except Exception as exc:
                        attempt.update(status='technical_failure',error_type=type(exc).__name__)
                        report['stop_reason']='technical_failure'
                    finally:
                        attempt.update(provider_calls=copy.deepcopy(recording.calls),wire_requests=copy.deepcopy(wire.requests))
                        if fixture is not None:fixture.close()
                        save()
                    print(case['id'],attempt['status'],attempt.get('turn',{}).get('context',{}).get('answer_contract',{}).get('status'),flush=True)
                    if failures>=2:report['stop_reason']='repeated_transport_failure'
                    if report.get('stop_reason'):break
                report['metadata_after']=pipeline.metadata(client,model)
                report['metadata_stable']=report['metadata_after']==report['metadata_before']
                if not report['metadata_stable']:report['stop_reason']='metadata_changed'
                if not report.get('stop_reason') and len(report['attempts'])==16:
                    report['status']='completed'
        except (Exception,KeyboardInterrupt) as exc:
            report.update(error_type=type(exc).__name__,stop_reason='probe_error')
        finally:
            delegate.close();report['ended_at']=pipeline.timestamp();save()
    return 0 if report['status']=='completed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--model',default='qwen3.5:4b')
    args=parser.parse_args()
    raise SystemExit(run(args.output,args.model))
