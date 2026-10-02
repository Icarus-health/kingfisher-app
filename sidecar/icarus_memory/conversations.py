"""Persistente lokale Gespräche für die Kingfisher-Oberfläche."""

from __future__ import annotations

import json
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


_MIGRATIONS = (Migration(1, "initial_conversations", _migrate_v1, _verify_v1),)


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


__all__ = ["Conversation", "ConversationStore", "ConversationSummary", "Message"]
