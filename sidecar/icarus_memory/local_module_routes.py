"""Authenticated, bounded HTTP seam for one already configured local controller.

The no-argument factory belongs to trusted application wiring. These routes do
not install a runtime, construct stores, choose providers or expose worker grants.
An outer application boundary still owns long-running module lifecycle shutdown.
"""
from contextlib import contextmanager
import json
import re

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .local_module_controller import ControllerError, LocalModuleController, MODEL


_PREFIX = '/api/v1/modules/local-source'
_MAX_BODY = 8192
_RUN_ID = re.compile(r'[a-f0-9]{32}\Z')
_FINGERPRINT = re.compile(r'[a-f0-9]{64}\Z')
_BINDING = re.compile(r'[A-Za-z0-9_-]{43}\Z')
_IDEMPOTENCY = re.compile(r'[A-Za-z0-9_-]{8,80}\Z')
_PREPARE = frozenset({'source_id', 'question'})
_START = _PREPARE | {'source_fingerprint', 'review_binding', 'consent', 'idempotency_key'}
_ERRORS = {
    'InvalidRequest': (400, 'Bitte Quelle, Frage und ausdrückliche Zustimmung prüfen.'),
    'ReviewChanged': (409, 'Die Grundlage hat sich geändert. Bitte die Quelle erneut prüfen.'),
    'Unavailable': (503, 'Die lokale Prüfung ist noch nicht bereit.'),
    'Busy': (409, 'Eine lokale Prüfung läuft noch. Bitte kurz warten.'),
    'Capacity': (429, 'Zu viele Prüfungen. Bitte später erneut versuchen.'),
    'NotFound': (404, 'Diese Prüfung ist nicht mehr verfügbar.'),
    'Restarted': (503, 'Die lokale Prüfung wurde durch einen Neustart beendet.'),
    'Failed': (503, 'Die lokale Prüfung konnte nicht abgeschlossen werden.'),
    'Cancelled': (409, 'Die lokale Prüfung wurde gestoppt.'),
    'TimedOut': (504, 'Die lokale Prüfung hat das Zeitlimit erreicht.'),
}
_NOTICE = ('Der Status zeigt nur Konfiguration und Rechenbelegung. '
           'Er bestätigt weder Laufzeitbereitschaft noch Isolation.')


class _PublicError(HTTPException):
    """Only failures created by this boundary may pass through unchanged."""


def _error(code, *, status=None):
    safe_status, message = _ERRORS.get(code, _ERRORS['Unavailable'])
    safe_code = code if code in _ERRORS else 'Unavailable'
    return _PublicError(status_code=status or safe_status, detail={'code': safe_code, 'message': message})


def _pairs(entries):
    result = {}
    for key, value in entries:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError('finite JSON required')


async def _payload(request, fields=frozenset(), *, allow_empty=False):
    # Parse here instead of a framework body model: validation errors must never
    # echo question text, unexpected credentials, provider URLs or input values.
    if request.query_params:
        raise _error('InvalidRequest')
    lengths = request.headers.getlist('content-length')
    if len(lengths) > 1 or (lengths and not re.fullmatch(r'[0-9]{1,10}', lengths[0])):
        raise _error('InvalidRequest')
    if lengths and int(lengths[0]) > _MAX_BODY:
        raise _error('InvalidRequest', status=413)
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > _MAX_BODY:
                raise _error('InvalidRequest', status=413)
            raw.extend(chunk)
    except _PublicError:
        raise
    except Exception:
        raise _error('InvalidRequest') from None
    if not raw and allow_empty:
        return {}
    if (request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json'
            or request.headers.get('content-encoding', 'identity').lower() != 'identity'):
        raise _error('InvalidRequest', status=415)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_nonfinite)
        if type(value) is not dict or value.keys() != fields:
            raise ValueError('closed JSON object required')
    except (ValueError, UnicodeError, RecursionError):
        raise _error('InvalidRequest') from None
    return value


def _review_request(value):
    if (type(value['source_id']) is not str or not 1 <= len(value['source_id']) <= 80
            or type(value['question']) is not str
            or not 1 <= len(value['question'].strip()) <= len(value['question']) <= 1200):
        raise _error('InvalidRequest')


def _start_request(value):
    _review_request(value)
    if (value['consent'] is not True
            or type(value['source_fingerprint']) is not str
            or not _FINGERPRINT.fullmatch(value['source_fingerprint'])
            or type(value['review_binding']) is not str
            or not _BINDING.fullmatch(value['review_binding'])
            or type(value['idempotency_key']) is not str
            or not _IDEMPOTENCY.fullmatch(value['idempotency_key'])):
        raise _error('InvalidRequest')


@contextmanager
def _allowed(boundary):
    acquired = False
    try:
        if boundary is not None:
            boundary.check()
            # Do not wait through an exclusive update and then admit an old
            # request. A check-only injected boundary remains useful in tests.
            if hasattr(boundary, 'try_enter'):
                if not boundary.try_enter():
                    raise _error('Unavailable')
                acquired = True
            boundary.check()
        yield
        if boundary is not None:
            boundary.check()
    finally:
        if acquired:
            boundary.leave()


def register(app, guard, *, controller_factory, boundary=None):
    """Register only main-application routes; factory never receives input."""
    def invoke(method, *args, **kwargs):
        try:
            # Revocation remains possible during restore/update, unlike new
            # reviews, execution admissions and reads of earlier results.
            with _allowed(None if method == 'cancel' else boundary):
                controller = controller_factory()
                if controller is None and method == 'status':
                    return {'status': 'not_installed', 'model': MODEL, 'notice': _NOTICE}
                if not isinstance(controller, LocalModuleController):
                    raise _error('Unavailable')
                if method == 'status':
                    return {'status': 'configured', 'model': MODEL,
                            'runtime': controller.runtime_status(), 'notice': _NOTICE}
                return getattr(controller, method)(*args, **kwargs)
        except _PublicError:
            raise
        except ControllerError as error:
            # Use the fixed table, never str(error), args or provider diagnostics.
            raise _error(error.code) from None
        except Exception:
            raise _error('Unavailable') from None

    async def run_request(request, run_id):
        await _payload(request, allow_empty=True)
        if not _RUN_ID.fullmatch(run_id):
            raise _error('InvalidRequest')

    @app.get(_PREFIX + '/status', dependencies=guard)
    async def status(request: Request):
        await _payload(request, allow_empty=True)
        return await run_in_threadpool(invoke, 'status')

    @app.post(_PREFIX + '/prepare', dependencies=guard)
    async def prepare(request: Request):
        value = await _payload(request, _PREPARE)
        _review_request(value)
        return await run_in_threadpool(invoke, 'prepare', value['source_id'], value['question'])

    @app.post(_PREFIX + '/start', dependencies=guard)
    async def start(request: Request):
        value = await _payload(request, _START)
        _start_request(value)
        source_id = value.pop('source_id')
        return await run_in_threadpool(invoke, 'start', source_id, **value)

    @app.get(_PREFIX + '/runs/{run_id}', dependencies=guard)
    async def poll(run_id: str, request: Request):
        await run_request(request, run_id)
        return await run_in_threadpool(invoke, 'poll', run_id)

    @app.post(_PREFIX + '/runs/{run_id}/cancel', dependencies=guard)
    async def cancel(run_id: str, request: Request):
        await run_request(request, run_id)
        return await run_in_threadpool(invoke, 'cancel', run_id)
