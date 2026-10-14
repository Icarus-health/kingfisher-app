"""Die Posteingangsliste braucht eine begrenzte Vorschau, keine ganzen Anlagen."""
import re

from icarus_memory.connectors import mail


class PreviewIMAP:
    calls = []
    raw = b''
    ignore_range = False

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, *args):
        pass

    def select(self, folder, readonly):
        assert folder == 'INBOX' and readonly
        return 'OK', [b'1']

    def response(self, name):
        assert name == 'UIDVALIDITY'
        return name, [b'7']

    def uid(self, operation, *args):
        self.calls.append((operation, args))
        if operation == 'search':
            return 'OK', [b'103']
        assert operation == 'fetch' and args[0] == b'103'
        partial = re.search(r'BODY\.PEEK\[\]<0\.(\d+)>', args[1])
        raw = self.raw if self.ignore_range or partial is None else self.raw[:int(partial[1])]
        header = f'1 (UID 103 FLAGS (\\Seen) RFC822.SIZE {len(self.raw)} BODY[]<0> {{{len(raw)}}}'.encode()
        return 'OK', [(header, raw)]


def reader(monkeypatch, raw, *, ignore_range=False):
    monkeypatch.setattr(PreviewIMAP, 'raw', raw)
    monkeypatch.setattr(PreviewIMAP, 'calls', [])
    monkeypatch.setattr(PreviewIMAP, 'ignore_range', ignore_range)
    monkeypatch.setattr(mail.imaplib, 'IMAP4_SSL', PreviewIMAP)
    return mail.MailConnector(mail.MailConfig('invalid', 'test', 'test'))


def large_mail():
    return (b'Subject: Plan\r\nFrom: test@example.invalid\r\n'
            b'Content-Type: text/plain; charset=utf-8\r\n\r\nBitte den Entwurf pruefen.\r\n' + b'x' * 300000)


def test_inbox_requests_bounded_peek_and_marks_partial_preview(monkeypatch):
    item = reader(monkeypatch, large_mail()).inbox()[0]
    fields = next(args[1] for operation, args in PreviewIMAP.calls if operation == 'fetch')
    match = re.search(r'BODY\.PEEK\[\]<0\.(\d+)>', fields)
    assert match is not None, 'Inbox list must not fetch complete MIME bodies and attachments'
    assert int(match[1]) <= 64 * 1024
    assert 'RFC822.SIZE' in fields
    assert item.uid == '7.103' and item.subject == 'Plan'
    assert item.truncated and item.body == '' and not item.unread
    assert 'Entwurf' in item.preview


def test_inbox_bounds_parser_even_if_server_ignores_partial_range(monkeypatch):
    connector = reader(monkeypatch, large_mail(), ignore_range=True)
    original = mail.email.message_from_bytes
    parsed_sizes = []

    def parse(raw, *args, **kwargs):
        parsed_sizes.append(len(raw))
        return original(raw, *args, **kwargs)

    monkeypatch.setattr(mail.email, 'message_from_bytes', parse)
    item = connector.inbox()[0]
    assert parsed_sizes and max(parsed_sizes) <= 64 * 1024
    assert item.truncated


def test_small_complete_preview_keeps_complete_state_and_list_flags(monkeypatch):
    raw = (b'Subject: Kurz\r\nFrom: test@example.invalid\r\nX-Spam-Flag: YES\r\n'
           b'List-Id: list.invalid\r\nContent-Type: text/plain\r\n\r\nHallo')
    item = reader(monkeypatch, raw).inbox()[0]
    assert item.preview == 'Hallo' and not item.truncated
    assert item.spam_flag and item.list_mail and item.body == ''


def test_inbox_api_preserves_preview_limit_marker(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import server

    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)

    class Inbox:
        def inbox(self, **kwargs):
            return [mail.Message('7.103', 'Plan', 'test@example.invalid', None,
                                 'Bitte den Entwurf prüfen.', False, truncated=True)]

    with TestClient(server.create_app()) as client:
        client.app.state.mail = Inbox()
        row = client.get('/api/v1/messages').json()['messages'][0]
    assert row['truncated'] is True
