"""Every HTTP byte below is synthetic and handled by httpx.MockTransport."""
import copy
import importlib
import json

import httpx
import pytest


MODEL = 'mistral-small-2603'
ENDPOINT = 'https://api.eu.mistral.ai/v1'
MESSAGES = [{'role': 'system', 'content': 'Synthetic instructions'},
            {'role': 'user', 'content': 'Synthetic private source'}]
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
          'properties': {'items': {'type': 'array', 'maxItems': 12, 'items': {
              'type': 'object', 'additionalProperties': False, 'required': ['quote'],
              'properties': {'quote': {'type': 'string', 'minLength': 1}}}}}}


def module():
    return importlib.import_module('icarus_memory.mistral_import_provider')


def metadata(context=262144):
    return {'object': 'list', 'data': [{'id': MODEL, 'max_context_length': context,
                                      'capabilities': {'completion_chat': True}}]}


def envelope():
    return {'id': 'synthetic-reply', 'object': 'chat.completion', 'model': MODEL,
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': '{"items":[]}'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
            'service_tier': 'standard'}


def prepared(tmp_path, monkeypatch, handler=None, cap=1_000_000):
    ledger_module = importlib.import_module('icarus_memory.cloud_import_budget')
    ledger = ledger_module.MistralSourceBudget(tmp_path / 'budget.sqlite3')
    if cap:
        ledger.set_total_cap(cap, ledger.status()['revision'])
    state = ledger.status()
    permission, revision, calls, counts = [True], ['one'], [], []
    def route(request):
        calls.append(request)
        if handler:
            response = handler(request)
            if response is not None:
                return response
        return httpx.Response(200, json=metadata() if request.method == 'GET' else envelope())
    monkeypatch.setattr(module().MistralImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(route), trust_env=False, follow_redirects=False))
    provider = module().MistralImportProvider(MODEL, 'synthetic-secret', 'one', lambda: revision[0],
        budget=ledger, job_id='synthetic-job', budget_id=state['budget_id'],
        budget_revision=state['revision'], price_id=state['price_id'])
    def complete(**kwargs):
        arguments = dict(max_tokens=300, schema=SCHEMA, before_send=lambda: counts.append('counted'),
                         still_permitted=lambda: permission[0])
        arguments.update(kwargs)
        return provider.complete_json_guarded(MESSAGES, **arguments)
    return provider, ledger, calls, counts, permission, revision, complete


