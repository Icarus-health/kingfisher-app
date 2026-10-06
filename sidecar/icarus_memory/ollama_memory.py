"""Bound the resident lifetime of Kingfisher-owned local Ollama models."""
from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

import httpx

_LOG = logging.getLogger(__name__)
_MANAGED_PREFIX = "kingfisher-"
_TIMEOUT_SECONDS = 3.0
_MAX_RESPONSE_BYTES = 1024 * 1024
_MANAGED_MODEL_LOCK = threading.RLock()


def _ollama_client(*, timeout: float = _TIMEOUT_SECONDS, trust_env: bool = False,
                   follow_redirects: bool = False) -> httpx.Client:
    """Use only the configured local endpoint, without proxy or redirect routing."""
    return httpx.Client(timeout=timeout, trust_env=trust_env, follow_redirects=follow_redirects)


def _scope(provider: Any) -> tuple[str, str] | None:
    # Import lazily: providers owns ProviderError and imports this helper at runtime.
    from .providers import OpenAICompatible, is_local_endpoint

    if type(provider) is not OpenAICompatible:
        return None
    model = getattr(provider, "model", None)
    if (not isinstance(model, str) or not model.startswith(_MANAGED_PREFIX)
            or model != model.strip() or len(model) > 256):
        return None
    base_url = getattr(provider, "base_url", None)
    if not isinstance(base_url, str):
        return None
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme not in {"http", "https"} or port != 11434
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in {"", "/", "/v1", "/v1/"}):
        return None
    trusted_hosts = getattr(provider, "_trusted_local_hosts", ())
    if not is_local_endpoint(base_url, trusted_hosts):
        return None
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    # Ollama reports an omitted tag as `:latest` in /api/ps.
    ollama_name = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
    return origin, ollama_name


def _request(client: httpx.Client, method: str, url: str, body: dict | None = None) -> bytes:
    kwargs = {"json": body} if body is not None else {}
    with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > _MAX_RESPONSE_BYTES:
                raise ValueError("Ollama response exceeded its size limit")
            content.extend(chunk)
    return bytes(content)


def _loaded_models(client: httpx.Client, origin: str) -> list[str]:
    raw = _request(client, "GET", origin + "/api/ps")
    value = json.loads(raw)
    models = value.get("models") if isinstance(value, dict) else None
    if not isinstance(models, list):
        raise ValueError("Ollama did not return a loaded-model list")
    names = []
    for item in models:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name:
            raise ValueError("Ollama returned an invalid loaded-model name")
        names.append(name)
    return names


def _prepare(origin: str, target: str) -> None:
    with _ollama_client(timeout=_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False) as client:
        loaded = _loaded_models(client, origin)
        for name in dict.fromkeys(loaded):
            if name != target and name.startswith(_MANAGED_PREFIX):
                _request(client, "POST", origin + "/api/generate",
                         {"model": name, "keep_alive": 0})


def _shorten_target_retention(origin: str, target: str) -> None:
    with _ollama_client(timeout=_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False) as client:
        if target not in _loaded_models(client, origin):
            return
        _request(client, "POST", origin + "/api/generate",
                 {"model": target, "keep_alive": "15s"})


@contextmanager
def managed_model(provider: Any) -> Iterator[None]:
    """Prepare and briefly retain one Kingfisher-owned model around a local call.

    Providers outside the explicit local Ollama/model scope pass through without
    locking or making HTTP requests. A scoped call fails closed if competing
    Kingfisher models cannot be unloaded before its body runs.
    """
    scope = _scope(provider)
    if scope is None:
        yield
        return

    from .providers import ProviderError

    origin, target = scope
    with _MANAGED_MODEL_LOCK:
        try:
            _prepare(origin, target)
        except Exception as exc:  # Fail closed before allowing the model call.
            raise ProviderError("Kingfisher could not prepare Ollama model memory.") from exc
        try:
            yield
        finally:
            try:
                _shorten_target_retention(origin, target)
            except Exception:  # Do not replace a valid reply or the original call error.
                _LOG.warning("Kingfisher could not shorten its Ollama model retention.")
