"""Antwortzeiten im Bericht: Median und 90-Prozent-Wert je Stufe, das Ziel „≤ 8 s Median“, nie „bestanden“ ohne Modell."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from skriptmodell import SkriptModell

from messlatte import bericht, lokal
from messlatte import zeiten as antwortzeit
from messlatte.aufnahme import aufnehmen
from messlatte.ergebnisse import AntwortErgebnis
from messlatte.instanz import instanz_starten
from messlatte.lauf import Optionen, durchfuehren
from messlatte.welt import lade_welt, pruefe_fragen_lokal

MINI = Path(__file__).parent / 'mini_welt'
REGELN = {'Umsatzsteuervoranmeldung': ['Umsatzsteuervoranmeldung'], 'Angebot für das Klinikum Mainz raus': ['26. Oktober'],
          'Wann entscheidet das Klinikum': ['Anfang November'], 'Stromrechnung im August': ['Rechnungsbetrag']}


def antwort(dauer, *, kalt=False, zeiten=None, fehler=''):
    return AntwortErgebnis(frage_id='q', dauer_s=dauer, kalt=kalt, zeiten=zeiten or {}, fehler=fehler)


# -- Rechnung ------------------------------------------------------------------------------------------


def test_median_und_90_prozent_wert_nach_naechstem_rang():
    assert antwortzeit.kennzahl([]) is None
    assert antwortzeit.kennzahl([2.0]) == {'n': 1, 'median_s': 2.0, 'p90_s': 2.0}
    kz = antwortzeit.kennzahl([float(i) for i in range(1, 11)])
    assert kz == {'n': 10, 'median_s': 5.5, 'p90_s': 9.0}


def test_die_zielgrenze_ist_die_des_produkts():
    from icarus_memory import zeitmessung
    assert antwortzeit.ZIEL_MEDIAN_S == zeitmessung.ZIEL_MEDIAN_S == 8.0
    assert [n for n, _ in antwortzeit.ABSCHNITTE] == [*zeitmessung.ABSCHNITTE, zeitmessung.GESAMT]


def test_zeiten_aus_dem_kontext_werden_streng_gelesen():
    assert antwortzeit.lese({'suche': 0.3, 'gesamt': 2, 'fremd': 1, 'frage': 'x', 'satzpruefung': True}) == {
        'suche': 0.3, 'gesamt': 2.0}
    assert antwortzeit.lese(None) == antwortzeit.lese([]) == {}


def test_ziel_bestanden_nicht_bestanden_und_nie_bestanden_ohne_modell():
    schnell = [antwort(1.0, zeiten={'antwort_modell': 0.5, 'gesamt': 1.0}) for _ in range(3)]
    langsam = [antwort(12.0, zeiten={'antwort_modell': 5.0, 'saetze_modell': 6.0, 'gesamt': 12.0}) for _ in range(3)]
    ohne = [antwort(0.1) for _ in range(3)]
    assert 'Antwortzeit im Ziel: ≤ 8 s Median: bestanden (Median 1.0 s' in antwortzeit.ziel_zeile(
        antwortzeit.auswerten([], schnell))
    assert 'Antwortzeit im Ziel: ≤ 8 s Median: nicht bestanden (Median 12.0 s' in antwortzeit.ziel_zeile(
        antwortzeit.auswerten([], langsam))
    text = antwortzeit.ziel_zeile(antwortzeit.auswerten([], ohne))
    assert 'nicht gemessen (kein Modell lief)' in text and 'bestanden' not in text.replace('nicht gemessen', '')


def test_die_kalte_antwort_und_fehler_zaehlen_nicht():
    liste = [antwort(60.0, kalt=True, zeiten={'antwort_modell': 59.0, 'gesamt': 60.0}),
             antwort(99.0, fehler='Timeout', zeiten={'antwort_modell': 99.0, 'gesamt': 99.0}),
             antwort(2.0, zeiten={'antwort_modell': 1.5, 'gesamt': 2.0})]
    auswertung = antwortzeit.auswerten([], liste)
    assert auswertung['antwort_warm']['n'] == 1 and auswertung['antwort_warm']['median_s'] == 2.0
    assert auswertung['abschnitte']['antwort_modell'] == {'n': 1, 'median_s': 1.5, 'p90_s': 1.5}


def test_abschnitte_die_nie_liefen_stehen_nicht_in_der_tabelle():
    auswertung = antwortzeit.auswerten([0.2, 0.4], [antwort(1.0, zeiten={'suche': 0.2, 'antwort_modell': 0.6, 'gesamt': 1.0})])
    tabelle = '\n'.join(antwortzeit.markdown(auswertung))
    assert 'Abruf je Frage (Suche ohne Modell) | 2 | 0.3 | 0.4' in tabelle
    assert 'Antwortmodell' in tabelle and 'Sätze (zweiter Modellaufruf)' not in tabelle


# -- Im Bericht des Laufs -------------------------------------------------------------------------------


@pytest.fixture(scope='module')
def ohne_modell():
    return durchfuehren(Optionen(welten=(str(MINI),)))


@pytest.fixture(scope='module')
def mit_modell():
    modell = SkriptModell(dict(REGELN), chat='Das weiß ich nicht.')
    return durchfuehren(Optionen(welten=(str(MINI),), modell='ollama:skript'), anbieter_bauen=lambda wahl: modell)


def test_bericht_mit_skriptmodell_zeigt_zeiten_je_stufe_und_das_ziel(mit_modell):
    text = bericht.markdown(mit_modell)
    assert '- **Antwortzeit im Ziel: ≤ 8 s Median: bestanden' in text.split('## Aufnahme')[0]
    abschnitt = text.split('### Antwortzeit')[1].split('## Abruf je Kategorie')[0]
    for zeile in ('Abruf je Frage (Suche ohne Modell)', 'Antwort gesamt, warm (über die API)', 'Suche und Kontext',
                  'Antwortmodell (Quellen wählen)', 'Sätze (zweiter Modellaufruf)', 'Satzprüfung',
                  'Antwort gesamt laut Produkt'):
        assert zeile in abschnitt, zeile
    assert 'Median (s) | 90-Prozent-Wert (s)' in abschnitt


def test_json_traegt_die_kennzahlen_und_je_frage_die_zeiten(mit_modell, tmp_path):
    json_pfad, _ = bericht.schreibe(mit_modell, tmp_path)
    daten = json.loads(json_pfad.read_text(encoding='utf-8'))
    zeit = daten['antwort']['antwortzeit']
    assert zeit['modell_lief'] is True and zeit['ziel']['bestanden'] is True and zeit['ziel']['grenze_s'] == 8.0
    assert set(zeit['abschnitte']) >= {'suche', 'antwort_modell', 'saetze_modell', 'satzpruefung', 'gesamt'}
    assert zeit['abruf']['n'] == 8 and zeit['antwort_warm']['n'] >= 1
    assert any(set(f['antwort']['zeiten']) >= {'antwort_modell', 'gesamt'} for f in daten['fragen'])


def test_ohne_modell_steht_nicht_gemessen_und_der_abruf_hat_trotzdem_seine_zeit(ohne_modell):
    text = bericht.markdown(ohne_modell)
    assert 'Antwortzeit im Ziel: ≤ 8 s Median: nicht gemessen (kein Modell lief)' in text
    assert 'Abruf je Frage (Suche ohne Modell) | 8 |' in text
    assert 'bestanden' not in text.casefold()


def test_langsames_modell_ist_nicht_bestanden(monkeypatch):
    """Ein Modell, das länger als die Grenze braucht: Die Zeile sagt es, der Lauf bricht nicht ab."""
    modell = SkriptModell(dict(REGELN), chat='Das weiß ich nicht.')
    ergebnis = durchfuehren(Optionen(welten=(str(MINI),), modell='ollama:skript'), anbieter_bauen=lambda wahl: modell)
    langsam = [antwort(9.5, zeiten={'antwort_modell': 9.0, 'gesamt': 9.5}) for _ in ergebnis.fragen]
    monkeypatch.setattr(bericht, '_antwortzeit', lambda fragen: antwortzeit.auswerten([], langsam))
    assert 'Antwortzeit im Ziel: ≤ 8 s Median: nicht bestanden' in bericht.markdown(ergebnis)


# -- Im lokalen Modus -----------------------------------------------------------------------------------


class OhneSchliessen:
    def __init__(self, client):
        self._client = client

    def request(self, methode, url, **kwargs):
        return self._client.request(methode, url, **kwargs)

    def close(self):
        pass


def test_lokal_berichtet_median_und_90_prozent_wert_ohne_inhalte():
    welt = lade_welt(MINI)
    modell = SkriptModell({'Umsatzsteuervoranmeldung': ['Umsatzsteuervoranmeldung']})
    fragen = pruefe_fragen_lokal({'fragen': [
        {'id': f'z-{i}', 'frage': 'Bis wann muss die Umsatzsteuervoranmeldung abgegeben werden?',
         'erwartet': {'verhalten': 'antworten', 'aussagen': [['10. Oktober']]}} for i in range(3)]})
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell) as instanz:
        aufnehmen(instanz, welt.quellen, welt.stichtag, modell=modell)
        ergebnis = lokal.messen(OhneSchliessen(instanz.client), fragen)
    text = lokal.markdown(ergebnis)
    assert '## Antwortzeit' in text and 'Antwortzeit im Ziel: ≤ 8 s Median: bestanden' in text
    assert 'Antwortmodell (Quellen wählen) | 2 |' in text, 'zwei warme Antworten, die kalte zählt nicht'
    daten = lokal.zu_dict(ergebnis)
    assert daten['antwortzeit']['modell_lief'] is True and daten['antwortzeit']['abruf'] is None
    assert all('gesamt' in f['zeiten'] for f in daten['fragen'])
    assert 'Umsatzsteuervoranmeldung abgegeben' not in json.dumps(daten) + text, 'keine Fragetexte im Bericht'
