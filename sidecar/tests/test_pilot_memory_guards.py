"""The pilot must not substitute topics or silently conflate named people."""
import pytest
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import classifier, run_working
from tests.test_conversation_retraction import _close_app


@pytest.mark.parametrize('body,question,status', [
    ('Projekt Werkstatt: Lea Sommer liefert die Ventile am 14. Oktober 2026. '
     'Lea Winter liefert die Ventile am 19. Oktober 2026.',
     'Wann liefert Lea die Ventile für Werkstatt?', 'working_unclear'),
    ('Projekt Labor: Jan Meier schickt die Proben am 4. November 2026. '
     'Jan Kranz schickt die Proben am 9. November 2026.',
     'Wann schickt Jan die Proben für Labor?', 'working_unclear'),
    ('Lea Sommer liefert die Ventile am 14. Oktober 2026. Lea Winter liefert die Ventile am 19. Oktober 2026.',
     'Wann liefert Lea Sommer die Ventile?', 'working_reports'),
    ('Lea Sommer liefert die Ventile am 14. Oktober 2026. Lea Winter liefert die Ventile am 19. Oktober 2026.',
     'Wann liefern beide Lea jeweils die Ventile?', 'working_reports'),
    ('Lea liefert die Ventile am 14. Oktober 2026. Im Sommer liefert Lea die Ersatzteile.',
     'Wann liefert Lea die Ventile?', 'working_reports'),
    ('Lea Sommer liefert die Ventile am 14. Oktober 2026. Lea Winter liefert die Rohre am 19. Oktober 2026.',
     'Wann liefert Lea die Ventile?', 'working_reports'),
    ('Buchungsbestätigung HB-731: Hotel Hafenblick in Bremen ist verbindlich gebucht.',
     'Welche Zugbuchung habe ich für Bremen?', 'working_unknown'),
    ('Buchungsbestätigung HB-731: Hotel Hafenblick in Bremen ist verbindlich gebucht.',
     'Welche Flugbuchung habe ich für Bremen?', 'working_unknown'),
    ('Die Zugbuchung für Bremen ist bestätigt. Das Hotel ist noch offen.',
     'Welche Hotelbuchung habe ich für Bremen?', 'working_reports'),
    ('Die Bahnfahrkarte für Bremen ist gebucht. Das Hotel ist ebenfalls reserviert.',
     'Welche Zugbuchung habe ich für Bremen?', 'working_reports'),
    ('Für Bremen ist die Reservierung bestätigt, Kennung R-42.',
     'Welche Zugbuchung habe ich für Bremen?', 'working_reports'),
])
def test_selected_source_is_guarded_without_replacing_model_relevance(core,tmp_path,monkeypatch,body,question,status):
    app, client, provider = _api(core,tmp_path,monkeypatch)
    classifier(provider)  # Deliberately selects every source, including wrong-topic reports.
    try:
        eid = _upload(client,body); run_working(app)
        answer = _ask(client,_conversation(client),question)
        context = answer['metadata']['context']
        assert context['answer_contract']['status'] == status
        refs = context['working_answer']['refs']
        if status == 'working_unknown':
            assert refs == []
            assert 'HB-731' not in answer['content']
        else:
            assert {r['episode_id'] for r in refs} == {eid}
            assert body in answer['content']
        if status == 'working_unclear':
            assert 'Welche der genannten Personen meinst du?' in answer['content']
    finally:
        client.close(); _close_app(app)


def test_delivery_after_withdrawal_stays_in_evidence_path(core,tmp_path,monkeypatch):
    app, client, provider = _api(core,tmp_path,monkeypatch)
    classifier(provider)
    def forbidden(*args,**kwargs):
        raise AssertionError('Missing personal record escaped into free chat')
    provider.complete = forbidden
    try:
        eid = _upload(client,'Werkstatt: Lea liefert die Ventile am 14. Oktober 2026.')
        run_working(app)
        question = 'Wann liefert Lea die Ventile für Werkstatt?'
        assert _ask(client,_conversation(client),question)['metadata']['context']['answer_contract']['status'] == 'working_reports'
        assert client.post(f'/api/v1/episodes/{eid}/ignore').is_success
        answer = _ask(client,_conversation(client),question)
        assert answer['metadata']['context']['answer_contract']['status'] in {'unknown','working_unknown','insufficient_evidence'}
        assert '14. Oktober' not in answer['content']
    finally:
        client.close(); _close_app(app)
