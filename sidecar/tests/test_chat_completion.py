"""Provider must distinguish a visible reply from reasoning-only/empty output."""
import json

import httpx
import pytest
from icarus_memory.providers import OpenAICompatible, ProviderError


def provider(monkeypatch, message):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'choices': [{'message': message, 'finish_reason': 'stop'}]}))
    monkeypatch.setattr('icarus_memory.providers._http',
                        lambda timeout=120: httpx.Client(transport=transport))
    return OpenAICompatible('synthetic', base_url='http://127.0.0.1:11434/v1')


@pytest.mark.parametrize('message', [{}, {'content': ''}, {'content': '  \n'},
                                     {'content': None, 'reasoning_content': 'private reasoning'},
                                     {'content': None, 'reasoning': 'private reasoning'}])
def test_empty_chat_completion_is_a_provider_error(monkeypatch, message):
    with pytest.raises(ProviderError, match='keine sichtbare Antwort'):
        provider(monkeypatch, message).complete([], [])


def test_tool_only_reply_remains_valid(monkeypatch):
    result = provider(monkeypatch, {'tool_calls': [{'id': 't1', 'function': {
        'name': 'test', 'arguments': '{}'}}]}).complete([], [])
    assert result.tool_calls[0].name == 'test'


def test_visible_text_remains_unchanged(monkeypatch):
    assert provider(monkeypatch, {'content': 'Hallo.'}).complete([], []).text == 'Hallo.'


def test_local_ollama_chat_bounds_generation_and_disables_reasoning(monkeypatch):
    calls = []
    transport = httpx.MockTransport(lambda request: (calls.append(request) or httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {
            'content': 'OK', 'reasoning': 'must remain private',
        }}],
    })))
    monkeypatch.setattr(
        'icarus_memory.providers._http',
        lambda timeout=120: (calls.append(('timeout', timeout)) or httpx.Client(transport=transport)),
    )
    result = OpenAICompatible('qwen3.5:4b', base_url='http://127.0.0.1:11434/v1').complete(
        [{'role': 'user', 'content': 'synthetic'}], [])

    assert result.text == 'OK'
    assert 'must remain private' not in result.text
    assert ('timeout', 60.0) in calls
    payload = json.loads(calls[1].content)
    assert payload['max_tokens'] == 1024
    assert payload['reasoning_effort'] == 'none'


def test_local_ollama_chat_budget_preserves_tool_calls(monkeypatch):
    calls = []
    transport = httpx.MockTransport(lambda request: (calls.append(request) or httpx.Response(200, json={
        'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None, 'tool_calls': [{
            'id': 'call-1', 'function': {'name': 'lookup', 'arguments': '{}'},
        }]}}],
    })))
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: httpx.Client(transport=transport))

    result = OpenAICompatible('qwen3.5:4b', base_url='http://127.0.0.1:11434/v1').complete(
        [{'role': 'user', 'content': 'synthetic'}], [{'name': 'lookup', 'parameters': {'type': 'object'}}])

    assert result.tool_calls[0].name == 'lookup'
    payload = json.loads(calls[0].content)
    assert payload['max_tokens'] == 1024
    assert payload['reasoning_effort'] == 'none'
    assert payload['tools'][0]['function']['name'] == 'lookup'


def test_remote_openai_compatible_chat_keeps_existing_request_shape(monkeypatch):
    calls = []
    transport = httpx.MockTransport(lambda request: (calls.append(request) or httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {'content': 'Hallo.'}}],
    })))
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: httpx.Client(transport=transport))

    result = OpenAICompatible('remote', base_url='https://api.example.invalid:11434/v1').complete(
        [{'role': 'user', 'content': 'synthetic'}], [])

    assert result.text == 'Hallo.'
    payload = json.loads(calls[0].content)
    assert 'max_tokens' not in payload
    assert 'reasoning_effort' not in payload


def test_truncated_remote_tool_arguments_are_never_returned_as_tool_calls(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'choices': [{'finish_reason': 'length', 'message': {'content': None, 'tool_calls': [{
            'id': 'call-1', 'function': {'name': 'lookup', 'arguments': '{"query":"partial'},
        }]}}],
    }))
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: httpx.Client(transport=transport))

    with pytest.raises(ProviderError, match='Antwort abgeschnitten'):
        OpenAICompatible('remote', base_url='https://api.example.invalid/v1').complete(
            [{'role': 'user', 'content': 'synthetic'}], [{'name': 'lookup', 'parameters': {'type': 'object'}}])


def test_local_chat_does_not_return_a_token_truncated_answer(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'choices': [{'finish_reason': 'length', 'message': {'content': 'Partial answer'}}],
    }))
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: httpx.Client(transport=transport))

    with pytest.raises(ProviderError, match='Antwort abgeschnitten'):
        OpenAICompatible('local', base_url='http://127.0.0.1:11434/v1').complete(
            [{'role': 'user', 'content': 'synthetic'}], [])
