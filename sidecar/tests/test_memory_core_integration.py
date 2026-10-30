"""Synthetische Gesamtkette mit echten Stores und Gesprächs-/Korrekturrouten.

Nur die Sprachgrenzen sind deterministische Attrappen; Einordnung, Belege,
Aufgabenprüfung, Personenwahl und Wiederöffnen verwenden den Produktcode.
"""
import json
from threading import RLock

from fastapi.testclient import TestClient

from icarus_memory import aufgaben_post, personen
from icarus_memory.aufgaben_von_selbst import Durchlauf
from icarus_memory.config import MailAccountSettings
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStatus
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_worker import Zwischenstand, run
from tests.test_aufgaben_post import ICH, JETZT, LENA, mail
from tests.test_aufgaben_von_selbst import vorschlag
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _ask, _conversation
from tests.test_source_correction_flow import preview, submit

WORK = 'Alex Winter <alex.work@alpha.example>'
HOME = 'Alex Winter <alex.home@beta.example>'
OTHER = 'Alex Sommer <alex.sommer@gamma.example>'
REQUEST = 'Bitte schicke mir die Druckdaten bis zum 5. November 2026.'
ACCESS = 'Atlas Zugang liegt im blauen Fach.'
CORRECTED = 'Atlas Zugang liegt jetzt im grünen Fach.'
PROMISE = 'Die Druckdaten sind noch nicht fertig. Ich werde sie nächste Woche schicken.'


class Sprache:
    """Feste Eingaben an den bestehenden Klassifizierungs-/Auswahlvertrag."""
    name = model = 'synthetische-integration'
    is_local = True

    def __init__(self):
        self.calls = []

    def complete_json(self, messages, **kwargs):
        packet = json.loads(messages[-1]['content'])
        self.calls.append(packet)
        if 'blocks' in packet:
            kinds = {REQUEST: 'request', ACCESS: 'fact', PROMISE: 'status'}
            return Reply(text=json.dumps({'items': {
                block['block_id']: kinds.get(block['text'], 'fact')
                for block in packet['blocks']}}))
        if 'sources' in packet:
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [
                row['id'] for row in packet['sources']
                if row['id'].startswith('S') and not row.get('andere_person')]}))
        # Der Fragetext darf bei diesen eindeutigen Routen keine Person raten.
        return Reply(text=json.dumps({'sachen': ['Alex'], 'zeitraum': 'keiner',
            'absicht': 'fakt', 'suchworte': [], 'umschreibungen': []}))


def _app():
    app = create_app()
    provider = Sprache()
    app.state.agent._provider = provider
    app.state.agent._saetze = False
    app.state.agent._working_memory_search = None
    app.state.agent._frage_anbieter = lambda: None
    app.state.settings.mail_accounts.append(MailAccountSettings(
        id='synthetic', label='Probe', imap_host='127.0.0.1', user=ICH, sender=ICH))
    return app, TestClient(app), provider


def _classify(app, provider, sources):
    result = run(app.state.episodes, provider, RLock(),
                 source_ids=[source.id for source in sources], stand=Zwischenstand())
    assert result.ok, result
    memory = WorkingMemoryStore(app.state.episodes)
    for source in sources:
        refs = memory.source_refs(episode_ids=[source.id])['refs']
        assert refs
        for ref in refs:
            snapshot = memory.resolve(ref)
            assert snapshot is not None
            assert snapshot.episode.body[ref['start']:ref['end']] == source.body
    return memory


def _choose(client, base, response, source_ids):
    assert response.status_code == 201, response.text
    context = response.json()['context']
    assert context['answer_contract']['status'] == 'meaning_choice'
    pending = context['meaning_choice']
    index = next(i for i, option in enumerate(pending['options'])
                 if set(option['ids']) == set(source_ids))
    chosen = client.post(base + '/messages', json={
        'message': pending['options'][index]['label'], 'clarification_choice': index})
    assert chosen.status_code == 201, chosen.text
    answer = chosen.json()['messages'][-1]
    scope = answer['metadata']['context']['working_answer']['meaning_scope']
    assert scope['chosen'] is True and set(scope['ids']) == set(source_ids)
    return answer


