"""Nur synthetische Transportproben; keine Verbindung zum echten Anbieter."""
import json

import httpx
import pytest

from icarus_memory.cloud_import_provider import AnthropicImportProvider, credential_status
from icarus_memory.providers import ProviderError


def test_anthropic_send_uses_fixed_endpoint_bounded_output_and_no_redirect_or_retry(monkeypatch):
    calls = []
    events = []
    def handler(request):
        calls.append(request)
        assert events == ['counted']
        payload = json.loads(request.content)
        assert payload['model'] == 'claude-synthetic'
        assert payload['max_tokens'] == 300
        assert payload['tools'][0]['input_schema'] == {'type': 'object'}
        return httpx.Response(200, json={'stop_reason': 'tool_use', 'content': [
            {'type': 'tool_use', 'name': 'memory_result', 'input': {'items': []}}]})
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(transport=transport, follow_redirects=False, trust_env=False))
    provider = AnthropicImportProvider('claude-synthetic', 'synthetic-secret', 'revision-one', lambda: 'revision-one')
    result = provider.complete_json_guarded([{'role':'user', 'content':'Synthetic source'}], max_tokens=300,
                                            schema={'type':'object'}, before_send=lambda: events.append('counted'), still_permitted=lambda: True)
    assert json.loads(result.text) == {'items': []}
    assert len(calls) == 1
    assert str(calls[0].url) == 'https://api.anthropic.com/v1/messages'


def test_anthropic_paused_during_client_preparation_never_sends_or_counts(monkeypatch):
    permitted = [True]
    def prepare(self):
        permitted[0] = False
        return httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail('No late send')))
    monkeypatch.setattr(AnthropicImportProvider, '_client', prepare)
    provider = AnthropicImportProvider('claude-synthetic', 'synthetic-secret', 'revision-one', lambda: 'revision-one')
    with pytest.raises(ProviderError):
        provider.complete_json_guarded([{'role':'user', 'content':'Synthetic'}], max_tokens=100,
                                      schema={'type':'object'}, before_send=lambda: pytest.fail('No count'),
                                      still_permitted=lambda: permitted[0])


@pytest.mark.parametrize('status', [302, 401, 429, 500])
def test_anthropic_http_error_does_not_echo_key_response_or_retry(monkeypatch, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={'location':'https://other.example'}, text='private provider error synthetic-secret')
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False))
    provider = AnthropicImportProvider('claude-synthetic', 'synthetic-secret', 'revision-one', lambda: 'revision-one')
    with pytest.raises(ProviderError) as error:
        provider.complete_json_guarded([], max_tokens=100, schema={'type':'object'}, before_send=lambda:None, still_permitted=lambda:True)
    assert 'synthetic-secret' not in str(error.value)
    assert 'private provider' not in str(error.value)
    assert len(calls) == 1


def test_credentials_require_encrypted_preparation_and_revision_changes_with_environment():
    class Keys:
        available = True
        values = {'ICARUS_PREPARED_ANTHROPIC_API_KEY': 'synthetic-secret', 'CLOUD_IMPORT_ANTHROPIC_REVISION': 'synthetic-salt'}
        def get(self, name):
            return self.values.get(name)
    class Settings:
        cloud_models = {'anthropic': 'claude-synthetic'}
    keys = Keys()
    status = credential_status(keys, Settings(), {'ICARUS_PREPARED_ANTHROPIC_API_KEY':'synthetic-secret'})
    assert status['available']
    assert 'synthetic-secret' not in json.dumps(status)
    changed = credential_status(keys, Settings(), {'ICARUS_PREPARED_ANTHROPIC_API_KEY':'synthetic-different'})
    assert not changed['available']
    keys.values.pop('CLOUD_IMPORT_ANTHROPIC_REVISION')
    assert not credential_status(keys, Settings(), {'ICARUS_PREPARED_ANTHROPIC_API_KEY':'synthetic-secret'})['available']


@pytest.mark.parametrize('response', [[], None, {'content':None}, {'content':[],'stop_reason':'max_tokens'},
    {'stop_reason':'tool_use','content':[{'type':'tool_use','name':'other','input':{}}]}])
def test_anthropic_malformed_or_truncated_result_is_rejected_without_partial_commit(monkeypatch, response):
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200,json=response))))
    provider = AnthropicImportProvider('claude-synthetic','synthetic-secret','revision-one',lambda:'revision-one')
    with pytest.raises(ProviderError):
        provider.complete_json_guarded([],max_tokens=100,schema={'type':'object'},before_send=lambda:None,still_permitted=lambda:True)


