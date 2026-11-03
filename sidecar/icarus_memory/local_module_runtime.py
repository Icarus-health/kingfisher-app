"""Explicit managed pairing and bounded quiescence; no installation or OS proof.

Native wiring must verify its fixed runtime/configuration before exposing start.
A fresh controller never adopts a healthy worker without its own acknowledged
one-time initialize. Any uncertainty requires fresh worker/gateway processes.
"""
from contextlib import contextmanager
import re
import threading
import time

from .harness_broker import Broker
from .local_module_controller import ControllerError, LocalModuleController, MODEL, MODE
from .local_module_gateway import FixedGatewayClient, GatewayError
from .local_module_model import VerifiedModuleModel


_INSTANCE = re.compile(r'[a-f0-9]{32,64}\Z')
_HEALTH = {'status', 'mode', 'model', 'syntheticOnly', 'osIsolationVerified', 'instance'}


def _wait_limit(value):
    if type(value) not in (int, float) or not 0 <= value <= 2:
        raise ValueError('invalid shutdown wait')


def _generation(value):
    if (type(value) is not dict or set(value) != _HEALTH or value.get('status') != 'ok'
            or value.get('mode') != MODE or value.get('model') != MODEL
            or value.get('syntheticOnly') is not False or value.get('osIsolationVerified') is not False
            or type(value.get('instance')) is not str or not _INSTANCE.fullmatch(value['instance'])):
        raise GatewayError()
    return value['instance']


class _BrokerListener:
    """Only the separate grant-scoped app can be bound on the fixed broker port."""
    def __init__(self):
        self._server = self._thread = None
        self._exited = threading.Event()

    def start(self, app, *, timeout_seconds):
        import uvicorn
        config = uvicorn.Config(app, host='0.0.0.0', port=8892, access_log=False,
            log_config=None, log_level='critical', proxy_headers=False, server_header=False,
            lifespan='off', timeout_keep_alive=1, timeout_graceful_shutdown=1,
            limit_concurrency=8, backlog=8)
        self._server = uvicorn.Server(config)
        def serve():
            try:
                self._server.run()
            except BaseException:
                # Bind/SystemExit errors are private diagnostics, not app failure.
                pass
            finally:
                self._exited.set()
        self._thread = threading.Thread(target=serve, name='kf-module-broker', daemon=True)
        self._thread.start()
        deadline = time.monotonic() + timeout_seconds
        while not self.running():
            if self._exited.wait(.005) or time.monotonic() >= deadline:
                raise GatewayError()

    def running(self):
        return bool(self.alive() and self._server.started and not self._server.should_exit)

    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        if self._server is not None:
            self._server.should_exit = True


class _PairedGateway:
    def __init__(self, runtime):
        self._runtime = runtime

    def health(self):
        return self._runtime._health()

    def run(self, *args):
        return self._runtime._call('run', *args)


