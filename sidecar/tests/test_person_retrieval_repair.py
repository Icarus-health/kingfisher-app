"""Bestätigte Identität gilt auch beim Abruf; ein Kurzname rät keine Person."""
from datetime import datetime, timedelta, timezone
from contextlib import nullcontext
from dataclasses import replace
import json

import pytest
from fastapi.testclient import TestClient

from icarus_memory import personen, personenfrage, working_memory_answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.frage import rueckfall
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.working_memory_store import WorkingMemoryStore
from .test_conversation_retraction import _close_app

AT = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)


class Auswahl:
    name = model = 'synthetisch'
    is_local = True

    def __init__(self):
        self.calls = []

    def complete_json(self, messages, **kwargs):
        try:
            packet = json.loads(messages[-1]['content'])
        except ValueError:
            packet = {'question': messages[-1]['content']}
        self.calls.append(packet)
        if 'sources' not in packet:
            return Reply(text=json.dumps({'sachen': ['Alex'], 'zeitraum': 'keiner',
                'absicht': 'fakt', 'suchworte': [], 'umschreibungen': []}))
        return Reply(text=json.dumps({'status': 'source_reports',
            'ids': [row['id'] for row in packet['sources'] if row['id'].startswith('S') and not row.get('andere_person')]}))


@pytest.fixture
def bestand():
    app = create_app()
    provider = Auswahl()
    app.state.agent._provider = provider
    app.state.agent._saetze = False
    app.state.agent._working_memory_search = None
    yield app, provider
    _close_app(app)


def mail(app, name, address, title='Atlas Lieferung', text=None, days=0):
    text = text or f'{name}: {title}: Lieferung am 5. November.'
    return app.state.episodes.record(EpisodeKind.MESSAGE, title, text,
        Provenance(SourceType.EMAIL, 'synthetic:' + title + address, AT),
        occurred_at=AT - timedelta(days=days), participants=[f'{name} <{address}>'])[0]


def einordnen(app):
    memory = WorkingMemoryStore(app.state.episodes)
    for snapshot in memory.pending():
        assert memory.commit(snapshot, [{'start': 0, 'end': len(snapshot.episode.body), 'kind': 'fact'}],
                             model='synthetisch')


def zusammen(app, label='Alex Winter'):
    people = personen.alle(episodes=app.state.episodes, jetzt=AT)
    return app.state.claims.person_merges.confirm({'label': label, 'members': [
        {'id': personen._graph_person_id(person.id), 'label': person.name, 'kind': 'person'}
        for person in people]}, confirmed=True)


def frage(app, text, absicht='fakt'):
    return app.state.agent.answer_memory(text, anfrage=replace(rueckfall(text), absicht=absicht))


def test_kurzer_name_mit_konkreter_frist_fragt_vor_modell_zurueck(bestand):
    app, provider = bestand
    first = mail(app, 'Alex Winter', 'winter@alpha.example')
    second = mail(app, 'Alex Sommer', 'sommer@beta.example', text='Lieferung am 12. November.')
    einordnen(app)
    turn = frage(app, 'Wann ist die Lieferung von Alex?')
    assert turn.context['answer_contract']['status'] == 'meaning_choice'
    assert provider.calls == []
    options = turn.context['meaning_choice']['options']
    assert {tuple(option['ids']) for option in options} == {(first.id,), (second.id,)}
    chosen = app.state.agent.answer_meaning_choice(turn.context['meaning_choice'], 0)
    assert chosen.context['working_answer']['meaning_scope']['chosen'] is True
    assert len(chosen.context['working_answer']['meaning_scope']['ids']) == 1


@pytest.mark.parametrize('question', [
    'Welche Frist hat Alex?', 'Welche Aufgaben hat Alex?',
    'Welche Aufgaben hat Alex aus der Nachricht übernommen?',
    'Welche Aufgaben hat Alex beim Termin übernommen?',
])
def test_betreff_allein_ueberspringt_die_fruehe_personenwahl_nicht(bestand, monkeypatch, question):
    app, provider = bestand
    first = mail(app, 'Alex Winter', 'winter@alpha.example', title='Frist und Aufgaben: Nachricht zum Termin für Projekt Atlas')
    second = mail(app, 'Alex Sommer', 'sommer@beta.example', title='Projekt Birke')
    app.state.agent._frage_anbieter = lambda: provider
    from icarus_memory import working_memory_semantic_runtime
    class Suche:
        def request(self):
            return nullcontext()
        def search(self, *args, **kwargs):
            pytest.fail('Vor der Personenwahl darf keine semantische Suche beginnen.')
    monkeypatch.setattr(working_memory_semantic_runtime, 'search', lambda *_: Suche())
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    response = client.post(f'/api/v1/conversations/{cid}/messages',
                           json={'message': question, 'answer_mode': 'auto'})
    assert response.status_code == 201, response.text
    context = response.json()['context']
    assert context['answer_contract']['status'] == 'meaning_choice'
    assert {tuple(o['ids']) for o in context['meaning_choice']['options']} == {(first.id,), (second.id,)}
    assert provider.calls == []


