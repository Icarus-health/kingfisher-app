"""Vollständige MIME in begrenzten, identitätsgebundenen Teilabrufen; nur erfundene Daten."""
from email.message import EmailMessage
from email.policy import SMTP
from io import BytesIO
import re

import pytest
from pypdf import PdfReader, PdfWriter

from icarus_memory import anhaenge
from icarus_memory.connectors import mail


class RangeIMAP:
    """Die externe IMAP-Grenze: Teilbereiche samt den tatsächlich gelieferten Metadaten."""

    capabilities = ()

    def __init__(self, raw):
        self.raw = raw
        self.requests = []
        self.selects = []
        self.validity = b'7'
        self.responses = {}
        self.untagged_responses = self.responses
        self.change = None

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def login(self, *args): pass

    def select(self, folder, readonly):
        assert readonly
        self.selects.append(folder)
        self.responses['UIDVALIDITY'] = [self.validity]
        return 'OK', [b'1']

    def response(self, name):
        return name, self.responses.pop(name, None)

    def uid(self, operation, uid, fields):
        assert operation == 'fetch' and uid == b'103'
        # Kein Ganzabruf, keine Flagschreibweise, keine parallelen Anfragen.
        match = re.search(r'BODY\.PEEK\[\]<(\d+)\.(\d+)>', fields)
        assert match is not None
        offset, count = map(int, match.groups())
        self.requests.append((offset, count))
        raw = self.raw[offset:offset + count]
        header = f'1 (UID 103 FLAGS (\\Seen) RFC822.SIZE {len(self.raw)} BODY[]<{offset}> {{{len(raw)}}}'.encode()
        result = ('OK', [(header, raw), b')'])
        return self.change(self, len(self.requests), result) if self.change else result


def reader(monkeypatch, raw):
    server = RangeIMAP(raw)
    monkeypatch.setattr(mail.imaplib, 'IMAP4_SSL', lambda *args, **kwargs: server)
    return mail.MailConnector(mail.MailConfig('invalid', 'synthetic', 'synthetic')), server


