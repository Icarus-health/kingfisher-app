"""One ephemeral local source review; registration/installation are separate.

Only trusted application wiring constructs this controller and its unbound
worker app. No request supplies a provider, URL, model, executable or tool set.
Existing synthetic-only workers deliberately fail the controlled-mode contract.
"""
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import re
import secrets
import threading
import time

from fastapi import FastAPI

from .episodes import AUSGEBLENDETE_ZUSTAENDE, CHAT_LOOKUP_TAG
from .harness_broker import BridgeError
from .harness_protocol import register


MODEL = 'kingfisher-qwen3.5:9b-8k'
MODE = 'controlled-local-readonly-v1'
LIMITS = dict(seconds=120, tools=8, model_calls=3, protocol_requests=40, sources=1)
_NONCE = re.compile(r'[A-Za-z0-9_-]{43}\Z')
_IDEMPOTENCY = re.compile(r'[A-Za-z0-9_-]{8,80}\Z')
_INSTANCE = re.compile(r'[a-f0-9]{32,64}\Z')
_MESSAGES = {
    'InvalidRequest': 'Bitte Quelle, Frage und ausdrückliche Zustimmung prüfen.',
    'ReviewChanged': 'Die Grundlage hat sich geändert. Bitte die Quelle erneut prüfen.',
    'Unavailable': 'Die lokale Prüfung ist noch nicht bereit.',
    'Busy': 'Eine lokale Prüfung läuft noch. Bitte kurz warten.',
    'Capacity': 'Zu viele Prüfungen. Bitte später erneut versuchen.',
    'NotFound': 'Diese Prüfung ist nicht mehr verfügbar.',
    'Restarted': 'Die lokale Prüfung wurde durch einen Neustart beendet.',
    'Failed': 'Die lokale Prüfung konnte nicht abgeschlossen werden.',
    'Cancelled': 'Die lokale Prüfung wurde gestoppt.',
    'TimedOut': 'Die lokale Prüfung hat das Zeitlimit erreicht.',
}


class ControllerError(ValueError):
    """Fixed frontend-safe failure; never wrap the original exception text."""
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(_MESSAGES[code])


@dataclass(frozen=True)
class ProviderIdentity:
    """Trusted local-provider identity; revision changes on provider replacement.

    Application wiring must bind infer to this identity, including its verified
    local endpoint/configuration; a model name alone is not a locality proof.
    """
    model: str
    local: bool
    revision: str


@dataclass
class _Scope:
    source_id: str
    fingerprint: str
    selection: dict = field(repr=False)
    provider: ProviderIdentity
    source_length: int


@dataclass
class _Review:
    binding: str
    question: str = field(repr=False)
    scope: _Scope
    instance: str
    expires: float
    epoch: int = 0
    run_id: str | None = None


@dataclass
class _Job:
    id: str
    review: _Review = field(repr=False)
    grant_id: str = field(repr=False)
    token: str = field(repr=False)
    deadline: float
    cancelled: threading.Event = field(default_factory=threading.Event, repr=False)
    status: str = 'running'
    finished: float | None = None
    text: str | None = field(default=None, repr=False)
    evidence: list = field(default_factory=list, repr=False)
    failure: str | None = None
    execution_done: bool = False
    inferences: int = 0


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=False).encode()).hexdigest()


