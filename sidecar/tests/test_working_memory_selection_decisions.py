"""Selection decisions describe a missing decision, not the query's topic."""
import json

import pytest

from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import classifier, run_working
from icarus_memory.providers import Reply
from icarus_memory.working_memory_answers import _time_reference_missing


DECISIONS = {
    'source_reports': ('working_reports', 'none'),
    'no_relevant_sources': ('working_unknown', 'none'),
    'needs_person_choice': ('working_unclear', 'person'),
    'needs_project_choice': ('working_unclear', 'scope'),
    'needs_missing_time_reference': ('working_unclear', 'time'),
    'unresolved_conflicting_sources': ('working_unclear', 'conflict'),
}


@pytest.mark.parametrize('decision', DECISIONS)
def test_explicit_model_decisions_preserve_existing_answer_contract(core, tmp_path, monkeypatch, decision):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    classify = provider.complete_json
    seen = []

    def select(messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        if 'sources' not in data:
            return classify(messages, **kwargs)
        seen.append(kwargs['schema']['properties']['status']['enum'])
        return Reply(text=json.dumps({'status': decision, 'ids': [] if decision == 'no_relevant_sources'
                                      else [data['sources'][0]['id']]}))

    provider.complete_json = select
    try:
        # Die relative Angabe ohne Quellenzeit hält die Zeitrückfrage zulässig.
        _upload(client, 'Für den Gusstest bitte ab nächsten Montag erst nach 11 Uhr anrufen.')
        run_working(app)
        message = _ask(client, _conversation(client), 'Wann kann man mich wegen des Gusstests anrufen?')
        context = message['metadata']['context']
        expected, uncertainty = DECISIONS[decision]
        assert context['answer_contract']['status'] == expected
        assert context['working_answer']['uncertainty'] == uncertainty
        assert seen == [list(DECISIONS)]
        if decision == 'source_reports':
            assert 'erst nach 11 Uhr' in message['content']
            assert 'Von wann stammt' not in message['content']
        if decision == 'no_relevant_sources':
            # Keine Scheinmehrdeutigkeit: Es fehlt eine Angabe, nicht eine Auswahl.
            assert message['content'] == 'Dazu liegt in den bisher eingeordneten Quellen keine Information vor.'
    finally:
        client.close()
        _close_app(app)


def test_descriptive_decision_does_not_make_an_unknown_source_id_valid(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    classify = provider.complete_json

    def select(messages, **kwargs):
        if 'sources' in json.loads(messages[-1]['content']):
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': ['S999']}))
        return classify(messages, **kwargs)

    provider.complete_json = select
    try:
        _upload(client, 'Gusstest: Nur nach schriftlicher Freigabe liefern.')
        run_working(app)
        message = _ask(client, _conversation(client), 'Wann liefern wir den Gusstest?')
        assert message['metadata']['context']['answer_contract']['status'] == 'working_selection_failed'
        assert 'schriftlicher Freigabe' not in message['content']
    finally:
        client.close()
        _close_app(app)


def _select_time(provider):
    classify = provider.complete_json

    def select(messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        if 'sources' not in data:
            return classify(messages, **kwargs)
        return Reply(text=json.dumps({'status': 'needs_missing_time_reference',
                                      'ids': [data['sources'][0]['id']]}))
    provider.complete_json = select


def test_clear_call_window_is_reported_without_a_date_question(core, tmp_path, monkeypatch):
    # Beobachteter Modellfehler: eindeutiges Uhrzeitfenster, trotzdem Zeitrückfrage.
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _select_time(provider)
    try:
        _upload(client, 'Für den Gusstest bitte erst nach 11 Uhr anrufen; morgens bin ich in der Halle.')
        run_working(app)
        message = _ask(client, _conversation(client), 'Wann kann man mich wegen des Gusstests anrufen?')
        context = message['metadata']['context']
        assert context['answer_contract']['status'] == 'working_reports'
        assert context['working_answer']['uncertainty'] == 'none'
        assert 'erst nach 11 Uhr' in message['content']
        assert 'Von wann stammt' not in message['content']
    finally:
        client.close()
        _close_app(app)


def test_relative_day_without_source_time_keeps_the_date_question(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _select_time(provider)
    try:
        _upload(client, 'Wir können die Gussprobe nächsten Freitag liefern.')
        run_working(app)
        message = _ask(client, _conversation(client), 'An welchem Datum kommt die Gussprobe?')
        assert message['metadata']['context']['answer_contract']['status'] == 'working_unclear'
        assert 'relative Zeitangabe' in message['content']
        assert 'Von wann stammt' in message['content']
        assert 'nächsten Freitag' in message['content']
    finally:
        client.close()
        _close_app(app)


def test_date_question_needs_relative_time_and_missing_source_time():
    def row(identifier, text, occurred_at=None):
        return {'id': identifier, 'context': text, 'occurred_at': occurred_at}
    relative = row('S1', 'Lieferung nächsten Freitag.')
    assert _time_reference_missing([relative], ['S1'])
    # Bekannte Quellenzeit: Das Datum der Nachricht steht bereits in der Antwort.
    assert not _time_reference_missing([row('S1', 'Lieferung nächsten Freitag.', '2026-09-23T10:00:00+02:00')], ['S1'])
    # Vollständiger Termin oder Uhrzeitfenster: Es fehlt kein Zeitbezug.
    assert not _time_reference_missing([row('S1', 'Lieferung am 6. Oktober 2026.')], ['S1'])
    assert not _time_reference_missing([row('S1', 'Bitte erst nach 10 Uhr anrufen; morgens bin ich weg.')], ['S1'])
    # Nur gewählte automatische Quellen zählen, keine übergangenen Kandidaten.
    assert not _time_reference_missing([relative, row('S2', 'Termin am 6. Oktober 2026.')], ['S2'])
    assert not _time_reference_missing([row('K1', 'Lieferung morgen.')], ['K1'])
    for text in ('Wir melden uns morgen.', 'Kommende Woche passt.', 'In zwei Wochen liefern wir.',
                 'Ende des Monats ist es fertig.', 'Wir liefern am Montag.', 'Delivery is due next week.'):
        assert _time_reference_missing([row('S1', text)], ['S1']), text
