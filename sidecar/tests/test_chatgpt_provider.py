import json
import httpx
import pytest

from icarus_memory.chatgpt_provider import ChatGPTProvider
from icarus_memory.providers import ProviderError


class OAuth:
    active = True
    def available(self, grant_id): return self.active and grant_id == 'grant'
    def access_token(self, grant_id):
        assert self.available(grant_id)
        return 'synthetic-access'


def provider(events, *, status=200):
    calls, oauth = [], OAuth()
    def handle(request):
        calls.append(request)
        return httpx.Response(status, text='\n\n'.join('data: '+json.dumps(e) for e in events)+'\n\n',
                              headers={'Content-Type':'text/event-stream'})
    result = ChatGPTProvider(oauth, 'chosen-model', 'grant',
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handle)))
    return result, calls, oauth


def test_json_uses_public_responses_stream_and_developer_instruction():
    p, calls, _ = provider([{'type':'response.output_text.delta','delta':'{"items":[]}'},
        {'type':'response.completed','response':{'status':'completed','usage':{'input_tokens':10,'output_tokens':5}}}])
    reply = p.complete_json([{'role':'system','content':'JSON only'}, {'role':'user','content':'synthetic mail'}],
                            max_tokens=1200, schema={'type':'object','properties':{}})
    assert reply.text == '{"items":[]}' and reply.model == 'chosen-model'
    payload = json.loads(calls[0].content)
    assert str(calls[0].url) == 'https://api.openai.com/v1/responses'
    assert payload['store'] is False and payload['stream'] is True
    assert payload['input'][0]['role'] == 'developer'
    assert not {'max_output_tokens','temperature','tools','background'} & payload.keys()
    assert p.usage['input_tokens'] == 10


@pytest.mark.parametrize('events', [[], [{'type':'response.output_text.delta','delta':'{}'}],
    [{'type':'response.failed','response':{'error':{'message':'private server body'}}}],
    [{'type':'response.completed','response':{'status':'incomplete'}}]])
def test_missing_completed_or_failure_is_not_a_result(events):
    p, _, _ = provider(events)
    with pytest.raises(ProviderError) as failure: p.complete_json([], max_tokens=10, schema={})
    assert 'private server body' not in str(failure.value)


@pytest.mark.parametrize('status', [401,403,429,500])
def test_http_failure_never_falls_back_or_exposes_token(status):
    p, calls, _ = provider([], status=status)
    with pytest.raises(ProviderError) as failure: p.complete_json([], max_tokens=10, schema={})
    assert len(calls) == 1 and 'synthetic-access' not in str(failure.value)


def test_revoked_session_is_checked_before_request_and_before_result():
    p, calls, oauth = provider([{'type':'response.completed','response':{'status':'completed'}}])
    oauth.active = False
    with pytest.raises(ProviderError): p.complete_json([], max_tokens=10, schema={})
    assert not calls


def test_tool_calls_and_oversize_output_are_rejected():
    for event in ({'type':'response.output_item.added','item':{'type':'function_call'}},
                  {'type':'response.output_text.delta','delta':'x'*17000}):
        p, _, _ = provider([event, {'type':'response.completed','response':{'status':'completed'}}])
        with pytest.raises(ProviderError): p.complete_json([], max_tokens=10, schema={})


def test_tool_in_completed_envelope_is_rejected():
    p, _, _ = provider([{'type':'response.completed','response':{'status':'completed','output':[{'type':'function_call'}]}}])
    with pytest.raises(ProviderError): p.complete_json([],max_tokens=10,schema={})


def test_unterminated_stream_is_bounded_before_reading_entire_body():
    class Stream(httpx.SyncByteStream):
        reads=0
        def __iter__(self):
            for _ in range(1000):
                self.reads+=1
                yield b'x'*4096
    stream=Stream()
    p=ChatGPTProvider(OAuth(),'chosen-model','grant',client_factory=lambda:httpx.Client(
        transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=stream))))
    with pytest.raises(ProviderError): p.complete_json([],max_tokens=10,schema={})
    assert stream.reads<250


def test_revocation_while_reading_stream_rejects_result():
    oauth=OAuth()
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'data: {"type":"response.output_text.delta","delta":"{}"}\n\n'+b' '*4096+b'\n'
            oauth.active=False
            yield b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
    p=ChatGPTProvider(oauth,'chosen-model','grant',client_factory=lambda:httpx.Client(
        transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Stream()))))
    with pytest.raises(ProviderError): p.complete_json([],max_tokens=10,schema={})


def test_job_pause_during_token_preparation_prevents_source_transmission():
    p,calls,oauth=provider([])
    permission={'allowed':True}
    def delayed_token(_grant):
        permission['allowed']=False
        return 'synthetic-access'
    oauth.access_token=delayed_token
    def before_send():
        if not permission['allowed']: raise ProviderError('Job paused')
    with pytest.raises(ProviderError):
        p.complete_json_guarded([],max_tokens=10,schema={},before_send=before_send,
                                still_permitted=lambda:permission['allowed'])
    assert not calls
