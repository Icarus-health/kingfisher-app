"""Expliziter kleiner Ollama-Kontext: vollständiger Eingang oder technischer Fehler."""
from contextlib import nullcontext
import json
import httpx
import pytest

from icarus_memory.providers import OpenAICompatible,ProviderError

ALIAS='kingfisher-synthetic:8k'
BASE='http://127.0.0.1:11434/v1'


def setup(monkeypatch,*,version='0.40.13',parameters='num_ctx 8192',reply=None):
    monkeypatch.setenv('ICARUS_OLLAMA_8K_PROFILE',ALIAS)
    requests=[];tags={'models':[{'name':ALIAS,'digest':'a'*64,'size':1000,'details':{'format':'gguf'}}]}
    show={'details':{'format':'gguf'},'capabilities':['completion'],
          'model_info':{'general.architecture':'qwen','general.parameter_count':1000},'parameters':parameters}
    response=reply or {'done':True,'done_reason':'stop','message':{'content':'{}'},'prompt_eval_count':300,'eval_count':8}
    def handler(request):
        body=json.loads(request.content) if request.content else None
        requests.append((request.url.path,body))
        if request.url.path=='/api/tags':return httpx.Response(200,json=tags)
        if request.url.path=='/api/show':return httpx.Response(200,json=show)
        if request.url.path=='/api/version':return httpx.Response(200,json={'version':version})
        if request.url.path=='/api/chat':return httpx.Response(400 if 'error' in response else 200,json=response)
        if request.url.path=='/v1/chat/completions':return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'legacy'}}]})
        pytest.fail(f'Unexpected source/model request: {request.url.path}')
    original=httpx.Client
    def client(**kw):
        assert kw.get('trust_env') is False and kw.get('follow_redirects') is False
        return original(transport=httpx.MockTransport(handler),**kw)
    monkeypatch.setattr(httpx,'Client',client)
    provider=OpenAICompatible(ALIAS,base_url=BASE)
    monkeypatch.setattr(provider,'_ampel',nullcontext)
    return provider,requests,show,tags


@pytest.mark.parametrize('json_mode',[False,True])
def test_selected_exact_profile_sends_native_no_truncation_and_v1_defaults(monkeypatch,json_mode):
    p,requests,_,_=setup(monkeypatch)
    messages=[{'role':'user','content':'synthetic'}]
    result=p.complete_json(messages,schema={'type':'object'}) if json_mode else p.complete(messages,[])
    assert result.text=='{}'
    body=next(body for path,body in requests if path=='/api/chat')
    assert body['messages']==messages and body['truncate'] is False and body['shift'] is False
    assert body['options']['num_ctx']==8192 and body['options']['num_predict']==(256 if json_mode else 1024)
    assert body['options']['temperature']==(0 if json_mode else 1.0)
    assert body['options']['top_p']==1.0 and body['options']['presence_penalty']==0.0 and body['options']['frequency_penalty']==0.0
    assert body['think'] is False and body['stream'] is False
    if json_mode:assert body['format']=={'type':'object'}
    assert not any(path=='/v1/chat/completions' for path,_ in requests)


@pytest.mark.parametrize('version',['0.40.12','0.40.13-rc1','garbage'])
def test_unsupported_server_fails_before_source_submission(monkeypatch,version):
    p,requests,_,_=setup(monkeypatch,version=version)
    with pytest.raises(ProviderError):p.complete([{'role':'user','content':'SOURCE_SENTINEL'}],[])
    assert not any(path in {'/api/chat','/v1/chat/completions'} for path,_ in requests)


@pytest.mark.parametrize('parameters',['num_ctx 32768','','num_ctx 8192\nnum_ctx 32768'])
def test_wrong_or_ambiguous_profile_fails_before_ampel_or_source(monkeypatch,parameters):
    p,requests,_,_=setup(monkeypatch,parameters=parameters)
    monkeypatch.setattr(p,'_ampel',lambda:pytest.fail('must fail before model preparation'))
    with pytest.raises(ProviderError):p.complete_json([{'role':'user','content':'synthetic'}])
    assert not any(path=='/api/chat' for path,_ in requests)


@pytest.mark.parametrize('where',['message','tools','schema','history'])
def test_complete_logical_input_overflow_fails_before_model_preparation(monkeypatch,where):
    p,requests,_,_=setup(monkeypatch)
    monkeypatch.setattr(p,'_ampel',lambda:pytest.fail('overlimit input must never prepare model'))
    messages=[{'role':'user','content':'x'*17000 if where=='message' else 'synthetic'}]
    if where=='history':messages.append({'role':'assistant','content':'ä'*9000})
    with pytest.raises(ProviderError):
        if where=='schema':p.complete_json(messages,schema={'description':'x'*17000})
        else:p.complete(messages,[{'name':'write_tool','description':'x'*17000,'parameters':{}}] if where=='tools' else [])
    assert requests==[]


