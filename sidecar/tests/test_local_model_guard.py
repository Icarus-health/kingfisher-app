"""A localhost Ollama endpoint may proxy a cloud model; verify actual weights."""
import copy
import json

import httpx
import pytest

from icarus_memory import local_model_guard as guard
from icarus_memory.providers import OpenAICompatible, ProviderError


def metadata():
    return ({'models': [{'name': 'local:latest', 'digest': 'a' * 64,
                        'size': 100000, 'details': {'format': 'gguf'}}]},
            {'details': {'format': 'gguf'}, 'capabilities': ['completion'],
             'model_info': {'general.architecture': 'qwen2',
                            'general.parameter_count': 100000}})


def wire(monkeypatch, tags=None, show=None, *, chat=None):
    default_tags, default_show = metadata()
    tags = default_tags if tags is None else tags
    show = default_show if show is None else show
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json=tags)
        if request.url.path == '/api/show':
            assert json.loads(request.content) == {'model': 'local:latest'}
            return httpx.Response(200, json=show)
        assert request.url.path == '/v1/chat/completions'
        assert chat is not None, 'Private text must never reach an unverified model'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': chat}}]})
    real_client = httpx.Client
    def client(**kwargs):
        assert kwargs.get('trust_env') is False
        assert kwargs.get('follow_redirects') is False
        return real_client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(httpx, 'Client', client)
    return requests, tags, show


def provider(model='local'):
    return OpenAICompatible(model=model, base_url='http://127.0.0.1:11434/v1')


def test_installed_local_weights_are_positively_verified(monkeypatch):
    requests, _, _ = wire(monkeypatch)
    identity = guard.verify_local_model(provider())
    assert identity.name == 'local:latest'
    assert identity.digest == 'a' * 64
    assert [r.url.path for r in requests] == ['/api/tags', '/api/show', '/api/tags']
    assert all(b'private' not in r.content for r in requests)


@pytest.mark.parametrize('where,field,value', [
    ('tags', 'remote_host', 'https://ollama.com'),
    ('tags', 'remote_model', 'cloud-model'),
    ('show', 'remote_host', 'https://ollama.com'),
    ('show', 'remote_model', 'cloud-model'),
    ('tags', 'size', 0),
    ('tags', 'digest', ''),
    ('show', 'model_info', {}),
    ('show', 'capabilities', ['embedding']),
    ('show', 'details', {'format': ''}),
])
def test_cloud_or_unproven_model_never_receives_private_text(monkeypatch, where, field, value):
    tags, show = metadata()
    target = tags['models'][0] if where == 'tags' else show
    target[field] = value
    requests, _, _ = wire(monkeypatch, tags, show)
    with pytest.raises(ProviderError):
        guard.VerifiedLocalProvider(provider()).complete([{'role': 'user', 'content': 'private'}], [])
    assert all(r.url.path != '/v1/chat/completions' for r in requests)


def test_every_request_rechecks_model_before_sending_private_text(monkeypatch):
    requests, tags, show = wire(monkeypatch, chat='{}')
    checked = guard.VerifiedLocalProvider(provider())
    assert checked.complete_json([{'role': 'user', 'content': 'private-one'}]).text == '{}'
    show['remote_model'] = 'later-cloud-alias'
    with pytest.raises(ProviderError):
        checked.complete([{'role': 'user', 'content': 'private-two'}], [])
    assert len([r for r in requests if r.url.path == '/v1/chat/completions']) == 1
    assert all(b'private-two' not in r.content for r in requests)


def test_changed_local_weights_need_new_binding(monkeypatch):
    requests, tags, _ = wire(monkeypatch, chat='ok')
    checked = guard.VerifiedLocalProvider(provider())
    checked.complete([{'role': 'user', 'content': 'first'}], [])
    tags['models'][0]['digest'] = 'b' * 64
    with pytest.raises(ProviderError):
        checked.complete([{'role': 'user', 'content': 'second'}], [])
    assert len([r for r in requests if r.url.path == '/v1/chat/completions']) == 1


def test_verification_cannot_silently_use_redirect_or_unknown_provider(monkeypatch):
    real_client = httpx.Client
    seen = []
    def redirect(request):
        seen.append(str(request.url))
        return httpx.Response(307, headers={'location': 'https://remote.invalid/api/tags'})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(
        transport=httpx.MockTransport(redirect), **kw))
    with pytest.raises(ProviderError):
        guard.verify_local_model(provider())
    assert len(seen) == 1
    assert '127.0.0.1' in seen[0]
    with pytest.raises(ProviderError):
        guard.verify_local_model(type('Fake', (), {'is_local': True, 'model': 'local'})())


def test_remote_or_changed_endpoint_rejected_before_metadata_request(monkeypatch):
    requests, _, _ = wire(monkeypatch)
    remote = OpenAICompatible(model='local', base_url='https://remote.invalid/v1')
    changed = provider()
    changed._base = 'https://remote.invalid/v1'
    for candidate in [remote, changed]:
        with pytest.raises(ProviderError):
            guard.verify_local_model(candidate)
    assert not requests


def test_wrapping_keeps_user_directed_provider_unchanged(monkeypatch):
    wire(monkeypatch, chat='ok')
    ordinary = provider()
    snapshot = copy.copy(vars(ordinary))
    checked = guard.VerifiedLocalProvider(ordinary)
    checked.complete([{'role': 'user', 'content': 'synthetic'}], [])
    assert vars(ordinary) == snapshot


def test_pause_during_metadata_check_prevents_content_request(monkeypatch):
    requests, _, _ = wire(monkeypatch)
    allowed = [True]
    real_verify = guard.verify_local_model
    def verify_then_pause(candidate):
        identity = real_verify(candidate)
        allowed[0] = False
        return identity
    monkeypatch.setattr(guard, 'verify_local_model', verify_then_pause)
    checked = guard.VerifiedLocalProvider(provider(), permitted=lambda: allowed[0])
    with pytest.raises(ProviderError):
        checked.complete([{'role': 'user', 'content': 'private'}], [])
    assert requests and all(r.url.path != '/v1/chat/completions' for r in requests)


def test_provider_subclass_cannot_bypass_verified_direct_transport(monkeypatch):
    requests, _, _ = wire(monkeypatch)
    class OverriddenTransport(OpenAICompatible):
        def complete(self, messages, tools):
            pytest.fail('Unknown outbound implementation was called')
    candidate = OverriddenTransport('local', base_url='http://127.0.0.1:11434/v1')
    with pytest.raises(ProviderError):
        guard.VerifiedLocalProvider(candidate).complete([], [])
    assert not requests


@pytest.mark.parametrize('json_mode', [False, True])
def test_pause_during_inference_discards_result(monkeypatch, json_mode):
    requests, _, _ = wire(monkeypatch, chat='{}')
    allowed = [True]
    method = 'complete_json' if json_mode else 'complete'
    original = getattr(OpenAICompatible, method)
    def complete_then_pause(self, *args, **kwargs):
        reply = original(self, *args, **kwargs)
        allowed[0] = False
        return reply
    monkeypatch.setattr(OpenAICompatible, method, complete_then_pause)
    checked = guard.VerifiedLocalProvider(provider(), permitted=lambda: allowed[0])
    with pytest.raises(ProviderError):
        if json_mode:
            checked.complete_json([{'role': 'user', 'content': 'synthetic'}])
        else:
            checked.complete([{'role': 'user', 'content': 'synthetic'}], [])
    assert len([r for r in requests if r.url.path == '/v1/chat/completions']) == 1