def test_intake_classification_task_person_choice_correction_withdrawal_restart_and_undo(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'data'))
    app, client, provider = _app()
    try:
        # Bestehender Mail-Aufnahmehelfer: Original, Rollen und Kopfzeilenbezug
        # landen unverändert in der echten EpisodeStore, nicht in Suchattrappen.
        post = aufgaben_post.Lauf(app.state.tasks, app.state.episodes, app.state.proposals,
                                  eigene=lambda: [ICH], jetzt=lambda: JETZT)
        post.schritt()  # Der bisherige Bestand wird nicht nachträglich verarbeitet.
        request = mail(app.state.episodes, 'Druckdaten', REQUEST, von=WORK, an=[LENA],
                       kennung='request', tage=1)
        home = mail(app.state.episodes, 'Druckdaten privat', 'Die Druckdaten betreffen Atlas.',
                    von=HOME, an=[LENA], kennung='home')
        access = mail(app.state.episodes, 'Atlas Zugang', ACCESS, von=HOME, an=[LENA],
                      kennung='access')
        other = mail(app.state.episodes, 'Druckdaten',
                     'Bitte schicke mir die Druckdaten bis zum 12. November 2026.',
                     von=OTHER, an=[LENA], kennung='other')
        memory = _classify(app, provider, [request, home, access, other])
        request_refs = memory.source_refs(episode_ids=[request.id])['refs']
        assert request_refs[0]['kind'] == 'request'

        # Fester, geprüfter Sprachvorschlag wie im bestehenden Aufnahmetest;
        # Annahme, Person, Quelle und Frist berechnet der reale Aufgabenlauf.
        candidate = vorschlag(app.state.proposals, app.state.episodes, request,
                             'Druckdaten an Alex schicken', REQUEST)
        tasks = Durchlauf(app.state.tasks, app.state.episodes, app.state.proposals,
                          workspace=app.state.workspace, eigene=lambda: [ICH], jetzt=lambda: JETZT)
        assert tasks.schritt()['angelegt'] == 1
        task = app.state.tasks.get('t-suggestion-' + candidate.id)
        assert task.status is TaskStatus.OPEN
        assert task.person['adresse'] == 'alex.work@alpha.example'
        assert task.provenance.source_ref == 'episode:' + request.id
        assert task.due.date().isoformat() == '2026-11-05'

        cid = _conversation(client)
        base = '/api/v1/conversations/' + cid
        before = len(provider.calls)
        response = client.post(base + '/messages', json={
            'message': 'Bis wann will Alex die Druckdaten?', 'answer_mode': 'auto'})
        assert response.json()['context']['answer_contract']['status'] == 'meaning_choice'
        assert len(provider.calls) == before  # Klärung vor Sprach-/Sucharbeit.
        first = _choose(client, base, response, [request.id])
        assert REQUEST in first['content'] and '12. November' not in first['content']

        # Eine ausdrückliche Bestätigung, keine angenommene Adresschronologie.
        merge_base = '/api/v1/memory/person-merges'
        selection = {'member_ids': [personen._graph_person_id('a:' + address) for address in
                     ('alex.work@alpha.example', 'alex.home@beta.example')], 'label': 'Alex Winter'}
        prepared = client.post(merge_base + '/preview', json=selection)
        assert prepared.status_code == 200, prepared.text
        merged = client.post(merge_base, json={**selection,
            'preview_token': prepared.json()['preview_token'], 'confirmed': True})
        assert merged.status_code == 201, merged.text
        merge_id = merged.json()['id']
        person = client.get('/people/Alex Winter')
        assert person.status_code == 200, person.text
        assert set(person.json()['adressen']) == {'alex.work@alpha.example', 'alex.home@beta.example'}
        assert person.json()['episoden_anzahl'] == 3
        group_cid = _conversation(client)
        group_base = '/api/v1/conversations/' + group_cid
        asked = client.post(group_base + '/messages', json={
            'message': 'Was hat Alex berichtet?', 'answer_mode': 'auto'})
        assert len(asked.json()['context']['meaning_choice']['options']) == 2
        answer = _choose(client, group_base, asked, [request.id, home.id, access.id])
        refs = answer['metadata']['context']['working_answer']['refs']
        assert {ref['episode_id'] for ref in refs} == {request.id, home.id, access.id}
        assert ACCESS in answer['content'] and 'Zugangskarte' not in answer['content']
        assert other.id not in {ref['episode_id'] for ref in refs}
        for ref in refs:
            source = client.get('/api/v1/episodes/' + ref['episode_id'])
            assert source.status_code == 200, source.text
            snapshot = memory.resolve(ref)
            assert snapshot is not None
            assert source.json()['body'][ref['start']:ref['end']] in answer['content']

        # Eine unfertige Zusage erledigt auch im gemeinsamen Bestand nichts.
        promise = mail(app.state.episodes, 'AW: Druckdaten', PROMISE, von=LENA, an=[WORK],
                       kennung='promise', antwort_auf=['request'])
        _classify(app, provider, [promise])
        assert memory.source_refs(episode_ids=[promise.id])['refs'][0]['kind'] == 'status'
        assert post.schritt()['erledigt'] == 0
        assert app.state.tasks.get(task.id).status is TaskStatus.OPEN
        [pending] = client.get('/api/v1/aufgaben-post/vorschlaege').json()['items']
        assert pending['aufgabe']['id'] == task.id
        assert 'an Alex Winter geschrieben' in pending['satz']

        correction = submit(client, access.id, preview(client, access.id), CORRECTED)
        assert correction.status_code == 201, correction.text
        correction_id = correction.json()['episode_id']
        assert app.state.episodes.get(access.id).body == ACCESS  # Original bleibt.
        old = client.get(group_base).json()['messages'][-1]
        assert ACCESS not in old['content']
        corrected_cid = _conversation(client)
        current = _ask(client, corrected_cid, 'Was steht zu "Atlas Zugang" in meinen Quellen?')
        assert CORRECTED in current['content'] and ACCESS not in current['content']
        current_refs = current['metadata']['context']['source_answer']['refs']
        assert {ref['episode_id'] for ref in current_refs} == {correction_id}
        assert client.post('/api/v1/episodes/' + correction_id + '/ignore').status_code == 200
        withdrawn = client.get('/api/v1/conversations/' + corrected_cid).json()['messages'][-1]
        assert CORRECTED not in withdrawn['content']
        assert app.state.tasks.get(task.id).status is TaskStatus.OPEN
        due = task.due
    finally:
        client.close()
        _close_app(app)

    # Tatsächlich neue App/Store-Verbindungen zum selben synthetischen Bestand.
    reopened, client, _ = _app()
    try:
        assert reopened.state.tasks.get(task.id).status is TaskStatus.OPEN
        assert reopened.state.tasks.get(task.id).due == due
        assert client.get(merge_base).json()['merges'][0]['undone_at'] is None
        assert set(client.get('/people/Alex Winter').json()['adressen']) == {
            'alex.work@alpha.example', 'alex.home@beta.example'}
        assert WorkingMemoryStore(reopened.state.episodes).source_refs(
            episode_ids=[access.id, correction_id])['refs'] == []
        assert CORRECTED not in str(client.get('/api/v1/conversations/' + corrected_cid).json())
        assert ACCESS not in client.get(group_base).json()['messages'][-1]['content']
        assert client.post(merge_base + '/' + merge_id + '/undo', json={'confirmed': True}).status_code == 200
        ask = client.post('/api/v1/conversations/' + _conversation(client) + '/messages', json={
            'message': 'Was hat Alex Winter zu den Druckdaten berichtet?', 'answer_mode': 'auto'})
        assert ask.status_code == 201, ask.text
        options = ask.json()['context']['meaning_choice']['options']
        assert {frozenset(option['ids']) for option in options} == {
            frozenset([request.id, promise.id]), frozenset([home.id])}
        # Erst der explizite Klick darf erledigen; Rückgängig trennt diese Mail.
        [pending] = client.get('/api/v1/aufgaben-post/vorschlaege').json()['items']
        accepted = client.post('/api/v1/aufgaben-post/vorschlaege/' + pending['id'] + '/annehmen')
        assert accepted.status_code == 200 and accepted.json()['status'] == 'done'
        undone = client.post('/api/v1/tasks/' + task.id + '/rueckgaengig')
        assert undone.status_code == 200 and undone.json()['status'] == 'open'
        assert reopened.state.tasks.get(task.id).due == due
        assert reopened.state.tasks.post_getrennt(task.id, promise.id)
        assert aufgaben_post.lauf_fuer(reopened).verarbeiten(
            reopened.state.episodes.get(promise.id)) == {'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
        assert aufgaben_post.lauf_fuer(reopened).schritt()['erledigt'] == 0
    finally:
        client.close()
        _close_app(reopened)
