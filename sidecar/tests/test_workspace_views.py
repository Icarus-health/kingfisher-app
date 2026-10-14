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


def test_group_store_undo_rechecks_members_without_writing_history_on_conflict(client):
    from icarus_memory.workspace_views import ViewChanged
    views = client.app.state.workspace_views
    views.put('organisation_group', 'g1', {'name': 'Erste', 'members': ['a', 'b']}, 0)
    views.put('organisation_group', 'g1', {'name': 'Erste', 'members': ['a', 'c']}, 1)
    views.put('organisation_group', 'g2', {'name': 'Zweite', 'members': ['b', 'd']}, 0)
    with pytest.raises(ViewChanged):
        views.undo('organisation_group', 'g1', 2)
    current = views.get('organisation_group', 'g1')
    assert current['revision'] == 2 and current['data']['members'] == ['a', 'c']
    # Store-Konsistenz separat von der zusätzlichen Quellenprüfung des HTTP-Undos.
    views.undo('organisation_group', 'g2', 1)
    restored = views.undo('organisation_group', 'g1', 2)
    assert restored['revision'] == 3 and restored['data']['members'] == ['a', 'b']


def test_generic_group_write_cannot_bypass_membership_guard(client):
    body = {'revision': 0, 'data': {'name': 'Erste', 'members': ['a', 'b']}}
    assert client.put('/api/v1/workspace-view/organisation_group/first', json=body).status_code == 200
    body['data'] = {'name': 'Zweite', 'members': ['b', 'c']}
    assert client.put('/api/v1/workspace-view/organisation_group/second', json=body).status_code == 409


def test_group_membership_guard_covers_records_beyond_overview_limit(tmp_path):
    from icarus_memory.workspace_views import WorkspaceViews, ViewChanged
    views = WorkspaceViews(tmp_path/'views.sqlite3')
    try:
        for index in range(2001):
            views.put('organisation_group', f'g-{index:04}', {'name': str(index), 'members': [f'm-{index}']}, 0)
        with pytest.raises(ViewChanged):
            views.put('organisation_group', 'other', {'name': 'Andere', 'members': ['m-2000']}, 0)
    finally:
        views.close()
def test_metadata_backup_restores_images_folders_revisions_and_undo(tmp_path):
    import base64
    from icarus_memory.workspace_views import WorkspaceViews
    from icarus_memory.backup import snapshot_all, restore_all, verify_snapshot_set
    data=tmp_path/'data'
    views=WorkspaceViews(data/'workspace-views.sqlite3')
    views.put('folder','docs',{'name':'Dokumente','parent_id':None},0)
    views.put('folder','docs',{'name':'Verträge','parent_id':None},1)
    image='data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\nsynthetic').decode()
    views.put('avatar','person-test',{'data_url':image},0)
    saved=snapshot_all(data,tmp_path/'backups')
    assert 'workspace-views.sqlite3' in {row['name'] for row in verify_snapshot_set(saved)}
    restore_all(saved,tmp_path/'restored')
    restored=WorkspaceViews(tmp_path/'restored'/'workspace-views.sqlite3')
    assert restored.get('folder','docs')['revision']==2
    assert restored.get('avatar','person-test')['data']['data_url']==image
    assert restored.undo('folder','docs',2)['data']['name']=='Dokumente'
    restored.close();views.close()
