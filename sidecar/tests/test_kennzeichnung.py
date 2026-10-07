"""Namensvettern und Zeiträume im Antwortkontext kennzeichnen (Nachtrag zu E2): nichts wird entfernt.

Zusicherungen (Sabotageproben in `docs/39-kennzeichnung.md`):

1. Eine Quelle mit der Adresse eines Namensvetters, aber nicht der gemeinten Person, trägt `andere_person`;
   ein bloßer Name ohne Adresse, eine Quelle mit beiden Adressen und eine Frage ohne Entscheidung kennzeichnen nichts.
2. Ein Termin liegt nach seinem Beginn im Zeitraum, eine Mail nach ihrem Datum; außerhalb trägt `ausserhalb_zeitraum`.
3. Das Modell der Auswahl sieht die Felder und die Anweisung dazu, die Zeilen stehen hinter den passenden.
4. Der Rahmen wird gespeichert und geprüft (ungültig heißt veraltet); der Zitatmodus sagt es in der Überschrift.

Kalenderzeitraum: `test_kalenderzeitraum.py`; Sätze: `test_kennzeichnung_saetze.py`.
"""
from datetime import datetime, timezone

import pytest

from icarus_memory import EpisodeKind, kennzeichnung, personenfrage, satzantwort, working_memory_answers as wma
from icarus_memory.kennzeichnung import ANDERE_PERSON, AUSSERHALB, Gemeint, Kennzeichen, Rahmen, Zeitraum
from icarus_memory.providers import ProviderError
from tests.test_akten import mail
from tests.test_bezuege import ICH, JETZT, quelle, welt  # noqa: F401 - Fixture und Hilfen
from tests.test_satzantwort import DIENSTAG, Skript, nr, raum  # noqa: F401 - Fixture und Hilfen

CATERING = 'Alex Winter <alex.winter@winter-catering.example>'
INSTITUT = 'Alex Winter <alex.winter@ifeh-hessen.example>'
A_CATERING, A_INSTITUT = 'alex.winter@winter-catering.example', 'alex.winter@ifeh-hessen.example'
FRAGE_CATERING = 'Was kostet das Catering von Alex Winter pro Person?'


# -- 1. Andere Person ------------------------------------------------------------------------------------------


@pytest.fixture
def winter(welt):
    episodes, _, _ = welt
    return {
        'catering': quelle(episodes, 'Preisanpassung', '38 Euro pro Person.', [CATERING, ICH], tage=5),
        'institut': quelle(episodes, 'Bitte um Feedback zum Fragebogen', 'Feedback bis 16. Oktober.', [INSTITUT, ICH], tage=4),
        'beide': quelle(episodes, 'Gruppenmail', 'Beide Alex Winter im Verteiler.', [CATERING, INSTITUT, ICH], tage=3),
        'nur_name': quelle(episodes, 'Notiz', 'Alex Winter hat angerufen.', ['Alex Winter'], tage=2),
    }


def rahmen_fuer(episodes, frage, zeitraum=None):
    gemeinte = personenfrage.gemeinte_unter_namensvettern(frage, episodes, eigene=[ICH])
    return kennzeichnung.rahmen_der_frage(gemeinte, zeitraum)


def test_die_frage_entscheidet_fuer_eine_person_und_der_andere_wird_zum_namensvetter(welt, winter):
    episodes, _, _ = welt
    rahmen = rahmen_fuer(episodes, FRAGE_CATERING)
    assert rahmen.personen == (Gemeint('Alex Winter', A_CATERING, (A_INSTITUT,)),)
    marken = kennzeichnung.kennzeichen(winter['institut'], rahmen)
    assert marken == (Kennzeichen(ANDERE_PERSON, A_INSTITUT, 'Alex Winter', A_CATERING),)
    assert kennzeichnung.kennzeichen(winter['catering'], rahmen) == ()


def test_eine_quelle_mit_beiden_adressen_und_ein_bloszer_name_sind_nicht_eindeutig_fremd(welt, winter):
    episodes, _, _ = welt
    rahmen = rahmen_fuer(episodes, FRAGE_CATERING)
    assert kennzeichnung.kennzeichen(winter['beide'], rahmen) == ()
    assert kennzeichnung.kennzeichen(winter['nur_name'], rahmen) == (), 'Ein Name ohne Adresse beweist nichts'


def test_ohne_entscheidung_der_frage_gibt_es_keine_namensvettern_die_rueckfrage_bleibt(welt, winter):
    episodes, _, _ = welt
    assert personenfrage.gemeinte_unter_namensvettern('Was ist mit Alex Winter?', episodes, eigene=[ICH]) == []
    assert personenfrage.unklare_person('Was ist mit Alex Winter?', episodes, eigene=[ICH]) is not None
    rahmen = rahmen_fuer(episodes, 'Was ist mit Alex Winter?')
    assert rahmen.leer() and kennzeichnung.kennzeichen(winter['institut'], rahmen) == ()


