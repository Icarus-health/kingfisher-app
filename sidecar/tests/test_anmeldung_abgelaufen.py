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
from types import SimpleNamespace

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
    vorher = len(postfach.anmeldungen)
    hintergrund_takte(client, 6)
    assert len(postfach.anmeldungen) - vorher == 1, 'ein abgelehntes Passwort wird nicht in jedem Takt neu probiert'
    eins, zwei = _stand(client, konto)
    # Eine Aussage an allen Stellen: dieselbe in „Für Techniker“, auf Heute und in der Einrichtung.
    assert eins['zustand'] == zwei['zustand'] == 'fehler'
    assert eins['satz'] == zwei['satz'] == SATZ
    assert eins['verweis'] == zwei['verweis'] == 'zugaenge'
    for text in (eins['satz'], str(eins.get('technik'))):
        assert 'AUTHENTICATIONFAILED' not in text and 'Authentication failed' not in text

    # Unter Zugänge: Nur das Passwort, die Adresse kennt Kingfisher. Ein falsches wird mit Satz abgelehnt.
    from icarus_memory.server import _integration_secret
    geweckt = []
    client.app.state.scheduler.aufnahme_wecken = lambda: geweckt.append(True)
    falsch = client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': 'immer-noch-falsch'})
    assert falsch.status_code == 422 and 'abgelehnt' in falsch.json()['detail']
    assert _integration_secret(client.app, 'mail', konto) == PASSWORT, 'abgelehnt heißt: nichts gespeichert'
    assert _stand(client, konto)[0]['zustand'] == 'fehler' and not geweckt
    richtig = client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': 'neues-geheimnis'})
    assert richtig.status_code == 200, richtig.text
    assert [a['id'] for a in richtig.json()['mail_accounts']] == [konto], 'kein zweites Postfach'
    assert _integration_secret(client.app, 'mail', konto) == 'neues-geheimnis'
    assert geweckt, 'die Aufnahme liest gleich weiter, nicht erst nach dem Takt'
    # Der Grund ist sofort weg, nicht erst nach dem nächsten Abruf.
    assert _stand(client, konto)[0]['zustand'] != 'fehler'
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
    geweckt = []
    app.state.scheduler.aufnahme_wecken = lambda: geweckt.append(True)
    assert anmelden(client)['status'] == 'connected'
    # Ohne weiteren Abruf: Die neue Anmeldung löscht den gemerkten Grund und weckt die Aufnahme.
    assert client.get('/api/v1/microsoft/konten').json()['konten'][0]['verbunden'] is True
    assert geweckt
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == post['id'])
    assert stand['zustand'] != 'fehler'


# -- Befunde des Reviews ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    '[LIMIT] Too many login attempts, try again later',
    '[ALERT] Too many simultaneous connections. (Failure)',
    '[INUSE] Mailbox in use by another session',
    '[SERVERBUG] Internal error occurred',
    'Temporary server error. Please try again later',
])
def test_voruebergehende_ablehnungen_sind_keine_abgelaufene_anmeldung(tmp_path, text):
    assert _grund(tmp_path, _mit_ursache(AnmeldungAbgelehnt(text))) == 'inventory_unavailable'


@pytest.mark.parametrize('text', [
    '[AUTHENTICATIONFAILED] Invalid credentials',
    '[AUTHORIZATIONFAILED] Not authorized for this mailbox',
    '[EXPIRED] Password expired',
    'Login failed.',
])
def test_echte_ablehnungen_bleiben_anmeldung(tmp_path, text):
    assert _grund(tmp_path, _mit_ursache(AnmeldungAbgelehnt(text))) == 'anmeldung'


class Zaehlend(Fehlerhaft):
    def __init__(self, fehler):
        super().__init__(fehler)
        self.versuche = 0

    def inventory_page(self, *args, **kwargs):
        self.versuche += 1
        raise self.fehler


def test_ein_abgelehntes_passwort_wird_nicht_jeden_takt_neu_probiert(tmp_path, monkeypatch):
    # Jeder Versuch ist eine Anmeldung beim Anbieter; viele abgelehnte führen dort zur Kontosperre.
    uhr = [1_000_000.0]
    monkeypatch.setattr('icarus_memory.mail_intake.time', SimpleNamespace(time=lambda: uhr[0]))
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    leser = Zaehlend(_mit_ursache(AnmeldungAbgelehnt('[AUTHENTICATIONFAILED] Authentication failed.')))
    for _ in range(10):
        intake.step('a', leser, nur_neu=True)
        intake.step('a', leser)
        uhr[0] += 30
    assert leser.versuche == 1 and intake.status('a')['error'] == 'anmeldung'
    uhr[0] += 3600  # höchstens ein seltener Wiederversuch
    intake.step('a', leser)
    intake.step('a', leser)
    assert leser.versuche == 2
    # Neu angemeldet: Der Grund ist gelöscht, und es geht sofort weiter.
    intake.anmeldung_erneuert('a')
    assert intake.status('a')['error'] is None
    intake.step('a', leser)
    assert leser.versuche == 3
    ep.close()


