"""Positive, per-request Ollama weight verification for local-only automation.

A loopback address is insufficient: Ollama can forward to a cloud model. This
guard uses metadata only, never pulls a model and never sends source contents
until installed local weights have been verified. It trusts the local Ollama
service, not arbitrary endpoints claiming `is_local`.
"""
from copy import copy
from contextlib import nullcontext
from dataclasses import dataclass
import json
import re
from urllib.parse import urlsplit, urlunsplit

import httpx

from .providers import OpenAICompatible, ProviderError, is_local_endpoint

_UNAVAILABLE = 'Ein installiertes lokales Ollama-Modell konnte nicht bestätigt werden. Die automatische Einordnung bleibt pausiert.'
_MAX_METADATA = 8 * 1024 * 1024


@dataclass(frozen=True)
class LocalModelIdentity:
    name: str
    digest: str


def _json(client, method, url, **kwargs):
    with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > _MAX_METADATA:
                raise ValueError('Metadata limit exceeded')
            content.extend(chunk)
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError('Invalid metadata')
    return result


def _local_row(tags, name):
    rows = tags.get('models')
    if not isinstance(rows, list):
        raise ValueError('Missing inventory')
    matches = [row for row in rows if isinstance(row, dict) and row.get('name') == name]
    if len(matches) != 1:
        raise ValueError('Exact model is not installed')
    row = matches[0]
    digest = row.get('digest')
    if (row.get('remote_host') or row.get('remote_model')
            or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
            or type(row.get('size')) is not int or row['size'] <= 0
            or not isinstance(row.get('details'), dict)
            or row['details'].get('format') != 'gguf'):
        raise ValueError('No installed local weights')
    return LocalModelIdentity(name, digest)


def verify_local_model(provider, *, capability='completion', client=None) -> LocalModelIdentity:
    """Verify exact installed weights/capability; unsupported fails closed.

    An embedding adapter can supply its own bounded, local-only client so the
    same metadata gate also applies immediately before its source submission.
    """
    try:
        if capability not in {'completion', 'decision', 'embedding'} or type(provider) is not OpenAICompatible or not provider.is_local:
            raise ValueError('Unsupported provider')
        base = urlsplit(provider.base_url)
        if (base.scheme not in {'http', 'https'} or base.username or base.password
                or base.query or base.fragment or base.path.rstrip('/') not in {'', '/v1'}
                or not is_local_endpoint(provider.base_url, provider._trusted_local_hosts)):
            raise ValueError('Unsupported local endpoint')
        model = provider.model
        if not isinstance(model, str) or not model or model != model.strip() or len(model) > 256:
            raise ValueError('Missing model')
        # Namespace and optional registry port are not the model tag.
        name = model if ':' in model.rsplit('/', 1)[-1] else model + ':latest'
        origin = urlunsplit((base.scheme, base.netloc, '', '', ''))
        with (nullcontext(client) if client is not None else
              httpx.Client(timeout=5.0, trust_env=False, follow_redirects=False)) as client:
            first = _local_row(_json(client, 'GET', origin + '/api/tags'), name)
            show = _json(client, 'POST', origin + '/api/show', json={'model': name})
            details, info = show.get('details'), show.get('model_info')
            capabilities = show.get('capabilities')
            if (show.get('remote_host') or show.get('remote_model')
                    or not isinstance(details, dict) or details.get('format') != 'gguf'
                    or not isinstance(info, dict) or not info.get('general.architecture')
                    or type(info.get('general.parameter_count')) is not int
                    or info['general.parameter_count'] <= 0
                    or not isinstance(capabilities, list) or capability not in capabilities):
                raise ValueError('No verified local text model')
            # Catch an ordinary model replacement during the metadata check.
            if _local_row(_json(client, 'GET', origin + '/api/tags'), name) != first:
                raise ValueError('Model changed during verification')
        return first
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise ProviderError(_UNAVAILABLE) from exc


class VerifiedLocalProvider:
    """A job-local provider copy; ordinary, user-directed chat is unaffected."""

    def __init__(self, provider, *, permitted=lambda: True):
        self._provider = copy(provider)
        self._provider._verified_local_transport = True
        self._identity = None
        self._permitted = permitted
        self.name = getattr(provider, 'name', '')
        self.model = getattr(provider, 'model', '')
        self.base_url = getattr(provider, 'base_url', '')
        self.is_local = bool(getattr(provider, 'is_local', False))
        self.entity_anchor_mode = getattr(provider, 'entity_anchor_mode', 'absolute')

    def _verify(self, *, capability='completion'):
        if not self._permitted():
            raise ProviderError(_UNAVAILABLE)
        identity = (verify_local_model(self._provider) if capability == 'completion'
                    else verify_local_model(self._provider, capability=capability))
        if not self._permitted():
            raise ProviderError(_UNAVAILABLE)
        if self._identity is not None and identity != self._identity:
            raise ProviderError(_UNAVAILABLE)
        self._identity = identity

    def complete(self, messages, tools):
        self._verify()
        reply = self._provider.complete(messages, tools)
        if not self._permitted():
            raise ProviderError(_UNAVAILABLE)
        return reply

    def complete_json(self, messages, **kwargs):
        self._verify()
        reply = self._provider.complete_json(messages, **kwargs)
        if not self._permitted():
            raise ProviderError(_UNAVAILABLE)
        return reply

    def decide(self, state, questions, **kwargs):
        self._verify(capability='decision')
        result = self._provider.decide(state, questions, **kwargs)
        if not self._permitted():
            raise ProviderError(_UNAVAILABLE)
        return result
