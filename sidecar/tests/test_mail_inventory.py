"""Historical IMAP intake stays bounded, read-only and generation-aware."""

import re

import pytest

from icarus_memory.connectors.mail import MailConfig, MailConnector, MailError, MailboxGenerationChanged, Message
from icarus_memory.connectors.mail import MAX_MESSAGE_WIRE_BYTES


class InventoryIMAP:
    def __init__(self, *args, **kwargs):
        self.selected = None
        self.calls = []
        self.validity = b"7"
        self.uidnext = b"311"
        self.available = {1, 103, 105, 207, 310}
        self.capabilities = (b"IMAP4REV1", b"X-GM-EXT-1")
        self.flags = b"()"
        self.listed = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
            b'(\\HasNoChildren) "/" "Projects/He said \\"yes\\""',
            b'(\\HasNoChildren) "/" "Back\\\\slash"',
            (b'(\\HasNoChildren) "/" {13}', b'Literal Space'),
            b'(\\Noselect) "/" "[Gmail]"',
            b'(\\Trash) "/" "[Gmail]/Papierkorb"',
            b'(\\Junk) "/" "[Gmail]/Spam"',
            b'(\\HasNoChildren) "/" "Trash"',
            b'(\\HasNoChildren) "/" "Junk"',
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, *args):
        self.calls.append(("login", args))

    def select(self, folder, readonly):
        assert readonly
        self.selected = folder
        self.calls.append(("select", folder, readonly))
        return "OK", [b"5"]

    def list(self):
        self.calls.append(("list",))
        return "OK", self.listed

    def response(self, name):
        return name, [self.validity if name == "UIDVALIDITY" else self.uidnext]

    def uid(self, operation, *args):
        self.calls.append((operation, args))
        if operation == "search":
            assert args[:2] == (None, "UID")
            first, last = map(int, args[2].split(":"))
            assert first <= last
            assert "*" not in args[2]
            found = sorted(uid for uid in self.available if first <= uid <= last)
            return "OK", [" ".join(map(str, found)).encode()]
        assert operation == "fetch"
        assert "BODY.PEEK[]" in args[1]
        if b"X-GM-EXT-1" in self.capabilities:
            assert "X-GM-MSGID" in args[1]
        raw = (b"Subject: Historical\r\nFrom: a@example.invalid\r\n"
               b"Message-ID: <same@example.invalid>\r\nContent-Type: text/plain\r\n\r\nBody")
        return "OK", [(b"1 (UID " + args[0] + b" FLAGS " + self.flags + b" X-GM-MSGID 123456789)", raw)]


@pytest.fixture
def mailbox(monkeypatch):
    fake = InventoryIMAP()
    monkeypatch.setattr("icarus_memory.connectors.mail.imaplib.IMAP4_SSL", lambda *a, **kw: fake)
    connector = MailConnector(MailConfig("invalid", "user", "password"))
    return connector, fake


def test_list_parses_quoted_escaped_and_literal_names_and_prefers_all_mail(mailbox):
    connector, fake = mailbox
    folders = connector.folders()
    assert [folder["name"] for folder in folders] == [
        "INBOX", "[Gmail]/All Mail", 'Projects/He said "yes"', "Back\\slash", "Literal Space",
    ]
    assert folders[1]["attributes"] == ["\\HasNoChildren", "\\All"]
    assert folders[1]["delimiter"] == "/"
    assert [folder["name"] for folder in folders if folder["historical"]] == ["[Gmail]/All Mail"]
    assert not any(call[0] == "select" for call in fake.calls)


def test_list_falls_back_to_inbox_and_sent_without_special_use_all_mail(mailbox):
    # Ohne Gesamtbestand (`\All`) liest Kingfisher Posteingang **und** Gesendet: Ein Stabschef kennt die eigenen Zusagen.
    connector, fake = mailbox
    # „Verzonden“ steht in keiner Namensliste: Hier zählt allein das SPECIAL-USE-Attribut.
    fake.listed = [b'() NIL INBOX', b'(\\Sent) "/" "Verzonden"', b'(\\HasNoChildren) "/" "Archiv"']
    folders = connector.folders()
    assert folders[0] == {"name": "INBOX", "attributes": [], "delimiter": None, "historical": True, "gesendet": False}
    assert folders[1]["name"] == "Verzonden" and folders[1]["historical"] and folders[1]["gesendet"]
    assert not folders[2]["historical"] and not folders[2]["gesendet"]
    assert not folders[0]["gesendet"]