def test_no_hidden_probe_then_exact_eu_model_schema_and_billing(monkeypatch, tmp_path):
    provider, ledger, calls, counts, _, _, complete = prepared(tmp_path, monkeypatch)
    assert provider.available() and calls == []
    before = ledger.status()
    result = complete()
    assert result.text == '{"items":[]}' and result.model == MODEL
    assert [(call.method, str(call.url)) for call in calls] == [('GET', ENDPOINT + '/models'),
                                                               ('POST', ENDPOINT + '/chat/completions')]
    assert not calls[0].content and 'Synthetic' not in str(calls[0].url)
    payload = json.loads(calls[1].content)
    assert payload == {'model': MODEL, 'messages': MESSAGES, 'max_tokens': 300, 'n': 1,
        'stream': False, 'temperature': 0, 'reasoning_effort': 'none', 'service_tier': 'standard_only',
        'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'memory_result', 'strict': True, 'schema': SCHEMA}}}
    assert calls[1].headers['authorization'] == 'Bearer synthetic-secret'
    assert calls[1].headers['content-type'] == 'application/json'
    assert counts == ['counted']
    assert ledger.status()['spent_microusd'] == 30
    assert ledger.status()['held_microusd'] == 0
    complete()  # context metadata cache is local to this adapter only
    assert [call.method for call in calls] == ['GET', 'POST', 'POST']
    assert ledger.status()['spent_microusd'] == 60
    assert ledger.status()['budget_id'] == before['budget_id']


def test_client_disables_environment_redirects_and_has_finite_timeout(monkeypatch, tmp_path):
    captured = []
    actual = httpx.Client
    def factory(*args, **kwargs):
        captured.append(kwargs)
        return actual(*args, **kwargs)
    monkeypatch.setattr(httpx, 'Client', factory)
    ledger_module = importlib.import_module('icarus_memory.cloud_import_budget')
    ledger = ledger_module.MistralSourceBudget(tmp_path / 'budget.sqlite3')
    state = ledger.status()
    provider = module().MistralImportProvider(MODEL, 'synthetic-secret', 'one', lambda: 'one',
        budget=ledger, job_id='synthetic-job', budget_id=state['budget_id'],
        budget_revision=state['revision'], price_id=state['price_id'])
    with provider._client():
        pass
    assert captured == [{'timeout': 90, 'trust_env': False, 'follow_redirects': False}]


@pytest.mark.parametrize('maximum,schema', [(True, SCHEMA), (63, SCHEMA), (1201, SCHEMA),
                                           (300.0, SCHEMA), (300, []), (300, {'type': 'array'})])
def test_invalid_request_does_not_probe_or_reserve(monkeypatch, tmp_path, maximum, schema):
    _, ledger, calls, counts, _, _, complete = prepared(tmp_path, monkeypatch)
    with pytest.raises(module().MistralBudgetError) as error:
        complete(max_tokens=maximum, schema=schema)
    assert error.value.code == 'invalid_request'
    assert calls == counts == [] and ledger.status()['held_microusd'] == 0


@pytest.mark.parametrize('context', [None, True, '262144', 0, -1, 262144.0])
def test_missing_or_ambiguous_numeric_context_never_posts(monkeypatch, tmp_path, context):
    def handler(request):
        return httpx.Response(200, json=metadata(context))
    _, ledger, calls, counts, _, _, complete = prepared(tmp_path, monkeypatch, handler)
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert error.value.code == 'metadata_unavailable'
    assert [call.method for call in calls] == ['GET'] and counts == []
    assert ledger.status()['held_microusd'] == 0


@pytest.mark.parametrize('data', [[], {'data': []}, {'data': [metadata()['data'][0]] * 2},
    {'data': [{'id': MODEL, 'max_context_length': 262144, 'capabilities': {'completion_chat': False}}]},
    {'data': [{'id': 'mistral-small-latest', 'max_context_length': 262144,
               'capabilities': {'completion_chat': True}}]}])
def test_metadata_requires_exact_unique_model_with_chat_capability(monkeypatch, tmp_path, data):
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch,
        lambda request: httpx.Response(200, json=data))
    with pytest.raises(module().MistralBudgetError):
        complete()
    assert len(calls) == 1 and calls[0].method == 'GET'
    assert ledger.status()['held_microusd'] == 0


def test_budget_zero_and_wrong_model_never_probe(monkeypatch, tmp_path):
    provider, _, calls, _, _, _, complete = prepared(tmp_path, monkeypatch, cap=0)
    assert not provider.available()
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert error.value.code == 'budget_exhausted' and calls == []
    provider.model = 'mistral-small-latest'
    with pytest.raises(module().MistralBudgetError):
        complete()
    assert calls == []


@pytest.mark.parametrize('when', ['client', 'metadata', 'count', 'dispatch'])
@pytest.mark.parametrize('what', ['permission', 'credential', 'budget'])
def test_revocation_at_every_pre_send_boundary_never_posts(monkeypatch, tmp_path, when, what):
    provider, ledger, calls, counts, permission, revision, complete = prepared(tmp_path, monkeypatch)
    def revoke():
        if what == 'permission':
            permission[0] = False
        elif what == 'credential':
            revision[0] = 'changed'
        else:
            ledger.set_total_cap(2_000_000, ledger.status()['revision'])
    if when == 'client':
        original = provider._client
        def client():
            revoke()
            return original()
        monkeypatch.setattr(provider, '_client', client)
    if when == 'metadata':
        monkeypatch.setattr(provider, '_client', lambda: httpx.Client(transport=httpx.MockTransport(
            lambda request: (calls.append(request), revoke(), httpx.Response(200, json=metadata()))[-1])))
    if when == 'count':
        def count():
            counts.append('counted')
            revoke()
    else:
        count = lambda: counts.append('counted')
    if when == 'dispatch':
        original = ledger.dispatch
        def dispatch(reservation):
            original(reservation)
            revoke()
        monkeypatch.setattr(ledger, 'dispatch', dispatch)
    with pytest.raises(module().MistralBudgetError):
        complete(before_send=count)
    assert all(request.method == 'GET' for request in calls)
    assert ledger.status()['held_microusd'] == (43452 if when == 'dispatch' else 0)
    assert ledger.status()['reconciliation_required'] == (when == 'dispatch')


