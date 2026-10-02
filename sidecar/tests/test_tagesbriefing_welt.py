"""Tageslage: die Zeilen Wetter (Wohnort und Termin) und Welt (eine Meldung, nur wenn vorhanden)."""
from icarus_memory import tagesbriefing as tb
from tests.test_tagesbriefing import JETZT, WEG, WETTER, frist, vorbereitung

MELDUNG = {'id': 'm1', 'titel': 'Klinikum Rheingau-Süd baut aus', 'link': 'https://news.example/a1', 'quelle_id': 'f0',
           'quelle': 'Fachzeitung', 'sache': 'organisation:klinikum', 'sache_name': 'Klinikum Rheingau-Süd',
           'grund': 'Betrifft Klinikum Rheingau-Süd, weil dazu 4 Quellen in deinen Akten stehen.'}
DORT = {'ort': 'Mainz', 'wann': JETZT.replace(hour=14), 'wetter': {'temperature_c': 12, 'condition': 'Regen', 'schirm': True}}


def test_ohne_meldung_gibt_es_keine_weltzeile():
    lage = tb.erstellen([vorbereitung(weg=WEG)], [frist()], WETTER, jetzt=JETZT, welt=None)
    assert 'welt' not in [z.art for z in lage.zeilen]
    assert 'welt' not in [z.art for z in tb.erstellen([], [], None, jetzt=JETZT, welt={}).zeilen]


def test_die_weltzeile_zitiert_den_titel_nennt_den_grund_und_bietet_vier_wege():
    lage = tb.erstellen([vorbereitung(weg=WEG)], [frist()], WETTER, jetzt=JETZT, welt=MELDUNG)
    zeile = lage.zeilen[-1]
    assert zeile.art == 'welt' and len(lage.zeilen) <= tb.MAX_ZEILEN
    assert zeile.text == ('„Klinikum Rheingau-Süd baut aus“ (Fachzeitung). Betrifft Klinikum Rheingau-Süd, weil dazu 4 Quellen '
                          'in deinen Akten stehen.')
    assert [(a.art, a.ref) for a in zeile.aktionen] == [
        ('link', 'https://news.example/a1'), ('akte', 'organisation:klinikum'), ('welt_quelle', 'f0'),
        ('welt_sache', 'organisation:klinikum')]
    assert zeile.aktionen[3].beschriftung == 'Nicht mehr zu Klinikum Rheingau-Süd'


def test_eine_meldung_ohne_begruendung_wird_nicht_gezeigt():
    ohne = {k: v for k, v in MELDUNG.items() if k != 'grund'}
    assert tb.erstellen([], [], None, jetzt=JETZT, welt=ohne).zeilen == []


def test_wetter_daheim_und_am_termin_stehen_in_einer_zeile_getrennt_von_der_packliste():
    lage = tb.erstellen([vorbereitung(weg=WEG, einpacken=False)], [], WETTER, jetzt=JETZT, termin_wetter=DORT)
    assert 'einpacken' not in [z.art for z in lage.zeilen]
    wetter = next(z for z in lage.zeilen if z.art == 'wetter')
    assert wetter.text == 'Wetter in Wiesbaden: 14 °C, bewölkt. Mainz, 14 Uhr: 12 °C, regen – Schirm einpacken?'


def test_nur_das_wetter_am_termin_bekommt_ein_wetter_als_praefix():
    lage = tb.erstellen([vorbereitung(weg=WEG)], [], None, jetzt=JETZT, termin_wetter=DORT)
    assert next(z for z in lage.zeilen if z.art == 'wetter').text == 'Wetter: Mainz, 14 Uhr: 12 °C, regen – Schirm einpacken?'
    assert 'wetter' not in [z.art for z in tb.erstellen([vorbereitung(weg=WEG)], [], None, jetzt=JETZT).zeilen]


def test_mit_allem_bleiben_es_hoechstens_sechs_zeilen_in_fester_reihenfolge():
    lage = tb.erstellen([vorbereitung(weg=WEG)], [frist()], WETTER, jetzt=JETZT, termin_wetter=DORT, welt=MELDUNG)
    assert [z.art for z in lage.zeilen] == ['termin', 'leute', 'einpacken', 'fristen', 'wetter', 'welt']
