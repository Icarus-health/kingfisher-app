"""Synthetic long-mail plans must fit their approved, restart-stable budget."""
import json
from copy import deepcopy
from datetime import datetime, timezone

import httpx
import pytest

from icarus_memory.cloud_import_provider import AnthropicImportProvider
from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.cloud_memory import CloudMemoryJobs
from icarus_memory.mail_filter import Decision
from icarus_memory.working_memory_analysis import interpret


class SubscriptionProvider:
    name, model, grant_id = 'chatgpt', 'subscription-test', 'grant-one'
    is_local, is_remote = False, True

    def __init__(self):
        self.calls = []

    def available(self):
        return True

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]['content'])
        self.calls.append(payload)
        value = ({'items': [{'block_id': b['block_id'], 'kind': 'fact'} for b in payload['blocks']]}
                 if 'items' in schema['properties'] else {'categories': [], 'entities': []})
        return type('Reply', (), {'text': json.dumps(value), 'tool_calls': []})()


def add_email(episodes, body='Synthetic mail text'):
    return episodes.record(EpisodeKind.MESSAGE, 'Synthetic mail', body,
        Provenance(SourceType.EMAIL, source_ref='mail:synthetic:' + str(len(body))),
        at=datetime(2026, 10, 19, tzinfo=timezone.utc))[0]


def setup(tmp_path, provider=None):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    provider = provider or SubscriptionProvider()
    grant = {'available': True, 'grant_id': 'grant-one'}
    jobs = CloudMemoryJobs(episodes, tmp_path / 'jobs.sqlite3', lambda model: provider, lambda: grant)
    return episodes, jobs, grant, provider


def finish(jobs, job_id):
    jobs._threads[job_id].join(timeout=5)
    assert not jobs._threads[job_id].is_alive()
    return jobs.status(job_id)['job']


def long_mail():
    return '\n\n'.join(f'Absatz {i}: Sachstand im Projekt.' for i in range(90))


def test_complex_mail_budget_is_planned_before_send_and_survives_restart(tmp_path):
    class Quotes(SubscriptionProvider):
        entity_anchor_mode = 'block_quote'

    provider = Quotes()
    episodes, jobs, grant, _ = setup(tmp_path, provider=provider)
    source = add_email(episodes, long_mail())
    preview = jobs.preview(source_ids=[source.id])
    assert not provider.calls
    assert preview['request_limit'] >= 8
    result = finish(jobs, jobs.start(preview['preview_id'], provider.model, True)['job']['id'])
    assert result['state'] == 'complete'
    assert result['completed'] == 1
    assert result['requests'] == 8
    assert result['request_limit'] == preview['request_limit']
    restored = CloudMemoryJobs(episodes, jobs.path, lambda model: provider, lambda: grant)
    assert restored.status(result['id'])['job']['request_limit'] == result['request_limit']


