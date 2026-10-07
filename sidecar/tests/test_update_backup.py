"""Vor einem Umbau der Datenbank liegt eine vollständige Kopie von vorher."""
import sqlite3

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.backup import UPDATE_SET_PREFIX, list_snapshots, snapshot_all, verify_snapshot_set
from icarus_memory.claims import ClaimStore
from icarus_memory.update_backup import backup_before_update, outdated
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.working_memory_legacy import downgrade_terms

BODY = 'Anna liefert die Prüfmuster am 3. Oktober.'


def _bestand(data_dir):
    episodes = EpisodeStore(data_dir / 'episodes.sqlite3')
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Mail', BODY, Provenance(SourceType.EMAIL))
    memory = WorkingMemoryStore(episodes)
    assert memory.commit(memory.pending()[0], [{'start': 0, 'end': len(BODY), 'kind': 'fact'}], model='a')
    episodes.close()
    ClaimStore(data_dir / 'knowledge.sqlite3').close()
    return episode


def _version(path):
    connection = sqlite3.connect(path)
    try:
        return connection.execute('PRAGMA user_version').fetchone()[0]
    finally:
        connection.close()


def _alt(data_dir):
    connection = sqlite3.connect(data_dir / 'episodes.sqlite3')
    downgrade_terms(connection, 9)
    connection.close()


def test_current_or_new_data_needs_no_backup(tmp_path):
    assert backup_before_update(tmp_path) is None
    _bestand(tmp_path)
    assert outdated(tmp_path) == []
    assert backup_before_update(tmp_path) is None
    assert not (tmp_path / 'sicherungen').exists()


def test_outdated_database_is_saved_before_it_is_rebuilt(tmp_path):
    episode = _bestand(tmp_path)
    _alt(tmp_path)
    assert outdated(tmp_path) == ['episodes.sqlite3']

    saved = backup_before_update(tmp_path)
    assert saved is not None and saved.parent == tmp_path / 'sicherungen'
    assert saved.name.startswith(UPDATE_SET_PREFIX)
    names = {entry['name'] for entry in verify_snapshot_set(saved)}
    assert {'episodes.sqlite3', 'knowledge.sqlite3'} <= names
    # Die Kopie ist der Stand von vorher, nicht der umgebaute.
    assert _version(saved / 'episodes.sqlite3') == 9

    reopened = EpisodeStore(tmp_path / 'episodes.sqlite3')
    assert reopened.get(episode.id).body == BODY
    reopened.close()
    assert _version(tmp_path / 'episodes.sqlite3') == 18
    # Nach dem Umbau steht nichts mehr an: kein zweiter Satz beim nächsten Start.
    assert backup_before_update(tmp_path) is None
    assert len(list((tmp_path / 'sicherungen').iterdir())) == 1
    # Die regelmäßige Sicherung räumt sie nicht weg, und sie steht in der Liste.
    for _ in range(3):
        snapshot_all(tmp_path, tmp_path / 'sicherungen', keep=1)
    listed = list_snapshots(tmp_path / 'sicherungen')
    assert [entry['name'] for entry in listed if entry['before_update']] == [saved.name]
    assert sum(not entry['before_update'] for entry in listed) == 1
    # Neueste zuerst, gleich welcher Art.
    assert listed[-1]['name'] == saved.name


def test_update_backup_is_listed_for_restore(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    _bestand(tmp_path)
    _alt(tmp_path)
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    saved = backup_before_update(tmp_path)
    app = create_app(episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    with TestClient(app) as client:
        names = [entry['name'] for entry in client.get('/backups').json() if entry.get('before_update')]
        assert names == [saved.name]
    app.state.scheduler.stop()


def test_failed_backup_does_not_block_start(tmp_path, monkeypatch):
    from icarus_memory import update_backup
    _bestand(tmp_path)
    _alt(tmp_path)

    def voll(*args, **kwargs):
        raise OSError('No space left on device')
    monkeypatch.setattr(update_backup, 'snapshot_all', voll)
    assert backup_before_update(tmp_path) is None
    EpisodeStore(tmp_path / 'episodes.sqlite3').close()


def test_create_app_saves_before_opening_stores(tmp_path, monkeypatch):
    from icarus_memory import server
    calls = []

    def recorded(data_dir):
        calls.append((data_dir, (data_dir / 'episodes.sqlite3').exists()))
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(server, 'backup_before_update', recorded)
    monkeypatch.setattr(server, '_build_agent', lambda app: None)
    try:
        server.create_app()
    except Exception:  # noqa: BLE001 - nur die Reihenfolge zählt hier
        pass
    assert calls == [(tmp_path, False)]
