"""Unsent drafts stay local, survive restart, and never overwrite newer input."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import sqlite3
from threading import Barrier

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from icarus_memory.conversations import ConversationStore


def test_v1_migration_preserves_messages_and_adds_durable_separate_drafts(tmp_path):
    path = tmp_path / 'conversations.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.executescript('''
            CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE INDEX idx_conversation_messages_order ON conversation_messages(conversation_id, created_at, id);
            PRAGMA user_version=1;
        ''')
        connection.execute('INSERT INTO conversations VALUES (?,?,?,?)', ('c-0123456789ab', 'Gespeichert', '2026-11-04T12:00:00+00:00', '2026-11-04T12:00:00+00:00'))
        connection.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?,?,?)', ('m-fixture', 'c-0123456789ab', 'user', 'Gesendete Nachricht', 'complete', '2026-11-04T12:00:00+00:00', '{}'))
    with closing(ConversationStore(path)) as store:
        before = store.get('c-0123456789ab').to_dict()
        assert store.draft_get('c-0123456789ab') == {'text': '', 'revision': 0}
        assert store.draft_put('c-0123456789ab', '  Ungesendeter Entwurf\n', 0) == {'text': '  Ungesendeter Entwurf\n', 'revision': 1}
        assert store.get('c-0123456789ab').to_dict() == before
        assert store.history('c-0123456789ab') == [{'role': 'user', 'content': 'Gesendete Nachricht'}]
        assert store.page(q='Ungesendeter')['total'] == 0
        assert store.list()[0].preview == 'Gesendete Nachricht'
    with closing(ConversationStore(path)) as store:
        assert store.draft_get('c-0123456789ab') == {'text': '  Ungesendeter Entwurf\n', 'revision': 1}
    with sqlite3.connect(path) as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 3
        assert connection.execute('SELECT COUNT(*) FROM conversation_messages').fetchone()[0] == 1


def test_new_draft_does_not_create_conversation_and_empty_tombstone_retains_revision(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        assert store.draft_get('new') == {'text': '', 'revision': 0}
        assert store.draft_put('new', 'Noch nicht gesendet', 0)['revision'] == 1
        assert store.draft_put('new', '', 1) == {'text': '', 'revision': 2}
        assert store.list() == [] and store.latest() is None
        assert store.draft_get('new') == {'text': '', 'revision': 2}


def test_only_exact_previous_revision_with_identical_text_is_idempotent(tmp_path):
    from icarus_memory.conversations import DraftConflict
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        first = store.draft_put('new', 'A', 0)
        assert store.draft_put('new', 'A', 0) == first
        with pytest.raises(DraftConflict): store.draft_put('new', 'B', 0)
        assert store.draft_put('new', 'A', 1)['revision'] == 2
        with pytest.raises(DraftConflict): store.draft_put('new', 'A', 0)
        with pytest.raises(DraftConflict): store.draft_put('new', 'future', 99)
        assert store.draft_get('new') == {'text': 'A', 'revision': 2}
        empty = store.draft_put('new', '', 2)
        assert store.draft_put('new', '', 2) == empty


@pytest.mark.parametrize('revision', [True, False, -1, 1.0, '0', None, 2**63])
def test_store_rejects_non_integer_or_unbounded_revisions(tmp_path, revision):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        with pytest.raises(ValueError): store.draft_put('new', 'Text', revision)
        assert store.draft_get('new')['revision'] == 0


@pytest.mark.parametrize('text', [None, 17, 'x' * 20001])
def test_store_text_is_strict_and_bounded(tmp_path, text):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        with pytest.raises(ValueError): store.draft_put('new', text, 0)
        assert store.draft_put('new', 'x' * 20000, 0)['revision'] == 1


@pytest.mark.parametrize('identifier', ['', 'latest', 'c-bad', 'c-0123456789AB', '../new'])
def test_invalid_composer_id_is_rejected(tmp_path, identifier):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        with pytest.raises(ValueError): store.draft_get(identifier)
        with pytest.raises(ValueError): store.draft_put(identifier, 'Text', 0)


def test_unknown_conversation_does_not_create_or_store_a_draft(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        with pytest.raises(KeyError): store.draft_get('c-ffffffffffff')
        with pytest.raises(KeyError): store.draft_put('c-ffffffffffff', 'Text', 0)
        assert store.list() == []


def test_atomic_compare_and_swap_across_independent_connections(tmp_path):
    from icarus_memory.conversations import DraftConflict
    path = tmp_path / 'chat.sqlite3'
    with closing(ConversationStore(path)) as one, closing(ConversationStore(path)) as two:
        barrier = Barrier(2)
        def write(store, text):
            barrier.wait(timeout=3)
            try: return store.draft_put('new', text, 0)
            except DraftConflict: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(write, one, 'Erster Schreiber'); b = pool.submit(write, two, 'Zweiter Schreiber')
            results = [a.result(timeout=5), b.result(timeout=5)]
        assert sum(result is not None for result in results) == 1
        assert one.draft_get('new') == next(result for result in results if result is not None)


def test_existing_full_backup_restores_drafts_with_the_conversation_database(tmp_path):
    from icarus_memory.backup import restore_all, snapshot_all
    path = tmp_path / 'data/conversations.sqlite3'
    with closing(ConversationStore(path)) as store:
        conversation = store.create('Erhalten')
        store.draft_put(conversation.id, 'Gesicherter Entwurf', 0)
        store.draft_put('new', 'Noch ohne Gespräch', 0)
        saved = snapshot_all(path.parent, tmp_path / 'backups')
    restore_all(saved, tmp_path / 'restored')
    with closing(ConversationStore(tmp_path / 'restored/conversations.sqlite3')) as store:
        assert store.draft_get(conversation.id) == {'text': 'Gesicherter Entwurf', 'revision': 1}
        assert store.draft_get('new') == {'text': 'Noch ohne Gespräch', 'revision': 1}
        assert store.messages(conversation.id) == []


def client_for(store, *, permitted=True):
    from icarus_memory.conversation_draft_routes import register
    app = FastAPI(); app.state.conversations = store
    class ForbiddenLock:
        def __enter__(self): raise AssertionError('Drafts must not acquire the LLM/conversation lock')
        def __exit__(self, *args): pass
    app.state.conversation_lock = ForbiddenLock()
    def guard():
        if not permitted: raise HTTPException(401)
    register(app, [Depends(guard)])
    return TestClient(app)


def test_routes_are_guarded_and_avoid_llm_lock(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        blocked = client_for(store, permitted=False)
        assert blocked.get('/api/v1/conversation-drafts/new').status_code == 401
        assert blocked.put('/api/v1/conversation-drafts/new', json={'text': 'private', 'expected_revision': 0, 'instance_id': 'a' * 32}).status_code == 401
        client = client_for(store)
        initial = client.get('/api/v1/conversation-drafts/new').json()
        assert set(initial) == {'text', 'revision', 'instance_id'}
        assert initial['text'] == '' and initial['revision'] == 0 and len(initial['instance_id']) == 32
        body = {'text': 'Lokaler Entwurf', 'expected_revision': 0, 'instance_id': initial['instance_id']}
        saved = client.put('/api/v1/conversation-drafts/new', json=body)
        assert saved.status_code == 200 and saved.json() == {**initial, 'text': 'Lokaler Entwurf', 'revision': 1}
        assert client.put('/api/v1/conversation-drafts/new', json=body).json() == saved.json()
        conflict = client.put('/api/v1/conversation-drafts/new', json={**body, 'text': 'Ältere andere Eingabe'})
        assert conflict.status_code == 409 and conflict.json()['detail']['code'] == 'draft_conflict'
        assert 'Lokaler Entwurf' not in conflict.text
        assert client.get('/api/v1/conversation-drafts/new').json() == saved.json()


def test_restart_preserves_text_but_old_instance_writes_never_apply(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    with closing(ConversationStore(path)) as first:
        client = client_for(first); before = client.get('/api/v1/conversation-drafts/new').json()
        old = {'text': 'Wieder aufnehmen', 'expected_revision': 0, 'instance_id': before['instance_id']}
        assert client.put('/api/v1/conversation-drafts/new', json=old).status_code == 200
    with closing(ConversationStore(path)) as reopened:
        client = client_for(reopened); current = client.get('/api/v1/conversation-drafts/new').json()
        assert current['text'] == old['text'] and current['revision'] == 1
        assert current['instance_id'] != old['instance_id']
        # Even the exact retry must be rejected across registrations.
        for stale in (old, {**old, 'text': 'Verspätet', 'expected_revision': 1}):
            response = client.put('/api/v1/conversation-drafts/new', json=stale)
            assert response.status_code == 409 and response.json()['detail']['code'] == 'draft_instance_changed'
        assert client.get('/api/v1/conversation-drafts/new').json() == current
        assert client.put('/api/v1/conversation-drafts/new', json={**old, 'text': 'Aktuelle Instanz', 'expected_revision': 1, 'instance_id': current['instance_id']}).status_code == 200


@pytest.mark.parametrize('change', [
    {'expected_revision': True}, {'expected_revision': '0'}, {'expected_revision': 0.0}, {'expected_revision': -1},
    {'text': 42}, {'text': 'x' * 20001}, {'unexpected': 'secret'}, {'instance_id': None},
])
def test_put_schema_is_closed_and_strict(tmp_path, change):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        client = client_for(store); nonce = client.get('/api/v1/conversation-drafts/new').json()['instance_id']
        body = {'text': 'valid', 'expected_revision': 0, 'instance_id': nonce}
        assert client.put('/api/v1/conversation-drafts/new', json=body | change).status_code == 422
        assert store.draft_get('new') == {'text': '', 'revision': 0}


def test_http_ids_are_valid_and_must_refer_to_existing_conversations(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        client = client_for(store); nonce = client.get('/api/v1/conversation-drafts/new').json()['instance_id']
        for identifier, expected in [('latest', 422), ('c-bad', 422), ('c-ffffffffffff', 404)]:
            assert client.get('/api/v1/conversation-drafts/' + identifier).status_code == expected
            assert client.put('/api/v1/conversation-drafts/' + identifier, json={'text': 'Text', 'expected_revision': 0, 'instance_id': nonce}).status_code == expected
        conversation = store.create('Vorhanden')
        assert client.put('/api/v1/conversation-drafts/' + conversation.id, json={'text': 'Zuordnung', 'expected_revision': 0, 'instance_id': nonce}).status_code == 200
        assert store.draft_get(conversation.id)['text'] == 'Zuordnung'


def test_bind_lost_response_is_recoverable_and_does_not_consume_later_new_text(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        store.draft_put('new', '  Erster Versand\n', 0)
        bound = store.draft_bind(1)
        assert bound['handoff']['text'] == '  Erster Versand\n' and bound['handoff']['state'] == 'ready'
        assert store.messages(bound['conversation_id']) == []
        assert store.draft_get('new') == {'text': '', 'revision': 2, 'binding': bound}
        assert store.draft_get(bound['conversation_id']) == {'text': '', 'revision': 0, 'handoff': bound['handoff']}
        assert store.draft_bind(1) == bound
        assert len(store.list()) == 1
        store.draft_put('new', 'Ganz neues Gespräch', 2)
        assert store.draft_bind(1) == bound  # lost response for the exact old step
        newer = store.draft_bind(3)
        assert newer['conversation_id'] != bound['conversation_id']
        assert newer['handoff']['text'] == 'Ganz neues Gespräch'
        assert store.draft_get('new')['binding'] == newer
        assert len(store.list()) == 2


def test_bind_is_atomic_across_windows_and_stale_revision_never_creates(tmp_path):
    from icarus_memory.conversations import DraftConflict
    path = tmp_path / 'chat.sqlite3'
    with closing(ConversationStore(path)) as one, closing(ConversationStore(path)) as two:
        one.draft_put('new', 'Ein Gespräch', 0)
        barrier = Barrier(2)
        def bind(store): barrier.wait(timeout=3); return store.draft_bind(1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(bind, one); b = pool.submit(bind, two)
            assert a.result(timeout=5) == b.result(timeout=5)
        assert len(one.list()) == 1
        with pytest.raises(DraftConflict): one.draft_bind(0)
        with pytest.raises(DraftConflict): one.draft_bind(99)
        assert len(one.list()) == 1


@pytest.mark.parametrize('text', ['', ' \n\t'])
def test_empty_new_draft_cannot_create_empty_conversation(tmp_path, text):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        store.draft_put('new', text, 0)
        with pytest.raises(ValueError): store.draft_bind(1)
        assert store.list() == [] and store.draft_get('new') == {'text': text, 'revision': 1}


def test_handoff_claim_is_single_use_across_restart_and_finish_preserves_followup(tmp_path):
    from icarus_memory.conversations import DraftConflict
    path = tmp_path / 'chat.sqlite3'
    with closing(ConversationStore(path)) as store:
        store.draft_put('new', 'Eingefrorene Frage', 0); bound = store.draft_bind(1)
        cid = bound['conversation_id']; hid = bound['handoff']['id']
        store.draft_put(cid, 'Nachgetippter Folgetext', 0)
        with pytest.raises(DraftConflict): store.draft_handoff_finish(cid, hid)
        claimed = store.draft_handoff_start(cid, hid)
        assert claimed['claimed'] is True and claimed['handoff']['state'] == 'started'
        assert store.draft_handoff_start(cid, hid)['claimed'] is False
    with closing(ConversationStore(path)) as store:
        assert store.draft_handoff_start(cid, hid)['claimed'] is False
        assert store.draft_get(cid)['handoff'] == {'id': hid, 'state': 'started', 'text': 'Eingefrorene Frage'}
        finished = store.draft_handoff_finish(cid, hid)
        assert finished['handoff'] == {'id': hid, 'state': 'accepted', 'text': ''}
        assert store.draft_handoff_finish(cid, hid) == finished
        assert store.draft_bind(1)['handoff'] == finished['handoff']
        assert store._conn.execute('SELECT text FROM conversation_draft_handoffs WHERE id=?', (hid,)).fetchone()[0] == ''
        assert store.draft_handoff_start(cid, hid)['claimed'] is False
        assert store.draft_get(cid) == {'text': 'Nachgetippter Folgetext', 'revision': 1, 'handoff': finished['handoff']}
        assert store.draft_get('new') == {'text': '', 'revision': 2}
        assert store.messages(cid) == []


def test_two_windows_cannot_both_claim_the_same_handoff(tmp_path):
    path = tmp_path / 'chat.sqlite3'
    with closing(ConversationStore(path)) as one, closing(ConversationStore(path)) as two:
        one.draft_put('new', 'Ein Versand', 0); bound = one.draft_bind(1)
        barrier = Barrier(2)
        def start(store):
            barrier.wait(timeout=3)
            return store.draft_handoff_start(bound['conversation_id'], bound['handoff']['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(start, one); b = pool.submit(start, two)
            assert sorted([a.result(timeout=5)['claimed'], b.result(timeout=5)['claimed']]) == [False, True]


def test_handoff_guard_nonce_and_closed_http_protocol(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        client = client_for(store); nonce = client.get('/api/v1/conversation-drafts/new').json()['instance_id']
        store.draft_put('new', 'Zum Senden bereit', 0)
        endpoint = '/api/v1/conversation-drafts/new/bind'
        body = {'instance_id': nonce, 'expected_revision': 1}
        assert client.put(endpoint, json=body).status_code == 405
        assert client.post(endpoint, json={**body, 'text': 'ungeprüfter Text'}).status_code == 422
        assert client.post(endpoint, json={**body, 'expected_revision': True}).status_code == 422
        assert client.post(endpoint, json={**body, 'instance_id': 'f' * 32}).status_code == 409
        response = client.post(endpoint, json=body)
        assert response.status_code == 200
        bound = response.json(); assert bound['instance_id'] == nonce
        assert client.post(endpoint, json=body).json() == bound
        cid = bound['conversation_id']; hid = bound['handoff']['id']
        payload = {'instance_id': nonce, 'handoff_id': hid}
        prefix = '/api/v1/conversation-drafts/' + cid + '/handoff/'
        assert client.post(prefix + 'start', json=payload | {'extra': 1}).status_code == 422
        assert client.post(prefix + 'finish', json=payload).status_code == 409
        assert client.post(prefix + 'start', json=payload).json()['claimed'] is True
        assert client.post(prefix + 'start', json=payload).json()['claimed'] is False
        newer = client_for(store); current = newer.get('/api/v1/conversation-drafts/' + cid).json()
        assert current['instance_id'] != nonce and current['handoff']['state'] == 'started'
        assert newer.post(prefix + 'finish', json=payload).json()['detail']['code'] == 'draft_instance_changed'
        assert newer.post(prefix + 'start', json=payload | {'instance_id': current['instance_id']}).json()['claimed'] is False
        assert newer.post(prefix + 'finish', json=payload | {'instance_id': current['instance_id']}).json()['handoff']['state'] == 'accepted'
        blocked = client_for(store, permitted=False)
        assert blocked.post(endpoint, json=body).status_code == 401
        assert blocked.post(prefix + 'start', json=payload).status_code == 401
        assert blocked.post(prefix + 'finish', json=payload).status_code == 401


def test_handoff_id_cannot_be_claimed_for_another_conversation(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        store.draft_put('new', 'Frage', 0); bound = store.draft_bind(1)
        other = store.create('Anderes Gespräch')
        with pytest.raises(KeyError): store.draft_handoff_start(other.id, bound['handoff']['id'])
        with pytest.raises(KeyError): store.draft_handoff_finish(other.id, bound['handoff']['id'])
        assert store.draft_get(bound['conversation_id'])['handoff']['state'] == 'ready'


def test_failed_binding_rolls_back_chat_handoff_and_new_tombstone_together(tmp_path):
    with closing(ConversationStore(tmp_path / 'chat.sqlite3')) as store:
        store.draft_put('new', 'Bei Fehler erhalten', 0)
        store._conn.execute("""CREATE TEMP TRIGGER fail_handoff BEFORE INSERT ON conversation_draft_handoffs
            BEGIN SELECT RAISE(ABORT, 'synthetic disk write failure'); END""")
        with pytest.raises(sqlite3.IntegrityError): store.draft_bind(1)
        assert store.list() == []
        assert store.draft_get('new') == {'text': 'Bei Fehler erhalten', 'revision': 1}
        store._conn.execute('DROP TRIGGER fail_handoff')
        assert store.draft_bind(1)['handoff']['text'] == 'Bei Fehler erhalten'


def test_v2_migration_and_backup_preserve_drafts_and_started_handoff(tmp_path):
    from icarus_memory.backup import restore_all, snapshot_all
    path = tmp_path / 'data/conversations.sqlite3'
    with closing(ConversationStore(path)) as store:
        store.draft_put('new', 'Vor neuer Übergabeversion', 0)
    # Exact older v2 database: ordinary draft table retained, no handoff table.
    with sqlite3.connect(path) as connection:
        connection.execute('DROP TABLE conversation_draft_handoffs')
        connection.execute('PRAGMA user_version=2')
    with closing(ConversationStore(path)) as store:
        assert store.draft_get('new') == {'text': 'Vor neuer Übergabeversion', 'revision': 1}
        bound = store.draft_bind(1); cid = bound['conversation_id']; hid = bound['handoff']['id']
        store.draft_handoff_start(cid, hid)
        store.draft_put(cid, 'Eigener Folgetext', 0)
        saved = snapshot_all(path.parent, tmp_path / 'backups')
    restore_all(saved, tmp_path / 'restored')
    with closing(ConversationStore(tmp_path / 'restored/conversations.sqlite3')) as store:
        assert store.draft_handoff_start(cid, hid)['claimed'] is False
        assert store.draft_get(cid)['text'] == 'Eigener Folgetext'
        assert store.draft_get(cid)['handoff']['state'] == 'started'
        assert store.draft_get('new')['binding']['conversation_id'] == cid
        assert store.page(q='Vor neuer Übergabeversion')['total'] == 0
