"""Automatische Quellenberichte müssen ohne Annahmeklick im echten Gespräch ankommen."""
import json
import pytest

from tests.test_context_identity import core, AT
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_conversation_retraction import _close_app
from icarus_memory.providers import Reply

TEXT = 'Mainz: Anna liefert den Entwurf am 25. September 2026, wenn die Freigabe vorliegt.'
QUESTION = 'Bis wann liefert Anna den Entwurf für Mainz?'


def classifier(provider):
    def complete_json(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        provider.calls.append(data)
        if 'blocks' in data:
            return Reply(text=json.dumps({'items': [
                {'block_id': block['block_id'], 'kind': 'conditional'} for block in data['blocks']]}))
        return Reply(text=json.dumps({'status': 'reports', 'ids': [row['id'] for row in data['sources']]}))
    provider.complete_json = complete_json


def run_working(app):
    if not hasattr(app.state, 'scheduler'):
        from icarus_memory.server import _wire_scheduler, Summarizer
        app.state.summarizer = Summarizer(app.state.episodes, provider=app.state.agent.provider)
        _wire_scheduler(app)
    callback = getattr(app.state.scheduler, '_run_working_memory', None)
    assert callable(callback), 'Automatische Einordnung fehlt im vorhandenen Hintergrundlauf'
    return callback(True)


def test_uploaded_conditional_source_is_answered_without_acceptance(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        source = _upload(client, TEXT)
        claims_before = app.state.claims.revision
        proposals_before = app.state.proposals.counts()
        run_working(app)
        message = _ask(client, _conversation(client), QUESTION)
        assert TEXT in message['content']
        assert 'Quelle berichtet' in message['content']
        assert message['metadata']['context']['working_answer']['refs'][0]['episode_id'] == source
        assert app.state.claims.revision == claims_before
        assert app.state.proposals.counts() == proposals_before
    finally:
        client.close()
        _close_app(app)


def test_equal_date_conflicting_historical_sources_keep_neutral_caption_on_saved_read(
    core, tmp_path, monkeypatch
):
    from icarus_memory.working_memory_store import WorkingMemoryStore

    app, client, provider = _api(core, tmp_path, monkeypatch)
    question = 'Was steht zu MINT-442 in meinen Quellen?'
    sources = [
        ('mint-442-a.txt', 'Vorgang MINT-442: Die Freigabe ist am 11. Oktober 2026.'),
        ('mint-442-b.txt', 'Vorgang MINT-442: Die Freigabe ist am 19. Oktober 2026.'),
    ]
    try:
        store = WorkingMemoryStore(app.state.episodes)
        source_ids = []
        for title, body in sources:
            response = client.post('/episodes', json={
                'title': title, 'body': body, 'occurred_at': '2026-10-02T10:00:00+02:00',
            })
            assert response.status_code == 201
            source_id = response.json()['id']
            source_ids.append(source_id)
            snapshot = store.pending(episode_ids=[source_id])[0]
            assert store.commit(snapshot, [{'start': 0, 'end': len(body), 'kind': 'historical'}],
                                model='synthetic')

        app.state.agent._working_memory_search = None
        selection_calls = []

        def select_conflicting_sources(messages, *, max_tokens, schema):
            selection_calls.append(True)
            data = json.loads(messages[-1]['content'])
            rows = data['sources']
            assert len(rows) == 2
            return Reply(text=json.dumps({
                'status': 'unresolved_conflicting_sources',
                'ids': [row['id'] for row in rows],
            }))

        provider.complete_json = select_conflicting_sources
        conversation = _conversation(client)
        answer = _ask(client, conversation, question)
        assert answer['metadata']['context']['answer_contract']['status'] == 'working_unclear'
        assert 'Zeitbezug ungeklärt' in answer['content']
        assert 'Frühere Aussage' not in answer['content']
        for _, body in sources:
            assert body in answer['content']
        saved = app.state.conversations.messages(conversation)[-1]
        assert saved.role == 'assistant'

        calls_before_read = len(selection_calls)
        reopened = client.get(f'/api/v1/conversations/{conversation}')
        assert reopened.status_code == 200
        projected = reopened.json()['messages'][-1]
        assert projected['metadata']['context']['answer_contract']['status'] == 'working_unclear'
        assert 'Zeitbezug ungeklärt' in projected['content']
        assert 'Frühere Aussage' not in projected['content']
        for _, body in sources:
            assert body in projected['content']
        assert len(selection_calls) == calls_before_read
        assert len(projected['metadata']['context']['working_answer']['refs']) == 2
        assert {ref['episode_id'] for ref in projected['metadata']['context']['working_answer']['refs']} == set(source_ids)
    finally:
        client.close()
        _close_app(app)


def test_source_withdrawal_removes_saved_answer_and_model_history(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        source = _upload(client, TEXT)
        run_working(app)
        conversation = _conversation(client)
        assert TEXT in _ask(client, conversation, QUESTION)['content']
        stored = app.state.conversations.messages(conversation)[-1]
        assert TEXT not in stored.content and TEXT not in str(stored.metadata)
        app.state.episodes.ignore(source)
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert TEXT not in reopened['content']
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        app.state.agent.load_history([{'role': 'assistant', 'content': TEXT, 'context': stored.metadata['context']}])
        assert TEXT not in str(app.state.agent._history)
    finally:
        client.close()
        _close_app(app)


def test_new_related_source_invalidates_old_current_state(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        run_working(app)
        conversation = _conversation(client)
        assert TEXT in _ask(client, conversation, QUESTION)['content']
        _upload(client, 'Mainz: Anna hat den 25. September abgesagt. Der Entwurf bleibt offen.')
        run_working(app)
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert TEXT not in reopened['content']
        assert 'verändert' in reopened['content']
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('already_incomplete', [False, True])
def test_pending_related_source_invalidates_saved_nonsemantic_answer(core, tmp_path, monkeypatch, already_incomplete):
    """Raw intake must count before classification, even if coverage was already incomplete."""
    from icarus_memory import working_memory_answers
    from icarus_memory.working_memory_store import WorkingMemoryStore

    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    agent = app.state.agent
    agent._working_memory_search = None
    try:
        _upload(client, TEXT)
        run_working(app)
        if already_incomplete:
            _upload(client, 'Mainz: Anna wartet auf die Freigabe für den Entwurf.')
        turn = agent.answer_memory(QUESTION, retrieval_query=QUESTION)
        assert turn.context['answer_contract']['status'] == 'working_reports'
        saved = {'role': 'assistant', 'content': turn.reply, 'metadata': {'context': turn.context}}
        pending = _upload(client, 'Mainz: Anna hat den 25. September abgesagt. Der Entwurf bleibt offen.')
        assert WorkingMemoryStore(app.state.episodes).source_state(pending) == 'pending'
        reopened = working_memory_answers.project_message(saved, app.state.episodes, app.state.claims)
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert TEXT not in reopened['content']
        assert not reopened['metadata']['context']['source_links']
        refreshed = agent.answer_memory(QUESTION, retrieval_query=QUESTION)
        assert refreshed.context['working_answer']['limited'] is True
        assert 'Belegabschnitt' in refreshed.reply and 'Antwort kann unvollständig sein' in refreshed.reply
    finally:
        client.close()
        _close_app(app)


def test_pending_unrelated_source_keeps_nonsemantic_answer_readable(core, tmp_path, monkeypatch):
    from icarus_memory import working_memory_answers

    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    app.state.agent._working_memory_search = None
    try:
        _upload(client, TEXT)
        run_working(app)
        turn = app.state.agent.answer_memory(QUESTION, retrieval_query=QUESTION)
        saved = {'role': 'assistant', 'content': turn.reply, 'metadata': {'context': turn.context}}
        _upload(client, 'Rostock: Ben hat die Wand gestrichen.')
        reopened = working_memory_answers.project_message(saved, app.state.episodes, app.state.claims)
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_reports'
        assert TEXT in reopened['content']
    finally:
        client.close()
        _close_app(app)


def test_second_analysis_does_not_repeat_model_call(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        run_working(app)
        before = len(provider.calls)
        run_working(app)
        assert len(provider.calls) == before
    finally:
        client.close()
        _close_app(app)


def test_condition_in_separate_paragraph_is_not_lost_in_answer(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    body = 'Mainz: Anna liefert am 25. September 2026.\n\nDas gilt nur, wenn die Freigabe vorliegt.'
    original = provider.complete_json
    def select_first(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            return Reply(text=json.dumps({'status':'reports','ids':[data['sources'][0]['id']]}))
        return original(messages,max_tokens=max_tokens,schema=schema)
    provider.complete_json = select_first
    try:
        _upload(client, body)
        run_working(app)
        message = _ask(client, _conversation(client), QUESTION)
        assert 'Das gilt nur, wenn die Freigabe vorliegt.' in message['content']
    finally:
        client.close()
        _close_app(app)


def test_confirmed_entry_stays_visible_beside_new_source_report(core, tmp_path, monkeypatch):
    _, _, _, _, accept = core
    confirmed_text = 'Mainz: Anna hat die Lieferung am 25. September 2026 zugesagt.'
    accept('person:anna', confirmed_text)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    original = provider.complete_json
    def select_source(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            provider.calls.append(data)
            return Reply(text=json.dumps({'status':'reports','ids':[r['id'] for r in data['sources'] if r['id'].startswith('S')]}))
        return original(messages,max_tokens=max_tokens,schema=schema)
    provider.complete_json = select_source
    try:
        _upload(client, 'Mainz: Anna hat die Lieferung inzwischen abgesagt.')
        run_working(app)
        message = _ask(client, _conversation(client), QUESTION)
        assert confirmed_text in message['content']
        assert 'abgesagt' in message['content']
        assert any(confirmed_text in str(call.get('sources', [])) for call in provider.calls)
    finally:
        client.close()
        _close_app(app)


import pytest

@pytest.mark.parametrize('mode', ['chat', 'auto'])
def test_advice_request_keeps_chat_even_with_matching_memory(core, tmp_path, monkeypatch, mode):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        run_working(app)
        conversation = _conversation(client)
        response = client.post(f'/api/v1/conversations/{conversation}/messages',
            json={'message': 'Wie erkläre ich Anna den Entwurf für Mainz?', 'answer_mode': mode})
        message = response.json()['messages'][-1]
        assert message['content'] == 'Synthetische Antwort.'
        assert 'working_answer' not in message['metadata']['context']
    finally:
        client.close()
        _close_app(app)


def test_short_clarification_continues_the_original_memory_question(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    original = provider.complete_json
    def uncertain(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            provider.calls.append(data)
            return Reply(text=json.dumps({'status': 'time' if 'Präzisierung' not in data['question'] else 'reports',
                'ids':[data['sources'][0]['id']]}))
        return original(messages,max_tokens=max_tokens,schema=schema)
    provider.complete_json = uncertain
    try:
        # Die Zeitrückfrage setzt eine relative Angabe ohne Quellenzeit voraus.
        relative = 'Mainz: Anna liefert den Entwurf nächsten Freitag, wenn die Freigabe vorliegt.'
        _upload(client, relative)
        run_working(app)
        conversation = _conversation(client)
        assert 'Von wann stammt' in _ask(client, conversation, QUESTION)['content']
        answer = _ask(client, conversation, 'Der 25. September 2026')
        assert relative in answer['content']
        selection = next(call for call in reversed(provider.calls) if 'sources' in call)
        assert QUESTION in selection['question'] and 'Präzisierung' in selection['question']
    finally:
        client.close()
        _close_app(app)


def test_coverage_and_dismissal_use_the_same_working_state(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        source = _upload(client, TEXT)
        run_working(app)
        coverage = client.get('/api/v1/memory/coverage').json()
        assert coverage['working_memory']['complete'] == 1
        conversation = _conversation(client)
        assert TEXT in _ask(client, conversation, QUESTION)['content']
        response = client.post(f'/api/v1/memory/working/{source}/dismiss')
        assert response.status_code == 200
        assert app.state.episodes.get(source).body == TEXT
        assert TEXT not in client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]['content']
        before = len(provider.calls)
        run_working(app)
        assert len(provider.calls) == before
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('selector_reply', ['{"status":"unknown","ids":[]}', 'invalid json'])
def test_failed_selection_shows_confirmed_entry_without_unselected_source(core, tmp_path, monkeypatch, selector_reply):
    _, _, _, _, accept = core
    known = 'Mainz: Anna hat die Lieferung am 25. September 2026 zugesagt.'
    accept('person:anna', known)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    original = provider.complete_json
    def unknown(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            return Reply(text=selector_reply)
        return original(messages,max_tokens=max_tokens,schema=schema)
    provider.complete_json = unknown
    try:
        _upload(client, 'Mainz: Anna hat die Lieferung abgesagt.')
        run_working(app)
        message = _ask(client, _conversation(client), QUESTION)
        assert known in message['content']
        assert 'abgesagt' not in message['content']
        assert 'Quellenauswahl ist noch unklar' in message['content']
    finally:
        client.close()
        _close_app(app)


def test_unrelated_new_source_keeps_existing_answer_readable(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        run_working(app)
        conversation = _conversation(client)
        assert TEXT in _ask(client, conversation, QUESTION)['content']
        _upload(client, 'Rostock: Ben hat die Wand gestrichen.')
        run_working(app)
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert TEXT in reopened['content']
    finally:
        client.close()
        _close_app(app)


def test_thirteenth_matching_confirmed_claim_invalidates_saved_answer(core, tmp_path, monkeypatch):
    _, _, _, claims, accept = core
    for n in range(12):
        accept(f'topic:mainz-{n}', f'Mainz Anna Entwurf: bestätigter Stand {n}.')
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        for _ in range(3):
            run_working(app)  # 13 source fixtures, five per bounded pass.
        conversation = _conversation(client)
        assert TEXT in _ask(client, conversation, QUESTION)['content']
        extra, _ = accept('topic:mainz-extra',
            'Mainz: Ein weiterer bestätigter Sachverhalt zu Anna und dem Entwurf, '
            'mit vielen zusätzlichen Wörtern zur eindeutigen Einordnung dieser Meldung.')
        indexed, _ = claims.search_context(QUESTION)
        assert extra.id in {claim.id for claim in indexed}
        assert extra.id not in {claim.id for claim in indexed[:12]}
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert TEXT not in reopened['content']
        assert 'verändert' in reopened['content']
    finally:
        client.close()
        _close_app(app)


def test_unrelated_confirmed_claim_keeps_saved_answer_readable(core, tmp_path, monkeypatch):
    _, _, _, _, accept = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        run_working(app)
        conversation = _conversation(client)
        assert TEXT in _ask(client, conversation, QUESTION)['content']
        accept('topic:rostock', 'Rostock: Ben hat die Wand gestrichen.')
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert TEXT in reopened['content']
    finally:
        client.close()
        _close_app(app)


def test_confirmed_source_over_context_limit_is_reported_as_incomplete(core, tmp_path, monkeypatch):
    _, _, _, _, accept = core
    accept('topic:mainz-large', 'Mainz Anna Entwurf ' + 'langequelle ' * 1100)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, TEXT)
        run_working(app)
        message = _ask(client, _conversation(client), QUESTION)
        assert TEXT in message['content']
        assert 'Die Auswahl ist begrenzt' in message['content']
    finally:
        client.close()
        _close_app(app)