def test_wer_nacheinander_die_adresse_wechselt_ist_kein_namensvetter(welt):
    episodes, _, _ = welt
    quelle(episodes, 'Früher', 'Alt.', ['Jasmin Krüger <j.krueger@alt.example>', ICH], tage=400)
    quelle(episodes, 'Jetzt', 'Neu, Kassel.', ['Jasmin Krüger <j.krueger@neu-kassel.example>', ICH], tage=5)
    assert personenfrage.gemeinte_unter_namensvettern('Wo arbeitet Jasmin Krüger in Kassel?', episodes, eigene=[ICH]) == []


def test_die_namen_werden_fuer_quellen_und_namensvettern_nur_einmal_nachgeschlagen(welt, winter, monkeypatch):
    """Das Nachschlagen durchsucht die Beteiligten des ganzen Bestands (bei 10.000 Quellen spürbar): einmal je Frage."""
    from types import SimpleNamespace

    from icarus_memory.agent import Agent
    episodes, _, _ = welt
    aufrufe = []
    echt = personenfrage.erwaehnte
    monkeypatch.setattr(personenfrage, 'erwaehnte', lambda *a, **k: aufrufe.append(1) or echt(*a, **k))
    agent = SimpleNamespace(_episodes=episodes, _own_addresses=lambda: [ICH])
    quellen, vettern = Agent._personen_der_frage(agent, FRAGE_CATERING)
    assert len(aufrufe) == 1
    assert quellen and [(erwaehnung.begriff, gemeint.adresse) for erwaehnung, gemeint, _ in vettern] == [
        ('Alex Winter', A_CATERING)]
    # Dasselbe Ergebnis wie beim getrennten Aufruf.
    assert quellen == personenfrage.kandidatenquellen(FRAGE_CATERING, episodes, eigene=[ICH])


# -- 2. Zeitraum -----------------------------------------------------------------------------------------------


LETZTE_WOCHE = Zeitraum(datetime(2026, 9, 21, tzinfo=timezone.utc), datetime(2026, 9, 28, tzinfo=timezone.utc),
                        'der letzten Woche')


def test_eine_mail_zaehlt_nach_ihrem_datum_ein_termin_nach_seinem_beginn(welt):
    episodes, _, _ = welt
    innen = quelle(episodes, 'Mail innen', 'Text innen.', [ICH], tage=5)                      # 24.09.
    aussen = quelle(episodes, 'Mail außen', 'Text außen.', [ICH], tage=40)                    # 20.08.
    # Der Termin wurde spät eingetragen, beginnt aber vor drei Tagen: Sein Beginn (occurred_at) entscheidet.
    termin = quelle(episodes, 'Termin', 'Ort: Büro', [ICH], art=EpisodeKind.EVENT, tage=3)
    rahmen = Rahmen(zeitraum=LETZTE_WOCHE)
    assert kennzeichnung.kennzeichen(innen, rahmen) == ()
    assert kennzeichnung.kennzeichen(termin, rahmen) == ()
    assert kennzeichnung.kennzeichen(aussen, rahmen) == (
        Kennzeichen(AUSSERHALB, '2026-08-20', 'der letzten Woche'),)
    spaeter = quelle(episodes, 'Mail zu spät', 'Text zu spät.', [ICH], tage=0)                  # 29.09. liegt nach dem Zeitraum
    assert kennzeichnung.kennzeichen(spaeter, rahmen)[0].art == AUSSERHALB


def test_der_rahmen_wird_gespeichert_und_ungueltiges_gilt_nicht():
    rahmen = Rahmen((Gemeint('Alex Winter', A_CATERING, (A_INSTITUT,)),), LETZTE_WOCHE)
    assert Rahmen.aus_dict(rahmen.als_dict()) == rahmen
    assert Rahmen.aus_dict(kennzeichnung.LEER.als_dict()) == kennzeichnung.LEER
    for aendern in (lambda d: d.update(version=9), lambda d: d['personen'][0].update(andere=[]),
                    lambda d: d['zeitraum'].update(von='gestern'), lambda d: d['zeitraum'].update(bis=d['zeitraum']['von']),
                    lambda d: d.update(unbekannt=1)):
        d = Rahmen(rahmen.personen, rahmen.zeitraum).als_dict()
        aendern(d)
        assert Rahmen.aus_dict(d) is None
    assert Rahmen.aus_dict(None) is None


