"""Lokale HTTP-Schnittstelle für die Desktop-App.

Bindet ausschließlich an 127.0.0.1. Der Sidecar ist ein Implementierungsdetail
der App, kein Netzwerkdienst — es gibt bewusst keine Option, ihn zu öffnen.

Zusätzlich verlangt jede Anfrage ein Token, das die App beim Start erzeugt und
per Umgebungsvariable übergibt. Ohne das könnte jeder lokale Prozess das
Selbstmodell auslesen; auf einem Einzelplatzrechner ist das der relevante
Angriffsweg.
"""

from __future__ import annotations

import json
import base64
import binascii
import hashlib
import logging
import os
import re
import secrets
import shlex
import sys
import threading
import uuid
from urllib.parse import urlsplit
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Annotated, Any, Literal

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, field_validator

from .source_versions import invalidate_with_corrections
from .agent import Agent, Turn
from .source_versions import track_document, exclude_missing_documents
from .mail_task_suggestions import suggest as suggest_mail_tasks, source_digest as mail_source_digest, task_identity as mail_task_identity
from .audit import AuditLog
from .backends import CogneeBackend, SqliteBackend, ImmutableContentError
from .backup import (
    BackupError,
    export_model,
    import_model,
    list_snapshots,
    restore,
    restore_all,
    snapshot,
    snapshot_all,
)
from .update_backup import backup_before_update
from . import (
    briefing, config, entscheidungen, goals, graph, identitaet, logbuch, mail_ingestion, mcp_client, personen,
    providers, suche, urteil, working_memory_semantic_runtime,
)
from .agent_verdrahtung import (
    _projekt_mappe, _project_directory, _search_calendar, baue_hintergrund, verdrahte_speicher,
    verdrahte_zusaetze,
)
from .consolidation import Consolidator
from dataclasses import asdict, replace
from .task_candidates import TaskCandidates
from .task_detection import TaskDetector, candidate_batches, for_briefing as task_candidates_for_briefing
from .claims import ClaimError, ClaimStore, KnowledgeService, statements_conflict
from .entities import EntityError
from .conversations import ConversationStore
from . import conversation_memory
from .proposals import Evidence, ProposalError, ProposalKind, ProposalState, ProposalStore
from .regeln import ERLAUBTE_STUFEN, RegelFehler, RegelStore
from .scheduler import (
    Scheduler,
    JobResult,
    backup_job,
    consolidation_job,
    ingest_job,
    summary_job,
)
from .summaries import MIN_EPISODES, Summarizer
from .connectors import (
    CalendarCollection,
    CalendarConfig,
    CalendarConnector,
    ICalendarSubscription,
    MailCollection,
    MailConfig,
    MailConnector,
    NamedCalendar,
    NamedMail,
)
from .episodes import EpisodeError, EpisodeKind, EpisodeState, EpisodeStore
from .ingest import ADAPTERS, TEXT_SUFFIXES, ingest_directory
from .transkript_routes import nach_aufnahme, termin_stand
from .model import Kind, Provenance, RedactionReason, Sensitivity, SourceType, ensure_aware
from .morning import compose as compose_morning
from .policy import Policy, PolicyError
from .providers import from_env as provider_from_env
from .model_roles import lese_wahlen, provider_fuer, rollen_von
from .connectors.mail import MailError
from .providers_mail import catalogue as mail_catalogue
from .providers_mail import guess as guess_mail_provider
from .secrets import Keychain, load_into_env
from .security import SecurityError, file_roots_from_env
from .store import ConflictError, SelfModelStore
from .tasks import TaskStore, TaskChangedError, TaskRequestConflict
from .tools import build_registry
from .zeitgrenze import mit_zeitgrenze
from .workspace import (
    NoteKind,
    Priority,
    ProjectStatus,
    WorkspaceError,
    WorkspaceStore,
)

# Wo in der Oberfläche man etwas einrichtet. Steht hier einmal, weil es in
# mehreren Meldungen vorkommt: ein Wegweiser, der auf einen Ort zeigt, den es
# nicht mehr gibt, ist schlimmer als keiner.
WEGWEISER = "Unter „Einstellungen“"
# So lange wartet die Startseite auf das Postfach, dann zeigt sie den Rest.
POSTFACH_ZEITGRENZE = 6.0

TOKEN_ENV = "ICARUS_SIDECAR_TOKEN"
UI_SESSION_COOKIE = "kingfisher_session"
DATA_ENV = "ICARUS_DATA_DIR"
ROOTS_ENV = "ICARUS_FILE_ROOTS"
UI_ENV = "ICARUS_UI_DIR"
#: Unter der eigenen Frage: der Weg zu der Quelle, als die Kingfisher die Frage gespeichert hat. Der Name sagt, dass es
#: die eigene Frage ist und kein Beleg der Antwort (Fremdprobe 2, Befund 13).
EIGENE_FRAGE_ANSEHEN = "So ist deine Nachricht gespeichert"

#: Adresse, an die gebunden wird. Standard ist Loopback, und das bleibt so.
#:
#: Im Container muss der Dienst auf 0.0.0.0 hören, sonst greift die
#: Portfreigabe nicht — dort ist „alle Adressen" *innerhalb* des Containers,
#: und was von außen erreichbar ist, entscheidet die Freigabe in `compose.yaml`.
#: Die muss `127.0.0.1:8890:8890` lauten. Steht dort `8890:8890`, hängt das
#: gesamte persönliche Gedächtnis im lokalen Netz.
HOST_ENV = "ICARUS_SIDECAR_HOST"
DEFAULT_HOST = "127.0.0.1"


def _ui_dir() -> Path | None:
    """Wo die Oberfläche liegt, wenn der Sidecar sie selbst ausliefern soll.

    Im Container zeigt `ICARUS_UI_DIR` auf die gebaute React-Oberfläche
    (`/opt/kingfisher/ui`). In einer Arbeitskopie ist es der Vite-Ausgabeordner
    `app/dist` — falls gebaut. Sonst gibt es keine Oberfläche, und der Sidecar
    ist nur die API.
    """
    configured = os.environ.get(UI_ENV)
    if configured:
        target = Path(configured)
        return target if target.is_dir() else None
    # Arbeitskopie: sidecar/icarus_memory/server.py → ../../app/dist
    # (Ausgabeordner von `npm run build` in app/kingfisher, siehe vite.config.ts)
    candidate = Path(__file__).resolve().parents[2] / "app" / "dist"
    return candidate if candidate.is_dir() else None


def _data_dir() -> Path:
    configured = os.environ.get(DATA_ENV)
    if configured:
        return Path(configured)
    # macOS-Konvention; die App überschreibt das ohnehin per Umgebungsvariable.
    return Path.home() / "Library" / "Application Support" / "Icarus"


# -- Anfragemodelle --------------------------------------------------------


class ProvenanceIn(BaseModel):
    source_type: SourceType
    source_ref: str | None = None
    captured_at: datetime | None = None
    extracted_by: str | None = None
    verbatim: str | None = None


class RecordIn(BaseModel):
    statement: str = Field(min_length=1)
    kind: Kind
    provenance: ProvenanceIn
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    supersedes: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity = Sensitivity.NORMAL
    tags: list[str] = Field(default_factory=list)


class GoalFinishIn(BaseModel):
    outcome: Literal["achieved", "stopped"]
    note: str = Field(default="", max_length=4000)


class RegelIn(BaseModel):
    name: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    stufe: str = "notify"
    passt_auf: dict[str, str] = Field(default_factory=dict)


class RedactIn(BaseModel):
    reason: RedactionReason = RedactionReason.USER_REQUEST


class ChatIn(BaseModel):
    message: str = Field(min_length=1)


class ConversationIn(BaseModel):
    title: str = Field(default="Neues Gespräch", min_length=1, max_length=120)


class CalendarAssignmentIn(BaseModel):
    uid: str = Field(min_length=1, max_length=2048)
    project_id: str | None = Field(default=None, max_length=200)
    start: str | None = Field(default=None, max_length=64)


class CalendarFollowupIn(BaseModel):
    uid: str = Field(min_length=1, max_length=2048)
    start: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=512 * 1024)
    format: Literal["text", "srt", "vtt"] = "text"
    notiz: str = Field(default="", max_length=512 * 1024)
    project_id: str | None = Field(default=None, max_length=200)


class CalendarFollowupStatusIn(BaseModel):
    uid: str = Field(min_length=1, max_length=2048)
    start: str = Field(min_length=1, max_length=64)
    nichts: bool


class ConversationMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    answer_mode: Literal['auto', 'chat', 'memory_evidence'] = 'auto'
    new_question: bool = False
    # Angeklickte Antwort auf die unmittelbar vorherige Rückfrage.
    clarification_choice: int | None = Field(default=None, ge=0, le=5)
    # Vom Nutzer gewähltes Datum der Nachricht auf eine Zeitrückfrage.
    clarification_date: date | None = None


class KnowledgeEvidenceIn(BaseModel):
    episode_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class KnowledgeCandidateIn(BaseModel):
    subject_ref: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    rationale: str = ""
    scope_ref: str | None = None
    target_ref: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[KnowledgeEvidenceIn] = Field(min_length=1)
    proposed_by: str = ""


class EntityCreateIn(BaseModel):
    kind: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=500)


class EntityRenameIn(BaseModel):
    label: str = Field(min_length=1, max_length=500)


class EntitySourceIn(BaseModel):
    source: str = Field(min_length=1)
    account: str = Field(min_length=1)
    native_id: str = Field(min_length=1)


class KnowledgeRetractIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class KnowledgeCorrectIn(BaseModel):
    value: str = Field(min_length=1, max_length=2000)
    statement: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=1, max_length=2000)
    scope_ref: str | None = None
    target_ref: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class KnowledgeAcceptIn(BaseModel):
    supersedes: list[str] = Field(default_factory=list)


class MemoryQuestionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stand: str = Field(min_length=64, max_length=64)
    proposal_id: str | None


class ConversationMemoryCandidateIn(BaseModel):
    """Ein ausdrücklich aus einer Nutzerzeile formulierter Wissensvorschlag.

    Diese Schnittstelle ist absichtlich strukturiert. Sie ist der Übergang für
    einen späteren Gesprächsablauf, nicht ein stiller Extraktor: Der aufrufende
    Ablauf muss die konkrete Quellnachricht sowie Subjekt, Beziehung und Wert
    benennen. Ohne diesen Aufruf bleibt ein Gespräch ausschließlich Gespräch.
    """

    source_message_id: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    rationale: str = ""
    scope_ref: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ConversationMemoryAcceptIn(BaseModel):
    """Die Ersetzung bestehender Stände braucht einen zweiten, sichtbaren Klick."""

    replace_conflicts: bool = False


class ResolveIn(BaseModel):
    granted: bool
    confirmation: str | None = None


class ExportIn(BaseModel):
    passphrase: str | None = None


class RestoreIn(BaseModel):
    # Nur der Dateiname, nie ein Pfad. `Path(name).name` wirft alles davor weg;
    # so ist „../../etc/passwd" schlicht „passwd" und findet sich nicht.
    name: str = Field(min_length=1)


class VerifyIn(BaseModel):
    path: str
    passphrase: str | None = None


def _mail_sink(app: FastAPI):
    """Verbindet das Werkzeug mail_senden mit dem echten Versand.

    Wird erst nach erteilter Freigabe gerufen. Ohne eingerichteten Mailzugang
    schlägt es hörbar fehl, statt Erfolg vorzutäuschen.
    """

    if not hasattr(app.state, "mail_reply_execution"):
        app.state.mail_reply_execution = threading.local()

    def send(payload: dict) -> str:
        token = getattr(app.state.mail_reply_execution, "token", None)
        if token:
            # Last check occurs inside the approved tool, immediately before
            # its outward effect. The token is assigned only by approval routes.
            from .mail_reply_suggestions import validate_context, validate_destination
            context = validate_context(app, token)
            validate_destination(context, payload.get('account_id', ''), payload.get('to', ''))
            if payload != getattr(app.state.mail_reply_execution, "arguments", None):
                raise RuntimeError("Der freigegebene Antwortinhalt stimmt nicht mit dem Versand überein.")
        mail = getattr(app.state, "mail", None)
        if mail is None:
            raise RuntimeError(
                "Kein Mailzugang eingerichtet. Die Freigabe war erteilt, "
                "aber es gibt keinen Kanal (ICARUS_SMTP_HOST fehlt)."
            )
        return mail.send(
            payload["to"], payload["subject"], payload["body"],
            in_reply_to=payload.get("in_reply_to", "") or "",
            **({"account_id": payload["account_id"]} if payload.get("account_id") else {}),
        )

    return send


class TaskIn(BaseModel):
    title: str = Field(min_length=1)
    due: datetime | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    goal_id: str | None = Field(default=None, max_length=200)


class MailTaskIn(BaseModel):
    request_id: uuid.UUID | None = None
    quick_accept: bool = False
    source_quote: str | None = Field(default=None, min_length=8, max_length=4000)
    source_digest: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    title: str = Field(min_length=1, max_length=4096)
    project_id: str | None = None
    due: datetime | None = None
    waiting_for: str | None = Field(default=None, max_length=1024)


class TaskCandidateIn(BaseModel):
    title: str = Field(min_length=1, max_length=4096)
    project_id: str | None = None
    due: datetime | None = None
    waiting_for: str | None = Field(default=None, max_length=1024)


class MailReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=100000)
    context_token: str | None = Field(default=None, min_length=20, max_length=200)


class ThreadSummaryIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context_fingerprint: str = Field(pattern='^[0-9a-f]{64}$')


class TaskProjectIn(BaseModel):
    project_id: str | None


class TaskEditIn(BaseModel):
    title: str | None = Field(default=None, max_length=4096)
    due: datetime | None = None
    notes: str | None = None
    remind_at: datetime | None = None
    expected_remind_at: datetime | None = None


class SourceProjectIn(BaseModel):
    project_id: str | None = Field(default=None, max_length=200)


class SourceProjectsIn(BaseModel):
    """Mehrere Quellen umhängen, nur wo sie noch den erwarteten Stand haben."""
    episode_ids: list[str] = Field(min_length=1, max_length=500)
    project_id: str | None = Field(default=None, max_length=200)
    only_if_project_id: str | None = Field(default=None, max_length=200)


class MCPServerIn(BaseModel):
    name: str = Field(min_length=1)
    befehl: str = Field(min_length=1)
    """Als eine Zeile, wie man sie im Terminal tippen würde.

    Zerlegt wird hier, mit `shlex` — nicht von einer Shell. Der Nutzer soll
    `npx -y @dienst/server` eintippen dürfen, ohne eine Liste zu bauen; eine
    Shell dabei laufen zu lassen wäre etwas ganz anderes.
    """
    umgebung: dict[str, str] = Field(default_factory=dict)


class EntscheidungIn(BaseModel):
    statement: str = Field(min_length=1)
    derived_from: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    project_id: str | None = None


class WartetIn(BaseModel):
    name: str = Field(min_length=1)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1)
    area: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    priority: Priority = Priority.MEDIUM
    description: str | None = None
    deadline: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class ProjectPatch(BaseModel):
    status: ProjectStatus | None = None
    priority: Priority | None = None
    description: str | None = None
    deadline: datetime | None = None
    area: str | None = None


class NoteIn(BaseModel):
    title: str = Field(min_length=1)
    body: str = ""
    kind: NoteKind = NoteKind.REFERENCE
    project_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class NotePatch(BaseModel):
    title: str | None = None
    body: str | None = None
    project_id: str | None = None


class EpisodeIn(BaseModel):
    kind: EpisodeKind = EpisodeKind.DOCUMENT
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    occurred_at: datetime | None = None
    project_id: str | None = None
    participants: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class DocumentPreviewIn(BaseModel):
    content_base64: str = Field(min_length=1, max_length=7 * 1024 * 1024)


class TranscriptPreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=512 * 1024)
    format: Literal["srt", "vtt"]


class DocumentSourceIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=512 * 1024)
    project_id: str | None = None


class IngestIn(BaseModel):
    path: str = Field(min_length=1)
    adapter: str = "markdown"
    limit: int = Field(default=5000, ge=1, le=100000)


class MailIn(BaseModel):
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    user: str = ""
    sender: str = ""


class CalendarIn(BaseModel):
    url: str = ""
    user: str = ""


class MailAccountIn(BaseModel):
    """Eine neue oder aktualisierte lokale Mail-Konfiguration.

    Ein Passwort ist optional, damit eine Quelle zunächst nur vorbereitet
    werden kann. Erst ein späterer Verbindungstest entscheidet, ob sie als
    erreichbar gilt.
    """

    label: str = Field(min_length=1, max_length=120)
    imap_host: str = Field(min_length=1, max_length=255)
    imap_port: int = Field(default=993, ge=1, le=65535)
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    user: str = Field(min_length=1, max_length=320)
    sender: str = Field(default="", max_length=320)
    password: str | None = Field(default=None, max_length=4096)


class KalenderAnmeldungIn(BaseModel):
    """Kalender wie Mail (`kalender_anmeldung.py`): die Mailadresse, dazu das Passwort oder das Postfach, dessen
    Passwort gelten soll; eine eigene Adresse nur, wenn der Anbieter unbekannt ist."""
    model_config = ConfigDict(extra="forbid")
    adresse: str = Field(min_length=3, max_length=320)
    password: str | None = Field(default=None, max_length=4096)
    mail_konto: str | None = Field(default=None, max_length=120)
    url: str | None = Field(default=None, max_length=2048)


class KalenderAboIn(BaseModel):
    """Ein Kalender über seine (geheime) iCal-Adresse (`kalender_abo.py`); der Name ist freiwillig."""
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=8, max_length=2048)
    label: str | None = Field(default=None, max_length=120)


class CalendarSourceIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern="^(caldav|ical)$")
    url: str = Field(min_length=1, max_length=2048)
    user: str = Field(default="", max_length=320)
    password: str | None = Field(default=None, max_length=4096)


class SetupIn(BaseModel):
    """Einstellungen ändern.

    Jedes Feld ist optional und `None` bedeutet **nicht ändern**. Ein leerer
    String bedeutet dagegen **leeren** — sonst ließe sich ein einmal
    eingetragener Mailserver nie wieder loswerden.

    Geheimnisse gehen nur in diese Richtung. Es gibt bewusst kein Feld, das sie
    zurückgibt: Ein solches wäre der bequemste Weg, einen Schlüssel
    versehentlich zu protokollieren.
    """

    provider: str | None = None
    model: str | None = None
    endpoint: str | None = None
    file_roots: list[str] | None = None
    mail: MailIn | None = None
    calendar: CalendarIn | None = None
    onboarded: bool | None = None

    api_key: str | None = None
    mail_password: str | None = None
    calendar_password: str | None = None


class ScheduleIn(BaseModel):
    mail_accounts: list[str] | None = None
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=10080)
    with_model: bool | None = None
    sources: dict[str, str] | None = None
    backup: bool | None = None


