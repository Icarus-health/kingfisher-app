"""Akten-Routen: Sachen, Akte, Bezüge einer Quelle, Zuordnung des Nutzers, Abgleich im Hintergrund."""
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import akten_routes
from icarus_memory.model import Provenance, SourceType
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_mappe import _projekt, _quelle
from tests.test_source_answers_http import _api

BITTE = 'Bitte schicke mir bis Freitag die Druckdaten für das Plakat.'
ERLEDIGT = 'Die Druckdaten für das Plakat sind erhalten und geprüft.'


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        yield app, client
    finally:
        client.close()


def abgleichen(client):
    return client.post('/api/v1/akten/aktualisieren').json()


def test_sachen_akte_und_quelle_ueber_die_routen(api):
    app, client = api
    projekt = _projekt(app, 'Mainz')
    e = _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id, tage=3)
    assert abgleichen(client)['offen'] == 0
    sachen = client.get('/api/v1/akten/sachen', params={'art': 'projekt', 'warten': True}).json()
    assert sachen['gesamt'] == 1 and sachen['berechnung']['offen'] == 0
    eintrag = sachen['sachen'][0]
    assert (eintrag['sache'], eintrag['name'], eintrag['art_text'], eintrag['quellen']) == (
        f'projekt:{projekt.id}', 'Mainz', 'Projekt', 1)
    akte = client.get('/api/v1/akten/akte', params={'sache': eintrag['sache']}).json()
    assert akte['name'] == 'Mainz' and akte['verlauf']['gesamt'] == 1
    assert [z['text'] for z in akte['offen']['eintraege']] == [BITTE]
    assert akte['fristen']['gesamt']['kommend'] + akte['fristen']['gesamt']['verstrichen'] == 1
    bezuege = client.get(f'/api/v1/akten/quellen/{e.id}').json()
    namen = {b['sache']: (b['name'], b['grundlagen']) for b in bezuege['bezuege']}
    assert namen[f'projekt:{projekt.id}'] == ('Mainz', ['anker'])
    assert namen['person:a:anna@agentur.example'] == ('Anna Keller', ['anker'])


def test_fehler_der_routen_sind_deutlich(api):
    _, client = api
    assert client.get('/api/v1/akten/sachen', params={'art': 'tier'}).status_code == 422
    assert client.get('/api/v1/akten/akte', params={'sache': 'unsinn'}).status_code == 422
    assert client.get('/api/v1/akten/akte', params={'sache': 'ort:nirgends'}).status_code == 404
    assert client.get('/api/v1/akten/quellen/e-gibtesnicht').status_code == 404
    assert client.put('/api/v1/akten/quellen/e-gibtesnicht/zuordnung', json={'sache': 'ort:x', 'aktion': 'zu'}).status_code == 404
    assert client.put('/api/v1/akten/quellen/e-x/zuordnung', json={'sache': 'ort:x', 'aktion': 'vielleicht'}).status_code == 422
    assert client.delete('/api/v1/akten/quellen/e-x/zuordnung', params={'sache': 'ort:x'}).status_code == 404
    assert client.get('/api/v1/akten/sachen').status_code == 200
    assert client.get('/api/v1/akten/sachen', headers={'X-Icarus-Token': 'falsch'}).status_code in (401, 403)


def test_zuordnung_setzen_und_entfernen_wirkt_auf_akte_und_liste(api):
    app, client = api
    e = _quelle(app, 'Notiz', [('Kurze Notiz zur Sache.', 'fact')], tage=2)
    abgleichen(client)
    antwort = client.put(f'/api/v1/akten/quellen/{e.id}/zuordnung', json={'sache': 'ort:mainz', 'aktion': 'zu'}).json()
    assert {b['sache']: b['grundlagen'] for b in antwort['bezuege']}['ort:mainz'] == ['nutzer']
    akte = client.get('/api/v1/akten/akte', params={'sache': 'ort:mainz'}).json()
    assert akte['verlauf']['gesamt'] == 1 and akte['verlauf']['eintraege'][0]['grundlagen'] == ['nutzer']
    # Ablehnen einer gefundenen Verknüpfung nimmt die Quelle aus der Akte der Person.
    person = 'person:a:anna@agentur.example'
    assert client.get('/api/v1/akten/akte', params={'sache': person}).status_code == 200
    client.put(f'/api/v1/akten/quellen/{e.id}/zuordnung', json={'sache': person, 'aktion': 'nicht'})
    assert client.get('/api/v1/akten/akte', params={'sache': person}).status_code == 404
    rueck = client.delete(f'/api/v1/akten/quellen/{e.id}/zuordnung', params={'sache': person}).json()
    assert person in {b['sache'] for b in rueck['bezuege']}
    assert client.get('/api/v1/akten/akte', params={'sache': person}).status_code == 200
    assert client.delete(f'/api/v1/akten/quellen/{e.id}/zuordnung', params={'sache': person}).status_code == 404


def test_entzogene_quelle_verschwindet_aus_akte_und_bezuegen(api):
    app, client = api
    e = _quelle(app, 'Notiz', [('Text zur Sache.', 'fact')], tage=2)
    abgleichen(client)
    person = 'person:a:anna@agentur.example'
    assert client.get('/api/v1/akten/akte', params={'sache': person}).status_code == 200
    app.state.episodes.ignore(e.id)
    assert client.get('/api/v1/akten/akte', params={'sache': person}).status_code == 404
    assert client.get(f'/api/v1/akten/quellen/{e.id}').status_code == 404
    assert client.put(f'/api/v1/akten/quellen/{e.id}/zuordnung', json={'sache': 'ort:x', 'aktion': 'zu'}).status_code == 404
    assert client.get('/api/v1/akten/sachen').json()['gesamt'] == 0


