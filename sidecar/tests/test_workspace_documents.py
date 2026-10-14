"""Vollständiger synthetischer Dokumentbestand statt Graph- oder Metadatenvorschau."""
import json
import threading
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory.episodes import EpisodeStore, EpisodeKind, EpisodeState
from icarus_memory.model import Provenance, SourceType
from icarus_memory.workspace import WorkspaceStore, ProjectStatus
from icarus_memory.workspace_views import WorkspaceViews


@pytest.fixture
def inventory(tmp_path):
    from icarus_memory.workspace_documents import register
    app = FastAPI()
    app.state.episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    app.state.workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    app.state.workspace_views = WorkspaceViews(tmp_path / 'views.sqlite3')
    app.state.conversation_lock = threading.RLock()
    register(app, [])
    yield TestClient(app), app.state
    app.state.workspace_views.close()
    app.state.workspace.close()
    app.state.episodes.close()


def doc(state, index, **kwargs):
    return state.episodes.record(EpisodeKind.DOCUMENT, f'Dokument {index}',
        f'Synthetischer Inhalt {index}', Provenance(SourceType.DOCUMENT),
        at=datetime(2020, 1, 1, tzinfo=timezone.utc), **kwargs)[0]


def test_complete_pagination_and_unicode_body_search(inventory):
    client, state = inventory
    sources = [doc(state, index) for index in range(63)]
    note = state.workspace.add_note('Notiz', 'Straße / ÜBERGABE %_ weiter', Provenance(SourceType.USER_STATED))
    first = client.get('/api/v1/workspace-documents', params={'limit': 25}).json()
    second = client.get('/api/v1/workspace-documents', params={'limit': 25, 'offset': 25}).json()
    third = client.get('/api/v1/workspace-documents', params={'limit': 25, 'offset': 50}).json()
    assert (first['total'], first['has_more'], second['has_more'], third['has_more']) == (64, True, True, False)
    assert len({item['id'] for page in (first, second, third) for item in page['items']}) == 64
    assert third['offset'] == 50 and third['limit'] == 25
    found = client.get('/api/v1/workspace-documents', params={'q': 'STRASSE / übergabe %_'}).json()
    assert [item['id'] for item in found['items']] == ['note:' + note.id]
    assert all('body' not in item and len(item['preview']) <= 240 for page in (first, second, third) for item in page['items'])
    last = third['items'][-1]
    result = client.get('/api/v1/workspace-documents', params={'q': last['title']}).json()
    assert last['id'] in [item['id'] for item in result['items']]
    assert client.get('/api/v1/workspace-documents', params={'offset': 999}).json()['items'] == []


def test_all_assignments_nested_and_unassigned_beyond_metadata_limit(inventory):
    client, state = inventory
    views = state.workspace_views
    views.put('folder', 'root', {'name': 'Oberordner', 'parent_id': None}, 0)
    views.put('folder', 'nested', {'name': 'Unterordner', 'parent_id': 'root'}, 0)
    for i in range(2005):
        views.put('source_folder', f'episode:aaa-{i:04}', {'folder_id': 'root'}, 0)
    for i in range(2002):
        views.put('folder', f'aaa-folder-{i:04}', {'name': f'Ordner {i}', 'parent_id': None}, 0)
    source = doc(state, 1)
    other = doc(state, 2)
    views.put('source_folder', 'episode:' + source.id, {'folder_id': 'nested'}, 0)
    page = client.get('/api/v1/workspace-documents', params={'folder_id': 'root'}).json()
    assert [item['id'] for item in page['items']] == ['episode:' + source.id]
    assert len(page['options']['folders']) == 2004
    assert client.get('/api/v1/workspace-documents', params={'folder_id': 'unassigned'}).json()['items'][0]['id'] == 'episode:' + other.id
    views.put('source_folder', 'episode:' + source.id, {'folder_id': None}, 1)
    assert client.get('/api/v1/workspace-documents', params={'folder_id': 'root'}).json()['total'] == 0
    assert client.get('/api/v1/workspace-documents', params={'folder_id': 'unassigned'}).json()['total'] == 2


def test_projects_closed_history_and_current_category_corrections(inventory):
    from icarus_memory.memory_categories import Categories
    from icarus_memory.working_memory_store import source_fingerprint
    client, state = inventory
    project = state.workspace.add_project('Historisches Projekt', Provenance(SourceType.USER_STATED), area='health', status=ProjectStatus.DONE)
    episode = doc(state, 42, project_id=project.id)
    category = Categories(state.episodes)
    snapshot = category.memory._snapshot(episode.id)
    category._write(snapshot, category.taxonomy()['version'], [('work', 0, 8)], [], 'synthetic')
    assert client.get('/api/v1/workspace-documents', params={'source_area': 'work'}).json()['total'] == 1
    category.correct(episode.id, ['personal'])
    assert client.get('/api/v1/workspace-documents', params={'source_area': 'work'}).json()['total'] == 0
    page = client.get('/api/v1/workspace-documents', params={'project_id': project.id, 'project_area': 'health', 'source_area': 'personal'}).json()
    assert page['total'] == 1 and page['items'][0]['project_id'] == project.id
    assert page['options']['projects'] == [{'id': project.id, 'name': project.name, 'status': 'done'}]
    assert page['options']['source_areas'] == [{'id': 'personal', 'label': 'Persönliches'}]
    # Eine explizite leere Korrektur verdrängt weiterhin automatische Themen.
    category.correct(episode.id, [])
    assert client.get('/api/v1/workspace-documents', params={'source_area': 'work'}).json()['total'] == 0
    assert client.get('/api/v1/workspace-documents').json()['options']['source_areas'] == []


