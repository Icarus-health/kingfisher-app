import httpx
import pytest

from probe_hybrid_memory import LocalEmbedder, cases, compare
from memory_probe_support import validate_case


def transport(seen, *, redirect=False, mismatch=False):
    def respond(request):
        seen.append(request)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'bge-m3:latest', 'digest': 'a' * 64,
                                                       'capabilities': ['embedding']}]})
        if redirect:
            return httpx.Response(307, headers={'location': 'https://example.invalid/leak'})
        return httpx.Response(200, json={'model': 'other' if mismatch else 'bge-m3:latest',
                                         'embeddings': [[1., 0.]]})
    return httpx.MockTransport(respond)


def test_only_fixed_loopback_endpoint_and_untruncated_input():
    import json
    seen = []
    with LocalEmbedder(transport=transport(seen)) as embedder:
        assert embedder.embed(['synthetic']) == [[1., 0.]]
    assert all(str(r.url).startswith('http://127.0.0.1:11434/') for r in seen)
    body = json.loads(next(r.content for r in seen if r.method == 'POST'))
    assert body == {'model': 'bge-m3:latest', 'input': ['synthetic'], 'truncate': False}


@pytest.mark.parametrize('redirect,mismatch', [(True, False), (False, True)])
def test_redirect_or_wrong_model_fails_without_external_request(redirect, mismatch):
    seen = []
    with LocalEmbedder(transport=transport(seen, redirect=redirect, mismatch=mismatch)) as embedder:
        with pytest.raises(RuntimeError): embedder.embed(['synthetic'])
    assert all(r.url.host == '127.0.0.1' for r in seen)


def test_missing_installed_model_never_pulls_or_generates():
    seen = []
    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={'models': []})
    with pytest.raises(RuntimeError):
        with LocalEmbedder(transport=httpx.MockTransport(respond)):
            pass
    assert [r.url.path for r in seen] == ['/api/tags']


def test_documented_tags_response_without_capabilities_is_supported():
    def respond(request):
        return httpx.Response(200, json={'models': [{'name': 'bge-m3:latest', 'digest': 'b' * 64}]})
    with LocalEmbedder(transport=httpx.MockTransport(respond)) as embedder:
        assert embedder.model_key.endswith('b' * 64)


def test_development_cases_are_valid_unique_and_have_negative_controls():
    dataset = cases()
    for case in dataset: validate_case(case)
    assert len({c['id'] for c in dataset}) == len(dataset) == 10
    assert any(not c['expected_source_ids'] for c in dataset)
    assert any(c['forbidden_source_ids'] for c in dataset)


def test_comparison_scores_actual_provider_payload_not_expected_ids():
    class Fake:
        is_local = True
        model_key = 'synthetic-weights'
        def embed(self, texts): return [[1., 0.] for _ in texts]
    results = compare(Fake(), [cases()[0]])
    assert len(results) == 2
    for result in results:
        actual = set(result['actual_source_ids'])
        assert result['retrieval']['missing'] == sorted({'S1'} - actual)
        assert result['retrieval']['forbidden_seen'] == sorted({'S9'} & actual)
        assert not result['payload_mismatch_claim_ids']
        assert result['provider_calls']
