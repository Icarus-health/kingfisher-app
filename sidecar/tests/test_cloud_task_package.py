"""Source-bound Mistral tasks use the existing proposals, never the local model.

All provider traffic goes through MockTransport; there is no external request.
"""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.secrets import PASSPHRASE_ENV
from icarus_memory.server import create_app
from icarus_memory.task_review import REVIEW_MARKER

MODEL = 'mistral-small-2603'
QUOTE = 'Bitte sende mir das Angebot bis zum 30.11.2026 um 14:30 Uhr.'
MEETING = 'Unser Treffen ist am 28.11.2026 um 10:00 Uhr.'


@pytest.fixture
def package(monkeypatch):
    from icarus_memory.mistral_import_provider import MistralImportProvider
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-task-package')
    state = {'calls': [], 'hook': lambda stage: None}

    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': MODEL, 'max_context_length': 16000,
                'capabilities': {'completion_chat': True}}]})
        payload = json.loads(request.content)
        source = json.loads(payload['messages'][-1]['content'])
        schema = payload['response_format']['json_schema']['schema']
        if 'blocks' in source and 'items' in schema['properties']:
            stage, result = 'source', {'items': {b['block_id']: 'fact' for b in source['blocks']}}
        elif 'categories' in schema['properties']:
            stage, result = 'categories', {'categories': [], 'entities': []}
        elif 'reviews' in schema['properties']:
            stage, result = 'review', {'reviews': [
                {'id': i, 'kind': 'request_to_recipient' if item['quote'] == QUOTE else 'information',
                 'title_supported': True} for i, item in enumerate(source['candidates'])]}
        else:
            stage, result = 'tasks', {'items': [
                {'title': quote, 'quote': quote} for quote in [QUOTE, MEETING] if quote in source['body']]}
        if state.get('bad_review') and stage == 'review':
            result = {'reviews': []}
        state['calls'].append((stage, payload))
        state['hook'](stage)
        return httpx.Response(200, json={'model': MODEL, 'service_tier': 'standard',
            'usage': {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280},
            'choices': [{'index': 0, 'finish_reason': 'stop',
                        'message': {'role': 'assistant', 'content': json.dumps(result)}}]})

    monkeypatch.setattr(MistralImportProvider, '_client', lambda _: httpx.Client(
        transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False))
    app = create_app()
    with TestClient(app) as client:
        assert client.put('/api/v1/models/cloud-access/mistral', json={
            'api_key': 'synthetic-key', 'model': 'ordinary-chat-model'}).status_code == 200
        budget = client.get('/api/v1/memory/cloud/budget?provider=mistral').json()
        assert client.put('/api/v1/memory/cloud/budget', json={'provider': 'mistral',
            'cap_microusd': 1000000, 'expected_revision': budget['revision'], 'consent': True}).status_code == 200
        original, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Angebot von Anna Berg',
            f'Hallo Sören,\n{QUOTE}\n{MEETING}\nViele Grüße\nAnna Berg',
            Provenance(SourceType.EMAIL, source_ref='synthetic:selected'),
            contacts=[{'rolle': 'von', 'adresse': 'anna@example.test', 'name': 'Anna Berg'},
                      {'rolle': 'an', 'adresse': 'soeren@example.test', 'name': 'Sören', 'ich': True}])
        other, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'NOT APPROVED', 'UNSELECTED PRIVATE BODY',
            Provenance(SourceType.EMAIL, source_ref='synthetic:other'))
        state.update(app=app, client=client, original=original, other=other)
        yield state


def run(package, *, include_tasks=True):
    client = package['client']
    response = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral',
        'source_ids': [package['original'].id], 'include_tasks': include_tasks})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['include_tasks'] is include_tasks
    assert package['calls'] == []
    response = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral',
        'preview_id': preview['preview_id'], 'model': MODEL, 'consent': True})
    assert response.status_code == 200, response.text
    jobs = package['app'].state.cloud_memory_jobs
    job_id = response.json()['job']['id']
    jobs._threads[job_id].join(10)
    assert not jobs._threads[job_id].is_alive()
    return jobs.status(job_id)['job']


