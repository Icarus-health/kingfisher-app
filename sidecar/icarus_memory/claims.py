"""Belegte Aussagen über Personen, Projekte und andere Entitäten.

Das Selbstmodell bleibt Aussagen über den lokalen Nutzer vorbehalten. Diese
Schicht trägt bestätigtes Wissen über andere Entitäten, ohne es in den Prompt
über den Nutzer zu mischen. Auch hier gilt: Quellen erzeugen zunächst
Vorschläge. Erst eine ausdrückliche Annahme wird zu einer ``Claim``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import claim_index
from .datumstext import iso_lesen_streng as _parse
from .episodes import EpisodeError, EpisodeKind, EpisodeState
from .person_digests import PersonDigests, TABLES as DIGEST_TABLES, install_schema as install_digest_schema
from .person_merges import PersonMerges, TABLES as MERGE_TABLES, install_schema as install_merge_schema
from .entities import EntityRegistry, install_schema, SCHEMA_TABLES, SCHEMA_INDEXES, SCHEMA_PRIMARY_KEYS
from .relations import predicates_equivalent, values_conflict, intervals_overlap, validate_interval
from .migrations import (
    IndexContract,
    Migration,
    run_migrations,
    validate_legacy_or_empty,
    verify_schema,
)
from .model import Status, ensure_aware, now
from .proposals import (
    Evidence,
    Proposal,
    ProposalError,
    ProposalKind,
    ProposalState,
    ProposalStore,
)


class ClaimError(Exception):
    """Ein Wissenskandidat oder eine bestätigte Aussage ist ungültig."""


@dataclass
class Claim:
    id: str
    proposal_id: str
    subject_ref: str
    predicate: str
    value: str
    statement: str
    evidence: list[Evidence]
    created_at: datetime
    scope_ref: str | None = None
    confidence: float | None = None
    status: Status = Status.ACTIVE
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    target_ref: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    depends_on: list[str] = field(default_factory=list)

    def usable(self, at: datetime | None = None) -> bool:
        moment = ensure_aware(at) or now()
        return (self.status is Status.ACTIVE
                and (self.valid_from is None or self.valid_from <= moment)
                and (self.valid_until is None or moment < self.valid_until))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_id": self.proposal_id,
            "subject_ref": self.subject_ref,
            "predicate": self.predicate,
            "value": self.value,
            "statement": self.statement,
            "scope_ref": self.scope_ref,
            "confidence": self.confidence,
            "status": self.status.value,
            "evidence": [item.to_dict() for item in self.evidence],
            "created_at": self.created_at.astimezone().isoformat(),
            "supersedes": list(self.supersedes),
            "superseded_by": self.superseded_by,
            "target_ref": self.target_ref,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "depends_on": list(self.depends_on),
        }


_CREATE_CLAIMS = """
CREATE TABLE IF NOT EXISTS knowledge_claims (
    id          TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    predicate   TEXT NOT NULL,
    value       TEXT NOT NULL,
    scope_ref   TEXT,
    statement   TEXT NOT NULL,
    evidence    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL,
    document    TEXT NOT NULL
)
"""

_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_proposal ON knowledge_claims(proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_claims_subject ON knowledge_claims(subject_ref)",
    "CREATE INDEX IF NOT EXISTS idx_claims_lookup ON knowledge_claims(subject_ref, predicate, scope_ref)",
    "CREATE INDEX IF NOT EXISTS idx_claims_status ON knowledge_claims(status)",
)
_INDEX_CONTRACTS = {
    "idx_claims_proposal": IndexContract(
        "knowledge_claims", ("proposal_id",), unique=True
    ),
    "idx_claims_subject": IndexContract("knowledge_claims", ("subject_ref",)),
    "idx_claims_lookup": IndexContract(
        "knowledge_claims", ("subject_ref", "predicate", "scope_ref")
    ),
    "idx_claims_status": IndexContract("knowledge_claims", ("status",)),
}
_SCHEMA = {
    "knowledge_claims": {
        "id", "proposal_id", "subject_ref", "predicate", "value", "scope_ref", "statement",
        "evidence", "created_at", "status", "document",
    }
}
_PRIMARY_KEYS = {"knowledge_claims": {"id"}}

_IMMUTABLE_TRIGGER_V1 = """
CREATE TRIGGER IF NOT EXISTS trg_claims_immutable
BEFORE UPDATE ON knowledge_claims
WHEN NEW.subject_ref IS NOT OLD.subject_ref
  OR NEW.proposal_id IS NOT OLD.proposal_id
  OR NEW.predicate IS NOT OLD.predicate
  OR NEW.value IS NOT OLD.value
  OR NEW.scope_ref IS NOT OLD.scope_ref
  OR NEW.statement IS NOT OLD.statement
  OR NEW.evidence IS NOT OLD.evidence
  OR NEW.created_at IS NOT OLD.created_at
