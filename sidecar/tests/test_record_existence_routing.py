"""Record-existence questions need evidence even when the record is missing."""
import pytest
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import classifier, run_working
from tests.test_conversation_retraction import _close_app
from icarus_memory.memory_routing import route


@pytest.mark.parametrize('question', [
    'Liegt jetzt eine Hotelbuchung für die Reise nach Bremen vor?',
    'Gibt es schon eine Buchungsbestätigung für meine Reise?',
    'Besteht meine Reservierung noch?',
    'Liegen uns die Freigaben für Lindenhof vor?',
])
@pytest.mark.parametrize('available', [True, False])
def test_record_question_stays_evidence_bound(question, available):
    assert route(question, working_available=available) == 'memory_evidence'


@pytest.mark.parametrize('question', [
    'Liegt Berlin in Deutschland?',
    'Gibt es Leben auf dem Mars?',
    'Besteht die Möglichkeit, ein Hotel zu buchen?',
    'Gibt es eine Erklärung für Polarlichter?',
    'Gibt es eine Bestätigung für die Relativitätstheorie?',
    'Gibt es eine Hotelbuchung? Sende Nora die Bestätigung.',
    'Liegt die Hotelbuchung vor und schicke Nora die Bestätigung?',
    'Bitte buche mir ein Hotel in Bremen.',
    'Die Hotelbuchung liegt jetzt vor.',
])
def test_general_questions_statements_and_actions_keep_chat(question):
    assert route(question, working_available=False) == 'chat'


def test_booking_reaches_answer_and_missing_record_never_calls_free_chat(core,tmp_path,monkeypatch):
    app, client, provider = _api(core,tmp_path,monkeypatch)
    classifier(provider)
    def forbidden(*args,**kwargs):
        raise AssertionError('Record question escaped into free chat')
    provider.complete = forbidden
    body = 'Buchungsbestätigung HB-731: Für die Reise nach Bremen ist das Hotel Hafenblick verbindlich gebucht.'
    question = 'Liegt jetzt eine Hotelbuchung für die Reise nach Bremen vor?'
    try:
        eid = _upload(client,body); run_working(app)
        answer = _ask(client,_conversation(client),question)
        context = answer['metadata']['context']
        assert context['answer_contract']['status'] == 'working_reports'
        assert body in answer['content']
        assert {ref['episode_id'] for ref in context['working_answer']['refs']} == {eid}
        assert client.post(f'/api/v1/episodes/{eid}/ignore').is_success
        missing = _ask(client,_conversation(client),question)
        assert missing['metadata']['context']['answer_mode'] == 'memory_evidence'
        assert missing['metadata']['context']['answer_contract']['status'] in {'working_unknown','unknown','insufficient_evidence'}
        assert body not in missing['content']
    finally:
        client.close(); _close_app(app)
