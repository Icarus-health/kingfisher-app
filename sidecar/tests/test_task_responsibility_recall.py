"""Synthetic, socket-blocked conversation integration; no semantic-model acceptance."""
import json
import uuid

import pytest

from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from tests.test_task_completion_confirmation import read, session
from tests.test_task_status_recall import ask, conversation, MANUAL
from tests.test_context_identity import core

TITLE = 'Prüfadapter nachmessen'
OLD = 'Niko fragt an: Elif übernimmt das Nachmessen des Prüfadapters.'


def correct(client, task, owner=None, *, operation='set', target=None):
    path = f'/api/v1/tasks/{task.id}/responsibility'
    snapshot = read(client.get(path))
    body = dict(request_id=uuid.uuid4().hex, expected_revision=snapshot['revision'],
                confirmed=True, operation=operation)
    if operation == 'set':
        body['owner'] = owner or dict(decision='person', address='mara@example.invalid', label='Mara')
    if target is not None:
        body['target_event_sequence'] = target
    return read(client.post(path, json=body))


def source_task(app, client):
    episode = read(client.post('/episodes', json={'title': 'Prüfadapter Notiz', 'body': OLD}), 201)
    task = app.state.tasks.add(TITLE, Provenance(SourceType.EMAIL, source_ref='episode:' + episode['id']))
    correct(client, task)
    return episode['id'], task


def test_corrected_owner_initial_retry_reopen_and_history_isolation(session, monkeypatch):
    app, client, provider = session
    episode, task = source_task(app, client)
    url = conversation(client)
    question = f'Wer ist für die Aufgabe {task.id} zuständig?'
    first = ask(client, url, question)
    answer = first['messages'][-1]
    assert 'mara@example.invalid' in answer['content']
    assert 'Elif' not in answer['content']
    link = first['context']['task_link']
    event = read(client.get(f'/api/v1/tasks/{task.id}/history', params={'sequence': link['sequence']}))['items'][0]
    assert event['kind'] == 'responsibility_confirmed'
    stored = app.state.conversations.messages(url.rsplit('/', 1)[1])[-1]
    assert all(text not in str(stored.to_dict()) for text in [TITLE, 'Mara', 'mara@', OLD])
    assert read(client.get(url))['messages'][-1]['content'] == answer['content']
    assert provider.calls == []
    correct(client, task, dict(decision='self'))
    stale = read(client.get(url))['messages'][-1]
    assert 'mara@' not in str(stale) and 'task_link' not in stale['metadata']['context']
    refreshed = ask(client, url, question)
    assert 'Du selbst' in refreshed['messages'][-1]['content']
    write = app.state.conversations.add_message
    with monkeypatch.context() as patch:
        def fail_assistant(*args, **kwargs):
            if kwargs.get('metadata', {}).get('context', {}).get('task_status_answer'):
                raise RuntimeError('synthetic response persistence failure')
            return write(*args, **kwargs)
        patch.setattr(app.state.conversations, 'add_message', fail_assistant)
        failure = ask(client, url, question)['messages'][-1]
    assert failure['status'] == 'error'
    correct(client, task, operation='reset')
    repeated = read(client.post(f"{url}/messages/{failure['id']}/retry"), 201)
    assert 'ausdrücklich ungeklärt' in repeated['messages'][-1]['content']
    assert len([m for m in repeated['messages'] if m['role'] == 'user']) == 3
    ask(client, url, 'Sag Hallo.', 'chat')
    assert all(text not in str(provider.calls[-1]) for text in [question, TITLE, 'Mara', 'mara@', task.id])
    assert app.state.episodes.get(episode).body == OLD


@pytest.mark.parametrize('question', ['Wer kümmert sich um Prüfadapter?', 'Wer ist dafür zuständig?',
                                     'Wer übernimmt das Nachmessen?', 'Wer macht die Aufgabe?'])
