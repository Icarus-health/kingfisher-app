"""An upload may wake only the already authorized local memory worker."""

import threading
import time
from datetime import timedelta

from fastapi.testclient import TestClient
import pytest

from icarus_memory import EpisodeKind, MemoryBackend, Provenance, SelfModelStore, SourceType
from icarus_memory.model import now
from icarus_memory.scheduler import JobResult, MAX_PENDING_UPLOADS, Scheduler
from icarus_memory.server import create_app
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_working_memory_worker import FakeCloudProvider, FakeLocalProvider


def local_app(tmp_path, monkeypatch, provider):
    import icarus_memory.server as server

    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setattr(server, 'provider_from_env', lambda: provider)
    app = create_app(SelfModelStore(MemoryBackend(), 'test'))
    return app, TestClient(app)


def test_prompt_requires_enabled_model_and_uses_only_memory_step():
    called = threading.Event()
    other = []
    plan = Scheduler(
        run_ingest=lambda: (other.append('ingest'), [])[1],
        run_backup=lambda: (other.append('backup'), JobResult('backup'))[1],
        run_prompt_working_memory=lambda ids: (called.set(), JobResult('gedaechtnis'))[1],
    )
    assert not plan.request_working_memory('source-1')
    plan.configure(enabled=True)
    plan.start()
    try:
        assert not plan.request_working_memory('source-1')
        plan.configure(with_model=True)
        plan._last_at = now()  # keep the ordinary schedule out of this test
        assert plan.request_working_memory('source-1')
        assert called.wait(2)
        assert other == []
    finally:
        plan.stop()


def test_prompt_completion_defers_backlog_until_next_idle_tick(monkeypatch):
    from icarus_memory import scheduler

    monkeypatch.setattr(scheduler, 'TICK_SECONDS', 0.08)
    prompt_done, backlog_started = threading.Event(), threading.Event()
    plan = Scheduler(
        run_prompt_working_memory=lambda _ids: (
            prompt_done.set(), JobResult('gedaechtnis'))[1],
        run_working_memory=lambda _with_model: (
            backlog_started.set(), JobResult('gedaechtnis'))[1],
    )
    plan.configure(enabled=True, with_model=True)
    plan._last_at = now()
    plan.start()
    try:
        assert plan.request_working_memory('uploaded-source')
        assert prompt_done.wait(1)
        assert not backlog_started.wait(0.03)
        assert backlog_started.wait(1)
    finally:
        plan.stop()


def test_upload_signals_during_a_pass_are_coalesced_and_stop_discards_pending():
    entered, release, second, third = (threading.Event() for _ in range(4))
    calls = []

    def memory(ids):
        calls.append(ids)
        if len(calls) == 1:
            entered.set()
            release.wait(3)
        elif len(calls) == 2:
            second.set()
        else:
            third.set()
        return JobResult('gedaechtnis')

    plan = Scheduler(run_prompt_working_memory=memory)
    plan.configure(enabled=True, with_model=True)
    plan._last_at = now()
    plan.start()
    try:
        assert plan.request_working_memory('first')
        assert entered.wait(2)
        for index in range(6):
            assert plan.request_working_memory(f'later-{index}')
        assert plan.request_working_memory('later-0')  # duplicate signal coalesces
        release.set()
        assert second.wait(3)
        assert third.wait(3)
        assert calls == [['first'], [f'later-{index}' for index in range(5)], ['later-5']]
        assert plan.request_working_memory('after')
        plan.stop()
        assert len(calls) == 3
        assert not plan.request_working_memory('after-stop')
    finally:
        release.set()
        plan.stop()


def test_prompt_queue_has_a_cap_and_duplicates_do_not_consume_it():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def memory(ids):
        calls.append(ids)
        entered.set()
        release.wait(3)
        return JobResult('gedaechtnis')

    plan = Scheduler(run_prompt_working_memory=memory)
    plan.configure(enabled=True, with_model=True)
    plan._last_at = now()
    plan.start()
    try:
        assert plan.request_working_memory('active')
        assert entered.wait(2)
        for index in range(MAX_PENDING_UPLOADS):
            assert plan.request_working_memory(f'pending-{index}')
        assert plan.request_working_memory('pending-0')
        assert plan.request_working_memory('active')
        assert not plan.request_working_memory('overflow')
        assert len(plan._memory_pending) == MAX_PENDING_UPLOADS
        plan.stop(timeout=0)
    finally:
        release.set()
        plan.stop()
    assert calls == [['active']]
    assert plan._memory_pending == {}


