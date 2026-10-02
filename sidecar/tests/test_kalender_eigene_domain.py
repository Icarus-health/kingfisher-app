"""Kalender einer eigenen Domain selbst finden (Fremdprobe 2, Befund 5): SRV `_caldavs._tcp`, dann `/.well-known/caldav`
auf dem Mailserver; nur das Passwort des Postfachs, und erst nachdem ohne Passwort feststeht, dass dort ein Kalender
antwortet. Gegen die CalDAV- und die Namensdienst-Attrappe, mit Netzsperre."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, config, dns_abfrage, kalender_anmeldung
from icarus_memory.mail_anmeldung import Anmeldefehler
from icarus_memory.server import create_app
from tests.caldav_attrappe import PASSWORT, CaldavAttrappe
from tests.dns_attrappe import Namensdienst
from tests.microsoft_hilfen import kein_netz  # noqa: F401 - Fixture

ADRESSE = 'lena.probe@eigen-probe.example'
MAILSERVER = 'mail.eigen-probe.example'


@pytest.fixture
def dav(monkeypatch, kein_netz):
    dns_abfrage.vergessen()
    namensdienst = Namensdienst()
    monkeypatch.setenv(dns_abfrage.UMGEBUNG, f'127.0.0.1:{namensdienst.port}')
    with CaldavAttrappe() as dienst:
        yield dienst
    namensdienst.schliessen()
    dns_abfrage.vergessen()
    assert not kein_netz, f'Die Suche wollte ins Netz: {kein_netz}'


def test_srv_mit_pfad(dav):
    assert kalender_anmeldung.eigener_kalender('verein-probe.example') == 'https://dav.verein-probe.example/dav/'


def test_srv_mit_punkt_und_ohne_mailserver_heisst_nicht_gefunden(dav):
    assert kalender_anmeldung.eigener_kalender('kanzlei-probe.example') is None
    assert kalender_anmeldung.eigener_kalender('eigen-probe.example') is None


def test_well_known_auf_dem_mailserver_erst_ohne_passwort(dav):
    ort = kalender_anmeldung.eigener_kalender('eigen-probe.example', MAILSERVER, transport=dav.transport(MAILSERVER))
    assert ort == f'https://{MAILSERVER}/.well-known/caldav'
    # Gefragt wurde einmal, beim Mailserver, und ohne Passwort.
    assert dav.anfragen_an == [(MAILSERVER, '/.well-known/caldav', False)]
    assert dav.anmeldungen == []


def test_kein_kalenderdienst_bekommt_kein_passwort():
    gesehen = []

    def antwort(request):
        gesehen.append('Authorization' in request.headers)
        return httpx.Response(404)
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_anmeldung.startpunkt(ADRESSE, None, mailserver=MAILSERVER, dns=lambda *_: [],
                                      transport=httpx.MockTransport(antwort))
    assert fehler.value.grund == 'adresse_fehlt' and 'überspringen' in fehler.value.satz
    assert gesehen == [False]


@pytest.fixture
def client(tmp_path, monkeypatch, dav):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    app.state.caldav_transport = dav.transport(MAILSERVER)
    with TestClient(app) as test_client:
        yield app, test_client


def test_die_route_nimmt_den_mailserver_des_postfachs_und_dessen_passwort(client, dav):
    app, http = client
    # Ein Postfach dieser Adresse beim Mailserver der Domain, mit Passwort im Schlüsselbund (ohne Anmeldung angelegt).
    konto = config.MailAccountSettings(id='mail-eigen', label='eigen-probe.example', imap_host=MAILSERVER, imap_port=993,
                                       smtp_host='', smtp_port=587, user=ADRESSE, sender=ADRESSE)
    app.state.settings.mail_accounts.append(konto)
    config.store_secret(app.state.keychain, config.integration_secret_name('mail', konto.id), PASSWORT)
    antwort = http.post('/api/v1/integrations/calendar/anmelden', json={'adresse': ADRESSE, 'mail_konto': konto.id})
    assert antwort.status_code == 201, antwort.text
    assert antwort.json()['gefunden'] == ['Privat'] and antwort.json()['anbieter'] == MAILSERVER
    # Zuerst ohne Passwort am bekannten Ort, dann erst mit dem Passwort des Postfachs.
    assert dav.anfragen_an[0] == (MAILSERVER, '/.well-known/caldav', False)
    assert dav.anmeldungen and all(passwort == PASSWORT for _, passwort in dav.anmeldungen)


def test_die_route_sagt_ehrlich_wenn_nichts_zu_finden_ist(client, dav):
    _, http = client
    antwort = http.post('/api/v1/integrations/calendar/anmelden',
                        json={'adresse': 'lena.probe@kanzlei-probe.example', 'password': PASSWORT})
    assert antwort.status_code == 422 and antwort.json()['grund'] == 'adresse_fehlt'
    assert dav.anmeldungen == []
