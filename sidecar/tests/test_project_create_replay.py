from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app


def test_retried_project_creation_is_one_project_and_payload_conflicts_are_visible(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    client = TestClient(create_app(SelfModelStore(MemoryBackend(), subject_id='test')))
    payload = {'name':'Atlas', 'description':'Vertrag', 'request_id':'fd761f9d-9fc6-4ef8-ae7f-0bbb1808cb75'}
    first = client.post('/api/v1/projects', json=payload)
    second = client.post('/api/v1/projects', json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()['id'] == second.json()['id']
    assert len(client.get('/api/v1/projects').json()) == 1
    assert client.post('/api/v1/projects',json={**payload,'name':'Anderes'}).status_code == 409
