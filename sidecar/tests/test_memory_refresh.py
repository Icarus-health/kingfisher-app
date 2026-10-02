"""Eine veraltete Antwort lässt sich mit einem Klick neu beantworten."""
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation
from tests.test_working_memory_choices import NORD, SUED, QUESTION, _mail, _selector


def _messages(client, conversation):
    return client.get(f'/api/v1/conversations/{conversation}').json()['messages']


def test_stale_answer_offers_refresh_with_original_question(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        nord = _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        _selector(provider, 'source_reports')
        conversation = _conversation(client)
        answer = _ask(client, conversation, QUESTION)
        context = answer['metadata']['context']
        assert context['original_question'] == QUESTION
        assert context['refresh_available'] is False

        # Neue Quelle zur selben Frage: die gespeicherte Auswahl passt nicht mehr.
        _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        stale = _messages(client, conversation)[-1]
        assert stale['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert stale['metadata']['context']['refresh_available'] is True
        assert 'Werk Nord' not in stale['content']

        response = client.post(f'/api/v1/conversations/{conversation}/messages',
                               json={'message': stale['metadata']['context']['original_question'],
                                     'new_question': True})
        assert response.status_code == 201
        fresh = response.json()['messages'][-1]
        assert 'Werk Nord' in fresh['content'] and 'Werk Süd' in fresh['content']
        assert fresh['metadata']['context']['refresh_available'] is False
        # Die frühere Antwort bleibt als veraltet im Verlauf stehen.
        assert _messages(client, conversation)[-3]['metadata']['context']['refresh_available'] is True
        assert nord.id
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


def test_stale_choice_is_answered_again_and_says_so(core, tmp_path, monkeypatch):  # noqa: F811
    from tests.test_working_memory_choices import _choose
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mail(app, 'Vorgang 4831', NORD, 'Jonas Weller <jonas@nord.example>')
        _mail(app, 'Vorgang 9584', SUED, 'Jonas Weller <weller@sued.example>')
        calls = _selector(provider, 'needs_person_choice')
        conversation = _conversation(client)
        asked = _ask(client, conversation, QUESTION)
        options = [option['label'] for option in asked['metadata']['context']['clarification_choices']]
        label = 'Jonas Weller <jonas@nord.example> · Vorgang 4831'
        _mail(app, 'Vorgang 7000', 'Zur Musterlieferung: Die Prüfmuster gehen am 20. November an Werk West.',
              'Jonas Weller <jw@west.example>')
        _selector(provider, 'source_reports')
        response = _choose(client, conversation, options.index(label), label)
        assert response.status_code == 201
        reply = response.json()['messages'][-1]
        assert reply['content'].startswith('Die Quellen haben sich seit der Rückfrage geändert.')
        assert reply['metadata']['context']['refreshed_after_change'] is True
        # Neu geladen steht der Hinweis weiterhin da.
        again = _messages(client, conversation)[-1]
        assert again['content'].startswith('Die Quellen haben sich seit der Rückfrage geändert.')
    finally:
        client.close()
        _close_app(app)
