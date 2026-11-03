"""Trusted main-app wiring and maintenance seams; runtime remains opt-in and idle."""
from contextlib import asynccontextmanager, contextmanager, ExitStack
import json
import os
from pathlib import Path
import re
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .local_module_controller import MODE
from .local_module_model import VerifiedModuleModel
from .local_module_runtime import ManagedLocalSourceRuntime
from .model_roles import rollen_von


_KEY = re.compile(r'[A-Za-z0-9_-]{43}\Z')
_MESSAGE = 'Die lokale Prüfung wird noch beendet. Bitte kurz warten und erneut versuchen.'
_ADMIN = {('GET', '/api/v1/modules/local-source/runtime/status'),
          ('POST', '/api/v1/modules/local-source/runtime/shutdown')}


class ModuleMaintenanceError(RuntimeError):
    def __init__(self):
        super().__init__(_MESSAGE)


def runtime(app):
    return getattr(app.state, 'local_source_runtime', None)


def configure(app):
    """Only trusted launch environment can construct; never start or reconcile."""
    if hasattr(app.state, 'local_source_runtime'):
        return runtime(app)
    app.state.local_source_runtime = None
    key = os.environ.get('KF_GATEWAY_CONTROL_KEY', '')
    if os.environ.get('KF_HARNESS_MODE') != MODE or not _KEY.fullmatch(key):
        return None
    try:
        model = VerifiedModuleModel(lambda: rollen_von(app).provider('hintergrund'),
            app.state.conversation_lock, boundary=app.state.runtime_boundary)
        app.state.local_source_runtime = ManagedLocalSourceRuntime(
            app.state.episodes, app.state.procedures, model, key)
    except Exception:
        # A missing optional runtime never prevents opening the ordinary app.
        pass
    return runtime(app)


def controller(app):
    manager = runtime(app)
    return manager.controller_for_request() if manager is not None else None


def stop_for_transition(app, *, wait_seconds=2):
    manager = runtime(app)
    if manager is None:
        return
    try:
        value = manager.shutdown(wait_seconds=wait_seconds)
        if value['stopping'] or value['jobs_busy'] or value['broker_running']:
            raise ModuleMaintenanceError()
    except Exception:
        raise ModuleMaintenanceError() from None


@contextmanager
def backup_context(app, *, before_update=False):
    manager = runtime(app)
    if manager is None:
        yield
        return
    if before_update:
        stop_for_transition(app)
        yield
        return
    with ExitStack() as stack:
        try:
            stack.enter_context(manager.paused_for_backup(wait_seconds=2))
        except Exception:
            raise ModuleMaintenanceError() from None
        yield


def scheduled_backup(app, backup):
    def run():
        try:
            with backup_context(app):
                return backup()
        except ModuleMaintenanceError:
            from .scheduler import JobResult
            return JobResult('sicherung', False, _MESSAGE)
    return run


def install(app, guard, *, authorized):
    configure(app)
    app.state.local_module_authorized = authorized
    from .local_module_routes import register as source_routes
    from .local_module_lifecycle_routes import register as lifecycle_routes
    source_routes(app, guard, controller_factory=lambda: controller(app), boundary=app.state.runtime_boundary)
    lifecycle_routes(app, guard, runtime_factory=lambda: runtime(app), boundary=app.state.runtime_boundary)
    async def shutdown():
        manager = runtime(app)
        if manager is not None:
            # Bounded fallback revocation. Native must verify the explicit
            # shutdown status before terminating its processes or replacing data.
            try:
                await run_in_threadpool(manager.shutdown, wait_seconds=2)
            except Exception:
                pass
    previous_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(target):
        async with previous_lifespan(target) as state:
            try:
                yield state
            finally:
                await shutdown()
    app.router.lifespan_context = lifespan


def authorized(app, scope):
    check = getattr(app.state, 'local_module_authorized', None)
    try:
        return bool(check and check(scope))
    except Exception:
        return False


def _restore_check_and_stop(app, directory, name):
    from .backup import verify_legacy_snapshot, verify_snapshot_set
    target = Path(directory) / 'sicherungen' / Path(name).name
    if not target.is_file() and not target.is_dir():
        return JSONResponse({'detail': 'Diese Sicherung ist nicht verfügbar.'}, status_code=404)
    try:
        verify_snapshot_set(target) if target.is_dir() else verify_legacy_snapshot(target)
    except Exception:
        return JSONResponse({'detail': 'Diese Sicherung konnte nicht geprüft werden.'}, status_code=409)
    try:
        stop_for_transition(app)
    except ModuleMaintenanceError:
        return JSONResponse({'detail': _MESSAGE}, status_code=409)
    return None


async def before_restore(app, scope, receive):
    """Auth and bounded snapshot preflight before waiting on module readers.

    Middleware records/replays the bounded messages consumed here. A rejected
    snapshot does not interrupt a module, and no password is accepted or logged.
    """
    if runtime(app) is None:
        return None
    if not authorized(app, scope):
        return JSONResponse({'detail': 'Ungültiges Token'}, status_code=401)
    request = Request(scope, receive)
    content_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if ((content_type and content_type != 'application/json')
            or request.headers.get('content-encoding', 'identity').lower() != 'identity'):
        return JSONResponse({'detail': 'Bitte eine gültige Sicherungsanfrage senden.'}, status_code=415)
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 8192:
                return JSONResponse({'detail': 'Die Wiederherstellungsanfrage ist zu groß.'}, status_code=413)
            raw.extend(chunk)
        from .local_module_routes import _pairs, _nonfinite
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_nonfinite)
        if (type(value) is not dict or set(value) != {'name'} or type(value['name']) is not str
                or not 1 <= len(value['name']) <= 255):
            raise ValueError()
    except Exception:
        return JSONResponse({'detail': 'Bitte eine gültige Sicherung auswählen.'}, status_code=422)
    try:
        return await run_in_threadpool(_restore_check_and_stop, app, app.state.runtime_boundary.directory, value['name'])
    except Exception:
        return JSONResponse({'detail': 'Die Wiederherstellung ist noch nicht bereit.'}, status_code=503)


class _InspectionAdmin:
    def __init__(self, app, admin):
        self.app, self.admin = app, admin
    async def __call__(self, scope, receive, send):
        target = self.admin if scope['type'] == 'http' and (scope['method'], scope['path']) in _ADMIN else self.app
        return await target(scope, receive, send)


def inspection_admin(app, expected):
    """Historical cold boot has no runtime, yet fixed native status/stop work."""
    admin = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    def auth(request: Request):
        values = [request.headers.get('x-icarus-token'), request.cookies.get('kingfisher_session')]
        if expected is not None and not any(value is not None and secrets.compare_digest(value, expected) for value in values):
            raise HTTPException(401, 'Ungültiges Token')
    from .local_module_lifecycle_routes import register
    register(admin, [Depends(auth)], runtime_factory=lambda: None)
    app.add_middleware(_InspectionAdmin, admin=admin)
