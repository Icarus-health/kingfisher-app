"""Vorhandener Word-Leser an der Mailgrenze; ausschließlich künstliche Originale."""
from contextlib import ExitStack
from dataclasses import replace
from email.message import EmailMessage
from email.policy import SMTP
from html import escape
from io import BytesIO
import re
import struct
from zipfile import ZipFile

import pytest

from icarus_memory import anhaenge
from icarus_memory.claims import ClaimStore
from icarus_memory.connectors import mail
from icarus_memory.document_text import NAMESPACE
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_ingestion import remember
from icarus_memory.source_versions import invalidate_with_corrections

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
TASK = 'Bitte bis zum 18.11.2026 den Raumplan freigeben.'
MAIN_TEXT = TASK + '\n\nSeite 7\n\nRaum\tNordflügel'


def word(*, text=None, xml=None, extra=()):
    """Kleines DOCX-Paket mit Haupttext, Tabelle und verworfenen Änderungen."""
    if xml is None:
        paragraphs = (f'<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>' if text is not None else
                      f'<w:p><w:r><w:t>{TASK}</w:t></w:r>'
                      '<w:del><w:r><w:t>VERALTETER_LOESCHTEXT</w:t></w:r></w:del>'
                      '<w:moveFrom><w:r><w:t>VERALTETER_VERSCHIEBETEXT</w:t></w:r></w:moveFrom></w:p>'
                      '<w:p><w:r><w:t>Seite 7</w:t></w:r></w:p>'
                      '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Raum</w:t></w:r></w:p></w:tc>'
                      '<w:tc><w:p><w:r><w:t>Nordflügel</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
        xml = f'<w:document xmlns:w="{NAMESPACE}"><w:body>{paragraphs}</w:body></w:document>'
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml',
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Default Extension="png" ContentType="image/png"/>'
                         f'<Override PartName="/word/document.xml" ContentType="{DOCX_MIME}.main+xml"/></Types>')
        archive.writestr('_rels/.rels',
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                         'Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', xml)
        archive.writestr('word/header1.xml', f'<w:hdr xmlns:w="{NAMESPACE}"><w:p><w:r>'
                         '<w:t>UNGELESENER_KOPFTEXT</w:t></w:r></w:p></w:hdr>')
        archive.writestr('word/comments.xml', f'<w:comments xmlns:w="{NAMESPACE}">'
                         '<w:comment w:id="0" w:author="Synthetic"><w:p><w:r>'
                         '<w:t>UNGELESENER_KOMMENTAR</w:t></w:r></w:p></w:comment></w:comments>')
        archive.writestr('word/media/image1.png', b'UNGELESENES_BILD')
        for name, data in extra:
            archive.writestr(name, data)
    return stream.getvalue()


def message(*files):
    result = EmailMessage()
    result['From'] = 'Planungsbüro <plan@example.invalid>'
    result['To'] = 'reader@example.invalid'
    result['Subject'] = 'Raumplan zur Freigabe'
    result['Date'] = 'Sat, 31 Oct 2026 10:00:00 +0000'
    result['Message-ID'] = '<docx-original@example.invalid>'
    result.set_content('Anbei der Raumplan.')
    for name, data, mime in files:
        maintype, subtype = mime.split('/', 1)
        result.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return result


class SyntheticIMAP:
    """Nur lesende, vollständige MIME-Literale statt eines echten Postfachs."""
    capabilities = ()

    def __init__(self, raw):
        self.raw = raw
        self.untagged_responses = {}

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def login(self, *args): pass

    def select(self, folder, readonly):
        assert readonly
        self.untagged_responses['UIDVALIDITY'] = [b'7']
        return 'OK', [b'1']

    def response(self, name):
        return name, self.untagged_responses.pop(name, None)

    def uid(self, operation, uid, fields):
        assert operation == 'fetch' and uid == b'103'
        match = re.search(r'BODY\.PEEK\[\]<(\d+)\.(\d+)>', fields)
        assert match is not None
        offset, count = map(int, match.groups())
        raw = self.raw[offset:offset + count]
        header = f'1 (UID 103 FLAGS (\\Seen) RFC822.SIZE {len(self.raw)} BODY[]<{offset}> {{{len(raw)}}}'.encode()
        return 'OK', [(header, raw), b')']


