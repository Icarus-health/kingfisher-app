"""Zeitmessung einer Antwort: Sammler, Abschnitte im Antwort-Dict, gespeicherte Zahlen, Kennzahlen."""
import copy

import pytest

from icarus_memory import working_memory_answers as wma, zeitmessung
from icarus_memory.zeitmessung import Zeiten
from tests.test_satzantwort import Skript, antwort, nr, raum, stand_wandel, wandel  # noqa: F401 - Fixture und Hilfen
from tests.test_bezuege import welt  # noqa: F401 - Fixture (von `raum` gebraucht)


class Uhr:
    """Eine Uhr, die nur vorgestellt wird."""

    def __init__(self):
        self.jetzt = 100.0

    def __call__(self):
        return self.jetzt

    def weiter(self, sekunden):
        self.jetzt += sekunden


# -- Der Sammler ----------------------------------------------------------------------------------------


def test_abschnitte_summieren_und_gesamt_umfasst_auch_das_ungemessene():
    uhr = Uhr()
    zeiten = Zeiten(uhr)
    with zeiten.abschnitt('suche'):
        uhr.weiter(0.3)
    uhr.weiter(0.5)  # in keinem Abschnitt
    with zeiten.abschnitt('antwort_modell'):
        uhr.weiter(1.25)
    assert zeiten.als_dict() == {'suche': 0.3, 'antwort_modell': 1.25, 'gesamt': 2.05}


def test_ein_abschnitt_ohne_aufruf_fehlt_statt_null_zu_sein():
    zeiten = Zeiten(Uhr())
    assert list(zeiten.als_dict()) == ['gesamt']


def test_derselbe_abschnitt_zweimal_wird_addiert_und_ende_ist_wiederholbar():
    uhr = Uhr()
    zeiten = Zeiten(uhr)
    with zeiten.abschnitt('suche'):
        uhr.weiter(1)
    lauf = zeiten.abschnitt('suche')
    uhr.weiter(2)
    lauf.ende()
    uhr.weiter(5)
    lauf.ende()  # zählt nicht noch einmal
    assert zeiten.als_dict()['suche'] == 3.0


def test_ein_abschnitt_zaehlt_auch_wenn_der_block_mit_einer_ausnahme_endet():
    uhr = Uhr()
    zeiten = Zeiten(uhr)
    with pytest.raises(RuntimeError):
        with zeiten.abschnitt('saetze_modell'):
            uhr.weiter(4)
            raise RuntimeError('Modell weg')
    assert zeiten.als_dict()['saetze_modell'] == 4.0


def test_vorlauf_geht_in_abschnitt_und_gesamt_ein():
    uhr = Uhr()
    zeiten = Zeiten(uhr)
    zeiten.vorlauf('frage', 0.4)
    uhr.weiter(1)
    assert zeiten.als_dict() == {'frage': 0.4, 'gesamt': 1.4}


def test_unbekannte_abschnitte_werden_abgelehnt_und_ohne_sammler_passiert_nichts():
    with pytest.raises(ValueError):
        Zeiten().abschnitt('kaffee')
    with zeitmessung.messen(None, 'suche'):
        pass
    assert zeitmessung.beginne(None, 'suche') is None


def test_jede_antwort_hat_ihren_eigenen_sammler_nichts_wird_geteilt():
    a, b = Zeiten(Uhr()), Zeiten(Uhr())
    with a.abschnitt('suche'):
        pass
    assert 'suche' in a.als_dict() and 'suche' not in b.als_dict()


def test_gespeicherte_zeiten_werden_streng_gelesen():
    gut = {'suche': 0.3, 'gesamt': 2, 'fremd': 9}
    assert zeitmessung.gueltig(gut) == {'suche': 0.3, 'gesamt': 2.0}
    for schlecht in (None, [], {}, {'suche': 1}, {'gesamt': -1}, {'gesamt': 'x'}, {'gesamt': True},
                     {'gesamt': 1, 'suche': float('nan')}, {'gesamt': 1, 'suche': None}, {'gesamt': 10 ** 6}):
        assert zeitmessung.gueltig(schlecht) is None, schlecht


def test_kennzahlen_median_und_90_prozent_wert_je_abschnitt():
    liste = [{'gesamt': float(i), 'suche': 0.1 * i} for i in range(1, 11)] + [{'gesamt': 99.0}]
    kennzahlen = zeitmessung.kennzahlen(liste)
    assert kennzahlen['gesamt'] == {'median': 6.0, 'p90': 10.0, 'anzahl': 11}
    assert kennzahlen['suche']['anzahl'] == 10 and kennzahlen['suche']['median'] == 0.55
    assert 'saetze_modell' not in kennzahlen
    assert zeitmessung.kennzahlen([]) == {}


# -- Im Antwortweg ------------------------------------------------------------------------------------


