"""„Postfach verbinden“ meldet sich wirklich an (Fremdprobe, Befund 3). Nur synthetische Zugänge, IMAP-Attrappe lokal."""
from __future__ import annotations

import imaplib
import socket
import time

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, mail_anmeldung
from icarus_memory.audit import AuditLog
from icarus_memory.connectors.mail import MailConfig, MailConnector
from icarus_memory.episodes import EpisodeStore
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from tests.imap_attrappe import PASSWORT, ImapAttrappe

ADRESSE = 'lena.probe@example.org'


@pytest.fixture
def attrappe(monkeypatch):
    with ImapAttrappe() as dienst:
        # Der Sidecar baut seinen TLS-Kontext mit `ssl.create_default_context()`; so vertraut er der Attrappe.
        monkeypatch.setenv('SSL_CERT_FILE', str(dienst.zertifikat))
        yield dienst


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id='test'),
        audit=AuditLog(tmp_path / 'audit.sqlite3'), tasks=TaskStore(tmp_path / 'tasks.sqlite3'),
        workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'), episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'),
    )
    with TestClient(app) as c:
        yield c


def verbinden(client, port, passwort=PASSWORT, host='127.0.0.1'):
    return client.post('/api/v1/integrations/mail', json={
        'label': 'Probe-Post', 'imap_host': host, 'imap_port': port, 'user': ADRESSE, 'sender': ADRESSE,
        'password': passwort})


def nichts_gespeichert(client):
    assert client.get('/api/v1/integrations').json()['mail_accounts'] == []
    assert client.get('/api/v1/einrichtung').json()['vorhanden']['mail'] is False


def test_richtige_anmeldung_verbindet(client, attrappe):
    antwort = verbinden(client, attrappe.port)
    assert antwort.status_code == 201, antwort.text
    assert attrappe.anmeldungen == [(ADRESSE, PASSWORT)]
    assert client.get('/api/v1/einrichtung').json()['vorhanden']['mail'] is True


def test_falsches_passwort_wird_abgelehnt_und_nicht_gespeichert(client, attrappe):
    antwort = verbinden(client, attrappe.port, passwort='erfunden')
    assert antwort.status_code == 422
    # Fremdprobe 2, Befund 4: Abgelehnt hat der Server, nicht „Probe-Post“ (der Name, den der Nutzer vergab).
    assert antwort.json()['detail'] == ('Der Mailserver 127.0.0.1 hat die Anmeldung abgelehnt: Adresse oder Passwort '
                                        'stimmen nicht.')
    assert 'Probe-Post' not in antwort.json()['detail']
    assert 'erfunden' not in antwort.text
    nichts_gespeichert(client)


def test_imap_aus_wird_so_benannt(client, attrappe):
    attrappe.modus = 'imap_aus'
    antwort = verbinden(client, attrappe.port)
    assert antwort.status_code == 422
    assert 'Schalte IMAP in den Einstellungen deines Postfachs ein' in antwort.json()['detail']
    nichts_gespeichert(client)


def test_schweigender_server_antwortet_in_der_zeitgrenze(client, attrappe, monkeypatch):
    monkeypatch.setattr(mail_anmeldung, 'ZEITGRENZE', 1.0)
    attrappe.modus = 'stumm'
    start = time.monotonic()
    antwort = verbinden(client, attrappe.port)
    assert time.monotonic() - start < 5
    assert antwort.status_code == 503
    assert antwort.json()['detail'] == ('Der Mailserver 127.0.0.1 antwortet gerade nicht. Prüfe die Internetverbindung '
                                        'und versuche es gleich noch einmal.')
    nichts_gespeichert(client)


def test_geschlossener_port_heisst_nicht_erreichbar(client):
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        frei = s.getsockname()[1]
    antwort = verbinden(client, frei)
    assert antwort.status_code == 503 and 'antwortet gerade nicht' in antwort.json()['detail']
    nichts_gespeichert(client)


def test_haengende_namensaufloesung_endet_an_der_wanduhr(client, monkeypatch):
    # `socket.getaddrinfo` kennt keine Zeitgrenze; die Wanduhr um die Anmeldung fängt auch das.
    monkeypatch.setattr(mail_anmeldung, 'ZEITGRENZE', 0.5)
    monkeypatch.setattr(MailConnector, 'pruefe_anmeldung', lambda self, timeout=8.0: time.sleep(5))
    start = time.monotonic()
    antwort = verbinden(client, 993, host='imap.web.de')
    assert time.monotonic() - start < 3
    assert antwort.status_code == 503 and antwort.json()['detail'].startswith('WEB.DE antwortet gerade nicht.')
    nichts_gespeichert(client)