def test_neu_anmelden_braucht_den_zugang_wie_jede_andere_route(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'geheim')
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    with TestClient(create_app()) as http:
        assert http.post('/api/v1/integrations/mail/irgendeins/anmelden', json={'password': 'x'}).status_code in (401, 403)
        assert http.post('/api/v1/integrations/mail/irgendeins/anmelden', json={'password': 'x'},
                         headers={'X-Icarus-Token': 'geheim'}).status_code == 404


def test_ein_zu_langes_passwort_steht_nicht_in_der_ablehnung(client, postfach):
    konto = einlesen_starten(client, postfach)
    geheim = 'geheim-' + 'x' * 5000
    antwort = client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': geheim})
    assert antwort.status_code == 422
    assert 'xxxxxxxxxx' not in antwort.text and 'geheim-' not in antwort.text
    # Andere Felder dürfen ihre Eingabe weiter nennen; nur Geheimnisse nicht.
    zu_lang = client.post('/api/v1/integrations/mail', json={'label': 'L' * 200, 'imap_host': 'h', 'user': 'u',
                                                            'password': geheim})
    assert zu_lang.status_code == 422 and 'geheim-' not in zu_lang.text


def test_ohne_gemerkten_grund_weckt_eine_anmeldung_die_aufnahme_nicht(tmp_path):
    # Die erste Microsoft-Verbindung (oder ein vorsorglich neu eingegebenes Passwort) hat nichts fortzusetzen: Dann
    # bleibt der Zeitplan in seinem Takt, statt mitten in einen laufenden Durchgang einen zweiten zu schieben.
    from icarus_memory.mail_intake import nach_neuer_anmeldung
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    Intake(ep).start('a', ['INBOX'])
    geweckt = []
    app = SimpleNamespace(state=SimpleNamespace(episodes=ep, scheduler=SimpleNamespace(aufnahme_wecken=lambda: geweckt.append(True))))
    nach_neuer_anmeldung(app, 'a')
    assert geweckt == []
    with ep.transaction():
        ep._conn.execute("UPDATE mail_intake_folders SET error='anmeldung' WHERE account='a'")
    nach_neuer_anmeldung(app, 'a')
    assert geweckt == [True]
    with ep._lock:
        assert ep._conn.execute("SELECT error FROM mail_intake_folders WHERE account='a'").fetchone()[0] is None
    ep.close()


GEHEIM_IN_DER_ANFRAGE = 'geheim-synthetisch-4711'


@pytest.mark.parametrize('methode, pfad, inhalt', [
    # Nach-Review 3: Fehlt ein anderes Pflichtfeld, nannte FastAPI das ganze Objekt als Eingabe, samt Passwort.
    ('post', '/api/v1/integrations/mail', {'label': 'Privat', 'imap_host': 'imap.example.org',
                                           'password': GEHEIM_IN_DER_ANFRAGE}),
    ('post', '/api/v1/integrations/calendar', {'label': 'Privat', 'kind': 'caldav',
                                               'password': GEHEIM_IN_DER_ANFRAGE}),
    ('post', '/api/v1/integrations/calendar/anmelden', {'password': GEHEIM_IN_DER_ANFRAGE}),
    ('put', '/api/v1/setup', {'mail': {'imap_host': 'imap.example.org', 'password': GEHEIM_IN_DER_ANFRAGE},
                              'mail_password': GEHEIM_IN_DER_ANFRAGE, 'onboarded': 'vielleicht'}),
    ('post', '/api/v1/integrations/mail', [GEHEIM_IN_DER_ANFRAGE]),
])
def test_eine_ablehnung_nennt_kein_geheimnis_auch_wenn_ein_anderes_feld_fehlt(client, methode, pfad, inhalt):
    antwort = getattr(client, methode)(pfad, json=inhalt)
    assert antwort.status_code == 422, antwort.text
    assert GEHEIM_IN_DER_ANFRAGE not in antwort.text
    assert antwort.json()['detail'], 'die Ablehnung sagt weiter, welches Feld fehlt'