def test_die_antwort_traegt_die_abschnitte_die_gelaufen_sind(raum):
    episodes, _, _ = raum
    wandel(episodes)
    zeiten = Zeiten()
    episodes_, claims, akten = raum
    akten.bezuege.aktualisieren()
    gespeichert = wma.prepare('Bis wann ist die Einreichfrist?', episodes_, claims, Skript(stand_wandel),
                              saetze=True, zeiten=zeiten)
    assert gespeichert['satzantwort']['status'] == 'saetze'
    daten = zeiten.als_dict()
    assert set(daten) == {'suche', 'antwort_modell', 'saetze_modell', 'satzpruefung', 'gesamt'}
    assert all(wert >= 0 for wert in daten.values())
    assert daten['gesamt'] >= sum(wert for name, wert in daten.items() if name != 'gesamt') - 0.002


def test_ohne_saetze_fehlen_die_abschnitte_des_zweiten_aufrufs(raum):
    episodes, claims, akten = raum
    wandel(episodes)
    akten.bezuege.aktualisieren()
    zeiten = Zeiten()
    wma.prepare('Bis wann ist die Einreichfrist?', episodes, claims, Skript(stand_wandel), saetze=False, zeiten=zeiten)
    assert {'suche', 'antwort_modell'} <= set(zeiten.als_dict())
    assert not {'saetze_modell', 'satzpruefung'} & set(zeiten.als_dict())


def test_die_zeiten_ueberleben_das_anzeigen_und_gelten_nicht_fuer_eine_auswahl_ohne_modell(raum):
    episodes, claims, akten = raum
    wandel(episodes)
    akten.bezuege.aktualisieren()
    zeiten = Zeiten()
    gespeichert = wma.prepare('Bis wann ist die Einreichfrist?', episodes, claims, Skript(stand_wandel),
                              saetze=True, zeiten=zeiten)
    gespeichert['zeiten'] = zeiten.als_dict()
    nachricht = {'role': 'assistant', 'content': wma.NEUTRAL,
                 'metadata': {'context': {'working_answer': copy.deepcopy(gespeichert),
                                          'zeiten': {'gesamt': 999}, 'answer_contract': {}}}}
    angezeigt = wma.project_message(nachricht, episodes, claims)
    assert angezeigt['metadata']['context']['zeiten'] == zeitmessung.gueltig(gespeichert['zeiten'])
    # Kaputte gespeicherte Zahlen werden nicht angezeigt.
    gespeichert['zeiten'] = {'gesamt': 'schnell'}
    nachricht['metadata']['context']['working_answer'] = gespeichert
    assert 'zeiten' not in wma.project_message(nachricht, episodes, claims)['metadata']['context']


# -- Im Agenten ------------------------------------------------------------------------------------------


@pytest.fixture
def agent(raum, tmp_path):
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.agent import Agent
    from icarus_memory.policy import Policy
    episodes, claims, akten = raum
    wandel(episodes)
    akten.bezuege.aktualisieren()
    modell = Skript(stand_wandel)
    from icarus_memory.audit import AuditLog
    agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='zeit'), policy=Policy(), tools={},
                  audit=AuditLog(tmp_path / 'audit.sqlite3'),
                  provider=modell, knowledge=claims, episodes=episodes)
    agent.modell = modell
    return agent


def test_das_antwort_dict_des_agenten_traegt_zeiten_samt_frage_und_die_oberflaeche_bekommt_sie(agent):
    turn = agent.answer_memory('Bis wann ist die Einreichfrist?')
    zeiten = turn.context['working_answer']['zeiten']
    assert {'frage', 'suche', 'antwort_modell', 'saetze_modell', 'satzpruefung', 'gesamt'} <= set(zeiten)
    assert turn.context['zeiten'] == zeiten
    assert turn.context['satzantwort']['saetze']


def test_schalter_aus_gibt_keine_satzantwort_und_keinen_zweiten_modellaufruf_der_zitatmodus_bleibt(agent):
    agent._saetze = False
    turn = agent.answer_memory('Bis wann ist die Einreichfrist?')
    assert agent.modell.satzanfragen == [], 'das Modell wurde für die Sätze nicht gefragt'
    assert 'satzantwort' not in turn.context and 'satzantwort' not in turn.context['working_answer']
    assert 'Quelle berichtet' in turn.reply, 'die Antwort steht im Zitatmodus da'
    zeiten = turn.context['zeiten']
    assert 'antwort_modell' in zeiten and not {'saetze_modell', 'satzpruefung'} & set(zeiten)


def test_schalter_an_ist_die_vorgabe_und_fragt_das_modell_nach_saetzen(agent):
    turn = agent.answer_memory('Bis wann ist die Einreichfrist?')
    assert len(agent.modell.satzanfragen) == 1
    assert turn.context['satzantwort']['saetze']


def test_die_dauer_des_verstehens_reist_mit_der_anfrage_und_wird_nie_gespeichert(agent):
    import dataclasses
    anfrage = agent.frage_verstehen('Bis wann ist die Einreichfrist?')
    assert anfrage.dauer_s > 0
    assert anfrage == agent.frage_verstehen('Bis wann ist die Einreichfrist?'), 'die Dauer zählt nicht zur Gleichheit'
    assert 'dauer_s' not in anfrage.als_dict()
    turn = agent.answer_memory('Bis wann ist die Einreichfrist?', anfrage=dataclasses.replace(anfrage, dauer_s=7.5))
    assert turn.context['zeiten']['frage'] == 7.5
    assert turn.context['zeiten']['gesamt'] >= 7.5
