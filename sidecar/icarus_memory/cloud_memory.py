"""Explicitly scoped, bounded processing through a ChatGPT subscription."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import nullcontext
from pathlib import Path

from . import abschnitte
from .memory_categories import Categories
from .memory_categories import SourceValidationError
from .model import SourceType
from .providers import ProviderError
from .restore_boundary import guarded
from .source_processing_policy import ExplicitSourcePolicy
from .working_memory_analysis import UnsupportedSource, abschnitte_der, interpret_abschnitt
from .working_memory_store import WorkingMemoryStore, source_fingerprint

MAX_SOURCES = 100
MAX_BULK_SOURCES = 1000
REQUESTS_PER_SOURCE = 4
MAX_CANDIDATES = 2000
PREVIEW_TTL = 15 * 60


class CloudMemoryError(ValueError):
    pass


class _ScopedProvider:
    """Count each request and recheck consent, source, and OAuth grant at send time."""
    is_local = False
    is_remote = True

    def __init__(self, provider, policy, before_request):
        self._provider = provider
        self._policy = policy
        self._before_request = before_request
        self.name = getattr(provider, "name", "chatgpt")
        self.model = getattr(provider, "model", "")
        self.grant_id = getattr(provider, "grant_id", None)
        self.entity_anchor_mode = getattr(provider, "entity_anchor_mode", "absolute")

    def complete_json(self, messages, *, max_tokens, schema):
        guarded_call = getattr(self._provider, "complete_json_guarded", None)
        if callable(guarded_call):
            return guarded_call(
                messages, max_tokens=max_tokens, schema=schema,
                before_send=self._before_request,
                still_permitted=lambda: self._policy.permits(self, self._episode),
            )
        self._before_request()
        return self._provider.complete_json(messages, max_tokens=max_tokens, schema=schema)


class CloudMemoryJobs:
    def __init__(self, episodes, database: Path, provider_factory, grant_status,
                 permission_lock=None, runtime_boundary=None):
        self.episodes = episodes
        self.memory = WorkingMemoryStore(episodes)
        self.categories = Categories(episodes)
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.provider_factory = provider_factory
        self.grant_status = grant_status
        self.permission_lock = permission_lock or threading.RLock()
        self._runtime_boundary = runtime_boundary
        self.lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS cloud_memory_previews (
                id TEXT PRIMARY KEY, purpose TEXT NOT NULL, model_scope TEXT NOT NULL,
                grant_id TEXT, sources TEXT NOT NULL, expires_at REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS cloud_memory_jobs (
                id TEXT PRIMARY KEY, purpose TEXT NOT NULL, model TEXT NOT NULL,
                grant_id TEXT NOT NULL, source_ids TEXT NOT NULL, fingerprints TEXT NOT NULL,
                source_limit INTEGER NOT NULL DEFAULT 100,
                state TEXT NOT NULL, consent INTEGER NOT NULL, position INTEGER NOT NULL,
                requests INTEGER NOT NULL, completed INTEGER NOT NULL, failed INTEGER NOT NULL,
                stop_reason TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
            issue_schema = """CREATE TABLE IF NOT EXISTS cloud_memory_issues (
                job_id TEXT NOT NULL, episode_id TEXT NOT NULL,
                stage TEXT NOT NULL CHECK(stage IN ('source','categories')),
                code TEXT NOT NULL CHECK(code IN ('invalid_entity_evidence',
                    'invalid_category_evidence', 'invalid_output_format', 'unsupported_source')),
                PRIMARY KEY(job_id,episode_id))"""
            db.execute(issue_schema)
            issue_columns = {row[1] for row in db.execute("PRAGMA table_info(cloud_memory_issues)")}
            if "reason" not in issue_columns:
                db.execute("ALTER TABLE cloud_memory_issues ADD COLUMN reason TEXT NOT NULL DEFAULT 'unspecified'")
            columns = {row[1] for row in db.execute("PRAGMA table_info(cloud_memory_jobs)")}
            if "source_limit" not in columns:
                db.execute("ALTER TABLE cloud_memory_jobs ADD COLUMN source_limit INTEGER NOT NULL DEFAULT 100")
            # Recovery never resumes unattended; the user must press Resume.
            db.execute("UPDATE cloud_memory_jobs SET state='paused',stop_reason=?,updated_at=? WHERE state='running'",
                       ("App-Neustart; bitte ausdrücklich fortsetzen.", time.time()))

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _grant(self):
        status = self.grant_status() if callable(self.grant_status) else {}
        if not isinstance(status, dict):
            return None
        available = status.get("available", status.get("active", False))
        return status.get("grant_id") if available and isinstance(status.get("grant_id"), str) else None

    @staticmethod
    def _source_type(snapshot):
        return getattr(snapshot.episode.provenance, "source_type", None) is SourceType.EMAIL

    def _snapshot(self, episode_id):
        with self.episodes._lock:
            snapshot = self.memory._snapshot(episode_id)
            status = self.memory._status(episode_id)
            if (not self.memory._eligible(snapshot) or not self._source_type(snapshot)
                    or (status and status[1] == "dismissed")):
                return None
            return snapshot

    def _cloud_complete(self, episode_id, fingerprint):
        """A current remote result needs both derived layers before bulk skips it."""
        with self.episodes._lock:
            row = self.episodes._conn.execute(
                "SELECT fingerprint,status,model FROM working_memory_sources WHERE episode_id=?",
                (episode_id,)).fetchone()
            if not row or row[0] != fingerprint or row[1] != "complete" or not row[2].startswith("chatgpt:"):
                return False
        return self.categories.list_for(episode_id)["status"] in {"complete", "empty"}

    @guarded
    def preview(self, purpose="pilot", source_ids=None, limit=None, cursor=None):
        if purpose not in {"pilot", "bulk", "recheck"}:
            raise CloudMemoryError("Unbekannter Verarbeitungsumfang.")
        source_limit = MAX_SOURCES if purpose == "pilot" else MAX_BULK_SOURCES
        if limit is None:
            limit = source_limit
        if type(limit) is not int or not 1 <= limit <= source_limit:
            raise CloudMemoryError(f"Die Vorschau darf höchstens {source_limit} E-Mails enthalten.")
        if source_ids is not None and (type(source_ids) is not list or len(source_ids) > source_limit
                                       or any(type(i) is not str or not 1 <= len(i) <= 200 for i in source_ids)):
            raise CloudMemoryError(f"Bitte höchstens {source_limit} konkrete Quellen auswählen.")
        if cursor is not None and (source_ids is not None or type(cursor) is not int or cursor < 1):
            raise CloudMemoryError("Der Seitenzeiger gilt nur für eine ungefilterte Vorschau.")
        grant_id = self._grant()
        rowids = {}
        if source_ids is None:
            with self.episodes._lock:
                if cursor is None:
                    rows = self.episodes._conn.execute(
                        "SELECT rowid,id FROM episodes ORDER BY rowid DESC LIMIT ?",
                        (MAX_CANDIDATES + 1,)).fetchall()
                else:
                    rows = self.episodes._conn.execute(
                        "SELECT rowid,id FROM episodes WHERE rowid<? ORDER BY rowid DESC LIMIT ?",
                        (cursor, MAX_CANDIDATES + 1)).fetchall()
            has_more = len(rows) > MAX_CANDIDATES
            page = rows[:MAX_CANDIDATES]
            ids = [row[1] for row in page]
            rowids = {row[1]: row[0] for row in page}
            next_cursor = page[-1][0] if has_more and page else None
        else:
            ids = list(dict.fromkeys(source_ids))
            has_more = False
            next_cursor = None
        candidates = []
        for episode_id in ids:
            snapshot = self._snapshot(episode_id)
            if snapshot is None:
                continue
            fp = source_fingerprint(snapshot)
            # The pilot must include sources already classified locally. Bulk skips only
            # sources already completed by this explicit cloud workflow in both layers.
            if purpose == "bulk" and self._cloud_complete(episode_id, fp):
                continue
            episode = snapshot.episode
            candidate = {"id": episode.id, "fingerprint": fp,
                         "title": (episode.title or "")[:240],
                         "occurred_at": episode.occurred_at.isoformat() if episode.occurred_at else None}
            if source_ids is None:
                candidate["_rowid"] = rowids[episode_id]
            candidates.append(candidate)
        if source_ids is None and len(candidates) > limit:
            # Continue after the selected prefix so no eligible source within this
            # scan page is stranded when source_limit is smaller than the candidate count.
            sources = candidates[:limit]
            next_cursor = sources[-1]["_rowid"]
        else:
            sources = candidates[:limit]
        preview_id = uuid.uuid4().hex
        expires = time.time() + PREVIEW_TTL
        model_scope = "subscription-catalog-at-start"
        with self._connect() as db:
            db.execute("INSERT INTO cloud_memory_previews VALUES(?,?,?,?,?,?)",
                       (preview_id, purpose, model_scope, grant_id,
                        json.dumps(sources, separators=(",", ":")), expires))
        return {"preview_id": preview_id, "purpose": purpose, "count": len(sources),
                "source_limit": source_limit,
                "sources": [{k: v for k, v in source.items() if k not in {"fingerprint", "_rowid"}}
                            for source in sources[:10]],
                "candidate_count": len(candidates),
                "candidate_scan_limit": MAX_CANDIDATES,
                "scanned_count": len(ids),
                "next_cursor": next_cursor,
                "sampling": "consecutive eligible sources in bounded storage-order pages" if source_ids is None else "selected source IDs",
                "sampling_note": (f"Es werden höchstens {MAX_CANDIDATES} Quellen pro Seite geprüft. "
                                  "Bei weiteren Treffern kannst du den nächsten Quellenabschnitt prüfen. "
                                  "Neu eingehende Mails werden in einer neuen Vorschau berücksichtigt."
                                  if source_ids is None else "Es werden nur die ausdrücklich ausgewählten Quellen geprüft."),
                "expires_at": expires}

    @guarded
    def start(self, preview_id, model, consent, source_ids=None):
        if consent is not True:
            raise CloudMemoryError("Für die Cloudverarbeitung ist eine ausdrückliche Zustimmung erforderlich.")
        if type(model) is not str or not 1 <= len(model) <= 128:
            raise CloudMemoryError("Bitte ein gültiges ChatGPT-Modell auswählen.")
        with self.lock:
            if any(thread.is_alive() for thread in self._threads.values()):
                raise CloudMemoryError("Es läuft bereits ein Cloud-Gedächtnisauftrag.")
            with self._connect() as db:
                preview = db.execute("SELECT * FROM cloud_memory_previews WHERE id=?", (preview_id,)).fetchone()
            if not preview or preview["expires_at"] < time.time():
                raise CloudMemoryError("Die Vorschau ist abgelaufen. Bitte neu prüfen.")
            if preview["purpose"] == "bulk":
                with self._connect() as db:
                    pilot = db.execute(
                        "SELECT state FROM cloud_memory_jobs WHERE purpose='pilot' ORDER BY created_at DESC LIMIT 1"
                    ).fetchone()
                if not pilot or pilot["state"] != "complete":
                    raise CloudMemoryError("Der 100-Mail-Pilot muss abgeschlossen sein, bevor der Bulk-Lauf startet.")
            grant_id = self._grant()
            if not grant_id or (preview["grant_id"] and grant_id != preview["grant_id"]):
                raise CloudMemoryError("Das angemeldete ChatGPT-Konto hat sich geändert. Bitte neu prüfen.")
            sources = json.loads(preview["sources"])
            allowed = {item["id"]: item for item in sources}
            chosen = list(dict.fromkeys(source_ids if source_ids is not None else allowed))
            source_limit = MAX_SOURCES if preview["purpose"] == "pilot" else MAX_BULK_SOURCES
            if (not chosen or len(chosen) > source_limit or any(i not in allowed for i in chosen)):
                raise CloudMemoryError(f"Die Auswahl muss aus der Vorschau stammen und höchstens {source_limit} E-Mails enthalten.")
            # Pin exact source versions again after user review, immediately before creating the job.
            for episode_id in chosen:
                snapshot = self._snapshot(episode_id)
                if snapshot is None or source_fingerprint(snapshot) != allowed[episode_id]["fingerprint"]:
                    raise CloudMemoryError("Eine Quelle wurde geändert oder zurückgezogen. Bitte neu prüfen.")
            provider = self.provider_factory(model)
            if getattr(provider, "is_local", True) or not getattr(provider, "is_remote", False):
                raise CloudMemoryError("Der ausgewählte Anbieter ist kein expliziter Cloudanbieter.")
            if getattr(provider, "grant_id", None) != grant_id:
                raise CloudMemoryError("Die ChatGPT-Freigabe hat sich geändert. Bitte neu prüfen.")
            job_id = uuid.uuid4().hex
            now = time.time()
            fingerprints = {i: allowed[i]["fingerprint"] for i in chosen}
            with self._connect() as db:
                db.execute("""INSERT INTO cloud_memory_jobs
                    (id,purpose,model,grant_id,source_ids,fingerprints,source_limit,state,consent,
                     position,requests,completed,failed,stop_reason,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (job_id, preview["purpose"], model, grant_id,
                            json.dumps(chosen), json.dumps(fingerprints), source_limit,
                            "running", 1, 0, 0, 0, 0, "", now, now))
            thread = threading.Thread(target=self._run, args=(job_id, provider),
                                      name="cloud-memory-job", daemon=True)
            self._threads[job_id] = thread
            thread.start()
            return self.status(job_id)

    def _job(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM cloud_memory_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def _save(self, job_id, **changes):
        allowed = {"state", "consent", "position", "requests", "completed", "failed", "stop_reason"}
        if set(changes) - allowed:
            raise ValueError("unsupported cloud job field")
        changes["updated_at"] = time.time()
        with self._connect() as db:
            db.execute("UPDATE cloud_memory_jobs SET " + ",".join(f"{k}=?" for k in changes) + " WHERE id=?",
                       (*changes.values(), job_id))

    def status(self, job_id=None):
        if job_id is None:
            with self._connect() as db:
                row = db.execute("SELECT id FROM cloud_memory_jobs ORDER BY created_at DESC LIMIT 1").fetchone()
            job_id = row[0] if row else None
        job = self._job(job_id) if job_id else None
        if not job:
            return {"job": None}
        ids = json.loads(job["source_ids"])
        with self._connect() as db:
            issue_count = db.execute("SELECT COUNT(*) FROM cloud_memory_issues WHERE job_id=?",
                                     (job["id"],)).fetchone()[0]
            issue_rows = db.execute("SELECT episode_id,stage,code,reason FROM cloud_memory_issues "
                                    "WHERE job_id=? ORDER BY rowid LIMIT 10", (job["id"],)).fetchall()
        return {"job": {"id": job["id"], "purpose": job["purpose"], "model": job["model"],
                         "state": job["state"], "selected": len(ids), "position": job["position"],
                         "completed": job["completed"], "failed": job["failed"],
                         "requests": job["requests"],
                         "request_limit": job["source_limit"] * REQUESTS_PER_SOURCE,
                         "source_limit": job["source_limit"], "stop_reason": job["stop_reason"],
                         "issue_count": issue_count,
                         "issues": [{"episode_id": row["episode_id"], "stage": row["stage"],
                                     "code": row["code"],
                                     **({"reason": row["reason"]} if row["reason"] in
                                        getattr(SourceValidationError, "REASONS", ())
                                        and row["reason"] != "unspecified" else {})}
                                    for row in issue_rows],
                         "updated_at": job["updated_at"]}}

    def _permitted(self, job_id, provider, snapshot):
        job = self._job(job_id)
        return bool(job and job["state"] == "running" and job["consent"] == 1
                    and job["grant_id"] == self._grant()
                    and job["grant_id"] == getattr(provider, "grant_id", None)
                    and callable(getattr(provider, "available", None)) and provider.available()
                    and self.memory.is_current(snapshot)
                    and source_fingerprint(snapshot) == json.loads(job["fingerprints"])[snapshot.episode.id])

    def _run(self, job_id, provider):
        try:
            job = self._job(job_id)
            ids = json.loads(job["source_ids"])
            fingerprints = json.loads(job["fingerprints"])
            for index in range(job["position"], len(ids)):
                boundary = (self._runtime_boundary.operation() if self._runtime_boundary is not None
                            else nullcontext())
                with boundary:
                    job = self._job(job_id)
                    if job["state"] != "running" or not job["consent"]:
                        return
                    episode_id = ids[index]
                    snapshot = self._snapshot(episode_id)
                    if snapshot is None or source_fingerprint(snapshot) != fingerprints[episode_id]:
                        with self.permission_lock:
                            current = self._job(job_id)
                            if current and current["state"] == "running":
                                self._save(job_id, state="stopped",
                                           stop_reason="Eine Quelle wurde geändert oder zurückgezogen.")
                        return
                    successful = True
                    stage = "source"
                    try:
                        # Every cloud run is an explicit user-approved re-evaluation,
                        # including pilot upgrades of sources previously handled locally.
                        self._analyze_one(job_id, provider, snapshot, explicit_recheck=True)
                        stage = "categories"
                        self._categories_one(job_id, provider, snapshot)
                    except SourceValidationError as exc:
                        with self.permission_lock:
                            if not self._permitted(job_id, provider, snapshot):
                                current = self._job(job_id)
                                if current and current["state"] == "running":
                                    self._save(job_id, state="stopped",
                                               stop_reason="Freigabe oder Quelle wurde während des Auftrags geändert.")
                                return
                            job = self._job(job_id)
                            reason = getattr(exc, "reason", "unspecified")
                            if not isinstance(reason, str) or reason not in getattr(SourceValidationError, "REASONS", ()):
                                reason = "unspecified"
                            with self._connect() as db:
                                db.execute("INSERT OR REPLACE INTO cloud_memory_issues "
                                           "(job_id,episode_id,stage,code,reason) VALUES(?,?,?,?,?)",
                                           (job_id, episode_id, stage, exc.code, reason))
                            self._save(job_id, position=index + 1, failed=job["failed"] + 1)
                        continue
                    except UnsupportedSource:
                        successful = False
                        with self.permission_lock:
                            if not self._permitted(job_id, provider, snapshot):
                                return
                            with self._connect() as db:
                                db.execute("INSERT OR REPLACE INTO cloud_memory_issues "
                                           "(job_id,episode_id,stage,code) VALUES(?,?,?,?)",
                                           (job_id, episode_id, stage, "unsupported_source"))
                            if stage == "source":
                                self.memory.defer(snapshot)
                            job = self._job(job_id)
                            self._save(job_id, failed=job["failed"] + 1)
                    with self.permission_lock:
                        if not self._permitted(job_id, provider, snapshot):
                            current = self._job(job_id)
                            if current and current["state"] == "running":
                                self._save(job_id, state="stopped",
                                           stop_reason="Freigabe oder Quelle wurde während des Auftrags geändert.")
                            return
                        job = self._job(job_id)
                        self._save(job_id, position=index + 1,
                                   completed=job["completed"] + int(successful))
            job = self._job(job_id)
            with self.permission_lock:
                job = self._job(job_id)
                if job["state"] == "running":
                    state = "complete" if job["completed"] == len(ids) and job["failed"] == 0 else "complete_with_gaps"
                    reason = "" if state == "complete" else "Einige Quellen wurden zurückgestellt oder konnten nicht ausgewertet werden."
                    self._save(job_id, state=state, stop_reason=reason)
        except Exception as exc:
            # Do not persist provider text, source text, credentials, or exception details.
            current = self._job(job_id)
            with self.permission_lock:
                current = self._job(job_id)
                if current and current["state"] == "running":
                    retryable = self._retryable(exc)
                    self._save(job_id, state="paused" if retryable else "stopped",
                               consent=0 if self._grant() != current["grant_id"] else current["consent"],
                               failed=current["failed"] + int(not retryable),
                               stop_reason=self._stop_reason(exc))

    @staticmethod
    def _retryable(exc):
        message = str(exc).lower()
        name = type(exc).__name__.lower()
        return any(token in name or token in message for token in
                   ("quota", "kontingent", "rate limit", "anfragelimit", "429",
                    "timeout", "connection", "unterbrochen", "nicht erreicht"))

    @staticmethod
    def _stop_reason(exc):
        name = type(exc).__name__.lower()
        message = str(exc).lower()
        if "quota" in name or "quota" in message or "kontingent" in message:
            return "ChatGPT-Kontingent erreicht; Auftrag gestoppt."
        if "rate" in name or "rate limit" in message or "anfragelimit" in message:
            return "ChatGPT hat die Anfrage begrenzt; Auftrag gestoppt."
        if "auth" in name or "unauthor" in name or "grant" in message or "anmeldung" in message:
            return "Die Anmeldung oder Freigabe ist nicht mehr gültig."
        if isinstance(exc, UnsupportedSource):
            return "Eine Quelle überschreitet das Auswertungsbudget."
        return "Die Verarbeitung ist fehlgeschlagen; bitte Anmeldung und Verbindung prüfen."

    def _scoped(self, job_id, provider, snapshot):
        scoped = _ScopedProvider(provider, None,
                                 lambda: self._count_request(job_id, provider, snapshot))
        scoped._episode = snapshot.episode
        def authorize(_episode):
            with self.permission_lock:
                return self._permitted(job_id, provider, snapshot)
        policy = ExplicitSourcePolicy(scoped, snapshot.episode.id, authorize)
        scoped._policy = policy
        return scoped, policy

    def _count_request(self, job_id, provider, snapshot):
        with self.permission_lock:
            if not self._permitted(job_id, provider, snapshot):
                raise ProviderError("Die Freigabe oder Quellenfassung hat sich geändert.")
            job = self._job(job_id)
            request_limit = job["source_limit"] * REQUESTS_PER_SOURCE
            if job["requests"] >= request_limit:
                self._save(job_id, state="stopped", stop_reason=f"Das Anfragebudget von {request_limit} wurde erreicht.")
                raise ProviderError("Das Anfragebudget wurde erreicht.")
            self._save(job_id, requests=job["requests"] + 1)

    def _analyze_one(self, job_id, provider, snapshot, *, explicit_recheck=False):
        scoped, policy = self._scoped(job_id, provider, snapshot)
        plan = abschnitte_der(snapshot.episode)
        results = []
        for section in plan:
            if not policy.permits(scoped, snapshot.episode):
                raise ProviderError("Freigabe oder Quelle nicht mehr aktuell.")
            results.append(interpret_abschnitt(scoped, snapshot.episode, section, len(plan), policy=policy))
        merged = abschnitte.zusammenfuehren(results)
        with self.permission_lock:
            if not self._permitted(job_id, provider, snapshot) or not self.memory.is_current(snapshot):
                raise ProviderError("Freigabe oder Quelle vor dem Speichern geändert.")
            self.memory.commit(snapshot, merged, model=f"chatgpt:{getattr(provider, 'model', '')}",
                               explicit_recheck=explicit_recheck)

    def _categories_one(self, job_id, provider, snapshot):
        episode_id = snapshot.episode.id
        with self.permission_lock:
            if not self._permitted(job_id, provider, snapshot):
                raise ProviderError("Freigabe oder Quelle vor Kategorienauswertung geändert.")
            self.categories.request_recheck([episode_id])
        scoped, policy = self._scoped(job_id, provider, snapshot)
        # `Categories.run` reuses the source selection, validation, and correction-aware write path.
        result = self.categories.run(scoped, limit=1, permitted=lambda: self._permitted(job_id, provider, snapshot),
                                     permission_lock=self.permission_lock, source_ids=[episode_id],
                                     processing_policy=lambda _selected: policy,
                                     preserve_on_failure=True)
        if not result.ok:
            raise ProviderError(result.detail)
        state = self.categories.list_for(episode_id)["status"]
        if state == "deferred":
            raise UnsupportedSource("Category analysis is deferred for this source.")
        if state not in {"complete", "empty"}:
            raise ProviderError("Category analysis did not produce a current result.")

    def pause(self, job_id=None, revoke=False):
        job = self._job(job_id) if job_id else self._job(self._latest_id())
        if not job:
            return self.status()
        with self.permission_lock:
            job = self._job(job["id"])
            if job["state"] in {"running", "paused"}:
                self._save(job["id"], state="stopped" if revoke else "paused",
                           consent=0 if revoke else job["consent"],
                           stop_reason="Freigabe widerrufen." if revoke else "Vom Nutzer pausiert.")
        return self.status(job["id"])

    def _latest_id(self):
        with self._connect() as db:
            row = db.execute("SELECT id FROM cloud_memory_jobs ORDER BY created_at DESC LIMIT 1").fetchone()
        return row[0] if row else None

    @guarded
    def resume(self, job_id=None):
        with self.lock:
            job = self._job(job_id) if job_id else self._job(self._latest_id())
            if not job or job["state"] != "paused" or not job["consent"]:
                raise CloudMemoryError("Dieser Auftrag kann nicht fortgesetzt werden.")
            old_thread = self._threads.get(job["id"])
            if old_thread is not None and old_thread.is_alive():
                raise CloudMemoryError("Der pausierte Auftrag beendet noch eine laufende Anfrage. Bitte gleich erneut versuchen.")
            provider = self.provider_factory(job["model"])
            with self.permission_lock:
                job = self._job(job["id"])
                if job["state"] != "paused" or not job["consent"]:
                    raise CloudMemoryError("Dieser Auftrag kann nicht fortgesetzt werden.")
                if (getattr(provider, "grant_id", None) != job["grant_id"] or
                        self._grant() != job["grant_id"] or not provider.available()):
                    self._save(job["id"], state="stopped", consent=0,
                               stop_reason="Die Anmeldung hat sich geändert; Vorschau und Zustimmung erneut erforderlich.")
                    raise CloudMemoryError("Die Anmeldung hat sich geändert. Bitte eine neue Vorschau und Zustimmung erteilen.")
                self._save(job["id"], state="running", stop_reason="")
            thread = threading.Thread(target=self._run, args=(job["id"], provider),
                                      name="cloud-memory-job", daemon=True)
            self._threads[job["id"]] = thread
            thread.start()
            return self.status(job["id"])
