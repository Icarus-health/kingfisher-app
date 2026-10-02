"""Namensvettern und Zeiträume im Kontext: Die Messlatte zählt sie als gekennzeichnet, getrennt nach Art.

Zusicherungen (Sabotageproben in `docs/39-kennzeichnung.md`):

1. Der Kandidatenerfasser liest die Felder `andere_person` und `ausserhalb_zeitraum` der Kontextzeilen
   (nicht nur `ueberholt`); die Ergebnisse führen sie getrennt nach Art.
2. Die Bewertung zählt eine so gekennzeichnete verbotene Quelle nicht mehr als ungekennzeichnet und weist die
   Belege je Art aus; ein Beleg mit zwei Arten zählt in beiden, aber nur einmal als gekennzeichnet.
3. Auf einer Mini-Welt mit zwei Alex Winter und einer Angebotsgeschichte kommt das durch den ganzen Produktpfad:
   Namensvetter und Quellen außerhalb der letzten Woche sind gekennzeichnet (ein Termin nach seinem Beginn), die
   passenden nicht, nichts fehlt, die offene Frage nach „Alex Winter“ bleibt eine Rückfrage.
4. Der Bericht führt die Arten getrennt in Kennzahl und Fehlerliste.
"""
from __future__ import annotations

import json
import shutil

import pytest
from conftest import MINI_WELT

from messlatte import bericht
from messlatte.abruf import Kandidatenerfasser
from messlatte.bewertung import bewerte_abruf, zaehle_abruf
from messlatte.daten import Erwartet, Frage, Verboten
from messlatte.ergebnisse import KENNZEICHNUNGEN, AbrufErgebnis
from messlatte.lauf import Optionen, durchfuehren

CATERING = {'name': 'Alex Winter', 'adresse': 'alex.winter@winter-catering.example'}
INSTITUT = {'name': 'Alex Winter', 'adresse': 'alex.winter@ifeh-hessen.example'}
LEA = {'name': 'Lea Hartmann', 'adresse': 'lea@hartmann-beratung.example'}
NORA = {'name': 'Nora Feldmann', 'adresse': 'n.feldmann@klinikum-rheingau.example'}


def mail(nummer, zeit, von, an, betreff, text, **weiter):
    return {'id': f'namensvettern-{nummer:03d}', 'art': 'mail', 'zeit': zeit, 'von': von, 'an': [an],
            'betreff': betreff, 'text': text, **weiter}


def termin(nummer, zeit, beginn, titel):
    return {'id': f'namensvettern-{nummer:03d}', 'art': 'termin', 'zeit': zeit, 'beginn': beginn,
            'ende': beginn.replace(':00+', ':45+', 1), 'titel': titel, 'teilnehmer': [NORA, LEA]}


