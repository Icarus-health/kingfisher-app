"""Fixed, positively verified local model for explicitly scoped module work.

Application wiring supplies the stable background-role provider and shared
conversation lock. Metadata never warms/loads a model. All execution leases
are nonblocking and remain owned until the entered transport actually exits.
"""
from contextlib import contextmanager
from copy import copy, deepcopy
import hashlib
import hmac
import json
import secrets
import threading
import time

from . import local_context_profile as profile
from .harness_broker import BridgeError
from .local_model_guard import VerifiedLocalProvider
from .local_module_controller import MODEL, ProviderIdentity
from .providers import OpenAICompatible, json_request_deadline, _json_transport_timeout


_UNAVAILABLE = 'Das bestätigte lokale Modell ist nicht mehr verfügbar.'
_BUSY = 'Das lokale Modell arbeitet bereits. Bitte kurz warten.'
_SECONDS = 60.0
_METADATA_SECONDS = 10.0


class _Busy(Exception):
    pass


class VerifiedModuleModel:
    def __init__(self, provider_getter, shared_lock, boundary=None):
        self._get_provider, self._shared_lock, self._boundary = provider_getter, shared_lock, boundary
        self._inference_lock = threading.Lock()
        self._identity_lock = threading.Lock()
        self._salt = secrets.token_bytes(32)
        self._last_provider = None
        self._last_binding = None
        self._epoch = 0

    @staticmethod
    def _configuration(provider):
        if (type(provider) is not OpenAICompatible or provider.model != MODEL
                or provider.is_local is not True or not profile.selected(provider)
                or getattr(provider, 'ueber_ollama_cloud', False)):
            raise ValueError('unverified local provider')
        # Copy configuration as opaque hash input, including existing credential
        # configuration; no env/key file is loaded or exposed. A mutable profile
        # verification cache is not configuration and must stay job-local.
        values = {key: value for key, value in vars(provider).items() if key != '_small_context_identity'}
        if any(callable(value) for value in values.values()):
            raise ValueError('overridden instance transport')
        return json.dumps(values, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

    def _live(self, provider, configuration):
        try:
            return self._get_provider() is provider and self._configuration(provider) == configuration
        except Exception:
            return False

    def _revision(self, provider, configuration, weights):
        binding = hashlib.sha256(configuration).digest(), weights.name, weights.digest
        with self._identity_lock:
            if self._last_provider is not provider or self._last_binding != binding:
                self._epoch += 1
                self._last_provider, self._last_binding = provider, binding
            value = json.dumps([self._epoch, id(provider), binding[0].hex(), weights.name,
                                weights.digest, profile.CONTEXT], separators=(',', ':')).encode()
            revision = hmac.new(self._salt, value, hashlib.sha256).hexdigest()
        return ProviderIdentity(model=MODEL, local=True, revision=revision)

    @contextmanager
    def _boundary_lease(self):
        if self._boundary is None:
            yield
            return
        self._boundary.check()
        if not self._boundary.try_enter():
            raise _Busy()
        try:
            self._boundary.check()
            yield
            self._boundary.check()
        finally:
            self._boundary.leave()

    def _read(self, deadline):
        provider = self._get_provider()
        configuration = self._configuration(provider)
        local = copy(provider)
        # Never pin/update an ordinary provider's verification cache. A fresh
        # review may bind newly installed weights on the same provider object.
        local.__dict__.pop('_small_context_identity', None)
        local._verified_local_transport = True
        local._verified_local_permitted = lambda: (
            time.monotonic() < deadline and self._live(provider, configuration))
        with json_request_deadline(deadline):
            weights = profile.verify_lifecycle(local)
        if weights is None or not local._verified_local_permitted():
            raise ValueError('changed local identity')
        return provider, configuration, local, self._revision(provider, configuration, weights)

    def identity(self):
        """Positive metadata only: no AMPEL/model preparation/warmup/generation."""
        try:
            with self._boundary_lease():
                return self._read(time.monotonic() + _METADATA_SECONDS)[3]
        except Exception:
            raise BridgeError(_UNAVAILABLE) from None

    def infer(self, expectedIdentity, messages, tools, permitted):
        """Infer once, with no queue/fallback and a fresh immutable local binding.

        Request deadlines and permission checks prevent late loading/submission
        and late result release. They do not promise an OS kill of a stuck call;
        all leases stay held until its actual callback/transport exits.
        """
        if not self._inference_lock.acquire(blocking=False):
            raise BridgeError(_BUSY)
        shared = False
        try:
            if (not isinstance(expectedIdentity, ProviderIdentity) or expectedIdentity.model != MODEL
                    or expectedIdentity.local is not True or not permitted()):
                raise ValueError('unavailable local request')
            if not self._shared_lock.acquire(blocking=False):
                raise _Busy()
            shared = True
            from .hintergrund import AMPEL
            from .ollama_memory import try_managed_model
            with self._boundary_lease(), AMPEL.try_vordergrund() as capacity:
                if not capacity:
                    raise _Busy()
                with try_managed_model() as memory:
                    if not memory:
                        raise _Busy()
                    deadline = time.monotonic() + _SECONDS
                    with json_request_deadline(deadline):
                        provider, configuration, local, current = self._read(deadline)
                        if current != expectedIdentity:
                            raise ValueError('changed reviewed provider')
                        def allowed():
                            try:
                                _json_transport_timeout(_SECONDS)
                                if self._boundary is not None:
                                    self._boundary.check()
                                return (time.monotonic() < deadline and permitted()
                                        and self._live(provider, configuration))
                            except Exception:
                                return False
                        if not allowed():
                            raise ValueError('revoked local request')
                        local._verified_local_permitted = allowed
                        # This factual source job has the protocol's fixed
                        # 256-token ceiling and deterministic sampling. Never
                        # inherit ordinary conversation generation defaults.
                        local._request_payload = lambda payload: dict(payload, max_tokens=256, temperature=0)
                        # Existing complete() uses its ordinary 60s native path.
                        # Clamp only this job-local copy to the inherited shared
                        # deadline, including time spent in metadata/preparation.
                        local._client = lambda timeout: OpenAICompatible._client(
                            local, _json_transport_timeout(min(_SECONDS, timeout)))
                        checked = VerifiedLocalProvider(local, permitted=allowed)
                        reply = checked.complete(deepcopy(messages), deepcopy(tools))
                        if not allowed() or reply.model != MODEL:
                            raise ValueError('revoked local result')
                        if self._read(deadline)[3] != expectedIdentity or not allowed():
                            raise ValueError('changed local result binding')
                        return reply
        except _Busy:
            raise BridgeError(_BUSY) from None
        except Exception:
            raise BridgeError(_UNAVAILABLE) from None
        finally:
            if shared:
                self._shared_lock.release()
            self._inference_lock.release()
