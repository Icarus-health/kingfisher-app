"""Eine veraltete Antwort lässt sich mit einem Klick neu beantworten."""
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation
from tests.test_working_memory_choices import NORD, SUED, QUESTION, _mail, _selector
from tests.test_working_memory_choices import _choose
from icarus_memory import personen


def _messages(client, conversation):
    return client.get(f'/api/v1/conversations/{conversation}').json()['messages']


def test_stale_answer_offers_refresh_with_original_question(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        nord = _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        sued = _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        west = _mail(app, 'Vorgang 7000', 'Zur Musterlieferung: Die Prüfmuster gehen an Werk West.',
                     'Jonas Weller <jw@west.example>')
        calls = _selector(provider, 'source_reports')
        conversation = _conversation(client)
        asked = _ask(client, conversation, QUESTION)
        pending = asked['metadata']['context']['meaning_choice']
        assert calls == []
        index = next(i for i, option in enumerate(pending['options']) if option['ids'] == [nord.id])
        selected = _choose(client, conversation, index, pending['options'][index]['label'])
        assert selected.status_code == 201, selected.text
        answer = selected.json()['messages'][-1]
        assert NORD in answer['content'] and SUED not in answer['content']
        context = answer['metadata']['context']
        assert context['original_question'] == QUESTION
        assert context['refresh_available'] is False

        # Echte Identitätsänderung: Der zuvor gewählte Einzelanker ist nun Teil
        # einer bestätigten Gruppe. Ein bloßer neuer Namensvetter genügt nicht.
        merge = app.state.claims.person_merges.confirm({'label': 'Jonas Weller', 'members': [
            {'id': personen._graph_person_id('a:' + address), 'kind': 'person', 'label': 'Jonas Weller'}
            for address in ['jonas@nord.example', 'weller@sued.example']]}, confirmed=True)
        stale = _messages(client, conversation)[-1]
        assert stale['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert stale['metadata']['context']['refresh_available'] is True
        assert 'Werk Nord' not in stale['content']

        response = client.post(f'/api/v1/conversations/{conversation}/messages',
                               json={'message': stale['metadata']['context']['original_question'],
                                     'new_question': True})
        assert response.status_code == 201
        fresh = response.json()['messages'][-1]
        fresh_context = fresh['metadata']['context']
        assert fresh_context['answer_contract']['status'] == 'meaning_choice'
        assert fresh_context.get('refresh_available') is not True
        options = fresh_context['meaning_choice']['options']
        assert len(options) == 2
        index = next(i for i, option in enumerate(options) if option['ref'] == merge['id'])
        assert set(options[index]['ids']) == {nord.id, sued.id}
        assert next(option for option in options if option['ids'] == [west.id])
        chosen = _choose(client, conversation, index, options[index]['label'])
        assert chosen.status_code == 201, chosen.text
        reply = chosen.json()['messages'][-1]
        assert NORD in reply['content'] and SUED in reply['content']
        assert 'Werk West' not in reply['content']
        assert reply['metadata']['context']['refresh_available'] is False
        # Die frühere Antwort bleibt als veraltet im Verlauf stehen.
        previous = next(message for message in _messages(client, conversation) if message['id'] == answer['id'])
        assert previous['metadata']['context']['refresh_available'] is True
    finally:
        client.close()
        _close_app(app)


def test_followup_answer_is_not_offered_for_refresh(core, tmp_path, monkeypatch):  # noqa: F811
    from icarus_memory.working_memory_answers import original_question
    assert original_question({'query': 'und Ben?', 'retrieval_query': 'Wann liefert Ben?'}) is None
    assert original_question({'query': '   '}) is None
    assert original_question({'query': 'x' * 2001}) is None
    assert original_question({'query': ' Wann liefert Anna? '}) == 'Wann liefert Anna?'
    assert original_question(None) is None


def test_clarified_question_offers_the_original_question():
    from icarus_memory.working_memory_answers import original_question
    assert original_question({'query': 'Wann?\nPräzisierung des Nutzers: Nord'}) == 'Wann?'


def test_stale_person_choice_offers_refresh_after_source_withdrawal(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        nord = _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        sued = _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        calls = _selector(provider, 'source_reports')
        conversation = _conversation(client)
        asked = _ask(client, conversation, QUESTION)
        assert asked['metadata']['context']['answer_contract']['status'] == 'meaning_choice'
        options = asked['metadata']['context']['meaning_choice']['options']
        index = next(i for i, option in enumerate(options) if option['ids'] == [nord.id])
        _mail(app, 'Vorgang 7000', 'Zur Musterlieferung: Die Prüfmuster gehen am 20. November an Werk West.',
              'Jonas Weller <jw@west.example>')
        assert _messages(client, conversation)[-1]['metadata']['context']['answer_contract']['status'] == 'meaning_choice'
        app.state.episodes.ignore(nord.id)  # Erst der Entzug macht die Auswahl tatsächlich veraltet.
        stale = _messages(client, conversation)[-1]
        context = stale['metadata']['context']
        assert context['answer_contract']['status'] == 'meaning_outdated'
        assert context['refresh_available'] is True and context['original_question'] == QUESTION
        assert _choose(client, conversation, index, options[index]['label']).status_code == 409
        assert calls == []  # Kein Modell entscheidet heimlich eine ungültige Personenwahl.
        response = client.post(f'/api/v1/conversations/{conversation}/messages',
                               json={'message': context['original_question'], 'new_question': True})
        assert response.status_code == 201, response.text
        pending = response.json()['messages'][-1]['metadata']['context']['meaning_choice']
        assert len(pending['options']) == 2
        index = next(i for i, option in enumerate(pending['options']) if option['ids'] == [sued.id])
        chosen = _choose(client, conversation, index, pending['options'][index]['label'])
        assert chosen.status_code == 201, chosen.text
        reply = chosen.json()['messages'][-1]
        assert SUED in reply['content'] and NORD not in reply['content'] and 'Werk West' not in reply['content']
        assert _messages(client, conversation)[-1]['metadata']['context']['refresh_available'] is False
    finally:
        client.close()
        _close_app(app)