SZENARIO = {
    'id': 'namensvettern',
    'titel': 'Zwei Alex Winter und ein Angebot über Monate',
    'beschreibung': 'Prüft die Kennzeichnung von Namensvettern und von Quellen außerhalb des gefragten Zeitraums.',
    'quellen': [
        mail(1, '2026-03-02T09:00:00+01:00', CATERING, LEA, 'Angebot Verpflegung', 'Unser Preis beträgt 34 Euro pro Person netto.'),
        mail(2, '2026-08-27T10:48:00+02:00', CATERING, LEA, 'Preisanpassung',
             'Der Preis pro Person beträgt jetzt 38 Euro netto. Herzliche Grüße Alex Winter, Catering'),
        mail(3, '2026-01-15T09:50:00+01:00', INSTITUT, LEA, 'Interviewanfrage Studie',
             'Ich bin Mitarbeiterin am Institut für Ernährungsforschung und bitte um ein Interview. Alex Winter'),
        mail(4, '2026-09-10T13:25:00+02:00', INSTITUT, LEA, 'Bitte um Feedback zum Fragebogen',
             'Könnten Sie mir bis zum 16. Oktober Feedback zum Fragebogen geben? Alex Winter, Institut'),
        mail(5, '2026-09-24T10:00:00+02:00', NORA, LEA, 'Referenzen fürs Gremium',
             'Bitte schicken Sie uns drei Referenzen zu Ihrem Angebot für das Klinikum Rheingau.'),
        mail(6, '2026-04-02T15:40:00+02:00', LEA, NORA, 'Angebot Klinikum Rheingau',
             'Mein Angebot für das Klinikum Rheingau: 35.000 Euro netto für neun Monate.', ordner='Sent'),
        # Angelegt im August, beginnt aber in der letzten Woche: Der Beginn zählt.
        termin(7, '2026-08-20T09:00:00+02:00', '2026-09-25T10:00:00+02:00', 'Nachgespräch Klinikum Rheingau'),
        # Angelegt in der letzten Woche, beginnt aber im Oktober: außerhalb.
        termin(8, '2026-09-22T09:00:00+02:00', '2026-10-14T10:00:00+02:00', 'Gremium Klinikum Rheingau'),
    ],
    'fragen': [
        {'id': 'namensvettern-01', 'frage': 'Was kostet das Catering von Alex Winter pro Person?', 'kategorie': 'identitaet',
         'schwere': 'kritisch',
         'erwartet': {'verhalten': 'antworten', 'aussagen': [['38 Euro']], 'belege': ['namensvettern-002']},
         'verboten': {'aussagen': [], 'belege': ['namensvettern-003', 'namensvettern-004']}},
        {'id': 'namensvettern-02', 'frage': 'Was ist mit Alex Winter?', 'kategorie': 'mehrdeutigkeit', 'schwere': 'kritisch',
         'erwartet': {'verhalten': 'rueckfrage', 'aussagen': [], 'bedeutungen': [['catering'], ['ifeh']],
                      'belege': ['namensvettern-002', 'namensvettern-004']},
         'verboten': {'aussagen': [], 'belege': []}},
        {'id': 'namensvettern-03', 'frage': 'Was lief letzte Woche mit dem Angebot für das Klinikum Rheingau?',
         'kategorie': 'zeitraum', 'schwere': 'normal',
         'erwartet': {'verhalten': 'antworten', 'aussagen': [['Referenzen']],
                      'belege': ['namensvettern-005', 'namensvettern-007']},
         'verboten': {'aussagen': [], 'belege': ['namensvettern-006', 'namensvettern-008']}},
    ],
}


@pytest.fixture(scope='module')
def lauf(tmp_path_factory):
    """Der ganze Lauf (Aufnahme, Abruf, Bericht) auf der Mini-Welt mit dem zusätzlichen Szenario."""
    ziel = tmp_path_factory.mktemp('kennzeichnung') / 'welt'
    shutil.copytree(MINI_WELT, ziel)
    (ziel / 'szenarien' / 'namensvettern.json').write_text(json.dumps(SZENARIO, ensure_ascii=False, indent=2), encoding='utf-8')
    return durchfuehren(Optionen(welten=(str(ziel),)))


def frage_von(lauf, kennung):
    return next(f for f in lauf.fragen if f.frage.id == kennung)


# -- 1. Der Erfasser --------------------------------------------------------------------------------------------


def test_der_erfasser_liest_alle_drei_kennzeichnungen_getrennt():
    erfasser = Kandidatenerfasser()
    quellen = [{'id': 'S1', 'ueberholt': [{'grund': 'x'}]}, {'id': 'S2', 'andere_person': [{'name': 'A'}]},
               {'id': 'S3', 'ausserhalb_zeitraum': {'datum_der_quelle': '2026-03-23'}}, {'id': 'S4'},
               {'id': 'S5', 'andere_person': [{'name': 'A'}], 'ausserhalb_zeitraum': {'datum_der_quelle': '2026-03-23'}}]
    erfasser.complete_json([{'role': 'system', 'content': 'x'},
                            {'role': 'user', 'content': json.dumps({'question': 'q', 'sources': quellen})}])
    assert erfasser.gekennzeichnet == {'ueberholt': {'S1'}, 'andere_person': {'S2', 'S5'}, 'ausserhalb_zeitraum': {'S3', 'S5'}}
    assert set(erfasser.gekennzeichnet) == set(KENNZEICHNUNGEN)


