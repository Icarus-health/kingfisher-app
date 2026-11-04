"""Recovery evidence must never restore historical execution authority."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.backup import SQLITE_DATA_FILES, restore_all, snapshot_all
from icarus_memory.procedures import ProcedureStore
from icarus_memory.restore_boundary import mark_pending
from icarus_memory.restore_inspection import create_inspection_app

TOKEN = 'synthetic-preflight-token'
HEADERS = {'x-icarus-token': TOKEN}
STAMP = '20261104T120000Z'


def request(root, monkeypatch, body=None):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', TOKEN)
    return TestClient(create_inspection_app(root)).post(
        '/api/v1/recovery/preflight', json={} if body is None else body, headers=HEADERS)


def db(root, name='tasks.sqlite3'):
    root.mkdir(exist_ok=True)
    with sqlite3.connect(root / name) as conn:
        conn.execute('CREATE TABLE sample (id TEXT PRIMARY KEY, value BLOB)')
        conn.execute('INSERT INTO sample VALUES (?,?)', ('private-key', 'private-content'))


def fingerprints(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.iterdir() if p.is_file() and not p.is_symlink()}


def files(report):
    return {f['name']: f for f in report['restored']['files']}


def test_revoked_source_and_skill_are_differences_not_restored_permission(tmp_path, monkeypatch):
    data = tmp_path / 'data'
    episodes = EpisodeStore(data / 'episodes.sqlite3')
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Private source title',
        'Private source body', Provenance(source_type=SourceType.USER_STATED))
    procedures = ProcedureStore(data / 'procedures.sqlite3')
    skill = procedures.propose(dict(name='recovery-check', title='Private skill title',
        description='Einen Entwurf prüfen.', area='mail', triggers=['probe'],
        steps=['Anlass prüfen. Danach den Entwurf prüfen.'],
        positive='Schreibe eine Probe Mail.', negative='Schreibe eine Urlaubs Mail.'))
    procedures.accept(skill['id'])
    snapshot = snapshot_all(data, tmp_path / 'snapshots')
    episodes.ignore(episode.id)
    procedures.revoke(skill['id'])
    episodes.close(); procedures.close()
    restore_all(snapshot, data, at=datetime(2026, 11, 4, 12, tzinfo=timezone.utc))
    before = fingerprints(data)
    response = request(data, monkeypatch)
    assert response.status_code == 200, response.text
    report = response.json()
    assert not report['operational'] and not report['activation_allowed']
    assert not report['comparison_complete']
    assert report['comparison_groups'][0]['relationship'] == 'unverified'
    changes = {(t['store'], t['table']): t for t in report['comparison_groups'][0]['tables']}
    assert changes['episodes.sqlite3', 'episodes']['changed_rows'] == 1
    assert changes['procedures.sqlite3', 'procedures']['changed_rows'] == 1
    assert set(files(report)) >= set(SQLITE_DATA_FILES)
    for secret in (episode.id, skill['id'], 'Private source', 'Private skill'):
        assert secret not in response.text
    assert fingerprints(data) == before
    assert request(data, monkeypatch).json()['report_fingerprint'] == report['report_fingerprint']


def test_absent_comparison_is_unknown_not_no_changes(tmp_path, monkeypatch):
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    response = request(tmp_path, monkeypatch)
    assert response.status_code == 200
    report = response.json()
    assert report['comparison_groups'] == []
    assert 'no_comparison_state' in report['unresolved']
    assert files(report)['knowledge.sqlite3']['status'] == 'missing'
    assert not report['activation_allowed']
    assert 'private-content' not in response.text and 'private-key' not in response.text


@pytest.mark.parametrize('fault,expected', [('symlink','symlink'), ('corrupt','corrupt'),
    ('wal','sidecar_present'), ('new_schema','unsupported_schema')])
def test_unreadable_or_ambiguous_database_never_counts_as_unchanged(tmp_path, monkeypatch, fault, expected):
    data = tmp_path / 'data'
    db(data)
    mark_pending(data, 'synthetic')
    path = data / 'tasks.sqlite3'
    if fault == 'symlink':
        original = tmp_path / 'outside.sqlite3'
        path.rename(original); path.symlink_to(original)
    elif fault == 'corrupt':
        path.write_text('private-corrupt-content')
    elif fault == 'wal':
        path.with_name(path.name + '-wal').write_bytes(b'private-uncheckpointed')
    else:
        with sqlite3.connect(path) as conn:
            conn.execute('PRAGMA user_version=999999')
    response = request(data, monkeypatch)
    assert response.status_code == 200
    result = files(response.json())['tasks.sqlite3']
    assert result['status'] == expected
    assert result.get('tables', []) == []
    assert not response.json()['activation_allowed']
    assert 'private-' not in response.text


def test_authentication_and_closed_body_before_any_preflight(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', TOKEN)
    client = TestClient(create_inspection_app(tmp_path))
    assert client.post('/api/v1/recovery/preflight', json={}).status_code == 401
    assert client.post('/api/v1/recovery/preflight', json={'path': '/tmp'}, headers=HEADERS).status_code == 422
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN')
    client = TestClient(create_inspection_app(tmp_path))
    assert client.post('/api/v1/recovery/preflight', json={}).status_code == 503
    assert list(tmp_path.iterdir()) == []


def test_corrupt_marker_is_not_a_recovery_release(tmp_path, monkeypatch):
    db(tmp_path)
    (tmp_path / 'restore-state.json').write_text('{broken')
    response = request(tmp_path, monkeypatch)
    assert response.status_code == 200
    assert 'invalid_restore_marker' in response.json()['unresolved']
    assert not response.json()['activation_allowed']


def test_equal_rows_after_reordering_and_multiple_groups_are_compared_separately(tmp_path, monkeypatch):
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    path = tmp_path / 'tasks.sqlite3'
    for stamp in (STAMP, '20261104T130000Z'):
        aside = tmp_path / f'tasks.vor-wiederherstellung-{stamp}.sqlite3'
        aside.write_bytes(path.read_bytes())
        with sqlite3.connect(aside) as conn:
            conn.execute('DELETE FROM sample')
            conn.execute('INSERT INTO sample VALUES (?,?)', ('second', None))
            conn.execute('INSERT INTO sample VALUES (?,?)', ('private-key', 'private-content'))
            if stamp == STAMP:
                conn.execute("DELETE FROM sample WHERE id='second'")
        with sqlite3.connect(aside) as conn:
            conn.execute('VACUUM')
    response = request(tmp_path, monkeypatch)
    assert response.status_code == 200
    groups = {g['group']: g for g in response.json()['comparison_groups']}
    first = next(t for t in groups[STAMP]['tables'] if t['table'] == 'sample')
    assert first['same_rows'] == 1 and first['changed_rows'] == 0
    second = next(t for t in groups['20261104T130000Z']['tables'] if t['table'] == 'sample')
    assert second['same_rows'] == 1 and second['only_in_comparison'] == 1
    assert all(g['relationship'] == 'unverified' for g in groups.values())
    assert not response.json()['activation_allowed']


def test_changed_during_scan_discards_comparison_results(tmp_path, monkeypatch):
    from icarus_memory import recovery_preflight as module
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    path = tmp_path / 'tasks.sqlite3'
    (tmp_path / f'tasks.vor-wiederherstellung-{STAMP}.sqlite3').write_bytes(path.read_bytes())
    original = module._tables
    changed = False
    def scan(conn, budget):
        nonlocal changed
        result = original(conn, budget)
        if not changed:
            changed = True
            with sqlite3.connect(path) as writer:
                writer.execute("UPDATE sample SET value='changed privately'")
        return result
    monkeypatch.setattr(module, '_tables', scan)
    report = request(tmp_path, monkeypatch).json()
    assert files(report)['tasks.sqlite3']['status'] == 'changed_during_read'
    assert 'changed_during_read' in report['unresolved']
    assert report['comparison_groups'][0]['tables'] == []


def test_typed_values_and_missing_primary_keys_do_not_report_false_equality(tmp_path, monkeypatch):
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    path = tmp_path / 'tasks.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE no_key (value)')
        conn.execute("INSERT INTO no_key VALUES ('private value')")
    aside = tmp_path / f'tasks.vor-wiederherstellung-{STAMP}.sqlite3'
    aside.write_bytes(path.read_bytes())
    with sqlite3.connect(aside) as conn:
        conn.execute('UPDATE sample SET value=?', (b'private-content',))
        conn.execute('UPDATE no_key SET value=?', ('different private value',))
    report = request(tmp_path, monkeypatch).json()
    tables = {t['table']: t for t in report['comparison_groups'][0]['tables']}
    assert tables['sample']['changed_rows'] == 1
    assert tables['no_key']['changed_rows'] is None
    assert tables['no_key']['status'] == 'unresolved'


def test_bounded_work_and_missing_group_file_do_not_invent_counts(tmp_path, monkeypatch):
    from icarus_memory import recovery_preflight as module
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    (tmp_path / f'einstellungen.vor-wiederherstellung-{STAMP}.json').write_text('{}')
    monkeypatch.setattr(module, 'MAX_ROWS', 0)
    report = request(tmp_path, monkeypatch).json()
    assert files(report)['tasks.sqlite3']['status'] == 'limit_exceeded'
    assert report['comparison_groups'][0]['tables'] == []
    assert next(f for f in report['comparison_groups'][0]['files']
                if f['name'] == 'tasks.sqlite3')['status'] == 'missing'


def test_unauthorized_or_invalid_requests_never_start_scan(tmp_path, monkeypatch):
    from icarus_memory import recovery_preflight as module
    def forbidden(*args, **kwargs):
        raise AssertionError('Unauthorized recovery preflight started')
    monkeypatch.setattr(module, 'preflight', forbidden)
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', TOKEN)
    client = TestClient(create_inspection_app(tmp_path))
    assert client.post('/api/v1/recovery/preflight', json={}).status_code == 401
    assert client.post('/api/v1/recovery/preflight', json={'activate': True}, headers=HEADERS).status_code == 422


def test_unknown_database_schema_is_not_called_verified(tmp_path, monkeypatch):
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    with sqlite3.connect(tmp_path / 'tasks.sqlite3') as conn:
        conn.execute('CREATE VIRTUAL TABLE special USING fts5(text)')
    report = request(tmp_path, monkeypatch).json()
    table = next(t for t in files(report)['tasks.sqlite3']['tables'] if t['table'] == 'special')
    assert table['status'] == 'virtual_table' and table.get('content_sha256') is None


def test_file_limit_bounds_single_large_row_before_sqlite_read(tmp_path, monkeypatch):
    from icarus_memory import recovery_preflight as module
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    monkeypatch.setattr(module, 'MAX_BYTES', 1)
    report = request(tmp_path, monkeypatch).json()
    assert files(report)['tasks.sqlite3']['status'] == 'limit_exceeded'
    assert files(report)['tasks.sqlite3']['tables'] == []


def test_older_python_sqlite_error_api_still_returns_a_bounded_finding(tmp_path, monkeypatch):
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    (tmp_path / 'tasks.sqlite3').write_text('private-corrupt-content')
    monkeypatch.delattr(sqlite3, 'SQLITE_CORRUPT', raising=False)
    monkeypatch.delattr(sqlite3, 'SQLITE_NOTADB', raising=False)
    report = request(tmp_path, monkeypatch).json()
    assert files(report)['tasks.sqlite3']['status'] in ('unreadable', 'corrupt')
    assert not report['activation_allowed']


def test_generated_column_before_primary_key_does_not_conflate_row_identities(tmp_path, monkeypatch):
    mark_pending(tmp_path, 'synthetic')
    path = tmp_path / 'tasks.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE example (value TEXT, generated TEXT GENERATED ALWAYS AS (value) VIRTUAL, id TEXT PRIMARY KEY)')
        conn.execute("INSERT INTO example(value,id) VALUES ('same value','id-before')")
    aside = tmp_path / f'tasks.vor-wiederherstellung-{STAMP}.sqlite3'
    aside.write_bytes(path.read_bytes())
    with sqlite3.connect(aside) as conn:
        conn.execute("UPDATE example SET id='id-after'")
    report = request(tmp_path, monkeypatch).json()
    table = next(t for t in report['comparison_groups'][0]['tables'] if t['table'] == 'example')
    assert table['changed_rows'] == 0
    assert table['only_in_restored'] == 1
    assert table['only_in_comparison'] == 1


def test_directory_read_failure_is_unresolved_without_filesystem_details(tmp_path, monkeypatch):
    from icarus_memory import recovery_preflight as module
    db(tmp_path)
    mark_pending(tmp_path, 'synthetic')
    def denied(*args, **kwargs):
        raise PermissionError('private-path must not appear in the response')
    monkeypatch.setattr(module.os, 'scandir', denied)
    response = request(tmp_path, monkeypatch)
    assert response.status_code == 200
    assert 'unreadable_directory' in response.json()['unresolved']
    assert not response.json()['activation_allowed']
    assert 'private-path' not in response.text
