"""Mailbezug beweist keine Erfüllung und ein Vorname keine Identität.

Echte SQLite-Stores; ausschließlich synthetische Personen und Nachrichten.
Die Tests brechen bei automatischer Erledigung durch Worttreffer, bei Übergehen
bekannter Adressen oder beim Bestätigen eines entzogenen/ersetzten Belegs.
"""
import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.proposals import ProposalError, ProposalKind, ProposalState
from icarus_memory.tasks import TaskStatus
from tests.test_aufgaben_post import (
    ANNA, JETZT, LENA, aufgabe, bitte_von_anna, mail, vorschlaege, welt,
)


@pytest.mark.parametrize('text', [
    'Die Druckdaten sind noch nicht fertig. Ich werde sie nächste Woche schicken.',
    'Ich habe die Druckdaten noch nicht geschickt.',
    'Ich prüfe die Druckdaten morgen.',
    'Hallo Anna, danke für die Druckdaten.',
    'Hallo Anna, anbei die Druckdaten.',
])
def test_worttreffer_ist_keine_nachgewiesene_erfuellung(welt, text):
    episodes, tasks, proposals, lauf, buch = welt
    quelle = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=quelle, faellig_vor_tagen=-7)
    antwort = mail(episodes, 'AW: Druckdaten', text, von=LENA, an=[ANNA],
                   kennung='antwort', antwort_auf=['a1'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 1}
    offen = tasks.get(task.id)
    assert offen.status is TaskStatus.OPEN and offen.due == task.due
    assert offen.erledigt_grund is None and offen.done_at is None
    assert [e for e in buch.ereignisse(JETZT) if e.art == 'aufgabe_post'] == []
    [vorschlag] = lauf.vorschlaege()
    assert 'Ist die Aufgabe damit erledigt?' in vorschlag['satz']
    assert 'geschickt hast' not in vorschlag['satz']
    assert lauf.verarbeiten(antwort) == {'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
    assert lauf.schritt()['geprueft'] == 0
    erledigt = lauf.vorschlag_annehmen(vorschlag['id'])
    assert erledigt.status is TaskStatus.DONE and erledigt.due == task.due
    assert erledigt.erledigt_grund['satz'] == 'Erledigt nach deiner Bestätigung zur Mail an Anna Berg vom 21. Oktober.'
    wieder = lauf.rueckgaengig(task.id)
    assert wieder.status is TaskStatus.OPEN and wieder.due == task.due
    assert lauf.verarbeiten(antwort) == {'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}


@pytest.mark.parametrize('im_verlauf', [False, True])
def test_andere_anna_beantwortet_nicht_die_aufgabe_der_bekannten_adresse(welt, im_verlauf):
    episodes, tasks, proposals, lauf, _ = welt
    quelle = mail(episodes, 'Freigabe Flyer', 'Anna, bitte den Flyer freigeben.',
                  von=LENA, an=[ANNA], tage=4, kennung='an-berg')
    task = aufgabe(tasks, 'Freigabe Flyer von Anna', quelle=quelle, wartet_auf='Anna')
    mail(episodes, 'AW: Freigabe Flyer', 'Der Flyer ist freigegeben.',
         von='Anna Frei <anna.frei@example.org>', an=[LENA], kennung='von-frei',
         antwort_auf=['an-berg'] if im_verlauf else [])
    assert lauf.schritt()['zurueck'] == 0
    assert tasks.get(task.id).wartet_auf == 'Anna'
    assert tasks.get(task.id).geaendert_grund is None
    assert vorschlaege(proposals) == []


def test_gleicher_name_ohne_bekannte_adresse_bleibt_vorschlag(welt):
    episodes, tasks, proposals, lauf, _ = welt
    task = aufgabe(tasks, 'Freigabe Flyer von Anna', wartet_auf='Anna Berg')
    mail(episodes, 'Flyer', 'Der Flyer ist freigegeben.', von=ANNA, an=[LENA], kennung='ohne-quelle')
    assert lauf.schritt()['zurueck'] == 0
    assert tasks.get(task.id).wartet_auf == 'Anna Berg'
    assert len(vorschlaege(proposals, ProposalKind.TASK_WAITING_RESOLVED)) == 1


@pytest.mark.parametrize('bezug', [False, True])
def test_bekannte_adresse_braucht_bezug_und_funktioniert_ohne_anzeigenamen(welt, bezug):
    episodes, tasks, proposals, lauf, _ = welt
    quelle = mail(episodes, 'Freigabe Flyer', 'Bitte den Flyer freigeben.',
                  von=LENA, an=[ANNA], tage=4, kennung='bekannt')
    task = aufgabe(tasks, 'Freigabe Flyer von Anna', quelle=quelle, wartet_auf='Anna')
    mail(episodes, 'Flyer' if bezug else 'Sommerfest', 'Passt so.',
         von='anna.berg@example.org', an=[LENA], kennung='ohne-name')
    assert lauf.schritt()['zurueck'] == int(bezug)
    assert tasks.get(task.id).wartet_auf == (None if bezug else 'Anna')
    assert len(vorschlaege(proposals)) == int(not bezug)


@pytest.mark.parametrize('welche', ['antwort', 'aufgabenquelle'])
@pytest.mark.parametrize('aenderung', ['entzug', 'ersetzt'])
def test_vorschlag_darf_entzogene_oder_ersetzte_quelle_nicht_bestaetigen(welt, welche, aenderung):
    episodes, tasks, proposals, lauf, _ = welt
    quelle = mail(episodes, 'Druckdaten für den Flyer', 'Bitte Druckdaten senden.',
                  von=ANNA, an=[LENA], tage=3, kennung='a1', source_key='synthetic:bitte')
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=quelle)
    antwort = mail(episodes, 'AW: Flyer', 'Ich melde mich.', von=LENA, an=[ANNA],
                   kennung='spaeter', antwort_auf=['a1'], source_key='synthetic:antwort')
    lauf.schritt()
    [vorschlag] = vorschlaege(proposals)
    betroffen = antwort if welche == 'antwort' else quelle
    if aenderung == 'entzug':
        episodes.ignore(betroffen.id)
    else:
        key = 'synthetic:antwort' if welche == 'antwort' else 'synthetic:bitte'
        neu, _ = episodes.record(EpisodeKind.MESSAGE, 'Berichtigte Quelle', 'Diese Bitte gilt nicht mehr.',
                                 Provenance(SourceType.EMAIL), source_key=key)
        episodes.advance_source_head(key, betroffen.id, neu.id)
    with pytest.raises(ProposalError):
        lauf.vorschlag_annehmen(vorschlag.id)
    assert tasks.get(task.id).status is TaskStatus.OPEN
    assert proposals.get(vorschlag.id).state is ProposalState.SUPERSEDED
    assert lauf.vorschlaege() == []


def test_mehrere_gleichnamige_quellempfaenger_belegen_keine_eindeutige_gegenseite(welt):
    episodes, tasks, proposals, lauf, _ = welt
    quelle = mail(episodes, 'Freigabe Flyer', 'Bitte den Flyer freigeben.', von=LENA,
                  an=[ANNA, 'Anna Frei <anna.frei@example.org>'], tage=4, kennung='beide-annas')
    task = aufgabe(tasks, 'Freigabe Flyer von Anna', quelle=quelle, wartet_auf='Anna')
    mail(episodes, 'Freigabe Flyer', 'Der Flyer passt.', von=ANNA, an=[LENA], kennung='eine-anna')
    assert lauf.schritt()['zurueck'] == 0
    assert tasks.get(task.id).wartet_auf == 'Anna'
    assert len(vorschlaege(proposals)) == 1


def test_vorschlagsgrund_erfindet_keinen_empfaenger_aus_dem_verlauf(welt):
    episodes, tasks, proposals, lauf, _ = welt
    quelle = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=quelle)
    mail(episodes, 'AW: Druckdaten', 'Jonas, bitte die Druckdaten vorbereiten.',
         von=LENA, an=['Jonas Keller <jonas.keller@example.org>'], kennung='weiter', antwort_auf=['a1'])
    lauf.schritt()
    [vorschlag] = lauf.vorschlaege()
    assert 'Du hast Anna Berg' not in vorschlag['satz']
    assert vorschlag['satz'] == ('Du hast am 21. Oktober an Jonas Keller geschrieben '
                                 '(„AW: Druckdaten“). Ist die Aufgabe damit erledigt?')
    erledigt = lauf.vorschlag_annehmen(vorschlag['id'])
    assert 'Mail an Anna Berg' not in erledigt.erledigt_grund['satz']


def test_bestehender_offener_vorschlag_zeigt_keinen_veralteten_empfaengergrund(welt):
    from icarus_memory.proposals import Evidence
    episodes, tasks, proposals, lauf, _ = welt
    quelle = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=quelle)
    antwort = mail(episodes, 'AW: Druckdaten', 'Jonas, bitte vorbereiten.', von=LENA,
                   an=['Jonas Keller <jonas.keller@example.org>'], kennung='alt-weiter', antwort_auf=['a1'])
    proposals.propose(ProposalKind.TASK_DONE, f'Erledigt? „{task.title}“',
                      'Du hast Anna Berg geantwortet. Ist die Aufgabe erledigt?',
                      evidence=[Evidence(antwort.id, antwort.title, antwort.digest)],
                      target_ref=f'task:{task.id}', proposed_by='aufgaben_post')
    [vorschlag] = lauf.vorschlaege()
    assert 'Du hast Anna Berg' not in vorschlag['satz']
    assert 'Jonas Keller' in vorschlag['satz']


def test_bestaetigter_wartevorschlag_erfindet_keine_antwort_im_verlauf(welt):
    episodes, tasks, proposals, lauf, _ = welt
    task = aufgabe(tasks, 'Freigabe von Anna', wartet_auf='Anna Berg')
    mail(episodes, 'Sommerfest', 'Kommst du zum Sommerfest?', von=ANNA, an=[LENA], kennung='fremdes-thema')
    assert lauf.schritt()['vorschlaege'] == 1
    [vorschlag] = lauf.vorschlaege()
    zurueck = lauf.vorschlag_annehmen(vorschlag['id'])
    assert zurueck.wartet_auf is None
    assert zurueck.geaendert_grund['satz'] == 'Wieder bei dir, weil Anna Berg am 21. Oktober geschrieben hat.'