def test_ohne_passwort_nur_vorbereitet_ohne_anmeldung(client, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(MailConnector, 'pruefe_anmeldung', lambda self, timeout=8.0: aufrufe.append(1))
    antwort = client.post('/api/v1/integrations/mail', json={'label': 'Vorbereitet', 'imap_host': 'imap.example.test',
                                                              'user': ADRESSE})
    assert antwort.status_code == 201 and aufrufe == []
    assert client.get('/api/v1/einrichtung').json()['vorhanden']['mail'] is False


@pytest.mark.parametrize(('host', 'text', 'grund', 'teil'), [
    ('imap.web.de', b'[AUTHENTICATIONFAILED] Authentication failed', 'passwort',
     'WEB.DE hat die Anmeldung abgelehnt: Das Passwort stimmt nicht, oder IMAP ist'),
    ('imap.gmail.com', b'[ALERT] Application-specific password required', 'app_passwort', 'App-Passwort nötig'),
    # Gmail lehnt das normale Passwort mit diesem Text ab; erkannt am Server und am Text (Fremdprobe, Befund 2).
    ('imap.gmail.com', b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)', 'app_passwort', 'App-Passwort nötig'),
    ('imap.probe.example', b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)', 'app_passwort',
     'Google-Seite „App-Passwörter“'),
    ('outlook.office365.com', b'[ALERT] Application-specific password required', 'app_passwort',
     'Outlook / Microsoft 365 verlangt ein App-Passwort'),
    ('imap.gmx.net', b'IMAP access is disabled', 'imap_aus', 'GMX lässt die Anmeldung über IMAP nicht zu'),
    ('imap.example.test', b'LOGIN failed', 'passwort', 'Adresse oder Passwort stimmen nicht.'),
])
def test_gruende_in_einem_satz(host, text, grund, teil):
    fehler = mail_anmeldung.einordnen(imaplib.IMAP4.error(text), host, 'Eigenes Postfach')
    assert fehler.grund == grund and teil in fehler.satz
    # Ein Satz: ein Satzende, am Schluss (Punkte in Namen wie „WEB.DE“ zählen nicht).
    assert fehler.satz.endswith('.') and '. ' not in fehler.satz


def test_abbruch_und_netzfehler_sind_nicht_erreichbar():
    for fehler in (imaplib.IMAP4.abort('socket error: EOF'), socket.gaierror(-3, 'Temporary failure'),
                   ConnectionRefusedError(), TimeoutError(10.0)):
        assert mail_anmeldung.einordnen(fehler, 'imap.web.de').grund == 'nicht_erreichbar'


def test_erreichbar_meldet_ein_schweigendes_postfach_mit_satz(client, attrappe, monkeypatch):
    """Befund 5: Die Fertig-Seite fragt, ob das verbundene Postfach gerade antwortet, statt „bereit“ zu behaupten."""
    assert verbinden(client, attrappe.port).status_code == 201
    [konto] = client.get('/api/v1/mail/erreichbar').json()['accounts']
    assert konto['erreichbar'] is True and konto['satz'] is None and konto['label'] == 'Probe-Post'
    monkeypatch.setattr(mail_anmeldung, 'ZEITGRENZE', 1.0)
    attrappe.modus = 'stumm'
    start = time.monotonic()
    [konto] = client.get('/api/v1/mail/erreichbar').json()['accounts']
    assert time.monotonic() - start < 5
    assert konto['erreichbar'] is False and konto['grund'] == 'nicht_erreichbar'
    assert konto['satz'].startswith('Probe-Post antwortet gerade nicht.')
    attrappe.modus = 'ablehnen'
    [konto] = client.get('/api/v1/mail/erreichbar').json()['accounts']
    assert konto['erreichbar'] is False and konto['grund'] == 'passwort'


def test_erreichbar_ohne_konto_ist_leer(client):
    assert client.get('/api/v1/mail/erreichbar').json() == {'accounts': []}


def test_connector_prueft_mit_echter_anmeldung(attrappe):
    connector = MailConnector(MailConfig(imap_host='127.0.0.1', imap_port=attrappe.port, username=ADRESSE,
                                         password='erfunden'))
    connector._context = attrappe.client_kontext()
    with pytest.raises(mail_anmeldung.Anmeldefehler) as fehler:
        mail_anmeldung.pruefe(connector, '127.0.0.1', name='Probe-Post')
    assert fehler.value.grund == 'passwort' and fehler.value.status == 422


def test_google_lehnt_ab_und_die_einrichtung_sagt_app_passwort_noetig(client, attrappe):
    """Befund 2: Gmail über IMAP mit App-Passwort; das normale Passwort lehnt Google ab, und das steht so da."""
    attrappe.modus = 'google_ablehnen'
    antwort = verbinden(client, attrappe.port, passwort='mein-normales-passwort')
    assert antwort.status_code == 422, antwort.text
    assert antwort.json()['grund'] == 'app_passwort'
    assert antwort.json()['detail'].startswith('App-Passwort nötig:')
    assert 'Bestätigung in zwei Schritten' in antwort.json()['detail']
    nichts_gespeichert(client)


def test_gmail_karte_erklaert_den_weg_in_zwei_saetzen_mit_der_richtigen_seite():
    from icarus_memory.providers_mail import BY_ID
    gmail = BY_ID['gmail']
    assert gmail.app_password and gmail.help_url == 'https://myaccount.google.com/apppasswords'
    assert gmail.hint.count('. ') == 1 and gmail.hint.endswith('.'), 'zwei Sätze'
    assert 'zwei Schritten' in gmail.hint and 'App-Passwort' in gmail.hint
    assert gmail.kalender_ical and 'iCal' in gmail.caldav_note
