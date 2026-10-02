"""Mailaufnahme von vorn bis hinten: Postfach verbinden, Einlesen starten, Mails stehen im Gedächtnis.

Fremdprobe 3, Befund 1: Alle fünf Mails scheiterten, weil die Aufnahme in einer wiederverwendeten IMAP-Sitzung die
UIDVALIDITY nicht mehr fand. Die bisherigen Attrappen hatten ein leeres Postfach und konnten das nicht zeigen. Hier
läuft der echte Weg über die API gegen eine IMAP-Attrappe, die wie ein normgerechter Server antwortet (UIDVALIDITY nur
bei SELECT/EXAMINE). Alle Mails sind synthetisch.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeStore
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from tests.imap_attrappe import PASSWORT, ImapAttrappe, probe_postfach

ADRESSE = 'lena.probe@example.org'


@pytest.fixture
def postfach(monkeypatch):
    with ImapAttrappe(nachrichten=probe_postfach(), uidvalidity=7) as dienst:
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
        app.state.scheduler.stop()


def einlesen_starten(client, postfach) -> str:
    antwort = client.post('/api/v1/integrations/mail', json={
        'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': postfach.port, 'user': ADRESSE,
        'sender': ADRESSE, 'password': PASSWORT})
    assert antwort.status_code == 201, antwort.text
    konto = client.get('/api/v1/integrations').json()['mail_accounts'][0]['id']
    umfang = client.get(f'/api/v1/mail/intake/{konto}/preview').json()
    assert umfang['folders'] == ['INBOX']
    gestartet = client.post(f'/api/v1/mail/intake/{konto}/start', json={'folders': umfang['folders']})
    assert gestartet.status_code == 200, gestartet.text
    return konto


def hintergrund_takte(client, anzahl: int = 3) -> None:
    """So, wie der Zeitplan die Aufnahme im Hintergrund antreibt (`server._wire_scheduler`), aber im Takt des Tests:
    Der Faden des Zeitplans ruht, damit kein zweiter Durchgang dazwischenkommt."""
    client.app.state.scheduler.stop()
    for _ in range(anzahl):
        client.app.state.scheduler._run_mail_intake()


def betreffe_im_gedaechtnis(client) -> set[str]:
    return {e['title'] for e in client.get('/episodes', params={'limit': 50}).json()}


def test_mails_aus_dem_postfach_landen_im_gedaechtnis(client, postfach):
    konto = einlesen_starten(client, postfach)
    hintergrund_takte(client)

    betreffe = betreffe_im_gedaechtnis(client)
    for betreff in ('Treffen am Montag', 'Bitte: Angebot Vereinsfest bis Freitag', 'Erinnerung an Ihren Termin',
                    'Nachtrag: Aufbau'):
        assert any(betreff in titel for titel in betreffe), (betreff, betreffe)

    stand = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    ordner = stand['folders'][0]
    assert ordner['failed'] == 0 and ordner['pending'] == 0
    # Jede Mail ist entweder im Gedächtnis oder bewusst ausgefiltert (der Newsletter), keine hängt.
    assert ordner['captured'] + ordner['filtered'] == ordner['total'] == 5
    assert stand['stand']['zustand'] == 'aktuell', stand['stand']
    # Bestand und Abruf teilen sich eine Sitzung: ein EXAMINE je Takt und Ordner, die Abrufe ohne neues EXAMINE.
    assert postfach.befehle.count('UID FETCH') == ordner['captured'] + ordner['filtered']
    assert postfach.befehle.count('EXAMINE') < postfach.befehle.count('UID FETCH')


def ohne_korrektur_aus_a771b17(monkeypatch):
    """Befund 1 nachstellen: Die Sitzung setzt die UIDVALIDITY bei Wiederverwendung nicht wieder ein."""
    from icarus_memory.connectors import mail

    def select_wie_vorher(self, ordner, frisch=True):
        if not frisch and self.folder == ordner:
            return 'OK'
        self.folder = None
        status = self._imap.select(ordner, readonly=True)[0]
        if status == 'OK':
            self.folder = ordner
        return status
    monkeypatch.setattr(mail._Sitzung, 'select', select_wie_vorher)


def test_gescheiterte_mails_sagen_warum_und_lassen_sich_erneut_versuchen(client, postfach, monkeypatch):
    """Befund 2: Scheitern ist nie still. Der Stand nennt den Grund in einem Satz, nicht „wird gelesen“."""
    ohne_korrektur_aus_a771b17(monkeypatch)
    konto = einlesen_starten(client, postfach)
    hintergrund_takte(client, 2)

    stand = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    assert stand['folders'][0]['failed_by'] == {'kennung': 5}
    satz = stand['stand']['satz']
    assert stand['stand']['zustand'] == 'gescheitert', stand['stand']
    assert '5 Mails kamen nicht ins Gedächtnis.' in satz and 'wird gelesen' not in satz
    # Technisches nur getrennt: Fehlerklasse und eigene Meldung, kein Fachwort im Satz.
    assert 'MailError' not in satz and 'UIDVALIDITY' not in satz
    assert 'MailError: Das Postfach liefert keine stabile Nachrichtenkennung.' in stand['stand']['technik']
    # Dieselbe Aussage an allen Stellen.
    assert client.get('/api/v1/mail/stand').json()['accounts'][0]['satz'] == satz

    # „Erneut versuchen“: sofort wieder offen, beim nächsten Takt mit behobener Ursache im Gedächtnis.
    monkeypatch.undo()
    monkeypatch.setenv('SSL_CERT_FILE', str(postfach.zertifikat))
    nach_klick = client.post(f'/api/v1/mail/intake/{konto}/retry').json()['accounts'][0]
    assert nach_klick['stand']['zustand'] == 'liest', nach_klick['stand']
    hintergrund_takte(client)
    stand = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    assert stand['stand']['zustand'] == 'aktuell', stand['stand']
    assert stand['stand']['technik'] is None
