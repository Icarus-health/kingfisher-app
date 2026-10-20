"""Deutsche Fristformulierungen: was gebunden wird, was Text bleibt und was nie eine Frist ist.

Alle Sätze sind erfunden. Bezug ist Donnerstag, 3. September 2026. Eine falsche Frist ist schlimmer als
keine: Jede neue Form hat Gegenbeispiele, die gleich aussehen und keine Frist sind.
"""
from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from icarus_memory import akten as akten_modul
from icarus_memory.fristen import fristangaben_in, fristen_in
from tests.test_akten import akten, neu_rechnen  # noqa: F401
from tests.test_bezuege import welt  # noqa: F401
from tests.test_date_roles import PERSON, source

BEZUG = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)


def _gebunden(text):
    suche = fristangaben_in(text, BEZUG)
    return [f.datum.isoformat() for f in suche.fristen], len(suche.ohne_datum)


@pytest.mark.parametrize('text,tage', [
    # Binnenfristen zählen ab der Quelle wie „in 14 Tagen“.
    ('Bitte überweisen Sie den Betrag innerhalb von 14 Tagen.', ['2026-09-17']),
    ('Zahlbar innerhalb von 14 Tagen ohne Abzug.', ['2026-09-17']),
    ('Bitte zahlen Sie binnen zwei Wochen.', ['2026-09-17']),
    ('Bitte antworten Sie innerhalb einer Woche.', ['2026-09-10']),
    ('Bitte reichen Sie die Belege innerhalb eines Monats ein.', ['2026-10-03']),
    ('Das Seminar findet am 25.09. statt; Anmeldung innerhalb von zwei Wochen.', ['2026-09-17']),
    ('Ich liefere den Entwurf in drei Wochen.', ['2026-09-24']),
    # Zahlung
    ('Zahlbar bis 30.09.2026.', ['2026-09-30']),
    ('Zahlungsziel: 30.09.2026', ['2026-09-30']),
    ('Bitte begleichen Sie die Rechnung bis zum 30.09.', ['2026-09-30']),
    ('Der Betrag ist bis zum 30.09. zu überweisen.', ['2026-09-30']),
    ('Die Zahlung muss bis zum 30.09. bei uns eingegangen sein.', ['2026-09-30']),
    ('Wir bitten um Überweisung bis einschließlich 30.09.', ['2026-09-30']),
    # Unterlagen und Formulare, auch mit abgetrennter Vorsilbe
    ('Bitte unterschreiben Sie den Vertrag bis zum 18.09.', ['2026-09-18']),
    ('Bitte füllen Sie den Fragebogen bis Freitag aus.', ['2026-09-04']),
    ('Bitte füllen Sie den Fragebogen bis Freitag vollständig aus.', ['2026-09-04']),
    ('Bitte laden Sie die Dokumente bis zum 18.09. hoch.', ['2026-09-18']),
    ('Bitte geben Sie die Hausarbeit bis Freitag ab.', ['2026-09-04']),
    ('Wer mitspielen will, trägt sich bis morgen in die Liste ein.', ['2026-09-04']),
    ('Die Unterlagen müssen bis zum 18.09. beim Finanzamt eingegangen sein.', ['2026-09-18']),
    ('Das Attest muss uns in zwei Monaten vorliegen.', ['2026-11-03']),
    ('Wir benötigen die Unterlagen bis spätestens 18.09.', ['2026-09-18']),
    ('Ihre Stellungnahme benötigen wir bis zum 18.09.', ['2026-09-18']),
    ('Abgabe der Hausarbeit bis 18.09.', ['2026-09-18']),
    ('Die Steuererklärung ist bis zum 31. Juli 2027 abzugeben.', ['2027-07-31']),
    ('Wir bitten Sie, die Unterlagen bis zum 18.09. nachzureichen.', ['2026-09-18']),
    ('Wir sagen Ihnen zu, die Fenster bis zum 2. Oktober 2026 einzubauen.', ['2026-10-02']),
    ('Ihre Bestellung wird bis spätestens 10.9. geliefert.', ['2026-09-10']),
    # Antworten
    ('Bitte geben Sie uns bis Freitag Bescheid.', ['2026-09-04']),
    ('Bitte gebt bis Freitag Bescheid.', ['2026-09-04']),
    ('Bitte teilen Sie uns bis zum 18.09. mit, ob Sie teilnehmen.', ['2026-09-18']),
    ('Bitte entscheiden Sie bis zum 18.09., welche Variante wir nehmen.', ['2026-09-18']),
    ('Die Zustimmung erbitte ich bis zum 18.09.', ['2026-09-18']),
    # Kündigung, Widerruf, Anmeldung
    ('Die Kündigung muss bis zum 30.09. vorliegen.', ['2026-09-30']),
    ('Ein Widerruf ist bis zum 17.09. möglich.', ['2026-09-17']),
    ('Sie können den Vertrag bis zum 30.09. schriftlich kündigen.', ['2026-09-30']),
    ('Bis zum 30.09. können Sie kündigen.', ['2026-09-30']),
    ('Letzter Anmeldetag ist der 18.09.', ['2026-09-18']),
    ('Anmeldeschluss für den Workshop am 10. Oktober ist der 25.09.2026.', ['2026-09-25']),
    ('Räumen Sie den Flur bitte bis Montag frei.', ['2026-09-07']),
    # Zwei verbundene Fristen
    ('Ich liefere den Entwurf in drei Wochen und die Endfassung bis zum 30. Oktober 2026.',
     ['2026-09-24', '2026-10-30']),
    ('Bitte senden Sie den Antrag bis zum 18.09. und die Belege bis zum 25.09.', ['2026-09-18', '2026-09-25']),
])
def test_deadline_wording_is_bound_to_its_calendar_day(text, tage):
    assert _gebunden(text) == (tage, 0)


