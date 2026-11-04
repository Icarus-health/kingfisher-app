"""Offline mechanics only: artificial HTTP answers are not model quality."""
import importlib
import json
import shutil
import threading
import time

import httpx
import pytest


@pytest.fixture
def probe(monkeypatch):
    unexpected = []
    def deny(*_a, **_k):
        unexpected.append(True)
        raise AssertionError('Real HTTP forbidden')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', deny)
    assert importlib.util.find_spec('probe_mistral_memory_pilot'), 'Pilot CLI is missing'
    module = importlib.import_module('probe_mistral_memory_pilot')
    from icarus_memory.secrets import Keychain
    monkeypatch.setattr(Keychain, '__init__', lambda *_a, **_k: pytest.fail('Saved keys forbidden'))
    monkeypatch.delenv(module.KEY_ENV, raising=False)
    yield module
    assert not unexpected, 'Even failed probes must never try real HTTP'


def transport(*, missing_usage=False, hook=None):
    calls = []

    def handle(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': 'mistral-small-2603',
                'max_context_length': 16000, 'capabilities': {'completion_chat': True}}]})
        payload = json.loads(request.content)
        source = json.loads(payload['messages'][-1]['content'])
        schema = payload['response_format']['json_schema']['schema']['properties']
        if 'blocks' in source and 'items' in schema:
            stage, result = 'source', {'items': {b['block_id']: 'fact' for b in source['blocks']}}
        elif 'categories' in schema:
            stage, result = 'categories', {'categories': [], 'entities': []}
        elif 'reviews' in schema:
            stage, result = 'review', {'reviews': [{'id': i, 'kind': 'request_to_recipient',
                'title_supported': True} for i, _ in enumerate(source['candidates'])]}
        else:
            stage = 'tasks'
            quote = 'bitte schicke mir den Leuchtplan für den Pavillon Fenn bis 6. November 2026, 15:00 Uhr Berliner Zeit'
            result = {'items': [{'title': 'Leuchtplan schicken', 'quote': quote}]} if quote in source['body'] else {'items': []}
        calls.append((stage, payload, source))
        if hook:
            hook(stage)
        answer = {'model': 'mistral-small-2603', 'service_tier': 'standard',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': json.dumps(result)}}]}
        if not missing_usage:
            answer['usage'] = {'prompt_tokens': 200, 'completion_tokens': 80, 'total_tokens': 280}
        return httpx.Response(200, json=answer)

    return httpx.MockTransport(handle), calls


def run(probe, monkeypatch, **kwargs):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-pilot-only-key')
    return probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, **kwargs)


def test_default_cli_previews_exact_sources_without_credentials_network_or_classification(probe, tmp_path):
    output = tmp_path / 'preview.json'
    assert probe.main(['--output', str(output)]) == 0
    report = json.loads(output.read_text())
    assert report['execution_status'] == 'not_run'
    assert report['semantic_grade'] == 'requires_review'
    assert report['questions'] == 'not_run'
    assert report['preview']['include_tasks'] is True
    assert report['preview']['count'] == len(report['sources']) == 10
    assert report['inference_requests'] == report['metadata_requests'] == 0
    assert report['automatic_tasks'] == []
    assert all(row['working_memory_state'] == 'pending' for row in report['results'])
    sent = next(row for row in report['sources'] if row['id'] == 'P04')
    assert sent['folder'] == 'Sent'
    own = next(c for c in sent['original']['contacts'] if c.get('ich'))
    assert own['adresse'] == 'mika@studio-fenn.example' and own['rolle'] == 'von'
    assert sent['original']['occurred_at'] == '2026-11-03T10:00:00+01:00'
    assert all(s['body'].strip() == s['original']['body'].strip() for s in report['sources'])
    assert report['preview']['request_limit'] <= 60
    assert all(row['planned_request_upper_bound'] == 5 for row in report['sources'])
    assert probe.main(['--output', str(output)]) == 2


