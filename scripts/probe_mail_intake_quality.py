#!/usr/bin/env python3
"""Frische synthetische Mailkette, nur vorhandenes lokales Qwen, mit eigenem Lastwächter.

Native 8K-Diagnose statt unveränderter 32K-App-Transport. Bewertet feste Verträge,
keine universelle Wahrheit; der Großimport wird niemals freigegeben.
"""
import argparse
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import copy
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
from icarus_memory.providers import OpenAICompatible, ProviderError, Reply, ToolCall
from icarus_memory.policy import ActionClass
from unittest.mock import patch
from mail_intake_quality import CATALOG, load_catalog, run_pipeline

MODEL='kingfisher-qwen3.5:9b-32k'
BASE='http://127.0.0.1:11434'
READ_TOOLS=frozenset({'gedaechtnis_suchen','episoden_suchen','episode_lesen','notizen_suchen',
    'notiz_lesen','aktuelle_zeit','aufgaben','projekte','projekt_stand'})
MAX_TOOL_CALLS=4


class ProbeLimit(ProviderError):
    fatal=True


class NativeProbe:
    is_local=True
    name='synthetic-local-native-diagnostic'
    def __init__(self,model,report,save,limit=140):
        self.model=model;self.report=report;self.save=save;self.limit=limit
        self.base=OpenAICompatible(model,base_url=BASE+'/v1')
        self.identity=None
        self.registry=None;self.prior_calls={}

    def _native_messages(self,messages):
        """Nur eigene bekannte Aufrufe in Ollamas Nachrichtenvertrag übersetzen."""
        if not isinstance(messages,list) or any(not isinstance(message,dict) for message in messages):
            raise ProviderError('Ungültige Werkzeughistorie.')
        native=copy.deepcopy(messages);pending={};seen=set()
        for message in native:
            if message.get('tool_calls'):
                if (message.get('role')!='assistant' or pending or not isinstance(message['tool_calls'],list)):
                    raise ProviderError('Ungültige Werkzeughistorie.')
                calls=[]
                for call in message['tool_calls']:
                    if not isinstance(call,dict) or not isinstance(call.get('id'),str) or not isinstance(call.get('function'),dict):
                        raise ProviderError('Ungültige historische Werkzeugdefinition.')
                    identifier=call.get('id');known=self.prior_calls.get(identifier);function=call.get('function',{})
                    try:arguments=json.loads(function.get('arguments'))
                    except (TypeError,ValueError):raise ProviderError('Ungültige historische Werkzeugargumente.')
                    if (known is None or identifier in seen or function.get('name')!=known.name
                            or arguments!=known.arguments):raise ProviderError('Unbekannte oder veränderte Werkzeughistorie.')
                    seen.add(identifier);pending[identifier]=known.name
                    calls.append({'type':'function','function':{'name':known.name,'arguments':arguments}})
                message['tool_calls']=calls
            elif message.get('role')=='tool':
                identifier=message.get('tool_call_id')
                if (not isinstance(identifier,str) or identifier not in pending or
                        identifier!=next(iter(pending)) or not isinstance(message.get('content'),str)):
                    raise ProviderError('Werkzeugergebnis ohne bekannten vorherigen Aufruf.')
                name=pending.pop(identifier)
                if 'tool_name' in message and message['tool_name']!=name:
                    raise ProviderError('Widersprüchlicher Werkzeugname in der Historie.')
                message.pop('tool_call_id');message['tool_name']=name
            elif pending:
                raise ProviderError('Werkzeugergebnis fehlt in der Historie.')
        if pending:raise ProviderError('Werkzeugergebnis fehlt in der Historie.')
        return native

    def _read_calls(self,raw,tools,row):
        """Den ganzen Antrag prüfen; erst danach erreicht etwas die Agent-Policy."""
        from icarus_memory.agent import _fehlende_pflichtfelder
        row['tool_requests']=copy.deepcopy(raw);decisions=[];calls=[];error=None
        if not isinstance(raw,list) or not 1<=len(raw)<=MAX_TOOL_CALLS:
            row['tool_decisions']=[{'decision':'rejected','reason':'tool_batch_limit_or_shape'}]
            raise ProviderError('Ungültige oder zu große Werkzeugantwort.')
        offered={tool.get('name'):tool for tool in tools or []}
        identifiers=set(self.prior_calls)
        for i,request in enumerate(raw):
            function=request.get('function') if isinstance(request,dict) else None
            name=function.get('name') if isinstance(function,dict) else None
            arguments=function.get('arguments') if isinstance(function,dict) else None
            identifier=request.get('id',f'probe_{len(self.report["model_calls"])}_{i}') if isinstance(request,dict) else None
            reason=None;tool=(self.registry or {}).get(name) if isinstance(name,str) else None
            if not isinstance(request,dict) or request.get('type','function')!='function':reason='invalid_call_shape'
            elif not isinstance(name,str) or name not in READ_TOOLS:reason='not_local_read_allowlist'
            elif tool is None:reason='isolated_registry_not_bound'
            elif (tool.action_class is not ActionClass.READ or offered.get(name)!=tool.schema()):reason='registry_contract_changed'
            elif (not isinstance(identifier,str) or not identifier or identifier in identifiers):reason='invalid_call_id'
            elif not isinstance(arguments,dict):reason='arguments_not_object'
            elif _fehlende_pflichtfelder(tool,arguments):reason='required_arguments_missing'
            else:
                properties=tool.parameters.get('properties',{})
                types={'string':str,'boolean':bool,'integer':int,'number':(int,float)}
                if any(key not in properties or type(value) not in (
                        types.get(properties[key].get('type')) if isinstance(types.get(properties[key].get('type')),tuple)
                        else (types.get(properties[key].get('type')),)) for key,value in arguments.items()):
                    reason='argument_type_or_name'
                elif any(isinstance(value,str) and not value.strip() and key in tool.parameters.get('required',[])
                         for key,value in arguments.items()):reason='empty_required_argument'
                elif tool.classify(arguments) is not ActionClass.READ:reason='classified_non_read'
            decisions.append({'name':name,'id':identifier,'decision':'rejected' if reason else 'validated_read','reason':reason})
            if reason:error=reason
            else:
                identifiers.add(identifier);calls.append(ToolCall(id=identifier,name=name,arguments=copy.deepcopy(arguments)))
        row['tool_decisions']=decisions
        if error:
            for decision in decisions:
                if decision['decision']=='validated_read':decision['decision']='not_returned_reply_rejected'
            raise ProviderError('Werkzeugantwort vollständig abgelehnt: '+error)
        for decision in decisions:decision['decision']='allowed_read'
        return calls

    def _call(self,messages,*,max_tokens,schema=None,tools=None):
        if len(self.report['model_calls'])>=self.limit:self._refuse(ProbeLimit('Aufrufgrenze erreicht.'))
        # Definitionen sind noch keine Ausführung. Der vollständige Modelleingang
        # zählt einschließlich Werkzeug- und Ausgabeschema gegen dieselbe Grenze.
        model_input={'messages':messages}
        if schema is not None:model_input['format']=schema
        if tools:model_input['tools']=[{'type':'function','function':tool} for tool in tools]
        byte_size=lambda value:len(json.dumps(value,ensure_ascii=False).encode())
        row={'stage':self.report.get('stage'),'question_id':self.report.get('question_id'),
             'messages':messages,'tools':tools or [],'tool_count':len(tools or []),
             'messages_bytes':byte_size(messages),'requested_input_bytes':byte_size(model_input),'status':'started'}
        self.report['model_calls'].append(row);self.save();start=time.monotonic()
        phase='tool_history_invalid'
        try:
            native=self._native_messages(messages)
            native_input=dict(model_input,messages=native)
            row['native_messages']=native;row['native_input_bytes']=byte_size(native_input)
            row['requested_input_bytes']=max(row['requested_input_bytes'],row['native_input_bytes'])
            phase='input_limit'
            if row['requested_input_bytes']>16000:
                raise ProviderError('Eingabe über der sicheren 8K-Diagnosegrenze; nicht gekürzt.')
            phase='model_identity'
            identity=verify_local_model(self.base)
            if self.identity is not None and self.identity!=identity:raise ProbeLimit('Modellgewichte geändert.')
            self.identity=identity
            payload={'model':self.model,'messages':native,'stream':False,'think':False,'keep_alive':'15s',
                     'options':{'num_ctx':8192,'num_predict':min(max_tokens,1200),'temperature':0,'seed':42}}
            if schema is not None:payload['format']=schema
            if tools:payload['tools']=model_input['tools']
            phase='transport'
            with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as client:
                response=client.post(BASE+'/api/chat',json=payload);response.raise_for_status();data=response.json()
            row['response']=data
            message=data.get('message') or {}
            phase='response_invalid'
            raw_calls=message.get('tool_calls')
            if (data.get('done') is not True or data.get('done_reason') not in (None,'stop')
                    or not isinstance(message.get('content'),str) or not (message['content'].strip() or raw_calls)):
                raise ProviderError('Leere oder abgeschnittene Antwort.')
            phase='context_reserve'
            if (type(data.get('prompt_eval_count')) is not int or data['prompt_eval_count']<=0
                    or type(data.get('eval_count')) is not int or data['eval_count']<0
                    or data['prompt_eval_count']>=6992):
                raise ProviderError('Kontextreserve nicht nachgewiesen; Ergebnis nicht vollständig gewertet.')
            phase='model_identity'
            if verify_local_model(self.base)!=identity:raise ProbeLimit('Modellgewichte geändert.')
            phase='tool_call_rejected'
            calls=self._read_calls(raw_calls,tools,row) if raw_calls else []
            for call in calls:self.prior_calls[call.id]=call
            row['status']='completed';return Reply(text=message['content'],tool_calls=calls,model=self.model)
        except Exception as exc:
            row.update(status='failed',error=type(exc).__name__+': '+str(exc),failure_reason=phase,
                       failure_origin='adapter' if phase in {'input_limit','tool_history_invalid','tool_call_rejected'} else
                       'model_response' if phase in {'response_invalid','context_reserve'} else phase)
            raise
        finally:
            row['seconds']=round(time.monotonic()-start,3);self.save()

    def _refuse(self,error):
        self.report.setdefault('provider_refusals',[]).append({'stage':self.report.get('stage'),
            'question_id':self.report.get('question_id'),'failure_origin':'adapter','error':str(error)})
        self.save();raise error

    def complete_json(self,messages,*,max_tokens=256,schema=None):
        return self._call(messages,max_tokens=max_tokens,schema=schema or 'json')

    def complete(self,messages,tools):
        # Ausschließlich geprüfte lokale Leseanträge erreichen die normale
        # Agent-Policy; dieser Adapter führt selbst kein Werkzeug aus.
        return self._call(messages,max_tokens=1024,tools=tools)


