"""Satzprüfung mit Kennzeichnung: Ein Satz nur aus Quellen eines Namensvetters oder außerhalb des Zeitraums besteht nicht."""
from datetime import datetime, timezone

from icarus_memory import kennzeichnung, personenfrage, satzantwort, working_memory_answers as wma
from icarus_memory.kennzeichnung import ANDERE_PERSON, AUSSERHALB, Kennzeichen
from icarus_memory.satzantwort import AntwortBeleg, pruefe_satz
from icarus_memory.satzpruefung import Satz
from tests.test_bezuege import ICH, welt  # noqa: F401 - Fixture
from tests.test_kennzeichnung import (A_CATERING, A_INSTITUT, FRAGE_CATERING, fragen_und_antworten,  # noqa: F401
                                      winter_mails)
from tests.test_satzantwort import Skript, nr, raum  # noqa: F401 - Fixture und Hilfen



def antwort_mit_saetzen(raum, saetze, *, auswahl=None, literal=False, **weiter):
    episodes, _, _ = raum
    winter_mails(episodes, feedback=('Alex Winter bittet bis zum 16. Oktober um Feedback.'
                                    if literal else None))
    vettern = personenfrage.gemeinte_unter_namensvettern(FRAGE_CATERING, episodes, eigene=[ICH])
    modell = Skript(saetze=saetze, auswahl=auswahl)
    return fragen_und_antworten(raum, modell, FRAGE_CATERING, namensvettern=vettern, **weiter), modell


def satz_nur_institut(text):
    return lambda n: {'status': 'antwort', 'saetze': [{'text': text, 'belege': [nr(n, 'Feedback')]}]}


def nur_titel(*titel):
    # Satzregeln prüfen die ausdrücklich ausgewählten Belege. Weitere Quellen
    # dürfen als Kontext vorhanden sein, aber nicht unbemerkt ausgewählt fehlen.
    return lambda n: [q['id'] for q in n['sources'] if any(t in q['title'] for t in titel)]


def test_ein_satz_nur_aus_der_quelle_des_namensvetters_besteht_nicht(raum):
    antwort, _ = antwort_mit_saetzen(raum, satz_nur_institut('Alex Winter bittet bis zum 16. Oktober um Feedback.'))
    satz = antwort['satzantwort']
    assert satz['status'] == 'zitate' and 'kein Satz bestand' in satz['grund']
    assert any('anderen Person gleichen Namens' in g for g in satz['gruende'])


def test_derselbe_satz_besteht_wenn_er_den_anderen_alex_winter_ausdruecklich_nennt(raum):
    antwort, _ = antwort_mit_saetzen(raum, satz_nur_institut('Ein anderer Alex Winter bittet bis zum 16. Oktober um Feedback.'),
                                    auswahl=nur_titel('Feedback'), literal=True)
    assert antwort['satzantwort']['status'] == 'saetze' and antwort['satzantwort']['verworfen'] == 0


def test_ein_satz_der_auch_die_passende_quelle_nennt_besteht(raum):
    def beide(n):
        return {'status': 'antwort', 'saetze': [{
            'text': 'Der Preis beträgt 38 Euro pro Person; die Bitte um Feedback bis zum 16. Oktober ist eine andere Sache.',
            'belege': [nr(n, 'Preisanpassung'), nr(n, 'Feedback')]}]}
    antwort, _ = antwort_mit_saetzen(raum, beide, auswahl=nur_titel('Preisanpassung', 'Feedback'))
    assert antwort['satzantwort']['status'] == 'saetze'


def test_die_satzanfrage_zeigt_dem_modell_die_kennzeichnung_und_der_beleg_kennt_sie(raum):
    antwort, modell = antwort_mit_saetzen(raum, satz_nur_institut('Ein anderer Alex Winter bittet um Feedback.'))
    belege = modell.satzanfragen[0]['belege']
    institut = next(b for b in belege if 'Feedback' in b['quelle'])
    assert institut['andere_person'][0]['adresse_dieser_person'] == A_INSTITUT
    assert not any('andere_person' in b for b in belege if 'Preisanpassung' in b['quelle'])
    assert 'andere_person' in satzantwort.ANWEISUNG and 'ausserhalb_zeitraum' in satzantwort.ANWEISUNG


def test_benennt_erkennt_nur_den_ausdruecklichen_hinweis():
    vetter = Kennzeichen(ANDERE_PERSON, A_INSTITUT, 'Alex Winter', A_CATERING)
    zeit = Kennzeichen(AUSSERHALB, '2026-03-23', 'der letzten Woche')
    assert kennzeichnung.benennt('Ein anderer Alex Winter bittet um Feedback.', vetter)
    assert kennzeichnung.benennt('Das ist ein Namensvetter.', vetter)
    assert not kennzeichnung.benennt('Alex Winter bittet um Feedback, andere Fragen folgen.', vetter)
    assert kennzeichnung.benennt('Das liegt außerhalb des Zeitraums.', zeit)
    assert kennzeichnung.benennt('Das war nicht im gefragten Zeitraum.', zeit)
    assert not kennzeichnung.benennt('Das war im März.', zeit)


def test_satz_aus_einer_quelle_ausserhalb_des_zeitraums_besteht_nur_mit_ausdruecklichem_hinweis():
    beleg = AntwortBeleg(1, {}, 'Quelle', 'e1', 'Angebot März', 'Angebot März; 23.03.2026',
                         'Das Angebot kostet 35.000 Euro.', None, (),
                         kennzeichen=(Kennzeichen(AUSSERHALB, '2026-03-23', 'der letzten Woche'),))
    jetzt = datetime(2026, 9, 29, tzinfo=timezone.utc)
    ohne = pruefe_satz(Satz('Das Angebot kostet 35.000 Euro.', ('1',)), {'1': beleg}, jetzt)
    assert not ohne.bestanden and 'außerhalb des gefragten Zeitraums' in ohne.gruende[0]
    mit = pruefe_satz(Satz('Außerhalb des Zeitraums kostete das Angebot 35.000 Euro.', ('1',)), {'1': beleg}, jetzt)
    assert mit.bestanden, mit.gruende


