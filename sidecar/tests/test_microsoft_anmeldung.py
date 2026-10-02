"""Mit Microsoft anmelden (docs/50-microsoft-365.md): Gerätecode, nur lesende Rechte, ehrliche Sätze, Token bleibt hier.

Gegen die Graph-Attrappe (`graph_attrappe.py`) auf 127.0.0.1; jeder andere Netzzugriff schlägt fehl (`kein_netz`).
"""
from __future__ import annotations

import json
import re
import struct

import pytest

from icarus_memory import dns_abfrage, microsoft_anmeldung as ma
from icarus_memory.microsoft_anmeldung import MicrosoftAnmeldung, MicrosoftFehler
from tests.graph_attrappe import ADRESSE, MANDANT, USER_CODE
from tests.microsoft_hilfen import NetzVersuch, Schluessel, Uhr, graph, kein_netz  # noqa: F401 - Fixtures

GEHEIM = re.compile(r'geraet-geheim|erneuern-\d|zugriff-\d')


def anmeldung(uhr=None) -> MicrosoftAnmeldung:
    return MicrosoftAnmeldung(Schluessel(), clock=uhr or Uhr())


# -- Nur lesen ------------------------------------------------------------------------------------------------------

def test_angefragt_werden_nur_lesende_rechte():
    for scopes in (ma.scopes_fuer(False), ma.scopes_fuer(True)):
        text = ma.nur_lesend(scopes)
        assert not re.search(r'write|send|manage|delete|create', text, re.I), text
        for scope in scopes:
            assert scope.endswith('.Read') or scope in ('offline_access', ma.MITSCHRIFT_SCOPE), scope
    assert set(ma.GRUND_SCOPES) == {'User.Read', 'Mail.Read', 'Calendars.Read', 'OnlineMeetings.Read', 'offline_access'}
    assert ma.MITSCHRIFT_SCOPE == 'OnlineMeetingTranscript.Read.All'
    assert ma.MITSCHRIFT_SCOPE not in ma.GRUND_SCOPES, 'Mitschriften verlangen die IT und gehören nicht in die erste Anmeldung'
    for falsch in ('Mail.Send', 'Mail.ReadWrite', 'Calendars.ReadWrite', 'Files.ReadWrite.All', 'Mail.Read.All', 'Sites.Read.All'):
        with pytest.raises(ValueError):
            ma.nur_lesend([falsch])


def test_die_anfrage_an_microsoft_traegt_nur_lesende_rechte(graph):
    anm = anmeldung()
    anm.beginnen(ADRESSE)
    anm.beginnen(ADRESSE, mitschriften=True)
    gesendet = [a['scope'] for a in graph.anfragen if a['pfad'].endswith('/devicecode')]
    assert gesendet == [' '.join(ma.GRUND_SCOPES), ' '.join(ma.GRUND_SCOPES + (ma.MITSCHRIFT_SCOPE,))]
    assert not any(re.search(r'write|send', s, re.I) for s in gesendet)


# -- Gerätecode -----------------------------------------------------------------------------------------------------

def test_geraetecode_mit_warten_bremsen_und_erfolg(graph):
    uhr = Uhr()
    anm = anmeldung(uhr)
    graph.ablauf[:] = ['pending', 'slow_down', 'pending', 'ok']
    start = anm.beginnen(ADRESSE)
    assert start['user_code'] == USER_CODE and start['verification_uri'] == 'https://microsoft.com/devicelogin'
    assert start['status'] == 'waiting' and start['restsekunden'] == 900
    # Der Mandant kommt aus der OpenID-Beschreibung der Domain, nicht aus einer Rückfrage.
    assert any(a['pfad'] == f'/{MANDANT}/oauth2/v2.0/devicecode' for a in graph.anfragen)
    token = lambda: sum(a['pfad'].endswith('/token') for a in graph.anfragen)  # noqa: E731
    sid = start['sitzung']
    assert not GEHEIM.search(json.dumps(start)), 'der Start verrät den Gerätecode nicht'
    sicht = anm.nachfragen(sid)
    assert sicht['status'] == 'waiting' and token() == 1
    assert not GEHEIM.search(json.dumps(sicht)), 'auch das Warten verrät den Gerätecode nicht'
    assert anm.nachfragen(sid)['status'] == 'waiting' and token() == 2  # slow_down
    # Nach slow_down wächst das Intervall um fünf Sekunden (RFC 8628): eine Nachfrage zu früh fragt Microsoft nicht.
    assert anm.offen[sid]['intervall'] == 5
    assert anm.nachfragen(sid)['status'] == 'waiting' and token() == 2
    uhr.jetzt += 5
    assert anm.nachfragen(sid)['status'] == 'waiting' and token() == 3
    uhr.jetzt += 5
    fertig = anm.nachfragen(sid)
    assert fertig['status'] == 'ready' and fertig['email'] == ADRESSE and token() == 4
    assert not GEHEIM.search(json.dumps(fertig)), 'die Ansicht verrät nie Gerätecode oder Token'
    grant = anm.uebernehmen(sid)['grant']
    assert grant['refresh_token'] == 'erneuern-1' and grant['mandant'] == MANDANT
    assert 'Mail.Read' in grant['scope'] and 'https://' not in grant['scope']


