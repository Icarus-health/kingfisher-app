"""Artificial runner proves guarded transport, never live model quality."""
import importlib
import json

import httpx
import pytest


@pytest.fixture
def probe(monkeypatch):
    # Removing any path's HTTP fixture must fail closed, not spend real money.
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request',
                        lambda *_args, **_kwargs: pytest.fail('Real HTTP forbidden'))
    assert importlib.util.find_spec('probe_mistral_source_package'), 'Artificial helper is missing'
    module = importlib.import_module('probe_mistral_source_package')
    monkeypatch.delenv(module.KEY_ENV, raising=False)
    return module


def response_handler(*, wrong_topic=False, missing_usage=False, malformed_source=False, after_post=None):
    calls, source_texts = [], []

    def handle(request):
        calls.append((request.method, str(request.url)))
        assert str(request.url).startswith('https://api.eu.mistral.ai/v1/')
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': 'mistral-small-2603',
                'max_context_length': 16000, 'capabilities': {'completion_chat': True}}]})
        payload = json.loads(request.content)
        assert payload['model'] == 'mistral-small-2603'
        assert payload['service_tier'] == 'standard_only' and payload['reasoning_effort'] == 'none'
        source = json.loads(payload['messages'][-1]['content'])
        blocks = source['blocks']
        body = '\n'.join(block['text'] for block in blocks)
        source_texts.append(body)
        if 'items' in payload['response_format']['json_schema']['schema']['properties']:
            result = {'items': []} if malformed_source else {'items': {block['block_id']: 'fact' for block in blocks}}
        else:
            entities, categories = [], []
            for name in ('Vera König', 'Alex Rot', 'Alex Blau'):
                block = next((block for block in blocks if name in block['text']), None)
                if block:
                    entities.append({'kind': 'person', 'name': name, 'block_id': block['block_id'],
                                     'occurrence': 1, 'role': 'mentioned'})
            for topic, phrase in [('personal', 'Wohnungsbewerbung'), ('information', 'Fachnewsletter'), ('work', 'Projekt Atlas')]:
                block = next((block for block in blocks if phrase in block['text']), None)
                if block:
                    categories.append({'category_id': topic, 'block_id': block['block_id']})
            if wrong_topic and 'Wohnungsbewerbung' in body and 'Fachnewsletter' not in body:
                categories.append({'category_id': 'information', 'block_id': blocks[0]['block_id']})
            result = {'entities': entities, 'categories': categories}
        answer = {'model': 'mistral-small-2603', 'service_tier': 'standard',
                  'choices': [{'index': 0, 'finish_reason': 'stop',
                               'message': {'role': 'assistant', 'content': json.dumps(result)}}]}
        if not missing_usage:
            answer['usage'] = {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280}
        if after_post:
            after_post()
        return httpx.Response(200, json=answer)

    return httpx.MockTransport(handle), calls, source_texts


@pytest.mark.parametrize('options', [
    {}, {'allow_artificial_cloud': True},
    {'allow_artificial_cloud': True, 'cap_microusd': 0},
    {'allow_artificial_cloud': True, 'cap_microusd': 1000001},
    {'allow_artificial_cloud': True, 'cap_microusd': True},
    {'allow_artificial_cloud': True, 'cap_microusd': 1.0},
    {'allow_artificial_cloud': True, 'cap_microusd': 1000000, 'max_requests': 22},
    {'allow_artificial_cloud': True, 'cap_microusd': 1000000, 'seconds': 601},
])
def test_approval_explicit_integer_cap_and_bounds_fail_before_opening_any_store(probe, monkeypatch, options):
    monkeypatch.setattr(probe, 'EpisodeStore', lambda *_: pytest.fail('No store before authorization'))
    with pytest.raises(ValueError):
        probe.evaluate(**options)


def test_dedicated_artificial_key_never_falls_back_to_main_key(probe, monkeypatch):
    monkeypatch.setenv('MISTRAL_API_KEY', 'synthetic-main-key-must-not-be-used')
    with pytest.raises(ValueError, match='dedicated'):
        probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000)
    assert __import__('os').environ['MISTRAL_API_KEY'] == 'synthetic-main-key-must-not-be-used'


def test_changed_frozen_originals_are_rejected_before_network(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    altered = [dict(case) for case in probe.CASES]
    altered[0]['body'] += ' altered'
    monkeypatch.setattr(probe, 'CASES', tuple(altered))
    with pytest.raises(ValueError, match='frozen'):
        probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000)