def synthetic_pdf(size):
    """Gültige einseitige PDF in einer gezielten Dateigröße, ohne fremde Inhalte."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    padding = size - 500
    for _ in range(3):
        writer.add_metadata({'/SyntheticPadding': 'x' * padding})
        data = BytesIO()
        writer.write(data)
        pdf = data.getvalue()
        if len(pdf) == size:
            assert len(PdfReader(BytesIO(pdf)).pages) == 1
            return pdf
        padding += size - len(pdf)
    raise AssertionError('Synthetische PDF erreicht die gewünschte Größe nicht')


def multipart_pdf():
    # Ca. 2,6 MB als MIME, klar unter der unterstützten Grenze je Anhang.
    pdf = synthetic_pdf(1_900_000)
    message = EmailMessage()
    message['Subject'] = 'Erfundene Unterlage'
    message['From'] = 'synthetic@example.invalid'
    message['To'] = 'reader@example.invalid'
    message.set_content('Anbei die erfundene Unterlage.')
    message.add_attachment(pdf, maintype='application', subtype='pdf', filename='Unterlage.pdf')
    return message.as_bytes(policy=SMTP), pdf


def test_supported_pdf_beyond_first_wire_range_reaches_reader_complete(monkeypatch):
    raw, pdf = multipart_pdf()
    assert 2_500_000 < len(raw) < 2_700_000 and len(pdf) < anhaenge.MAX_BYTES
    connector, server = reader(monkeypatch, raw)
    parsed = []
    original = mail.email.message_from_bytes

    def parse(data, *args, **kwargs):
        parsed.append(data)
        return original(data, *args, **kwargs)

    monkeypatch.setattr(mail.email, 'message_from_bytes', parse)
    received = []

    def pdf_pages(data, **kwargs):
        received.append(data)
        assert kwargs == {'max_seiten': 30, 'bilder': False, 'zeitgrenze': 12.0}
        return {'seiten': ['Erfundene Unterlage: Freigabe bis Freitag.'], 'gesamt': 1, 'leer': []}

    monkeypatch.setattr('icarus_memory.document_text.pdf_seiten', pdf_pages)
    item = connector.message_mit_anhaengen('INBOX', '7.103')

    assert not item.truncated, 'Unterstützte Anlagen brauchen die vollständige MIME, nicht nur deren Anfang'
    assert parsed == [raw] and received == [pdf]
    assert item.body.strip() == 'Anbei die erfundene Unterlage.' and not item.unread
    attachment, = item.anhaenge
    assert attachment.vollstaendig and attachment.seiten == ('Erfundene Unterlage: Freigabe bis Freitag.',)
    assert item.anhang_bericht['abruf_vollstaendig'] and item.anhang_bericht['vollstaendig']
    assert server.requests == [(0, 2 * 1024 * 1024), (2 * 1024 * 1024, len(raw) - 2 * 1024 * 1024)]
    assert raw.endswith(b'--\r\n')  # Original samt abschließender Multipart-Grenze blieb unangetastet.


def small_mail(body=b'Hallo'):
    return b'Subject: Kurz\r\nContent-Type: text/plain\r\n\r\n' + body


@pytest.mark.parametrize('folder', ['INBOX', 'Sent'])
def test_small_mail_needs_one_readonly_request_and_no_origin_when_size_proves_complete(monkeypatch, folder):
    connector, server = reader(monkeypatch, small_mail())

    def no_origin(server, number, result):
        header, raw = result[1][0]
        return 'OK', [(header.replace(b'BODY[]<0>', b'BODY[]'), raw), b')']

    server.change = no_origin
    item = connector.message_in_folder(folder, '7.103')
    assert item.body == 'Hallo' and item.subject == 'Kurz' and not item.truncated
    assert len(server.requests) == 1 and server.selects == [folder if folder == 'INBOX' else '"Sent"']


def test_complete_wire_still_applies_text_cap(monkeypatch):
    connector, server = reader(monkeypatch, small_mail(b'z' * 25_000))
    item = connector.message('7.103')
    assert item.body == 'z' * 20_000 and item.truncated
    assert len(server.requests) == 1


@pytest.mark.parametrize('unknown_size', [True, False])
def test_short_or_unknown_first_reply_never_claims_completeness_or_retries(monkeypatch, unknown_size):
    raw = small_mail()
    connector, server = reader(monkeypatch, raw)

    def shorten(server, number, result):
        header, raw = result[1][0]
        size = b'' if unknown_size else b' RFC822.SIZE 2000000'
        header = re.sub(rb' RFC822\.SIZE \d+', size, header)
        return 'OK', [(header, raw), b')']

    server.change = shorten
    item = connector.message_mit_anhaengen('INBOX', '7.103')
    assert item.truncated and not item.anhang_bericht['abruf_vollstaendig']
    assert item.body == 'Hallo' and len(server.requests) == 1


@pytest.mark.parametrize('problem', ['wrong_uid', 'missing_uid', 'duplicate_uid', 'changed_size', 'missing_size',
                                     'wrong_origin', 'ignored_offset', 'missing_origin', 'duplicate_origin',
                                     'malformed_origin', 'multiple_literals'])
def test_unsafe_continuation_is_rejected_before_parsing(monkeypatch, problem):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))

    def corrupt(server, number, result):
        if number == 1:
            return result
        header, raw = result[1][0]
        if problem == 'wrong_uid': header = header.replace(b'UID 103', b'UID 104')
        if problem == 'missing_uid': header = header.replace(b'UID 103 ', b'')
        if problem == 'duplicate_uid': header = header.replace(b'UID 103', b'UID 103 UID 104')
        if problem == 'changed_size': header = re.sub(rb'RFC822\.SIZE \d+', b'RFC822.SIZE 123', header)
        if problem == 'missing_size': header = re.sub(rb'RFC822\.SIZE \d+ ', b'', header)
        if problem in ('wrong_origin', 'ignored_offset'): header = re.sub(rb'BODY\[\]<\d+>', b'BODY[]<0>', header)
        if problem == 'missing_origin': header = re.sub(rb'BODY\[\]<\d+>', b'BODY[]', header)
        if problem == 'duplicate_origin': header = header.replace(b'BODY[]', b'BODY[]<0> BODY[]')
        if problem == 'malformed_origin': header = re.sub(rb'BODY\[\]<\d+>', b'BODY[]<oops>', header)
        if problem == 'ignored_offset': raw = server.raw[:len(raw)]
        if problem == 'multiple_literals': return 'OK', [(header, raw), (header, b'foreign'), b')']
        return 'OK', [(header, raw), b')']

    server.change = corrupt
    monkeypatch.setattr(mail.email, 'message_from_bytes', lambda *args: pytest.fail('Unsichere Teile dürfen keine Quelle bilden'))
    with pytest.raises(mail.MailError):
        connector.message('7.103')
    assert len(server.requests) == 2


@pytest.mark.parametrize('when', ['before_continuation', 'during_first_fetch', 'during_last_fetch'])
def test_changed_generation_never_stitches_or_parses(monkeypatch, when):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))

    def changed(server, number, result):
        if number == 1 and when == 'before_continuation': server.validity = b'8'
        if (number == 1 and when == 'during_first_fetch') or (number == 2 and when == 'during_last_fetch'):
            server.responses['UIDVALIDITY'] = [b'8']
        return result

    server.change = changed
    monkeypatch.setattr(mail.email, 'message_from_bytes', lambda *args: pytest.fail('Geänderte Generation darf keine Quelle bilden'))
    with pytest.raises(mail.MailboxGenerationChanged):
        connector.message('7.103')
    assert len(server.requests) == (2 if when == 'during_last_fetch' else 1)


@pytest.mark.parametrize('returned', ['short', 'empty', 'overdelivery', 'literal_length_mismatch'])
def test_bad_continuation_length_stops_incomplete_without_unbounded_retry(monkeypatch, returned):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))
    parsed_lengths = []
    original = mail.email.message_from_bytes

    def parse(raw):
        parsed_lengths.append(len(raw))
        return original(raw)

    def corrupt(server, number, result):
        if number == 1: return result
        header, raw = result[1][0]
        if returned == 'short': raw = raw[:5]
        if returned == 'empty': raw = b''
        if returned == 'overdelivery': raw += b'EXTRA'
        if returned != 'literal_length_mismatch':
            header = re.sub(rb'\{\d+\}', b'{' + str(len(raw)).encode() + b'}', header)
        else:
            header = re.sub(rb'\{\d+\}', b'{1}', header)
        return 'OK', [(header, raw), b')']

    server.change = corrupt
    monkeypatch.setattr(mail.email, 'message_from_bytes', parse)
    item = connector.message_mit_anhaengen('INBOX', '7.103')
    assert item.truncated and not item.anhang_bericht['abruf_vollstaendig']
    assert len(server.requests) == 2 and parsed_lengths[0] <= len(server.raw)


@pytest.mark.parametrize('size', [2 * 1024 * 1024, 2 * 1024 * 1024 + 1])
def test_unknown_size_at_first_range_limit_is_incomplete_without_continuation(monkeypatch, size):
    connector, server = reader(monkeypatch, small_mail(b'x' * size))
    server.change = lambda server, number, result: ('OK', [(
        re.sub(rb'RFC822\.SIZE \d+ ', b'', result[1][0][0]), result[1][0][1]), b')'])
    item = connector.message('7.103')
    assert item.truncated and server.requests == [(0, 2 * 1024 * 1024)]


@pytest.mark.parametrize('size', [40 * 1024 * 1024, 40 * 1024 * 1024 + 1])
def test_aggregate_bound_has_finite_request_count_and_parser_bytes(monkeypatch, size):
    connector, server = reader(monkeypatch, b'')
    parsed = []
    original = mail.email.message_from_bytes

    def generate(server, number, result):
        offset, count = server.requests[-1]
        data = b'x' * min(count, size - offset)
        header = f'1 (UID 103 RFC822.SIZE {size} BODY[]<{offset}> {{{len(data)}}}'.encode()
        return 'OK', [(header, data), b')']

    def parse(raw):
        parsed.append(len(raw))
        return original(small_mail())

    server.change = generate
    monkeypatch.setattr(mail.email, 'message_from_bytes', parse)
    item = connector.message('7.103')
    assert parsed == [40 * 1024 * 1024]
    assert len(server.requests) == 20
    assert all(count <= 2 * 1024 * 1024 for _, count in server.requests)
    assert sum(count for _, count in server.requests) == 40 * 1024 * 1024
    assert item.truncated is (size > 40 * 1024 * 1024)


@pytest.mark.parametrize('extra', [0, 1])
def test_five_mib_pdf_reaches_but_never_bypasses_existing_attachment_guard(monkeypatch, extra):
    # Exakt 5 MiB ist unterstützt; Base64 und CRLF brauchen zusammen rund 7 MiB.
    pdf = synthetic_pdf(5 * 1024 * 1024 + extra)
    message = EmailMessage()
    message['Subject'] = 'Erfundene Grenzunterlage'
    message.set_content('Anbei.')
    message.add_attachment(pdf, maintype='application', subtype='pdf', filename='Grenzunterlage.pdf')
    raw = message.as_bytes(policy=SMTP)
    assert 7_000_000 < len(raw) < 7_300_000
    connector, server = reader(monkeypatch, raw)
    received = []

    def pdf_pages(data, **kwargs):
        received.append(data)
        assert kwargs == {'max_seiten': 30, 'bilder': False, 'zeitgrenze': 12.0}
        return {'seiten': ['Erfundener Grenzbeleg.'], 'gesamt': 1, 'leer': []}

    monkeypatch.setattr('icarus_memory.document_text.pdf_seiten', pdf_pages)
    item = connector.message_mit_anhaengen('Sent', '7.103')
    assert not item.truncated and item.anhang_bericht['abruf_vollstaendig']
    assert item.anhaenge[0].vollstaendig is (extra == 0)
    assert item.anhang_bericht['vollstaendig'] is (extra == 0)
    assert received == ([pdf] if extra == 0 else [])
    if extra:
        assert item.anhaenge[0].status == anhaenge.ZU_GROSS
    assert len(server.requests) == 4 and sum(count for _, count in server.requests) == len(raw)


@pytest.mark.parametrize('origin', [b'BODY[]<1>', b'BODY[]<oops>', b'BODY[]<0', b'BODY[HEADER]<0>'])
def test_explicit_wrong_or_malformed_first_section_is_not_a_complete_message(monkeypatch, origin):
    connector, server = reader(monkeypatch, small_mail())
    server.change = lambda server, number, result: ('OK', [(
        result[1][0][0].replace(b'BODY[]<0>', origin), result[1][0][1]), b')'])
    with pytest.raises(mail.MailError):
        connector.message('7.103')


def test_metadata_after_literal_is_bound_to_the_single_message(monkeypatch):
    connector, server = reader(monkeypatch, small_mail())

    def reorder(server, number, result):
        header, raw = result[1][0]
        size = len(raw)
        return 'OK', [(f'1 (BODY[]<0> {{{size}}}'.encode(), raw),
                      f' UID 103 RFC822.SIZE {size} FLAGS (\\Seen))'.encode()]

    server.change = reorder
    item = connector.message('7.103')
    assert item.body == 'Hallo' and not item.truncated and not item.unread


def test_first_overdelivery_is_clipped_and_never_claimed_complete(monkeypatch):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))
    parsed = []
    original = mail.email.message_from_bytes

    def parse(raw):
        parsed.append(len(raw))
        return original(raw)

    def ignore_range(server, number, result):
        return 'OK', [(f'1 (UID 103 RFC822.SIZE {len(server.raw)} BODY[]<0> {{{len(server.raw)}}}'.encode(), server.raw), b')']

    server.change = ignore_range
    monkeypatch.setattr(mail.email, 'message_from_bytes', parse)
    item = connector.message('7.103')
    assert item.truncated and parsed == [2 * 1024 * 1024] and len(server.requests) == 1


def test_first_range_without_origin_is_not_extended_from_an_unverified_prefix(monkeypatch):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))
    server.change = lambda server, number, result: ('OK', [(
        result[1][0][0].replace(b'BODY[]<0>', b'BODY[]'), result[1][0][1]), b')'])
    item = connector.message_mit_anhaengen('INBOX', '7.103')
    assert item.truncated and not item.anhang_bericht['abruf_vollstaendig'] and len(server.requests) == 1


def test_session_reconnect_restarts_ranges_without_reusing_prior_chunks(monkeypatch):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))
    parsed = []
    original = mail.email.message_from_bytes

    def parse(raw):
        parsed.append(raw)
        return original(raw)

    def abort_once(server, number, result):
        if number == 2:
            raise mail.imaplib.IMAP4.abort('Synthetischer Verbindungsabbruch')
        return result

    server.change = abort_once
    monkeypatch.setattr(mail.email, 'message_from_bytes', parse)
    with connector.session():
        item = connector.message('7.103')
    assert item.subject == 'Kurz' and parsed == [server.raw]
    assert server.requests == [(0, 2 * 1024 * 1024), (2 * 1024 * 1024, 543)] * 2


def test_reused_session_keeps_consumed_generation_after_a_ranged_message(monkeypatch):
    connector, server = reader(monkeypatch, small_mail(b'x' * (2 * 1024 * 1024 + 500)))
    with connector.session():
        first = connector.message('7.103')
        second = connector.message('7.103')
    assert first.body == second.body == 'x' * 20_000
    assert len(server.requests) == 4 and len(server.selects) == 3


@pytest.mark.parametrize('placement', ['after_literal', 'before_literal', 'same_tail', 'second_record'])
def test_separate_fetch_record_can_never_supply_identity_for_a_body_literal(monkeypatch, placement):
    raw = small_mail(b'FOREIGN SOURCE')
    connector, server = reader(monkeypatch, raw)

    def separate(server, number, result):
        foreign = (f'2 (BODY[]<0> {{{len(raw)}}}'.encode(), raw)
        identity = f'1 (UID 103 RFC822.SIZE {len(raw)})'.encode()
        if placement == 'after_literal': return 'OK', [foreign, b')', identity]
        if placement == 'before_literal': return 'OK', [identity, foreign, b')']
        if placement == 'same_tail': return 'OK', [foreign, b') ' + identity]
        return 'OK', [result[1][0], b')', b'2 (FLAGS (\\Seen))']

    server.change = separate
    with pytest.raises(mail.MailError):
        connector.message('7.103')


@pytest.mark.parametrize('values', [[b'7', b'8'], [b'7', b'invalid'], [b'7', b''], [b'7', None], [None, b'7']])
@pytest.mark.parametrize('when', ['select', 'fetch'])
def test_all_reported_generation_values_must_be_valid_and_agree(monkeypatch, values, when):
    connector, server = reader(monkeypatch, small_mail())
    select = server.select

    def selected(folder, readonly):
        result = select(folder, readonly)
        server.responses['UIDVALIDITY'] = values
        return result

    def fetched(server, number, result):
        server.responses['UIDVALIDITY'] = values
        return result

    if when == 'select': server.select = selected
    else: server.change = fetched
    with pytest.raises(mail.MailError):
        connector.message('7.103')


@pytest.mark.parametrize('when', ['select', 'fetch'])
def test_identical_repeated_generation_values_preserve_a_complete_small_reply(monkeypatch, when):
    connector, server = reader(monkeypatch, small_mail())
    select = server.select

    def selected(folder, readonly):
        result = select(folder, readonly)
        server.responses['UIDVALIDITY'] = [b'7', b'7']
        return result

    def fetched(server, number, result):
        server.responses['UIDVALIDITY'] = [b'7', b'7']
        return result

    if when == 'select': server.select = selected
    else: server.change = fetched
    item = connector.message('7.103')
    assert item.body == 'Hallo' and not item.truncated


def test_explicit_body_section_without_closing_bracket_is_never_absent_metadata(monkeypatch):
    connector, server = reader(monkeypatch, small_mail())
    server.change = lambda server, number, result: ('OK', [(
        result[1][0][0].replace(b'BODY[]<0>', b'BODY[HEADER'), result[1][0][1]), b')'])
    with pytest.raises(mail.MailError):
        connector.message('7.103')