def test_anthropic_rechecks_permission_and_revision_after_request_counting(monkeypatch):
    permitted = [True]
    revision = ['revision-one']
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(transport=httpx.MockTransport(
        lambda _: pytest.fail('No send after counting callback revokes permission'))))
    provider = AnthropicImportProvider('claude-synthetic','synthetic-secret','revision-one',lambda:revision[0])
    def revoke():
        permitted[0] = False
        revision[0] = 'revision-two'
    with pytest.raises(ProviderError):
        provider.complete_json_guarded([],max_tokens=100,schema={'type':'object'},before_send=revoke,still_permitted=lambda:permitted[0])


def test_sonnet_55_uses_bounded_json_output_instead_of_unsupported_forced_tool(monkeypatch):
    calls, events = [], []
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
              'properties': {'items': {'type': 'object', 'additionalProperties': False,
                                      'required': ['B1'], 'properties': {'B1': {'type': 'string'}}}}}

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert events == ['counted']
        assert payload['model'] == 'claude-sonnet-5-5'
        assert payload['max_tokens'] == 300
        assert payload['output_config'] == {'effort': 'medium',
                                            'format': {'type': 'json_schema', 'schema': schema}}
        assert payload['thinking'] == {'type': 'between_tools'}
        assert 'tools' not in payload and 'tool_choice' not in payload
        assert payload['system'] == 'Synthetic instructions'
        assert payload['messages'] == [{'role': 'user', 'content': 'Synthetic original'}]
        return httpx.Response(200, json={'stop_reason': 'end_turn',
            'content': [{'type': 'text', 'text': '{"items":{"B1":"fact"}}'}]})

    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False, trust_env=False))
    provider = AnthropicImportProvider('claude-sonnet-5-5', 'synthetic-secret', 'one', lambda: 'one')
    result = provider.complete_json_guarded([
        {'role': 'system', 'content': 'Synthetic instructions'},
        {'role': 'user', 'content': 'Synthetic original'}], max_tokens=300, schema=schema,
        before_send=lambda: events.append('counted'), still_permitted=lambda: True)
    assert json.loads(result.text) == {'items': {'B1': 'fact'}}
    assert result.model == 'claude-sonnet-5-5'
    assert len(calls) == 1
    assert str(calls[0].url) == 'https://api.anthropic.com/v1/messages'


@pytest.mark.parametrize('response', [
    {'stop_reason': 'max_tokens', 'content': [{'type': 'text', 'text': '{"items":{}}'}]},
    {'stop_reason': 'refusal', 'content': [{'type': 'text', 'text': '{"items":{}}'}]},
    {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'not JSON'}]},
    {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '[]'}]},
    {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': None}]},
    {'stop_reason': 'end_turn', 'content': [
        {'type': 'text', 'text': '{}'}, {'type': 'text', 'text': '{}'}]},
    {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{}'},
        {'type': 'tool_use', 'name': 'memory_result', 'input': {}}]},
])
def test_sonnet_55_rejects_incomplete_or_ambiguous_json_without_retry(monkeypatch, response):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response)
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(handler)))
    provider = AnthropicImportProvider('claude-sonnet-5-5', 'synthetic-secret', 'one', lambda: 'one')
    with pytest.raises(ProviderError):
        provider.complete_json_guarded([], max_tokens=100, schema={'type': 'object'},
                                       before_send=lambda: None, still_permitted=lambda: True)
    assert len(calls) == 1


def test_sonnet_55_preserves_duplicate_keys_for_existing_source_validator(monkeypatch):
    # Parsing and reserializing here would silently discard the duplicate B1.
    text = '{"items":{"B1":"fact","B1":"request"}}'
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
            'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': text}]}))))
    provider = AnthropicImportProvider('claude-sonnet-5-5', 'synthetic-secret', 'one', lambda: 'one')
    result = provider.complete_json_guarded([], max_tokens=100, schema={'type': 'object'},
                                           before_send=lambda: None, still_permitted=lambda: True)
    assert result.text == '{"items":{"B1":"fact","B1":"request"}}'


def test_sonnet_55_revocation_during_request_does_not_return_a_result(monkeypatch):
    permitted = [True]
    def handler(_):
        permitted[0] = False
        return httpx.Response(200, json={'stop_reason': 'end_turn',
            'content': [{'type': 'text', 'text': '{"items":{}}'}]})
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(handler)))
    provider = AnthropicImportProvider('claude-sonnet-5-5', 'synthetic-secret', 'one', lambda: 'one')
    with pytest.raises(ProviderError):
        provider.complete_json_guarded([], max_tokens=100, schema={'type': 'object'},
                                       before_send=lambda: None, still_permitted=lambda: permitted[0])
