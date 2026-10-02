"""Telefonate und Termine ohne Mitschrift: knappe, abweisbare Nachfrage (F3)."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

from icarus_memory.calendar_memory import KalenderGedaechtnis, fenster
from icarus_memory.connectors.calendar import Event
from icarus_memory.model import Provenance, SourceType
from icarus_memory.nachbereitung import MAX_KARTEN, externe, frage_zu, offene
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_nachbereitung import JETZT, Kalender, _offen, _vorbei
from tests.test_source_answers_http import _api

EIGENE = ['ich@firma.example']
EXTERN = 'Anna Keller <anna@agentur.example>'
KOLLEGE = 'Bert Kraus <bert@firma.example>'


def test_externe_sind_nur_die_von_ausserhalb():
    assert externe([KOLLEGE, EXTERN, 'Ich <ich@firma.example>'], EIGENE) == [EXTERN]
    assert externe([KOLLEGE], EIGENE) == []
    # Eine Adresse ohne erkennbare Domäne zählt als extern: Fragen ist billiger als Verschweigen.
    assert externe(['Carla Neu'], EIGENE) == ['Carla Neu']


def test_ein_privater_anbieter_macht_niemanden_zum_kollegen():
    assert externe(['Bert <bert@gmail.com>'], ['ich@gmail.com']) == ['Bert <bert@gmail.com>']


def test_die_frage_nennt_die_menschen():
    assert frage_zu('Abstimmung', [EXTERN]) == 'Wie war das Gespräch mit Anna Keller?'
    assert frage_zu('Abstimmung', [EXTERN, 'Carl Neu <carl@x.example>']) == 'Wie war das Gespräch mit Anna Keller und Carl Neu?'
    assert frage_zu('Abstimmung', [EXTERN, 'C <c@x.example>', 'D <d@x.example>']) == 'Wie war das Gespräch mit Anna Keller und 2 weiteren?'
    assert frage_zu('Abstimmung', []) == 'Wie war „Abstimmung“?'


def _termine(n, attendees=(EXTERN,)):
    ergebnis = []
    for index in range(n):
        beginn = JETZT - timedelta(hours=4 + index)
        ergebnis.append({'uid': f't{index}', 'summary': f'Runde {index}', 'start': beginn.isoformat(),
                         'end': (beginn + timedelta(minutes=30)).isoformat(), 'attendees': list(attendees)})
    return ergebnis


def test_nie_mehr_als_drei_karten_und_die_neuesten_zuerst():
    karten = offene(_termine(6), jetzt=JETZT, eigene=EIGENE, erledigt={})
    assert len(karten) == MAX_KARTEN == 3
    assert [k['uid'] for k in karten] == ['t0', 't1', 't2']
    assert all(k['frage'] == 'Wie war das Gespräch mit Anna Keller?' and k['mit'] == ['Anna Keller'] for k in karten)


def test_interne_termine_fragen_nicht_nach():
    assert offene(_termine(2, attendees=(KOLLEGE,)), jetzt=JETZT, eigene=EIGENE, erledigt={}) == []


def test_mit_mitschrift_wird_nicht_gefragt():
    termine = _termine(2)
    from icarus_memory.nachbereitung import schluessel
    key = schluessel('t0', termine[0]['start'])
    karten = offene(termine, jetzt=JETZT, eigene=EIGENE, erledigt={}, hat_mitschrift=lambda k: k == key)
    assert [k['uid'] for k in karten] == ['t1']


def test_erledigte_und_abgewiesene_termine_fragen_nie_wieder():
    from icarus_memory.nachbereitung import schluessel
    termine = _termine(3)
    erledigt = {schluessel('t0', termine[0]['start']): None, schluessel('t1', termine[1]['start']): 'e-1'}
    assert [k['uid'] for k in offene(termine, jetzt=JETZT, eigene=EIGENE, erledigt=erledigt)] == ['t2']


def test_dashboard_liefert_hoechstens_drei_karten_mit_frage(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.calendar = Kalender([_vorbei(uid=f'u{i}', summary=f'Runde {i}', stunden=3 + i) for i in range(5)])
        karten = _offen(client)
        assert [k['uid'] for k in karten] == ['u0', 'u1', 'u2']
        assert karten[0]['frage'] == 'Wie war das Gespräch mit Anna Keller?'
        # Eine Karte weniger, sobald jemand sie abweist: die nächste rückt nach, nicht mehr als drei.
        client.put('/api/v1/calendar/nachbereitung/stand', json={'uid': 'u0', 'start': karten[0]['start'], 'nichts': True})
        assert [k['uid'] for k in _offen(client)] == ['u1', 'u2', 'u3']
    finally:
        client.close()


def test_antwort_wird_quelle_und_kein_fakt(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        vorher = app.state.store.alles()
        antwort = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': termin.start.isoformat(), 'text': 'Telefonat: Angebot kommt bis Freitag.'}).json()
        episode = app.state.episodes.get(antwort['id'])
        assert episode.provenance.source_ref.startswith('termin:t1|')          # verknüpft mit dem Termin
        assert episode.provenance.source_type is SourceType.USER_STATED        # Rohmaterial: was der Nutzer sagt
        assert episode.produced == [] and app.state.store.alles() == vorher    # kein Fakt im Bestand
        assert _offen(client) == []                                            # und danach keine Nachfrage mehr
    finally:
        client.close()


def test_zugeordnete_mitschrift_ersetzt_die_nachfrage_und_erscheint_am_termin(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        # Derselbe Termin steht auch im Gedächtnis (Episode der Art `event`).
        von, bis = fenster(datetime.now(timezone.utc))
        KalenderGedaechtnis(app.state.episodes, app.state.claims).abgleichen(
            'k', 'Arbeit', [termin], von, bis, at=datetime.now(timezone.utc))
        assert len(_offen(client)) == 1
        lokal = termin.start.astimezone()
        name = f'{lokal:%Y-%m-%d %H.%M} Abstimmung Druck.txt'
        anna = 'Anna Keller: Guten Tag.\nIch: Hallo.\nAnna Keller: Wir schicken das Angebot.\nIch: Danke.\n'
        anmeldung = client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'}).json()['pick_request']['id']
        zustand = client.post('/api/v1/transcript-sync/worker', json={'root_id': 'r', 'folder': '/m', 'picked': anmeldung}).json()
        scope = {'root_id': 'r', 'generation': zustand['generation']}
        lauf = {**scope, 'run_id': client.post('/api/v1/transcript-sync/begin', json=scope).json()['run_id']}
        antwort = client.post('/api/v1/transcript-sync/files', json={
            **lauf, 'filename': name, 'content_base64': base64.b64encode(anna.encode()).decode()})
        assert antwort.status_code == 200, antwort.text
        assert _offen(client) == []          # es liegt eine Mitschrift vor: nichts nachzufragen
        stand = client.get('/api/v1/calendar/nachbereitung',
                           params={'uid': 't1', 'start': termin.start.isoformat()}).json()
        assert [t['id'] for t in stand['transkripte']] == [antwort.json()['id']]
        # Löst der Nutzer die Zuordnung, fragt das Programm wieder.
        client.delete(f"/api/v1/transkripte/{antwort.json()['id']}/zuordnung")
        assert len(_offen(client)) == 1
    finally:
        client.close()