def fetch(monkeypatch, *files):
    server = SyntheticIMAP(message(*files).as_bytes(policy=SMTP))
    monkeypatch.setattr(mail.imaplib, 'IMAP4_SSL', lambda *args, **kwargs: server)
    connector = mail.MailConnector(mail.MailConfig('invalid', 'reader@example.invalid', 'synthetic'))
    return replace(connector.message_mit_anhaengen('INBOX', '7.103'), account_id='synthetic')


@pytest.fixture
def stores(tmp_path):
    with ExitStack() as stack:
        result = []
        for cls, name in ((EpisodeStore, 'episodes'), (ClaimStore, 'claims')):
            store = cls(tmp_path / (name + '.sqlite3'))
            stack.callback(store.close)
            result.append(store)
        yield tuple(result)


def test_docx_main_text_reaches_its_own_original_bound_source(monkeypatch, stores):
    # Ein fehlender DOCX-Dispatcher darf den wörtlichen Originalbeleg nicht verlieren.
    episodes, claims = stores
    item = fetch(monkeypatch, ('Raumplan.docx', word(), DOCX_MIME))
    attachment, = item.anhaenge
    assert item.body.strip() == 'Anbei der Raumplan.' and not item.truncated
    assert attachment.art == 'docx' and attachment.gelesen and attachment.vollstaendig
    assert attachment.haupttext == MAIN_TEXT and attachment.seiten == ()
    assert not anhaenge.wartet_auf_texterkennung(attachment)
    coverage = item.anhang_bericht
    assert coverage['abruf_vollstaendig'] and coverage['vollstaendig']
    info, = coverage['dateien']
    assert info['seiten'] is None and info['gesamt'] is None
    assert info['textumfang'] == 'Word-Haupttext'
    assert 'Word-Haupttext' in coverage['hinweis']

    result = remember(episodes, item, claims=claims)
    child_id, = result['anhaenge']
    parent_id = result['episode']['id']
    child = episodes.get(child_id)
    assert child.kind.value == 'document' and 'anhang:gelesen' in child.tags
    assert f'mail-parent:{parent_id}' in child.tags and 'source:truncated' not in child.tags
    assert child.provenance.source_ref == 'synthetic:<docx-original@example.invalid>#anhang:1:Raumplan.docx'
    assert child.contacts == episodes.get(parent_id).contacts
    assert '\n\nWord-Haupttext\n' + MAIN_TEXT in child.body
    assert 'VERALTETER_' not in child.body and 'UNGELESENER_' not in child.body and 'UNGELESENES_BILD' not in child.body
    assert 'Kopf-/Fußzeilen' in child.body and 'Kommentare' in child.body and 'Bilder' in child.body and 'Layout' in child.body
    assert '\nSeite 1\n' not in child.body
    assert anhaenge.seite_der_stelle(child.body, TASK) is None
    assert anhaenge.seite_der_stelle(child.body, 'Nordflügel') is None  # „Seite 7“ ist Originaltext, keine Seitenmetadaten.
    assert episodes.support_snapshot(child_id).current()
    assert child_id in {entry['id'] for entry in episodes.mentions('Nordflügel')[0]}
    assert remember(episodes, item, claims=claims)['anhaenge'] == []


