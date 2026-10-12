"""Dauerhafte Wiedervorlage geänderter Quellen; keine Texte und keine Modellaktivierung."""
from .migrations import IndexContract

TABLES = {'task_rechecks': {'id', 'generation', 'position'},
          'task_recheck_turn': {'id', 'priority'}}
KEYS = {'task_rechecks': {'id'}, 'task_recheck_turn': {'id'}}
INDEXES = {'idx_task_rechecks_position': IndexContract('task_rechecks', ('position', 'id'))}
TRIGGERS = {
    'trg_task_recheck_change': '''CREATE TRIGGER trg_task_recheck_change
    AFTER UPDATE OF support_generation ON episodes WHEN NEW.support_generation > OLD.support_generation
    BEGIN INSERT INTO task_rechecks(id,generation,position)
    VALUES(NEW.id,NEW.support_generation,(SELECT COALESCE(MAX(position),0)+1 FROM task_rechecks))
    ON CONFLICT(id) DO UPDATE SET generation=excluded.generation; END''',
    'trg_task_recheck_delete': '''CREATE TRIGGER trg_task_recheck_delete
    AFTER DELETE ON episodes BEGIN DELETE FROM task_rechecks WHERE id=OLD.id; END''',
}


def migrate(connection):
    connection.execute('CREATE TABLE task_rechecks(id TEXT PRIMARY KEY, generation INTEGER NOT NULL, position INTEGER NOT NULL)')
    connection.execute('CREATE INDEX idx_task_rechecks_position ON task_rechecks(position,id)')
    connection.execute('CREATE TABLE task_recheck_turn(id INTEGER PRIMARY KEY CHECK(id=1), priority INTEGER NOT NULL CHECK(priority IN (0,1)))')
    connection.execute('INSERT INTO task_recheck_turn VALUES(1,1)')
    connection.execute('INSERT INTO task_rechecks SELECT id,support_generation,rowid FROM episodes WHERE support_generation>0')
    for sql in TRIGGERS.values():
        connection.execute(sql)


def enqueue(store, episode_id):
    """Neue laufende Post vormerken; mit Aufnahme und Fortschritt atomar speicherbar."""
    with store.transaction():
        store._conn.execute(
            'INSERT INTO task_rechecks(id,generation,position) '
            'SELECT id,support_generation,(SELECT COALESCE(MAX(position),0)+1 FROM task_rechecks) '
            'FROM episodes WHERE id=? '
            'ON CONFLICT(id) DO UPDATE SET generation=excluded.generation', (episode_id,))


def budget(store, total):
    if total < 1:
        return 0
    if total > 1:
        return total // 2
    with store.transaction():
        if not store._conn.execute('SELECT 1 FROM task_rechecks LIMIT 1').fetchone():
            return 0
        turn = store._conn.execute('SELECT priority FROM task_recheck_turn WHERE id=1').fetchone()[0]
        store._conn.execute('UPDATE task_recheck_turn SET priority=1-priority WHERE id=1')
        return turn


def pending(store, limit):
    with store._lock:
        return [dict(r) for r in store._conn.execute(
            'SELECT id,generation,position FROM task_rechecks ORDER BY position,id LIMIT ?',
            (max(0, min(limit, 20)),))]


def finish(store, row, completed):
    # Erst nach dem dauerhaften Jobabschluss bestätigen. Ein Crash dazwischen
    # wiederholt idempotent; ein alter Abschluss entfernt keine neuere Änderung.
    with store.transaction():
        if completed:
            store._conn.execute('DELETE FROM task_rechecks WHERE id=? AND generation=?', (row['id'], row['generation']))
        else:
            store._conn.execute('UPDATE task_rechecks SET position=(SELECT COALESCE(MAX(position),0)+1 FROM task_rechecks) '
                                'WHERE id=? AND generation=?', (row['id'], row['generation']))
