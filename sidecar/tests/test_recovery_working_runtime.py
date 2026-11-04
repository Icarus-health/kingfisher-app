"""A recovered normal app uses fresh instance authority, never inherited keys."""
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess

from fastapi.testclient import TestClient

from icarus_memory import server
from icarus_memory.restore_boundary import pending
from icarus_memory.secrets import Keychain, SERVICE
from .test_recovery_workspace import rich, hashes

INSTANCE = 'a' * 32
TOKEN = 'b' * 64
PASSPHRASE = 's' * 64


def working_data(tmp_path):
    tmp_path = tmp_path.resolve()
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'restore-state.json').write_text(json.dumps({
        'version': 1, 'mode': 'working_copy', 'policy_version': 1,
        'restore_id': INSTANCE, 'source_fingerprint': 'c' * 64,
        'selection': 'restored', 'unknown_history_acknowledged': True,
        'permissions_reset': True, 'operational': True,
    }))
    (data / 'einstellungen.json').write_text('{}')
    (data / 'fassung.json').write_text(json.dumps({'pruefen': False}))
    start = tmp_path / 'settings.env'
    start.write_text(''.join(f'{key}={shlex.quote(value)}\n' for key, value in environment(data).items() if key.startswith('ICARUS_')))
    start.chmod(0o600)
    return data


def environment(data):
    return {'HOME': str(data.parent), 'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
            'ICARUS_DATA_DIR': str(data), 'ICARUS_SIDECAR_TOKEN': TOKEN,
            'ICARUS_SECRETS_PASSPHRASE': PASSPHRASE, 'ICARUS_RECOVERY_BOOT_ID': INSTANCE}


def forbidden(*args, **kwargs):
    raise AssertionError('Recovered startup must not use inherited OS credentials or external work')