class ManagedLocalSourceRuntime:
    def __init__(self, episodes, procedures, model_adapter, control_key, *,
                 listener_factory=None, gateway=None):
        if not isinstance(model_adapter, VerifiedModuleModel):
            raise ValueError('verified local module adapter required')
        fixed = FixedGatewayClient(control_key)
        self._gateway = gateway if gateway is not None else fixed
        self._listener_factory = listener_factory or _BrokerListener
        self._listener = None
        self._lock = threading.RLock()
        self._attempted = self._starting = self._closed = self._stopping = False
        self._restart_needed = self._stop_sent = self._paused = False
        self._pair = None
        self._callbacks = 0
        self._controller = LocalModuleController(Broker(episodes, procedures),
            gateway=_PairedGateway(self), provider=model_adapter.identity, infer=model_adapter.infer)

    def _call(self, name, *args, startup=False):
        with self._lock:
            if self._closed or (self._pair is None and not startup):
                raise GatewayError()
            self._callbacks += 1
        try:
            return getattr(self._gateway, name)(*args)
        finally:
            with self._lock:
                self._callbacks -= 1

    def _invalidate(self):
        with self._lock:
            self._closed = self._stopping = self._restart_needed = True
            self._pair = None
        self._controller.close(wait_seconds=0)
        self._progress_shutdown()

    def _health(self):
        try:
            value = self._call('health')
            generation = _generation(value)
            with self._lock:
                if self._closed or generation != self._pair:
                    raise GatewayError()
            return value
        except Exception:
            self._invalidate()
            raise GatewayError() from None

    def start(self):
        """Explicit once only; main-app lifespan must never call this implicitly."""
        with self._lock:
            if self._closed or self._restart_needed:
                raise ControllerError(503, 'Restarted')
            if self._starting or self._paused:
                raise ControllerError(409, 'Busy')
            repeated = self._attempted
            if not repeated:
                self._attempted = self._starting = True
        if repeated:
            return self.status()
        try:
            listener = self._listener_factory()
            with self._lock:
                self._listener = listener
                if self._closed:
                    raise GatewayError()
            listener.start(self._controller.worker_app(), timeout_seconds=2)
            if not listener.running():
                raise GatewayError()
            reply = self._call('initialize', startup=True)
            if reply != {'status': 'initialized'}:
                raise GatewayError()
            generation = _generation(self._call('health', startup=True))
            with self._lock:
                if self._closed or not listener.running():
                    raise GatewayError()
                self._pair = generation
            return self._snapshot()
        except Exception:
            self._invalidate()
            raise ControllerError(503, 'Unavailable') from None
        finally:
            with self._lock:
                self._starting = False
            self._progress_shutdown()

    def controller_for_request(self):
        with self._lock:
            if self._closed or self._starting or self._paused or self._pair is None:
                return None
        try:
            if not self._listener_state('running'):
                raise GatewayError()
            self._health()
            with self._lock:
                if not self._closed and not self._paused and self._pair is not None:
                    return self._controller
        except Exception:
            self._invalidate()
        return None

    def _listener_state(self, name):
        if self._listener is None:
            return False
        try:
            return bool(getattr(self._listener, name)())
        except Exception:
            # Unknown liveness must keep shutdown pending, never promise stop.
            return name == 'alive'

    def _progress_shutdown(self):
        busy = self._controller.runtime_status()['busy']
        with self._lock:
            if not self._stopping or busy or self._starting or self._callbacks:
                return
            if self._listener is not None and not self._stop_sent:
                self._stop_sent = True
                try:
                    self._listener.stop()
                except Exception:
                    # Keep stopping while the listener still reports alive.
                    pass
            if not self._listener_state('alive'):
                self._stopping = False

    def _snapshot(self):
        jobs_busy = self._controller.runtime_status()['busy']
        with self._lock:
            return dict(model=MODEL, mode=MODE, configured=True,
                paired=self._pair is not None and not self._closed,
                broker_running=self._listener_state('running'),
                jobs_busy=jobs_busy, stopping=self._stopping, restart_needed=self._restart_needed)

    def status(self):
        """Explicit metadata only; never initialize, infer, download or adopt."""
        with self._lock:
            paired = self._pair is not None and not self._closed
        if paired:
            self.controller_for_request()
        self._progress_shutdown()
        return self._snapshot()

    def shutdown(self, *, wait_seconds=0):
        """Revoke first; listener teardown follows actual compute/callback drain."""
        _wait_limit(wait_seconds)
        deadline = time.monotonic() + wait_seconds
        with self._lock:
            self._closed = self._stopping = self._restart_needed = True
            self._pair = None
        self._controller.close(wait_seconds=0)
        while True:
            self._progress_shutdown()
            result = self._snapshot()
            if not result['stopping'] or time.monotonic() >= deadline:
                return result
            time.sleep(min(.005, max(0, deadline - time.monotonic())))

    @contextmanager
    def paused_for_backup(self, *, wait_seconds=2):
        """Reuse controller quiescence; do not stop an idle listener or worker."""
        _wait_limit(wait_seconds)
        with self._lock:
            if self._paused or self._starting:
                raise ControllerError(409, 'Busy')
            self._paused = True
            closed = self._closed
        try:
            if closed:
                if self._controller.runtime_status()['busy']:
                    raise ControllerError(409, 'Busy')
                yield
            else:
                with self._controller.quiescent(wait_seconds=wait_seconds):
                    yield
        finally:
            with self._lock:
                self._paused = False