def test_selected_package_extracts_and_reviews_tasks_with_same_cost_limit(package):
    state = package['app'].state
    before_cursor = state.proposals.task_scan_cursor()
    result = run(package)
    assert result['state'] == 'complete', result
    assert result['include_tasks'] is True
    assert result['quality_verified'] is False
    assert [stage for stage, _ in package['calls']] == ['source', 'categories', 'tasks', 'review']
    assert result['requests'] == 4 <= result['request_limit']
    assert result['budget']['spent_microusd'] > 0
    assert result['budget']['held_microusd'] == 0
    assert 'UNSELECTED PRIVATE BODY' not in json.dumps(package['calls'])
    assert state.proposals.task_scan_cursor() == before_cursor
    proposals = state.proposals.pending(ProposalKind.TASK)
    assert len(proposals) == 1
    assert proposals[0].evidence[0].episode_id == package['original'].id
    assert proposals[0].evidence[0].quote == QUOTE
    assert proposals[0].statement == QUOTE
    assert proposals[0].proposed_by.endswith(REVIEW_MARKER)
    assert state.tasks.get(f't-suggestion-{proposals[0].id}') is None
    assert state.proposals.memory_analysis.snapshot(package['other'].id) is None


def test_source_only_consent_does_not_silently_gain_task_calls(package):
    result = run(package, include_tasks=False)
    assert result['state'] == 'complete'
    assert [stage for stage, _ in package['calls']] == ['source', 'categories']
    assert package['app'].state.proposals.pending(ProposalKind.TASK) == []


@pytest.mark.parametrize('stage', ['tasks', 'review'])
def test_revocation_during_task_call_discards_result(package, stage):
    def revoke(actual):
        if actual == stage:
            package['app'].state.cloud_memory_jobs.pause(revoke=True)
    package['hook'] = revoke
    result = run(package)
    assert result['state'] == 'stopped'
    assert result['completed'] == 0
    assert package['app'].state.proposals.pending(ProposalKind.TASK) == []
    assert package['calls'][-1][0] == stage


def test_withdrawn_source_is_not_reported_as_complete(package):
    # The transport callback changes the current source after extraction. A
    # review with an obsolete source must never be issued or saved.
    def change(stage):
        if stage == 'tasks':
            package['app'].state.episodes.ignore(package['original'].id)
    package['hook'] = change
    result = run(package)
    assert result['state'] == 'paused'
    assert result['completed'] == 0
    assert package['app'].state.proposals.pending(ProposalKind.TASK) == []
    assert package['calls'][-1][0] == 'tasks'


def test_task_scope_requires_strict_boolean_and_mistral(package):
    for value in ['true', 1, None]:
        assert package['client'].post('/api/v1/memory/cloud/preview', json={
            'provider': 'mistral', 'include_tasks': value}).status_code == 422
    response = package['client'].post('/api/v1/memory/cloud/preview', json={
        'provider': 'anthropic', 'include_tasks': True})
    assert response.status_code == 409
    assert package['calls'] == []


def test_source_only_completed_mail_is_not_skipped_when_tasks_are_requested(package):
    assert run(package, include_tasks=False)['state'] == 'complete'
    client = package['client']
    preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral',
        'purpose': 'bulk', 'source_ids': [package['original'].id], 'include_tasks': True}).json()
    assert preview['count'] == 1
    package['calls'].clear()
    assert run(package)['state'] == 'complete'
    preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral',
        'purpose': 'bulk', 'source_ids': [package['original'].id], 'include_tasks': True}).json()
    assert preview['count'] == 0


