"""Main-app seam with artificial stores, fake listener/gateway and MockHTTP model."""
from contextlib import contextmanager
import importlib
import json
import threading
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from icarus_memory import server
from icarus_memory.episodes import EpisodeKind
from icarus_memory.local_module_controller import ControllerError, MODEL, MODE
from icarus_memory.local_module_runtime import ManagedLocalSourceRuntime
from icarus_memory.model import Provenance, SourceType
from icarus_memory.restore_boundary import mark_pending
from tests.test_conversation_retraction import _make_app, _close_app
from tests.test_local_module_controller import QUESTION, begin
from tests.test_local_module_model import fixture as verified
from tests.test_local_module_runtime import Gateway, Listener


PREFIX = '/api/v1/modules/local-source'
HEADERS = {'X-Icarus-Token': 'artificial-main-token'}


def api():
    return importlib.import_module('icarus_memory.local_module_integration')


@pytest.mark.parametrize('mode,key', [(None,None), (MODE,None), ('synthetic', 'k'*43),
    (MODE,'k'*42), (MODE,'a'*64), (MODE,'private secret')])
def test_only_exact_trusted_launch_environment_can_configure_runtime(monkeypatch, mode, key):
    module = api()
    monkeypatch.delenv('KF_HARNESS_MODE', raising=False)
    monkeypatch.delenv('KF_GATEWAY_CONTROL_KEY', raising=False)
    if mode is not None:
        monkeypatch.setenv('KF_HARNESS_MODE', mode)
    if key is not None:
        monkeypatch.setenv('KF_GATEWAY_CONTROL_KEY', key)
    monkeypatch.setattr(module, 'ManagedLocalSourceRuntime', lambda *_a, **_k: pytest.fail('untrusted runtime creation'))
    app = FastAPI()
    assert module.configure(app) is None
    assert app.state.local_source_runtime is None


def test_configured_runtime_uses_canonical_stores_actual_lock_and_live_background_role(monkeypatch):
    module = api()
    monkeypatch.setenv('KF_HARNESS_MODE', MODE)
    monkeypatch.setenv('KF_GATEWAY_CONTROL_KEY', 'k'*43)
    app = FastAPI()
    app.state.episodes, app.state.procedures = object(), object()
    app.state.conversation_lock, app.state.runtime_boundary = threading.Lock(), object()
    current = [object()]
    calls = []
    monkeypatch.setattr(module, 'rollen_von', lambda target: SimpleNamespace(provider=lambda role: (
        calls.append((target, role)) or current[0])))
    class Model:
        def __init__(self, getter, lock, boundary):
            self.getter, self.lock, self.boundary = getter, lock, boundary
    captures = []
    def runtime(*args):
        captures.append(args)
        return object()
    monkeypatch.setattr(module, 'VerifiedModuleModel', Model)
    monkeypatch.setattr(module, 'ManagedLocalSourceRuntime', runtime)
    assert module.configure(app) is app.state.local_source_runtime
    assert not calls
    episodes, procedures, model, key = captures[0]
    assert episodes is app.state.episodes and procedures is app.state.procedures
    assert key == 'k'*43 and model.lock is app.state.conversation_lock
    assert model.boundary is app.state.runtime_boundary
    assert model.getter() is current[0]
    current[0] = object()
    assert model.getter() is current[0]
    assert all(target is app and role == 'hintergrund' for target, role in calls)


@pytest.fixture
def integrated(tmp_path, monkeypatch, verified):
    module = api()
    monkeypatch.setenv('KF_HARNESS_MODE', MODE)
    monkeypatch.setenv('KF_GATEWAY_CONTROL_KEY', 'k'*43)
    gateway, listener = Gateway(), Listener()
    created = []
    def construct(episodes, procedures, model, key):
        runtime = ManagedLocalSourceRuntime(episodes, procedures, model, key,
            listener_factory=lambda: listener, gateway=gateway)
        gateway.controller = runtime._controller
        created.append(runtime)
        return runtime
    monkeypatch.setattr(module, 'ManagedLocalSourceRuntime', construct)
    monkeypatch.setattr(module, 'rollen_von', lambda _app: SimpleNamespace(provider=lambda _role: verified['ordinary']))
    app = _make_app(tmp_path, monkeypatch, token=HEADERS['X-Icarus-Token'])
    source = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Künstliches Original',
        'Die Zugangskarte liegt in Fach A42.', Provenance(source_type=SourceType.DOCUMENT))[0]
    assert len(created) == 1
    with TestClient(app) as client:
        yield dict(app=app, client=client, runtime=created[0], gateway=gateway, listener=listener,
                   source=source, verified=verified, directory=tmp_path)
    gateway.release.set()
    created[0].shutdown(wait_seconds=2)
    _close_app(app)
    app.state.procedures.close()