def test_current_exclusions_source_change_and_note_freshness(inventory):
    client, state = inventory
    old = doc(state, 1, source_key='file:versioned')
    new = doc(state, 2, source_key='file:versioned')
    state.episodes.advance_source_head('file:versioned', None, old.id)
    state.episodes.advance_source_head('file:versioned', old.id, new.id)
    ignored = doc(state, 3)
    state.episodes.ignore(ignored.id)
    archived = doc(state, 4)
    archived.state = EpisodeState.ARCHIVED
    state.episodes._put(archived)
    state.episodes.record(EpisodeKind.MESSAGE, 'Mail', 'Keine Dokumentquelle', Provenance(SourceType.EMAIL))
    state.episodes.record(EpisodeKind.DOCUMENT, 'Eigene Suchfrage', 'Suchfrage', Provenance(SourceType.USER_STATED), tags=['conversation:memory-lookup'])
    note = state.workspace.add_note('Notiz', 'alter Text', Provenance(SourceType.USER_STATED))
    assert {item['id'] for item in client.get('/api/v1/workspace-documents').json()['items']} == {'episode:' + new.id, 'note:' + note.id}
    state.workspace.update_note(note.id, body='aktueller Text')
    assert client.get('/api/v1/workspace-documents', params={'q': 'alter Text'}).json()['total'] == 0
    page = client.get('/api/v1/workspace-documents', params={'q': 'aktueller Text'}).json()
    assert page['items'][0]['revision'] == 2
    state.episodes.ignore(new.id)
    assert client.get('/api/v1/workspace-documents', params={'q': 'Dokument'}).json()['total'] == 0


@pytest.mark.parametrize('params', [{'limit': 0}, {'limit': 101}, {'offset': -1}, {'offset': '1.5'}, {'offset': 100000001}, {'q': 'x' * 201}, {'folder_id': 'x' * 1001}, {'source_area': 'x' * 1001}])
def test_invalid_query_bounds_are_rejected(inventory, params):
    client, _ = inventory
    assert client.get('/api/v1/workspace-documents', params=params).status_code == 422


def test_database_failure_returns_safe_terminal_error(inventory, monkeypatch):
    import icarus_memory.workspace_documents as module
    client, _ = inventory
    def broken(*args, **kwargs):
        raise RuntimeError('sensitive database path')
    monkeypatch.setattr(module, 'document_page', broken)
    reply = client.get('/api/v1/workspace-documents')
    assert reply.status_code == 503
    assert 'sensitive' not in reply.text


def test_category_freshness_source_integrity_and_long_document(inventory):
    from icarus_memory.memory_categories import Categories
    from icarus_memory.episodes import digest_of
    client, state = inventory
    episode = doc(state, 88)
    categories = Categories(state.episodes)
    categories.correct(episode.id, ['work'])
    assert client.get('/api/v1/workspace-documents', params={'source_area': 'work'}).json()['total'] == 1
    episode.body = 'Aktueller Inhalt statt früherer Grundlage'
    episode.digest = digest_of(episode.body)
    state.episodes._put(episode)
    with state.episodes._lock, state.episodes._conn:
        state.episodes._conn.execute('UPDATE episodes SET body=?,digest=? WHERE id=?', (episode.body, episode.digest, episode.id))
    assert client.get('/api/v1/workspace-documents', params={'source_area': 'work'}).json()['total'] == 0
    assert client.get('/api/v1/workspace-documents', params={'q': 'Aktueller Inhalt'}).json()['total'] == 1
    # Unstimmiges Original darf selbst ohne Bereichsfilter nicht als aktuell erscheinen.
    with state.episodes._lock, state.episodes._conn:
        state.episodes._conn.execute('UPDATE episodes SET body=? WHERE id=?', ('abweichende Kopie', episode.id))
    assert client.get('/api/v1/workspace-documents').json()['total'] == 0
    long = state.episodes.record(EpisodeKind.DOCUMENT, 'Langes Dokument', 'x' * 100_000 + 'Schlussfund', Provenance(SourceType.DOCUMENT))[0]
    result = client.get('/api/v1/workspace-documents', params={'q': 'schlussfund'}).json()
    assert result['total'] == 1 and result['items'][0]['id'] == 'episode:' + long.id
    assert 'Schlussfund' in result['items'][0]['preview'] and len(result['items'][0]['preview']) <= 240


def test_folder_metadata_endpoint_is_complete_and_source_assignment_revision_current(inventory):
    client, state = inventory
    for i in range(2001):
        state.workspace_views.put('folder', f'f-{i:04}', {'name': f'Ordner {i}', 'parent_id': None}, 0)
    response = client.get('/api/v1/workspace-document-folders').json()
    assert len(response['folders']) == 2001
    source = doc(state, 1)
    state.workspace_views.put('source_folder', 'episode:' + source.id, {'folder_id': 'f-2000'}, 0)
    first = client.get('/api/v1/workspace-documents').json()['items'][0]
    assert first['folder_id'] == 'f-2000' and first['source_folder_revision'] == 1
    state.workspace_views.undo('source_folder', 'episode:' + source.id, 1)
    second = client.get('/api/v1/workspace-documents').json()['items'][0]
    assert second['folder_id'] is None and second['source_folder_revision'] == 2


def test_both_read_endpoints_use_the_supplied_guard(tmp_path):
    from fastapi import Depends, HTTPException
    from icarus_memory.workspace_documents import register
    app = FastAPI()
    def deny():
        raise HTTPException(401, 'Freigabe fehlt')
    register(app, [Depends(deny)])
    client = TestClient(app)
    assert client.get('/api/v1/workspace-documents').status_code == 401
    assert client.get('/api/v1/workspace-document-folders').status_code == 401