def test_old_source_only_pilot_cannot_unlock_bulk_with_new_task_scope(package):
    assert run(package, include_tasks=False)['state'] == 'complete'
    client = package['client']
    preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral',
        'purpose': 'bulk', 'source_ids': [package['original'].id], 'include_tasks': True}).json()
    response = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral',
        'preview_id': preview['preview_id'], 'model': MODEL, 'consent': True})
    if response.status_code == 200:
        package['app'].state.cloud_memory_jobs._threads[response.json()['job']['id']].join(10)
    assert response.status_code == 409, response.text
    assert [stage for stage, _ in package['calls']] == ['source', 'categories']


@pytest.mark.parametrize('incomplete', [False, True])
def test_only_complete_task_pilot_unlocks_task_bulk(package, incomplete):
    if incomplete:
        package['original'] = package['app'].state.episodes.record(EpisodeKind.MESSAGE, 'Lange Mail',
            'Weiterer künstlicher Satz.\n' * 800, Provenance(SourceType.EMAIL, source_ref='synthetic:pilot-gap'))[0]
    result = run(package)
    assert result['state'] == ('complete_with_gaps' if incomplete else 'complete')
    client = package['client']
    preview = client.post('/api/v1/memory/cloud/preview', json={'provider': 'mistral',
        'purpose': 'bulk', 'source_ids': [package['other'].id], 'include_tasks': True}).json()
    response = client.post('/api/v1/memory/cloud/start', json={'provider': 'mistral',
        'preview_id': preview['preview_id'], 'model': MODEL, 'consent': True})
    if response.status_code == 200:
        jobs = package['app'].state.cloud_memory_jobs
        job_id = response.json()['job']['id']
        jobs._threads[job_id].join(10)
        assert jobs.status(job_id)['job']['state'] == 'complete'
    assert response.status_code == (409 if incomplete else 200), response.text


def test_rejected_task_stays_rejected_after_metadata_change(package):
    assert run(package)['state'] == 'complete'
    state = package['app'].state
    proposal = state.proposals.pending(ProposalKind.TASK)[0]
    state.proposals.reject(proposal.id)
    from icarus_memory.task_review import current_task_context
    previous = current_task_context(state.episodes, package['original'].id)
    changed = state.episodes.get(package['original'].id)
    state.episodes.remove_contacts(changed.id, [changed.contacts[0]], [])
    assert current_task_context(state.episodes, changed.id) != previous
    package['calls'].clear()
    assert run(package)['state'] == 'complete'
    assert any(stage == 'tasks' for stage, _ in package['calls'])
    assert state.proposals.pending(ProposalKind.TASK) == []
    assert state.proposals.get(proposal.id).state.value == 'rejected'


def test_invalid_review_never_produces_task_or_full_completion(package):
    package['bad_review'] = True
    result = run(package)
    assert result['state'] == 'stopped'
    assert result['completed'] == 0
    assert 'Aufgabenprüfung' in result['stop_reason']
    assert package['app'].state.proposals.pending(ProposalKind.TASK) == []


def test_long_mail_task_gap_is_visible_and_keeps_source_classification(package):
    state = package['app'].state
    source, _ = state.episodes.record(EpisodeKind.MESSAGE, 'Lange künstliche Mail',
        'Künstlicher weiterer Satz.\n' * 800, Provenance(SourceType.EMAIL, source_ref='synthetic:long'))
    package['original'] = source
    result = run(package)
    assert result['state'] == 'complete_with_gaps', result
    assert result['issues'] == [{'episode_id': source.id, 'stage': 'tasks', 'code': 'unsupported_source'}]
    assert state.cloud_memory_jobs.memory.source_state(source.id) == 'complete'
    assert not any(stage in ('tasks', 'review') for stage, _ in package['calls'])