def start(integrated):
    result = integrated['client'].post(PREFIX + '/runtime/initialize', headers=HEADERS, json={})
    assert result.status_code == 200, result.text
    assert result.json()['paired'] is True
    return integrated['runtime']._controller


def test_main_lifespan_status_and_construction_never_initialize_runtime(integrated):
    client = integrated['client']
    assert integrated['listener'].starts == integrated['gateway'].initializations == 0
    assert client.get(PREFIX + '/runtime/status').status_code == 401
    status = client.get(PREFIX + '/runtime/status', headers=HEADERS)
    assert status.status_code == 200 and status.json()['configured'] is True
    assert status.json()['paired'] is False
    assert client.get(PREFIX + '/status', headers=HEADERS).json()['status'] == 'not_installed'
    assert integrated['listener'].starts == integrated['gateway'].initializations == 0
    assert integrated['verified']['requests'] == []


def test_main_module_routes_receive_only_the_explicitly_paired_runtime(integrated):
    controller = start(integrated)
    response = integrated['client'].post(PREFIX + '/prepare', headers=HEADERS,
        json=dict(source_id=integrated['source'].id, question=QUESTION))
    assert response.status_code == 200
    assert response.json()['source']['id'] == integrated['source'].id
    assert integrated['runtime'].controller_for_request() is controller


@pytest.mark.parametrize('update', [False, True])
def test_backup_quiesces_module_before_snapshot_without_stopping_normal_idle_worker(integrated, monkeypatch, update):
    start(integrated)
    runtime, events = integrated['runtime'], []
    snapshot = server.snapshot_all
    def checked(*args, **kwargs):
        events.append('snapshot')
        assert runtime.controller_for_request() is None
        assert integrated['listener'].running() is (not update)
        return snapshot(*args, **kwargs)
    monkeypatch.setattr(server, 'snapshot_all', checked)
    path = '/backups?vor_update=true' if update else '/backups'
    response = integrated['client'].post(path, headers=HEADERS)
    assert response.status_code == 201, response.text
    assert events == ['snapshot']
    assert integrated['listener'].running() is (not update)
    if not update:
        assert runtime.controller_for_request() is not None


def test_encrypted_download_pauses_before_taking_conversation_lock(integrated, monkeypatch):
    from icarus_memory import sicherung_download
    start(integrated)
    entered = []
    def export(_directory, _password):
        entered.append(True)
        assert integrated['runtime'].controller_for_request() is None
        assert not integrated['app'].state.conversation_lock.acquire(blocking=False)
        return b'artificial-encrypted-archive'
    monkeypatch.setattr(sicherung_download, 'erstellen', export)
    response = integrated['client'].post('/api/v1/recovery/herunterladen', headers=HEADERS,
        json={'password': 'artificial-password-long-enough'})
    assert response.status_code == 200 and response.content == b'artificial-encrypted-archive'
    assert entered and integrated['listener'].running()
    assert integrated['runtime'].controller_for_request() is not None


def test_scheduler_backup_uses_live_runtime_pause_even_when_wired_before_runtime(integrated, monkeypatch):
    from icarus_memory.scheduler import JobResult
    start(integrated)
    events = []
    def backup(_directory):
        def run():
            events.append(True)
            assert integrated['runtime'].controller_for_request() is None
            return JobResult('sicherung', True, 'artificial-backup')
        return run
    monkeypatch.setattr(server, 'backup_job', backup)
    integrated['app'].state.settings.schedule.backup = True
    server._wire_scheduler(integrated['app'])
    result = integrated['app'].state.scheduler._run_backup()
    assert result.ok and events and integrated['listener'].running()


def test_busy_module_failure_prevents_backup_and_hides_provider_diagnostics(integrated, monkeypatch):
    runtime = integrated['runtime']
    @contextmanager
    def blocked(**_kwargs):
        raise RuntimeError('private-provider control-key secret')
        yield
    with monkeypatch.context() as patch:
        patch.setattr(runtime, 'paused_for_backup', blocked)
        patch.setattr(server, 'snapshot_all', lambda *_a, **_k: pytest.fail('backup wrote before quiescence'))
        response = integrated['client'].post('/backups', headers=HEADERS)
    assert response.status_code == 409
    assert 'private' not in response.text and 'secret' not in response.text


