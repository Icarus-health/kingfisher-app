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