@pytest.mark.parametrize(('extra', 'complete'), [(0, True), (1, False)])
def test_docx_character_budget_has_an_explicit_partial_state(monkeypatch, stores, extra, complete):
    episodes, claims = stores
    item = fetch(monkeypatch, ('Lang.docx', word(text='x' * (59_985 + extra)), DOCX_MIME))
    attachment, = item.anhaenge
    assert attachment.vollstaendig is complete
    assert item.anhang_bericht['vollstaendig'] is complete
    assert item.anhang_bericht['teilweise'] == (0 if complete else 1)
    child_id, = remember(episodes, item, claims=claims)['anhaenge']
    child = episodes.get(child_id)
    assert ('source:truncated' in child.tags) is (not complete)
    payload = child.body.split('\n\n')[1]
    assert payload.startswith('Word-Haupttext\n') and len(payload) == 60_000
    assert ('Gekürzt' in child.body) is (not complete)


@pytest.mark.parametrize(('name', 'mime'), [
    ('Raumplan.docx', DOCX_MIME), ('Raumplan.DOCX', 'application/octet-stream'),
    ('Raumplan.docx', 'application/zip'), ('Raumplan', DOCX_MIME),
])
def test_supported_docx_name_and_mime_reuse_the_word_reader(name, mime):
    attachment, = anhaenge.aus_mail(message((name, word(), mime)))
    assert attachment.haupttext == MAIN_TEXT and attachment.vollstaendig


@pytest.mark.parametrize(('name', 'mime'), [
    ('Raumplan.doc', 'application/msword'), ('Raumplan.docm', 'application/vnd.ms-word.document.macroEnabled.12'),
    ('Raumplan.docm', DOCX_MIME), ('Raumplan.doc', DOCX_MIME), ('Raumplan.dotx', DOCX_MIME),
    ('Raumplan.txt', DOCX_MIME), ('Raumplan.zip', 'application/zip'),
    ('Raumplan.docx', 'application/vnd.ms-word.document.macroEnabled.12'),
    ('Raumplan.docx', 'image/png'), ('Raumplan.docx', 'application/msword'),
])
def test_unsupported_or_conflicting_word_formats_stay_unsupported(name, mime):
    report = {}
    assert anhaenge.aus_mail(message((name, word(), mime)), bericht=report) == ()
    assert report['nicht_unterstuetzt'] == 1 and not report['vollstaendig']


def encrypted_word():
    # ZIP-Verschlüsselungsflag ohne Schlüssel; der vorhandene Leser muss ablehnen.
    data = bytearray(word())
    for signature, flag_offset in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
        position = 0
        while (position := data.find(signature, position)) >= 0:
            flags = struct.unpack_from('<H', data, position + flag_offset)[0]
            struct.pack_into('<H', data, position + flag_offset, flags | 1)
            position += 4
    return bytes(data)


def duplicate_word():
    with pytest.warns(UserWarning, match='Duplicate name'):
        return word(extra=(('word/document.xml', '<x/>'),))


@pytest.mark.parametrize('data', [
    b'not a zip', encrypted_word(), word(text=''), word(xml='<broken'), word(xml='<x/>'),
    word(xml='x' * (2 * 1024 * 1024 + 1)), word(text='x' * (512 * 1024 + 1)),
    word(xml='<!DOCTYPE x [<!ENTITY e "synthetic">]><x/>'),
    word(xml='<!DOCTYPE x [<!ENTITY e "synthetic">]><x/>'.encode('utf-16')),
    duplicate_word(),
], ids=['corrupt', 'encrypted', 'empty', 'malformed_xml', 'not_word', 'xml_budget', 'text_budget',
        'dtd', 'utf16_dtd', 'duplicate_main_text'])
def test_existing_docx_reader_guards_leave_an_explicit_unread_source(data):
    report = {}
    attachment, = anhaenge.aus_mail(message(('Grenze.docx', data, DOCX_MIME)), bericht=report)
    assert attachment.art == 'docx' and attachment.status == anhaenge.FEHLER
    assert not attachment.gelesen and not attachment.vollstaendig
    assert report['ungelesen'] == 1 and not report['vollstaendig']
    assert 'konnte nicht gelesen werden' in attachment.hinweis
    assert not anhaenge.wartet_auf_texterkennung(attachment)
    assert 'Word-Haupttext' in anhaenge.text(attachment, 'Grenzen', None)