def test_native_tools_keep_all_definitions_ids_and_json_argument_objects(monkeypatch):
    response={'done':True,'done_reason':'stop','message':{'content':'','tool_calls':[{
        'id':'returned-call','function':{'name':'write_tool','arguments':{'title':'synthetic'}}}]},'prompt_eval_count':300,'eval_count':20}
    p,requests,_,_=setup(monkeypatch,reply=response)
    tools=[{'name':'write_tool','description':'Existing policy remains responsible','parameters':{'type':'object'}}]
    messages=[{'role':'user','content':'synthetic'}, {'role':'assistant','content':'','tool_calls':[{
        'id':'old-call','type':'function','function':{'name':'write_tool','arguments':'{"title":"original"}'}}]},
        {'role':'tool','tool_call_id':'old-call','content':'original result'}]
    reply=p.complete(messages,tools)
    assert reply.tool_calls[0].id=='returned-call' and reply.tool_calls[0].arguments=={'title':'synthetic'}
    body=next(body for path,body in requests if path=='/api/chat')
    assert body['tools']==[{'type':'function','function':tools[0]}]
    assert body['messages'][1]['tool_calls'][0]['id']=='old-call'
    assert body['messages'][1]['tool_calls'][0]['function']['arguments']=={'title':'original'}
    assert body['messages'][2]=={'role':'tool','tool_call_id':'old-call','tool_name':'write_tool','content':'original result'}
    assert messages[1]['tool_calls'][0]['function']['arguments']=='{"title":"original"}'


@pytest.mark.parametrize('change',[{'done':False},{'done_reason':'length'},{'prompt_eval_count':6992},{'eval_count':1500},{'prompt_eval_count':None}])
def test_native_incomplete_or_unproven_context_is_never_success(monkeypatch,change):
    data={'done':True,'done_reason':'stop','message':{'content':'{}'},'prompt_eval_count':300,'eval_count':8,**change}
    p,_,_,_=setup(monkeypatch,reply=data)
    with pytest.raises(ProviderError):p.complete_json([{'role':'user','content':'synthetic'}])


@pytest.mark.parametrize('mutation',['flag_blank','different_name','subclass','remote'])
def test_unselected_provider_keeps_old_transport(monkeypatch,mutation):
    p,requests,_,_=setup(monkeypatch)
    if mutation=='flag_blank':monkeypatch.delenv('ICARUS_OLLAMA_8K_PROFILE')
    if mutation=='different_name':p.model=ALIAS+'-also8k'
    if mutation=='subclass':
        class Other(OpenAICompatible):pass
        p=Other(ALIAS,base_url=BASE);monkeypatch.setattr(p,'_ampel',nullcontext)
    if mutation=='remote':
        p=OpenAICompatible(ALIAS,base_url='https://remote.example/v1');monkeypatch.setattr(p,'_ampel',nullcontext)
        original=httpx.Client
        monkeypatch.setattr(p,'_client',lambda timeout:original(timeout=timeout,trust_env=False,follow_redirects=False))
        # Only inspect the explicit selection function; no remote request.
        from icarus_memory.local_context_profile import selected
        assert selected(p) is False;return
    assert p.complete([],[]).text=='legacy'
    assert [path for path,_ in requests]==['/v1/chat/completions']


def test_compose_passes_explicit_profile_without_default_activation():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    for filename in ('compose.yaml','deploy/compose.app.yaml'):
        assert 'ICARUS_OLLAMA_8K_PROFILE=${ICARUS_OLLAMA_8K_PROFILE:-}' in (root/filename).read_text()


@pytest.mark.parametrize('stage',['prepare','warm','shorten'])
def test_lifecycle_never_loads_wrong_profile(monkeypatch,stage):
    from icarus_memory import ollama_memory as memory
    p,requests,show,_=setup(monkeypatch,parameters='num_ctx 8192' if stage=='shorten' else 'num_ctx 32768')
    monkeypatch.setattr(memory,'_VORGEWAERMT',{})
    monkeypatch.setattr(memory,'_prepare',lambda *args:None if stage=='shorten' else pytest.fail('unverified model preparation'))
    monkeypatch.setattr(memory,'_shorten_target_retention',lambda *args:pytest.fail('unverified retention'))
    if stage=='warm':assert memory.vorwaermen(p)=='fehler'
    elif stage=='prepare':
        with pytest.raises(ProviderError):
            with memory.managed_model(p):pytest.fail('wrong profile allowed into body')
    else:
        with memory.managed_model(p):show['parameters']='num_ctx 32768'
    assert not any(path in {'/api/chat','/api/generate'} for path,_ in requests)


