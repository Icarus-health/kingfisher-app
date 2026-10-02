import base64

from fastapi.testclient import TestClient
import pytest

from icarus_memory.server import create_app
from icarus_memory.proposals import Evidence


def register(client):
    response = client.post('/api/v1/folder-sync/worker', json={'root_id': 'test-root', 'folder': '/test/Kingfisher-Eingang'})
    assert response.status_code == 200
    assert response.json()['enabled'] is False
    response = client.put('/api/v1/folder-sync', json={'enabled': True})
    assert response.status_code == 200
    return response.json()['generation']


def begin(client, generation):
    response = client.post('/api/v1/folder-sync/begin', json={'root_id': 'test-root', 'generation': generation})
    assert response.status_code == 200
    return { 'root_id': 'test-root', 'generation': generation, 'run_id': response.json()['run_id'] }


def upload(client, run, text, filename='meeting.txt'):
    return client.post('/api/v1/folder-sync/files', json={**run, 'filename': filename,
        'content_base64': base64.b64encode(text.encode()).decode()})


def test_opt_in_change_withdrawal_and_duplicate_sources():
    app = create_app()
    with TestClient(app) as client:
        generation = register(client)
        run = begin(client, generation)
        first = upload(client, run, 'Confirmed plan A')
        assert first.status_code == 200, first.text
        old = app.state.episodes.get(first.json()['id'])
        proposal, _ = app.state.knowledge_service.propose(subject_ref='project:qa', predicate='plan', value='A',
            statement='Plan A', rationale='Explicit source', evidence=[Evidence(old.id, old.body, old.digest)], proposed_by='test')
        claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
        again = upload(client, run, 'Confirmed plan A')
        assert again.json()['id'] == old.id and not again.json()['created']
        changed = upload(client, run, 'Corrected plan B')
        assert changed.json()['id'] != old.id
        assert app.state.claims.get(claim.id).status.value != 'active'
        assert app.state.episodes.get(old.id).state.value == 'ignored'
        finish = client.post('/api/v1/folder-sync/finish', json={**run, 'observed': ['meeting.txt'], 'errors': [], 'complete': True})
        assert finish.status_code == 200
        next_run = begin(client, generation)
        removed = client.post('/api/v1/folder-sync/finish', json={**next_run, 'observed': [], 'errors': [], 'complete': True})
        assert removed.status_code == 200
        assert app.state.episodes.get(changed.json()['id']).state.value == 'ignored'


def test_pause_rejects_inflight_data_and_retains_old_source():
    app = create_app()
    with TestClient(app) as client:
        generation = register(client)
        run = begin(client, generation)
        first = upload(client, run, 'First').json()
        assert client.put('/api/v1/folder-sync', json={'enabled': False}).status_code == 200
        assert upload(client, run, 'Late').status_code == 409
        assert app.state.episodes.get(first['id']).state.value != 'ignored'
        assert client.post('/api/v1/folder-sync/finish', json={**run, 'observed': [], 'errors': [], 'complete': True}).status_code == 409


def test_incomplete_scan_never_means_source_disappeared():
    app = create_app()
    with TestClient(app) as client:
        generation = register(client)
        run = begin(client, generation)
        first = upload(client, run, 'Keep').json()
        result = client.post('/api/v1/folder-sync/finish', json={**run, 'observed': [], 'errors': ['Folder unavailable'], 'complete': False})
        assert result.status_code == 200
        assert app.state.episodes.get(first['id']).state.value != 'ignored'
        assert result.json()['last_run']['errors']


def test_transcripts_use_existing_parser_and_paths_are_bounded():
    app = create_app()
    with TestClient(app) as client:
        generation = register(client)
        run = begin(client, generation)
        result = upload(client, run, 'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Lea>Hello\n', 'meeting.vtt')
        assert result.status_code == 200, result.text
        assert 'Lea: Hello' in app.state.episodes.get(result.json()['id']).body
        for filename in ('../secret.txt', '/secret.txt', 'a/../../secret.txt', 'image.exe'):
            assert upload(client, run, 'Not allowed', filename).status_code == 422


def test_folder_endpoints_require_token(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'test-only')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/folder-sync').status_code == 401
        assert client.post('/api/v1/folder-sync/worker', json={'root_id':'x','folder':'/test'}).status_code == 401


def test_invalid_new_file_version_excludes_previous_evidence():
    app = create_app()
    with TestClient(app) as client:
        generation = register(client)
        run = begin(client, generation)
        first = upload(client, run, 'Original').json()
        broken = client.post('/api/v1/folder-sync/files', json={**run, 'filename': 'meeting.txt',
            'content_base64': base64.b64encode(b'\x00\xff').decode()})
        assert broken.status_code == 422
        assert app.state.episodes.get(first['id']).state.value == 'ignored'


def test_removed_files_remain_reviewable_after_scan():
    app = create_app()
    with TestClient(app) as client:
        generation = register(client)
        run = begin(client, generation)
        upload(client, run, 'Original')
        client.post('/api/v1/folder-sync/finish', json={**run, 'observed': [], 'complete': True})
        files = client.get('/api/v1/folder-sync').json()['files']
        assert len(files) == 1 and files[0]['state'] == 'ignored'


def test_unchanged_bytes_do_not_repeat_document_extraction(monkeypatch):
    from icarus_memory import folder_sync
    with TestClient(create_app()) as client:
        run = begin(client, register(client))
        first = upload(client, run, 'Same').json()
        calls = []
        original = folder_sync.extract
        def tracked(*args):
            calls.append(args)
            return original(*args)
        monkeypatch.setattr(folder_sync, 'extract', tracked)
        result = upload(client, run, 'Same')
        assert result.status_code == 200
        assert result.json()['id'] == first['id'] and not result.json()['created']
        assert calls == []


def test_folder_state_and_duplicate_identity_survive_app_restart():
    with TestClient(create_app()) as client:
        generation = register(client)
        run = begin(client, generation)
        first = upload(client, run, 'Persist').json()
        client.post('/api/v1/folder-sync/finish', json={**run, 'observed':['meeting.txt'], 'complete':True})
    with TestClient(create_app()) as restarted:
        state = restarted.get('/api/v1/folder-sync').json()
        assert state['enabled'] and state['files'][0]['id'] == first['id']
        assert upload(restarted, begin(restarted, state['generation']), 'Persist').json()['id'] == first['id']


def test_replaced_folder_withdraws_previous_sources_and_requires_new_consent():
    app = create_app()
    with TestClient(app) as client:
        run = begin(client, register(client))
        first = upload(client, run, 'Old folder').json()
        replaced = client.post('/api/v1/folder-sync/worker', json={'root_id':'replacement', 'folder':'/test/Kingfisher-Eingang'}).json()
        assert not replaced['enabled']
        assert app.state.episodes.get(first['id']).state.value == 'ignored'