@pytest.mark.parametrize('truncated', [False, True])
def test_oversized_or_incomplete_docx_never_enters_the_parser(monkeypatch, truncated):
    monkeypatch.setattr('icarus_memory.document_text.docx_text',
                        lambda _: pytest.fail('Unvollständige oder übergroße Originale dürfen nicht gelesen werden'))
    report = {}
    data = word() if truncated else b'x' * (5 * 1024 * 1024 + 1)
    attachment, = anhaenge.aus_mail(message(('Gross.docx', data, DOCX_MIME)),
                                    abgeschnitten=truncated, bericht=report)
    assert attachment.status == anhaenge.ZU_GROSS and not attachment.gelesen
    assert not report['vollstaendig'] and report['ungelesen'] == 1
    assert report['abruf_vollstaendig'] is (not truncated)


def test_docx_count_duplicates_and_unnamed_controls_remain_bounded():
    first = word(text='Original 0')
    files = [('Erstes.docx', first, DOCX_MIME), ('Kopie.docx', first, DOCX_MIME)]
    files += [(f'Original-{n}.docx', word(text=f'Original {n}'), DOCX_MIME) for n in range(1, 6)]
    report = {}
    assert len(anhaenge.aus_mail(message(*files), bericht=report)) == 5
    assert report['gelesen'] == 5 and report['doppelt'] == 1 and report['ausgelassen'] == 1
    assert not report['vollstaendig']
    unnamed = {}
    assert anhaenge.aus_mail(message((None, word(), DOCX_MIME)), bericht=unnamed) == ()
    assert unnamed['unbenannt'] == 1 and not unnamed['zuordnung_vollstaendig']


def test_changed_and_withdrawn_docx_never_keep_old_evidence_current(monkeypatch, stores):
    episodes, claims = stores
    first = fetch(monkeypatch, ('Raumplan.docx', word(), DOCX_MIME))
    initial = remember(episodes, first, claims=claims)
    old_id, = initial['anhaenge']
    parent_id = initial['episode']['id']
    updated = fetch(monkeypatch, ('Raumplan.docx', word(text='Neue Freigabe bis zum 19.11.2026.'), DOCX_MIME))
    changed = remember(episodes, updated, claims=claims)
    new_id, = changed['anhaenge']
    assert changed['episode']['id'] == parent_id
    assert not episodes.support_snapshot(old_id).current() and episodes.support_snapshot(new_id).current()
    assert TASK in episodes.get(old_id).body  # Original bleibt erhalten.
    assert 'Neue Freigabe bis zum 19.11.2026.' in episodes.get(new_id).body
    assert old_id not in {entry['id'] for entry in episodes.mentions('Nordflügel')[0]}

    absent = fetch(monkeypatch)
    incomplete = replace(absent, anhang_bericht={**absent.anhang_bericht, 'abruf_vollstaendig': False})
    remember(episodes, incomplete, claims=claims)
    assert episodes.support_snapshot(new_id).current()
    remember(episodes, absent, claims=claims)
    assert not episodes.support_snapshot(new_id).current()
    assert episodes.get(new_id).state.value == 'ignored'


def test_docx_evidence_is_bound_to_parent_permission(monkeypatch, stores):
    episodes, claims = stores
    result = remember(episodes, fetch(monkeypatch, ('Raumplan.docx', word(), DOCX_MIME)), claims=claims)
    child_id, = result['anhaenge']
    parent_id = result['episode']['id']
    invalidate_with_corrections(episodes, claims, parent_id)
    episodes.ignore(parent_id)
    assert not episodes.support_snapshot(child_id).current()
    assert child_id not in {entry['id'] for entry in episodes.mentions('Nordflügel')[0]}