@pytest.mark.parametrize('options', [{}, {'allow_artificial_cloud': True},
    {'allow_artificial_cloud': True, 'cap_microusd': 0},
    {'allow_artificial_cloud': True, 'cap_microusd': True},
    {'allow_artificial_cloud': True, 'cap_microusd': 1000001},
    {'allow_artificial_cloud': True, 'cap_microusd': 1000000, 'max_requests': 61},
    {'allow_artificial_cloud': True, 'cap_microusd': 1000000, 'seconds': 601}])
def test_live_run_requires_explicit_dedicated_authority_before_stores(probe, monkeypatch, options):
    monkeypatch.setattr(probe, 'EpisodeStore', lambda *_: pytest.fail('Unauthorized store'))
    monkeypatch.setenv('MISTRAL_API_KEY', 'must-not-be-used')
    with pytest.raises(ValueError):
        probe.evaluate(**options)


def test_frozen_catalog_change_is_rejected_before_cloud(probe, monkeypatch, tmp_path):
    target = tmp_path / 'catalog.json'
    target.write_text('{}')
    monkeypatch.setattr(probe, 'CATALOG', target)
    with pytest.raises(ValueError, match='frozen'):
        probe.preview()


@pytest.mark.parametrize('name', ['reference.json', 'README.md', 'freeze.json', 'sources.json'])
def test_changed_frozen_reference_or_manifest_blocks_before_stores(probe, monkeypatch, tmp_path, name):
    folder = tmp_path / 'pilot'
    shutil.copytree(probe.CATALOG.parent, folder)
    (folder / name).write_text('{}')
    monkeypatch.setattr(probe, 'CATALOG', folder / 'catalog.json')
    monkeypatch.setattr(probe, 'EpisodeStore', lambda *_: pytest.fail('Store before freeze validation'))
    with pytest.raises(ValueError, match='frozen'):
        probe.preview()


def test_real_jobs_reach_tasks_and_review_without_gold_or_automatic_execution(probe, monkeypatch):
    http, calls = transport()
    report = run(probe, monkeypatch, _http_transport=http)
    assert report['execution_status'] == 'execution_complete', report
    assert report['semantic_grade'] == 'requires_review' and report['questions'] == 'not_run'
    assert report['live_model_verified'] is False and report['injected_http'] is True
    assert report['originals_unchanged'] is True
    assert report['automatic_tasks'] == [] and len(report['task_proposals']) == 1
    assert report['deadline_suggestions'][0]['due'] == '2026-11-06T15:00:00+01:00'
    assert {'tasks', 'review'} <= {stage for stage, _, _ in calls}
    encoded = json.dumps(calls)
    assert 'semantic_grade' not in encoded and 'allowed_evidence' not in encoded
    assert 'required' not in json.dumps([source for _, _, source in calls])
    contexts = [source['source_context'] for stage, _, source in calls if stage == 'tasks']
    assert len(contexts) == 10
    assert any(any(c.get('ich') and c['rolle'] == 'von' for c in ctx['contacts']) for ctx in contexts)
    assert report['usage_complete'] is True and report['budget']['spent_microusd'] > 0
    assert 'synthetic-pilot-only-key' not in json.dumps(report)


@pytest.mark.parametrize('stop', ['usage', 'revoke', 'requests', 'deadline'])
def test_shared_guards_stop_without_retry_or_execution(probe, monkeypatch, stop):
    now = [100.0]
    if stop == 'deadline':
        monkeypatch.setattr(probe.time, 'monotonic', lambda: now[0])
    def hook(_stage):
        if stop == 'revoke':
            monkeypatch.delenv(probe.KEY_ENV)
        if stop == 'deadline':
            now[0] = 702.0
    http, calls = transport(missing_usage=stop == 'usage', hook=hook)
    report = run(probe, monkeypatch, _http_transport=http, max_requests=2 if stop == 'requests' else 60)
    assert len(calls) == 1
    assert report['execution_status'] == 'incomplete'
    assert report['automatic_tasks'] == []
    if stop == 'usage':
        assert report['budget']['reconciliation_required'] is True
        assert report['budget']['held_microusd'] > 0


