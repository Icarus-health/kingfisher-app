"""Large local JSON prompts get bounded transport time without a larger output budget."""
from contextlib import contextmanager
import json
import time

import httpx
import pytest

from icarus_memory.providers import OpenAICompatible, ProviderError, json_request_deadline


def _local_provider(monkeypatch, requests, timeouts):
    provider = OpenAICompatible("synthetic-local", base_url="http://127.0.0.1:11434/v1")

    @contextmanager
    def no_model_wait():
        yield

    def client(timeout):
        timeouts.append(timeout)

        def respond(request):
            requests.append(request.read())
            return httpx.Response(200, json={"choices": [{
                "finish_reason": "stop", "message": {"content": "{}"},
            }]})

        return httpx.Client(transport=httpx.MockTransport(respond), timeout=timeout)

    monkeypatch.setattr(provider, "_ampel", no_model_wait)
    monkeypatch.setattr(provider, "_client", client)
    return provider


def test_large_input_gets_existing_long_transport_class_without_more_output_tokens(monkeypatch):
    requests, timeouts = [], []
    provider = _local_provider(monkeypatch, requests, timeouts)
    content = "candidate evidence " * 1900  # 36,100 chars, close to the measured prompt.
    messages = [{"role": "user", "content": content}]

    reply = provider.complete_json(messages, max_tokens=256)

    assert reply.text == "{}"
    assert timeouts == [60.0]
    payload = json.loads(requests[0])
    assert payload["messages"] == messages
    assert payload["max_tokens"] == 256


def test_small_input_keeps_the_short_transport_class(monkeypatch):
    requests, timeouts = [], []
    provider = _local_provider(monkeypatch, requests, timeouts)

    provider.complete_json([{"role": "user", "content": "short prompt"}], max_tokens=256)

    assert timeouts == [30.0]
    assert json.loads(requests[0])["max_tokens"] == 256


def test_large_input_transport_stays_inside_the_question_deadline(monkeypatch):
    requests, timeouts = [], []
    provider = _local_provider(monkeypatch, requests, timeouts)
    messages = [{"role": "user", "content": "candidate " * 2000}]

    with json_request_deadline(time.monotonic() + 6.0):
        provider.complete_json(messages, max_tokens=256)

    assert len(timeouts) == 1
    assert 0 < timeouts[0] <= 6.0
    assert json.loads(requests[0])["max_tokens"] == 256


def test_expired_question_does_not_enter_model_gate_or_start_transport(monkeypatch):
    provider = OpenAICompatible("synthetic-local", base_url="http://127.0.0.1:11434/v1")
    monkeypatch.setattr(provider, "_ampel", lambda: pytest.fail("expired request entered model gate"))
    monkeypatch.setattr(provider, "_client", lambda _timeout: pytest.fail("expired request started transport"))

    with json_request_deadline(time.monotonic() - 1), pytest.raises(ProviderError, match="deadline"):
        provider.complete_json([{"role": "user", "content": "large " * 3000}], max_tokens=256)