def test_owner_ambiguity_never_falls_back_to_source_model(session, question):
    app, client, provider = session
    source_task(app, client)
    result = ask(client, conversation(client), question)
    assert 'Welche gespeicherte Aufgabe' in result['messages'][-1]['content']
    assert provider.calls == []


def test_general_literal_source_reports_current_decision_separately(session):
    app, client, provider = session
    episode, task = source_task(app, client)
    url = conversation(client)
    result = ask(client, url, 'Was steht zu "Prüfadapter" in meinen Quellen?')
    answer = result['messages'][-1]
    assert 'mara@example.invalid' in answer['content'] and OLD in answer['content']
    assert 'Historische Quellenangabe' in answer['content']
    assert 'mara@' not in str(app.state.conversations.messages(url.rsplit('/', 1)[1])[-1].to_dict())
    correct(client, task, dict(decision='self'))
    assert OLD not in str(read(client.get(url))['messages'][-1])
    refreshed = ask(client, url, 'Was steht zu "Prüfadapter" in meinen Quellen?')
    assert 'Du selbst' in refreshed['messages'][-1]['content']
    app.state.episodes.ignore(episode)
    hidden = read(client.get(url))['messages'][-1]
    assert OLD not in str(hidden) and not hidden['metadata']['context'].get('source_links')
    owner = ask(client, conversation(client), f'Wer kümmert sich um "{TITLE}"?')
    assert 'Du selbst' in owner['messages'][-1]['content']
    assert app.state.episodes.get(episode).body == OLD


def test_general_working_source_context_reaches_selection_with_current_decision(session):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    app, client, provider = session
    episode, task = source_task(app, client)
    working = WorkingMemoryStore(app.state.episodes)
    snapshot = working.pending(episode_ids=[episode])[0]
    assert working.commit(snapshot, [{'start': 0, 'end': len(OLD), 'kind': 'commitment'}], model='synthetic')
    app.state.agent._working_memory_search = None
    captures = []
    def capture(messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]['content'])
        captures.append(payload)
        # Select the visible source ID, never supply an expected owner as model prose.
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in payload['sources']]}))
    provider.complete_json = capture
    result = ask(client, conversation(client), 'Was weißt du über den Prüfadapter?', 'memory_evidence')
    assert captures and 'mara@example.invalid' in str(captures)
    assert 'mara@example.invalid' in result['messages'][-1]['content']
    assert OLD in result['messages'][-1]['content']


def test_duplicate_titles_names_reset_undo_unrelated_and_hidden_task(session):
    app, client, provider = session
    first = app.state.tasks.from_suggestion('owner-hidden', TITLE, MANUAL, angelegt={'art': 'automatisch'})
    second = app.state.tasks.add(TITLE, MANUAL)
    correct(client, first, dict(decision='person', address='mara-a@example.invalid', label='Mara'))
    correct(client, second, dict(decision='person', address='mara-b@example.invalid', label='Mara'))
    url = conversation(client)
    assert 'Welche gespeicherte Aufgabe' in ask(client, url, f'Wer kümmert sich um "{TITLE}"?')['messages'][-1]['content']
    first_answer = ask(client, url, f'Wer übernimmt die Aufgabe {first.id}?')['messages'][-1]
    assert 'mara-a@' in first_answer['content'] and 'mara-b@' not in first_answer['content']
    reset = correct(client, first, operation='reset')
    assert 'ausdrücklich ungeklärt' in ask(client, url, f'Wer macht {first.id}?')['messages'][-1]['content']
    correct(client, first, operation='undo', target=reset['responsibility_event_sequence'])
    assert 'mara-a@' in ask(client, url, f'Wer macht {first.id}?')['messages'][-1]['content']
    assert read(client.get(f'/api/v1/tasks/{second.id}/responsibility'))['task']['responsibility']['address'] == 'mara-b@example.invalid'
    app.state.tasks.anlage_entfernen(first.id)
    assert 'mara-a@' not in str(read(client.get(url))['messages'][-1])
    assert provider.calls == []