def test_continuous_prompt_queue_does_not_starve_due_intake_and_backup():
    entered, release, backed_up = threading.Event(), threading.Event(), threading.Event()
    order = []
    plan = None

    def memory(ids):
        order.append('prompt')
        # Keep another upload waiting while the first model call is in flight.
        assert plan.request_working_memory(f'more-{len(order)}')
        if not entered.is_set():
            entered.set()
            release.wait(3)
        return JobResult('gedaechtnis')

    def ingest():
        order.append('ingest')
        return []

    def backup():
        order.append('backup')
        backed_up.set()
        return JobResult('backup')

    plan = Scheduler(run_prompt_working_memory=memory, run_ingest=ingest,
                     run_backup=backup)
    plan.configure(enabled=True, with_model=True)
    plan._last_at = now()
    plan.start()
    try:
        assert plan.request_working_memory('first')
        assert entered.wait(2)
        plan._last_at = now() - timedelta(minutes=241)
        release.set()
        assert backed_up.wait(2)
        assert order[:3] == ['prompt', 'ingest', 'backup']
    finally:
        release.set()
        plan.stop()


def test_document_upload_wakes_local_worker_without_ingest_or_backup(tmp_path, monkeypatch):
    provider = FakeLocalProvider()
    app, client = local_app(tmp_path, monkeypatch, provider)
    scheduler = app.state.scheduler
    other = []
    try:
        # Defaults remain disabled, including when the provider is local.
        first = client.post('/api/v1/sources/documents', json={
            'filename': 'first.txt', 'body': 'A private first source.'})
        assert first.status_code == 200
        assert provider.calls == []
        scheduler._run_ingest = lambda: (other.append('ingest'), [])[1]
        scheduler._run_backup = lambda: (other.append('backup'), JobResult('backup'))[1]

        enabled = client.put('/schedule', json={'enabled': True, 'with_model': True})
        assert enabled.status_code == 200
        scheduler._last_at = now()
        uploaded = client.post('/api/v1/sources/documents', json={
            'filename': 'second.txt', 'body': 'A private second source.'})
        assert uploaded.status_code == 200
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if WorkingMemoryStore(app.state.episodes).coverage()['complete'] >= 1 and len(provider.calls) == 2:
                break
            time.sleep(.01)
        coverage = WorkingMemoryStore(app.state.episodes).coverage()
        assert coverage['complete'] == 1
        assert coverage['pending'] == 1  # before activation: not swept in by upload
        assert len(provider.calls) == 2
        assert all(call['blocks'][0]['text'] == 'A private second source.' for call in provider.calls)
        assert other == []

        client.put('/schedule', json={'with_model': False})
        third = client.post('/api/v1/sources/documents', json={
            'filename': 'third.txt', 'body': 'A private third source.'})
        assert third.status_code == 200
        assert len(provider.calls) == 2
        app.state.agent._provider = FakeCloudProvider()
        client.put('/schedule', json={'with_model': True})
        fourth = client.post('/api/v1/sources/documents', json={
            'filename': 'fourth.txt', 'body': 'A private fourth source.'})
        assert fourth.status_code == 200
        assert app.state.agent.provider.calls == []
    finally:
        scheduler.stop()


def test_new_upload_is_processed_ahead_of_older_pending_backlog(tmp_path, monkeypatch):
    provider = FakeLocalProvider()
    app, client = local_app(tmp_path, monkeypatch, provider)
    scheduler = app.state.scheduler
    try:
        for index in range(140):
            app.state.episodes.record(
                EpisodeKind.DOCUMENT, f'old-{index}.txt', f'Old pending source {index}',
                Provenance(SourceType.DOCUMENT, source_ref=f'upload:old-{index}.txt'),
            )
        cursor_before = app.state.episodes._conn.execute(
            'SELECT cursor FROM working_memory_scan WHERE id=1').fetchone()[0]
        assert client.put('/schedule', json={'enabled': True, 'with_model': True}).status_code == 200
        scheduler._last_at = now()
        response = client.post('/api/v1/sources/documents', json={
            'filename': 'new.txt', 'body': 'New source needs prompt memory.'})
        assert response.status_code == 200
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if WorkingMemoryStore(app.state.episodes).coverage()['complete'] == 1 and len(provider.calls) == 2:
                break
            time.sleep(.01)
        assert WorkingMemoryStore(app.state.episodes).coverage()['complete'] == 1
        assert WorkingMemoryStore(app.state.episodes).coverage()['pending'] == 140
        assert len(provider.calls) == 2
        assert all(call['blocks'][0]['text'] == 'New source needs prompt memory.' for call in provider.calls)
        assert app.state.episodes._conn.execute(
            'SELECT cursor FROM working_memory_scan WHERE id=1').fetchone()[0] == cursor_before
    finally:
        scheduler.stop()


