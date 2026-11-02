"""Managed lifecycle with real canonical stores/model adapter; fake listeners only."""
from contextlib import contextmanager
import importlib
import json
import threading
import time

from fastapi.testclient import TestClient
import pytest

from icarus_memory.local_module_controller import ControllerError, MODEL, MODE
from tests.test_local_module_controller import env, GatewayFixture, QUESTION, begin, terminal
from tests.test_local_module_model import fixture as verified


KEY = 'k' * 43


def api():
    return importlib.import_module('icarus_memory.local_module_runtime')


class Listener:
    def __init__(self):
        self.live = self.ready = False
        self.fail = self.sticky = False
        self.starts = self.stops = 0
        self.app = None
    def start(self, app, *, timeout_seconds):
        self.starts += 1
        assert 0 < timeout_seconds <= 2
        self.app = app
        if self.fail:
            raise OSError('private bind diagnostic and control credential')
        self.live = self.ready = True
    def running(self):
        return self.live and self.ready
    def alive(self):
        return self.live
    def stop(self):
        self.stops += 1
        self.ready = False
        if not self.sticky:
            self.live = False


class Gateway(GatewayFixture):
    def __init__(self):
        super().__init__()
        self.health_value['osIsolationVerified'] = False
        self.initializations = self.healths = 0
        self.init_error = None
        self.init_entered, self.init_release = threading.Event(), threading.Event()
        self.init_release.set()
    def initialize(self):
        self.initializations += 1
        self.init_entered.set()
        assert self.init_release.wait(3)
        if self.init_error:
            raise self.init_error
        return {'status': 'initialized'}
    def health(self):
        self.healths += 1
        return super().health()


@pytest.fixture
def managed(env, verified):
    gateway, listener = Gateway(), Listener()
    model = verified['create']()
    runtime = api().ManagedLocalSourceRuntime(env['episodes'], env['skills'], model, KEY,
        listener_factory=lambda: listener, gateway=gateway)
    gateway.controller = runtime._controller
    yield dict(runtime=runtime, gateway=gateway, listener=listener, model=model,
               env=env, verified=verified)
    gateway.init_release.set()
    gateway.release.set()
    listener.sticky = False
    result = runtime.shutdown(wait_seconds=2)
    assert result['stopping'] is False and result['jobs_busy'] is False


def ready(managed):
    runtime = managed['runtime']
    status = runtime.start()
    assert status['paired'] is True and status['broker_running'] is True
    controller = runtime.controller_for_request()
    assert controller is managed['gateway'].controller
    return controller


def test_constructor_status_and_factory_cannot_adopt_an_old_healthy_worker(managed):
    runtime, gateway = managed['runtime'], managed['gateway']
    assert runtime.controller_for_request() is None
    assert runtime.status() == dict(model=MODEL, mode=MODE, configured=True, paired=False,
        broker_running=False, jobs_busy=False, stopping=False, restart_needed=False)
    assert gateway.initializations == gateway.healths == 0
    assert managed['listener'].starts == 0
    assert managed['verified']['requests'] == []


