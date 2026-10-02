"""Stufe „Antwort“ mit dem zweiten Tor (Prüfmodell): ein falscher Satz ohne Anker wird verworfen und getrennt gezählt.

Die Mini-Welt bekommt dafür (nur in der Kopie) ein Skript für `mainz-03`: Der richtige Satz sagt, dass das Klinikum
Anfang November entscheidet; der falsche, dass Lea Hartmann entscheidet. Beide bestehen die Satzprüfung ohne Modell
(Name, Zeitangabe und Wörter stehen im Beleg). Ohne Prüfmodell kommt der falsche durch und die Bewertung sieht die
falsche Aussage; mit Prüfmodell wird er verworfen und als „vom Prüfmodell verworfen“ gezählt.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import Bestand, finde
from skriptmodell import SkriptModell

from messlatte import bericht
from messlatte.akten import RegelEinordnung
from messlatte.antwort import antworten
from messlatte.aufnahme import aufnehmen
from messlatte.bewertung import bewerte_antwort
from messlatte.instanz import instanz_starten
from messlatte.lauf import Optionen, durchfuehren
from messlatte.modell import ModellFehler, lese_modell
from messlatte.welt import WeltFehler, lade_welt

RICHTIG = 'Das Klinikum entscheidet über das Angebot erst Anfang November.'
FALSCH = 'Lea Hartmann entscheidet über das Angebot erst Anfang November.'


def mit_skript(frage, **aenderung):
    frage['verboten'] = {'aussagen': ['Lea Hartmann entscheidet']}
    frage['skript'] = {'auswahl': ['Anfang November'], 'richtig': RICHTIG, 'falsch': FALSCH, **aenderung}


@pytest.fixture
def welt_mit_skript(welt_kopie):
    welt_kopie('mainz', lambda d: mit_skript(finde(d['fragen'], 'mainz-03')))
    return welt_kopie.pfad


def lauf(pfad, modell, pruefung=''):
    return durchfuehren(Optionen(welten=(str(pfad),), modell=modell, modell_pruefung=pruefung, nur='wartet_auf',
                                 einordnung='regel'))


def test_unaufmerksam_ohne_pruefmodell_kommt_der_falsche_satz_durch_und_wird_als_falsch_erkannt(welt_mit_skript):
    ergebnis = lauf(welt_mit_skript, 'skript:unaufmerksam')
    [f] = ergebnis.fragen
    assert FALSCH in f.antwort.text and f.antwort_bewertung.falsche_aussage
    assert (f.antwort.verworfen_pruefmodell, f.antwort.pruefung) == (0, 'kein_modell')
    assert ergebnis.kopf['modell_pruefung'] == 'keins (zweites Tor aus)'


def test_unaufmerksam_mit_pruefmodell_wird_der_falsche_satz_verworfen_und_getrennt_gezaehlt(welt_mit_skript):
    ergebnis = lauf(welt_mit_skript, 'skript:unaufmerksam', 'skript:pruefung')
    [f] = ergebnis.fragen
    assert FALSCH not in f.antwort.text and RICHTIG in f.antwort.text
    assert not f.antwort_bewertung.falsche_aussage and f.antwort_bewertung.klasse == 'richtig'
    assert (f.antwort.verworfen_satzpruefung, f.antwort.verworfen_pruefmodell, f.antwort.pruefung) == (0, 1, 'an')
    text = bericht.markdown(ergebnis)
    assert '**vom Prüfmodell (zweites Tor): 1** (in 1 Antworten; Tor: an)' in text
    assert '| mainz-03 | 0 | 1 | an |' in text
    assert bericht.zu_dict(ergebnis)['antwort']['tore']['pruefmodell'] == 1


def test_sorgfaeltig_mit_pruefmodell_verwirft_keinen_richtigen_satz(welt_mit_skript):
    ergebnis = lauf(welt_mit_skript, 'skript:sorgfaeltig', 'skript:pruefung')
    [f] = ergebnis.fragen
    assert f.antwort.text.startswith(RICHTIG) and f.antwort_bewertung.klasse == 'richtig'
    assert (f.antwort.verworfen_satzpruefung, f.antwort.verworfen_pruefmodell) == (0, 0)
    assert 'Keine Antwort mit verworfenen Sätzen.' in bericht.markdown(ergebnis)


# -- Skriptmodell der Tests: Prüfmodus ------------------------------------------------------------


@pytest.fixture(scope='module')
def stufe():
    welt = lade_welt(Path(__file__).parent / 'mini_welt')
    modell = SkriptModell({'Klinikum über mein Angebot': ['Anfang November']})
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell, pruef_provider=modell) as instanz:
        bestand = Bestand(instanz, welt, aufnehmen(instanz, welt.quellen, welt.stichtag, modell=RegelEinordnung()))
        bestand.modell = modell
        yield bestand


def beide(nutzer):
    nummer = nutzer['belege'][0]['nr']
    return {'status': 'antwort', 'saetze': [{'text': RICHTIG, 'belege': [nummer]}, {'text': FALSCH, 'belege': [nummer]}]}


@pytest.mark.parametrize('urteil, bleibt', [('nein', [RICHTIG]), ('unklar', [RICHTIG]), (RuntimeError('weg'), [RICHTIG]),
                                            ('ja', [RICHTIG, FALSCH])])
def test_der_pruefmodus_des_skriptmodells_ist_skriptbar(stufe, urteil, bleibt):
    stufe.modell.saetze = {'Klinikum über mein Angebot': beide}
    stufe.modell.pruefung = {'Lea Hartmann': urteil}
    stufe.modell.pruefanfragen.clear()
    ergebnis = antworten(stufe.instanz, stufe.frage('mainz-03'), stufe.rueck)
    assert [s for s in (RICHTIG, FALSCH) if s in ergebnis.text] == bleibt
    assert sorted(stufe.modell.pruefanfragen) == sorted([RICHTIG, FALSCH]), 'jeder bestandene Satz wird gefragt'
    assert ergebnis.verworfen_pruefmodell == (0 if urteil == 'ja' else 1)
    assert bewerte_antwort(stufe.frage('mainz-03'), ergebnis).klasse == 'richtig'


# -- Welt und Modellwahl ----------------------------------------------------------------------------


def test_das_skript_muss_die_verbotene_aussage_tragen(welt_kopie):
    welt_kopie('mainz', lambda d: mit_skript(finde(d['fragen'], 'mainz-03'), falsch='Etwas ganz anderes.'))
    with pytest.raises(WeltFehler, match='skript.falsch'):
        lade_welt(welt_kopie.pfad)


def test_der_richtige_satz_darf_keine_verbotene_aussage_tragen(welt_kopie):
    welt_kopie('mainz', lambda d: mit_skript(finde(d['fragen'], 'mainz-03'), richtig=FALSCH))
    with pytest.raises(WeltFehler, match='skript.richtig'):
        lade_welt(welt_kopie.pfad)


def test_die_kategorie_inhalt_ist_erlaubt(welt_kopie):
    welt_kopie('mainz', lambda d: finde(d['fragen'], 'mainz-03').update(kategorie='inhalt'))
    assert finde([{'id': f.id, 'k': f.kategorie} for f in lade_welt(welt_kopie.pfad).fragen], 'mainz-03')['k'] == 'inhalt'


def test_skript_modellwahl():
    assert lese_modell('skript:sorgfaeltig').bezeichnung == 'skript:sorgfaeltig'
    with pytest.raises(ModellFehler, match='sorgfaeltig'):
        lese_modell('skript:irgendwas')
