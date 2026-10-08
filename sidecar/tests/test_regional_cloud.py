import json

import httpx
import pytest

from icarus_memory.model_roles import RollenWahl, _cloud
from icarus_memory.providers import ProviderError


@pytest.mark.parametrize('provider,name,endpoint', [
    ('mistral', 'MISTRAL_API_KEY', 'https://api.eu.mistral.ai/v1'),
    ('openrouter', 'OPENROUTER_API_KEY', 'https://eu.openrouter.ai/api/v1'),
])
def test_regional_provider_no_proxy_redirect_or_global_fallback(monkeypatch, provider, name, endpoint):
    chosen = _cloud(RollenWahl(anbieter=provider, modell='synthetic-model'), {name: 'synthetic-secret'})
    assert chosen.base_url == endpoint and not chosen.is_local
    assert _cloud(RollenWahl(anbieter=provider, modell='synthetic-model'), {'OPENAI_API_KEY': 'wrong-key'}) is None
    assert _cloud(RollenWahl(anbieter=provider), {name: 'synthetic-secret'}) is None
    calls = []
    def request(req):
        calls.append(req)
        payload = json.loads(req.content)
        assert payload['max_tokens'] == 1024
        if provider == 'openrouter':
            assert payload['provider'] == {'zdr': True, 'data_collection': 'deny', 'allow_fallbacks': False}
        return httpx.Response(302, headers={'location': 'https://global.example.invalid'})
    client_type = httpx.Client
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return client_type(**kwargs, transport=httpx.MockTransport(request))
    monkeypatch.setattr(httpx, 'Client', client)
    with pytest.raises(ProviderError):
        chosen.complete([{'role': 'user', 'content': 'synthetic only'}], [])
    assert len(calls) == 1 and str(calls[0].url) == endpoint + '/chat/completions'