def test_task_id_reuse_never_revives_owner_proof(session):
    app, client, _ = session
    task = app.state.tasks.from_suggestion('owner-reuse', TITLE, MANUAL, angelegt={'art': 'automatisch'})
    correct(client, task)
    url = conversation(client)
    ask(client, url, f'Wer macht {task.id}?')
    app.state.tasks.anlage_entfernen(task.id)
    recreated = app.state.tasks.from_suggestion('owner-reuse', TITLE, MANUAL, angelegt={'art': 'automatisch'})
    assert recreated.id == task.id
    assert 'mara@' not in str(read(client.get(url))['messages'][-1])
    fresh = ask(client, url, f'Wer macht {task.id}?')['messages'][-1]
    assert 'nicht bestätigt' in fresh['content'] and 'task_link' not in fresh['metadata']['context']


def test_old_source_metadata_is_withheld_after_later_task_correction(session):
    from icarus_memory import source_answers
    app, client, _ = session
    episode, task = source_task(app, client)
    url = conversation(client)
    # Real old persisted reference format, without the new task binding.
    old = source_answers.prepare('Was steht zu "Prüfadapter" in meinen Quellen?', app.state.episodes, app.state.claims)
    app.state.conversations.add_message(url.rsplit('/', 1)[1], 'assistant', 'Old neutral', metadata={
        'context': {'items': [], 'answer_mode': 'memory_evidence', 'source_answer': old}})
    projected = read(client.get(url))['messages'][-1]
    assert OLD not in str(projected) and 'Bitte frage erneut' in projected['content']


def test_general_multi_task_source_keeps_historical_content_and_separate_decisions(session):
    app, client, _ = session
    episode, task = source_task(app, client)
    second = app.state.tasks.add('Prüfadapter transportieren', Provenance(SourceType.EMAIL, source_ref='episode:' + episode))
    correct(client, second, dict(decision='self'))
    result = ask(client, conversation(client), 'Was steht zu "Prüfadapter" in meinen Quellen?')['messages'][-1]
    assert OLD in result['content'] and 'mara@example.invalid' in result['content'] and 'Du selbst' in result['content']
    assert 'mehreren Aufgaben' in result['content'] and 'Welche gespeicherte Aufgabe' in result['content']


def test_task_change_during_working_selection_withholds_answer(session):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    app, client, provider = session
    episode, task = source_task(app, client)
    working = WorkingMemoryStore(app.state.episodes)
    assert working.commit(working.pending(episode_ids=[episode])[0],
                          [{'start': 0, 'end': len(OLD), 'kind': 'commitment'}], model='synthetic')
    app.state.agent._working_memory_search = None
    def capture(messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]['content'])
        correct(client, task, dict(decision='self'))
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in payload['sources']]}))
    provider.complete_json = capture
    result = ask(client, conversation(client), 'Was weißt du über den Prüfadapter?', 'memory_evidence')['messages'][-1]
    assert OLD not in str(result) and 'mara@' not in str(result)
    assert 'Bitte frage erneut' in result['content']


def test_bounded_source_task_lookup_fails_closed(session, monkeypatch):
    from icarus_memory import tasks
    app, client, _ = session
    episode, task = source_task(app, client)
    for i in range(9):
        app.state.tasks.add(f'Weitere Aufgabe {i}', Provenance(SourceType.EMAIL, source_ref='episode:' + episode))
    result = ask(client, conversation(client), 'Was steht zu "Prüfadapter" in meinen Quellen?')['messages'][-1]
    assert OLD not in str(result) and 'Bitte frage erneut' in result['content']


