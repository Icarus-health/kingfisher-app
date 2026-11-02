"""Authenticated native lifecycle HTTP with artificial stores and no listener ports."""
import asyncio
import importlib
import threading

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import httpx
import pytest

from icarus_memory.local_module_controller import MODEL, MODE
from icarus_memory.restore_boundary import RuntimeBoundary, mark_pending
from tests.test_local_module_runtime import managed, env, verified


PREFIX = '/api/v1/modules/local-source/runtime'
HEADERS = {'X-Icarus-Token': 'artificial-admin-token'}


def app_for(factory, boundary=None):
    app = FastAPI()
    async def authorized(request: Request):
        if request.headers.get('X-Icarus-Token') != HEADERS['X-Icarus-Token']:
            raise HTTPException(401, 'Nicht angemeldet.')
    importlib.import_module('icarus_memory.local_module_lifecycle_routes').register(
        app, [Depends(authorized)], runtime_factory=factory, boundary=boundary)
    @app.get('/pulse')
    async def pulse():
        return {'ok': True}
    return app


@pytest.mark.parametrize('method,path', [('GET','/status'), ('POST','/initialize'), ('POST','/shutdown')])
def test_auth_precedes_all_runtime_factory_and_setup_work(method, path):
    with TestClient(app_for(lambda: pytest.fail('unauthorized runtime access'))) as client:
        assert client.request(method, PREFIX + path, json={'control_key': 'private'}).status_code == 401


def test_default_absence_never_starts_any_runtime():
    with TestClient(app_for(lambda: None)) as client:
        status = client.get(PREFIX + '/status', headers=HEADERS)
        assert status.status_code == 200
        assert status.json() == dict(model=MODEL, mode=MODE, configured=False, paired=False,
            broker_running=False, jobs_busy=False, stopping=False, restart_needed=False)
        assert client.post(PREFIX + '/initialize', headers=HEADERS, json={}).status_code == 503
        assert client.post(PREFIX + '/shutdown', headers=HEADERS, json={}).json() == status.json()


def test_explicit_initialize_and_shutdown_use_only_trusted_configuration(managed):
    with TestClient(app_for(lambda: managed['runtime'])) as client:
        assert client.get(PREFIX + '/status', headers=HEADERS).json()['paired'] is False
        assert managed['gateway'].initializations == 0
        initialized = client.post(PREFIX + '/initialize', headers=HEADERS, json={})
        assert initialized.status_code == 200 and initialized.json()['paired'] is True
        assert managed['gateway'].initializations == 1
        assert client.post(PREFIX + '/initialize', headers=HEADERS, json={}).json()['paired'] is True
        assert managed['gateway'].initializations == 1
        stopped = client.post(PREFIX + '/shutdown', headers=HEADERS, json={})
        assert stopped.status_code == 200 and stopped.json()['stopping'] is False
        assert stopped.json()['broker_running'] is False
        assert managed['verified']['requests'] == []


@pytest.mark.parametrize('path,body', [('/initialize', {'model': MODEL}),
    ('/initialize', {'control_key': 'private-secret'}), ('/initialize', {'path': '/private'}),
    ('/shutdown', {'wait_seconds': 9999})])
def test_admin_body_is_closed_and_never_reflects_values(path, body):
    with TestClient(app_for(lambda: pytest.fail('invalid body reached runtime'))) as client:
        response = client.post(PREFIX + path, headers=HEADERS, json=body)
    assert response.status_code == 400
    assert 'private' not in response.text and 'secret' not in response.text


def test_admin_body_limit_and_query_are_sanitized_before_factory():
    with TestClient(app_for(lambda: pytest.fail('invalid request reached runtime'))) as client:
        response = client.post(PREFIX + '/initialize', headers=HEADERS | {'Content-Type': 'application/json'},
                               content=b'private-secret'*1000)
        assert response.status_code == 413
        assert 'private' not in response.text
        response = client.get(PREFIX + '/status?control_key=private-secret', headers=HEADERS)
        assert response.status_code == 400 and 'secret' not in response.text


def test_admin_shutdown_retains_revocation_access_during_restore(managed, tmp_path):
    boundary = RuntimeBoundary(tmp_path / 'boundary')
    managed['runtime'].start()
    mark_pending(boundary.directory, 'artificial restore')
    with TestClient(app_for(lambda: managed['runtime'], boundary)) as client:
        assert client.post(PREFIX + '/initialize', headers=HEADERS, json={}).status_code == 503
        response = client.post(PREFIX + '/shutdown', headers=HEADERS, json={})
        assert response.status_code == 200 and response.json()['broker_running'] is False


def test_runtime_factory_exception_is_fixed_safe_error():
    def factory():
        raise HTTPException(418, 'private-runtime control-key secret')
    with TestClient(app_for(factory)) as client:
        response = client.get(PREFIX + '/status', headers=HEADERS)
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'Unavailable'
    assert 'private' not in response.text and 'secret' not in response.text


def test_blocked_runtime_metadata_leaves_main_event_loop_responsive(managed, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    status = managed['runtime'].status
    def blocked():
        entered.set()
        assert release.wait(3)
        return status()
    async def scenario():
        app = app_for(lambda: managed['runtime'])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://artificial') as client:
            pending = asyncio.create_task(client.get(PREFIX + '/status', headers=HEADERS))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                assert (await asyncio.wait_for(client.get('/pulse'), timeout=.5)).json() == {'ok': True}
            finally:
                release.set()
            assert (await pending).status_code == 200
    with monkeypatch.context() as patch:
        patch.setattr(managed['runtime'], 'status', blocked)
        asyncio.run(scenario())
