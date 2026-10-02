"""Bedingungsfragen dürfen belegte Quellen nicht am Gedächtnis vorbeileiten."""
import pytest
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import classifier, run_working
from tests.test_conversation_retraction import _close_app
from icarus_memory.memory_routing import route


@pytest.mark.parametrize('question', [
    'Unter welchen Voraussetzungen verschickt Lea die Baupläne für Birkenhain?',
    'Unter welchen Bedingungen findet die Abnahme statt?',
    'Unter welcher Voraussetzung wird der Termin verbindlich?',
])
def test_condition_questions_use_available_sources(question):
    assert route(question, working_available=True) == 'memory_evidence'


@pytest.mark.parametrize('question', [
    'Unter welchen Bedingungen findet die Abnahme statt? Sende Lea eine Mail.',
    'Unter welchen Bedingungen darf ich eine Mail senden?',
    'Unter welchen Bedingungen findet eine Sonnenfinsternis statt?',
])
def test_actions_or_questions_without_sources_keep_chat(question):
    assert route(question, working_available='Sonnenfinsternis' not in question) == 'chat'


def test_condition_question_delivers_original_and_withdraws_it(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    body = ('Projekt Birkenhain: Lea verschickt die Baupläne am 14. Dezember 2026.\n\n'
            'Dies gilt ausschließlich nach schriftlicher Zustimmung der Eigentümer. '
            'Diese Zustimmung steht noch aus.')
    classifier(provider)
    try:
        source = _upload(client, body)
        run_working(app)
        cid = _conversation(client)
        answer = _ask(client, cid, 'Unter welchen Voraussetzungen verschickt Lea die Baupläne für Birkenhain?')
        context = answer['metadata']['context']
        assert context['answer_contract']['status'] == 'working_reports'
        assert body in answer['content']
        assert {ref['episode_id'] for ref in context['working_answer']['refs']} == {source}
        assert client.post(f'/api/v1/episodes/{source}/ignore').status_code == 200
        reopened = client.get(f'/api/v1/conversations/{cid}').json()['messages'][-1]
        assert body not in reopened['content']
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
    finally:
        client.close()
        _close_app(app)