@pytest.mark.parametrize('captured', [datetime(2026, 9, 24, tzinfo=timezone.utc),
                                    datetime(2026, 10, 7, tzinfo=timezone.utc)])
def test_undated_source_is_not_assigned_inside_or_outside_period_from_import(welt, captured):
    from icarus_memory.model import Provenance, SourceType
    episodes, _, _ = welt
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Undated original',
                                 'Orion: Die Freigabe ist offen.', Provenance(SourceType.DOCUMENT), at=captured)
    assert kennzeichnung.kennzeichen(episode, Rahmen(zeitraum=LETZTE_WOCHE)) == ()


# -- 3. Kontext des Modells ----------------------------------------------------------------------------------------


def fragen_und_antworten(raum, modell, frage, *, namensvettern=(), person_ids=(), **weiter):
    episodes, claims, akten = raum
    akten.bezuege.aktualisieren()
    return wma.prepare(frage, episodes, claims, modell, saetze=True, namensvettern=namensvettern, person_ids=person_ids, **weiter)


def winter_mails(episodes):
    """Beide Personen mit je zwei Mails, zeitlich überlappend (sonst wirkten die Adressen wie ein Wechsel)."""
    mail(episodes, 'Angebot Verpflegung', [('Der Preis betrug 34 Euro pro Person netto.', 'fact')], tage=60,
         absender=CATERING, weitere=(ICH,))
    catering = mail(episodes, 'Preisanpassung', [('Der Preis beträgt 38 Euro pro Person netto.', 'fact')], tage=5,
                    absender=CATERING, weitere=(ICH,))
    mail(episodes, 'Interview Studie', [('Vielen Dank für das Interview, Alex Winter.', 'fact')], tage=30,
         absender=INSTITUT, weitere=(ICH,))
    institut = mail(episodes, 'Bitte um Feedback zum Fragebogen',
                    [('Bitte geben Sie mir bis zum 16. Oktober Feedback, Alex Winter.', 'request')], tage=4,
                    absender=INSTITUT, weitere=(ICH,))
    return catering, institut


def test_das_modell_sieht_andere_person_und_die_zeile_steht_hinten_nichts_faellt_weg(raum):
    episodes, _, _ = raum
    catering, institut = winter_mails(episodes)
    vettern = personenfrage.gemeinte_unter_namensvettern(FRAGE_CATERING, episodes, eigene=[ICH])
    modell = Skript(auswahl=lambda nutzer: [q['id'] for q in nutzer['sources']])
    fragen_und_antworten(raum, modell, FRAGE_CATERING, namensvettern=vettern)
    zeilen = modell.auswahlen[0]['sources']
    titel = [z['title'] for z in zeilen]
    assert set(titel) == {'Angebot Verpflegung', 'Preisanpassung', 'Interview Studie', 'Bitte um Feedback zum Fragebogen'}
    gekennzeichnet = [bool(z.get('andere_person')) for z in zeilen]
    assert gekennzeichnet == sorted(gekennzeichnet), 'Die gekennzeichneten Zeilen stehen alle hinter den passenden'
    assert {z['title'] for z in zeilen if z.get('andere_person')} == {'Interview Studie', 'Bitte um Feedback zum Fragebogen'}
    feedback = next(z for z in zeilen if z['title'].startswith('Bitte um Feedback'))
    assert feedback['andere_person'] == [
        {'name': 'Alex Winter', 'adresse_dieser_person': A_INSTITUT, 'gemeinte_adresse': A_CATERING}]


def test_ohne_namensvettern_und_zeitraum_bleibt_der_kontext_unveraendert(raum):
    episodes, _, _ = raum
    winter_mails(episodes)
    modell = Skript()
    antwort = fragen_und_antworten(raum, modell, FRAGE_CATERING)
    assert all('andere_person' not in z and 'ausserhalb_zeitraum' not in z for z in modell.auswahlen[0]['sources'])
    assert 'kennzeichnung' not in antwort


