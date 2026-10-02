"""Eine IMAP-Verbindung je Aufnahmedurchgang, Wiederverbindung bei Abbruch, ein TLS-Kontext."""
import imaplib
import threading

import pytest

from icarus_memory.connectors.mail import MailConfig, MailConnector, MailError


class Server:
    """Zählt Verbindungen, Anmeldungen und Abmeldungen; kann Verbindungen abbrechen lassen."""

    def __init__(self):
        self.verbindungen = 0
        self.anmeldungen = 0
        self.abmeldungen = 0
        self.selects = []
        self.abbrechen_bei_abruf = set()   # laufende Nummern der Abrufe (1, 2, ...), die abbrechen
        self.abrufe = 0

    def klasse(self):
        server = self

        class Verbindung:
            def __init__(self, *args, **kwargs):
                server.verbindungen += 1

            def __enter__(self):
                return self

            def __exit__(self, *args):
                server.abmeldungen += 1

            def login(self, *args):
                server.anmeldungen += 1

            def select(self, ordner, readonly):
                assert readonly
                server.selects.append(ordner)
                return 'OK', [b'1']

            def response(self, name):
                return name, [b'7' if name == 'UIDVALIDITY' else b'500']

            def uid(self, befehl, *args):
                assert befehl == 'fetch'
                server.abrufe += 1
                if server.abrufe in server.abbrechen_bei_abruf:
                    raise imaplib.IMAP4.abort('Verbindung abgebrochen')
                nummer = args[0].decode()
                roh = f'Subject: Nr {nummer}\r\nFrom: a@example.invalid\r\nContent-Type: text/plain\r\n\r\nText'.encode()
                return 'OK', [(f'1 (UID {nummer} FLAGS ())'.encode(), roh)]

        return Verbindung


@pytest.fixture
def server(monkeypatch):
    s = Server()
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', s.klasse())
    return s


def leser():
    return MailConnector(MailConfig(imap_host='invalid', username='t', password='t'))


def test_mehrere_nachrichten_ueber_eine_verbindung(server):
    connector = leser()
    with connector.session():
        betreffs = [connector.message_in_folder('INBOX', f'7.{n}').subject for n in (1, 2, 3)]
    assert betreffs == ['Nr 1', 'Nr 2', 'Nr 3']
    assert (server.verbindungen, server.anmeldungen, server.abmeldungen) == (1, 1, 1)
    assert server.selects == ['INBOX']   # gleicher Ordner bleibt gewählt


def test_ohne_sitzung_bleibt_es_je_abruf_eine_verbindung(server):
    connector = leser()
    connector.message_in_folder('INBOX', '7.1')
    connector.message_in_folder('INBOX', '7.2')
    assert (server.verbindungen, server.abmeldungen) == (2, 2)


def test_sitzung_ohne_abruf_oeffnet_keine_verbindung(server):
    with leser().session():
        pass
    assert server.verbindungen == 0


def test_ordnerwechsel_waehlt_neu_ohne_neue_verbindung(server):
    connector = leser()
    with connector.session():
        connector.message_in_folder('INBOX', '7.1')
        connector.message_in_folder('Sent', '7.2')
        connector.message_in_folder('Sent', '7.3')
    assert [s.strip('"') for s in server.selects] == ['INBOX', 'Sent']
    assert server.verbindungen == 1


def test_wiederverbindung_nach_abbruch(server):
    server.abbrechen_bei_abruf = {2}   # der zweite Abruf reißt die Verbindung ab
    connector = leser()
    with connector.session():
        betreffs = [connector.message_in_folder('INBOX', f'7.{n}').subject for n in (1, 2, 3)]
    assert betreffs == ['Nr 1', 'Nr 2', 'Nr 3']
    assert server.verbindungen == 2
    assert server.abmeldungen == 2
    assert server.selects == ['INBOX', 'INBOX']   # nach dem Neuaufbau wird der Ordner wieder gewählt


def test_zweiter_abbruch_in_folge_wird_gemeldet_und_sitzung_bleibt_brauchbar(server):
    server.abbrechen_bei_abruf = {1, 2}
    connector = leser()
    with connector.session():
        with pytest.raises(MailError, match='IMAP-Zugriff fehlgeschlagen'):
            connector.message_in_folder('INBOX', '7.1')
        assert connector.message_in_folder('INBOX', '7.2').subject == 'Nr 2'
    assert server.abmeldungen == server.verbindungen


def test_ssl_kontext_wird_einmal_gebaut(server, monkeypatch):
    gebaut = []
    monkeypatch.setattr('icarus_memory.connectors.mail.ssl.create_default_context',
                        lambda: gebaut.append(1) or object())
    connector = leser()
    for n in (1, 2, 3):
        connector.message_in_folder('INBOX', f'7.{n}')
    assert len(gebaut) == 1


def test_sitzung_gehoert_dem_thread_der_sie_oeffnet(server):
    connector = leser()
    fremd = []
    with connector.session():
        connector.message_in_folder('INBOX', '7.1')
        thread = threading.Thread(target=lambda: fremd.append(connector.message_in_folder('INBOX', '7.2').subject))
        thread.start()
        thread.join()
    assert fremd == ['Nr 2']
    assert server.verbindungen == 2   # der fremde Thread hatte eine eigene, kurzlebige Verbindung
