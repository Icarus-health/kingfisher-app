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
from datetime import datetime, timedelta, timezone
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


class TaskRequestConflict(ValueError):
    """A saved request may not be reused for a different task payload."""


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

    goal_id: str | None = None
    """Welches ausdrücklich festgehaltene Ziel diese Aufgabe voranbringt.

    Die Beziehung ist dauerhaft: Ein späterer Abschluss des Ziels ändert
    nicht, warum die Aufgabe angelegt wurde.
    """

    remind_at: datetime | None = None
    """Wiedervorlage unabhängig von der Fälligkeit und vom Wartestatus."""

    erledigt_grund: dict[str, Any] | None = None
    """Warum die Post diese Aufgabe erledigt hat (`aufgaben_post.py`): Satz, Mail, Zeitpunkt, der vorige Zustand.

    Ein Ablagevorgang, kein Fakt im Bestand: sichtbar mit Grund, mit einem Klick umkehrbar (`post_rueckgaengig`).
    Leer, wenn der Mensch selbst abgehakt hat oder die Änderung zurückgenommen wurde.
    """

    geaendert_grund: dict[str, Any] | None = None
    """Warum die Post das Warten aufgelöst hat („Anna hat am … geantwortet“): wie `erledigt_grund`, nur für
    „wieder bei dir“. Die Aufgabe ist dann offen, nicht erledigt."""

    person: dict[str, str] | None = None
    """Wer zu dieser Aufgabe gehört: wer darum gebeten hat oder wem zugesagt wurde (`{"adresse", "name"}`).

    Ein Mensch ist zuerst seine Adresse (`personen.py`); die Adresse führt zur Akte. Kein Fakt über den Menschen,
    nur die Ablage der Aufgabe bei ihm (`aufgaben_von_selbst.py`)."""

    angelegt: dict[str, Any] | None = None
    """Wie die Aufgabe entstand, wenn nicht von Hand: `art` `automatisch` (Kingfisher hat eine eindeutige Bitte oder
    Zusage aus einer neuen Mail selbst angelegt, mit Satz, Mail und Grundsatz) oder `alle_uebernehmen` (mit einem
    Klick zusammen mit anderen Vorschlägen übernommen, mit `gruppe`). Beides lässt sich zurücknehmen
    (`aufgaben_von_selbst.py`)."""

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
            "goal_id": self.goal_id,
            "wartet_auf": self.wartet_auf,
            "wartet_seit": iso(self.wartet_seit),
            "wartet_tage": self.wartet_tage(),
            "overdue": self.is_overdue(),
            "erledigt_grund": dict(self.erledigt_grund) if self.erledigt_grund else None,
            "geaendert_grund": dict(self.geaendert_grund) if self.geaendert_grund else None,
            "person": dict(self.person) if self.person else None,
            "angelegt": dict(self.angelegt) if self.angelegt else None,
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
_HISTORY_FIELDS = ("id", "created_at", "status", "due", "remind_at", "done_at", "project_id", "goal_id",
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


def _migrate_v3(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE task_requests (
        request_id TEXT PRIMARY KEY,
        payload_digest TEXT NOT NULL,
        task_id TEXT NOT NULL
    )""")


def _verify_v3(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_CURRENT_SCHEMA, "task_events": _HISTORY_SCHEMA,
                         "task_requests": {"request_id", "payload_digest", "task_id"}},
        expected_indexes={**_INDEX_CONTRACTS, "idx_task_events_task_sequence": _HISTORY_INDEX},
        expected_triggers=_HISTORY_TRIGGERS,
        expected_primary_keys={**_PRIMARY_KEYS, "task_events": {"sequence"}, "task_requests": {"request_id"}},
    )


# Aufgaben folgen der Post (`aufgaben_post.py`): die Merkliste der geprüften Mails, die vom Nutzer getrennten Paare
# (Aufgabe, Mail) und der Stand des Durchlaufs (Zeilennummer der Episoden). Nur Kennungen, kein Text.
_POST_TABLES = {
    "aufgaben_post_mails": {"episode_id", "digest", "verarbeitet_am"},
    "aufgaben_post_getrennt": {"task_id", "episode_id", "getrennt_am"},
    "aufgaben_post_stand": {"id", "zeile"},
}
_POST_KEYS = {"aufgaben_post_mails": {"episode_id"}, "aufgaben_post_getrennt": {"task_id", "episode_id"},
              "aufgaben_post_stand": {"id"}}


def _migrate_v4(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE aufgaben_post_mails (
        episode_id TEXT PRIMARY KEY,
        digest TEXT NOT NULL,
        verarbeitet_am TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE aufgaben_post_getrennt (
        task_id TEXT NOT NULL,
        episode_id TEXT NOT NULL,
        getrennt_am TEXT NOT NULL,
        PRIMARY KEY (task_id, episode_id)
    )""")
    connection.execute("CREATE TABLE aufgaben_post_stand (id INTEGER PRIMARY KEY CHECK(id = 1), zeile INTEGER NOT NULL)")


def _verify_v4(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_CURRENT_SCHEMA, "task_events": _HISTORY_SCHEMA,
                         "task_requests": {"request_id", "payload_digest", "task_id"}, **_POST_TABLES},
        expected_indexes={**_INDEX_CONTRACTS, "idx_task_events_task_sequence": _HISTORY_INDEX},
        expected_triggers=_HISTORY_TRIGGERS,
        expected_primary_keys={**_PRIMARY_KEYS, "task_events": {"sequence"}, "task_requests": {"request_id"},
                               **_POST_KEYS},
    )


