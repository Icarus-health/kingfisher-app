"""Sicherungsaufträge überleben den App-Neustart ohne Passwort auf Disk."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from icarus_memory.recovery_jobs import RecoveryJobs
from icarus_memory.server import create_app


def test_password_is_claimed_once_and_never_stored(tmp_path):
    jobs = RecoveryJobs(tmp_path/'status.sqlite3')
    assert jobs.claim() is None
    password = 'synthetic-long-secret-password'
    job = jobs.enqueue(password)
    assert password not in json.dumps(jobs.status())
    for file in tmp_path.iterdir():
        assert password.encode() not in file.read_bytes()
    with pytest.raises(ValueError, match='bereits'):
        jobs.enqueue('another-long-password')
    assert jobs.claim() == {'id':job['id'], 'password':password}
    assert jobs.passwords == {}
    restarted = RecoveryJobs(tmp_path/'status.sqlite3')
    assert restarted.status()['job']['status'] == 'running'
    restarted.finish(job['id'], True, '/synthetic/backup.recovery')
    restarted.finish(job['id'], True, '/synthetic/backup.recovery')
    assert restarted.status()['job']['status'] == 'completed'
    assert restarted.claim() is None


def test_pending_password_is_lost_on_restart_and_not_replayed(tmp_path):
    jobs = RecoveryJobs(tmp_path/'status.sqlite3')
    jobs.claim()
    jobs.enqueue('synthetic-long-password')
    restarted = RecoveryJobs(tmp_path/'status.sqlite3')
    assert restarted.status()['job']['status'] == 'failed'
    assert restarted.claim() is None


def test_offline_short_password_and_interrupted_worker(tmp_path):
    jobs = RecoveryJobs(tmp_path/'status.sqlite3')
    with pytest.raises(ValueError):
        jobs.enqueue('synthetic-long-password')
    jobs.claim()
    with pytest.raises(ValueError):
        jobs.enqueue('short')
    assert jobs.status()['job'] is None
    job = jobs.enqueue('synthetic-long-password')
    jobs.claim()
    assert jobs.claim() is None
    assert jobs.status()['job']['status'] == 'failed'
    assert jobs.enqueue('synthetic-retry-password')['id'] != job['id']


def test_cookie_can_request_but_cannot_read_worker_password(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN','synthetic-worker-token')
    ui = tmp_path/'ui';ui.mkdir();(ui/'index.html').write_text('<title>Kingfisher</title>')
    monkeypatch.setenv('ICARUS_UI_DIR',str(ui))
    with TestClient(create_app()) as browser:
        assert browser.get('/api/v1/recovery').status_code == 401
        browser.get('/settings')
        assert browser.get('/api/v1/recovery').status_code == 200
        assert browser.get('/api/v1/recovery/worker').status_code == 401
        header = {'x-icarus-token':'synthetic-worker-token'}
        assert browser.get('/api/v1/recovery/worker',headers=header).json()['job'] is None
        response = browser.post('/api/v1/recovery',json={'password':'synthetic-backup-password'})
        assert response.status_code == 202
        ident = response.json()['id']
        assert 'password' not in browser.get('/api/v1/recovery').text
        claim = browser.get('/api/v1/recovery/worker',headers=header)
        assert claim.headers['cache-control'] == 'no-store'
        assert claim.json()['job']['password'] == 'synthetic-backup-password'
        result = {'id':ident,'success':True,'path':'/synthetic/backup.recovery'}
        assert browser.post('/api/v1/recovery/worker',json=result).status_code == 401
        assert browser.post('/api/v1/recovery/worker',json=result,headers=header).status_code == 200
        assert browser.get('/api/v1/recovery').json()['job']['status'] == 'completed'
