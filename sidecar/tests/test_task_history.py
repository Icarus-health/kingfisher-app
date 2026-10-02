"""Synthetic evidence for the prerequisite task history, not Matter semantics."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event

import pytest

from icarus_memory.model import Provenance, SourceType
from icarus_memory.tasks import TaskStore

P = Provenance(source_type=SourceType.CHAT, source_ref='synthetic:history')
OLD = datetime(2020, 1, 2, tzinfo=timezone.utc)


def test_history_survives_restart_and_noops(tmp_path):
    path = tmp_path / 'tasks.db'
    store = TaskStore(path)
    task = store.add('Synthetic task', P, at=OLD)
    store.complete(task.id, at=OLD)
    store.complete(task.id)
    store.reopen(task.id)
    store.reopen(task.id)
    store.warten_auf(task.id, 'Synthetic person', at=OLD)
    store.warten_auf(task.id, 'Synthetic person')
    store.assign_project(task.id, 'synthetic-project')
    store.assign_project(task.id, 'synthetic-project')
    store.zurueckholen(task.id)
    store.zurueckholen(task.id)
    store.drop(task.id, at=OLD)
    store.drop(task.id)
    expected = store.history(task.id)
    assert [e['kind'] for e in reversed(expected)] == [
        'created', 'completed', 'reopened', 'waiting_for', 'project_assigned', 'returned', 'dropped']
    assert all(e['actor_id'] is None for e in expected)
    assert datetime.fromisoformat(expected[-1]['recorded_at']) > OLD
    assert datetime.fromisoformat(expected[-1]['business_at']) == OLD
    assert expected[-1]['before'] is None
    assert expected[0]['before']['status'] == 'open'
    assert expected[0]['after']['status'] == 'dropped'
    assert len(store.history(task.id, limit=2)) == 2
    with pytest.raises(ValueError):
        store.history(task.id, limit=201)
    store.close()
    reopened = TaskStore(path)
    assert reopened.history(task.id) == expected
    reopened.close()


def test_suggestion_replay_is_once_across_connections(tmp_path):
    path = tmp_path / 'tasks.db'
    stores = [TaskStore(path), TaskStore(path)]
    with ThreadPoolExecutor(2) as pool:
        tasks = list(pool.map(lambda s: s.from_suggestion('synthetic-proposal', 'Task', P), stores))
    assert tasks[0].id == tasks[1].id
    assert [e['kind'] for e in stores[0].history(tasks[0].id)] == ['from_suggestion']
    for store in stores:
        store.close()


def test_history_failure_rolls_back_task_change(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    task = store.add('Task', P)
    store._conn.execute("CREATE TRIGGER fail_history BEFORE INSERT ON task_events BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.complete(task.id)
    assert store.get(task.id).status.value == 'open'
    assert len(store.history(task.id)) == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.add('Must roll back', P)
    assert len(store.all_tasks()) == 1
    store.close()


def test_two_connection_read_modify_write_does_not_lose_fields(tmp_path, monkeypatch):
    path = tmp_path / 'tasks.db'
    first, second = TaskStore(path), TaskStore(path)
    task = first.add('Task', P)
    entered, release, attempting = Event(), Event(), Event()
    original = first._from_row
    def paused_read(row):
        value = original(row)
        entered.set()
        assert release.wait(3)
        return value
    monkeypatch.setattr(first, '_from_row', paused_read)
    def assign():
        attempting.set()
        return second.assign_project(task.id, 'synthetic-project')
    with ThreadPoolExecutor(2) as pool:
        waiting = pool.submit(first.warten_auf, task.id, 'Synthetic person')
        assert entered.wait(3)
        assigned = pool.submit(assign)
        assert attempting.wait(3)
        # A second writer must be unable to read until the first transaction commits.
        assert not assigned.done()
        release.set()
        waiting.result()
        assigned.result()
    final = second.get(task.id)
    assert final.wartet_auf == 'Synthetic person'
    assert final.project_id == 'synthetic-project'
    assert len(second.history(task.id)) == 3
    first.close()
    second.close()


def test_legacy_snapshot_does_not_invent_past_action(tmp_path):
    from icarus_memory.tasks import Task, _migrate_v1
    import json
    path = tmp_path / 'tasks.db'
    task = Task(id='legacy', title='Synthetic old task', provenance=P, created_at=OLD)
    with sqlite3.connect(path) as conn:
        _migrate_v1(conn)
        conn.execute('INSERT INTO tasks (id, created_at, status, title, document) VALUES (?, ?, ?, ?, ?)',
                     (task.id, OLD.isoformat(), 'open', task.title, json.dumps(task.to_dict())))
        conn.execute('PRAGMA user_version=1')
    store = TaskStore(path)
    event, = store.history(task.id)
    assert event['kind'] == 'preexisting_snapshot'
    assert event['business_at'] is None
    assert event['before'] is None
    assert datetime.fromisoformat(event['recorded_at']) > OLD
    store.complete(task.id)
    assert len(store.history(task.id)) == 2
    for sql in ('UPDATE task_events SET kind="created"', 'DELETE FROM task_events'):
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(sql)
        store._conn.rollback()
    store.close()


def test_failed_baseline_migration_keeps_original_version_and_document(tmp_path):
    from icarus_memory.migrations import MigrationError
    from icarus_memory.tasks import _migrate_v1
    path = tmp_path / 'tasks.db'
    with sqlite3.connect(path) as conn:
        _migrate_v1(conn)
        conn.execute("INSERT INTO tasks (id, created_at, status, title, document) VALUES ('synthetic-broken', ?, 'open', 'Task', 'invalid-json')", (OLD.isoformat(),))
        conn.execute('PRAGMA user_version=1')
    with pytest.raises(MigrationError):
        TaskStore(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 1
        assert conn.execute("SELECT document FROM tasks").fetchone()[0] == 'invalid-json'
        assert conn.execute("SELECT count(*) FROM sqlite_schema WHERE name='task_events'").fetchone()[0] == 0


def test_history_minimizes_private_content_and_does_not_use_dynamic_fields(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    task = store.add('Synthetic private title', P, notes='Synthetic private notes')
    store.assign_project(task.id, 'synthetic-project')
    for event in store.history(task.id):
        assert 'title' not in event['after']
        assert 'notes' not in event['after']
        assert 'provenance' not in event['after']
        assert 'overdue' not in event['after']
        assert 'wartet_tage' not in event['after']
    assert store.history('unknown') == []
    with pytest.raises(KeyError):
        store.complete('unknown')
    assert len(store.history(task.id)) == 2
    store.close()


@pytest.mark.parametrize('recursive_triggers', [0, 1])
def test_insert_or_replace_cannot_overwrite_history(tmp_path, recursive_triggers):
    path = tmp_path / 'tasks.db'
    store = TaskStore(path)
    task = store.add('Synthetic immutable task', P)
    before = store.history(task.id)
    sequence = before[0]['sequence']
    store.close()
    # Independent connections retain the contract without a Store-owned PRAGMA.
    with sqlite3.connect(path) as conn:
        conn.execute(f'PRAGMA recursive_triggers={recursive_triggers}')
        with pytest.raises(sqlite3.IntegrityError, match='append-only'):
            conn.execute(
                "INSERT OR REPLACE INTO task_events "
                "(sequence, task_id, kind, recorded_at, after_state) "
                "VALUES (?, ?, 'forged', ?, '{}')", (sequence, task.id, OLD.isoformat()))
    reopened = TaskStore(path)
    assert reopened.history(task.id) == before
    reopened.complete(task.id)
    assert len(reopened.history(task.id)) == 2
    reopened.close()