@pytest.mark.parametrize('mutate', [False, True])
def test_general_knowledge_context_uses_current_task_proof(core, tmp_path, monkeypatch, mutate):
    from tests.test_source_answers_http import _api
    from tests.test_conversation_retraction import _close_app
    _, _, _, _, accept = core
    claim, source = accept('project:probe-adapter', 'Prüfadapter: ' + OLD)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        task = app.state.tasks.add(TITLE, Provenance(SourceType.EMAIL, source_ref='episode:' + source.id))
        correct(client, task)
        app.state.agent._working_memory_search = None
        captures = []
        def capture(messages, *, max_tokens, schema):
            captures.append(messages)
            if mutate:
                correct(client, task, dict(decision='self'))
            return Reply(text=json.dumps({'version': 1, 'kind': 'evidence', 'evidence_ids': ['E1']}))
        provider.complete_json = capture
        url = conversation(client)
        result = ask(client, url, 'Was weißt du über den Prüfadapter?', 'memory_evidence')['messages'][-1]
        assert captures and 'mara@example.invalid' in str(captures), result
        if mutate:
            assert OLD not in str(result) and 'mara@' not in str(result)
        else:
            assert 'mara@example.invalid' in result['content'] and 'Elif' in result['content']
            assert 'Historische Quellenangabe' in result['content']
            assert 'mara@' not in str(app.state.conversations.messages(url.rsplit('/', 1)[1])[-1].to_dict())
            assert read(client.get(url))['messages'][-1]['content'] == result['content']
            correct(client, task, dict(decision='self'))
            assert 'Elif' not in str(read(client.get(url))['messages'][-1])
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('mutate', [False, True])
def test_approved_cloud_selection_keeps_task_decision_local(core, tmp_path, monkeypatch, mutate):
    from tests.test_tempo_gedaechtnis_cloud import _welt, QUESTION, TEXT
    from tests.test_conversation_retraction import _close_app
    app, client, cloud = _welt(core, tmp_path, monkeypatch)
    try:
        episode = next(e for e in app.state.episodes.all_episodes() if e.body == TEXT)
        task = app.state.tasks.add('Abnahme ORKA begleiten', Provenance(SourceType.EMAIL, source_ref='episode:' + episode.id))
        correct(client, task)
        complete = cloud.complete
        def capture(messages, tools):
            response = complete(messages, tools)
            if mutate:
                correct(client, task, dict(decision='self'))
            return response
        cloud.complete = capture
        url = conversation(client)
        result = ask(client, url, QUESTION, 'memory_evidence')['messages'][-1]
        assert cloud.calls and 'mara@' not in str(cloud.calls) and task.id not in str(cloud.calls)
        assert result['metadata']['context']['history_egress'] == 'local_only'
        assert result['metadata']['context']['gedaechtnis_cloud']['gesendet'] == ['frage', 'textstellen']
        assert result['metadata']['context']['answer_contract']['model_egress'] == 'external'
        if mutate:
            assert TEXT not in str(result) and 'mara@' not in str(result)
        else:
            assert 'mara@example.invalid' in result['content'] and TEXT in result['content']
            assert len(cloud.calls) == 1  # no source-based prose rephrasing of ownership
            assert read(client.get(url))['messages'][-1]['content'] == result['content']
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('change', ['archive', 'body', 'context'])
def test_source_changes_remove_historical_rendering_but_not_explicit_owner(session, change):
    from tests.test_knowledge_time import change_source
    app, client, _ = session
    episode, task = source_task(app, client)
    url = conversation(client)
    ask(client, url, 'Was steht zu "Prüfadapter" in meinen Quellen?')
    if change == 'archive':
        from datetime import datetime, timezone
        app.state.episodes.mark_consolidated(episode)
        assert app.state.episodes.archive_before(datetime(2100, 1, 1, tzinfo=timezone.utc)) == 1
    elif change == 'body':
        change_source(app.state.episodes, episode, body='Geänderter synthetischer Bericht.')
    else:
        change_source(app.state.episodes, episode, source_ref='synthetic:revised-origin')
    hidden = read(client.get(url))['messages'][-1]
    assert OLD not in str(hidden) and not hidden['metadata']['context'].get('source_links')
    current = ask(client, conversation(client), f'Wer ist für die Aufgabe {task.id} zuständig?')
    assert 'mara@example.invalid' in current['messages'][-1]['content']


