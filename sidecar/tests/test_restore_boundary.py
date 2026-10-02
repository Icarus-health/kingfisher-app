"""A historical snapshot never grants current operational authority."""
import json
import threading
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from icarus_memory import server
from icarus_memory.backup import restore_all, snapshot_all
from icarus_memory.recovery_bundle import restore_bundle
from .test_recovery_bundle import sample, PASSWORD


def test_bundle_boots_inspection_before_any_provider_or_connector(tmp_path, monkeypatch):
    bundle, task = sample(tmp_path)
    target = restore_bundle(bundle, tmp_path / 'restored', PASSWORD)
    assert (target / 'data' / 'restore-state.json').exists(), 'Restore lacks a persistent inspection boundary'
    monkeypatch.setenv('ICARUS_DATA_DIR', str(target / 'data'))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-token')
    def forbidden(*args, **kwargs): raise AssertionError('Restored authority must not construct integrations')
    monkeypatch.setattr(server, '_build_agent', forbidden)
    monkeypatch.setattr(server, 'load_into_env', forbidden)
    app = server.create_app()
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/api/v1/recovery/status').status_code == 401
    headers = {'x-icarus-token': 'synthetic-token'}
    state = client.get('/api/v1/recovery/status', headers=headers).json()
    assert state['mode'] == 'inspection' and state['operational'] is False
    for path, body in [('/chat', {'message': 'Was weißt du?'}),
                       ('/schedule/run', {}), ('/tools/senden', {}),
                       ('/summaries/run', {}), ('/consolidate', {})]:
        assert client.post(path, headers=headers, json=body).status_code == 423
    records = client.get('/api/v1/recovery/records?store=tasks.sqlite3', headers=headers).json()
    assert task.title in json.dumps(records, ensure_ascii=False)
    # Fresh process/app construction preserves the same restriction.
    assert TestClient(server.create_app()).post('/chat', headers=headers, json={'message': 'Hallo'}).status_code == 423


def test_full_snapshot_restore_marks_before_operational_reopening(tmp_path):
    bundle, _ = sample(tmp_path)
    snapshot = snapshot_all(tmp_path / 'data', tmp_path / 'snapshots')
    target = tmp_path / 'copy'
    restore_all(snapshot, target)
    assert (target / 'restore-state.json').exists()
    state = json.loads((target / 'restore-state.json').read_text())
    assert state['mode'] == 'inspection'
    assert state['restore_id']


def test_corrupt_restore_marker_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    (tmp_path / 'restore-state.json').write_text('{broken')
    def forbidden(*args): raise AssertionError('Must not build integrations')
    monkeypatch.setattr(server, '_build_agent', forbidden)
    response = TestClient(server.create_app()).post('/chat', json={'message':'Hello'})
    assert response.status_code == 423


def test_restore_boundary_waits_for_active_operation_and_blocks_old_agent(core, tmp_path):
    from icarus_memory import restore_boundary
    gate = restore_boundary.RuntimeBoundary(tmp_path)
    agent = core[0]
    agent._runtime_boundary = gate
    entered, release = threading.Event(), threading.Event()
    def operation():
        with gate.operation():
            entered.set()
            assert release.wait(2)
    thread = threading.Thread(target=operation)
    thread.start()
    assert entered.wait(1)
    assert not gate.try_enter(exclusive=True)
    release.set(); thread.join(2)
    assert gate.try_enter(exclusive=True)
    restore_boundary.mark_pending(tmp_path, 'synthetic')
    gate.leave(exclusive=True)
    with pytest.raises(restore_boundary.RestorePending): agent.send('Hello')
    assert core[1].calls == []


from .test_context_identity import core


def test_in_place_restore_enters_inspection_and_retains_original_files(tmp_path, monkeypatch):
    from .test_conversation_retraction import _make_app, _close_app
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    snapshot = client.post('/backups').json()['name']
    result = client.post('/backups/restore', json={'name': snapshot})
    assert result.status_code == 200
    assert result.json()['mode'] == 'inspection'
    assert client.post('/chat', json={'message':'Hello'}).status_code == 423
    assert client.get('/api/v1/recovery/status').json()['operational'] is False
    assert list(tmp_path.glob('*.vor-wiederherstellung-*'))
    _close_app(app)


