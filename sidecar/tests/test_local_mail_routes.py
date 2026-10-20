from types import SimpleNamespace
from datetime import datetime, timezone
import threading
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType

@pytest.fixture
def fixture(tmp_path):
    from icarus_memory.local_mail_routes import register
    app = FastAPI()
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    app.state.episodes = store
    app.state.conversation_lock = threading.RLock()
    app.state.settings = SimpleNamespace(mail_accounts=[SimpleNamespace(id='a', label='Privat'), SimpleNamespace(id='b', label='Arbeit')], mail_sync_status={'a': {'last_success': '2026-10-10T12:00:00Z'}})
    app.state.mail = SimpleNamespace(message=lambda *a: pytest.fail('No provider read'), reader_for=lambda *a: pytest.fail('No reader creation'))
    register(app, [])
    with TestClient(app) as client:
        yield store, client
    store.close()

def mail(store, account, uid, body, date=None, source_key=None):
    from icarus_memory.source_versions import track_source
    key = source_key or f'mail:{account}:{uid}'
    episode = store.record(EpisodeKind.MESSAGE, 'Brief', body, Provenance(source_type=SourceType.EMAIL, source_ref=f'{account}:<same-id@example.com>'), occurred_at=date, participants=['Anna <anna@example.com>'], source_key=key)[0]
    from icarus_memory.claims import ClaimStore
    claims = ClaimStore(store._path.parent / 'claims.sqlite3')
    try:
        track_source(store, claims, key, episode)
    finally:
        claims.close()
    return episode

def test_local_paging_filters_account_content_and_literal_search_without_provider(fixture):
    store, client = fixture
    first = mail(store, 'a', '1', 'Budget 100%_final', datetime(2020,1,1,tzinfo=timezone.utc))
    second = mail(store, 'b', '1', 'Budget second', datetime(2021,1,1,tzinfo=timezone.utc))
    unknown = mail(store, 'a', '2', 'No original date')
    page = client.get('/api/v1/local-mail?limit=1').json()
    assert page['total'] == 3 and page['has_more']
    assert page['items'][0]['episode_id'] == second.id
    assert len(client.get('/api/v1/local-mail?offset=2&limit=1').json()['items']) == 1
    found = client.get('/api/v1/local-mail', params={'account_id': 'a', 'q': '100%_'}).json()
    assert [item['episode_id'] for item in found['items']] == [first.id]
    assert found['items'][0]['account_id'] == 'a'
    assert found['accounts'][0]['last_sync'] == '2026-10-10T12:00:00+00:00'
    undated = client.get('/api/v1/local-mail', params={'q': 'No original date'}).json()['items'][0]
    assert undated['date'] is None and undated['recorded_at']
    assert undated['remote_uid'] is None

def test_local_read_and_search_hide_ignored_and_superseded_sources(fixture):
    store, client = fixture
    original = mail(store, 'a', '1', 'old body', source_key='mail:revision')
    changed = mail(store, 'a', '1', 'current body', source_key='mail:revision')
    # record installs the new source head; no inferred account/UID fusion.
    result = client.get('/api/v1/local-mail').json()
    assert [item['episode_id'] for item in result['items']] == [changed.id]
    assert client.get(f'/api/v1/local-mail/{original.id}').status_code == 409
    detail = client.get(f'/api/v1/local-mail/{changed.id}').json()
    assert detail['body'] == 'current body' and not detail['can_reply']
    store.ignore(changed.id)
    assert client.get('/api/v1/local-mail').json()['total'] == 0
    assert client.get(f'/api/v1/local-mail/{changed.id}').status_code == 409

def test_local_mail_rejects_non_mail_and_invalid_paging(fixture):
    store, client = fixture
    doc = store.record(EpisodeKind.DOCUMENT,'Doc','body',Provenance(source_type=SourceType.DOCUMENT))[0]
    assert client.get(f'/api/v1/local-mail/{doc.id}').status_code == 404
    assert client.get('/api/v1/local-mail?offset=-1').status_code == 422
    assert client.get('/api/v1/local-mail?limit=1001').status_code == 422

def test_missing_original_is_clean_not_found(fixture):
    _, client = fixture
    assert client.get('/api/v1/local-mail/missing').status_code == 404

