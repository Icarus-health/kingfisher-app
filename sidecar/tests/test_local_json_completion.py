from types import SimpleNamespace

import pytest

from icarus_memory.providers import OpenAICompatible, ProviderError
from icarus_memory.routing_provider import RoutedProvider
from icarus_memory.model_routing import Candidate


class Response:
    def raise_for_status(self): pass
    def json(self):
        return {"choices": [{"message": {"content": '{"category":"important"}'}}]}


def test_openai_local_json_uses_30_second_timeout_256_tokens_and_json_mode(monkeypatch):
    calls = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): calls.append((args, kwargs)); return Response()
    monkeypatch.setattr("icarus_memory.providers._http", lambda timeout=120.0: (calls.append(("timeout", timeout)) or Client()))
    provider = OpenAICompatible("llama", base_url="http://127.0.0.1:11434/v1")
    reply = provider.complete_json([{"role": "user", "content": "mail"}])
    assert reply.text == '{"category":"important"}'
    assert ("timeout", 30.0) in calls
    payload = next(item[1]["json"] for item in calls if item[0] != "timeout")
    assert payload["max_tokens"] == 256
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["reasoning_effort"] == "none"
    assert "tools" not in payload


def test_routed_json_never_uses_cloud_fallback():
    class Local:
        model, is_local, name = "local", True, "local"
        def complete(self, *args): raise AssertionError("normal path")
        def complete_json(self, messages): return SimpleNamespace(text='{"ok":true}', model=self.model)
    class Cloud:
        model, is_local, name = "cloud", False, "cloud"
        def complete(self, *args): raise AssertionError("normal cloud path")
        def complete_json(self, messages): raise AssertionError("cloud fallback")
    candidate = lambda id, local: Candidate(id, id, local, frozenset({"text"}), 1, 1, 1)
    routed = RoutedProvider(Local(), [(candidate("local", True), Local()), (candidate("cloud", False), Cloud())])
    assert routed.complete_json([]).text == '{"ok":true}'


def test_routed_json_requires_provider_capability():
    class Local:
        model, is_local, name = "local", True, "local"
        def complete(self, *args): pass
    provider = Local()
    candidate = Candidate("local", "local", True, frozenset({"text"}), 1, 1, 1)
    with pytest.raises(ProviderError):
        RoutedProvider(provider, [(candidate, provider)]).complete_json([])


def test_openai_json_rejects_remote_provider(monkeypatch):
    monkeypatch.setattr("icarus_memory.providers._http", lambda timeout=120.0: pytest.fail("remote must not connect"))
    provider = OpenAICompatible("remote", base_url="https://api.example.invalid/v1")
    with pytest.raises(ProviderError):
        provider.complete_json([])


def test_routed_json_rejects_remote_wrapper_even_when_local_only_false():
    provider = SimpleNamespace(model="cloud", is_local=False, name="cloud", complete=lambda *args: None,
                               complete_json=lambda messages: pytest.fail("cloud called"))
    candidate = Candidate("cloud", "cloud", False, frozenset({"text"}), 1, 1, 1)
    routed = RoutedProvider(provider, [(candidate, provider)], local_only=False)
    with pytest.raises(ProviderError):
        routed.complete_json([])


def test_routed_json_does_not_retry_network_failure_or_use_cloud():
    calls = []
    class Local:
        model, is_local, name = "local", True, "local"
        def complete(self, *args): pass
        def complete_json(self, messages):
            calls.append("local")
            raise ProviderError("offline")
    class Cloud:
        model, is_local, name = "cloud", False, "cloud"
        def complete(self, *args): pass
        def complete_json(self, messages): calls.append("cloud"); return SimpleNamespace(text="{}")
    candidates = [(Candidate("local", "local", True, frozenset({"text"}), 1, 1, 1), Local()),
                  (Candidate("cloud", "cloud", False, frozenset({"text"}), 2, 1, 1), Cloud())]
    with pytest.raises(ProviderError):
        RoutedProvider(candidates[0][1], candidates).complete_json([])
    assert calls == ["local"]


def test_json_completion_rejects_tool_calls(monkeypatch):
    class ToolResponse(Response):
        def json(self):
            return {"choices": [{"message": {"content": "{}", "tool_calls": [{"id": "x"}]}}]}
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return ToolResponse()
    monkeypatch.setattr("icarus_memory.providers._http", lambda timeout=120.0: Client())
    provider = OpenAICompatible("llama", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError):
        provider.complete_json([])


def test_person_overview_json_can_request_bounded_larger_reply(monkeypatch):
    calls = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): calls.append(kwargs['json']); return Response()
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: (calls.append(timeout) or Client()))
    provider = OpenAICompatible('local', base_url='http://127.0.0.1:11434/v1')
    provider.complete_json([], max_tokens=1100)
    assert 60.0 in calls
    assert calls[-1]['max_tokens'] == 1100
    with pytest.raises(ProviderError):
        provider.complete_json([], max_tokens=50000)


def test_local_overview_uses_schema_constrained_json(monkeypatch):
    calls = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): calls.append(kwargs['json']); return Response()
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: Client())
    provider = OpenAICompatible('local', base_url='http://127.0.0.1:11434/v1')
    schema = {'type':'object','properties':{'points':{'type':'array'}}}
    provider.complete_json([], max_tokens=1100, schema=schema)
    assert calls[0]['response_format']['json_schema']['schema'] == schema
    assert calls[0]['temperature'] == 0


def test_valid_json_cut_off_by_token_budget_is_not_complete(monkeypatch):
    class LimitedResponse(Response):
        def json(self):
            return {'choices': [{'finish_reason': 'length', 'message': {'content': '{"items":[]}'}}]}
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return LimitedResponse()
    monkeypatch.setattr('icarus_memory.providers._http', lambda timeout=120: Client())
    provider = OpenAICompatible('local', base_url='http://127.0.0.1:11434/v1')
    with pytest.raises(ProviderError):
        provider.complete_json([])


def test_routed_json_preserves_explicit_output_budget():
    calls = []
    class Local:
        model, is_local, name = 'local', True, 'local'
        def complete(self, *args): raise AssertionError('kein freier Modellaufruf')
        def complete_json(self, messages, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text='{"items":[]}', model=self.model)
    provider = Local()
    candidate = Candidate('local', 'local', True, frozenset({'text'}), 1, 1, 1)
    routed = RoutedProvider(provider, [(candidate, provider)])
    schema = {'type': 'object', 'additionalProperties': False}
    routed.complete_json([], max_tokens=1200, schema=schema)
    assert calls == [{'max_tokens': 1200, 'schema': schema}]
