"""IMAP-Positionen dürfen keine Nachrichtenidentität sein."""
import email
import pytest
from icarus_memory.connectors.mail import MailConnector, MailConfig, MailError, _body


class FakeIMAP:
    validity = b'7'
    calls = []
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def login(self, *args): pass
    def select(self, folder, readonly):
        assert readonly
        return 'OK', [b'1']
    def response(self, name):
        assert name == 'UIDVALIDITY'
        return name, [self.validity]
    def uid(self, operation, *args):
        self.calls.append((operation, args))
        if operation == 'search': return 'OK', [b'103']
        assert operation == 'fetch' and args[0] == b'103'
        assert 'BODY.PEEK[]' in args[1]
        return 'OK', [(b'1 (UID 103 FLAGS ())', b'Subject: Stabil\r\nFrom: a@example.invalid\r\nContent-Type: text/plain\r\n\r\nInhalt')]


def test_uid_survives_sequence_changes_and_rejects_new_mailbox(monkeypatch):
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', FakeIMAP)
    monkeypatch.setattr(FakeIMAP, 'validity', b'7')
    connector = MailConnector(MailConfig(imap_host='invalid', username='test', password='test'))
    item = connector.inbox()[0]
    assert item.uid == '7.103'
    assert connector.message(item.uid).subject == 'Stabil'
    monkeypatch.setattr(FakeIMAP, 'validity', b'8')
    with pytest.raises(MailError, match='veraltet'):
        connector.message(item.uid)
    with pytest.raises(MailError, match='veraltet'):
        connector.message('1')


def _raw_mail(subject, extra=''):
    return (f'Subject: {subject}\r\nFrom: {subject.lower()}@example.invalid\r\n'
            f'{extra}Content-Type: text/plain\r\n\r\n{subject}').encode()


class BatchInboxIMAP:
    calls = []
    response_rows = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def login(self, *args): pass
    def select(self, folder, readonly):
        assert folder == 'INBOX' and readonly
        return 'OK', []
    def response(self, name):
        assert name == 'UIDVALIDITY'
        return name, [b'7']
    def uid(self, operation, *args):
        self.calls.append((operation, args))
        if operation == 'search':
            return 'OK', [b'101 102 103 104']
        assert operation == 'fetch'
        assert args[1] == '(UID FLAGS BODY.PEEK[])'
        return 'OK', self.response_rows


@pytest.mark.parametrize('limit', [0, -1, 101, True])
def test_inbox_rejects_unbounded_limits_before_connecting(monkeypatch, limit):
    def no_connection(*args, **kwargs):
        pytest.fail('Invalid limits must not connect or fetch a mailbox')
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', no_connection)
    with pytest.raises(ValueError):
        MailConnector(MailConfig('invalid', 'test', 'test')).inbox(limit=limit)


def test_inbox_batches_uids_and_maps_reverse_order_by_explicit_uid(monkeypatch):
    BatchInboxIMAP.calls = []
    BatchInboxIMAP.response_rows = [
        (b'1 (UID 104 FLAGS () BODY[] {0}', _raw_mail('Newest')),
        (b'2 (UID 102 FLAGS (\\Seen) BODY[] {0}', _raw_mail('Oldest')),
        (b'3 (UID 103 FLAGS () BODY[] {0}', _raw_mail('Middle', 'X-Spam-Flag: YES\r\nList-Id: list.invalid\r\n')),
    ]
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', BatchInboxIMAP)
    connector = MailConnector(MailConfig('invalid', 'test', 'test'))

    messages = connector.inbox(limit=3)

    assert [message.uid for message in messages] == ['7.104', '7.103', '7.102']
    assert [message.subject for message in messages] == ['Newest', 'Middle', 'Oldest']
    assert [message.unread for message in messages] == [True, True, False]
    assert messages[1].spam_flag and messages[1].list_mail
    fetches = [args for operation, args in BatchInboxIMAP.calls if operation == 'fetch']
    assert fetches == [(b'102,103,104', '(UID FLAGS BODY.PEEK[])')]


def test_inbox_skips_missing_malformed_and_foreign_uid_responses(monkeypatch):
    BatchInboxIMAP.calls = []
    BatchInboxIMAP.response_rows = [
        (b'1 (FLAGS () BODY[] {0}', _raw_mail('No UID')),
        (b'2 (UID nope FLAGS () BODY[] {0}', _raw_mail('Malformed UID')),
        (b'3 (UID 999 FLAGS () BODY[] {0}', _raw_mail('Foreign UID')),
        (b'4 (UID ' + b'9' * 5000 + b' FLAGS () BODY[] {0}', _raw_mail('Oversized UID')),
        (b'5 (UID 103 FLAGS () UID 102 BODY[] {0}', _raw_mail('Ambiguous UID')),
        (b'6 (UID 103 FLAGS () BODY[] {0}', _raw_mail('Matched')),
    ]
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', BatchInboxIMAP)
    connector = MailConnector(MailConfig('invalid', 'test', 'test'))

    messages = connector.inbox(limit=3)

    assert [(message.uid, message.subject) for message in messages] == [('7.103', 'Matched')]


def test_html_is_readable_text_without_active_content():
    message = email.message_from_string('Content-Type: text/html; charset=utf-8\n\n<p>Hallo</p><script>evil()</script><img src="https://invalid.test/pixel"><p>Termin am Freitag</p>')
    text = _body(message)
    assert 'Hallo' in text and 'Termin am Freitag' in text
    assert 'evil' not in text and '<img' not in text and 'https://' not in text


class ScanIMAP(FakeIMAP):
    found = b'108 103 105 103'
    def uid(self, operation, *args):
        assert operation == 'search'
        self.calls.append((operation, args))
        return 'OK', [self.found]


def test_pending_uids_are_ordered_bounded_and_resume_without_gaps(monkeypatch):
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', ScanIMAP)
    monkeypatch.setattr(ScanIMAP, 'validity', b'7')
    connector = MailConnector(MailConfig(imap_host='invalid', username='test', password='test'))
    assert connector.pending_uids(limit=2) == ['7.103', '7.105']
    assert connector.pending_uids(after='7.105', limit=2) == ['7.108']
    assert connector.pending_uids(after='7.108') == []
    assert ScanIMAP.calls[-1] == ('search', (None, 'UID', '109:*'))
    monkeypatch.setattr(ScanIMAP, 'validity', b'8')
    assert connector.pending_uids(after='7.108', limit=2) == ['8.103', '8.105']


@pytest.mark.parametrize('cursor', ['broken', '7.-1', '7.1 UID SEARCH ALL', '0.1', '7.4294967296'])
def test_pending_uids_reject_invalid_cursor_before_connecting(cursor, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Ungültiger Cursor darf keine Verbindung öffnen')
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', forbidden)
    connector = MailConnector(MailConfig(imap_host='invalid', username='test', password='test'))
    with pytest.raises(ValueError):
        connector.pending_uids(after=cursor)
