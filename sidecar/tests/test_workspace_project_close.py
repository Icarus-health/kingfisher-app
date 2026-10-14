from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
from icarus_memory.workspace import ProjectStatus


def client_for(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    return app, TestClient(app)


def test_project_completion_requires_resolving_own_and_waiting_tasks(tmp_path, monkeypatch):
    app, client = client_for(tmp_path, monkeypatch)
    project = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()
    own = client.post('/api/v1/tasks', json={'title': 'Bericht', 'project_id': project['id']}).json()
    waiting = client.post('/api/v1/tasks', json={'title': 'Freigabe', 'project_id': project['id']}).json()
    client.post(f"/api/v1/tasks/{waiting['id']}/warten", json={'name': 'Alex'})
    url = f"/api/v1/projects/{project['id']}"
    result = client.patch(url, json={'status': 'done'})
    assert result.status_code == 409
    assert app.state.workspace.project(project['id']).status is ProjectStatus.ACTIVE
    client.post(f"/api/v1/tasks/{own['id']}/done")
    assert client.patch(url, json={'status': 'done'}).status_code == 409
    client.patch(f"/api/v1/tasks/{waiting['id']}/project", json={'project_id': None})
    assert client.patch(url, json={'status': 'done'}).status_code == 200
    assert client.get('/api/v1/tasks?view=waiting').json()['tasks'][0]['id'] == waiting['id']


def test_closed_project_cannot_receive_new_tasks_but_legacy_open_tasks_stay_visible(tmp_path, monkeypatch):
    app, client = client_for(tmp_path, monkeypatch)
    project = client.post('/api/v1/projects', json={'name': 'Altprojekt'}).json()
    task = client.post('/api/v1/tasks', json={'title': 'Alte offene Aufgabe', 'project_id': project['id']}).json()
    app.state.workspace.update_project(project['id'], status=ProjectStatus.DONE)
    assert client.post('/api/v1/tasks', json={'title': 'Neue Aufgabe', 'project_id': project['id']}).status_code == 409
    assert client.get('/api/v1/tasks?view=mine').json()['tasks'][0]['id'] == task['id']
    assert client.get(f"/api/v1/projects/{project['id']}").json()['tasks'][0]['id'] == task['id']