def test_learning_direct_bypass_uses_identical_profile_flags_and_full_schema_guard(monkeypatch):
    from icarus_memory.procedure_model import draft
    p,requests,_,_=setup(monkeypatch)
    assert draft(p,[{'role':'user','content':'synthetic'}],{'type':'object'}).text=='{}'
    body=next(body for path,body in requests if path=='/api/chat')
    assert body['truncate'] is False and body['shift'] is False and body['format']=={'type':'object'}
    requests.clear()
    with pytest.raises(ProviderError):draft(p,[{'role':'user','content':'synthetic'}],{'description':'ä'*9000})
    assert requests==[]


def test_json_deadline_expiring_while_waiting_never_submits_source(monkeypatch):
    import time
    from contextlib import contextmanager
    from icarus_memory.providers import json_request_deadline
    p,requests,_,_=setup(monkeypatch)
    @contextmanager
    def expired_wait():
        with json_request_deadline(time.monotonic()-1):yield
    monkeypatch.setattr(p,'_ampel',expired_wait)
    with json_request_deadline(time.monotonic()+10),pytest.raises(ProviderError,match='deadline'):
        p.complete_json([{'role':'user','content':'synthetic'}])
    assert not any(path=='/api/chat' for path,_ in requests)


def test_json_transport_timeout_is_recomputed_after_metadata_and_wait(monkeypatch):
    import time
    from icarus_memory.providers import json_request_deadline
    p,requests,_,_=setup(monkeypatch);timeouts=[]
    original=p._client
    def client(timeout):timeouts.append(timeout);return original(timeout)
    monkeypatch.setattr(p,'_client',client)
    with json_request_deadline(time.monotonic()+3):p.complete_json([{'role':'user','content':'synthetic'}])
    assert len(timeouts)==1 and 0<timeouts[0]<=3


@pytest.mark.parametrize('change',['image','unknown_message_field','orphan_result','duplicate_argument','array_argument','contradictory_name'])
def test_unrepresentable_history_is_rejected_before_any_transport(monkeypatch,change):
    p,requests,_,_=setup(monkeypatch)
    messages=[{'role':'user','content':'synthetic'}]
    if change=='image':messages[0]['content']=[{'type':'image_url','image_url':{'url':'synthetic'}}]
    if change=='unknown_message_field':messages[0]['name']='speaker'
    if change=='orphan_result':messages.append({'role':'tool','tool_call_id':'missing','content':'synthetic'})
    if change in {'duplicate_argument','array_argument','contradictory_name'}:
        messages.extend([{'role':'assistant','content':'','tool_calls':[{'id':'one','type':'function','function':{
            'name':'arbitrary_existing_tool','arguments':'{"x":1,"x":2}' if change=='duplicate_argument' else
                '[]' if change=='array_argument' else '{"x":1}'}}]},
            {'role':'tool','tool_call_id':'one','content':'synthetic'}])
        if change=='contradictory_name':messages[-1]['tool_name']='other'
    with pytest.raises(ProviderError):p.complete(messages,[])
    assert requests==[]


def test_changed_weights_or_pause_after_metadata_never_accepts_response(monkeypatch):
    from icarus_memory.local_model_guard import VerifiedLocalProvider
    p,requests,_,tags=setup(monkeypatch)
    wrapped=VerifiedLocalProvider(p)
    assert wrapped.complete_json([{'role':'user','content':'first'}]).text=='{}'
    tags['models'][0]['digest']='b'*64
    with pytest.raises(ProviderError):wrapped.complete_json([{'role':'user','content':'second'}])
    assert sum(path=='/api/chat' for path,_ in requests)==1


def test_selected_native_context_overflow_is_error_without_v1_fallback(monkeypatch):
    p,requests,_,_=setup(monkeypatch,reply={'error':'input exceeds available context size'})
    with pytest.raises(ProviderError):p.complete([{'role':'user','content':'synthetic'}],[])
    assert not any(path=='/v1/chat/completions' for path,_ in requests)


def test_permission_revoked_during_additional_profile_metadata_prevents_source(monkeypatch):
    from icarus_memory.local_model_guard import VerifiedLocalProvider
    from icarus_memory import local_context_profile as context
    p,requests,_,_=setup(monkeypatch);allowed=[True]
    original=context.verify_local_model
    def verified_then_paused(*args,**kwargs):
        identity=original(*args,**kwargs);allowed[0]=False;return identity
    monkeypatch.setattr(context,'verify_local_model',verified_then_paused)
    with pytest.raises(ProviderError):
        VerifiedLocalProvider(p,permitted=lambda:allowed[0]).complete_json([{'role':'user','content':'SOURCE_SENTINEL'}])
    assert not any(path=='/api/chat' for path,_ in requests)


