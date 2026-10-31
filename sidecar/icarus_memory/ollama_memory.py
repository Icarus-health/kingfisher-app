"""Bound the resident lifetime of Kingfisher-owned local Ollama models.

Warum andere Modelle entladen werden (RAM): Kingfisher kann für Frage, Antwort, Prüfung und Hintergrund
verschiedene eigene Modelle (`kingfisher-*`) benutzen. Zwei davon zugleich im Speicher sprengen auf einem Rechner
mit 8 bis 16 GB den Arbeitsspeicher; deshalb entlädt jeder Aufruf vorher die anderen eigenen Modelle (`_prepare`).
Das bleibt so.

Wie lange das gerufene Modell danach bleibt (Paket T, 26.10.2026): Im Hintergrund 15 Sekunden wie bisher, damit ein
Modell, das nur nachts einordnet, keinen Speicher hält. Das **Antwortmodell eines Gesprächs** bleibt nach der Antwort
fünf Minuten (`HALTEN_GESPRAECH`): Die nächste Frage kommt meist innerhalb dieser Zeit, und ein kaltes Laden kostet
auf dem Zielgerät mehrere Sekunden. Es hält damit nicht mehr Speicher als Ollamas eigene Vorgabe für alle anderen
Modelle (5 Minuten), und der nächste Aufruf eines anderen eigenen Modells entlädt es weiterhin zuerst. Dazu wärmt
`vorwaermen` das Antwortmodell beim Öffnen eines Gesprächs vor: nicht blockierend, nur bei einem lokalen Modell,
nie, solange ein anderer Modellaufruf läuft.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

import httpx

_LOG = logging.getLogger(__name__)
_MANAGED_PREFIX = "kingfisher-"
_TIMEOUT_SECONDS = 3.0
_MAX_RESPONSE_BYTES = 1024 * 1024
_MANAGED_MODEL_LOCK = threading.RLock()
HALTEN_HINTERGRUND = "15s"
HALTEN_GESPRAECH = "5m"
#: Das Antwortmodell des laufenden Gesprächs (Ollama-Name), gesetzt von `im_gespraech`; sonst None.
_GESPRAECH_MODELL: ContextVar[str | None] = ContextVar("kingfisher_gespraech_modell", default=None)


def _ollama_client(*, timeout: float = _TIMEOUT_SECONDS, trust_env: bool = False,
                   follow_redirects: bool = False) -> httpx.Client:
    """Use only the configured local endpoint, without proxy or redirect routing."""
    return httpx.Client(timeout=timeout, trust_env=trust_env, follow_redirects=follow_redirects)


def _scope(provider: Any) -> tuple[str, str] | None:
    # Import lazily: providers owns ProviderError and imports this helper at runtime.
    from .providers import OpenAICompatible, is_local_endpoint

    if type(provider) is not OpenAICompatible:
        return None
    model = getattr(provider, "model", None)
    if (not isinstance(model, str) or not model.startswith(_MANAGED_PREFIX)
            or model != model.strip() or len(model) > 256):
        return None
    base_url = getattr(provider, "base_url", None)
    if not isinstance(base_url, str):
        return None
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme not in {"http", "https"} or port != 11434
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in {"", "/", "/v1", "/v1/"}):
        return None
    trusted_hosts = getattr(provider, "_trusted_local_hosts", ())
    if not is_local_endpoint(base_url, trusted_hosts):
        return None
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    # Ollama reports an omitted tag as `:latest` in /api/ps.
    return origin, _ollama_name(model)


def _request(client: httpx.Client, method: str, url: str, body: dict | None = None) -> bytes:
    kwargs = {"json": body} if body is not None else {}
    with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > _MAX_RESPONSE_BYTES:
                raise ValueError("Ollama response exceeded its size limit")
            content.extend(chunk)
    return bytes(content)


def _loaded_models(client: httpx.Client, origin: str) -> list[str]:
    raw = _request(client, "GET", origin + "/api/ps")
    value = json.loads(raw)
    models = value.get("models") if isinstance(value, dict) else None
    if not isinstance(models, list):
        raise ValueError("Ollama did not return a loaded-model list")
    names = []
    for item in models:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name:
            raise ValueError("Ollama returned an invalid loaded-model name")
        names.append(name)
    return names


def _prepare(origin: str, target: str, ready=None) -> None:
    with _ollama_client(timeout=_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False) as client:
        loaded = _loaded_models(client, origin)
        for name in dict.fromkeys(loaded):
            if name != target and name.startswith(_MANAGED_PREFIX):
                if ready is not None:ready()
                _request(client, "POST", origin + "/api/generate",
                         {"model": name, "keep_alive": 0})


def _ollama_name(model: str) -> str:
    return model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"


def halten_fuer(target: str) -> str:
    """Wie lange `target` nach einem Aufruf bleibt: das Antwortmodell im Gespräch fünf Minuten, sonst 15 Sekunden."""
    gespraech = _GESPRAECH_MODELL.get()
    return HALTEN_GESPRAECH if gespraech is not None and _ollama_name(gespraech) == target else HALTEN_HINTERGRUND


@contextmanager
def im_gespraech(provider: Any) -> Iterator[None]:
    """Für die Dauer einer Gesprächsantwort: Das Modell von `provider` (Rolle `antwort`) ist das Antwortmodell."""
    model = getattr(provider, "model", None) if getattr(provider, "is_local", False) else None
    marke = _GESPRAECH_MODELL.set(model if isinstance(model, str) and model.strip() else None)
    try:
        yield
    finally:
        _GESPRAECH_MODELL.reset(marke)


def _shorten_target_retention(origin: str, target: str, ready=None) -> None:
    with _ollama_client(timeout=_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False) as client:
        if target not in _loaded_models(client, origin):
            return
        if ready is not None:ready()
        _request(client, "POST", origin + "/api/generate",
                 {"model": target, "keep_alive": halten_fuer(target)})


@contextmanager
def managed_model(provider: Any) -> Iterator[None]:
    """Prepare and briefly retain one Kingfisher-owned model around a local call.

    Providers outside the explicit local Ollama/model scope pass through without
    locking or making HTTP requests. A scoped call fails closed if competing
    Kingfisher models cannot be unloaded before its body runs.
    """
    scope = _scope(provider)
    if scope is None:
        yield
        return

    from .providers import ProviderError
    from .local_context_profile import selected,verify_lifecycle,check_deadline

    origin, target = scope
    with _MANAGED_MODEL_LOCK:
        try:
            verify_lifecycle(provider)
            if selected(provider):_prepare(origin,target,lambda:check_deadline(provider))
            else:_prepare(origin, target)
        except Exception as exc:  # Fail closed before allowing the model call.
            raise ProviderError("Kingfisher could not prepare Ollama model memory.") from exc
        try:
            yield
        finally:
            try:
                verify_lifecycle(provider)
                if selected(provider):_shorten_target_retention(origin,target,lambda:check_deadline(provider))
                else:_shorten_target_retention(origin, target)
            except Exception:  # Do not replace a valid reply or the original call error.
                _LOG.warning("Kingfisher could not shorten its Ollama model retention.")


_VORGEWAERMT: dict[tuple[str, str], float] = {}
_VORWAERMEN_ABSTAND_S = 60.0


def _lokaler_ollama(provider: Any) -> tuple[str, str] | None:
    """(Ursprung, Ollama-Name) für ein lokales Modell auf dem lokalen Ollama (Port 11434), auch ohne `kingfisher-`."""
    from .providers import OpenAICompatible, is_local_endpoint

    if not isinstance(provider, OpenAICompatible) or not getattr(provider, "is_local", False):
        return None
    if getattr(provider, "ueber_ollama_cloud", False):
        return None
    model = getattr(provider, "model", None)
    if not isinstance(model, str) or not model.strip() or model != model.strip() or len(model) > 256:
        return None
    try:
        parsed = urlsplit(provider.base_url)
        port = parsed.port
    except (ValueError, AttributeError):
        return None
    if (parsed.scheme not in {"http", "https"} or port != 11434 or parsed.username or parsed.password
            or not is_local_endpoint(provider.base_url, getattr(provider, "_trusted_local_hosts", ()))):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")), _ollama_name(model)


def vorwaermen(provider: Any, *, beschaeftigt: Any = None, uhr: Any = time.monotonic) -> str:
    """Lädt das Antwortmodell vorab in den Speicher, ohne etwas zu fragen (Ollama: `/api/generate` ohne Prompt).

    Gibt zurück, was geschah: `geladen`, `kein_lokales_modell` (kein Aufruf), `kuerzlich` (in der letzten Minute schon),
    `beschaeftigt` (ein anderer Modellaufruf läuft; dann nicht dazwischen) oder `fehler`. Blockiert nie auf eine Sperre.
    Für ein eigenes Modell (`kingfisher-*`) gilt dieselbe RAM-Regel wie bei jedem Aufruf: erst die anderen entladen.
    """
    ziel = _lokaler_ollama(provider)
    if ziel is None:
        return "kein_lokales_modell"
    origin, name = ziel
    jetzt = uhr()
    if jetzt - _VORGEWAERMT.get(ziel, float("-inf")) < _VORWAERMEN_ABSTAND_S:
        return "kuerzlich"
    try:
        if callable(beschaeftigt) and beschaeftigt():
            return "beschaeftigt"
    except Exception:  # noqa: BLE001 - im Zweifel nicht dazwischen
        return "beschaeftigt"
    if not _MANAGED_MODEL_LOCK.acquire(blocking=False):
        return "beschaeftigt"
    try:
        _VORGEWAERMT[ziel] = jetzt
        from .local_context_profile import selected,verify_lifecycle,check_deadline
        verify_lifecycle(provider)
        if _scope(provider) is not None:
            if selected(provider):_prepare(origin,name,lambda:check_deadline(provider))
            else:_prepare(origin, name)
        verify_lifecycle(provider)
        with _ollama_client(timeout=120.0, trust_env=False, follow_redirects=False) as client:
            _request(client, "POST", origin + "/api/generate", {"model": name, "keep_alive": HALTEN_GESPRAECH})
        return "geladen"
    except Exception:  # noqa: BLE001 - Vorwärmen ist eine Hilfe, kein Muss; die Antwort lädt sonst selbst
        _LOG.warning("Kingfisher could not warm its answer model.")
        return "fehler"
    finally:
        _MANAGED_MODEL_LOCK.release()
