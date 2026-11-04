"""Authenticated routes for explicit Cloud Gedächtnis jobs."""
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError
from starlette.concurrency import run_in_threadpool

from .cloud_memory import CloudMemoryError, CloudMemoryJobs
from .providers import ProviderError
from .cloud_import_provider import AnthropicImportProvider, credential_status
import os
import threading
from .cloud_credentials import PREPARED_CLOUD_KEYS, MISTRAL_IMPORT_MODEL
from .cloud_import_budget import MistralSourceBudget, MistralBudgetError
from .mail_filter import classify_episode, policy


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="chatgpt", pattern=r"^(chatgpt|anthropic|mistral)$")
    purpose: str = Field(default="pilot", pattern=r"^(pilot|bulk|recheck)$")
    source_ids: list[str] | None = Field(default=None, max_length=1000)
    limit: int | None = Field(default=None, ge=1, le=1000)
    cursor: int | None = Field(default=None, ge=1)


class StartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="chatgpt", pattern=r"^(chatgpt|anthropic|mistral)$")
    preview_id: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:/-]+$")
    consent: bool
    source_ids: list[str] | None = Field(default=None, max_length=1000)


class BudgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["mistral"]
    cap_microusd: StrictInt = Field(ge=0, le=1_000_000_000)
    expected_revision: StrictInt = Field(ge=0)
    consent: StrictBool


class JobActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str | None = Field(default=None, max_length=64)


def register(app, guard, data_dir, provider_factory):
    manager_lock = threading.Lock()
    budget_lock = threading.Lock()

    def source_budget():
        with budget_lock:
            value = getattr(app.state, "mistral_source_budget", None)
            if value is None:
                value = MistralSourceBudget(Path(data_dir()) / "mistral-source-budget.sqlite3")
                app.state.mistral_source_budget = value
            return value

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
        if identifier not in {"anthropic", "mistral"}:
            return {}
        return credential_status(getattr(app.state, "keychain", None), app.state.settings, provider=identifier)

    def build_api_provider(identifier, model, **kwargs):
        credential = api_credential(identifier)
        if identifier not in {"anthropic", "mistral"} or not credential.get("available") or credential.get("model") != model:
            raise CloudMemoryError("Der API-Zugang oder das Modell ist nicht vorbereitet. Bitte erneut prüfen.")
        if identifier == "mistral":
            from .mistral_import_provider import MistralImportProvider
            if model != MISTRAL_IMPORT_MODEL:
                raise CloudMemoryError("Das Mistral-Quellenmodell ist nicht freigegeben.")
            key = os.environ.get(PREPARED_CLOUD_KEYS[identifier])
            if not key:
                raise CloudMemoryError("Der Mistral-Zugang wurde geändert. Bitte erneut prüfen.")
            return MistralImportProvider(model, key,
                credential["credential_revision"], lambda: api_credential(identifier).get("credential_revision"),
                budget=source_budget(), **kwargs)
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
                                        source_screen=lambda episode: classify_episode(episode, policy(app.state.settings)),
                                        mistral_budget=source_budget)
                app.state.cloud_memory_jobs = value
            return value

    # Shared cumulative allowance and credential factory, not a new grant.
    # Consumers must provide their own exact reviewed-data capability.
    app.state.mistral_source_budget_factory = source_budget
    app.state.mistral_source_provider_factory = build_api_provider
    app.state.mistral_source_credential = lambda: api_credential('mistral')

    def invoke(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MistralBudgetError as exc:
            raise HTTPException(409, CloudMemoryJobs._stop_reason(exc)) from None
        except CloudMemoryError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/v1/memory/cloud/budget", dependencies=guard)
    def get_budget(provider: Literal["mistral"]):
        return invoke(lambda: source_budget().status())

    @app.put("/api/v1/memory/cloud/budget", dependencies=guard)
    async def put_budget(request: Request):
        raw = await request.body()
        if len(raw) > 4096:
            raise HTTPException(422, "Die Budgeteingabe ist zu groß.")
        try:
            body = BudgetIn.model_validate_json(raw)
        except ValidationError:
            # Never reflect arbitrary extra fields through validation input data.
            raise HTTPException(422, "Bitte Anbieter, Gesamtbudget, Fassung und Zustimmung prüfen.") from None
        if body.consent is not True:
            raise HTTPException(422, "Eine Budgetänderung benötigt ausdrückliche Zustimmung.")
        return await run_in_threadpool(invoke, lambda: source_budget().set_total_cap(body.cap_microusd, body.expected_revision))

    @app.post("/api/v1/memory/cloud/preview", dependencies=guard)
    def preview(body: PreviewIn):
        return invoke(lambda: manager().preview(body.purpose, body.source_ids, body.limit, body.cursor, provider=body.provider))

    @app.post("/api/v1/memory/cloud/start", dependencies=guard)
    def start(body: StartIn):
        return invoke(lambda: manager().start(body.preview_id, body.model, body.consent, body.source_ids, provider=body.provider))

    @app.get("/api/v1/memory/cloud/status", dependencies=guard)
    def status():
        return invoke(lambda: manager().status())

    @app.post("/api/v1/memory/cloud/pause", dependencies=guard)
    def pause(body: JobActionIn):
        return invoke(lambda: manager().pause(body.job_id))

    @app.post("/api/v1/memory/cloud/resume", dependencies=guard)
    def resume(body: JobActionIn):
        return invoke(lambda: manager().resume(body.job_id))

    @app.post("/api/v1/memory/cloud/revoke", dependencies=guard)
    def revoke(body: JobActionIn):
        return invoke(lambda: manager().pause(body.job_id, revoke=True))
