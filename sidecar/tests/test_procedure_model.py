"""Kleine Lernaufträge reservieren nicht den großen Gesprächskontext."""
from contextlib import nullcontext
import json
import httpx
import pytest
from icarus_memory.providers import OpenAICompatible, ProviderError
from icarus_memory.local_model_guard import LocalModelIdentity
from icarus_memory.procedure_model import draft


def test_native_learning_bounds_context_tokens_and_does_not_change_provider(monkeypatch):
    provider = OpenAICompatible('synthetic:9b', base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model', lambda p: LocalModelIdentity('synthetic:9b','a'*64))
    monkeypatch.setattr(provider, '_ampel', nullcontext)
    seen=[]
    def handle(request):
        seen.append((str(request.url),json.loads(request.content)))
        return httpx.Response(200,json={'model':'synthetic:9b','done':True,'done_reason':'stop',
                                       'message':{'content':'{"example":true}'}})
    monkeypatch.setattr(provider, '_client', lambda timeout:httpx.Client(transport=httpx.MockTransport(handle)))
    assert draft(provider,[{'role':'user','content':'Ein künstlicher Ablauf.'}],{'type':'object'}).text == '{"example":true}'
    url,body=seen[0]
    assert url == 'http://127.0.0.1:11434/api/chat'
    assert body['options']['num_ctx'] == 8192 and body['options']['num_predict'] == 1200
    assert body['think'] is False and body['stream'] is False
    assert 'tools' not in body
    assert provider.model == 'synthetic:9b' and provider.base_url.endswith('/v1')


def test_unverified_model_receives_no_learning_text(monkeypatch):
    provider=OpenAICompatible('remote:cloud',base_url='http://127.0.0.1:11434/v1')
    def reject(_):raise ProviderError('Not local')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',reject)
    monkeypatch.setattr(provider,'_client',lambda _:pytest.fail('No source submission'))
    with pytest.raises(ProviderError):draft(provider,[{'role':'user','content':'PRIVATE'}],{})


@pytest.mark.parametrize('change',[{'done':False},{'done_reason':'length'},{'message':{'content':'{}','tool_calls':[{}]}}])
def test_incomplete_native_learning_is_not_accepted(monkeypatch,change):
    provider=OpenAICompatible('synthetic:9b',base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',lambda p:LocalModelIdentity('synthetic:9b','a'*64))
    monkeypatch.setattr(provider,'_ampel',nullcontext)
    data={'done':True,'done_reason':'stop','message':{'content':'{}'},**change}
    monkeypatch.setattr(provider,'_client',lambda _:httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))))
    with pytest.raises(ProviderError):draft(provider,[{'role':'user','content':'Probe'}],{})