# -- Nach-Review 2: Die Ruhe gilt kontoweit, für jede Verbindung -------------------------------------------------------

class _ImapZaehler:
    """Ein IMAP-Server, der jede Anmeldung zählt und mit `antwort` ablehnt (oder annimmt, wenn `antwort` leer ist)."""

    def __init__(self, antwort='[AUTHENTICATIONFAILED] Authentication failed.'):
        self.antwort, self.anmeldungen = antwort, []
        zaehler = self

        class Verbindung:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def login(self, benutzer, passwort):
                zaehler.anmeldungen.append(passwort)
                if zaehler.antwort:
                    raise imaplib.IMAP4.error(zaehler.antwort)

            def select(self, *a, **kw):
                return 'OK', [b'0']

            def uid(self, *a):
                return 'OK', [b'']

            def response(self, *a):
                return 'OK', [b'7']
        self.Verbindung = Verbindung


def test_eine_abgelehnte_anmeldung_ruht_fuer_jede_verbindung_mit_denselben_zugangsdaten(monkeypatch):
    from icarus_memory.connectors import mail as connector_mail
    uhr = [1_000_000.0]
    monkeypatch.setattr(connector_mail, '_ruhe_uhr', lambda: uhr[0])
    server = _ImapZaehler()
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', server.Verbindung)
    alt = MailConfig('imap.example.org', 'lena@example.org', 'altes-passwort')
    with pytest.raises(MailError):
        MailConnector(alt).inventory_page('INBOX')
    assert len(server.anmeldungen) == 1
    # Posteingang, Ordnerliste, ein neu gebauter Leser (wie nach jeder Änderung der Einstellungen): keine Anmeldung.
    for versuch in (lambda c: c.inbox(limit=5), lambda c: c.folders(), lambda c: c.inventory_page('Archiv')):
        with pytest.raises(MailError) as gefangen:
            versuch(MailConnector(alt))
        assert einordnen(gefangen.value.__cause__, 'imap.example.org').grund == 'passwort'
    assert len(server.anmeldungen) == 1, 'die Ruhe gilt für jede Verbindung mit denselben Zugangsdaten'
    # Ein neues Passwort (Neu anmelden) gilt sofort; die ausdrückliche Prüfung fragt immer den Server.
    with pytest.raises(imaplib.IMAP4.error):
        MailConnector(alt).pruefe_anmeldung()
    assert len(server.anmeldungen) == 2
    with pytest.raises(MailError):
        MailConnector(MailConfig('imap.example.org', 'lena@example.org', 'neues-passwort')).inventory_page('INBOX')
    assert len(server.anmeldungen) == 3
    # Nach einer Stunde genau ein neuer Versuch mit dem alten Passwort.
    uhr[0] += 3601
    for _ in range(3):
        with pytest.raises(MailError):
            MailConnector(alt).inventory_page('INBOX')
    assert len(server.anmeldungen) == 4


def test_eine_voruebergehende_ablehnung_wartet_wachsend(monkeypatch):
    # Nach-Review 4: „too many failed login attempts“ alle 30 s erneut zu versuchen verlängert die Sperre beim Anbieter.
    from icarus_memory.connectors import mail as connector_mail
    uhr = [1_000_000.0]
    monkeypatch.setattr(connector_mail, '_ruhe_uhr', lambda: uhr[0])
    server = _ImapZaehler('[LIMIT] Too many connections, try again later')
    monkeypatch.setattr('icarus_memory.connectors.mail.imaplib.IMAP4_SSL', server.Verbindung)
    zugang = MailConfig('imap.example.org', 'lena@example.org', 'passwort')
    zeiten = []
    for _ in range(240):  # zwei Stunden im 30-Sekunden-Takt
        try:
            MailConnector(zugang).inventory_page('INBOX')
        except MailError as fehler:
            assert einordnen(fehler.__cause__, 'imap.example.org').grund == 'nicht_erreichbar'
        if len(server.anmeldungen) > len(zeiten):
            zeiten.append(uhr[0])
        uhr[0] += 30
    abstaende = [b - a for a, b in zip(zeiten, zeiten[1:])]
    assert len(zeiten) <= 8 and abstaende == sorted(abstaende) and abstaende[-1] >= 1200, abstaende
    # Gelingt die Anmeldung, ist alles vergessen.
    server.antwort = ''
    uhr[0] += 1800
    MailConnector(zugang).inventory_page('INBOX')
    vorher = len(server.anmeldungen)
    MailConnector(zugang).inventory_page('INBOX')
    assert len(server.anmeldungen) == vorher + 1


