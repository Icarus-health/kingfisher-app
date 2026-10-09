"""Retry binding and the complete initial task state share one transaction."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from icarus_memory.model import Provenance, SourceType
from icarus_memory.tasks import TaskStore

P = Provenance(source_type=SourceType.USER_STATED, source_ref='synthetic:mail')


def test_two_store_instances_save_one_task_with_one_initial_history(tmp_path):
    path = tmp_path / 'tasks.db'
    first, second = TaskStore(path), TaskStore(path)
    try:
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(store.from_request, 'synthetic-request', 'a'*64, 'Bericht senden', P,
                                   waiting_for='Lea') for store in (first, second)]
            tasks = [future.result() for future in futures]
        assert tasks[0].id == tasks[1].id
        assert len(first.all_tasks()) == 1
        events = first.history(tasks[0].id)
        assert len(events) == 1
        assert events[0]['after']['wartet_auf'] == 'Lea'
        assert events[0]['after']['wartet_seit'] is not None
    finally:
        first.close(); second.close()


@pytest.mark.parametrize('table', ['task_requests', 'task_events'])
def test_failure_in_request_or_history_rolls_back_entire_task(tmp_path, table):
    store = TaskStore(tmp_path / 'tasks.db')
    try:
        store._conn.execute(f"CREATE TRIGGER synthetic_failure BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        with pytest.raises(sqlite3.IntegrityError):
            store.from_request('synthetic-request', 'a'*64, 'Bericht senden', P, waiting_for='Lea')
        assert store.all_tasks() == []
        assert store._conn.execute('SELECT count(*) FROM task_events').fetchone()[0] == 0
        assert store._conn.execute('SELECT count(*) FROM task_requests').fetchone()[0] == 0
        store._conn.execute('DROP TRIGGER synthetic_failure')
        task = store.from_request('synthetic-request', 'a'*64, 'Bericht senden', P, waiting_for='Lea')
        assert task.wartet_auf == 'Lea' and len(store.history(task.id)) == 1
    finally:
        store.close()


def test_v2_upgrade_preserves_existing_task_and_history(tmp_path):
    from icarus_memory.migrations import run_migrations
    from icarus_memory.tasks import _MIGRATIONS
    path = tmp_path / 'tasks.db'
    with sqlite3.connect(path) as connection:
        run_migrations(connection, store='tasks', path=path, migrations=_MIGRATIONS[:2])
    # Seed a real v2 row without opening the newer TaskStore.
    import json
    from icarus_memory.tasks import Task
    from datetime import datetime, timezone
    old = Task(id='t-old', title='Vorhandene Aufgabe', provenance=P,
               created_at=datetime(2026, 10, 1, tzinfo=timezone.utc))
    with sqlite3.connect(path) as connection:
        connection.execute('INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)',
            (old.id, old.created_at.isoformat(), 'open', None, old.title, json.dumps(old.to_dict()), None))
        before = connection.execute('SELECT * FROM tasks').fetchall()
        history = connection.execute('SELECT * FROM task_events').fetchall()
    store = TaskStore(path)
    try:
        assert store.get(old.id).title == 'Vorhandene Aufgabe'
        assert store._conn.execute('PRAGMA user_version').fetchone()[0] == 3
        assert [tuple(row) for row in store._conn.execute('SELECT * FROM tasks')] == before
        assert [tuple(row) for row in store._conn.execute('SELECT * FROM task_events')] == history
        assert store._conn.execute('SELECT count(*) FROM task_requests').fetchone()[0] == 0
    finally:
        store.close()
