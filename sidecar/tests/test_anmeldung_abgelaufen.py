"""Abgelaufene Anmeldung ehrlich melden (statt „antwortet gerade nicht. Du musst nichts tun“).

Früher wurde jeder Fehler der Bestandsaufnahme zu `inventory_unavailable`: Ein Postfach, dessen Passwort geändert oder
dessen Microsoft-Anmeldung abgelaufen war, stand für immer als „antwortet gerade nicht. Du musst nichts tun: Kingfisher
versucht es von selbst noch einmal“ da. Jetzt erkennt die Aufnahme Anmeldefehler mit der vorhandenen Einordnung
(`mail_anmeldung.einordnen`, `MicrosoftFehler`), merkt den Grund `anmeldung` und sagt in einem Satz, was zu tun ist,
mit Verweis auf Einstellungen → Zugänge. Dort lässt sich das Postfach neu anmelden. Nur synthetische Zugänge.
"""
from __future__ import annotations

import imaplib
import socket
from datetime import datetime, timezone

import pytest

from icarus_memory.connectors.mail import AnmeldungAbgelehnt, MailConfig, MailConnector, MailError, Message
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_anmeldung import einordnen
from icarus_memory.mail_intake import Intake
from icarus_memory.mail_stand import konto_stand
from icarus_memory.microsoft_anmeldung import GRUENDE, MicrosoftFehler
from icarus_memory.microsoft_graph import GraphFehler
from tests.imap_attrappe import PASSWORT
from tests.microsoft_hilfen import graph, kein_netz  # noqa: F401 - Fixtures
from tests.test_mailaufnahme_ende_zu_ende import client, einlesen_starten, hintergrund_takte, postfach  # noqa: F401
from tests.test_microsoft_routes import anmelden, sidecar  # noqa: F401

SATZ = ('Postfach Probe-Post lässt Kingfisher nicht mehr hinein: Die Anmeldung ist abgelaufen oder das Passwort hat '
        'sich geändert. Melde dich unter Einstellungen → Zugänge neu an.')


class Fehlerhaft:
    """Ein Postfach, dessen Bestandsaufnahme mit `fehler` scheitert."""

    def __init__(self, fehler):
        self.fehler = fehler

    def inventory_page(self, *args, **kwargs):
        raise self.fehler

    def message_in_folder(self, folder, uid):  # pragma: no cover - die Bestandsaufnahme scheitert vorher
        return Message(uid, 'x', 'a@example.org', datetime(2026, 1, 1, tzinfo=timezone.utc), 'x', False, body='x')


def _mit_ursache(ursache):
    """So kommt ein Fehler von `imaplib` aus `MailConnector`: als `MailError` mit der Ursache dahinter."""
    try:
        raise ursache
    except Exception as gefangen:  # noqa: BLE001
        try:
            raise MailError(f'IMAP-Zugriff fehlgeschlagen: {gefangen}') from gefangen
        except MailError as fehler:
            return fehler


def _grund(tmp_path, fehler):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    intake.step('a', Fehlerhaft(fehler))
    grund = intake.status('a')['error']
    ep.close()
    return grund


@pytest.mark.parametrize('fehler', [
    _mit_ursache(AnmeldungAbgelehnt('[AUTHENTICATIONFAILED] Authentication failed.')),
    _mit_ursache(AnmeldungAbgelehnt('Invalid credentials (Failure)')),
    _mit_ursache(AnmeldungAbgelehnt('IMAP access is disabled for this account')),
    MicrosoftFehler('abgemeldet'),
    GraphFehler('abgemeldet'),
], ids=['passwort', 'google', 'imap_aus', 'microsoft_token', 'graph_401'])
def test_abgelehnte_anmeldung_wird_als_anmeldung_gemerkt(tmp_path, fehler):
    assert _grund(tmp_path, fehler) == 'anmeldung'


@pytest.mark.parametrize('fehler', [
    OSError('Connection refused'),
    _mit_ursache(socket.timeout('timed out')),
    _mit_ursache(AnmeldungAbgelehnt('[UNAVAILABLE] Temporary authentication failure')),
    # Eine Ablehnung nach der Anmeldung (etwa BAD auf eine Suche) ist keine abgelaufene Anmeldung.
    _mit_ursache(imaplib.IMAP4.error('SEARCH command error: BAD')),
    MailError('Nachrichtenbestand konnte nicht ermittelt werden.'),
    MicrosoftFehler('nicht_erreichbar'),
    GraphFehler('gedrosselt', 7),
], ids=['verweigert', 'zeitgrenze', 'voruebergehend', 'bad_nach_anmeldung', 'eigene_meldung', 'ms_netz', 'ms_drossel'])
def test_andere_fehler_bleiben_voruebergehend(tmp_path, fehler):
    assert _grund(tmp_path, fehler) == 'inventory_unavailable'


def test_connector_kennzeichnet_die_abgelehnte_anmeldung(monkeypatch):
    class Abweisend:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            raise imaplib.IMAP4.error('[AUTHENTICATIONFAILED] Authentication failed.')

    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', lambda *a, **kw: Abweisend())
    connector = MailConnector(MailConfig('imap.example.org', 'lena@example.org', 'falsch'))
    with pytest.raises(MailError) as gefangen:
        connector.inventory_page('INBOX')
    assert isinstance(gefangen.value.__cause__, AnmeldungAbgelehnt)
    # Die Prüfung beim Verbinden sieht weiter einen Fehler von `imaplib` und sagt denselben Satz wie bisher.
    with pytest.raises(imaplib.IMAP4.error) as direkt:
        connector.pruefe_anmeldung()
    assert einordnen(direkt.value, 'imap.example.org').grund == 'passwort'