def test_gespeicherte_stille_personenwahl_wird_nach_neuer_regel_ungueltig(bestand, monkeypatch):
    app, provider = bestand
    mail(app, 'Alex Winter', 'winter@alpha.example', title='Frist geändert')
    mail(app, 'Alex Sommer', 'sommer@beta.example', title='Projekt Birke')
    einordnen(app)
    # Eine frühere Fassung hat ohne Nutzerwahl Winter gewählt. Danach muss auch
    # der gespeicherte Belegrahmen veralten, nicht nur die nächste neue Frage.
    with monkeypatch.context() as legacy:
        legacy.setattr(personenfrage, 'unterscheidet', lambda text, mention, episodes:
                       next(k for k in mention.kandidaten if k.adresse == 'winter@alpha.example'))
        answer = frage(app, 'Welche Frist hat Alex?').context['working_answer']
        assert working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    assert not working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)


def test_dominanz_und_getrennte_zeitraeume_waehlen_keine_person(bestand):
    app, provider = bestand
    for i in range(25):
        mail(app, 'Alex Winter', 'winter@alpha.example', title=f'Atlas Lieferung {i}')
    mail(app, 'Alex Sommer', 'sommer@beta.example', days=250)
    einordnen(app)
    turn = frage(app, 'Was ist mit Alex los?', 'ueberblick')
    assert turn.context['answer_contract']['status'] == 'meaning_choice'
    assert len(turn.context['meaning_choice']['options']) == 2
    assert provider.calls == []


def test_bestaetigte_adressen_gelten_nach_neustart_und_widerruf_trennt(bestand):
    app, provider = bestand
    work = mail(app, 'Alex Winter', 'work@alpha.example', title='Arbeitsbericht', text='Arbeitsbericht fertig.')
    home = mail(app, 'Alex Winter', 'home@beta.example', title='Privatbericht', text='Privatbericht fertig.')
    einordnen(app)
    record = zusammen(app)
    # Zweite Verbindung lädt die tatsächlich gespeicherte Bestätigung.
    path = app.state.claims._path
    app.state.claims.close()
    app.state.claims = ClaimStore(path)
    app.state.agent._knowledge = app.state.claims
    turn = frage(app, 'Was ist mit Alex Winter los?', 'ueberblick')
    assert turn.context['answer_contract']['status'] != 'meaning_choice'
    packet = provider.calls[-1]
    assert {row['text'] for row in packet['sources']} == {'Arbeitsbericht fertig.', 'Privatbericht fertig.'}
    answer = turn.context['working_answer']
    assert working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    app.state.claims.person_merges.undo(record['id'], confirmed=True)
    assert not working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    again = frage(app, 'Was ist mit Alex Winter los?', 'ueberblick')
    assert again.context['answer_contract']['status'] == 'meaning_choice'


def test_auto_gespraech_fragt_vor_frage_modell_und_semantischer_suche(bestand, monkeypatch):
    app, provider = bestand
    mail(app, 'Alex Winter', 'winter@alpha.example')
    mail(app, 'Alex Sommer', 'sommer@beta.example')
    # Keine Einordnung: So würde der normale Einstieg bis zur semantischen Suche laufen.
    app.state.agent._frage_anbieter = lambda: provider
    calls = []
    from icarus_memory import working_memory_semantic_runtime
    class Suche:
        def request(self):
            return nullcontext()
        def search(self, *args, **kwargs):
            calls.append('semantic')
            return []
    monkeypatch.setattr(working_memory_semantic_runtime, 'search', lambda *_: Suche())
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    response = client.post(f'/api/v1/conversations/{cid}/messages',
                           json={'message': 'Wann ist die Lieferung von Alex?', 'answer_mode': 'auto'})
    assert response.status_code == 201, response.text
    context = response.json()['messages'][-1]['metadata']['context']
    assert context['answer_contract']['status'] == 'meaning_choice'
    assert provider.calls == []
    assert calls == []


