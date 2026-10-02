#!/usr/bin/env python3
"""Paired, synthetic local M3 experiment; no private configuration or action tools.

Run on the prompt-only candidate commit immediately after the preparation commit.
Only HEAD and its first parent may supply prompts. The prepared comparison driver
must be identical in both. Results stay review_required; no semantic auto-grading.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from unittest.mock import patch

import httpx
from icarus_memory import agent as agent_module, providers
from memory_answer_comparison import compare_requests, differing_paths
from memory_probe_fixtures import build_fixture, case_hash
import probe_memory_pipeline as pipeline

AGENT_PATH='sidecar/icarus_memory/agent.py'
MAX_WALL_SECONDS=1800


def git(*args):
    return subprocess.run(['git',*args],cwd=pipeline.REPO,capture_output=True,check=True,timeout=10).stdout


def prompt_from_source(source):
    tree=ast.parse(source)
    assignments=[node for node in tree.body if isinstance(node,ast.Assign) and
                 any(isinstance(t,ast.Name) and t.id=='SYSTEM_PROMPT' for t in node.targets)]
    if len(assignments)!=1 or not isinstance(assignments[0].value,ast.Constant) or not isinstance(assignments[0].value.value,str):
        raise ValueError('Expected exactly one literal SYSTEM_PROMPT')
    prompt=assignments[0].value.value
    assignments[0].value=ast.Constant(value='<SYSTEM_PROMPT>')
    return prompt,ast.dump(tree,include_attributes=False)


def committed_versions():
    # Untracked user drafts are not runtime input. Any tracked worktree/index change blocks inference.
    git('diff','--quiet');git('diff','--cached','--quiet')
    current=git('rev-parse','HEAD').decode().strip()
    previous=git('rev-parse','HEAD^').decode().strip()
    if git('diff','--name-only',previous,current).decode().splitlines()!=[AGENT_PATH]:
        raise ValueError('Candidate must change only the agent prompt file from its parent')
    before,old_tree=prompt_from_source(git('show',previous+':'+AGENT_PATH))
    after,new_tree=prompt_from_source(git('show',current+':'+AGENT_PATH))
    if old_tree!=new_tree or before==after or after!=agent_module.SYSTEM_PROMPT:
        raise ValueError('Candidate must change only SYSTEM_PROMPT literal')
    return {'baseline':{'commit':previous,'prompt':before},'candidate':{'commit':current,'prompt':after}}


class UnsafeDiagnosticRequest(ValueError):
    """A diagnostic boundary violation must stop every further attempt."""


class WireTransport(httpx.BaseTransport):
    """Capture exact JSON payload after the production adapter; allow loopback only."""
    def __init__(self,delegate):
        self.delegate=delegate
        self.requests=[]

    def handle_request(self,request):
        if (request.url.scheme,request.url.host,request.url.port)!=('http','127.0.0.1',11434):
            raise UnsafeDiagnosticRequest('Non-loopback diagnostic request rejected')
        if (request.method,request.url.path) not in {
            ('GET','/api/tags'),('GET','/api/version'),('POST','/api/show'),('POST','/v1/chat/completions')}:
            raise UnsafeDiagnosticRequest('Unexpected diagnostic route')
        if request.url.path=='/v1/chat/completions':
            if len(self.requests)>=1:
                raise UnsafeDiagnosticRequest('One generation request per attempt')
            self.requests.append(json.loads(request.content))
        return self.delegate.handle_request(request)

    def close(self):
        # Several production clients share the one serial transport. Owner closes it.
        pass


def run_comparison(output_path,versions,selection,model,*,transport=None,wall_seconds=MAX_WALL_SECONDS):
    if not 0<=wall_seconds<=MAX_WALL_SECONDS or not 1<=len(selection)<=32:
        raise ValueError('Comparison budget out of bounds')
    for row in selection:
        pipeline.validate_case(row['case'])
        if row['mode'] not in {'agent','reference_identity_context'}:
            raise ValueError('Unsupported comparison mode')
    keys=[(r['catalog']['sha256'],r['case']['id'],r['mode']) for r in selection]
    if len(keys)!=len(set(keys)):
        raise ValueError('Duplicate pair')
    cells=[]
    for index,row in enumerate(selection):
        for variant in (('baseline','candidate') if index%2==0 else ('candidate','baseline')):
            cells.append({'id':f'{index}:{variant}','pair':index,'variant':variant})
    report={'suite':'memory-answer-contract-v1','status':'incomplete','semantic_qualification':False,
            'started_at':pipeline.timestamp(),'variants':versions,'model':model,
            'manifest':[{'catalog':r['catalog'],'case_id':r['case']['id'],'case_sha256':case_hash(r['case']),
                         'scenario_id':r['case']['scenario_id'],'mode':r['mode']} for r in selection],
            'cells':cells,'attempt_limit':len(cells),'wall_seconds':wall_seconds,
            'transport_failure_limit':2,'attempts':[],'pairs':[],
            'metadata_stable':None,'metadata_after':None,
            'transport':{'endpoint':pipeline.BASE+'/v1','trust_env':False,'follow_redirects':False,
                         'read_timeout_seconds':60,'content_retries':0},
            'rubric':'Review original question, permitted sources and required/forbidden case semantics. '
                     'Record unsupported facts/action success/negative conclusions, attribution, identity, time, '
                     'source omissions, helpful clarification and unnecessary refusal separately. Codex review is not human acceptance.',
            'limitations':'Development subset, prepared claims, fixed diagnostic clock, unseeded generation; '
                          'no extraction, holdout, human acceptance, causality or latency qualification.'}
    for value in report['variants'].values():
        value['prompt_sha256']=hashlib.sha256(value['prompt'].encode()).hexdigest()
    # Reserve exclusive output before metadata or inference; never replace/resume existing attempts.
    with Path(output_path).open('x',encoding='utf-8') as output:
        os.fchmod(output.fileno(),0o600)
        def save():
            launched={a['id'] for a in report['attempts']}
            report['unrun_cells']=[c['id'] for c in cells if c['id'] not in launched]
            output.seek(0);json.dump(report,output,ensure_ascii=False,indent=2)
            output.truncate();output.flush();os.fsync(output.fileno())
        save()
        started=time.monotonic(); failures=0
        delegate=transport or httpx.HTTPTransport(retries=0,trust_env=False)
        wire=WireTransport(delegate)
        try:
            with pipeline.bounded_transport(wire) as client, tempfile.TemporaryDirectory(prefix='kingfisher-m3-synthetic-') as temp:
                report['metadata_before']=pipeline.metadata(client,model);save()
                provider=providers.OpenAICompatible(model=model,api_key='synthetic-local-probe',base_url=pipeline.BASE+'/v1')
                for index,row in enumerate(selection):
                    if time.monotonic()-started>=wall_seconds:
                        report['stop_reason']='wall_clock_budget';break
                    root=Path(temp)/str(index);seed=root/'seed'
                    fixture=build_fixture(row['case'],seed,provider);fixture.close()
                    attempts={}
                    for cell in [c for c in cells if c['pair']==index]:
                        if time.monotonic()-started>=wall_seconds:
                            report['stop_reason']='wall_clock_budget';break
                        variant=cell['variant'];arm=root/variant
                        shutil.copytree(seed,arm)
                        attempt={**cell,'catalog':row['catalog'],'case_id':row['case']['id'],
                                 'mode':row['mode'],'status':'started','result':{},'wire_requests':[]}
                        report['attempts'].append(attempt);attempts[variant]=attempt;save()
                        wire.requests=[]
                        try:
                            with patch.object(agent_module,'SYSTEM_PROMPT',versions[variant]['prompt']):
                                pipeline.run_attempt(row['case'],arm,provider,row['mode'],attempt['result'])
                            attempt['status']=attempt['result']['status']
                            failures = failures + 1 if any(
                                call['status']=='error' for call in attempt['result'].get('provider_calls',[])
                            ) else 0
                        except UnsafeDiagnosticRequest as exc:
                            attempt.update(status='technical_failure',error_type=type(exc).__name__)
                            report['stop_reason']='unsafe_request'
                        except Exception as exc:
                            attempt.update(status='technical_failure',error_type=type(exc).__name__)
                            failures+=1
                        finally:
                            attempt['wire_requests']=copy.deepcopy(wire.requests);save()
                        if report.get('stop_reason'):break
                        if failures>=2:
                            report['stop_reason']='repeated_transport_failure';break
                    if len(attempts)==2:
                        a,b=attempts['baseline'],attempts['candidate']
                        comparison='incomplete';differences=[]
                        if a['wire_requests'] and b['wire_requests']:
                            differences=compare_requests(a['wire_requests'],b['wire_requests'],versions['baseline']['prompt'],versions['candidate']['prompt'])
                            comparison='prompt_only'
                        elif all(x['status']=='completed' for x in (a,b)):
                            if not a['wire_requests'] and not b['wire_requests']:
                                differences=differing_paths(
                                    {k:a['result'].get(k) for k in ('answer','answer_mode','context','calendar_source_ids')},
                                    {k:b['result'].get(k) for k in ('answer','answer_mode','context','calendar_source_ids')})
                                if a['result'].get('answer_mode')!='calendar_data':differences.append('unexpected_zero_provider_path')
                                comparison='unchanged_deterministic_path'
                            else: differences=['provider_request_count']
                        report['pairs'].append({'pair':index,'comparison':'confounded' if differences else comparison,'differences':differences,
                                                'answers_completed':all(x['status']=='completed' for x in (a,b))})
                        if differences:report['stop_reason']='payload_mismatch'
                    else:
                        report['pairs'].append({'pair':index,'comparison':'incomplete','differences':[]})
                    save()
                    if report.get('stop_reason'):break
                    fresh=pipeline.metadata(client,model)
                    if fresh!=report['metadata_before']:
                        report['stop_reason']='metadata_changed';break
                report['metadata_after']=pipeline.metadata(client,model)
                report['metadata_stable']=report['metadata_before']==report['metadata_after']
                if (not report.get('stop_reason') and report['metadata_stable'] and
                    len(report['attempts'])==len(cells) and all(a['status']=='completed' for a in report['attempts'])):
                    report['status']='completed'
        except (Exception,KeyboardInterrupt) as exc:
            report['error_type']=type(exc).__name__
            if isinstance(exc,UnsafeDiagnosticRequest):report['stop_reason']='unsafe_request'
        finally:
            delegate.close();report['ended_at']=pipeline.timestamp();save()
    return 0 if report['status']=='completed' else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--model',default='qwen2.5:14b')
    args=parser.parse_args(argv)
    versions=committed_versions()
    selection=[]
    # Frozen balanced development subset: six original families and all ten countercases.
    for selector in ('countercases-v1','development-v1'):
        cases,meta=pipeline.load_catalog(selector)
        for case in cases.values():
            if selector=='development-v1' and not case['id'].endswith('-01'):continue
            for mode in ('agent','reference_identity_context'):
                selection.append({'catalog':meta,'case':case,'mode':mode})
    return run_comparison(args.output,versions,selection,args.model)


if __name__=='__main__':
    raise SystemExit(main())
