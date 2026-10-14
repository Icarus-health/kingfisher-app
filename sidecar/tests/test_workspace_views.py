import pytest
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    return TestClient(create_app(SelfModelStore(MemoryBackend(), subject_id='test')))


def test_view_defaults_and_folder_roundtrip_with_revision_guard(client):
    assert client.get('/api/v1/workspace-view').status_code == 200
    assert client.get('/api/v1/workspace-view').json()['online'] == {'logos': False, 'maps': False}
    create = client.put('/api/v1/workspace-view/folder/f-docs', json={'revision': 0, 'data': {'name': 'Dokumente', 'parent_id': None}})
    assert create.status_code == 200
    folder = create.json()
    assert folder['revision'] == 1
    assert client.put('/api/v1/workspace-view/folder/f-docs', json={'revision': 0, 'data': {'name': 'Veraltet', 'parent_id': None}}).status_code == 409
    assert client.get('/api/v1/workspace-view').json()['folders'][0]['data']['name'] == 'Dokumente'
    assert client.post('/api/v1/workspace-view/folder/f-docs/undo', json={'revision': 1}).status_code == 200
    assert client.get('/api/v1/workspace-view').json()['folders'] == []


def test_folder_parent_cycle_and_missing_parent_rejected(client):
    put = lambda id, revision, parent: client.put(f'/api/v1/workspace-view/folder/{id}', json={'revision': revision, 'data': {'name': id, 'parent_id': parent}})
    assert put('a', 0, 'missing').status_code == 422
    assert put('a', 0, None).status_code == 200
    assert put('b', 0, 'a').status_code == 200
    assert put('a', 1, 'b').status_code == 422


def test_group_is_reversible_metadata_and_place_is_explicit(client):
    group = {'name': 'Amazon', 'members': ['organisation:amazon.de', 'organisation:amazon.com']}
    assert client.put('/api/v1/workspace-view/organisation_group/amazon', json={'revision': 0, 'data': group}).status_code == 200
    assert client.get('/api/v1/workspace-view').json()['organisation_groups'][0]['data'] == group
    assert client.put('/api/v1/workspace-view/place/ort-staufen', json={'revision': 0, 'data': {'lat': 47.882, 'lng': 7.733}}).status_code == 200
    assert client.put('/api/v1/workspace-view/place/ort-invalid', json={'revision': 0, 'data': {'lat': 500, 'lng': 0}}).status_code == 422
    assert client.put('/api/v1/workspace-view/place/ort-bool', json={'revision': 0, 'data': {'lat': True, 'lng': 0}}).status_code == 422
    assert client.put('/api/v1/workspace-view/unknown/id', json={'revision': 0, 'data': {}}).status_code == 422
