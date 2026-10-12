"""The benchmark must distinguish grounded output from correct interpretation."""
import json

import httpx
import pytest

import probe_category_quality as probe
from icarus_memory.providers import ProviderError, Reply


MODEL = 'synthetic:latest'


def inventory(art='local', calls=None):
    def respond(request):
        if calls is not None:
            calls.append(request.url.path)
        model = {'name': MODEL, 'digest': 'a' * 64, 'details': {'format': 'gguf'}}
        if art == 'cloud':
            model['remote_host'] = 'https://cloud.invalid'
        if art == 'missing':
            return httpx.Response(200, json={'models': []})
        if art == 'down':
            raise httpx.ConnectError('offline', request=request)
        return httpx.Response(200, json={'models': [model]})
    return lambda: httpx.Client(transport=httpx.MockTransport(respond))


class GroundedButWrong:
    name = model = MODEL
    is_local = True
    entity_anchor_mode = 'block_quote'

    def complete_json(self, messages, *, max_tokens, schema):
        return Reply(text=json.dumps({'categories': [{'category_id': 'work', 'block_id': 'B1'}], 'entities': []}))


class Invalid(GroundedButWrong):
    def complete_json(self, messages, *, max_tokens, schema):
        return Reply(text=json.dumps({'categories': [{'category_id': 'work', 'block_id': 'B404'}], 'entities': []}))


class Oracle(GroundedButWrong):
    """Only proves the scoring/pipeline can pass, never a real-model result."""
    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]['content'])
        text = '\n\n'.join(block['text'] for block in payload['blocks'])
        case = next(case for case in json.loads(probe.CATALOG.read_text())['cases'] if case['body'] == text)
        categories = [{'category_id': category,
                       'block_id': payload['blocks'][1 if case['id'] == 'newsletter-with-real-assignment' and category == 'work' else 0]['block_id']}
                      for category in case['required_categories']]
        entities = [{'kind': 'person', 'name': name, 'role': 'mentioned',
                     'block_id': next(block['block_id'] for block in payload['blocks'] if name in block['text'])}
                    for name in case['required_people']]
        return Reply(text=json.dumps({'categories': categories, 'entities': entities}))


class ExtraCategory(Oracle):
    def complete_json(self, *args, **kwargs):
        reply = super().complete_json(*args, **kwargs)
        data = json.loads(reply.text)
        data['categories'].append({'category_id': 'unclear', 'block_id': 'B1'})
        return Reply(text=json.dumps(data))


@pytest.mark.parametrize('base', ['https://cloud.invalid/v1', 'http://192.168.1.2:11434/v1',
                                 'http://user:secret@localhost:11434/v1',
                                 'http://127.0.0.1:11434/v1?secret=x'])
def test_non_loopback_or_credential_endpoint_rejected_before_network(base):
    def forbidden():
        pytest.fail('no client or provider may be created')
    with pytest.raises(ValueError):
        probe.run(MODEL, base_url=base, client_factory=forbidden, provider_factory=forbidden)


@pytest.mark.parametrize('art,reason', [('down', 'ollama_unreachable'), ('missing', 'model_not_proven_local'),
                                      ('cloud', 'model_not_proven_local')])
def test_unavailable_or_cloud_model_never_runs_and_never_claims_pass(art, reason):
    def forbidden(*args):
        pytest.fail('unverified model must not be instantiated')
    result = probe.run(MODEL, client_factory=inventory(art), provider_factory=forbidden)
    assert result['status'] == 'not_run'
    assert result['reason'] == reason
    assert result['model_calls_attempted'] == result['cases_evaluated'] == 0
    assert result['cases_planned'] == 8
    assert not result['model_run_completed'] and result['results'] == []


def test_real_category_pipeline_rejects_invalid_evidence_and_keeps_originals():
    result = probe.run(MODEL, client_factory=inventory(), provider_factory=lambda *args: Invalid())
    assert result['cases_evaluated'] == result['model_calls_attempted'] == 8
    assert result['cases_meeting_requirements'] == 0
    assert all(row['source_status'] == 'failed' and row['original_unchanged'] for row in result['results'])
    assert result['model_run_completed']


