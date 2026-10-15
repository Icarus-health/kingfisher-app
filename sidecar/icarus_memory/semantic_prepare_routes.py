"""One explicit local embedding batch, independent of heavy classification."""
from contextlib import nullcontext
from dataclasses import asdict
import threading

from . import working_memory_semantic_runtime as runtime
from .hintergrund import GRUND_TEXT
from . import storage_capacity


def register(app, guard, data_dir):
    single_flight = threading.Lock()

    def blocked():
        # Check storage independently even when the background controller has
        # not been wired. Its live gate also covers power and memory pressure.
        reason = storage_capacity.reason(data_dir())
        control = getattr(app.state, 'hintergrund', None)
        if reason is None:
            reason = control.sperre() if control is not None else 'control_unavailable'
        # This explicit foreground request is itself recorded as user input.
        # Only its soft idle delay is irrelevant; pause, resources and running
        # answers take precedence in Steuerung.sperre and remain live gates.
        return None if reason == 'nutzer' else reason

    def response(status, reason=None, result=None):
        return {'status': status, 'reason': reason,
                'detail': GRUND_TEXT.get(reason, {
                    'busy': 'Die Suchvorbereitung läuft bereits.',
                    'not_ready': 'Die lokale Bedeutungssuche ist noch nicht bereit.',
                    'changed': 'Die Freigabe oder Suchkonfiguration hat sich geändert.',
                    'control_unavailable': 'Die Ressourcenprüfung ist noch nicht bereit.',
                }.get(reason, '')),
                'job': asdict(result) if result is not None else None,
                'semantic_index': runtime.coverage(app)}

    @app.post('/api/v1/memory/semantic/prepare', dependencies=guard)
    def prepare():
        if not single_flight.acquire(blocking=False):
            return response('waiting', 'busy')
        try:
            boundary = getattr(app.state, 'runtime_boundary', None)
            with boundary.operation() if boundary is not None else nullcontext():
                service = runtime.search(app)
                if service is None:
                    return response('not_ready', 'not_ready')
                configuration = service._configuration()

                def permitted():
                    return (runtime.search(app) is service
                            and service._configuration() == configuration
                            and blocked() is None)

                reason = blocked()
                if reason is not None:
                    return response('waiting', reason)
                # index_batch checks this predicate before model transport and
                # again under the conversation lock before committing vectors.
                result = service.index_batch(permitted=permitted)
                reason = blocked()
                if reason is not None:
                    return response('waiting', reason, result)
                if not permitted():
                    return response('not_ready', 'changed', result)
                coverage = service.coverage()
                if not result.ok or coverage['status'] in {'unavailable', 'disabled'}:
                    return response('not_ready', 'not_ready', result)
                return response('prepared', result=result)
        finally:
            single_flight.release()