def test_no_provider_copy_describes_approved_availability(session):
    app, client, provider = session
    provider.is_local, provider.is_remote = False, True
    result = ask(client, conversation(client), 'Was wissen wir über Prüfadapter?', 'memory_evidence')['messages'][-1]
    assert 'freigegebenes Modell' in result['content']
    assert provider.calls == []


def test_general_working_selection_does_not_display_unselected_task_owner(session):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    app, client, provider = session
    episode, task = source_task(app, client)
    other_body = 'Prüfadapter: Das Lager befindet sich in Halle Nord.'
    other = read(client.post('/episodes', json={'title': 'Prüfadapter Lager', 'body': other_body}), 201)['id']
    working = WorkingMemoryStore(app.state.episodes)
    for identifier, body in [(episode, OLD), (other, other_body)]:
        assert working.commit(working.pending(episode_ids=[identifier])[0],
                              [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='synthetic')
    app.state.agent._working_memory_search = None
    def capture(messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]['content'])
        rows = [row for row in payload['sources'] if row['title'] == 'Prüfadapter Lager']
        assert len(rows) == 1
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [row['id'] for row in rows]}))
    provider.complete_json = capture
    result = ask(client, conversation(client), 'Was weißt du zum Prüfadapter Lager?', 'memory_evidence')['messages'][-1]
    assert other_body in result['content']
    assert 'mara@' not in result['content'] and TITLE not in result['content']


def test_knowledge_clarification_keeps_correction_binding(core, tmp_path, monkeypatch):
    from tests.test_source_answers_http import _api
    from tests.test_conversation_retraction import _close_app
    _, _, _, _, accept = core
    _, source = accept('project:adapter-one', 'Prüfadapter: ' + OLD)
    accept('project:adapter-two', 'Prüfadapter: Der andere Vorgang findet in Halle Nord statt.')
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        task = app.state.tasks.add(TITLE, Provenance(SourceType.EMAIL, source_ref='episode:' + source.id))
        correct(client, task)
        app.state.agent._working_memory_search = None
        url = conversation(client)
        initial = ask(client, url, 'Was weißt du über Prüfadapter?', 'memory_evidence')['messages'][-1]
        assert initial['metadata']['context']['answer_contract']['status'] == 'clarify'
        selected = next(index for index, item in enumerate(initial['metadata']['context']['items'], 1)
                        if 'Elif' in item['knowledge_projection']['statement'])
        reply = ask(client, url, str(selected), 'memory_evidence')['messages'][-1]
        assert 'mara@example.invalid' in reply['content'] and 'Elif' in reply['content']
    finally:
        client.close()
        _close_app(app)


def test_task_change_during_final_projection_withholds_source(session, monkeypatch):
    app, client, _ = session
    episode, task = source_task(app, client)
    url = conversation(client)
    ask(client, url, 'Was steht zu "Prüfadapter" in meinen Quellen?')
    snapshot = app.state.tasks.responsibility_snapshot
    calls = 0
    def changed(identifier):
        nonlocal calls
        calls += 1
        if calls == 3:
            app.state.tasks.edit(identifier, title='Prüfadapter erneut nachmessen')
        return snapshot(identifier)
    monkeypatch.setattr(app.state.tasks, 'responsibility_snapshot', changed)
    result = read(client.get(url))['messages'][-1]
    assert OLD not in str(result) and 'mara@' not in str(result)
    assert 'Bitte frage erneut' in result['content']


