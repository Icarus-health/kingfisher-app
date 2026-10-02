"""Wegezeit: Einwilligung, ehrliche Sätze ohne Dienst, Startpunkt, Losfahrzeit, Schlüssel nie im Log."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from icarus_memory import wegezeit as w
from icarus_memory.wegezeit import (Briefkasten, Einstellung, Fahrzeit, GoogleRoutes, MacKarten, NichtUnterstuetzt,
                                    OpenRouteService, WegezeitDienst, WegezeitFehler)

BEGINN = datetime(2026, 9, 30, 14, 0, tzinfo=timezone(timedelta(hours=2)))
ORT = 'Seniorenresidenz Rheinauenblick, Uferweg 7, Wiesbaden-Biebrich'
HEIMAT = 'Musterstraße 1, 65183 Wiesbaden'
GEHEIM = 'sk-geheim-0123456789'


class Fake:
    """Ein Anbieter, der zählt, wie oft und mit welchen Adressen er gefragt wurde."""

    def __init__(self, name='Fake', minuten=35, verfuegbar=True, fehler=None):
        self.name, self.minuten, self._verfuegbar, self.fehler = name, minuten, verfuegbar, fehler
        self.aufrufe = []

    def verfuegbar(self):
        return self._verfuegbar

    def fahrzeit(self, von, nach, verkehrsmittel, abfahrt):
        self.aufrufe.append((von, nach, verkehrsmittel))
        if self.fehler:
            raise self.fehler
        return Fahrzeit(self.minuten, verkehrsmittel, self.name)


def dienst(*anbieter, **einstellung):
    daten = {'aktiv': True, 'heimat': HEIMAT, **einstellung}
    return WegezeitDienst({'apple': anbieter[0]} if len(anbieter) == 1 else
                          {'apple': anbieter[0], 'google': anbieter[1]}, einstellung=lambda: Einstellung.aus(daten))


def test_ohne_einwilligung_wird_kein_anbieter_gefragt_und_es_gibt_keine_zahl():
    fake = Fake()
    auskunft = dienst(fake, aktiv=False).auskunft(ORT, beginn=BEGINN)
    assert fake.aufrufe == []
    assert (auskunft.status, auskunft.minuten, auskunft.losfahren) == (w.AUS, None, None)
    assert auskunft.satz == f'Ort: {ORT}. Fahrzeit unbekannt.' and auskunft.hinweis == 'einwilligung'


def test_einwilligung_ist_vorgabe_aus_und_nur_ein_echtes_true_zaehlt():
    assert Einstellung.aus({}).aktiv is False and Einstellung.aus(None).aktiv is False
    assert Einstellung.aus({'aktiv': 'ja'}).aktiv is False and Einstellung.aus({'aktiv': 1}).aktiv is False
    assert Einstellung.aus({'aktiv': True}).aktiv is True


def test_ohne_dienst_steht_ein_ehrlicher_satz_statt_einer_zahl():
    auskunft = dienst(Fake(verfuegbar=False)).auskunft(ORT, beginn=BEGINN)
    assert auskunft.status == w.OHNE_DIENST and auskunft.minuten is None and auskunft.losfahren is None
    assert auskunft.satz == f'Ort: {ORT}. Fahrzeit unbekannt.'
    assert 'Kartendienst' in auskunft.grund and auskunft.hinweis == 'dienst'


def test_ohne_startort_fragt_die_auskunft_nach_der_heimat_statt_zu_raten():
    fake = Fake()
    auskunft = dienst(fake, heimat='').auskunft(ORT, beginn=BEGINN)
    assert auskunft.status == w.OHNE_START and auskunft.hinweis == 'heimat' and fake.aufrufe == []
    assert auskunft.satz == f'Ort: {ORT}. Fahrzeit unbekannt.'


def test_berechnet_nennt_zahl_verkehrsmittel_quelle_und_losfahrzeit_mit_puffer():
    fake = Fake(name='Apple Karten', minuten=35)
    auskunft = dienst(fake).auskunft(ORT, beginn=BEGINN)
    assert fake.aufrufe == [(HEIMAT, ORT, 'auto')]
    assert (auskunft.status, auskunft.minuten, auskunft.puffer_min) == (w.BERECHNET, 35, 10)
    assert auskunft.losfahren == BEGINN - timedelta(minutes=45) and auskunft.quelle == 'Apple Karten'
    assert 'Losfahren um 13:15 Uhr' in auskunft.satz and '35 Minuten mit dem Auto' in auskunft.satz
    assert 'Apple Karten' in auskunft.satz and '10 Minuten Puffer' in auskunft.satz


def test_oepnv_bekommt_mehr_puffer_und_zu_fuss_wird_benannt():
    oepnv = dienst(Fake(minuten=40), verkehrsmittel='oepnv').auskunft(ORT, beginn=BEGINN)
    assert oepnv.puffer_min == 15 and oepnv.losfahren == BEGINN - timedelta(minutes=55) and 'Bus und Bahn' in oepnv.satz
    fuss = dienst(Fake(minuten=20), verkehrsmittel='fuss').auskunft(ORT, beginn=BEGINN)
    assert 'zu Fuß' in fuss.satz and fuss.puffer_min == 10


def test_startpunkt_ist_der_ort_des_vorherigen_termins_und_ein_zu_spaetes_ende_wird_gemeldet():
    fake = Fake(minuten=30)
    ende = BEGINN - timedelta(minutes=20)
    auskunft = dienst(fake).auskunft(ORT, beginn=BEGINN, vorheriger=('Klinikum Mitte, Hauptstraße 3', ende))
    assert fake.aufrufe == [('Klinikum Mitte, Hauptstraße 3', ORT, 'auto')]
    assert auskunft.start_art == 'vorheriger_termin' and 'von Klinikum Mitte' in auskunft.satz
    # Losfahren 13:20, der Termin davor endet 13:40: knapp.
    assert auskunft.knapp == 'Der Termin davor endet erst um 13:40 Uhr. Das wird knapp.' and auskunft.knapp in auskunft.satz
    rechtzeitig = dienst(Fake(minuten=30)).auskunft(ORT, beginn=BEGINN, vorheriger=('Klinikum Mitte', BEGINN - timedelta(hours=3)))
    assert rechtzeitig.knapp == ''


def test_ein_vorheriger_termin_der_sich_ueberschneidet_ist_kein_startpunkt():
    fake = Fake()
    dienst(fake).auskunft(ORT, beginn=BEGINN, vorheriger=('Klinikum Mitte', BEGINN + timedelta(minutes=10)))
    assert fake.aufrufe[0][0] == HEIMAT


def test_online_termine_und_fehlende_orte_verlassen_den_rechner_nie():
    fake = Fake()
    d = dienst(fake)
    for ort in ('', None, 'Zoom', 'https://teams.microsoft.com/l/meetup-join/abc', 'online', 'Telefonat'):
        assert d.auskunft(ort, beginn=BEGINN).status == w.OHNE_ORT
    assert fake.aufrufe == []
    assert dienst(fake).auskunft('', beginn=BEGINN).satz == 'Kein Ort im Termin.'


def test_am_ziel_braucht_es_keine_fahrt():
    fake = Fake()
    assert dienst(fake).auskunft(HEIMAT.upper(), beginn=BEGINN).status == w.OHNE_ORT and fake.aufrufe == []


def test_zweite_frage_kommt_aus_dem_zwischenspeicher():
    fake = Fake()
    d = dienst(fake)
    d.auskunft(ORT, beginn=BEGINN)
    d.auskunft(ORT, beginn=BEGINN)
    assert len(fake.aufrufe) == 1


def test_nicht_unterstuetztes_verkehrsmittel_faellt_auf_den_naechsten_anbieter():
    erster = Fake('Erster', fehler=NichtUnterstuetzt('kein Bus'))
    zweiter = Fake('Zweiter', minuten=50)
    auskunft = dienst(erster, zweiter, verkehrsmittel='oepnv').auskunft(ORT, beginn=BEGINN)
    assert auskunft.status == w.BERECHNET and auskunft.quelle == 'Zweiter' and len(erster.aufrufe) == 1


def test_ausfall_des_anbieters_liefert_keine_zahl_und_keinen_fremdtext():
    unerwartet = Fake(fehler=RuntimeError(f'Verbindung zu geheim.example/{HEIMAT} abgelehnt'))
    auskunft = dienst(unerwartet).auskunft(ORT, beginn=BEGINN)
    assert auskunft.status == w.FEHLER and auskunft.minuten is None and HEIMAT not in auskunft.grund
    bekannt = dienst(Fake(fehler=WegezeitFehler('Apple Karten findet keine Route.'))).auskunft(ORT, beginn=BEGINN)
    assert bekannt.grund == 'Apple Karten findet keine Route.' and bekannt.satz == f'Ort: {ORT}. Fahrzeit unbekannt.'


def test_gewaehlter_dienst_wird_genau_er_gefragt():
    apple, google = Fake('Apple'), Fake('Google')
    auskunft = dienst(apple, google, dienst='google').auskunft(ORT, beginn=BEGINN)
    assert apple.aufrufe == [] and auskunft.quelle == 'Google'


# -- Kartendienste mit Schlüssel ----------------------------------------------


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openrouteservice_schluessel_im_kopf_nie_in_der_adresse_und_nie_im_log(caplog):
    gesehen = []

    def handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen.append(anfrage)
        if anfrage.url.path.endswith('/geocode/search'):
            return httpx.Response(200, json={'features': [{'geometry': {'coordinates': [8.2, 50.1]}}]})
        return httpx.Response(200, json={'features': [{'properties': {'summary': {'duration': 1980.0}}}]})

    dienst_ = OpenRouteService(lambda: GEHEIM, client=_client(handler))
    with caplog.at_level(logging.DEBUG):
        fahrzeit = dienst_.fahrzeit(HEIMAT, ORT, 'auto', None)
    assert (fahrzeit.minuten, fahrzeit.quelle) == (33, 'OpenRouteService')
    assert all(GEHEIM not in str(a.url) and a.headers['Authorization'] == GEHEIM for a in gesehen)
    assert GEHEIM not in caplog.text
    assert any(a.url.path.endswith('/v2/directions/driving-car') for a in gesehen)


def test_openrouteservice_kennt_keinen_oepnv_und_meldet_fehler_ohne_schluessel(caplog):
    with pytest.raises(NichtUnterstuetzt):
        OpenRouteService(lambda: GEHEIM, client=_client(lambda a: httpx.Response(200))).fahrzeit('a', 'b', 'oepnv', None)
    with pytest.raises(WegezeitFehler) as fehler:
        OpenRouteService(lambda: GEHEIM, client=_client(lambda a: httpx.Response(401, text=GEHEIM))).fahrzeit('a', 'b', 'auto', None)
    assert GEHEIM not in str(fehler.value) and 'Schlüssel' in str(fehler.value)
    assert not OpenRouteService(lambda: None).verfuegbar()
    with pytest.raises(WegezeitFehler):
        OpenRouteService(lambda: None).fahrzeit('a', 'b', 'auto', None)


def test_google_routes_schickt_nur_zwei_adressen_und_liest_die_dauer(caplog):
    gesehen = []

    def handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen.append(anfrage)
        return httpx.Response(200, json={'routes': [{'duration': '2460s'}]})

    fahrzeit = GoogleRoutes(lambda: GEHEIM, client=_client(handler)).fahrzeit(HEIMAT, ORT, 'oepnv', BEGINN)
    assert (fahrzeit.minuten, fahrzeit.verkehrsmittel) == (41, 'oepnv')
    anfrage = gesehen[0]
    assert anfrage.headers['X-Goog-Api-Key'] == GEHEIM and GEHEIM not in str(anfrage.url)
    import json
    koerper = json.loads(anfrage.content)
    assert koerper['origin'] == {'address': HEIMAT} and koerper['destination'] == {'address': ORT}
    assert koerper['travelMode'] == 'TRANSIT' and set(koerper) <= {'origin', 'destination', 'travelMode', 'departureTime'}


def test_google_routes_fehler_tragen_weder_schluessel_noch_adresse():
    with pytest.raises(WegezeitFehler) as fehler:
        GoogleRoutes(lambda: GEHEIM, client=_client(lambda a: httpx.Response(403, text=GEHEIM))).fahrzeit(HEIMAT, ORT, 'auto', None)
    assert GEHEIM not in str(fehler.value) and HEIMAT not in str(fehler.value)

    def kaputt(anfrage):
        raise httpx.ConnectError(f'{GEHEIM} {HEIMAT}')
    with pytest.raises(WegezeitFehler) as fehler:
        GoogleRoutes(lambda: GEHEIM, client=_client(kaputt)).fahrzeit(HEIMAT, ORT, 'auto', None)
    assert GEHEIM not in str(fehler.value) and HEIMAT not in str(fehler.value)
    assert fehler.value.__cause__ is None or GEHEIM not in repr(fehler.value.__cause__)


def test_httpx_protokolliert_keine_adressen_der_kartendienste(caplog):
    logger = logging.getLogger('httpx')
    with caplog.at_level(logging.INFO, logger='httpx'):
        logger.info('HTTP Request: GET https://api.openrouteservice.org/geocode/search?text=Musterstra%C3%9Fe "HTTP/1.1 200 OK"')
        logger.info('HTTP Request: GET https://example.org/anderes "HTTP/1.1 200 OK"')
    assert 'openrouteservice' not in caplog.text and 'example.org' in caplog.text


def test_geheimnis_gibt_sich_nicht_aus():
    g = w.Geheimnis(GEHEIM)
    assert GEHEIM not in repr(g) and GEHEIM not in str(g) and GEHEIM not in f'{g!r} {g}' and g.offen() == GEHEIM


# -- Apple Karten über den Mac-Helfer -------------------------------------------


def test_mac_karten_ohne_lebenszeichen_wartet_nicht():
    kasten = Briefkasten()
    karten = MacKarten(kasten, warten_s=5)
    assert not karten.verfuegbar()
    begonnen = time.monotonic()
    with pytest.raises(WegezeitFehler):
        karten.fahrzeit(HEIMAT, ORT, 'auto', None)
    assert time.monotonic() - begonnen < 1


def test_mac_karten_frage_und_antwort_ueber_den_briefkasten():
    kasten = Briefkasten()
    kasten.offene()  # Lebenszeichen des Arbeiters
    karten = MacKarten(kasten, warten_s=5)

    def arbeiter():
        for _ in range(100):
            offen = kasten.offene()
            if offen:
                assert (offen[0]['von'], offen[0]['nach'], offen[0]['verkehrsmittel']) == (HEIMAT, ORT, 'auto')
                kasten.beantworten(offen[0]['id'], minuten=28)
                return
            time.sleep(0.02)
    faden = threading.Thread(target=arbeiter)
    faden.start()
    fahrzeit = karten.fahrzeit(HEIMAT, ORT, 'auto', None)
    faden.join()
    assert (fahrzeit.minuten, fahrzeit.quelle) == (28, 'Apple Karten')


def test_mac_karten_fehler_und_nicht_unterstuetzt_werden_uebersetzt():
    kasten = Briefkasten()
    kasten.offene()
    karten = MacKarten(kasten, warten_s=5)

    def antworten(**antwort):
        def arbeiter():
            for _ in range(100):
                offen = kasten.offene()
                if offen:
                    kasten.beantworten(offen[0]['id'], **antwort)
                    return
                time.sleep(0.02)
        faden = threading.Thread(target=arbeiter)
        faden.start()
        return faden
    faden = antworten(fehler='nicht_unterstuetzt')
    with pytest.raises(NichtUnterstuetzt):
        karten.fahrzeit(HEIMAT, ORT, 'oepnv', None)
    faden.join()
    faden = antworten(fehler='keine_route')
    with pytest.raises(WegezeitFehler):
        karten.fahrzeit(HEIMAT, ORT, 'auto', None)
    faden.join()
    assert kasten.beantworten('gibt-es-nicht', minuten=5) is False
