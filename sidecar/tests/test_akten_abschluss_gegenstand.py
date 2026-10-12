"""Ein Abschluss betrifft die genannte Aufgabe, nicht jede Zusage zum selben Event."""
import pytest

from icarus_memory import Provenance, SourceType
from icarus_memory.akten import Akten
from icarus_memory.akten_kontext import aufbauen, hinweis_fuer_modell
from tests.test_akten import SACHE, mail
from tests.test_bezuege import JETZT, welt  # noqa: F401 - echte temporäre Stores

ZUSAGE = 'Ich übernehme den Standdienst beim Herbstmarkt.'


@pytest.mark.parametrize('neu', [
    'Meine separate Zusage für den Plakatdruck beim Herbstmarkt ist zurückgezogen; der Standdienst ist davon unabhängig.',
    'Meine Zusage für den Plakatdruck beim Herbstmarkt ist zurückgezogen.',
    'Der Plakatdruck beim Herbstmarkt ist erledigt.',
    'Der Standdienst beim Herbstmarkt ist nicht abgesagt.',
    'Abgesagt ist der Standdienst beim Herbstmarkt nicht.',
    'Der Standdienst beim Herbstmarkt ist nicht erledigt.',
    'Erledigt ist der Standdienst beim Herbstmarkt nicht.',
    'Der Plakatdruck ist abgesagt, der Standdienst beim Herbstmarkt nicht.',
    'Der Plakatdruck ist abgesagt, nicht der Standdienst beim Herbstmarkt.',
    'Abgesagt ist der Plakatdruck, nicht der Standdienst beim Herbstmarkt.',
    'Nicht der Standdienst, sondern der Plakatdruck beim Herbstmarkt ist abgesagt.',
])
@pytest.mark.parametrize('sicht', ['person', 'projekt', 'modell'])
def test_fremder_oder_verneinter_abschluss_laesst_standdienst_offen(welt, neu, sicht):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Herbstmarkt', Provenance(SourceType.USER_STATED))
    alt = mail(episodes, 'Standdienst', [(ZUSAGE, 'commitment')], tage=20, projekt=projekt.id)
    neu = mail(episodes, 'Plakatdruck', [(neu, 'change')], tage=5, projekt=projekt.id)
    bezuege.aktualisieren()
    akten = Akten(episodes, bezuege, claims=None)
    if sicht == 'modell':
        kontext = aufbauen(episodes, None, [alt.id, neu.id], akten=akten)
        assert not kontext.gekennzeichnet(alt.id)
        assert hinweis_fuer_modell(kontext, alt.id, {alt.id: 'S1', neu.id: 'S2'}, {}) == []
    else:
        sache = SACHE if sicht == 'person' else f'projekt:{projekt.id}'
        offen = akten.akte(sache, jetzt=JETZT)['offen']
        assert [e['text'] for e in offen['eintraege']] == [ZUSAGE]
        assert offen['erledigt']['gesamt'] == 0


@pytest.mark.parametrize('neu,grund', [
    ('Meine Zusage für den Standdienst beim Herbstmarkt ist zurückgezogen.', 'absage'),
    ('Der Standdienst beim Herbstmarkt ist erledigt.', 'erledigt'),
    ('Der gesamte Herbstmarkt ist abgesagt.', 'absage'),
    ('Der gesamte Herbstmarkt findet nicht statt.', 'absage'),
    ('Der Standdienst beim Herbstmarkt ist nicht nur abgesagt, sondern auch gestrichen.', 'absage'),
    ('Der Standdienst beim Herbstmarkt ist nicht nur erledigt, sondern auch bezahlt.', 'erledigt'),
])
def test_gleiche_aufgabe_und_gesamte_eventabsage_bleiben_erkannt(welt, neu, grund):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Herbstmarkt', Provenance(SourceType.USER_STATED))
    alt = mail(episodes, 'Standdienst', [(ZUSAGE, 'commitment')], tage=20, projekt=projekt.id)
    neu = mail(episodes, 'Neuer Stand', [(neu, 'change')], tage=5, projekt=projekt.id)
    bezuege.aktualisieren()
    akten = Akten(episodes, bezuege, claims=None)
    for sache in [SACHE, f'projekt:{projekt.id}']:
        offen = akten.akte(sache, jetzt=JETZT)['offen']
        assert offen['gesamt'] == 0
        assert offen['erledigt']['eintraege'][0]['grund'] == grund
        assert offen['erledigt']['eintraege'][0]['durch']['episode_id'] == neu.id
    kontext = aufbauen(episodes, None, [alt.id, neu.id], akten=akten)
    hinweise = hinweis_fuer_modell(kontext, alt.id, {alt.id: 'S1', neu.id: 'S2'}, {})
    assert [h['grund'] for h in hinweise] == ['vermutlich abgesagt' if grund == 'absage' else 'vermutlich erledigt']


