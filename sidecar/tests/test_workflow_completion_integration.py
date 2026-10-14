"""Gesamtserver: neue lokale Routen und widerrufbare Hintergrundfreigabe."""
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
from .test_memory_automation import app_client


def test_new_routes_use_real_registration_and_existing_auth(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-only')
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    with TestClient(app) as client:
        paths = ['/api/v1/organisation-group-suggestions', '/api/v1/workspace-documents',
                 '/api/v1/workspace-document-folders']
        for path in paths:
            assert client.get(path).status_code == 401
            assert client.get(path, headers={'x-icarus-token': 'synthetic-only'}).status_code == 200
        path = '/api/v1/local-mail/missing/workflow'
        assert client.get(path).status_code == 401
        assert client.get(path, headers={'x-icarus-token': 'synthetic-only'}).status_code == 404


@pytest.mark.parametrize('change', ['pause', 'disabled', 'model', 'provider', 'generation', 'agent', 'scheduler_stop'])
def test_saved_mail_background_receives_raw_provider_and_rechecks_freedom(app_client, monkeypatch, change):
    from icarus_memory import server, local_mail_workflow, task_project_hints
    app, _ = app_client
    plan = app.state.settings.schedule
    plan.enabled = plan.with_model = plan.local_model_only = True
    provider = app.state.agent.provider
    scheduler_allowed = [True]
    app.state.scheduler.prompt_allowed = lambda: scheduler_allowed[0]
    captured = {}
    class Detector:
        def __init__(self, *args, **kwargs): pass
        def run(self, **kwargs):
            return SimpleNamespace(available=True, cancelled=False, analyzed=0, proposed=0, failed=0)
    monkeypatch.setattr(server, 'TaskDetector', Detector)
    monkeypatch.setattr(task_project_hints.TaskProjectHints, 'prepare', lambda *a, **k: None)
    monkeypatch.setattr(local_mail_workflow, 'prepare_background',
        lambda app, raw, **kwargs: captured.update(provider=raw, **kwargs))
    server._wire_scheduler(app)
    app.state.scheduler._run_task_detection(True)
    assert captured['provider'] is provider and captured['limit'] == 1
    assert captured['permitted']()
    if change == 'pause': plan.with_model = False
    elif change == 'disabled': plan.enabled = False
    elif change == 'model': provider.model = 'changed'
    elif change == 'provider': app.state.agent.provider = SimpleNamespace(is_local=True, model='other')
    elif change == 'generation': app.state.local_model_automation_generation += 1
    elif change == 'agent': app.state.agent = SimpleNamespace(provider=provider)
    elif change == 'scheduler_stop': scheduler_allowed[0] = False
    assert not captured['permitted']()


def test_saved_mail_background_detects_model_change_during_task_detection(app_client, monkeypatch):
    from icarus_memory import server, local_mail_workflow, task_project_hints
    app, _ = app_client
    app.state.settings.schedule.enabled = app.state.settings.schedule.with_model = True
    provider = app.state.agent.provider
    class Detector:
        def __init__(self, *args, **kwargs): pass
        def run(self, **kwargs):
            provider.model = 'changed-during-detection'
            return SimpleNamespace(available=True, cancelled=False, analyzed=0, proposed=0, failed=0)
    monkeypatch.setattr(server, 'TaskDetector', Detector)
    monkeypatch.setattr(task_project_hints.TaskProjectHints, 'prepare', lambda *a, **k: None)
    monkeypatch.setattr(local_mail_workflow, 'prepare_background', lambda *a, **k: pytest.fail('changed model'))
    server._wire_scheduler(app)
    app.state.scheduler._run_task_detection(True)


@pytest.mark.parametrize('enabled, with_model', [(False, True), (True, False)])
def test_saved_mail_background_does_not_start_while_paused(app_client, monkeypatch, enabled, with_model):
    from icarus_memory import server, local_mail_workflow, task_project_hints
    app, _ = app_client
    app.state.settings.schedule.enabled = enabled
    app.state.settings.schedule.with_model = with_model
    class Detector:
        def __init__(self, *args, **kwargs): pass
        def run(self, **kwargs):
            return SimpleNamespace(available=True, cancelled=False, analyzed=0, proposed=0, failed=0)
    monkeypatch.setattr(server, 'TaskDetector', Detector)
    monkeypatch.setattr(task_project_hints.TaskProjectHints, 'prepare', lambda *a, **k: None)
    monkeypatch.setattr(local_mail_workflow, 'prepare_background', lambda *a, **k: pytest.fail('paused mail preparation'))
    server._wire_scheduler(app)
    app.state.scheduler._run_task_detection(True)