@contextmanager
def read_tool_scope(provider):
    """Nur die frisch isolierte Messinstanz darf die echte Registry binden."""
    from messlatte import instanz
    original=instanz.instanz_starten
    @contextmanager
    def launch(*args,**kwargs):
        with original(*args,**kwargs) as app:
            provider.registry=app.agent._tools
            try:yield app
            finally:provider.registry=None
    with patch.object(instanz,'instanz_starten',launch):yield


class TrackedEmbedding:
    """Auch Identitätsfehler vor embed() müssen im Diagnosebericht erhalten bleiben."""
    is_local=True
    def __init__(self,factory,report,save):
        self.factory=factory;self.report=report;self.save=save;self.permission_check=lambda:None

    def _observe(self,key,operation,**fields):
        row={'stage':self.report.get('stage'),'status':'started',**fields}
        self.report.setdefault(key,[]).append(row);self.save();start=time.monotonic()
        try:
            value=operation();row['status']='completed';return value
        except Exception as error:
            row.update(status='failed',error=type(error).__name__+': '+str(error));raise
        finally:row['seconds']=round(time.monotonic()-start,3);self.save()

    def __enter__(self):
        def enter():
            self.adapter=self.factory();self.adapter.permission_check=self.permission_check
            self.active=self.adapter.__enter__();self.model_key=self.active.model_key
        self._observe('embedding_sessions',enter)
        return self

    def __exit__(self,*args):return self.adapter.__exit__(*args)

    def embed(self,texts):
        return self._observe('embedding_calls',lambda:self.active.embed(texts),count=len(texts))


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
    failures=[f'{key}:{i}' for key in ('model_calls','embedding_calls','embedding_sessions')
              for i,row in enumerate(report.get(key,[])) if row.get('status')!='completed']
    failures.extend(f'provider_refusal:{i}' for i,_ in enumerate(report.get('provider_refusals',[])))
    technical=(report.get('finished') is True and report.get('originals_preserved') is True
        and not failures and not report.get('error')
        and report.get('tasks_created_without_confirmation')==0
        and (report.get('mode')!='live_qwen_bge' or
             (report.get('semantic_search') is True and report.get('semantic_coverage',{}).get('status')=='indexed'
              and report.get('semantic_after_recall',{}).get('status')=='indexed'
              and exact(report.get('semantic_observations',[]),expected_questions)
              and all(r['coverage'].get('status')=='indexed' for r in report.get('semantic_observations',[]))
              and all(report.get(k) for k in ('model_calls','embedding_calls','embedding_sessions'))))
        and exact(classifications,expected_sources)
        and all(r['state'] in {'complete','empty'} and r['original_body_preserved'] and r['date_absence_preserved'] for r in classifications)
        and exact(report.get('questions',[]),expected_questions)
        and exact(report.get('task_checks',[]),expected_sources)
        and set(report.get('people_checks',{}))=={'required_identities_present','identities_not_merged','service_not_person'}
        and not any(r.get('error') for r in report.get('questions',[]))
        and bool(scan) and all(r['available'] and not r['failed'] and not r['cancelled'] for r in scan))
    return {'pipeline_complete':technical,'contract_checks_passed':sum(bool(v) for _,v in checks),
        'contract_checks_total':len(checks),'failed_contracts':[k for k,v in checks if not v],
        'technical_failures':failures,
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
                return TrackedEmbedding(lambda:LocalEmbedder(model='bge-m3:latest',verify_weights=True,keep_alive='15s'),report,save)
            with read_tool_scope(provider):
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
