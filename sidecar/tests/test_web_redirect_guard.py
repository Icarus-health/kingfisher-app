import httpx
import pytest
from icarus_memory import tools
from icarus_memory.security import SecurityError


def test_private_redirect_is_rejected_before_network(monkeypatch):
    calls = []
    real_client = httpx.Client
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={'location':'http://127.0.0.1/private'})
    def check(url):
        if '127.0.0.1' in url:
            raise SecurityError('private')
    monkeypatch.setattr(tools, 'check_url', check)
    monkeypatch.setattr(tools.httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(SecurityError):
        tools._web_fetch('https://public.example/')
    assert calls == ['https://public.example/']