def test_die_ruhe_gilt_fuer_das_ganze_postfach_nicht_je_ordner(tmp_path, monkeypatch):
    # Nach-Review 2b: Mit sechs Ordnern ruhte jeder Ordner für sich, sechs Fehlanmeldungen je Stunde.
    uhr = [1_000_000.0]
    monkeypatch.setattr('icarus_memory.mail_intake.time', SimpleNamespace(time=lambda: uhr[0]))
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX', 'Archiv', 'Gesendet', 'Rechnungen', 'Verein', 'Familie'])
    leser = Zaehlend(_mit_ursache(AnmeldungAbgelehnt('[AUTHENTICATIONFAILED] Authentication failed.')))
    for _ in range(120):  # eine Stunde im 30-Sekunden-Takt
        intake.step('a', leser)
        uhr[0] += 30
    assert leser.versuche == 1, leser.versuche
    uhr[0] += 30
    for _ in range(4):
        intake.step('a', leser)
    assert leser.versuche == 2
    ep.close()


def test_offene_mails_werden_nach_abgelehnter_anmeldung_nicht_einzeln_abgeholt(tmp_path, monkeypatch):
    # Nicht gefangene Sabotage: Die Ruhe bei der Auswahl der Einträge fehlte, und kein Test hatte offene Einträge.
    uhr = [1_000_000.0]
    monkeypatch.setattr('icarus_memory.mail_intake.time', SimpleNamespace(time=lambda: uhr[0]))
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    with ep.transaction():
        ep._conn.execute("UPDATE mail_intake_folders SET generation='7',upper_uid=5,live_uid=5,inventory_complete=1")
        for uid in range(1, 6):
            ep._conn.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane) VALUES('a','INBOX','7',?,'history')", (uid,))
    abgelehnt = _mit_ursache(AnmeldungAbgelehnt('[AUTHENTICATIONFAILED] Authentication failed.'))

    class Abholend(Zaehlend):
        def message_in_folder(self, folder, uid):
            self.versuche += 1
            raise abgelehnt
    leser = Abholend(abgelehnt)
    for _ in range(10):
        intake.step('a', leser)
        uhr[0] += 30
    assert leser.versuche == 1, leser.versuche
    with ep._lock:
        assert ep._conn.execute("SELECT COUNT(*) FROM mail_intake_items WHERE status='pending' AND attempts=0").fetchone()[0] == 5
    ep.close()


def test_geaendertes_passwort_heute_nachrichten_und_nachtrag_klopfen_nicht_an(client, postfach):
    # Nach-Review 2a und 2c: Der Nachtrag der Beteiligten und der Posteingang auf Heute und unter „Nachrichten“
    # meldeten sich mit dem alten Passwort weiter an. Jetzt ruht das Konto für jede Verbindung, und der Satz sagt,
    # was zu tun ist.
    konto = einlesen_starten(client, postfach)
    hintergrund_takte(client)
    store = client.app.state.episodes
    with store.transaction():
        # Ältere Mails ohne Beteiligte (vor der Rollenangabe aufgenommen): Der Nachtrag holt ihre Kopfzeilen.
        store._conn.execute("UPDATE episodes SET document=json_remove(document,'$.contacts') WHERE kind='message'")
    postfach.passwort = 'neues-geheimnis'
    vorher = len(postfach.anmeldungen)
    hintergrund_takte(client, 6)
    for _ in range(3):
        nachrichten = client.get('/api/v1/messages').json()
        heute = client.get('/dashboard').json()
    assert len(postfach.anmeldungen) - vorher == 1, postfach.anmeldungen[vorher:]
    satz = nachrichten['partial_failure']['message']
    assert 'Zugänge neu an' in satz and 'antwortet gerade nicht' not in satz, satz
    assert 'Zugänge neu an' in heute['mail']['error'] and 'sobald es wieder antwortet' not in heute['mail']['error']
    # Neu angemeldet: alles geht wieder, ohne Wartezeit.
    assert client.post(f'/api/v1/integrations/mail/{konto}/anmelden', json={'password': 'neues-geheimnis'}).status_code == 200
    assert client.get('/api/v1/messages').json().get('partial_failure') is None


