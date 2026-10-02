"""Different project reports can require scope clarification without identity claims."""
import json

from .test_context_identity import core
from .test_source_answers_http import _api, _ask, _conversation, _upload
from .test_working_memory_flow import classifier, run_working
from .test_conversation_retraction import _close_app
from icarus_memory.providers import Reply


def test_project_scope_question_preserves_both_reports_without_merging_people(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    classify = provider.complete_json
    def select(messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        if 'sources' in payload:
            return Reply(text=json.dumps({'status': 'scope', 'ids': [row['id'] for row in payload['sources']]}))
        return classify(messages, **kwargs)
    provider.complete_json = select
    bodies = [
        'Mira Bach hat für Projekt Nord die Gussprobe freigegeben.',
        'Mira Bach hat für Projekt Süd noch keine Gussprobe freigegeben.',
    ]
    try:
        identifiers = {_upload(client, body) for body in bodies}
        run_working(app)
        conversation = _conversation(client)
        answer = _ask(client, conversation, 'Was hat Mira Bach zur Gussprobe entschieden?')
        assert 'Welches Projekt oder welchen Vorgang meinst du?' in answer['content']
        assert 'Welche der genannten Personen' not in answer['content']
        assert all(body in answer['content'] for body in bodies)
        context = answer['metadata']['context']
        assert context['answer_contract']['status'] == 'working_unclear'
        assert context['working_answer']['uncertainty'] == 'scope'
        assert {link['episode_id'] for link in context['source_links']} == identifiers
        app.state.episodes.ignore(next(iter(identifiers)))
        old = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert old['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert all(body not in old['content'] for body in bodies)
    finally:
        client.close()
        _close_app(app)
