from fastapi.testclient import TestClient
from icarus_memory.server import create_app
from icarus_memory.model import Provenance, SourceType


def test_task_history_requires_owner_token(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-history-token')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/tasks/unknown/history').status_code == 401


def test_unknown_task_and_recorded_changes():
    app = create_app()
    with TestClient(app) as client:
        assert client.get('/api/v1/tasks/unknown/history').status_code == 404
        task = app.state.tasks.add('Synthetischer Entwurf', Provenance(source_type=SourceType.USER_STATED))
        app.state.tasks.complete(task.id)
        response = client.get(f'/api/v1/tasks/{task.id}/history')
        assert response.status_code == 200
        data = response.json()
        assert [event['kind'] for event in data['items']] == ['completed', 'created']
        assert all(event['actor_id'] is None for event in data['items'])
        assert data['truncated'] is False
