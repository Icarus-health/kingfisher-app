"""Persistente lokale Gespräche für die Kingfisher-Oberfläche."""

from __future__ import annotations

import json
import base64
import hashlib
import math
import re
import copy
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .datumstext import iso_lesen_streng as _parse
from .migrations import IndexContract, Migration, run_migrations, verify_schema
from .model import now


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    status: str
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at.astimezone().isoformat(),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.astimezone().isoformat(),
            "updated_at": self.updated_at.astimezone().isoformat(),
        }


@dataclass(frozen=True)
class ConversationSummary:
    """Die belegte, sparsame Zeile für die Gesprächshistorie."""

    id: str
    title: str
    updated_at: datetime
    preview: str
    message_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "updated_at": self.updated_at.astimezone().isoformat(),
            "preview": self.preview,
            "message_count": self.message_count,
        }


_CREATE = (
"""CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)""",
"""CREATE TABLE IF NOT EXISTS conversation_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL
)""",
"""CREATE INDEX IF NOT EXISTS idx_conversation_messages_order
    ON conversation_messages(conversation_id, created_at, id)""",
)

_SCHEMA = {
    "conversations": {"id", "title", "created_at", "updated_at"},
    "conversation_messages": {
        "id", "conversation_id", "role", "content", "status", "created_at", "metadata"
    },
}
_INDEXES = {
    "idx_conversation_messages_order": IndexContract(
        "conversation_messages", ("conversation_id", "created_at", "id")
    )
}
_PRIMARY_KEYS = {"conversations": {"id"}, "conversation_messages": {"id"}}


