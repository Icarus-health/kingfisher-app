"""Stabile Kennungen für Entitäten und ihre Quellverweise.

Die Registry ist absichtlich klein und deterministisch: Ein gleicher Name ist
kein Beweis für dieselbe Entität. Eine Zuordnung entsteht deshalb nur durch
eine ausdrücklich übergebene Kennung oder durch eine ausdrücklich verknüpfte
Quellenkennung.

``install_schema`` gehört in die Migration des aufrufenden Stores. Die
Funktion verändert weder die Transaktion noch ``PRAGMA user_version``. Die
Registry selbst übernimmt nur kurze, gesperrte Transaktionen für ihre
Schreib- und Lesevorgänge. Eine bereits laufende Transaktion des Aufrufers
wird abgelehnt, damit sie nicht versehentlich fremde Änderungen committet.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .migrations import IndexContract


class EntityError(Exception):
    """Eine Entität oder ein Quellenverweis ist ungültig."""


SUPPORTED_KINDS = frozenset({"person", "project", "topic", "organization", "place", "document"})
MAX_ID_LENGTH = 200
MAX_LABEL_LENGTH = 500
MAX_SOURCE_VALUE_LENGTH = 500

# Der Vertrag wird von der Knowledge-Migration verwendet. Die SQLite-
# Autoindexe der Primärschlüssel gehören nicht in ``SCHEMA_INDEXES``; sie sind
# über ``SCHEMA_PRIMARY_KEYS`` abgedeckt.
SCHEMA_TABLES = {
    "entity_registry": {"id", "kind", "label", "created_at"},
    "entity_aliases": {"source", "account", "native_id", "entity_id"},
}
SCHEMA_INDEXES = {
    "idx_entity_aliases_entity": IndexContract("entity_aliases", ("entity_id",)),
}
SCHEMA_PRIMARY_KEYS = {
    "entity_registry": {"id"},
    "entity_aliases": {"source", "account", "native_id"},
}
SCHEMA_TRIGGERS: dict[str, str] = {}


def install_schema(connection: sqlite3.Connection) -> None:
    """Installiert das Registry-Schema in der Transaktion des Aufrufers.

    Keine der Anweisungen commitet. Das erlaubt einer bestehenden Migration,
    Registry-Tabellen und ihren ``user_version``-Schritt atomar zu speichern.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_registry (
            id         TEXT PRIMARY KEY,
            kind       TEXT NOT NULL,
            label      TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS entity_aliases (
            source    TEXT NOT NULL,
            account   TEXT NOT NULL,
            native_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            PRIMARY KEY (source, account, native_id),
            FOREIGN KEY (entity_id) REFERENCES entity_registry(id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_entity_aliases_entity "
        "ON entity_aliases(entity_id)"
    )


def _text(value: Any, field: str, *, limit: int) -> str:
    if not isinstance(value, str):
        raise EntityError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise EntityError(f"{field} must not be empty")
    if len(cleaned) > limit:
        raise EntityError(f"{field} exceeds the maximum length of {limit}")
    if "\x00" in cleaned:
        raise EntityError(f"{field} contains a NUL character")
    return cleaned


def _kind(value: Any) -> str:
    kind = _text(value, "kind", limit=40)
    if kind not in SUPPORTED_KINDS:
        supported = ", ".join(sorted(SUPPORTED_KINDS))
        raise EntityError(f"unsupported entity kind {kind!r}; expected one of {supported}")
    return kind


def _label(value: Any) -> str:
    return _text(value, "label", limit=MAX_LABEL_LENGTH)


def _id(value: Any, field: str = "id") -> str:
    return _text(value, field, limit=MAX_ID_LENGTH)


def _source_value(value: Any, field: str) -> str:
    return _text(value, field, limit=MAX_SOURCE_VALUE_LENGTH)


def _source_key(
    source: str | tuple[str, str, str],
    account: str | None,
    native_id: str | None,
) -> tuple[str, str, str]:
    """Akzeptiert sowohl drei Argumente als auch einen Quellen-Tupel."""

    if account is None and native_id is None and isinstance(source, tuple):
        if len(source) != 3:
            raise EntityError("source tuple must contain source, account and native_id")
        source, account, native_id = source
    if account is None or native_id is None:
        raise EntityError("source, account and native_id are all required")
    return (
        _source_value(source, "source"),
        _source_value(account, "account"),
        _source_value(native_id, "native_id"),
    )


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat()


class EntityRegistry:
    """Verwaltet stabile IDs auf einer vom Aufrufer besessenen Verbindung."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        lock: threading.RLock | None = None,
    ) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("connection must be a sqlite3.Connection")
        self._connection = connection
        self._lock = lock or threading.RLock()

    @contextmanager
    def _transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        """Führt genau eine Registry-Transaktion unter dem Registry-Lock aus."""

        with self._lock:
            if self._connection.in_transaction:
                raise EntityError(
                    "An entity operation cannot run while the connection has "
                    "an active external transaction"
                )
            try:
                self._connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            except sqlite3.DatabaseError as exc:
                raise EntityError("Could not start the entity transaction") from exc
            try:
                yield self._connection
            except Exception:
                try:
                    self._connection.rollback()
                except sqlite3.DatabaseError:
                    pass
                raise
            else:
                try:
                    self._connection.commit()
                except sqlite3.DatabaseError as exc:
                    try:
                        self._connection.rollback()
                    except sqlite3.DatabaseError:
                        pass
                    raise EntityError("Could not commit the entity transaction") from exc

    @staticmethod
    def _entity(row: sqlite3.Row | tuple[Any, ...] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": row[0],
            "kind": row[1],
            "label": row[2],
            "created_at": row[3],
        }

    def create(self, kind: str, label: str, explicit_id: str | None = None) -> dict[str, Any]:
        """Erzeugt eine Entität und gibt ihre stabile Kennung zurück."""

        checked_kind = _kind(kind)
        checked_label = _label(label)
        if explicit_id is not None:
            checked_id = _id(explicit_id, "explicit_id")
            prefix = f"{checked_kind}:"
            if not checked_id.startswith(prefix) or len(checked_id) == len(prefix):
                raise EntityError(
                    f"explicit_id must use the {checked_kind!r} prefix ({prefix!r})"
                )
        else:
            checked_id = f"{checked_kind}:{uuid.uuid4().hex}"

        with self._transaction():
            if self._connection.execute(
                "SELECT 1 FROM entity_registry WHERE id = ?", (checked_id,)
            ).fetchone() is not None:
                raise EntityError(f"Entity ID already exists: {checked_id}")
            try:
                self._connection.execute(
                    "INSERT INTO entity_registry(id, kind, label, created_at) VALUES (?, ?, ?, ?)",
                    (checked_id, checked_kind, checked_label, _created_at()),
                )
            except sqlite3.IntegrityError as exc:
                # The explicit-ID case is handled above. This branch mostly
                # protects the random-ID path if an astronomically unlikely
                # collision occurs between the check and insert.
                raise EntityError(f"Entity ID already exists: {checked_id}") from exc
            row = self._connection.execute(
                "SELECT id, kind, label, created_at FROM entity_registry WHERE id = ?",
                (checked_id,),
            ).fetchone()
            result = self._entity(row)
        if result is None:  # pragma: no cover - INSERT above guarantees this
            raise EntityError(f"Entity was not created: {checked_id}")
        return result

    def get(self, entity_id: str) -> dict[str, Any] | None:
        """Gibt eine Entität zurück; unbekannte IDs ergeben ``None``."""

        checked_id = _id(entity_id)
        with self._transaction(immediate=False):
            row = self._connection.execute(
                "SELECT id, kind, label, created_at FROM entity_registry WHERE id = ?",
                (checked_id,),
            ).fetchone()
            return self._entity(row)

    def list(self, kind: str | None = None) -> list[dict[str, Any]]:
        """Listet Entitäten deterministisch, ohne Namen zusammenzulegen."""

        checked_kind = _kind(kind) if kind is not None else None
        with self._transaction(immediate=False):
            if checked_kind is None:
                rows = self._connection.execute(
                    "SELECT id, kind, label, created_at FROM entity_registry "
                    "ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT id, kind, label, created_at FROM entity_registry "
                    "WHERE kind = ? ORDER BY created_at, id",
                    (checked_kind,),
                ).fetchall()
            return [self._entity(row) for row in rows if row is not None]

    def search(self, label: str, kind: str | None = None) -> list[dict[str, Any]]:
        """Sucht den exakten Namen und liefert alle gleichnamigen Kandidaten."""

        checked_label = _label(label)
        checked_kind = _kind(kind) if kind is not None else None
        wanted = checked_label.casefold()
        with self._transaction(immediate=False):
            if checked_kind is None:
                rows = self._connection.execute(
                    "SELECT id, kind, label, created_at FROM entity_registry "
                    "ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT id, kind, label, created_at FROM entity_registry "
                    "WHERE kind = ? ORDER BY created_at, id",
                    (checked_kind,),
                ).fetchall()
            return [
                entity
                for row in rows
                if (entity := self._entity(row)) is not None
                and entity["label"].casefold() == wanted
            ]

    # ``list`` and ``search`` are the public API; these aliases make the
    # intent explicit for callers that prefer descriptive names.
    list_entities = list
    search_exact = search

    def sources(self, entity_id: str) -> list[dict[str, str]]:
        """Nur die ausdrücklich mit dieser Identität verknüpften Quellkennungen."""
        checked_id = _id(entity_id)
        with self._transaction(immediate=False):
            rows = self._connection.execute(
                "SELECT source, account, native_id FROM entity_aliases WHERE entity_id = ? "
                "ORDER BY source, account, native_id", (checked_id,),
            ).fetchall()
            return [{"source": row[0], "account": row[1], "native_id": row[2]} for row in rows]

    def rename(self, entity_id: str, label: str) -> dict[str, Any]:
        """Ändert nur das Label; Kennung, Art und Erstellungszeit bleiben gleich."""

        checked_id = _id(entity_id)
        checked_label = _label(label)
        with self._transaction():
            cursor = self._connection.execute(
                "UPDATE entity_registry SET label = ? WHERE id = ?",
                (checked_label, checked_id),
            )
            if cursor.rowcount != 1:
                raise EntityError(f"Unknown entity ID: {checked_id}")
            row = self._connection.execute(
                "SELECT id, kind, label, created_at FROM entity_registry WHERE id = ?",
                (checked_id,),
            ).fetchone()
            result = self._entity(row)
        if result is None:  # pragma: no cover - UPDATE above guarantees this
            raise EntityError(f"Unknown entity ID: {checked_id}")
        return result

    def link_source(
        self,
        entity_id: str,
        source: str,
        account: str,
        native_id: str,
    ) -> dict[str, Any]:
        """Verknüpft eine Quellenkennung, ohne eine bestehende Bindung zu ersetzen."""

        checked_entity_id = _id(entity_id, "entity_id")
        checked_source = _source_value(source, "source")
        checked_account = _source_value(account, "account")
        checked_native_id = _source_value(native_id, "native_id")
        key = (checked_source, checked_account, checked_native_id)

        with self._transaction():
            if self._connection.execute(
                "SELECT 1 FROM entity_registry WHERE id = ?", (checked_entity_id,)
            ).fetchone() is None:
                raise EntityError(f"Unknown entity ID: {checked_entity_id}")
            existing = self._connection.execute(
                "SELECT entity_id FROM entity_aliases "
                "WHERE source = ? AND account = ? AND native_id = ?",
                key,
            ).fetchone()
            if existing is not None:
                if existing[0] != checked_entity_id:
                    raise EntityError(
                        "Source identity is already linked to another entity: "
                        f"{checked_source}/{checked_account}/{checked_native_id}"
                    )
                row = self._connection.execute(
                    "SELECT id, kind, label, created_at FROM entity_registry WHERE id = ?",
                    (checked_entity_id,),
                ).fetchone()
                result = self._entity(row)
                if result is None:  # pragma: no cover - FK prevents this state
                    raise EntityError(f"Unknown entity ID: {checked_entity_id}")
                return result
            try:
                self._connection.execute(
                    "INSERT INTO entity_aliases(source, account, native_id, entity_id) "
                    "VALUES (?, ?, ?, ?)",
                    (*key, checked_entity_id),
                )
            except sqlite3.IntegrityError as exc:
                raise EntityError("Source identity is already linked") from exc
            row = self._connection.execute(
                "SELECT id, kind, label, created_at FROM entity_registry WHERE id = ?",
                (checked_entity_id,),
            ).fetchone()
            result = self._entity(row)
        if result is None:  # pragma: no cover - entity checked above
            raise EntityError(f"Unknown entity ID: {checked_entity_id}")
        return result

    def resolve_source(
        self,
        source: str | tuple[str, str, str],
        account: str | None = None,
        native_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Löst eine vollständige Quellenkennung auf eine Entität auf.

        Für Adapter, die den Schlüssel bereits als Datensatz führen, ist auch
        ``resolve_source((source, account, native_id))`` erlaubt.
        """

        key = _source_key(source, account, native_id)
        with self._transaction(immediate=False):
            row = self._connection.execute(
                "SELECT e.id, e.kind, e.label, e.created_at "
                "FROM entity_aliases AS a JOIN entity_registry AS e ON e.id = a.entity_id "
                "WHERE a.source = ? AND a.account = ? AND a.native_id = ?",
                key,
            ).fetchone()
            return self._entity(row)

    def unlink_source(
        self,
        source: str | tuple[str, str, str],
        account: str | None = None,
        native_id: str | None = None,
        *,
        entity_id: str | None = None,
    ) -> bool:
        """Entfernt nur die Quellenbindung; die Entität bleibt bestehen."""

        key = _source_key(source, account, native_id)
        clause = " AND entity_id = ?" if entity_id is not None else ""
        params = (*key, _id(entity_id)) if entity_id is not None else key
        with self._transaction():
            cursor = self._connection.execute(
                "DELETE FROM entity_aliases WHERE source = ? AND account = ? AND native_id = ?" + clause,
                params,
            )
            return cursor.rowcount == 1
