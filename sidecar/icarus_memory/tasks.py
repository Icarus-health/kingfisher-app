"""Aufgaben.

Bewusst eine eigene Ablage neben dem Selbstmodell, obwohl es verlockend wäre,
sie als Aussagen vom Typ `goal` zu führen.

Der Grund: Aussagen im Selbstmodell beschreiben, **wie jemand ist**. Aufgaben
beschreiben, **was zu tun ist**. Eine erledigte Aufgabe ist nicht „ersetzt“ oder
„widerrufen“ — sie ist fertig, und das ist ein anderer Lebenszyklus. Sie in
dasselbe Modell zu pressen würde beide verwässern.

Was übernommen wird, ist das Prinzip: Auch eine Aufgabe trägt ihre Herkunft.
Wenn in drei Monaten „Rechnung an Müller schicken“ auftaucht, muss beantwortbar
sein, woher das kam — aus einer Mail, aus einem Gespräch, oder hat das System
es sich ausgedacht.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from .datumstext import iso_lesen as _parse
from .migrations import (
    IndexContract,
    Migration,
    run_migrations,
    table_columns,
    validate_legacy_or_empty,
    verify_schema,
)
from .model import Provenance, SourceType, ensure_aware, now


class TaskChangedError(ValueError):
    """The displayed reminder no longer matches the stored task."""


class TaskStatus(str, Enum):
    OPEN = "open"
    DONE = "done"
    DROPPED = "dropped"
    """Fallengelassen — nicht erledigt, aber auch nicht mehr offen.

    Der Unterschied zu `done` ist für ein System, das Jahre läuft, wichtig:
    Sonst sieht es später aus, als wäre alles geschafft worden.
    """


@dataclass
class Task:
    id: str
    title: str
    provenance: Provenance
    created_at: datetime
    status: TaskStatus = TaskStatus.OPEN
    due: datetime | None = None
    notes: str | None = None
    done_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    wartet_auf: str | None = None
    """Bei wem die Aufgabe gerade liegt.

    Ein Stabschef unterscheidet zwei Dinge, die eine flache Liste in einen Topf
    wirft: was **du** noch tun musst, und worauf du **wartest**. Beides ist
    offen, aber nur das erste ist Arbeit für dich. Solange hier ein Name steht,
    liegt die Aufgabe bei jemand anderem.
    """

    wartet_seit: datetime | None = None
    """Seit wann sie dort liegt — die Grundlage jedes Nachfassens."""

    project_id: str | None = None
    """Zu welchem Projekt die Aufgabe gehört.

    Optional, und das ist Absicht: Nicht alles im Leben ist ein Projekt, und
    ein Pflichtfeld hier würde dazu führen, dass ein Sammelprojekt „Sonstiges“
    entsteht — das wäre dieselbe flache Liste mit mehr Schritten.
    """

    remind_at: datetime | None = None
    """Wiedervorlage unabhängig von der Fälligkeit und vom Wartestatus."""

    def is_overdue(self, at: datetime | None = None) -> bool:
        """Überfällig ist nur, was bei **dir** liegt.

        Was jemand anderes schuldet, kann sein Datum reißen, ohne dass es
        deine Versäumnisliste verlängert. Sonst wächst dort ein roter Berg
        aus Dingen, an denen du nichts ändern kannst — und die Liste, die
        eigentlich handlungsfähig machen soll, wird zur Anklage.
        """
        return (
            self.status is TaskStatus.OPEN
            and self.wartet_auf is None
            and self.due is not None
            and (at or now()) > self.due
        )

    def wartet_tage(self, at: datetime | None = None) -> int | None:
        """Wie viele Tage die Aufgabe schon bei jemandem liegt."""
        if self.wartet_seit is None:
            return None
        return max(0, ((at or now()) - self.wartet_seit).days)

    def to_dict(self) -> dict[str, Any]:
        def iso(v: datetime | None) -> str | None:
            return v.astimezone().isoformat() if v else None

        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "provenance": self.provenance.to_dict(),
            "created_at": iso(self.created_at),
            "due": iso(self.due),
            "remind_at": iso(self.remind_at),
            "notes": self.notes,
            "done_at": iso(self.done_at),
            "tags": list(self.tags),
            "project_id": self.project_id,
            "wartet_auf": self.wartet_auf,
            "wartet_seit": iso(self.wartet_seit),
            "wartet_tage": self.wartet_tage(),
            "overdue": self.is_overdue(),
        }


_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL,
    due        TEXT,
    title      TEXT NOT NULL,
    document   TEXT NOT NULL,
    project_id TEXT
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)",
)
_INDEX_CONTRACTS = {
    "idx_tasks_status": IndexContract("tasks", ("status",)),
    "idx_tasks_due": IndexContract("tasks", ("due",)),
    "idx_tasks_project": IndexContract("tasks", ("project_id",)),
}
_LEGACY_SCHEMA = {
    "tasks": {"id", "created_at", "status", "due", "title", "document"}
}
_CURRENT_SCHEMA = {
    "tasks": {
        "id",
        "created_at",
        "status",
        "due",
        "title",
        "document",
        "project_id",
    }
}
_PRIMARY_KEYS = {"tasks": {"id"}}


def _migrate_v1(connection: sqlite3.Connection) -> None:
    validate_legacy_or_empty(
        connection,
        store="tasks",
        path=connection.execute("PRAGMA database_list").fetchone()[2],
        expected_tables=_LEGACY_SCHEMA,
        allowed_column_sets={
            "tasks": (_LEGACY_SCHEMA["tasks"], _CURRENT_SCHEMA["tasks"])
        },
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )
    connection.execute(_CREATE_TASKS)
    # Bekannter Legacy-Bestand aus der Zeit vor der Projektebene. Anders als
    # bisher wird nur die erwartete fehlende Spalte behandelt; andere
    # OperationalErrors werden nicht verschluckt.
    if "project_id" not in table_columns(connection, "tasks"):
        connection.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT")
    for statement in _INDEXES:
        connection.execute(statement)


def _verify_v1(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_CURRENT_SCHEMA,
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )


# Deliberately only prerequisite state history, not a Matter/Obligation model.
# No copied title, notes, source quote or claimed authenticated actor.
_HISTORY_FIELDS = ("id", "created_at", "status", "due", "remind_at", "done_at", "project_id",
                   "wartet_auf", "wartet_seit")
_HISTORY_SCHEMA = {"sequence", "task_id", "kind", "recorded_at", "business_at",
                   "before_state", "after_state"}
_HISTORY_INDEX = IndexContract("task_events", ("task_id", "sequence"))
_HISTORY_TRIGGERS = {
    f"task_events_no_{action.lower()}":
        f"CREATE TRIGGER task_events_no_{action.lower()} BEFORE {action} ON task_events "
        "BEGIN SELECT RAISE(ABORT, 'task history is append-only'); END"
    for action in ("UPDATE", "DELETE")
}
# REPLACE implicitly deletes conflicting rows and can skip DELETE triggers when
# recursive_triggers is off (SQLite's default). Guard before conflict handling.
_HISTORY_TRIGGERS["task_events_no_replace"] = (
    "CREATE TRIGGER task_events_no_replace BEFORE INSERT ON task_events "
    "WHEN EXISTS (SELECT 1 FROM task_events WHERE sequence = NEW.sequence) "
    "BEGIN SELECT RAISE(ABORT, 'task history is append-only'); END"
)


def _state(document: dict[str, Any]) -> dict[str, Any]:
    return {key: document.get(key) for key in _HISTORY_FIELDS}


def _migrate_v2(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE task_events (
        sequence INTEGER PRIMARY KEY,
        task_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        business_at TEXT,
        before_state TEXT,
        after_state TEXT NOT NULL
    )""")
    connection.execute("CREATE INDEX idx_task_events_task_sequence ON task_events(task_id, sequence)")
    for statement in _HISTORY_TRIGGERS.values():
        connection.execute(statement)
    # Observation at migration time, explicitly not reconstructed past actions.
    recorded_at = now().isoformat()
    for task_id, document in connection.execute("SELECT id, document FROM tasks ORDER BY id"):
        connection.execute(
            "INSERT INTO task_events (task_id, kind, recorded_at, business_at, before_state, after_state) "
            "VALUES (?, 'preexisting_snapshot', ?, NULL, NULL, ?)",
            (task_id, recorded_at, json.dumps(_state(json.loads(document)), ensure_ascii=False)),
        )


