"""Microsoft 365 im echten Sidecar (`create_app`): erkennen, anmelden, Post und Kalender, Mitschriften, trennen.

Gegen die Graph-Attrappe auf 127.0.0.1; jeder andere Netzzugriff lässt den Test scheitern. Zusätzlich: Kein Token
steht in einer Antwort, im Protokoll oder in der Einstellungsdatei.
"""
from __future__ import annotations

import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, dns_abfrage
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from icarus_memory.microsoft_anmeldung import konto_schluessel
from icarus_memory.microsoft_graph import UMFANG
from icarus_memory.server import _configured_calendar, create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from tests.dns_attrappe import Namensdienst
from tests.graph_attrappe import ADRESSE, USER_CODE
from tests.microsoft_hilfen import graph, kein_netz  # noqa: F401 - Fixtures

GEHEIM = re.compile(r'geraet-geheim|erneuern-\d+|zugriff-\d+')


@pytest.fixture
def namensdienst(monkeypatch, kein_netz):
    """Der Namensdienst des Rechners ist die DNS-Attrappe auf 127.0.0.1 (`hochschule.example` liegt bei Microsoft)."""
    dns_abfrage.vergessen()
    dienst = Namensdienst()
    monkeypatch.setenv(dns_abfrage.UMGEBUNG, f'127.0.0.1:{dienst.port}')
    yield dienst
    dienst.schliessen()
    dns_abfrage.vergessen()