def test_tiny_cap_prevents_first_inference(probe, monkeypatch):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-key')
    http, calls = transport()
    report = probe.evaluate(allow_artificial_cloud=True, cap_microusd=1, _http_transport=http)
    assert not calls and report['inference_requests'] == 0
    assert report['execution_status'] == 'incomplete'


def test_total_http_limit_counts_metadata_too(probe, monkeypatch):
    http, calls = transport()
    report = run(probe, monkeypatch, _http_transport=http, max_requests=2)
    assert report['metadata_requests'] + report['inference_requests'] <= 2
    assert len(calls) == 1 and report['execution_status'] == 'incomplete'


def test_intake_cannot_silently_substitute_the_frozen_body(probe, monkeypatch):
    from dataclasses import replace
    from messlatte.postfach import Postfach
    original = Postfach.ablegen_mail
    monkeypatch.setattr(Postfach, 'ablegen_mail', lambda self, mail:
                        original(self, replace(mail, text='Different artificial body')))
    with pytest.raises(ValueError, match='original'):
        probe.preview()


def test_new_unselected_source_revokes_before_cloud_dispatch(probe, monkeypatch):
    from icarus_memory import EpisodeKind, Provenance, SourceType
    original = probe.CloudMemoryJobs.preview
    def add(jobs, *args, **kwargs):
        result = original(jobs, *args, **kwargs)
        jobs.episodes.record(EpisodeKind.MESSAGE, 'Unselected artificial mail', 'Extra',
                             Provenance(SourceType.EMAIL, source_ref='synthetic-extra'))
        return result
    monkeypatch.setattr(probe.CloudMemoryJobs, 'preview', add)
    http, calls = transport()
    report = run(probe, monkeypatch, _http_transport=http)
    assert not calls and report['metadata_requests'] == 0
    assert report['originals_unchanged'] is False
    assert report['execution_status'] == 'incomplete'


def test_cli_requires_run_flag_and_all_gates_and_never_claims_semantic_success(probe, monkeypatch, tmp_path):
    blocked = tmp_path / 'blocked.json'
    assert probe.main(['--run', '--output', str(blocked)]) == 2
    assert not blocked.exists()
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-key')
    assert probe.main(['--run', '--output', str(blocked), '--allow-artificial-cloud']) == 2
    assert not blocked.exists()
    http, _ = transport()
    original = probe.evaluate
    monkeypatch.setattr(probe, 'evaluate', lambda **kw: original(**kw, _http_transport=http))
    output = tmp_path / 'mock-result.json'
    assert probe.main(['--run', '--output', str(output), '--allow-artificial-cloud', '--cap-usd', '1']) == 1
    report = json.loads(output.read_text())
    assert report['execution_status'] == 'execution_complete'
    assert report['semantic_grade'] == 'requires_review' and report['questions'] == 'not_run'
    assert report['live_model_verified'] is False


@pytest.mark.parametrize('value', [False, 0, 'invalid'])
def test_invalid_transport_never_falls_back_to_network(probe, monkeypatch, value):
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-key')
    with pytest.raises(ValueError, match='transport'):
        probe.evaluate(allow_artificial_cloud=True, cap_microusd=1000000, _http_transport=value)


def test_scenario_clock_is_frozen_but_budget_clock_stays_real(probe, monkeypatch):
    import time
    from icarus_memory import model, cloud_import_budget
    before = time.time()
    observations = []
    def observe(_stage):
        observations.append((model.now().isoformat(), cloud_import_budget._now()))
    http, _ = transport(hook=observe)
    report = run(probe, monkeypatch, _http_transport=http, max_requests=2)
    assert observations
    assert observations[0][0] == '2026-11-04T15:00:00+00:00'
    assert before <= observations[0][1] <= time.time()
    assert report['seconds'] >= 0