def test_real_job_and_ledger_complete_all_seven_without_claiming_task_quality(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    monkeypatch.setenv('MISTRAL_API_KEY', 'synthetic-main-key')
    transport, calls, texts = response_handler()
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert report['synthetic_only'] is True and report['injected_http'] is True
    assert report['live_model_verified'] is False
    assert report['execution_status'] == 'execution_complete', report
    assert report['status'] == report['quality_status'] == 'incomplete'
    assert report['tasks'] == report['deadlines'] == 'not_evaluated'
    assert report['persons_categories_status'] == 'passed'
    assert len(report['results']) == report['original_count'] == 7
    assert all(row['original_unchanged'] and row['checks'] == {'persons': True, 'categories': True}
               for row in report['results'])
    assert len(set(report['source_ids'])) == 7
    assert set(report['source_ids']) == {row['source_id'] for row in report['results']}
    assert [row['id'] for row in report['results']] == [
        'optional-portal', 'optional-direct', 'explicit-deadline', 'newsletter', 'mixed',
        'appointment-versus-deadline', 'distinct-people']
    assert report['dataset_sha256'] == '5d1d15390f03db316d534d5fa339c7f7f04a3678b7839810ecbbac137db8aadc'
    assert report['originals_unchanged'] is True and report['original_store'] == 'temporary'
    assert calls[0] == ('GET', 'https://api.eu.mistral.ai/v1/models')
    assert len(calls) == 15 and report['inference_requests'] == 14
    assert report['budget']['spent_microusd'] == 1204 and report['budget']['held_microusd'] == 0
    assert report['budget']['remaining_microusd'] == 998796
    assert report['manifest']['input_microusd_per_million'] == 165000
    assert report['manifest']['output_microusd_per_million'] == 660000
    assert report['verified_context_limits'] == [16000]
    assert report['usage'] == {'prompt_tokens': 2800, 'completion_tokens': 1120, 'total_tokens': 3920}
    assert all(text and 'synthetic-main-key' not in text for text in texts)
    assert __import__('os').environ['MISTRAL_API_KEY'] == 'synthetic-main-key'
    assert 'synthetic-artificial-key' not in json.dumps(report)


def test_valid_but_wrong_category_is_a_quality_failure(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    transport, _, _ = response_handler(wrong_topic=True)
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert report['execution_status'] == 'execution_complete'
    assert report['persons_categories_status'] == report['quality_status'] == report['status'] == 'failed'
    assert report['results'][0]['checks']['categories'] is False


def test_ambiguous_usage_stops_after_one_post_with_durable_hold_and_no_retry(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    transport, calls, _ = response_handler(missing_usage=True)
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert len(calls) == 2
    assert report['execution_status'] == 'incomplete'
    assert report['budget']['reconciliation_required'] is True and report['budget']['held_microusd'] > 0
    assert report['originals_unchanged'] is True
    assert all(row['working_memory_state'] == 'pending' for row in report['results'])


def test_invalid_source_output_never_counts_as_success_or_saves_classification(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    transport, _, _ = response_handler(malformed_source=True)
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert report['execution_status'] == 'incomplete'
    assert report['status'] != 'passed'
    assert all(row['working_memory_state'] == 'pending' for row in report['results'])
    assert report['budget']['spent_microusd'] > 0


def test_request_limit_prevents_second_post_before_another_reservation(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    transport, calls, _ = response_handler()
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000,
                            max_requests=1, _http_transport=transport)
    assert len(calls) == 2 and report['inference_requests'] == 1
    assert report['budget']['spent_microusd'] == 86 and report['budget']['held_microusd'] == 0
    assert report['execution_status'] == 'incomplete'


def test_cli_has_no_default_cloud_allowance_or_success_exit(probe, monkeypatch, tmp_path):
    output = tmp_path / 'report.json'
    assert probe.main(['--output', str(output)]) == 2
    assert not output.exists()
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    transport, _, _ = response_handler()
    evaluate = probe.evaluate
    monkeypatch.setattr(probe, 'evaluate', lambda **kwargs: evaluate(**kwargs, _http_transport=transport))
    assert probe.main(['--output', str(output), '--allow-artificial-cloud', '--cap-usd', '1.00']) == 1
    assert json.loads(output.read_text())['execution_status'] == 'execution_complete'
    # A prepared report must never be overwritten by another run.
    assert probe.main(['--output', str(output), '--allow-artificial-cloud', '--cap-usd', '1.00']) == 2


def test_an_extra_source_after_preview_revokes_entire_synthetic_scope_before_network(probe, monkeypatch):
    from icarus_memory import EpisodeKind, Provenance, SourceType
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    preview = probe.CloudMemoryJobs.preview

    def add_unreviewed_source(jobs, *args, **kwargs):
        result = preview(jobs, *args, **kwargs)
        jobs.episodes.record(EpisodeKind.MESSAGE, 'Unexpected artificial source', 'Not in the frozen seven',
                             Provenance(SourceType.EMAIL, source_ref='synthetic:unexpected'))
        return result

    monkeypatch.setattr(probe.CloudMemoryJobs, 'preview', add_unreviewed_source)
    transport, calls, _ = response_handler()
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert calls == []
    assert report['originals_unchanged'] is False and report['execution_status'] == 'incomplete'
    assert report['original_count'] == 8 and report['selected_source_count'] == 7
    assert report['budget']['spent_microusd'] == report['budget']['held_microusd'] == 0


def test_original_change_during_first_post_stops_all_writes_and_further_requests(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    stores = []
    original_store = probe.EpisodeStore

    def capture_store(path):
        store = original_store(path)
        stores.append(store)
        return store

    def change_original():
        store = stores[0]
        episode = store.all_episodes()[0]
        episode.body += ' Synthetic source changed during request.'
        store._put(episode)

    monkeypatch.setattr(probe, 'EpisodeStore', capture_store)
    transport, calls, _ = response_handler(after_post=change_original)
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert len(calls) == 2 and report['inference_requests'] == 1
    assert report['originals_unchanged'] is False
    assert not all(row['original_unchanged'] for row in report['results'])
    assert all(row['working_memory_state'] != 'complete' for row in report['results'])
    assert all(row['topics'] == [] and row['person_names'] == [] for row in report['results'])
    assert report['execution_status'] == 'incomplete'


def test_deadline_cannot_start_another_request_or_accept_an_overdue_response(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    now = [1000.0]
    monkeypatch.setattr(probe.time, 'monotonic', lambda: now[0])
    transport, calls, _ = response_handler(after_post=lambda: now.__setitem__(0, 1002.0))
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000,
                            seconds=1, _http_transport=transport)
    assert len(calls) == 2 and report['execution_status'] == 'incomplete'
    assert all(row['working_memory_state'] == 'pending' for row in report['results'])
    assert report['budget']['held_microusd'] + report['budget']['spent_microusd'] > 0


def test_real_metadata_reservation_must_fit_even_a_small_explicit_cap(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    transport, calls, _ = response_handler()
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1, _http_transport=transport)
    assert calls == [('GET', 'https://api.eu.mistral.ai/v1/models')]
    assert report['inference_requests'] == 0 and report['execution_status'] == 'incomplete'
    assert report['budget']['spent_microusd'] == report['budget']['held_microusd'] == 0


@pytest.mark.parametrize('cap', ['1.000001', '2', '0', '-1', 'NaN', '1e-3', '0.0000001'])
def test_cli_rejects_nonexplicit_or_over_limit_decimal_caps_without_a_run(probe, tmp_path, cap):
    output = tmp_path / 'blocked.json'
    assert probe.main(['--output', str(output), '--allow-artificial-cloud', '--cap-usd', cap]) == 2
    assert not output.exists()


def test_unavailable_new_ledger_returns_an_honest_report_without_an_inference(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')

    def unavailable(path):
        path.touch()
        raise probe.MistralBudgetError('budget_unavailable')

    monkeypatch.setattr(probe, 'MistralSourceBudget', unavailable)
    transport, calls, _ = response_handler()
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
    assert calls == [] and report['execution_status'] == 'incomplete'
    assert report['error'] == 'MistralBudgetError' and report['originals_unchanged'] is True


@pytest.mark.parametrize('transport', [False, 0, 'not-a-transport'])
def test_invalid_injected_transport_cannot_silently_fall_back_to_real_http(probe, monkeypatch, transport):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-artificial-key')
    with pytest.raises(ValueError, match='transport'):
        probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=transport)
