"""Die eine Anbieter-Erkennung: Google Workspace, Microsoft 365 und die bekannten Anbieter an einer Adresse.

Gegen die Namensdienst-Attrappe (`tests/dns_attrappe.py`, UDP auf 127.0.0.1) und mit der Netzsperre (`kein_netz`):
Jeder Versuch, den Rechner zu verlassen, wird gefangen und lässt den Test scheitern. Gefragt wird nur nach der Domain,
nur beim Namensdienst des Rechners, nie bei Google oder Microsoft.
"""
from __future__ import annotations

import socket
import struct
import time

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, anbieter_erkennen, dns_abfrage
from icarus_memory.server import create_app
from tests.dns_attrappe import Namensdienst
from tests.microsoft_hilfen import kein_netz  # noqa: F401 - Fixture

LOKAL = 'lena.probe'


@pytest.fixture
def dienst(monkeypatch, kein_netz):
    dns_abfrage.vergessen()
    namensdienst = Namensdienst()
    monkeypatch.setenv(dns_abfrage.UMGEBUNG, f'127.0.0.1:{namensdienst.port}')
    yield namensdienst
    namensdienst.schliessen()
    dns_abfrage.vergessen()
    assert not kein_netz, f'Die Erkennung wollte ins Netz: {kein_netz}'


def kurz(erkennung):
    return (erkennung.anbieter.id if erkennung.anbieter else None, erkennung.dienst, erkennung.art, erkennung.woran)


def test_eine_erkennung_fuer_google_microsoft_und_den_rest(dienst):
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@praxis-probe.example')) == ('gmail', 'google', 'organisation', 'mx')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@firma-probe.example')) == ('outlook', 'microsoft', 'organisation', 'mx')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@hochschule.example')) == ('outlook', 'microsoft', 'organisation', 'mx')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@filter-probe.example')) == (
        'outlook', 'microsoft', 'organisation', 'autodiscover')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@mandant-probe.example')) == ('outlook', 'microsoft', 'organisation', 'txt')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@eigen-probe.example')) == (None, '', '', '')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@unbekannt-probe.example')) == (None, '', '', '')
    assert kurz(anbieter_erkennen.erkennen('kaputt')) == (None, '', '', '')
    # Gefragt wurde nur nach Domains, nie nach der Adresse oder ihrem Namensteil.
    assert dienst.anfragen and all('@' not in frage and LOKAL not in frage for frage in dienst.anfragen)


def test_bekannte_endung_fragt_niemanden(dienst):
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@gmail.com')) == ('gmail', 'google', 'privat', 'domain')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@outlook.de')) == ('outlook', 'microsoft', 'privat', 'domain')
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@web.de')) == ('webde', '', '', 'domain')
    assert dienst.anfragen == []


def test_google_braucht_eine_anfrage_und_antworten_werden_gemerkt(dienst):
    anbieter_erkennen.erkennen(f'{LOKAL}@praxis-probe.example')
    anbieter_erkennen.erkennen(f'{LOKAL}@praxis-probe.example')
    assert dienst.fragen == [('praxis-probe.example', 'MX')]
    anbieter_erkennen.vergessen()
    anbieter_erkennen.erkennen(f'{LOKAL}@praxis-probe.example')
    assert dienst.fragen == [('praxis-probe.example', 'MX')] * 2


def test_microsoft_wird_nie_fuer_google_gehalten_und_umgekehrt():
    """Eine Domain mit beiden Zeichen: Der Mailserver entscheidet, er sagt, wo die Post wirklich liegt."""
    def dns(name, art):
        return {('ms.example', 'MX'): ['ms-example.mail.protection.outlook.com'],
                ('g.example', 'MX'): ['smtp.google.com'],
                ('autodiscover.g.example', 'CNAME'): ['autodiscover.outlook.com']}.get((name, art), [])
    assert anbieter_erkennen.erkennen('a@ms.example', dns).dienst == 'microsoft'
    assert anbieter_erkennen.erkennen('a@g.example', dns).dienst == 'google'
    # Eine Domain, die nur so heißt wie Google, ist nicht Google.
    assert anbieter_erkennen.erkennen('a@x.example', lambda n, a: ['mx.nicht-google.com'] if a == 'MX' else []).dienst == ''


