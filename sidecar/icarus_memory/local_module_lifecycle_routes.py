"""Fixed authenticated native lifecycle; installation/configuration live outside HTTP."""
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from .local_module_controller import ControllerError, MODEL, MODE
from .local_module_routes import _allowed, _error, _payload, _PublicError
from .local_module_runtime import ManagedLocalSourceRuntime


_PREFIX = '/api/v1/modules/local-source/runtime'


def register(app, guard, *, runtime_factory, boundary=None):
    def invoke(action):
        try:
            # Status and revocation stay accessible while ordinary work is
            # restricted. Global middleware must preserve this access too.
            with _allowed(boundary if action == 'start' else None):
                runtime = runtime_factory()
                if runtime is None and action in {'status', 'shutdown'}:
                    return dict(model=MODEL, mode=MODE, configured=False, paired=False,
                        broker_running=False, jobs_busy=False, stopping=False, restart_needed=False)
                if not isinstance(runtime, ManagedLocalSourceRuntime):
                    raise _error('Unavailable')
                if action == 'shutdown':
                    return runtime.shutdown(wait_seconds=2)
                return getattr(runtime, action)()
        except _PublicError:
            raise
        except ControllerError as error:
            raise _error(error.code) from None
        except Exception:
            raise _error('Unavailable') from None

    @app.get(_PREFIX + '/status', dependencies=guard)
    async def status(request: Request):
        await _payload(request, allow_empty=True)
        return await run_in_threadpool(invoke, 'status')

    @app.post(_PREFIX + '/initialize', dependencies=guard)
    async def initialize(request: Request):
        await _payload(request, allow_empty=True)
        return await run_in_threadpool(invoke, 'start')

    @app.post(_PREFIX + '/shutdown', dependencies=guard)
    async def shutdown(request: Request):
        await _payload(request, allow_empty=True)
        return await run_in_threadpool(invoke, 'shutdown')