# -- 2. Die Bewertung ---------------------------------------------------------------------------------------------


def frage():
    return Frage(id='x-1', frage='?', kategorie='identitaet', schwere='kritisch',
                 erwartet=Erwartet('antworten', (('a',),), belege=('neu',)),
                 verboten=Verboten(belege=('alt', 'vetter', 'frueher', 'beides', 'frei')))


def abruf(**nach_art):
    kandidaten = ('neu', 'alt', 'vetter', 'frueher', 'beides', 'frei')
    return AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=kandidaten,
                         gekennzeichnet=tuple(dict.fromkeys(b for liste in nach_art.values() for b in liste)),
                         gekennzeichnet_nach_art=nach_art)


def test_gekennzeichnete_verbotene_belege_stehen_je_art_und_sind_nicht_mehr_ungekennzeichnet():
    bewertung = bewerte_abruf(frage(), abruf(ueberholt=('alt',), andere_person=('vetter', 'beides'),
                                             ausserhalb_zeitraum=('frueher', 'beides')))
    assert bewertung.verboten_gesehen == ('alt', 'vetter', 'frueher', 'beides', 'frei')
    assert bewertung.verboten_ungekennzeichnet == ('frei',)
    assert bewertung.verboten_gekennzeichnet == {'ueberholt': ('alt',), 'andere_person': ('vetter', 'beides'),
                                                 'ausserhalb_zeitraum': ('frueher', 'beides')}
    zaehler = zaehle_abruf([bewertung])
    assert (zaehler.verbotene_belege, zaehler.verbotene_belege_ungekennzeichnet) == (5, 1)
    # Ein Beleg mit zwei Arten zählt in beiden, aber die Summe der Arten übersteigt die gekennzeichneten Belege nicht unbemerkt:
    assert zaehler.verbotene_belege_gekennzeichnet == {'ueberholt': 1, 'andere_person': 2, 'ausserhalb_zeitraum': 2}
    assert zaehler.fragen_mit_verbotenem_beleg_ungekennzeichnet == 1


def test_ohne_die_neuen_arten_zaehlt_die_bisherige_kennzeichnung_als_ueberholt():
    alt = AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=('neu', 'alt'), gekennzeichnet=('alt',))
    bewertung = bewerte_abruf(frage(), alt)
    assert bewertung.verboten_gekennzeichnet == {'ueberholt': ('alt',)} and bewertung.verboten_ungekennzeichnet == ()


def test_eine_art_ausserhalb_der_kandidaten_zaehlt_nicht():
    ergebnis = AbrufErgebnis(frage_id='x-1', weg='bedeutungsfrage', kandidaten=('neu',),
                             gekennzeichnet=('vetter',), gekennzeichnet_nach_art={'andere_person': ('vetter',)})
    assert bewerte_abruf(frage(), ergebnis).verboten_gekennzeichnet == {}


# -- 3. Der Produktpfad ------------------------------------------------------------------------------------------------


def test_namensvetter_sind_gekennzeichnet_und_der_gemeinte_alex_winter_nicht(lauf):
    f = frage_von(lauf, 'namensvettern-01')
    assert f.abruf.weg == 'arbeitsstand', 'Das Catering entscheidet: keine Rückfrage'
    assert f.abruf_bewertung.gefunden == ('namensvettern-002',)
    assert set(f.abruf_bewertung.verboten_gesehen) == {'namensvettern-003', 'namensvettern-004'}
    assert f.abruf_bewertung.verboten_ungekennzeichnet == ()
    assert set(f.abruf.gekennzeichnet_nach_art['andere_person']) == {'namensvettern-003', 'namensvettern-004'}
    assert 'namensvettern-001' not in f.abruf.gekennzeichnet and 'namensvettern-002' not in f.abruf.gekennzeichnet