def test_only_explicit_start_pairs_once_and_exposes_separate_scoped_app(managed):
    controller = ready(managed)
    assert managed['runtime'].start()['paired'] is True
    assert managed['gateway'].initializations == managed['listener'].starts == 1
    assert managed['verified']['requests'] == []
    client = TestClient(managed['listener'].app)
    assert client.get('/docs').status_code == 404
    assert client.get('/api/v1/modules/local-source/status').status_code == 404
    assert client.get('/').status_code == 404
    for key in (KEY, 'ui-bootstrap-token', 'master-app-token'):
        response = client.post('/worker/mcp', headers={'Authorization': 'Bearer ' + key},
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        assert response.status_code == 401
    review = controller.prepare(managed['env']['source'].id, QUESTION)
    assert review['model'] == MODEL
    assert managed['verified']['requests']
    assert not any(path == '/api/chat' for path, *_ in managed['verified']['requests'])


def test_listener_bind_failure_is_sanitized_latched_and_never_pairs(managed):
    managed['listener'].fail = True
    with pytest.raises(ControllerError) as error:
        managed['runtime'].start()
    assert error.value.code == 'Unavailable' and 'private' not in str(error.value)
    assert managed['gateway'].initializations == 0
    assert managed['runtime'].controller_for_request() is None
    assert managed['runtime'].status()['restart_needed'] is True
    managed['listener'].fail = False
    with pytest.raises(ControllerError):
        managed['runtime'].start()
    assert managed['listener'].starts == 1 and managed['gateway'].initializations == 0


@pytest.mark.parametrize('failure', ['lost_reply', 'bad_reply', 'synthetic', 'unverified_flag', 'wrong_model'])
def test_failed_or_uncertain_pair_never_retries_or_adopts_existing_health(managed, failure):
    gateway = managed['gateway']
    if failure == 'lost_reply':
        gateway.init_error = TimeoutError('private key or lost initialized reply')
    elif failure == 'bad_reply':
        gateway.initialize = lambda: {'status': 'initialized', 'key': KEY}
    elif failure == 'synthetic':
        gateway.health_value['syntheticOnly'] = True
    elif failure == 'unverified_flag':
        gateway.health_value['osIsolationVerified'] = True
    else:
        gateway.health_value['model'] = 'other-model'
    with pytest.raises(ControllerError):
        managed['runtime'].start()
    assert managed['runtime'].controller_for_request() is None
    status = managed['runtime'].status()
    assert status['restart_needed'] is True and status['paired'] is False
    count = gateway.initializations
    gateway.init_error = None
    gateway.health_value.update(syntheticOnly=False, model=MODEL, osIsolationVerified=False)
    with pytest.raises(ControllerError):
        managed['runtime'].start()
    assert gateway.initializations == count
    assert managed['verified']['requests'] == []


@pytest.mark.parametrize('change', ['generation', 'listener', 'metadata_failure'])
def test_ready_pair_replacement_or_loss_revokes_and_cannot_reactivate(managed, change):
    controller = ready(managed)
    review = controller.prepare(managed['env']['source'].id, QUESTION)
    if change == 'generation':
        managed['gateway'].health_value['instance'] = 'b' * 64
    elif change == 'listener':
        managed['listener'].live = False
    else:
        managed['gateway'].health = lambda: (_ for _ in ()).throw(RuntimeError('private worker failure'))
    assert managed['runtime'].controller_for_request() is None
    assert managed['runtime'].status()['restart_needed'] is True
    with pytest.raises(ControllerError):
        begin(controller, managed['env']['source'], review=review)
    assert not managed['gateway'].tokens


def test_runtime_pins_same_verified_model_and_canonical_stores_without_writes(managed):
    episodes = managed['env']['episodes']
    before = '\n'.join(episodes._conn.iterdump())
    skills = managed['env']['skills'].items()
    controller = ready(managed)
    run = begin(controller, managed['env']['source'])
    result = terminal(controller, run)
    assert result['status'] == 'completed' and result['verified'] is False
    assert result['evidence'][0]['id'] == managed['env']['source'].id
    assert len([path for path, *_ in managed['verified']['requests'] if path == '/api/chat']) == 1
    assert '\n'.join(episodes._conn.iterdump()) == before
    assert managed['env']['skills'].items() == skills
    status = managed['runtime'].status()
    assert set(status) == {'model','mode','configured','paired','broker_running','jobs_busy','stopping','restart_needed'}
    assert KEY not in json.dumps(status) and 'http' not in json.dumps(status)


def test_shutdown_revokes_before_stopping_listener_and_waits_for_live_inference(managed):
    controller = ready(managed)
    entered, release, exited = (threading.Event() for _ in range(3))
    def block_model(request):
        if request.url.path == '/api/chat':
            entered.set()
            try:
                assert release.wait(3)
            finally:
                exited.set()
    managed['verified']['state']['hook'] = block_model
    gateway = managed['gateway']
    requests, workers = [], []
    def detached(token, question, cancelled, deadline):
        gateway.tokens.append(token)
        worker = threading.Thread(target=lambda: requests.append(TestClient(controller.worker_app()).post(
            '/worker/v1/chat/completions', headers={'Authorization': 'Bearer ' + token},
            json=dict(model=MODEL, messages=[dict(role='user', content=question)], stream=True, tools=[]))))
        workers.append(worker); worker.start()
        assert entered.wait(3)
        gateway.entered.set()
        assert cancelled.wait(3)
        gateway.exited.set()
        raise TimeoutError('detached private inference still active')
    gateway.run = detached
    run = begin(controller, managed['env']['source'])
    try:
        assert gateway.entered.wait(3)
        started = time.monotonic()
        status = managed['runtime'].shutdown(wait_seconds=.02)
        assert time.monotonic() - started < .5
        assert status['stopping'] is True and status['jobs_busy'] is True
        assert status['paired'] is False
        assert managed['listener'].stops == 0 and managed['listener'].running()
        assert managed['runtime'].controller_for_request() is None
        assert controller.poll(run['id'])['status'] == 'restarted'
        assert controller._broker.current(gateway.tokens[0]) is False
    finally:
        release.set()
    assert exited.wait(3)
    for worker in workers:
        worker.join(3)
    status = managed['runtime'].shutdown(wait_seconds=1)
    assert status['stopping'] is False and status['jobs_busy'] is False
    assert status['broker_running'] is False and managed['listener'].stops == 1
    assert all('Late' not in request.text for request in requests)


def test_shutdown_during_initialization_retains_listener_until_callback_exits(managed):
    gateway = managed['gateway']
    gateway.init_release.clear()
    errors = []
    def start():
        try:
            managed['runtime'].start()
        except ControllerError as error:
            errors.append(error.code)
    task = threading.Thread(target=start)
    task.start()
    try:
        assert gateway.init_entered.wait(1)
        status = managed['runtime'].shutdown(wait_seconds=.01)
        assert status['stopping'] is True and status['paired'] is False
        assert managed['listener'].stops == 0
    finally:
        gateway.init_release.set()
        task.join(3)
    assert errors and managed['runtime'].controller_for_request() is None
    assert managed['runtime'].shutdown(wait_seconds=1)['stopping'] is False


def test_shutdown_reports_stopping_until_listener_thread_actually_exits(managed):
    ready(managed)
    managed['listener'].sticky = True
    status = managed['runtime'].shutdown(wait_seconds=.01)
    assert status['stopping'] is True and status['broker_running'] is False
    assert managed['listener'].stops == 1
    assert managed['runtime'].shutdown(wait_seconds=.01)['stopping'] is True
    assert managed['listener'].stops == 1
    managed['listener'].live = False
    assert managed['runtime'].status()['stopping'] is False


@pytest.mark.parametrize('seconds', [-1, 3, True, '1'])
def test_shutdown_wait_is_strict_and_bounded(managed, seconds):
    with pytest.raises(ValueError):
        managed['runtime'].shutdown(wait_seconds=seconds)


def test_backup_pause_does_not_stop_runtime_or_rewrite_originals(managed):
    controller = ready(managed)
    review = controller.prepare(managed['env']['source'].id, QUESTION)
    before = '\n'.join(managed['env']['episodes']._conn.iterdump())
    with managed['runtime'].paused_for_backup(wait_seconds=.1):
        assert managed['runtime'].controller_for_request() is None
        with pytest.raises(ControllerError):
            begin(controller, managed['env']['source'], review=review)
        assert managed['listener'].running() and managed['listener'].stops == 0
    assert managed['runtime'].controller_for_request() is controller
    assert '\n'.join(managed['env']['episodes']._conn.iterdump()) == before


def test_backup_failure_releases_pause_without_stopping_idle_worker(managed, monkeypatch):
    controller = ready(managed)
    @contextmanager
    def unavailable(*, wait_seconds):
        raise ControllerError(409, 'Busy')
        yield
    with monkeypatch.context() as patch:
        patch.setattr(controller, 'quiescent', unavailable)
        with pytest.raises(ControllerError) as error:
            with managed['runtime'].paused_for_backup(wait_seconds=.01):
                pytest.fail('backup entered before real quiescence')
        assert error.value.code == 'Busy'
    assert managed['runtime'].controller_for_request() is controller
    assert managed['listener'].running() and managed['listener'].stops == 0


def test_production_listener_uses_fixed_background_address_without_access_logs(monkeypatch):
    import uvicorn
    from types import SimpleNamespace
    captured, threads = {}, []
    exited = threading.Event()
    def configuration(app, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(app=app)
    class Server:
        def __init__(self, config):
            self.started = self.should_exit = False
            self.config = config
        def run(self):
            threads.append(threading.get_ident())
            self.started = True
            while not self.should_exit:
                time.sleep(.005)
            exited.set()
    with monkeypatch.context() as patch:
        patch.setattr(uvicorn, 'Config', configuration)
        patch.setattr(uvicorn, 'Server', Server)
        listener = api()._BrokerListener()
        try:
            listener.start(object(), timeout_seconds=.2)
            assert listener.running()
            assert captured['host'] == '0.0.0.0' and captured['port'] == 8892
            assert captured['access_log'] is False and captured['log_config'] is None
            assert captured['log_level'] == 'critical' and captured['proxy_headers'] is False
            assert threads and threads[0] != threading.get_ident()
        finally:
            listener.stop()
        assert exited.wait(1)
        deadline = time.monotonic() + 1
        while listener.alive() and time.monotonic() < deadline:
            time.sleep(.005)
        assert not listener.alive()


def test_background_listener_bind_exit_never_propagates_private_diagnostics(monkeypatch, capsys):
    import uvicorn
    from types import SimpleNamespace
    class Server:
        started = should_exit = False
        def __init__(self, _config):
            pass
        def run(self):
            raise SystemExit('private bind path and key')
    with monkeypatch.context() as patch:
        patch.setattr(uvicorn, 'Config', lambda *_args, **_kwargs: SimpleNamespace())
        patch.setattr(uvicorn, 'Server', Server)
        listener = api()._BrokerListener()
        with pytest.raises(Exception) as error:
            listener.start(object(), timeout_seconds=.2)
        assert 'private' not in str(error.value)
        assert not listener.alive()
    output = capsys.readouterr()
    assert 'private' not in output.out + output.err


@pytest.mark.parametrize('operation', ['running', 'alive'])
def test_unknown_listener_state_is_sanitized_without_claiming_quiescence(managed, monkeypatch, operation):
    ready(managed)
    def failed():
        raise RuntimeError('private listener state and key')
    with monkeypatch.context() as patch:
        patch.setattr(managed['listener'], operation, failed)
        if operation == 'alive':
            status = managed['runtime'].shutdown(wait_seconds=.01)
            assert status['stopping'] is True
        else:
            status = managed['runtime'].status()
            assert status['paired'] is False and status['broker_running'] is False
        assert status['restart_needed'] is True
        assert 'private' not in json.dumps(status)
