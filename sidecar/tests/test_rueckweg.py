"""Ein Rückweg, der bleibt (Persona-Prüfung, Paket Z, Z2 und Z4, 27.10.2026).

Rückgängig stand nur sechs Sekunden im Hinweis; danach gab es für eine zurückgenommene automatische Aufgabe und für
„Alle übernehmen“ keinen Weg zurück. Ein einzeln übernommener Vorschlag hatte gar keinen.

Zusicherungen:
1. Was Kingfisher selbst angelegt hatte und du zurückgenommen hast, steht dauerhaft unter „Zurückgenommen“
   (`GET /api/v1/aufgaben-von-selbst/zurueckgenommen`), jüngste zuerst, mit Titel und Zeitpunkt, und lässt sich auch
   Tage später wiederherstellen; danach steht sie dort nicht mehr.
2. Ein übernommener Vorschlag (einzeln oder mit „Alle übernehmen“) trägt seine Herkunft (`angelegt.art`
   `uebernommen` bzw. `alle_uebernehmen`) und geht jederzeit mit `POST /api/v1/task-candidates/aufgabe/{id}/zurueck`
   zurück zur Prüfung: Die Aufgabe ist weg, der Vorschlag steht wieder offen da (nicht verworfen).
3. Was schon dir gehört, bleibt: eine erledigte übernommene Aufgabe (409 mit Satz), eine von Hand angelegte (409),
   eine unbekannte (404). Die Gruppe von „Alle übernehmen“ geht weiterhin auch ganz zurück.
Nur synthetische Daten (Lena Probe, Anna Berg, Jonas Keller).
"""
from __future__ import annotations

import pytest

from icarus_memory.proposals import ProposalState
from tests.test_aufgaben_von_selbst import ANNA, JONAS, LENA, bitte, client  # noqa: F401 - Fixture und Hilfen


def test_zurueckgenommene_automatische_aufgabe_bleibt_wiederherstellbar(client):
    app = client.app
    _, p = bitte(app.state.episodes, app.state.proposals)
    assert client.post('/api/v1/aufgaben-von-selbst/durchlauf').json()['angelegt'] == 1
    task_id = client.get('/api/v1/aufgaben-von-selbst/heute').json()['aufgaben'][0]['id']
    titel = client.get(f'/api/v1/tasks/{task_id}').json()['title']
    assert client.get('/api/v1/aufgaben-von-selbst/zurueckgenommen').json()['aufgaben'] == []
    assert client.post(f'/api/v1/aufgaben-von-selbst/{task_id}/rueckgaengig').status_code == 200

    # Auch Tage später (lange nach jedem Hinweis): Der Eintrag steht noch da.
    with app.state.tasks._lock:  # noqa: SLF001 - Zeitpunkt in die Vergangenheit legen
        app.state.tasks._conn.execute("UPDATE aufgaben_auto_zurueck SET zurueck_am = '2026-09-20T08:00:00+00:00'")  # noqa: SLF001
        app.state.tasks._conn.commit()  # noqa: SLF001
    liste = client.get('/api/v1/aufgaben-von-selbst/zurueckgenommen').json()
    assert [(a['id'], a['title']) for a in liste['aufgaben']] == [(task_id, titel)]
    assert liste['aufgaben'][0]['zurueck_am'].startswith('2026-09-20')
    assert 'weil Anna Berg dich' in liste['aufgaben'][0]['satz']

    assert client.post(f'/api/v1/aufgaben-von-selbst/{task_id}/wiederherstellen').status_code == 200
    assert client.get(f'/api/v1/tasks/{task_id}').json()['status'] == 'open'
    assert client.get('/api/v1/aufgaben-von-selbst/zurueckgenommen').json()['aufgaben'] == []


def test_zurueckgenommen_juengste_zuerst_und_begrenzt(client):
    app = client.app
    for i in range(3):
        bitte(app.state.episodes, app.state.proposals, titel=f'Druckdaten {i} schicken',
              text=f'Kannst du mir bitte die Druckdaten {i} für den Flyer schicken?', ref=f'konto:d{i}', stunden=2 + i)
    assert client.post('/api/v1/aufgaben-von-selbst/durchlauf').json()['angelegt'] == 3
    ids = [a['id'] for a in client.get('/api/v1/aufgaben-von-selbst/heute').json()['aufgaben']]
    for task_id in ids:
        assert client.post(f'/api/v1/aufgaben-von-selbst/{task_id}/rueckgaengig').status_code == 200
    liste = client.get('/api/v1/aufgaben-von-selbst/zurueckgenommen').json()['aufgaben']
    assert [a['id'] for a in liste] == list(reversed(ids))
    assert len(client.get('/api/v1/aufgaben-von-selbst/zurueckgenommen', params={'limit': 2}).json()['aufgaben']) == 2


