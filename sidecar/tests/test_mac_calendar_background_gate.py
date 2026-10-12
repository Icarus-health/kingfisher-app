"""Mac history intake must honor the same pause/power gate as other background jobs."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory.mac_calendar import MacCalendar, WorkerUpdate, install_routes


def setup(tmp_path, reason):
    calendar = MacCalendar(tmp_path / 'calendar.sqlite3')
    generation = calendar.enable()['generation']
    calendar.update(WorkerUpdate(generation=generation, status='granted',
                                calendars=[{'id': 'selected', 'name': 'Synthetisch'}]))
    generation = calendar.select(['selected'])['generation']
    app = FastAPI()
    if reason != 'missing':
        app.state.hintergrund = SimpleNamespace(sperre=lambda: reason)
    # Assertion is on the HTTP contract and absence of real intake, not the gate fake.
    install_routes(app, [], calendar, lambda: None)
    at = datetime(2026, 10, 9, tzinfo=timezone.utc)
    body = {'generation': generation, 'range_from': at.isoformat(),
            'range_to': (at + timedelta(days=1)).isoformat(), 'events': []}
    return app, calendar, body


@pytest.mark.parametrize('reason', ['pausiert', 'akku', 'energie_unbekannt', 'antwort', 'nutzer', 'missing'])
def test_blocked_history_intake_is_rejected_but_live_heartbeat_remains(tmp_path, reason):
    app, calendar, body = setup(tmp_path, reason)
    with TestClient(app) as client:
        assert client.get('/api/v1/mac-calendar').json()['memory_allowed'] is False
        assert client.post('/api/v1/mac-calendar/memory', json=body).status_code == 409
        heartbeat = client.post('/api/v1/mac-calendar/worker', json={
            'generation': body['generation'], 'status': 'granted',
            'calendars': [{'id': 'selected', 'name': 'Synthetisch'}]})
        assert heartbeat.status_code == 200
        assert calendar.public()['online']


def test_current_idle_gate_allows_history_contract(tmp_path):
    app, _, body = setup(tmp_path, None)
    with TestClient(app) as client:
        assert client.get('/api/v1/mac-calendar').json()['memory_allowed'] is True
        assert client.post('/api/v1/mac-calendar/memory', json=body).json() == {'stored': False}


def test_disconnect_between_poll_and_upload_still_rejects(tmp_path):
    app, calendar, body = setup(tmp_path, None)
    with TestClient(app) as client:
        assert client.get('/api/v1/mac-calendar').json()['memory_allowed'] is True
        calendar.disconnect()
        response = client.post('/api/v1/mac-calendar/memory', json=body)
        assert response.status_code == 409


def test_passive_native_poll_does_not_consume_current_permission_request(tmp_path):
    app, calendar, _ = setup(tmp_path, None)
    generation = calendar.enable()['generation']
    with TestClient(app) as client:
        response = client.post('/api/v1/mac-calendar/worker', json={
            'generation': generation, 'status': 'not_determined', 'authorization_attempted': False})
        assert response.status_code == 200
        assert calendar.read()['authorize'] is True
        # Der bestehende Entwicklungsworker bestätigt die Anfrage wie zuvor.
        response = client.post('/api/v1/mac-calendar/worker', json={
            'generation': generation, 'status': 'denied'})
        assert response.status_code == 200
        assert calendar.read()['authorize'] is False


def test_history_error_is_visible_without_invalidating_live_snapshot(tmp_path):
    app, calendar, body = setup(tmp_path, None)
    with TestClient(app) as client:
        response = client.post('/api/v1/mac-calendar/worker', json={
            'generation': body['generation'], 'status': 'granted',
            'calendars': [{'id': 'selected', 'name': 'Synthetisch'}],
            'events': [], 'range_from': body['range_from'], 'range_to': body['range_to'],
            'memory_error': 'Gedächtnisabgleich bitte prüfen.'})
        assert response.status_code == 200
        state = client.get('/api/v1/mac-calendar').json()
        assert state['memory_error'] == 'Gedächtnisabgleich bitte prüfen.'
        assert state['status'] == 'granted' and state['synced_at']
        assert state['error'] == ''
