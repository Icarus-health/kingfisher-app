"""Wetter: nur der Ort verlässt den Rechner, ohne Einstellung keine Anfrage, der Schirm nur als Frage."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from icarus_memory import wetter
from icarus_memory.wetter import Einstellung, WetterDienst, WetterFehler, ortsname, satz_am_termin

BERLIN = ZoneInfo('Europe/Berlin')
WANN = datetime(2026, 9, 30, 14, 0, tzinfo=BERLIN)
MAINZ = {'aktiv': True, 'ort': 'Wiesbaden, Hessen, Deutschland', 'name': 'Wiesbaden', 'breite': 50.0826, 'laenge': 8.24}
ADRESSE = 'Druckerei Braun, Werkstraße 4, 55116 Mainz'


class Attrappe:
    """Open-Meteo als Attrappe: merkt jede Anfrage, antwortet mit Regen um 14 Uhr."""

    def __init__(self, code=61, regen=80, fehler=False):
        self.aufrufe: list[tuple[str, dict]] = []
        self.code, self.regen, self.fehler = code, regen, fehler

    def __call__(self, url, params):
        self.aufrufe.append((url, dict(params)))
        if self.fehler:
            raise WetterFehler('HTTPError')
        if 'geocoding' in url:
            return {'results': [{'name': params['name'], 'latitude': 49.9929, 'longitude': 8.2473, 'admin1': 'Rheinland-Pfalz',
                                 'country': 'Deutschland'}]}
        tag = datetime(2026, 9, 30)
        zeiten = [(tag + timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M') for h in range(72)]
        return {'timezone': 'Europe/Berlin', 'current': {'temperature_2m': 14.4, 'weather_code': 3},
                'hourly': {'time': zeiten, 'temperature_2m': [12.4] * 72, 'weather_code': [self.code] * 72,
                           'precipitation_probability': [self.regen] * 72}}


def dienst(daten=MAINZ, holen=None, **kw):
    holen = holen or Attrappe(**kw)
    return WetterDienst(lambda: Einstellung.aus(daten, {}), holen=holen), holen


# -- Einstellung -------------------------------------------------------------------------------------------------------


def test_vorgabe_ist_aus_und_nur_ein_echtes_true_mit_ort_zaehlt():
    assert Einstellung.aus({}, {}).aktiv is False
    assert Einstellung.aus({'aktiv': 'true', 'name': 'Mainz', 'breite': 50, 'laenge': 8}, {}).aktiv is False
    assert Einstellung.aus({'aktiv': True, 'name': '', 'breite': 50, 'laenge': 8}, {}).aktiv is False  # ohne Ort
    assert Einstellung.aus({'aktiv': True, 'name': 'Mainz', 'breite': 500, 'laenge': 8}, {}).aktiv is False  # kein Ort auf der Erde
    assert Einstellung.aus({'aktiv': True, 'name': 'Mainz', 'breite': 50, 'laenge': 8}, {}).aktiv is True


def test_umgebungsvariablen_bleiben_als_vorbelegung_gueltig_und_die_oberflaeche_gewinnt():
    umgebung = {'KINGFISHER_WEATHER_ENABLED': 'true', 'KINGFISHER_WEATHER_LOCATION': 'Bonn',
                'KINGFISHER_WEATHER_LATITUDE': '50.73', 'KINGFISHER_WEATHER_LONGITUDE': '7.1'}
    vorbelegt = Einstellung.aus({}, umgebung)
    assert vorbelegt.aktiv and vorbelegt.name == 'Bonn' and vorbelegt.breite == 50.73
    assert not Einstellung.aus({}, {**umgebung, 'KINGFISHER_WEATHER_LATITUDE': ''}).aktiv  # unvollständig
    # Was in der Oberfläche gespeichert wurde, gilt; auch „aus“ schlägt die Umgebung.
    assert Einstellung.aus({'aktiv': False, 'name': 'Mainz', 'breite': 50, 'laenge': 8}, umgebung).aktiv is False
    assert Einstellung.aus({'aktiv': True, 'name': 'Mainz', 'breite': 50, 'laenge': 8}, umgebung).name == 'Mainz'


# -- Datensparsamkeit ----------------------------------------------------------------------------------------------------


def test_ohne_einstellung_geht_keine_anfrage_hinaus():
    d, holen = dienst({})
    assert d.aktuell() is None and d.am_ort(ADRESSE, WANN) is None
    d2, holen2 = dienst({**MAINZ, 'aktiv': False})
    assert d2.aktuell() is None and d2.am_ort(ADRESSE, WANN) is None
    assert holen.aufrufe == [] and holen2.aufrufe == [] and d.anfragen == d2.anfragen == 0


def test_nur_der_ortsname_und_gerundete_koordinaten_verlassen_den_rechner():
    d, holen = dienst()
    ergebnis = d.am_ort(ADRESSE, WANN)
    assert ergebnis['ort'] == 'Mainz' and ergebnis['schirm'] is True
    geocoding, vorhersage = holen.aufrufe
    assert geocoding[0] == wetter.GEOCODING_URL and geocoding[1]['name'] == 'Mainz'
    assert set(geocoding[1]) == {'name', 'count', 'language', 'format'}
    assert vorhersage[0] == wetter.VORHERSAGE_URL
    assert vorhersage[1]['latitude'] == '49.99' and vorhersage[1]['longitude'] == '8.25'  # gerundet, ein Kilometer
    assert set(vorhersage[1]) == {'latitude', 'longitude', 'timezone', 'forecast_days', 'current', 'hourly'}
    alles = repr(holen.aufrufe)
    for fremd in ('Werkstraße', 'Braun', 'Druckerei', 'Gespräch', '55116'):
        assert fremd not in alles


def test_nur_die_beiden_open_meteo_adressen_mit_https_werden_gefragt():
    d, holen = dienst()
    for url in ('https://evil.example/v1/forecast', 'http://api.open-meteo.com/v1/forecast',
                'https://api.open-meteo.com.evil.example/x'):
        with pytest.raises(WetterFehler):
            d._anfragen(url, {}, ttl=1, einwilligung=True)
    with pytest.raises(WetterFehler):
        d._anfragen(wetter.VORHERSAGE_URL, {}, ttl=1, einwilligung=False)
    assert holen.aufrufe == []


def test_antworten_werden_gemerkt_und_ein_fehler_wird_nicht_sofort_wiederholt():
    d, holen = dienst()
    assert d.aktuell()['temperature_c'] == 14 and d.aktuell()['condition'] == 'Bewölkt'
    assert len(holen.aufrufe) == 1
    kaputt = Attrappe(fehler=True)
    d2, _ = dienst(holen=kaputt)
    assert d2.aktuell() is None and d2.aktuell() is None and d2.am_ort(ADRESSE, WANN) is None
    assert len(kaputt.aufrufe) == 2  # Ortssuche und Vorhersage je einmal, dann Pause


# -- Ortsnamen und Sätze -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize('adresse, erwartet', [
    ('Druckerei Braun, Werkstraße 4, 55116 Mainz', 'Mainz'),
    ('Musterstraße 1, 65183 Wiesbaden', 'Wiesbaden'),
    ('55116 Mainz, Deutschland', 'Mainz'),
    ('Klinikum Rheingau-Süd, Bingen', 'Bingen'),
    ('Frankfurt', 'Frankfurt'),
    ('Konferenzraum 3', ''),
    ('Raum 4.12, Hauptstraße 3', ''),
    ('Zoom-Link https://x.example/j/1', ''),
    ('', ''),
])
def test_ortsname_ist_nur_der_ort_nie_die_strasse(adresse, erwartet):
    assert ortsname(adresse) == erwartet


def test_der_satz_zum_termin_nennt_den_schirm_nur_als_frage():
    nass = {'temperature_c': 12, 'condition': 'Regen', 'schirm': True}
    assert satz_am_termin('Mainz', WANN, nass) == 'Mainz, 14 Uhr: 12 °C, regen – Schirm einpacken?'
    trocken = {'temperature_c': 18, 'condition': 'Klar', 'schirm': False}
    assert satz_am_termin('Mainz', WANN.replace(minute=30), trocken) == 'Mainz, 14:30 Uhr: 18 °C, klar.'


def test_regenwahrscheinlichkeit_allein_reicht_fuer_die_frage_nach_dem_schirm():
    d, _ = dienst(code=3, regen=70)
    assert d.am_ort(ADRESSE, WANN)['schirm'] is True
    d2, _ = dienst(code=3, regen=10)
    assert d2.am_ort(ADRESSE, WANN)['schirm'] is False


def test_zeit_ausserhalb_der_vorhersage_gibt_kein_wetter():
    d, _ = dienst()
    assert d.am_ort(ADRESSE, WANN + timedelta(days=9)) is None


def test_die_ortssuche_liefert_treffer_zum_anklicken_und_schickt_nur_den_namen():
    d, holen = dienst({})
    treffer = d.suche('Mainz')
    assert treffer == [{'name': 'Mainz', 'ort': 'Mainz, Rheinland-Pfalz, Deutschland', 'breite': 49.9929, 'laenge': 8.2473}]
    assert holen.aufrufe[0][1]['name'] == 'Mainz' and d.suche('M') == []