def test_einzeln_uebernommener_vorschlag_geht_zurueck_zur_pruefung(client):
    app = client.app
    _, p = bitte(app.state.episodes, app.state.proposals, an=[JONAS], cc=[LENA], ref='konto:k1')
    assert client.post('/api/v1/aufgaben-von-selbst/durchlauf').json()['angelegt'] == 0  # unsicher: bleibt Vorschlag
    aufgabe = client.post(f'/api/v1/task-candidates/{p.id}/accept', json={'title': 'Druckdaten schicken', 'project_id': None}).json()
    assert aufgabe['angelegt']['art'] == 'uebernommen'
    assert client.get('/api/v1/task-candidates/page').json()['total'] == 0
    zurueck = client.post(f'/api/v1/task-candidates/aufgabe/{aufgabe["id"]}/zurueck')
    assert zurueck.status_code == 200
    assert zurueck.json()['satz'] == 'Der Vorschlag steht wieder zur Prüfung.'
    assert client.get(f'/api/v1/tasks/{aufgabe["id"]}').status_code == 404
    assert app.state.proposals.get(p.id).state is ProposalState.PENDING
    assert client.get('/api/v1/task-candidates/page').json()['total'] == 1
    # Noch einmal übernehmen geht, und auch das lässt sich wieder zurücknehmen.
    wieder = client.post(f'/api/v1/task-candidates/{p.id}/accept', json={'title': 'Druckdaten schicken', 'project_id': None}).json()
    assert wieder['id'] == aufgabe['id']
    assert client.post(f'/api/v1/task-candidates/aufgabe/{wieder["id"]}/zurueck').status_code == 200


def test_aus_alle_uebernehmen_einzeln_oder_ganz_zurueck(client):
    app = client.app
    episodes, proposals = app.state.episodes, app.state.proposals
    _, p1 = bitte(episodes, proposals, an=[JONAS], cc=[LENA], ref='konto:n1')
    _, p2 = bitte(episodes, proposals, an=[JONAS], cc=[LENA], titel='Rechnung 4711 prüfen',
                  text='Bitte prüfe die Rechnung 4711 bis Freitag.', ref='konto:n2')
    antwort = client.post('/api/v1/task-candidates/alle-uebernehmen', json={'ids': [p1.id, p2.id]}).json()
    erste, zweite = antwort['aufgaben']
    assert client.post(f'/api/v1/task-candidates/aufgabe/{erste["id"]}/zurueck').status_code == 200
    assert client.get('/api/v1/task-candidates/page').json()['total'] == 1
    # Die übrige der Gruppe geht mit der Gruppe zurück.
    assert client.post(f'/api/v1/task-candidates/gruppe/{antwort["gruppe"]}/rueckgaengig').json() == {'zurueckgenommen': 1, 'geblieben': 0}
    assert client.get('/api/v1/task-candidates/page').json()['total'] == 2
    assert app.state.tasks.get(zweite['id']) is None


def test_was_dir_gehoert_bleibt(client):
    app = client.app
    _, p = bitte(app.state.episodes, app.state.proposals, an=[JONAS], cc=[LENA], ref='konto:k1')
    aufgabe = client.post(f'/api/v1/task-candidates/{p.id}/accept', json={'title': 'Druckdaten schicken', 'project_id': None}).json()
    app.state.tasks.complete(aufgabe['id'])
    erledigt = client.post(f'/api/v1/task-candidates/aufgabe/{aufgabe["id"]}/zurueck')
    assert erledigt.status_code == 409 and 'erledigt' in erledigt.json()['detail']
    hand = client.post('/api/v1/tasks', json={'title': 'Von Hand'}).json()
    assert client.post(f'/api/v1/task-candidates/aufgabe/{hand["id"]}/zurueck').status_code == 409
    assert client.post('/api/v1/task-candidates/aufgabe/t-unbekannt/zurueck').status_code == 404
    assert app.state.proposals.get(p.id).state is ProposalState.ACCEPTED


@pytest.mark.parametrize('art', ['automatisch'])
def test_automatische_aufgabe_geht_nicht_zur_pruefung_sondern_wird_zurueckgenommen(client, art):
    """Was Kingfisher selbst angelegt hat, hat seinen eigenen Rückweg (Rückgängig, gemerkt); „zur Prüfung“ gilt nur für
    Übernommenes."""
    app = client.app
    bitte(app.state.episodes, app.state.proposals)
    client.post('/api/v1/aufgaben-von-selbst/durchlauf')
    task_id = client.get('/api/v1/aufgaben-von-selbst/heute').json()['aufgaben'][0]['id']
    assert client.get(f'/api/v1/tasks/{task_id}').json()['angelegt']['art'] == art
    assert client.post(f'/api/v1/task-candidates/aufgabe/{task_id}/zurueck').status_code == 409