def test_selected_complete_cannot_silently_ignore_final_payload_hook(monkeypatch):
    p,requests,_,_=setup(monkeypatch)
    monkeypatch.setattr(p,'_request_payload',lambda payload:{**payload,'unsupported_final_option':'must_not_disappear'})
    monkeypatch.setattr(p,'_ampel',lambda:pytest.fail('unsupported final payload must fail before preparation'))
    with pytest.raises(ProviderError):p.complete([{'role':'user','content':'synthetic'}],[])
    assert requests==[]


def test_dangling_second_context_parameter_is_ambiguous(monkeypatch):
    p,requests,_,_=setup(monkeypatch,parameters='num_ctx 8192\nnum_ctx')
    with pytest.raises(ProviderError):p.complete_json([{'role':'user','content':'synthetic'}])
    assert not any(path=='/api/chat' for path,_ in requests)


def test_selected_payload_cannot_target_unverified_other_model(monkeypatch):
    p,requests,_,_=setup(monkeypatch)
    monkeypatch.setattr(p,'_request_payload',lambda payload:{**payload,'model':'remote:cloud'})
    monkeypatch.setattr(p,'_ampel',lambda:pytest.fail('payload model mismatch before preparation'))
    with pytest.raises(ProviderError):p.complete([{'role':'user','content':'synthetic'}],[])
    assert requests==[]


def test_selected_profile_rejects_unsupported_decision_path_before_source(monkeypatch):
    p,requests,_,_=setup(monkeypatch)
    monkeypatch.setattr(p,'_ampel',lambda:pytest.fail('decision must fail before preparation'))
    with pytest.raises(ProviderError,match='(?i)profil'):
        p.decide('synthetic',{'decision':{'type':'choice','instructions':'synthetic','criteria':{'yes':'synthetic'}}})
    assert requests==[]


def test_selected_profile_keeps_existing_ampel_and_managed_lifecycle(monkeypatch):
    from types import MethodType
    from icarus_memory import ollama_memory
    p,requests,_,_=setup(monkeypatch);events=[]
    monkeypatch.setattr(p,'_ampel',MethodType(OpenAICompatible._ampel,p))
    monkeypatch.setattr(ollama_memory,'_prepare',lambda *args:events.append('prepare'))
    monkeypatch.setattr(ollama_memory,'_shorten_target_retention',lambda *args:events.append('retain'))
    assert p.complete_json([{'role':'user','content':'synthetic'}]).text=='{}'
    assert events==['prepare','retain']
    assert sum(path=='/api/chat' for path,_ in requests)==1


@pytest.mark.parametrize('expires_at',['metadata','queue','prepare_ps','second_unload','retention_ps'])
def test_real_profile_lifecycle_never_prepares_after_json_deadline(monkeypatch,expires_at):
    from contextlib import contextmanager
    from types import MethodType
    from icarus_memory import providers,ollama_memory as memory,local_context_profile as context
    Client=httpx.Client
    p,requests,_,_=setup(monkeypatch);clock=[0.0];events=[];ps_calls=[0]
    monkeypatch.setattr(providers.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(p,'_ampel',MethodType(OpenAICompatible._ampel,p))
    original=context.verify_profile
    def metadata(provider):
        value=original(provider)
        if expires_at=='metadata':clock[0]=2.0
        return value
    monkeypatch.setattr(context,'verify_profile',metadata)
    if expires_at=='queue':
        @contextmanager
        def queue():clock[0]=2.0;yield
        monkeypatch.setattr('icarus_memory.hintergrund.AMPEL',type('Wait',(),{'aufruf':staticmethod(queue)})())
    def lifecycle(request):
        if request.url.path=='/api/ps':
            ps_calls[0]+=1
            if expires_at=='prepare_ps':clock[0]=2.0
            if expires_at=='retention_ps' and ps_calls[0]>1:clock[0]=2.0
            names=[ALIAS] if ps_calls[0]>1 else (
                ['kingfisher-other:one','kingfisher-other:two'] if expires_at=='second_unload' else
                ['kingfisher-other:one'] if expires_at=='prepare_ps' else [])
            return httpx.Response(200,json={'models':[{'name':name} for name in names]})
        events.append((clock[0],json.loads(request.content)))
        if expires_at=='second_unload':clock[0]=2.0
        return httpx.Response(200,json={})
    monkeypatch.setattr(memory,'_ollama_client',lambda **opts:Client(transport=httpx.MockTransport(lifecycle),**opts))
    with providers.json_request_deadline(1.0):
        if expires_at=='retention_ps':assert p.complete_json([{'role':'user','content':'synthetic'}]).text=='{}'
        else:
            with pytest.raises(ProviderError):p.complete_json([{'role':'user','content':'synthetic'}])
    assert all(at<1.0 for at,_ in events)
    assert len(events)==(1 if expires_at=='second_unload' else 0)
    assert sum(path=='/api/chat' for path,_ in requests)==(1 if expires_at=='retention_ps' else 0)