def test_gespeicherte_satzantwort_traegt_den_rahmen_und_prueft_beim_anzeigen_erneut(raum):
    episodes, claims, _ = raum
    antwort, _ = antwort_mit_saetzen(raum, satz_nur_institut('Ein anderer Alex Winter bittet bis zum 16. Oktober um Feedback.'),
                                    auswahl=nur_titel('Feedback'), literal=True)
    assert antwort['satzantwort']['rahmen']['personen'][0]['adresse'] == A_CATERING
    assert satzantwort.wiederherstellen(antwort['satzantwort'], episodes, claims) is not None
    # Derselbe Satz ohne den ausdrücklichen Hinweis besteht nach dem Speichern nicht mehr.
    verfaelscht = {**antwort['satzantwort'], 'saetze': [
        {**antwort['satzantwort']['saetze'][0], 'roh': 'Alex Winter bittet bis zum 16. Oktober um Feedback.',
         'text': 'Alex Winter bittet bis zum 16. Oktober um Feedback.'}]}
    assert satzantwort.wiederherstellen(verfaelscht, episodes, claims) is None
    ohne_rahmen = {k: v for k, v in antwort['satzantwort'].items() if k != 'rahmen'}
    assert satzantwort.wiederherstellen({**ohne_rahmen, 'rahmen': {'version': 3}}, episodes, claims) is None


def test_die_worte_des_hinweises_gelten_der_satzpruefung_nicht_als_erfundene_namen():
    """„Außerhalb“, „Zeitraums“ und „Namensvetter“ sind Großgeschriebenes, aber keine Namen, die im Beleg stehen müssten."""
    jetzt = datetime(2026, 9, 29, tzinfo=timezone.utc)
    vetter = AntwortBeleg(1, {}, 'Quelle', 'e1', 'Fragebogen', 'Fragebogen', 'Alex Winter bittet um Feedback.', None, (),
                          kennzeichen=(Kennzeichen(ANDERE_PERSON, A_INSTITUT, 'Alex Winter', A_CATERING),))
    zeit = AntwortBeleg(1, {}, 'Quelle', 'e2', 'Angebot', 'Angebot', 'Das Angebot kostet 35.000 Euro.', None, (),
                        kennzeichen=(Kennzeichen(AUSSERHALB, '2026-03-23', 'der letzten Woche'),))
    assert pruefe_satz(Satz('Das ist ein Namensvetter: Alex Winter bittet um Feedback.', ('1',)), {'1': vetter}, jetzt).bestanden
    assert pruefe_satz(Satz('Außerhalb des Zeitraums kostete das Angebot 35.000 Euro.', ('1',)), {'1': zeit}, jetzt).bestanden
    assert not pruefe_satz(Satz('Das Angebot kostet 35.000 Euro.', ('1',)), {'1': zeit}, jetzt).bestanden


def test_namensvetter_hinweis_belegt_keine_akteursrolle_aus_einer_bitte(raum):
    answer, _ = antwort_mit_saetzen(raum, satz_nur_institut(
        'Ein anderer Alex Winter bittet bis zum 16. Oktober um Feedback.'),
        auswahl=nur_titel('Feedback'))
    episodes, claims, _ = raum
    assert answer['satzantwort']['status'] == 'zitate'
    text, links, status = wma.render(answer, episodes, claims)
    assert status == 'working_reports' and links
    assert 'Bitte geben Sie mir bis zum 16. Oktober Feedback, Alex Winter.' in text
    assert 'Ein anderer Alex Winter bittet' not in text


def test_fehlender_identitaetshinweis_bleibt_bei_wortlautbeleg_verboten():
    marke = Kennzeichen(ANDERE_PERSON, A_INSTITUT, 'Alex Winter', A_CATERING)
    text = 'Alex Winter bittet um Feedback.'
    beleg = AntwortBeleg(1, {}, 'Quelle', 'e1', '', '', text, None,
                         kennzeichen=(marke,), personen=('Alex Winter',))
    jetzt = datetime(2026, 9, 29, tzinfo=timezone.utc)
    result = pruefe_satz(Satz(text, ('1',)), {'1': beleg}, jetzt)
    assert not result.bestanden
    assert any('anderen Person gleichen Namens' in g for g in result.gruende)
    annotated = 'Ein anderer ' + text
    assert pruefe_satz(Satz(annotated, ('1',)), {'1': beleg}, jetzt).bestanden
    swapped = 'Ein anderer Alex Winter gibt Feedback.'
    assert not pruefe_satz(Satz(swapped, ('1',)), {'1': beleg}, jetzt).bestanden


def test_wortgetreue_quelle_mit_eigenem_identitaetsrahmen_bleibt_gueltig():
    text = 'Ein anderer Alex Winter bittet um Feedback.'
    beleg = AntwortBeleg(1, {}, 'Quelle', 'e1', '', '', text, None,
                         kennzeichen=(Kennzeichen(ANDERE_PERSON, A_INSTITUT, 'Alex Winter', A_CATERING),),
                         personen=('Alex Winter',))
    jetzt = datetime(2026, 9, 29, tzinfo=timezone.utc)
    assert pruefe_satz(Satz(text, ('1',)), {'1': beleg}, jetzt).bestanden
