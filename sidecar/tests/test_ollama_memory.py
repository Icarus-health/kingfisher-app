"""Scoped Ollama model switching for Kingfisher memory calls."""
from __future__ import annotations

import json
import threading
import time

import httpx
import pytest

from icarus_memory import ollama_memory
from icarus_memory.providers import OpenAICompatible, ProviderError


BASE = "http://127.0.0.1:11434/v1"


def test_provider_gate_prepares_and_releases_managed_model(monkeypatch):
    from contextlib import contextmanager
    events = []
    @contextmanager
    def managed(selected):
        events.append(('prepare', selected.model))
        try:
            yield
        finally:
            events.append(('release', selected.model))
    monkeypatch.setattr(ollama_memory, 'managed_model', managed)
    selected = provider()
    with selected._ampel():
        events.append(('call', selected.model))
    assert events == [('prepare', selected.model), ('call', selected.model), ('release', selected.model)]


def provider(model="kingfisher-memory", base=BASE):
    return OpenAICompatible(model=model, base_url=base)


def fake_client(monkeypatch, handler):
    options = []

    def make_client(*, timeout, trust_env, follow_redirects):
        options.append((timeout, trust_env, follow_redirects))
        return httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout,
                            trust_env=trust_env, follow_redirects=follow_redirects)

    monkeypatch.setattr(ollama_memory, "_ollama_client", make_client)
    return options


def test_unloads_only_other_managed_models_and_shortens_target_retention(monkeypatch):
    calls = []
    target_loaded = False

    def handle(request):
        nonlocal target_loaded
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.method == "GET":
            names = ["kingfisher-memory:latest", "kingfisher-other:latest", "llama3:latest"]
            if target_loaded:
                names = ["kingfisher-memory:latest", "llama3:latest"]
            return httpx.Response(200, json={"models": [{"name": name} for name in names]})
        if body == {"model": "kingfisher-other:latest", "keep_alive": 0}:
            return httpx.Response(200, json={"response": ""})
        if body == {"model": "kingfisher-memory:latest", "keep_alive": "15s"}:
            return httpx.Response(200, json={"response": ""})
        return httpx.Response(400)

    options = fake_client(monkeypatch, handle)
    with ollama_memory.managed_model(provider()):
        target_loaded = True

    assert calls == [
        ("GET", "/api/ps", None),
        ("POST", "/api/generate", {"model": "kingfisher-other:latest", "keep_alive": 0}),
        ("GET", "/api/ps", None),
        ("POST", "/api/generate", {"model": "kingfisher-memory:latest", "keep_alive": "15s"}),
    ]
    assert options and all(timeout <= 3 and trust_env is False and redirects is False
                           for timeout, trust_env, redirects in options)


def test_scoped_context_is_noop_for_remote_unscoped_or_invalid_provider(monkeypatch):
    calls = []
    options = fake_client(monkeypatch, lambda request: calls.append(request))
    candidates = [
        provider("ordinary-model"),
        provider(base="https://remote.example:11434/v1"),
        provider(base="http://127.0.0.1:11434/proxy/v1"),
        provider(base="http://127.0.0.1:1234/v1"),
        provider(base="http://127.0.0.1:11434/v1?route=elsewhere"),
    ]
    stale_local_flag = provider()
    stale_local_flag._base = "https://remote.example:11434/v1"
    candidates.append(stale_local_flag)

    class NotOpenAICompatible:
        model = "kingfisher-memory:latest"
        base_url = BASE
        is_local = True

    candidates.append(NotOpenAICompatible())
    for candidate in candidates:
        with ollama_memory.managed_model(candidate):
            pass

    assert calls == []
    assert options == []


def test_preflight_failure_blocks_the_managed_call(monkeypatch):
    fake_client(monkeypatch, lambda request: httpx.Response(503))
    yielded = False

    with pytest.raises(ProviderError):
        with ollama_memory.managed_model(provider()):
            yielded = True

    assert yielded is False


def test_oversized_preflight_response_blocks_the_managed_call(monkeypatch):
    raw = b'{"models":[]}' + b" " * ollama_memory._MAX_RESPONSE_BYTES
    fake_client(monkeypatch, lambda request: httpx.Response(200, content=raw))
    yielded = False

    with pytest.raises(ProviderError):
        with ollama_memory.managed_model(provider()):
            yielded = True

    assert yielded is False


def test_target_retention_runs_after_error_and_does_not_mask_it(monkeypatch, caplog):
    calls = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(200, json={"models": [{"name": "kingfisher-memory:latest"}]})
        if body == {"model": "kingfisher-memory:latest", "keep_alive": "15s"}:
            return httpx.Response(500, json={"error": "private response detail"})
        return httpx.Response(200, json={})

    fake_client(monkeypatch, handle)
    with pytest.raises(RuntimeError, match="original call failure"):
        with ollama_memory.managed_model(provider()):
            raise RuntimeError("original call failure")

    assert calls[-2:] == [("GET", "/api/ps", None),
                          ("POST", "/api/generate", {"model": "kingfisher-memory:latest", "keep_alive": "15s"})]
    assert "private response detail" not in caplog.text


def test_does_not_load_target_for_retention_when_it_is_not_loaded(monkeypatch):
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"models": []})

    fake_client(monkeypatch, handle)
    with pytest.raises(RuntimeError, match="model call failed"):
        with ollama_memory.managed_model(provider()):
            raise RuntimeError("model call failed")

    assert calls == [("GET", "/api/ps"), ("GET", "/api/ps")]


def test_retention_failure_logs_constant_warning_without_failing_success(monkeypatch, caplog):
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        if request.method == "GET":
            return httpx.Response(200, json={"models": [{"name": "kingfisher-memory:latest"}]})
        return httpx.Response(500, json={"error": "private response detail"})

    fake_client(monkeypatch, handle)
    with ollama_memory.managed_model(provider()):
        result = "valid reply"

    assert result == "valid reply"
    assert calls == 3
    assert "could not shorten its Ollama model retention" in caplog.text
    assert "private response detail" not in caplog.text


def test_managed_calls_are_serialized_process_wide(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"models": []})

    fake_client(monkeypatch, handle)
    first_inside = threading.Event()
    release_first = threading.Event()
    second_inside = threading.Event()

    def first():
        with ollama_memory.managed_model(provider()):
            first_inside.set()
            release_first.wait(timeout=2)

    def second():
        first_inside.wait(timeout=2)
        with ollama_memory.managed_model(provider("kingfisher-second:latest")):
            second_inside.set()

    a = threading.Thread(target=first)
    b = threading.Thread(target=second)
    a.start()
    b.start()
    assert first_inside.wait(timeout=2)
    time.sleep(0.05)
    assert not second_inside.is_set()
    release_first.set()
    a.join(timeout=2)
    b.join(timeout=2)

    assert not a.is_alive() and not b.is_alive()
    assert second_inside.is_set()