def test_all_task_segments_are_reviewed_with_budget_planned_before_consent(package, monkeypatch):
    state = package['app'].state
    original = package['original']
    source, _ = state.episodes.record(EpisodeKind.MESSAGE, original.title,
        original.body + '\n' + ('Künstliche Zusatzinformation.\n' * 400),
        Provenance(SourceType.EMAIL, source_ref='synthetic:segments'), contacts=original.contacts)
    package['original'] = source
    # An explicitly selected package must not touch the scheduler's global work.
    for owner, names in [(state.proposals, ['task_scan_cursor', 'advance_task_scan']),
                         (state.episodes, ['task_recheck_budget', 'task_rechecks', 'finish_task_recheck'])]:
        for name in names:
            monkeypatch.setattr(owner, name, lambda *a, **kw: pytest.fail('global task scheduler touched'))
    from icarus_memory.task_detection import TaskDetector
    monkeypatch.setattr(TaskDetector, 'expire_sources', lambda *a: pytest.fail('global proposal expiry touched'))
    result = run(package)
    assert result['state'] == 'complete', result
    stages = [stage for stage, _ in package['calls']]
    assert stages.count('tasks') == 2
    assert stages.count('review') == 1
    assert result['requests'] <= result['request_limit']
    assert len(state.proposals.pending(ProposalKind.TASK)) == 1


def test_competing_task_lease_does_not_turn_no_progress_into_complete(package):
    from types import SimpleNamespace
    state = package['app'].state
    state.proposals.memory_analysis.acquire(package['other'], SimpleNamespace(name='synthetic', model='busy'))
    result = run(package)
    assert result['state'] == 'stopped'
    assert result['completed'] == 0
    assert [stage for stage, _ in package['calls']] == ['source', 'categories']
    assert state.proposals.pending(ProposalKind.TASK) == []


def test_changed_budget_during_tasks_pauses_and_discards_result(package):
    def change(stage):
        if stage == 'tasks':
            ledger = package['app'].state.mistral_source_budget
            budget = ledger.status()
            ledger.set_total_cap(0, budget['revision'])
    package['hook'] = change
    result = run(package)
    assert result['state'] == 'paused'
    assert result['completed'] == 0
    assert package['app'].state.proposals.pending(ProposalKind.TASK) == []
    assert package['calls'][-1][0] == 'tasks'


def test_explicit_empty_task_selection_never_falls_back_to_inventory(package, monkeypatch):
    from icarus_memory.task_detection import TaskDetector
    from threading import RLock
    from types import SimpleNamespace
    state = package['app'].state
    monkeypatch.setattr(state.episodes, 'analysis_batch', lambda *a: pytest.fail('inventory scan'))
    provider = SimpleNamespace(is_local=True, name='synthetic', model='never-called')
    report = TaskDetector(state.episodes, state.proposals, provider, RLock()).run(with_model=True, source_ids=[])
    assert report.analyzed == report.proposed == 0
    assert state.proposals.pending(ProposalKind.TASK) == []


def test_existing_issue_constraint_migrates_without_losing_records(tmp_path):
    import sqlite3
    from icarus_memory import EpisodeStore
    from icarus_memory.cloud_memory import CloudMemoryJobs
    path = tmp_path / 'old-jobs.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE cloud_memory_issues (job_id TEXT NOT NULL,episode_id TEXT NOT NULL,"
                   "stage TEXT NOT NULL CHECK(stage IN ('source','categories')),code TEXT NOT NULL,"
                   "PRIMARY KEY(job_id,episode_id))")
        db.execute("INSERT INTO cloud_memory_issues VALUES('old','source','categories','invalid_output_format')")
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        manager = CloudMemoryJobs(episodes, path, None, None)
        with manager._connect() as db:
            rows = db.execute('SELECT * FROM cloud_memory_issues').fetchall()
            assert [dict(row) for row in rows] == [{'job_id': 'old', 'episode_id': 'source',
                'stage': 'categories', 'code': 'invalid_output_format', 'reason': 'unspecified'}]
            db.execute("INSERT INTO cloud_memory_issues VALUES('new','source','tasks','unsupported_source','unspecified')")
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        CloudMemoryJobs(episodes, path, None, None)
        with manager._connect() as db:
            assert db.execute('SELECT COUNT(*) FROM cloud_memory_issues').fetchone()[0] == 2
    finally:
        episodes.close()