def test_schweigender_namensdienst_haelt_nicht_auf(monkeypatch, kein_netz):
    dns_abfrage.vergessen()
    stumm = Namensdienst(stumm=True)
    monkeypatch.setenv(dns_abfrage.UMGEBUNG, f'127.0.0.1:{stumm.port}')
    beginn = time.monotonic()
    assert kurz(anbieter_erkennen.erkennen(f'{LOKAL}@praxis-probe.example')) == (None, '', '', '')
    # Vier Fragen (MX, CNAME, TXT, dazu SRV für den eigenen Server; MX wird nicht zweimal gefragt), jede mit
    # Zeitgrenze; Schweigen wird nicht gemerkt.
    assert time.monotonic() - beginn < 4 * dns_abfrage.ZEITGRENZE + 1
    assert [art for _, art in stumm.fragen] == ['MX', 'CNAME', 'TXT', 'SRV']
    stumm.schliessen()

    def kaputt(name, art):
        raise OSError('keine Antwort')
    assert anbieter_erkennen.erkennen('a@uni.example', kaputt).dienst == ''
    assert not kein_netz


def test_nur_die_domain_nur_an_den_namensdienst_des_rechners(monkeypatch, kein_netz):
    """Ohne `KINGFISHER_DNS` geht die Frage an den Namensdienst aus `resolv.conf` und nirgendwo sonst hin."""
    dns_abfrage.vergessen()
    monkeypatch.delenv(dns_abfrage.UMGEBUNG, raising=False)
    monkeypatch.setattr(dns_abfrage, 'namensdienste', lambda: [('192.0.2.53', 53)])
    gesendet: list[tuple[object, bytes]] = []
    sperre = socket.socket.sendto

    def mitschreiben(sock, daten, *rest):
        gesendet.append((rest[-1], bytes(daten)))
        return sperre(sock, daten, *rest)
    monkeypatch.setattr(socket.socket, 'sendto', mitschreiben)
    assert anbieter_erkennen.erkennen(f'{LOKAL}@hochschule.example').dienst == ''  # die Sperre lässt nichts durch
    assert {ziel for ziel, _ in gesendet} == {('192.0.2.53', 53)}
    assert set(kein_netz) == {('192.0.2.53', 53)}
    for _, daten in gesendet:
        frage = daten[12:]
        assert b'lena' not in frage and b'@' not in frage
        typ, klasse = struct.unpack('>HH', frage[-4:])
        assert klasse == 1 and typ in dns_abfrage.TYPEN.values()
        assert b'\x0ahochschule\x07example\x00' in frage
    dns_abfrage.vergessen()


def test_route_nennt_anbieter_und_dienst(dienst, tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    with TestClient(app) as client:
        def frage(adresse):
            return client.get('/api/v1/integrations/mail-providers/erkennen', params={'adresse': adresse}).json()
        google = frage(f'{LOKAL}@praxis-probe.example')
        assert (google['erkannt_an'], google['dienst'], google['art']) == ('mx', 'google', 'organisation')
        assert google['provider']['id'] == 'gmail' and google['provider']['kalender_ical'] is True
        microsoft = frage(f'{LOKAL}@hochschule.example')
        assert (microsoft['dienst'], microsoft['art'], microsoft['provider']['id']) == ('microsoft', 'organisation', 'outlook')
        assert frage('a@eigen-probe.example') == {'provider': None, 'erkannt_an': '', 'dienst': '', 'art': ''}
        # Es gibt nur diesen einen Weg; der frühere eigene Microsoft-Endpunkt ist entfallen.
        assert client.get('/api/v1/microsoft/erkennen', params={'adresse': f'{LOKAL}@hochschule.example'}).status_code == 404
