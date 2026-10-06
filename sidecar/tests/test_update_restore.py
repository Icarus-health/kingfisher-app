"""Offline update rollback restores the pre-migration store into inspection mode."""

from datetime import datetime, timezone
import sqlite3

import pytest

from icarus_memory.backup import UPDATE_SET_PREFIX, snapshot_all
from icarus_memory.restore_boundary import pending
from icarus_memory.update_restore import restore_update


def test_restores_pre_migration_sqlite_and_keeps_inspection_boundary(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    database = data / 'self-model.sqlite3'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE evidence (value TEXT NOT NULL)')
        connection.execute("INSERT INTO evidence VALUES ('vorher')")
        connection.execute('PRAGMA user_version = 1')
    snapshot = snapshot_all(data, data / 'sicherungen', at=datetime(2026, 10, 6, tzinfo=timezone.utc),
                            prefix=UPDATE_SET_PREFIX)

    with sqlite3.connect(database) as connection:
        connection.execute('ALTER TABLE evidence ADD COLUMN new_release TEXT')
        connection.execute("UPDATE evidence SET value = 'nachher', new_release = 'only-new-code'")
        connection.execute('PRAGMA user_version = 2')

    restore_update(snapshot.name, data_dir=data)

    with sqlite3.connect(database) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 1
        assert connection.execute('SELECT * FROM evidence').fetchall() == [('vorher',)]
    assert snapshot.is_dir()
    assert pending(data)


@pytest.mark.parametrize('name', ['../vor-update-20261006T000000Z', '/tmp/vor-update-20261006T000000Z',
                                  'vor-update-20261006T000000Z/other', 'vor-update-latest'])
def test_rejects_untrusted_snapshot_names_without_changing_data(tmp_path, name):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'sentinel').write_text('unchanged')
    with pytest.raises(ValueError):
        restore_update(name, data_dir=data)
    assert (data / 'sentinel').read_text() == 'unchanged'
    assert not pending(data)


def test_rejects_symlink_snapshot(tmp_path):
    data = tmp_path / 'data'
    snapshots = data / 'sicherungen'
    snapshots.mkdir(parents=True)
    (snapshots / 'vor-update-20261006T000000Z').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        restore_update('vor-update-20261006T000000Z', data_dir=data)
    assert not pending(data)
