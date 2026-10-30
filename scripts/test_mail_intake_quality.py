"""Die Messprobe muss falsche Belege und fehlende Aufgaben sichtbar lassen."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    path = Path(__file__).with_name('mail_intake_quality.py')
    assert path.exists(), 'Aufnahmeprüfer fehlt'
    spec = importlib.util.spec_from_file_location('mail_intake_quality', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_catalog_has_fixed_sources_and_hides_oracle_from_rfc822():
    m = module(); data = m.load_catalog()
    assert len(data['mails']) == 24 and len(data['questions']) >= 12
    from messlatte.postfach import rohmail
    source = copy.deepcopy(data['mails'][0])
    source['expect']['note'] = 'ORACLE_ONLY_SECRET_SENTINEL'
    wire = rohmail(m.to_mail(source, data['owner']))
    assert b'ORACLE_ONLY_SECRET_SENTINEL' not in wire
    from email import policy
    from email.parser import BytesParser
    assert BytesParser(policy=policy.default).parsebytes(wire).get_content().strip() == source['body'].strip()


@pytest.mark.parametrize('mutation', ['real_address', 'future_source', 'missing_source', 'duplicate', 'not_synthetic'])
def test_invalid_catalog_fails_before_any_network(tmp_path, mutation):
    m=module(); data=m.load_catalog()
    if mutation=='real_address': data['mails'][0]['sender']['address']='person@gmail.com'
    if mutation=='future_source': data['mails'][0]['at']='2030-01-01T12:00:00+01:00'
    if mutation=='missing_source': data['questions'][0]['required']=['not-a-source']
    if mutation=='duplicate': data['mails'][1]['id']=data['mails'][0]['id']
    if mutation=='not_synthetic': data['synthetic_only']=False
    path=tmp_path/'catalog.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):m.load_catalog(path)


def test_correct_words_with_wrong_or_missing_sources_never_pass():
    m=module();case={'required':['a'],'allowed':['a'],'status':['working_reports'],'contains':['blau'],'excludes':[]}
    assert not all(m.grade_question(case,{'sources':['b'],'status':'working_reports','text':'blau'}).values())
    assert not all(m.grade_question(case,{'sources':[],'status':'working_reports','text':'blau'}).values())
    assert all(m.grade_question(case,{'sources':['a'],'status':'working_reports','text':'blau'}).values())


def test_unknown_answer_rejects_any_source_and_forbidden_statement():
    m=module();case={'required':[],'allowed':[],'status':['working_unknown'],'contains':[],'excludes':['bestätigt']}
    assert not all(m.grade_question(case,{'sources':['a'],'status':'working_unknown','text':'bestätigt'}).values())


def test_required_task_is_not_satisfied_by_an_empty_result_or_wrong_person_date():
    m=module();expect={'tasks':'required','person':'alex@work.example','due':'2026-11-02T18:00:00+01:00','anchor':'Druckdaten'}
    row={'statement':'Druckdaten schicken','person_vorschlag':{'adresse':'alex@work.example'},'frist_vorschlag':'2026-11-02T17:00:00+00:00'}
    assert not all(m.grade_tasks(expect,[]).values())
    assert all(m.grade_tasks(expect,[row]).values())
    for field,value in [('person_vorschlag',{'adresse':'alex@home.example'}),('frist_vorschlag','2026-11-02T23:59:00+01:00')]:
        bad={**row,field:value};assert not all(m.grade_tasks(expect,[bad]).values())


def test_review_must_not_prefill_a_superseded_due_date():
    m=module();expect={'tasks':'review','person':'alex@work.example','due':None,'anchor':'Druckdaten','temporal':['followup']}
    row={'statement':'Druckdaten schicken','person_vorschlag':{'adresse':'alex@work.example'},'frist_vorschlag':None,'temporal_status':'followup'}
    assert all(m.grade_tasks(expect,[row]).values())
    assert not all(m.grade_tasks(expect,[{**row,'frist_vorschlag':'2026-11-02T18:00:00+01:00'}]).values())


def test_profile_check_detects_same_name_people_merged_and_service_as_human():
    m=module();expect={'separate':[['alex@work.example'],['alex@home.example']],'not_people':['service@shop.example']}
    correct=[{'adressen':['alex@work.example']},{'adressen':['alex@home.example']}]
    assert all(m.grade_people(expect,correct).values())
    assert not all(m.grade_people(expect,[{'adressen':['alex@work.example','alex@home.example']}]).values())
    assert not all(m.grade_people(expect,correct+[{'adressen':['service@shop.example']}]).values())


def test_real_parser_store_and_api_keep_oracle_out_and_missing_task_visible(tmp_path):
    m=module();data=m.load_catalog();source=copy.deepcopy(data['mails'][3])
    source['expect']['note']='ORACLE_ONLY_SECRET_SENTINEL'
    data['mails']=[source,data['mails'][21]];data['questions']=[data['questions'][4]]
    data['people']={'separate':[['alex.sommer@beta.example']],'not_people':[]}
    from icarus_memory.providers import Reply
    class Boundary:
        is_local=True;name=model='synthetic-mechanics-only'
        def __init__(self):self.seen=[]
        def complete_json(self,messages,**kwargs):
            self.seen.append(messages)
            try:payload=json.loads(messages[-1]['content'])
            except ValueError:payload={}
            if 'blocks' in payload:
                return Reply(text=json.dumps({'items':{b['block_id']:'fact' for b in payload['blocks']}}))
            if 'sources' in payload:
                return Reply(text=json.dumps({'status':'source_reports','ids':[s['id'] for s in payload['sources']]}))
            return Reply(text='{"items":[]}')
        def complete(self,messages,tools):return self.complete_json(messages)
    class EmbeddingBoundary:
        is_local=True;model_key='synthetic-embedding:'+('a'*64)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def embed(self,texts):return [[1.0,0.0,0.0] for text in texts]
    provider=Boundary();report={};m.run_pipeline(data,provider,tmp_path,report,lambda:None,embedding_factory=EmbeddingBoundary)
    assert report['classification'][0]['original_body_preserved']
    assert report['classification'][0]['state']=='complete'
    assert report['classification'][1]['occurred_at'] is None
    assert report['classification'][1]['date_absence_preserved'] is True
    assert len(report['questions'])==1
    assert not all(report['task_checks'][0]['checks'].values())
    assert report['tasks_created_without_confirmation']==0
    assert report['semantic_search'] is True
    assert report['semantic_coverage']['status']=='indexed'
    assert 'ORACLE_ONLY_SECRET_SENTINEL' not in json.dumps(provider.seen)
    assert report['bulk_import_authorized'] is False and report['semantic_grade']=='requires_review'


def probe_module():
    path=Path(__file__).with_name('probe_mail_intake_quality.py')
    assert path.exists(), 'Begrenzter lokaler Probenläufer fehlt'
    spec=importlib.util.spec_from_file_location('probe_mail_quality',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('reply,reason,valid', [('ok','stop',True),('','stop',False),('partial','length',False)])
def test_native_boundary_is_bounded_and_empty_or_truncated_is_never_success(monkeypatch,reply,reason,valid):
    import httpx
    from icarus_memory.providers import ProviderError
    from types import SimpleNamespace
    m=probe_module();monkeypatch.setattr(m,'verify_local_model',lambda p:SimpleNamespace(name=p.model,digest='fixture'))
    requests=[]
    def handler(request):
        requests.append(request);assert request.url.host=='127.0.0.1' and request.url.path=='/api/chat'
        return httpx.Response(200,json={'message':{'content':reply},'done':True,'done_reason':reason,'prompt_eval_count':100,'eval_count':10})
    original=httpx.Client
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(handler),**kwargs)
    monkeypatch.setattr(m.httpx,'Client',client)
    record={'model_calls':[]};p=m.NativeProbe('synthetic',record,lambda:None,limit=1)
    if valid:assert p.complete_json([{'role':'user','content':'synthetic'}]).text=='ok'
    else:
        with pytest.raises(ProviderError):p.complete_json([{'role':'user','content':'synthetic'}])
    payload=json.loads(requests[0].content)
    assert payload['options']['num_ctx']==8192 and payload['options']['num_predict']<=1200
    assert 'tools' not in payload and payload['think'] is False
    with pytest.raises(m.ProbeLimit):p.complete_json([])
    assert len(requests)==1


def test_unverified_weights_are_rejected_without_source_submission(monkeypatch):
    import httpx
    from icarus_memory.providers import ProviderError
    m=probe_module()
    def unverified(provider):raise ProviderError('no local weights')
    monkeypatch.setattr(m,'verify_local_model',unverified)
    monkeypatch.setattr(m.httpx,'Client',lambda **kw:pytest.fail('must verify before source request'))
    with pytest.raises(ProviderError):m.NativeProbe('missing',{'model_calls':[]},lambda:None).complete_json([])


def test_context_risk_and_tool_execution_do_not_become_good_answers(monkeypatch):
    import httpx
    from types import SimpleNamespace
    from icarus_memory.providers import ProviderError
    m=probe_module();monkeypatch.setattr(m,'verify_local_model',lambda p:SimpleNamespace(name=p.model,digest='fixture'))
    original=httpx.Client
    monkeypatch.setattr(m.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'message':{'content':'ok'},'done':True,'done_reason':'stop','prompt_eval_count':8000,'eval_count':10})),**kw))
    p=m.NativeProbe('synthetic',{'model_calls':[]},lambda:None)
    with pytest.raises(ProviderError):p.complete_json([])
    with pytest.raises(ProviderError):p.complete([], [{'name':'send_mail'}])


@pytest.mark.parametrize('elapsed,pressure,free,want', [(901,1,50,'time_budget'),(3,4,50,'memory_pressure'),(3,1,20,'memory_reserve'),(3,1,45,None)])
def test_worker_stop_conditions_preserve_mac_reserve(elapsed,pressure,free,want):
    assert probe_module().stop_reason(elapsed,{'pressure':pressure,'free_percent':free},900)==want


def test_summary_never_treats_partial_coverage_or_changed_originals_as_complete():
    m=probe_module()
    report={'finished':True,'originals_preserved':True,'tasks_created_without_confirmation':0,'task_scan':[{'failed':0,'cancelled':False,'available':True}],
        'task_checks':[{'id':f'm{i:02}','checks':{'present':True}} for i in range(1,25)],
        'people_checks':{'required_identities_present':True,'identities_not_merged':True,'service_not_person':True},
        'classification':[{'id':f'm{i:02}','state':'complete','original_body_preserved':True,'date_absence_preserved':True} for i in range(1,25)],
        'questions':[{'id':f'q{i:02}','checks':{'source':True}} for i in range(1,17)]}
    assert m.summarize(report)['pipeline_complete'] is True
    for change in [{'originals_preserved':False},{'tasks_created_without_confirmation':1},
                   {'questions':report['questions'][:-1]},
                   {'questions':report['questions'][:-1]+[report['questions'][0]]},
                   {'finished':False}]:
        assert m.summarize({**report,**change})['pipeline_complete'] is False
    assert m.summarize(report)['bulk_import_authorized'] is False


@pytest.mark.parametrize('failure', ['failed_model','unfinished_model','refusal','failed_embedding','failed_identity','stale_coverage'])
def test_useful_fallback_never_masks_transport_failure(failure):
    m=probe_module()
    catalog=module().load_catalog();catalog['mails']=catalog['mails'][:1];catalog['questions']=catalog['questions'][:1]
    report={'mode':'live_qwen_bge','finished':True,'originals_preserved':True,'tasks_created_without_confirmation':0,
        'semantic_search':True,'semantic_coverage':{'status':'indexed'},'semantic_after_recall':{'status':'indexed'},
        'semantic_observations':[{'id':'q01','coverage':{'status':'indexed'}}],
        'classification':[{'id':'m01','state':'complete','original_body_preserved':True,'date_absence_preserved':True}],
        'task_scan':[{'available':True,'failed':0,'cancelled':False}],
        'task_checks':[{'id':'m01','checks':{'task':True}}],
        'people_checks':dict.fromkeys(('required_identities_present','identities_not_merged','service_not_person'),True),
        'questions':[{'id':'q01','observed':{'text':'Hilfreiches Originalzitat'},'checks':{'correct_source':True}}],
        'model_calls':[{'status':'completed'}],'embedding_calls':[{'status':'completed'}],
        'embedding_sessions':[{'status':'completed'}]}
    assert m.summarize(report,catalog)['pipeline_complete'] is True
    if failure=='failed_model':report['model_calls'].append({'status':'failed'})
    if failure=='unfinished_model':report['model_calls'].append({'status':'started'})
    if failure=='refusal':report['provider_refusals']=[{'error':'budget'}]
    if failure=='failed_embedding':report['embedding_calls'].append({'status':'failed'})
    if failure=='failed_identity':report['embedding_sessions'].append({'status':'failed'})
    if failure=='stale_coverage':report['semantic_observations'][0]['coverage']['status']='unavailable'
    assert m.summarize(report,catalog)['pipeline_complete'] is False


@pytest.mark.parametrize('refusal', ['weights','input','limit','tools'])
def test_all_pretransport_refusals_are_recorded(monkeypatch,refusal):
    import httpx
    from types import SimpleNamespace
    from icarus_memory.providers import ProviderError
    m=probe_module();report={'model_calls':[]}
    def identity(provider):
        if refusal=='weights':raise ProviderError('synthetic identity failure')
        return SimpleNamespace(name=provider.model,digest='fixture')
    monkeypatch.setattr(m,'verify_local_model',identity)
    monkeypatch.setattr(m.httpx,'Client',lambda **kw:pytest.fail('refusal must precede source transport'))
    p=m.NativeProbe('synthetic',report,lambda:None,limit=0 if refusal=='limit' else 1)
    with pytest.raises(ProviderError):
        if refusal=='tools':p.complete([], [{'name':'send_mail'}])
        else:p.complete_json([{'role':'user','content':'x'*17000 if refusal=='input' else 'synthetic'}])
    assert report.get('provider_refusals') or any(r['status']=='failed' for r in report['model_calls'])


@pytest.mark.parametrize('failure',['identity','query'])
def test_real_semantic_failure_preserves_answer_and_reports_recall_gap(tmp_path,failure):
    from icarus_memory.providers import ProviderError,Reply
    m=module();runner=probe_module();data=m.load_catalog()
    data['mails']=[data['mails'][4]];data['questions']=[data['questions'][1]]
    data['people']={'separate':[['alex.zweit@alpha.example']],'not_people':[]}
    report={'mode':'live_qwen_bge','model_calls':[]}
    class Language:
        is_local=True;name=model='synthetic-mechanics-only'
        def complete_json(self,messages,**kwargs):
            payload=json.loads(messages[-1]['content'])
            if 'blocks' in payload:return Reply(text=json.dumps({'items':{b['block_id']:'fact' for b in payload['blocks']}}))
            if 'sources' in payload:return Reply(text=json.dumps({'status':'source_reports','ids':[s['id'] for s in payload['sources']]}))
            return Reply(text='{"items":[]}')
        def complete(self,messages,tools):return self.complete_json(messages)
    class Embedding:
        is_local=True;model_key='synthetic:'+('a'*64)
        def __enter__(self):
            if report.get('stage')=='fresh_recall' and failure=='identity':raise ProviderError('synthetic identity failure')
            return self
        def __exit__(self,*args):pass
        def embed(self,texts):
            if report.get('stage')=='fresh_recall' and failure=='query':raise ProviderError('synthetic query failure')
            return [[1.,0.,0.] for _ in texts]
    m.run_pipeline(data,Language(),tmp_path,report,lambda:None,
        embedding_factory=lambda:runner.TrackedEmbedding(Embedding,report,lambda:None))
    assert report['questions'][0]['observed']['sources']==['m05']
    assert all(report['questions'][0]['checks'].values())  # Hilfreicher echter Zitat-Rückfall.
    assert report['semantic_coverage']['status']=='indexed'
    assert report['semantic_observations'][0]['coverage']['status']=='unavailable'
    assert not runner.summarize(report,data)['pipeline_complete']


def test_real_sentence_failure_preserves_quote_but_is_not_technical_success(tmp_path):
    from icarus_memory.providers import ProviderError,Reply
    from icarus_memory.satzantwort import ist_satzanfrage
    m=module();runner=probe_module();data=m.load_catalog()
    data['mails']=[data['mails'][4]];data['questions']=[data['questions'][1]]
    data['people']={'separate':[['alex.zweit@alpha.example']],'not_people':[]}
    report={'model_calls':[]}
    class Language:
        is_local=True;name=model='synthetic-mechanics-only'
        def complete_json(self,messages,**kwargs):
            if ist_satzanfrage(messages):
                report['model_calls'].append({'status':'failed'});raise ProviderError('synthetic sentence failure')
            payload=json.loads(messages[-1]['content'])
            if 'blocks' in payload:return Reply(text=json.dumps({'items':{b['block_id']:'fact' for b in payload['blocks']}}))
            if 'sources' in payload:return Reply(text=json.dumps({'status':'source_reports','ids':[s['id'] for s in payload['sources']]}))
            return Reply(text='{"items":[]}')
        def complete(self,messages,tools):return self.complete_json(messages)
    m.run_pipeline(data,Language(),tmp_path,report,lambda:None)
    assert report['model_calls'][-1]['status']=='failed'
    assert all(report['questions'][0]['checks'].values())
    assert not runner.summarize(report,data)['pipeline_complete']


def test_missing_context_accounting_is_incomplete_not_a_safe_response(monkeypatch):
    import httpx
    from types import SimpleNamespace
    from icarus_memory.providers import ProviderError
    m=probe_module();monkeypatch.setattr(m,'verify_local_model',lambda p:SimpleNamespace(name=p.model,digest='fixture'))
    original=httpx.Client
    monkeypatch.setattr(m.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'message':{'content':'ok'},'done':True,'done_reason':'stop'})),**kw))
    with pytest.raises(ProviderError):m.NativeProbe('synthetic',{'model_calls':[]},lambda:None).complete_json([])


def test_pressure_watch_terminates_only_its_own_worker():
    import multiprocessing
    import time
    m=probe_module();context=multiprocessing.get_context('spawn')
    owned=context.Process(target=time.sleep,args=(30,));other=context.Process(target=time.sleep,args=(30,))
    owned.start();other.start()
    try:
        samples,reason=m.monitor_worker(owned,900,measure=lambda:{'pressure':4,'free_percent':45})
        assert reason=='memory_pressure' and samples
        assert not owned.is_alive() and other.is_alive()
    finally:
        for process in (owned,other):
            if process.is_alive():process.terminate()
            process.join(5)


def test_offline_ollama_leaves_an_explicit_incomplete_report_and_never_overwrites(monkeypatch,tmp_path):
    import httpx
    m=probe_module();monkeypatch.setattr(m,'resources',lambda:{'pressure':1,'free_percent':45})
    original=httpx.Client
    def offline(request):raise httpx.ConnectError('synthetic offline',request=request)
    monkeypatch.setattr(m.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(offline),**kw))
    output=tmp_path/'first'
    assert m.run(output)==2
    before=(output/'report.json').read_bytes();report=json.loads(before)
    assert report['stop_reason']=='ollama_unavailable' and report['finished'] is False
    assert report['model_calls']==[] and report['bulk_import_authorized'] is False
    with pytest.raises(FileExistsError):m.run(output)
    assert (output/'report.json').read_bytes()==before