def test_gespraech_auswahl_und_fortsetzung_bleiben_bei_einer_person(bestand):
    app, provider = bestand
    first = mail(app, 'Alex Winter', 'winter@alpha.example', text='Lieferung am 5. November.')
    second = mail(app, 'Alex Sommer', 'sommer@beta.example', text='Lieferung am 12. November.')
    einordnen(app)
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    base = f'/api/v1/conversations/{cid}'
    response = client.post(base + '/messages', json={'message': 'Wann ist die Lieferung von Alex?'})
    pending = response.json()['context']['meaning_choice']
    index = next(i for i, option in enumerate(pending['options']) if option['ids'] == [second.id])
    chosen = client.post(base + '/messages', json={'message': pending['options'][index]['label'],
                                                  'clarification_choice': index})
    assert chosen.status_code == 201, chosen.text
    scope = chosen.json()['context']['working_answer']['meaning_scope']
    assert scope['chosen'] is True and scope['ids'] == [second.id]
    followup = client.post(base + '/messages', json={'message': 'Und wann genau?'})
    assert followup.status_code == 201, followup.text
    assert followup.json()['context']['working_answer']['meaning_scope']['ids'] == [second.id]
    assert all('5. November' not in row['text'] for packet in provider.calls for row in packet.get('sources', []))
    assert first.id not in scope['ids']


@pytest.mark.parametrize('change', ['merge', 'withdraw'])
def test_gespeicherte_auswahl_wird_nach_identitaetswechsel_oder_entzug_verworfen(bestand, change):
    app, _ = bestand
    first = mail(app, 'Alex Winter', 'winter@alpha.example')
    mail(app, 'Alex Winter', 'sommer@beta.example', text='Lieferung am 12. November.')
    einordnen(app)
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    base = f'/api/v1/conversations/{cid}'
    response = client.post(base + '/messages', json={'message': 'Wann ist die Lieferung von Alex Winter?'})
    pending = response.json()['context']['meaning_choice']
    if change == 'merge':
        zusammen(app)
    else:
        app.state.episodes.ignore(first.id)
    opened = client.get(base).json()['messages'][-1]
    assert opened['metadata']['context']['answer_contract']['status'] == 'meaning_outdated'
    assert 'meaning_choice' not in opened['metadata']['context']
    stale = client.post(base + '/messages', json={'message': pending['options'][0]['label'],
                                                 'clarification_choice': 0})
    assert stale.status_code == 409


def test_bestaetigter_alias_nimmt_alle_aktuellen_adressen_aber_keine_entzogene_quelle(bestand):
    app, provider = bestand
    first = mail(app, 'Alex Winter', 'work@alpha.example', title='Arbeit', text='Arbeitsbericht fertig.')
    second = mail(app, 'A. Winter', 'home@beta.example', title='Privat', text='Privatbericht fertig.')
    einordnen(app)
    zusammen(app, label='Robin Winter')
    turn = frage(app, 'Was hat Robin Winter berichtet?')
    assert turn.context['answer_contract']['status'] == 'working_reports'
    assert {row['text'] for row in provider.calls[-1]['sources']} == {'Arbeitsbericht fertig.', 'Privatbericht fertig.'}
    saved = turn.context['working_answer']
    app.state.episodes.ignore(second.id)
    assert not working_memory_answers._fresh(saved, app.state.episodes, app.state.claims)
    current = frage(app, 'Was hat Robin Winter berichtet?')
    assert current.context['answer_contract']['status'] == 'working_reports'
    assert [row['text'] for row in provider.calls[-1]['sources']] == ['Arbeitsbericht fertig.']
    assert first.id in current.context['working_answer']['person_scope']


def test_einzelperson_und_expliziter_kontext_brauchen_keine_namenswahl(bestand):
    app, provider = bestand
    mail(app, 'Alex Winter', 'winter@alpha.example', title='Lieferung Catering')
    einordnen(app)
    assert frage(app, 'Wann liefert Alex?').context['answer_contract']['status'] == 'working_reports'
    mail(app, 'Alex Sommer', 'sommer@beta.example', title='Lieferung Labor', text='Labor liefert am 12. November.')
    einordnen(app)
    assert frage(app, 'Wann ist die Lieferung von Alex beim Catering?').context['answer_contract']['status'] != 'meaning_choice'
    labor = next(row for row in provider.calls[-1]['sources'] if 'Labor liefert' in row['text'])
    assert labor['andere_person'][0]['adresse_dieser_person'] == 'sommer@beta.example'


