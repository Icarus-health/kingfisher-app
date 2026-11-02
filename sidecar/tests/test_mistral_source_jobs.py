"""Existing explicit packages pin Mistral source credentials and durable budget identity."""
import json
import sqlite3

import pytest

from icarus_memory.cloud_memory import CloudMemoryError, CloudMemoryJobs
from icarus_memory.working_memory_store import WorkingMemoryStore
from .test_cloud_memory import ApiImportProvider, add_email, finish, setup

MODEL = 'mistral-small-2603'


class Budget:
    """Offline admission fixture; production-ledger behavior lives in its own suite."""
    def __init__(self, cap=1000000):
        self.value = {'provider': 'mistral', 'currency': 'USD', 'budget_id': 'synthetic-budget',
                      'revision': 1, 'price_id': 'synthetic-price', 'price_valid_until': '2026-12-02',
                      'cap_microusd': cap, 'spent_microusd': 0, 'held_microusd': 0,
                      'remaining_microusd': cap, 'reconciliation_required': False,
                      'ready': cap > 0, 'blocked_reason': None if cap else 'budget_exhausted'}
    def status(self):
        return dict(self.value)
    def matches(self, budget_id, revision, price_id):
        return (budget_id, revision, price_id) == (self.value['budget_id'], self.value['revision'], self.value['price_id']) and not self.value['reconciliation_required']


def mistral_setup(tmp_path, cap=1000000):
    episodes, _, grant, _ = setup(tmp_path)
    budget = Budget(cap)
    credential = {'available': True, 'credential_revision': 'revision-one', 'model': MODEL}
    provider = ApiImportProvider()
    provider.name, provider.model = 'mistral', MODEL
    built = []
    def factory(identifier, model, **kwargs):
        built.append((identifier, model, kwargs))
        return provider
    jobs = CloudMemoryJobs(episodes, tmp_path / 'mistral-jobs.sqlite3',
                          lambda _: pytest.fail('No ChatGPT fallback'), lambda: grant,
                          api_provider_factory=factory, credential_status=lambda _: dict(credential),
                          mistral_budget=budget)
    return episodes, jobs, credential, provider, budget, built


def test_mistral_preview_with_zero_budget_is_offline_and_start_cannot_build_provider(tmp_path):
    episodes, jobs, _, provider, budget, built = mistral_setup(tmp_path, cap=0)
    add_email(episodes)
    preview = jobs.preview(provider='mistral')
    assert preview['provider'] == 'mistral' and preview['import_model'] == MODEL
    assert preview['budget'] == budget.status()
    assert preview['budget_revision'] == 1
    assert not preview['budget']['ready']
    with pytest.raises(CloudMemoryError):
        jobs.start(preview['preview_id'], MODEL, True, provider='mistral')
    assert not built and not provider.calls and jobs.status()['job'] is None


def test_mistral_job_passes_pinned_budget_to_only_its_factory_and_bulk_recognizes_result(tmp_path):
    episodes, jobs, _, provider, budget, built = mistral_setup(tmp_path)
    source = add_email(episodes)
    preview = jobs.preview(source_ids=[source.id], provider='mistral')
    assert not built and not provider.calls
    started = jobs.start(preview['preview_id'], MODEL, True, provider='mistral')
    result = finish(jobs, started['job']['id'])
    assert result['state'] == 'complete', result
    assert result['budget'] == budget.status()
    stored = jobs._job(result['id'])
    assert (stored['budget_id'], stored['budget_revision'], stored['price_id']) == ('synthetic-budget', 1, 'synthetic-price')
    assert built == [('mistral', MODEL, {'job_id': result['id'], 'budget_id': 'synthetic-budget',
                                      'budget_revision': 1, 'price_id': 'synthetic-price'})]
    assert WorkingMemoryStore(episodes).source_state(source.id) == 'complete'
    assert jobs.preview('bulk', provider='mistral')['count'] == 0


@pytest.mark.parametrize('change', ['revision', 'budget_id', 'price_id', 'held'])
def test_changed_or_held_budget_rejects_review_before_factory(tmp_path, change):
    episodes, jobs, _, provider, budget, built = mistral_setup(tmp_path)
    add_email(episodes)
    preview = jobs.preview(provider='mistral')
    if change == 'held':
        budget.value.update(reconciliation_required=True, ready=False, blocked_reason='budget_uncertain')
    elif change == 'revision':
        budget.value[change] += 1
    else:
        budget.value[change] += '-changed'
    with pytest.raises(CloudMemoryError):
        jobs.start(preview['preview_id'], MODEL, True, provider='mistral')
    assert not built and not provider.calls


