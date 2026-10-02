"""Projektzuordnung bleibt derselbe Bestand in Aufgaben, Details und Briefing."""
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore


def test_project_task_lifecycle_and_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name': 'Atlas', 'description': 'Lokaler Test'}).json()
    project_id = project['id']
    task = client.post('/api/v1/tasks', json={'title': 'Angebot prüfen', 'project_id': project_id, 'due': '2026-01-01T12:00:00+00:00'}).json()
    task_id = task['id']
    assert client.get(f'/api/v1/projects/{project_id}').json()['tasks'][0]['id'] == task_id
    assert client.get(f'/api/v1/tasks?view=mine&project_id={project_id}').json()['tasks'][0]['project_id'] == project_id
    morning = client.get('/api/v1/morning-briefing').json()
    attention = next(row for row in morning['needs_you'] if row['source_ref'] == task_id)
    assert attention['detail'] == 'Projekt: Atlas'
    assert attention['project_id'] == project_id
    client.post(f'/api/v1/tasks/{task_id}/warten', json={'name': 'Alex'})
    client.patch(f'/api/v1/tasks/{task_id}/project', json={'project_id': None})
    waiting = client.get('/api/v1/tasks?view=waiting').json()['tasks'][0]
    assert waiting['wartet_auf'] == 'Alex'
    assert waiting['project_id'] is None
    assert client.get(f'/api/v1/tasks?view=waiting&project_id={project_id}').json()['tasks'] == []
    client.patch(f'/api/v1/tasks/{task_id}/project', json={'project_id': project_id})
    client.patch(f'/api/v1/projects/{project_id}', json={'status': 'done'})
    assert client.get('/api/v1/projects').json() == []
    assert client.get('/api/v1/projects?all=true').json()[0]['status'] == 'done'
    assert client.get(f'/api/v1/tasks?view=waiting&project_id={project_id}').json()['tasks'][0]['id'] == task_id
    # Tatsächlich neue Verbindungen statt nur erneutem HTTP-Aufruf.
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    assert tasks.get(task_id).project_id == project_id
    assert tasks.get(task_id).wartet_auf == 'Alex'
    assert workspace.project(project_id).status.value == 'done'
    tasks.close(); workspace.close()
    client.patch(f'/api/v1/projects/{project_id}', json={'status': 'active'})
    assert client.get('/api/v1/projects').json()[0]['open'] is True


def test_unknown_project_is_rejected_without_losing_task(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    client = TestClient(create_app(SelfModelStore(MemoryBackend(), subject_id='test')))
    assert client.post('/api/v1/projects', json={'name': '   '}).status_code == 422
    assert client.post('/api/v1/tasks', json={'title': 'Test', 'project_id': 'missing'}).status_code == 404
    task = client.post('/api/v1/tasks', json={'title': 'Test'}).json()
    assert client.patch(f'/api/v1/tasks/{task["id"]}/project', json={'project_id': 'missing'}).status_code == 404
    assert client.patch(f'/api/v1/tasks/{task["id"]}/project', json={}).status_code == 422
    assert client.get('/api/v1/tasks').json()['tasks'][0]['project_id'] is None