def test_der_kontext_nennt_den_zeitraum_und_das_datum_der_quelle_ausserhalb(raum, monkeypatch):
    episodes, _, _ = raum
    monkeypatch.setattr('icarus_memory.time_scope.datetime',
                        type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: DIENSTAG)}))
    alt = mail(episodes, 'Angebot März', [('Das Angebot Rheingau kostet 35.000 Euro.', 'fact')], tage=190)
    neu = mail(episodes, 'Referenzen Rheingau', [('Die Referenzen für Rheingau sind versandt.', 'fact')], tage=5)
    modell = Skript()
    antwort = fragen_und_antworten(raum, modell, 'Was lief letzte Woche mit dem Angebot Rheingau?')
    zeilen = {z['title']: z for z in modell.auswahlen[0]['sources']}
    assert 'ausserhalb_zeitraum' not in zeilen['Referenzen Rheingau']
    assert zeilen['Angebot März']['ausserhalb_zeitraum'] == {'datum_der_quelle': '2026-03-23', 'gefragter_zeitraum': 'der letzten Woche'}
    assert list(zeilen) == ['Referenzen Rheingau', 'Angebot März']
    assert Rahmen.aus_dict(antwort['kennzeichnung']).zeitraum.beschriftung == 'der letzten Woche'
    assert {r['episode_id'] for r in antwort['basis']} == {alt.id, neu.id}, 'Nichts wird entfernt'


def test_im_rueckblick_auf_das_fruehjahr_rutscht_die_neuere_quelle_hinter_die_passende(raum, monkeypatch):
    """Die Suche stellt die neuere Mail voran; die Kennzeichnung setzt sie hinter die aus dem Frühjahr (nichts fällt weg)."""
    episodes, _, _ = raum
    monkeypatch.setattr('icarus_memory.time_scope.datetime',
                        type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: DIENSTAG)}))
    april = mail(episodes, 'Angebot April', [('Das Angebot Rheingau kostet 35.000 Euro.', 'fact')], tage=170)
    september = mail(episodes, 'Nachfrage September', [('Zum Angebot Rheingau gibt es eine Nachfrage.', 'fact')], tage=5)
    modell = Skript()
    antwort = fragen_und_antworten(raum, modell, 'Was ist im Frühjahr mit dem Angebot Rheingau passiert?')
    assert [r['episode_id'] for r in antwort['basis']] == [september.id, april.id], 'Die Suche hat die neuere Mail vorn'
    zeilen = modell.auswahlen[0]['sources']
    assert [z['title'] for z in zeilen] == ['Angebot April', 'Nachfrage September']
    assert [bool(z.get('ausserhalb_zeitraum')) for z in zeilen] == [False, True]
    assert zeilen[1]['ausserhalb_zeitraum']['gefragter_zeitraum'] == 'im Frühjahr 2026'


class MitAnweisung(Skript):
    """Merkt sich die Systemnachricht der Auswahl."""

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        if not satzantwort.ist_satzanfrage(messages):
            self.anweisung = messages[0]['content']
        return super().complete_json(messages, max_tokens=max_tokens, schema=schema)


def test_die_auswahl_bekommt_die_anweisung_zu_den_neuen_feldern(raum):
    episodes, _, _ = raum
    winter_mails(episodes)
    modell = MitAnweisung()
    fragen_und_antworten(raum, modell, FRAGE_CATERING)
    assert 'Trägt eine Quelle das Feld andere_person' in modell.anweisung
    assert 'Trägt eine Quelle das Feld ausserhalb_zeitraum' in modell.anweisung


# -- 4. Gespeichert und geprüft ------------------------------------------------------------------------------


def test_ein_ungueltiger_gespeicherter_rahmen_macht_die_antwort_veraltet(raum):
    episodes, claims, _ = raum
    winter_mails(episodes)
    vettern = personenfrage.gemeinte_unter_namensvettern(FRAGE_CATERING, episodes, eigene=[ICH])
    antwort = fragen_und_antworten(raum, Skript(), FRAGE_CATERING, namensvettern=vettern)
    assert wma._fresh(antwort, episodes, claims)
    kaputt = {**antwort, 'kennzeichnung': {**antwort['kennzeichnung'], 'version': 7}}
    assert not wma._fresh(kaputt, episodes, claims)


def test_der_zitatmodus_zeigt_die_andere_person_hinten_und_sagt_es(raum):
    episodes, claims, _ = raum
    catering, institut = winter_mails(episodes)
    vettern = personenfrage.gemeinte_unter_namensvettern(FRAGE_CATERING, episodes, eigene=[ICH])
    modell = Skript(saetze=ProviderError('kein Modell'))
    antwort = fragen_und_antworten(raum, modell, FRAGE_CATERING, namensvettern=vettern)
    text, _, _ = wma.render(antwort, episodes, claims)
    gekennzeichnet = ('Interview Studie', 'Bitte um Feedback zum Fragebogen')
    assert max(text.index('Angebot Verpflegung'), text.index('Preisanpassung')) < min(text.index(t) for t in gekennzeichnet)
    assert 'Andere Person gleichen Namens (Alex Winter, alex.winter@ifeh-hessen.example)' in text
    assert all('andere Person' in text.split(t)[1].splitlines()[0] for t in gekennzeichnet), 'Die Überschrift sagt es'
