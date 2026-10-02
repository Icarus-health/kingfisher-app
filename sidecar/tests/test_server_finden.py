"""Den Mailserver einer eigenen Domain selbst finden (Fremdprobe 2, Befund 2): SRV, Autoconfig, MX gegen den Katalog.

Gegen die Namensdienst-Attrappe (UDP auf 127.0.0.1), die Autoconfig-Attrappe (HTTPS auf 127.0.0.1) und mit der
Netzsperre: Jeder Versuch, den Rechner zu verlassen, lässt den Test scheitern. Gefragt wird nur nach der Domain.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, anbieter_erkennen, dns_abfrage, server_finden
from icarus_memory.server import create_app
from tests.autoconfig_attrappe import AutoconfigAttrappe, config_xml
from tests.dns_attrappe import Namensdienst
from tests.microsoft_hilfen import kein_netz  # noqa: F401 - Fixture

LOKAL = 'lena.probe'


@pytest.fixture
def netz(monkeypatch, kein_netz):
    """Namensdienst und Autoconfig als Attrappen; `server_finden` nimmt standardmäßig die Autoconfig-Attrappe."""
    dns_abfrage.vergessen()
    namensdienst = Namensdienst()
    autoconfig = AutoconfigAttrappe(autoconfig={'verein-probe.example': config_xml('verein-probe.example', 'falsch.example')})
    monkeypatch.setenv(dns_abfrage.UMGEBUNG, f'127.0.0.1:{namensdienst.port}')
    monkeypatch.setattr(server_finden, 'TRANSPORT', autoconfig.transport())
    yield namensdienst, autoconfig
    namensdienst.schliessen()
    autoconfig.schliessen()
    dns_abfrage.vergessen()
    assert not kein_netz, f'Die Suche wollte ins Netz: {kein_netz}'


def fund(adresse):
    erkennung = anbieter_erkennen.erkennen(adresse)
    a = erkennung.anbieter
    return None if a is None else (a.id, a.label, a.imap_host, a.imap_port, a.smtp_host, a.smtp_port, a.benutzer,
                                   erkennung.woran)


def test_srv_nennt_den_server_nach_vorrang(netz):
    # RFC 6186: `_imaps._tcp` mit dem kleinsten Vorrang, Versand über `_submission._tcp`. SRV kommt vor Autoconfig.
    assert fund(f'{LOKAL}@verein-probe.example') == ('gefunden', 'mail.verein-probe.example', 'mail.verein-probe.example',
                                                      993, 'mail.verein-probe.example', 587, 'adresse', 'srv')
    _, autoconfig = netz
    assert not any(host.endswith('verein-probe.example') for host, _ in autoconfig.anfragen)


def test_autoconfig_unter_autoconfig_punkt_domain(netz):
    namensdienst, autoconfig = netz
    assert fund(f'{LOKAL}@example.org') == ('gefunden', 'mail.example.org', 'mail.example.org', 993, 'mail.example.org',
                                            587, 'adresse', 'autoconfig')
    # Zuerst SRV beim Namensdienst, dann die Datei beim Server der Domain; nie die Adresse, nie ihr Namensteil.
    assert ('_imaps._tcp.example.org', 'SRV') in namensdienst.fragen
    assert autoconfig.anfragen == [('autoconfig.example.org', '/mail/config-v1.1.xml')]
    alles = [*namensdienst.anfragen, *(h + p for h, p in autoconfig.anfragen)]
    assert all('@' not in frage and LOKAL not in frage for frage in alles)


def test_autoconfig_unter_well_known_mit_namensteil(netz):
    _, autoconfig = netz
    assert fund(f'{LOKAL}@wellknown-probe.example') == (
        'gefunden', 'imap.wellknown-probe.example', 'imap.wellknown-probe.example', 993, '', 587, 'lokalteil', 'autoconfig')
    assert [h for h, _ in autoconfig.anfragen] == ['autoconfig.wellknown-probe.example', 'wellknown-probe.example']


@pytest.mark.parametrize('domain', ['starttls-probe.example', 'doctype-probe.example', 'riesig-probe.example',
                                    'umleitung-probe.example', 'eigen-probe.example', 'unbekannt-probe.example'])
def test_nichts_brauchbares_heisst_nicht_gefunden(netz, domain):
    """Nur IMAP mit TLS; kein DOCTYPE, nichts über 64 KB, keine Weiterleitung. Dann fragt die Oberfläche nach dem Server."""
    _, autoconfig = netz
    assert fund(f'{LOKAL}@{domain}') is None
    if domain == 'umleitung-probe.example':
        assert all(not p.startswith('/anderswo') for _, p in autoconfig.anfragen)


def test_srv_mit_punkt_heisst_kein_imap_und_es_geht_weiter(netz):
    # `kanzlei-probe.example` sagt per SRV, dass es kein IMAP anbietet; die übrigen Wege kommen trotzdem dran.
    _, autoconfig = netz
    assert fund(f'{LOKAL}@kanzlei-probe.example') is None
    assert 'autoconfig.kanzlei-probe.example' in [h for h, _ in autoconfig.anfragen]


def test_mx_bei_einem_bekannten_hoster(netz):
    assert fund(f'{LOKAL}@hoster-probe.example') == ('gefunden', 'IONOS', 'imap.ionos.de', 993, 'smtp.ionos.de', 587,
                                                      'adresse', 'mx')
    assert fund(f'{LOKAL}@kas-probe.example') == ('gefunden', 'ALL-INKL (w0123456.kasserver.com)',
                                                   'w0123456.kasserver.com', 993, 'w0123456.kasserver.com', 587,
                                                   'adresse', 'mx')


def test_google_und_microsoft_gehen_weiter_vor(netz):
    _, autoconfig = netz
    assert anbieter_erkennen.erkennen(f'{LOKAL}@praxis-probe.example').anbieter.id == 'gmail'
    assert anbieter_erkennen.erkennen(f'{LOKAL}@firma-probe.example').anbieter.id == 'outlook'
    assert autoconfig.anfragen == []


def test_ein_fund_wird_gemerkt_ein_nichtfund_nicht(netz):
    _, autoconfig = netz
    fund(f'{LOKAL}@example.org')
    fund(f'{LOKAL}@example.org')
    assert len(autoconfig.anfragen) == 1
    fund(f'{LOKAL}@eigen-probe.example')
    fund(f'{LOKAL}@eigen-probe.example')
    assert sum(1 for h, _ in autoconfig.anfragen if h.endswith('eigen-probe.example')) == 4


def test_die_suche_hat_eine_zeitgrenze(monkeypatch, kein_netz):
    stumm = Namensdienst(stumm=True)
    monkeypatch.setenv(dns_abfrage.UMGEBUNG, f'127.0.0.1:{stumm.port}')
    beginn = time.monotonic()
    assert server_finden.finde('eigen-probe.example', sekunden=1.0) is None
    assert time.monotonic() - beginn < 1.5
    stumm.schliessen()
    assert not kein_netz


def test_lies_autoconfig_ersetzt_platzhalter_und_meidet_starttls():
    text = config_xml('d.example', 'mail.%EMAILDOMAIN%', smtp_host='smtp.%EMAILDOMAIN%')
    gefunden = server_finden.lies_autoconfig(text, 'd.example')
    assert (gefunden.imap_host, gefunden.smtp_host) == ('mail.d.example', 'smtp.d.example')
    assert server_finden.lies_autoconfig(config_xml('d.example', 'x.example', 143, socket_typ='STARTTLS'), 'd.example') is None
    assert server_finden.lies_autoconfig('<kaputt', 'd.example') is None
    assert server_finden.lies_autoconfig(config_xml('d.example', 'nicht erlaubt/../x'), 'd.example') is None


def _nur_mit_transport(echt):
    def aufruf(domain, transport=None):
        assert transport is not None, 'ohne Transport ginge die Suche ins Netz'
        return echt(domain, transport)
    return aufruf


def test_die_schnittstelle_liefert_den_fund(netz, tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    _, autoconfig = netz
    # Die Route nimmt den Transport aus `app.state` (so wie die Browserprobe); ohne ihn käme hier niemand durch.
    monkeypatch.setattr(server_finden, 'TRANSPORT', None)
    monkeypatch.setattr(server_finden, 'aus_autoconfig', _nur_mit_transport(server_finden.aus_autoconfig))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    app.state.autoconfig_transport = autoconfig.transport()
    with TestClient(app) as client:
        antwort = client.get('/api/v1/integrations/mail-providers/erkennen', params={'adresse': f'{LOKAL}@example.org'})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten['erkannt_an'] == 'autoconfig' and daten['dienst'] == ''
    assert daten['provider']['id'] == 'gefunden' and daten['provider']['imap_host'] == 'mail.example.org'
    assert daten['provider']['imap_port'] == 993 and daten['provider']['benutzer'] == 'adresse'