@pytest.mark.parametrize('field', ['sender', 'recipient', 'title', 'date', 'folder', 'reply'])
def test_all_frozen_metadata_is_checked_before_snapshot_or_http(probe, monkeypatch, field):
    from dataclasses import replace
    from datetime import timedelta
    from messlatte.daten import Adresse
    from messlatte.postfach import Postfach
    original = Postfach.ablegen_mail
    def alter(box, mail):
        if mail.id == 'P01':
            changes = {'sender': {'von': Adresse('Substitute', 'other@example.example')},
                'recipient': {'an': (Adresse('Other', 'other@example.example'),)},
                'title': {'betreff': 'Substituted subject'},
                'date': {'zeit': mail.zeit + timedelta(days=1)},
                'folder': {'ordner': 'Sent'}, 'reply': {'antwort_auf': 'P03'}}
            mail = replace(mail, **changes[field])
        return original(box, mail)
    monkeypatch.setattr(Postfach, 'ablegen_mail', alter)
    http, calls = transport()
    with pytest.raises(ValueError, match='original'):
        run(probe, monkeypatch, _http_transport=http)
    assert not calls


def test_preparation_exhausts_the_same_absolute_deadline_before_any_http(probe, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(probe.time, 'monotonic', lambda: now[0])
    original = probe._intake
    def slow(*args):
        result = original(*args)
        now[0] = 701.0
        return result
    monkeypatch.setattr(probe, '_intake', slow)
    http, calls = transport()
    report = run(probe, monkeypatch, _http_transport=http)
    assert report['metadata_requests'] == report['inference_requests'] == 0
    assert not calls and report['execution_status'] == 'incomplete'
    assert report['deadline_exhausted'] is True


def test_missing_original_during_post_keeps_integrity_and_cost_receipt(probe, monkeypatch):
    stores = []
    original = probe.EpisodeStore
    def capture(path):
        store = original(path); stores.append(store); return store
    monkeypatch.setattr(probe, 'EpisodeStore', capture)
    def remove(_stage):
        store = stores[0]
        identifier = next(e.id for e in store.all_episodes() if e.title == 'Fenn: Leuchtplan zur Freigabe')
        with store._lock:
            store._conn.execute('DELETE FROM episodes WHERE id=?', (identifier,)); store._conn.commit()
    http, calls = transport(hook=remove)
    report = run(probe, monkeypatch, _http_transport=http)
    assert len(calls) == report['inference_requests'] == 1
    assert report['metadata_requests'] == 1 and report['execution_status'] == 'incomplete'
    assert report['originals_unchanged'] is False
    missing = next(row for row in report['results'] if row['id'] == 'P01')
    assert missing['integrity'] == 'missing'
    assert len(report['sources']) == 10
    assert report['budget']['held_microusd'] + report['budget']['spent_microusd'] > 0
    assert report['reservations']


@pytest.mark.parametrize('phase', ['headers', 'body'])
def test_blocked_http_returns_held_receipt_and_late_result_never_reopens_stores(probe, monkeypatch, phase):
    probe.preview()  # Load the existing scenario helper before the short timing probe.
    release, dispatched, finished = threading.Event(), threading.Event(), threading.Event()
    closed, late_access = set(), []
    original_get, original_close = probe.EpisodeStore.get, probe.EpisodeStore.close
    def get(store, *args, **kwargs):
        if id(store) in closed:
            late_access.append(True)
        return original_get(store, *args, **kwargs)
    def close(store):
        closed.add(id(store)); return original_close(store)
    monkeypatch.setattr(probe.EpisodeStore, 'get', get)
    monkeypatch.setattr(probe.EpisodeStore, 'close', close)
    def block(_stage):
        dispatched.set(); release.wait(4); finished.set()
    http, calls = transport(hook=block if phase == 'headers' else None)
    if phase == 'body':
        inner = http
        class BlockedBody(httpx.SyncByteStream):
            def __init__(self, body): self.body = body
            def __iter__(self):
                block('body')
                yield self.body
        def handle(request):
            response = inner.handle_request(request)
            return (httpx.Response(200, stream=BlockedBody(response.content))
                    if request.method == 'POST' else response)
        http = httpx.MockTransport(handle)
    started = time.monotonic()
    try:
        report = run(probe, monkeypatch, _http_transport=http, seconds=0.7)
        elapsed = time.monotonic() - started
        assert dispatched.is_set(), report
        assert elapsed < 1.5, 'The runner must not wait for the blocked HTTP exchange'
        assert report['execution_status'] == 'incomplete'
        assert report['budget']['reconciliation_required'] is True
        assert report['budget']['held_microusd'] > 0
        assert report['usage_complete'] is False
        assert report['inference_requests'] == len(calls) == 1
        assert closed and not finished.is_set()
    finally:
        release.set()
        assert finished.wait(2)
    time.sleep(0.05)
    assert not late_access


def test_unavailable_accounting_keeps_independent_counters_and_conservative_receipt(probe, monkeypatch):
    def unavailable(_path):
        raise OSError('artificial ledger read error')
    monkeypatch.setattr(probe, '_accounting', unavailable)
    http, calls = transport()
    report = run(probe, monkeypatch, _http_transport=http, max_requests=2)
    assert len(calls) == report['inference_requests'] == 1 and report['metadata_requests'] == 1
    assert report['budget']['spent_microusd'] > 0
    assert report['accounting_status'] == 'unavailable' and report['usage_complete'] is False
    assert report['reconciliation_required'] is True
    assert report['unverified_cost_upper_bound_microusd'] == 1000000
    assert report['originals_unchanged'] is True and len(report['sources']) == 10


def test_paid_cli_preflight_consumes_same_deadline_as_dispatch_and_receipt(probe, monkeypatch, tmp_path):
    now = [1000.0]
    original_sources, original_evaluate = probe._sources, probe.evaluate
    reads = []
    def slow_preflight():
        sources = original_sources()
        if not reads:
            now[0] += 601
        reads.append(True)
        return sources
    http, calls = transport()
    def evaluate(**options):
        return original_evaluate(_http_transport=http, **options)
    monkeypatch.setattr(probe.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(probe, '_sources', slow_preflight)
    monkeypatch.setattr(probe, 'evaluate', evaluate)
    monkeypatch.setenv(probe.KEY_ENV, 'synthetic-pilot-only-key')
    output = tmp_path / 'paid.json'
    assert probe.main(['--run', '--allow-artificial-cloud', '--cap-usd', '1',
                       '--max-requests', '2', '--seconds', '600', '--output', str(output)]) == 1
    report = json.loads(output.read_text())
    assert report['metadata_requests'] == report['inference_requests'] == 0
    assert calls == [] and report['execution_status'] == 'incomplete'
    assert report['deadline_exhausted'] is True and report['seconds'] >= 601


def test_delayed_http_worker_cannot_begin_post_after_timeout_receipt(probe, monkeypatch):
    probe.preview()
    release, queued, finished = threading.Event(), threading.Event(), threading.Event()
    exchange = probe._http_exchange
    def delayed(transport, request, *args):
        if request.method == 'POST':
            queued.set()
            release.wait(4)
            try:
                return exchange(transport, request, *args)
            finally:
                finished.set()
        return exchange(transport, request, *args)
    monkeypatch.setattr(probe, '_http_exchange', delayed)
    http, calls = transport()
    try:
        report = run(probe, monkeypatch, _http_transport=http, seconds=0.7)
        assert queued.is_set() and not finished.is_set()
        assert report['execution_status'] == 'incomplete'
        assert calls == []
        assert report['budget']['held_microusd'] > 0 and report['usage_complete'] is False
    finally:
        release.set()
        assert finished.wait(2)
    assert calls == [], 'A queued HTTP worker must not initiate transport after its timeout receipt'


@pytest.mark.parametrize('supplied', ['future', float('nan'), float('inf'), float('-inf'), True, 'invalid'])
def test_supplied_start_cannot_extend_deadline_or_be_nonfinite_or_wrong_type(probe, monkeypatch, supplied):
    start = time.monotonic() + 60 if supplied == 'future' else supplied
    http, calls = transport()
    with pytest.raises(ValueError, match='start'):
        run(probe, monkeypatch, _http_transport=http, max_requests=2, seconds=0.001, _started=start)
    assert calls == []