@pytest.mark.parametrize('text', [
    # Ein anderes Ereignis als die Quelle oder Werktage: Frist ja, Kalendertag nein.
    'Der Rechnungsbetrag ist innerhalb von 30 Tagen nach Rechnungsdatum fällig.',
    'Bitte überweisen Sie den Betrag innerhalb von 10 Werktagen.',
    'Innerhalb von 14 Tagen nach Erhalt der Ware können Sie widerrufen.',
    'Sie können innerhalb von 14 Tagen ab Erhalt der Ware ohne Angabe von Gründen widerrufen.',
    'Bitte sagen Sie den Termin spätestens 24 Stunden vorher ab.',
    'Die Gebühr ist spätestens zwei Wochen vor Beginn der Tagung zu überweisen.',
    'Den Anamnesebogen benötigen wir spätestens drei Werktage vor Ihrem Termin.',
    'Bitte reichen Sie die Belege bis Ende September ein.',
    'Ihre Stellungnahme benötigen wir bis nächste Woche.',
    'Bitte gebt bis nächsten Freitag Bescheid.',
])
def test_deadline_without_a_certain_day_stays_verbatim(text):
    assert _gebunden(text) == ([], 1)


@pytest.mark.parametrize('text', [
    'Das Büro ist bis zum 18.09. geschlossen.',
    'Bitte beachten Sie: Die Praxis bleibt bis 18.09. geschlossen.',
    'Das Angebot ist bis zum 30.09. gültig.',
    'Unser Angebot gilt nur bis Freitag, den 11. September.',
    'Die Preise gelten bis 30.09.2026.',
    'Bitte prüfen Sie die bis zum 30.09. gültigen Preise.',
    'Das Formular ist bis zum 30.09. online verfügbar.',
    'Die Anmeldung ist bis zum 18.09. geöffnet.',
    'Der Betrag wird am 18.09. abgebucht.',
    'Wir buchen den Betrag am 18.09. ab.',
    'Wir haben innerhalb von 14 Tagen geliefert.',
    'Wir haben die Unterlagen innerhalb von 14 Tagen geprüft.',
    'Ihre Unterlagen sind bis zum 18.09. bei uns eingegangen.',
    'Die Bescheinigung haben wir bis zum 18.09. erhalten.',
    'Die Ware wurde bis zum 10.9. geliefert.',
    'Bis heute ist keine Zahlung eingegangen.',
    'Bis heute haben wir keine Zahlung erhalten.',
    'Bis Freitag haben wir die Rechnung bezahlt.',
    'In zwei Wochen beginnt die Anmeldung.',
    'Ich bin in zwei Wochen zurück.',
    'Ich bin innerhalb von zwei Wochen zurück.',
    'Die Tagung ist in drei Wochen.',
    'Bitte rufen Sie mich nicht vor Montag an.',
    'Wir bitten Sie, das Büro bis zum 18.09. nicht zu betreten.',
    'Es ist geplant, die Ausstellung bis zum 18.09. zu zeigen.',
    'Ich bin bis Freitag, den 11. September, im Urlaub.',
    'Bitte senden Sie die Rechnung an die Adresse, die bis zum 30.09. gilt.',
    'Vor 14 Tagen haben wir Ihnen geschrieben.',
    'Die Lieferzeit beträgt innerhalb Deutschlands zwei Wochen.',
    'Wir brauchen das Auto bis zum 18.09.',
])
def test_lookalikes_are_never_deadlines(text):
    assert _gebunden(text) == ([], 0)