def test_oracle_passes_all_eight_cases_through_product_code():
    result = probe.run(MODEL, client_factory=inventory(), provider_factory=lambda *args: Oracle())
    assert result['status'] == 'evaluated' and result['reason'] is None
    assert result['cases_evaluated'] == result['cases_meeting_requirements'] == result['model_calls_attempted'] == 8
    assert all(row['original_unchanged'] for row in result['results'])


def test_valid_but_wrong_categories_and_missing_people_are_counted_as_errors():
    result = probe.run(MODEL, client_factory=inventory(), provider_factory=lambda *args: GroundedButWrong())
    rows = {row['id']: row for row in result['results']}
    assert rows['advertising-only']['source_status'] == 'complete'
    assert rows['advertising-only']['forbidden_categories_found'] == ['work']
    assert rows['specific-work']['missing_people'] == ['Lene Kühn']
    assert not rows['specific-work']['meets_requirements']
    assert 0 < result['cases_meeting_requirements'] < 8
    assert result['scope'] == 'category_and_person_mentions_only'
    assert result['personal_data_used'] is False


def test_unlisted_extra_categories_cannot_pass():
    result = probe.run(MODEL, client_factory=inventory(), provider_factory=lambda *args: ExtraCategory())
    assert result['model_run_completed']
    assert result['cases_meeting_requirements'] == 0
    assert all(row['unexpected_categories'] == ['unclear'] for row in result['results'])


@pytest.mark.parametrize('successful_first', [False, True])
def test_completion_failure_is_not_a_completed_quality_measurement(successful_first):
    class Failing(Oracle):
        calls = 0
        def complete_json(self, *args, **kwargs):
            self.calls += 1
            if successful_first and self.calls == 1:
                return super().complete_json(*args, **kwargs)
            raise ProviderError('synthetic unavailable provider')
    result = probe.run(MODEL, client_factory=inventory(), provider_factory=lambda *args: Failing())
    assert result['status'] == ('interrupted' if successful_first else 'not_run')
    assert result['reason'] == 'model_inference_failed'
    assert not result['model_run_completed']
    assert result['model_calls_attempted'] == result['cases_attempted'] == (2 if successful_first else 1)
    assert result['cases_evaluated'] == result['cases_meeting_requirements'] == int(successful_first)
    assert result['results'][-1]['failure_code'] == 'provider_error'


def test_model_switching_to_cloud_stops_before_next_completion():
    reads = []
    def respond(request):
        reads.append(request.url.path)
        model = {'name': MODEL, 'digest': 'a' * 64, 'details': {'format': 'gguf'}}
        if len(reads) > 1:
            model['remote_model'] = 'cloud-model'
        return httpx.Response(200, json={'models': [model]})
    result = probe.run(MODEL, client_factory=lambda: httpx.Client(transport=httpx.MockTransport(respond)),
                       provider_factory=lambda *args: GroundedButWrong())
    assert result['status'] == 'interrupted' and not result['model_run_completed']
    assert result['cases_evaluated'] == result['model_calls_attempted'] == 1
    assert len(reads) == 2


def test_existing_report_is_not_overwritten(tmp_path):
    target = tmp_path / 'report.json'
    target.write_text('keep me')
    with pytest.raises(FileExistsError):
        probe.write_report(target, {'status': 'not_run'})
    assert target.read_text() == 'keep me'


@pytest.mark.parametrize('change', ['empty', 'duplicate', 'missing_expectation', 'empty_expectation'])
def test_broken_catalog_cannot_become_a_successful_measurement(tmp_path, monkeypatch, change):
    catalog = json.loads(probe.CATALOG.read_text())
    if change == 'empty':
        catalog['cases'] = []
    elif change == 'duplicate':
        catalog['cases'][1]['id'] = catalog['cases'][0]['id']
    elif change == 'missing_expectation':
        del catalog['cases'][0]['required_categories']
    else:
        catalog['cases'][0]['required_categories'] = []
    path = tmp_path / 'broken.json'
    path.write_text(json.dumps(catalog))
    monkeypatch.setattr(probe, 'CATALOG', path)
    def forbidden(*args):
        pytest.fail('broken catalog must be rejected before networking')
    with pytest.raises(ValueError, match='catalog'):
        probe.run(MODEL, client_factory=forbidden, provider_factory=forbidden)