def test_restore_wrong_auth_never_revokes_or_waits_on_active_inference(integrated):
    controller = start(integrated)
    name = integrated['client'].post('/backups', headers=HEADERS).json()['name']
    gateway = integrated['gateway']
    gateway.release.clear()
    run = begin(controller, integrated['source'])
    try:
        assert gateway.entered.wait(1)
        started = time.monotonic()
        response = integrated['client'].post('/backups/restore', json={'name': name})
        assert response.status_code == 401
        assert time.monotonic() - started < .5
        assert controller._broker.current(gateway.tokens[0])
        assert controller.poll(run['id'])['status'] == 'running'
    finally:
        controller.cancel(run['id']); gateway.release.set()


def test_invalid_restore_does_not_revoke_an_existing_runtime(integrated):
    start(integrated)
    folder = integrated['directory'] / 'sicherungen'
    folder.mkdir(exist_ok=True)
    (folder / 'broken.sqlite3').write_text('not a database')
    response = integrated['client'].post('/backups/restore', headers=HEADERS, json={'name':'broken.sqlite3'})
    assert response.status_code == 409
    assert integrated['runtime'].controller_for_request() is not None
    assert integrated['listener'].running()


def test_restore_revokes_before_waiting_for_model_boundary_reader(integrated):
    controller = start(integrated)
    name = integrated['client'].post('/backups', headers=HEADERS).json()['name']
    entered, release = threading.Event(), threading.Event()
    def block(request):
        if request.url.path == '/api/chat':
            entered.set()
            assert release.wait(3)
    integrated['verified']['state']['hook'] = block
    run = begin(controller, integrated['source'])
    result, done = [], threading.Event()
    def restoring():
        try:
            result.append(integrated['client'].post('/backups/restore', headers=HEADERS, json={'name':name}))
        finally:
            done.set()
    task = threading.Thread(target=restoring)
    try:
        assert entered.wait(1)
        assert not integrated['app'].state.runtime_boundary.try_enter(exclusive=True)
        task.start()
        deadline = time.monotonic() + .5
        while controller._broker.current(integrated['gateway'].tokens[0]) and time.monotonic() < deadline:
            time.sleep(.005)
        assert not controller._broker.current(integrated['gateway'].tokens[0])
        assert not done.is_set()
    finally:
        release.set()
        if task.ident is not None:
            task.join(3)
    assert done.is_set() and result[0].status_code == 200, result[0].text if result else ''
    assert result[0].json()['mode'] == 'inspection'
    assert controller.poll(run['id'])['status'] == 'restarted'


@pytest.mark.parametrize('pending', [False, True])
def test_only_exact_authenticated_revocation_and_runtime_status_bypass_restore_gate(integrated, pending):
    controller = start(integrated)
    gateway, gate, client = integrated['gateway'], integrated['app'].state.runtime_boundary, integrated['client']
    gateway.release.clear()
    run = begin(controller, integrated['source'])
    assert gateway.entered.wait(1)
    if pending:
        mark_pending(gate.directory, 'artificial restore')
    else:
        assert gate.try_enter(exclusive=True)
    try:
        assert client.get(PREFIX + '/runtime/status').status_code == 401
        assert client.post(PREFIX + '/runtime/shutdown', json={}).status_code == 401
        assert client.post(PREFIX + '/runs/' + run['id'] + '/cancel').status_code == 401
        assert controller._broker.current(gateway.tokens[0])
        assert client.get(PREFIX + '/runtime/status', headers=HEADERS).status_code == 200
        denied = client.post(PREFIX + '/prepare', headers=HEADERS,
            json={'source_id': integrated['source'].id, 'question':QUESTION})
        assert denied.status_code in (423,503)
        wrong = client.post(PREFIX + '/runtime/initialize', headers=HEADERS, json={})
        assert wrong.status_code in (423,503)
        cancelled = client.post(PREFIX + '/runs/' + run['id'] + '/cancel', headers=HEADERS)
        assert cancelled.status_code == 200 and cancelled.json()['status'] == 'cancelled'
        gateway.release.set()
        stopped = client.post(PREFIX + '/runtime/shutdown', headers=HEADERS, json={})
        assert stopped.status_code == 200 and stopped.json()['stopping'] is False
    finally:
        gateway.release.set()
        if not pending:
            gate.leave(exclusive=True)


