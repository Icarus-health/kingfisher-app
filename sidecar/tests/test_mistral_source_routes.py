"""Authenticated synthetic read/write routes never infer from budget or preparation."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.secrets import PASSPHRASE_ENV
from icarus_memory.server import create_app

MODEL = 'mistral-small-2603'


def test_budget_routes_are_authenticated_strict_cumulative_and_offline(monkeypatch, tmp_path):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-budget-token')
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-budget-passphrase')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **kw: pytest.fail('No provider request from status, key, preview or cap'))
    app = create_app()
    with TestClient(app) as client:
        path = '/api/v1/memory/cloud/budget'
        assert client.get(path + '?provider=mistral').status_code == 401
        headers = {'X-Icarus-Token': 'synthetic-budget-token'}
        response = client.get(path + '?provider=mistral', headers=headers)
        assert response.status_code == 200, response.text
        first = response.json()
        assert first['cap_microusd'] == first['spent_microusd'] == first['held_microusd'] == 0
        assert not first['ready'] and first['provider'] == 'mistral'
        ledger = app.state.mistral_source_budget
        for method in ['get', 'put']:
            if method == 'get':
                response = client.get(path + '?provider=anthropic', headers=headers)
            else:
                response = client.put(path, headers=headers, json={'provider': 'anthropic', 'cap_microusd': 100, 'expected_revision': first['revision'], 'consent': True})
            assert response.status_code == 422
        body = {'provider': 'mistral', 'cap_microusd': 1000000, 'expected_revision': first['revision'], 'consent': True}
        for bad in [{'cap_microusd': True}, {'cap_microusd': 0.5}, {'expected_revision': True},
                    {'expected_revision': 1.0}, {'consent': False}, {'consent': 1},
                    {'cap_microusd': -1}, {'cap_microusd': 1000000001}, {'extra': 'forbidden'}]:
            response = client.put(path, headers=headers, json={**body, **bad})
            assert response.status_code == 422, response.text
        assert client.get(path + '?provider=mistral', headers=headers).json() == first
        assert client.put('/api/v1/models/cloud-access/mistral', headers=headers,
                          json={'api_key': 'synthetic-key', 'model': 'unrelated-chat-model'}).status_code == 200
        original, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic source', 'Synthetic source text',
            Provenance(SourceType.EMAIL, source_ref='synthetic:budget-route'))
        preview = client.post('/api/v1/memory/cloud/preview', headers=headers,
                              json={'provider': 'mistral', 'source_ids': [original.id]})
        assert preview.status_code == 200, preview.text
        assert preview.json()['budget'] == first
        assert app.state.cloud_memory_jobs.mistral_budget is ledger
        assert client.post('/api/v1/memory/cloud/start', headers=headers, json={
            'provider': 'mistral', 'preview_id': preview.json()['preview_id'], 'model': MODEL, 'consent': True}).status_code == 409
        changed = client.put(path, headers=headers, json=body)
        assert changed.status_code == 200, changed.text
        assert changed.json()['cap_microusd'] == 1000000
        assert changed.json()['revision'] == first['revision'] + 1
        assert client.get('/api/v1/memory/cloud/status', headers=headers).json()['job'] is None
        assert app.state.mistral_source_budget is ledger
        # A cap update invalidates an earlier zero-budget review.
        assert client.post('/api/v1/memory/cloud/start', headers=headers, json={
            'provider': 'mistral', 'preview_id': preview.json()['preview_id'], 'model': MODEL, 'consent': True}).status_code == 409
        assert client.put(path, headers=headers, json=body).status_code == 409


def test_real_mistral_route_uses_same_ledger_and_exact_source_policy(monkeypatch):
    from icarus_memory.mistral_import_provider import MistralImportProvider
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-route-passphrase')
    calls = []
    def handler(request):
        calls.append((request.method, str(request.url)))
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': MODEL, 'max_context_length': 16000,
                'capabilities': {'completion_chat': True}}]})
        payload = json.loads(request.content)
        schema = payload['response_format']['json_schema']['schema']
        source = json.loads(payload['messages'][-1]['content'])
        result = ({'items': {block['block_id']: 'fact' for block in source['blocks']}}
                  if 'items' in schema['properties'] else {'categories': [], 'entities': []})
        return httpx.Response(200, json={'model': MODEL, 'service_tier': 'standard',
            'usage': {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280},
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(result)}}]})
    monkeypatch.setattr(MistralImportProvider, '_client', lambda _: httpx.Client(
        transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False))
    app = create_app()
    with TestClient(app) as client:
        assert client.put('/api/v1/models/cloud-access/mistral', json={'api_key': 'synthetic-key', 'model': 'ordinary-chat-model'}).status_code == 200
        original, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic approved source', 'Synthetic original only',
            Provenance(SourceType.EMAIL, source_ref='synthetic:route-e2e'))
        other, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic unselected source', 'Unselected source only',
            Provenance(SourceType.EMAIL, source_ref='synthetic:unselected'))
        budget = client.get('/api/v1/memory/cloud/budget?provider=mistral').json()
        assert client.put('/api/v1/memory/cloud/budget', json={'provider': 'mistral', 'cap_microusd': 1000000,
            'expected_revision': budget['revision'], 'consent': True}).status_code == 200
        preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral', 'source_ids': [original.id]}).json()
        assert calls == []
        start = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral', 'model': MODEL,
            'preview_id': preview['preview_id'], 'consent': True})
        assert start.status_code == 200, start.text
        job_id = start.json()['job']['id']
        app.state.cloud_memory_jobs._threads[job_id].join(10)
        result = client.get('/api/v1/memory/cloud/status').json()['job']
        assert result['state'] == 'complete', result
        assert result['budget']['spent_microusd'] > 0 and result['budget']['held_microusd'] == 0
        assert calls == [('GET', 'https://api.eu.mistral.ai/v1/models'),
                         ('POST', 'https://api.eu.mistral.ai/v1/chat/completions'),
                         ('POST', 'https://api.eu.mistral.ai/v1/chat/completions')]
        assert app.state.cloud_memory_jobs.memory.source_state(other.id) == 'pending'
        assert app.state.settings.cloud_models['mistral'] == 'ordinary-chat-model'
        for path in [app.state.cloud_memory_jobs.path, app.state.mistral_source_budget.path]:
            contents = path.read_bytes()
            assert b'synthetic-key' not in contents and b'Synthetic original only' not in contents


def test_unrelated_cloud_status_does_not_open_or_depend_on_mistral_ledger(monkeypatch):
    from icarus_memory.cloud_import_budget import MistralBudgetError
    from icarus_memory import cloud_memory_routes
    def unavailable(*args):
        raise MistralBudgetError('budget_unavailable')
    monkeypatch.setattr(cloud_memory_routes, 'MistralSourceBudget', unavailable)
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/api/v1/memory/cloud/status')
        assert response.status_code == 200 and response.json() == {'job': None}
        assert getattr(app.state, 'mistral_source_budget', None) is None
        response = client.get('/api/v1/memory/cloud/budget?provider=mistral')
        assert response.status_code == 409
        assert 'budget_unavailable' not in response.text


def test_key_delete_race_during_adapter_construction_rejects_start_safely(monkeypatch):
    import os
    from icarus_memory import cloud_memory_routes
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-race-passphrase')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **kw: pytest.fail('No metadata or inference after key deletion'))
    app = create_app()
    with TestClient(app) as client:
        assert client.put('/api/v1/models/cloud-access/mistral', json={'api_key': 'synthetic-race-key', 'model': 'chat-model'}).status_code == 200
        source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic source', 'Synthetic key race source',
            Provenance(SourceType.EMAIL, source_ref='synthetic:key-race'))
        budget = client.get('/api/v1/memory/cloud/budget?provider=mistral').json()
        client.put('/api/v1/memory/cloud/budget', json={'provider': 'mistral', 'cap_microusd': 1000000,
            'expected_revision': budget['revision'], 'consent': True})
        preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral', 'source_ids': [source.id]}).json()
        original = cloud_memory_routes.credential_status
        checks = []
        def revoke_after_status(*args, **kwargs):
            result = original(*args, **kwargs)
            checks.append(1)
            if len(checks) == 2:
                os.environ.pop('MISTRAL_API_KEY', None)
            return result
        monkeypatch.setattr(cloud_memory_routes, 'credential_status', revoke_after_status)
        response = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral', 'model': MODEL,
            'preview_id': preview['preview_id'], 'consent': True})
        assert response.status_code == 409
        assert app.state.cloud_memory_jobs.status()['job'] is None


@pytest.mark.parametrize('failure_stage', ['source', 'categories'])
def test_ambiguous_mistral_billing_pauses_once_and_cannot_retry_failed_stage(monkeypatch, failure_stage):
    from icarus_memory.mistral_import_provider import MistralImportProvider
    from icarus_memory.working_memory_store import WorkingMemoryStore
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-uncertain-passphrase')
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': MODEL, 'max_context_length': 16000,
                'capabilities': {'completion_chat': True}}]})
        payload = json.loads(request.content)
        schema = payload['response_format']['json_schema']['schema']
        source = json.loads(payload['messages'][-1]['content'])
        stage = 'source' if 'items' in schema['properties'] else 'categories'
        result = ({'items': {block['block_id']: 'fact' for block in source['blocks']}}
                  if stage == 'source' else {'categories': [], 'entities': []})
        answer = {'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
                  'message': {'role': 'assistant', 'content': json.dumps(result)}}]}
        if stage != failure_stage:
            answer['usage'] = {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280}
        # Missing usage is deliberately ambiguous, even when JSON itself is valid.
        return httpx.Response(200, json=answer)
    monkeypatch.setattr(MistralImportProvider, '_client', lambda _: httpx.Client(
        transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False))
    app = create_app()
    with TestClient(app) as client:
        client.put('/api/v1/models/cloud-access/mistral', json={'api_key': 'synthetic-uncertain-key', 'model': 'chat-model'})
        source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic uncertain source', 'Synthetic original unchanged',
            Provenance(SourceType.EMAIL, source_ref='synthetic:uncertain'))
        tasks_before = app.state.tasks.all_tasks()
        budget = client.get('/api/v1/memory/cloud/budget?provider=mistral').json()
        client.put('/api/v1/memory/cloud/budget', json={'provider': 'mistral', 'cap_microusd': 1000000,
            'expected_revision': budget['revision'], 'consent': True})
        preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral', 'source_ids': [source.id]}).json()
        started = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral', 'model': MODEL,
            'preview_id': preview['preview_id'], 'consent': True})
        assert started.status_code == 200, started.text
        job_id = started.json()['job']['id']
        app.state.cloud_memory_jobs._threads[job_id].join(10)
        result = client.get('/api/v1/memory/cloud/status').json()['job']
        assert result['state'] == 'paused', result
        assert result['budget']['reconciliation_required'] and result['budget']['held_microusd'] > 0
        assert 'unklar' in result['stop_reason']
        assert len(calls) == (2 if failure_stage == 'source' else 3)
        before_resume = list(calls)
        assert client.post('/api/v1/memory/cloud/resume', json={'job_id': job_id}).status_code == 409
        assert calls == before_resume
        assert WorkingMemoryStore(app.state.episodes).source_state(source.id) == ('pending' if failure_stage == 'source' else 'complete')
        assert app.state.cloud_memory_jobs.categories.list_for(source.id)['categories'] == []
        assert app.state.tasks.all_tasks() == tasks_before
        assert app.state.episodes.get(source.id).body == 'Synthetic original unchanged'
        assert b'synthetic-uncertain-key' not in app.state.cloud_memory_jobs.path.read_bytes()
        assert b'Synthetic original unchanged' not in app.state.mistral_source_budget.path.read_bytes()


def test_billed_source_validation_failure_keeps_rejected_result_out_of_memory_and_tasks(monkeypatch):
    from icarus_memory.mistral_import_provider import MistralImportProvider
    from icarus_memory.working_memory_store import WorkingMemoryStore
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-invalid-passphrase')
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': MODEL, 'max_context_length': 16000,
                'capabilities': {'completion_chat': True}}]})
        return httpx.Response(200, json={'model': MODEL,
            'usage': {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280},
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{"items":[]}'}}]})
    monkeypatch.setattr(MistralImportProvider, '_client', lambda _: httpx.Client(
        transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False))
    app = create_app()
    with TestClient(app) as client:
        client.put('/api/v1/models/cloud-access/mistral', json={'api_key': 'synthetic-invalid-key', 'model': 'chat-model'})
        source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic invalid source', 'Synthetic source still authoritative',
            Provenance(SourceType.EMAIL, source_ref='synthetic:invalid'))
        tasks_before = app.state.tasks.all_tasks()
        budget = client.get('/api/v1/memory/cloud/budget?provider=mistral').json()
        client.put('/api/v1/memory/cloud/budget', json={'provider': 'mistral', 'cap_microusd': 1000000,
            'expected_revision': budget['revision'], 'consent': True})
        preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral', 'source_ids': [source.id]}).json()
        started = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral', 'model': MODEL,
            'preview_id': preview['preview_id'], 'consent': True})
        job_id = started.json()['job']['id']
        app.state.cloud_memory_jobs._threads[job_id].join(10)
        result = client.get('/api/v1/memory/cloud/status').json()['job']
        assert result['state'] == 'stopped' and result['failed'] == 1
        assert result['budget']['spent_microusd'] > 0 and result['budget']['held_microusd'] == 0
        assert WorkingMemoryStore(app.state.episodes).source_state(source.id) == 'pending'
        assert app.state.tasks.all_tasks() == tasks_before
        assert app.state.episodes.get(source.id).body == 'Synthetic source still authoritative'
        assert calls == ['GET', 'POST']


def test_malformed_budget_body_never_echoes_sensitive_extra_input():
    with TestClient(create_app()) as client:
        response = client.put('/api/v1/memory/cloud/budget', json={
            'provider': 'mistral', 'cap_microusd': 'synthetic-sensitive-source-or-key',
            'expected_revision': 1, 'consent': True, 'private_note': 'synthetic-sensitive-source-or-key'})
        assert response.status_code == 422
        assert 'synthetic-sensitive-source-or-key' not in response.text