class LocalModuleController:
    def __init__(self, broker, *, gateway, provider, infer, clock=time.monotonic,
                 max_jobs=16, max_reviews=16, retention=300):
        if (type(max_jobs) is not int or not 1 <= max_jobs <= 16
                or type(max_reviews) is not int or not 1 <= max_reviews <= 16
                or type(retention) not in (int, float) or not 0 < retention <= 300):
            raise ValueError('invalid module retention limits')
        self._broker, self._gateway = broker, gateway
        self._provider, self._infer, self._clock = provider, infer, clock
        self._max_jobs, self._max_reviews, self._retention = max_jobs, max_reviews, retention
        self._jobs, self._reviews, self._keys = OrderedDict(), OrderedDict(), {}
        self._lock = threading.RLock()
        self._active = None
        self._idle = threading.Event()
        self._idle.set()
        self._closed = False
        self._paused = 0
        self._pause_epoch = 0
        self._worker_app = None

    def _admission(self):
        """Caller holds the lock; maintenance and closure never admit work."""
        if self._closed:
            raise ControllerError(503, 'Restarted')
        if self._paused:
            raise ControllerError(409, 'Busy')

    @staticmethod
    def _request(source_id, question):
        if (not isinstance(source_id, str) or not 1 <= len(source_id) <= 80
                or not isinstance(question, str) or not 1 <= len(question.strip()) <= len(question) <= 1200):
            raise ControllerError(400, 'InvalidRequest')

    def _scope(self, source_id, question):
        """Read canonical snapshots only; never create a second source store."""
        try:
            identity = self._provider()
            if (not isinstance(identity, ProviderIdentity) or identity.model != MODEL
                    or identity.local is not True or not isinstance(identity.revision, str)
                    or not 1 <= len(identity.revision) <= 128):
                raise ControllerError(503, 'Unavailable')
            snapshot = self._broker.episodes.belegbarer_snapshot(source_id, max_bytes=256 * 1024)
            if (snapshot is None or not snapshot.current()
                    or snapshot.episode.state in AUSGEBLENDETE_ZUSTAENDE
                    or CHAT_LOOKUP_TAG in snapshot.episode.tags):
                raise ControllerError(409, 'ReviewChanged')
            selected = self._broker.procedures.select(question, area='analysis', local=True)
            if not self._broker.procedures.current(selected):
                raise ControllerError(409, 'ReviewChanged')
            # Selection/currentness and provider metadata may take time. Validate
            # the collected view after that work; never release a former source
            # or provider just because it was current before selection finished.
            if self._provider() != identity or not self._broker.procedures.current(selected):
                raise ControllerError(409, 'ReviewChanged')
            # A support snapshot's lineage can remain current when its original
            # is ignored. Re-read through the Broker's full original policy.
            fresh = self._broker._snapshot(source_id)
            if fresh.support_fingerprint() != snapshot.support_fingerprint():
                raise ControllerError(409, 'ReviewChanged')
            return _Scope(source_id, snapshot.support_fingerprint(), deepcopy(selected), identity,
                          len(snapshot.episode.body))
        except ControllerError:
            raise
        except Exception:
            raise ControllerError(503, 'Unavailable') from None

    def _runtime(self):
        try:
            value = self._gateway.health()
            if (not isinstance(value, dict) or value.get('status') != 'ok'
                    or value.get('mode') != MODE or value.get('model') != MODEL
                    or value.get('syntheticOnly') is not False
                    or not isinstance(value.get('instance'), str)
                    or not _INSTANCE.fullmatch(value['instance'])):
                raise ControllerError(503, 'Unavailable')
            return value['instance']
        except ControllerError:
            raise
        except Exception:
            raise ControllerError(503, 'Unavailable') from None

    def _review_current(self, review):
        try:
            # Network health can block. Take the canonical source/skill/provider
            # snapshot after it, so a withdrawal during health cannot pass poll.
            instance = self._runtime()
            current = self._scope(review.scope.source_id, review.question)
            return (current.fingerprint == review.scope.fingerprint
                    and current.provider == review.scope.provider
                    and current.selection['signature'] == review.scope.selection['signature']
                    and current.selection['conflicts'] == review.scope.selection['conflicts']
                    and instance == review.instance)
        except Exception:
            return False

    def _cleanup(self):
        now = self._clock()
        expired = [identifier for identifier, job in self._jobs.items()
                   if job is not self._active and job.finished is not None
                   and now - job.finished >= self._retention]
        for identifier in expired:
            self._forget(identifier)
        for binding, review in list(self._reviews.items()):
            if now >= review.expires:
                del self._reviews[binding]

    def _forget(self, identifier):
        job = self._jobs.pop(identifier)
        self._broker.cancel(job.grant_id)
        job.token, job.text, job.evidence = '', None, []
        self._keys = {key: value for key, value in self._keys.items() if value[1] != identifier}

    def _remember_key(self, key, parameters, run_id):
        if len(self._keys) >= self._max_jobs * 4 and key not in self._keys:
            raise ControllerError(429, 'Capacity')
        self._keys[key] = parameters, run_id

    def prepare(self, source_id, question):
        """Return an expiring opaque consent review, no inference or setup effect."""
        self._request(source_id, question)
        with self._lock:
            self._admission()
            epoch = self._pause_epoch
        scope, instance = self._scope(source_id, question), self._runtime()
        review = _Review(secrets.token_urlsafe(32), question, scope, instance,
                         self._clock() + 120, epoch=epoch)
        with self._lock:
            self._admission()
            if epoch != self._pause_epoch:
                raise ControllerError(409, 'ReviewChanged')
            self._cleanup()
            while len(self._reviews) >= self._max_reviews:
                self._reviews.popitem(last=False)
            self._reviews[review.binding] = review
        return dict(review_binding=review.binding, source=dict(id=source_id, fingerprint=scope.fingerprint),
                    model=MODEL, expires_in=120, limits=dict(LIMITS))

    def start(self, source_id, *, question, source_fingerprint, review_binding, consent, idempotency_key):
        """Explicit start. Client cannot choose extra sources, provider or tools."""
        self._request(source_id, question)
        if (consent is not True or not isinstance(idempotency_key, str)
                or not _IDEMPOTENCY.fullmatch(idempotency_key)):
            raise ControllerError(400, 'InvalidRequest')
        if (not isinstance(review_binding, str) or not _NONCE.fullmatch(review_binding)
                or not isinstance(source_fingerprint, str) or len(source_fingerprint) != 64):
            raise ControllerError(409, 'ReviewChanged')
        parameters = _hash([source_id, source_fingerprint, question, review_binding, True])
        with self._lock:
            self._admission()
            admission_epoch = self._pause_epoch
            self._cleanup()
            previous = self._keys.get(idempotency_key)
            if previous is not None and previous[0] != parameters:
                raise ControllerError(409, 'ReviewChanged')
            replay = self._jobs.get(previous[1]) if previous else next(
                (job for job in self._jobs.values() if job.review.binding == review_binding), None)
            review = replay.review if replay is not None else self._reviews.get(review_binding)
            if (review is None or review.scope.source_id != source_id or review.question != question
                    or review.scope.fingerprint != source_fingerprint):
                raise ControllerError(409, 'ReviewChanged')
            if replay is None and (self._clock() >= review.expires
                                   or review.epoch != self._pause_epoch):
                raise ControllerError(409, 'ReviewChanged')
        # Network health and canonical reads happen without holding the UI/cancel lock.
        if not self._review_current(review):
            if replay is not None:
                self._end(replay, 'stale', 'ReviewChanged')
            raise ControllerError(409, 'ReviewChanged')
        with self._lock:
            self._admission()
            if admission_epoch != self._pause_epoch:
                raise ControllerError(409, 'ReviewChanged')
            previous = self._keys.get(idempotency_key)
            if previous is not None and previous[0] != parameters:
                raise ControllerError(409, 'ReviewChanged')
            if replay is not None:
                self._remember_key(idempotency_key, parameters, replay.id)
                return self._public(replay)
            # A concurrent start may have won while this caller checked freshness.
            if review.run_id is not None:
                winner = self._jobs.get(review.run_id)
                if winner is None:
                    raise ControllerError(409, 'ReviewChanged')
                self._remember_key(idempotency_key, parameters, winner.id)
                return self._public(winner)
            if (self._clock() >= review.expires
                    or review.epoch != self._pause_epoch
                    or self._reviews.get(review_binding) is not review):
                raise ControllerError(409, 'ReviewChanged')
            if self._active is not None:
                raise ControllerError(409, 'Busy')
            while len(self._jobs) >= self._max_jobs:
                evict = next((job.id for job in self._jobs.values() if job is not self._active
                              and job.status != 'running'), None)
                if evict is None:
                    raise ControllerError(429, 'Capacity')
                self._forget(evict)
            try:
                grant = self._broker.issue(question, area='analysis', sources=[source_id], ttl=120)
            except Exception:
                raise ControllerError(409, 'ReviewChanged') from None
            job = _Job(secrets.token_hex(16), review, grant['id'], grant['token'], self._clock() + 120)
            review.run_id = job.id
            self._jobs[job.id], self._active = job, job
            self._idle.clear()
            self._keys[idempotency_key] = parameters, job.id
            response = self._public(job)
            started = False
            try:
                threading.Thread(target=self._execute, args=(job,), daemon=True,
                                 name='kf-local-module').start()
                started = True
                threading.Thread(target=self._watch, args=(job,), daemon=True,
                                 name='kf-local-module-watch').start()
            except Exception:
                self._end(job, 'failed', 'Failed')
                if not started:
                    job.execution_done = True
                    self._release_if_idle(job)
                # If execution did start it retains the slot until it exits.
                raise ControllerError(503, 'Failed') from None
            return response

    def _end(self, job, status, failure):
        with self._lock:
            if job.status not in {'running', 'completed'}:
                return
            job.cancelled.set()
            self._broker.cancel(job.grant_id)
            job.token, job.text, job.evidence = '', None, []
            job.status, job.failure, job.finished = status, failure, self._clock()

    def _refresh(self, job):
        with self._lock:
            status = job.status
            expired = status == 'running' and self._clock() >= job.deadline
        if expired:
            self._end(job, 'timed_out', 'TimedOut')
        elif status in {'running', 'completed'} and not self._review_current(job.review):
            self._end(job, 'stale', 'ReviewChanged')

    def _watch(self, job):
        while not job.cancelled.wait(1.0):
            self._refresh(job)

    def _execute(self, job):
        try:
            self._refresh(job)
            with self._lock:
                if job.status != 'running':
                    return
                token = job.token
            value = self._gateway.run(token, job.review.question, job.cancelled, job.deadline)
            self._refresh(job)
            if (not isinstance(value, dict) or value.get('status') != 'complete'
                    or value.get('mode') != MODE or value.get('model') != MODEL
                    or value.get('syntheticOnly') is not False or value.get('instance') != job.review.instance
                    or not isinstance(value.get('text'), str) or not value['text'].strip()
                    or len(value['text']) > 32000 or token in value['text']):
                raise ControllerError(503, 'Failed')
            with self._lock:
                if job.status == 'running' and self._broker.current(token):
                    if not job.evidence:
                        raise ControllerError(503, 'Failed')
                    job.text, job.status, job.finished = value['text'], 'completed', self._clock()
                    # No worker capabilities survive successful execution. Polls
                    # independently revalidate the immutable review snapshot.
                    self._broker.cancel(job.grant_id)
                    job.token = ''
                    job.cancelled.set()
        except Exception:
            self._end(job, 'failed', 'Failed')
        finally:
            with self._lock:
                if job.status == 'running':
                    self._end(job, 'stale', 'ReviewChanged')
                job.execution_done = True
                self._release_if_idle(job)

    def _release_if_idle(self, job):
        if self._active is job and job.execution_done and job.inferences == 0:
            self._active = None
            self._idle.set()

    @staticmethod
    def _public(job):
        result = dict(id=job.id, status=job.status, model=MODEL,
                      execution_pending=not job.execution_done or job.inferences > 0,
                      source=dict(id=job.review.scope.source_id, fingerprint=job.review.scope.fingerprint))
        if job.status == 'completed':
            opened, end = 0, 0
            for receipt in sorted(job.evidence, key=lambda item: (item['start'], item['end'])):
                opened += max(0, receipt['end'] - max(end, receipt['start']))
                end = max(end, receipt['end'])
            result.update(label='DRAFT', verified=False, text=job.text, evidence=deepcopy(job.evidence),
                coverage=dict(source_characters=job.review.scope.source_length, opened_characters=opened,
                              complete_text_opened=opened == job.review.scope.source_length))
        elif job.failure is not None:
            result.update(error=job.failure, message=_MESSAGES[job.failure])
        return result

    def poll(self, run_id):
        with self._lock:
            self._cleanup()
            job = self._jobs.get(run_id) if isinstance(run_id, str) else None
            if job is None:
                raise ControllerError(404, 'NotFound')
        self._refresh(job)
        with self._lock:
            return self._public(job)

    def cancel(self, run_id):
        with self._lock:
            self._cleanup()
            job = self._jobs.get(run_id) if isinstance(run_id, str) else None
            if job is None:
                raise ControllerError(404, 'NotFound')
            self._end(job, 'cancelled', 'Cancelled')
            return self._public(job)

    def runtime_status(self):
        """Compute occupancy; this is not a runtime setup/readiness attestation."""
        with self._lock:
            busy = self._active is not None
            status = ('stopping' if busy else 'stopped') if self._closed else (
                'running' if busy and self._active.status == 'running' else 'cancelling' if busy else 'idle')
            return dict(status=status, busy=busy, model=MODEL)

    def close(self, *, wait_seconds=0):
        """Revoke first, optionally wait at most 2s; never promise physical kill.

        Lifecycle must require a returned `stopped` before treating the old
        execution as quiescent. A blocked trusted provider can leave `stopping`.
        """
        if type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 2:
            raise ValueError('invalid shutdown wait')
        with self._lock:
            self._closed = True
            self._reviews.clear()
            self._keys.clear()
            for job in self._jobs.values():
                self._end(job, 'restarted', 'Restarted')
        self._idle.wait(wait_seconds)
        return self.runtime_status()

    @contextmanager
    def quiescent(self, *, wait_seconds=2):
        """Pause admission and yield only after physical execution has exited.

        A cancelled request can retain a trusted provider callback. Maintenance
        must fail closed until that callback and the gateway execution end.
        Epochs also invalidate reviews collected across a completed pause.
        """
        if type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 2:
            raise ValueError('invalid maintenance wait')
        with self._lock:
            self._paused += 1
            self._pause_epoch += 1
            self._reviews.clear()
            for job in self._jobs.values():
                if job.status == 'running':
                    self._end(job, 'cancelled', 'Cancelled')
        try:
            if not self._idle.wait(wait_seconds):
                raise ControllerError(409, 'Busy')
            yield
        finally:
            with self._lock:
                self._paused -= 1

    def _owned_job(self, token):
        with self._lock:
            job = self._active
            if (job is None or job.status != 'running' or not isinstance(token, str)
                    or not secrets.compare_digest(token, job.token)):
                raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
        self._refresh(job)
        with self._lock:
            if job.status != 'running' or not self._broker.current(token):
                raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
        return job

    def worker_app(self):
        """Unbound fixed-protocol app; later lifecycle owns its 8892 listener.

        Never mount this on the main application's routes or accept master/UI
        tokens here. The proxy adds controller freshness, not new authorization.
        """
        with self._lock:
            if self._worker_app is None:
                app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
                register(app, _ProtocolBroker(self), model=MODEL, infer=self._guarded_infer)
                self._worker_app = app
            return self._worker_app

    def _guarded_infer(self, messages, tools, permitted):
        with self._lock:
            job = self._active
        if job is None or not permitted():
            raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
        with self._lock:
            if job.status != 'running' or self._closed:
                raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
            job.inferences += 1
        try:
            result = self._infer(job.review.scope.provider, messages, tools, permitted)
            if not permitted() or getattr(result, 'model', None) != MODEL:
                raise BridgeError('Das freigegebene lokale Modell ist nicht mehr verfügbar.')
            return result
        finally:
            with self._lock:
                job.inferences -= 1
                self._release_if_idle(job)