def _verify_v2(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_CURRENT_SCHEMA, "task_events": _HISTORY_SCHEMA},
        expected_indexes={**_INDEX_CONTRACTS, "idx_task_events_task_sequence": _HISTORY_INDEX},
        expected_triggers=_HISTORY_TRIGGERS,
        expected_primary_keys={**_PRIMARY_KEYS, "task_events": {"sequence"}},
    )


_MIGRATIONS = (
    Migration(1, "initial_explicit_version", _migrate_v1, _verify_v1),
    Migration(2, "append_only_task_history", _migrate_v2, _verify_v2),
)


_UNSET = object()


class TaskStore:
    """Aufgaben in einer lokalen Datei, neben dem Selbstmodell."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Wie SqliteBackend: FastAPI bedient aus einem Threadpool.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        try:
            with self._lock:
                run_migrations(
                    self._conn,
                    store="tasks",
                    path=self._path,
                    migrations=_MIGRATIONS,
                )
        except Exception:
            self._conn.close()
            raise

    # -- Schreiben ---------------------------------------------------------

    def add(
        self,
        title: str,
        provenance: Provenance,
        *,
        due: datetime | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        project_id: str | None = None,
        at: datetime | None = None,
    ) -> Task:
        task = Task(
            id=f"t-{uuid.uuid4().hex[:12]}",
            title=title,
            provenance=provenance,
            created_at=ensure_aware(at) or now(),
            # Über HTTP kommen Fälligkeiten ohne Zeitzone herein.
            due=ensure_aware(due),
            notes=notes,
            tags=list(tags or []),
            project_id=project_id,
        )
        with self._transaction():
            self._write(task)
            self._append_event(task, "created", None, at)
        return task

    def from_suggestion(self, proposal_id: str, title: str, provenance: Provenance, *, due: datetime | None = None, project_id: str | None = None, waiting_for: str | None = None) -> Task:
        """Eine ausdrückliche Übernahme bleibt auch nach einem Abbruch einmalig."""
        if not proposal_id or not title.strip():
            raise ValueError("Vorschlag und Aufgabentitel dürfen nicht leer sein.")
        at = now()
        task = Task(
            id=f"t-suggestion-{proposal_id}", title=title.strip(), provenance=provenance,
            created_at=at, due=ensure_aware(due), project_id=project_id,
            wartet_auf=waiting_for, wartet_seit=at if waiting_for else None,
        )
        with self._transaction():
            row = self._conn.execute("SELECT document FROM tasks WHERE id = ?", (task.id,)).fetchone()
            if row:
                return self._from_row(row)
            self._write(task)
            self._append_event(task, "from_suggestion", None, None)
        return task

    def complete(self, task_id: str, at: datetime | None = None) -> Task:
        def change(task: Task) -> None:
            if task.status is not TaskStatus.DONE:
                task.status = TaskStatus.DONE
                task.done_at = ensure_aware(at) or now()
        return self._change(task_id, "completed", change, at)

    def drop(self, task_id: str, at: datetime | None = None) -> Task:
        def change(task: Task) -> None:
            if task.status is not TaskStatus.DROPPED:
                task.status = TaskStatus.DROPPED
                task.done_at = ensure_aware(at) or now()
        return self._change(task_id, "dropped", change, at)

    def warten_auf(self, task_id: str, name: str, at: datetime | None = None) -> Task:
        """Repeated assignment to the same person retains the original wait date."""
        name = name.strip()
        if not name:
            raise ValueError("Ohne Namen ist nicht sagbar, bei wem es liegt.")
        def change(task: Task) -> None:
            if task.wartet_auf != name:
                task.wartet_auf = name
                task.wartet_seit = ensure_aware(at) or now()
        return self._change(task_id, "waiting_for", change, at)

    def zurueckholen(self, task_id: str) -> Task:
        def change(task: Task) -> None:
            task.wartet_auf = None
            task.wartet_seit = None
        return self._change(task_id, "returned", change)

    def reopen(self, task_id: str) -> Task:
        def change(task: Task) -> None:
            task.status = TaskStatus.OPEN
            task.done_at = None
        return self._change(task_id, "reopened", change)

    def assign_project(self, task_id: str, project_id: str | None) -> Task:
        """Changes only project assignment; concurrent state changes are retained."""
        return self._change(task_id, "project_assigned",
                            lambda task: setattr(task, "project_id", project_id))

    def edit(self, task_id: str, *, title: str | None | object = _UNSET,
             due: datetime | None | object = _UNSET,
             remind_at: datetime | None | object = _UNSET,
             expected_remind_at: datetime | None | object = _UNSET,
             notes: str | None | object = _UNSET,
             at: datetime | None = None) -> Task:
        """Edit user-maintained details without changing task identity/state.

        An omitted value is retained; explicit ``None`` clears optional dates/notes.
        History records that an edit occurred but deliberately does not copy
        task titles or notes into the append-only event log.
        """
        if title is not _UNSET and (not isinstance(title, str) or not title.strip()):
            raise ValueError("Der Aufgabentitel darf nicht leer sein.")
        if not any(value is not _UNSET for value in (title, due, remind_at, notes)):
            raise ValueError("Bitte mindestens ein Aufgabenfeld ändern.")
        with self._transaction():
            row = self._conn.execute("SELECT document FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unbekannte Aufgabe: {task_id}")
            task = self._from_row(row)
            if expected_remind_at is not _UNSET and task.remind_at != ensure_aware(expected_remind_at):
                raise TaskChangedError('Die Wiedervorlage wurde inzwischen geändert. Bitte neu laden.')
            if remind_at is not _UNSET and remind_at is not None and task.status is not TaskStatus.OPEN:
                raise TaskChangedError('Die Aufgabe ist nicht mehr offen. Bitte ihren aktuellen Stand prüfen.')
            before = _state(task.to_dict())
            old_values = (task.title, task.due, task.remind_at, task.notes)
            if title is not _UNSET:
                task.title = title.strip()
            if due is not _UNSET:
                task.due = ensure_aware(due)
            if remind_at is not _UNSET:
                task.remind_at = ensure_aware(remind_at)
            if notes is not _UNSET:
                task.notes = notes
            if (task.title, task.due, task.remind_at, task.notes) != old_values:
                self._write(task)
                self._append_event(task, "edited", before, at)
            return task

    # -- Lesen -------------------------------------------------------------

    def history(self, task_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Newest recorded events first, bounded to 200; [] for an unknown task.

        ``business_at`` is caller-supplied, possibly unknown. ``recorded_at`` is
        the actual recording time. Neither an operation nor task provenance
        authenticates a user, so actor_id stays unknown. Preexisting snapshots
        mark a history gap rather than asserting a past creation/decision.
        State snapshots omit source content; original provenance is on Task.
        Retained state (including waiting names) is private data too and must
        participate in any future deletion/retention mechanism.
        """
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("history limit must be between 1 and 200")
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY sequence DESC LIMIT ?",
                (task_id, limit),
            ).fetchall()
        return [{"sequence": row["sequence"], "task_id": row["task_id"],
                 "kind": row["kind"], "recorded_at": row["recorded_at"],
                 "business_at": row["business_at"], "actor_id": None,
                 "before": json.loads(row["before_state"]) if row["before_state"] else None,
                 "after": json.loads(row["after_state"])} for row in rows]

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def reminders_due(self, at: datetime | None = None, limit: int = 100) -> list[Task]:
        """Open tasks whose reminder time has arrived, oldest reminder first.

        This intentionally scans every open task rather than reusing the
        user-facing 200-task list, so an older/undated task cannot hide a
        reminder. Reminder delivery is left to the caller; reading this list
        never changes task or deadline state.
        """
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("reminder limit must be between 1 and 200")
        moment = ensure_aware(at) or now()
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM tasks WHERE status = ? "
                "AND julianday(json_extract(document,'$.remind_at')) <= julianday(?) "
                "ORDER BY julianday(json_extract(document,'$.remind_at')), created_at, id LIMIT ?",
                (TaskStatus.OPEN.value, moment.isoformat(), limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def open_tasks(self, limit: int | None = 200) -> list[Task]:
        """Offene Aufgaben, überfällige und bald fällige zuerst.

        Aufgaben ohne Fälligkeit landen hinten — sonst verdrängen sie das,
        was tatsächlich ansteht.
        Für vollständige fachliche Auswertungen hebt None die Listengrenze auf.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM tasks WHERE status = ? "
                "ORDER BY due IS NULL, due ASC, created_at ASC LIMIT ?",
                (TaskStatus.OPEN.value, -1 if limit is None else limit),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def due_within(self, days: int = 7, at: datetime | None = None) -> list[Task]:
        at = at or now()
        limit = at + timedelta(days=days)
        return [
            t for t in self.open_tasks()
            if t.due is not None and t.due <= limit
        ]

    def wartend(self, at: datetime | None = None) -> list[Task]:
        """Alles, was gerade bei anderen liegt — am längsten Wartendes zuerst."""
        offen = [t for t in self.open_tasks() if t.wartet_auf is not None]
        return sorted(offen, key=lambda t: t.wartet_seit or t.created_at)

    def by_project(self, project_id: str, include_closed: bool = False) -> list[Task]:
        """Alle Aufgaben eines Projekts.

        Die zentrale Abfrage der Projektansicht: „Was steht bei X noch an?“
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM tasks WHERE project_id = ? "
                "ORDER BY due IS NULL, due ASC, created_at ASC",
                (project_id,),
            ).fetchall()
        items = [self._from_row(r) for r in rows]
        if not include_closed:
            items = [t for t in items if t.status is TaskStatus.OPEN]
        return items

    def all_tasks(self, limit: int = 500) -> list[Task]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- Intern ------------------------------------------------------------

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        # Acquire the SQLite write lock BEFORE reading, across Store instances.
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

    def _change(self, task_id: str, kind: str, mutate: Callable[[Task], None],
                at: datetime | None = None) -> Task:
        with self._transaction():
            row = self._conn.execute("SELECT document FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unbekannte Aufgabe: {task_id}")
            task = self._from_row(row)
            before = _state(task.to_dict())
            mutate(task)
            if _state(task.to_dict()) != before:
                self._write(task)
                self._append_event(task, kind, before, at)
            return task

    def _append_event(self, task: Task, kind: str, before: dict[str, Any] | None,
                      at: datetime | None) -> None:
        business_at = ensure_aware(at)
        self._conn.execute(
            "INSERT INTO task_events (task_id, kind, recorded_at, business_at, before_state, after_state) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task.id, kind, now().isoformat(), business_at.isoformat() if business_at else None,
             json.dumps(before, ensure_ascii=False) if before is not None else None,
             json.dumps(_state(task.to_dict()), ensure_ascii=False)),
        )

    def _write(self, task: Task) -> None:
        """Write only inside the same transaction as the matching event."""
        d = task.to_dict()
        self._conn.execute(
            "INSERT INTO tasks (id, created_at, status, due, title, project_id, document) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
            "due=excluded.due, title=excluded.title, "
            "project_id=excluded.project_id, document=excluded.document",
            (d["id"], d["created_at"], d["status"], d["due"], d["title"],
             d["project_id"], json.dumps(d, ensure_ascii=False)),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Task:
        d = json.loads(row["document"])
        p = d["provenance"]
        return Task(
            id=d["id"],
            title=d["title"],
            provenance=Provenance(
                source_type=SourceType(p["source_type"]),
                source_ref=p.get("source_ref"),
                captured_at=_parse(p.get("captured_at")),
                extracted_by=p.get("extracted_by"),
                verbatim=p.get("verbatim"),
            ),
            created_at=_parse(d["created_at"]),  # type: ignore[arg-type]
            status=TaskStatus(d["status"]),
            due=_parse(d.get("due")),
            remind_at=_parse(d.get("remind_at")),
            notes=d.get("notes"),
            done_at=_parse(d.get("done_at")),
            tags=list(d.get("tags", [])),
            project_id=d.get("project_id"),
            wartet_auf=d.get("wartet_auf"),
            wartet_seit=_parse(d.get("wartet_seit")),
        )


__all__ = ["Task", "TaskStatus", "TaskStore"]