def test_only_proven_inbox_account_uid_can_enable_remote_actions(fixture):
    from icarus_memory.mail_intake import Intake
    store, client = fixture
    Intake(store)
    inbox = mail(store, 'a', '1', 'Inbox source')
    archived = mail(store, 'a', '2', 'Archive source')
    duplicate = mail(store, 'b', '1', 'Other account')
    with store.transaction():
        for account, folder in [('a','INBOX'),('a','Archive'),('b','INBOX')]:
            store._conn.execute('INSERT INTO mail_intake_folders(account,folder,generation) VALUES(?,?,?)', (account,folder,'123'))
        for account, folder, uid, episode, status in [('a','INBOX',1,inbox,'captured'),('a','Archive',2,archived,'captured'),('b','INBOX',1,duplicate,'duplicate')]:
            store._conn.execute('INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES(?,?,?,?,?,?,?)', (account,folder,'123',uid,'history',status,episode.id))
    assert client.get(f'/api/v1/local-mail/{inbox.id}').json()['remote_uid'] == 'a:123.1'
    assert client.get(f'/api/v1/local-mail/{archived.id}').json()['remote_uid'] is None
    assert client.get(f'/api/v1/local-mail/{duplicate.id}').json()['remote_uid'] == 'b:123.1'
    # Zwei UIDs derselben Generation für eine Quelle: nie eine beliebige wählen.
    with store.transaction():
        store._conn.execute('INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES(?,?,?,?,?,?,?)', ('a','INBOX','123',9,'history','duplicate',inbox.id))
    assert client.get(f'/api/v1/local-mail/{inbox.id}').json()['remote_uid'] is None


def test_remote_uid_gilt_nur_fuer_die_aktuelle_ordnergeneration(fixture):
    # Nach einem UIDVALIDITY-Wechsel zeigt eine alte UID auf eine andere oder keine Mail. Die Aktion darf nur die UID
    # der aktuellen Generation des Ordners nennen, auch wenn die alte Zeile noch als 'captured' dasteht.
    from icarus_memory.mail_intake import Intake
    store, client = fixture
    Intake(store)
    quelle = mail(store, 'a', '1', 'Inbox source')
    with store.transaction():
        store._conn.execute('INSERT INTO mail_intake_folders(account,folder,generation) VALUES(?,?,?)', ('a','INBOX','456'))
        store._conn.execute('INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES(?,?,?,?,?,?,?)', ('a','INBOX','123',1,'history','captured',quelle.id))
    # Die neue Bestandsaufnahme hat die Mail noch nicht erreicht: keine Aktion statt einer veralteten UID.
    assert client.get(f'/api/v1/local-mail/{quelle.id}').json()['remote_uid'] is None
    with store.transaction():
        store._conn.execute('INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES(?,?,?,?,?,?,?)', ('a','INBOX','456',7,'history','duplicate',quelle.id))
    # Wiedergefunden in der neuen Generation: genau ihre UID, nicht die alte und nicht „keine“.
    assert client.get(f'/api/v1/local-mail/{quelle.id}').json()['remote_uid'] == 'a:456.7'
    assert client.get('/api/v1/local-mail').json()['items'][0]['remote_uid'] == 'a:456.7'

def test_content_search_matches_unicode_case_and_manual_known_sync(fixture):
    from icarus_memory.mail_stand import merke_gelesen
    store, client = fixture
    mail(store,'a','1','ÄRZTLICHE Rückmeldung')
    app = client.app
    merke_gelesen(app, {'a':1}, zeit=datetime(2026,10,14,12,tzinfo=timezone.utc))
    result = client.get('/api/v1/local-mail',params={'q':'ärztliche'}).json()
    assert result['total'] == 1
    assert result['accounts'][0]['last_sync'] == '2026-10-14T12:00:00+00:00'

def test_routes_retain_shared_authentication_guard():
    from fastapi import Depends, HTTPException
    from icarus_memory.local_mail_routes import register
    app = FastAPI()
    def deny():
        raise HTTPException(403, 'Not permitted')
    # No episode store exists: the guard must run before any source read.
    register(app, [Depends(deny)])
    with TestClient(app) as client:
        assert client.get('/api/v1/local-mail').status_code == 403
        assert client.get('/api/v1/local-mail/original').status_code == 403