@pytest.mark.parametrize('text,datum', [
    ('Bitte bis Freitag, den 11. September, zurückmelden.', '2026-09-11'),
    ('Antwort bitte bis Mittwoch, 9.9.', '2026-09-09'),
    ('Schicken Sie das Formular bitte bis Montag, den 14. September 2026, zurück.', '2026-09-14'),
])
def test_weekday_with_date_takes_the_date_not_the_next_weekday(text, datum):
    # Früher wurde aus „bis Montag, den 14. September“ der nächste Montag (7.9.).
    assert _gebunden(text) == ([datum], 0)


def test_weekday_that_contradicts_its_date_gives_no_day():
    # Der 17. September 2026 ist ein Donnerstag, kein Dienstag.
    text = 'Bitte reichen Sie den Nachweis bis Dienstag, den 17. September, ein.'
    assert _gebunden(text) == ([], 1)
    suche = fristen_in(text, BEZUG)
    assert suche.fristen == [] and suche.ohne_datum == ['bis Dienstag, den 17. September']


@pytest.mark.parametrize('text,erwartet', [
    ('innerhalb von 14 Tagen', date(2026, 9, 17)),
    ('innerhalb von 14 Kalendertagen', date(2026, 9, 17)),
    ('binnen zwei Wochen', date(2026, 9, 17)),
    ('innerhalb eines Monats', date(2026, 10, 3)),
    ('innerhalb einer Woche', date(2026, 9, 10)),
])
def test_broad_api_resolves_periods_from_the_source(text, erwartet):
    suche = fristen_in(text, BEZUG)
    assert [(f.datum, f.art, f.ausdruck) for f in suche.fristen] == [(erwartet, 'relativ', text)]


@pytest.mark.parametrize('text', [
    'innerhalb von 10 Werktagen', 'binnen drei Arbeitstagen', 'innerhalb von 14 Tagen nach Erhalt der Ware',
    'innerhalb von 30 Tagen ab Rechnungsdatum', 'innerhalb von zwei bis drei Wochen',
    'spätestens drei Werktage vor Ihrem Termin', 'eine Woche vorher',
])
def test_broad_api_keeps_anchored_or_business_day_periods_as_text(text):
    suche = fristen_in(text, BEZUG)
    assert suche.fristen == [] and suche.ohne_datum == [text]


def test_without_source_date_periods_stay_text():
    assert fristen_in('innerhalb von 14 Tagen', None).ohne_datum == ['innerhalb von 14 Tagen']


def test_person_profile_shows_a_payment_period_as_a_deadline(welt, akten):
    # Ende zu Ende: aus der Mail wird eine kommende Frist in der Akte, die Quelle bleibt unverändert.
    episodes = welt[0]
    text = 'Bitte überweisen Sie den Betrag innerhalb von 14 Tagen.'
    episode = source(episodes, text, reference=BEZUG)
    original = deepcopy(episodes.get(episode.id).to_dict())
    profile = neu_rechnen(akten).akte(PERSON, jetzt=BEZUG)
    assert [item['datum'] for item in profile['fristen']['kommend']] == ['2026-09-17']
    assert profile['fristen']['kommend'][0]['ausdruck'] == 'innerhalb von 14 Tagen'
    assert episodes.get(episode.id).to_dict() == original


def test_cached_profile_from_the_old_rules_is_recomputed(welt, akten, monkeypatch):
    # Eine Akte aus Fassung 1.0.25 kannte „innerhalb von 14 Tagen“ nicht. Nach dem Update gilt die neue Regel.
    source(welt[0], 'Bitte überweisen Sie den Betrag innerhalb von 14 Tagen.', reference=BEZUG)
    akten.bezuege.aktualisieren()
    quellen = akten.bezuege.quellen_von(PERSON)
    with monkeypatch.context() as alt:
        alt.setattr(akten_modul, 'AKTEN_VERSION', 9)
        roh = akten.roh(PERSON, quellen)
        roh['fristen'] = []
        akten._speichern(PERSON, akten._eingabe(PERSON, quellen), roh)
    profile = akten.akte(PERSON, jetzt=BEZUG)
    assert [item['datum'] for item in profile['fristen']['kommend']] == ['2026-09-17']
    assert not profile['aus_zwischenspeicher']


def test_person_profile_ignores_a_closing_period(welt, akten):
    source(welt[0], 'Bitte beachten Sie: Die Praxis bleibt bis 18.09. geschlossen.', reference=BEZUG)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=BEZUG)
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