class _ProtocolBroker:
    """Delegate all auth/quotas to Broker and record only actual read receipts."""
    def __init__(self, controller):
        self._controller = controller
        self._broker = controller._broker

    def authorize_request(self, token):
        self._broker.authorize_request(token)
        self._controller._owned_job(token)

    def current(self, token):
        try:
            self._controller._owned_job(token)
            return True
        except BridgeError:
            return False

    def instructions(self, token):
        self._controller._owned_job(token)
        return self._broker.instructions(token)

    def model(self, token, infer):
        self._controller._owned_job(token)
        result = self._broker.model(token, infer)
        self._controller._owned_job(token)
        return result

    def invoke(self, token, name, arguments):
        job = self._controller._owned_job(token)
        result = self._broker.invoke(token, name, arguments)
        self._controller._owned_job(token)
        receipts = result.get('items', []) if name == 'memory_search' else [result] if name in {'source_excerpt', 'selected_original'} else []
        with self._controller._lock:
            if (self._controller._active is not job or job.status != 'running'
                    or job.cancelled.is_set()):
                raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
            for receipt in receipts:
                if (isinstance(receipt, dict) and receipt.get('id') == job.review.scope.source_id
                        and receipt.get('fingerprint') == job.review.scope.fingerprint
                        and isinstance(receipt.get('quote'), str) and receipt['quote']
                        and type(receipt.get('start')) is int and type(receipt.get('end')) is int
                        and 0 <= receipt['start'] < receipt['end'] <= job.review.scope.source_length
                        and len(receipt['quote']) == receipt['end'] - receipt['start']
                        and len(job.evidence) < 8 and receipt not in job.evidence):
                    job.evidence.append(deepcopy(receipt))
        return result
