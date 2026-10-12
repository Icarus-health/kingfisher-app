"""Progress must expose the live execution gate, even after a cached model check."""
import pytest
from tests.test_memory_automation import app_client  # noqa: F401


def enabled(app, client):
    app.state.settings.schedule.enabled = True
    app.state.settings.schedule.with_model = True
    app.state.settings.schedule.local_model_only = True
    assert client.get('/api/v1/memory/automation').json()['state'] == 'active'


def test_cached_ready_model_does_not_hide_global_pause_or_resume(app_client, monkeypatch):
    app, client = app_client
    enabled(app, client)
    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model',
                        lambda *_: pytest.fail('automatic progress must not probe a model'))
    assert client.post('/api/v1/hintergrund/pause').status_code == 200
    status = client.get('/api/v1/memory/coverage').json()['automation']
    assert status['state'] == 'active' and status['requested'] is True
    assert 'Pausiert' in (status.get('execution_pause_reason') or '')
    assert client.post('/api/v1/hintergrund/weiter').status_code == 200
    assert client.get('/api/v1/memory/coverage').json()['automation'].get('execution_pause_reason') is None
    assert app.state.settings.schedule.with_model is True


@pytest.mark.parametrize('power, text', [('battery', 'Akkubetrieb'), ('unknown', 'Energiestatus')])
def test_cached_ready_model_does_not_hide_energy_gate(app_client, monkeypatch, power, text):
    app, client = app_client
    enabled(app, client)
    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model',
                        lambda *_: pytest.fail('automatic progress must not probe a model'))
    assert client.post('/api/v1/device/power', json={'source': power}).status_code == 200
    status = client.get('/api/v1/memory/coverage').json()['automation']
    assert text in (status.get('execution_pause_reason') or '')
    assert client.post('/api/v1/device/power', json={'source': 'ac'}).status_code == 200
    assert client.get('/api/v1/memory/coverage').json()['automation'].get('execution_pause_reason') is None


def test_unverified_poll_still_reports_execution_pause_without_model_probe(app_client, monkeypatch):
    app, client = app_client
    app.state.settings.schedule.enabled = app.state.settings.schedule.with_model = True
    app.state.settings.schedule.local_model_only = True
    app.state.hintergrund.pausieren(True)
    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model',
                        lambda *_: pytest.fail('unverified progress must stay model-free'))
    status = client.get('/api/v1/memory/coverage').json()['automation']
    assert status['state'] == 'unverified'
    assert 'Pausiert' in (status.get('execution_pause_reason') or '')