@pytest.mark.parametrize('wo', ['bestandsaufnahme', 'abholen'])
def test_ein_laufender_schritt_ueberschreibt_die_neue_anmeldung_nicht(tmp_path, wo):
    # Nach-Review 8: Scheiterte ein noch laufender Schritt mit dem alten Passwort, nachdem „Neu anmelden“ den Grund
    # gelöscht hatte, schrieb er `anmeldung` zurück. Gilt der Leser nicht mehr (`permitted`), schreibt er nichts.
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    if wo == 'abholen':
        with ep.transaction():
            ep._conn.execute("UPDATE mail_intake_folders SET generation='7',upper_uid=1,live_uid=1,inventory_complete=1")
            ep._conn.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane) VALUES('a','INBOX','7',1,'history')")
    gilt = [True]
    abgelehnt = _mit_ursache(AnmeldungAbgelehnt('[AUTHENTICATIONFAILED] Authentication failed.'))

    class Alt(Fehlerhaft):
        def _neu_angemeldet_und_scheitern(self):
            intake.anmeldung_erneuert('a')  # derweil unter Zugänge neu angemeldet: neuer Leser
            gilt[0] = False
            raise abgelehnt

        def inventory_page(self, *a, **kw):
            if wo == 'abholen':
                return dict(folder='INBOX', uidvalidity='7', upper_uid=1, uids=[], next_uid=1, done=True)
            self._neu_angemeldet_und_scheitern()

        def message_in_folder(self, folder, uid):
            self._neu_angemeldet_und_scheitern()
    intake.step('a', Alt(abgelehnt), permitted=lambda: gilt[0])
    assert intake.status('a')['error'] is None
    with ep._lock:
        assert ep._conn.execute("SELECT error FROM mail_intake_folders").fetchone()[0] is None
    ep.close()


def test_eine_neue_anmeldung_hebt_die_ruhe_auch_fuer_google_auf(tmp_path):
    # Bei XOAUTH2 wechselt das Token stündlich; der Fingerabdruck der Ruhe ist deshalb fest. Neu anmelden vergisst sie.
    from icarus_memory.connectors.mail import ANMELDERUHE
    from icarus_memory.mail_intake import nach_neuer_anmeldung
    google = MailConnector(MailConfig('imap.gmail.com', 'Lena.Probe@gmail.example', '', access_token=lambda: 'token-1'))
    ANMELDERUHE.abgelehnt(google._ruhe_schluessel(), echt=True)
    assert google.anmeldung_ruht()
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    app = SimpleNamespace(state=SimpleNamespace(episodes=ep, settings=SimpleNamespace(
        mail_accounts=[SimpleNamespace(id='g', user='lena.probe@gmail.example')])))
    nach_neuer_anmeldung(app, 'g')
    assert not google.anmeldung_ruht()
    ep.close()


@pytest.mark.parametrize('text, host, erwartet', [
    # Nach-Review 4: Der ausdrückliche Code geht dem Freitext vor.
    ('[AUTHENTICATIONFAILED] Too many failed login attempts, try again later', 'imap.example.org', 'passwort'),
    ('[AUTHORIZATIONFAILED] Temporary restriction on this account', 'imap.example.org', 'passwort'),
    ('[EXPIRED] Password expired, try again later after changing it', 'imap.example.org', 'passwort'),
    # Gmail: ein Kontingent, kein fehlendes App-Passwort.
    ('[ALERT] Account exceeded command or bandwidth limits. (Failure)', 'imap.gmail.com', 'nicht_erreichbar'),
    # Nicht gefangene Sabotage: „temporar“ allein, ohne „try again later“ und ohne Code.
    ('Temporary authentication failure', 'imap.example.org', 'nicht_erreichbar'),
])
def test_der_code_geht_dem_freitext_vor(text, host, erwartet):
    assert einordnen(imaplib.IMAP4.error(text), host).grund == erwartet


def test_der_nachtrag_der_beteiligten_ruht_mit_dem_postfach(tmp_path, monkeypatch):
    # Nach-Review 2a: Der Nachtrag fragte nur `store.aktiv` und holte jede Mail mit einer eigenen Anmeldung. `aktiv`
    # (seine Freigabe im Zeitplan) gilt jetzt nicht, solange das Postfach nach einer Ablehnung ruht.
    uhr = [1_000_000.0]
    monkeypatch.setattr('icarus_memory.mail_intake.time', SimpleNamespace(time=lambda: uhr[0]))
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX', 'Archiv'])
    assert intake.aktiv('a', lambda: True)
    with ep.transaction():
        ep._conn.execute("UPDATE mail_intake_folders SET error='anmeldung',updated=? WHERE folder='Archiv'", (uhr[0],))
    assert not intake.aktiv('a', lambda: True) and intake.anmeldung_ruht('a')
    uhr[0] += 3601
    assert intake.aktiv('a', lambda: True), 'nach der Ruhezeit ein neuer Versuch'
    ep.close()
