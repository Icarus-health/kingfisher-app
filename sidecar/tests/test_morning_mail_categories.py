from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory.connectors.mail import Message
from icarus_memory.morning import compose
from icarus_memory.server import create_app


def test_dashboard_labels_mail_and_morning_keeps_personal_message_visible():
    messages = [
        Message(uid=str(i), subject=f"Newsletter {i}", sender="news@example.org",
                date=None, preview="Weekly news", unread=True, list_mail=True)
        for i in range(3)
    ] + [Message(uid="personal", subject="Dein Kurs fällt aus", sender="anna@example.org",
                 date=None, preview="Der Kurs am Freitag fällt aus.", unread=True)]

    class Reader:
        def inbox(self, *, limit):
            return messages[:limit]

    app = create_app()
    app.state.mail = Reader()
    with TestClient(app) as client:
        dashboard = client.get('/dashboard').json()
        morning = client.get('/api/v1/morning-briefing').json()

    assert [item['title'] for item in morning['happening_now']] == ['Dein Kurs fällt aus']
    assert len(dashboard['mail']['items']) == 4
    assert dashboard['mail']['unread'] == 4
    assert [item['category'] for item in dashboard['mail']['items']] == [
        'newsletter', 'newsletter', 'newsletter', 'inbox']
    assert dashboard['mail']['items'][0]['filter_reason'] == 'newsletter'


def test_morning_respects_explicitly_allowed_newsletter_sender():
    class Reader:
        def inbox(self, *, limit):
            return [Message(uid="allowed", subject="Wichtiger Kursbrief", sender="course@example.org",
                            date=None, preview="Kurstermin", unread=True, list_mail=True)]

    app = create_app()
    app.state.mail = Reader()
    app.state.settings.mail_filter = {'allowed': ['course@example.org']}
    with TestClient(app) as client:
        result = client.get('/api/v1/morning-briefing').json()
    assert [item['title'] for item in result['happening_now']] == ['Wichtiger Kursbrief']


@pytest.mark.parametrize('allowed', ['course@example.org', '@example.org'])
@pytest.mark.parametrize('hint', ['newsletter', 'spam'])
@pytest.mark.parametrize('hard_filter,expected', [
    (None, 'inbox'), ('blocked', 'blocked'), ('spam_header', 'spam'),
])
def test_current_allow_overrides_advisory_hint_but_preserves_hard_filters(allowed, hint, hard_filter, expected):
    message = Message(uid='work:1.1', account_id='work', subject='Dein Kurstermin',
                      sender='Kurs <course@example.org>', date=None, preview='Kursinfo',
                      unread=True, list_mail=True, spam_flag=hard_filter == 'spam_header')

    class Reader:
        def inbox(self, *, limit):
            return [message]

    app = create_app()
    app.state.mail = Reader()
    app.state.settings.mail_filter = {'pending': {'old': {
        'account_id': 'work', 'uid': '1.1', 'sender': message.sender,
        'subject': message.subject, 'preview': message.preview,
        'category': hint, 'reason': 'ai_' + hint,
    }}}
    with TestClient(app) as client:
        updated = client.put('/api/v1/mail-filter', json={
            'allowed': [allowed],
            'blocked': ['course@example.org'] if hard_filter == 'blocked' else [],
        })
        assert updated.status_code == 200
        assert len(updated.json()['pending']) == 1
        dashboard = client.get('/dashboard').json()
        morning = client.get('/api/v1/morning-briefing').json()
        inbox = client.get('/api/v1/messages').json()

    assert dashboard['mail']['items'][0]['category'] == expected
    assert inbox['messages'][0]['category'] == expected
    assert [item['title'] for item in morning['happening_now']] == (
        ['Dein Kurstermin'] if expected == 'inbox' else [])
    assert dashboard['mail']['unread'] == 1
    assert len(app.state.settings.mail_filter['pending']) == 1


@pytest.mark.parametrize('category,visible', [
    (None, True), ('inbox', True), ('unclear', True), ('unknown', True),
    ('newsletter', False), ('spam', False), ('blocked', False),
])
def test_compact_morning_only_omits_known_filtered_categories(category, visible):
    mail = {'uid': 'mail', 'subject': 'Nachricht', 'unread': True}
    if category is not None:
        mail['category'] = category
    now = datetime(2026, 10, 15, 7, tzinfo=timezone.utc)
    result = compose({'mail': {'items': [mail]}}, now=now, target=now.date())
    assert bool(result['happening_now']) is visible
