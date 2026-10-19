"""„Worauf warte ich noch?“ und „Was habe ich zugesagt?“ aus den Akten, ohne Modell und nie im freien Chat.

Zusicherungen:
1. Die festen Frageformen werden erkannt; ähnliche Fragen über andere Personen nicht.
2. „Worauf warte ich?“ nennt Zusagen anderer an dich und deine eigenen Bitten, „Was habe ich zugesagt?“ deine
   Zusagen; jeweils nur vermutlich offene, mit Quelle.
3. Was du in der Akte als erledigt abgelegt hast, steht nicht mehr da.
4. Die Frage geht nie in den freien Chat, auch mit einem Handlungswort („schicken“).
5. Im Gesprächsverlauf steht kein Zitat; beim Öffnen wird die Antwort neu aus den Akten gebildet.
"""
import pytest

from icarus_memory import offene_punkte
from icarus_memory.akten_entscheidungen import Entscheidungen
from icarus_memory.memory_routing import route
from tests.test_akten import akten, neu_rechnen  # noqa: F401 - Fixture und Hilfen
from tests.test_akten_entscheidungen import (ABLAUF, AKADEMIE, LEA, NACHHOLEN, SILKE, verlaufsmail,  # noqa: F401
                                             workshop)
from tests.test_akten_routes import api  # noqa: F401 - Fixture
from tests.test_bezuege import ICH, JETZT, welt  # noqa: F401 - Fixture
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_mappe import _quelle


@pytest.mark.parametrize('frage,art', [
    ('Worauf warte ich noch?', 'wartet_auf'), ('Auf was warten wir eigentlich?', 'wartet_auf'),
    ('Auf was warte ich noch?', 'wartet_auf'), ('Wer schuldet mir noch etwas?', 'wartet_auf'),
    ('Was habe ich noch zugesagt?', 'zugesagt'), ('Welche Zusagen habe ich offen?', 'zugesagt'),
    ('Was muss ich noch schicken?', 'zugesagt'), ('Was hat Silke zugesagt?', None),
    ('Worauf wartet Silke?', None),
])
def test_feste_frageformen(frage, art):
    assert offene_punkte.art_der_frage(frage) == art


def test_worauf_warte_ich_und_was_habe_ich_zugesagt(welt, akten):
    episodes, _, bezuege = welt
    workshop(episodes)
    verlaufsmail(episodes, 'AW: Absage Workshop', [(NACHHOLEN, 'commitment')], 11, absender=LEA, an=SILKE,
                 kennung='a4', antwort_auf='a3')
    neu_rechnen(akten)
    warten = offene_punkte.sammeln(akten, bezuege, 'wartet_auf', jetzt=JETZT)
    assert [p['text'] for p in warten['punkte']] == [ABLAUF]
    text, links = offene_punkte.als_text(warten, 'wartet_auf')
    assert text.startswith('Du wartest vermutlich noch auf eine Sache')
    assert f'1. Silke Vogt, Zusage vom 16. Juli 2026: „{ABLAUF}“ [Quelle 1]' in text
    assert links == [{'episode_id': warten['punkte'][0]['episode_id'], 'label': 'Quelle 1 öffnen',
                      'automatic_memory': True}]
    zugesagt = offene_punkte.sammeln(akten, bezuege, 'zugesagt', jetzt=JETZT)
    assert [p['text'] for p in zugesagt['punkte']] == [NACHHOLEN]
    assert offene_punkte.als_text(zugesagt, 'zugesagt')[0].startswith('Du hast vermutlich noch eine Zusage offen')
    # Abgelegt heißt: nicht mehr offen, auch hier.
    Entscheidungen(episodes).setzen(warten['punkte'][0]['ziel'], 'erledigt')
    leer = offene_punkte.sammeln(akten, bezuege, 'wartet_auf', jetzt=JETZT)
    assert leer['punkte'] == [] and offene_punkte.als_text(leer, 'wartet_auf')[0].startswith(
        'In deinen Akten finde ich nichts, worauf du noch wartest')


@pytest.mark.parametrize('frage', ['Worauf warte ich noch?', 'Was muss ich noch schicken?',
                                   'Was habe ich zugesagt?'])
def test_nie_im_freien_chat(frage):
    assert route(frage) == 'memory_evidence'


def test_welche_fristen_geht_in_den_belegweg():
    assert route('Welche Fristen stehen an?') == 'memory_evidence'


def test_im_gespraech_ohne_modell_ohne_zitat_im_verlauf(api):
    app, client = api
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    _quelle(app, 'Druckdaten', [('Ich schicke Ihnen die Druckdaten bis Freitag.', 'commitment')], tage=2)
    client.post('/api/v1/akten/aktualisieren')
    gespraech = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    antwort = client.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': 'Worauf warte ich noch?'})
    assert antwort.status_code == 201
    gespeichert = app.state.conversations.messages(gespraech)[-1]
    assert gespeichert.metadata['context']['answer_contract']['status'] == 'akten'
    assert gespeichert.metadata['context']['answer_contract']['model_called'] is False
    # Kein Zitat im Verlauf: nur die Frage.
    assert 'Druckdaten' not in gespeichert.content and 'source_links' not in gespeichert.metadata['context']
    geoeffnet = client.get(f'/api/v1/conversations/{gespraech}').json()
    letzte = geoeffnet['messages'][-1]
    assert 'Ich schicke Ihnen die Druckdaten bis Freitag.' in letzte['content']
    assert letzte['metadata']['context']['source_links'][0]['label'] == 'Quelle 1 öffnen'


@pytest.mark.parametrize('frage,weg', [
    ('An welche Adresse soll ich die Rechnung für Frau Krüger schicken?', 'memory_evidence'),
    ('Wohin soll ich die Unterlagen schicken?', 'memory_evidence'),
    ('An wen muss ich die Kündigung senden?', 'memory_evidence'),
    ('Schick die Rechnung an Frau Krüger.', 'chat'),
    ('An welche Adresse soll ich schicken? Schick sie gleich los.', 'chat'),
])
def test_zielfrage_mit_handlungswort_ist_eine_frage(frage, weg):
    assert route(frage) == weg
