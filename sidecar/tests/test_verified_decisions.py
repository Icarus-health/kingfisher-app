"""Cloud aliases and permission changes must not receive sources via systemone either."""
import pytest

from icarus_memory.local_model_guard import VerifiedLocalProvider
from icarus_memory.providers import OpenAICompatible, ProviderError
from .test_local_model_guard import wire, metadata, provider


def test_local_decision_weights_are_verified_before_inference(monkeypatch):
    tags, show = metadata()
    show['capabilities'] = ['decision']
    requests, _, _ = wire(monkeypatch, tags=tags, show=show)
    calls = []
    def decide(self, state, questions, **kwargs):
        assert self._verified_local_transport
        calls.append(state)
        return {'answers': {}}
    monkeypatch.setattr(OpenAICompatible, 'decide', decide)
    result = VerifiedLocalProvider(provider()).decide({'private': 'synthetic'}, {})
    assert result == {'answers': {}} and calls == [{'private': 'synthetic'}]
    assert [r.url.path for r in requests] == ['/api/tags', '/api/show', '/api/tags']


@pytest.mark.parametrize('capabilities,remote', [(['embedding'], False), (['decision'], True)])
def test_decision_inference_rejects_missing_weights_or_wrong_capability(monkeypatch, capabilities, remote):
    tags, show = metadata()
    show['capabilities'] = capabilities
    if remote:
        show['remote_host'] = 'https://ollama.com'
    wire(monkeypatch, tags=tags, show=show)
    monkeypatch.setattr(OpenAICompatible, 'decide', lambda *a, **k: pytest.fail('No sources may be sent'))
    with pytest.raises(ProviderError):
        VerifiedLocalProvider(provider()).decide({'private': 'synthetic'}, {})


def test_revocation_during_decision_discards_the_result(monkeypatch):
    tags, show = metadata()
    show['capabilities'] = ['decision']
    wire(monkeypatch, tags=tags, show=show)
    allowed = [True]
    def decide(*args, **kwargs):
        allowed[0] = False
        return {'answers': {}}
    monkeypatch.setattr(OpenAICompatible, 'decide', decide)
    with pytest.raises(ProviderError):
        VerifiedLocalProvider(provider(), permitted=lambda: allowed[0]).decide({}, {})