def test_die_offene_frage_nach_alex_winter_bleibt_eine_rueckfrage_ohne_kennzeichnung(lauf):
    f = frage_von(lauf, 'namensvettern-02')
    assert f.abruf.weg == 'bedeutungsfrage' and f.abruf.gekennzeichnet == ()
    assert not f.abruf_bewertung.unnoetige_rueckfrage
    assert lauf.abruf_gesamt.unnoetige_rueckfragen == 0


def test_quellen_ausserhalb_der_letzten_woche_sind_gekennzeichnet_ein_termin_zaehlt_nach_seinem_beginn(lauf):
    f = frage_von(lauf, 'namensvettern-03')
    innen, aussen = {'namensvettern-005', 'namensvettern-007'}, {'namensvettern-006', 'namensvettern-008'}
    assert innen <= set(f.abruf.kandidaten) and aussen <= set(f.abruf.kandidaten), 'Nichts wird entfernt'
    assert set(f.abruf.gekennzeichnet_nach_art['ausserhalb_zeitraum']) >= aussen
    assert not innen & set(f.abruf.gekennzeichnet), 'Der Termin vom 25.9. liegt in der Woche, auch wenn er im August angelegt wurde'
    assert f.abruf_bewertung.verboten_ungekennzeichnet == () and f.abruf_bewertung.fehlend == ()


def test_die_gesamtkennzahl_der_mini_welt_hat_keine_neue_rueckfrage_und_keinen_verlorenen_beleg(lauf):
    z = lauf.abruf_gesamt
    assert z.unnoetige_rueckfragen == 0
    assert all(not f.abruf_bewertung.fehlend for f in lauf.fragen if f.frage.id.startswith('namensvettern-')), \
        'Die Kennzeichnung verliert keinen erwarteten Beleg'
    assert z.verbotene_belege_gekennzeichnet.get('andere_person', 0) >= 2
    assert z.verbotene_belege_gekennzeichnet.get('ausserhalb_zeitraum', 0) >= 2


# -- 4. Der Bericht -----------------------------------------------------------------------------------------------------


def test_der_bericht_fuehrt_die_arten_getrennt_in_kennzahl_und_fehlerliste(lauf):
    text = bericht.markdown(lauf)
    assert 'gekennzeichnet nach Art' in text and 'andere Person ' in text and 'außerhalb des Zeitraums ' in text
    assert 'weder als überholt noch als andere Person noch als außerhalb des Zeitraums' in text
    zeile = next(z for z in text.splitlines() if 'namensvettern-003' in z and 'verbotene Belege im Kontext' in z)
    assert 'ungekennzeichnet: keiner' in zeile and 'andere Person: namensvettern-003, namensvettern-004' in zeile
    zeile = next(z for z in text.splitlines() if 'namensvettern-006' in z and 'verbotene Belege im Kontext' in z)
    assert 'außerhalb des Zeitraums: ' in zeile


def test_das_json_traegt_die_arten(lauf, tmp_path):
    json_pfad, _ = bericht.schreibe(lauf, tmp_path)
    daten = json.loads(json_pfad.read_text(encoding='utf-8'))
    assert daten['abruf']['gesamt']['verbotene_belege_gekennzeichnet']['andere_person'] >= 2
    erste = next(f for f in daten['fragen'] if f['frage']['id'] == 'namensvettern-01')
    assert 'andere_person' in erste['abruf']['gekennzeichnet_nach_art']
    assert 'andere_person' in erste['abruf_bewertung']['verboten_gekennzeichnet']
