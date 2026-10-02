"""Rückfragen nach Person oder Vorgang lassen sich mit einem Klick beantworten."""
import json

from icarus_memory import conversation_memory
from icarus_memory.episodes import CHAT_LOOKUP_TAG, EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation

QUESTION = 'Was hat Jonas Weller zur Musterlieferung mitgeteilt?'
NORD = 'Zur Musterlieferung: Die Prüfmuster gehen am 12. November an Werk Nord.'
SUED = 'Zur Musterlieferung: Die Prüfmuster gehen am 18. November an Werk Süd zurück.'


def _mail(app, title, body, sender):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, title, body,
        Provenance(SourceType.EMAIL, source_ref=f'work:<{len(body)}-{title}@example.invalid>'),
        participants=[sender])
    store = WorkingMemoryStore(app.state.episodes)
    pending = store.pending(episode_ids=[episode.id])[0]
    assert store.commit(pending, [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='local-test')
    return episode


def _selector(provider, status):
    calls = []

    def complete_json(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        calls.append(data)
        return Reply(text=json.dumps({'status': status, 'ids': [row['id'] for row in data['sources']]}))
    provider.complete_json = complete_json
    return calls


def _choose(client, conversation, index, label):
    return client.post(f'/api/v1/conversations/{conversation}/messages',
                       json={'message': label, 'clarification_choice': index})


def test_person_question_offers_senders_and_click_answers_without_model(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        nord = _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        calls = _selector(provider, 'needs_person_choice')
        conversation = _conversation(client)
        asked = _ask(client, conversation, QUESTION)
        context = asked['metadata']['context']
        assert context['answer_contract']['status'] == 'working_unclear'
        labels = sorted(option['label'] for option in context['clarification_choices'])
        assert labels == ['Jonas Weller <jonas@nord.example> · Vorgang 4831',
                          'Jonas Weller <weller@sued.example> · Vorgang 9584']
        index = [option['label'] for option in context['clarification_choices']].index(
            'Jonas Weller <jonas@nord.example> · Vorgang 4831')
        selections = len(calls)
        claims_before = app.state.claims.revision

        response = _choose(client, conversation, index, 'Jonas Weller <jonas@nord.example> · Vorgang 4831')
        assert response.status_code == 201, response.text
        messages = response.json()['messages']
        answer = messages[-1]
        assert answer['metadata']['context']['answer_contract']['status'] == 'working_reports'
        assert 'Deine Auswahl: Jonas Weller <jonas@nord.example> · Vorgang 4831' in answer['content']
        assert NORD in answer['content'] and SUED not in answer['content']
        assert [link['episode_id'] for link in answer['metadata']['context']['source_links']] == [nord.id]
        assert 'clarification_choices' not in answer['metadata']['context']
        # Die Auswahl ist eindeutig: kein neuer Modellaufruf, keine neue Aussage.
        assert len(calls) == selections
        assert app.state.claims.revision == claims_before
        assert messages[-2]['role'] == 'user' and messages[-2]['metadata']['clarification_choice'] == index
        # Der Klick ist keine neue Aussage: nur als Abfragezeile markiert.
        clicked = conversation_memory.find(app.state.episodes, conversation, messages[-2]['id'])
        assert CHAT_LOOKUP_TAG in clicked.tags
    finally:
        client.close()
        _close_app(app)


def test_stale_or_mismatched_choice_is_refused(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        nord = _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        _selector(provider, 'needs_person_choice')
        conversation = _conversation(client)
        options = _ask(client, conversation, QUESTION)['metadata']['context']['clarification_choices']
        count = len(app.state.conversations.messages(conversation))
        # Beschriftung passt nicht zur Nummer: nichts wird geschrieben.
        assert _choose(client, conversation, 0, 'Jemand anderes').status_code == 409
        assert _choose(client, conversation, 5, options[0]['label']).status_code == 409
        # Eine entzogene Quelle macht die Auswahl ungültig.
        app.state.episodes.ignore(nord.id)
        assert _choose(client, conversation, 0, options[0]['label']).status_code == 409
        assert len(app.state.conversations.messages(conversation)) == count
    finally:
        client.close()
        _close_app(app)


def test_project_question_uses_source_titles(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mail(app, 'Projekt Orion', 'Lena Vogt bittet um eine überarbeitete Keramikprobe.', 'Lena Vogt <lena@orion.example>')
        _mail(app, 'Projekt Atlas', 'Lena Vogt hat die Keramikproben freigegeben.', 'Lena Vogt <lena@orion.example>')
        _selector(provider, 'needs_project_choice')
        conversation = _conversation(client)
        asked = _ask(client, conversation, 'Was hat Lena Vogt zur Keramikprobe entschieden?')
        options = [option['label'] for option in asked['metadata']['context']['clarification_choices']]
        assert sorted(options) == ['Projekt Atlas', 'Projekt Orion']
        response = _choose(client, conversation, options.index('Projekt Atlas'), 'Projekt Atlas')
        assert response.status_code == 201, response.text
        content = response.json()['messages'][-1]['content']
        assert 'freigegeben' in content and 'überarbeitete' not in content
    finally:
        client.close()
        _close_app(app)


def test_no_choices_without_a_distinguishing_feature(core, tmp_path, monkeypatch):
    # Gleicher Absender: Eine Auswahl würde nichts unterscheiden.
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <jonas@nord.example>')
        _selector(provider, 'needs_person_choice')
        asked = _ask(client, _conversation(client), QUESTION)
        assert asked['metadata']['context']['answer_contract']['status'] == 'working_unclear'
        assert 'clarification_choices' not in asked['metadata']['context']
    finally:
        client.close()
        _close_app(app)


def test_reopened_conversation_keeps_choices_only_while_current(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        nord = _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        _selector(provider, 'needs_person_choice')
        conversation = _conversation(client)
        _ask(client, conversation, QUESTION)
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert len(reopened['metadata']['context']['clarification_choices']) == 2
        app.state.episodes.ignore(nord.id)
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert 'clarification_choices' not in reopened['metadata']['context']
    finally:
        client.close()
        _close_app(app)


def test_conflict_choice_applies_only_to_this_answer(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mail(app, 'Lieferant', 'Die Keramikproben kommen am 12. Oktober 2026.', 'Lieferant <l@example.invalid>')
        _mail(app, 'Einkauf', 'Die Keramikproben kommen am 14. Oktober 2026.', 'Einkauf <e@example.invalid>')
        calls = _selector(provider, 'unresolved_conflicting_sources')
        conversation = _conversation(client)
        asked = _ask(client, conversation, 'Wann kommen die Keramikproben?')
        options = [option['label'] for option in asked['metadata']['context']['clarification_choices']]
        assert sorted(options) == ['Die Keramikproben kommen am 12. Oktober 2026.',
                                   'Die Keramikproben kommen am 14. Oktober 2026.']
        selections, claims_before = len(calls), app.state.claims.revision
        chosen = 'Die Keramikproben kommen am 14. Oktober 2026.'
        response = _choose(client, conversation, options.index(chosen), chosen)
        assert response.status_code == 201, response.text
        content = response.json()['messages'][-1]['content']
        assert '14. Oktober' in content and '12. Oktober' not in content
        assert 'Gilt nur für diese Antwort' in content
        assert len(calls) == selections and app.state.claims.revision == claims_before
        # Die andere Quelle bleibt unverändert auffindbar.
        again = _ask(client, _conversation(client), 'Wann kommen die Keramikproben?')
        assert '12. Oktober' in again['content'] and '14. Oktober' in again['content']
    finally:
        client.close()
        _close_app(app)


def test_conflict_with_confirmed_claim_offers_no_click(monkeypatch):
    from types import SimpleNamespace
    from icarus_memory import working_memory_answers

    class Store:
        def __init__(self, episodes):
            pass

        def resolve(self, ref):
            body = ref['text']
            return SimpleNamespace(episode=SimpleNamespace(body=body, title='T', participants=[]))
    monkeypatch.setattr(working_memory_answers, 'WorkingMemoryStore', Store)
    refs = [{'text': 'Termin am 12. Oktober.', 'start': 0, 'end': 22},
            {'text': 'Termin am 14. Oktober.', 'start': 0, 'end': 22}]
    answer = {'status': 'unclear', 'uncertainty': 'conflict', 'refs': refs, 'claim_basis': {}}
    assert len(working_memory_answers.choices(answer, episodes=None)) == 2
    # Mit bestätigter Aussage entscheidet deren eigene Prüfung, nicht ein Klick.
    answer['claim_basis'] = {'c-1': {}}
    assert working_memory_answers.choices(answer, episodes=None) == []


def _relative_source(app):
    body = 'Wir können die Gussprobe nächsten Freitag liefern.'
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Gussprobe', body,
        Provenance(SourceType.EMAIL, source_ref='work:<guss@example.invalid>'),
        participants=['Werk <werk@example.invalid>'])
    store = WorkingMemoryStore(app.state.episodes)
    assert store.commit(store.pending(episode_ids=[episode.id])[0],
                        [{'start': 0, 'end': len(body), 'kind': 'commitment'}], model='local-test')
    return episode


def _send_date(client, conversation, value, message=None):
    from datetime import date
    stated = date.fromisoformat(value)
    return client.post(f'/api/v1/conversations/{conversation}/messages', json={
        'message': message or f"Die Nachricht stammt vom {stated.strftime('%d.%m.%Y')}.",
        'clarification_date': value})


def test_time_question_takes_a_date_without_model_or_calculation(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        episode = _relative_source(app)
        calls = _selector(provider, 'needs_missing_time_reference')
        conversation = _conversation(client)
        asked = _ask(client, conversation, 'An welchem Datum kommt die Gussprobe?')
        assert asked['metadata']['context']['clarification_date'] is True
        selections = len(calls)
        response = _send_date(client, conversation, '2026-09-22')
        assert response.status_code == 201, response.text
        messages = response.json()['messages']
        content = messages[-1]['content']
        assert messages[-1]['metadata']['context']['answer_contract']['status'] == 'working_reports'
        assert 'Nach deiner Angabe stammt die Nachricht vom 22.09.2026.' in content
        assert 'nächsten Freitag' in content
        # Kein berechnetes Kalenderdatum, kein Modellaufruf, keine geänderte Quelle.
        assert '25.09.2026' not in content and '2. Oktober' not in content
        assert len(calls) == selections
        assert app.state.episodes.get(episode.id).occurred_at is None
        assert 'clarification_date' not in messages[-1]['metadata']['context']
        assert messages[-2]['metadata']['clarification_date'] == '2026-09-22'
    finally:
        client.close()
        _close_app(app)


def test_mismatched_or_future_date_is_refused(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _relative_source(app)
        _selector(provider, 'needs_missing_time_reference')
        conversation = _conversation(client)
        _ask(client, conversation, 'An welchem Datum kommt die Gussprobe?')
        count = len(app.state.conversations.messages(conversation))
        assert _send_date(client, conversation, '2026-09-22', 'Irgendwann.').status_code == 409
        assert _send_date(client, conversation, '2999-01-01').status_code == 409
        assert client.post(f'/api/v1/conversations/{conversation}/messages', json={
            'message': 'x', 'clarification_date': '2026-09-22', 'clarification_choice': 0}).status_code == 422
        assert len(app.state.conversations.messages(conversation)) == count
    finally:
        client.close()
        _close_app(app)
