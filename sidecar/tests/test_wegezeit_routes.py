"""Wegezeit über die Routen: Einwilligung, Schlüssel nie zurück, Mac-Arbeiter, Weg im Tagesbriefing."""
import logging
import os
from datetime import datetime, timedelta

import pytest

from icarus_memory import config
from icarus_memory.wegezeit import Fahrzeit
from icarus_memory.wegezeit_routes import dienst
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api
from tests.test_terminvorbereitung import ANNA, ICH, _mail, kalender, termin

GEHEIM = 'sk-routen-geheim-9876543210'
HEIMAT = 'Musterstraße 1, 65183 Wiesbaden'


class Keychain:
    available = False
    backend = 'none'


class Fake:
    name = 'Fake Karten'

    def __init__(self):
        self.aufrufe = []

    def verfuegbar(self):
        return True

    def fahrzeit(self, von, nach, verkehrsmittel, abfahrt):
        self.aufrufe.append((von, nach))
        return Fahrzeit(30, verkehrsmittel, self.name)


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    app.state.keychain = Keychain()
    monkeypatch.delenv('ICARUS_ORS_KEY', raising=False)
    monkeypatch.delenv('ICARUS_GOOGLE_ROUTES_KEY', raising=False)
    try:
        yield app, client
    finally:
        client.close()


def test_vorgabe_ist_aus_und_die_einstellung_wird_gespeichert(api, tmp_path):
    app, client = api
    anfang = client.get('/api/v1/wegezeit/einstellungen').json()
    assert (anfang['aktiv'], anfang['heimat'], anfang['verkehrsmittel']) == (False, '', 'auto')
    client.get('/api/v1/wegezeit/mac/anfragen')  # Apple Karten ist da (Mac-Arbeiter meldet sich)
    neu = client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True, 'heimat': f'  {HEIMAT} '}).json()
    assert (neu['aktiv'], neu['heimat']) == (True, HEIMAT)
    assert config.load(tmp_path / 'source-answer-api').wegezeit['aktiv'] is True
    assert client.put('/api/v1/wegezeit/einstellungen', json={'verkehrsmittel': 'oepnv'}).json()['aktiv'] is True
    assert client.put('/api/v1/wegezeit/einstellungen', json={'verkehrsmittel': 'rakete'}).status_code == 422
    assert client.put('/api/v1/wegezeit/einstellungen', json={'egal': 1}).status_code == 422
    assert client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': False}).json()['aktiv'] is False


def test_einschalten_erst_wenn_es_rechnen_kann(api, monkeypatch):
    """Befund 19: Ohne Startort oder ohne Kartendienst lässt sich die Wegezeit nicht einschalten; der Stand sagt in
    einem Satz, was fehlt. Apple Karten zählt, sobald sich der Mac-Arbeiter meldet, auch vor der Einwilligung."""
    app, client = api
    stand = client.get('/api/v1/wegezeit/einstellungen').json()
    assert (stand['kann_rechnen'], stand['fehlt']) == (False, 'startort')
    assert stand['fehlt_satz'] == 'Für die Wegezeit fehlt noch dein Startort.'
    abgelehnt = client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True})
    assert abgelehnt.status_code == 409 and 'Startort' in abgelehnt.json()['detail']
    assert client.get('/api/v1/wegezeit/einstellungen').json()['aktiv'] is False
    # Startort da, aber kein Dienst (kein Mac, kein Schlüssel): wieder nein, mit dem Grund.
    stand = client.put('/api/v1/wegezeit/einstellungen', json={'heimat': HEIMAT}).json()
    assert (stand['aktiv'], stand['kann_rechnen'], stand['fehlt']) == (False, False, 'dienst')
    abgelehnt = client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True})
    assert abgelehnt.status_code == 409 and 'Apple Karten' in abgelehnt.json()['detail']
    # Ein Schlüssel für den eigenen Kartendienst macht es möglich.
    monkeypatch.setenv('ICARUS_ORS_KEY', GEHEIM)
    assert client.get('/api/v1/wegezeit/einstellungen').json()['kann_rechnen'] is True
    assert client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True}).json()['aktiv'] is True
    # Ausschalten geht immer, auch wenn inzwischen etwas fehlt.
    monkeypatch.delenv('ICARUS_ORS_KEY')
    assert client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': False}).json()['aktiv'] is False


def test_der_mac_arbeiter_macht_apple_karten_moeglich_ohne_etwas_zu_bekommen(api):
    app, client = api
    client.put('/api/v1/wegezeit/einstellungen', json={'heimat': HEIMAT})
    assert client.get('/api/v1/wegezeit/einstellungen').json()['fehlt'] == 'dienst'
    assert client.get('/api/v1/wegezeit/mac/anfragen').json() == {'anfragen': [], 'aktiv': False}
    stand = client.get('/api/v1/wegezeit/einstellungen').json()
    assert (stand['kann_rechnen'], stand['fehlt'], stand['fehlt_satz']) == (True, None, '')
    assert app.state.wegezeit_briefkasten.online() is False  # ohne Einwilligung nicht „online“, nur da


