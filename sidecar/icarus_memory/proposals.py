"""Vorschläge: was die Verdichtung dem Menschen vorlegt.

Die eine Regel, an der dieses ganze Modul hängt, steht in
docs/08-gedaechtnisschichten.md:

    Verdichtung schlägt vor. Sie schreibt nicht.

Ein System, das aus Mails und Notizen stillschweigend Fakten über eine Person
ableitet und in den Bestand schreibt, hat wieder ein Gedächtnis, dem niemand
zusehen kann — genau das Versagen, gegen das dieses Projekt gebaut ist. Die
Roadmap hat den Punkt von Anfang an als kritisch markiert, und daran ändert
sich nichts, wenn die Bequemlichkeit lockt.

Deshalb gibt es diese Schicht. Ein Vorschlag ist eine **Behauptung auf Probe**:
formuliert, belegt, begründet — und ohne Wirkung, bis ein Mensch zustimmt.

## Warum drei Arten

Nicht jeder Vorschlag braucht ein Modell, und das ist wichtig. Ein
Gedächtniskern, dessen Pflege einen Anbieter voraussetzt, ist keiner.

* `assertion` — „daraus folgt eine Aussage über dich". Braucht ein Modell.
* `confirmation` — „das hier ist alt, gilt es noch?". Reine Regel, kein Modell.
* `conflict` — „diese beiden widersprechen sich womöglich". Reine Regel.

Die letzten beiden tragen den Alltag: Sie halten den Bestand ehrlich, auch wenn
nie ein Schlüssel eingetragen wird.

## Belege sind Pflicht

Jeder Vorschlag trägt seine `evidence` — welche Episode, welche Stelle im
Wortlaut. Ohne das wäre die Verdichtung eine Blackbox, die Behauptungen
ausspuckt, und der Nutzer müsste raten, worauf sie beruhen. Ein Vorschlag ohne
Beleg wird abgewiesen, nicht gespeichert.
"""

from __future__ import annotations

import hashlib
import json
from . import support_schema
from .datumstext import iso_lesen as _parse
from .store_transactions import sqlite_transaction
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .migrations import (
    IndexContract,
    Migration,
    run_migrations,
    validate_legacy_or_empty,
    verify_schema,
)
from . import logbuch
from .model import Kind, Sensitivity, ensure_aware, now
from .relations import validate_interval


class ProposalKind(str, Enum):
    TASK = "task"
    """Belegte Aufgabe oder Zusage; Annahme ausschließlich über den Aufgabenpfad."""

    ASSERTION = "assertion"
    """Aus Episoden abgeleitete Aussage über die Person. Braucht ein Modell."""

    CONFIRMATION = "confirmation"
    """Eine bestehende Aussage ist über ihren Horizont. Gilt sie noch?

    Kein Modell nötig — `currency.py` weiß, was alt ist. Das ist der
    Mechanismus, über den ein Bestand aktuell bleibt, ohne dass jemand rät.
    """

    CONFLICT = "conflict"
    """Zwei Aussagen widersprechen sich womöglich.

    Ausdrücklich ein **Kandidat**, kein Urteil. Die Regel findet Ähnlichkeit,
    nicht Widerspruch — entscheiden muss der Mensch, und erst seine Zustimmung
    setzt `disputed`.
    """

    KNOWLEDGE = "knowledge"
    """Belegte Aussage über eine Person, ein Projekt oder eine andere Entität.

    Sie bleibt Kandidat, bis ein Mensch sie über den Wissenspfad annimmt. Sie
    darf niemals über den Selbstmodell-Accept-Pfad in Aussagen über den lokalen
    Nutzer geraten.
    """