def test_subset_budget_does_not_inherit_unselected_long_sources(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    short = add_email(episodes)
    long = add_email(episodes, long_mail())
    preview = jobs.preview(source_ids=[short.id, long.id])
    result = finish(jobs, jobs.start(preview['preview_id'], provider.model, True, [short.id])['job']['id'])
    assert result['request_limit'] == 4
    assert result['selected'] == 1


def test_cloud_preview_applies_cheap_filter_without_model_or_source_changes(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    before = source.to_dict()
    jobs.source_screen = lambda episode: Decision(False, 'newsletter', 'sender_subject_marketing')
    preview = jobs.preview(source_ids=[source.id])
    assert preview['count'] == 0
    assert preview['filtered_count'] == 1
    assert preview['review_count'] == 0
    assert not provider.calls
    assert episodes.get(source.id).to_dict() == before


def test_filter_revocation_after_preview_prevents_paid_start(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    allowed = [True]
    jobs.source_screen = lambda episode: Decision(allowed[0], 'blocked')
    preview = jobs.preview(source_ids=[source.id])
    allowed[0] = False
    with pytest.raises(ValueError, match='Filter'):
        jobs.start(preview['preview_id'], provider.model, True)
    assert not provider.calls


def test_filter_revocation_during_request_keeps_result_out_of_memory(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    allowed = [True]
    jobs.source_screen = lambda episode: Decision(allowed[0], 'blocked')
    original = provider.complete_json
    def complete(*args, **kwargs):
        result = original(*args, **kwargs)
        allowed[0] = False
        return result
    provider.complete_json = complete
    preview = jobs.preview(source_ids=[source.id])
    result = finish(jobs, jobs.start(preview['preview_id'], provider.model, True)['job']['id'])
    assert result['state'] == 'stopped'
    assert result['completed'] == 0
    assert len(provider.calls) == 1


def test_classification_schema_requires_every_block_without_changing_old_reply_compatibility(tmp_path):
    class Reader:
        is_local = True

        def complete_json(self, messages, *, max_tokens, schema):
            requested = [b['block_id'] for b in json.loads(messages[-1]['content'])['blocks']]
            mapping = schema['properties']['items']
            assert mapping['type'] == 'object'
            assert mapping['required'] == requested
            assert mapping['additionalProperties'] is False
            return type('Reply', (), {'text': json.dumps({'items': {b: 'fact' for b in requested}}),
                                       'tool_calls': []})()

    episodes, _, _, _ = setup(tmp_path)
    result = interpret(Reader(), add_email(episodes, 'Ein Fakt.\n\nNoch ein Fakt.'))
    assert [item['kind'] for item in result] == ['fact', 'fact']


def test_anthropic_uses_strict_supported_schema_but_keeps_local_validator_constraints(monkeypatch):
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
              'properties': {'items': {'type': 'array', 'maxItems': 8, 'items': {
                  'type': 'object', 'additionalProperties': False, 'required': ['name', 'occurrence'],
                  'properties': {'name': {'type': 'string', 'minLength': 1, 'maxLength': 80},
                                 'occurrence': {'type': 'integer', 'minimum': 1, 'maximum': 20}}}}}}
    unchanged = deepcopy(schema)

    def handle(request):
        tool = json.loads(request.content)['tools'][0]
        assert tool['strict'] is True
        array = tool['input_schema']['properties']['items']
        assert 'maxItems' not in array
        fields = array['items']['properties']
        assert fields['name'] == {'type': 'string'}
        assert fields['occurrence'] == {'type': 'integer'}
        return httpx.Response(200, json={'stop_reason': 'tool_use', 'content': [
            {'type': 'tool_use', 'name': 'memory_result', 'input': {'items': []}}]})

    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(handle), trust_env=False, follow_redirects=False))
    provider = AnthropicImportProvider('claude-synthetic', 'synthetic', 'one', lambda: 'one')
    provider.complete_json_guarded([], max_tokens=300, schema=schema,
                                   before_send=lambda: None, still_permitted=lambda: True)
    assert schema == unchanged


@pytest.mark.parametrize('answer', [None, True, {'include': True}])
def test_unreadable_filter_holds_source_without_inference(tmp_path, answer):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    jobs.source_screen = lambda episode: answer
    preview = jobs.preview(source_ids=[source.id])
    assert preview['count'] == 0
    assert preview['review_count'] == 1
    assert not provider.calls


def test_filter_error_holds_source_without_inference(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    def unreadable(episode):
        raise RuntimeError('Synthetic unavailable filter')
    jobs.source_screen = unreadable
    preview = jobs.preview(source_ids=[source.id])
    assert preview['count'] == 0
    assert preview['review_count'] == 1
    assert not provider.calls


def test_legacy_job_ceiling_is_not_widened_by_new_planner(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    preview = jobs.preview(source_ids=[source.id])
    result = finish(jobs, jobs.start(preview['preview_id'], provider.model, True)['job']['id'])
    with jobs._connect() as db:
        db.execute('UPDATE cloud_memory_jobs SET request_limit=NULL WHERE id=?', (result['id'],))
    assert jobs.status(result['id'])['job']['request_limit'] == 4


def test_legacy_preview_requires_new_consent_without_creating_paid_job(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    source = add_email(episodes)
    preview = jobs.preview(source_ids=[source.id])
    with jobs._connect() as db:
        row = db.execute('SELECT sources FROM cloud_memory_previews WHERE id=?', (preview['preview_id'],)).fetchone()
        sources = json.loads(row[0])
        for item in sources:
            item.pop('planned_requests')
        db.execute('UPDATE cloud_memory_previews SET sources=? WHERE id=?', (json.dumps(sources), preview['preview_id']))
    with pytest.raises(ValueError, match='älteren Fassung'):
        jobs.start(preview['preview_id'], provider.model, True)
    assert not provider.calls
    assert jobs.status()['job'] is None


def test_required_block_mapping_rejects_duplicate_json_keys(tmp_path):
    from icarus_memory.providers import ProviderError, Reply
    class Ambiguous:
        is_local = True
        def complete_json(self, messages, **kwargs):
            return Reply(text='{"items":{"B1":"request","B1":"fact","B2":"fact"}}')
    episodes, _, _, _ = setup(tmp_path)
    source = add_email(episodes, 'Ein Fakt.\n\nNoch ein Fakt.')
    with pytest.raises(ProviderError, match='JSON'):
        interpret(Ambiguous(), source)