@pytest.mark.parametrize("name", ["Gesendet", "Sent", "Sent Items", "Sent Messages", "Gesendete Objekte",
                                  "Gesendete Elemente", "INBOX.Sent", "INBOX/Sent", "gesendet", "SENT ITEMS"])
def test_list_recognises_sent_folder_by_name_without_attribute(mailbox, name):
    connector, fake = mailbox
    fake.listed = [b'() NIL INBOX', b'(\\HasNoChildren) "." "Entwuerfe"',
                   b'(\\HasNoChildren) "." "' + name.encode() + b'"', b'(\\HasNoChildren) "." "Gesendet-Archiv"']
    folders = connector.folders()
    assert [f["name"] for f in folders if f["historical"]] == ["INBOX", name]
    assert [f["name"] for f in folders if f["gesendet"]] == [name]


def test_list_prefers_sent_attribute_over_an_earlier_name_match(mailbox):
    # Das Attribut sagt, was der Server meint; ein Ordner, der nur „Sent“ heißt, steht dahinter zurück.
    connector, fake = mailbox
    fake.listed = [b'() NIL INBOX', b'(\\HasNoChildren) "/" "Sent"', b'(\\Sent) "/" "Verzonden"']
    folders = connector.folders()
    assert [f["name"] for f in folders if f["historical"]] == ["INBOX", "Verzonden"]


def test_list_with_all_mail_marks_no_additional_sent_folder(mailbox):
    # Gmail: Der Gesamtbestand enthält Gesendet schon; ein zweiter Ordner brächte jede eigene Mail doppelt.
    connector, fake = mailbox
    fake.listed = [b'() NIL INBOX', b'(\\Sent) "/" "[Gmail]/Sent Mail"', b'(\\All) "/" "[Gmail]/All Mail"']
    folders = connector.folders()
    assert [f["name"] for f in folders if f["historical"]] == ["[Gmail]/All Mail"]
    assert not any(f["gesendet"] and f["historical"] for f in folders)


def test_list_sent_never_resurrects_trash_or_junk(mailbox):
    connector, fake = mailbox
    fake.listed = [b'() NIL INBOX', b'(\\Trash \\Sent) "/" "Papierkorb"', b'(\\Junk) "/" "Sent Spam"',
                   b'(\\HasNoChildren) "/" "Sent/Trash"']
    folders = connector.folders()
    assert [f["name"] for f in folders] == ["INBOX"]
    assert [f["name"] for f in folders if f["historical"]] == ["INBOX"]


def test_message_in_folder_marks_drafts(mailbox):
    # Gmail führt Entwürfe im Gesamtbestand mit `\Draft`; sie sind nichts, was geschah.
    connector, fake = mailbox
    fake.flags = b"(\\Draft \\Seen)"
    nachricht = connector.message_in_folder("[Gmail]/All Mail", "7.103")
    assert nachricht.entwurf is True and nachricht.unread is False
    fake.flags = b"(\\Seen)"
    assert connector.message_in_folder("INBOX", "7.105").entwurf is False


def test_empty_ranges_advance_scan_without_counting_deleted_uids(mailbox):
    connector, fake = mailbox
    fake.available = {103, 105, 310}
    first = connector.inventory_page("INBOX", limit=100)
    assert first == {"folder": "INBOX", "uidvalidity": "7", "upper_uid": 310,
                     "uids": [], "next_uid": 100, "done": False}
    second = connector.inventory_page("INBOX", after_uid=first["next_uid"], before_uid=310, limit=100)
    assert second["uids"] == [103, 105]
    assert second["next_uid"] == 200 and not second["done"]
    third = connector.inventory_page("INBOX", after_uid=200, before_uid=310, limit=100)
    assert third["uids"] == [] and third["next_uid"] == 300 and not third["done"]
    last = connector.inventory_page("INBOX", after_uid=300, before_uid=310, limit=100)
    assert last["uids"] == [310] and last["next_uid"] == 310 and last["done"]
    assert [call[1][2] for call in fake.calls if call[0] == "search"] == ["1:100", "101:200", "201:300", "301:310"]


def test_snapshot_boundary_excludes_mail_arriving_during_initial_intake(mailbox):
    connector, fake = mailbox
    snapshot = connector.inventory_page("INBOX", limit=100)["upper_uid"]
    fake.uidnext = b"401"
    fake.available.add(400)
    last = connector.inventory_page("INBOX", after_uid=300, before_uid=snapshot, limit=100)
    assert last["upper_uid"] == snapshot and last["uids"] == [310] and last["done"]
    assert fake.calls[-1] == ("search", (None, "UID", "301:310"))