# Aufgaben von selbst (`aufgaben_von_selbst.py`, 26.10.2026): welche Vorschläge der Durchlauf schon geprüft hat (mit
# dem Ergebnis als Kürzel), was der Nutzer zurückgenommen hat (damit es nicht wiederkommt; mit dem Dokument der Aufgabe,
# damit „Rückgängig“ des Zurücknehmens sie unverändert wiederherstellt) und der Schalter „Aufgaben aus Mails selbst
# anlegen“ (keine Zeile: an).
_AUTO_TABLES = {
    "aufgaben_auto_geprueft": {"proposal_id", "ergebnis", "geprueft_am"},
    "aufgaben_auto_zurueck": {"proposal_id", "episode_id", "titel_schluessel", "zitat_schluessel", "task_id",
                              "dokument", "zurueck_am"},
    "aufgaben_auto_einstellung": {"id", "an"},
}
_AUTO_KEYS = {"aufgaben_auto_geprueft": {"proposal_id"}, "aufgaben_auto_zurueck": {"proposal_id"},
              "aufgaben_auto_einstellung": {"id"}}
_AUTO_INDEX = {"idx_aufgaben_auto_zurueck_quelle": IndexContract("aufgaben_auto_zurueck", ("episode_id",))}


def _migrate_v5(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE aufgaben_auto_geprueft (
        proposal_id TEXT PRIMARY KEY,
        ergebnis TEXT NOT NULL,
        geprueft_am TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE aufgaben_auto_zurueck (
        proposal_id TEXT PRIMARY KEY,
        episode_id TEXT NOT NULL,
        titel_schluessel TEXT NOT NULL,
        zitat_schluessel TEXT NOT NULL,
        task_id TEXT NOT NULL,
        dokument TEXT NOT NULL,
        zurueck_am TEXT NOT NULL
    )""")
    connection.execute("CREATE INDEX idx_aufgaben_auto_zurueck_quelle ON aufgaben_auto_zurueck(episode_id)")
    connection.execute("CREATE TABLE aufgaben_auto_einstellung (id INTEGER PRIMARY KEY CHECK(id = 1), an INTEGER NOT NULL)")


def _verify_v5(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_CURRENT_SCHEMA, "task_events": _HISTORY_SCHEMA,
                         "task_requests": {"request_id", "payload_digest", "task_id"}, **_POST_TABLES, **_AUTO_TABLES},
        expected_indexes={**_INDEX_CONTRACTS, "idx_task_events_task_sequence": _HISTORY_INDEX, **_AUTO_INDEX},
        expected_triggers=_HISTORY_TRIGGERS,
        expected_primary_keys={**_PRIMARY_KEYS, "task_events": {"sequence"}, "task_requests": {"request_id"},
                               **_POST_KEYS, **_AUTO_KEYS},
    )


_MIGRATIONS = (
    Migration(1, "initial_explicit_version", _migrate_v1, _verify_v1),
    Migration(2, "append_only_task_history", _migrate_v2, _verify_v2),
    Migration(3, "atomic_task_save_requests", _migrate_v3, _verify_v3),
    Migration(4, "aufgaben_folgen_der_post", _migrate_v4, _verify_v4),
    Migration(5, "aufgaben_von_selbst", _migrate_v5, _verify_v5),
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
        goal_id: str | None = None,
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
            goal_id=goal_id,
        )
        with self._transaction():
            self._write(task)
            self._append_event(task, "created", None, at)
        return task

    def from_request(self, request_id: str, payload_digest: str, title: str, provenance: Provenance,
                     *, due: datetime | None = None, project_id: str | None = None,
                     waiting_for: str | None = None, notes: str | None = None,
                     tags: list[str] | None = None, goal_id: str | None = None) -> Task:
        """Save the task, initial waiting state, history and retry binding atomically.

        A retry returns the current task, preserving edits and completion made
        since the original save. Content equality alone is never deduplication.
        The caller must still verify the source before invoking this method.
        """
        at = now()
        with self._transaction():
            binding = self._conn.execute("SELECT payload_digest, task_id FROM task_requests WHERE request_id = ?",
                                         (request_id,)).fetchone()
            if binding:
                if binding['payload_digest'] != payload_digest:
                    raise TaskRequestConflict("Der Speicherauftrag wurde bereits mit anderen Eingaben verwendet.")
                row = self._conn.execute("SELECT document FROM tasks WHERE id = ?", (binding['task_id'],)).fetchone()
                if row is None:
                    raise TaskRequestConflict("Die bereits gespeicherte Aufgabe ist nicht mehr verfügbar.")
                return self._from_row(row)
            task = Task(id=f"t-{uuid.uuid4().hex}", title=title, provenance=provenance,
                        created_at=at, due=ensure_aware(due), project_id=project_id,
                        wartet_auf=waiting_for, wartet_seit=at if waiting_for else None,
                        notes=notes, tags=list(tags or []), goal_id=goal_id)
            self._write(task)
            self._append_event(task, "created", None, None)
            self._conn.execute("INSERT INTO task_requests (request_id, payload_digest, task_id) VALUES (?, ?, ?)",
                               (request_id, payload_digest, task.id))
            return task

    def from_suggestion(self, proposal_id: str, title: str, provenance: Provenance, *, due: datetime | None = None,
                        project_id: str | None = None, waiting_for: str | None = None,
                        person: dict[str, str] | None = None, angelegt: dict[str, Any] | None = None) -> Task:
        """Eine ausdrückliche Übernahme bleibt auch nach einem Abbruch einmalig."""
        if not proposal_id or not title.strip():
            raise ValueError("Vorschlag und Aufgabentitel dürfen nicht leer sein.")
        at = now()
        task = Task(
            id=f"t-suggestion-{proposal_id}", title=title.strip(), provenance=provenance,
            created_at=at, due=ensure_aware(due), project_id=project_id,
            wartet_auf=waiting_for, wartet_seit=at if waiting_for else None,
            person=dict(person) if person else None, angelegt=dict(angelegt) if angelegt else None,
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

    # -- Aufgaben folgen der Post (`aufgaben_post.py`) ---------------------------
    #
    # Ein Ablagevorgang, kein Fakt im Bestand: Die Änderung trägt ihren Grund und ihren vorigen Zustand, damit
    # „Rückgängig“ ihn wiederherstellt. Was der Nutzer zurückgenommen hat, bleibt getrennt (Aufgabe, Mail).

    _VORHER = ("status", "done_at", "wartet_auf", "wartet_seit")

    def post_erledigen(self, task_id: str, grund: dict[str, Any], at: datetime | None = None) -> Task:
        """Erledigt durch die eigene Post. Nur eine offene Aufgabe, die bei dir liegt; sonst `ValueError`."""
        def change(task: Task) -> None:
            if task.status is not TaskStatus.OPEN or task.wartet_auf is not None:
                raise ValueError("Nur eine offene Aufgabe, die bei dir liegt, kann die Post erledigen.")
            vorher = {k: v for k, v in task.to_dict().items() if k in self._VORHER}
            task.status = TaskStatus.DONE
            task.done_at = ensure_aware(at) or now()
            task.erledigt_grund = {**grund, "vorher": vorher}
            task.geaendert_grund = None
        return self._change(task_id, "post_completed", change, at)

    def post_zurueckholen(self, task_id: str, grund: dict[str, Any], at: datetime | None = None) -> Task:
        """Wieder bei dir, weil die Person geantwortet hat. Nur eine offene, wartende Aufgabe; sonst `ValueError`."""
        def change(task: Task) -> None:
            if task.status is not TaskStatus.OPEN or task.wartet_auf is None:
                raise ValueError("Nur eine Aufgabe, die bei jemandem liegt, kann die Post zurückholen.")
            vorher = {k: v for k, v in task.to_dict().items() if k in self._VORHER}
            task.wartet_auf = None
            task.wartet_seit = None
            task.geaendert_grund = {**grund, "vorher": vorher}
        return self._change(task_id, "post_returned", change, at)

    def post_rueckgaengig(self, task_id: str, at: datetime | None = None) -> Task:
        """Stellt den Zustand vor der Änderung durch die Post wieder her und trennt Aufgabe und Mail dauerhaft.

        `KeyError` für eine unbekannte Aufgabe, `LookupError` ohne eine Änderung, die zurückzunehmen wäre.
        """
        getrennt: list[str] = []

        def change(task: Task) -> None:
            grund = task.erledigt_grund or task.geaendert_grund
            if not grund:
                raise LookupError("Zu dieser Aufgabe gibt es keine Änderung durch die Post, die zurückzunehmen wäre.")
            vorher = grund.get("vorher") or {}
            task.status = TaskStatus(vorher.get("status") or TaskStatus.OPEN.value)
            task.done_at = _parse(vorher.get("done_at"))
            task.wartet_auf = vorher.get("wartet_auf")
            task.wartet_seit = _parse(vorher.get("wartet_seit"))
            task.erledigt_grund = None
            task.geaendert_grund = None
            if grund.get("episode_id"):
                getrennt.append(str(grund["episode_id"]))

        with self._transaction():
            row = self._conn.execute("SELECT document FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unbekannte Aufgabe: {task_id}")
            task = self._from_row(row)
            before = _state(task.to_dict())
            change(task)
            self._write(task)
            self._append_event(task, "post_undone", before, at)
            for episode_id in getrennt:
                self._conn.execute(
                    "INSERT OR IGNORE INTO aufgaben_post_getrennt (task_id, episode_id, getrennt_am) VALUES (?, ?, ?)",
                    (task.id, episode_id, now().isoformat()))
            return task

    def post_trennen(self, task_id: str, episode_id: str) -> None:
        """Merkt sich, dass diese Mail für diese Aufgabe nicht zuständig ist (Vorschlag verworfen)."""
        with self._transaction():
            self._conn.execute(
                "INSERT OR IGNORE INTO aufgaben_post_getrennt (task_id, episode_id, getrennt_am) VALUES (?, ?, ?)",
                (task_id, episode_id, now().isoformat()))

    def post_getrennt(self, task_id: str, episode_id: str) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM aufgaben_post_getrennt WHERE task_id = ? AND episode_id = ?",
                                      (task_id, episode_id)).fetchone() is not None

    def post_mail_verarbeitet(self, episode_id: str, digest: str) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM aufgaben_post_mails WHERE episode_id = ? AND digest = ?",
                                      (episode_id, digest)).fetchone() is not None

    def post_mail_merken(self, episode_id: str, digest: str) -> None:
        with self._transaction():
            self._conn.execute(
                "INSERT INTO aufgaben_post_mails (episode_id, digest, verarbeitet_am) VALUES (?, ?, ?) "
                "ON CONFLICT(episode_id) DO UPDATE SET digest=excluded.digest, verarbeitet_am=excluded.verarbeitet_am",
                (episode_id, digest, now().isoformat()))

    def post_stand(self) -> int | None:
        """Die Zeilennummer der Episoden, bis zu der die Post geprüft ist; None vor dem ersten Durchlauf."""
        with self._lock:
            row = self._conn.execute("SELECT zeile FROM aufgaben_post_stand WHERE id = 1").fetchone()
        return int(row["zeile"]) if row else None

    def post_stand_setzen(self, zeile: int) -> None:
        with self._transaction():
            self._conn.execute("INSERT INTO aufgaben_post_stand (id, zeile) VALUES (1, ?) "
                               "ON CONFLICT(id) DO UPDATE SET zeile=excluded.zeile", (int(zeile),))

    def post_aenderungen(self, seit: datetime, limit: int = 200) -> list[Task]:
        """Aufgaben, die die Post seit `seit` erledigt oder zurückgeholt hat (nicht zurückgenommene), jüngste zuerst."""
        # `am` steht in UTC (ISO); der Vergleich als Text verlangt dieselbe Zone.
        moment = (ensure_aware(seit) or now()).astimezone(timezone.utc)
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM tasks WHERE "
                "coalesce(json_extract(document,'$.erledigt_grund.am'), json_extract(document,'$.geaendert_grund.am')) >= ? "
                "ORDER BY coalesce(json_extract(document,'$.erledigt_grund.am'), json_extract(document,'$.geaendert_grund.am')) DESC "
                "LIMIT ?", (moment.isoformat(), limit)).fetchall()
        return [self._from_row(row) for row in rows]

    # -- Aufgaben von selbst (`aufgaben_von_selbst.py`) ---------------------------
    #
    # Eine Aufgabe ist Ablage, kein Fakt (docs/66-automatik.md): Kingfisher darf eine eindeutige Bitte oder Zusage
    # selbst anlegen, aber sichtbar, mit Grund und Rückgängig. Zurücknehmen entfernt die Aufgabe und merkt sich das
    # (Quelle, Titel, Textstelle), damit sie nicht wiederkommt; das Dokument bleibt für „Rückgängig“ des Zurücknehmens.

    def auto_an(self) -> bool:
        """Der Schalter „Aufgaben aus Mails selbst anlegen“; ohne gespeicherte Wahl an (die Vorgabe)."""
        with self._lock:
            row = self._conn.execute("SELECT an FROM aufgaben_auto_einstellung WHERE id = 1").fetchone()
        return True if row is None else bool(row["an"])

    def auto_setzen(self, an: bool) -> bool:
        with self._transaction():
            self._conn.execute("INSERT INTO aufgaben_auto_einstellung (id, an) VALUES (1, ?) "
                               "ON CONFLICT(id) DO UPDATE SET an=excluded.an", (1 if an else 0,))
        return bool(an)

    def auto_geprueft(self) -> set[str]:
        """Die Vorschläge, die der Durchlauf schon geprüft hat (jeder einmal)."""
        with self._lock:
            return {row["proposal_id"] for row in self._conn.execute("SELECT proposal_id FROM aufgaben_auto_geprueft")}

    def auto_geprueft_merken(self, proposal_id: str, ergebnis: str) -> None:
        with self._transaction():
            self._conn.execute("INSERT INTO aufgaben_auto_geprueft (proposal_id, ergebnis, geprueft_am) VALUES (?, ?, ?) "
                               "ON CONFLICT(proposal_id) DO UPDATE SET ergebnis=excluded.ergebnis, "
                               "geprueft_am=excluded.geprueft_am", (proposal_id, ergebnis, now().isoformat()))

    def auto_ergebnis(self, proposal_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT ergebnis FROM aufgaben_auto_geprueft WHERE proposal_id = ?",
                                     (proposal_id,)).fetchone()
        return row["ergebnis"] if row else None

    def auto_zurueckgenommen(self, episode_id: str, titel_schluessel: str, zitat_schluessel: str) -> bool:
        """Ob der Nutzer eine Aufgabe aus dieser Mail mit demselben Titel oder derselben Textstelle zurückgenommen hat."""
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM aufgaben_auto_zurueck WHERE episode_id = ? AND (titel_schluessel = ? OR zitat_schluessel = ?)",
                (episode_id, titel_schluessel, zitat_schluessel)).fetchone() is not None

    def mit_quelle(self, source_ref: str) -> list[Task]:
        """Alle Aufgaben (jeder Zustand) aus dieser Quelle (`episode:<id>`)."""
        with self._lock:
            rows = self._conn.execute("SELECT document FROM tasks WHERE json_extract(document,'$.provenance.source_ref') = ?",
                                      (source_ref,)).fetchall()
        return [self._from_row(row) for row in rows]

    def angelegt_seit(self, seit: datetime, art: str = "automatisch", limit: int = 200) -> list[Task]:
        """Aufgaben, die Kingfisher seit `seit` selbst angelegt hat (nicht zurückgenommene), jüngste zuerst."""
        moment = (ensure_aware(seit) or now()).astimezone(timezone.utc)
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM tasks WHERE json_extract(document,'$.angelegt.art') = ? "
                "AND json_extract(document,'$.angelegt.am') >= ? "
                "ORDER BY json_extract(document,'$.angelegt.am') DESC LIMIT ?",
                (art, moment.isoformat(), limit)).fetchall()
        return [self._from_row(row) for row in rows]

    def gruppe(self, gruppe: str) -> list[Task]:
        """Die Aufgaben einer gemeinsamen Übernahme („Alle übernehmen“)."""
        with self._lock:
            rows = self._conn.execute("SELECT document FROM tasks WHERE json_extract(document,'$.angelegt.gruppe') = ?",
                                      (gruppe,)).fetchall()
        return [self._from_row(row) for row in rows]

    def anlage_entfernen(self, task_id: str, *, merken: dict[str, str] | None = None) -> Task:
        """Entfernt eine Aufgabe, die Kingfisher angelegt oder gemeinsam übernommen hat; die Geschichte bleibt.

        `merken` (`proposal_id`, `episode_id`, `titel_schluessel`, `zitat_schluessel`) hält fest, dass der Nutzer sie
        zurückgenommen hat, damit dieselbe Bitte nicht wieder angelegt wird; dazu das Dokument für das Wiederherstellen.
        `KeyError` unbekannt, `LookupError`, wenn die Aufgabe nicht von selbst oder gemeinsam entstand.
        """
        with self._transaction():
            row = self._conn.execute("SELECT document FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unbekannte Aufgabe: {task_id}")
            task = self._from_row(row)
            if not task.angelegt:
                raise LookupError("Diese Aufgabe hat Kingfisher nicht selbst angelegt; sie bleibt.")
            before = _state(task.to_dict())
            self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._conn.execute(
                "INSERT INTO task_events (task_id, kind, recorded_at, business_at, before_state, after_state) "
                "VALUES (?, 'auto_removed', ?, NULL, ?, ?)",
                (task.id, now().isoformat(), json.dumps(before, ensure_ascii=False),
                 json.dumps({**before, "status": "removed"}, ensure_ascii=False)))
            if merken:
                self._conn.execute(
                    "INSERT INTO aufgaben_auto_zurueck (proposal_id, episode_id, titel_schluessel, zitat_schluessel, "
                    "task_id, dokument, zurueck_am) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(proposal_id) DO UPDATE SET "
                    "task_id=excluded.task_id, dokument=excluded.dokument, zurueck_am=excluded.zurueck_am",
                    (merken["proposal_id"], merken["episode_id"], merken["titel_schluessel"], merken["zitat_schluessel"],
                     task.id, row["document"], now().isoformat()))
            return task

    def anlage_wiederherstellen(self, task_id: str) -> tuple[Task, str]:
        """Nimmt das Zurücknehmen zurück: dieselbe Aufgabe wie vorher, und sie gilt nicht mehr als zurückgenommen.

        Gibt die Aufgabe und den Vorschlag zurück. `KeyError`, wenn es nichts wiederherzustellen gibt; `ValueError`,
        wenn unter der Kennung inzwischen wieder eine Aufgabe steht."""
        with self._transaction():
            row = self._conn.execute("SELECT proposal_id, dokument FROM aufgaben_auto_zurueck WHERE task_id = ? "
                                     "ORDER BY zurueck_am DESC LIMIT 1", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Nichts wiederherzustellen: {task_id}")
            if self._conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
                raise ValueError("Diese Aufgabe steht schon wieder in der Liste.")
            task = self._from_row({"document": row["dokument"]})  # type: ignore[arg-type]
            self._write(task)
            self._append_event(task, "auto_restored", None, None)
            self._conn.execute("DELETE FROM aufgaben_auto_zurueck WHERE proposal_id = ?", (row["proposal_id"],))
            return task, row["proposal_id"]

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

    def page(self, view: str = 'mine', *, project_id: str | None = None,
             q: str = '', limit: int = 200, cursor: str | None = None,
             ids: set[str] | None = None, auswahl: str | None = None) -> dict[str, Any]:
        from .task_pages import query_page
        with self._lock:
            page = query_page(self._conn, view, project_id=project_id, q=q, limit=limit, cursor=cursor,
                              ids=ids, auswahl=auswahl)
        page['tasks'] = [self._from_row(row).to_dict() for row in page.pop('rows')]
        return page

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

    def project_overview(self, project_id: str, at: datetime | None = None,
                         ids: set[str] | None = None) -> dict[str, Any]:
        """Full-project counts and bounded previews from one read snapshot.

        Waiting work is not the user's overdue work. Dropped tasks are not
        completed tasks. No task, event, or deadline is changed by this read.
        `ids` begrenzt auf die Aufgaben eines Bereichs (Paket Z1): dieselbe Auswahl wie die Liste darunter.
        """
        moment = ensure_aware(at) or now()
        waiting = "json_extract(document, '$.wartet_auf')"
        nur = '' if ids is None else ' AND id IN (SELECT value FROM json_each(?))'
        nur_wert = () if ids is None else (json.dumps(sorted(ids)),)
        with self._lock:
            self._conn.execute('BEGIN')
            try:
                counts = self._conn.execute(f"""
                    SELECT
                      coalesce(sum(status='open' AND {waiting} IS NULL),0) AS mine,
                      coalesce(sum(status='open' AND {waiting} IS NOT NULL),0) AS waiting,
                      coalesce(sum(status='done'),0) AS done,
                      coalesce(sum(status='dropped'),0) AS dropped,
                      coalesce(sum(status='open' AND {waiting} IS NULL AND julianday(due)<julianday(?)),0) AS overdue,
                      coalesce(sum(status='open' AND {waiting} IS NULL AND due IS NULL),0) AS undated
                    FROM tasks WHERE project_id=?{nur}
                """, (moment.isoformat(), project_id, *nur_wert)).fetchone()
                mine = self._conn.execute(f"""
                    SELECT document FROM tasks WHERE project_id=?{nur} AND status='open' AND {waiting} IS NULL
                    ORDER BY due IS NULL, julianday(due), julianday(created_at), id LIMIT 3
                """, (project_id, *nur_wert)).fetchall()
                waiting_rows = self._conn.execute(f"""
                    SELECT document FROM tasks WHERE project_id=?{nur} AND status='open' AND {waiting} IS NOT NULL
                    ORDER BY coalesce(julianday(json_extract(document,'$.wartet_seit')),julianday(created_at)), id LIMIT 3
                """, (project_id, *nur_wert)).fetchall()
            finally:
                self._conn.rollback()
        def preview(row: sqlite3.Row) -> dict[str, Any]:
            task = self._from_row(row)
            return {**task.to_dict(), 'overdue': task.is_overdue(moment), 'wartet_tage': task.wartet_tage(moment)}
        return {'project_id': project_id, 'as_of': moment.isoformat(), 'counts': dict(counts),
                'next_tasks': [preview(row) for row in mine],
                'waiting_tasks': [preview(row) for row in waiting_rows]}

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
            goal_id=d.get("goal_id"),
            wartet_auf=d.get("wartet_auf"),
            wartet_seit=_parse(d.get("wartet_seit")),
            erledigt_grund=d.get("erledigt_grund") or None,
            geaendert_grund=d.get("geaendert_grund") or None,
            person=d.get("person") or None,
            angelegt=d.get("angelegt") or None,
        )


__all__ = ["Task", "TaskStatus", "TaskStore"]
