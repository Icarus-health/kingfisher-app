"""Die Antwortstufe fragt über die echte Konversations-API; das Modell ist ein Skript."""
from __future__ import annotations

import pytest
from conftest import Bestand
from skriptmodell import SkriptModell

from messlatte.antwort import antworten, lese_nachricht
from messlatte.aufnahme import aufnehmen
from messlatte.bewertung import bewerte_antwort
from messlatte.instanz import instanz_starten
from messlatte.welt import lade_welt

from pathlib import Path

REGELN = {
    'Umsatzsteuervoranmeldung': ['Umsatzsteuervoranmeldung'],
    'Angebot für das Klinikum Mainz raus': ['26. Oktober'],
    'Wann entscheidet das Klinikum': ['Anfang November'],
    'Stromrechnung im August': ['Rechnungsbetrag'],
}


@pytest.fixture(scope='module')
def modellbestand():
    welt = lade_welt(Path(__file__).parent / 'mini_welt')
    modell = SkriptModell(dict(REGELN))
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell) as instanz:
        # Das Modell ordnet die Quellen selbst ein, wie im Betrieb.
        bestand = Bestand(instanz, welt, aufnehmen(instanz, welt.quellen, welt.stichtag, modell=modell))
        bestand.modell = modell
        yield bestand


def frage_stellen(bestand, kennung, **optionen):
    frage = bestand.frage(kennung)
    ergebnis = antworten(bestand.instanz, frage, bestand.rueck, **optionen)
    return frage, ergebnis, bewerte_antwort(frage, ergebnis)


def test_das_modell_hat_die_quellen_eingeordnet(modellbestand):
    assert modellbestand.modell.einordnungen >= 13
    assert 'Modell skript-1' in modellbestand.aufnahme.einordnung


def test_frist_wird_richtig_beantwortet_mit_beleg_als_welt_id(modellbestand):
    _, ergebnis, bewertung = frage_stellen(modellbestand, 'rechnung-02')
    assert ergebnis.fehler == '' and ergebnis.status == 'working_reports'
    assert ergebnis.belege == ('rechnung-004',)
    assert bewertung.klasse == 'richtig', bewertung


def test_aktuelle_frist_ohne_die_alte(modellbestand):
    _, ergebnis, bewertung = frage_stellen(modellbestand, 'mainz-01')
    assert '26. Oktober' in ergebnis.text and '12. Oktober' not in ergebnis.text
    assert ergebnis.belege == ('mainz-003',) and bewertung.klasse == 'richtig', bewertung


def test_veraltete_quelle_im_kontext_wird_als_falsche_aussage_erkannt(modellbestand):
    # Das Skript wählt beide Fristen: Der Nutzer läse „12. Oktober“. Genau das ist die falsche Aussage.
    modellbestand.modell.regeln['Angebot für das Klinikum Mainz raus'] = ['Oktober']
    try:
        _, ergebnis, bewertung = frage_stellen(modellbestand, 'mainz-01')
    finally:
        modellbestand.modell.regeln['Angebot für das Klinikum Mainz raus'] = REGELN['Angebot für das Klinikum Mainz raus']
    assert '12. Oktober' in ergebnis.text
    assert bewertung.klasse == 'falsch' and bewertung.falsche_aussage
    assert bewertung.verbotene_aussagen == ('12. Oktober',)
    assert {'mainz-001', 'mainz-002'} & set(bewertung.verbotene_belege)


def test_belegte_antwort_wird_als_richtig_bewertet(modellbestand):
    _, ergebnis, bewertung = frage_stellen(modellbestand, 'mainz-03')
    assert 'Anfang November' in ergebnis.text and bewertung.klasse == 'richtig', (ergebnis.text, bewertung)


def test_nichts_vorhanden_wird_ehrlich_gesagt(modellbestand):
    _, ergebnis, bewertung = frage_stellen(modellbestand, 'rechnung-03')
    assert ergebnis.status == 'working_unknown' and 'keine Information vor' in ergebnis.text
    assert bewertung.klasse == 'richtig' and bewertung.erkannt == 'nicht_bekannt'


def test_mehrdeutige_frage_wird_als_rueckfrage_erkannt(modellbestand):
    _, ergebnis, bewertung = frage_stellen(modellbestand, 'mainz-02')
    assert ergebnis.status == 'meaning_choice' and len(ergebnis.auswahl) >= 1
    assert bewertung.erkannt == 'rueckfrage'
    assert bewertung.klasse in {'richtig', 'unvollstaendig'}  # unvollständig, solange das Produkt nicht alle Bedeutungen anbietet


def test_eine_frage_zum_bestand_geht_in_den_belegten_weg_und_nicht_in_den_chat(modellbestand):
    # „Um wie viel Uhr beginnt …?“ begann früher mit keinem Fragewort der Liste und ging in den freien Chat.
    _, ergebnis, _ = frage_stellen(modellbestand, 'mainz-04')
    assert ergebnis.belege is not None and ergebnis.status.startswith('working_'), (ergebnis.text, ergebnis.status)


def test_freier_chat_ohne_belege_wird_am_text_bewertet(modellbestand):
    from dataclasses import replace
    # Eine Wissensfrage ohne Bezug zum Bestand bleibt im freien Chat.
    frage = replace(modellbestand.frage('mainz-04'), frage='Wie funktioniert ein Vulkan?')
    ergebnis = antworten(modellbestand.instanz, frage, modellbestand.rueck)
    bewertung = bewerte_antwort(frage, ergebnis)
    assert ergebnis.belege is None
    # Das Skript antwortet im Chat „Das weiß ich nicht.“ – belegt und beantwortbar, also verweigert.
    assert bewertung.klasse == 'verweigert', (ergebnis.text, ergebnis.status, bewertung)


def test_erste_anfrage_ist_kalt_gekennzeichnet_und_die_zeit_wird_gemessen(modellbestand):
    _, kalt, _ = frage_stellen(modellbestand, 'rechnung-01', kalt=True)
    _, warm, _ = frage_stellen(modellbestand, 'rechnung-01')
    assert kalt.kalt and not warm.kalt and kalt.dauer_s > 0 and warm.dauer_s > 0


def test_jede_frage_bekommt_ein_neues_gespraech(modellbestand):
    vorher = len(modellbestand.instanz.app.state.conversations.list(200))
    frage_stellen(modellbestand, 'rechnung-01')
    frage_stellen(modellbestand, 'rechnung-01')
    assert len(modellbestand.instanz.app.state.conversations.list(200)) == vorher + 2


def test_technischer_fehler_wird_zum_ergebnis_nicht_zur_ausnahme():
    class Kaputt:
        def anfrage(self, *_):
            raise RuntimeError('Server nicht erreichbar')

    from messlatte.daten import Erwartet, Frage
    frage = Frage(id='x-1', frage='?', kategorie='frist', schwere='normal', erwartet=Erwartet('antworten', (('a',),)))
    ergebnis = antworten(Kaputt(), frage, {})
    assert 'Server nicht erreichbar' in ergebnis.fehler
    assert bewerte_antwort(frage, ergebnis).klasse == 'fehler'


def test_nachricht_ohne_metadaten_wird_gelesen():
    assert lese_nachricht({'content': 'Hallo'}, {}) == {'text': 'Hallo', 'status': '', 'belege': None, 'auswahl': (), 'zeiten': {}}