@pytest.mark.parametrize('what', ['permission', 'credential', 'budget'])
def test_revoked_inflight_response_settles_billing_but_withholds_content(monkeypatch, tmp_path, what):
    _, ledger, calls, _, permission, revision, complete = prepared(tmp_path, monkeypatch)
    def handler(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json=metadata())
        if what == 'permission':
            permission[0] = False
        elif what == 'credential':
            revision[0] = 'changed'
        else:
            ledger.set_total_cap(2_000_000, ledger.status()['revision'])
        return httpx.Response(200, json=envelope())
    # Replace just the mock boundary; all actual provider/ledger behavior remains.
    monkeypatch.setattr(module().MistralImportProvider, '_client', lambda self: httpx.Client(
        transport=httpx.MockTransport(handler)))
    with pytest.raises(module().MistralBudgetError):
        complete()
    assert ledger.status()['spent_microusd'] == 30 and ledger.status()['held_microusd'] == 0
    assert len(calls) == 2


@pytest.mark.parametrize('mutation', [
    lambda data: data['choices'][0].update(finish_reason='length'),
    lambda data: data['choices'][0].update(index=True),
    lambda data: data['choices'].append(copy.deepcopy(data['choices'][0])),
    lambda data: data['choices'][0]['message'].update(tool_calls=[{'id': 'tool'}]),
    lambda data: data['choices'][0]['message'].update(role='tool'),
    lambda data: data['choices'][0]['message'].update(content=[{'type': 'text', 'text': '{}'}]),
    lambda data: data['choices'][0]['message'].update(content='[]'),
    lambda data: data['choices'][0]['message'].update(content='{}{}'),
    lambda data: data['choices'][0]['message'].update(content='{"a":1,"a":2}'),
    lambda data: data['choices'][0]['message'].update(content='{"n":NaN}'),
    lambda data: data['choices'][0]['message'].update(content=''),
])
def test_billed_rejected_output_settles_but_never_returns_partial_result(monkeypatch, tmp_path, mutation):
    data = envelope()
    mutation(data)
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch,
        lambda request: httpx.Response(200, json=data) if request.method == 'POST' else None)
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert error.value.code == 'response_invalid'
    assert ledger.status()['spent_microusd'] == 30 and ledger.status()['held_microusd'] == 0
    assert len(calls) == 2


@pytest.mark.parametrize('mutation', [
    lambda data: data.pop('usage'),
    lambda data: data.update(model='mistral-small-latest'),
    lambda data: data.update(service_tier='priority'),
    lambda data: data.update(billing={'cost': 1}),
    lambda data: data['usage'].pop('total_tokens'),
    lambda data: data['usage'].update(prompt_tokens=True),
    lambda data: data['usage'].update(prompt_tokens=100.0),
    lambda data: data['usage'].update(total_tokens=121),
    lambda data: data['usage'].update(completion_tokens=301, total_tokens=401),
    lambda data: data['usage'].update(prompt_tokens=262145, total_tokens=262165),
    lambda data: data['usage'].update(prompt_audio_seconds=1),
    lambda data: data['usage'].update(completion_tokens=-1, total_tokens=99),
])
def test_unpriced_or_unknown_usage_stays_held_without_retry(monkeypatch, tmp_path, mutation):
    data = envelope()
    mutation(data)
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch,
        lambda request: httpx.Response(200, json=data) if request.method == 'POST' else None)
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert error.value.code == 'budget_uncertain'
    assert ledger.status()['held_microusd'] == 43452 and ledger.status()['reconciliation_required']
    with pytest.raises(module().MistralBudgetError):
        complete()
    assert len(calls) == 2 and ledger.status()['spent_microusd'] == 0