def test_exhausted_or_empty_mailbox_never_issues_reversed_search_range(mailbox):
    connector, fake = mailbox
    fake.uidnext = b"1"
    assert connector.inventory_page("INBOX")["done"]
    assert connector.inventory_page("INBOX")["next_uid"] == 0
    fake.uidnext = b"311"
    page = connector.inventory_page("INBOX", after_uid=310, before_uid=310)
    assert page["done"] and page["uids"] == [] and page["next_uid"] == 310
    assert not any(call[0] == "search" for call in fake.calls)


def test_folder_read_is_readonly_and_provider_identity_survives_label_overlap(mailbox):
    connector, fake = mailbox
    first = connector.message_in_folder("INBOX", "7.103")
    second = connector.message_in_folder('[Gmail]/All "Mail"', "7.105")
    assert first.uid != second.uid and first.provider_id == second.provider_id == "123456789"
    assert second.message_id == "<same@example.invalid>" and second.body == "Body"
    assert fake.selected == '"[Gmail]/All \\"Mail\\""'
    assert first.to_dict()["provider_id"] == "123456789"
    fake.validity = b"8"
    fetches = sum(call[0] == "fetch" for call in fake.calls)
    with pytest.raises(MailboxGenerationChanged, match="veraltet"):
        connector.message_in_folder("INBOX", "7.103")
    assert sum(call[0] == "fetch" for call in fake.calls) == fetches


def test_inventory_rejects_stale_generation_before_search(mailbox):
    connector, fake = mailbox
    fake.validity = b"8"
    with pytest.raises(MailboxGenerationChanged, match="veraltet"):
        connector.inventory_page("INBOX", after_uid=100, before_uid=310, uidvalidity="7")
    assert not any(call[0] == "search" for call in fake.calls)


def test_standard_imap_does_not_request_gmail_extension(mailbox):
    connector, fake = mailbox
    fake.capabilities = (b"IMAP4REV1",)
    original_uid = fake.uid

    def uid(operation, *args):
        if operation == "fetch":
            assert "X-GM-MSGID" not in args[1]
            return "OK", [(b"1 (UID 103 FLAGS (\\Seen))", b"Subject: Standard\r\n\r\nBody")]
        return original_uid(operation, *args)

    fake.uid = uid
    message = connector.message("7.103")
    assert message.provider_id == "" and not message.unread
    assert "provider_id" not in message.to_dict()
    assert Message("7.1", "Old", "", None, "", True).provider_id == ""


@pytest.mark.parametrize("kwargs", [
    {"after_uid": -1}, {"after_uid": 4294967296}, {"after_uid": True}, {"after_uid": None},
    {"before_uid": -1}, {"before_uid": "10"}, {"limit": 0}, {"limit": 1001},
    {"limit": True}, {"folder": "INBOX\r\nUID SEARCH ALL"}, {"uidvalidity": "7.1"},
])
def test_invalid_inventory_arguments_do_not_contact_mail_server(mailbox, kwargs):
    connector, fake = mailbox
    arguments = {"folder": "INBOX", **kwargs}
    with pytest.raises(ValueError):
        connector.inventory_page(**arguments)
    assert not fake.calls


@pytest.mark.parametrize("uidnext", [b"", b"0", b"invalid", b"4294967297"])
def test_invalid_uidnext_fails_without_unbounded_fallback(mailbox, uidnext):
    connector, fake = mailbox
    fake.uidnext = uidnext
    with pytest.raises(MailError):
        connector.inventory_page("INBOX")
    assert not any(call[0] == "search" for call in fake.calls)


def test_invalid_search_result_cannot_advance_scan(mailbox):
    connector, fake = mailbox
    fake.uid = lambda *args: ("OK", [b"2 invalid 5"])
    with pytest.raises(MailError):
        connector.inventory_page("INBOX")


def test_search_results_are_sorted_unique_and_restricted_to_requested_window(mailbox):
    connector, fake = mailbox
    fake.uid = lambda *args: ("OK", [b"105 103 105 99 201"])
    page = connector.inventory_page("INBOX", after_uid=100, limit=100)
    assert page["uids"] == [103, 105]
    assert page["next_uid"] == 200