def test_busy_request_must_finish_before_restore_replaces_stores(tmp_path, monkeypatch):
    from .test_conversation_retraction import _make_app, _close_app
    from icarus_memory.agent import Turn
    app = _make_app(tmp_path, monkeypatch)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def slow(message):
        started.set()
        assert release.wait(3)
        return Turn(reply='original operation completed')
    app.state.agent.send = slow
    with TestClient(app) as client:
        snapshot = client.post('/backups').json()['name']
        replies = []
        reader = threading.Thread(target=lambda: replies.append(client.post('/chat', json={'message':'Hello'})))
        def restoring():
            replies.append(client.post('/backups/restore', json={'name':snapshot}))
            finished.set()
        reader.start(); assert started.wait(1)
        writer = threading.Thread(target=restoring); writer.start()
        assert not finished.wait(.1)
        assert not (tmp_path / 'restore-state.json').exists()
        release.set(); reader.join(3); writer.join(3)
        assert finished.is_set()
        assert all(response.status_code == 200 for response in replies)
        assert client.post('/chat', json={'message':'Hello'}).status_code == 423
    _close_app(app)


def test_legacy_self_model_restore_is_also_inspection_only(tmp_path, monkeypatch):
    from icarus_memory import SqliteBackend, SelfModelStore, Provenance, SourceType, Kind
    from icarus_memory.backup import snapshot, restore
    data = tmp_path / 'data'
    backend = SqliteBackend(data / 'self-model.sqlite3')
    SelfModelStore(backend, subject_id='test').record('Synthetic preference', Kind.PREFERENCE,
        Provenance(source_type=SourceType.USER_STATED))
    backend.close()
    saved = snapshot(data / 'self-model.sqlite3', tmp_path / 'saved')
    target = tmp_path / 'restored' / 'self-model.sqlite3'
    restore(saved, target)
    monkeypatch.setenv('ICARUS_DATA_DIR', str(target.parent))
    assert TestClient(server.create_app()).post('/chat', json={'message':'Hello'}).status_code == 423


def test_historical_knowledge_records_are_readable_without_becoming_operational(core, tmp_path, monkeypatch):
    from icarus_memory.restore_boundary import mark_pending
    _, _, _, _, accept = core
    accept('project:history', 'HISTORICAL_CLAIM for inspection only')
    mark_pending(tmp_path, 'synthetic')
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    # core stores its knowledge in claims.sqlite3; inspection expects the product filename.
    import shutil
    core[3]._conn.execute('PRAGMA wal_checkpoint(FULL)')
    shutil.copy2(tmp_path / 'claims.sqlite3', tmp_path / 'knowledge.sqlite3')
    client = TestClient(server.create_app())
    response = client.get('/api/v1/recovery/records?store=knowledge.sqlite3')
    assert response.status_code == 200
    assert 'HISTORICAL_CLAIM' in response.text
    assert response.json()['operational'] is False


@pytest.mark.parametrize('legacy', [False, True])
def test_in_place_restore_stops_mcp_and_scheduler_before_file_replacement(tmp_path, monkeypatch, legacy):
    from .test_conversation_retraction import _make_app, _close_app
    from types import SimpleNamespace
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    events=[]
    app.state.mcp = {'synthetic': (SimpleNamespace(stop=lambda: events.append('mcp')), [])}
    app.state.scheduler = SimpleNamespace(stop=lambda: events.append('scheduler'))
    if legacy:
        from icarus_memory import SqliteBackend
        from icarus_memory.backup import snapshot
        backend = SqliteBackend(tmp_path / 'self-model.sqlite3'); backend.close()
        name = snapshot(tmp_path / 'self-model.sqlite3', tmp_path / 'sicherungen').name
    else:
        name = client.post('/backups').json()['name']
    result = client.post('/backups/restore', json={'name':name})
    assert result.status_code == 200
    assert set(events) == {'mcp','scheduler'}
    assert app.state.mcp == {}
    _close_app(app)


def test_rejected_legacy_snapshot_does_not_stop_current_integrations(tmp_path,monkeypatch):
    from .test_conversation_retraction import _make_app, _close_app
    from types import SimpleNamespace
    app=_make_app(tmp_path,monkeypatch);client=TestClient(app);events=[]
    connection=SimpleNamespace(stop=lambda:events.append('mcp'))
    app.state.mcp={'synthetic':(connection,[])}
    app.state.scheduler=SimpleNamespace(stop=lambda:events.append('scheduler'))
    directory=tmp_path/'sicherungen';directory.mkdir(exist_ok=True)
    (directory/'broken.sqlite3').write_text('not a database')
    try:
        response=client.post('/backups/restore',json={'name':'broken.sqlite3'})
        assert response.status_code==409
        assert events==[]
        assert app.state.mcp['synthetic'][0] is connection
        assert not(tmp_path/'restore-state.json').exists()
    finally:_close_app(app)