BEGIN
  SELECT RAISE(ABORT, 'knowledge claim content is immutable');
END
"""

# Der eigentliche Leseweg verwendet `document`. Seine Inhalte müssen daher
# denselben Vertrag erfüllen wie die suchbaren Spalten darüber. Status und
# `superseded_by` dürfen sich beim expliziten Ersetzen ändern; jeder andere
# Teil des Dokuments bleibt unveränderlich. Ohne diese zweite Prüfung könnte
# eine direkte SQL-Aktualisierung den später gelesenen Satz austauschen, obwohl
# die Spalten selbst unverändert blieben.
_IMMUTABLE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS trg_claims_immutable
BEFORE UPDATE ON knowledge_claims
WHEN NEW.subject_ref IS NOT OLD.subject_ref
  OR NEW.proposal_id IS NOT OLD.proposal_id
  OR NEW.predicate IS NOT OLD.predicate
  OR NEW.value IS NOT OLD.value
  OR NEW.scope_ref IS NOT OLD.scope_ref
  OR NEW.statement IS NOT OLD.statement
  OR NEW.evidence IS NOT OLD.evidence
  OR NEW.created_at IS NOT OLD.created_at
  OR json_valid(NEW.document) = 0
  OR json_extract(NEW.document, '$.id') IS NOT NEW.id
  OR json_extract(NEW.document, '$.proposal_id') IS NOT NEW.proposal_id
  OR json_extract(NEW.document, '$.subject_ref') IS NOT NEW.subject_ref
  OR json_extract(NEW.document, '$.predicate') IS NOT NEW.predicate
  OR json_extract(NEW.document, '$.value') IS NOT NEW.value
  OR json_extract(NEW.document, '$.scope_ref') IS NOT NEW.scope_ref
  OR json_extract(NEW.document, '$.statement') IS NOT NEW.statement
  OR json_extract(NEW.document, '$.created_at') IS NOT NEW.created_at
  OR json_extract(NEW.document, '$.status') IS NOT NEW.status
  OR json_remove(NEW.document, '$.status', '$.superseded_by')
       IS NOT json_remove(OLD.document, '$.status', '$.superseded_by')
  OR (NEW.status IS OLD.status AND NEW.document IS NOT OLD.document)
BEGIN
  SELECT RAISE(ABORT, 'knowledge claim content is immutable');
END
"""
_TRIGGER_CONTRACTS_V1 = {"trg_claims_immutable": _IMMUTABLE_TRIGGER_V1}
_TRIGGER_CONTRACTS = {"trg_claims_immutable": _IMMUTABLE_TRIGGER}


def _migrate_v1(connection: sqlite3.Connection) -> None:
    validate_legacy_or_empty(
        connection,
        store="knowledge_claims",
        path=connection.execute("PRAGMA database_list").fetchone()[2],
        expected_tables=_SCHEMA,
        expected_indexes=_INDEX_CONTRACTS,
        expected_triggers=_TRIGGER_CONTRACTS_V1,
        expected_primary_keys=_PRIMARY_KEYS,
    )
    connection.execute(_CREATE_CLAIMS)
    for statement in _INDEXES:
        connection.execute(statement)
    connection.execute(_IMMUTABLE_TRIGGER_V1)


def _verify_v1(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_SCHEMA,
        expected_indexes=_INDEX_CONTRACTS,
        expected_triggers=_TRIGGER_CONTRACTS_V1,
        expected_primary_keys=_PRIMARY_KEYS,
    )


