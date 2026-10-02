"""Kalender wie Mail (Fremdprobe, Befund 7): Adresse genügt, Kalender selbst finden, vor dem Speichern anmelden.

Gegen eine CalDAV-Attrappe als echter HTTPS-Dienst (`caldav_attrappe.py`), nur synthetische Zugänge.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, kalender_anmeldung, providers_mail
from icarus_memory.audit import AuditLog
from icarus_memory.connectors.mail import MailConnector
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_anmeldung import Anmeldefehler
from icarus_memory.providers_mail import MailProvider
from icarus_memory.server import _configured_calendar, create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from tests.caldav_attrappe import PASSWORT, CaldavAttrappe

ADRESSE = 'lena.probe@example.org'


@pytest.fixture
def attrappe(monkeypatch):
    with CaldavAttrappe() as dienst:
        monkeypatch.setenv('SSL_CERT_FILE', str(dienst.zertifikat))
        yield dienst


@pytest.fixture
def probe_anbieter(attrappe, monkeypatch):
    anbieter = MailProvider(id='probepost', label='Probe-Post', imap_host='127.0.0.1', smtp_host='127.0.0.1',
                            domains=('example.org',), caldav_url=attrappe.start)
    monkeypatch.setattr(providers_mail, 'PROVIDERS', (*providers_mail.PROVIDERS, anbieter))
    return anbieter


@pytest.fixture
def client(tmp_path, monkeypatch, probe_anbieter):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     tasks=TaskStore(tmp_path / 'tasks.sqlite3'), workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'),
                     episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    with TestClient(app) as test_client:
        yield app, test_client


# -- Suche nach den Kalendern -------------------------------------------------------------------------------------

def test_findet_den_kalender_mit_terminen_selbst(attrappe):
    gefunden = kalender_anmeldung.finde_kalender(attrappe.start, ADRESSE, PASSWORT, wer='Probe-Post')
    # Nur der Kalender mit Terminen, nicht die Aufgabenliste; die Adresse ist vollständig.
    assert [(k.name, k.url) for k in gefunden] == [('Privat', f'https://127.0.0.1:{attrappe.port}/dav/calendars/lena.probe/privat/')]


def test_ohne_pfad_findet_er_den_kalender_ueber_die_bekannte_adresse(attrappe):
    gefunden = kalender_anmeldung.finde_kalender(f'https://127.0.0.1:{attrappe.port}/', ADRESSE, PASSWORT, wer='Probe')
    assert [k.name for k in gefunden] == ['Privat']


def test_falsches_passwort_ist_ein_satz_mit_grund(attrappe):
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.finde_kalender(attrappe.start, ADRESSE, 'erfunden', wer='Probe-Post')
    assert fehler.value.grund == 'passwort' and fehler.value.status == 422
    assert fehler.value.satz == 'Probe-Post hat die Anmeldung abgelehnt: Adresse oder Passwort stimmen nicht.'
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.finde_kalender(attrappe.start, ADRESSE, 'erfunden', wer='iCloud', app_passwort=True)
    assert 'App-Passwort' in fehler.value.satz


def test_ein_schweigender_dienst_kostet_hoechstens_die_zeitgrenze(attrappe):
    attrappe.modus = 'stumm'
    start = time.monotonic()
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.finde_kalender(attrappe.start, ADRESSE, PASSWORT, wer='Probe-Post', sekunden=1.5)
    assert time.monotonic() - start < 4
    assert fehler.value.grund == 'nicht_erreichbar' and fehler.value.status == 503
    assert fehler.value.satz.startswith('Probe-Post antwortet gerade nicht.')


def test_angemeldet_aber_ohne_kalender_sagt_das(attrappe):
    attrappe.modus = 'leer'
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.finde_kalender(attrappe.start, ADRESSE, PASSWORT, wer='Probe-Post')
    assert fehler.value.grund == 'kein_kalender'


def test_nur_verschluesselte_adressen():
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.finde_kalender('http://kalender.example.test/', ADRESSE, PASSWORT, wer='Probe')
    assert fehler.value.grund == 'adresse_fehlt'


# -- Startpunkt aus der Mailadresse -------------------------------------------------------------------------------

def test_startpunkt_aus_dem_katalog():
    anbieter, start = kalender_anmeldung.startpunkt('lena.probe@web.de', None)
    assert anbieter.label == 'WEB.DE' and start == anbieter.caldav_url and start.startswith('https://')
    for adresse in ('lena.probe@gmx.de', 'lena.probe@icloud.com', 'lena.probe@posteo.de', 'lena.probe@mailbox.org'):
        assert kalender_anmeldung.startpunkt(adresse, None)[1].startswith('https://'), adresse


def test_google_und_microsoft_sagen_ehrlich_dass_es_so_nicht_geht():
    for adresse in ('lena.probe@gmail.com', 'lena.probe@outlook.com'):
        with pytest.raises(Anmeldefehler) as fehler:
            kalender_anmeldung.startpunkt(adresse, None)
        assert fehler.value.grund == 'kein_zugang'


def test_unbekannter_anbieter_braucht_die_adresse():
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.startpunkt('lena.probe@eigene-domain.example', None, dns=lambda *_: [])
    assert fehler.value.grund == 'adresse_fehlt'
    assert fehler.value.satz.startswith('Für diesen Anbieter brauche ich die Adresse deines Kalenders.')
    assert kalender_anmeldung.startpunkt('lena.probe@eigene-domain.example', ' https://dav.example/ ')[1] == 'https://dav.example/'


def test_jede_kalenderadresse_im_katalog_ist_https_und_ohne_zugangsdaten():
    for anbieter in providers_mail.PROVIDERS:
        if anbieter.caldav_url:
            assert anbieter.caldav_url.startswith('https://') and '@' not in anbieter.caldav_url, anbieter.id
            assert not anbieter.caldav_note, f'{anbieter.id}: Adresse und Hinweis „geht nicht“ widersprechen sich'


# -- Die Route: anmelden, dann speichern --------------------------------------------------------------------------

def test_erst_anmelden_dann_speichern(client, attrappe):
    app, http = client
    abgelehnt = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'password': 'erfunden'})
    assert abgelehnt.status_code == 422 and abgelehnt.json()['grund'] == 'passwort'
    assert http.get('/api/v1/integrations').json()['calendar_sources'] == []
    attrappe.modus = 'stumm'
    kalender_anmeldung.ZEITGRENZE, alt = 1.5, kalender_anmeldung.ZEITGRENZE
    try:
        schweigt = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'password': PASSWORT})
    finally:
        kalender_anmeldung.ZEITGRENZE = alt
    assert schweigt.status_code == 503 and schweigt.json()['grund'] == 'nicht_erreichbar'
    assert http.get('/api/v1/integrations').json()['calendar_sources'] == []

    attrappe.modus = 'annehmen'
    antwort = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'password': PASSWORT})
    assert antwort.status_code == 201, antwort.text
    daten = antwort.json()
    assert daten['gefunden'] == ['Privat'] and daten['neu'] == 1 and daten['anbieter'] == 'Probe-Post'
    [quelle] = daten['calendar_sources']
    assert quelle['label'] == 'Probe-Post: Privat' and quelle['kind'] == 'caldav' and quelle['secret_present'] is True
    assert PASSWORT not in antwort.text
    # Kingfisher liest die Termine danach wirklich.
    termine = _configured_calendar(app).events(days=30)
    assert [t.summary for t in termine] == ['Probe-Termin beim Steuerbüro']
    # Ein zweiter Klick legt nichts doppelt an.
    noch_einmal = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'password': PASSWORT}).json()
    assert noch_einmal['neu'] == 0 and len(noch_einmal['calendar_sources']) == 1


def test_das_passwort_des_postfachs_gilt_nur_fuer_dieselbe_adresse(client, monkeypatch):
    app, http = client
    monkeypatch.setattr(MailConnector, 'pruefe_anmeldung', lambda self, timeout=8.0: None)
    for user in (ADRESSE, 'jemand.anders@example.org'):
        assert http.post('/api/v1/integrations/mail', json={'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'user': user,
                                                            'password': PASSWORT}).status_code == 201
    konten = {k['user']: k['id'] for k in http.get('/api/v1/integrations').json()['mail_accounts']}
    fremd = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'mail_konto': konten['jemand.anders@example.org']})
    assert fremd.status_code == 422 and fremd.json()['grund'] == 'passwort_fehlt'
    eigen = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'mail_konto': konten[ADRESSE]})
    assert eigen.status_code == 201 and eigen.json()['neu'] == 1


def test_unbekannter_anbieter_mit_eigener_adresse(client, attrappe):
    _, http = client
    ohne = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': 'lena@eigene-domain.example', 'password': PASSWORT})
    assert ohne.status_code == 422 and ohne.json()['grund'] == 'adresse_fehlt'
    mit = http.post('/api/v1/integrations/calendar/anmelden',
                    json={'adresse': 'lena@eigene-domain.example', 'password': PASSWORT, 'url': attrappe.start})
    assert mit.status_code == 201 and mit.json()['calendar_sources'][0]['label'] == '127.0.0.1: Privat'


def test_google_ohne_passwortweg_nennt_den_grund(client):
    _, http = client
    antwort = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': 'lena.probe@gmail.com', 'password': 'x'})
    assert antwort.status_code == 422 and antwort.json()['grund'] == 'kein_zugang' and 'Google' in antwort.json()['detail']


def test_auch_der_weg_fuer_techniker_meldet_sich_vorher_an(client, attrappe):
    _, http = client
    antwort = http.post('/api/v1/integrations/calendar', json={'label': 'Eigener', 'kind': 'caldav', 'url': attrappe.start,
                                                              'user': ADRESSE, 'password': 'erfunden'})
    assert antwort.status_code == 422 and antwort.json()['grund'] == 'passwort'
    assert http.get('/api/v1/integrations').json()['calendar_sources'] == []