class ProposalState(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    """Ein neuerer Vorschlag hat denselben Punkt abgedeckt.

    Nötig, weil ein zweiter Verdichtungslauf denselben Sachverhalt erneut
    vorlegen kann. Ohne diesen Zustand wüchse die Schlange, bis niemand mehr
    hineinsieht — und eine Schlange, in die niemand sieht, ist dasselbe wie
    keine Kontrolle.
    """


@dataclass
class Evidence:
    """Worauf ein Vorschlag beruht.

    `quote` ist der wörtliche Ausschnitt, nicht eine Zusammenfassung. Wer prüft,
    ob ein Vorschlag stimmt, will die Stelle sehen und nicht eine zweite
    Interpretation davon.
    """

    episode_id: str
    quote: str = ""
    digest: str = ""
    """Digest der Episode zum Zeitpunkt des Vorschlags.

    Damit ist feststellbar, ob sich die Quelle seit dem Vorschlag geändert hat —
    die Voraussetzung für die Neuprüfung, die der Gedächtnis-Kontrakt als
    offenen Punkt führt.
    """

    def to_dict(self) -> dict[str, Any]:
        return {"episode_id": self.episode_id, "quote": self.quote, "digest": self.digest}


@dataclass
class Proposal:
    id: str
    kind: ProposalKind
    statement: str
    rationale: str
    created_at: datetime

    assertion_kind: Kind | None = None
    """Welche Art Aussage daraus würde. Nur bei `assertion` gesetzt."""

    sensitivity: Sensitivity = Sensitivity.NORMAL
    confidence: float | None = None
    evidence: list[Evidence] = field(default_factory=list)
    about: list[str] = field(default_factory=list)
    """Bestehende Aussagen, um die es geht — bei `confirmation` und `conflict`."""

    supersedes: list[str] = field(default_factory=list)
    """Aussagen, die diese hier ablösen würde, wenn sie angenommen wird."""

    state: ProposalState = ProposalState.PENDING
    decided_at: datetime | None = None
    produced: str | None = None
    """Die Kennung der Aussage, die aus der Annahme entstand."""

    proposed_by: str = ""
    """Regel oder Modell, das den Vorschlag gemacht hat."""

    subject_ref: str = ""
    predicate: str = ""
    value: str = ""
    scope_ref: str | None = None
    """Struktur eines allgemeinen Wissenskandidaten.

    Nur bei ``knowledge`` gesetzt. Der Gültigkeitsbereich ist Teil der
    Behauptung: dieselbe Person kann im privaten und beruflichen Kontext
    unterschiedliche Rollen haben, ohne dass daraus ein Widerspruch entsteht.
    """

    target_ref: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    depends_on: list[str] = field(default_factory=list)

    task_context: str | None = None
    """Kontextbindung automatisch erkannter Aufgaben; keine Autorisierung."""

    def to_dict(self) -> dict[str, Any]:
        def iso(v: datetime | None) -> str | None:
            return v.astimezone().isoformat() if v else None

        return {
            "id": self.id,
            "kind": self.kind.value,
            "statement": self.statement,
            "rationale": self.rationale,
            "assertion_kind": self.assertion_kind.value if self.assertion_kind else None,
            "sensitivity": self.sensitivity.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "about": list(self.about),
            "supersedes": list(self.supersedes),
            "state": self.state.value,
            "created_at": iso(self.created_at),
            "decided_at": iso(self.decided_at),
            "produced": self.produced,
            "proposed_by": self.proposed_by,
            "subject_ref": self.subject_ref,
            "predicate": self.predicate,
            "value": self.value,
            "scope_ref": self.scope_ref,
            "target_ref": self.target_ref,
            "valid_from": iso(self.valid_from),
            "valid_until": iso(self.valid_until),
            "depends_on": list(self.depends_on),
            **({"task_context": self.task_context} if self.task_context is not None else {}),
        }


_CREATE_PROPOSALS = """
CREATE TABLE IF NOT EXISTS proposals (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    state      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    document   TEXT NOT NULL
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_proposals_state ON proposals(state)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_kind ON proposals(kind)",
    # Kein UNIQUE-Index: Ein abgelehnter Vorschlag darf mit neuer Evidence
    # später erneut auftauchen.
    "CREATE INDEX IF NOT EXISTS idx_proposals_finger ON proposals(fingerprint)",
)
_INDEX_CONTRACTS = {
    "idx_proposals_state": IndexContract("proposals", ("state",)),
    "idx_proposals_kind": IndexContract("proposals", ("kind",)),
    "idx_proposals_finger": IndexContract("proposals", ("fingerprint",)),
}
_SCHEMA_CONTRACT = {
    "proposals": {"id", "kind", "state", "created_at", "fingerprint", "document"}
}
_PRIMARY_KEYS = {"proposals": {"id"}}


def _migrate_v1(connection: sqlite3.Connection) -> None:
    validate_legacy_or_empty(
        connection,
        store="proposals",
        path=connection.execute("PRAGMA database_list").fetchone()[2],
        expected_tables=_SCHEMA_CONTRACT,
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )
    connection.execute(_CREATE_PROPOSALS)
    for statement in _INDEXES:
        connection.execute(statement)


def _verify_v1(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_SCHEMA_CONTRACT,
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )


def _migrate_v2(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE task_analysis (episode_id TEXT PRIMARY KEY, digest TEXT NOT NULL, analyzed_at TEXT NOT NULL)")


def _verify_v2(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables={**_SCHEMA_CONTRACT, "task_analysis": {"episode_id", "digest", "analyzed_at"}},
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, "task_analysis": {"episode_id"}},
    )


def _migrate_v3(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE task_scan_cursor (id INTEGER PRIMARY KEY CHECK(id = 1), after_id TEXT NOT NULL)")


def _verify_v3(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables={**_SCHEMA_CONTRACT, "task_analysis": {"episode_id", "digest", "analyzed_at"},
                         "task_scan_cursor": {"id", "after_id"}},
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, "task_analysis": {"episode_id"}, "task_scan_cursor": {"id"}},
    )


def _migrate_v4(connection: sqlite3.Connection) -> None:
    from .memory_analysis import install_schema
    install_schema(connection)


def _verify_v4(connection: sqlite3.Connection) -> None:
    from .memory_analysis import TABLES, INDEXES
    verify_schema(connection,
        expected_tables={**_SCHEMA_CONTRACT, "task_analysis": {"episode_id", "digest", "analyzed_at"},
                         "task_scan_cursor": {"id", "after_id"}, **TABLES},
        expected_indexes={**_INDEX_CONTRACTS, **INDEXES},
        expected_primary_keys={**_PRIMARY_KEYS, "task_analysis": {"episode_id"},
                               "task_scan_cursor": {"id"}, "memory_analysis_jobs": {"id"}})


def _verify_v5(connection: sqlite3.Connection) -> None:
    from .memory_analysis import TABLES, INDEXES
    verify_schema(connection,
        expected_tables={**_SCHEMA_CONTRACT, "proposals": _SCHEMA_CONTRACT["proposals"] | {"produced_assertion_id","support_authorization"}, "task_analysis": {"episode_id", "digest", "analyzed_at"},
                         "task_scan_cursor": {"id", "after_id"}, **TABLES},
        expected_triggers=support_schema.PROPOSAL_TRIGGERS,
        expected_indexes={**_INDEX_CONTRACTS, **INDEXES, "idx_proposals_produced": IndexContract("proposals", ("produced_assertion_id",))},
        expected_primary_keys={**_PRIMARY_KEYS, "task_analysis": {"episode_id"},
                               "task_scan_cursor": {"id"}, "memory_analysis_jobs": {"id"}})


_MIGRATIONS = (
    Migration(1, "initial_explicit_version", _migrate_v1, _verify_v1),
    Migration(2, "task_analysis_checkpoints", _migrate_v2, _verify_v2),
    Migration(3, "fair_task_scan_cursor", _migrate_v3, _verify_v3),
    Migration(4, "bounded_memory_analysis", _migrate_v4, _verify_v4),
    Migration(5, "produced_support_authorization", support_schema.migrate_proposals, _verify_v5),
)


class ProposalError(Exception):
    """Ein Vorschlag ist unbekannt, unbelegt oder bereits entschieden."""


def fingerprint(
    kind: ProposalKind,
    statement: str,
    about: list[str],
    *,
    subject_ref: str = "",
    predicate: str = "",
    value: str = "",
    scope_ref: str | None = None,
    target_ref: str | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    depends_on: list[str] | None = None,
) -> str:
    """Kennzeichnet den *Sachverhalt*, nicht den einzelnen Vorschlag.

    Absichtlich grob: Kleinschreibung, normalisierte Leerzeichen, sortierte
    Bezüge. Ein Verdichtungslauf, der dieselbe Sache leicht anders formuliert,
    soll trotzdem als Wiederholung erkannt werden — sonst wächst die Schlange
    mit jeder Runde, und eine Schlange, in die niemand mehr sieht, ist dasselbe
    wie keine Kontrolle.
    """
    normal = " ".join(statement.casefold().split())
    base = f"{kind.value}|{normal}|{','.join(sorted(about))}"
    # Bestehende Datenbanken enthalten Fingerprints aus der Zeit vor den
    # strukturierten Wissenskandidaten. Deren Format muss bytegenau stabil
    # bleiben, damit ein alter offener Vorschlag weiterhin dedupliziert wird.
    if any((subject_ref, predicate, value, scope_ref)):
        structured = "|".join(
            " ".join(part.casefold().split())
            for part in (subject_ref, predicate, value, scope_ref or "")
        )
        base = f"{base}|{structured}"

    # Beziehungsmetadaten werden als separater JSON-Teil angehängt. Die alten
    # Fingerprints bleiben dadurch bytegenau erhalten; Ziel- und
    # Abhängigkeits-IDs behalten ihre Groß-/Kleinschreibung.
    if any((target_ref is not None, valid_from is not None, valid_until is not None,
            bool(depends_on))):
        validate_interval(valid_from, valid_until)

        def utc_iso(value: datetime | None) -> str | None:
            if value is None:
                return None
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        metadata = {
            "target_ref": target_ref,
            "valid_from": utc_iso(valid_from),
            "valid_until": utc_iso(valid_until),
            "depends_on": list(depends_on or []),
        }
        base += "|" + json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return base


class ProposalStore:
    """Die Vorschlagsschlange in einer lokalen Datei."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            with self._lock:
                run_migrations(
                    self._conn,
                    store="proposals",
                    path=self._path,
                    migrations=_MIGRATIONS,
                )
        except Exception:
            self._conn.close()
            raise

    # -- Anlegen -----------------------------------------------------------

    def propose(
        self,
        kind: ProposalKind,
        statement: str,
        rationale: str,
        *,
        assertion_kind: Kind | None = None,
        sensitivity: Sensitivity = Sensitivity.NORMAL,
        confidence: float | None = None,
        evidence: list[Evidence] | None = None,
        about: list[str] | None = None,
        supersedes: list[str] | None = None,
        proposed_by: str = "",
        subject_ref: str = "",
        predicate: str = "",
        value: str = "",
        scope_ref: str | None = None,
        target_ref: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        depends_on: list[str] | None = None,
        at: datetime | None = None,
    ) -> tuple[Proposal, bool]:
        """Legt einen Vorschlag an. Gibt ihn zurück und ob er **neu** war.

        Wird derselbe Sachverhalt erneut vorgelegt, während ein Vorschlag dazu
        noch offen ist, bleibt der bestehende stehen. Ein zweiter Eintrag wäre
        für den Nutzer dieselbe Frage zum zweiten Mal.

        Ein Vorschlag **ohne Beleg** wird abgewiesen. `confirmation` und
        `conflict` beziehen sich auf bestehende Aussagen (`about`), `assertion`
        auf Episoden (`evidence`) — eines von beidem muss da sein, sonst wäre
        die Verdichtung eine Blackbox.
        """
        evidence = list(evidence or [])
        about = list(about or [])
        if not evidence and not about:
            raise ProposalError(
                "Vorschlag ohne Beleg. Es braucht eine Episode oder eine "
                "bestehende Aussage, auf die er sich bezieht."
            )
        if kind is ProposalKind.ASSERTION and assertion_kind is None:
            raise ProposalError("Eine vorgeschlagene Aussage braucht eine Art.")
        if kind is ProposalKind.KNOWLEDGE and not all(
            item.strip() for item in (subject_ref, predicate, value)
        ):
            raise ProposalError(
                "Ein Wissenskandidat braucht Subjekt, Beziehung und Wert."
            )
        if target_ref is not None and not target_ref.strip():
            raise ProposalError("Eine Zielreferenz darf nicht leer sein.")
        if any(not isinstance(item, str) or not item.strip() for item in (depends_on or [])):
            raise ProposalError("Abhängigkeiten brauchen gültige Aussagekennungen.")
        if kind is ProposalKind.KNOWLEDGE:
            try:
                validate_interval(valid_from, valid_until)
            except (TypeError, ValueError) as exc:
                raise ProposalError(f"Ungültiges Gültigkeitsintervall: {exc}") from exc

        finger = fingerprint(
            kind,
            statement,
            about,
            subject_ref=subject_ref,
            predicate=predicate,
            value=value,
            scope_ref=scope_ref,
            target_ref=target_ref,
            valid_from=valid_from,
            valid_until=valid_until,
            depends_on=depends_on,
        )
        offen = self._by_fingerprint(finger, ProposalState.PENDING)
        if offen is not None:
            return offen, False

        proposal = Proposal(
            id=f"v-{uuid.uuid4().hex[:12]}",
            kind=kind,
            statement=statement,
            rationale=rationale,
            created_at=ensure_aware(at) or now(),
            assertion_kind=assertion_kind,
            sensitivity=sensitivity,
            confidence=confidence,
            evidence=evidence,
            about=about,
            supersedes=list(supersedes or []),
            proposed_by=proposed_by,
            subject_ref=subject_ref.strip(),
            predicate=predicate.strip(),
            value=value.strip(),
            scope_ref=scope_ref.strip() if scope_ref else None,
            target_ref=target_ref.strip() if target_ref is not None else None,
            valid_from=valid_from,
            valid_until=valid_until,
            depends_on=list(depends_on or []),
        )
        self._put(proposal, finger)
        logbuch.vermerke('vorschlag_erzeugt', sorte=getattr(kind, 'value', kind), id=proposal.id)
        return proposal, True

    def task_scan_cursor(self) -> str:
        with self._lock:
            row = self._conn.execute("SELECT after_id FROM task_scan_cursor WHERE id = 1").fetchone()
        return row["after_id"] if row else ""

    def advance_task_scan(self, after_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO task_scan_cursor (id, after_id) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET after_id=excluded.after_id", (after_id,),
            )

    def task_analysis_done(self, episode_id: str, digest: str) -> bool:
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM task_analysis WHERE episode_id = ? AND digest = ?",
                (episode_id, digest),
            ).fetchone() is not None

    @property
    def memory_analysis(self):
        from .memory_analysis import MemoryAnalysis
        return MemoryAnalysis(self)

    def _record_task_candidates(self, episode_id, digest, items, *, proposed_by, task_context=None):
        """Nur innerhalb der Transaktion des Aufrufers; noch kein Checkpoint."""
        at = now()
        candidates = []
        for item in items:
            title, quote = item["title"].strip(), item["quote"].strip()
            if not title or not quote or not episode_id or not digest:
                raise ProposalError("Aufgabenvorschlag ohne Titel oder Quellenbeleg.")
            basis = [episode_id, digest, quote]
            legacy_id = "v-" + hashlib.sha256(json.dumps(basis, ensure_ascii=False).encode()).hexdigest()[:24]
            # Ein explizit entschiedener Altvorschlag wird nicht wieder vorgelegt.
            legacy = self._conn.execute("SELECT state FROM proposals WHERE id=?", (legacy_id,)).fetchone()
            if task_context is not None:
                accepted = self._conn.execute(
                    "SELECT 1 FROM proposals WHERE kind='task' AND state='accepted' "
                    "AND json_extract(document,'$.evidence[0].episode_id')=? "
                    "AND json_extract(document,'$.evidence[0].digest')=? "
                    "AND json_extract(document,'$.evidence[0].quote')=? LIMIT 1",
                    (episode_id, digest, quote)).fetchone()
                if accepted or (legacy and legacy['state'] in {'accepted', 'rejected'}):
                    continue
                if legacy and legacy['state'] == 'pending':
                    self.supersede(legacy_id)
                basis.append(task_context)
            finger = "task|" + hashlib.sha256(json.dumps(basis, ensure_ascii=False).encode()).hexdigest()
            proposal = Proposal(
                id="v-" + finger.split("|")[1][:24], kind=ProposalKind.TASK,
                statement=title, rationale="In der Quelle erkannte Aufgabe oder Zusage. Bitte prüfen.",
                created_at=at, evidence=[Evidence(episode_id, quote, digest)], proposed_by=proposed_by, task_context=task_context,
            )
            candidates.append((proposal, finger))
        count = 0
        for proposal, finger in candidates:
            # Unter der bereits gehaltenen Schreibtransaktion: ein vorhandener
            # Vorschlag (auch abgelehnt) bleibt unverändert; kein REPLACE-Versuch.
            if self._conn.execute('SELECT 1 FROM proposals WHERE id=?', (proposal.id,)).fetchone():
                continue
            d = proposal.to_dict()
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO proposals (id, kind, state, created_at, fingerprint, document) VALUES (?, ?, ?, ?, ?, ?)",
                (d["id"], d["kind"], d["state"], d["created_at"], finger, json.dumps(d, ensure_ascii=False)),
            )
            count += cursor.rowcount
        return count

    def _record_task_checkpoint(self, episode_id, digest):
        self._conn.execute(
            "INSERT INTO task_analysis (episode_id, digest, analyzed_at) VALUES (?, ?, ?) "
            "ON CONFLICT(episode_id) DO UPDATE SET digest=excluded.digest, analyzed_at=excluded.analyzed_at",
            (episode_id, digest, now().isoformat()))

    def record_task_analysis(self, episode_id: str, digest: str, items: list[dict[str, str]], *, proposed_by: str) -> int:
        """Kompatibler atomarer Altlauf; beweist keine neue Umfangsabnahme."""
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            if self._conn.execute("SELECT 1 FROM task_analysis WHERE episode_id=? AND digest=?", (episode_id, digest)).fetchone():
                return 0
            count = self._record_task_candidates(episode_id, digest, items, proposed_by=proposed_by)
            self._record_task_checkpoint(episode_id, digest)
            return count

    # -- Entscheiden -------------------------------------------------------

    def accept(
        self, proposal_id: str, produced: str | None = None, at: datetime | None = None
    ) -> Proposal:
        with self.transaction():
            proposal = self._require_pending(proposal_id)
            proposal.state = ProposalState.ACCEPTED
            proposal.produced = produced
            proposal.decided_at = ensure_aware(at) or now()
            self._put(proposal)
        logbuch.vermerke('vorschlag_angenommen', sorte=getattr(proposal.kind, 'value', proposal.kind), id=proposal.id)
        return proposal

    def reject(self, proposal_id: str, at: datetime | None = None) -> Proposal:
        """Abgelehnt — und das bleibt sichtbar.

        Ein gelöschter Vorschlag wäre ein Vorgang ohne Spur. Wer später fragt,
        warum etwas *nicht* im Bestand steht, findet hier die Antwort.
        """
        with self.transaction():
            proposal = self._require_pending(proposal_id)
            proposal.state = ProposalState.REJECTED
            proposal.decided_at = ensure_aware(at) or now()
            self._put(proposal)
        logbuch.vermerke('vorschlag_abgelehnt', sorte=getattr(proposal.kind, 'value', proposal.kind), id=proposal.id)
        return proposal

    def supersede(self, proposal_id: str, at: datetime | None = None) -> Proposal:
        with self.transaction():
            proposal = self._require_pending(proposal_id)
            proposal.state = ProposalState.SUPERSEDED
            proposal.decided_at = ensure_aware(at) or now()
            self._put(proposal)
            return proposal

        # -- Lesen -------------------------------------------------------------

    def get(self, proposal_id: str) -> Proposal:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        if row is None:
            raise ProposalError(f"Unbekannter Vorschlag: {proposal_id}")
        return self._from_row(row)

    def pending(self, kind: ProposalKind | None = None, limit: int = 100) -> list[Proposal]:
        sql = "SELECT document FROM proposals WHERE state = ?"
        params: list[Any] = [ProposalState.PENDING.value]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind.value)
        sql += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._from_row(r) for r in rows]

    def pending_batches(self, kind: ProposalKind, *, batch_size: int = 200):
        """Read pending records without loading the entire import or truncating at 200."""
        after = 0
        while True:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT rowid,document FROM proposals WHERE rowid>? AND state=? AND kind=? ORDER BY rowid LIMIT ?",
                    (after, ProposalState.PENDING.value, kind.value, batch_size)).fetchall()
            if not rows:
                return
            after = rows[-1][0]
            yield [self._from_row(row) for row in rows]

    def pending_knowledge_for_subject(
        self, subject_ref: str, scope_ref: str | None, *, limit: int = 500,
        scan_guard: Callable[[], bool] | None = None,
    ) -> tuple[list[Proposal], bool]:
        """Return an exact, bounded pending set and whether it was complete.

        This avoids the global pending queue's oldest-500 limit when checking
        whether a particular accepted claim has an unresolved alternative.
        A SQLite step budget also bounds the scan when the JSON subject has no
        dedicated index. An interrupted scan is explicitly incomplete.
        """
        if not isinstance(subject_ref, str) or not subject_ref or not 0 <= limit <= 500:
            raise ValueError("Invalid pending knowledge query")
        steps = 0

        def budget() -> int:
            nonlocal steps
            steps += 1
            return int(steps > 2000 or (scan_guard is not None and scan_guard()))

        with self._lock:
            if scan_guard is not None and scan_guard():
                return [], False
            self._conn.set_progress_handler(budget, 1000)
            try:
                rows = self._conn.execute(
                    "SELECT substr(CAST(document AS BLOB), 1, 65537) AS document, "
                    "length(CAST(document AS BLOB)) AS document_bytes "
                    "FROM proposals WHERE state=? AND kind=? "
                    "AND json_extract(document, '$.subject_ref')=? "
                    "AND json_extract(document, '$.scope_ref') IS ? "
                    "ORDER BY created_at ASC, id ASC LIMIT ?",
                    (ProposalState.PENDING.value, ProposalKind.KNOWLEDGE.value,
                     subject_ref, scope_ref, limit + 1),
                ).fetchall()
            except sqlite3.Error:
                return [], False
            finally:
                self._conn.set_progress_handler(None, 0)
        # A tiny query may finish before SQLite invokes the progress handler.
        if scan_guard is not None and scan_guard():
            return [], False
        # A corrupt or oversized matching document cannot silently disappear
        # from the conflict check. The SQL projection itself stays bounded.
        if any(row["document_bytes"] > 65536 for row in rows):
            return [], False
        complete = len(rows) <= limit
        return [self._from_row(row) for row in rows[:limit]], complete

    def von(self, proposed_by: str, limit: int = 100) -> list[Proposal]:
        """Alle Vorschläge (gleich welchen Zustands), die `proposed_by` genau so gemacht hat, älteste zuerst.

        Damit findet eine Antwort ihre eigenen Vorschläge wieder (`uebernehmen.py`), auch nach einem Neustart.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM proposals WHERE json_extract(document, '$.proposed_by') = ? "
                "ORDER BY created_at ASC, id ASC LIMIT ?", (proposed_by, limit)).fetchall()
        return [self._from_row(r) for r in rows]

    def all_proposals(self, limit: int = 200) -> list[Proposal]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM proposals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def counts(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT state, COUNT(*) AS n FROM proposals GROUP BY state"
            ).fetchall()
        return {r["state"]: r["n"] for r in rows}

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- Intern ------------------------------------------------------------

    def _require_pending(self, proposal_id: str) -> Proposal:
        proposal = self.get(proposal_id)
        if proposal.state is not ProposalState.PENDING:
            raise ProposalError(
                f"Vorschlag {proposal_id} ist bereits {proposal.state.value}."
            )
        return proposal

    def _by_fingerprint(self, finger: str, state: ProposalState) -> Proposal | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM proposals WHERE fingerprint = ? AND state = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (finger, state.value),
            ).fetchone()
        return self._from_row(row) if row else None

    def _put(self, proposal: Proposal, finger: str | None = None) -> None:
        d = proposal.to_dict()
        finger = finger or fingerprint(
            proposal.kind,
            proposal.statement,
            proposal.about,
            subject_ref=proposal.subject_ref,
            predicate=proposal.predicate,
            value=proposal.value,
            scope_ref=proposal.scope_ref,
            target_ref=proposal.target_ref,
            valid_from=proposal.valid_from,
            valid_until=proposal.valid_until,
            depends_on=proposal.depends_on,
        )
        if any(key in d for key in ('support_authorization','authorization','commitment')):
            raise ProposalError('Authorization cannot be imported through a proposal document')
        with self.transaction():
            document = json.dumps(d, ensure_ascii=False)
            if self._conn.execute('SELECT 1 FROM proposals WHERE id=?',(proposal.id,)).fetchone():
                self._conn.execute('UPDATE proposals SET state=?,document=?,produced_assertion_id=? WHERE id=?',
                    (d['state'],document,d['produced'],d['id']))
            else:
                self._conn.execute('INSERT INTO proposals(id,kind,state,created_at,fingerprint,document,produced_assertion_id) VALUES(?,?,?,?,?,?,?)',
                    (d['id'],d['kind'],d['state'],d['created_at'],finger,document,d['produced']))

    def transaction(self):
        return sqlite_transaction(self._conn, self._lock)

    def commit(self) -> None:
        """Schließt die laufende Transaktion ab (etwa vor einem Schritt, der danach scheitern darf)."""
        with self._lock:
            self._conn.commit()

    def angenommene_aussagen_ab(self, nach: str, limit: int) -> list[str]:
        """Ids von Aussagen, die aus angenommenen Vorschlägen entstanden sind, aufsteigend nach `nach`."""
        with self._lock:
            return [r[0] for r in self._conn.execute(
                "SELECT DISTINCT produced_assertion_id FROM proposals WHERE produced_assertion_id>? "
                "AND state='accepted' ORDER BY produced_assertion_id LIMIT ?", (nach, limit))]

    def accepted_self_model_support(self, assertion_id):
        with self._lock:
            rows = self._conn.execute("SELECT document FROM proposals WHERE produced_assertion_id=? AND state='accepted' AND kind='assertion' LIMIT 2", (assertion_id,)).fetchall()
            result = [self._from_row(row) for row in rows]
            if any(p.produced != assertion_id or p.state is not ProposalState.ACCEPTED for p in result):
                raise ProposalError('Producer projection mismatch')
            return result

    def support_authorization(self, proposal_id):
        with self._lock:
            row = self._conn.execute('SELECT support_authorization FROM proposals WHERE id=?',(proposal_id,)).fetchone()
            return json.loads(row[0]) if row and row[0] else None

    def _issue_support_authorization(self, proposal_id, commitment):
        # Trusted service boundary, never Proposal.to_dict/_put/import or generic accept.
        if not self._conn.in_transaction:
            raise ProposalError('Authorization requires producer reservation')
        self._conn.execute('UPDATE proposals SET support_authorization=? WHERE id=?',
                           (json.dumps(commitment,sort_keys=True),proposal_id))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Proposal:
        d = json.loads(row["document"])
        if any(key in d for key in ('support_authorization', 'authorization', 'commitment')):
            raise ProposalError('Autorisierungen dürfen nicht aus Vorschlagsdokumenten importiert werden.')
        return Proposal(
            id=d["id"],
            kind=ProposalKind(d["kind"]),
            statement=d["statement"],
            rationale=d.get("rationale", ""),
            created_at=_parse(d["created_at"]),  # type: ignore[arg-type]
            assertion_kind=Kind(d["assertion_kind"]) if d.get("assertion_kind") else None,
            sensitivity=Sensitivity(d.get("sensitivity", "normal")),
            confidence=d.get("confidence"),
            evidence=[
                Evidence(
                    episode_id=e["episode_id"],
                    quote=e.get("quote", ""),
                    digest=e.get("digest", ""),
                )
                for e in d.get("evidence", [])
            ],
            about=list(d.get("about", [])),
            supersedes=list(d.get("supersedes", [])),
            state=ProposalState(d["state"]),
            decided_at=_parse(d.get("decided_at")),
            produced=d.get("produced"),
            proposed_by=d.get("proposed_by", ""),
            subject_ref=d.get("subject_ref", ""),
            predicate=d.get("predicate", ""),
            value=d.get("value", ""),
            scope_ref=d.get("scope_ref"),
            target_ref=d.get("target_ref"),
            valid_from=_parse(d.get("valid_from")),
            valid_until=_parse(d.get("valid_until")),
            depends_on=list(d.get("depends_on", [])),
            task_context=d.get("task_context"),
        )


__all__ = [
    "Evidence",
    "Proposal",
    "ProposalError",
    "ProposalKind",
    "ProposalState",
    "ProposalStore",
    "fingerprint",
]