def _migrate_v2(connection: sqlite3.Connection) -> None:
    """Schützt auch das kanonische JSON-Dokument der bestehenden Aussagen."""
    connection.execute("DROP TRIGGER IF EXISTS trg_claims_immutable")
    connection.execute(_IMMUTABLE_TRIGGER)


def _verify_v2(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_SCHEMA,
        expected_indexes=_INDEX_CONTRACTS,
        expected_triggers=_TRIGGER_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )



# Identitäten und Änderungsjournal gehören in dieselbe gesicherte SQLite-Datei.
_EXTRA_TABLES = {"knowledge_changes": {"revision", "claim_id", "action", "reason", "created_at"}}

def _migrate_v3(connection: sqlite3.Connection) -> None:
    install_schema(connection)
    connection.execute("""CREATE TABLE knowledge_changes (
        revision INTEGER PRIMARY KEY, claim_id TEXT NOT NULL,
        action TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
    )""")

def _verify_v3(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_SCHEMA, **SCHEMA_TABLES, **_EXTRA_TABLES},
        expected_indexes={**_INDEX_CONTRACTS, **SCHEMA_INDEXES},
        expected_triggers=_TRIGGER_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, **SCHEMA_PRIMARY_KEYS,
                               "knowledge_changes": {"revision"}})


def _migrate_v4(connection: sqlite3.Connection) -> None:
    install_merge_schema(connection)


def _verify_v4(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_SCHEMA, **SCHEMA_TABLES, **_EXTRA_TABLES, **MERGE_TABLES},
        expected_indexes={**_INDEX_CONTRACTS, **SCHEMA_INDEXES},
        expected_triggers=_TRIGGER_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, **SCHEMA_PRIMARY_KEYS,
                               "knowledge_changes": {"revision"}, "person_merges": {"id"}})


def _migrate_v5(connection: sqlite3.Connection) -> None:
    install_digest_schema(connection)


def _verify_v5(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_SCHEMA, **SCHEMA_TABLES, **_EXTRA_TABLES, **MERGE_TABLES, **DIGEST_TABLES},
        expected_indexes={**_INDEX_CONTRACTS, **SCHEMA_INDEXES},
        expected_triggers=_TRIGGER_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, **SCHEMA_PRIMARY_KEYS,
                               "knowledge_changes": {"revision"}, "person_merges": {"id"},
                               "person_digest_cache": {"person_ref"}})


def _verify_v6(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_SCHEMA, **SCHEMA_TABLES, **_EXTRA_TABLES, **MERGE_TABLES, **DIGEST_TABLES, **claim_index.TABLES},
        expected_indexes={**_INDEX_CONTRACTS, **SCHEMA_INDEXES},
        expected_triggers={**_TRIGGER_CONTRACTS, **claim_index.TRIGGERS},
        expected_primary_keys={**_PRIMARY_KEYS, **SCHEMA_PRIMARY_KEYS,
                               "knowledge_changes": {"revision"}, "person_merges": {"id"},
                               "person_digest_cache": {"person_ref"}, **claim_index.PRIMARY_KEYS})
    claim_index.verify(connection)


def statements_conflict(left: Claim | Proposal, right: Claim | Proposal) -> bool:
    """Eine Regel für Annahme, Klärung und Gesprächskarten."""
    return (left.subject_ref == right.subject_ref
            and predicates_equivalent(left.predicate, right.predicate)
            and left.scope_ref == right.scope_ref
            and intervals_overlap(left.valid_from, left.valid_until,
                                  right.valid_from, right.valid_until)
            and values_conflict(left.predicate, left.value, right.value,
                                left.target_ref, right.target_ref))


_MIGRATIONS = (
    Migration(1, "initial_claim_store", _migrate_v1, _verify_v1),
    Migration(2, "protect_claim_document", _migrate_v2, _verify_v2),
    Migration(3, "entity_registry_and_changes", _migrate_v3, _verify_v3),
    Migration(4, "reversible_person_groups", _migrate_v4, _verify_v4),
    Migration(5, "derived_person_overviews", _migrate_v5, _verify_v5),
    Migration(6, "indexed_lexical_candidates_v1", claim_index.install, _verify_v6),
)


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