@pytest.mark.parametrize('status', [302, 401, 403, 429, 500])
def test_http_failure_is_one_shot_safe_and_keeps_full_dispatch(monkeypatch, tmp_path, status):
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch,
        lambda request: httpx.Response(status, headers={'location': 'https://other.example'},
            text='synthetic-secret private provider body') if request.method == 'POST' else None)
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert str(error.value) == 'provider_rejected'
    assert ledger.status()['reconciliation_required'] and len(calls) == 2


def test_timeout_duplicate_envelope_and_unbounded_reply_are_held(monkeypatch, tmp_path):
    for scenario in ('timeout', 'duplicate', 'oversized'):
        subdir = tmp_path / scenario
        def handler(request):
            if request.method == 'GET':
                return None
            if scenario == 'timeout':
                raise httpx.ReadTimeout('synthetic-secret', request=request)
            if scenario == 'duplicate':
                content = json.dumps(envelope()).replace('"usage":', '"usage":{},"usage":')
            else:
                content = json.dumps(envelope()).replace('synthetic-reply', 'x' * 1_100_000)
            return httpx.Response(200, content=content)
        _, ledger, calls, _, _, _, complete = prepared(subdir, monkeypatch, handler)
        with pytest.raises(module().MistralBudgetError) as error:
            complete()
        assert str(error.value) == 'budget_uncertain'
        assert ledger.status()['held_microusd'] == 43452
        assert len(calls) == 2


def test_known_counting_failure_cancels_only_unsent_reservation(monkeypatch, tmp_path):
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch)
    def count():
        raise RuntimeError('synthetic-secret private source')
    with pytest.raises(module().MistralBudgetError) as error:
        complete(before_send=count)
    assert str(error.value) == 'permission_changed'
    assert ledger.status()['held_microusd'] == 0 and not ledger.status()['reconciliation_required']
    assert len(calls) == 1 and calls[0].method == 'GET'


def test_ambiguous_dispatch_marker_failure_is_held_not_only_busy(monkeypatch, tmp_path):
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch)
    original = ledger.dispatch
    def ambiguous_dispatch(reservation):
        original(reservation)
        raise RuntimeError('synthetic-secret ambiguous durable marker')
    monkeypatch.setattr(ledger, 'dispatch', ambiguous_dispatch)
    with pytest.raises(module().MistralBudgetError):
        complete()
    assert ledger.status()['reconciliation_required']
    assert ledger.status()['blocked_reason'] == 'budget_uncertain'
    assert len(calls) == 1 and calls[0].method == 'GET'


def test_schema_non_json_keys_are_rejected_without_weakening(monkeypatch, tmp_path):
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch)
    schema = {'type': 'object', 'properties': {1: {'type': 'string'}}}
    with pytest.raises(module().MistralBudgetError) as error:
        complete(schema=schema)
    assert str(error.value) == 'invalid_request'
    assert calls == [] and ledger.status()['held_microusd'] == 0


