"""Exact task navigation must not depend on the first 200 list entries."""
from fastapi.testclient import TestClient
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app


def test_get_exact_task_retains_details_across_waiting_and_completion():
    app = create_app()
    with TestClient(app) as client:
        for number in range(200):
            app.state.tasks.add(f'Ältere Aufgabe {number}', Provenance(source_type=SourceType.USER_STATED))
        task = client.post('/api/v1/tasks', json={'title': 'Angebot prüfen', 'notes': 'Original behalten'}).json()
        listed = client.get('/api/v1/tasks?view=mine').json()['tasks']
        assert len(listed) == 200 and task['id'] not in {item['id'] for item in listed}
        path = '/api/v1/tasks/' + task['id']
        assert client.get(path).status_code == 200
        assert client.get(path).json() == task
        client.post(path + '/warten', json={'name': 'Anna'})
        assert client.get(path).json()['wartet_auf'] == 'Anna'
        client.post(path + '/done')
        loaded = client.get(path).json()
        assert loaded['status'] == 'done'
        assert loaded['notes'] == 'Original behalten'
        assert loaded['provenance'] == task['provenance']
        assert client.get('/api/v1/tasks/missing').status_code == 404
