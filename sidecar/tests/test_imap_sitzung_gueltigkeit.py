"""Eine Sitzung, die einen Ordner ohne neues SELECT weiterbenutzt, kennt seine UIDVALIDITY noch.

`imaplib.IMAP4.response()` entnimmt die gemerkte Antwort des Servers. Ein normgerechter Server schickt UIDVALIDITY nur
bei SELECT/EXAMINE. Die Aufnahme las erst den Bestand (SELECT, UIDVALIDITY gelesen und damit entnommen) und holte die
Mails dann mit `frisch=False`: Dort fehlte der Wert, und jede Mail scheiterte mit „Das Postfach liefert keine stabile
Nachrichtenkennung.“ (Fremdprobe 3, Befund 1). Geprüft wird mit dem echten `response()` von imaplib.
"""
import imaplib
from contextlib import contextmanager

from icarus_memory.connectors.mail import _mailbox_validity, _Sitzung


class NormgerechterServer(imaplib.IMAP4):
    """Nur das Nötige: SELECT legt UIDVALIDITY ab wie imaplib es beim Lesen der Serverantwort tut."""

    def __init__(self) -> None:  # noqa: D107 - keine Verbindung
        self.untagged_responses = {}
        self.selects = 0
        self.debug = 0  # imaplib liest es in _untagged_response

    def select(self, mailbox='INBOX', readonly=False):
        self.selects += 1
        self.untagged_responses['UIDVALIDITY'] = [b'4711']
        return 'OK', [b'5']


class Verbinder:
    def __init__(self, server) -> None:
        self.server = server

    @contextmanager
    def _open(self):
        yield self.server


def test_weiterbenutzter_ordner_kennt_seine_gueltigkeit():
    server = NormgerechterServer()
    sitzung = _Sitzung(Verbinder(server))
    sitzung._connect()
    assert sitzung.select('INBOX', True) == 'OK'
    assert _mailbox_validity(server) == '4711'            # Bestandsaufnahme liest und entnimmt den Wert
    assert server.untagged_responses.get('UIDVALIDITY') is None
    assert sitzung.select('INBOX', False) == 'OK'          # Abruf nach UID ohne neues SELECT
    assert _mailbox_validity(server) == '4711'
    assert sitzung.select('INBOX', False) == 'OK'          # und beim nächsten Abruf wieder
    assert _mailbox_validity(server) == '4711'
    assert server.selects == 1


def test_neue_verbindung_vergisst_die_gueltigkeit():
    server = NormgerechterServer()
    sitzung = _Sitzung(Verbinder(server))
    sitzung._connect()
    sitzung.select('INBOX', True)
    sitzung._connect()                                     # Verbindungsabbruch, neu verbunden
    assert sitzung.select('INBOX', False) == 'OK'          # anderer Ordnerstand: es wird neu gewählt
    assert server.selects == 2