def test_real_classification_category_and_repair_schemas_keep_separate_reservations(monkeypatch, tmp_path):
    from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
    from icarus_memory.memory_categories import _DEFAULTS, _interpret, _schema
    from icarus_memory.source_processing_policy import ExplicitSourcePolicy, ScopedProvider
    from icarus_memory.working_memory_analysis import _classification_schema, interpret
    provider, ledger, calls, _, _, _, _ = prepared(tmp_path, monkeypatch)
    sources = EpisodeStore(tmp_path / 'sources.sqlite3')
    try:
        source = sources.record(EpisodeKind.MESSAGE, 'Synthetic evidence source',
            'Beleg https://example.de.\n\nExample.de ist ein Handelsname.',
            Provenance(SourceType.EMAIL, source_ref='mail:synthetic-budget'))[0]
        original = source.to_dict()
        taxonomy = [{'id': row[0], 'label': row[1], 'description': row[2]} for row in _DEFAULTS]
        packets, categories, counts = [], [], []
        def route(request):
            calls.append(request)
            if request.method == 'GET':
                return httpx.Response(200, json=metadata())
            state = ledger.status()
            assert state['held_microusd'] == 44046
            assert not state['reconciliation_required']
            assert ledger.matches(state['budget_id'], state['revision'], state['price_id'])
            packet = json.loads(request.content)
            schema = packet['response_format']['json_schema']['schema']
            payload = json.loads(packet['messages'][-1]['content'])
            packets.append((schema, payload))
            if 'items' in schema['properties']:
                assert schema == _classification_schema(2)
                output = {'items': {'B1': 'fact', 'B2': 'fact'}}
            else:
                assert schema == _schema(taxonomy, 'block_quote')
                categories.append(payload)
                output = {'categories': [{'category_id': 'finance', 'block_id': 'B1'}], 'entities': [
                    {'kind': 'organization', 'name': 'Example.de', 'block_id': 'B1' if len(categories) == 1 else 'B2',
                     'occurrence': 1, 'role': 'mentioned'}]}
            data = envelope()
            data['choices'][0]['message']['content'] = json.dumps(output)
            return httpx.Response(200, json=data)
        monkeypatch.setattr(provider, '_client', lambda: httpx.Client(transport=httpx.MockTransport(route)))
        scoped = ScopedProvider(provider, None, lambda: counts.append('counted'))
        scoped._episode = source
        policy = ExplicitSourcePolicy(scoped, source.id, lambda episode: episode.id == source.id)
        scoped._policy = policy
        blocks = interpret(scoped, source, policy=policy)
        topics, entities = _interpret(scoped, source, taxonomy, policy=policy)
        assert len(blocks) == 2 and len(topics) == len(entities) == 1
        assert entities[0] == ('organization', source.body.index('Example.de'),
                               source.body.index('Example.de') + len('Example.de'), 'mentioned')
        assert len(counts) == len(packets) == 3
        assert [request.method for request in calls] == ['GET', 'POST', 'POST', 'POST']
        assert categories[1]['validation_failure']['code'] == 'invalid_entity_evidence'
        assert categories[0]['blocks'] == categories[1]['blocks']
        assert sources.get(source.id).to_dict() == original
        assert ledger.status()['spent_microusd'] == 90
        assert ledger.status()['held_microusd'] == 0
    finally:
        sources.close()


def test_durable_settlement_failure_keeps_full_reservation(monkeypatch, tmp_path):
    import sqlite3
    _, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch)
    with sqlite3.connect(tmp_path / 'budget.sqlite3') as connection:
        connection.execute("""CREATE TRIGGER synthetic_write_failure BEFORE UPDATE ON mistral_reservations
            WHEN NEW.state='settled' BEGIN SELECT RAISE(ABORT, 'synthetic-secret'); END""")
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert str(error.value) == 'budget_unavailable'
    assert ledger.status()['reconciliation_required']
    assert ledger.status()['held_microusd'] == 43452 and ledger.status()['spent_microusd'] == 0
    assert len(calls) == 2


def test_transport_data_and_provider_errors_do_not_enter_budget_database(monkeypatch, tmp_path):
    _, ledger, _, _, _, _, complete = prepared(tmp_path, monkeypatch,
        lambda request: httpx.Response(500, text='synthetic-secret private provider body')
        if request.method == 'POST' else None)
    with pytest.raises(module().MistralBudgetError):
        complete()
    raw = ledger.path.read_bytes()
    for secret in (b'synthetic-secret', b'private provider body', b'Synthetic private source', b'Synthetic instructions'):
        assert secret not in raw


@pytest.mark.parametrize('job_id', [None, '', 'Synthetic private source!', True])
def test_adapter_without_opaque_job_identity_is_unavailable_and_never_probes(monkeypatch, tmp_path, job_id):
    provider, ledger, calls, _, _, _, complete = prepared(tmp_path, monkeypatch)
    provider._job_id = job_id
    assert not provider.available()
    with pytest.raises(module().MistralBudgetError) as error:
        complete()
    assert str(error.value) == 'invalid_request'
    assert calls == [] and ledger.status()['held_microusd'] == 0