@pytest.mark.parametrize('neu', [
    'Der Plakatdruck ist abgesagt, der Standdienst beim Herbstmarkt nicht.',
    'Der Plakatdruck ist abgesagt, nicht der Standdienst beim Herbstmarkt.',
    'Abgesagt ist der Plakatdruck, nicht der Standdienst beim Herbstmarkt.',
    'Nicht der Standdienst, sondern der Plakatdruck beim Herbstmarkt ist abgesagt.',
])
def test_kontrast_sagt_den_plakatdruck_ab(welt, neu):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Herbstmarkt', Provenance(SourceType.USER_STATED))
    alt = mail(episodes, 'Plakatdruck', [('Ich übernehme den Plakatdruck beim Herbstmarkt.', 'commitment')],
               tage=20, projekt=projekt.id)
    neu = mail(episodes, 'Absage', [(neu, 'change')], tage=5, projekt=projekt.id)
    bezuege.aktualisieren()
    akten = Akten(episodes, bezuege, claims=None)
    for sache in [SACHE, f'projekt:{projekt.id}']:
        offen = akten.akte(sache, jetzt=JETZT)['offen']
        assert offen['gesamt'] == 0
        assert offen['erledigt']['eintraege'][0]['durch']['episode_id'] == neu.id
    hinweise = hinweis_fuer_modell(aufbauen(episodes, None, [alt.id, neu.id], akten=akten),
                                  alt.id, {alt.id: 'S1', neu.id: 'S2'}, {})
    assert [h['grund'] for h in hinweise] == ['vermutlich abgesagt']


@pytest.mark.parametrize('alt_text,neu_text', [
    ('Ich übernehme die Aufgabe Standdienst beim Herbstmarkt.',
     'Die Aufgabe Plakatdruck beim Herbstmarkt ist abgesagt.'),
    ('Ich übernehme die Planung des Standdiensts beim Herbstmarkt.',
     'Die Planung des Plakatdrucks beim Herbstmarkt ist abgesagt.'),
])
@pytest.mark.parametrize('sicht', ['person', 'projekt', 'modell'])
def test_gemeinsame_kategorie_beendet_keine_andere_aufgabe(welt, alt_text, neu_text, sicht):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Herbstmarkt', Provenance(SourceType.USER_STATED))
    alt = mail(episodes, 'Standdienst', [(alt_text, 'commitment')], tage=20, projekt=projekt.id)
    neu = mail(episodes, 'Plakatdruck', [(neu_text, 'change')], tage=5, projekt=projekt.id)
    bezuege.aktualisieren()
    akten = Akten(episodes, bezuege, claims=None)
    if sicht == 'modell':
        kontext = aufbauen(episodes, None, [alt.id, neu.id], akten=akten)
        assert not kontext.gekennzeichnet(alt.id)
        assert hinweis_fuer_modell(kontext, alt.id, {alt.id: 'S1', neu.id: 'S2'}, {}) == []
    else:
        sache = SACHE if sicht == 'person' else f'projekt:{projekt.id}'
        offen = akten.akte(sache, jetzt=JETZT)['offen']
        assert [e['text'] for e in offen['eintraege']] == [alt_text]
        assert offen['erledigt']['gesamt'] == 0


@pytest.mark.parametrize('alt_text,neu_text', [
    ('Ich übernehme die Aufgabe Standdienst beim Herbstmarkt.',
     'Die Aufgabe Standdienst beim Herbstmarkt ist abgesagt.'),
    ('Ich übernehme die Planung des Standdiensts beim Herbstmarkt.',
     'Die Planung des Standdiensts beim Herbstmarkt ist abgesagt.'),
])
def test_vollstaendiger_gleicher_gegenstand_bleibt_erkannt(welt, alt_text, neu_text):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Herbstmarkt', Provenance(SourceType.USER_STATED))
    alt = mail(episodes, 'Standdienst', [(alt_text, 'commitment')], tage=20, projekt=projekt.id)
    neu = mail(episodes, 'Absage', [(neu_text, 'change')], tage=5, projekt=projekt.id)
    bezuege.aktualisieren()
    akten = Akten(episodes, bezuege, claims=None)
    for sache in [SACHE, f'projekt:{projekt.id}']:
        offen = akten.akte(sache, jetzt=JETZT)['offen']
        assert offen['gesamt'] == 0
        assert offen['erledigt']['eintraege'][0]['durch']['episode_id'] == neu.id
    kontext = aufbauen(episodes, None, [alt.id, neu.id], akten=akten)
    hinweise = hinweis_fuer_modell(kontext, alt.id, {alt.id: 'S1', neu.id: 'S2'}, {})
    assert [h['grund'] for h in hinweise] == ['vermutlich abgesagt']
