"""Task reminders retain their own chronology without rewriting task deadlines."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from icarus_memory.model import Provenance, SourceType
from icarus_memory.tasks import TaskStore


P = Provenance(source_type=SourceType.CHAT, source_ref="synthetic:reminder")


def test_reminder_edit_is_separate_from_due_and_survives_restart_and_clear(tmp_path):
    path = tmp_path / "tasks.db"
    store = TaskStore(path)
    due = datetime(2026, 10, 15, 21, 59, tzinfo=timezone.utc)
    reminder = datetime(2026, 10, 10, 8, 30, tzinfo=timezone(timedelta(hours=2)))
    task = store.add("Synthetic private title", P, due=due, notes="Synthetic private notes")
    store.warten_auf(task.id, "Synthetic waiting person")

    updated = store.edit(task.id, remind_at=reminder)
    assert updated.due == due
    assert updated.remind_at == reminder
    assert [item.id for item in store.reminders_due(datetime(2026, 10, 10, 6, 0, tzinfo=timezone.utc))] == []
    assert [item.id for item in store.reminders_due(datetime(2026, 10, 10, 7, 0, tzinfo=timezone.utc))] == [task.id]

    history = store.history(task.id)
    assert history[0]["kind"] == "edited"
    assert history[0]["after"]["remind_at"] == reminder.astimezone().isoformat()
    assert history[0]["after"]["due"] == due.astimezone().isoformat()
    for event in history:
        assert "title" not in event["after"]
        assert "notes" not in event["after"]

    store.close()
    store = TaskStore(path)
    restored = store.get(task.id)
    assert restored is not None
    assert restored.due == due
    assert restored.remind_at == reminder
    cleared = store.edit(task.id, remind_at=None)
    assert cleared.remind_at is None
    assert cleared.due == due
    store.close()


def test_reminders_include_waiting_tasks_and_scan_beyond_open_task_list_limit(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    at = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    for index in range(205):
        task = store.add(f"Synthetic task {index}", P)
        if index == 204:
            store.warten_auf(task.id, "Synthetic person")
            store.edit(task.id, remind_at=at - timedelta(minutes=1))
            expected = task.id
    assert len(store.open_tasks()) == 200
    assert [task.id for task in store.reminders_due(at)] == [expected]
    store.close()


def test_legacy_task_document_without_remind_at_loads_as_none(tmp_path):
    path = tmp_path / "tasks.db"
    store = TaskStore(path)
    task = store.add("Synthetic legacy task", P)
    with store._lock:
        row = store._conn.execute("SELECT document FROM tasks WHERE id = ?", (task.id,)).fetchone()
        document = json.loads(row["document"])
        document.pop("remind_at", None)
        store._conn.execute("UPDATE tasks SET document = ? WHERE id = ?", (json.dumps(document), task.id))
        store._conn.commit()
    store.close()

    reopened = TaskStore(path)
    restored = reopened.get(task.id)
    assert restored is not None
    assert restored.remind_at is None
    reopened.close()


def test_reminders_are_ordered_and_exclude_finished_or_dropped_tasks(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    at = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    late = store.add("Synthetic later reminder", P)
    early = store.add("Synthetic earlier reminder", P)
    done = store.add("Synthetic completed task", P)
    dropped = store.add("Synthetic dropped task", P)
    store.edit(late.id, remind_at=at - timedelta(minutes=10))
    store.edit(early.id, remind_at=at - timedelta(minutes=30))
    store.edit(done.id, remind_at=at - timedelta(hours=1))
    store.edit(dropped.id, remind_at=at - timedelta(hours=2))
    store.complete(done.id)
    store.drop(dropped.id)

    assert [task.id for task in store.reminders_due(at, limit=1)] == [early.id]
    assert [task.id for task in store.reminders_due(at)] == [early.id, late.id]
    for invalid in (0, 201, True):
        try:
            store.reminders_due(at, limit=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid reminder limit was accepted: {invalid!r}")
    store.close()