def test_auswahlmodell_erhaelt_die_bestaetigte_identitaet(bestand):
    app, provider = bestand
    mail(app, 'Alex Winter', 'work@alpha.example', title='Arbeit', text='Arbeitsbericht fertig.')
    mail(app, 'Alex Winter', 'home@beta.example', title='Privat', text='Privatbericht fertig.')
    einordnen(app)
    zusammen(app)
    original = provider.complete_json
    def nach_bestaetigung(messages, **kwargs):
        packet = json.loads(messages[-1]['content'])
        identities = {row.get('confirmed_person') for row in packet['sources']}
        if len(identities) != 1 or None in identities:
            return Reply(text=json.dumps({'status': 'needs_person_choice', 'ids': ['S1', 'S2']}))
        return original(messages, **kwargs)
    provider.complete_json = nach_bestaetigung
    turn = frage(app, 'Was ist mit Alex Winter los?', 'ueberblick')
    assert turn.context['answer_contract']['status'] == 'working_reports'


def test_gespeicherte_gruppenwahl_gilt_nach_undo_auch_im_gespraech_nicht_mehr(bestand):
    app, _ = bestand
    mail(app, 'Alex Winter', 'work@alpha.example', title='Arbeit')
    mail(app, 'Alex Winter', 'home@beta.example', title='Privat')
    record = zusammen(app)
    mail(app, 'Alex Sommer', 'summer@gamma.example', title='Arbeit und Privat', text='Lieferung im Dezember.')
    einordnen(app)
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    base = f'/api/v1/conversations/{cid}'
    response = client.post(base + '/messages', json={'message': 'Wann ist die Lieferung von Alex?'})
    pending = response.json()['context']['meaning_choice']
    index = next(i for i, option in enumerate(pending['options']) if option['ref'] == record['id'])
    app.state.claims.person_merges.undo(record['id'], confirmed=True)
    opened = client.get(base).json()['messages'][-1]
    assert opened['metadata']['context']['answer_contract']['status'] == 'meaning_outdated'
    assert client.post(base + '/messages', json={'message': pending['options'][index]['label'],
                                                'clarification_choice': index}).status_code == 409


def test_personenantwort_ohne_bedeutungsrahmen_wird_nach_undo_veraltet(bestand):
    app, _ = bestand
    mail(app, 'Alex Winter', 'work@alpha.example', title='Arbeit', text='Arbeitsbericht fertig.', days=1)
    mail(app, 'Alex Winter', 'home@beta.example', title='Privat', text='Privatbericht fertig.')
    einordnen(app)
    record = zusammen(app)
    turn = frage(app, 'Was hat Alex Winter berichtet?')
    answer = turn.context['working_answer']
    assert turn.context['answer_contract']['status'] == 'working_reports'
    assert 'meaning_scope' not in answer
    assert working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    app.state.claims.person_merges.undo(record['id'], confirmed=True)
    assert not working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    legacy = dict(answer)
    legacy.pop('person_identity_basis')
    assert not working_memory_answers._fresh(legacy, app.state.episodes, app.state.claims)


def test_kontext_kennzeichnet_alle_adressen_der_anderen_bestaetigten_person(bestand):
    from icarus_memory import kennzeichnung
    app, _ = bestand
    selected = mail(app, 'Alex Winter', 'work@alpha.example', title='Catering', text='Catering: 30 Euro.')
    mail(app, 'Alex Winter', 'home@beta.example', title='Catering privat', text='Catering: 32 Euro.')
    foreign = mail(app, 'Alex Winter', 'office@gamma.example', title='Institut', text='Institut: Termin im Dezember.')
    mail(app, 'Alex Winter', 'lab@delta.example', title='Institut Labor', text='Labor: Termin im Januar.')
    for addresses in [('work@alpha.example', 'home@beta.example'), ('office@gamma.example', 'lab@delta.example')]:
        app.state.claims.person_merges.confirm({'label': 'Alex Winter', 'members': [
            {'id': personen._graph_person_id('a:' + a), 'kind': 'person', 'label': 'Alex Winter'}
            for a in addresses]}, confirmed=True)
    mixed, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Gruppenmail', 'Beide Personen im Verteiler.',
        Provenance(SourceType.EMAIL, 'synthetic:mixed', AT), occurred_at=AT,
        participants=['Alex Winter <work@alpha.example>', 'Alex Winter <lab@delta.example>'])
    mentions = personenfrage.erwaehnte('Was kostet Catering von Alex Winter?', app.state.episodes,
                                     confirmed_merges=app.state.claims.person_merges.list())
    resolved = personenfrage.gemeinte_unter_namensvettern('Was kostet Catering von Alex Winter?',
                                                        app.state.episodes, erwaehnungen=mentions)
    scope = kennzeichnung.rahmen_der_frage(resolved, None)
    assert kennzeichnung.kennzeichen(selected, scope) == ()
    assert kennzeichnung.kennzeichen(mixed, scope) == ()
    assert kennzeichnung.kennzeichen(foreign, scope)[0].art == kennzeichnung.ANDERE_PERSON
    assert kennzeichnung.Rahmen.aus_dict(scope.als_dict()) == scope