@pytest.fixture
def sidecar(graph, tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    caplog.set_level(logging.DEBUG)
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     tasks=TaskStore(tmp_path / 'tasks.sqlite3'), workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'),
                     episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    antworten: list[str] = []

    class Mitschreiber(TestClient):
        def request(self, *a, **k):
            antwort = super().request(*a, **k)
            antworten.append(antwort.text)
            return antwort
    with Mitschreiber(app) as client:
        yield app, client, antworten
    app.state.microsoft_halt.set()


def anmelden(client, mitschriften=False):
    start = client.post('/api/v1/microsoft/anmelden', json={'adresse': ADRESSE, 'mitschriften': mitschriften})
    assert start.status_code == 200, start.text
    assert start.json()['user_code'] == USER_CODE
    for _ in range(5):
        stand = client.get(f"/api/v1/microsoft/anmelden/{start.json()['sitzung']}").json()
        if stand['status'] != 'waiting':
            return stand
    raise AssertionError('Anmeldung nicht fertig')


def test_vom_erkennen_bis_zum_trennen(sidecar, graph, namensdienst, tmp_path, caplog):
    app, client, antworten = sidecar
    erkannt = client.get('/api/v1/integrations/mail-providers/erkennen', params={'adresse': ADRESSE}).json()
    assert (erkannt['dienst'], erkannt['art'], erkannt['erkannt_an']) == ('microsoft', 'organisation', 'mx')
    # Das Erkennen fragt Microsoft nicht (keine Anfrage an die Attrappe), nur den Namensdienst, und nur nach der Domain.
    assert graph.anfragen == []
    assert namensdienst.fragen == [('hochschule.example', 'MX')]

    graph.ablauf[:] = ['pending']
    fertig = anmelden(client)
    assert fertig['status'] == 'connected' and fertig['email'] == ADRESSE
    assert fertig['neu'] == ['post', 'kalender'] and fertig['mitschriften_an'] is False

    uebersicht = client.get('/api/v1/integrations').json()
    post = next(m for m in uebersicht['mail_accounts'] if m['user'] == ADRESSE)
    assert post['auth'] == 'microsoft' and post['secret_present'] and post['can_send'] is False
    kalender = next(c for c in uebersicht['calendar_sources'] if c['kind'] == 'microsoft')
    assert kalender['secret_present']

    # Post: derselbe Weg wie IMAP, mit eigenem Umfang.
    vorschau = client.get(f"/api/v1/mail/intake/{post['id']}/preview").json()
    assert vorschau['folders'] == ['INBOX', 'SentItems'] and vorschau['description'] == UMFANG
    assert client.post(f"/api/v1/mail/intake/{post['id']}/start", json={'folders': vorschau['folders']}).status_code == 200
    leser = app.state.mail.reader_for(post['id'])
    for _ in range(6):
        Intake(app.state.episodes).step(post['id'], leser, batch=5)
    stand = client.get('/api/v1/mail/intake').json()['accounts']
    ordner = {f['folder']: f for f in next(a for a in stand if a['account_id'] == post['id'])['folders']}
    assert ordner['INBOX']['captured'] == 7 and ordner['SentItems']['captured'] == 2
    assert client.get('/api/v1/mail/erreichbar').json()['accounts'][0]['erreichbar'] is True

    # Kalender wie jeder andere.
    termine = _configured_calendar(app).events(days=3)
    assert any(t.summary == 'Sprechstunde' for t in termine)

    # Teams-Mitschriften: zweite Anmeldung mit dem zusätzlichen Recht, dasselbe Konto, nichts doppelt.
    zweite = anmelden(client, mitschriften=True)
    assert zweite['status'] == 'connected' and zweite['neu'] == [] and zweite['mitschriften_an'] is True
    abgeholt = client.post('/api/v1/microsoft/mitschriften/abholen').json()
    assert abgeholt['ergebnis'][ADRESSE] == {'besprechungen': 1, 'aufgenommen': 1, 'ohne': 0}
    konto = abgeholt['konten'][0]
    assert konto['mitschriften'] and konto['besprechungen'][0]['stand'] == 'aufgenommen'
    quelle = app.state.episodes.get(app.state.episodes.source_head(f'microsoft:teams:{ADRESSE}:mitschrift-1'))
    assert 'transkript' in quelle.tags and quelle.title == 'Mitschrift: Haushalt Fakultät'
    assert 'Lena Probe: [' in quelle.body and 'Anna Keller' in quelle.participants
    assert app.state.zuordnungen.zeile(quelle.id) is not None, 'die Mitschrift wird einem Termin zugeordnet'

    # Kein Geheimnis in Antworten, Protokoll oder Einstellungen.
    assert not [t for t in antworten if GEHEIM.search(t)]
    assert not GEHEIM.search(caplog.text)
    einstellungen = (tmp_path / 'einstellungen.json').read_text()
    assert not GEHEIM.search(einstellungen) and 'refresh' not in einstellungen

    # Trennen: Erst der letzte Zugang des Kontos nimmt die Anmeldung mit.
    schluessel = konto_schluessel(ADRESSE)
    assert client.delete(f"/api/v1/integrations/mail/{post['id']}").status_code == 200
    assert app.state.microsoft.keychain.get(schluessel)
    assert client.delete(f"/api/v1/integrations/calendar/{kalender['id']}").status_code == 200
    assert not app.state.microsoft.keychain.get(schluessel)
    assert client.get('/api/v1/microsoft/konten').json()['konten'] == []


def test_anmeldung_scheitert_mit_einem_satz_und_legt_nichts_an(sidecar, graph):
    app, client, _ = sidecar
    graph.ablauf[:] = ['admin']
    stand = anmelden(client)
    assert stand['status'] == 'failed' and stand['grund'] == 'admin' and 'IT' in stand['satz']
    assert app.state.settings.mail_accounts == [] and app.state.settings.calendar_sources == []
    assert client.get('/api/v1/microsoft/anmelden/unbekannt').json()['status'] == 'expired'


def test_ohne_app_kennung_sagt_die_seite_was_fehlt(sidecar, monkeypatch):
    _, client, _ = sidecar
    monkeypatch.delenv('KINGFISHER_MS_CLIENT_ID')
    assert client.get('/api/v1/microsoft/config').json()['configured'] is False
    antwort = client.post('/api/v1/microsoft/anmelden', json={'adresse': ADRESSE})
    assert antwort.status_code == 422 and antwort.json()['grund'] == 'keine_app' and 'Techniker' in antwort.json()['detail']
    gesetzt = client.put('/api/v1/microsoft/config', json={'client_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'}).json()
    assert gesetzt['configured'] and gesetzt['quelle'] == 'einstellung'
    assert client.put('/api/v1/microsoft/config', json={'client_id': 'falsch'}).status_code == 422


def test_abgemeldetes_konto_sagt_es_beim_pruefen(sidecar, graph):
    app, client, _ = sidecar
    anmelden(client)
    graph.modus.add('refresh_abgelaufen')
    app.state.microsoft.tokens.clear()
    konten = client.get('/api/v1/mail/erreichbar').json()['accounts']
    assert konten[0]['erreichbar'] is False and konten[0]['grund'] == 'abgemeldet'