def test_voruebergehend_abgelehnte_anmeldung_heisst_antwortet_nicht():
    fehler = imaplib.IMAP4.error('[UNAVAILABLE] Temporary authentication failure')
    assert einordnen(fehler, 'imap.example.org').grund == 'nicht_erreichbar'


def test_der_satz_sagt_was_zu_tun_ist_und_wohin():
    stand = konto_stand('Probe-Post', intake={'started': True, 'error': 'anmeldung', 'folders': []})
    assert stand['zustand'] == 'fehler' and stand['satz'] == SATZ and stand['verweis'] == 'zugaenge'
    # Gegenbeispiel: Ein Postfach, das gerade schweigt, bleibt „Du musst nichts tun“, ohne Verweis.
    schweigt = konto_stand('Probe-Post', intake={'started': True, 'error': 'inventory_unavailable', 'folders': []})
    assert 'Du musst nichts tun' in schweigt['satz'] and schweigt['verweis'] is None


def _stand(client, konto):
    eins = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == konto)
    zwei = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)['stand']
    return eins, zwei


def test_geaendertes_passwort_von_der_meldung_bis_zur_neuen_anmeldung(client, postfach):
    konto = einlesen_starten(client, postfach)
    hintergrund_takte(client)
    assert _stand(client, konto)[0]['zustand'] == 'aktuell'

    postfach.passwort = 'neues-geheimnis'  # beim Anbieter geändert
    hintergrund_takte(client, 1)
    eins, zwei = _stand(client, konto)
    # Eine Aussage an allen Stellen: dieselbe in „Für Techniker“, auf Heute und in der Einrichtung.
    assert eins['zustand'] == zwei['zustand'] == 'fehler'
    assert eins['satz'] == zwei['satz'] == SATZ
    assert eins['verweis'] == zwei['verweis'] == 'zugaenge'
    for text in (eins['satz'], str(eins.get('technik'))):
        assert 'AUTHENTICATIONFAILED' not in text and 'Authentication failed' not in text

    # Unter Zugänge: Nur das Passwort, die Adresse kennt Kingfisher. Ein falsches wird mit Satz abgelehnt.
    falsch = client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': 'immer-noch-falsch'})
    assert falsch.status_code == 422 and 'abgelehnt' in falsch.json()['detail']
    assert _stand(client, konto)[0]['zustand'] == 'fehler'
    richtig = client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': 'neues-geheimnis'})
    assert richtig.status_code == 200, richtig.text
    assert [a['id'] for a in richtig.json()['mail_accounts']] == [konto], 'kein zweites Postfach'
    hintergrund_takte(client, 1)
    assert _stand(client, konto)[0]['zustand'] == 'aktuell'


def test_neu_anmelden_nur_fuer_postfaecher_mit_passwort(client, postfach):
    konto = einlesen_starten(client, postfach)
    assert client.post('/api/v1/integrations/mail/unbekannt/anmelden', json={'password': PASSWORT}).status_code == 404
    eintrag = next(e for e in client.app.state.settings.mail_accounts if e.id == konto)
    eintrag.auth_method = 'microsoft_graph'
    assert client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': PASSWORT}).status_code == 409


def test_abgelaufene_microsoft_anmeldung_zeigt_neu_anmelden(sidecar, graph):
    app, client, _ = sidecar
    anmelden(client)
    post = next(m for m in client.get('/api/v1/integrations').json()['mail_accounts'] if m.get('auth') == 'microsoft')
    vorschau = client.get(f"/api/v1/mail/intake/{post['id']}/preview").json()
    assert client.post(f"/api/v1/mail/intake/{post['id']}/start", json={'folders': vorschau['folders']}).status_code == 200
    leser = app.state.mail.reader_for(post['id'])
    Intake(app.state.episodes).step(post['id'], leser, batch=5)
    assert client.get('/api/v1/microsoft/konten').json()['konten'][0]['verbunden'] is True

    graph.modus.add('refresh_abgelaufen')
    app.state.microsoft.tokens.clear()
    Intake(app.state.episodes).step(post['id'], leser, batch=5)
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == post['id'])
    assert stand['zustand'] == 'fehler' and stand['verweis'] == 'zugaenge' and 'Zugänge neu an' in stand['satz']
    # Unter Zugänge steht beim Microsoft-Konto dann „Neu anmelden“ (die Oberfläche zeigt es, wenn nicht verbunden).
    konto = client.get('/api/v1/microsoft/konten').json()['konten'][0]
    assert konto['verbunden'] is False and konto['satz'] == GRUENDE['abgemeldet']

    graph.modus.discard('refresh_abgelaufen')
    assert anmelden(client)['status'] == 'connected'
    Intake(app.state.episodes).step(post['id'], app.state.mail.reader_for(post['id']), batch=5)
    assert client.get('/api/v1/microsoft/konten').json()['konten'][0]['verbunden'] is True
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == post['id'])
    assert stand['zustand'] != 'fehler'