class ConsolidateIn(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    with_model: bool = True


class SummariseIn(BaseModel):
    # Wenige pro Lauf: Ein erster Durchgang über fünf Jahre Vault schriebe
    # sonst sechzig Modellanfragen in einem Zug.
    limit: int = Field(default=3, ge=1, le=24)
    with_model: bool = True


class ToolIn(BaseModel):
    """Argumente eines direkten Werkzeugaufrufs.

    Bewusst frei: Jedes Werkzeug bringt sein eigenes Schema mit, und die
    Prüfung gehört dorthin, nicht in eine zweite Beschreibung hier.
    """

    model_config = {"extra": "allow"}


def _loese_mcp(app: FastAPI) -> None:
    """Beendet alle angedockten Server.

    Muss vor jedem Neubau laufen: Sonst bliebe bei jeder Änderung an den
    Einstellungen ein Kindprozess übrig, und nach dem zehnten Speichern liefen
    zehn fremde Programme.
    """
    for verbindung, _ in (getattr(app.state, "mcp", None) or {}).values():
        try:
            verbindung.stop()
        except Exception:  # noqa: BLE001 - ein hängender Fremdprozess darf hier nichts kippen
            pass
    app.state.mcp = {}


def _docke_mcp_an(app: FastAPI) -> None:
    """Startet die eingetragenen MCP-Server und holt ihre Werkzeuge.

    Ein Server, der nicht startet, ist kein Grund, die App nicht zu starten.
    Sein Fehler wird gemerkt und in der Einrichtung angezeigt — dort kann
    jemand etwas dagegen tun.
    """
    _loese_mcp(app)
    fehler: dict[str, str] = {}
    verbindungen: dict[str, Any] = {}
    if not config.mcp_tuer_offen():
        # Ausgeschaltet heißt: kein fremdes Programm wird gestartet, auch
        # nicht, wenn noch Einträge aus früherer Zeit in den Einstellungen stehen.
        app.state.mcp = verbindungen
        app.state.mcp_fehler = fehler
        return

    for eintrag in getattr(app.state, "settings", config.Settings()).mcp_server:
        angabe = mcp_client.Serverangabe.from_dict(eintrag)
        if not angabe.aktiv or not angabe.name:
            continue
        verbindung = mcp_client.MCPVerbindung(angabe)
        try:
            verbindung.start()
            werkzeuge = verbindung.werkzeuge()
        except mcp_client.MCPFehler as exc:
            verbindung.stop()
            fehler[angabe.name] = str(exc)
            continue
        verbindungen[angabe.name] = (verbindung, werkzeuge)

    app.state.mcp = verbindungen
    app.state.mcp_fehler = fehler


def _integration_secret(app: FastAPI, kind: str, integration_id: str) -> str | None:
    """Liest genau das Passwort einer lokalen Integration.

    Geheimnisse werden nie aus `einstellungen.json` und nie in einen
    Modellkontext übernommen. Die dynamische Kennung bleibt vom Namen und der
    Adresse des Kontos entkoppelt.
    """
    name = config.integration_secret_name(kind, integration_id)
    value = os.environ.get(name)
    if value:
        return value
    keychain = getattr(app.state, "keychain", None)
    return keychain.get(name) if keychain is not None and keychain.available else None


def _configured_mail(app: FastAPI) -> Any:
    """Erzeugt den lesenden Mehrkonto-Zugriff aus den lokalen Einstellungen."""
    settings: config.Settings = app.state.settings
    accounts: list[NamedMail] = []
    for entry in settings.mail_accounts:
        if not entry.configured:
            continue
        if entry.auth_method == "microsoft_graph":
            # Microsoft 365 über Graph (microsoft_routes.py): ein Zugang je Konto, kein Passwort, nur lesen.
            from .microsoft_routes import post_leser
            leser = post_leser(app, entry)
            if leser is not None:
                accounts.append(NamedMail(id=entry.id, label=entry.label, reader=leser, can_send=False,
                                          sender=entry.user))
            continue
        password = _integration_secret(app, "mail", entry.id)
        if not password:
            continue
        connector = MailConnector(MailConfig(
            imap_host=entry.imap_host,
            username=entry.user,
            password=password,
            smtp_host=entry.smtp_host,
            imap_port=entry.imap_port,
            smtp_port=entry.smtp_port,
            from_address=entry.sender,
            access_token=(lambda key=config.integration_secret_name("mail", entry.id): app.state.google_oauth.access_token(key)) if entry.auth_method == "google_oauth" else None,
        ))
        accounts.append(NamedMail(
            id=entry.id,
            label=entry.label,
            reader=connector,
            can_send=bool(entry.smtp_host),
            sender=entry.sender or entry.user,
        ))
    legacy = MailConfig.from_env(dict(os.environ))
    # Ein vorhandenes Ein-Konto-Setup darf beim Hinzufügen eines neuen Kontos
    # nicht unsichtbar werden. Ohne weitere Quelle bleibt es sein bisheriger
    # Connector, damit Kennungen und der Versandweg kompatibel bleiben.
    if legacy and not accounts:
        return MailConnector(legacy)
    if legacy:
        accounts.append(NamedMail(
            id="legacy-mail", label="Bestehendes Mailkonto",
            reader=MailConnector(legacy), can_send=bool(legacy.smtp_host),
            sender=legacy.sender,
        ))
    return MailCollection(accounts) if accounts else None


def _configured_calendar(app: FastAPI) -> Any:
    """Erzeugt eine lesende Vereinigung von CalDAV und iCalendar-Abos."""
    settings: config.Settings = app.state.settings
    sources: list[NamedCalendar] = []
    mac = getattr(app.state, "mac_calendar", None)
    if mac is not None and mac.read()["enabled"]:
        sources.append(NamedCalendar(id="mac-calendar", label="Mac-Kalender", reader=mac))
    for entry in settings.calendar_sources:
        if not entry.configured:
            continue
        if entry.kind == "google":
            from .google_calendar import GoogleCalendar
            key = config.integration_secret_name("calendar", entry.id)
            if _integration_secret(app, "calendar", entry.id):
                sources.append(NamedCalendar(id=entry.id, label=entry.label,
                    reader=GoogleCalendar(entry.url, lambda key=key: app.state.google_oauth.access_token(key))))
            continue
        if entry.kind == "microsoft":
            from .microsoft_routes import kalender_leser
            leser = kalender_leser(app, entry)
            if leser is not None:
                sources.append(NamedCalendar(id=entry.id, label=entry.label, reader=leser))
            continue
        if entry.kind == "ical":
            # Eine geheime Adresse (Google, `kalender_abo.py`) liegt im Schlüsselbund; ältere Abos stehen in `url`.
            sources.append(NamedCalendar(
                id=entry.id, label=entry.label,
                reader=ICalendarSubscription(_integration_secret(app, "calendar", entry.id) or entry.url,
                                             transport=getattr(app.state, "ical_transport", None)),
            ))
            continue
        password = _integration_secret(app, "calendar", entry.id)
        if not password or not entry.user:
            continue
        sources.append(NamedCalendar(
            id=entry.id, label=entry.label,
            reader=CalendarConnector(CalendarConfig(
                url=entry.url, username=entry.user, password=password,
            )),
        ))
    legacy = CalendarConfig.from_env(dict(os.environ))
    if legacy and not sources:
        return CalendarConnector(legacy)
    if legacy:
        sources.append(NamedCalendar(
            id="legacy-calendar", label="Bestehender Kalender",
            reader=CalendarConnector(legacy),
        ))
    return CalendarCollection(sources) if sources else None


from .self_model_support import EpisodeSupportResolver
from .support_review import SupportReview, SupportReviewConflict


class SupportReassessmentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_token: str = Field(min_length=1, max_length=256)
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def require_true(cls, value):
        if value is not True:
            raise ValueError('Eine ausdrückliche Bestätigung ist erforderlich.')
        return value


logger = logging.getLogger(__name__)

def _frage_verstehen(app: FastAPI, message: str):
    """Die strukturierte Anfrage zur Nachricht (Rolle „frage“); ohne dieses Vermögen der Rückfall."""
    verstehen = getattr(app.state.agent, "frage_verstehen", None)
    if callable(verstehen):
        return verstehen(message)
    from .frage import rueckfall
    return rueckfall(message)


def _project_sources_available(app: FastAPI, message: str) -> bool:
    """Nennt die Nachricht ein Projekt mit eingeordneten Quellen?"""
    from .working_memory_answers import MAX_PROJECT_SOURCES, mentioned_projects
    from .working_memory_store import WorkingMemoryStore
    try:
        mentioned = mentioned_projects(message, _project_directory(app)())
    except Exception:  # noqa: BLE001 - ohne Projektverzeichnis bleibt die Wortsuche
        return False
    store = WorkingMemoryStore(app.state.episodes)
    for identifier in mentioned:
        members = [e.id for e in app.state.episodes.by_project(identifier, limit=MAX_PROJECT_SOURCES)]
        if members and store.source_refs(episode_ids=members, limit=64)['refs']:
            return True
    return False


def _working_memory_pace(app: FastAPI):
    """Ein Durchsatzmesser je App; nur Hintergrundpakete, keine Einzelaufträge."""
    pace = getattr(app.state, "working_memory_pace", None)
    if pace is None:
        from .working_memory_worker import Pace
        pace = app.state.working_memory_pace = Pace()
    return pace


def _build_agent(app: FastAPI) -> Agent:
    """Baut Konnektoren, Werkzeuge und Agent aus der aktuellen Umgebung.

    Als eigene Funktion, weil das **zweimal** gebraucht wird: beim Start und
    nach jeder Änderung an den Einstellungen. Ohne das müsste der Nutzer die
    App neu starten, nachdem er einen Schlüssel eingetragen hat — und genau
    diese Art Reibung ist der Grund, warum Programme nach dem ersten Versuch
    weggelegt werden.

    Der Gesprächsverlauf geht dabei absichtlich verloren. Ein Verlauf, der vor
    einem Anbieterwechsel entstanden ist, gehört einem anderen Modell; ihn
    mitzunehmen hieße, Aussagen weiterzuschleppen, die ein neuer Anbieter nie
    gesehen hat.
    """
    app.state.runtime_boundary.check()
    app.state.mail = _configured_mail(app)
    app.state._calendar_search_generation = getattr(app.state, '_calendar_search_generation', 0) + 1
    app.state.search_calendar_cache = None
    app.state.calendar = _configured_calendar(app)
    _docke_mcp_an(app)

    from .memory_routes import coverage as memory_coverage
    from .calendar_context import local_snapshot

    # Ohne Rollenkonfiguration ist der Anbieter für alles derselbe wie bisher.
    # Mit ihr bekommt der Agent (Gespräch) den Anbieter der Rolle „antwort“;
    # der Standardanbieter bleibt für die übrigen Rollen gemerkt.
    standard_provider = provider_from_env()
    app.state.standard_provider = standard_provider
    app.state.rollen = None
    agent = Agent(
        store=app.state.store,
        policy=Policy(),
        audit=app.state.audit,
        regeln=getattr(app.state, "regeln", None),
        tools=build_registry(
            app.state.store,
            outward_sink=_mail_sink(app),
            file_roots=file_roots_from_env(os.environ.get(ROOTS_ENV)),
            mail=app.state.mail,
            calendar=app.state.calendar,
            task_store=app.state.tasks,
            workspace=app.state.workspace,
            episodes=app.state.episodes,
            mcp_verbindungen=getattr(app.state, "mcp", None),
        ),
        provider=provider_fuer("antwort", standard_provider, lese_wahlen(app.state.settings.model_roles)),
        knowledge=app.state.claims,
        knowledge_conflicts=app.state.knowledge_service.answer_conflict_status,
        episodes=app.state.episodes,
        support_resolver=EpisodeSupportResolver(app.state.proposals, app.state.episodes),
        snapshot_provider=app.state.episodes.support_snapshot,
        memory_coverage=lambda: memory_coverage(app.state.episodes, app.state.proposals),
        calendar_context=lambda: local_snapshot(getattr(app.state, "mac_calendar", None)),
    )
    verdrahte_zusaetze(app, agent)
    from .knowledge_search import configured_search
    app.state.agent = agent
    working_memory_semantic_runtime.bind(app, agent)
    rollen = rollen_von(app)
    agent._knowledge_search = (configured_search(rollen.provider("einbettung"), rollen.einbettung_modell())
                               if "einbettung" in rollen.wahlen else configured_search(rollen.provider("einbettung")))
    # Verdichter und Zusammenfasser hängen am Anbieter der Rolle `hintergrund`, nicht am Gespräch.
    baue_hintergrund(app)
    _wire_scheduler(app)
    return agent


def _wire_scheduler(app: FastAPI) -> None:
    """Hängt den Zeitplan an die aktuellen Bausteine.

    Muss nach jedem Agentenneubau erneut laufen: Der Verdichter darin ist ein
    neues Objekt, und ein Zeitplan, der auf den alten zeigt, würde weiter das
    abgemeldete Modell fragen.
    """
    settings: config.Settings = app.state.settings
    plan = settings.schedule
    roots = file_roots_from_env(os.environ.get(ROOTS_ENV))
    generation = getattr(app.state, "local_model_automation_generation", 0) + 1
    app.state.local_model_automation_generation = generation

    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        scheduler = Scheduler()
        app.state.scheduler = scheduler

    def scheduled_provider(provider, *, agent, plan_at_start):
        if provider is not None and plan_at_start["local_model_only"]:
            from .local_model_guard import VerifiedLocalProvider
            from .memory_analysis import model_key
            original_model = model_key(provider)
            return VerifiedLocalProvider(provider, permitted=lambda: (
                app.state.local_model_automation_generation == generation
                and app.state.agent is agent
                and rollen_von(app).provider("hintergrund") is provider and model_key(provider) == original_model
                and asdict(app.state.settings.schedule) == plan_at_start
            ))
        return provider

    def run_sources():
        was_enabled = app.state.settings.schedule.enabled
        with app.state.conversation_lock:
            results = ingest_job(app.state.episodes, roots, dict(app.state.settings.schedule.sources),
                on_source=lambda root, ref, episode: track_document(app.state.episodes, app.state.claims, root, ref, episode),
                on_complete=lambda root, adapter, observed: exclude_missing_documents(app.state.episodes, app.state.claims, root, adapter, observed),
                on_transcript=nach_aufnahme(app))()
        from . import mail_sync_status, mail_filter
        for account_id in list(app.state.settings.schedule.mail_accounts):
            from .mail_intake import Intake
            if account_id in Intake(app.state.episodes).accounts():
                continue  # Persistent intake runs in bounded background packages.
            code = 'credentials_missing'
            try:
                with app.state.conversation_lock:
                    mail_sync_status.record_attempt(app.state.settings, account_id)
                    config.save(_data_dir(), app.state.settings)
                    reader = app.state.mail.reader_for(account_id)
                    code = 'unavailable'
                    selected_filter = mail_filter.policy(app.state.settings)
                    screening_agent = app.state.agent
                    screening_with_model = app.state.settings.schedule.with_model
                def permitted():
                    current = app.state.settings
                    return (account_id in current.schedule.mail_accounts
                            and (not was_enabled or current.schedule.enabled)
                            and any(entry.id == account_id and entry.configured for entry in current.mail_accounts)
                            and app.state.mail.reader_for(account_id) is reader
                            and mail_filter.policy(current) == selected_filter
                            and app.state.agent is screening_agent
                            and current.schedule.with_model == screening_with_model
                            and app.state.local_model_automation_generation == generation)
                screening_provider = (mail_filter.screening_provider(app, permitted=permitted)
                    if selected_filter['ai_enabled'] else None)
                report = mail_ingestion.sync_account(
                    app.state.episodes, account_id, reader, limit=10 if selected_filter['ai_enabled'] else 50,
                    permitted=permitted, permission_lock=app.state.conversation_lock, claims=app.state.claims,
                    screen=lambda message: mail_filter.classify(message, selected_filter, screening_provider),
                    hold=lambda message, decision: mail_filter.hold(app, message, decision,
                        lambda: config.save(_data_dir(), app.state.settings)),
                )
                with app.state.conversation_lock:
                    if report.get('cancelled'):
                        mail_sync_status.record_failure(app.state.settings, account_id, 'cancelled')
                    else:
                        mail_sync_status.record_success(app.state.settings, account_id, report)
                    config.save(_data_dir(), app.state.settings)
                detail = "Aufnahme gestoppt." if report.get("cancelled") else f"{report['recorded']} neu, {report['duplicates']} bekannt"
                if report.get('filtered'):
                    detail += f", {report['filtered']} zur Prüfung"
                results.append(JobResult(f"mail:{account_id}", True, detail))
            except Exception:
                # Keine Serverantworten oder Zugangsdaten in Statusmeldungen.
                with app.state.conversation_lock:
                    mail_sync_status.record_failure(app.state.settings, account_id, code)
                    config.save(_data_dir(), app.state.settings)
                results.append(JobResult(f"mail:{account_id}", False, "Mailaufnahme fehlgeschlagen. Fortschritt bleibt erhalten."))
        from .world_monitor import WorldMonitor
        monitor = WorldMonitor(app.state.settings, app.state.episodes, app.state.claims,
            lambda settings: config.save(_data_dir(), settings), app.state.conversation_lock)
        for source in monitor.list():
            if not source['enabled']:
                continue
            if was_enabled and not app.state.settings.schedule.enabled:
                break
            try:
                monitor.refresh(source['id'], permitted=lambda: not was_enabled or app.state.settings.schedule.enabled)
                results.append(JobResult('world:' + source['id'], True, 'Öffentliche Quelle aktualisiert.'))
            except (ValueError, KeyError):
                results.append(JobResult('world:' + source['id'], False, 'Öffentliche Quelle gerade nicht erreichbar.'))
        from .calendar_memory_routes import abgleichen as kalender_abgleichen
        try:
            kalender = kalender_abgleichen(app, erlaubt=lambda: not was_enabled or app.state.settings.schedule.enabled)
            for quelle, r in kalender['quellen'].items():
                summe = ', '.join(f'{r[name]} {name}' for name in ('neu', 'geaendert', 'entzogen') if r[name])
                results.append(JobResult(f'kalender:{quelle}', not r['fehler'],
                    (summe or 'Termine unverändert') + ('. Lesefehler; Termine unberührt.' if r['fehler'] else '')))
        except Exception:  # Keine Kalenderdaten in Statusmeldungen.
            results.append(JobResult('kalender', False, 'Termine konnten nicht ins Gedächtnis übernommen werden.'))
        with app.state.conversation_lock:
            if not was_enabled or app.state.settings.schedule.enabled:
                from .learning_service import propose_patterns
                try:
                    proposed = propose_patterns(app.state.store, app.state.episodes,
                        app.state.proposals, app.state.knowledge_service, at=datetime.now().astimezone())
                    results.append(JobResult('lernen', True, f'{len(proposed)} belegte Beobachtungen zur Prüfung.'))
                except ValueError:
                    results.append(JobResult('lernen', False, 'Beobachtungen konnten nicht vollständig geprüft werden.'))
        return results
    def run_task_detection(with_model, *, limit=10, rechecks_only=False):
        agent = getattr(app.state, "agent", None)
        plan_at_start = asdict(app.state.settings.schedule)
        detector = TaskDetector(app.state.episodes, app.state.proposals,
                                scheduled_provider(rollen_von(app).provider("hintergrund"), agent=agent,
                                                   plan_at_start=plan_at_start), app.state.conversation_lock,
                                tasks=app.state.tasks)
        def permitted():
            return (getattr(app.state, "agent", None) is agent
                    and asdict(app.state.settings.schedule) == plan_at_start)
        report = detector.run(with_model=with_model, limit=limit, rechecks_only=rechecks_only, permitted=permitted)
        if report.cancelled:
            return JobResult("zusagen", True, "Prüfung nach geänderter Freigabe gestoppt.")
        if not report.available:
            return JobResult("zusagen", True, "Für Zusagenerkennung die Modellprüfung mit einem lokalen Modell aktivieren.")
        detail = f"{report.analyzed} Quellen geprüft, {report.proposed} Vorschläge zur Prüfung"
        if report.failed:
            detail += f", {report.failed} Prüfungen fehlgeschlagen; erneuter Versuch folgt"
        return JobResult("zusagen", report.failed == 0, detail)

    def run_working_memory(with_model, *, prompt=False, source_ids=None):
        if not with_model:
            return JobResult('gedaechtnis', True, 'Automatische Einordnung pausiert: Modellprüfung ist ausgeschaltet.')
        from .working_memory_worker import run
        agent = app.state.agent
        plan_at_start = asdict(app.state.settings.schedule)
        if prompt and (not plan_at_start['enabled'] or not plan_at_start['with_model']
                       or not scheduler.prompt_allowed()
                       or not getattr(rollen_von(app).provider('hintergrund'), 'is_local', False)):
            return JobResult('gedaechtnis', True, 'Einordnung nach geänderter Freigabe gestoppt.')
        result = run(app.state.episodes, scheduled_provider(rollen_von(app).provider('hintergrund'), agent=agent,
            plan_at_start=plan_at_start), app.state.conversation_lock, source_ids=source_ids,
            pace=None if prompt else _working_memory_pace(app),
            permitted=lambda: (app.state.agent is agent
                               and asdict(app.state.settings.schedule) == plan_at_start
                               and (not prompt or scheduler.prompt_allowed())))
        from .memory_categories import Categories
        Categories(app.state.episodes).run(
            scheduled_provider(rollen_von(app).provider('hintergrund'), agent=agent, plan_at_start=plan_at_start), limit=1 if prompt else 2,
            permission_lock=app.state.conversation_lock, source_ids=source_ids if prompt else None,
            permitted=lambda: (app.state.agent is agent
                and asdict(app.state.settings.schedule) == plan_at_start
                and (not prompt or scheduler.prompt_allowed())))
        semantic = working_memory_semantic_runtime.search(app)
        if semantic is not None and plan_at_start['enabled'] and plan_at_start['with_model']:
            # Always take one global batch: a stream of newly uploaded IDs
            # must not starve older already-classified sources.
            indexed = semantic.index_batch(permitted=lambda: (
                app.state.local_model_automation_generation == generation
                and app.state.agent is agent
                and getattr(app.state, 'semantic_search', None) is semantic
                and asdict(app.state.settings.schedule) == plan_at_start
                and (not prompt or scheduler.prompt_allowed())))
            return JobResult(result.name, result.ok and indexed.ok, result.detail + ' ' + indexed.detail)
        return result

    def run_lage(with_model):
        # Ebene 3: Lagen aus den Akten, nur mit lokalem Modell und derselben Freigabe wie die Einordnung.
        if not with_model:
            return JobResult('lage', True, 'Lagen pausiert: Modellprüfung ist ausgeschaltet.')
        from .lage_routes import lauf as lage_lauf
        agent = app.state.agent
        plan_at_start = asdict(app.state.settings.schedule)
        return lage_lauf(
            app, scheduled_provider(rollen_von(app).provider('hintergrund'), agent=agent, plan_at_start=plan_at_start),
            permitted=lambda: app.state.agent is agent and asdict(app.state.settings.schedule) == plan_at_start,
            permission_lock=app.state.conversation_lock)

    from .teilnehmer_nachtrag import Lauf as NachtragLauf
    nachtrag = getattr(app.state, "nachtrag", None)
    if nachtrag is None:
        nachtrag = app.state.nachtrag = NachtragLauf()

    def run_mail_intake():
        from .mail_intake import Intake
        from . import mail_filter
        store = Intake(app.state.episodes)
        for account_id in store.accounts():
            if account_id not in app.state.settings.schedule.mail_accounts:
                continue
            try:
                reader = app.state.mail.reader_for(account_id)
                if hasattr(reader, 'ocr'):
                    # Gescannte Anhänge nur mit einem lokalen OCR-Modell (`anhaenge.ocr_fuer`), nie über die Cloud.
                    from .anhaenge import ocr_fuer
                    reader.ocr = ocr_fuer(app)
                with app.state.conversation_lock:
                    selected_filter = mail_filter.policy(app.state.settings)
                    selected_settings = SimpleNamespace(mail_filter=selected_filter)
                    screening_agent = app.state.agent
                    screening_with_model = app.state.settings.schedule.with_model
                def allowed():
                    current = app.state.settings.schedule
                    return (current.enabled and account_id in current.mail_accounts
                            and any(e.id == account_id and e.configured for e in app.state.settings.mail_accounts)
                            and app.state.mail.reader_for(account_id) is reader
                            and app.state.agent is screening_agent
                            and current.with_model == screening_with_model
                            and mail_filter.policy(app.state.settings) == selected_filter
                            and app.state.local_model_automation_generation == generation)
                screening_provider = (mail_filter.screening_provider(app, permitted=allowed)
                    if selected_filter['ai_enabled'] else None)
                ids = store.background_step(account_id, reader, selected_settings, permitted=allowed,
                    permission_lock=app.state.conversation_lock, claims=app.state.claims, provider=screening_provider,
                    hold=lambda message, decision, folder: mail_filter.hold(app, message, decision,
                        lambda: config.save(_data_dir(), app.state.settings), folder=folder))
                if ids:
                    for episode_id in ids:
                        scheduler.request_working_memory(episode_id)
                # Nachrangig: Empfänger für ältere Mails nachtragen, gedrosselt und mit derselben Freigabe.
                nachtrag.schritt(app.state.episodes, reader, account_id,
                                 permitted=lambda: store.aktiv(account_id, allowed),
                                 permission_lock=app.state.conversation_lock,
                                 mit_modell=bool(app.state.settings.schedule.with_model))
            except Exception:
                pass  # Per-account safe error states are persisted by intake; der Nachtrag ist wiederholbar.

    scheduler._run_mail_intake = run_mail_intake
    scheduler._run_working_memory = run_working_memory
    scheduler._run_lage = run_lage  # noqa: SLF001
    scheduler._run_prompt_working_memory = lambda ids: run_working_memory(True, prompt=True, source_ids=ids)
    scheduler._runtime_boundary = app.state.runtime_boundary
    scheduler._run_task_detection = run_task_detection  # noqa: SLF001
    def run_priority_tasks():
        # Keine wiederholte Modellarbeit ohne vorgemerkte neue/korrigierte Quelle.
        if not app.state.episodes.task_rechecks(limit=1):
            return JobResult('zusagen', True)
        return run_task_detection(True, limit=2, rechecks_only=True)
    scheduler._run_priority_tasks = run_priority_tasks  # noqa: SLF001

    scheduler._run_ingest = run_sources  # noqa: SLF001
    bound_agent = app.state.agent
    plan_at_wire = asdict(plan)
    scheduled_model = scheduled_provider(rollen_von(app).provider("hintergrund"),
                                         agent=bound_agent, plan_at_start=plan_at_wire)
    consolidation = (Consolidator(app.state.store, app.state.episodes, app.state.proposals, provider=scheduled_model)
                     if scheduled_model is not getattr(app.state.consolidator, "_provider", None)
                     else app.state.consolidator)
    summarizer = (Summarizer(app.state.episodes, provider=scheduled_model)
                  if scheduled_model is not getattr(app.state.summarizer, "_provider", None)
                  else app.state.summarizer)
    scheduler._run_consolidation = consolidation_job(consolidation)  # noqa: SLF001
    scheduler._run_summary = summary_job(summarizer)  # noqa: SLF001
    scheduler._run_backup = backup_job(_data_dir()) if plan.backup else None  # noqa: SLF001
    hinten = rollen_von(app).provider("hintergrund")
    scheduler.configure(
        enabled=plan.enabled,
        interval_minutes=plan.interval_minutes,
        # Vorgemerktes Sortieren (Fremdprobe 3, Befund 3) wartet, bis ein lokales Modell mit Namen da ist.
        with_model=bool(plan.with_model and (
            not plan.local_model_only
            or (getattr(hinten, "is_local", False) and str(getattr(hinten, "model", "") or "").strip())
        )),
    )
    # Die tägliche Fassungsprüfung läuft im selben Faden, auch wenn der Zeitplan selbst aus ist (fassung_routes.py).
    from .fassung_routes import zeitplan_anschliessen
    if zeitplan_anschliessen(app, scheduler, _data_dir) or plan.enabled:
        scheduler.start()


def _close_persistent_state(app: FastAPI) -> None:
    """Schließt alle offenen SQLite-Verbindungen vor einer Wiederherstellung."""
    cloud_jobs = getattr(app.state, "cloud_memory_jobs", None)
    if cloud_jobs is not None:
        cloud_jobs.pause(revoke=True)
        app.state.cloud_memory_jobs = None
    for name in (
        "semantic_search", "backend", "audit", "tasks", "workspace", "episodes", "proposals",
        "conversations", "claims", "regeln", "zuordnungen", "rueckmeldungen", "logbuch", "lint_befunde",
    ):
        close = getattr(getattr(app.state, name, None), "close", None)
        if callable(close):
            close()


def _reopen_persistent_state(app: FastAPI) -> None:
    """Verdrahtet nach einem vollständigen Restore jeden Store neu.

    SQLite-Verbindungen zeigen nach `os.replace` auf die alte Datei. Ein
    partieller Neubau wäre noch gefährlicher als keiner: etwa Gespräche kämen
    aus dem wiederhergestellten Bestand, während Aufgaben weiter im alten
    geöffneten Handle lebten. Daher gibt es nach einem vollständigen Restore
    nur einen vollständig neuen Satz von lokalen Stores.
    """
    data_dir = _data_dir()
    from .restore_boundary import pending
    if pending(data_dir):
        return
    previous_backend = getattr(app.state, "backend", None)
    subject_id = getattr(getattr(app.state, "store", None), "_subject_id", "local")
    backend = (
        CogneeBackend(data_dir / "self-model.sqlite3")
        if isinstance(previous_backend, CogneeBackend)
        else SqliteBackend(data_dir / "self-model.sqlite3")
    )
    app.state.backend = backend
    app.state.store = SelfModelStore(backend, subject_id=subject_id)
    app.state.audit = AuditLog(data_dir / "audit.sqlite3")
    app.state.tasks = TaskStore(data_dir / "tasks.sqlite3")
    app.state.workspace = WorkspaceStore(data_dir / "workspace.sqlite3")
    app.state.episodes = EpisodeStore(data_dir / "episodes.sqlite3")
    if getattr(app.state, "settings", None) is not None:
        from . import suchindex_routes
        suchindex_routes.anwenden(app)
    app.state.proposals = ProposalStore(data_dir / "proposals.sqlite3")
    app.state.conversations = ConversationStore(data_dir / "conversations.sqlite3")
    app.state.claims = ClaimStore(data_dir / "knowledge.sqlite3")
    from .akten_routes import verbinden as verbinde_akten
    verbinde_akten(app)
    app.state.support_review = SupportReview(app.state.store, app.state.proposals, app.state.episodes, app.state.audit)
    app.state.regeln = RegelStore(data_dir / "regeln.sqlite3")
    if getattr(app.state, "zuordnungen", None) is not None:
        from .transkript_zuordnung import Zuordnungen
        app.state.zuordnungen = Zuordnungen(data_dir / "gespraeche.sqlite3")
    if getattr(app.state, "rueckmeldungen", None) is not None:
        from .rueckmeldung import Rueckmeldungen
        app.state.rueckmeldungen = Rueckmeldungen(data_dir / "rueckmeldungen.sqlite3")
    if getattr(app.state, "logbuch", None) is not None:
        from .logbuch_routes import verbinden as verbinde_logbuch
        verbinde_logbuch(app, lambda: data_dir)
    if getattr(app.state, "lint_befunde", None) is not None:
        from .lint import Befunde
        app.state.lint_befunde = Befunde(data_dir / "lint.sqlite3")
    app.state.knowledge_service = KnowledgeService(
        proposals=app.state.proposals,
        claims=app.state.claims,
        episodes=app.state.episodes,
    )

    # Ein selbst erzeugter Agent darf die wiederhergestellten Einstellungen
    # samt verschlüsseltem Datei-Schlüsselspeicher sofort übernehmen. Explizit
    # beim Start gesetzte Umgebungswerte bleiben dabei weiterhin vorrangig.
    if getattr(app.state, "owns_agent", False):
        for name in getattr(app.state, "loaded_secrets", []):
            os.environ.pop(name, None)
        app.state.loaded_secrets = load_into_env(app.state.keychain)
        for name in getattr(app.state, "env_from_settings", []):
            os.environ.pop(name, None)
        app.state.settings = config.load(data_dir)
        app.state.env_from_settings = config.apply_to_env(app.state.settings)
        _build_agent(app)
    else:
        agent = app.state.agent
        verdrahte_speicher(app, agent)
        verdrahte_zusaetze(app, agent)
        agent.reset()
        if getattr(app.state, "semantic_search", None) is not None:
            working_memory_semantic_runtime.bind(app, agent)
        baue_hintergrund(app)


def create_app(
    store: SelfModelStore | None = None,
    agent: Agent | None = None,
    audit: AuditLog | None = None,
    tasks: TaskStore | None = None,
    workspace: WorkspaceStore | None = None,
    episodes: EpisodeStore | None = None,
    proposals: ProposalStore | None = None,
    conversations: ConversationStore | None = None,
    knowledge: ClaimStore | None = None,
) -> FastAPI:
    from .restore_boundary import RuntimeBoundary, RecoveryBoundaryMiddleware, pending
    from .restore_inspection import create_inspection_app
    if os.environ.get('ICARUS_RESTORE_INSPECTION') == '1' and not pending(_data_dir()):
        from .restore_boundary import mark_pending
        mark_pending(_data_dir(), 'forced_inspection_launcher')
    inspection = create_inspection_app(_data_dir())
    if pending(_data_dir()):
        return inspection
    # Vor dem ersten Öffnen: steht ein Umbau an, erst eine Kopie von vorher.
    backup_before_update(_data_dir())
    app = FastAPI(title="Kingfisher", version="0.1.0")
    app.state.runtime_boundary = RuntimeBoundary(_data_dir())
    app.add_middleware(RecoveryBoundaryMiddleware, boundary=app.state.runtime_boundary, inspection=inspection)
    from .mac_calendar import MacCalendar, install_routes
    app.state.mac_calendar = MacCalendar(_data_dir() / "mac-calendar.sqlite3")
    app.state.owns_agent = agent is None

    if isinstance(agent, Agent):
        if store is not None and store is not agent._store:
            raise ValueError('Agent und Anwendung benötigen dasselbe Selbstmodell.')
        store = agent._store
        if agent._knowledge is not None:
            if knowledge is not None and knowledge is not agent._knowledge:
                raise ValueError('Agent und Anwendung benötigen denselben Wissensspeicher.')
            knowledge = agent._knowledge
        if agent._episodes is not None:
            if episodes is not None and episodes is not agent._episodes:
                raise ValueError('Agent und Anwendung benötigen denselben Episodenspeicher.')
            episodes = agent._episodes
        if agent._support_resolver is not None:
            if episodes is not None and episodes is not agent._support_resolver.episodes:
                raise ValueError('Agent und Belegauflösung benötigen denselben Episodenspeicher.')
            episodes = agent._support_resolver.episodes
            if proposals is not None and proposals is not agent._support_resolver.proposals:
                raise ValueError('Agent und Anwendung benötigen denselben Vorschlagsspeicher.')
            proposals = agent._support_resolver.proposals
    if store is None:
        backend = CogneeBackend(_data_dir() / "self-model.sqlite3")
        store = SelfModelStore(backend, subject_id="local")
        app.state.backend = backend
    app.state.store = store

    if audit is None:
        audit = AuditLog(_data_dir() / "audit.sqlite3")
    app.state.audit = audit

    if tasks is None:
        tasks = TaskStore(_data_dir() / "tasks.sqlite3")
    app.state.tasks = tasks

    if workspace is None:
        workspace = WorkspaceStore(_data_dir() / "workspace.sqlite3")
    app.state.workspace = workspace

    if episodes is None:
        episodes = EpisodeStore(_data_dir() / "episodes.sqlite3")
    app.state.episodes = episodes

    if proposals is None:
        proposals = ProposalStore(_data_dir() / "proposals.sqlite3")
    app.state.proposals = proposals

    if conversations is None:
        conversations = ConversationStore(_data_dir() / "conversations.sqlite3")
    app.state.conversations = conversations
    app.state.conversation_lock = threading.Lock()
    app.state.mail_reply_execution = threading.local()

    if knowledge is None:
        knowledge = ClaimStore(_data_dir() / "knowledge.sqlite3")
    app.state.claims = knowledge
    app.state.knowledge_service = KnowledgeService(
        proposals=app.state.proposals,
        claims=knowledge,
        episodes=app.state.episodes,
    )

    app.state.regeln = RegelStore(_data_dir() / "regeln.sqlite3")

    if agent is None:
        # Schlüssel aus dem Schlüsselbund holen, bevor Anbieter und Konnektoren
        # gebaut werden — Zugangsdaten sollen nicht aus .env kommen müssen.
        app.state.keychain = Keychain()
        app.state.loaded_secrets = load_into_env(app.state.keychain)

        # Und dann die Einstellungen des Nutzers. Gesetzte Umgebungsvariablen
        # gewinnen, siehe config.apply_to_env.
        app.state.settings = config.load(_data_dir())
        # Merken, welche Namen *aus der Datei* kamen. Nur die dürfen beim
        # Speichern wieder verschwinden — siehe put_setup.
        app.state.env_from_settings = config.apply_to_env(app.state.settings)

        _build_agent(app)
    else:
        verdrahte_speicher(app, agent)
        verdrahte_zusaetze(app, agent)
        app.state.agent = agent
        baue_hintergrund(app)
        app.state.settings = getattr(app.state, "settings", config.Settings())
        if working_memory_semantic_runtime.enabled():
            working_memory_semantic_runtime.bind(app, agent)

    expected = os.environ.get(TOKEN_ENV)

    def angemeldet(
        x_icarus_token: str | None,
        kingfisher_session: str | None,
    ) -> bool:
        """Header für die Desktop-App, HttpOnly-Sitzung für den Browser.

        Die Browser-Sitzung wird ausschließlich beim Ausliefern der lokalen UI
        gesetzt. Sie ist SameSite-strict, für JavaScript nicht lesbar und gilt
        nur für `/api`; das Token bleibt damit aus URL, DOM und Startlogs.
        """
        if expected is None:
            return True
        return any(
            candidate is not None and secrets.compare_digest(candidate, expected)
            for candidate in (x_icarus_token, kingfisher_session)
        )

    def auth(
        x_icarus_token: Annotated[str | None, Header()] = None,
        kingfisher_session: Annotated[
            str | None, Cookie(alias=UI_SESSION_COOKIE)
        ] = None,
    ) -> None:
        # Ohne gesetztes Token läuft der Sidecar offen — nur für Tests und
        # lokale Entwicklung. Die Desktop-App sendet einen Header, der lokale
        # Browser bekommen eine kurzlebige, HttpOnly-Sitzung.
        if not angemeldet(x_icarus_token, kingfisher_session):
            raise HTTPException(status_code=401, detail="Ungültiges Token")

    guard = [Depends(auth)]

    def mcp_tuer() -> None:
        """Sperrt die Routen der MCP-Tür, solange der Schalter aus ist.

        403 statt 404: Der Aufrufer ist angemeldet, die Funktion ist gewollt
        abgeschaltet — die Meldung soll sagen, wie man sie einschaltet, statt
        so zu tun, als gäbe es die Route nicht. Das Token wird zuerst geprüft.
        """
        if not config.mcp_tuer_offen():
            raise HTTPException(status_code=403, detail=config.MCP_TUER_ZU_TEXT)

    tuer_guard = [*guard, Depends(mcp_tuer)]
    from .mail_intake_routes import register as register_mail_intake
    register_mail_intake(app, guard, _data_dir, _wire_scheduler)
    from .device_profile import load_device_profile, save_device_profile
    from .model_roles_routes import register as register_model_roles
    register_model_roles(app, guard, _data_dir, lambda: _build_agent(app))
    from .cloud_access_routes import register as register_cloud_access
    register_cloud_access(app, guard, _data_dir, lambda: _build_agent(app))
    from .chatgpt_routes import register as register_chatgpt
    register_chatgpt(app, guard, _data_dir)
    from .cloud_memory_routes import register as register_cloud_memory
    register_cloud_memory(app, guard, _data_dir, lambda model: app.state.chatgpt_oauth.provider(model))

    @app.get("/api/v1/device/profile", dependencies=guard)
    def device_profile():
        from .device_profile import mit_eigener_messung
        return mit_eigener_messung(load_device_profile(_data_dir()))

    @app.get("/api/v1/system", dependencies=guard)
    def system_angabe() -> dict[str, Any]:
        """Auf welchem System Kingfisher läuft (Mac-App, Docker im Browser, Linux …), für passende Sätze (Befund 18)."""
        from .laufumgebung import beschreiben
        return beschreiben(_data_dir())

    @app.post("/api/v1/device/profile", dependencies=guard)
    def report_device(body: dict):
        try:
            return save_device_profile(_data_dir(), body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    from .google_routes import install_routes as install_google_routes
    install_google_routes(app, guard, _data_dir, lambda: _build_agent(app))
    from .calendar_action_routes import install_routes as install_calendar_action_routes
    install_calendar_action_routes(app, guard, _data_dir, lambda: _build_agent(app))
    from .microsoft_routes import install_routes as install_microsoft_routes
    install_microsoft_routes(app, guard, _data_dir, lambda: _build_agent(app))
    from .memory_routes import install_routes as install_memory_routes
    install_memory_routes(app, guard)
    from .recovery_jobs import RecoveryJobs, install_routes as install_recovery_routes
    app.state.recovery_jobs = RecoveryJobs(_data_dir() / "recovery-status.sqlite3")
    install_recovery_routes(app, guard, app.state.recovery_jobs, expected)

    @app.post("/api/v1/recovery/herunterladen", dependencies=guard)
    def recovery_herunterladen(body: dict[str, Any]) -> Any:
        """Sicherung ohne Helfer (Befund 8): verschlüsselt, geprüft, als Download; auf dem Rechner bleibt nichts liegen."""
        from fastapi import Response
        from .backup import BackupError
        from .sicherung_download import dateiname, erstellen
        passwort = body.get("password") if isinstance(body, dict) else None
        if not isinstance(passwort, str) or not 16 <= len(passwort) <= 256:
            return JSONResponse({"detail": "Bitte ein Sicherungspasswort mit 16 bis 256 Zeichen wählen."}, status_code=422)
        try:
            with app.state.conversation_lock:  # ein ruhiger Moment: keine Antwort schreibt gerade mitten hinein
                archiv = erstellen(_data_dir(), passwort)
        except BackupError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        except (OSError, ValueError):
            return JSONResponse({"detail": "Die Sicherung ließ sich gerade nicht erstellen. Bitte versuche es noch einmal."},
                                status_code=500)
        return Response(content=archiv, media_type="application/octet-stream", headers={
            "Content-Disposition": f'attachment; filename="{dateiname()}"', "Cache-Control": "no-store"})

    from .calendar_memory import KalenderGedaechtnis
    from .calendar_memory_routes import install_routes as install_calendar_memory_routes
    app.state.calendar_memory = KalenderGedaechtnis(app.state.episodes, app.state.claims,
                                                    lock=app.state.conversation_lock)
    install_routes(app, guard, app.state.mac_calendar, lambda: _build_agent(app), app.state.calendar_memory)
    install_calendar_memory_routes(app, guard)
    from .akten_routes import register as register_akten
    register_akten(app, guard)
    from .akten_export_routes import register as register_akten_export
    register_akten_export(app, guard, _data_dir)
    from .tag_routes import register as register_tag
    from .wegezeit_routes import register as register_wegezeit
    register_wegezeit(app, guard, _data_dir)
    from .wetter_routes import register as register_wetter
    from .welt_briefing_routes import register as register_welt_briefing
    register_wetter(app, guard, _data_dir)
    register_welt_briefing(app, guard, _data_dir)
    from .einrichtung_routes import register as register_einrichtung
    register_einrichtung(app, guard, _data_dir)
    from .hintergrund import einbauen as hintergrund_einbauen
    hintergrund_einbauen(app, guard, _data_dir)
    from . import suchindex_routes
    suchindex_routes.anwenden(app)
    suchindex_routes.register(app, guard, _data_dir)
    register_tag(app, guard)

    def health_authenticated(
        token: str | None,
        kingfisher_session: str | None,
    ) -> bool:
        """Ob ein Aufrufer sich ausgewiesen hat — ohne abzuweisen.

        Gebraucht von `/health`: Der Endpunkt muss offen bleiben, weil
        `make start` und der Healthcheck des Containers darauf warten, dass der
        Sidecar antwortet. Er darf aber nicht jedem alles sagen.
        """
        return angemeldet(token, kingfisher_session)

    def configured_provider_name(provider: Any) -> str | None:
        """Nennt die gewählte Produktintegration, nicht ihr HTTP-Protokoll.

        Ollama und andere kompatible Dienste benutzen intern denselben
        OpenAI-kompatiblen Adapter. Dessen Klassenname ist kein sinnvoller
        Einrichtungsstatus: Wer Ollama gewählt hat, muss dort auch Ollama
        sehen. Eine beim Start gesetzte Umgebung bleibt wie überall sonst
        vorrangig.
        """
        selected = os.environ.get("ICARUS_PROVIDER", "").strip().lower()
        if selected:
            return selected
        settings = getattr(app.state, "settings", None)
        configured = getattr(settings, "provider", "") if settings is not None else ""
        return configured or getattr(provider, "name", None)

    @app.get("/health")
    def health(
        x_icarus_token: Annotated[str | None, Header()] = None,
        kingfisher_session: Annotated[
            str | None, Cookie(alias=UI_SESSION_COOKIE)
        ] = None,
    ) -> dict[str, Any]:
        """Lebenszeichen für alle, Auskunft nur für Angemeldete.

        Ohne Token stand hier bis eben der ganze Zustand: die **absoluten Pfade
        der freigegebenen Ordner**, der eingerichtete Anbieter, ob Mail und
        Kalender stehen. Jeder Prozess auf demselben Rechner konnte das lesen —
        und genau der ist laut Bedrohungsmodell dieses Projekts der relevante
        Angreifer. Ordnernamen verraten dabei mehr als sie sollten; ein Pfad wie
        `/Users/…/Praxis/Patienten` ist für sich schon eine Auskunft.

        Offen bleiben muss der Endpunkt trotzdem: `make start` und der
        Healthcheck des Containers warten darauf, dass er antwortet, und beide
        haben an dieser Stelle kein Token zur Hand. Ein Lebenszeichen ist alles,
        was sie brauchen.
        """
        if not health_authenticated(x_icarus_token, kingfisher_session):
            return {"status": "ok"}

        backend = getattr(app.state, "backend", None)
        provider = app.state.agent.provider
        return {
            "status": "ok",
            "semantic_search": not getattr(backend, "degraded", False),
            "detail": getattr(backend, "degraded_reason", None),
            # Ohne Modell bleibt der Gedächtniskern voll nutzbar — die
            # Oberfläche sagt das, statt einen kaputten Chat anzubieten.
            "chat": provider is not None,
            "provider": configured_provider_name(provider),
            "model": getattr(provider, "model", None),
            # Sicherheitsrelevanter Zustand, damit die Oberfläche ihn zeigen
            # kann, statt dass der Nutzer ihn erraten muss.
            "keychain": getattr(getattr(app.state, "keychain", None), "backend", "none"),
            "file_roots": [str(p) for p in file_roots_from_env(os.environ.get(ROOTS_ENV))],
            "mail": getattr(app.state, "mail", None) is not None,
            "calendar": getattr(app.state, "calendar", None) is not None,
        }

    # -- Einrichtung -------------------------------------------------------
    #
    # Damit niemand eine .env anlegen muss, bevor er das Programm zum ersten
    # Mal öffnet. Geheimnisse gehen in den Schlüsselbund und kommen über diese
    # Schnittstelle nie zurück — nur die Auskunft, ob eines hinterlegt ist.

    def _system_angabe() -> dict[str, Any]:
        from .laufumgebung import beschreiben
        return beschreiben(_data_dir())

    def _setup_state() -> dict[str, Any]:
        settings: config.Settings = app.state.settings
        keychain = getattr(app.state, "keychain", None) or Keychain()
        provider = app.state.agent.provider
        backend = getattr(app.state, "backend", None)
        return {
            "settings": settings.to_dict(),
            "secrets": config.secret_status(keychain),
            "keychain": keychain.backend,
            # Ohne Schlüsselspeicher gilt ein eingetragener Schlüssel nur für
            # diese Sitzung. Das muss die Oberfläche sagen dürfen.
            "keychain_available": keychain.available,
            "providers": [p for p in config.PROVIDERS],
            # Die Beschriftungen kommen mit. Sie standen bisher zusätzlich im
            # Client — und zwei Listen laufen früher oder später auseinander.
            "provider_labels": config.PROVIDER_LABELS,
            "provider_braucht_adresse": list(config.PROVIDER_BRAUCHT_ADRESSE),
            "bekannte_adressen": config.BEKANNTE_ADRESSEN,
            "default_models": config.DEFAULT_MODELS,
            "adapters": sorted(ADAPTERS),
            # Damit niemand einen IMAP-Hostnamen kennen muss. Siehe
            # providers_mail.py und CLAUDE.md, Grundsatz 1.
            "mail_providers": mail_catalogue(),
            # Auf welchem System Kingfisher läuft; die Oberfläche wählt danach „Mac“ oder „Rechner“ (laufumgebung.py).
            "system": _system_angabe(),
            "status": {
                "chat": provider is not None,
                "provider": configured_provider_name(provider),
                "model": getattr(provider, "model", None),
                # Tatsächlich aktives Ziel; Startvariablen können den
                # gespeicherten Endpunkt übersteuern. Nur in der geschützten
                # Einrichtung ausgeben, nicht im öffentlichen Healthcheck.
                "endpoint": getattr(provider, "base_url", None),
                "mail": getattr(app.state, "mail", None) is not None,
                "calendar": getattr(app.state, "calendar", None) is not None,
                # Was **tatsächlich** gilt, nicht was in der Datei steht.
                # Eine gesetzte Umgebungsvariable gewinnt (siehe
                # config.apply_to_env), und die Oberfläche muss den geltenden
                # Stand zeigen — sonst sagt sie „kein Ordner freigegeben“,
                # während einer freigegeben ist.
                "file_roots": [
                    str(p) for p in file_roots_from_env(os.environ.get(ROOTS_ENV))
                ],
                # Welche davon vom Startbefehl kommen und nicht aus den
                # Einstellungen. Sie lassen sich hier nicht entfernen — die
                # Umgebung gewinnt —, und ein Knopf, der nichts bewirkt, ist
                # schlimmer als keiner.
                "file_roots_vom_start": [
                    str(p)
                    for p in file_roots_from_env(os.environ.get(ROOTS_ENV))
                    if str(p) not in set(settings.file_roots)
                ],
                "semantic_search": not getattr(backend, "degraded", False),
                # Die eine Aussage zur lokalen KI (lokale_ki.py, Fremdprobe Befund 9). Karten und Formulare zeigen
                # diesen Satz, statt aus Anbietername, fester Adresse und Modellliste je eigene Schlüsse zu ziehen.
                "lokale_ki": _lokale_ki_stand(),
            },
        }

    def _lokale_ki_stand() -> dict[str, Any] | None:
        from .lokale_ki import stand as lokale_ki_stand
        try:
            return lokale_ki_stand(app)
        except Exception:  # noqa: BLE001 - die Auskunft ist Beiwerk; die Einrichtung darf nie daran scheitern
            logger.exception("Stand der lokalen KI nicht bestimmbar")
            return None

    @app.get("/api/v1/setup", dependencies=guard)
    @app.get("/setup", dependencies=guard)
    def get_setup() -> dict[str, Any]:
        return _setup_state()

    def microsoft_zugang(adresse: str) -> bool:
        from .microsoft_routes import zugang_da
        return zugang_da(app, adresse)

    def integration_overview() -> dict[str, list[dict[str, Any]]]:
        """Zeigt Konfiguration und Geheimnis-Status, aber niemals Geheimnisse."""
        settings: config.Settings = app.state.settings
        mail = []
        for entry in settings.mail_accounts:
            mail.append({
                "id": entry.id,
                "label": entry.label,
                "user": entry.user,
                "enabled": entry.enabled,
                "configured": entry.configured,
                "secret_present": bool(_integration_secret(app, "mail", entry.id)) or (
                    entry.auth_method == "microsoft_graph" and microsoft_zugang(entry.user)),
                "can_send": bool(entry.smtp_host),
                **({"auth": "microsoft"} if entry.auth_method == "microsoft_graph" else {}),
            })
        calendars = []
        for entry in settings.calendar_sources:
            calendars.append({
                "id": entry.id,
                "label": entry.label,
                "kind": entry.kind,
                "enabled": entry.enabled,
                "configured": entry.configured,
                # Bei einem Abo heißt das: Die geheime Adresse liegt im Schlüsselbund (ältere Abos: False); bei
                # Microsoft: Der Zugang des Kontos liegt im Schlüsselspeicher.
                "secret_present": (
                    microsoft_zugang(entry.user) if entry.kind == "microsoft"
                    else bool(_integration_secret(app, "calendar", entry.id))
                ),
            })
        return {"mail_accounts": mail, "calendar_sources": calendars}

    @app.get("/api/v1/integrations", dependencies=guard)
    def list_integrations() -> dict[str, list[dict[str, Any]]]:
        """Listet mehrere lokale Quellen ohne Passwörter oder URLs."""
        return integration_overview()

    @app.get("/api/v1/integrations/mail-providers", dependencies=guard)
    def list_mail_providers() -> dict[str, list[dict[str, Any]]]:
        """Liefert lokale Eingabehilfen, nie Zugänge oder Kontodaten."""
        return {"providers": mail_catalogue()}

    @app.get("/api/v1/integrations/mail-providers/erkennen", dependencies=guard)
    def erkenne_mail_anbieter(adresse: Annotated[str, Query(min_length=3, max_length=320)]) -> dict[str, Any]:
        """Die eine Anbieter-Erkennung (`anbieter_erkennen.py`): bekannter Anbieter, Google Workspace, Microsoft 365.

        `{"provider": {…} | null, "erkannt_an": "domain" | "mx" | "autodiscover" | "txt" | "",
        "dienst": "google" | "microsoft" | "", "art": "organisation" | "privat" | ""}`. Gefragt wird nur nach der
        Domain, nur beim Namensdienst des Rechners; Google und Microsoft erfahren davon nichts. Für eine eigene Domain
        sucht `server_finden.py` den Server selbst (SRV, Autoconfig beim Server der Domain, MX gegen den Katalog);
        dann ist `provider.id` `gefunden` (Fremdprobe 2, Befund 2).
        """
        from .anbieter_erkennen import erkennen
        return erkennen(adresse.strip(), transport=getattr(app.state, "autoconfig_transport", None)).to_dict()

    @app.post("/api/v1/integrations/mail", dependencies=guard, status_code=201)
    def add_mail_account(body: MailAccountIn) -> Any:
        """Fügt ein Mailkonto hinzu, ohne es abzurufen. Mit Passwort wird vorher einmal angemeldet."""
        settings: config.Settings = app.state.settings
        if body.password:
            # Erst anmelden, dann speichern: Ein Konto, das sich nicht anmelden lässt, ist nicht „verbunden“
            # (Fremdprobe, Befund 3). Der Grund kommt als ein Satz zurück; gespeichert wird dann nichts.
            from . import mail_anmeldung
            probe = MailConnector(MailConfig(imap_host=body.imap_host, imap_port=body.imap_port,
                                             username=body.user, password=body.password))
            try:
                # Ohne `name`: Die Ablehnung nennt den Anbieter oder Server, nie den selbst vergebenen Namen (Befund 4).
                mail_anmeldung.pruefe(probe, body.imap_host)
            except mail_anmeldung.Anmeldefehler as exc:
                # `grund` dazu, damit die Oberfläche etwa „App-Passwort nötig“ (Google, Befund 2) erkennen kann.
                return JSONResponse({"detail": exc.satz, "grund": exc.grund}, status_code=exc.status)
        account_id = f"mail-{uuid.uuid4().hex}"
        entry = config.MailAccountSettings(
            id=account_id,
            label=body.label,
            imap_host=body.imap_host,
            imap_port=body.imap_port,
            smtp_host=body.smtp_host,
            smtp_port=body.smtp_port,
            user=body.user,
            sender=body.sender,
        )
        if body.password:
            config.store_secret(
                getattr(app.state, "keychain", Keychain()),
                config.integration_secret_name("mail", account_id), body.password,
            )
        settings.mail_accounts.append(entry)
        config.save(_data_dir(), settings)
        _build_agent(app)
        return integration_overview()

    @app.post("/api/v1/integrations/calendar", dependencies=guard, status_code=201)
    def add_calendar_source(body: CalendarSourceIn) -> dict[str, Any]:
        """Fügt einen CalDAV-Kalender oder ein HTTPS-iCalendar-Abo hinzu."""
        if body.kind == "ical" and not body.url.startswith("https://"):
            raise HTTPException(
                status_code=400,
                detail="iCalendar-Abonnements benötigen eine HTTPS-Adresse.",
            )
        if body.kind == "caldav" and not body.user:
            raise HTTPException(status_code=400, detail="CalDAV benötigt einen Benutzernamen.")
        if body.kind == "caldav" and body.password:
            # Erst anmelden, dann speichern, wie beim Postfach (Befunde 3 und 7); sonst ein Satz mit Grund.
            from . import kalender_anmeldung
            from .mail_anmeldung import Anmeldefehler
            try:
                kalender_anmeldung.finde_kalender(body.url, body.user, body.password, wer=body.label,
                                                  transport=getattr(app.state, "caldav_transport", None))
            except Anmeldefehler as exc:
                return JSONResponse({"detail": exc.satz, "grund": exc.grund}, status_code=exc.status)
        source_id = f"calendar-{uuid.uuid4().hex}"
        entry = config.CalendarSourceSettings(
            id=source_id, label=body.label, kind=body.kind,
            url=body.url, user=body.user,
        )
        if body.kind == "caldav" and body.password:
            config.store_secret(
                getattr(app.state, "keychain", Keychain()),
                config.integration_secret_name("calendar", source_id), body.password,
            )
        settings: config.Settings = app.state.settings
        settings.calendar_sources.append(entry)
        config.save(_data_dir(), settings)
        _build_agent(app)
        return integration_overview()

    @app.post("/api/v1/integrations/calendar/anmelden", dependencies=guard, status_code=201)
    def kalender_anmelden(body: KalenderAnmeldungIn) -> Any:
        """Kalender wie Mail (Befund 7): Anbieter an der Adresse erkennen, Kalender selbst finden, vorher anmelden.

        Gespeichert wird erst, wenn die Anmeldung gelang und mindestens ein Kalender mit Terminen gefunden ist; jeder
        gefundene Kalender wird eine Quelle (nur lesen). Sonst kommt `{"detail": Satz, "grund": …}` zurück.
        """
        from . import kalender_anmeldung
        from .mail_anmeldung import Anmeldefehler
        from .providers_mail import guess
        settings: config.Settings = app.state.settings
        adresse = body.adresse.strip()
        passwort = body.password
        if not passwort and body.mail_konto:
            # Dasselbe Konto beim selben Anbieter: Das Passwort des Postfachs gilt auch für den Kalender. Nur für ein
            # Postfach mit genau dieser Adresse; das Passwort verlässt dabei den Rechner nur zum eigenen Anbieter.
            konto = next((e for e in settings.mail_accounts if e.id == body.mail_konto), None)
            if konto is not None and konto.user.strip().lower() == adresse.lower():
                passwort = _integration_secret(app, "mail", konto.id)
        if not passwort:
            return JSONResponse({"detail": "Bitte gib das Passwort für deinen Kalender ein.", "grund": "passwort_fehlt"},
                                status_code=422)
        # Für eine eigene Domain sucht Kingfisher den Kalender beim Mailserver des Postfachs (Fremdprobe 2, Befund 5):
        # dem verbundenen Postfach mit dieser Adresse, sonst dem Server, den es für die Domain selbst gefunden hat.
        mailserver = next((e.imap_host for e in settings.mail_accounts
                           if e.user.strip().lower() == adresse.lower() and e.imap_host), "")
        if not mailserver and guess(adresse) is None and not (body.url or "").strip():
            from . import server_finden
            fund = server_finden.finde(adresse.rpartition("@")[2],
                                       transport=getattr(app.state, "autoconfig_transport", None))
            mailserver = fund.imap_host if fund is not None else ""
        try:
            anbieter, start = kalender_anmeldung.startpunkt(adresse, body.url, mailserver=mailserver,
                                                            transport=getattr(app.state, "caldav_transport", None))
            wer = anbieter.label if anbieter is not None else (urlsplit(start).hostname or "Dein Kalenderdienst")
            gefunden = kalender_anmeldung.finde_kalender(
                start, adresse, passwort, wer=wer, app_passwort=bool(anbieter and anbieter.app_password),
                transport=getattr(app.state, "caldav_transport", None))
        except Anmeldefehler as exc:
            return JSONResponse({"detail": exc.satz, "grund": exc.grund}, status_code=exc.status)
        vorhanden = {(e.url, e.user.lower()) for e in settings.calendar_sources if e.kind == "caldav"}
        neu = []
        for kalender in gefunden:
            if (kalender.url, adresse.lower()) in vorhanden:
                continue
            source_id = f"calendar-{uuid.uuid4().hex}"
            config.store_secret(getattr(app.state, "keychain", Keychain()),
                                config.integration_secret_name("calendar", source_id), passwort)
            neu.append(config.CalendarSourceSettings(id=source_id, label=f"{wer}: {kalender.name}"[:120], kind="caldav",
                                                     url=kalender.url, user=adresse))
        settings.calendar_sources.extend(neu)
        config.save(_data_dir(), settings)
        _build_agent(app)
        return {**integration_overview(), "gefunden": [k.name for k in gefunden], "neu": len(neu), "anbieter": wer}

    @app.post("/api/v1/integrations/calendar/abo", dependencies=guard, status_code=201)
    def kalender_abo(body: KalenderAboIn) -> Any:
        """Ein Kalender über seine geheime iCal-Adresse, nur lesend (Fremdprobe, Befund 2: Google ohne Cloud-Projekt).

        Die Adresse wird vorher einmal abgerufen (Wanduhr 10 s, keine Weiterleitung, gültiges iCalendar); sonst kommt
        `{"detail": Satz, "grund": …}` zurück und nichts wird gespeichert. Die Adresse ist ein Schlüssel: Sie liegt im
        Schlüsselbund, in den Einstellungen steht bei Google nur `https://calendar.google.com/`.
        """
        from . import kalender_abo as abo
        from .mail_anmeldung import Anmeldefehler
        try:
            einordnung, gefunden = abo.pruefe(body.url, transport=getattr(app.state, "ical_transport", None))
        except Anmeldefehler as exc:
            return JSONResponse({"detail": exc.satz, "grund": exc.grund}, status_code=exc.status)
        settings: config.Settings = app.state.settings
        for entry in settings.calendar_sources:
            if entry.kind == "ical" and (_integration_secret(app, "calendar", entry.id) or entry.url) == einordnung.url:
                return {**integration_overview(), "gefunden": entry.label, "termine": gefunden.termine, "neu": 0}
        name = (body.label or "").strip() or (f"Google: {gefunden.name}" if einordnung.google and gefunden.name
                                              else gefunden.name or ("Google-Kalender" if einordnung.google
                                                                      else "Kalender-Abo"))
        source_id = f"calendar-{uuid.uuid4().hex}"
        config.store_secret(getattr(app.state, "keychain", Keychain()),
                            config.integration_secret_name("calendar", source_id), einordnung.url)
        anzeige = abo.GOOGLE_ANZEIGE if einordnung.google else f"https://{urlsplit(einordnung.url).hostname}/"
        settings.calendar_sources.append(config.CalendarSourceSettings(
            id=source_id, label=name[:120], kind="ical", url=anzeige))
        config.save(_data_dir(), settings)
        _build_agent(app)
        return {**integration_overview(), "gefunden": name[:120], "termine": gefunden.termine, "neu": 1}

    @app.delete("/api/v1/integrations/{kind}/{integration_id}", dependencies=guard)
    def remove_integration(kind: str, integration_id: str) -> dict[str, list[dict[str, Any]]]:
        """Entzieht einen einzelnen Zugang samt zugehörigem Geheimnis."""
        if kind not in {"mail", "calendar"}:
            raise HTTPException(status_code=404, detail="Unbekannte Integrationsart.")
        settings: config.Settings = app.state.settings
        field = "mail_accounts" if kind == "mail" else "calendar_sources"
        current = getattr(settings, field)
        remaining = [entry for entry in current if entry.id != integration_id]
        if len(remaining) == len(current):
            raise HTTPException(status_code=404, detail="Diese Integration gibt es nicht.")
        entfernt = next(entry for entry in current if entry.id == integration_id)
        with app.state.conversation_lock:
            setattr(settings, field, remaining)
        with app.state.google_oauth.lock:
            config.clear_secret(
                getattr(app.state, "keychain", Keychain()),
                config.integration_secret_name(kind, integration_id),
            )
        config.save(_data_dir(), settings)
        # Der letzte Zugang eines Microsoft-Kontos nimmt dessen Anmeldung mit (microsoft_routes.nach_entfernen).
        from .microsoft_routes import nach_entfernen
        nach_entfernen(app, entfernt)
        _build_agent(app)
        if kind == "calendar":
            # Getrennt heißt entzogen: Die Termine der Quelle verlassen das Gedächtnis.
            from .calendar_memory_routes import freigegeben
            app.state.calendar_memory.entziehen_ohne_freigabe(freigegeben(app))
        return integration_overview()

    @app.get("/setup/folder", dependencies=guard)
    def check_folder(path: str) -> dict[str, Any]:
        """Sieht nach, ob ein Ordner da ist und was darin liegt.

        Ein Pfad wird getippt, und getippte Pfade sind falsch. Heute merkt man
        das erst, wenn die Aufnahme scheitert — drei Bildschirme später, mit
        einer Fehlermeldung, die den Tippfehler nicht nennt.

        Deshalb: beim Hinzufügen prüfen. „1.243 Dateien gefunden“ bestätigt
        obendrein, dass es der *gemeinte* Ordner ist — ein Pfad, der existiert
        und leer ist, ist meistens der falsche.

        Bewusst **ohne** Freigabeprüfung: Hier wird noch nichts gelesen, nur
        gezählt. Das ist die Auskunft, die der Nutzer braucht, *bevor* er
        freigibt.
        """
        ziel = Path(path).expanduser()
        if not ziel.exists():
            return {"ok": False, "detail": "Diesen Ordner gibt es nicht."}
        if not ziel.is_dir():
            return {"ok": False, "detail": "Das ist eine Datei, kein Ordner."}
        try:
            dateien = sum(
                1 for f in ziel.rglob("*")
                if f.is_file() and f.suffix.lower() in TEXT_SUFFIXES
            )
        except PermissionError:
            return {"ok": False, "detail": "Auf diesen Ordner fehlt der Zugriff."}
        return {
            "ok": True,
            "path": str(ziel),
            "files": dateien,
            "detail": (
                f"{dateien} lesbare Datei{'' if dateien == 1 else 'en'} gefunden."
                if dateien else
                "Der Ordner ist da, enthält aber keine lesbaren Textdateien."
            ),
        }

    @app.get("/setup/mail-provider", dependencies=guard)
    def mail_provider_for(address: str) -> dict[str, Any]:
        """Rät den Anbieter aus der Mailadresse.

        Damit ist der Regelfall **ein** Feld: Adresse eintippen, und Hosts,
        Ports und der Hinweis auf ein nötiges App-Passwort stehen schon da. Wer
        eine eigene Domain hat, bekommt `null` — das ist genau die Gruppe, die
        einen IMAP-Host auch selbst einträgt.
        """
        treffer = guess_mail_provider(address)
        return {"provider": treffer.to_dict() if treffer else None}

    @app.get("/api/v1/setup/models", dependencies=guard)
    @app.get("/setup/models", dependencies=guard)
    def modelle(anbieter: str = "", adresse: str = "") -> dict[str, Any]:
        """Welche Modelle der eingerichtete Anbieter kennt.

        Zeigen statt tippen: Wer den genauen Namen eines Modells nicht
        auswendig kann — und das kann fast niemand — soll ihn nicht raten
        müssen. Anthropic hat keinen solchen Weg; dort bleibt es ein Tippfeld,
        und die Antwort sagt das auch.
        """
        anbieter = (anbieter or os.environ.get("ICARUS_PROVIDER", "")).strip().lower()

        if anbieter == "anthropic":
            return {
                "modelle": [],
                "detail": "Anthropic führt keine Liste. Modellnamen von Hand eintragen.",
            }

        ziel = (adresse or os.environ.get("ICARUS_BASE_URL", "")).strip()
        if not ziel:
            ziel = {
                "openai": "https://api.openai.com/v1",
                "ollama": "http://localhost:11434/v1",
            }.get(anbieter, "")
        if not ziel:
            return {"modelle": [], "detail": "Keine Adresse — erst Anbieter wählen."}

        # Gegen den Endpunkt, nicht gegen eine gepflegte Liste im Code: eine
        # solche Liste ist am Tag ihrer Veröffentlichung veraltet.
        namen = providers.verfuegbare_modelle(
            ziel, os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        )
        if not namen:
            return {
                "modelle": [],
                "detail": f"{ziel} hat keine Liste geliefert. Namen von Hand eintragen.",
            }
        return {"modelle": namen, "detail": f"{len(namen)} Modelle gefunden."}

    @app.put("/api/v1/setup", dependencies=guard)
    @app.put("/setup", dependencies=guard)
    def put_setup(body: SetupIn) -> dict[str, Any]:
        """Übernimmt Einstellungen und baut den Agenten neu.

        Nur gesetzte Felder werden angefasst. Ein `null` heißt „nicht ändern",
        ein leerer String heißt „leeren" — sonst könnte man einen einmal
        eingetragenen Mailserver nie wieder loswerden.
        """
        settings: config.Settings = app.state.settings
        keychain = getattr(app.state, "keychain", None) or Keychain()
        if any(value is not None for value in (body.model, body.provider, body.endpoint)):
            from .model_recommendation import geraet_aus_profil, model_memory_gb, gb_text
            proposed = replace(settings)
            if body.provider is not None:
                proposed.provider = body.provider
                if body.model is None and body.provider:
                    proposed.model = config.DEFAULT_MODELS.get(body.provider, "")
            if body.model is not None:
                proposed.model = body.model
            if body.endpoint is not None:
                proposed.endpoint = body.endpoint
            # Mirror the post-save environment without changing settings or the
            # process: external overrides win, old file-derived values do not.
            derived = set(getattr(app.state, "env_from_settings", []))
            effective = {key: value for key, value in os.environ.items() if key not in derived}
            config.apply_to_env(proposed, effective)
            target_provider = effective.get("ICARUS_PROVIDER", "").strip().lower()
            target_model = effective.get("ICARUS_MODEL", "").strip()
            endpoint = effective.get("ICARUS_BASE_URL", "http://localhost:11434/v1" if target_provider == "ollama" else "")
            trusted_hosts = effective.get("ICARUS_TRUSTED_LOCAL_MODEL_HOSTS", "").split(",")
            is_local = target_provider in {"ollama", "kompatibel", "openai"} and providers.is_local_endpoint(endpoint, trusted_hosts)
            known = model_memory_gb(target_model) if is_local else None
            budget = geraet_aus_profil(device_profile()).modellbudget_gb
            if known is not None and budget is not None and known > budget:
                raise HTTPException(422, f"{target_model} braucht etwa {gb_text(known)} GB Arbeitsspeicher; "
                                         f"für Modelle sind rund {gb_text(budget)} GB eingeplant. "
                                         "Bitte ein kleineres Modell wählen, damit andere Programme nutzbar bleiben.")

        if body.provider is not None:
            if body.provider not in config.PROVIDERS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unbekannter Anbieter: {body.provider!r}",
                )
            settings.provider = body.provider
            # Modell mitziehen, wenn der Nutzer keins nennt: Ein Anbieter ohne
            # Modell führt zu einer Fehlermeldung beim ersten Satz, und der
            # Nutzer weiß nicht, warum.
            if body.model is None and body.provider:
                settings.model = config.DEFAULT_MODELS.get(body.provider, "")
        if body.model is not None:
            settings.model = body.model
        if body.endpoint is not None:
            settings.endpoint = body.endpoint
        if body.file_roots is not None:
            settings.file_roots = [p for p in body.file_roots if p.strip()]

        if body.mail is not None:
            settings.mail = config.MailSettings(
                imap_host=body.mail.imap_host,
                imap_port=body.mail.imap_port,
                # Ein Mailkonto ohne SMTP kann lesen und nicht senden. Den
                # IMAP-Host als Vorgabe zu übernehmen wäre geraten und falsch.
                smtp_host=body.mail.smtp_host,
                smtp_port=body.mail.smtp_port,
                user=body.mail.user,
                sender=body.mail.sender,
            )
        if body.calendar is not None:
            settings.calendar = config.CalendarSettings(
                url=body.calendar.url, user=body.calendar.user
            )
        if body.onboarded is not None:
            settings.onboarded = body.onboarded

        # Geheimnisse: leerer String löscht, None lässt unangetastet.
        secret_targets = {
            "api_key": config.secret_name_for_provider(settings.provider),
            "mail_password": config.SECRET_FIELDS["mail_password"],
            "calendar_password": config.SECRET_FIELDS["calendar_password"],
        }
        for feld, name in secret_targets.items():
            value = getattr(body, feld)
            if value is None or name is None:
                continue
            if value:
                config.store_secret(keychain, name, value)
            else:
                config.clear_secret(keychain, name)

        config.save(_data_dir(), settings)

        # Die Umgebung neu setzen. **Nur** die Namen, die beim Start aus der
        # Datei kamen — sonst gewinnt für immer die erste Einstellung.
        #
        # Nicht alle: Wer `ICARUS_IMAP_HOST=…` vor den Start setzt, hat damit
        # ausdrücklich etwas anderes gemeint als das, was in der Datei steht.
        # Diese Werte hier mit wegzuräumen hieß, dass sein Posteingang beim
        # ersten Speichern verschwindet — und zwar still. Genau das ist beim
        # Prüfen passiert: Der Einrichtungsassistent hat beim Überspringen den
        # per Umgebung eingerichteten Mailzugang gelöscht.
        for name in getattr(app.state, "env_from_settings", []):
            os.environ.pop(name, None)
        app.state.env_from_settings = config.apply_to_env(settings)
        _build_agent(app)

        return _setup_state()

    @app.post("/api/v1/setup/test/{ziel}", dependencies=guard)
    @app.post("/setup/test/{ziel}", dependencies=guard)
    def test_setup(ziel: str) -> dict[str, Any]:
        """Probiert eine Verbindung wirklich aus, statt sie zu behaupten.

        Ein Einrichtungsassistent, der „gespeichert" sagt und beim ersten
        echten Gebrauch scheitert, ist schlimmer als keiner — dann sucht der
        Nutzer den Fehler an der falschen Stelle.
        """
        try:
            if ziel == "modell":
                provider = app.state.agent.provider
                if provider is None:
                    return {"ok": False, "detail": "Kein Anbieter eingerichtet."}
                reply = provider.complete(
                    [{"role": "user", "content": "Antworte mit dem Wort: bereit"}], []
                )
                # Nicht `provider.name` — der heißt bei jedem OpenAI-kompatiblen
                # Dienst „openai“, und wer OpenRouter eingerichtet hat, liest
                # dann „openai antwortet“ und zweifelt zu Recht. Die Adresse
                # sagt die Wahrheit.
                wo = getattr(provider, "base_url", "") or provider.name
                host = wo.split("//")[-1].split("/")[0] if "//" in wo else wo
                return {
                    "ok": True,
                    "detail": f"{host} antwortet — Modell {provider.model}.",
                    "sample": reply.text[:200],
                }

            if ziel == "mail":
                mail = getattr(app.state, "mail", None)
                if mail is None:
                    return {"ok": False, "detail": "Kein Mailzugang eingerichtet."}
                messages = mail.inbox(limit=1)
                return {"ok": True, "detail": f"Posteingang erreichbar ({len(messages)} gelesen)."}

            if ziel == "kalender":
                calendar = getattr(app.state, "calendar", None)
                if calendar is None:
                    return {"ok": False, "detail": "Kein Kalender eingerichtet."}
                events = calendar.events(days=7)
                return {"ok": True, "detail": f"Kalender erreichbar ({len(events)} Termine)."}
        except Exception as exc:  # noqa: BLE001 - der echte Fehler ist die Antwort
            return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

        raise HTTPException(status_code=400, detail=f"Unbekanntes Ziel: {ziel}")

    # -- Assistent ---------------------------------------------------------

    @app.post("/chat", dependencies=guard)
    def chat(body: ChatIn) -> dict[str, Any]:
        return app.state.agent.send(body.message).to_dict()

    @app.get("/context", dependencies=tuer_guard)
    def context() -> dict[str, str]:
        """Was ein fremder Assistent über den Nutzer zu sehen bekommt — wörtlich.

        Nur für die MCP-Tür (`icarus_kontext`), deshalb hinter dem Schalter und
        immer mit der Grenze `NORMAL`: Die Schutzbedarfsgrenze des Hausmodells
        gilt für dieses Modell, nicht für einen Assistenten von außen. Die
        Oberfläche der App braucht diese Route nicht.
        """
        return {"context": app.state.agent.context(external_caller=True)}

    @app.post("/chat/reset", dependencies=guard, status_code=204)
    def reset() -> None:
        app.state.agent.reset()

    # -- Freigaben ---------------------------------------------------------

    def _cancel_bound_mail_reply(approval_id: str) -> Turn:
        """Consume a sourced mail approval without reading revoked content."""
        try:
            approval = app.state.agent.policy.reject(approval_id)
        except PolicyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        app.state.agent._prune_approval_inputs()
        app.state.audit.record(approval.tool, approval.decision.action_class.value,
            approval.decision.level.value, "refused", {"approval_id": approval_id},
            approved_by="user", detail="Antwortfreigabe vom Nutzer abgebrochen.")
        return Turn(reply="Abgebrochen. Nichts versendet.", approval_outcome="rejected",
                    context={"items": [], "history_egress": "local_only"})

    @app.get("/approvals", dependencies=guard)
    def approvals() -> list[dict[str, Any]]:
        with app.state.conversation_lock:
            visible = []
            validity_cache = {}
            for approval in app.state.agent.policy.pending():
                message = app.state.conversations.approval_message(approval.id)
                if message is not None:
                    lineage = _conversation_lineages(app.state.conversations.messages(message.conversation_id))[message.id]
                    if not conversation_memory.lineage_valid(app.state.episodes, lineage, validity_cache):
                        continue
                    context = message.metadata.get("mail_reply_context")
                    if context:
                        from .mail_reply_suggestions import context_active
                        if not context_active(app, context):
                            continue
                visible.append(approval.to_dict())
            return visible

    @app.post("/approvals/{approval_id}", dependencies=guard)
    def resolve(approval_id: str, body: ResolveIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            message = app.state.conversations.approval_message(approval_id)
            context = None
            if message is not None:
                context = message.metadata.get("mail_reply_context")
                if context and not body.granted:
                    return _cancel_bound_mail_reply(approval_id).to_dict()
                lineage = _conversation_lineages(app.state.conversations.messages(message.conversation_id))[message.id]
                if not conversation_memory.lineage_valid(app.state.episodes, lineage, {}):
                    raise HTTPException(status_code=409, detail="Die Gesprächsgrundlage dieser Freigabe wurde geändert oder ausgeschlossen.")
                if context:
                    from .mail_reply_suggestions import validate_context
                    validate_context(app, context["token"])
            execution = app.state.mail_reply_execution
            try:
                if context:
                    execution.token = context["token"]
                    execution.arguments = next((item["arguments"] for item in message.metadata.get("approvals", [])
                        if item.get("id") == approval_id), None)
                return app.state.agent.resolve(
                    approval_id, body.granted, body.confirmation
                ).to_dict()
            except PolicyError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            finally:
                if context:
                    del execution.token
                    del execution.arguments

    # -- Dauerregeln -------------------------------------------------------
    #
    # Was Icarus künftig ohne Rückfrage tun darf. Die Sicherheitszusagen
    # bleiben: eine Regel greift nie in einer kontaminierten Runde, sie schlägt
    # keine gesetzte Grenze, und sie hebt keine Stufe an. Siehe `regeln.py`.

    @app.get("/rules", dependencies=guard)
    def regeln_liste(alle: bool = False) -> dict[str, Any]:
        bank = getattr(app.state, "regeln", None)
        if bank is None:
            return {"items": [], "stufen": list(ERLAUBTE_STUFEN)}
        return {
            "items": [r.to_dict() for r in bank.alle(nur_aktive=not alle)],
            "stufen": list(ERLAUBTE_STUFEN),
        }

    @app.post("/rules", dependencies=guard, status_code=201)
    def regel_anlegen(body: RegelIn) -> dict[str, Any]:
        bank = getattr(app.state, "regeln", None)
        if bank is None:
            raise HTTPException(status_code=503, detail="Keine Regelbank.")
        if body.tool not in app.state.agent.tool_names:
            raise HTTPException(
                status_code=400,
                detail=f"Unbekanntes Werkzeug: {body.tool}.",
            )
        try:
            regel = bank.anlegen(body.name, body.tool, body.stufe, body.passt_auf)
        except RegelFehler as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Eine Dauerfreigabe ist selbst eine folgenreiche Entscheidung. Sie
        # gehört ins Protokoll wie jede andere.
        app.state.audit.record(
            "regel_anlegen", "write_local", "notify", "executed",
            {"tool": regel.tool, "stufe": regel.stufe, "passt_auf": regel.passt_auf},
            detail=regel.name,
        )
        return regel.to_dict()

    @app.post("/rules/{regel_id}/revoke", dependencies=guard)
    def regel_widerrufen(regel_id: str) -> dict[str, Any]:
        bank = getattr(app.state, "regeln", None)
        if bank is None:
            raise HTTPException(status_code=503, detail="Keine Regelbank.")
        try:
            regel = bank.widerrufen(regel_id)
        except RegelFehler as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        app.state.audit.record(
            "regel_widerrufen", "write_local", "notify", "executed",
            {"id": regel_id}, detail=regel.name,
        )
        return regel.to_dict()

    # -- Posteingang -------------------------------------------------------
    #
    # Mail im Gesprächsfenster: lesen, antworten, ins Gedächtnis nehmen.
    #
    # Die Sicherheitsregel bleibt unangetastet und ist hier die wichtigste im
    # ganzen System: **Jeder kann dir eine Mail schreiben.** Der Inhalt ist
    # ausnahmslos fremd, wird nie zur Anweisung, und der Versand geht durch
    # dieselbe Freigabe wie jede andere außenwirksame Handlung — der Knopf hier
    # ist kein zweiter Weg daran vorbei, sondern derselbe Weg, kürzer.

    def _mail_or_404():
        mail = getattr(app.state, "mail", None)
        if mail is None:
            raise HTTPException(
                status_code=409,
                detail=f"Kein Mailzugang eingerichtet. {WEGWEISER} bei „Mail“ mit dem Plus dein "
                       "Postfach hinzufügen — den Rest sucht Icarus.",
            )
        return mail

    @app.get("/mail", dependencies=guard)
    def mail_inbox(limit: int = 15, unread_only: bool = False) -> dict[str, Any]:
        """Der Posteingang — und ein leerer, wenn keiner eingerichtet ist.

        Bewusst **kein** Fehler in diesem Fall. Nichts eingerichtet zu haben
        ist der Normalzustand am ersten Tag, kein Störfall. Ein 409 färbte den
        Hinweis rot und schrieb bei jedem Öffnen des Gesprächs einen Fehler in
        die Konsole des Browsers — und eine Konsole voller normaler Zustände
        ist der beste Weg, einen echten Fehler zu übersehen.

        Die Abrufe einzelner Nachrichten bleiben beim 409: Wer eine bestimmte
        Mail verlangt, hat sich nicht verlaufen, sondern etwas verlangt, das
        es ohne Zugang nicht geben kann.
        """
        mail = getattr(app.state, "mail", None)
        if mail is None:
            return {
                "items": [],
                "unread": 0,
                "can_send": False,
                "eingerichtet": False,
                "detail": f"Noch keine Post verbunden. {WEGWEISER} bei „Mail“ mit dem Plus dein "
                          "Postfach hinzufügen — den Rest sucht Icarus.",
            }
        try:
            nachrichten = mail.inbox(limit=limit, unread_only=unread_only)
        except Exception as exc:  # noqa: BLE001 - Netzwerk, Anmeldung, Serverlaune
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        # Die Liste trägt keinen Volltext. Zwanzig ganze Mails sind ein
        # Vielfaches der Datenmenge, und sie stehen ohnehin zusammengefaltet
        # da. Hier abgeschnitten und nicht im Konnektor: So hängt die Zusage
        # am Endpunkt, statt daran, dass `inbox()` den Text zufällig nicht füllt.
        return {
            "items": [{**m.to_dict(), "body": ""} for m in nachrichten],
            "unread": sum(1 for m in nachrichten if m.unread),
            # Aus der Umgebung, nicht aus der Einstellungsdatei: Daraus liest
            # `MailConfig.from_env`, und nur das ist die tatsächlich wirksame
            # Konfiguration. Wer SMTP über die Umgebung setzt, bekam sonst ein
            # graues Antwortfeld mit „Kein SMTP eingerichtet“ — obwohl es
            # eingerichtet war.
            "can_send": bool(os.environ.get("ICARUS_SMTP_HOST")),
        }

    @app.get("/mail/{uid}", dependencies=guard)
    def mail_message(uid: str) -> dict[str, Any]:
        try:
            return _mail_or_404().message(uid).to_dict()
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _read_mail(uid: str) -> Any:
        try:
            return _mail_or_404().message(uid)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Die Nachricht konnte nicht geladen werden.") from exc

    from .mail_calendar_routes import install_routes as install_mail_calendar_routes, source_binding as calendar_mail_binding
    install_mail_calendar_routes(app, guard, _read_mail, _mail_or_404)

    def _can_reply(message: Any) -> bool:
        mail = _mail_or_404()
        if hasattr(mail, "can_send_from"):
            return mail.can_send_from(message.account_id)
        return bool(os.environ.get("ICARUS_SMTP_HOST"))

    @app.get("/api/v1/messages/{uid}", dependencies=guard)
    def read_kingfisher_mail(uid: str) -> dict[str, Any]:
        reader = _mail_or_404()
        message = _read_mail(uid)
        from .mail_thread import thread_context
        with app.state.conversation_lock:
            if app.state.mail is not reader or message.uid != uid:
                raise HTTPException(409, 'Die Mailquelle hat sich geändert. Bitte erneut öffnen.')
            binding = calendar_mail_binding(message, thread_context(app.state.episodes, message))
        return {**message.to_dict(), "source_digest": mail_source_digest(message), "calendar_source_digest": binding, "can_reply": _can_reply(message),
                "sending_account": getattr(_mail_or_404(), "sender_label", lambda _: "Standardkonto")(message.account_id)}

    @app.get("/api/v1/messages/{uid}/thread", dependencies=guard)
    def read_mail_thread(uid: str, limit: int = Query(default=20, ge=2, le=50)) -> dict[str, Any]:
        from .mail_thread import thread_context
        from .mail_thread_summary import fingerprint
        reader = _mail_or_404()
        message = _read_mail(uid)
        with app.state.conversation_lock:
            if app.state.mail is not reader or message.uid != uid:
                raise HTTPException(status_code=409, detail="Die Mailquelle hat sich geändert. Bitte erneut öffnen.")
            context = thread_context(app.state.episodes, message, limit=limit)
            return {**context, 'context_fingerprint': fingerprint(context)}

    thread_summary_lock = threading.Lock()

    @app.post('/api/v1/messages/{uid}/thread-summary', dependencies=guard)
    def summarize_mail_thread(uid: str, body: ThreadSummaryIn) -> dict[str, Any]:
        from .mail_thread import thread_context
        from .mail_thread_summary import fingerprint, summarize
        if not thread_summary_lock.acquire(blocking=False):
            raise HTTPException(status_code=429, detail='Ein Mailüberblick wird bereits erstellt. Bitte kurz warten.')
        try:
            reader = _mail_or_404()
            episodes = app.state.episodes
            message = _read_mail(uid)
            with app.state.conversation_lock:
                if app.state.mail is not reader or message.uid != uid or app.state.episodes is not episodes:
                    raise HTTPException(status_code=409, detail='Die Mailquelle hat sich geändert. Bitte erneut öffnen.')
                context = thread_context(episodes, message)
                if context['status'] != 'ready' or fingerprint(context) != body.context_fingerprint:
                    raise HTTPException(status_code=409, detail='Der Verlauf hat sich geändert. Bitte erneut laden.')

            def still_current(latest=message) -> bool:
                # Reuse the initial mail during cheap local guards; refetch it
                # once before delivery, outside the source mutation lock.
                with app.state.conversation_lock:
                    return (app.state.mail is reader and app.state.episodes is episodes and latest.uid == uid
                            and fingerprint(thread_context(episodes, latest)) == body.context_fingerprint)

            result = summarize(app, context, still_current=still_current)
            if not still_current(_read_mail(uid)) or result['status'] == 'changed':
                raise HTTPException(status_code=409, detail='Eine Grundlage des Überblicks hat sich geändert. Bitte erneut laden.')
            return result
        finally:
            thread_summary_lock.release()

    @app.post("/api/v1/messages/{uid}/reply", dependencies=guard, status_code=201)
    def prepare_mail_reply(uid: str, body: MailReplyIn) -> dict[str, Any]:
        if not body.body.strip():
            raise HTTPException(status_code=422, detail="Bitte einen Antworttext eingeben.")
        with app.state.conversation_lock:
            message = _read_mail(uid)
            if not _can_reply(message):
                raise HTTPException(status_code=409, detail="Für dieses Mailkonto ist kein Versand eingerichtet.")
            reply_context = None
            if body.context_token:
                from .mail_reply_suggestions import validate_context
                reply_context = validate_context(app, body.context_token, uid, expected_message=message)
            subject = message.subject if message.subject.lower().startswith("re:") else f"Re: {message.subject}"
            arguments = {"to": message.answer_address(), "subject": subject,
                         "body": body.body, "in_reply_to": message.message_id}
            if message.account_id:
                arguments["account_id"] = message.account_id
            # Nur der ausdrückliche Nutzerentwurf geht in den Modellverlauf.
            # Fremder Mailtext bleibt in der Leseansicht, nie eine Anweisung.
            app.state.agent.load_history([])
            result = app.state.agent.invoke("mail_senden", arguments)
            if not result.get("approvals"):
                raise HTTPException(status_code=409, detail="Der Antwortentwurf konnte nicht zur Freigabe vorbereitet werden.")
            conversation = app.state.conversations.create(f"Antwort: {message.subject}")
            app.state.conversations.add_message(conversation.id, "user", f"Mein Antwortentwurf:\n\n{body.body}",
                metadata={"mail_reply_context": reply_context} if reply_context else None)
            app.state.conversations.add_message(conversation.id, "assistant",
                "Die Antwort ist vorbereitet. Bitte Empfänger, Absender und Inhalt prüfen, bevor du den Versand freigibst.",
                metadata={"approvals": result["approvals"], "mail_source": {"uid": uid, "account_id": message.account_id},
                          "context": {"items": [], "history_egress": "local_only",
                                      **app.state.agent._lineage_metadata()},
                          **({"mail_reply_context": reply_context,
                              "conversation_source_lineage": reply_context["conversation_source_lineage"]}
                             if reply_context else {})})
        return _conversation_payload(conversation.id)

    @app.post("/api/v1/messages/{uid}/remember", dependencies=guard, status_code=201)
    @app.post("/mail/{uid}/remember", dependencies=guard, status_code=201)
    def remember_mail(uid: str) -> dict[str, Any]:
        """Nimmt eine Nachricht als Episode auf — nicht in den Bestand.

        Der Unterschied ist der ganze Punkt. Eine Episode hält fest, **dass
        etwas vorlag**; sie behauptet nichts über die Person. Ob aus einer Mail
        eine dauerhafte Aussage folgt, entscheidet die Verdichtung, und die legt
        vor, statt zu schreiben.

        Deshalb ist dieser Knopf unbedenklich, obwohl der Inhalt von einem
        Fremden stammt: Er füllt Rohmaterial, keine Fakten.

        Bewusst **auf Zuruf** und nicht automatisch. Ein Posteingang, der
        vollständig in die Episoden liefe, brächte Werbung und Newsletter mit —
        und jedes Stück davon ginge später als Material ins Modell.
        """
        source = _mail_or_404()
        message = _read_mail(uid)
        with app.state.conversation_lock:
            return _remember_mail_message(message, source, uid)

    def _remember_mail_message(nachricht: Any, source: Any, uid: str) -> dict[str, Any]:
        # Aufrufer halten die gemeinsame Sperre nach dem Netzabruf.
        if app.state.mail is not source or nachricht.uid != uid:
            raise HTTPException(status_code=409, detail="Die Mailquelle hat sich geändert. Bitte erneut öffnen.")
        return mail_ingestion.remember(app.state.episodes, nachricht, claims=app.state.claims)

    @app.post("/api/v1/messages/{uid}/task-suggestions", dependencies=guard)
    def mail_task_suggestions(uid: str) -> dict[str, Any]:
        message = _read_mail(uid)
        try:
            return suggest_mail_tasks(rollen_von(app).provider("hintergrund"), message)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Aufgabenvorschläge konnten nicht erstellt werden.") from exc

    @app.post("/api/v1/messages/{uid}/task", dependencies=guard, status_code=201)
    def task_from_mail(uid: str, body: MailTaskIn) -> dict[str, Any]:
        title = body.title.strip()
        waiting_for = body.waiting_for.strip() if body.waiting_for else None
        if not title or (body.waiting_for is not None and not waiting_for):
            raise HTTPException(status_code=422, detail="Aufgabe und gegebenenfalls wartende Person dürfen nicht leer sein.")
        if body.quick_accept and (not body.source_digest or not body.source_quote
                                  or body.project_id or body.due or body.waiting_for):
            raise HTTPException(status_code=422, detail="Die direkte Übernahme benötigt eine aktuelle Textstelle und enthält keine weiteren Zuordnungen.")
        _validate_task_project(body.project_id)
        if not body.source_digest:
            raise HTTPException(status_code=409, detail="Die gelesene Mailfassung fehlt. Bitte die Nachricht erneut öffnen und die Aufgabe prüfen.")
        # Erst die aktuelle Mail lesen; bei Quellenentzug entsteht keine Aufgabe.
        source = _mail_or_404()
        message = _read_mail(uid)
        if body.source_digest and body.source_digest != mail_source_digest(message):
            raise HTTPException(status_code=409, detail="Die Nachricht hat sich geändert. Bitte erneut lesen und prüfen.")
        if body.source_quote is not None and (not body.source_digest or body.source_quote not in (message.body or message.preview)):
            raise HTTPException(status_code=409, detail="Die Textstelle ist nicht in der aktuellen Nachricht belegt. Bitte erneut prüfen.")
        if body.quick_accept:
            from .mail_timeline import date_status
            if date_status(message.date, now=datetime.now().astimezone()) != 'recent':
                raise HTTPException(409, 'Historische oder undatierte Mail. Bitte zuerst die Aufgabe ausdrücklich prüfen und vorbereiten.')
        with app.state.conversation_lock:
            episode = _remember_mail_message(message, source, uid)["episode"]
            if episode['state'] == 'ignored':
                raise HTTPException(409, 'Diese Quelle wurde ausgeschlossen. Bitte zuerst die Quelle ausdrücklich prüfen.')
            provenance = Provenance(source_type=SourceType.USER_STATED, source_ref=f"episode:{episode['id']}",
                                    verbatim=body.source_quote, captured_at=datetime.now().astimezone())
            if body.quick_accept:
                from .mail_timeline import message_timing
                if message_timing(app.state.episodes, message, now=datetime.now().astimezone())['temporal_status'] != 'recent':
                    raise HTTPException(409, 'Bitte zuerst den zeitlichen Verlauf prüfen und die Aufgabe ausdrücklich vorbereiten.')
                # The same explicit suggestion remains once-only after a lost
                # response or reopening the mail. A source change still fails
                # the checks above, even if an earlier task already exists.
                key = mail_task_identity(message, title, body.source_quote)
                return app.state.tasks.from_suggestion(f'mail-{key}', title, provenance).to_dict()
            if body.request_id is not None:
                payload = {'uid': uid, 'source_digest': body.source_digest, 'source_quote': body.source_quote,
                           'title': title, 'project_id': body.project_id, 'waiting_for': waiting_for,
                           'due': ensure_aware(body.due).astimezone(timezone.utc).isoformat() if body.due else None}
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                try:
                    return app.state.tasks.from_request(str(body.request_id), digest, title, provenance,
                        due=body.due, project_id=body.project_id, waiting_for=waiting_for).to_dict()
                except TaskRequestConflict as exc:
                    raise HTTPException(409, str(exc) + ' Bitte die vorhandenen Aufgaben prüfen.') from exc
            task = app.state.tasks.add(title,
                provenance,
                due=body.due, project_id=body.project_id)
            if waiting_for:
                task = app.state.tasks.warten_auf(task.id, waiting_for)
            return task.to_dict()

    # -- Audit -------------------------------------------------------------

    @app.get("/audit", dependencies=guard)
    def audit_entries(limit: int = 50) -> list[dict[str, Any]]:
        return app.state.audit.entries(limit)

    @app.post("/api/v1/assertions", dependencies=guard, status_code=201)
    @app.post("/assertions", dependencies=guard, status_code=201)
    def record(body: RecordIn) -> dict[str, Any]:
        try:
            assertion = app.state.store.record(
                statement=body.statement,
                kind=body.kind,
                provenance=Provenance(
                    source_type=body.provenance.source_type,
                    source_ref=body.provenance.source_ref,
                    captured_at=body.provenance.captured_at,
                    extracted_by=body.provenance.extracted_by,
                    verbatim=body.provenance.verbatim,
                ),
                confidence=body.confidence,
                valid_from=body.valid_from,
                expires_at=body.expires_at,
                supersedes=body.supersedes,
                derived_from=body.derived_from,
                sensitivity=body.sensitivity,
                tags=body.tags,
            )
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return assertion.to_dict()

    @app.get("/assertions", dependencies=guard)
    def usable() -> list[dict[str, Any]]:
        return [a.to_dict() for a in app.state.store.usable()]

    @app.get("/suche", dependencies=guard)
    def suchen(q: str, limit: int = 6) -> dict[str, Any]:
        """Ein Feld für alles.

        Der Nutzer weiß nicht, ob „Brandt“ eine Aussage, eine Notiz, ein
        Projekt oder eine Mail ist. Ihn nach der Schicht zu fragen, hieße ihm
        die Architektur zuzumuten.
        """
        return suche.suche(
            q,
            store=app.state.store,
            tasks=app.state.tasks,
            workspace=app.state.workspace,
            episodes=app.state.episodes,
            limit=max(1, min(limit, 20)),
            eigene=_eigene_adressen(),
        )

    @app.get("/recall", dependencies=guard)
    def recall(q: str, limit: int = 10) -> list[dict[str, Any]]:
        return [a.to_dict() for a in app.state.store.recall(q, limit)]

    app.state.support_review = SupportReview(app.state.store, app.state.proposals, app.state.episodes, app.state.audit)

    @app.get('/api/v1/assertions/support-review', dependencies=guard)
    def support_review_list(cursor: str | None = None, limit: int = 25):
        try:
            return app.state.support_review.list(cursor, limit)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.post('/api/v1/assertions/{assertion_id}/support-reassessment/preview', dependencies=guard)
    def support_review_preview(assertion_id: str):
        try:
            with app.state.conversation_lock:
                return app.state.support_review.preview(assertion_id)
        except SupportReviewConflict as exc:
            raise HTTPException(409, detail=str(exc)) from exc

    @app.post('/api/v1/assertions/{assertion_id}/support-reassessment', dependencies=guard)
    def support_review_submit(assertion_id: str, body: SupportReassessmentIn):
        try:
            with app.state.conversation_lock:
                return app.state.support_review.submit(assertion_id, body.preview_token, body.confirmed)
        except (ValueError, ConflictError, ImmutableContentError) as exc:
            raise HTTPException(409, detail=str(exc)) from exc

    @app.get("/api/v1/assertions/{assertion_id}/history", dependencies=guard)
    @app.get("/assertions/{assertion_id}/history", dependencies=guard)
    def history(assertion_id: str) -> list[dict[str, Any]]:
        try:
            return [a.to_dict() for a in app.state.store.history(assertion_id)]
        except ConflictError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/assertions/{assertion_id}/confirm", dependencies=guard)
    def confirm(assertion_id: str) -> dict[str, Any]:
        try:
            return app.state.store.confirm(assertion_id).to_dict()
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/assertions/{assertion_id}/retract", dependencies=guard)
    @app.post("/assertions/{assertion_id}/retract", dependencies=guard)
    def retract(assertion_id: str) -> dict[str, Any]:
        """Die Aussage war inhaltlich falsch.

        Der Unterschied zu `redact` ist wichtig genug für einen eigenen Weg:
        Bei `redact` war der Inhalt womöglich richtig, soll aber weg — und
        dann muss alles Abgeleitete mit. Hier stimmte er nie. Der Satz bleibt
        lesbar, damit nachvollziehbar ist, was einmal geglaubt wurde, und
        alles, was darauf stand, bleibt stehen — erschüttert, nicht gelöscht.
        """
        try:
            return app.state.store.retract(assertion_id).to_dict()
        except ConflictError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/assertions/{assertion_id}/redact", dependencies=guard)
    def redact(assertion_id: str, body: RedactIn) -> list[dict[str, Any]]:
        try:
            affected = app.state.store.redact(assertion_id, reason=body.reason)
        except ConflictError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [a.to_dict() for a in affected]

    @app.get("/export", dependencies=guard)
    def export() -> dict[str, Any]:
        return app.state.store.export().to_dict()

    # -- Dashboard ---------------------------------------------------------

    @app.get("/dashboard", dependencies=guard)
    def dashboard(days: int = 7, post: bool = True) -> dict[str, Any]:
        """Alles für die Startseite in einem Aufruf.

        Jeder Bereich ist einzeln fehlertolerant: Ist ein Konnektor nicht
        eingerichtet oder gerade nicht erreichbar, fehlt genau dieser Block mit
        einer Begründung — der Rest der Seite steht trotzdem. Ein Dashboard,
        das komplett ausfällt, weil ein Mailserver hakt, ist nutzlos.
        """
        result: dict[str, Any] = {
            "now": datetime.now().astimezone().isoformat(),
            "projects": {"items": [], "error": None},
            "tasks": {"items": [], "error": None},
            "calendar": {"items": [], "nachzubereiten": [], "error": None},
            "mail": {"items": [], "error": None},
            "memory": {"count": 0, "recent": []},
            "working_memory": {"items": [], "truncated": False, "error": None},
        }

        try:
            result["projects"]["items"] = [
                p.to_dict() for p in app.state.workspace.projects()
            ]
        except Exception as exc:  # noqa: BLE001
            result["projects"]["error"] = str(exc)

        try:
            # Erst alle offenen Aufgaben bewerten, danach begrenzt das Briefing
            # die Anzeige. Sonst verdrängen alte Wartezustände eigene Fristen.
            offen = app.state.tasks.open_tasks(limit=None)
            result["tasks"]["items"] = [t.to_dict() for t in offen]
            result["tasks"]["overdue"] = sum(1 for t in offen if t.is_overdue())
            result["tasks"]["wartend"] = [
                t.to_dict() for t in offen if t.wartet_auf is not None
            ]
        except Exception as exc:  # noqa: BLE001 - ein Bereich darf die Seite nicht kippen
            result["tasks"]["error"] = str(exc)

        try:
            wanken = entscheidungen.erschuettert(app.state.store, knowledge=app.state.claims)
            result["decisions"] = {
                "erschuettert": [e.to_dict() for e in wanken],
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - ein Bereich darf die Seite nicht kippen
            result["decisions"] = {"erschuettert": [], "error": str(exc)}

        try:
            schlafend = urteil.eingeschlafen(
                store=app.state.store,
                episodes=getattr(app.state, "episodes", None),
                tasks=getattr(app.state, "tasks", None),
                workspace=getattr(app.state, "workspace", None),
            )
            result["goals"] = {
                "eingeschlafen": [v.to_dict() for v in schlafend],
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - ein Bereich darf die Seite nicht kippen
            result["goals"] = {"eingeschlafen": [], "error": str(exc)}

        calendar = getattr(app.state, "calendar", None)
        if calendar is None:
            # Kein Variablenname für den Nutzer: `ICARUS_CALDAV_URL` ist Wissen,
            # das niemand außerhalb der IT hat, und daraus folgt kein nächster
            # Schritt. Der Weg dorthin steht im Satz.
            result["calendar"]["error"] = (
                f"Noch kein Kalender verbunden. {WEGWEISER} bei „Kalender“ "
                "mit dem Plus einen Kalender hinzufügen."
            )
        else:
            try:
                # Ein Abruf für beides: Was kommt, wird vorbereitet; was in den
                # letzten 48 Stunden zu Ende ging, fragt nach seinem Ergebnis.
                from .nachbereitung import FENSTER
                jetzt_utc = datetime.now(timezone.utc)
                alle = [e.to_dict() for e in calendar.events(days=days + 2, at=jetzt_utc - FENSTER)]
                kommend, vergangen = [], []
                for item in alle:
                    # Ohne Ende (etwa DURATION statt DTEND) weiß niemand, ob
                    # der Termin vorbei ist; er bleibt dann bei den kommenden.
                    try:
                        ende = datetime.fromisoformat(str(item.get("end") or ""))
                    except ValueError:
                        ende = None
                    vorbei = ende is not None and ende.tzinfo is not None and ende <= jetzt_utc
                    (vergangen if vorbei else kommend).append(item)
                result["calendar"]["items"] = kommend
                _vorbereiten(result["calendar"]["items"])
                result["calendar"]["nachzubereiten"] = _nachzubereiten(vergangen, jetzt_utc)
                errors = list(getattr(calendar, "last_errors", {}).values())
                if errors:
                    result["calendar"]["error"] = "Einige Kalender sind gerade nicht verfügbar: " + "; ".join(str(error) for error in errors)
            except Exception as exc:  # noqa: BLE001
                result["calendar"]["error"] = str(exc)

        mail = getattr(app.state, "mail", None)
        if not post:
            # Die Startseite zeigt den Gruß sofort und holt die Post danach (Fremdprobe, Befund 22).
            result["mail"]["ausstehend"] = True
        elif mail is None:
            result["mail"]["error"] = (
                f"Noch kein Postfach verbunden. {WEGWEISER} bei „Mail“ mit dem Plus dein "
                "Postfach hinzufügen — den Rest sucht Icarus."
            )
        else:
            from .mail_anmeldung import Anmeldefehler
            from .postfach_lage import lage as postfach_lage, wer as postfach_wer
            host, name = postfach_wer(app)
            try:
                # Die Startseite wartet nicht auf ein Postfach, das nicht antwortet; schwieg es eben schon, gar nicht.
                messages = postfach_lage(app).lesen("alle", lambda: mail.inbox(limit=8), host=host, name=name,
                                                    sekunden=POSTFACH_ZEITGRENZE)
                result["mail"]["items"] = [m.to_dict() for m in messages]
                result["mail"]["unread"] = sum(1 for m in messages if m.unread)
                if len(messages) < 8:  # nur ein vollständiger Blick sagt, ob ein Postfach leer ist
                    from .mail_stand import merke_gelesen
                    merke_gelesen(app, {e.id: sum(1 for m in messages if (m.account_id or e.id) == e.id)
                                        for e in app.state.settings.mail_accounts if e.configured})
            except Anmeldefehler as fehler:
                result["mail"]["error"] = (
                    f"{fehler.satz} Die Startseite zeigt alles andere; die Mails kommen, sobald es wieder antwortet."
                )
            except Exception as exc:  # noqa: BLE001
                result["mail"]["error"] = str(exc)

        # Was roh vorliegt und noch niemand angesehen hat. Ein Chief of Staff,
        # der einen Berg unbearbeiteten Materials verschweigt, ist keiner.
        try:
            counts = app.state.episodes.counts()
            result["episodes"] = {
                "pending": counts.get("new", 0),
                # Für „Relevante Nachrichten“: nur, was von anderen kam (Fremdprobe 2, Befund 22).
                "neu_von_aussen": app.state.episodes.neue_von_aussen(),
                "counts": counts,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            result["episodes"] = {"pending": 0, "counts": {}, "error": str(exc)}

        # Die Vorschläge kommen mit Wortlaut, nicht nur als Zahl: das Briefing
        # zitiert sie, und eine Zahl kann man nicht zitieren.
        offene_vorschlaege: list[dict[str, Any]] = []
        try:
            offene_vorschlaege = [
                v.to_dict() for v in app.state.proposals.pending(limit=20)
            ]
            result["proposals"] = {
                "pending": app.state.proposals.counts().get(ProposalState.PENDING.value, 0),
                "items": offene_vorschlaege,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            result["proposals"] = {"pending": 0, "items": [], "error": str(exc)}

        # Erkannte Aufgaben aus Mails: Vorschläge, keine Aufgaben. Das Briefing
        # braucht dazu, von wem und wann — sonst liest sich „Rechnung senden“
        # wie etwas, das man sich selbst vorgenommen hat.
        try:
            result["task_candidates"] = task_candidates_for_briefing(app.state.proposals, app.state.episodes)
        except Exception as exc:  # noqa: BLE001
            result["task_candidates"] = {"pending": 0, "items": [], "error": str(exc)}

        # Wissenskandidaten und ihre Widersprüche sind nicht dasselbe wie die
        # allgemeine Vorschlagsschlange: Ein Widerspruch braucht eine bewusste
        # Entscheidung, bevor er als Wahrheit oder auch nur als Kontext gelten
        # darf. Für das Dashboard liefern wir deshalb nur Kennungen und Zahlen,
        # nie den fremden Quelltext oder die behaupteten Werte.
        try:
            clarifications = app.state.knowledge_service.clarifications()
            result["knowledge"] = {
                "pending": len(app.state.knowledge_service.pending()),
                "clarifications": [
                    {"id": item["id"]} for item in clarifications
                ],
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - eine kaputte Leseschicht darf nicht alles kippen
            result["knowledge"] = {
                "pending": 0,
                "clarifications": [],
                "error": str(exc),
            }

        try:
            usable = app.state.store.usable()
            result["memory"]["count"] = len(usable)
            result["memory"]["recent"] = [
                a.to_dict() for a in sorted(usable, key=lambda x: x.recorded_at, reverse=True)[:5]
            ]
        except Exception:  # noqa: BLE001 - gesunde Bereiche bleiben erreichbar
            result["memory"] = {"count": 0, "recent": [], "error": "Gedächtnis ist gerade nicht verfügbar. Bitte erneut laden."}

        try:
            from .working_memory_context import reports
            with app.state.conversation_lock:
                result["working_memory"] = reports(app.state.episodes, app.state.claims,
                    since=datetime.now().astimezone() - timedelta(hours=24))
        except Exception:  # Healthy dashboard sections remain usable.
            result["working_memory"] = {"items": [], "truncated": False,
                "error": "Die automatischen Quellenberichte sind gerade nicht verfügbar."}

        # Zuletzt das Urteil: was von alldem heute zählt. Es liest nur, was
        # oben steht — deshalb kann es die Seite auch nicht kippen.
        try:
            result["briefing"] = briefing.erstelle(
                result,
                jetzt=datetime.now().astimezone(),
                vorschlaege=offene_vorschlaege,
            ).to_dict()
        except Exception as exc:  # noqa: BLE001
            result["briefing"] = None
            result["briefing_error"] = str(exc)

        return result

    # -- Kingfisher Morning Briefing -------------------------------------

    def _calendar_overview(days: int = 7, year_view: bool = False, *, start: datetime | None = None,
                           finish: datetime | None = None, zone=None) -> dict[str, Any]:
        calendar = getattr(app.state, "calendar", None)
        result: dict[str, Any] = {"items": [], "errors": [], "configured": calendar is not None}
        # Bestätigte Geburtstage stehen jedes Jahr wieder im Kalender, auch ohne verbundenen Kalender; nur in dieser
        # Ansicht, in keinen Kalender eines Anbieters geschrieben (Fremdprobe 2, Befund 20).
        from .wiederkehrendes import kalender_eintraege
        heute = datetime.now().astimezone().date()
        von, bis = ((start.astimezone(zone).date(), finish.astimezone(zone).date()) if start and finish else
                    (heute.replace(month=1, day=1), heute.replace(year=heute.year + 1, month=1, day=1)) if year_view
                    else (heute, heute + timedelta(days=days)))
        if start and finish:
            result.update(range_start=start.isoformat(), range_end=finish.isoformat())
        geburtstage = kalender_eintraege(app.state.claims, von, bis)
        if calendar is None:
            result["items"] = geburtstage
            return result
        try:
            if start and finish:
                events = calendar.events(days=(finish - start).total_seconds() / 86400, at=start)
            elif year_view:
                current = datetime.now().astimezone()
                start = current.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                finish = start.replace(year=start.year + 1)
                events = calendar.events(days=(finish - start).days, at=start)
            else:
                events = calendar.events(days=days)
            result["items"] = [event.to_dict() for event in events]
            result["errors"] = list(getattr(calendar, "last_errors", {}).values())
        except Exception as exc:
            result["errors"] = [str(exc)]
        result["items"] = sorted([*result["items"], *geburtstage], key=lambda e: str(e.get("start") or ""))
        return result

    @app.get("/api/v1/calendar", dependencies=guard)
    def kingfisher_calendar(days: int = Query(default=7, ge=1, le=31), year_view: bool = False,
                           from_: str | None = Query(default=None, alias='from', max_length=100),
                           until: str | None = Query(default=None, max_length=100),
                           tz: str | None = Query(default=None, max_length=100)) -> dict[str, Any]:
        from .calendar_window import parse_calendar_window
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        if bool(from_) != bool(until):
            raise HTTPException(status_code=422, detail='Beginn und Ende des Kalenderzeitraums sind gemeinsam erforderlich.')
        try:
            zone = ZoneInfo(tz) if tz else None
            start, finish = parse_calendar_window(from_, until) if from_ is not None and until is not None else (None, None)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _calendar_overview(days, year_view, start=start, finish=finish, zone=zone)

    def _vorbereiten(items: list[dict[str, Any]]) -> None:
        """Kommende Termine der nächsten 24 Stunden bekommen ihre Zuordnung mit.

        Das Briefing sagt dann „mit Anna Keller, vermutlich Projekt Mainz“
        statt nur den Titel. Der Bestand läuft dafür einmal für alle
        Teilnehmer durch, nicht je Termin. Ein Fehler hier kostet die
        Anreicherung, nie die Termine, und wird protokolliert.
        """
        from .vorbereitung import zuordnung
        jetzt = datetime.now(timezone.utc)
        grenze = jetzt + timedelta(hours=24)
        kommend = []
        for item in items:
            try:
                start = datetime.fromisoformat(str(item.get("start") or ""))
                ende = datetime.fromisoformat(str(item.get("end") or item.get("start") or ""))
            except ValueError:
                continue
            if start.tzinfo is None or ende.tzinfo is None or item.get("all_day"):
                continue
            if start <= grenze and ende >= jetzt:
                kommend.append(item)
        if not kommend:
            return
        eigene = _eigene_adressen()
        try:
            index = app.state.episodes.participants_for_addresses(
                [a for item in kommend for a in item.get("attendees") or ()])
            projekte = app.state.workspace.projects(include_closed=True)
        except Exception:  # noqa: BLE001
            logger.exception("Termine konnten nicht vorbereitet werden")
            return
        for item in kommend:
            try:
                daten = zuordnung(item, episodes=app.state.episodes, workspace=app.state.workspace,
                                  eigene=eigene, index=index, projekte=projekte)
            except Exception:  # noqa: BLE001
                logger.exception("Termin konnte nicht vorbereitet werden")
                continue
            item["vorbereitung"] = {
                "bekannte": [p["name"] for p in daten["teilnehmer"] if p["person"]],
                "teilnehmer": daten["anzahl_teilnehmer"],
                "projekt": daten["projekt"]["name"] if daten["projekt"] else None,
                "vorschlag": bool(daten["projekt"] and daten["projekt"]["herkunft"] == "vorschlag"),
            }

    def _nachzubereiten(items: list[dict[str, Any]], jetzt: datetime) -> list[dict[str, Any]]:
        """Vergangene Termine mit anderen, die noch niemand nachbereitet hat.

        Ein Fehler hier kostet die Nachfrage, nie die Termine.
        """
        from .nachbereitung import offene, schluessel
        try:
            from .connectors.collections import event_uids
            keys = [k for item in items for uid in event_uids(item) if (k := schluessel(uid, item.get("start")))]
            erledigt = app.state.workspace.event_followups(keys)
            holen = getattr(app.state, "zuordner_holen", None)
            # Liegt zu einem Termin eine Mitschrift vor, gibt es nichts nachzufragen.
            return offene(items, jetzt=jetzt, eigene=_eigene_adressen(), erledigt=erledigt,
                          hat_mitschrift=(lambda key: bool(holen().fuer_termin(key))) if holen else (lambda key: False))
        except Exception:  # noqa: BLE001
            logger.exception("Nachbereitung konnte nicht ermittelt werden")
            return []

    def _eigene_adressen() -> list[str]:
        return identitaet.eigene_adressen(getattr(app.state, "settings", None))

    def _termin(uid: str, start: str | None = None) -> dict[str, Any]:
        from .connectors.collections import event_copy
        if start is not None:
            return _vorkommen(uid, start)
        current = _calendar_overview(year_view=True)
        matches = [copy for item in current["items"] if (copy := event_copy(item, uid)) is not None]
        if len(matches) > 1:
            raise HTTPException(status_code=409, detail="Dieser Kalenderlink ist mehrdeutig. Bitte ein konkretes Vorkommen mit Beginn auswählen.")
        event = matches[0] if matches else None
        if event is None:
            if current["errors"]:
                raise HTTPException(status_code=503, detail="Der Termin kann gerade nicht aus seiner Quelle geladen werden.")
            raise HTTPException(status_code=404, detail="Der Termin ist nicht mehr im verbundenen Kalender verfügbar.")
        return event

    @app.get("/api/v1/calendar/zuordnung", dependencies=guard)
    def calendar_assignment(uid: str = Query(min_length=1, max_length=2048), start: str | None = Query(default=None, max_length=64)) -> dict[str, Any]:
        """Wer kommt, und welches Projekt gilt: festgelegt oder vorgeschlagen, mit Grund."""
        from .vorbereitung import zuordnung
        return zuordnung(_termin(uid, start), episodes=app.state.episodes, workspace=app.state.workspace,
                         eigene=_eigene_adressen())

    @app.put("/api/v1/calendar/zuordnung", dependencies=guard)
    def set_calendar_assignment(body: CalendarAssignmentIn) -> dict[str, Any]:
        """Berichtigung mit einem Klick; gilt dauerhaft für diesen Termin."""
        from .vorbereitung import zuordnung
        event = _termin(body.uid, body.start)
        try:
            from .connectors.collections import event_uids
            app.state.workspace.set_event_projects(event_uids(event), body.project_id)
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return zuordnung(event, episodes=app.state.episodes, workspace=app.state.workspace,
                         eigene=_eigene_adressen())

    def _vorkommen(uid: str, start: str) -> dict[str, Any]:
        """Ein bestimmter Termin einer Serie: Kennung und Beginn.

        Der ausdrückliche Beginn bestimmt das Zeitfenster auch außerhalb des aktuellen Jahres.
        """
        from .nachbereitung import gleicher_beginn
        from .datumstext import iso_lesen_streng
        try:
            at = iso_lesen_streng(start)
            if at.utcoffset() is None:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=422, detail='Der Terminbeginn muss einen gültigen Zeitpunkt mit Zeitzone enthalten.') from None
        current = _calendar_overview(start=at.replace(hour=0, minute=0, second=0, microsecond=0),
                                     finish=at.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        kandidaten = list(current["items"])
        fehler = list(current["errors"])
        from .connectors.collections import event_copy
        event = next((copy for item in kandidaten if (copy := event_copy(item, uid)) is not None
                      and gleicher_beginn(copy.get("start"), start)), None)
        if event is None:
            if fehler:
                raise HTTPException(status_code=503, detail="Der Termin kann gerade nicht aus seiner Quelle geladen werden.")
            raise HTTPException(status_code=404, detail="Der Termin ist nicht mehr im verbundenen Kalender verfügbar.")
        return event

    def _nachbereitung_stand(event: dict[str, Any]) -> dict[str, Any]:
        from .nachbereitung import andere_teilnehmer, schluessel
        key = schluessel(str(event["uid"]), event.get("start"))
        from .connectors.collections import event_uids
        keys = [k for uid in event_uids(event) if (k := schluessel(uid, event.get("start")))]
        completed = app.state.workspace.event_followups(keys)
        erledigt = bool(completed)
        episode_id = next((completed[k] for k in keys if completed.get(k)), None)
        try:
            beginn = datetime.fromisoformat(str(event.get("start") or ""))
            begonnen = beginn.tzinfo is not None and beginn <= datetime.now(timezone.utc)
        except ValueError:
            begonnen = False
        transcripts = {"transkripte": [], "angebote": []}
        for copy_key in keys:
            for kind, values in termin_stand(app, copy_key).items():
                for value in values:
                    if value not in transcripts[kind]:
                        transcripts[kind].append(value)
        return {"uid": event["uid"], "start": event.get("start"), "end": event.get("end"),
                "summary": event.get("summary"), "begonnen": begonnen,
                "stand": "offen" if not erledigt else "festgehalten" if episode_id else "nichts",
                "episode_id": episode_id,
                "teilnehmer": andere_teilnehmer(event.get("attendees") or (), _eigene_adressen()),
                "termin": key, **transcripts}

    @app.get("/api/v1/calendar/nachbereitung", dependencies=guard)
    def calendar_followup(uid: str = Query(min_length=1, max_length=2048),
                          start: str = Query(min_length=1, max_length=64)) -> dict[str, Any]:
        """Ob ein vergangener Termin nachbereitet ist, und mit wem er war."""
        return _nachbereitung_stand(_vorkommen(uid, start))

    @app.post("/api/v1/calendar/nachbereitung", dependencies=guard)
    def record_calendar_followup(body: CalendarFollowupIn) -> dict[str, Any]:
        """Hält fest, was bei einem Termin herausgekommen ist, als Quelle.

        Die Quelle trägt die Teilnehmer, das Projekt und das Ende des Termins.
        Daraus werden Bitten, Zusagen und Aufgaben *vorgeschlagen*; ein Fakt
        entsteht erst durch Annahme. Wer zweimal nachbereitet, ergänzt.
        """
        from .nachbereitung import andere_teilnehmer, schluessel, text_aus_mitschrift
        event = _vorkommen(body.uid, body.start)
        stand = _nachbereitung_stand(event)
        if not stand["begonnen"]:
            raise HTTPException(status_code=409, detail="Der Termin hat noch nicht begonnen.")
        if "\0" in body.text:
            raise HTTPException(status_code=422, detail="Der Text enthält ungültige Zeichen.")
        try:
            size = len(body.text.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise HTTPException(status_code=422, detail="Der Text muss gültiger UTF-8-Text sein.") from exc
        if size > 512 * 1024:
            raise HTTPException(status_code=422, detail="Der Text darf höchstens 512 KiB groß sein.")
        if len(body.text.encode("utf-8", "replace")) + len(body.notiz.encode("utf-8", "replace")) > 512 * 1024:
            raise HTTPException(status_code=422, detail="Notiz und Mitschrift zusammen dürfen höchstens 512 KiB groß sein.")
        if body.format == "text":
            text = body.text.strip()
        else:
            try:
                text = text_aus_mitschrift(body.text, body.format)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"Die Mitschrift ist nicht lesbar: {exc}") from exc
            # Eigene Notizen gehen neben der Mitschrift nicht verloren.
            if body.notiz.strip():
                text = f"{body.notiz.strip()}\n\nMitschrift:\n{text}"
        if not text:
            raise HTTPException(status_code=422, detail="Bitte aufschreiben, was herausgekommen ist.")
        _validate_task_project(body.project_id)
        key = schluessel(str(event["uid"]), event.get("start"))
        ende = None
        try:
            ende = datetime.fromisoformat(str(event.get("end") or event.get("start")))
        except ValueError:
            pass
        titel = f"Nachbereitung: {event.get('summary') or 'Termin'}"
        # Der Kopf bindet den Text an diesen Termin. Ohne ihn fände derselbe
        # Satz („Nichts Neues.“) bei einem zweiten Termin die Quelle des
        # ersten wieder, samt deren Teilnehmern und Projekt. Beim selben
        # Termin führt derselbe Text dagegen zur selben Quelle: Erneut senden
        # legt nichts doppelt an.
        try:
            beginn = datetime.fromisoformat(str(event.get("start"))).astimezone(timezone.utc)
            wann = f" vom {beginn.day}.{beginn.month}.{beginn.year}, {beginn.hour}:{beginn.minute:02d} Uhr UTC"
        except ValueError:
            wann = ""
        inhalt = f"Nachbereitung des Termins „{event.get('summary') or 'Termin'}“{wann}:\n\n{text}"
        # Jede ergänzte Notiz ist eine eigene Quelle; nur derselbe Text zum
        # selben Vorkommen ist ein erneuter Versuch.
        source_key = f"termin:{key}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        with app.state.conversation_lock:
            episode, created = app.state.episodes.record(
                kind=EpisodeKind.MESSAGE, title=titel, body=inhalt,
                provenance=Provenance(
                    source_type=SourceType.USER_STATED if body.format == "text" else SourceType.DOCUMENT,
                    source_ref=f"termin:{key}", captured_at=datetime.now().astimezone()),
                occurred_at=ende, project_id=body.project_id, source_key=source_key,
                participants=andere_teilnehmer(event.get("attendees") or (), _eigene_adressen()),
            )
            if created:
                app.state.episodes.advance_source_head(source_key, app.state.episodes.source_head(source_key), episode.id)
            elif body.project_id is not None and episode.project_id != body.project_id:
                episode = app.state.episodes.link_project(episode.id, body.project_id)
            # Ein gewähltes Projekt gilt wie jede andere Wahl für diesen
            # Termin. „Kein Projekt“ hier ändert die Zuordnung nicht: Es kann
            # auch heißen, dass die Auswahl nicht geladen war.
            if body.project_id is not None:
                from .connectors.collections import event_uids
                app.state.workspace.set_event_projects(event_uids(event), body.project_id)
            app.state.workspace.set_event_followup(key, episode.id)
        einordnung = "aus" if created else "schon_festgehalten"
        schedule = app.state.settings.schedule
        agent = getattr(app.state, "agent", None)
        lokal = getattr(rollen_von(app).provider("hintergrund"), "is_local", False)
        scheduler = getattr(app.state, "scheduler", None)
        if created and schedule.enabled and schedule.with_model and lokal and scheduler is not None:
            scheduler.request_working_memory(episode.id)
            einordnung = "laeuft"
        return {"id": episode.id, "created": created, "title": episode.title,
                "project_id": episode.project_id, "einordnung": einordnung,
                "nachbereitung": _nachbereitung_stand(event)}

    @app.put("/api/v1/calendar/nachbereitung/stand", dependencies=guard)
    def set_calendar_followup_status(body: CalendarFollowupStatusIn) -> dict[str, Any]:
        """„Nichts festzuhalten“ oder das zurücknehmen; Festgehaltenes bleibt."""
        from .nachbereitung import schluessel
        event = _vorkommen(body.uid, body.start)
        key = schluessel(str(event["uid"]), event.get("start"))
        if key is None:
            raise HTTPException(status_code=422, detail="Dieser Termin hat keinen genauen Beginn.")
        # Unter derselben Sperre wie das Festhalten, und nur, wo noch nichts
        # steht: Ein „nichts“ aus einem zweiten Fenster überschreibt keine
        # festgehaltene Nachbereitung.
        with app.state.conversation_lock:
            from .connectors.collections import event_uids
            keys = [k for uid in event_uids(event) if (k := schluessel(uid, event.get("start")))]
            if body.nichts:
                if not app.state.workspace.event_followups(keys):
                    app.state.workspace.mark_event_nothing(key)
            else:
                for copy_key in keys:
                    app.state.workspace.reopen_event_followup(copy_key)
        return _nachbereitung_stand(event)

    @app.get("/api/v1/calendar/preparation", dependencies=guard)
    def calendar_preparation(uid: str = Query(min_length=1, max_length=2048),
                             project_id: str | None = None,
                             person_id: str | None = None,
                             start: str | None = Query(default=None, max_length=64)) -> dict[str, Any]:
        """Lesender, ausdrücklich gewählter Kontext ohne neue Terminzuordnung."""
        event = _termin(uid, start)
        result: dict[str, Any] = {"event": event, "project": None, "person": None, "tasks": [],
                                 "decisions": [], "claims": [], "notes": [], "sources": [],
                                 "sources_more": False, "working_memory_more": False}
        if person_id:
            try:
                person = app.state.claims.entities.get(person_id)
            except EntityError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if person is None or person["kind"] != "person":
                raise HTTPException(status_code=404, detail="Die gewählte Person ist nicht verfügbar.")
            result["person"] = person
        if project_id:
            try:
                project = app.state.workspace.project(project_id)
            except WorkspaceError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            result["project"] = project.to_dict()
            result["tasks"] = [item.to_dict() for item in app.state.tasks.by_project(project_id)]
            decisions = (item.to_dict() for item in
                         entscheidungen.alle(app.state.store, knowledge=app.state.claims))
            result["decisions"] = [item for item in decisions
                                   if item["status"] == "active" and item["project_id"] == project_id]
            result["notes"] = [item.to_dict() for item in app.state.workspace.notes(project_id=project_id)]
        if not project_id and not person_id:
            return result
        references = ([f"project:{project_id}"] if project_id else []) + ([person_id] if person_id else [])
        # Dieselbe gezielte Auswahl wie in Akten, ohne Abschneiden am globalen
        # Listenlimit. Gemeinsame Personen-/Projektbelege nur einmal anzeigen.
        selected_claims = {item.id: item for reference in references
                           for item in app.state.claims.by_reference(reference)}
        result["claims"] = [item.to_dict() for item in
                            sorted(selected_claims.values(), key=lambda item: item.created_at, reverse=True)]
        # Belege zuerst, danach ausdrücklich zugeordnetes Rohmaterial. Kein
        # Namens-/Titelabgleich: Erwähnung ist weder Identität noch Beziehung.
        sources: dict[str, dict[str, Any]] = {}
        for claim in result["claims"]:
            for evidence in claim["evidence"]:
                episode_id = evidence["episode_id"]
                if episode_id in sources:
                    continue
                try:
                    episode = app.state.episodes.get(episode_id)
                except EpisodeError:
                    continue
                sources[episode_id] = {"episode": episode, "reason": "Beleg einer aktuellen Aussage"}
        for task in result["tasks"]:
            ref = task["provenance"].get("source_ref") or ""
            if ref.startswith("episode:"):
                episode_id = ref.removeprefix("episode:")
                try:
                    episode = app.state.episodes.get(episode_id)
                except EpisodeError:
                    continue
                sources.setdefault(episode_id, {"episode": episode, "reason": "Quelle einer offenen Aufgabe"})
        project_sources = app.state.episodes.by_project(project_id, limit=101) if project_id else []
        result["sources_more"] = len(project_sources) > 100
        for episode in project_sources[:100]:
            if episode.state is not EpisodeState.IGNORED and episode.kind is not EpisodeKind.SUMMARY:
                sources.setdefault(episode.id, {"episode": episode, "reason": "Dem Projekt zugeordnet"})
        # Ein Aufgabenverweis hebt den ausdrücklichen Quellenausschluss nicht auf.
        sources = {key: entry for key, entry in sources.items()
                   if entry["episode"].state is not EpisodeState.IGNORED}
        result["sources_more"] = result["sources_more"] or len(sources) > 100
        result["sources"] = [{**entry["episode"].to_dict(), "reason": entry["reason"],
                              "body": entry["episode"].body[:20000],
                              "truncated": len(entry["episode"].body) > 20000 or "source:truncated" in entry["episode"].tags}
                             for entry in list(sources.values())[:100]]
        if result["sources"]:
            from .working_memory_context import reports
            with app.state.conversation_lock:
                report = reports(app.state.episodes, app.state.claims,
                                 episode_ids=[item["id"] for item in result["sources"]])
            classified = {item["episode_id"]: item for item in report["items"]}
            result["working_memory_more"] = report["truncated"]
            for item in result["sources"]:
                selected = classified.get(item["id"])
                item["working_kinds"] = list(selected["kinds"]) if selected else []
        return result

    @app.get("/api/v1/morning-briefing", dependencies=guard)
    def morning_briefing(
        target_date: Annotated[date | None, Query(alias="date")] = None,
        client_timezone: Annotated[str | None, Query(alias="timezone", max_length=100)] = None,
        post: bool = True,
    ) -> dict[str, Any]:
        try:
            zone = ZoneInfo(client_timezone) if client_timezone else None
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Die Zeitzone ist nicht verfügbar.") from exc
        if zone is None:
            # Ohne Angabe gilt die eingestellte Zeitzone (Kingfisher und du), nicht die des Rechners oder Containers
            # (Fremdprobe 2, Befund 9: im Kopf stand „UTC“).
            from .model import user_timezone
            zone = user_timezone()
        current = datetime.now(zone) if zone else datetime.now().astimezone()
        target = target_date or current.date()
        from .logbuch_routes import zeilen as logbuch_zeilen
        from .wetter_routes import dienst as wetter_dienst
        # `post=false`: ohne Posteingang, damit Heute den Gruß sofort zeigt; die Oberfläche holt danach den Rest.
        return compose_morning(dashboard(days=1, post=post), now=current, target=target,
                               wetter=lambda: wetter_dienst(app).aktuell(), verlauf=logbuch_zeilen(app, current),
                               nutzername=str((app.state.settings.einrichtung or {}).get("name") or ""))

    @app.get("/api/v1/status", dependencies=guard)
    def kingfisher_status() -> dict[str, bool]:
        """Nur die Fähigkeit, die der kanonische Chatfluss braucht.

        Der Browser muss nicht wissen, welcher Anbieter oder welches Modell
        hinterlegt ist. Er braucht ausschließlich die ehrliche Antwort, ob
        eine Nachricht überhaupt an einen eingerichteten lokalen Agenten gehen
        kann. Ohne diesen Check würde der Composer eine nicht vorhandene
        Funktion anbieten und erst nach dem Absenden scheitern.
        """
        return {"chat": getattr(app.state.agent, "provider", None) is not None}

    @app.get("/api/v1/messages", dependencies=guard)
    def kingfisher_messages(limit: int = Query(default=30, ge=1, le=100), account_id: str | None = Query(default=None, max_length=200)) -> dict[str, Any]:
        """Lokale Posteingangszeilen, bewusst ohne Mailvolltexte oder Empfänger."""
        mail = getattr(app.state, "mail", None)
        if mail is None:
            return {
                "messages": [],
                "partial_failure": {
                    "code": "not_configured",
                    "section": "mail",
                    "message": "Noch kein Postfach verbunden.",
                },
            }
        if account_id is not None:
            if not isinstance(mail, MailCollection):
                raise HTTPException(404, 'Dieses Mailkonto ist nicht verbunden.')
            try:
                mail.reader_for(account_id)
            except Exception as exc:
                raise HTTPException(404, 'Dieses Mailkonto ist nicht verbunden.') from exc
        from .mail_anmeldung import Anmeldefehler
        from .postfach_lage import lage as postfach_lage, wer as postfach_wer
        host, name = postfach_wer(app, account_id)
        try:
            # Mit Wanduhr, und sofort, wenn das Postfach eben schon schwieg (Fremdprobe, Befund 14). Der Satz nennt
            # das Postfach („WEB.DE antwortet gerade nicht …“), nicht „den lokalen Posteingang“.
            messages = postfach_lage(app).lesen(
                f"konto:{account_id}" if account_id is not None else "alle",
                (lambda: mail.inbox(limit=limit, account_id=account_id)) if account_id is not None else (lambda: mail.inbox(limit=limit)),
                host=host, name=name, sekunden=POSTFACH_ZEITGRENZE)
        except Anmeldefehler as fehler:
            return {
                "messages": [],
                "partial_failure": {
                    "code": "unavailable",
                    "section": "mail",
                    "grund": fehler.grund,
                    "message": fehler.satz,
                    "ziel": "/settings#zugaenge",
                },
            }
        # Ein erfolgreicher Blick hinein: Danach heißt ein leeres Postfach „verbunden und leer“ (Fremdprobe 2, Befund 17).
        from .mail_stand import merke_gelesen
        konten = [account_id] if account_id is not None else [e.id for e in app.state.settings.mail_accounts if e.configured]
        merke_gelesen(app, {konto: sum(1 for m in messages if (m.account_id or konto) == konto) for konto in konten})
        from .model import user_timezone
        abgerufen_um = datetime.now(user_timezone() or timezone.utc).strftime("%H:%M")
        from copy import deepcopy
        from types import SimpleNamespace
        from .inbox_filter import classify_row
        with app.state.conversation_lock:
            filter_settings = SimpleNamespace(mail_filter=deepcopy(app.state.settings.mail_filter))
        return {
            # Die Uhrzeit des Abrufs in der Zeitzone des Nutzers, dieselbe wie im Satz zum Postfach (Befund 18).
            "abgerufen_um": abgerufen_um,
            "messages": [
                {
                    "id": message.uid,
                    "subject": message.subject,
                    "sender": message.sender,
                    "date": message.date.astimezone().isoformat() if message.date else None,
                    "preview": message.preview,
                    "unread": message.unread,
                    "source": message.account_label or None,
                    "account_id": message.account_id,
                    **classify_row(message, filter_settings),
                }
                for message in messages
            ],
            "partial_failure": {"code": "unavailable", "section": "mail", "message": "Einige Postfächer sind gerade nicht erreichbar. Die übrigen Nachrichten werden angezeigt."} if getattr(mail, "last_errors", {}) else None,
        }

    # -- Persistente Gespräche ------------------------------------------

    def _conversation_candidate_source(message: Any, candidate: Any,
                                       message_lookup: dict[str, Any]) -> bool:
        """A card can show its quote only while its exact user source is current."""
        source_message_id = message.metadata.get("memory_source_message_id")
        source_message = message_lookup.get(source_message_id)
        if source_message is None or source_message.role != "user":
            return False
        source = conversation_memory.find(app.state.episodes, message.conversation_id, source_message_id)
        if source is None or not conversation_memory.matches_message(
            source, message.conversation_id, source_message
        ):
            return False
        try:
            snapshot = app.state.episodes.support_snapshot(source.id)
        except Exception:
            return False
        return (snapshot.current() and any(
            evidence.episode_id == source.id
            and evidence.digest == source.digest
            and evidence.quote == source_message.content
            for evidence in candidate.evidence
        ))

    def _conversation_candidate_card(message: Any,
                                     message_lookup: dict[str, Any]) -> dict[str, Any] | None:
        """Löst nur eine in diesem Gespräch persistierte Vorschlagskarte auf.

        Der Vorschlag selbst bleibt die führende Quelle für seinen Zustand. Die
        Nachricht hält lediglich seine Position im Gespräch fest; dadurch
        überlebt die Karte Browser- und Container-Neustarts, ohne dass ein
        zweiter, veränderlicher Wissensbestand entsteht.
        """
        proposal_id = message.metadata.get("memory_candidate_id")
        if not isinstance(proposal_id, str):
            return None
        try:
            candidate = app.state.proposals.get(proposal_id)
        except ProposalError:
            return None
        if candidate.kind is not ProposalKind.KNOWLEDGE or not _conversation_candidate_source(
            message, candidate, message_lookup
        ):
            return None

        # Der Vorschlag bleibt die Quelle für seinen sichtbaren Entscheidungs-
        # stand. Die zugehörige Aussage wird dagegen jedes Mal frisch aus dem
        # Wissensbestand gelesen: Ein Widerruf oder die Invalidierung einer
        # Grundlage darf eine bereits gerenderte Karte nicht als aktuell
        # erscheinen lassen.
        claim = app.state.claims.by_proposal(candidate.id)
        claim_usable = (
            app.state.claims.is_usable(claim) if claim is not None else False
        )

        conflicts = (
            app.state.claims.conflicts_for(candidate)
            if candidate.state is ProposalState.PENDING
            else []
        )
        competing = (
            [
                item
                for item in app.state.knowledge_service.pending()
                if item.id != candidate.id
                and statements_conflict(item, candidate)
            ]
            if candidate.state is ProposalState.PENDING
            else []
        )
        return {
            "message_id": message.id,
            "candidate": candidate.to_dict(),
            "conflicts": [item.to_dict() for item in conflicts],
            "competing_count": len(competing),
            "source_message_id": message.metadata.get("memory_source_message_id"),
            "claim": claim.to_dict() if claim is not None else None,
            "claim_usable": claim_usable,
        }

    def _require_conversation_candidate(conversation_id: str, proposal_id: str) -> None:
        """Schützt die Gesprächsroute davor, fremde Vorschläge zu entscheiden."""
        messages = app.state.conversations.messages(conversation_id)
        message_lookup = {message.id: message for message in messages}
        for message in messages:
            if message.metadata.get("memory_candidate_id") == proposal_id:
                try:
                    candidate = app.state.proposals.get(proposal_id)
                except ProposalError as exc:
                    raise HTTPException(status_code=404, detail="Unbekannter Gedächtnisvorschlag") from exc
                if not _conversation_candidate_source(message, candidate, message_lookup):
                    raise HTTPException(status_code=409,
                        detail="Die Gesprächsgrundlage dieses Vorschlags wurde geändert oder ausgeschlossen.")
                return
        raise HTTPException(status_code=404, detail="Unbekannter Gedächtnisvorschlag")

    def _explicit_memory_request(message: str) -> bool:
        """Erkennt nur eine eindeutige persönliche Speicherabsicht.

        Das Modell kann den Tool-Aufruf vorschlagen, aber niemals diese Grenze
        aufheben. Bewusst eng: eine beiläufige Aussage wie „das sollte man sich
        merken" reicht nicht; die Nutzerzeile muss am Anfang selbst eine
        Merkbitte ausdrücken.
        """
        normalized = " ".join(message.casefold().split())
        return bool(re.match(r"^(bitte )?(merk(?:e)?(?: dir)?|speicher(?:e)? als gedächtnis)\b", normalized))

    def _create_conversation_memory_candidate(
        conversation_id: str,
        source: Any,
        *,
        subject_ref: str,
        predicate: str,
        value: str,
        statement: str,
        rationale: str = "",
        scope_ref: str | None = None,
        confidence: float | None = None,
        participants: list[str] | None = None,
        tags: list[str] | None = None,
        project_id: str | None = None,
    ) -> tuple[Any, bool]:
        """Erstellt den belegten Kandidaten, aber niemals schon einen Claim."""
        episode, _ = conversation_memory.capture(app.state.episodes, conversation_id, source)
        if episode.state is EpisodeState.IGNORED:
            raise ClaimError("Diese Gesprächsquelle wurde ausgeschlossen.")
        if participants or tags or project_id:
            episode = app.state.episodes.enrich_chat_source(
                episode.id, conversation_memory.source_ref(conversation_id, source.id),
                participants=participants, tags=tags, project_id=project_id,
            )
        return app.state.knowledge_service.propose(
            subject_ref=subject_ref,
            predicate=predicate,
            value=value,
            statement=statement,
            rationale=rationale,
            scope_ref=scope_ref,
            confidence=confidence,
            evidence=[Evidence(episode.id, source.content, episode.digest)],
            proposed_by=f"conversation:{conversation_id}",
        )

    def _draft_candidate_fields(draft: dict[str, Any]) -> dict[str, Any]:
        """Leitet sichere Referenzen aus einem Modellvorschlag ab.

        Ein Modell darf weder freie interne IDs erfinden noch nebenbei ein
        Projekt anlegen. Personen und Themen erhalten deterministische
        Referenzen; ein Projekt muss bereits in der lokalen Arbeitsablage
        existieren.
        """
        subject_type = str(draft.get("subject_type", "")).strip()
        label = str(draft.get("subject_label", "")).strip()
        predicate = str(draft.get("predicate", "")).strip()
        value = str(draft.get("value", "")).strip()
        statement = str(draft.get("statement", "")).strip()
        if not all((subject_type, label, predicate, value, statement)):
            raise ValueError("Der Gedächtnisvorschlag ist unvollständig.")

        project_id: str | None = None
        participants: list[str] = []
        tags: list[str] = []
        if subject_type == "person":
            subject_ref = graph.person_id(label)
            participants.append(label)
        elif subject_type == "topic":
            subject_ref = graph.topic_id(label)
            tags.append(label)
        elif subject_type == "project":
            project = app.state.workspace.find_project(label)
            if project is None:
                raise ValueError(
                    "Das genannte Projekt existiert lokal noch nicht; es wird nicht automatisch angelegt."
                )
            subject_ref = f"project:{project.id}"
            project_id = project.id
        else:
            raise ValueError("Der Vorschlag muss Person, bestehendes Projekt oder Thema betreffen.")

        scope_ref: str | None = None
        scope_label = str(draft.get("scope_project", "")).strip()
        if scope_label:
            scope_project = app.state.workspace.find_project(scope_label)
            if scope_project is None:
                raise ValueError(
                    "Der genannte Projektkontext existiert lokal noch nicht."
                )
            scope_ref = scope_project.id
            project_id = project_id or scope_project.id

        confidence = draft.get("confidence")
        if confidence is not None and (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not 0 <= float(confidence) <= 1
        ):
            raise ValueError("Die Sicherheit des Vorschlags muss zwischen 0 und 1 liegen.")
        return {
            "subject_ref": subject_ref,
            "predicate": predicate,
            "value": value,
            "statement": statement,
            "rationale": str(draft.get("rationale", "")).strip(),
            "scope_ref": scope_ref,
            "confidence": float(confidence) if confidence is not None else None,
            "participants": participants,
            "tags": tags,
            "project_id": project_id,
        }

    def _conversation_lineages(messages: list[Any]) -> dict[str, list[dict[str, str]]]:
        """Record the user sources a displayed/modelled turn may contain."""
        from .mail_reply_suggestions import sources_eligible
        lineages: dict[str, list[dict[str, str]]] = {}
        prior: dict[str, dict[str, str]] = {}
        legacy_changed: dict[str, bool] = {}
        reply_proofs: dict[str, list[dict]] = {}
        for message in messages:
            if message.role == "user":
                reply_context = message.metadata.get("mail_reply_context")
                if reply_context:
                    for identifier in reply_context.get("source_ids", []):
                        if isinstance(identifier, str):
                            reply_proofs.setdefault(identifier, []).append(reply_context)
                    refs = reply_context.get("conversation_source_lineage", [])
                    if not sources_eligible(app, reply_context):
                        refs = [{"episode_id": "missing", "fingerprint": "invalid"}]
                else:
                    source = conversation_memory.find(app.state.episodes, message.conversation_id, message.id)
                    if source is not None:
                        try:
                            refs = [conversation_memory.stamp(app.state.episodes, source.id)
                                    if conversation_memory.matches_message(source, message.conversation_id, message)
                                    else {"episode_id": source.id, "fingerprint": "invalid"}]
                        except Exception:
                            refs = [{"episode_id": source.id, "fingerprint": "invalid"}]
                    elif message.metadata.get("source_capture_expected"):
                        refs = [{"episode_id": "missing", "fingerprint": "invalid"}]
                    else:
                        refs = []
                prior.update({item["episode_id"]: item for item in refs})
            else:
                reply_context = message.metadata.get("mail_reply_context")
                if reply_context:
                    refs = reply_context.get("conversation_source_lineage", [])
                    if not sources_eligible(app, reply_context):
                        refs = [{"episode_id": "missing", "fingerprint": "invalid"}]
                else:
                    stored = message.metadata.get("conversation_source_lineage")
                    if isinstance(stored, list):
                        refs = [item for item in stored if isinstance(item, dict)
                                and isinstance(item.get("episode_id"), str)
                                and isinstance(item.get("fingerprint"), str)]
                    else:
                        # Older assistant turns have no frozen source stamp. Once
                        # a source was ignored/reopened or otherwise changed, a
                        # fresh stamp would revive their old text and approvals.
                        refs = []
                        for item in prior.values():
                            identifier = item["episode_id"]
                            if identifier not in legacy_changed:
                                try:
                                    legacy_changed[identifier] = (
                                        app.state.episodes.support_snapshot(identifier).generation > 0)
                                except Exception:
                                    legacy_changed[identifier] = True
                            refs.append({"episode_id": identifier, "fingerprint": "legacy-unbound"}
                                        if legacy_changed[identifier] else item)
                    if any(not sources_eligible(app, proof)
                           for ref in refs for proof in reply_proofs.get(ref["episode_id"], [])):
                        refs = [{"episode_id": "missing", "fingerprint": "invalid"}]
            lineages[message.id] = refs
        return lineages

    def _conversation_title(conversation: Any, messages: list[Any],
                            lineages: dict[str, list[dict[str, str]]],
                            validity_cache: dict | None = None) -> dict[str, Any]:
        value = conversation.to_dict()
        for message in reversed(messages):
            if (message.role == "user" and message.metadata.get("generated_conversation_title")
                    and value["title"] == message.content[:60].rstrip()):
                if not conversation_memory.lineage_valid(app.state.episodes, lineages[message.id], validity_cache):
                    value["title"] = "Gespräch mit geänderter oder ausgeschlossener Quelle"
                break
        return value

    def _conversation_actions(messages: list[Any],
                              lineages: dict[str, list[dict[str, str]]] | None = None,
                              validity_cache: dict | None = None) -> list[dict[str, Any]]:
        policy = getattr(app.state.agent, "policy", None)
        pending = {item.id for item in policy.pending()} if policy is not None else set()
        outcomes = {message.metadata["resolved_approval_id"]: message.metadata.get("approval_outcome", "unknown")
                    for message in messages if "resolved_approval_id" in message.metadata}
        lineages = lineages or _conversation_lineages(messages)
        actions = []
        for message in messages:
            if message.role != "assistant":
                continue
            valid = conversation_memory.lineage_valid(app.state.episodes, lineages[message.id], validity_cache)
            for approval in message.metadata.get("approvals", []):
                if not isinstance(approval, dict) or "id" not in approval:
                    continue
                action = {**approval, "message_id": message.id,
                          "state": outcomes.get(approval["id"], "pending" if approval["id"] in pending else "expired")}
                if not valid:
                    action.update(dry_run="Grundlage dieser Freigabe geändert oder ausgeschlossen.",
                                  arguments={}, confirmation_phrase=None, reasons=[])
                    if action["state"] == "pending":
                        action["state"] = "expired"
                context = message.metadata.get("mail_reply_context")
                if context:
                    from .mail_reply_suggestions import context_active
                    if not context_active(app, context):
                        action.update(dry_run="Quellenbezug geändert. Bitte neuen Vorschlag erstellen.",
                                      arguments={}, confirmation_phrase=None, reasons=[])
                        if action["state"] == "pending":
                            action["state"] = "expired"
                actions.append(action)
        return actions

    def _conversation_payload(conversation_id: str) -> dict[str, Any]:
        # Keep the conversation, proposal and claim reads together. In
        # particular, a card must not combine a pre-retraction claim with a
        # post-retraction usability result (or vice versa).
        with app.state.conversation_lock:
            conversation = app.state.conversations.get(conversation_id)
            if conversation is None:
                raise HTTPException(status_code=404, detail="Unbekanntes Gespräch")
            messages = app.state.conversations.messages(conversation_id)
            message_lookup = {message.id: message for message in messages}
            lineages = _conversation_lineages(messages)
            validity_cache = {}
            visible_messages = [message for message in messages
                if conversation_memory.lineage_valid(app.state.episodes, lineages[message.id], validity_cache)]
            context = next(
                (
                    message.metadata.get("context")
                    for message in reversed(visible_messages)
                    if message.role == "assistant"
                    and isinstance(message.metadata.get("context"), dict)
                    and isinstance(message.metadata["context"].get("items"), list)
                ),
                {"query": "", "generated_at": None, "items": [], "withheld_count": 0},
            )
            # Stored assistant context is a historical record, but the
            # conversation view must not continue presenting a claim that has
            # since been retracted or invalidated through a dependency. Keep
            # all other provenance and historical messages intact.
            current_context = dict(context)
            current_items = context.get("items")
            if isinstance(current_items, list):
                from . import model as context_model
                context_at = context_model.now()
                from .self_model_basis import FrozenBuild
                basis_build = FrozenBuild(app.state.store, at=context_at,
                    support_build=EpisodeSupportResolver(app.state.proposals, app.state.episodes).build(
                        at=context_at, local=True, max_sensitivity=Sensitivity.SPECIAL_CATEGORY),
                                          max_sensitivity=context_model.Sensitivity.SPECIAL_CATEGORY)
                from .knowledge_render import KnowledgeInputBuild
                from . import knowledge_history
                knowledge_build = KnowledgeInputBuild(app.state.claims, app.state.episodes.support_snapshot, at=context_at)
                visible_items: list[Any] = []
                for item in current_items:
                    if not isinstance(item, dict):
                        continue
                    assertion_id = item.get("assertion_id")
                    if isinstance(assertion_id, str) and assertion_id.startswith("claim:"):
                        entries = knowledge_history.from_items([item])
                        if (entries is None
                                or not knowledge_history.available(entries, app.state.claims, build=knowledge_build)
                                or app.state.knowledge_service.answer_conflict_status(list(entries)) != 'clear'):
                            continue
                    else:
                        from . import self_model_history
                        profile = self_model_history.from_items([item])
                        if profile is None or not self_model_history.available(profile, app.state.store, at=context_at, build=basis_build):
                            continue
                    visible_items.append(item)
                current_context["items"] = visible_items
            current_context["memory_revision"] = app.state.claims.revision
            from .source_answers import project_message
            from . import knowledge_answer_view
            projected = []
            resolved_source_turns = 0
            resolved_knowledge_turns = 0
            mappen_neu, mappen_memo = 0, {}
            # Bound original-source reads when opening a long conversation.
            # Older references stay stored and neutral; no stale copied quotes.
            for message in reversed(messages):
                value = message.to_dict()
                if not conversation_memory.lineage_valid(app.state.episodes, lineages[message.id], validity_cache):
                    value["content"] = "Grundlage geändert oder ausgeschlossen; dieser Gesprächsteil wird nicht mehr verwendet."
                    value["metadata"] = {}
                    projected.append(value)
                    continue
                if message.role == "user" and lineages[message.id]:
                    value["metadata"] = dict(value["metadata"])
                    value["metadata"]["context"] = {
                        **value["metadata"].get("context", {}),
                        "source_links": [{"episode_id": source["episode_id"],
                                          "label": "Rohquelle ansehen" if message.metadata.get("mail_reply_context") else EIGENE_FRAGE_ANSEHEN,
                                          "automatic_memory": not bool(message.metadata.get("mail_reply_context"))}
                                         for source in lineages[message.id]],
                    }
                stored_context = message.metadata.get('context')
                if (message.role == 'assistant' and isinstance(stored_context, dict)
                        and 'source_answer' in stored_context):
                    value = project_message(value, app.state.episodes, app.state.claims,
                                            resolve=resolved_source_turns < 20)
                    resolved_source_turns += 1
                elif (message.role == 'assistant' and isinstance(stored_context, dict)
                        and 'working_answer' in stored_context):
                    from .working_memory_answers import project_message as project_working
                    value = project_working(value, app.state.episodes, app.state.claims,
                                            resolve=resolved_source_turns < 20,
                                            conflict_status=app.state.knowledge_service.answer_conflict_status)
                    resolved_source_turns += 1
                elif (message.role == 'assistant' and isinstance(stored_context, dict)
                        and 'mappe_answer' in stored_context):
                    # Die Mappe ist eine Ansicht, kein Stand von damals: Die
                    # jüngsten werden beim Anzeigen neu berechnet, jedes Projekt
                    # nur einmal je Aufruf; ältere bieten „neu fragen“ an.
                    stored = stored_context['mappe_answer']
                    key = stored.get('id') if isinstance(stored, dict) else None
                    neu_berechnet = mappen_neu < 5
                    if neu_berechnet:
                        mappen_neu += 1
                        if key not in mappen_memo:
                            mappen_memo[key] = app.state.agent.render_mappe(stored)
                        rendered = mappen_memo[key]
                    else:
                        rendered = None
                    current = {k: v for k, v in stored_context.items() if k != 'mappe_answer'}
                    if isinstance(stored, dict):
                        current['mappe_answer'] = {k: stored.get(k) for k in ('version', 'kind', 'id', 'label', 'query')}
                    if rendered is None:
                        value["content"] = ("Diese Mappe ist nicht mehr verfügbar." if neu_berechnet
                                            else "Älterer Stand der Dinge: Bitte erneut danach fragen.")
                        current['source_links'] = []
                        current['answer_contract'] = {**current.get('answer_contract', {}), 'status': 'mappe_unavailable'}
                        query = stored.get('query') if isinstance(stored, dict) else None
                        if isinstance(query, str) and query.strip():
                            current['original_question'] = query
                            current['refresh_available'] = True
                    else:
                        value["content"], current['source_links'] = rendered
                    value["metadata"] = {**value["metadata"], "context": current}
                elif (message.role == 'assistant' and isinstance(stored_context, dict)
                        and 'meaning_choice' in stored_context):
                    from .bedeutungen import meaning_choice_current
                    if not meaning_choice_current(stored_context['meaning_choice'], app.state.episodes):
                        # Die Bedeutungen stammen aus Quellen, die nicht mehr
                        # gelten: nichts davon bleibt wörtlich stehen.
                        value["content"] = "Diese Rückfrage ist nicht mehr aktuell."
                        outdated = {key: item for key, item in stored_context.items()
                                    if key not in {'meaning_choice', 'clarification_choices'}}
                        outdated['answer_contract'] = {**outdated.get('answer_contract', {}),
                                                       'status': 'meaning_outdated'}
                        query = stored_context['meaning_choice'].get('query') \
                            if isinstance(stored_context['meaning_choice'], dict) else None
                        if isinstance(query, str) and query.strip():
                            outdated['original_question'] = query
                            outdated['refresh_available'] = True
                        value["metadata"] = {**value["metadata"], "context": outdated}
                elif knowledge_answer_view.applies(value):
                    value = knowledge_answer_view.project_message(value,
                        app.state.claims, app.state.episodes,
                        app.state.knowledge_service.answer_conflict_status,
                        resolve=resolved_knowledge_turns < 20)
                    resolved_knowledge_turns += 1
                projected.append(value)
            projected.reverse()
            latest_context = next((item['metadata']['context'] for item in reversed(projected)
                if item.get('role') == 'assistant'
                and isinstance(item.get('metadata', {}).get('context'), dict)
                and isinstance(item['metadata']['context'].get('items'), list)), {})
            if latest_context.get('memory_answer_withheld'):
                current_context = latest_context
            if ('source_answer' in current_context or 'working_answer' in current_context
                    or 'mappe_answer' in current_context):
                current_context = dict(next((item['metadata']['context'] for item in reversed(projected)
                    if item.get('role') == 'assistant'
                    and isinstance(item.get('metadata', {}).get('context'), dict)
                    and ('source_answer' in item['metadata']['context']
                         or 'working_answer' in item['metadata']['context']
                         or 'mappe_answer' in item['metadata']['context'])), current_context))
                current_context['memory_revision'] = app.state.claims.revision
            return {
                "conversation": _conversation_title(conversation, messages, lineages, validity_cache),
                "messages": projected,
                "context": current_context,
                "action_requests": _conversation_actions(messages, lineages, validity_cache),
                "memory_candidates": [
                    card
                    for message in messages
                    if (card := _conversation_candidate_card(message, message_lookup)) is not None
                ],
            }

    @app.post("/api/v1/conversations", dependencies=guard, status_code=201)
    def create_conversation(body: ConversationIn) -> dict[str, Any]:
        conversation = app.state.conversations.create(body.title)
        return _conversation_payload(conversation.id)

    @app.get("/api/v1/conversations", dependencies=guard)
    def list_conversations(limit: int = Query(default=100, ge=1, le=200)) -> dict[str, Any]:
        """Lokale Gesprächshistorie ohne Volltexte aller Unterhaltungen."""
        with app.state.conversation_lock:
            summaries = []
            for summary in app.state.conversations.list(limit):
                messages = app.state.conversations.messages(summary.id)
                lineages = _conversation_lineages(messages)
                validity_cache = {}
                value = summary.to_dict()
                value["title"] = _conversation_title(summary, messages, lineages, validity_cache)["title"]
                if messages and not conversation_memory.lineage_valid(
                    app.state.episodes, lineages[messages[-1].id], validity_cache
                ):
                    value["preview"] = "Grundlage geändert oder ausgeschlossen; Gesprächsteil nicht mehr verwendet."
                summaries.append(value)
            return {"conversations": summaries}

    @app.get("/api/v1/conversations/latest", dependencies=guard)
    def get_latest_conversation() -> dict[str, Any]:
        """Gibt genau einen dauerhaften Navigationseinstieg zurück.

        Die Navigation darf nicht von `localStorage` abhängen: Gespräche
        gehören SQLite und bleiben auch nach Browser-Reset erreichbar. Eine
        vollständige Gesprächsliste ist dafür nicht nötig und wird erst mit
        ihrem eigenen genehmigten Screen eingeführt.
        """
        conversation = app.state.conversations.latest()
        if conversation is None:
            return {"conversation": None}
        with app.state.conversation_lock:
            messages = app.state.conversations.messages(conversation.id)
            return {"conversation": _conversation_title(conversation, messages,
                _conversation_lineages(messages))}

    # Der Rückkanal (rueckmeldung_routes.py) meldet, was der Nutzer gelesen hat, also die Ansicht, nicht den Rohspeicher.
    app.state.gespraech_ansicht = _conversation_payload
    @app.get("/api/v1/conversations/{conversation_id}", dependencies=guard)
    def get_conversation(conversation_id: str) -> dict[str, Any]:
        return _conversation_payload(conversation_id)

    @app.post("/api/v1/conversations/{conversation_id}/approvals/{approval_id}", dependencies=guard)
    def resolve_conversation_action(conversation_id: str, approval_id: str, body: ResolveIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            if app.state.conversations.get(conversation_id) is None:
                raise HTTPException(404, "Unbekanntes Gespräch")
            messages = app.state.conversations.messages(conversation_id)
            actions = _conversation_actions(messages)
            action = next((item for item in actions if item["id"] == approval_id), None)
            if action is None:
                raise HTTPException(404, "Diese Freigabe gehört nicht zu diesem Gespräch.")
            action_message = next(item for item in messages if item.id == action["message_id"])
            context = action_message.metadata.get("mail_reply_context")
            if context and not body.granted:
                turn = _cancel_bound_mail_reply(approval_id)
                app.state.conversations.add_message(conversation_id, "assistant",
                    turn.reply, metadata={"resolved_approval_id": approval_id,
                                          "approval_outcome": "rejected",
                                          "context": turn.context,
                                          "conversation_source_lineage": []})
            else:
                if action["state"] != "pending":
                    raise HTTPException(409, "Diese Freigabe ist nicht mehr offen. Bitte einen neuen Vorschlag anfordern.")
                if context:
                    from .mail_reply_suggestions import validate_context
                    validate_context(app, context["token"])
                action_lineage = _conversation_lineages(messages)[action_message.id]
                action_history = _current_conversation_history(conversation_id)
                resolved_sources = {item["episode_id"]: item for item in action_lineage}
                for item in action_history:
                    resolved_sources.update({source["episode_id"]: source
                        for source in item.get("conversation_source_lineage", [])})
                resolved_lineage = list(resolved_sources.values())
                app.state.agent.load_history(action_history)
                execution = app.state.mail_reply_execution
                try:
                    if context:
                        execution.token = context["token"]
                        execution.arguments = action["arguments"]
                    turn = app.state.agent.resolve(approval_id, body.granted, body.confirmation)
                except PolicyError as exc:
                    raise HTTPException(409, str(exc)) from exc
                except Exception:
                    app.state.conversations.add_message(conversation_id, "assistant",
                        "Die Aktion konnte nicht abschließend bestätigt werden. Bitte das Ergebnis prüfen, bevor du sie erneut anforderst.",
                        status="error", metadata={"resolved_approval_id": approval_id, "approval_outcome": "unknown",
                                                   "conversation_source_lineage": resolved_lineage})
                else:
                    app.state.conversations.add_message(conversation_id, "assistant",
                        turn.reply or ("Freigabe verarbeitet." if body.granted else "Abgelehnt. Nichts ausgeführt."),
                        metadata={"resolved_approval_id": approval_id,
                                  "approval_outcome": turn.approval_outcome or "unknown",
                                  "approvals": [item.to_dict() for item in turn.approvals],
                                  "notices": turn.notices, "used_tools": turn.used_tools,
                                  "context": turn.context,
                                  "conversation_source_lineage": resolved_lineage})
                finally:
                    if context:
                        del execution.token
                        del execution.arguments
        return _conversation_payload(conversation_id)

    def _current_conversation_history(conversation_id: str) -> list[dict[str, Any]]:
        revision = app.state.claims.revision
        messages = app.state.conversations.messages(conversation_id)
        lineages = _conversation_lineages(messages)
        validity_cache = {}
        start = 0
        for index, item in enumerate(messages):
            if item.role == "assistant":
                context = item.metadata.get("context") or {}
                if context.get("memory_revision", 0) != revision:
                    start = index + 1
        return [{"role": item.role, "content": item.content,
                 "context": item.metadata.get("context"),
                 "conversation_source_lineage": lineages[item.id]}
                for item in messages[start:]
                if item.role in {"user", "assistant"} and item.status == "complete"
                and not (item.role == "user" and item.metadata.get("mail_reply_context"))
                and conversation_memory.lineage_valid(app.state.episodes, lineages[item.id], validity_cache)]

    def _memory_conversation_turn(message, last, *, new_question=False, anfrage=None):
        pending = (last.metadata.get('context') if last is not None
                   and last.role == 'assistant' and last.status == 'complete' else None)
        from .memory_routing import is_working_followup
        if (not new_question and is_working_followup(message, pending)
                and isinstance(pending.get('mappe_answer'), dict)):
            mappe = pending['mappe_answer']
            scope = app.state.agent.project_scope(mappe['id'], mappe.get('label') or mappe['id'])
            return app.state.agent.answer_memory(mappe['query'] + '\nNachfrage des Nutzers: ' + message,
                                                 retrieval_query=mappe['query'], meaning_scope=scope)
        if (not new_question and is_working_followup(message, pending)):
            from .working_memory_answers import lookup_of
            retrieval_query = lookup_of(pending['working_answer'])
            selector_question = retrieval_query + '\nNachfrage des Nutzers: ' + message
            return app.state.agent.answer_memory(selector_question, retrieval_query=retrieval_query,
                                                 meaning_scope=pending['working_answer'].get('meaning_scope'))
        if (not new_question and isinstance(pending, dict)
                and isinstance(pending.get('working_answer'), dict)
                and pending.get('answer_contract', {}).get('status') == 'working_unclear'):
            question = pending['working_answer'].get('query', '')
            return app.state.agent.answer_memory(question + '\nPräzisierung des Nutzers: ' + message,
                                                 meaning_scope=pending['working_answer'].get('meaning_scope'))
        if (not new_question and isinstance(pending, dict)
                and pending.get('answer_mode') == 'memory_evidence'
                and isinstance(pending.get('answer_contract'), dict)
                and pending['answer_contract'].get('status') == 'clarify'):
            return app.state.agent.continue_memory(message, pending)
        return app.state.agent.answer_memory(message, **({'anfrage': anfrage} if anfrage is not None else {}))

    @app.post(
        "/api/v1/conversations/{conversation_id}/messages",
        dependencies=guard,
        status_code=201,
    )
    def send_conversation_message(
        conversation_id: str, body: ConversationMessageIn
    ) -> dict[str, Any]:
        if app.state.conversations.get(conversation_id) is None:
            raise HTTPException(status_code=404, detail="Unbekanntes Gespräch")

        # Der bestehende Agent verwaltet genau einen Verlauf. Dieser Lock lädt
        # für jeden Aufruf den zugehörigen SQLite-Verlauf und verhindert, dass
        # zwei Gespräche ihre Kontexte im Threadpool vermischen.
        with app.state.conversation_lock, working_memory_semantic_runtime.request(app):
            history = _current_conversation_history(conversation_id)
            previous = app.state.conversations.messages(conversation_id)
            previous_lineages = _conversation_lineages(previous)
            validity_cache = {}
            last = next((item for item in reversed(previous)
                if conversation_memory.lineage_valid(app.state.episodes, previous_lineages[item.id], validity_cache)), None)
            mode, fresh_question = body.answer_mode, body.new_question
            choice_answer = None
            date_answer = None
            if body.clarification_choice is not None and body.clarification_date is not None:
                raise HTTPException(422, "Bitte entweder eine Auswahl oder ein Datum senden.")
            if body.clarification_date is not None:
                from .working_memory_answers import needs_source_date
                pending = (last.metadata.get('context') if last is not None
                           and last.role == 'assistant' and last.status == 'complete' else None)
                date_answer = pending.get('working_answer') if isinstance(pending, dict) else None
                expected = f"Die Nachricht stammt vom {body.clarification_date.strftime('%d.%m.%Y')}."
                if (not needs_source_date(date_answer) or body.message.strip() != expected
                        or body.clarification_date > datetime.now(timezone.utc).date() + timedelta(days=1)):
                    raise HTTPException(409, "Diese Angabe passt nicht mehr zur Rückfrage. Bitte frage erneut.")
                mode, fresh_question = 'memory_evidence', False
            meaning_pending = None
            if body.clarification_choice is not None:
                from .working_memory_answers import choices as working_choices
                pending = (last.metadata.get('context') if last is not None
                           and last.role == 'assistant' and last.status == 'complete' else None)
                choice_answer = pending.get('working_answer') if isinstance(pending, dict) else None
                meaning_pending = (pending.get('meaning_choice') if isinstance(pending, dict)
                                   and choice_answer is None else None)
                from .bedeutungen import meaning_choice_current
                if meaning_pending is not None and not meaning_choice_current(meaning_pending, app.state.episodes):
                    raise HTTPException(409, "Diese Auswahl ist nicht mehr aktuell. Bitte frage erneut.")
                options = (working_choices(choice_answer, app.state.episodes) if choice_answer else
                           meaning_pending.get('options', []) if isinstance(meaning_pending, dict) else [])
                if (not isinstance(options, list) or body.clarification_choice >= len(options)
                        or not isinstance(options[body.clarification_choice], dict)
                        or options[body.clarification_choice].get('label') != body.message.strip()):
                    raise HTTPException(409, "Diese Auswahl ist nicht mehr aktuell. Bitte frage erneut.")
                mode, fresh_question = 'memory_evidence', False
            anfrage = None
            if mode == 'auto':
                from .memory_routing import route
                previous_context = (last.metadata.get('context') if last is not None
                    and last.role == 'assistant' and last.status == 'complete' else None)
                from .working_memory_store import WorkingMemoryStore
                from .source_answers import literal_query
                from .frage import rueckfall
                literal_lookup = (literal_query(body.message) is not None and
                    route(body.message, previous_context, new_question=body.new_question) == 'memory_evidence')
                # Die Frage in eine strukturierte Anfrage übersetzen (Modell der Rolle
                # „frage“, sonst Rückfall); sie gilt für Weg und Antwort dieser Nachricht.
                # Die Umschreibungen gehören zur Suche: „Catering“ findet „Verpflegung“.
                anfrage = rueckfall(body.message) if literal_lookup else _frage_verstehen(app, body.message)
                working_available = bool(WorkingMemoryStore(app.state.episodes).search(
                    anfrage.suchanfrage(body.message), limit=1)['refs'])
                if not working_available:
                    # „Was gibt es Neues zu Mainz?“ trifft kein Wort einer
                    # Quelle, aber die dem Projekt zugeordneten Quellen.
                    working_available = _project_sources_available(app, body.message)
                if not working_available and anfrage.absicht == 'ueberblick':
                    # „Was ist mit Mainz los?“ kennt der Bestand, auch wenn
                    # noch nichts eingeordnet ist: Die erste Suchstufe klärt
                    # dann, was gemeint ist. Andere Fragen zu roh vorliegenden
                    # Quellen bleiben beim Chat mit Werkzeugen, wie bisher.
                    from .frage_weg import bezug_im_bestand
                    working_available = bezug_im_bestand(anfrage, app.state.episodes, _project_directory(app)())
                if not working_available and not literal_lookup:
                    # Umschriebene Fragen haben keine gemeinsamen Wörter mit der Quelle.
                    from .working_memory_answers import is_question
                    from . import working_memory_semantic
                    if hasattr(app.state, 'semantic_search'):
                        meaning = working_memory_semantic_runtime.search(app)
                    else:  # explicit standalone diagnostic compatibility
                        _rollen = rollen_von(app)
                        meaning = (working_memory_semantic.for_provider(
                            _rollen.provider('einbettung'), _rollen.einbettung_modell())
                            if 'einbettung' in _rollen.wahlen
                            else working_memory_semantic.for_provider(_rollen.provider('einbettung')))
                    working_available = bool(meaning is not None and is_question(body.message)
                                             and meaning.search(app.state.episodes, body.message, 1))
                decision = route(body.message, previous_context, new_question=body.new_question,
                                 working_available=working_available, anfrage=anfrage)
                mode = 'chat' if decision == 'chat' else 'memory_evidence'
                fresh_question = decision != 'memory_followup'
            last_context = last.metadata.get('context') if last is not None and last.role == 'assistant' else None
            followup = (mode == 'memory_evidence' and not fresh_question
                and isinstance(last_context, dict)
                and isinstance(last_context.get('answer_contract'), dict)
                and last_context['answer_contract'].get('status') in {'clarify', 'working_unclear'})
            # Ein Klick auf eine Auswahl ist keine neue Aussage des Nutzers.
            clicked = choice_answer is not None or meaning_pending is not None
            lookup_only = ((mode == 'memory_evidence' and not followup)
                           or clicked or date_answer is not None)
            source = app.state.conversations.add_message(conversation_id, "user", body.message,
                metadata={'answer_mode': mode, 'new_question': fresh_question,
                          'source_capture_expected': True,
                          'memory_lookup_only': lookup_only,
                          **({'clarification_choice': body.clarification_choice}
                             if clicked else {}),
                          **({'clarification_date': body.clarification_date.isoformat()}
                             if date_answer is not None else {})})
            source_episode, created = conversation_memory.capture(
                app.state.episodes, conversation_id, source, lookup_only=lookup_only)
            if created and not lookup_only and app.state.settings.schedule.enabled and app.state.settings.schedule.with_model:
                scheduler = getattr(app.state, 'scheduler', None)
                if scheduler is not None and getattr(rollen_von(app).provider('hintergrund'), 'is_local', False):
                    scheduler.request_working_memory(source_episode.id)
            input_sources = {entry["episode_id"]: entry
                for item in history for entry in item.get("conversation_source_lineage", [])}
            source_stamp = conversation_memory.stamp(app.state.episodes, source_episode.id)
            source_captured = conversation_memory.usable(app.state.episodes, source_stamp)
            input_sources[source_episode.id] = source_stamp
            if mode == 'memory_evidence' and last is not None:
                input_sources.update({entry["episode_id"]: entry for entry in previous_lineages[last.id]})
            try:
                if mode == 'memory_evidence':
                    routing = None
                    execution_agent = app.state.agent
                    turn = (app.state.agent.answer_working_choice(choice_answer, body.clarification_choice)
                            if choice_answer is not None else
                            app.state.agent.answer_meaning_choice(meaning_pending, body.clarification_choice)
                            if meaning_pending is not None else
                            app.state.agent.answer_working_date(date_answer, body.clarification_date)
                            if date_answer is not None else None)
                    stale = turn is None and (clicked or date_answer is not None)
                    if turn is None and meaning_pending is not None:
                        # Die ursprüngliche Frage neu stellen, nicht die Beschriftung des Knopfes.
                        turn = app.state.agent.answer_memory(meaning_pending['query'])
                    if turn is None:
                        turn = _memory_conversation_turn(body.message, last, new_question=fresh_question,
                                                         anfrage=anfrage)
                    if stale:
                        # Die Quellen haben sich seit der Rückfrage geändert: Die
                        # ursprüngliche Frage wurde samt Auswahl neu beantwortet.
                        # Das wird gesagt, statt still eine andere Antwort zu zeigen.
                        from .working_memory_answers import REFRESHED
                        turn.context = {**turn.context, 'refreshed_after_change': True}
                        turn.reply = REFRESHED + '\n\n' + turn.reply
                else:
                    from .routing_runtime import scoped_agent
                    execution_agent, routing = scoped_agent(app, body.message)
                    execution_agent.load_history(history if not routing or routing['history_shared'] else [])
                    turn = execution_agent.send(
                        body.message, conversation_source_captured=source_captured)
                if routing:
                    turn.context['routing'] = routing
                    app.state.audit.record('agent_handoff', 'read', 'notify', 'executed',
                        {'from': routing['from'], 'to': routing['to'],
                         'context_ids': [item.get('assertion_id') for item in turn.context.get('items', [])],
                         'memory_revision': turn.context.get('memory_revision'),
                         'allowed_tools': routing['allowed_tools']}, model=execution_agent.provider.model)
                assistant_message = app.state.conversations.add_message(
                    conversation_id,
                    "assistant",
                    turn.reply or "Ich habe darauf gerade keine Antwort.",
                    metadata={
                        "approvals": [approval.to_dict() for approval in turn.approvals],
                        "notices": turn.notices,
                        "used_tools": turn.used_tools,
                        "context": turn.context,
                        "conversation_source_lineage": list(input_sources.values()),
                    },
                )
                # Das Modell darf keine Gedächtnisaktion still auslösen. Nur
                # ein nachweislich ausdrückliches „Merke …" in genau dieser
                # Nutzerzeile darf seinen strukturierten Entwurf in den
                # bestehenden Kandidatenpfad überführen.
                if _explicit_memory_request(source.content):
                    same_turn_messages = [assistant_message.id]
                    for draft in getattr(turn, "memory_candidate_drafts", []):
                        try:
                            fields = _draft_candidate_fields(draft)
                            candidate, created = _create_conversation_memory_candidate(
                                conversation_id, source, **fields
                            )
                        except (ClaimError, ProposalError, EpisodeError, ValueError) as exc:
                            app.state.conversations.add_message(
                                conversation_id,
                                "assistant",
                                f"Ich konnte dafür keinen Gedächtnisvorschlag vorbereiten: {exc}",
                                # Ein Hinweis des Programms, keine Antwort: ohne „Stimmt nicht?“ (Fremdprobe 2, Befund 14).
                                metadata={"systemhinweis": True},
                            )
                            continue
                        if created:
                            candidate_notice = app.state.conversations.add_message(
                                conversation_id,
                                "assistant",
                                "Ich habe einen Gedächtnisvorschlag vorbereitet. Bitte bestätige ihn nur, wenn er stimmt.",
                                metadata={
                                    "memory_candidate_id": candidate.id,
                                    "memory_source_message_id": source.id,
                                    "conversation_source_lineage": list(input_sources.values()),
                                },
                            )
                            same_turn_messages.append(candidate_notice.id)
                    # Explicit Merke may add person/topic/project hints to
                    # this same source after the model replied. Its text did
                    # not change; refresh only replies made in this locked turn.
                    input_sources[source_episode.id] = conversation_memory.stamp(
                        app.state.episodes, source_episode.id)
                    for message_id in same_turn_messages:
                        app.state.conversations.replace_source_lineage(
                            message_id, list(input_sources.values()))
            except Exception:  # noqa: BLE001 - Fehler bleibt lokal und sichtbar
                app.state.conversations.add_message(
                    conversation_id,
                    "assistant",
                    "Die Antwort konnte gerade nicht erstellt werden.",
                    status="error",
                    metadata={"conversation_source_lineage": list(input_sources.values())},
                )
        return _conversation_payload(conversation_id)

    @app.post(
        "/api/v1/conversations/{conversation_id}/memory-candidates",
        dependencies=guard,
        status_code=201,
    )
    def propose_conversation_memory_candidate(
        conversation_id: str, body: ConversationMemoryCandidateIn
    ) -> dict[str, Any]:
        """Hängt einen expliziten, belegten Vorschlag an ein Gespräch.

        Kein normaler Chat-POST ruft diese Route auf. Erst ein späterer,
        ausdrücklich gestalteter Gesprächsablauf darf sie mit einer bereits
        sichtbaren Nutzerzeile aufrufen. Die Zeile wird dann als unveränderte
        Chat-Episode aufgenommen, damit Zitat und Digest langfristig prüfbar
        bleiben.
        """
        if app.state.conversations.get(conversation_id) is None:
            raise HTTPException(status_code=404, detail="Unbekanntes Gespräch")
        source = next(
            (
                message
                for message in app.state.conversations.messages(conversation_id)
                if message.id == body.source_message_id
            ),
            None,
        )
        if source is None or source.role != "user" or source.status != "complete":
            raise HTTPException(
                status_code=409,
                detail="Ein Gedächtnisvorschlag braucht eine vollständige Nutzerzeile aus diesem Gespräch.",
            )

        try:
            candidate, created = _create_conversation_memory_candidate(
                conversation_id,
                source,
                subject_ref=body.subject_ref,
                predicate=body.predicate,
                value=body.value,
                statement=body.statement,
                rationale=body.rationale,
                scope_ref=body.scope_ref,
                confidence=body.confidence,
            )
        except (ClaimError, ProposalError, EpisodeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if created:
            app.state.conversations.add_message(
                conversation_id,
                "assistant",
                "Ich habe einen Gedächtnisvorschlag vorbereitet. Bitte bestätige ihn nur, wenn er stimmt.",
                metadata={
                    "memory_candidate_id": candidate.id,
                    "memory_source_message_id": source.id,
                },
            )
        return _conversation_payload(conversation_id)

    @app.post(
        "/api/v1/conversations/{conversation_id}/memory-candidates/{proposal_id}/accept",
        dependencies=guard,
    )
    def accept_conversation_memory_candidate(
        conversation_id: str, proposal_id: str, body: ConversationMemoryAcceptIn
    ) -> dict[str, Any]:
        _require_conversation_candidate(conversation_id, proposal_id)
        try:
            with app.state.conversation_lock:
                candidate = app.state.proposals.get(proposal_id)
                conflicts = app.state.claims.conflicts_for(candidate)
                if conflicts and not body.replace_conflicts:
                    raise ClaimError(
                        "Der bestehende Stand muss ausdrücklich ersetzt oder der Vorschlag nicht gespeichert werden."
                    )
                app.state.knowledge_service.accept(
                    proposal_id,
                    supersedes=[item.id for item in conflicts] if body.replace_conflicts else [],
                )
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _conversation_payload(conversation_id)

    @app.post(
        "/api/v1/conversations/{conversation_id}/memory-candidates/{proposal_id}/reject",
        dependencies=guard,
    )
    def reject_conversation_memory_candidate(
        conversation_id: str, proposal_id: str
    ) -> dict[str, Any]:
        _require_conversation_candidate(conversation_id, proposal_id)
        try:
            app.state.knowledge_service.reject(proposal_id)
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _conversation_payload(conversation_id)

    @app.post(
        "/api/v1/conversations/{conversation_id}/memory-candidates/{proposal_id}/retract",
        dependencies=guard,
    )
    def retract_conversation_memory_candidate(
        conversation_id: str, proposal_id: str, body: KnowledgeRetractIn
    ) -> dict[str, Any]:
        """Zieht die Wissensaussage einer angenommenen Gesprächskarte zurück.

        Der Proposal-Zustand bleibt dabei ``accepted``. Die Karte kann so die
        Entscheidungshistorie und den derzeit nicht mehr nutzbaren Claim
        gleichzeitig zeigen.
        """
        try:
            with app.state.conversation_lock:
                _require_conversation_candidate(conversation_id, proposal_id)
                candidate = app.state.proposals.get(proposal_id)
                if candidate.state is not ProposalState.ACCEPTED:
                    raise ClaimError(
                        "Nur ein angenommener Gedächtnisvorschlag kann zurückgezogen werden."
                    )
                claim = app.state.claims.by_proposal(proposal_id)
                if claim is None or not candidate.produced:
                    raise ClaimError(
                        "Der angenommene Gedächtnisvorschlag hat keine Wissensaussage."
                    )
                if claim.id != candidate.produced:
                    raise ClaimError(
                        "Der Gedächtnisvorschlag und seine Wissensaussage sind inkonsistent."
                    )
                app.state.claims.retract(claim.id, reason=body.reason)
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _conversation_payload(conversation_id)

    @app.post(
        "/api/v1/conversations/{conversation_id}/messages/{message_id}/retry",
        dependencies=guard,
        status_code=201,
    )
    def retry_conversation_message(
        conversation_id: str, message_id: str
    ) -> dict[str, Any]:
        """Wiederholt ausschließlich eine fehlgeschlagene Modellantwort.

        Die ursprüngliche Nutzerfrage ist bereits in SQLite. Ein zweiter POST
        mit dem gleichen Text wäre keine Wiederholung, sondern eine zweite
        Aussage im Verlauf – und verfälscht Kontext, Audit und spätere
        Erinnerung. Deshalb wird nur eine neue Assistant-Nachricht ergänzt.
        """
        if app.state.conversations.get(conversation_id) is None:
            raise HTTPException(status_code=404, detail="Unbekanntes Gespräch")

        with app.state.conversation_lock:
            messages = app.state.conversations.messages(conversation_id)
            failed_index = next(
                (
                    index for index, message in enumerate(messages)
                    if message.id == message_id
                    and message.role == "assistant"
                    and message.status == "error"
                    and not message.metadata.get("resolved_approval_id")
                ),
                None,
            )
            if failed_index is None:
                raise HTTPException(
                    status_code=409,
                    detail="Nur eine fehlgeschlagene Assistant-Nachricht kann wiederholt werden.",
                )
            user_index = next(
                (
                    index for index in range(failed_index - 1, -1, -1)
                    if messages[index].role == "user"
                ),
                None,
            )
            if user_index is None:
                raise HTTPException(
                    status_code=409,
                    detail="Die ursprüngliche Nutzerfrage fehlt im Gespräch.",
                )

            question = messages[user_index].content
            source_episode = conversation_memory.find(app.state.episodes, conversation_id, messages[user_index].id)
            if source_episode is None:
                source_episode, _ = conversation_memory.capture(
                    app.state.episodes, conversation_id, messages[user_index],
                    lookup_only=messages[user_index].metadata.get('memory_lookup_only') is True)
            if source_episode.state is EpisodeState.IGNORED:
                raise HTTPException(status_code=409, detail="Diese Gesprächsquelle wurde ausgeschlossen.")
            memory_mode = messages[user_index].metadata.get('answer_mode') == 'memory_evidence'
            if memory_mode and failed_index != len(messages) - 1:
                raise HTTPException(status_code=409,
                    detail="Das Gespräch wurde fortgesetzt. Bitte stelle die Gedächtnisfrage erneut.")
            lineages = _conversation_lineages(messages)
            validity_cache = {}
            history = [
                {"role": message.role, "content": message.content,
                 "context": message.metadata.get("context"),
                 "conversation_source_lineage": lineages[message.id]}
                for message in messages[:user_index]
                if message.status == "complete" and conversation_memory.lineage_valid(
                    app.state.episodes, lineages[message.id], validity_cache)
            ]
            input_sources = {entry["episode_id"]: entry
                for item in history for entry in item["conversation_source_lineage"]}
            source_stamp = conversation_memory.stamp(app.state.episodes, source_episode.id)
            source_captured = conversation_memory.usable(app.state.episodes, source_stamp)
            input_sources[source_episode.id] = source_stamp
            try:
                if memory_mode:
                    turn = _memory_conversation_turn(question,
                        messages[user_index - 1] if user_index else None,
                        new_question=messages[user_index].metadata.get('new_question') is True)
                else:
                    app.state.agent.load_history(history)
                    turn = app.state.agent.send(
                        question, conversation_source_captured=source_captured)
                app.state.conversations.add_message(
                    conversation_id,
                    "assistant",
                    turn.reply or "Ich habe darauf gerade keine Antwort.",
                    metadata={
                        "approvals": [approval.to_dict() for approval in turn.approvals],
                        "notices": turn.notices,
                        "used_tools": turn.used_tools,
                        "context": turn.context,
                        "retry_of": message_id,
                        "conversation_source_lineage": list(input_sources.values()),
                    },
                )
            except Exception:  # noqa: BLE001 - erneuter Fehler bleibt ebenfalls sichtbar
                app.state.conversations.add_message(
                    conversation_id,
                    "assistant",
                    "Die Antwort konnte gerade nicht erstellt werden.",
                    status="error",
                    metadata={"retry_of": message_id,
                              "conversation_source_lineage": list(input_sources.values())},
                )
        return _conversation_payload(conversation_id)

    # -- Aufgaben ----------------------------------------------------------

    def _task_view(view: str, project_id: str | None = None) -> list[dict[str, Any]]:
        """Die drei belegten Aufgabensichten für die Produktoberfläche.

        `delegated` fehlt bewusst: Die aktuelle Ablage kennt den tatsächlichen
        Wartezustand, aber keine davon unabhängige Delegationssemantik.
        """
        tasks = app.state.tasks
        if project_id:
            _validate_task_project(project_id)
            items = tasks.by_project(project_id, include_closed=True)
            if view == "mine":
                items = [task for task in items if task.status.value == "open" and task.wartet_auf is None]
            elif view == "waiting":
                items = [task for task in items if task.status.value == "open" and task.wartet_auf is not None]
                items.sort(key=lambda task: task.wartet_seit or task.created_at)
            elif view == "done":
                items = [task for task in items if task.status.value == "done"]
                items.sort(key=lambda task: task.done_at or task.created_at, reverse=True)
            return [task.to_dict() for task in items]
        if view == "mine":
            return [task.to_dict() for task in tasks.open_tasks() if task.wartet_auf is None]
        if view == "waiting":
            return [task.to_dict() for task in tasks.wartend()]
        if view == "done":
            completed = [task for task in tasks.all_tasks() if task.status.value == "done"]
            completed.sort(key=lambda task: task.done_at or task.created_at, reverse=True)
            return [task.to_dict() for task in completed]
        raise HTTPException(status_code=400, detail="Unbekannte Aufgabenansicht.")

    @app.get("/api/v1/tasks", dependencies=guard)
    def list_kingfisher_tasks(view: str = Query(default="mine", pattern="^(mine|waiting|done)$"), project_id: str | None = None,
                              q: str = Query(default='', max_length=200), limit: int = Query(default=200, ge=1, le=200),
                              cursor: str | None = Query(default=None, max_length=2048)) -> dict[str, Any]:
        """Liefert nur echte, lokal gespeicherte Aufgaben einer belegten Sicht."""
        from .task_pages import TaskPageChanged
        if project_id:
            _validate_task_project(project_id)
        try:
            return {'view': view, **app.state.tasks.page(view, project_id=project_id, q=q, limit=limit, cursor=cursor)}
        except TaskPageChanged as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/tasks/reminders", dependencies=guard)
    def task_reminders(limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        tasks = app.state.tasks.reminders_due(limit=limit + 1)
        return {"items": [task.to_dict() for task in tasks[:limit]], "truncated": len(tasks) > limit}

    @app.get("/api/v1/tasks/{task_id}", dependencies=guard)
    def read_kingfisher_task(task_id: str) -> dict[str, Any]:
        task = app.state.tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
        return task.to_dict()

    @app.get("/api/v1/tasks/{task_id}/history", dependencies=guard)
    def task_history(task_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            if app.state.tasks.get(task_id) is None:
                raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
            events = app.state.tasks.history(task_id, limit=101)
            return {"items": events[:100], "truncated": len(events) > 100,
                    "scope": "Gespeicherte Änderungen dieser Aufgabe, neueste zuerst."}

    @app.get("/api/v1/tasks/{task_id}/source", dependencies=guard)
    def task_source(task_id: str) -> dict[str, Any]:
        task = app.state.tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
        ref = task.provenance.source_ref or ""
        if not ref.startswith("episode:"):
            raise HTTPException(status_code=404, detail="Keine gespeicherte Quelle verknüpft.")
        try:
            episode = app.state.episodes.get(ref.removeprefix("episode:"))
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail="Die gespeicherte Quelle ist nicht verfügbar.") from exc
        return {**episode.to_dict(), "body": episode.body[:20000], "quote": task.provenance.verbatim,
                "truncated": len(episode.body) > 20000 or "source:truncated" in episode.tags}

    @app.post("/api/v1/tasks", dependencies=guard, status_code=201)
    def add_kingfisher_task(body: TaskIn) -> dict[str, Any]:
        """Legt eine ausdrücklich eingegebene Aufgabe mit Nutzerherkunft an."""
        with app.state.conversation_lock:
            _validate_task_project(body.project_id)
            _validate_task_goal(body.goal_id)
            return app.state.tasks.add(
                body.title,
                Provenance(source_type=SourceType.USER_STATED,
                           captured_at=datetime.now().astimezone()),
                due=body.due, notes=body.notes, tags=body.tags,
                project_id=body.project_id, goal_id=body.goal_id,
            ).to_dict()

    def _validate_task_project(project_id: str | None) -> None:
        if project_id is not None:
            try:
                app.state.workspace.project(project_id)
            except WorkspaceError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _validate_task_goal(goal_id: str | None) -> None:
        if goal_id is None:
            return
        goal = app.state.store.get(goal_id)
        if (goal is None or goal.kind is not Kind.GOAL
                or (goal.structured or {}).get("domain") == "habit"
                or not any(item.id == goal_id for item in app.state.store.usable())):
            raise HTTPException(status_code=409, detail="Das Ziel ist nicht mehr offen. Bitte neu laden.")

    @app.patch("/api/v1/tasks/{task_id}", dependencies=guard)
    def edit_kingfisher_task(task_id: str, body: TaskEditIn) -> dict[str, Any]:
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=422, detail="Bitte mindestens ein Aufgabenfeld ändern.")
        try:
            return app.state.tasks.edit(task_id, **changes).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.") from exc
        except TaskChangedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.patch("/api/v1/tasks/{task_id}/project", dependencies=guard)
    def assign_task_project(task_id: str, body: TaskProjectIn) -> dict[str, Any]:
        _validate_task_project(body.project_id)
        try:
            return app.state.tasks.assign_project(task_id, body.project_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/tasks/{task_id}/done", dependencies=guard)
    def complete_kingfisher_task(task_id: str) -> dict[str, Any]:
        try:
            return app.state.tasks.complete(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/tasks/{task_id}/reopen", dependencies=guard)
    def reopen_kingfisher_task(task_id: str) -> dict[str, Any]:
        try:
            return app.state.tasks.reopen(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def task_candidate_service():
        return TaskCandidates(app.state.episodes, app.state.proposals, app.state.tasks,
                              app.state.workspace, app.state.conversation_lock)

    @app.get("/api/v1/task-candidates/page", dependencies=guard)
    def task_candidates_page(
        limit: int = Query(default=25, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=250000),
        temporal: Literal["all", "recent", "review"] = Query(default="all"),
        generation: str | None = Query(default=None, min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$"),
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        total = 0
        digest = hashlib.sha256()
        # Offset pagination scans the full pending set to compute its total and generation (O(N)).
        with app.state.conversation_lock:
            for batch in candidate_batches(app.state.proposals, app.state.episodes):
                for proposal, _, timing in batch:
                    status = timing.get("temporal_status")
                    if temporal == "recent" and status != "recent":
                        continue
                    if temporal == "review" and status == "recent":
                        continue
                    # A task write can succeed immediately before the proposal is marked accepted.
                    # Do not show that already-created task as a still-pending suggestion.
                    if app.state.tasks.get(f"t-suggestion-{proposal.id}") is not None:
                        continue
                    digest.update(proposal.id.encode("utf-8"))
                    digest.update(b"\0")
                    digest.update(str(status or "").encode("utf-8"))
                    digest.update(b"\n")
                    if offset <= total < offset + limit:
                        items.append({**proposal.to_dict(), **timing})
                    total += 1
            current_generation = digest.hexdigest()
            if generation is not None and generation != current_generation:
                raise HTTPException(409, "Die Prüfliste hat sich geändert. Bitte die erste Seite neu laden.")
        return {"items": items, "total": total, "offset": offset, "limit": limit,
                "has_more": offset + len(items) < total, "generation": current_generation}

    @app.get("/api/v1/task-candidates", dependencies=guard)
    def task_candidates():
        TaskDetector(app.state.episodes, app.state.proposals, None, app.state.conversation_lock, tasks=app.state.tasks).expire_sources()
        from itertools import islice
        cards = ({**p.to_dict(), **timing} for batch in candidate_batches(app.state.proposals, app.state.episodes)
                 for p, _, timing in batch)
        return list(islice(cards, 100))

    @app.post("/api/v1/task-candidates/{proposal_id}/accept", dependencies=guard)
    def accept_task_candidate(proposal_id: str, body: TaskCandidateIn):
        try:
            return task_candidate_service().accept(proposal_id, title=body.title,
                project_id=body.project_id, due=body.due, waiting_for=body.waiting_for).to_dict()
        except (ProposalError, EpisodeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (WorkspaceError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/task-candidates/{proposal_id}/reject", dependencies=guard)
    def reject_task_candidate(proposal_id: str):
        try:
            return task_candidate_service().reject(proposal_id).to_dict()
        except ProposalError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/tasks", dependencies=guard)
    def list_tasks(all: bool = False) -> list[dict[str, Any]]:
        items = app.state.tasks.all_tasks() if all else app.state.tasks.open_tasks()
        return [t.to_dict() for t in items]

    @app.post("/tasks", dependencies=guard, status_code=201)
    def add_task(body: TaskIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            _validate_task_project(body.project_id)
            _validate_task_goal(body.goal_id)
            task = app.state.tasks.add(
                body.title,
                Provenance(source_type=SourceType.USER_STATED,
                           captured_at=datetime.now().astimezone()),
                due=body.due, notes=body.notes, tags=body.tags,
                project_id=body.project_id, goal_id=body.goal_id,
            )
            return task.to_dict()

    @app.post("/tasks/{task_id}/done", dependencies=guard)
    def complete_task(task_id: str) -> dict[str, Any]:
        try:
            return app.state.tasks.complete(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/tasks/{task_id}/drop", dependencies=guard)
    def drop_task(task_id: str) -> dict[str, Any]:
        """Fallenlassen, nicht erledigen.

        Der Unterschied ist für ein System, das Jahre läuft, wichtig: Sonst
        sieht es später aus, als wäre alles geschafft worden.
        """
        try:
            return app.state.tasks.drop(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/tasks/{task_id}/warten", dependencies=guard)
    @app.post("/tasks/{task_id}/warten", dependencies=guard)
    def wait_task(task_id: str, body: WartetIn) -> dict[str, Any]:
        """Abgeben, nicht abhaken.

        Die Aufgabe bleibt offen, zählt aber nicht mehr gegen dich. Was bei
        jemand anderem liegt, ist kein Versäumnis, sondern eine Wartezeit —
        und die will nachgefasst, nicht angemahnt werden.
        """
        try:
            return app.state.tasks.warten_auf(task_id, body.name).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/tasks/{task_id}/zurueckholen", dependencies=guard)
    @app.post("/tasks/{task_id}/zurueckholen", dependencies=guard)
    def unwait_task(task_id: str) -> dict[str, Any]:
        try:
            return app.state.tasks.zurueckholen(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/goals/{goal_id}/finish", dependencies=guard)
    @app.post("/goals/{goal_id}/finish", dependencies=guard)
    def finish_goal(goal_id: str, body: GoalFinishIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                return goals.finish(app.state.store, goal_id, body.outcome, body.note).to_dict()
            except ConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/goals/{completion_id}/reopen", dependencies=guard)
    @app.post("/goals/{completion_id}/reopen", dependencies=guard)
    def reopen_goal(completion_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                return goals.reopen(app.state.store, completion_id).to_dict()
            except ConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/goals", dependencies=guard)
    @app.get("/goals", dependencies=guard)
    def list_goals() -> dict[str, Any]:
        """Alle Vorhaben mit ihrer letzten Regung, das stillste zuerst."""
        alle = urteil.vorhaben(
            store=app.state.store,
            episodes=getattr(app.state, "episodes", None),
            tasks=getattr(app.state, "tasks", None),
            workspace=getattr(app.state, "workspace", None),
        )
        jetzt = datetime.now().astimezone()
        return {
            "items": [v.to_dict(jetzt) for v in alle],
            "eingeschlafen": sum(1 for v in alle if v.schlaeft(jetzt)),
            "completed": goals.completed(app.state.store),
        }

    # -- Angedockte Dienste ------------------------------------------------

    def _angabe_aus(body: MCPServerIn) -> mcp_client.Serverangabe:
        try:
            teile = shlex.split(body.befehl)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Der Befehl ist nicht lesbar: {exc}",
            ) from exc
        if not teile:
            raise HTTPException(status_code=400, detail="Der Befehl ist leer.")
        return mcp_client.Serverangabe(
            name=body.name.strip(), befehl=teile, umgebung=dict(body.umgebung)
        )

    @app.get("/mcp/tuer", dependencies=tuer_guard)
    def mcp_tuer_status() -> dict[str, bool]:
        """Antwortet nur, wenn die Tür offen ist (sonst sperrt `tuer_guard`).

        Die stdio-Brücke fragt hier an, bevor sie etwas ausliefert — auch für
        Werkzeuge, die an ungesperrten App-Endpunkten hängen.
        """
        return {"offen": True}

    @app.get("/mcp/server", dependencies=tuer_guard)
    def list_mcp() -> dict[str, Any]:
        """Was eingetragen ist, was läuft, und was nicht startete."""
        laufend = getattr(app.state, "mcp", None) or {}
        fehler = getattr(app.state, "mcp_fehler", None) or {}
        eintraege = []
        for roh in app.state.settings.mcp_server:
            angabe = mcp_client.Serverangabe.from_dict(roh)
            verbunden = laufend.get(angabe.name)
            eintraege.append({
                **angabe.to_dict(),
                "befehl_text": " ".join(angabe.befehl),
                "verbunden": verbunden is not None,
                "werkzeuge": [w.voller_name for w in (verbunden[1] if verbunden else [])],
                "fehler": fehler.get(angabe.name),
            })
        return {"items": eintraege}

    @app.post("/mcp/pruefen", dependencies=tuer_guard)
    def check_mcp(body: MCPServerIn) -> dict[str, Any]:
        """Verbinden und nachsehen — ohne etwas einzutragen.

        Der Knopf, der sagt, was dabei herauskam. Ein Eintrag, der erst beim
        nächsten Start scheitert, wäre eine Zusage ohne Deckung.
        """
        try:
            werkzeuge = mcp_client.nachsehen(_angabe_aus(body))
        except mcp_client.MCPFehler as exc:
            return {"ok": False, "detail": str(exc), "werkzeuge": []}
        namen = [w.voller_name for w in werkzeuge]
        if not namen:
            return {"ok": True, "detail": "Verbunden — aber der Dienst bietet "
                                          "kein Werkzeug an.", "werkzeuge": []}
        wie_viele = "ein Werkzeug" if len(namen) == 1 else f"{len(namen)} Werkzeuge"
        return {
            "ok": True,
            "detail": f"Verbunden. {wie_viele} gefunden.",
            "werkzeuge": namen,
        }

    @app.post("/mcp/server", dependencies=tuer_guard, status_code=201)
    def add_mcp(body: MCPServerIn) -> dict[str, Any]:
        """Einen Dienst andocken.

        Erst prüfen, dann eintragen: Ein Dienst, der nicht startet, soll gar
        nicht erst in der Liste stehen — sonst sammeln sich dort Einträge, von
        denen niemand weiß, ob sie je funktioniert haben.
        """
        angabe = _angabe_aus(body)
        if any(mcp_client.Serverangabe.from_dict(d).name == angabe.name
               for d in app.state.settings.mcp_server):
            raise HTTPException(
                status_code=409,
                detail=f"„{angabe.name}“ ist schon eingetragen.",
            )
        try:
            werkzeuge = mcp_client.nachsehen(angabe)
        except mcp_client.MCPFehler as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        app.state.settings.mcp_server.append({
            "name": angabe.name,
            "befehl": angabe.befehl,
            "umgebung": angabe.umgebung,
            "aktiv": True,
        })
        config.save(_data_dir(), app.state.settings)
        _build_agent(app)
        return {
            "name": angabe.name,
            "werkzeuge": [w.voller_name for w in werkzeuge],
            "detail": f"„{angabe.name}“ angedockt.",
        }

    @app.delete("/mcp/server/{name}", dependencies=tuer_guard)
    def remove_mcp(name: str) -> dict[str, Any]:
        vorher = len(app.state.settings.mcp_server)
        app.state.settings.mcp_server = [
            d for d in app.state.settings.mcp_server
            if mcp_client.Serverangabe.from_dict(d).name != name
        ]
        if len(app.state.settings.mcp_server) == vorher:
            raise HTTPException(status_code=404, detail=f"„{name}“ ist nicht eingetragen.")
        config.save(_data_dir(), app.state.settings)
        _build_agent(app)
        return {"detail": f"„{name}“ abgedockt."}

    # -- Entscheidungen ----------------------------------------------------

    @app.get("/api/v1/decisions", dependencies=guard)
    @app.get("/decisions", dependencies=guard)
    def list_decisions() -> dict[str, Any]:
        """Alle Entscheidungen mit dem Stand ihrer Grundlage.

        Auch widerrufene: Dass eine Entscheidung einmal getroffen wurde,
        bleibt wahr. Ein Gedächtnis, das nichts löscht, muss das zeigen.
        """
        alle = entscheidungen.alle(app.state.store, knowledge=app.state.claims)
        return {
            "items": [e.to_dict() for e in alle],
            "erschuettert": sum(1 for e in alle if e.erschuettert),
        }

    @app.get("/api/v1/decision-basis", dependencies=guard)
    def decision_basis() -> dict[str, Any]:
        return {"items": [
            {"id": f"assertion:{item.id}", "statement": item.statement, "kind": "self"}
            for item in app.state.store.usable() if item.kind is not Kind.DECISION
        ] + [
            {"id": f"claim:{item.id}", "statement": item.statement, "kind": "knowledge"}
            for item in app.state.claims.all_claims(include_inactive=False)
        ]}

    @app.post("/api/v1/decisions/{decision_id}/retract", dependencies=guard)
    def retract_decision(decision_id: str) -> dict[str, Any]:
        decision = next((item for item in entscheidungen.alle(app.state.store) if item.id == decision_id), None)
        if decision is None:
            raise HTTPException(status_code=404, detail="Unbekannte Entscheidung.")
        if decision.aussage.status.value not in ("active", "disputed", "retracted"):
            raise HTTPException(status_code=409, detail="Diese Entscheidung ist nicht mehr aktiv.")
        app.state.store.retract(decision_id)
        return next(item.to_dict() for item in entscheidungen.alle(app.state.store, knowledge=app.state.claims) if item.id == decision_id)

    @app.post("/api/v1/decisions", dependencies=guard, status_code=201)
    @app.post("/decisions", dependencies=guard, status_code=201)
    def add_decision(body: EntscheidungIn) -> dict[str, Any]:
        """Eine Entscheidung festhalten — und worauf sie stand.

        Die Grundlage ist optional, aber ohne sie kann Icarus später nicht
        merken, wenn sie wegfällt. Das sagt die Oberfläche auch.
        """
        if not body.statement.strip():
            raise HTTPException(status_code=422, detail="Bitte die Entscheidung beschreiben.")
        _validate_task_project(body.project_id)
        usable = {item.id for item in app.state.store.usable()}
        if any(ref not in usable for ref in body.derived_from):
            missing = next(ref for ref in body.derived_from if ref not in usable)
            raise HTTPException(status_code=409, detail=f"Grundlage {missing} ist nicht mehr verwendbar. Bitte neu auswählen.")
        usable_claims = {item.id for item in app.state.claims.all_claims(include_inactive=False)}
        if any(ref not in usable_claims for ref in body.claim_ids):
            raise HTTPException(status_code=409, detail="Eine Wissensgrundlage ist nicht mehr verwendbar. Bitte neu auswählen.")
        try:
            aussage = app.state.store.record(
                body.statement.strip(),
                Kind.DECISION,
                Provenance(source_type=SourceType.USER_STATED,
                           captured_at=datetime.now().astimezone()),
                derived_from=list(dict.fromkeys(body.derived_from)),
                tags=body.tags,
                structured={"claim_ids": list(dict.fromkeys(body.claim_ids)), "project_id": body.project_id},
            )
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        for eine in entscheidungen.alle(app.state.store, knowledge=app.state.claims):
            if eine.id == aussage.id:
                return eine.to_dict()
        return {"id": aussage.id, "satz": aussage.statement}

    # -- Projekte ----------------------------------------------------------

    @app.get("/api/v1/projects", dependencies=guard)
    @app.get("/projects", dependencies=guard)
    def list_projects(all: bool = False) -> list[dict[str, Any]]:
        return [p.to_dict() for p in app.state.workspace.projects(include_closed=all)]

    @app.post("/api/v1/projects", dependencies=guard, status_code=201)
    @app.post("/projects", dependencies=guard, status_code=201)
    def add_project(body: ProjectIn) -> dict[str, Any]:
        if not body.name.strip():
            raise HTTPException(status_code=422, detail="Bitte einen Projektnamen eingeben.")
        project = app.state.workspace.add_project(
            body.name.strip(),
            Provenance(source_type=SourceType.USER_STATED,
                       captured_at=datetime.now().astimezone()),
            area=body.area, status=body.status, priority=body.priority,
            description=body.description, deadline=body.deadline, tags=body.tags,
        )
        return project.to_dict()

    @app.get("/api/v1/projects/{project_id}/task-overview", dependencies=guard)
    def project_task_overview(project_id: str) -> dict[str, Any]:
        _validate_task_project(project_id)
        return app.state.tasks.project_overview(project_id)

    @app.get("/api/v1/projects/{project_id}", dependencies=guard)
    @app.get("/projects/{project_id}", dependencies=guard)
    def project_detail(project_id: str) -> dict[str, Any]:
        """Projekt samt allem, was daran hängt.

        Ein Aufruf statt drei — die Projektansicht soll nicht aus drei
        Anfragen zusammengesetzt werden, die einzeln scheitern können.
        """
        try:
            project = app.state.workspace.project(project_id)
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            **project.to_dict(),
            "tasks": [t.to_dict() for t in app.state.tasks.by_project(project_id)],
            "notes": [
                n.to_dict() for n in app.state.workspace.notes(project_id=project_id)
            ],
        }

    @app.patch("/api/v1/projects/{project_id}", dependencies=guard)
    @app.patch("/projects/{project_id}", dependencies=guard)
    def patch_project(project_id: str, body: ProjectPatch) -> dict[str, Any]:
        try:
            project = app.state.workspace.update_project(
                project_id,
                status=body.status, priority=body.priority,
                description=body.description, deadline=body.deadline, area=body.area,
            )
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return project.to_dict()

    # -- Notizen -----------------------------------------------------------

    @app.get("/notes", dependencies=guard)
    def list_notes(project_id: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
        if q:
            return [n.to_dict() for n in app.state.workspace.search_notes(q)]
        return [n.to_dict() for n in app.state.workspace.notes(project_id=project_id)]

    @app.post("/notes", dependencies=guard, status_code=201)
    def add_note(body: NoteIn) -> dict[str, Any]:
        try:
            note = app.state.workspace.add_note(
                body.title, body.body,
                Provenance(source_type=SourceType.USER_STATED,
                           captured_at=datetime.now().astimezone()),
                kind=body.kind, project_id=body.project_id, tags=body.tags,
            )
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return note.to_dict()

    @app.get("/api/v1/notes/{note_id}", dependencies=guard)
    @app.get("/notes/{note_id}", dependencies=guard)
    def note_detail(note_id: str) -> dict[str, Any]:
        try:
            return app.state.workspace.note(note_id).to_dict()
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/notes/{note_id}", dependencies=guard)
    def patch_note(note_id: str, body: NotePatch) -> dict[str, Any]:
        try:
            note = app.state.workspace.update_note(
                note_id, title=body.title, body=body.body, project_id=body.project_id,
            )
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return note.to_dict()

    # -- Episoden ----------------------------------------------------------
    #
    # Die Mittelfristschicht. Was hier liegt, ist Rohmaterial und behauptet
    # nichts über den Nutzer — deshalb gibt es hier keinen Weg in den Bestand.
    # Den zieht erst die Verdichtung, und sie legt vor.

    @app.get("/api/v1/sources/documents", dependencies=guard)
    def uploaded_documents(offset: int = 0) -> dict[str, Any]:
        if offset < 0:
            raise HTTPException(status_code=422, detail="Ungültige Seitenposition")
        from .working_memory_status import source_status
        items = app.state.episodes.uploaded_documents(offset=offset, limit=51)
        return {"items": [{"id": item.id, "title": item.title, "state": item.state.value,
                            "project_id": item.project_id, "recorded_at": item.recorded_at.isoformat(),
                            "memory_status": source_status(app, item.id)}
                           for item in items[:50]],
                "next_offset": offset + 50 if len(items) > 50 else None}

    @app.post("/api/v1/sources/documents/preview-pdf", dependencies=guard)
    def preview_pdf(body: DocumentPreviewIn) -> dict[str, Any]:
        from .document_text import pdf_text
        try:
            return pdf_text(base64.b64decode(body.content_base64, validate=True))
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/sources/documents/preview-docx", dependencies=guard)
    def preview_docx(body: DocumentPreviewIn) -> dict[str, str]:
        from .document_text import docx_text
        try:
            data = base64.b64decode(body.content_base64, validate=True)
            return {"body": docx_text(data)}
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/sources/documents/preview-transcript", dependencies=guard)
    def transcript_preview(body: TranscriptPreviewIn) -> dict[str, Any]:
        from .transcript_preview import preview_transcript
        try:
            return preview_transcript(body.text, body.format)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/sources/documents", dependencies=guard)
    def upload_document(body: DocumentSourceIn) -> dict[str, Any]:
        filename = body.filename
        allowed = {".md", ".markdown", ".txt", ".org", ".rst", ".csv", ".docx", ".pdf", ".srt", ".vtt"}
        if (any(char in filename for char in ("/", "\\", "\0"))
                or Path(filename).suffix.lower() not in allowed):
            raise HTTPException(status_code=422, detail="Bitte eine Textdatei mit einfachem Dateinamen auswählen.")
        try:
            size = len(body.body.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise HTTPException(status_code=422, detail="Die Datei muss gültigen UTF-8-Text enthalten.") from exc
        if not body.body.strip() or "\0" in body.body or size > 512 * 1024:
            raise HTTPException(status_code=422, detail="Die Textdatei darf nicht leer und höchstens 512 KiB groß sein.")
        _validate_task_project(body.project_id)
        episode, created = app.state.episodes.record(
            kind=EpisodeKind.DOCUMENT, title=filename, body=body.body,
            provenance=Provenance(source_type=SourceType.DOCUMENT, source_ref=f"upload:{filename}",
                                  captured_at=datetime.now().astimezone()),
            project_id=body.project_id,
        )
        if created and app.state.settings.schedule.enabled and app.state.settings.schedule.with_model:
            agent = getattr(app.state, 'agent', None)
            scheduler = getattr(app.state, 'scheduler', None)
            if scheduler is not None and getattr(rollen_von(app).provider('hintergrund'), 'is_local', False):
                scheduler.request_working_memory(episode.id)
        return {"id": episode.id, "created": created, "title": episode.title,
                "project_id": episode.project_id}

    @app.get("/episodes", dependencies=guard)
    def list_episodes(
        state: EpisodeState | None = None,
        project_id: str | None = None,
        q: str | None = None,
        days: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        eps = app.state.episodes
        if q:
            items = eps.search(q, limit)
        elif project_id:
            items = eps.by_project(project_id, limit)
        elif days is not None:
            items = eps.recent(days, limit)
        elif state is EpisodeState.NEW:
            items = eps.pending(limit)
        else:
            items = eps.all_episodes(limit)
        if state is not None:
            items = [e for e in items if e.state is state]
        return [e.to_dict() for e in items]

    @app.get("/episodes/counts", dependencies=guard)
    def episode_counts() -> dict[str, int]:
        return app.state.episodes.counts()

    @app.post("/episodes", dependencies=guard, status_code=201)
    def add_episode(body: EpisodeIn) -> dict[str, Any]:
        episode, is_new = app.state.episodes.record(
            kind=body.kind, title=body.title, body=body.body,
            provenance=Provenance(source_type=SourceType.USER_STATED,
                                  captured_at=datetime.now().astimezone()),
            occurred_at=body.occurred_at, project_id=body.project_id,
            participants=body.participants, tags=body.tags,
        )
        # 200 statt 201, wenn der Digest schon bekannt war: Der Aufrufer soll
        # unterscheiden können, ob er etwas erzeugt hat oder nur wiedergefunden.
        return {**episode.to_dict(), "created": is_new}

    @app.get("/api/v1/episodes/{episode_id}", dependencies=guard)
    @app.get("/episodes/{episode_id}", dependencies=guard)
    def episode_detail(episode_id: str) -> dict[str, Any]:
        try:
            from .working_memory_status import source_status
            result = app.state.episodes.get(episode_id).to_dict()
            result["memory_status"] = source_status(app, episode_id)
            from .anhaenge import gespeicherter_bericht
            result['attachment_coverage'] = gespeicherter_bericht(app.state.episodes.get(episode_id))
            result['attachment_check_pending'] = (result['kind'] == 'message'
                and result['provenance']['source_type'] == 'email' and result['attachment_coverage'] is None)
            result['source_incomplete'] = 'source:truncated' in result['tags']
            snapshot = app.state.episodes.support_snapshot(episode_id)
            result['source_current'] = bool(snapshot and snapshot.current())
            result['attachment_sources'] = ([{'id': child_id, 'title': app.state.episodes.get(child_id).title}
                for child_id in app.state.episodes.mail_attachment_children(episode_id)]
                if result['kind'] == 'message' else [])
            correction_id = app.state.episodes.source_head('source-correction:' + episode_id)
            if correction_id:
                result['correction_id'] = correction_id
            if (result['provenance']['source_type'] == 'manual_correction'
                    and (result['provenance'].get('source_ref') or '').startswith('source-correction:')):
                snapshot = app.state.episodes.support_snapshot(episode_id)
                result['correction_current'] = bool(snapshot and snapshot.current())
            return result
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/episodes/{episode_id}/ignore", dependencies=guard)
    @app.post("/episodes/{episode_id}/ignore", dependencies=guard)
    def ignore_episode(episode_id: str) -> dict[str, Any]:
        try:
            with app.state.conversation_lock:
                app.state.episodes.get(episode_id)
                # Zwei Datenbanken: zuerst Wissen sperren. Scheitert danach
                # das Ignorieren, bleibt es bis zur erneuten Prüfung gesperrt.
                invalidate_with_corrections(app.state.episodes, app.state.claims, episode_id)
                return app.state.episodes.ignore(episode_id).to_dict()
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/episodes/{episode_id}/reopen", dependencies=guard)
    def reopen_episode(episode_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                episode = app.state.episodes.get(episode_id)
            except EpisodeError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            if episode.state is not EpisodeState.IGNORED:
                return episode.to_dict()
            if app.state.episodes.source_head('source-correction:' + episode_id):
                raise HTTPException(status_code=409, detail='Zu dieser Quelle gibt es eine Berichtigung. Bitte diese prüfen.')
            # Erst die ausdrückliche Anforderung protokollieren und altes Wissen
            # sperren. Ein Teilausfall darf kein früheres Wissen reaktivieren.
            app.state.audit.record("quelle_wiederzulassen", "write_local", "confirm", "approved",
                                   {"episode_id": episode_id}, detail="Erneute Prüfung des gespeicherten Rohtexts angefordert.")
            invalidate_with_corrections(app.state.episodes, app.state.claims, episode_id)
            try:
                return app.state.episodes.reopen(episode_id).to_dict()
            except EpisodeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.put("/api/v1/episodes/{episode_id}/project", dependencies=guard)
    def link_episode_project(episode_id: str, body: SourceProjectIn) -> dict[str, Any]:
        """Quelle einem Projekt zuordnen oder die Zuordnung lösen.

        Eine Ablage des Nutzers, kein Fakt: Einordnung und Belege bleiben
        unverändert, deshalb ohne Rückfrage und jederzeit umkehrbar.
        """
        _validate_task_project(body.project_id)
        try:
            episode = app.state.episodes.get(episode_id)
            if episode.project_id != body.project_id:
                episode = app.state.episodes.link_project(episode_id, body.project_id)
                app.state.audit.record("quelle_projekt_zuordnen", "write_local", "auto", "executed",
                                       {"episode_id": episode_id, "project_id": body.project_id})
            return episode.to_dict()
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _project_names() -> dict[str, str]:
        return {project.id: project.name for project in app.state.workspace.projects(include_closed=True)}

    @app.get("/api/v1/episodes/{episode_id}/project-suggestion", dependencies=guard)
    def episode_project_suggestion(episode_id: str) -> dict[str, Any]:
        """Vorschlag aus den eigenen Zuordnungen; wird nie selbst angewendet."""
        from .project_suggestions import for_episode
        try:
            episode = app.state.episodes.get(episode_id)
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return for_episode(app.state.episodes, episode, _project_names())

    def _move_projects(ids, project_id, only_if):
        changed = []
        for identifier in dict.fromkeys(ids):
            try:
                current = app.state.episodes.get(identifier)
            except EpisodeError:
                continue
            if current.project_id == only_if and current.project_id != project_id:
                app.state.episodes.link_project(identifier, project_id)
                changed.append(identifier)
        if changed:
            app.state.audit.record("quellen_projekt_zuordnen", "write_local", "auto", "executed",
                                   {"episode_ids": changed, "project_id": project_id})
        return changed

    @app.post("/api/v1/episodes/{episode_id}/project/same-sender", dependencies=guard)
    def link_same_sender(episode_id: str, body: SourceProjectIn) -> dict[str, Any]:
        """Die übrigen Mails desselben Absenders ohne Projekt ebenfalls zuordnen.

        Nur auf ausdrücklichen Klick; bereits zugeordnete Mails bleiben, wie sie sind.
        """
        from .project_suggestions import same_sender
        if body.project_id is None:
            raise HTTPException(status_code=422, detail="Bitte ein Projekt wählen.")
        _validate_task_project(body.project_id)
        try:
            episode = app.state.episodes.get(episode_id)
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        peers = [peer.id for peer in same_sender(app.state.episodes, episode) if peer.project_id is None]
        return {"changed": _move_projects(peers, body.project_id, None)}

    @app.put("/api/v1/episodes/projects", dependencies=guard)
    def link_episode_projects(body: SourceProjectsIn) -> dict[str, Any]:
        """Mehrere Quellen umhängen, etwa zum Rückgängigmachen einer Sammelzuordnung."""
        _validate_task_project(body.project_id)
        return {"changed": _move_projects(body.episode_ids, body.project_id, body.only_if_project_id)}

    # -- Menschen ----------------------------------------------------------
    #
    # Abgeleitet, nicht gespeichert: Es gibt keine Personentabelle und keinen
    # Weg, hier etwas anzulegen. Wer in einer Episode vorkommt, ist da. Siehe
    # personen.py.

    @app.get("/people", dependencies=guard)
    def list_people() -> list[dict[str, Any]]:
        return [
            p.to_dict() for p in personen.alle(
                episodes=app.state.episodes,
                tasks=app.state.tasks,
                store=app.state.store,
                workspace=app.state.workspace,
                jetzt=datetime.now().astimezone(),
                eigene=_eigene_adressen(),
                confirmed_merges=app.state.claims.person_merges.list(),
            )
        ]

    def _mehrdeutig_melden(fehler: personen.Mehrdeutig) -> HTTPException:
        """Ein Name, der mehreren Menschen gehört: nennen, wer, statt einen zu raten."""
        wer = "; ".join(f"{p.name} <{p.adressen[0]}>" if p.adressen else p.name for p in fehler.kandidaten)
        return HTTPException(
            status_code=409,
            detail=f"„{fehler.name}“ gehört mehreren Menschen: {wer}. Bitte die Adresse angeben.",
        )

    @app.get("/people/{name}", dependencies=guard)
    def person_detail(name: str) -> dict[str, Any]:
        try:
            mensch = personen.eine(
                name,
                episodes=app.state.episodes,
                tasks=app.state.tasks,
                store=app.state.store,
                workspace=app.state.workspace,
                jetzt=datetime.now().astimezone(),
                eigene=_eigene_adressen(),
                confirmed_merges=app.state.claims.person_merges.list(),
            )
        except personen.Mehrdeutig as fehler:
            raise _mehrdeutig_melden(fehler) from fehler
        if mensch is None:
            # 404 und keine leere Person: Eine leere Seite über jemanden sähe
            # aus wie eine Auskunft, und wäre keine.
            raise HTTPException(
                status_code=404,
                detail=f"In deinen Aufzeichnungen kommt „{name}“ nicht vor.",
            )
        return mensch.to_dict()

    # -- Vernetztes Gedächtnis -------------------------------------------
    #
    # Ausschließlich abgeleitete Leseansichten. Der Graph ist kein zweiter
    # Speicher und nimmt deshalb auch keine Schreibanfragen entgegen.

    from .person_digest_api import install_routes as install_person_digest_routes
    install_person_digest_routes(app, guard)

    from .person_merge_api import install_routes as install_person_merge_routes
    install_person_merge_routes(app, guard)

    @app.get("/api/v1/memory/graph", dependencies=guard)
    def memory_graph() -> dict[str, Any]:
        return graph.build(
            episodes=app.state.episodes,
            workspace=app.state.workspace,
            tasks=app.state.tasks,
            store=app.state.store,
            knowledge=app.state.claims,
            eigene=_eigene_adressen(),
        ).to_dict()

    @app.get("/api/v1/memory/entities", dependencies=guard)
    def memory_entities() -> dict[str, Any]:
        """Ein gemeinsamer, rein abgeleiteter Index für spätere Profile."""
        memory_graph = graph.build(
            episodes=app.state.episodes,
            workspace=app.state.workspace,
            tasks=app.state.tasks,
            store=app.state.store,
            knowledge=app.state.claims,
            eigene=_eigene_adressen(),
        )
        return {
            "authority": "projection",
            "generated_at": memory_graph.generated_at.astimezone().isoformat(),
            "entities": graph.entity_directory(memory_graph),
        }

    @app.get("/api/v1/memory/registry", dependencies=guard)
    def registry_entities(kind: str | None = None, label: str | None = None) -> dict[str, Any]:
        try:
            registry = app.state.claims.entities
            items = registry.search(label, kind) if label is not None else registry.list(kind)
            return {"entities": items, "authority": "explicit_identity_registry"}
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/memory/registry", dependencies=guard, status_code=201)
    def create_registry_entity(body: EntityCreateIn) -> dict[str, Any]:
        try:
            return app.state.claims.entities.create(body.kind, body.label)
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch("/api/v1/memory/registry/{entity_id}", dependencies=guard)
    def rename_registry_entity(entity_id: str, body: EntityRenameIn) -> dict[str, Any]:
        try:
            return app.state.claims.entities.rename(entity_id, body.label)
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/memory/registry/{entity_id}/sources", dependencies=guard)
    def link_registry_source(entity_id: str, body: EntitySourceIn) -> dict[str, Any]:
        try:
            app.state.claims.entities.link_source(entity_id, body.source, body.account, body.native_id)
            return {"entity_id": entity_id, **body.model_dump()}
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/v1/memory/registry/{entity_id}/sources", dependencies=guard)
    def unlink_registry_source(entity_id: str, body: EntitySourceIn) -> dict[str, Any]:
        try:
            registry = app.state.claims.entities
            removed = registry.unlink_source(body.source, body.account, body.native_id, entity_id=entity_id)
            if not removed:
                raise EntityError("Die Quelle ist dieser Entität nicht zugeordnet.")
            return {"unlinked": True}
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/memory/registry/{entity_id}", dependencies=guard)
    def registry_profile(entity_id: str) -> dict[str, Any]:
        try:
            entity = app.state.claims.entities.get(entity_id)
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if entity is None:
            raise HTTPException(status_code=404, detail="Unbekannte Entität")
        related = app.state.claims.by_reference(entity_id, include_inactive=True)
        usable_ids = {item.id for item in app.state.claims.by_reference(entity_id)}
        references = {ref for item in related for ref in (item.subject_ref, item.target_ref, item.scope_ref) if ref}
        related_entities = {ref: item for ref in references if (item := app.state.claims.entities.get(ref)) is not None}
        # Arbeitsprojekte bleiben in ihrer führenden Ablage. Nur exakte Kennungen
        # auflösen; ein gleicher Name begründet keine Zuordnung.
        for ref in references - related_entities.keys():
            try:
                project = app.state.workspace.project(ref.removeprefix("project:"))
            except WorkspaceError:
                continue
            related_entities[ref] = {"id": f"project:{project.id}", "kind": "project",
                                     "label": project.name, "workspace_project_id": project.id}
        return {"entity": entity, "related_entities": related_entities,
                "sources": app.state.claims.entities.sources(entity_id),
                "same_name_entities": [item for item in app.state.claims.entities.search(entity["label"], entity["kind"]) if item["id"] != entity_id],
                "claims": [item.to_dict() for item in related if item.id in usable_ids],
                "claim_history": [item.to_dict() for item in related if item.id not in usable_ids],
                "revision": app.state.claims.revision}

    @app.post("/api/v1/memory/claims/{claim_id}/retract", dependencies=guard)
    def retract_memory_claim(claim_id: str, body: KnowledgeRetractIn) -> dict[str, Any]:
        try:
            with app.state.conversation_lock:
                claim = app.state.claims.retract(claim_id, reason=body.reason)
            return {"claim": claim.to_dict(), "revision": app.state.claims.revision}
        except ClaimError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/memory/claims/{claim_id}/correct", dependencies=guard)
    def correct_memory_claim(claim_id: str, body: KnowledgeCorrectIn) -> dict[str, Any]:
        from .relations import validate_interval
        try:
            validate_interval(body.valid_from, body.valid_until)
            for name in ("value", "statement", "reason", "scope_ref", "target_ref"):
                value = getattr(body, name)
                if value is not None and not value.strip():
                    raise ValueError("Leere Angaben sind nicht zulässig.")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            with app.state.conversation_lock:
                old = app.state.claims.get(claim_id)
                if old.status.value != "active":
                    raise ClaimError("Diese Aussage ist nicht mehr aktiv. Bitte das Profil neu laden.")
                content = {**body.model_dump(mode="json"), "correction_of": claim_id,
                           "subject_ref": old.subject_ref, "predicate": old.predicate}
                episode, _ = app.state.episodes.record(
                    EpisodeKind.MESSAGE, "Ausdrückliche Wissenskorrektur",
                    json.dumps(content, ensure_ascii=False, sort_keys=True),
                    Provenance(source_type=SourceType.USER_STATED,
                               captured_at=datetime.now().astimezone()),
                    tags=["knowledge:correction"],
                )
                proposal, _ = app.state.knowledge_service.propose(
                    subject_ref=old.subject_ref, predicate=old.predicate,
                    value=body.value.strip(), statement=body.statement.strip(),
                    rationale=body.reason.strip(), scope_ref=body.scope_ref,
                    target_ref=body.target_ref, valid_from=body.valid_from,
                    valid_until=body.valid_until, proposed_by="user:correction",
                    evidence=[Evidence(episode_id=episode.id, quote=episode.body, digest=episode.digest)],
                )
                try:
                    claim = app.state.knowledge_service.accept(
                        proposal.id, supersedes=[claim_id], correction_of=claim_id,
                    )
                except ClaimError:
                    app.state.knowledge_service.reject(proposal.id)
                    raise
            return {"claim": claim.to_dict(), "revision": app.state.claims.revision}
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/memory/changes", dependencies=guard)
    def memory_changes(after: int = 0) -> dict[str, Any]:
        return {"revision": app.state.claims.revision, "changes": app.state.claims.changes(after=after)}

    @app.get("/api/v1/memory/people/{name}", dependencies=guard)
    def memory_person(name: str) -> dict[str, Any]:
        try:
            profile = graph.person_profile(
                name,
                episodes=app.state.episodes,
                workspace=app.state.workspace,
                tasks=app.state.tasks,
                store=app.state.store,
                knowledge=app.state.claims,
                eigene=_eigene_adressen(),
            )
        except personen.Mehrdeutig as fehler:
            raise _mehrdeutig_melden(fehler) from fehler
        if profile is None:
            raise HTTPException(
                status_code=404,
                detail=f"In deinen Aufzeichnungen kommt „{name}“ nicht vor.",
            )
        return profile

    @app.get("/api/v1/memory/projects/{project_id}", dependencies=guard)
    def memory_project(project_id: str) -> dict[str, Any]:
        try:
            return graph.project_profile(
                project_id,
                episodes=app.state.episodes,
                workspace=app.state.workspace,
                tasks=app.state.tasks,
                knowledge=app.state.claims,
                eigene=_eigene_adressen(),
            )
        except WorkspaceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _mappen_termine():
        agent = getattr(app.state, 'agent', None)
        entries = getattr(agent, '_calendar_entries', None)
        return entries() if callable(entries) else []

    @app.get("/api/v1/memory/projects/{project_id}/einzelheiten", dependencies=guard)
    def memory_project_details(project_id: str, alle: bool = False) -> dict[str, Any]:
        """Mappe, Ebene 2: offene Punkte eines Projekts ohne Modell."""
        daten = _projekt_mappe(app, project_id, alle=alle)
        if daten is None:
            raise HTTPException(status_code=404, detail="Unbekanntes Projekt")
        return daten

    @app.get("/api/v1/memory/people/{name}/einzelheiten", dependencies=guard)
    def memory_person_details(name: str, alle: bool = False) -> dict[str, Any]:
        """Mappe, Ebene 2: offene Punkte mit einer Person ohne Modell.

        Ohne Profilaufbau: Die Quellen der Person kommen aus einer schlanken
        Abfrage, nicht aus einem Durchlauf über den ganzen Bestand.
        """
        from email.utils import parseaddr
        from . import personen
        from .mappe import einzelheiten
        ids = app.state.episodes.participant_ids(name)
        adressen = app.state.episodes.addresses_for_name(name) if '@' not in name else []
        if len(adressen) > 1:
            # Zwei Menschen mit demselben Namen: nicht mischen, nicht raten.
            raise HTTPException(
                status_code=409,
                detail=f"„{name}“ gehört mehreren Menschen: {'; '.join(adressen)}. Bitte die Adresse angeben.")
        key = personen.schluessel(name)
        tasks = [task for task in app.state.tasks.open_tasks(limit=None)
                 if task.wartet_auf and personen.schluessel(task.wartet_auf) == key]
        if not ids and not tasks:
            raise HTTPException(status_code=404, detail=f"In deinen Aufzeichnungen kommt „{name}“ nicht vor.")
        # Name gegen Titel und Ort, Adresse gegen die Gäste; nie gemischt.
        anzeige, adresse = parseaddr(name) if '@' in name else (name, '')
        namen = [anzeige] if anzeige else []
        if adresse and not namen:
            # Nur die Adresse angegeben: Ihre Anzeigenamen gelten gegen Titel und Ort.
            from .kontakte import anzeigename
            namen = [n for n in (anzeigename(e['name']) for e in
                                 app.state.episodes.participants_for_address(adresse, anzeigenamen=True)[:3]) if n]
        return einzelheiten(ids, episodes=app.state.episodes, claims=app.state.claims, tasks=tasks,
                            termine=_mappen_termine(), namen=namen,
                            adressen=[adresse] if adresse else [], alle=alle)

    @app.get("/api/v1/memory/candidates", dependencies=guard)
    def memory_candidates() -> list[dict[str, Any]]:
        return [item.to_dict() for item in app.state.knowledge_service.pending()]

    @app.post("/api/v1/memory/candidates", dependencies=guard, status_code=201)
    def propose_memory_candidate(body: KnowledgeCandidateIn) -> dict[str, Any]:
        try:
            with app.state.conversation_lock:
                proposal, created = app.state.knowledge_service.propose(
                    subject_ref=body.subject_ref,
                    predicate=body.predicate,
                    value=body.value,
                    statement=body.statement,
                    rationale=body.rationale,
                    scope_ref=body.scope_ref,
                    target_ref=body.target_ref, valid_from=body.valid_from, valid_until=body.valid_until,
                    depends_on=body.depends_on,
                    confidence=body.confidence,
                    evidence=[Evidence(**item.model_dump()) for item in body.evidence],
                    proposed_by=body.proposed_by,
                )
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"candidate": proposal.to_dict(), "created": created}

    @app.get("/api/v1/memory/clarifications", dependencies=guard)
    def memory_clarifications() -> list[dict[str, Any]]:
        return app.state.knowledge_service.clarifications()

    @app.get('/api/v1/memory/questions', dependencies=guard)
    def memory_questions() -> dict[str, Any]:
        from .memory_questions import list_questions
        questions = list_questions(app)
        return {'items': questions[:50], 'truncated': len(questions) > 50}

    @app.post('/api/v1/memory/questions/{question_id}/resolve', dependencies=guard)
    def resolve_memory_question(question_id: str, body: MemoryQuestionIn) -> dict[str, Any]:
        from .memory_questions import resolve_question
        return resolve_question(app, question_id, stand=body.stand, proposal_id=body.proposal_id)

    @app.post(
        "/api/v1/memory/candidates/{proposal_id}/accept",
        dependencies=guard,
    )
    def accept_memory_candidate(
        proposal_id: str, body: KnowledgeAcceptIn
    ) -> dict[str, Any]:
        try:
            with app.state.conversation_lock:
                claim = app.state.knowledge_service.accept(
                    proposal_id, supersedes=body.supersedes
                )
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return claim.to_dict()

    @app.post(
        "/api/v1/memory/candidates/{proposal_id}/reject",
        dependencies=guard,
    )
    def reject_memory_candidate(proposal_id: str) -> dict[str, Any]:
        try:
            with app.state.conversation_lock:
                return app.state.knowledge_service.reject(proposal_id).to_dict()
        except (ClaimError, ProposalError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # -- Aufnahme ----------------------------------------------------------

    @app.get("/ingest/adapters", dependencies=guard)
    def adapters() -> dict[str, Any]:
        return {
            "adapters": sorted(ADAPTERS),
            # Ohne freigegebene Ordner geht nichts. Die Oberfläche soll das
            # sagen können, statt den Nutzer in einen Fehler laufen zu lassen.
            "file_roots": [str(p) for p in file_roots_from_env(os.environ.get(ROOTS_ENV))],
        }

    @app.post("/ingest", dependencies=guard)
    def ingest(body: IngestIn) -> dict[str, Any]:
        """Liest einen Ordner ein. Alles landet als Episode, nichts im Bestand."""
        try:
            with app.state.conversation_lock:
                report = ingest_directory(
                    app.state.episodes, body.path, body.adapter,
                    roots=file_roots_from_env(os.environ.get(ROOTS_ENV)),
                    limit=body.limit,
                    on_source=lambda root, ref, episode: track_document(app.state.episodes, app.state.claims, root, ref, episode),
                    on_complete=lambda root, adapter, observed: exclude_missing_documents(app.state.episodes, app.state.claims, root, adapter, observed),
                    on_transcript=nach_aufnahme(app),
                )
        except SecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return report.to_dict()

    # -- Verdichtung -------------------------------------------------------
    #
    # Die Regel steht in docs/08-gedaechtnisschichten.md: Verdichtung schlägt
    # vor, sie schreibt nicht. Deshalb gibt es hier keinen Endpunkt, der eine
    # Aussage direkt aus einer Episode erzeugt — der Weg führt immer über einen
    # Vorschlag und dessen Annahme.

    @app.post("/consolidate", dependencies=guard)
    def consolidate(body: ConsolidateIn) -> dict[str, Any]:
        report = app.state.consolidator.run(
            limit=body.limit, with_model=body.with_model
        )
        return {**report.to_dict(), "summary": report.summary()}

    @app.get("/proposals", dependencies=guard)
    def list_proposals(
        kind: ProposalKind | None = None, all: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        items = (
            app.state.proposals.all_proposals(limit)
            if all else app.state.proposals.pending(kind, limit)
        )
        return [p.to_dict() for p in items]

    @app.get("/proposals/counts", dependencies=guard)
    def proposal_counts() -> dict[str, int]:
        return app.state.proposals.counts()

    @app.post("/proposals/{proposal_id}/accept", dependencies=guard)
    def accept_proposal(proposal_id: str) -> dict[str, Any]:
        try:
            assertion = app.state.consolidator.accept(proposal_id)
        except ProposalError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "proposal": app.state.proposals.get(proposal_id).to_dict(),
            "assertion": assertion.to_dict() if assertion else None,
        }

    @app.post("/proposals/{proposal_id}/reject", dependencies=guard)
    def reject_proposal(proposal_id: str) -> dict[str, Any]:
        try:
            app.state.consolidator.reject(proposal_id)
        except ProposalError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return app.state.proposals.get(proposal_id).to_dict()

    # -- Zusammenfassung ---------------------------------------------------
    #
    # Sie schreibt eine Episode, keine Aussage. Der Unterschied trägt das ganze
    # Verfahren: Episoden behaupten nichts über die Person, und die Quellen
    # bleiben liegen, statt ersetzt zu werden.

    @app.get("/summaries", dependencies=guard)
    def list_summaries() -> dict[str, Any]:
        """Was zusammengefasst ist — und was es könnte, auch ohne Modell."""
        return {
            "items": [e.to_dict() for e in app.state.episodes.summaries()],
            "candidates": [
                k.to_dict() for k in app.state.summarizer.candidates()
                if len(k.episodes) >= MIN_EPISODES
            ],
        }

    @app.post("/summaries/run", dependencies=guard)
    def run_summaries(body: SummariseIn) -> dict[str, Any]:
        report = app.state.summarizer.run(
            limit=body.limit, with_model=body.with_model
        )
        return {**report.to_dict(), "summary": report.summary()}

    @app.delete("/summaries/{episode_id}", dependencies=guard)
    def delete_summary(episode_id: str) -> dict[str, Any]:
        """Nimmt sie zurück und holt die Quellen hervor.

        Ohne diesen Weg wäre das Zusammenfassen eine Einbahnstraße — ein Monat,
        den ein Modell falsch gelesen hat, wäre faktisch ersetzt.
        """
        try:
            zurueck = app.state.episodes.delete_summary(episode_id)
        except EpisodeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"restored": zurueck}

    # -- Zeitplan ----------------------------------------------------------
    #
    # Er macht die Vorschlagsschlange voller, nie den Bestand. Das ist die
    # Eigenschaft, die ihn unbedenklich macht: Im schlimmsten Fall entsteht
    # Arbeit, die jemand ignoriert — nie ein falscher Fakt.

    def kosten_modell(app) -> str | None:
        plan = app.state.settings.schedule
        if not plan.with_model or getattr(plan, "local_model_only", False):
            return None
        try:
            anbieter = rollen_von(app).provider("hintergrund")
        except Exception:  # noqa: BLE001
            return None
        if anbieter is None or getattr(anbieter, "is_local", False):
            return None
        return str(getattr(anbieter, "model", "") or getattr(anbieter, "name", "") or "ein Modell im Internet")

    def mail_stand_lesen(app) -> list[dict[str, Any]]:
        from .mail_stand import stand
        try:
            return stand(app)
        except Exception:  # noqa: BLE001 - der Zeitplan bleibt lesbar, auch wenn der Stand gerade nicht zu bilden ist
            return []

    @app.get("/api/v1/schedule", dependencies=guard)
    @app.get("/schedule", dependencies=guard)
    def get_schedule() -> dict[str, Any]:
        return {
            **app.state.scheduler.state(),
            "sources": dict(app.state.settings.schedule.sources),
            "mail_accounts": list(app.state.settings.schedule.mail_accounts),
            "mail_status": dict(app.state.settings.mail_sync_status),
            # Die eine Aussage je Postfach, dieselbe wie auf Heute und in der Einrichtung (Fremdprobe 2, Befund 17).
            "mail_stand": mail_stand_lesen(app),
            # Welches Modell beim Abruf Kosten verursachen kann; None, wenn nur ein Modell auf diesem Rechner (oder gar
            # keines) gerufen wird. Ohne Kosten keine Kostenwarnung (Fremdprobe 2, Befund 28).
            "kosten_modell": kosten_modell(app),
            "backup": app.state.settings.schedule.backup,
        }

    @app.put("/api/v1/schedule", dependencies=guard)
    @app.put("/schedule", dependencies=guard)
    def put_schedule(body: ScheduleIn) -> dict[str, Any]:
        plan = app.state.settings.schedule
        if body.sources is not None and set(body.sources.values()) - set(ADAPTERS):
            raise HTTPException(status_code=400, detail=f"Unbekannte Quelle: {', '.join(sorted(set(body.sources.values()) - set(ADAPTERS)))}")
        if body.mail_accounts is not None:
            available = set()
            for entry in app.state.settings.mail_accounts:
                if not entry.configured:
                    continue
                try:
                    app.state.mail.reader_for(entry.id)
                    available.add(entry.id)
                except (AttributeError, KeyError, ValueError, MailError):
                    pass
            if set(body.mail_accounts) - available:
                raise HTTPException(status_code=422, detail="Bitte nur eingerichtete Mailkonten auswählen.")
            with app.state.conversation_lock:
                previous = plan.mail_accounts
                plan.mail_accounts = list(dict.fromkeys(body.mail_accounts))
                try:
                    config.save(_data_dir(), app.state.settings)
                except Exception:
                    plan.mail_accounts = previous
                    raise
        if body.enabled is not None:
            with app.state.conversation_lock:
                plan.enabled = body.enabled
        if body.interval_minutes is not None:
            # Die Oberfläche schickt den Abstand bei jedem Speichern mit; gewählt ist er erst, wenn er sich ändert.
            if body.interval_minutes != plan.interval_minutes:
                plan.interval_gewaehlt = True
            plan.interval_minutes = body.interval_minutes
        if body.with_model is not None:
            plan.with_model = body.with_model
        if body.sources is not None:
            unbekannt = sorted(set(body.sources.values()) - set(ADAPTERS))
            if unbekannt:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unbekannte Quelle: {', '.join(unbekannt)}",
                )
            plan.sources = dict(body.sources)
        if body.backup is not None:
            plan.backup = body.backup

        config.save(_data_dir(), app.state.settings)
        if not plan.enabled:
            app.state.scheduler.stop()
        _wire_scheduler(app)
        return get_schedule()

    @app.post("/schedule/run", dependencies=guard)
    def run_schedule() -> dict[str, Any]:
        """Einen Durchgang von Hand auslösen — auch wenn der Plan aus ist."""
        report = app.state.scheduler.run_once()
        return {**report.to_dict(), "summary": report.summary()}

    # -- Werkzeuge ---------------------------------------------------------
    #
    # Die Tür für andere Assistenten (siehe mcp.py). Bewusst *nicht* an der
    # Policy vorbei: `agent.invoke()` geht durch dieselbe Prüfung wie das
    # Modell im Haus, und Außenwirksames kommt als Antrag zurück, statt
    # ausgeführt zu werden.

    @app.get("/tools", dependencies=tuer_guard)
    def list_tools() -> list[dict[str, Any]]:
        return app.state.agent.tool_schemas(fuer_tuer=True)

    @app.post("/tools/{name}", dependencies=tuer_guard)
    def call_tool(name: str, body: ToolIn) -> dict[str, Any]:
        return app.state.agent.invoke(name, body.model_dump())

    # -- Sicherung ---------------------------------------------------------

    @app.get("/backups", dependencies=guard)
    def backups() -> list[dict[str, Any]]:
        return list_snapshots(_data_dir() / "sicherungen")

    @app.post("/backups", dependencies=guard, status_code=201)
    def create_backup(vor_update: bool = False) -> dict[str, Any]:
        # `vor_update`: die Sicherung, die die Mac-App vor einem Update anlegt; dieselbe wie bei
        # `make aktualisieren`, damit `make zurueck-vor-update` sie findet.
        from .backup import UPDATE_SET_PREFIX
        try:
            path = (snapshot_all(_data_dir(), _data_dir() / "sicherungen", keep=3, prefix=UPDATE_SET_PREFIX)
                    if vor_update else snapshot_all(_data_dir(), _data_dir() / "sicherungen"))
        except BackupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "path": str(path),
            "name": path.name,
            "kind": "kingfisher-snapshot",
        }

    @app.post("/backups/restore", dependencies=guard)
    def restore_backup(body: RestoreIn) -> dict[str, Any]:
        """Spielt eine Sicherung zurück.

        Ohne diesen Weg wäre das Sichern eine Beruhigung ohne Deckung: Der
        Zeitplan legt bei jedem Lauf einen Snapshot an, und am Tag, an dem man
        ihn braucht, käme man nicht heran.

        `restore()` legt den bestehenden Stand vorher zur Seite, statt ihn zu
        überschreiben — eine Wiederherstellung, die den aktuellen Stand
        vernichtet, wäre ein zweiter Weg, alles zu verlieren.

        Nur ein Name, kein Pfad: Sonst wäre dies ein Weg, jede beliebige Datei
        des Rechners zur Datenbank zu erklären.
        """
        data_dir = _data_dir()
        ordner = data_dir / "sicherungen"
        ziel = ordner / Path(body.name).name
        if not ziel.is_file() and not ziel.is_dir():
            raise HTTPException(
                status_code=404, detail=f"Keine Sicherung namens {body.name}."
            )
        try:
            from .backup import verify_legacy_snapshot, verify_snapshot_set
            if ziel.is_dir():
                verify_snapshot_set(ziel)
            else:
                verify_legacy_snapshot(ziel)
            # The middleware owns the exclusive boundary: no HTTP/Agent/worker
            # operation is still using these integrations when files are replaced.
            scheduler = getattr(app.state, "scheduler", None)
            if scheduler is not None:
                scheduler.stop()
            for connection, _ in (getattr(app.state, 'mcp', None) or {}).values():
                process = getattr(connection, '_prozess', None)
                try:
                    connection.stop()
                    if process is not None and process.poll() is None:
                        raise RuntimeError('MCP process still running')
                except Exception:
                    raise BackupError('Eine Verbindung konnte nicht beendet werden. Der Datenbestand wurde nicht ersetzt.') from None
            app.state.mcp = {}
            if ziel.is_dir():
                # Während des Restore darf weder der Zeitplan noch eine
                # Anfrage in eine gerade ersetzte Datenbank schreiben.
                _close_persistent_state(app)
                try:
                    restore_all(ziel, data_dir)
                finally:
                    # `restore_all` rollt eine fehlgeschlagene Dateiumsetzung
                    # zurück. Die Handles sind dennoch geschlossen und müssen
                    # in jedem Fall wieder geöffnet werden, sonst bliebe die
                    # App nach einem abgewiesenen Snapshot tot zurück.
                    _reopen_persistent_state(app)
            else:
                # Bestehende Icarus-Snapshots bleiben lesbar, sie enthalten
                # aber absichtlich nur das damalige Selbstmodell.
                restore(ziel, data_dir / "self-model.sqlite3")
        except BackupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        from .restore_boundary import pending
        if pending(data_dir):
            from .restore_inspection import assertion_count
            return {'restored': ziel.name, 'mode': 'inspection', 'operational': False,
                    'assertions': assertion_count(data_dir),
                    'detail': 'Historischer Sicherungsstand geöffnet. Modelle, Verbindungen und Aktionen bleiben gesperrt. Der bisherige Stand liegt unter vor-wiederherstellung. Bitte die Wiederherstellungsansicht öffnen.'}

        # Der Store hält eine offene Verbindung auf die alte Datei. Ohne
        # Neuaufbau liest die App weiter den Stand, den sie gerade ersetzt hat —
        # die Wiederherstellung sähe aus, als hätte sie nichts getan.
        #
        # Genau so aufgebaut wie beim Start, nicht „irgendein SQLite-Backend":
        # Mit `SqliteBackend` verlöre ein Nutzer mit cognee still die
        # semantische Suche, und `subject_id` muss derselbe bleiben, sonst
        # gehört der wiederhergestellte Bestand plötzlich jemand anderem.
        #
        # Nur wenn wir das Backend selbst angelegt haben. Wurde eines von außen
        # hereingereicht (Tests), gehört es nicht uns.
        if ziel.is_file() and getattr(app.state, "backend", None) is not None:
            app.state.backend = CogneeBackend(data_dir / "self-model.sqlite3")
            app.state.store = SelfModelStore(app.state.backend, subject_id="local")
            app.state.support_review = SupportReview(app.state.store, app.state.proposals, app.state.episodes, app.state.audit)
            _build_agent(app)

        return {
            "restored": ziel.name,
            "assertions": len(app.state.store.export().assertions),
            "detail": (
                "Alle gespeicherten Kingfisher-Daten wurden wiederhergestellt. "
                "Der vorherige Stand liegt je Datei daneben als "
                "…vor-wiederherstellung-…."
                if ziel.is_dir() else
                "Nur das Selbstmodell dieses alten Icarus-Snapshots wurde "
                "wiederhergestellt. Der vorherige Stand liegt daneben als "
                "self-model.vor-wiederherstellung-….sqlite3."
            ),
        }

    @app.post("/export/file", dependencies=guard)
    def export_file(body: ExportIn) -> dict[str, Any]:
        """Schreibt einen Export, optional verschlüsselt.

        Ohne Passphrase entsteht lesbares JSON — das ist gewollt, weil ein
        Format, das nur dieses Programm lesen kann, in zehn Jahren wertlos ist.
        """
        payload = export_model(app.state.store.export().to_dict(), body.passphrase)
        target = _data_dir() / "exporte"
        target.mkdir(parents=True, exist_ok=True)
        suffix = "icarus" if body.passphrase else "json"
        path = target / f"selbstmodell-{datetime.now():%Y%m%dT%H%M%S}.{suffix}"
        path.write_text(payload, encoding="utf-8")
        logbuch.vermerke("export", was="selbstmodell")
        return {"path": str(path), "encrypted": bool(body.passphrase)}

    @app.post("/export/verify", dependencies=guard)
    def verify_export(body: VerifyIn) -> dict[str, Any]:
        """Prüft, ob ein Export lesbar ist — bevor man sich darauf verlässt.

        Eine Sicherung, die niemand je zurückgelesen hat, ist keine Sicherung.
        """
        try:
            document = import_model(Path(body.path).read_text(encoding="utf-8"), body.passphrase)
        except (BackupError, OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "ok": True,
            "schema_version": document.get("schema_version"),
            "assertions": len(document.get("assertions", [])),
        }

    from .mail_reply_suggestions import register_reply_suggestions
    from .mail_briefing import register as register_mail_briefing
    register_mail_briefing(app, guard, _read_mail)
    register_reply_suggestions(app, guard)
    from .mail_style import register_mail_style
    register_mail_style(app, guard)
    from .working_profile import register as register_working_profile
    register_working_profile(app, guard)
    from .local_audio import register_local_audio_routes
    register_local_audio_routes(app, guard)
    from .mail_filter_routes import register_mail_filter_routes
    register_mail_filter_routes(app, guard, _data_dir)
    from .folder_sync import register_folder_routes
    register_folder_routes(app, guard, _data_dir)
    from .transkript_routes import register_transkript_routes
    register_transkript_routes(app, guard, _data_dir)
    from .rueckmeldung_routes import register as register_rueckmeldung
    register_rueckmeldung(app, guard, _data_dir)
    from .logbuch_routes import register as register_logbuch
    register_logbuch(app, guard, _data_dir)
    from .fassung_routes import register as register_fassung
    register_fassung(app, guard, _data_dir)
    from .uebernehmen_routes import register as register_uebernehmen
    register_uebernehmen(app, guard)
    from .lint_routes import register as register_lint
    register_lint(app, guard, _data_dir)
    from . import akten_arten_routes, kreis_routes, wiederkehrendes_routes
    kreis_routes.register(app, guard)
    akten_arten_routes.register(app, guard)
    wiederkehrendes_routes.register(app, guard)
    # Das Logbuch nennt morgens die offenen Befunde des Lint (docs/44, docs/42); fehlt eines von beiden, bleibt es still.
    if getattr(app.state, "logbuch", None) is not None:
        from .lint import zusammenfassung as lint_zusammenfassung
        from .logbuch_routes import befunde_lieferant_setzen
        befunde_lieferant_setzen(app, lambda: lint_zusammenfassung(app).get("je_art", {}))
    from .routing_runtime import register_routing_routes
    register_routing_routes(app, guard, _data_dir)
    from .learning_routes import register_learning_routes
    register_learning_routes(app, guard)
    from .world_routes import register_world_routes
    register_world_routes(app, guard, _data_dir)

    from .health_observations import register as register_health_observations
    register_health_observations(app, guard)

    # -- Oberfläche --------------------------------------------------------
    #
    # Ganz zum Schluss, und das ist keine Kosmetik: Ein Mount auf "/" fängt
    # alles ab, was vorher nicht als Route registriert wurde. Stünde er weiter
    # oben, wären alle danach angemeldeten Endpunkte unerreichbar.
    #
    # Nur wenn eine gebaute Oberfläche vorhanden ist (Container, `app/dist`).

    ui = _ui_dir()
    if ui is not None:
        # Die Dateien selbst sind **nicht** durch das Token geschützt, und das
        # ist Absicht: Sie enthalten kein Nutzerdatum, nur HTML, CSS und
        # JavaScript. Beim ersten lokalen UI-Aufruf legt der Sidecar aber eine
        # HttpOnly-Sitzung für `/api` ab. So bleibt jeder Datenendpunkt
        # geschützt, ohne das Token in einer URL, im JavaScript oder im Log
        # sichtbar zu machen.
        # Die zwei kanonischen Routen sind clientseitig. Direkte Aufrufe und
        # Reloads müssen deshalb dasselbe index.html erhalten.
        def ui_response() -> FileResponse:
            response = FileResponse(ui / "index.html")
            if expected is not None:
                response.set_cookie(
                    key=UI_SESSION_COOKIE,
                    value=expected,
                    httponly=True,
                    samesite="strict",
                    path="/api",
                )
                response.headers["Cache-Control"] = "no-store"
            return response

        @app.get("/", include_in_schema=False)
        def root_ui() -> FileResponse:
            return ui_response()

        @app.get("/today", include_in_schema=False)
        def today_ui() -> FileResponse:
            return ui_response()

        @app.get("/world", include_in_schema=False)
        def world_ui() -> FileResponse:
            return ui_response()

        @app.get("/memory", include_in_schema=False)
        @app.get("/review", include_in_schema=False)
        def memory_ui() -> FileResponse:
            return ui_response()

        @app.get("/settings", include_in_schema=False)
        def settings_ui() -> FileResponse:
            return ui_response()

        @app.get("/calendar", include_in_schema=False)
        def calendar_ui() -> FileResponse:
            return ui_response()

        @app.get("/vorhaben", include_in_schema=False)
        def tasks_ui() -> FileResponse:
            return ui_response()

        @app.get("/wellbeing", include_in_schema=False)
        @app.get("/development", include_in_schema=False)
        def development_ui() -> FileResponse:
            return ui_response()

        @app.get("/nachrichten", include_in_schema=False)
        def messages_ui() -> FileResponse:
            return ui_response()

        @app.get("/willkommen", include_in_schema=False)
        def willkommen_ui() -> FileResponse:
            return ui_response()

        @app.get("/memory/registry/{entity_id}", include_in_schema=False)
        def registry_profile_ui(entity_id: str) -> FileResponse:
            del entity_id
            return ui_response()

        @app.get("/memory/people/{name}", include_in_schema=False)
        def person_profile_ui(name: str) -> FileResponse:
            del name
            return ui_response()

        @app.get("/memory/projects/{project_id}", include_in_schema=False)
        def project_profile_ui(project_id: str) -> FileResponse:
            del project_id
            return ui_response()

        @app.get("/memory/akte/{sache:path}", include_in_schema=False)
        def akte_ui(sache: str) -> FileResponse:
            del sache
            return ui_response()

        @app.get("/conversations", include_in_schema=False)
        def conversations_ui() -> FileResponse:
            return ui_response()

        @app.get("/conversations/{conversation_id}", include_in_schema=False)
        def conversation_ui(conversation_id: str) -> FileResponse:
            del conversation_id
            return ui_response()

        app.mount("/", StaticFiles(directory=str(ui), html=True), name="ui")
        app.state.ui_dir = str(ui)

    return app



def write_connection_file(directory: Path, port: int, token: str | None) -> Path:
    """Hinterlegt Adresse und Token für die MCP-Tür.

    Die App vergibt Port und Token bei jedem Start neu. Ohne diese Datei müsste
    der Nutzer beides von Hand in die Konfiguration seines Assistenten
    eintragen — und nach jedem Neustart erneut.

    Die Datei enthält ein Token und gehört deshalb niemandem sonst: 0600, und
    das Verzeichnis 0700. Auf Windows greifen die Bits nicht; dort schützt die
    Lage im Benutzerprofil.
    """
    directory.mkdir(parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    path = directory / "verbindung.json"
    payload = {"url": f"http://127.0.0.1:{port}", "token": token}
    # Erst die Rechte, dann der Inhalt — sonst steht das Token kurzzeitig
    # unter den Standardrechten auf der Platte.
    path.touch(mode=0o600, exist_ok=True)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def browser_address(port: int) -> str:
    """Öffentliche lokale Einstiegadresse, ohne Geheimnis in der URL."""
    return f"http://127.0.0.1:{port}/today"


def main() -> None:  # pragma: no cover
    import uvicorn

    # Ein Einstieg, zwei Rollen: `--mcp` startet die MCP-Tür statt des Servers.
    # Beim Installieren über pip gibt es daneben den eigenen Befehl `icarus-mcp`.
    if "--mcp" in sys.argv[1:]:
        from .mcp import main as mcp_main

        mcp_main()
        return

    port = int(os.environ.get("ICARUS_SIDECAR_PORT", "8765"))
    host = os.environ.get(HOST_ENV, DEFAULT_HOST)
    token = os.environ.get(TOKEN_ENV)
    write_connection_file(_data_dir(), port, token)

    if _ui_dir() is not None:
        print(f"\n  Kingfisher läuft:  {browser_address(port)}\n", flush=True)
        if not token:
            print(
                "  WARNUNG: Ohne ICARUS_SIDECAR_TOKEN kann jeder Prozess auf "
                "diesem Rechner das Gedächtnis auslesen.\n",
                flush=True,
            )
    if host != DEFAULT_HOST:
        print(
            f"  Hinweis: Es wird an {host} gebunden statt an {DEFAULT_HOST}. "
            "Im Container ist das richtig — die Portfreigabe muss dann aber "
            "auf 127.0.0.1 beschränkt sein.\n",
            flush=True,
        )

    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":  # pragma: no cover
    main()
