import importlib.util
from pathlib import Path

import httpx
import pytest


def harness():
    path = Path(__file__).with_name('evaluate_cos_models.py')
    assert path.exists(), 'Missing separate model-only evaluation harness'
    spec = importlib.util.spec_from_file_location('cos_eval', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('message,reason,status', [
    ({'content': 'Belegt durch S2.'}, 'stop', 'review_required'),
    ({'content': '', 'thinking': 'hidden'}, 'stop', 'empty_response'),
    ({'content': 'partial'}, 'length', 'truncated'),
    ({'content': 'ok', 'tool_calls': [{'function': {'name': 'send'}}]}, 'stop', 'unexpected_tools'),
])
def test_records_real_request_and_never_auto_passes(message, reason, status):
    module = harness()
    sent = []
    def handler(request):
        import json
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'message': message, 'done': True, 'done_reason': reason})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = module.evaluate(client, 'synthetic', module.CASES[0], False)
    assert result['status'] == status
    assert result['semantic_verdict'] is None
    assert result['request'] == sent[0]
    assert 'tools' not in sent[0]
    assert result['response'] == {'message': message, 'done': True, 'done_reason': reason}
    assert result['model_requests'] == 1


def test_timeout_is_failure_not_success():
    module = harness()
    def handler(request):
        raise httpx.ReadTimeout('synthetic timeout', request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = module.evaluate(client, 'synthetic', module.CASES[0], False)
    assert result['status'] == 'transport_error'
    assert result['semantic_verdict'] is None


def test_uninstalled_model_rejected_before_generation():
    module = harness()
    def handler(request):
        assert request.url.path == '/api/tags'
        return httpx.Response(200, json={'models': []})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match='installed'):
            module.metadata(client, 'missing')