def test_cold_inspection_exposes_only_authenticated_absent_runtime_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', HEADERS['X-Icarus-Token'])
    monkeypatch.setenv('KF_HARNESS_MODE', MODE)
    monkeypatch.setenv('KF_GATEWAY_CONTROL_KEY', 'k'*43)
    mark_pending(tmp_path, 'artificial restore')
    monkeypatch.setattr(server, '_build_agent', lambda *_: pytest.fail('inspection constructed normal app'))
    with TestClient(server.create_app()) as client:
        assert client.get(PREFIX + '/runtime/status').status_code == 401
        result = client.get(PREFIX + '/runtime/status', headers=HEADERS)
        assert result.status_code == 200 and result.json()['configured'] is False
        assert client.post(PREFIX + '/runtime/shutdown', headers=HEADERS, json={}).status_code == 200
        assert client.post(PREFIX + '/runtime/initialize', headers=HEADERS, json={}).status_code == 423
        assert client.post('/chat', headers=HEADERS, json={'message':'private'}).status_code == 423


def test_restore_preflight_unknown_validator_error_is_sanitized_without_revoking(integrated, monkeypatch):
    from icarus_memory import backup
    start(integrated)
    name = integrated['client'].post('/backups', headers=HEADERS).json()['name']
    def broken(_target):
        raise RuntimeError('private snapshot path secret')
    with monkeypatch.context() as patch:
        patch.setattr(backup, 'verify_snapshot_set', broken)
        response = integrated['client'].post('/backups/restore', headers=HEADERS, json={'name':name})
    assert response.status_code == 409
    assert 'private' not in response.text and 'secret' not in response.text
    assert integrated['runtime'].controller_for_request() is not None


@pytest.mark.parametrize('body,status', [
    (b'{"name":"one","name":"two"}',422),
    (b'{"name":"one","password":"private-secret"}',422),
    (b'private-secret'*1000,413),
])
def test_restore_preflight_body_is_bounded_closed_and_never_reflects_secrets(integrated, body, status):
    start(integrated)
    response = integrated['client'].post('/backups/restore', headers=HEADERS | {'Content-Type':'application/json'}, content=body)
    assert response.status_code == status
    assert 'private' not in response.text and 'secret' not in response.text
    assert integrated['runtime'].controller_for_request() is not None


def test_restore_replay_cannot_accumulate_unbounded_empty_frames(integrated):
    import asyncio
    received, sent = [0], []
    async def receive():
        received[0] += 1
        if received[0] > 1000:
            raise AssertionError('unbounded replay frame accumulation')
        return {'type':'http.request', 'body':b'', 'more_body':True}
    async def send(message):
        sent.append(message)
    scope = dict(type='http', method='POST', path='/backups/restore', raw_path=b'/backups/restore',
        query_string=b'', root_path='', scheme='http', http_version='1.1',
        server=('artificial',80), client=('127.0.0.1',1),
        headers=[(b'x-icarus-token',HEADERS['X-Icarus-Token'].encode()),(b'content-type',b'application/json')])
    asyncio.run(integrated['app'](scope,receive,send))
    assert received[0] < 300
    assert sent[0]['status'] == 422


def test_restore_with_invalid_media_type_does_not_interrupt_runtime(integrated):
    start(integrated)
    name = integrated['client'].post('/backups', headers=HEADERS).json()['name']
    response = integrated['client'].post('/backups/restore', headers=HEADERS | {'Content-Type':'text/plain'},
        content=json.dumps({'name':name}))
    assert response.status_code == 415
    assert integrated['runtime'].controller_for_request() is not None


@pytest.mark.parametrize('failure,status', [('authorization',401), ('preflight',503)])
def test_unknown_restore_preflight_failure_is_safe_and_does_not_revoke(integrated, monkeypatch, failure, status):
    start(integrated)
    name = integrated['client'].post('/backups', headers=HEADERS).json()['name']
    def failed(*_args):
        raise RuntimeError('private preflight path and secret')
    with monkeypatch.context() as patch:
        if failure == 'authorization':
            patch.setattr(integrated['app'].state, 'local_module_authorized', failed)
        else:
            patch.setattr(api(), '_restore_check_and_stop', failed)
        response = integrated['client'].post('/backups/restore', headers=HEADERS, json={'name':name})
    assert response.status_code == status
    assert 'private' not in response.text and 'secret' not in response.text
    assert integrated['runtime'].controller_for_request() is not None
