"""Pair validity tests check the real adapter boundary, never grade answer prose."""
import copy
import pytest
from memory_answer_comparison import compare_requests


def payload(prompt):
    return {'model':'fixture-model','messages':[
        {'role':'system','content':prompt+'\nclock=2026-09-01'},
        {'role':'user','content':'{"source_id":"S1","text":"BASE unchanged source"}'},
        {'role':'user','content':'Has it been sent?'}], 'stream':False}


def test_only_intended_system_prefix_can_differ():
    assert compare_requests([payload('BASE')], [payload('CANDIDATE')], 'BASE','CANDIDATE') == []


@pytest.mark.parametrize('mutation', ['source_id','source_order','question','clock','option','extra_system','copied_prompt'])
def test_changed_other_payload_fields_confounds_pair(mutation):
    a,b=payload('BASE'),payload('CANDIDATE')
    if mutation=='source_id': b['messages'][1]['content']=b['messages'][1]['content'].replace('S1','S2')
    if mutation=='source_order': b['messages'][1],b['messages'][2]=b['messages'][2],b['messages'][1]
    if mutation=='question': b['messages'][2]['content']='Will it be sent?'
    if mutation=='clock': b['messages'][0]['content']=b['messages'][0]['content'].replace('09-01','09-02')
    if mutation=='option': b['temperature']=0
    if mutation=='extra_system': b['messages'].append({'role':'system','content':'extra instruction'})
    if mutation=='copied_prompt': b['messages'][1]['content']=b['messages'][1]['content'].replace('BASE','CANDIDATE')
    assert compare_requests([a],[b],'BASE','CANDIDATE')


@pytest.mark.parametrize('invalid', [[],[{'model':'fixture-model','messages':[]}],[payload('WRONG')]])
def test_missing_or_incorrect_system_prefix_is_not_a_valid_pair(invalid):
    assert compare_requests(invalid,[payload('CANDIDATE')],'BASE','CANDIDATE')


def test_comparison_never_mutates_original_requests():
    a,b=[payload('BASE')],[payload('CANDIDATE')]
    before=copy.deepcopy((a,b))
    compare_requests(a,b,'BASE','CANDIDATE')
    assert (a,b)==before

from pathlib import Path
import json
import httpx
from icarus_memory import agent as agent_module
from probe_memory_pipeline import catalog
import probe_memory_answer_contract as runner
from test_probe_memory_pipeline import fake_transport


def versions():
    return {'baseline':{'commit':'a'*40,'prompt':agent_module.SYSTEM_PROMPT},
            'candidate':{'commit':'b'*40,'prompt':agent_module.SYSTEM_PROMPT+'\nCompare candidate.'}}


def selection(case_id='same-name-01', mode='agent'):
    return [{'catalog':{'selector':'development-v1','sha256':'fixture-hash','commit':'a'*40},
             'case':catalog()[case_id], 'mode':mode}]


def test_pair_uses_identical_persisted_fixture_and_wire_payload(tmp_path):
    requests=[];output=tmp_path/'pair.json';prompt=agent_module.SYSTEM_PROMPT
    assert runner.run_comparison(output,versions(),selection(),'fixture-model',transport=fake_transport(requests))==0
    report=json.loads(output.read_text())
    assert report['pairs'][0]['differences']==[]
    assert report['pairs'][0]['comparison']=='prompt_only'
    a,b=report['attempts']
    assert a['result']['expected_manifest']==b['result']['expected_manifest']
    assert a['result']['semantic_verdict']==b['result']['semantic_verdict']=='review_required'
    assert a['wire_requests'][0]['model']=='fixture-model'
    assert agent_module.SYSTEM_PROMPT==prompt
    assert report['metadata_stable'] is True


def test_calendar_pair_is_explicit_unchanged_path_not_prompt_evidence(tmp_path):
    output=tmp_path/'calendar.json'
    assert runner.run_comparison(output,versions(),selection('stale-calendar-01'),'fixture-model',transport=fake_transport([]))==0
    report=json.loads(output.read_text())
    assert report['pairs'][0]['comparison']=='unchanged_deterministic_path'
    assert all(a['wire_requests']==[] for a in report['attempts'])


def test_interruption_reserves_attempt_before_inference_and_never_retries(tmp_path):
    output=tmp_path/'interrupted.json';requests=[]
    def interrupt(request):
        saved=json.loads(output.read_text())
        assert len(saved['attempts'])==1
        assert saved['attempts'][0]['status']=='started'
        raise KeyboardInterrupt()
    assert runner.run_comparison(output,versions(),selection(),'fixture-model',transport=fake_transport(requests,completion=interrupt))==1
    report=json.loads(output.read_text())
    assert len(report['attempts'])==1
    assert report['status']=='incomplete'
    assert len(report['unrun_cells'])==1
    assert report['error_type']=='KeyboardInterrupt'
    with pytest.raises(FileExistsError):
        runner.run_comparison(output,versions(),selection(),'fixture-model',transport=fake_transport(requests))


def test_wall_budget_prevents_launching_new_attempts(tmp_path):
    output=tmp_path/'budget.json'
    assert runner.run_comparison(output,versions(),selection(),'fixture-model',transport=fake_transport([]),wall_seconds=0)==1
    report=json.loads(output.read_text())
    assert report['attempts']==[]
    assert len(report['unrun_cells'])==2
    assert report['stop_reason']=='wall_clock_budget'