class ClaimStore:
    """Bestätigte Entitätsaussagen in einer lokalen, append-only SQLite-Datei."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            claim_index.register(self._conn)
            with self._lock:
                run_migrations(
                    self._conn,
                    store="knowledge_claims",
                    path=self._path,
                    migrations=_MIGRATIONS,
                )
        except Exception:
            self._conn.close()
            raise

    @property
    def person_digests(self) -> PersonDigests:
        return PersonDigests(self._conn, self._lock)

    @property
    def person_merges(self) -> PersonMerges:
        return PersonMerges(self._conn, self._lock)

    @property
    def entities(self) -> EntityRegistry:
        return EntityRegistry(self._conn, self._lock)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COALESCE(MAX(revision), 0) FROM knowledge_changes").fetchone()[0]

    def search_context(self, query: str, limit: int = 128) -> tuple[list[Claim], dict]:
        """Bounded lexical candidates; caller must validate current evidence."""
        with self._lock:
            rows, metadata = claim_index.search(self._conn, query, limit)
        return [self._from_row(row) for row in rows], metadata

    def get(self, claim_id: str) -> Claim:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM knowledge_claims WHERE id = ?", (claim_id,)
            ).fetchone()
        if row is None:
            raise ClaimError(f"Unbekannte Wissensaussage: {claim_id}")
        return self._from_row(row)

    def by_proposal(self, proposal_id: str) -> Claim | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM knowledge_claims WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def context_candidates(self, *, limit: int = 5000) -> list[Claim]:
        """Bounded candidates only; callers must validate time and provenance.

        Unlike all_claims this must not recursively traverse the whole store
        before the retrieval layer applies its dependency budget.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM knowledge_claims WHERE status = ? "
                "ORDER BY created_at DESC, id LIMIT ?",
                (Status.ACTIVE.value, max(0, min(limit, 5000))),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def semantic_inventory(self, limit: int) -> tuple[list[str], int]:
        """Bounded derived-index candidates, never a claim-usability decision."""
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError('invalid semantic inventory limit')
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM knowledge_claims WHERE status = ?",
                (Status.ACTIVE.value,)).fetchone()[0]
            rows = self._conn.execute("SELECT id FROM knowledge_claims WHERE status = ? "
                "ORDER BY created_at DESC, id LIMIT ?", (Status.ACTIVE.value, limit)).fetchall()
        return [row[0] for row in rows], count

    def source_is_unclaimed(self, episode_id: str) -> bool:
        """Conservative raw-display gate, including retracted/expired knowledge.

        Bounded work; failure to establish absence also defers the source. This
        is deliberately not an assertion that every interpretation is current.
        """
        steps = 0
        def budget():
            nonlocal steps
            steps += 1000
            return int(steps >= 100000)
        with self._lock:
            self._conn.set_progress_handler(budget, 1000)
            try:
                row = self._conn.execute(
                    "SELECT 1 FROM knowledge_claims c, json_each(c.evidence) e "
                    "WHERE json_extract(e.value, '$.episode_id')=? LIMIT 1", (episode_id,)).fetchone()
                return row is None
            except sqlite3.Error:
                return False
            finally:
                self._conn.set_progress_handler(None, 0)

    def all_claims(self, *, include_inactive: bool = True, limit: int = 5000, at: datetime | None = None) -> list[Claim]:
        sql = "SELECT document FROM knowledge_claims"
        params: list[Any] = []
        if not include_inactive:
            sql += " WHERE status = ?"
            params.append(Status.ACTIVE.value)
        sql += " ORDER BY created_at DESC"
        if include_inactive:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        result = [self._from_row(row) for row in rows]
        return result if include_inactive else [claim for claim in result if self.is_usable(claim, at=at)][:limit]

    def by_reference(self, reference: str, *, include_inactive: bool = False) -> list[Claim]:
        """Alle ausdrücklich zugeordneten Beziehungen, ohne globales Listenlimit."""
        references = (reference, reference.removeprefix("project:")) if reference.startswith("project:") else (reference,)
        placeholders = ",".join("?" for _ in references)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM knowledge_claims WHERE subject_ref IN ({placeholders}) "
                f"OR scope_ref IN ({placeholders}) OR json_extract(document, '$.target_ref') IN ({placeholders}) "
                "ORDER BY created_at DESC", references * 3,
            ).fetchall()
        result = [self._from_row(row) for row in rows]
        return result if include_inactive else [claim for claim in result if self.is_usable(claim)]

    def by_predicate(self, predicates: Any) -> list[Claim]:
        """Alle geltenden Aussagen mit einer dieser Beziehungen (etwa alle bestätigten Geburtstage), neueste zuerst."""
        werte = list(dict.fromkeys(str(p) for p in predicates))
        if not werte:
            return []
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM knowledge_claims WHERE status = ? AND predicate IN ({','.join('?' for _ in werte)}) "
                "ORDER BY created_at DESC", [Status.ACTIVE.value, *werte],
            ).fetchall()
        return [claim for claim in (self._from_row(row) for row in rows) if self.is_usable(claim)]

    def by_subject(self, subject_ref: str, *, include_inactive: bool = False) -> list[Claim]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM knowledge_claims WHERE subject_ref = ? "
                "ORDER BY created_at DESC",
                (subject_ref,),
            ).fetchall()
        result = [self._from_row(row) for row in rows]
        if not include_inactive:
            result = [claim for claim in result if self.is_usable(claim)]
        return result

    def is_usable(self, claim: Claim, *, at: datetime | None = None, _seen: frozenset[str] = frozenset()) -> bool:
        from .claim_traversal import validate_chain
        moment = ensure_aware(at) or now()
        try:
            return validate_chain(claim, self.get, lambda item: item.usable(moment), excluded=_seen)
        except ClaimError:
            return False

    def _depends_on_any(self, claim: Claim, roots: set[str], seen: frozenset[str] = frozenset()) -> bool:
        if claim.id in roots:
            return True
        if claim.id in seen:
            return False
        return any(self._depends_on_any(self.get(item), roots, seen | {claim.id})
                   for item in claim.depends_on)

    def conflicts_for(self, proposal: Proposal) -> list[Claim]:
        # Einschließlich künftig gültiger Aussagen; die Intervalle entscheiden.
        return [claim for claim in self.by_subject(proposal.subject_ref, include_inactive=True)
                if claim.status is Status.ACTIVE and statements_conflict(claim, proposal)]

    def _change(self, claim_id: str, action: str, reason: str, at: datetime) -> None:
        self._conn.execute(
            "INSERT INTO knowledge_changes (claim_id, action, reason, created_at) VALUES (?, ?, ?, ?)",
            (claim_id, action, reason, at.isoformat()))

    def _set_status(self, claim_id: str, status: Status, successor: str | None = None) -> None:
        # Original-JSON beibehalten: ältere Dokumente haben die neuen optionalen
        # Felder noch nicht. Eine Statusänderung darf sie nicht still ergänzen.
        row = self._conn.execute("SELECT document FROM knowledge_claims WHERE id = ?", (claim_id,)).fetchone()
        data = json.loads(row["document"])
        data["status"] = status.value
        data["superseded_by"] = successor
        self._conn.execute("UPDATE knowledge_claims SET status = ?, document = ? WHERE id = ?",
                           (status.value, json.dumps(data, ensure_ascii=False), claim_id))

    def _invalidate_dependents(self, roots: set[str], at: datetime) -> None:
        rows = self._conn.execute("SELECT document FROM knowledge_claims WHERE status = ?",
                                  (Status.ACTIVE.value,)).fetchall()
        remaining = [self._from_row(row) for row in rows]
        changed = True
        while changed:
            changed = False
            for claim in remaining[:]:
                if roots.intersection(claim.depends_on):
                    self._set_status(claim.id, Status.DISPUTED)
                    self._change(claim.id, "disputed", "Grundlage wurde ersetzt oder zurückgezogen.", at)
                    roots.add(claim.id)
                    remaining.remove(claim)
                    changed = True

    def accept(self, proposal: Proposal, *, supersedes: list[str], at: datetime, correction_of: str | None = None) -> Claim:
        if proposal.kind is not ProposalKind.KNOWLEDGE:
            raise ClaimError("Nur ein Wissenskandidat kann hier angenommen werden.")
        validate_interval(proposal.valid_from, proposal.valid_until)
        # Auch verschiedene Verbindungen/Prozesse prüfen Konflikte erst unter
        # dem SQLite-Schreiblock. Sonst könnten zwei Wahrheiten parallel gewinnen.
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                existing = self.by_proposal(proposal.id)
                if existing is not None:
                    self._conn.rollback()
                    return existing
                expected = {claim.id for claim in self.conflicts_for(proposal)}
                supplied = set(supersedes)
                if correction_of is not None and (supplied != {correction_of} or expected - {correction_of}):
                    raise ClaimError("Die Korrektur darf keine andere Aussage ersetzen.")
                if not expected.issubset(supplied):
                    raise ClaimError("Die zu ersetzenden Aussagen müssen ausdrücklich und vollständig bestätigt werden.")
                old_claims = [self.get(claim_id) for claim_id in supplied]
                for old in old_claims:
                    if (old.status is not Status.ACTIVE or old.subject_ref != proposal.subject_ref
                            or not predicates_equivalent(old.predicate, proposal.predicate)
                            or (old.scope_ref != proposal.scope_ref and old.id != correction_of)):
                        raise ClaimError("Nur aktive Aussagen derselben Beziehung und desselben Kontexts dürfen ersetzt werden.")
                for dependency in proposal.depends_on:
                    basis = self.get(dependency)
                    if not self.is_usable(basis, at=at) or self._depends_on_any(basis, supplied):
                        raise ClaimError("Die Grundlage ist nicht mehr gültig; der Kandidat muss neu geprüft werden.")
                claim = Claim(
                    id=f"k-{uuid.uuid4().hex[:12]}", proposal_id=proposal.id,
                    subject_ref=proposal.subject_ref, predicate=proposal.predicate,
                    value=proposal.value, statement=proposal.statement,
                    evidence=list(proposal.evidence), created_at=ensure_aware(at) or now(),
                    scope_ref=proposal.scope_ref, confidence=proposal.confidence,
                    supersedes=sorted(supplied), target_ref=proposal.target_ref,
                    valid_from=proposal.valid_from, valid_until=proposal.valid_until,
                    depends_on=list(proposal.depends_on))
                data = claim.to_dict()
                self._conn.execute(
                    "INSERT INTO knowledge_claims "
                    "(id, proposal_id, subject_ref, predicate, value, scope_ref, statement, "
                    "evidence, created_at, status, document) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (claim.id, claim.proposal_id, claim.subject_ref, claim.predicate,
                     claim.value, claim.scope_ref, claim.statement,
                     json.dumps(data["evidence"], ensure_ascii=False, sort_keys=True),
                     data["created_at"], claim.status.value, json.dumps(data, ensure_ascii=False)))
                for old in old_claims:
                    self._set_status(old.id, Status.SUPERSEDED, claim.id)
                    self._change(old.id, "superseded", claim.id, at)
                self._invalidate_dependents(supplied, at)
                self._change(claim.id, "accepted", proposal.id, at)
                self._conn.commit()
                return self.get(claim.id)
            except Exception:
                self._conn.rollback()
                raise

    def invalidate_source(self, episode_id: str, *, at: datetime | None = None) -> None:
        """Entzogene Belege sperren Wissen, ohne eine Aussage als falsch zu bewerten.

        Status und Änderungsjournal werden gemeinsam geschrieben. Keine
        Listenbegrenzung: auch alte und erst künftig gültige Aussagen zählen.
        """
        moment = ensure_aware(at) or now()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                rows = self._conn.execute(
                    "SELECT document FROM knowledge_claims WHERE status = ?",
                    (Status.ACTIVE.value,),
                ).fetchall()
                roots = set()
                for row in rows:
                    claim = self._from_row(row)
                    if any(item.episode_id == episode_id for item in claim.evidence):
                        self._set_status(claim.id, Status.DISPUTED)
                        self._change(claim.id, "disputed", f"Quelle ausgeschlossen: {episode_id}", moment)
                        roots.add(claim.id)
                self._invalidate_dependents(roots, moment)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def retract(self, claim_id: str, *, reason: str, at: datetime | None = None) -> Claim:
        if not reason.strip():
            raise ClaimError("Ein Widerruf braucht eine Begründung.")
        moment = ensure_aware(at) or now()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                claim = self.get(claim_id)
                if claim.status is Status.RETRACTED:
                    self._conn.rollback()
                    return claim
                if claim.status not in {Status.ACTIVE, Status.DISPUTED}:
                    raise ClaimError("Diese Aussage ist bereits inaktiv.")
                self._set_status(claim_id, Status.RETRACTED)
                self._change(claim_id, "retracted", reason.strip(), moment)
                self._invalidate_dependents({claim_id}, moment)
                self._conn.commit()
                return self.get(claim_id)
            except Exception:
                self._conn.rollback()
                raise

    def changes(self, *, after: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._conn.execute(
                "SELECT * FROM knowledge_changes WHERE revision > ? ORDER BY revision", (after,)).fetchall()]

    def as_known_at(self, known_at: datetime, *, episodes, valid_at: datetime | None = None,
                    reference: str | None = None, limit: int = 100, cursor: str | None = None) -> dict[str, Any]:
        from .memory_history import snapshot
        return snapshot(self, episodes, known_at, valid_at=valid_at, reference=reference, limit=limit, cursor=cursor)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Claim:
        data = json.loads(row["document"])
        return Claim(
            id=data["id"],
            proposal_id=data["proposal_id"],
            subject_ref=data["subject_ref"],
            predicate=data["predicate"],
            value=data["value"],
            statement=data["statement"],
            scope_ref=data.get("scope_ref"),
            confidence=data.get("confidence"),
            evidence=[Evidence(**item) for item in data.get("evidence", [])],
            created_at=_parse(data["created_at"]),
            status=Status(data["status"]),
            supersedes=list(data.get("supersedes", [])),
            superseded_by=data.get("superseded_by"),
            target_ref=data.get("target_ref"),
            valid_from=_parse(data["valid_from"]) if data.get("valid_from") else None,
            valid_until=_parse(data["valid_until"]) if data.get("valid_until") else None,
            depends_on=list(data.get("depends_on", [])),
        )


