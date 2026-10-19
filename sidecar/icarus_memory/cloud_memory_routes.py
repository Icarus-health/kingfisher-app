"""Authenticated routes for explicit Cloud Gedächtnis jobs."""
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .cloud_memory import CloudMemoryError, CloudMemoryJobs
from .providers import ProviderError
from .cloud_import_provider import AnthropicImportProvider, credential_status
import os
import threading
from .cloud_credentials import PREPARED_CLOUD_KEYS
from .mail_filter import classify_episode, policy


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="chatgpt", pattern=r"^(chatgpt|anthropic)$")
    purpose: str = Field(default="pilot", pattern=r"^(pilot|bulk|recheck)$")
    source_ids: list[str] | None = Field(default=None, max_length=1000)
    limit: int | None = Field(default=None, ge=1, le=1000)
    cursor: int | None = Field(default=None, ge=1)


class StartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="chatgpt", pattern=r"^(chatgpt|anthropic)$")
    preview_id: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:/-]+$")
    consent: bool
    source_ids: list[str] | None = Field(default=None, max_length=1000)


class JobActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str | None = Field(default=None, max_length=64)


def register(app, guard, data_dir, provider_factory):
    manager_lock = threading.Lock()

    def grant_status():
        oauth = getattr(app.state, "chatgpt_oauth", None)
        return oauth.status() if oauth is not None else {}

    def build_provider(model):
        oauth = getattr(app.state, "chatgpt_oauth", None)
        factory = provider_factory or (getattr(oauth, "provider", None) if oauth else None)
        if not callable(factory):
            raise CloudMemoryError("Der ChatGPT-Zugang ist nicht verfügbar.")
        try:
            return factory(model)
        except ProviderError as exc:
            raise CloudMemoryError(str(exc)) from None

    def api_credential(identifier):
        if identifier != "anthropic":
            return {}
        return credential_status(getattr(app.state, "keychain", None), app.state.settings)

    def build_api_provider(identifier, model):
        credential = api_credential(identifier)
        if identifier != "anthropic" or not credential.get("available") or credential.get("model") != model:
            raise CloudMemoryError("Der API-Zugang oder das Modell ist nicht vorbereitet. Bitte erneut prüfen.")
        return AnthropicImportProvider(model, os.environ[PREPARED_CLOUD_KEYS["anthropic"]], credential["credential_revision"],
                                       lambda: api_credential(identifier).get("credential_revision"))

    def manager():
        with manager_lock:
            value = getattr(app.state, "cloud_memory_jobs", None)
            if value is None:
                episodes = getattr(app.state, "episodes", None)
                if episodes is None:
                    raise CloudMemoryError("Der Gedächtnisspeicher ist nicht verfügbar.")
                value = CloudMemoryJobs(episodes, Path(data_dir()) / "cloud-memory-jobs.sqlite3",
                                        build_provider, grant_status,
                                        getattr(app.state, "conversation_lock", None),
                                        getattr(app.state, "runtime_boundary", None),
                                        api_provider_factory=build_api_provider, credential_status=api_credential,
                                        source_screen=lambda episode: classify_episode(episode, policy(app.state.settings)))
                app.state.cloud_memory_jobs = value
            return value

    def invoke(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except CloudMemoryError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/v1/memory/cloud/preview", dependencies=guard)
    def preview(body: PreviewIn):
        return invoke(manager().preview, body.purpose, body.source_ids, body.limit, body.cursor, provider=body.provider)

    @app.post("/api/v1/memory/cloud/start", dependencies=guard)
    def start(body: StartIn):
        return invoke(manager().start, body.preview_id, body.model, body.consent, body.source_ids, provider=body.provider)

    @app.get("/api/v1/memory/cloud/status", dependencies=guard)
    def status():
        return manager().status()

    @app.post("/api/v1/memory/cloud/pause", dependencies=guard)
    def pause(body: JobActionIn):
        return manager().pause(body.job_id)

    @app.post("/api/v1/memory/cloud/resume", dependencies=guard)
    def resume(body: JobActionIn):
        return invoke(manager().resume, body.job_id)

    @app.post("/api/v1/memory/cloud/revoke", dependencies=guard)
    def revoke(body: JobActionIn):
        return manager().pause(body.job_id, revoke=True)
