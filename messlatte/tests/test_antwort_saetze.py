"""Stufe „Antwort“ mit Sätzen (E3): sorgfältiges und unaufmerksames Skriptmodell, ohne echtes Modell.

Die Mechanik ist messbar: Ein sorgfältiges Modell erzeugt keine falsche Aussage, ein unaufmerksames, das die alte
Frist nennt, wird von der Bewertung als falsch erkannt (oder schon von der Satzprüfung verworfen), und erfundene
Zahlen fallen durch die Satzprüfung. Die Qualität eines echten Modells misst das nicht.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import Bestand
from skriptmodell import SkriptModell

from messlatte.akten import RegelEinordnung
from messlatte.antwort import antworten
from messlatte.aufnahme import aufnehmen
from messlatte.bewertung import bewerte_antwort
from messlatte.instanz import instanz_starten
from messlatte.welt import lade_welt

FRAGE = 'Bis wann muss das Angebot für das Klinikum Mainz raus?'


def sorgfaeltig(nutzer):
    neu = next(b['nr'] for b in nutzer['belege'] if 'Neue Frist' in b['quelle'])
    return {'status': 'antwort', 'saetze': [{'text': 'Das Angebot muss bis zum 26. Oktober raus.', 'belege': [neu]}]}


def unaufmerksam(nutzer):
    alt = next(b['nr'] for b in nutzer['belege'] if 'Re: Angebot' in b['quelle'])
    return {'status': 'antwort', 'saetze': [{'text': 'Das Angebot muss bis zum 12. Oktober raus.', 'belege': [alt]}]}


def erfindet(nutzer):
    neu = next(b['nr'] for b in nutzer['belege'] if 'Neue Frist' in b['quelle'])
    return {'status': 'antwort', 'saetze': [{'text': 'Das Angebot muss bis zum 30. Oktober raus.', 'belege': [neu]}]}


@pytest.fixture(scope='module')
def stufe():
    welt = lade_welt(Path(__file__).parent / 'mini_welt')
    modell = SkriptModell({'Angebot für das Klinikum Mainz raus': ['Oktober']}, saetze={})
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell) as instanz:
        bestand = Bestand(instanz, welt, aufnehmen(instanz, welt.quellen, welt.stichtag, modell=RegelEinordnung()))
        bestand.modell = modell
        yield bestand


def fragen(stufe, regel):
    stufe.modell.saetze = {'Angebot für das Klinikum Mainz raus': regel}
    frage = stufe.frage('mainz-01')
    ergebnis = antworten(stufe.instanz, frage, stufe.rueck)
    return ergebnis, bewerte_antwort(frage, ergebnis)


def test_sorgfaeltiges_modell_ergibt_einen_satz_mit_beleg_und_keine_falsche_aussage(stufe):
    ergebnis, bewertung = fragen(stufe, sorgfaeltig)
    assert ergebnis.text.startswith('Das Angebot muss bis zum 26. Oktober raus. [')
    assert bewertung.klasse == 'richtig' and not bewertung.falsche_aussage, (ergebnis.text, bewertung)
    assert 'mainz-003' in (ergebnis.belege or ())


def test_unaufmerksames_modell_wird_gestoppt_oder_als_falsch_erkannt(stufe):
    ergebnis, bewertung = fragen(stufe, unaufmerksam)
    # Entweder verwirft die Satzprüfung den Satz mit der überholten Frist (dann steht der Zitatmodus da und nennt
    # sie als überholt), oder er besteht, und die Bewertung erkennt die falsche Aussage. Nie stilles Durchgehen.
    if ergebnis.text.startswith('Das Angebot muss bis zum 12. Oktober'):
        assert bewertung.falsche_aussage and bewertung.klasse == 'falsch'
    else:
        assert 'Quelle berichtet' in ergebnis.text
        assert 'Das Angebot muss bis zum 12. Oktober raus.' not in ergebnis.text


def test_erfundene_zahl_faellt_durch_die_satzpruefung(stufe):
    ergebnis, _ = fragen(stufe, erfindet)
    assert '30. Oktober' not in ergebnis.text
    assert 'Quelle berichtet' in ergebnis.text, 'Kein Satz besteht: Zitatmodus statt einer unbelegten Antwort'


def test_nichts_vorhanden_wird_zur_ehrlichen_antwort_ohne_raten(stufe):
    ergebnis, bewertung = fragen(stufe, {'status': 'nichts_vorliegend', 'saetze': []})
    assert ergebnis.status == 'working_unknown' and 'keine Information vor' in ergebnis.text
    assert bewertung.erkannt == 'nicht_bekannt'
