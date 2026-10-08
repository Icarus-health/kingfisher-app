"""Thread context is exact, account-scoped, source-dated and read-only."""
from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import remember
from icarus_memory.server import create_app


def mail(uid, *, account='work', mid='', reply='', body='Bitte den Entwurf prüfen.', day=1, subject='Entwurf'):
    return Message(uid=f'{account}:{uid}', account_id=account, message_id=mid, in_reply_to=reply,
                   subject=subject, sender='Anna <anna@example.test>', body=body, preview='', unread=False,
                   date=datetime(2026, 10, day, 10, tzinfo=timezone.utc) if day else None)


def setup(app, message):
    app.state.mail = SimpleNamespace(message=lambda uid: message)


def test_thread_uses_exact_headers_and_source_order_without_model_or_ingestion():
    app = create_app()
    current = mail('3', mid='<third@test>', reply='<second@test>', day=3)
    setup(app, current)
    second = remember(app.state.episodes, mail('2', mid='<second@test>', reply='<first@test>', day=2, body='Bitte bis 14.10.2026 senden.'))['episode']
    first = remember(app.state.episodes, mail('1', mid='<first@test>', day=1))['episode']
    remember(app.state.episodes, mail('4', account='private', mid='<first@test>', day=4, body='Falsches Konto'))
    remember(app.state.episodes, mail('5', mid='<unrelated@test>', day=5, body='Gleicher Betreff, anderer Vorgang'))
    counts = app.state.episodes.counts()
    with TestClient(app) as client:
        response = client.get('/api/v1/messages/work:3/thread')
        assert response.status_code == 200
        data = response.json()
        assert [item['episode_id'] for item in data['items']] == [first['id'], second['id'], None]
        assert data['items'][-1]['current'] is True
        assert data['items'][0]['occurred_at'] == '2026-10-01T10:00:00+00:00'
        assert data['scope'] == 'stored_header_links'
        assert data['limited'] is False
        assert app.state.episodes.counts() == counts  # viewing never captures a source
        assert app.state.tasks.open_tasks() == []


def test_thread_withdrawal_and_latest_source_version_are_enforced_on_every_read():
    app = create_app()
    current = mail('3', mid='<third@test>', reply='<first@test>', day=3)
    setup(app, current)
    original = mail('1', mid='<first@test>', body='Alte Frist.', day=1)
    old = remember(app.state.episodes, original)['episode']
    new = remember(app.state.episodes, replace(original, body='Die Frist entfällt.'), claims=app.state.claims)['episode']
    with TestClient(app) as client:
        path = '/api/v1/messages/work:3/thread'
        data = client.get(path).json()
        assert [i['episode_id'] for i in data['items']] == [new['id'], None]
        assert old['id'] not in str(data)
        app.state.episodes.ignore(new['id'])
        data = client.get(path).json()
        assert len(data['items']) == 1 and 'Die Frist entfällt.' not in str(data)
        anchor = remember(app.state.episodes, current)['episode']
        app.state.episodes.ignore(anchor['id'])
        data = client.get(path).json()
        assert data['status'] == 'excluded' and data['items'] == []


def test_undated_sources_are_separate_and_limits_never_claim_complete_mailbox():
    app = create_app()
    current = mail('3', mid='<third@test>', reply='<first@test>', day=3)
    setup(app, current)
    remember(app.state.episodes, mail('1', mid='<first@test>', day=1))
    undated = remember(app.state.episodes, mail('2', mid='<second@test>', reply='<first@test>', day=0))['episode']
    with TestClient(app) as client:
        data = client.get('/api/v1/messages/work:3/thread').json()
        assert data['items'][-1]['episode_id'] == undated['id']
        assert data['items'][-1]['occurred_at'] is None
        assert 'Postfach' in data['detail']
        limited = client.get('/api/v1/messages/work:3/thread?limit=2').json()
        assert limited['limited'] is True
        assert len(limited['items']) == 2
        assert any(item['current'] for item in limited['items'])
        assert client.get('/api/v1/messages/work:3/thread?limit=51').status_code == 422


def test_no_header_does_not_join_same_subject_and_long_text_is_explicitly_truncated():
    app = create_app()
    current = mail('1', body='A' * 7000)
    setup(app, current)
    remember(app.state.episodes, mail('2', mid='<different@test>'))
    with TestClient(app) as client:
        data = client.get('/api/v1/messages/work:1/thread').json()
        assert len(data['items']) == 1
        assert data['items'][0]['truncated'] is True
        assert data['limited'] is True
        assert len(data['items'][0]['text']) <= 6000


def test_query_work_budget_returns_an_explicit_partial_result(monkeypatch):
    from icarus_memory import mail_thread
    monkeypatch.setattr(mail_thread, 'MAX_QUERY_STEPS', 0)
    app = create_app()
    current = mail('3', mid='<third@test>', reply='<first@test>', day=3)
    setup(app, current)
    for i in range(30):
        remember(app.state.episodes, mail(str(i + 10), mid=f'<other{i}@test>'))
    with TestClient(app) as client:
        data = client.get('/api/v1/messages/work:3/thread').json()
        assert data['limited'] is True
        assert len(data['items']) == 1 and data['items'][0]['current']
        # An interrupted read must not leave a handler poisoning later work.
        with app.state.episodes._lock:
            assert app.state.episodes._conn.execute('SELECT count(*) FROM episodes a, episodes b, episodes c').fetchone()[0] == 27000
        assert client.post('/api/v1/tasks', json={'title': 'Weiterarbeiten'}).status_code == 201


def test_mail_source_change_during_read_is_rejected():
    app = create_app()
    current = mail('1', mid='<first@test>')
    def switching_reader(uid):
        app.state.mail = SimpleNamespace(message=lambda _: current)
        return current
    app.state.mail = SimpleNamespace(message=switching_reader)
    with TestClient(app) as client:
        assert client.get('/api/v1/messages/work:1/thread').status_code == 409