@pytest.mark.parametrize('schritt,status,grund', [
    ('abgelaufen', 'expired', 'abgelaufen'),
    ('abgelehnt', 'cancelled', 'abgebrochen'),
    ('admin', 'failed', 'admin'),
    ('admin90094', 'failed', 'admin'),
])
def test_fehler_beim_nachfragen_werden_ein_satz(graph, schritt, status, grund):
    anm = anmeldung()
    graph.ablauf[:] = [schritt]
    sid = anm.beginnen(ADRESSE)['sitzung']
    sicht = anm.nachfragen(sid)
    assert (sicht['status'], sicht['grund']) == (status, grund)
    assert sicht['satz'] == ma.GRUENDE[grund]
    assert 'device_code' not in anm.offen[sid]


def test_ohne_freigabe_der_it_fuer_mitschriften_ein_eigener_satz(graph):
    anm = anmeldung()
    graph.ablauf[:] = ['admin']
    sid = anm.beginnen(ADRESSE, mitschriften=True)['sitzung']
    sicht = anm.nachfragen(sid)
    assert sicht['grund'] == 'admin_mitschriften' and 'Post und Kalender bleiben verbunden' in sicht['satz']


def test_code_laeuft_ab_ohne_dass_microsoft_gefragt_wird(graph):
    uhr = Uhr()
    anm = anmeldung(uhr)
    sid = anm.beginnen(ADRESSE)['sitzung']
    vorher = len(graph.anfragen)
    uhr.jetzt += 901
    sicht = anm.nachfragen(sid)
    assert sicht['status'] == 'expired' and sicht['grund'] == 'abgelaufen' and len(graph.anfragen) == vorher


def test_abbrechen(graph):
    anm = anmeldung()
    sid = anm.beginnen(ADRESSE)['sitzung']
    anm.abbrechen(sid)
    assert anm.nachfragen(sid)['status'] == 'cancelled'


def test_ohne_app_kennung_und_mit_falscher(graph, monkeypatch):
    monkeypatch.delenv(ma.CLIENT_ENV)
    anm = anmeldung()
    with pytest.raises(MicrosoftFehler) as fehler:
        anm.beginnen(ADRESSE)
    assert fehler.value.grund == 'keine_app' and 'Techniker' in fehler.value.satz
    with pytest.raises(ValueError):
        anm.client_setzen('keine-kennung')
    anm.client_setzen('00000000-0000-0000-0000-000000000001')
    assert anm.stand()['quelle'] == 'einstellung'
    with pytest.raises(MicrosoftFehler) as fehler:
        anm.beginnen(ADRESSE)
    assert fehler.value.grund == 'app_unbekannt'
    anm.client_setzen('')
    assert anm.stand()['configured'] is False


def test_unbekannte_domain_und_kein_schluesselspeicher(graph):
    anm = anmeldung()
    with pytest.raises(MicrosoftFehler) as fehler:
        anm.beginnen('jemand@nicht-bei-microsoft.example')
    assert fehler.value.grund == 'unbekannte_domain'
    anm.keychain.available = False
    with pytest.raises(MicrosoftFehler) as fehler:
        anm.beginnen(ADRESSE)
    assert fehler.value.grund == 'kein_speicher'


def test_kein_netz_ist_ein_satz_und_beendet_die_anmeldung_nicht(graph, monkeypatch):
    anm = anmeldung()
    sid = anm.beginnen(ADRESSE)['sitzung']
    monkeypatch.setenv(ma.LOGIN_ENV, 'http://127.0.0.1:9')  # niemand hört dort
    sicht = anm.nachfragen(sid)
    assert sicht['status'] == 'waiting' and sicht['hinweis'] == ma.GRUENDE['nicht_erreichbar']
    with pytest.raises(MicrosoftFehler) as fehler:
        anm.beginnen(ADRESSE)
    assert fehler.value.grund == 'nicht_erreichbar' and fehler.value.status == 503


