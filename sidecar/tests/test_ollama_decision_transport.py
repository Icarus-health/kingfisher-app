from __future__ import annotations

import json
import math

import httpx
import pytest

from icarus_memory.providers import OpenAICompatible, ProviderError


def questions():
    return {
        "route": {
            "type": "choice",
            "instructions": "Choose the best route.",
            "criteria": {"fast": "Lowest latency", "safe": "Most cautious"},
        }
    }


def test_decide_posts_bounded_choice_payload_to_ollama(monkeypatch):
    seen = {}
    real_client = httpx.Client

    def _capture_client(*args, **kwargs):
        seen["client_options"] = kwargs
        transport = httpx.MockTransport(lambda request: _reply(request, seen))
        return real_client(transport=transport, **kwargs)

    def _reply(request, capture):
        capture["url"] = str(request.url)
        capture["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "qwen", "answers": {"route": {"choice": "safe"}}, "usage": {}})

    monkeypatch.setattr(httpx, "Client", _capture_client)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    provider._verified_local_transport = False

    result = provider.decide({"text": "private state"}, questions(), timeout=4.0)

    assert result["answers"]["route"]["choice"] == "safe"
    assert seen["url"] == "http://127.0.0.1:11434/v1/systemone"
    assert seen["payload"] == {
        "model": "qwen",
        "state": {"text": "private state"},
        "questions": questions(),
    }
    assert seen["client_options"]["trust_env"] is False
    assert seen["client_options"]["follow_redirects"] is False
    assert seen["client_options"]["timeout"] == 4.0


def test_decide_builds_versioned_path_from_base_url_root(monkeypatch):
    seen = {}
    real_client = httpx.Client

    def capture(**kwargs):
        return real_client(
            transport=httpx.MockTransport(lambda request: (
                seen.setdefault("url", str(request.url))
                and httpx.Response(200, json={"answers": {}})
            )),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "Client", capture)
    OpenAICompatible("qwen", base_url="http://localhost:11434").decide("state", questions(), timeout=2)
    assert seen["url"] == "http://localhost:11434/v1/systemone"


def test_decide_rejects_remote_and_non_ollama_endpoints(monkeypatch):
    def forbidden(**_kwargs):
        raise AssertionError("remote transport must not be opened")

    monkeypatch.setattr(httpx, "Client", forbidden)
    for url in (
        "https://api.example/v1",
        "http://192.168.1.50:11434/v1",
        "http://127.0.0.1:1234/v1",
    ):
        provider = OpenAICompatible("qwen", base_url=url)
        with pytest.raises(ProviderError):
            provider.decide("state", questions())


def test_decide_revalidates_mutated_endpoint_and_rejects_unsupported_paths(monkeypatch):
    def forbidden(**_kwargs):
        raise AssertionError("invalid endpoint must not be opened")

    monkeypatch.setattr(httpx, "Client", forbidden)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    provider._base = "https://api.example/v1"
    with pytest.raises(ProviderError):
        provider.decide("state", questions())

    for path in ("/v2", "/proxy/v1"):
        provider = OpenAICompatible("qwen", base_url=f"http://127.0.0.1:11434{path}")
        with pytest.raises(ProviderError):
            provider.decide("state", questions())


@pytest.mark.parametrize("timeout", [0, -1, 30.01, math.inf, math.nan, 10**1000])
def test_decide_rejects_unbounded_or_invalid_timeouts_before_transport(monkeypatch, timeout):
    def forbidden(**_kwargs):
        raise AssertionError("invalid timeout must not open a transport")

    monkeypatch.setattr(httpx, "Client", forbidden)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError):
        provider.decide("state", questions(), timeout=timeout)


def test_decide_rejects_empty_questions_and_nonfinite_input(monkeypatch):
    def forbidden(**_kwargs):
        raise AssertionError("invalid input must not open a transport")

    monkeypatch.setattr(httpx, "Client", forbidden)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError):
        provider.decide("state", {})
    with pytest.raises(ProviderError):
        provider.decide({"value": float("nan")}, questions())


def test_decide_rechecks_current_endpoint_after_locality_changes(monkeypatch):
    real_client = httpx.Client
    seen = []

    def capture(**kwargs):
        def respond(request):
            seen.append(str(request.url))
            return httpx.Response(200, json={"answers": {"route": {"choice": "safe"}}})

        return real_client(
            transport=httpx.MockTransport(respond),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "Client", capture)
    provider = OpenAICompatible("qwen", base_url="https://api.example/v1")
    assert provider.is_local is False
    provider._base = "http://127.0.0.1:11434/v1"
    provider.decide("state", questions())
    assert seen == ["http://127.0.0.1:11434/v1/systemone"]


def test_decide_rejects_oversized_input_before_transport(monkeypatch):
    def forbidden(**_kwargs):
        raise AssertionError("oversized input must not be sent")

    monkeypatch.setattr(httpx, "Client", forbidden)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError, match="64 KiB"):
        provider.decide({"text": "x" * (64 * 1024)}, questions())


def test_decide_rejects_malformed_input_and_response(monkeypatch):
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError):
        provider.decide("state", {"bad": {"type": "freeform"}})
    with pytest.raises(ProviderError):
        provider.decide("state", {f"q{i}": questions()["route"] for i in range(17)})

    real_client = httpx.Client

    def capture(**kwargs):
        return real_client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"answers": []})),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "Client", capture)
    with pytest.raises(ProviderError):
        provider.decide("state", questions())


def test_decide_404_fails_without_chat_completions_fallback(monkeypatch):
    paths = []
    real_client = httpx.Client

    def capture(**kwargs):
        def respond(request):
            paths.append(request.url.path)
            return httpx.Response(404, json={"error": "unknown endpoint"})

        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(httpx, "Client", capture)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError):
        provider.decide("state", questions())
    assert paths == ["/v1/systemone"]


def test_decide_bounds_streamed_response_body(monkeypatch):
    real_client = httpx.Client

    def capture(**kwargs):
        return real_client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b" " * (64 * 1024 + 1))),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "Client", capture)
    provider = OpenAICompatible("qwen", base_url="http://127.0.0.1:11434/v1")
    with pytest.raises(ProviderError, match="64 KiB"):
        provider.decide("state", questions())