def test_der_schluessel_kommt_nie_zurueck_und_steht_nicht_im_log_oder_in_den_einstellungen(api, caplog, tmp_path):
    app, client = api
    with caplog.at_level(logging.DEBUG):
        antwort = client.put('/api/v1/wegezeit/schluessel', json={'dienst': 'openrouteservice', 'schluessel': GEHEIM})
        stand = client.get('/api/v1/wegezeit/einstellungen')
        tag = client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True, 'heimat': HEIMAT})
    assert antwort.status_code == 200 and antwort.json()['schluessel_hinterlegt'] == {'openrouteservice': True, 'google': False}
    assert GEHEIM not in antwort.text + stand.text + tag.text and GEHEIM not in caplog.text
    assert GEHEIM not in (tmp_path / 'source-answer-api' / config.DATEINAME).read_text()
    assert os.environ['ICARUS_ORS_KEY'] == GEHEIM  # ohne Schlüsselspeicher nur für diese Sitzung
    assert client.put('/api/v1/wegezeit/schluessel', json={'dienst': 'openrouteservice', 'schluessel': 'kurz'}).status_code == 422
    geloescht = client.delete('/api/v1/wegezeit/schluessel', params={'dienst_name': 'openrouteservice'}).json()
    assert geloescht['schluessel_hinterlegt']['openrouteservice'] is False and 'ICARUS_ORS_KEY' not in os.environ


def test_mac_arbeiter_bekommt_ohne_einwilligung_nichts_und_gilt_dann_nicht_als_online(api):
    app, client = api
    leer = client.get('/api/v1/wegezeit/mac/anfragen').json()
    assert leer == {'anfragen': [], 'aktiv': False}
    assert app.state.wegezeit_briefkasten.online() is False
    client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True, 'heimat': HEIMAT})
    assert client.get('/api/v1/wegezeit/mac/anfragen').json() == {'anfragen': [], 'aktiv': True}
    assert app.state.wegezeit_briefkasten.online() is True
    assert client.post('/api/v1/wegezeit/mac/antworten', json={'id': 'gibt-es-nicht', 'minuten': 5}).json() == {'angenommen': False}


def test_routen_verlangen_das_zugangswort(api):
    _, client = api
    for methode, pfad in (('get', '/api/v1/wegezeit/einstellungen'), ('get', '/api/v1/wegezeit/mac/anfragen'),
                          ('get', '/api/v1/tag/briefing')):
        assert getattr(client, methode)(pfad, headers={'X-Icarus-Token': 'falsch'}).status_code in (401, 403)


def briefing_mit_termin(app, client, **einstellung):
    _mail(app, 'Format', [('Das Plakat hätte ich gern im Format A2.', 'fact')], [ANNA, ICH], tage=3)
    kalender(app, termin(stunde=14, teilnehmer=(ANNA, ICH)))
    if einstellung:
        client.put('/api/v1/wegezeit/einstellungen', json=einstellung)
    return client.get('/api/v1/tag/briefing').json()


def test_ohne_einwilligung_steht_fahrzeit_unbekannt_mit_einer_aktion_und_kein_dienst_wird_gefragt(api):
    app, client = api
    fake = Fake()
    dienst(app)._anbieter['apple'] = fake
    daten = briefing_mit_termin(app, client)
    weg = daten['termine'][0]['wegezeit']
    assert weg['status'] == 'aus' and weg['minuten'] is None and weg['satz'].endswith('Fahrzeit unbekannt.')
    zeile = daten['tageslage']['zeilen'][0]
    assert zeile['art'] == 'termin' and 'Fahrzeit unbekannt.' in zeile['text'] and 'Losfahren' not in zeile['text']
    assert [a['art'] for a in zeile['aktionen']] == ['vorbereitung', 'fahrzeiten']
    assert fake.aufrufe == []


def test_mit_einwilligung_und_heimat_steht_losfahren_und_nur_zwei_adressen_gehen_hinaus(api):
    app, client = api
    fake = Fake()
    dienst(app)._anbieter['apple'] = fake
    daten = briefing_mit_termin(app, client, aktiv=True, heimat=HEIMAT)
    zeile = daten['tageslage']['zeilen'][0]
    assert 'Losfahren um 13:20 Uhr' in zeile['text'] and 'etwa 30 Minuten mit dem Auto' in zeile['text']
    assert 'Fake Karten' in zeile['text']
    assert fake.aufrufe == [(HEIMAT, 'Druckerei Braun, Werkstraße 4, Mainz')]


def test_ohne_heimat_fragt_die_zeile_nach_dem_startort(api):
    app, client = api
    dienst(app)._anbieter['apple'] = Fake()
    # Eingeschaltet wird nur mit Startort (Befund 19); wird er danach entfernt, fragt die Zeile nach ihm.
    client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True, 'heimat': HEIMAT})
    daten = briefing_mit_termin(app, client, heimat='')
    zeile = daten['tageslage']['zeilen'][0]
    assert 'Fahrzeit unbekannt.' in zeile['text'] and [a['art'] for a in zeile['aktionen']] == ['vorbereitung', 'heimat']


def test_der_vorherige_termin_ist_der_startpunkt(api):
    app, client = api
    fake = Fake()
    dienst(app)._anbieter['apple'] = fake
    _mail(app, 'Format', [('Das Plakat hätte ich gern im Format A2.', 'fact')], [ANNA, ICH], tage=3)
    kalender(app, termin('t0', 'Frühstück Agentur', stunde=11, ort='Agentur Keller, Hauptstraße 3, Mainz', teilnehmer=(ICH,), dauer=60),
             termin('t1', 'Gespräch Druckerei', stunde=14, teilnehmer=(ANNA, ICH)))
    client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True, 'heimat': HEIMAT})
    daten = client.get('/api/v1/tag/briefing').json()
    von = {t['titel']: t['wegezeit']['start'] for t in daten['termine']}
    assert von['Gespräch Druckerei'] == 'Agentur Keller, Hauptstraße 3, Mainz' and von['Frühstück Agentur'] == HEIMAT