def test_prompt_extraction_rejects_executable_values_and_detects_other_changes():
    with pytest.raises(ValueError):
        runner.prompt_from_source('SYSTEM_PROMPT = open("private").read()')
    _,before=runner.prompt_from_source('SYSTEM_PROMPT="one"\nx=1')
    _,after=runner.prompt_from_source('SYSTEM_PROMPT="two"\nx=2')
    assert before!=after
    _,only_prompt=runner.prompt_from_source('SYSTEM_PROMPT="two"\nx=1')
    assert before==only_prompt


@pytest.mark.parametrize('url', ['https://example.com/v1/chat/completions','http://127.0.0.1:11434/api/pull','http://localhost:11434/v1/chat/completions'])
def test_wire_boundary_rejects_remote_or_undeclared_routes(url):
    def forbidden(request):
        pytest.fail('Disallowed request reached transport')
    with pytest.raises(ValueError):
        runner.WireTransport(httpx.MockTransport(forbidden)).handle_request(httpx.Request('POST',url,json={}))


def test_metadata_drift_stops_remaining_pairs(tmp_path):
    calls=[];delegate=fake_transport(calls)
    tag_calls=0
    def drift(request):
        nonlocal tag_calls
        if request.url.path=='/api/tags':
            tag_calls+=1
            if tag_calls>1:return httpx.Response(200,json={'models':[{'name':'fixture-model','digest':'changed'}]})
        return delegate.handle_request(request)
    output=tmp_path/'drift.json'
    rows=selection()+selection('newer-rejection-01')
    assert runner.run_comparison(output,versions(),rows,'fixture-model',transport=httpx.MockTransport(drift))==1
    report=json.loads(output.read_text())
    assert len(report['attempts'])==2
    assert report['metadata_stable'] is False
    assert report['stop_reason']=='metadata_changed'
    assert len(report['unrun_cells'])==2


def test_two_transport_failures_stop_without_replacement(tmp_path):
    def fail(request):raise httpx.ReadTimeout('test interruption')
    output=tmp_path/'failed.json'
    rows=selection()+selection('newer-rejection-01')
    assert runner.run_comparison(output,versions(),rows,'fixture-model',transport=fake_transport([],completion=fail))==1
    report=json.loads(output.read_text())
    assert len(report['attempts'])==2
    assert all(a['status']=='technical_failure' for a in report['attempts'])
    assert report['stop_reason']=='repeated_transport_failure'
    assert len(report['unrun_cells'])==2


def test_input_mismatch_stops_even_when_one_answer_failed(tmp_path,monkeypatch):
    original=runner.providers.OpenAICompatible.complete
    def alter_question(self,messages,tools):
        messages=copy.deepcopy(messages)
        if 'Compare candidate.' in messages[0]['content']:messages[-1]['content']+=' changed'
        return original(self,messages,tools)
    monkeypatch.setattr(runner.providers.OpenAICompatible,'complete',alter_question)
    def completion(request):
        changed='Compare candidate.' in json.loads(request.content)['messages'][0]['content']
        return httpx.Response(200,json={'choices':[{'message':{'content':'' if changed else 'Synthetic answer'}}]})
    output=tmp_path/'mismatch-failure.json'
    assert runner.run_comparison(output,versions(),selection()+selection('newer-rejection-01'),'fixture-model',transport=fake_transport([],completion=completion))==1
    report=json.loads(output.read_text())
    assert len(report['attempts'])==2
    assert report['stop_reason']=='payload_mismatch'
    assert report['pairs'][0]['comparison']=='confounded'


def test_unsafe_route_stops_after_first_attempt(tmp_path,monkeypatch):
    original=runner.providers.OpenAICompatible.complete
    def unsafe(self,messages,tools):
        self._base='http://external.example.invalid/v1'
        return original(self,messages,tools)
    monkeypatch.setattr(runner.providers.OpenAICompatible,'complete',unsafe)
    output=tmp_path/'unsafe.json'
    assert runner.run_comparison(output,versions(),selection(),'fixture-model',transport=fake_transport([]))==1
    report=json.loads(output.read_text())
    assert len(report['attempts'])==1
    assert report['stop_reason']=='unsafe_request'


def test_metadata_drift_after_failed_pair_stops_before_next_pair(tmp_path):
    delegate=fake_transport([],completion=lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'','tool_calls':[{'id':'bad','function':{'name':'unknown','arguments':'{}'}}]}}]}))
    tag_calls=0
    def drift(request):
        nonlocal tag_calls
        if request.url.path=='/api/tags':
            tag_calls+=1
            if tag_calls>1:return httpx.Response(200,json={'models':[{'name':'fixture-model','digest':'changed'}]})
        return delegate.handle_request(request)
    output=tmp_path/'failed-drift.json'
    assert runner.run_comparison(output,versions(),selection()+selection('newer-rejection-01'),'fixture-model',transport=httpx.MockTransport(drift))==1
    report=json.loads(output.read_text())
    assert len(report['attempts'])==2
    assert report['stop_reason']=='metadata_changed'