def test_mehrdeutiger_name_in_neuer_aussage_bleibt_gespraechsquelle(bestand):
    from icarus_memory import conversation_memory
    from icarus_memory.episodes import CHAT_LOOKUP_TAG
    app, provider = bestand
    mail(app, 'Alex Winter', 'winter@alpha.example')
    mail(app, 'Alex Sommer', 'sommer@beta.example')
    app.state.agent._frage_anbieter = lambda: None
    provider.complete = lambda *args, **kwargs: Reply(text='Danke für die Nachricht.')
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    response = client.post(f'/api/v1/conversations/{cid}/messages', json={'message': 'Alex hat mich angerufen.'})
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['messages'][0]['metadata']['answer_mode'] == 'chat'
    source = conversation_memory.find(app.state.episodes, cid, data['messages'][0]['id'])
    assert CHAT_LOOKUP_TAG not in source.tags


@pytest.mark.parametrize('confirmed_group', [False, True])
def test_personenwahl_mit_mehr_als_500_quellen_bleibt_anklickbar_und_begrenzt(bestand, confirmed_group):
    app, provider = bestand
    busy = []
    for i in range(501):
        address = 'winter@alpha.example' if not confirmed_group or i < 250 else 'home@alpha.example'
        busy.append(mail(app, 'Alex Winter', address, title=f'Atlas Lieferung {i}', days=i + 1))
    if confirmed_group:
        zusammen(app)
    other = mail(app, 'Alex Sommer', 'sommer@beta.example', text='Lieferung am 12. November.')
    memory = WorkingMemoryStore(app.state.episodes)
    while batch := memory.pending(limit=200):
        for snapshot in batch:
            assert memory.commit(snapshot, [{'start': 0, 'end': len(snapshot.episode.body), 'kind': 'fact'}],
                                 model='synthetisch')
    client = TestClient(app)
    cid = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    base = f'/api/v1/conversations/{cid}'
    asked = client.post(base + '/messages', json={'message': 'Wann ist die Lieferung von Alex?'})
    assert asked.status_code == 201, asked.text
    pending = asked.json()['context']['meaning_choice']
    index = next(i for i, option in enumerate(pending['options']) if busy[0].id in option['ids'])
    assert pending['options'][index]['anzahl'] == 501
    assert provider.calls == []
    opened = client.get(base)
    assert opened.status_code == 200, opened.text
    chosen = client.post(base + '/messages', json={'message': pending['options'][index]['label'],
                                                  'clarification_choice': index})
    reopened_status = opened.json()['messages'][-1]['metadata']['context']['answer_contract']['status']
    assert (reopened_status, chosen.status_code) == ('meaning_choice', 201), chosen.text
    answer = chosen.json()['context']['working_answer']
    scope = answer['meaning_scope']
    assert scope['chosen'] is True and scope['truncated'] is True
    assert len(scope['ids']) == 500
    assert set(scope['ids']) < {episode.id for episode in busy}
    assert other.id not in scope['ids']
    assert all('12. November' not in row['text'] for packet in provider.calls for row in packet['sources'])
    # Eine neue Quelle außerhalb des gewählten, festgehaltenen Rahmens darf
    # dessen weiterhin gültige ältere Quellen nicht aus der Identität verdrängen.
    latest = mail(app, 'Alex Winter', 'winter@alpha.example', title='Atlas Lieferung neu', days=-1)
    snapshot = memory.pending(episode_ids=[latest.id])[0]
    assert memory.commit(snapshot, [{'start': 0, 'end': len(snapshot.episode.body), 'kind': 'fact'}],
                         model='synthetisch')
    assert working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    app.state.episodes.ignore(scope['ids'][0])
    assert not working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