@pytest.mark.parametrize('antwort,grund', [
    ({'error': 'invalid_grant', 'error_codes': [65001]}, 'admin'),
    ({'error': 'invalid_grant', 'error_description': 'AADSTS90094: Admin consent is required'}, 'admin'),
    ({'error': 'invalid_grant', 'error_codes': [90095]}, 'admin'),
    ({'error': 'invalid_request', 'error_codes': [7000218]}, 'kein_code_weg'),
    ({'error': 'invalid_grant', 'error_codes': [50105]}, 'nicht_zugewiesen'),
    ({'error': 'invalid_grant', 'error_codes': [53003]}, 'richtlinie'),
    ({'error': 'expired_token'}, 'abgelaufen'),
    ({'error': 'authorization_declined'}, 'abgebrochen'),
    ({'error': 'irgendwas'}, 'unbekannt'),
])
def test_fehlercodes_von_entra(antwort, grund):
    assert ma.grund_aus(antwort) == grund


# -- Zugriffstoken --------------------------------------------------------------------------------------------------

def test_erneuern_tauscht_den_refresh_token_und_merkt_das_zugriffstoken(graph):
    anm = anmeldung()
    anm.keychain.set(ma.konto_schluessel(ADRESSE), json.dumps({'client_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
        'mandant': MANDANT, 'refresh_token': 'erneuern-1', 'scope': 'Calendars.Read Mail.Read User.Read offline_access'}))
    assert anm.access_token(ADRESSE) == 'zugriff-2'
    assert anm.access_token(ADRESSE) == 'zugriff-2'  # gemerkt, keine zweite Anfrage
    assert sum(a['pfad'].endswith('/token') for a in graph.anfragen) == 1
    gespeichert = json.loads(anm.keychain.get(ma.konto_schluessel(ADRESSE)))
    assert gespeichert['refresh_token'] == 'erneuern-2'
    erneuert = [a for a in graph.anfragen if a['pfad'].endswith('/token')][0]
    assert not re.search(r'write|send', erneuert['scope'], re.I)
    assert ADRESSE not in ma.konto_schluessel(ADRESSE)


def test_abgelaufene_anmeldung_sagt_es(graph):
    anm = anmeldung()
    graph.modus.add('refresh_abgelaufen')
    anm.keychain.set(ma.konto_schluessel(ADRESSE), json.dumps({'client_id': 'x', 'mandant': MANDANT,
                                                               'refresh_token': 'erneuern-1', 'scope': 'Mail.Read'}))
    with pytest.raises(MicrosoftFehler) as fehler:
        anm.access_token(ADRESSE)
    assert fehler.value.grund == 'abgemeldet' and 'noch einmal an' in fehler.value.satz
    anm.vergessen(ADRESSE)
    with pytest.raises(MicrosoftFehler):
        anm.access_token(ADRESSE)


# -- DNS (die Erkennung selbst prüft `test_anbieter_erkennen.py`) ------------------------------------------------

def test_dns_antwort_wird_gelesen_auch_komprimiert():
    kennung = 4242
    frage = dns_abfrage._frage(kennung, 'uni.example', dns_abfrage.TYPEN['MX'])
    kopf = struct.pack('>HHHHHH', kennung, 0x8180, 1, 2, 0, 0)
    ziel = b'\x03uni\x07example\x00'
    # Antwort 1: MX auf „uni-example.mail.protection.outlook.com“; Antwort 2: komprimiert auf den Fragenamen (Stelle 12).
    mx1 = b'\x0buni-example\x04mail\x0aprotection\x07outlook\x03com\x00'
    antwort1 = b'\xc0\x0c' + struct.pack('>HHIH', 15, 1, 60, 2 + len(mx1)) + b'\x00\x0a' + mx1
    antwort2 = b'\xc0\x0c' + struct.pack('>HHIH', 15, 1, 60, 4) + b'\x00\x14' + b'\xc0\x0c'
    paket = kopf + frage[12:] + antwort1 + antwort2
    assert frage[12:].startswith(ziel)
    assert dns_abfrage.antwort_lesen(paket, kennung, 15) == ['uni-example.mail.protection.outlook.com', 'uni.example']
    assert dns_abfrage.antwort_lesen(paket, 1, 15) == []  # fremde Kennung zählt nicht


def test_dns_ohne_netz_bleibt_leer(kein_netz):
    assert dns_abfrage.abfragen('uni.example', 'MX', dienste=['192.0.2.1'], zeitgrenze=0.2) == []
    assert kein_netz, 'die Abfrage hätte den Rechner verlassen und wurde abgefangen'


def test_vorgaben_zeigen_auf_microsoft_und_https(monkeypatch):
    for name in (ma.LOGIN_ENV, ma.GRAPH_ENV):
        monkeypatch.delenv(name, raising=False)
    assert ma.login_basis() == 'https://login.microsoftonline.com'
    assert ma.graph_basis() == 'https://graph.microsoft.com/v1.0'


def test_ein_netzversuch_in_tests_wird_gefangen(kein_netz):
    import httpx
    with pytest.raises((NetzVersuch, httpx.HTTPError)):
        httpx.get('https://graph.microsoft.com/v1.0/me', timeout=1)
    assert kein_netz