def test_working_copy_saves_normal_task_and_reads_it_after_restart(tmp_path, monkeypatch):
    data = working_data(tmp_path)
    monkeypatch.setattr(os, 'environ', environment(data))
    monkeypatch.setattr(Keychain, '_detect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    headers = {'x-icarus-token': TOKEN}
    app = server.create_app()
    try:
        with TestClient(app) as client:
            response = client.post('/api/v1/tasks', json={'title': 'Nach Wiederherstellung weiterarbeiten'}, headers=headers)
            assert response.status_code == 201, response.text
            task = response.json()
            assert client.get('/api/v1/tasks', headers=headers).status_code == 200
            assert app.state.agent.provider is None
            assert app.state.keychain._backend == 'file'
            assert app.state.scheduler._thread is None
            assert not pending(data)
    finally:
        if hasattr(app.state, 'runtime_boundary'):
            server._close_persistent_state(app)
    # New process-like startup receives clean launcher environment, not the
    # environment changed by the first app's normal settings wiring.
    monkeypatch.setattr(os, 'environ', environment(data))
    reopened = server.create_app()
    try:
        with TestClient(reopened) as client:
            response = client.get('/api/v1/tasks/' + task['id'], headers=headers)
            assert response.status_code == 200
            assert response.json()['title'] == 'Nach Wiederherstellung weiterarbeiten'
            assert client.get('/api/v1/tasks').status_code == 401
            assert reopened.state.agent.provider is None
    finally:
        if hasattr(reopened.state, 'runtime_boundary'):
            server._close_persistent_state(reopened)


def test_working_marker_with_inherited_provider_key_stays_inspection_before_start(tmp_path, monkeypatch):
    data = working_data(tmp_path)
    env = environment(data)
    env['OPENAI_API_KEY'] = 'synthetic-old-provider-key'
    monkeypatch.setattr(os, 'environ', env)
    monkeypatch.setattr(server, '_build_agent', forbidden)
    monkeypatch.setattr(server, 'load_into_env', forbidden)
    client = TestClient(server.create_app())
    assert client.get('/health').json()['mode'] == 'inspection'
    assert client.post('/api/v1/tasks', json={'title': 'Must not write'}, headers={'x-icarus-token': TOKEN}).status_code == 423
    assert not (data / 'tasks.sqlite3').exists()


def test_wrong_instance_boot_id_stays_inspection(tmp_path, monkeypatch):
    data = working_data(tmp_path)
    env = environment(data)
    env['ICARUS_RECOVERY_BOOT_ID'] = 'd' * 32
    monkeypatch.setattr(os, 'environ', env)
    monkeypatch.setattr(server, '_build_agent', forbidden)
    assert TestClient(server.create_app()).get('/health').json()['mode'] == 'inspection'


def test_working_keychain_and_fallback_use_only_new_encrypted_store(tmp_path, monkeypatch):
    data = working_data(tmp_path)
    monkeypatch.setattr(os, 'environ', environment(data))
    monkeypatch.setattr(Keychain, '_detect', forbidden)
    first = Keychain()
    assert first.get('OPENAI_API_KEY') is None
    first.set('OPENAI_API_KEY', 'synthetic-explicit-new-key')
    fallback = Keychain()
    assert fallback.get('OPENAI_API_KEY') == 'synthetic-explicit-new-key'
    assert first._backend == fallback._backend == 'file'
    assert first._service == SERVICE + '.recovered.' + INSTANCE
    assert 'synthetic-explicit-new-key' not in (data / 'schluessel.icarus').read_text()


def test_malformed_working_contract_remains_pending(tmp_path, monkeypatch):
    data = working_data(tmp_path)
    state = json.loads((data / 'restore-state.json').read_text())
    state['permissions_reset'] = False
    (data / 'restore-state.json').write_text(json.dumps(state))
    monkeypatch.setattr(os, 'environ', environment(data))
    monkeypatch.setattr(server, '_build_agent', forbidden)
    assert pending(data)
    assert TestClient(server.create_app()).get('/health').json()['mode'] == 'inspection'


def test_prepared_full_copy_uses_normal_routes_without_old_authority(rich, tmp_path, monkeypatch):
    from icarus_memory.recovery_preflight import preflight
    from icarus_memory.recovery_workspace import prepare_working_copy, launch_environment
    from icarus_memory.scheduler import Scheduler
    before = hashes(rich['folder'])
    target = prepare_working_copy(rich['folder'], tmp_path.resolve() / 'working',
        fingerprint=preflight(rich['folder'])['report_fingerprint'],
        selection='restored', acknowledge_unknown=True)
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-inherited-key')
    monkeypatch.setenv('KF_HARNESS_MODE', 'synthetic-inherited-harness')
    clean_environment = launch_environment(target)
    monkeypatch.setattr(os, 'environ', dict(clean_environment))
    monkeypatch.setattr(Keychain, '_detect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(Scheduler, 'start', forbidden)
    headers = {'x-icarus-token': clean_environment['ICARUS_SIDECAR_TOKEN']}
    created_id = None
    for attempt in range(2):
        monkeypatch.setattr(os, 'environ', dict(clean_environment))
        app = server.create_app()
        try:
            with TestClient(app) as client:
                project = client.get('/api/v1/projects/' + rich['project'].id, headers=headers)
                assert project.status_code == 200, project.text
                assert project.json()['name'] == rich['project'].name
                assert any(task['id'] == rich['task'].id for task in project.json()['tasks'])
                original = client.get('/api/v1/episodes/' + rich['source'].id, headers=headers)
                assert original.status_code == 200, original.text
                assert original.json()['body'] == 'Unveränderter Originaltext.'
                withdrawn = client.get('/api/v1/episodes/' + rich['ignored'].id, headers=headers)
                assert withdrawn.status_code == 200, withdrawn.text
                assert withdrawn.json()['state'] == 'ignored'
                assert withdrawn.json()['source_current'] is False
                assert app.state.agent.provider is None
                assert not app.state.tasks.auto_an()
                assert not app.state.regeln.alle(nur_aktive=True)
                assert app.state.keychain.get('OPENAI_API_KEY') is None
                if attempt == 0:
                    result = client.post('/api/v1/tasks', headers=headers, json={
                        'title': 'In der Arbeitskopie ergänzte Aufgabe', 'project_id': rich['project'].id})
                    assert result.status_code == 201, result.text
                    created_id = result.json()['id']
                    # Exercise the existing settings/restore rebuild path too.
                    server._close_persistent_state(app)
                    server._reopen_persistent_state(app)
                    assert app.state.agent.provider is None
                result = client.get('/api/v1/tasks/' + created_id, headers=headers)
                assert result.status_code == 200, result.text
                assert result.json()['project_id'] == rich['project'].id
                assert result.json()['title'] == 'In der Arbeitskopie ergänzte Aufgabe'
        finally:
            if hasattr(app.state, 'runtime_boundary'):
                server._close_persistent_state(app)
    assert hashes(rich['folder']) == before
