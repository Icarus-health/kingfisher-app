"""Actual app registration, restart and draft-bound message protection."""
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app


def test_registered_drafts_survive_restart_and_reject_old_message_origin(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-draft-test')
    headers = {'x-icarus-token': 'synthetic-draft-test'}
    first = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    with TestClient(first) as client:
        assert client.get('/api/v1/conversation-drafts/new').status_code == 401
        initial = client.get('/api/v1/conversation-drafts/new', headers=headers).json()
        body = {'text': 'Künstlicher lokaler Startentwurf', 'expected_revision': 0, 'instance_id': initial['instance_id']}
        saved = client.put('/api/v1/conversation-drafts/new', headers=headers, json=body)
        assert saved.status_code == 200
        bound = client.post('/api/v1/conversation-drafts/new/bind', headers=headers,
            json={'instance_id': initial['instance_id'], 'expected_revision': saved.json()['revision']}).json()
        conversation_id = bound['conversation_id']
        assert first.state.conversations.messages(conversation_id) == []
        assert first.state.conversations.history(conversation_id) == []

    second = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    with TestClient(second) as client:
        restored = client.get(f'/api/v1/conversation-drafts/{conversation_id}', headers=headers).json()
        assert restored['handoff']['text'] == body['text']
        assert restored['handoff']['state'] == 'ready'
        assert restored['instance_id'] != initial['instance_id']
        # The guard precedes both conversation lookup and the model lock, even
        # if a different data instance happens to contain the same conversation.
        class ForbiddenLock:
            def __enter__(self): raise AssertionError('Stale draft must never reach model work')
            def __exit__(self, *args): pass
        second.state.conversation_lock = ForbiddenLock()
        response = client.post(f'/api/v1/conversations/{conversation_id}/messages',
            headers={**headers, 'X-Kingfisher-Draft-Instance': initial['instance_id']},
            json={'message': body['text']})
        assert response.status_code == 409
        assert response.json()['detail']['code'] == 'draft_instance_changed'
        assert second.state.conversations.messages(conversation_id) == []
        assert client.post('/api/v1/conversations/c-000000000000/messages',
            headers={**headers, 'X-Kingfisher-Draft-Instance': restored['instance_id']},
            json={'message': 'Nur Routing prüfen'}).status_code == 404