def test_mistral_fixed_model_and_preview_provider_cannot_be_rebound(tmp_path):
    episodes, jobs, _, provider, _, built = mistral_setup(tmp_path)
    add_email(episodes)
    preview = jobs.preview(provider='mistral')
    for model, identifier in [('ordinary-chat-model', 'mistral'), (MODEL, 'anthropic')]:
        with pytest.raises(CloudMemoryError):
            jobs.start(preview['preview_id'], model, True, provider=identifier)
    assert not built and not provider.calls


@pytest.mark.parametrize('change', ['key', 'budget'])
def test_mistral_resume_requires_fresh_review_after_key_or_budget_change(tmp_path, change):
    episodes, jobs, credential, provider, budget, _ = mistral_setup(tmp_path)
    add_email(episodes)
    provider.on_call = lambda _: jobs.pause(jobs._latest_id())
    preview = jobs.preview(provider='mistral')
    started = jobs.start(preview['preview_id'], MODEL, True, provider='mistral')
    job_id = started['job']['id']
    assert finish(jobs, job_id)['state'] == 'paused'
    if change == 'key':
        credential['credential_revision'] = 'revision-two'
    else:
        budget.value['revision'] += 1
    with pytest.raises(CloudMemoryError):
        jobs.resume(job_id)
    assert jobs.status(job_id)['job']['state'] == 'stopped'
    assert jobs._job(job_id)['consent'] == 0
    if change == 'budget':
        assert 'budget' in jobs.status(job_id)['job']['stop_reason'].lower()
    assert len(provider.calls) == 1


def test_mistral_budget_change_during_response_prevents_source_write_and_second_send(tmp_path):
    episodes, jobs, _, provider, budget, _ = mistral_setup(tmp_path)
    source = add_email(episodes)
    provider.on_call = lambda _: budget.value.update(revision=2)
    preview = jobs.preview(provider='mistral')
    result = finish(jobs, jobs.start(preview['preview_id'], MODEL, True, provider='mistral')['job']['id'])
    assert result['state'] == 'stopped'
    assert len(provider.calls) == 1
    assert WorkingMemoryStore(episodes).source_state(source.id) == 'pending'
    assert not jobs.categories.list_for(source.id)['categories']


def test_legacy_rows_gain_nullable_budget_fields_and_remain_readable(tmp_path):
    episodes, old, grant, provider = setup(tmp_path)
    add_email(episodes)
    preview = old.preview()
    job_id = old.start(preview['preview_id'], provider.model, True)['job']['id']
    assert finish(old, job_id)['state'] == 'complete'
    with sqlite3.connect(old.path) as connection:
        for table in ('cloud_memory_previews', 'cloud_memory_jobs'):
            for field in ('budget_id', 'budget_revision', 'price_id'):
                connection.execute(f'ALTER TABLE {table} DROP COLUMN {field}')
    jobs = CloudMemoryJobs(episodes, old.path, lambda _: provider, lambda: grant, mistral_budget=Budget())
    stored = jobs._job(job_id)
    assert all(stored[field] is None for field in ('budget_id', 'budget_revision', 'price_id'))
    result = jobs.status(job_id)['job']
    assert result['provider'] == 'chatgpt' and result['state'] == 'complete'
    assert 'budget' not in result


def test_mistral_budget_storage_failure_does_not_prevent_source_revocation_or_job_readback(tmp_path, monkeypatch):
    from icarus_memory.cloud_import_budget import MistralBudgetError
    episodes, jobs, _, provider, budget, _ = mistral_setup(tmp_path)
    add_email(episodes)
    provider.on_call = lambda _: jobs.pause(jobs._latest_id())
    preview = jobs.preview(provider='mistral')
    job_id = jobs.start(preview['preview_id'], MODEL, True, provider='mistral')['job']['id']
    assert finish(jobs, job_id)['state'] == 'paused'
    def unavailable():
        raise MistralBudgetError('budget_unavailable')
    monkeypatch.setattr(budget, 'status', unavailable)
    result = jobs.pause(job_id, revoke=True)['job']
    assert result['state'] == 'stopped' and jobs._job(job_id)['consent'] == 0
    assert result['budget_id'] == 'synthetic-budget' and 'budget' not in result
    assert jobs.status(job_id)['job'] == result
    assert len(provider.calls) == 1
