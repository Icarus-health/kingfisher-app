#!/usr/bin/env python3
"""Frische synthetische Mailkette, nur vorhandenes lokales Qwen, mit eigenem Lastwächter.

Native 8K-Diagnose statt unveränderter 32K-App-Transport. Bewertet feste Verträge,
keine universelle Wahrheit; der Großimport wird niemals freigegeben.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'sidecar'))
import httpx
from icarus_memory.local_model_guard import verify_local_model
from icarus_memory.providers import OpenAICompatible, ProviderError, Reply
from mail_intake_quality import CATALOG, load_catalog, run_pipeline

MODEL='kingfisher-qwen3.5:9b-32k'
BASE='http://127.0.0.1:11434'


class ProbeLimit(ProviderError):
    fatal=True


class NativeProbe:
    is_local=True
    name='synthetic-local-native-diagnostic'
    def __init__(self,model,report,save,limit=140):
        self.model=model;self.report=report;self.save=save;self.limit=limit
        self.base=OpenAICompatible(model,base_url=BASE+'/v1')
        self.identity=None

    def _call(self,messages,*,max_tokens,schema=None):
        if len(self.report['model_calls'])>=self.limit:raise ProbeLimit('Aufrufgrenze erreicht.')
        if len(json.dumps(messages,ensure_ascii=False).encode())>16000:
            raise ProviderError('Eingabe über der sicheren 8K-Diagnosegrenze; nicht gekürzt.')
        identity=verify_local_model(self.base)
        if self.identity is not None and self.identity!=identity:raise ProbeLimit('Modellgewichte geändert.')
        self.identity=identity
        row={'stage':self.report.get('stage'),'messages':messages,'status':'started'}
        self.report['model_calls'].append(row);self.save();start=time.monotonic()
        try:
            payload={'model':self.model,'messages':messages,'stream':False,'think':False,'keep_alive':'15s',
                     'options':{'num_ctx':8192,'num_predict':min(max_tokens,1200),'temperature':0,'seed':42}}
            if schema is not None:payload['format']=schema
            with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as client:
                response=client.post(BASE+'/api/chat',json=payload);response.raise_for_status();data=response.json()
            row['response']=data
            message=data.get('message') or {}
            if (data.get('done') is not True or data.get('done_reason') not in (None,'stop')
                    or message.get('tool_calls') or not isinstance(message.get('content'),str) or not message['content'].strip()):
                raise ProviderError('Leere, abgeschnittene oder werkzeughaltige Antwort.')
            if (type(data.get('prompt_eval_count')) is not int or data['prompt_eval_count']<=0
                    or type(data.get('eval_count')) is not int or data['eval_count']<0
                    or data['prompt_eval_count']>=6992):
                raise ProviderError('Kontextreserve nicht nachgewiesen; Ergebnis nicht vollständig gewertet.')
            if verify_local_model(self.base)!=identity:raise ProbeLimit('Modellgewichte geändert.')
            row['status']='completed';return Reply(text=message['content'],model=self.model)
        except Exception as exc:
            row['status']='failed';row['error']=type(exc).__name__+': '+str(exc);raise
        finally:
            row['seconds']=round(time.monotonic()-start,3);self.save()

    def complete_json(self,messages,*,max_tokens=256,schema=None):
        return self._call(messages,max_tokens=max_tokens,schema=schema or 'json')

    def complete(self,messages,tools):
        if tools:raise ProviderError('Werkzeugausführung gehört nicht zu dieser Quellenprobe.')
        return self._call(messages,max_tokens=1024)


def save_json(path,value):
    temporary=path.with_suffix('.new')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.chmod(0o600)
    temporary.replace(path)


def resources():
    try:
        free=subprocess.run(['memory_pressure','-Q'],text=True,capture_output=True,timeout=4,check=True)
        level=subprocess.run(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True,capture_output=True,timeout=4,check=True)
        match=re.search(r'free percentage:\s*(\d+)%',free.stdout)
        return {'pressure':int(level.stdout.strip()),'free_percent':int(match.group(1))} if match else None
    except (OSError,subprocess.SubprocessError,ValueError):return None


def stop_reason(elapsed,memory,limit):
    if elapsed>limit:return 'time_budget'
    if not isinstance(memory,dict):return 'memory_status_unavailable'
    if memory['pressure']>=4:return 'memory_pressure'
    if memory['free_percent']<25:return 'memory_reserve'
    return None


def summarize(report,catalog=None):
    checks=[]
    for row in report.get('task_checks',[]):
        checks.extend((f"task:{row['id']}:{name}",value) for name,value in row['checks'].items())
    for row in report.get('questions',[]):
        checks.extend((f"question:{row['id']}:{name}",value) for name,value in row.get('checks',{'technical':False}).items())
    checks.extend(('people:'+name,value) for name,value in report.get('people_checks',{}).items())
    classifications=report.get('classification',[])
    catalog=catalog or load_catalog()
    expected_sources={s['id'] for s in catalog['mails']}
    expected_questions={q['id'] for q in catalog['questions']}
    exact=lambda rows,ids: len(rows)==len(ids) and {r['id'] for r in rows}==ids
    scan=report.get('task_scan',[])
    technical=(report.get('finished') is True and report.get('originals_preserved') is True
        and report.get('tasks_created_without_confirmation')==0
        and (report.get('mode')!='live_qwen_bge' or
             report.get('semantic_search') is True and report.get('semantic_coverage',{}).get('status')=='indexed')
        and exact(classifications,expected_sources)
        and all(r['state'] in {'complete','empty'} and r['original_body_preserved'] and r['date_absence_preserved'] for r in classifications)
        and exact(report.get('questions',[]),expected_questions)
        and exact(report.get('task_checks',[]),expected_sources)
        and set(report.get('people_checks',{}))=={'required_identities_present','identities_not_merged','service_not_person'}
        and not any(r.get('error') for r in report.get('questions',[]))
        and bool(scan) and all(r['available'] and not r['failed'] and not r['cancelled'] for r in scan))
    return {'pipeline_complete':technical,'contract_checks_passed':sum(bool(v) for _,v in checks),
        'contract_checks_total':len(checks),'failed_contracts':[k for k,v in checks if not v],
        'model_calls':len(report.get('model_calls',[])),
        'model_seconds':round(sum(c.get('seconds',0) for c in report.get('model_calls',[])),3),
        'bulk_import_authorized':False,'semantic_grade':'requires_review'}


def worker(directory):
    output=Path(directory)/'report.json';catalog=load_catalog(Path(directory)/'catalog.json')
    report=json.loads(output.read_text());save=lambda:save_json(output,report)
    with (Path(directory)/'worker.log').open('w') as log,redirect_stdout(log),redirect_stderr(log):
        try:
            provider=NativeProbe(MODEL,report,save,limit=catalog['limits']['model_calls'])
            report['weights']=asdict(verify_local_model(provider.base));save()
            from icarus_memory.local_embeddings import LocalEmbedder
            report['embedding_calls']=[]
            def embedding_factory():
                adapter=LocalEmbedder(model='bge-m3:latest',verify_weights=True,keep_alive='15s')
                original=adapter.embed
                def embed(texts):
                    row={'stage':report.get('stage'),'count':len(texts),'status':'started'}
                    report['embedding_calls'].append(row);save();start=time.monotonic()
                    try:
                        vectors=original(texts);row.update(status='completed',dimensions=len(vectors[0]));return vectors
                    except Exception as exc:
                        row.update(status='failed',error=type(exc).__name__);raise
                    finally:row['seconds']=round(time.monotonic()-start,3);save()
                adapter.embed=embed
                return adapter
            run_pipeline(catalog,provider,Path(directory)/'runtime',report,save,embedding_factory=embedding_factory)
        except Exception as exc:
            report['finished']=False;report['error']=type(exc).__name__+': '+str(exc)
        finally:
            report['summary']=summarize(report,catalog);save()


def monitor_worker(process,limit,*,measure=resources):
    """Überwacht ausschließlich das übergebene, selbst gestartete Kind."""
    samples=[];start=time.monotonic();reason=None
    try:
        while process.is_alive():
            memory=measure();elapsed=time.monotonic()-start
            samples.append({'elapsed':round(elapsed,1),**(memory or {})})
            reason=stop_reason(elapsed,memory,limit)
            if reason:break
            process.join(1)
    except KeyboardInterrupt:
        reason='user_interrupted'
    finally:
        if process.is_alive():
            process.terminate();process.join(5)
            if process.is_alive():process.kill();process.join(5)
    return samples,reason


def run(output):
    catalog=load_catalog();output.mkdir(mode=0o700,parents=True,exist_ok=False)
    report={'suite':catalog['suite'],'synthetic_only':True,'finished':False,'model':MODEL,
        'created_at':datetime.now(timezone.utc).isoformat(),'catalog_sha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        'harness_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('mail_intake_quality.py'))},
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'transport':'native_ollama_diagnostic_8k','mode':'live_qwen_bge','semantic_search':False,'additional_judging_model':False,
        'bulk_import_authorized':False,'model_calls':[],'resources':[]}
    path=output/'report.json';save_json(path,report)
    save_json(output/'catalog.json',catalog)
    memory=resources();report['resources'].append(memory);reason=stop_reason(0,memory,catalog['limits']['seconds'])
    if reason:
        report['stop_reason']=reason;report['summary']=summarize(report,catalog);save_json(path,report);return 2
    try:
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
            response=client.get(BASE+'/api/ps');response.raise_for_status();loaded=response.json().get('models',[])
    except (httpx.HTTPError,ValueError,AttributeError) as error:
        report.update(stop_reason='ollama_unavailable',error=type(error).__name__)
        report['summary']=summarize(report,catalog);save_json(path,report);return 2
    if any(r.get('name')!=MODEL and not r.get('name','').startswith('bge-m3') for r in loaded):
        report['stop_reason']='other_model_loaded';save_json(path,report);return 2
    save_json(path,report)
    process=multiprocessing.get_context('spawn').Process(target=worker,args=(str(output),))
    process.start();samples,reason=monitor_worker(process,catalog['limits']['seconds'])
    report=json.loads(path.read_text());report['resource_samples']=samples;report['worker_exitcode']=process.exitcode
    if reason:report.update(finished=False,stop_reason=reason)
    report['summary']=summarize(report,catalog);save_json(path,report)
    print(json.dumps(report['summary'],ensure_ascii=False))
    return 0 if report['summary']['pipeline_complete'] and not report['summary']['failed_contracts'] else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Katalog prüfen, ohne Modell, Netzwerk oder Ergebnisordner.')
    parser.add_argument('--output',type=Path,help='Neuer leerer Ergebnisordner (wird exklusiv angelegt).')
    args=parser.parse_args()
    if args.check:
        catalog=load_catalog();print(f"{len(catalog['mails'])} künstliche Mails, {len(catalog['questions'])} Fragen");return 0
    if args.output is None:parser.error('--output ist für die Messung erforderlich.')
    return run(args.output)


if __name__=='__main__':raise SystemExit(main())