def test_largest_uid_has_a_finite_numeric_search_and_final_watermark(mailbox):
    connector, fake = mailbox
    fake.uidnext = b"4294967296"
    fake.available = {4294967295}
    page = connector.inventory_page("INBOX", after_uid=4294967294)
    assert page["uids"] == [4294967295] and page["next_uid"] == 4294967295 and page["done"]
    assert fake.calls[-1] == ("search", (None, "UID", "4294967295:4294967295"))


def test_failed_select_and_list_do_not_continue(mailbox):
    connector, fake = mailbox
    fake.select = lambda *args, **kwargs: ("NO", [])
    with pytest.raises(MailError):
        connector.inventory_page("INBOX")
    with pytest.raises(MailError):
        connector.message_in_folder("INBOX", "7.1")
    fake.list = lambda: ("NO", [])
    with pytest.raises(MailError):
        connector.folders()


def test_malformed_list_fails_without_silently_losing_folders(mailbox):
    connector, fake = mailbox
    fake.listed = [b'() "/" "INBOX"', b'() "/" "unterminated']
    with pytest.raises(MailError):
        connector.folders()


@pytest.mark.parametrize("attachment", [False, True])
def test_large_body_or_attachment_uses_bounded_sequential_wire_fetch(mailbox, attachment):
    connector, fake = mailbox
    if attachment:
        raw = (b'Subject: Large attachment\r\nContent-Type: multipart/mixed; boundary="bound"\r\n\r\n'
               b'--bound\r\nContent-Type: text/plain\r\n\r\nShort body\r\n'
               b'--bound\r\nContent-Type: application/octet-stream\r\n'
               b'Content-Disposition: attachment; filename="large.bin"\r\n\r\n'
               + b'x' * (MAX_MESSAGE_WIRE_BYTES + 500) + b'\r\n--bound--\r\n')
    else:
        raw = b'Subject: Large body\r\nContent-Type: text/plain\r\n\r\n' + b'x' * (MAX_MESSAGE_WIRE_BYTES + 500)
    calls = []

    def uid(operation, number, fields):
        assert operation == "fetch"
        calls.append(fields)
        partial = re.search(r"BODY\.PEEK\[\]<(\d+)\.(\d+)>", fields)
        assert partial is not None, "No full-message fallback is allowed"
        offset, requested = map(int, partial.groups())
        assert 0 < requested <= MAX_MESSAGE_WIRE_BYTES
        metadata = f"1 (UID 103 RFC822.SIZE {len(raw)} FLAGS () X-GM-MSGID 123 BODY[]<{offset}>)".encode()
        return "OK", [(metadata, raw[offset:offset + requested])]

    fake.uid = uid
    message = connector.message_in_folder("INBOX", "7.103") if attachment else connector.message("7.103")
    assert len(calls) == 2 and message.truncated is (not attachment) and message.provider_id == "123"
    assert len(message.body) <= 20_000
    if attachment:
        assert message.body.strip() == "Short body"


def test_reported_partial_wire_is_truncated_even_when_returned_body_is_short(mailbox):
    connector, fake = mailbox
    fake.uid = lambda *args: ("OK", [(b"1 (UID 103 RFC822.SIZE 10000000 FLAGS ())", b"Subject: Short\r\n\r\nShort")])
    assert connector.message_in_folder("INBOX", "7.103").truncated


@pytest.mark.parametrize("metadata", [
    b"1 (UID 105 FLAGS ())", b"1 (UID invalid FLAGS ())", b"1 (UID 103 RFC822.SIZE invalid FLAGS ())",
    b"1 (UID 103 FLAGS () X-GM-MSGID invalid)", b"1 (UID 103 FLAGS () X-GM-MSGID 0)",
    b"1 (UID 103 FLAGS () X-GM-MSGID 18446744073709551616)",
])
def test_wrong_or_invalid_fetch_metadata_never_becomes_a_source(mailbox, metadata):
    connector, fake = mailbox
    fake.uid = lambda *args: ("OK", [(metadata, b"Subject: Invalid\r\n\r\nBody")])
    with pytest.raises(MailError):
        connector.message_in_folder("INBOX", "7.103")


def test_unsolicited_provider_id_without_advertised_extension_is_ignored(mailbox):
    connector, fake = mailbox
    fake.capabilities = (b"IMAP4REV1",)
    fake.uid = lambda *args: ("OK", [(b"1 (UID 103 FLAGS () X-GM-MSGID 123)", b"Subject: Normal\r\n\r\nBody")])
    assert connector.message_in_folder("INBOX", "7.103").provider_id == ""