@pytest.mark.parametrize('path', ['literal', 'working'])
def test_failed_general_answer_retry_resolves_latest_owner(session, monkeypatch, path):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    app, client, provider = session
    episode, task = source_task(app, client)
    question = 'Was steht zu "Prüfadapter" in meinen Quellen?'
    if path == 'working':
        store = WorkingMemoryStore(app.state.episodes)
        assert store.commit(store.pending(episode_ids=[episode])[0],
                            [{'start': 0, 'end': len(OLD), 'kind': 'commitment'}], model='synthetic')
        app.state.agent._working_memory_search = None
        question = 'Was weißt du über den Prüfadapter?'
        def select(messages, *, max_tokens, schema):
            payload = json.loads(messages[-1]['content'])
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in payload['sources']]}))
        provider.complete_json = select
    url = conversation(client)
    write = app.state.conversations.add_message
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            context = kwargs.get('metadata', {}).get('context', {})
            if 'source_answer' in context or 'working_answer' in context:
                raise RuntimeError('synthetic persistence failure')
            return write(*args, **kwargs)
        patch.setattr(app.state.conversations, 'add_message', fail)
        error = ask(client, url, question, 'memory_evidence')['messages'][-1]
    assert error['status'] == 'error'
    correct(client, task, dict(decision='self'))
    result = read(client.post(f"{url}/messages/{error['id']}/retry"), 201)
    assert 'Du selbst' in result['messages'][-1]['content'] and OLD in result['messages'][-1]['content']
    assert 'mara@' not in result['messages'][-1]['content']
    assert len([m for m in result['messages'] if m['role'] == 'user']) == 1
    assert read(client.get(url))['messages'][-1]['content'] == result['messages'][-1]['content']


@pytest.mark.parametrize('mutation', ['rename', 'id_reuse'])
def test_full_title_lookup_cannot_bind_a_changed_task_snapshot(session, monkeypatch, mutation):
    app, client, provider = session
    proposal = 'synthetic-title-resolution-race'
    first_title, next_title = 'Messschablone A prüfen', 'Messschablone B prüfen'
    task = app.state.tasks.from_suggestion(proposal, first_title, MANUAL, angelegt={'art': 'automatisch'})
    original = correct(client, task)
    lookup = app.state.tasks.status_for_recall

    def change_after_lookup(reference, *, quoted=False):
        result = lookup(reference, quoted=quoted)
        assert result.proof.task_id == task.id
        assert result.proof.task_revision == original['revision']
        if mutation == 'rename':
            app.state.tasks.edit(task.id, title=next_title)
        else:
            app.state.tasks.anlage_entfernen(task.id)
            replacement = app.state.tasks.from_suggestion(proposal, next_title, MANUAL,
                                                         angelegt={'art': 'automatisch'})
            assert replacement.id == task.id
            current = app.state.tasks.responsibility_snapshot(task.id)
            app.state.tasks.change_responsibility(task.id, request_id='synthetic-new-lifetime-owner',
                expected_revision=current['revision'], operation='set', decision={'decision': 'self'})
        return result

    url = conversation(client)
    with monkeypatch.context() as patch:
        patch.setattr(app.state.tasks, 'status_for_recall', change_after_lookup)
        response = ask(client, url, f'Wer kümmert sich um "{first_title}"?')
    answer = response['messages'][-1]
    assert 'Welche gespeicherte Aufgabe' in answer['content']
    assert next_title not in str(answer) and 'mara@' not in str(answer)
    assert 'task_link' not in answer['metadata']['context']
    assert read(client.get(url))['messages'][-1]['content'] == answer['content']
    current = app.state.tasks.responsibility_snapshot(task.id)
    assert current['revision'] > original['revision']
    fresh = ask(client, url, f'Wer kümmert sich um "{next_title}"?')['messages'][-1]
    assert next_title in fresh['content']
    assert ('mara@example.invalid' if mutation == 'rename' else 'Du selbst') in fresh['content']
    assert fresh['metadata']['context']['task_link']['sequence'] == str(current['responsibility_event_sequence'])
    assert provider.calls == []
