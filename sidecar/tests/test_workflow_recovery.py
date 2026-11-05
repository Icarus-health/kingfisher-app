"""Recovered learning remains inspectable without restoring execution authority."""
import json
import sqlite3

from fastapi.testclient import TestClient

from icarus_memory import server
from icarus_memory.recovery_bundle import export_bundle, restore_bundle
from tests.test_workflow_learning import CORRECTION, feedback, flow


def test_encrypted_recovery_exposes_workflows_and_corrections_without_reactivation(flow, tmp_path, monkeypatch):
    app, client, provider = flow
    records = [feedback(flow, number)[0] for number in range(3)]
    identifier = records[-1]['lernen']['proposal_id']
    assert client.post(f'/api/v1/procedures/{identifier}/accept').status_code == 200
    source = app.state.procedures.get(identifier)
    assert source['state'] == 'active' and len(source['sources']) == 3
    app.state.rueckmeldungen.save_workflow_result('synthetic-negative', {'status': 'no_pattern'})
    data = app.state.episodes._path.parent
    config = tmp_path / 'synthetic-recovery.env'
    config.write_text('ICARUS_SIDECAR_TOKEN=synthetic-recovery-token\n')
    package = export_bundle(data, config, tmp_path / 'workflows.recovery', 'synthetic-recovery-password')
    restored = restore_bundle(package, tmp_path / 'historical', 'synthetic-recovery-password')
    # Negative decisions/cache records survive too, without being replayed.
    def checks(directory):
        with sqlite3.connect((directory / 'rueckmeldungen.sqlite3').as_uri() + '?mode=ro', uri=True) as conn:
            return conn.execute('SELECT request_key,result FROM workflow_checks ORDER BY request_key').fetchall()
    assert checks(restored / 'data') == checks(data)
    assert checks(data)

    monkeypatch.setenv('ICARUS_DATA_DIR', str(restored / 'data'))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-recovery-token')
    def forbidden(*args, **kwargs):
        raise AssertionError('Historical inspection must not initialize models or credentials')
    monkeypatch.setattr(server, '_build_agent', forbidden)
    monkeypatch.setattr(server, 'load_into_env', forbidden)
    headers = {'x-icarus-token': 'synthetic-recovery-token'}
    with TestClient(server.create_app()) as historical:
        state = historical.get('/api/v1/recovery/status', headers=headers).json()
        assert {'procedures.sqlite3', 'rueckmeldungen.sqlite3'} <= set(state['stores'])
        assert state['operational'] is False
        for store in ('procedures.sqlite3', 'rueckmeldungen.sqlite3'):
            assert historical.get('/api/v1/recovery/records', params={'store': store}).status_code == 401
        response = historical.get('/api/v1/recovery/records', params={'store': 'procedures.sqlite3'}, headers=headers)
        assert response.status_code == 200
        row = next(item for item in response.json()['items'] if item['id'] == identifier)
        assert row['state'] == 'active', 'Historical state is preserved, not present execution permission'
        assert json.loads(row['sources']) == source['sources']
        assert response.json()['historical'] and not response.json()['operational']
        response = historical.get('/api/v1/recovery/records', params={'store': 'rueckmeldungen.sqlite3'}, headers=headers)
        assert response.status_code == 200
        assert {item['id'] for item in response.json()['items']} == {item['meldung']['id'] for item in records}
        assert all(item['richtig'] == CORRECTION for item in response.json()['items'])
        for path in (f'/api/v1/procedures/{identifier}/accept', '/api/v1/procedure-learning/start', '/schedule/run'):
            assert historical.post(path, json={}, headers=headers).status_code == 423
        assert historical.get('/api/v1/recovery/records', params={'store': 'schluessel.icarus'}, headers=headers).status_code == 404
    assert len(provider.seen) == 1, 'Restoration itself performs no model work'