def _migrate_v1(connection: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables and not tables.issubset(_SCHEMA):
        raise sqlite3.DatabaseError("Unbekanntes Legacy-Schema für conversations")
    # ``executescript`` beendet unter sqlite3 eine laufende Transaktion. Die
    # gemeinsame Migrationsschicht garantiert aber genau eine atomare
    # ``BEGIN IMMEDIATE``-Transaktion pro Version, deshalb einzeln ausführen.
    for statement in _CREATE:
        connection.execute(statement)


def _verify_v1(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_SCHEMA,
        expected_indexes=_INDEXES,
        expected_primary_keys=_PRIMARY_KEYS,
    )


_DRAFT_SCHEMA = {**_SCHEMA, "conversation_drafts": {"composer_id", "text", "revision"}}


def _migrate_v2(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE conversation_drafts (
        composer_id TEXT PRIMARY KEY,
        text TEXT NOT NULL CHECK (typeof(text) = 'text' AND length(text) <= 20000),
        revision INTEGER NOT NULL CHECK (typeof(revision) = 'integer' AND revision >= 1)
    )""")


def _verify_v2(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_DRAFT_SCHEMA,
        expected_indexes=_INDEXES,
        expected_primary_keys={**_PRIMARY_KEYS, "conversation_drafts": {"composer_id"}},
    )


_HANDOFF_SCHEMA = {**_DRAFT_SCHEMA, "conversation_draft_handoffs": {
    "id", "conversation_id", "composer_revision", "text", "state",
}}
_HANDOFF_INDEXES = {
    **_INDEXES,
    "idx_conversation_draft_handoffs_revision": IndexContract(
        "conversation_draft_handoffs", ("composer_revision",), unique=True),
    "idx_conversation_draft_handoffs_conversation": IndexContract(
        "conversation_draft_handoffs", ("conversation_id",), unique=True),
}


def _migrate_v3(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE conversation_draft_handoffs (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        composer_revision INTEGER NOT NULL CHECK (typeof(composer_revision) = 'integer' AND composer_revision >= 1),
        text TEXT NOT NULL CHECK (typeof(text) = 'text' AND length(text) <= 20000),
        state TEXT NOT NULL CHECK (state IN ('ready','started','accepted'))
    )""")
    connection.execute("CREATE UNIQUE INDEX idx_conversation_draft_handoffs_revision ON conversation_draft_handoffs(composer_revision)")
    connection.execute("CREATE UNIQUE INDEX idx_conversation_draft_handoffs_conversation ON conversation_draft_handoffs(conversation_id)")


def _verify_v3(connection: sqlite3.Connection) -> None:
    verify_schema(connection, expected_tables=_HANDOFF_SCHEMA, expected_indexes=_HANDOFF_INDEXES,
        expected_primary_keys={**_PRIMARY_KEYS, "conversation_drafts": {"composer_id"}, "conversation_draft_handoffs": {"id"}})


_MIGRATIONS = (
    Migration(1, "initial_conversations", _migrate_v1, _verify_v1),
    Migration(2, "unsent_conversation_drafts", _migrate_v2, _verify_v2),
    Migration(3, "new_conversation_draft_handoffs", _migrate_v3, _verify_v3),
)


class DraftConflict(RuntimeError):
    """A draft write was based on a revision that is no longer current."""


class ConversationStore:
    """Eine versionierte SQLite-Ablage mit serialisierten Schreibvorgängen."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Mac- und Container-Bestände können verschiedene UTC-Offsets tragen.
        # Python erhält dabei auch Mikrosekunden, die SQLite julianday rundet.
        self._conn.create_function("kingfisher_time", 1, lambda value: _parse(value).timestamp(), deterministic=True)
        self._conn.create_function("kingfisher_casefold", 1, lambda value: str(value or "").casefold(), deterministic=True)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        try:
            with self._lock:
                run_migrations(
                    self._conn,
                    store="conversations",
                    path=self._path,
                    migrations=_MIGRATIONS,
                )
        except Exception:
            self._conn.close()
            raise

    @staticmethod
    def _draft_id(composer_id: str) -> None:
        if not isinstance(composer_id, str) or (composer_id != "new" and not re.fullmatch(r"c-[0-9a-f]{12}", composer_id)):
            raise ValueError("Ungültige Gesprächskennung.")

    def _require_composer(self, composer_id: str) -> None:
        # Called only while holding the short Store lock / write transaction.
        if composer_id != "new" and self._conn.execute(
            "SELECT 1 FROM conversations WHERE id=?", (composer_id,)
        ).fetchone() is None:
            raise KeyError(composer_id)

    def draft_get(self, composer_id: str) -> dict[str, Any]:
        """Return unsent composer input without touching messages or recency."""
        self._draft_id(composer_id)
        with self._lock:
            self._require_composer(composer_id)
            row = self._conn.execute(
                "SELECT text,revision FROM conversation_drafts WHERE composer_id=?", (composer_id,)
            ).fetchone()
            if composer_id == "new":
                handoff = self._conn.execute(
                    "SELECT * FROM conversation_draft_handoffs ORDER BY composer_revision DESC LIMIT 1"
                ).fetchone()
            else:
                handoff = self._conn.execute(
                    "SELECT * FROM conversation_draft_handoffs WHERE conversation_id=?", (composer_id,)
                ).fetchone()
        result = {"text": row["text"], "revision": row["revision"]} if row else {"text": "", "revision": 0}
        if handoff:
            if composer_id != "new":
                result["handoff"] = self._handoff_payload(handoff)["handoff"]
            elif handoff["state"] != "accepted":
                # Offer only the latest binding for recovery. Older unfinished
                # handoffs remain on their conversations, never hijack new input.
                result["binding"] = self._handoff_payload(handoff)
        return result

    @staticmethod
    def _draft_revision(expected_revision: int) -> None:
        if type(expected_revision) is not int or not 0 <= expected_revision <= 2**63 - 2:
            raise ValueError("Ungültige Entwurfsrevision.")

    def draft_put(self, composer_id: str, text: str, expected_revision: int) -> dict[str, Any]:
        """Atomic CAS, including empty tombstones and the exact previous retry.

        BEGIN IMMEDIATE protects independent Store connections too. No model or
        conversation-wide lock is involved, and drafts never enter chat history.
        """
        self._draft_id(composer_id)
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("Ein Entwurf darf höchstens 20000 Zeichen enthalten.")
        self._draft_revision(expected_revision)
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._require_composer(composer_id)
                row = self._conn.execute(
                    "SELECT text,revision FROM conversation_drafts WHERE composer_id=?", (composer_id,)
                ).fetchone()
                revision = row["revision"] if row else 0
                if revision != expected_revision:
                    if row and revision == expected_revision + 1 and row["text"] == text:
                        self._conn.commit()
                        return {"text": text, "revision": revision}
                    raise DraftConflict("Der Entwurf wurde inzwischen geändert.")
                revision += 1
                self._conn.execute(
                    "INSERT INTO conversation_drafts (composer_id,text,revision) VALUES (?,?,?) "
                    "ON CONFLICT(composer_id) DO UPDATE SET text=excluded.text,revision=excluded.revision",
                    (composer_id, text, revision),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return {"text": text, "revision": revision}

    @staticmethod
    def _handoff_payload(row) -> dict[str, Any]:
        return {"conversation_id": row["conversation_id"],
                "handoff": {"id": row["id"], "text": "" if row["state"] == "accepted" else row["text"], "state": row["state"]}}

    def draft_bind(self, expected_revision: int) -> dict[str, Any]:
        """Freeze one saved new-composer revision and atomically create its chat.

        Binding neither sends a message nor claims a send attempt. An exact
        revision retry retrieves its immutable binding even after later typing.
        """
        self._draft_revision(expected_revision)
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                existing = self._conn.execute(
                    "SELECT * FROM conversation_draft_handoffs WHERE composer_revision=?", (expected_revision,)
                ).fetchone()
                if existing:
                    self._conn.commit()
                    return self._handoff_payload(existing)
                draft = self._conn.execute("SELECT text,revision FROM conversation_drafts WHERE composer_id='new'").fetchone()
                revision = draft["revision"] if draft else 0
                if revision != expected_revision:
                    raise DraftConflict("Der Entwurf wurde inzwischen geändert.")
                if not draft or not draft["text"].strip():
                    raise ValueError("Zum Senden wird ein nicht leerer Entwurf benötigt.")
                conversation_id = f"c-{uuid.uuid4().hex[:12]}"
                handoff_id = "h-" + uuid.uuid4().hex
                timestamp = now().astimezone().isoformat()
                self._conn.execute("INSERT INTO conversations (id,title,created_at,updated_at) VALUES (?,?,?,?)",
                    (conversation_id, "Neues Gespräch", timestamp, timestamp))
                self._conn.execute("INSERT INTO conversation_draft_handoffs (id,conversation_id,composer_revision,text,state) VALUES (?,?,?,?,'ready')",
                    (handoff_id, conversation_id, revision, draft["text"]))
                self._conn.execute("UPDATE conversation_drafts SET text='',revision=? WHERE composer_id='new'", (revision + 1,))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return {"conversation_id": conversation_id, "handoff": {"id": handoff_id, "text": draft["text"], "state": "ready"}}

    def _draft_handoff_transition(self, conversation_id: str, handoff_id: str, *, finish: bool) -> dict[str, Any]:
        self._draft_id(conversation_id)
        if conversation_id == "new" or not isinstance(handoff_id, str) or not re.fullmatch(r"h-[0-9a-f]{32}", handoff_id):
            raise ValueError("Ungültige Gesprächsübergabe.")
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute("SELECT * FROM conversation_draft_handoffs WHERE id=? AND conversation_id=?",
                    (handoff_id, conversation_id)).fetchone()
                if row is None:
                    raise KeyError(handoff_id)
                state = row["state"]
                claimed = not finish and state == "ready"
                if finish and state == "ready":
                    raise DraftConflict("Der Versand wurde noch nicht begonnen.")
                if finish:
                    # The message owns confirmed content now. Keep only the
                    # binding/claim tombstone, never a second retained copy that
                    # could outlive later message deletion or redaction.
                    state = "accepted"
                    self._conn.execute("UPDATE conversation_draft_handoffs SET state='accepted',text='' WHERE id=?", (handoff_id,))
                elif claimed:
                    state = "started"
                    self._conn.execute("UPDATE conversation_draft_handoffs SET state='started' WHERE id=?", (handoff_id,))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        result = self._handoff_payload(row)
        result["handoff"]["state"] = state
        if finish:
            result["handoff"]["text"] = ""
        if not finish:
            result["claimed"] = claimed
        return result

    def draft_handoff_start(self, conversation_id: str, handoff_id: str) -> dict[str, Any]:
        """Claim at most one send attempt; a lost reply never permits a retry."""
        return self._draft_handoff_transition(conversation_id, handoff_id, finish=False)

    def draft_handoff_finish(self, conversation_id: str, handoff_id: str) -> dict[str, Any]:
        """Mark confirmed HTTP acceptance without changing any follow-up draft."""
        return self._draft_handoff_transition(conversation_id, handoff_id, finish=True)

    def create(self, title: str = "Neues Gespräch", *, at: datetime | None = None) -> Conversation:
        timestamp = (at or now()).astimezone().isoformat()
        conversation_id = f"c-{uuid.uuid4().hex[:12]}"
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conversation_id, title.strip() or "Neues Gespräch", timestamp, timestamp),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get(conversation_id)  # type: ignore[return-value]

    def get(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return self._conversation(row) if row else None

    def latest(self) -> Conversation | None:
        """Das zuletzt aktualisierte Gespräch, unabhängig vom Browserprofil."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations ORDER BY kingfisher_time(updated_at) DESC, id DESC LIMIT 1"
            ).fetchone()
        return self._conversation(row) if row else None

    def list(self, limit: int = 100) -> list[ConversationSummary]:
        """Listet die jüngsten Gespräche ohne ihren vollständigen Verlauf.

        Der Ausschnitt stammt aus der letzten gespeicherten Nachricht; er wird
        nicht vom Modell formuliert und macht keine Aussage über einen Status,
        den der Bestand nicht kennt.
        """
        safe_limit = max(1, min(int(limit), 200))
        with self._lock:
            rows = self._conn.execute(
                """SELECT c.id, c.title, c.updated_at,
                          COUNT(m.id) AS message_count,
                          COALESCE((
                            SELECT CASE WHEN last.role = 'assistant' AND json_valid(last.metadata)
                              AND (json_extract(last.metadata, '$.context.answer_mode') = 'memory_evidence'
                                OR json_array_length(json_extract(last.metadata, '$.context.knowledge_claim_ids')) > 0)
                              THEN 'Gedächtnisantwort — beim Öffnen erneut geprüft.'
                              ELSE last.content END
                            FROM conversation_messages AS last
                            WHERE last.conversation_id = c.id
                            ORDER BY kingfisher_time(last.created_at) DESC, last.rowid DESC
                            LIMIT 1
                          ), '') AS preview
                   FROM conversations AS c
                   LEFT JOIN conversation_messages AS m ON m.conversation_id = c.id
                   GROUP BY c.id
                   ORDER BY kingfisher_time(c.updated_at) DESC, c.id DESC
                   LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [self._summary(row) for row in rows]

    def page(self, *, q: str = "", limit: int = 30, cursor: str | None = None, filter_summary=None) -> dict[str, Any]:
        """Bounded keyset search across titles and message bodies, without a model.

        Evidence-based assistant replies are placeholders until opened and
        revalidated, so their old raw bodies are excluded from search too.
        HTTP callers must apply the same lineage sanitizer as the older list.
        """
        if not isinstance(q, str) or len(q) > 200:
            raise ValueError("Suchtext darf höchstens 200 Zeichen enthalten")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Limit muss zwischen 1 und 100 liegen")
        query = q.strip().casefold()
        fingerprint = hashlib.sha256(query.encode("utf-8")).hexdigest()
        position = None
        if cursor is not None:
            try:
                if len(cursor) > 1000:
                    raise ValueError()
                decoded = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
                if (not isinstance(decoded, dict) or set(decoded) != {"v", "q", "t", "id"}
                        or type(decoded["v"]) is not int or decoded["v"] != 1 or decoded["q"] != fingerprint
                        or isinstance(decoded["t"], bool) or not isinstance(decoded["t"], (int, float))
                        or not math.isfinite(decoded["t"])
                        or not isinstance(decoded["id"], str) or not re.fullmatch(r"c-[0-9a-f]{12}", decoded["id"])):
                    raise ValueError()
                position = (decoded["t"], decoded["t"], decoded["id"])
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                raise ValueError("Cursor ist ungültig oder gehört zu einer anderen Suche") from exc
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        # CASE guards json_extract for malformed imported metadata.
        protected = """CASE WHEN json_valid(m.metadata) THEN
            (COALESCE(json_extract(m.metadata, '$.context.answer_mode') = 'memory_evidence', 0)
             OR COALESCE(json_array_length(json_extract(m.metadata, '$.context.knowledge_claim_ids')), 0) > 0
             OR json_type(m.metadata, '$.context.source_answer') IS NOT NULL
             OR json_type(m.metadata, '$.context.working_answer') IS NOT NULL
             OR json_type(m.metadata, '$.context.mappe_answer') IS NOT NULL)
            ELSE 1 END"""
        match = f"""(kingfisher_casefold(c.title) LIKE ? ESCAPE '\\' OR EXISTS (
            SELECT 1 FROM conversation_messages m WHERE m.conversation_id = c.id
              AND (m.role = 'user' OR (m.role = 'assistant' AND NOT ({protected})))
              AND kingfisher_casefold(m.content) LIKE ? ESCAPE '\\'))"""
        parameters: list[Any] = [pattern, pattern]
        after = ""
        if position:
            after = " AND (kingfisher_time(c.updated_at) < ? OR (kingfisher_time(c.updated_at) = ? AND c.id < ?))"
        projection = f"""SELECT c.id, c.title, c.updated_at,
                (SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = c.id) AS message_count,
                COALESCE((SELECT CASE WHEN m.role = 'assistant' AND ({protected})
                    THEN 'Gedächtnisantwort — beim Öffnen erneut geprüft.' ELSE substr(m.content,1,600) END
                    FROM conversation_messages m WHERE m.conversation_id = c.id
                    ORDER BY kingfisher_time(m.created_at) DESC, m.rowid DESC LIMIT 1), '') AS preview
                FROM conversations c WHERE {match}"""
        order = " ORDER BY kingfisher_time(c.updated_at) DESC, c.id DESC"
        if filter_summary is not None and query:
            # Revalidate all matching source lineages before deriving counts or
            # cursors. Fetch bounded batches; do not materialize the archive.
            with self._lock:
                scan = self._conn.execute(projection + order, parameters)
            total, rows = 0, []
            while True:
                with self._lock:
                    batch = scan.fetchmany(100)
                if not batch:
                    break
                for row in batch:
                    if not filter_summary(self._summary(row), query):
                        continue
                    total += 1
                    time = _parse(row['updated_at']).timestamp()
                    follows = position is None or time < position[0] or (time == position[0] and row['id'] < position[2])
                    if follows and len(rows) < limit + 1:
                        rows.append(row)
        else:
            with self._lock:
                total = self._conn.execute(f"SELECT COUNT(*) FROM conversations c WHERE {match}", parameters).fetchone()[0]
                rows = self._conn.execute(projection + after + order + " LIMIT ?",
                    parameters + (list(position) if position else []) + [limit + 1]).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = None
        if more:
            last = rows[-1]
            value = {"v": 1, "q": fingerprint, "t": _parse(last["updated_at"]).timestamp(), "id": last["id"]}
            next_cursor = base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")
        return {"conversations": [self._summary(row) for row in rows], "next_cursor": next_cursor, "total": total}

    def messages(self, conversation_id: str) -> list[Message]:
        # Bei gleichem Zeitstempel (feste Uhr, Uhrsprung, gesetztes `at`) entscheidet die Einfügereihenfolge,
        # nicht die zufällige Kennung: sonst stünde die Antwort über ihrer Frage.
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM conversation_messages WHERE conversation_id = ? "
                "ORDER BY kingfisher_time(created_at), rowid",
                (conversation_id,),
            ).fetchall()
        return [self._message(row) for row in rows]

    def antwortzeiten(self, limit: int = 50) -> list[dict[str, Any]]:
        """Die gemessenen Zeiten der jüngsten Gedächtnisantworten (`working_answer.zeiten`), neueste zuerst.

        Nur die Zahlen und der Zeitpunkt, nie Text oder Frage. Kaputte Einträge werden übersprungen.
        """
        from .zeitmessung import gueltig
        with self._lock:
            rows = self._conn.execute(
                """SELECT created_at, json_extract(metadata, '$.context.working_answer.zeiten') AS zeiten
                   FROM conversation_messages
                   WHERE role = 'assistant' AND json_valid(metadata)
                     AND json_type(metadata, '$.context.working_answer.zeiten') = 'object'
                   ORDER BY kingfisher_time(created_at) DESC, rowid DESC
                   LIMIT ?""",
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        antworten = []
        for row in rows:
            try:
                zeiten = gueltig(json.loads(row["zeiten"]))
            except (TypeError, ValueError):
                zeiten = None
            if zeiten is not None:
                antworten.append({"zeitpunkt": _parse(row["created_at"]).astimezone().isoformat(), "zeiten": zeiten})
        return antworten

    def approval_message(self, approval_id: str) -> Message | None:
        """Locate the chat turn that requested a pending approval."""
        with self._lock:
            row = self._conn.execute(
                "SELECT m.* FROM conversation_messages AS m, "
                "json_each(m.metadata, '$.approvals') AS approval "
                "WHERE json_extract(approval.value, '$.id') = ? LIMIT 1",
                (approval_id,),
            ).fetchone()
        return self._message(row) if row else None

    def replace_source_lineage(self, message_id: str, lineage: list[dict[str, str]]) -> None:
        """Refresh a same-turn reply after explicit source metadata enrichment."""
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    "SELECT role, metadata FROM conversation_messages WHERE id=?", (message_id,)
                ).fetchone()
                if row is None or row["role"] != "assistant":
                    raise KeyError(message_id)
                metadata = json.loads(row["metadata"])
                metadata["conversation_source_lineage"] = lineage
                self._conn.execute("UPDATE conversation_messages SET metadata=? WHERE id=?",
                    (json.dumps(metadata, ensure_ascii=False), message_id))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        status: str = "complete",
        metadata: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> Message:
        if role not in {"user", "assistant"}:
            raise ValueError("Rolle muss user oder assistant sein")
        content = content.strip()
        if not content:
            raise ValueError("Eine Nachricht darf nicht leer sein")
        if (role == 'assistant' and isinstance(metadata, dict)
                and isinstance(metadata.get('context'), dict) and 'mappe_answer' in metadata['context']):
            # Die Mappe ist eine Ansicht: gespeichert wird nur, welche es war,
            # nie ein kopiertes Zitat. Beim Öffnen wird sie neu zusammengestellt.
            content = 'Stand der Dinge; wird beim Öffnen neu aus den Quellen zusammengestellt.'
            metadata = copy.deepcopy(metadata)
            metadata['context'].pop('source_links', None)
        elif (role == 'assistant' and isinstance(metadata, dict)
                and isinstance(metadata.get('context'), dict) and 'offene_punkte_answer' in metadata['context']):
            # Wie die Mappe: eine Ansicht der Akten, gespeichert wird nur die Frage, nie ein Zitat.
            content = 'Offene Punkte; wird beim Öffnen neu aus den Akten zusammengestellt.'
            metadata = copy.deepcopy(metadata)
            metadata['context'].pop('source_links', None)
        elif (role == 'assistant' and isinstance(metadata, dict)
                and isinstance(metadata.get('context'), dict) and 'kommendes_answer' in metadata['context']):
            # „Was brauche ich morgen?“: eine Ansicht von Kalender und Akten; gespeichert wird nur die Frage.
            content = 'Was ansteht; wird beim Öffnen neu aus Kalender, Akten und Aufgaben zusammengestellt.'
            metadata = copy.deepcopy(metadata)
            metadata['context'].pop('source_links', None)
        elif (role == 'assistant' and isinstance(metadata, dict)
                and isinstance(metadata.get('context'), dict)
                and ('source_answer' in metadata['context'] or 'working_answer' in metadata['context'])):
            from .source_answers import NEUTRAL as SOURCE_NEUTRAL
            from .working_memory_answers import NEUTRAL as WORKING_NEUTRAL
            NEUTRAL = WORKING_NEUTRAL if 'working_answer' in metadata['context'] else SOURCE_NEUTRAL
            content = NEUTRAL
            metadata = copy.deepcopy(metadata)
            metadata['context'].pop('source_links', None)
        timestamp = (at or now()).astimezone().isoformat()
        message_id = f"m-{uuid.uuid4().hex[:14]}"
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                conversation = self._conn.execute(
                    "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
                ).fetchone()
                if conversation is None:
                    raise KeyError(conversation_id)
                title = conversation["title"]
                stored_metadata = copy.deepcopy(metadata or {})
                if role == "user" and title == "Neues Gespräch":
                    title = content[:60].rstrip()
                    stored_metadata["generated_conversation_title"] = True
                self._conn.execute(
                    "INSERT INTO conversation_messages "
                    "(id, conversation_id, role, content, status, created_at, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        message_id,
                        conversation_id,
                        role,
                        content,
                        status,
                        timestamp,
                        json.dumps(stored_metadata, ensure_ascii=False),
                    ),
                )
                self._conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                    (title, timestamp, conversation_id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return next(message for message in self.messages(conversation_id) if message.id == message_id)

    def history(self, conversation_id: str) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in self.messages(conversation_id)
            if message.status == "complete"
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _conversation(row: sqlite3.Row) -> Conversation:
        return Conversation(
            id=row["id"],
            title=row["title"],
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
        )

    @staticmethod
    def _summary(row: sqlite3.Row) -> ConversationSummary:
        preview = " ".join(str(row["preview"] or "").split())
        if len(preview) > 180:
            preview = preview[:177].rstrip() + "…"
        return ConversationSummary(
            id=row["id"],
            title=row["title"],
            updated_at=_parse(row["updated_at"]),
            preview=preview,
            message_count=int(row["message_count"]),
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            status=row["status"],
            created_at=_parse(row["created_at"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )


__all__ = ["Conversation", "ConversationStore", "ConversationSummary", "DraftConflict", "Message"]