class KnowledgeService:
    """Belegprüfung, Vorschläge, Konflikte und ausdrückliche Annahme."""

    def __init__(self, *, proposals: ProposalStore, claims: ClaimStore, episodes: Any) -> None:
        self._proposals = proposals
        self._claims = claims
        self._episodes = episodes

    def propose(
        self,
        *,
        subject_ref: str,
        predicate: str,
        value: str,
        statement: str,
        rationale: str,
        evidence: list[Evidence],
        scope_ref: str | None = None,
        target_ref: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        depends_on: list[str] | None = None,
        confidence: float | None = None,
        proposed_by: str = "",
        at: datetime | None = None,
    ) -> tuple[Proposal, bool]:
        for item in evidence:
            self._validate(item)
        return self._proposals.propose(
            ProposalKind.KNOWLEDGE,
            statement,
            rationale,
            confidence=confidence,
            evidence=evidence,
            subject_ref=subject_ref,
            predicate=predicate,
            value=value,
            scope_ref=scope_ref,
            target_ref=target_ref, valid_from=valid_from, valid_until=valid_until,
            depends_on=depends_on,
            proposed_by=proposed_by,
            at=at,
        )

    def pending(self) -> list[Proposal]:
        return self._proposals.pending(ProposalKind.KNOWLEDGE, limit=500)

    def answer_conflict_status(self, claim_ids) -> str:
        """Live bounded check; pending alternatives are never accepted facts."""
        from .knowledge_conflicts import check
        return check(claim_ids, self._claims, self._proposals, self._episodes)

    def clarifications(self) -> list[dict[str, Any]]:
        pending = self.pending()
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in pending:
            active = self._claims.conflicts_for(candidate)
            competing = [
                other
                for other in pending
                if other.id != candidate.id
                and statements_conflict(other, candidate)
            ]
            ids = sorted([candidate.id, *(item.id for item in competing)])
            active_ids = sorted(item.id for item in active)
            if not competing and not active:
                continue
            key = "|".join((*ids, *active_ids))
            clarification_id = "c:" + hashlib.sha256(key.encode()).hexdigest()[:16]
            if clarification_id in seen:
                continue
            seen.add(clarification_id)
            result.append({
                "id": clarification_id,
                "subject_ref": candidate.subject_ref,
                "predicate": candidate.predicate,
                "scope_ref": candidate.scope_ref,
                "candidates": [item.to_dict() for item in [candidate, *competing]],
                "active_claims": [item.to_dict() for item in active],
                "decision_required": True,
            })
        return sorted(result, key=lambda item: item["id"])

    def accept(
        self, proposal_id: str, *, supersedes: list[str], at: datetime | None = None,
        correction_of: str | None = None
    ) -> Claim:
        proposal = self._proposals.get(proposal_id)
        if proposal.kind is not ProposalKind.KNOWLEDGE:
            raise ClaimError("Dieser Vorschlag ist kein Wissenskandidat.")
        if proposal.state is ProposalState.ACCEPTED and proposal.produced:
            return self._claims.get(proposal.produced)
        if proposal.state is not ProposalState.PENDING:
            raise ClaimError(
                f"Wissenskandidat {proposal_id} ist bereits {proposal.state.value}."
            )
        for item in proposal.evidence:
            self._validate(item)
        moment = ensure_aware(at) or now()
        claim = self._claims.accept(proposal, supersedes=supersedes, at=moment, correction_of=correction_of)
        latest = self._proposals.get(proposal_id)
        if latest.state is ProposalState.PENDING:
            try:
                self._proposals.accept(proposal_id, produced=claim.id, at=moment)
            except ProposalError:
                # Zwei Threads können beide noch den offenen Vorschlag sehen,
                # nachdem der Claim-Store den einen Claim bereits sauber
                # serialisiert hat. Der zweite darf dann nicht an einem
                # veralteten Proposal-Zustand scheitern, sondern muss den
                # inzwischen entschiedenen Stand lesen.
                latest = self._proposals.get(proposal_id)
                if not (
                    latest.state is ProposalState.ACCEPTED
                    and latest.produced == claim.id
                ):
                    raise
        elif not (
            latest.state is ProposalState.ACCEPTED and latest.produced == claim.id
        ):
            raise ClaimError(
                "Die Wissensaussage wurde gespeichert, aber der Vorschlagsstatus "
                "ist inkonsistent. Bitte nicht erneut entscheiden."
            )
        for other in self.pending():
            if (
                other.id != proposal.id
                and statements_conflict(other, proposal)
            ):
                self._proposals.supersede(other.id, at=moment)
        return claim

    def reject(self, proposal_id: str, *, at: datetime | None = None) -> Proposal:
        proposal = self._proposals.get(proposal_id)
        if proposal.kind is not ProposalKind.KNOWLEDGE:
            raise ClaimError("Dieser Vorschlag ist kein Wissenskandidat.")
        return self._proposals.reject(proposal_id, at=at)

    def _validate(self, evidence: Evidence) -> None:
        try:
            episode = self._episodes.get(evidence.episode_id)
        except EpisodeError as exc:
            raise ClaimError(str(exc)) from exc
        if episode.kind is EpisodeKind.SUMMARY or episode.state is EpisodeState.IGNORED:
            raise ClaimError("Zusammenfassungen und ignorierte Quellen sind keine Wissensbelege.")
        if not evidence.digest or evidence.digest != episode.digest:
            raise ClaimError("Der Beleg-Digest fehlt oder die Quelle hat sich verändert.")
        quote = " ".join(evidence.quote.split()).casefold()
        body = " ".join(episode.body.split()).casefold()
        if not quote or quote not in body:
            raise ClaimError("Das angegebene Zitat steht nicht in der Quelle.")


__all__ = ["Claim", "ClaimError", "ClaimStore", "KnowledgeService"]