@pytest.mark.parametrize('change', ['disable', 'model', 'shutdown'])
def test_prompt_cannot_commit_after_permission_or_model_changes(tmp_path, monkeypatch, change):
    called = threading.Event()
    provider = FakeLocalProvider()
    app, client = local_app(tmp_path, monkeypatch, provider)
    scheduler = app.state.scheduler

    def change_during_model(_payload):
        if change == 'disable':
            app.state.settings.schedule.with_model = False
            scheduler.configure(with_model=False)
        elif change == 'model':
            provider.model = 'replacement-model'
        else:
            scheduler.stop(timeout=0)
        called.set()

    provider.on_call = change_during_model
    try:
        assert client.put('/schedule', json={'enabled': True, 'with_model': True}).status_code == 200
        scheduler._last_at = now()
        response = client.post('/api/v1/sources/documents', json={
            'filename': 'private.txt', 'body': 'This source must not be committed after revocation.'})
        assert response.status_code == 200
        assert called.wait(2)
        # The run lock gives a deterministic completion point after the model call.
        assert scheduler._run_lock.acquire(timeout=2)
        scheduler._run_lock.release()
        assert WorkingMemoryStore(app.state.episodes).coverage()['complete'] == 0
    finally:
        scheduler.stop()


def test_shutdown_during_prompt_does_not_start_a_due_source_run():
    called = threading.Event()
    other = []
    plan = Scheduler(run_ingest=lambda: (other.append('ingest'), [])[1])
    def stop_during_prompt(_ids):
        plan._last_at = None  # A normal run would now be due.
        plan.stop(timeout=0)
        called.set()
        return JobResult('gedaechtnis')
    plan._run_prompt_working_memory = stop_during_prompt
    plan.configure(enabled=True, with_model=True)
    plan._last_at = now()
    plan.start()
    try:
        assert plan.request_working_memory('synthetic-episode')
        assert called.wait(2)
        plan.stop()
        assert other == []
    finally:
        plan.stop()


def test_upload_arriving_in_due_memory_pass_runs_before_optional_models():
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    order=[]
    def backlog(_with_model):
        entered.set(); release.wait(3)
        return JobResult('gedaechtnis')
    def prompt(ids):
        order.append(('prompt',ids));return JobResult('gedaechtnis')
    plan=Scheduler(run_working_memory=backlog, run_prompt_working_memory=prompt,
                   run_task_detection=lambda _: (order.append(('tasks',[])),JobResult('zusagen'))[1],
                   run_backup=lambda: (order.append(('backup',[])),done.set(),JobResult('backup'))[2])
    plan.configure(enabled=True,with_model=True);plan.start();plan._wake.set()
    try:
        assert entered.wait(2)
        assert plan.request_working_memory('new-document')
        release.set();assert done.wait(2)
        assert order[:3] == [('prompt',['new-document']),('tasks',[]),('backup',[])]
    finally:
        release.set();plan.stop()


def test_priority_batch_observes_pause_and_leaves_backup_running():
    entered,release,done=threading.Event(),threading.Event(),threading.Event()
    prompts=[]
    def backlog(_model):
        entered.set();release.wait(3);return JobResult('gedaechtnis')
    plan=Scheduler(run_working_memory=backlog,
        run_prompt_working_memory=lambda ids: (prompts.extend(ids),JobResult('gedaechtnis'))[1],
        run_task_detection=lambda _: JobResult('zusagen'),
        run_backup=lambda: (done.set(),JobResult('backup'))[1])
    plan.configure(enabled=True,with_model=True);plan.start();plan._wake.set()
    try:
        assert entered.wait(2)
        assert plan.request_working_memory('waiting')
        plan.configure(with_model=False);release.set();assert done.wait(2)
        assert prompts==[] and plan.memory_state('waiting') is None
    finally:
        release.set();plan.stop()