def test_erledigte_aufgabe_der_quelle_erledigt_die_bitte_in_der_akte(api):
    app, client = api
    projekt = _projekt(app, 'Mainz')
    e = _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id, tage=3)
    aufgabe = app.state.tasks.add('Druckdaten schicken', Provenance(SourceType.USER_STATED, source_ref=f'episode:{e.id}'),
                                  project_id=projekt.id)
    sache = f'projekt:{projekt.id}'
    akte = client.get('/api/v1/akten/akte', params={'sache': sache, 'warten': True}).json()
    assert akte['offen']['eintraege'][0]['aufgabe']['id'] == aufgabe.id
    assert [a['title'] for a in akte['aufgaben']['eintraege']] == ['Druckdaten schicken']
    app.state.tasks.complete(aufgabe.id)
    akte = client.get('/api/v1/akten/akte', params={'sache': sache}).json()
    assert akte['offen']['gesamt'] == 0 and akte['offen']['erledigt']['eintraege'][0]['grund'] == 'aufgabe_erledigt'


def test_projekt_und_person_zeigen_dieselbe_akte_wie_jede_andere_sache(api):
    app, client = api
    projekt = _projekt(app, 'Mainz')
    _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id, tage=5)
    _quelle(app, 'Antwort', [(ERLEDIGT, 'status')], 'Ben <ben@druck.example>', projekt.id, tage=2)
    abgleichen(client)
    akte = client.get('/api/v1/akten/akte', params={'sache': f'projekt:{projekt.id}'}).json()
    # Die spätere Statusmeldung nennt „erhalten“ und den Gegenstand: die Bitte gilt als erledigt.
    assert akte['offen']['gesamt'] == 0 and akte['offen']['erledigt']['gesamt'] == 1
    assert akte['stand_der_dinge']['aktuell']['text'] == ERLEDIGT
    assert {b['name'] for b in akte['beteiligte']['eintraege'] if b['art'] == 'person'} == {'Anna Keller', 'Ben'}
    # Die Mappe (Kurzansicht) bleibt kompatibel erreichbar.
    mappe = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
    assert mappe['bitten_und_zusagen']['gesamt'] == 1


def test_rest_rechnet_ein_hintergrundfaden_zu_ende_und_die_antwort_nennt_offenes(api, monkeypatch):
    app, client = api
    for n in range(3):
        _quelle(app, f'Q{n}', [(f'Angabe Nummer {n}.', 'fact')], f'P{n} <p{n}@f{n}.example>', tage=n + 1)
    monkeypatch.setattr(akten_routes, 'FRIST_S', 0.0)
    antwort = client.get('/api/v1/akten/sachen').json()
    assert antwort['berechnung']['offen'] > 0  # ehrlich: noch nicht alles berechnet
    app.state.akten_faden.join(timeout=20)
    monkeypatch.setattr(akten_routes, 'FRIST_S', 5.0)
    antwort = client.get('/api/v1/akten/sachen', params={'limit': 200}).json()
    assert antwort['berechnung']['offen'] == 0 and antwort['gesamt'] >= 6


def test_unveraenderter_stand_wird_nicht_nochmal_abgeglichen_eine_aenderung_schon(api, monkeypatch):
    from icarus_memory.bezuege import Bezuege
    app, client = api
    _quelle(app, 'Erste', [('Eine Angabe.', 'fact')], tage=2)
    aufrufe = []
    echt = Bezuege.aktualisieren
    monkeypatch.setattr(Bezuege, 'aktualisieren', lambda self, **kw: aufrufe.append(kw) or echt(self, **kw))
    client.get('/api/v1/akten/sachen')
    assert len(aufrufe) == 1
    client.get('/api/v1/akten/sachen')
    client.get('/api/v1/akten/akte', params={'sache': 'person:a:anna@agentur.example'})
    assert len(aufrufe) == 1, 'derselbe Stand: kein zweiter Abgleich'
    _quelle(app, 'Zweite', [('Noch eine Angabe.', 'fact')], tage=1)
    client.get('/api/v1/akten/sachen')
    assert len(aufrufe) == 2, 'neue Quelle: Abgleich'


def test_gleichzeitige_anstoesse_starten_nur_einen_hintergrundneuaufbau(api, monkeypatch):
    from icarus_memory.bezuege import Bezuege
    app, _client = api
    frei = threading.Event()
    hintergrund = []

    def gebremst(self, **kw):
        if 'frist_s' in kw:
            time.sleep(0.05)  # alle Anstöße sehen „offen“ und stehen zugleich vor der Prüfung des Fadens
            return {'offen': 3, 'berechnet': 0}
        hintergrund.append(threading.current_thread().name)
        frei.wait(10)
        return {'offen': 0, 'berechnet': 3}

    monkeypatch.setattr(Bezuege, 'aktualisieren', gebremst)
    start = threading.Barrier(8)
    fehler = []

    def anstoss():
        try:
            start.wait(5)
            akten_routes.nachfuehren(app)
        except Exception as exc:  # noqa: BLE001 - im Hauptfaden melden
            fehler.append(exc)

    faeden = [threading.Thread(target=anstoss) for _ in range(8)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(10)
    time.sleep(0.2)  # ein zweiter, fälschlich gestarteter Faden hätte sich inzwischen eingetragen
    try:
        assert fehler == []
        assert hintergrund == ['akten-bezuege'], f'{len(hintergrund)} Neuaufbauten gestartet'
    finally:
        frei.set()
        app.state.akten_faden.join(10)
