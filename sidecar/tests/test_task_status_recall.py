"""Saved task identity, provenance and history through local recall."""

from datetime import datetime, timezone

import pytest

from icarus_memory.model import Provenance, SourceType
from icarus_memory.tasks import TaskStore
from tests.test_task_completion_confirmation import read, session


MANUAL = Provenance(source_type=SourceType.USER_STATED)
AT = datetime(2026, 9, 24, 14, 5, tzinfo=timezone.utc)


def test_all_state_lookup_and_id_disambiguation(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    title = 'Ätlas-46: Material prüfen'
    old = store.add(title, MANUAL)
    store.complete(old.id, AT)
    for i in range(501):
        store.add(f'Füllaufgabe {i}', MANUAL)
    store.add('Ätlas-46: Material bestellen', MANUAL)
    assert store.status_for_recall(title).proof.task_id == old.id
    dropped = store.add(title, MANUAL)
    store.drop(dropped.id)
    assert store.status_for_recall(title).status == 'ambiguous'
    assert store.status_for_recall_id(old.id).proof.state.value == 'done'
    assert store.status_for_recall_id(dropped.id).proof.state.value == 'dropped'


def test_literal_matching_preserves_punctuation_and_checks_extensions(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    exact = store.add('Ätlas-46: Material prüfen', MANUAL)
    store.add('Ätlas-46: Material prüfen und ablegen', MANUAL)
    store.add('Ätlas-46: Material neu prüfen', MANUAL)
    assert store.status_for_recall('Ätlas-46:  Material prüfen').status == 'ambiguous'
    assert store.status_for_recall('Ätlas-46:  Material prüfen', quoted=True).proof.task_id == exact.id
    assert store.status_for_recall('Atlas-46: Material prüfen').status == 'not_found'
    assert store.status_for_recall('Ätlas-46 Material prüfen').status == 'not_found'
    assert store.status_for_recall('Ätlas-4').status == 'not_found'


def test_interrupted_scan_never_proves_one_match_and_connection_recovers(tmp_path, monkeypatch):
    from icarus_memory import tasks
    store = TaskStore(tmp_path / 'tasks.db')
    old = store.add('Frühe Testaufgabe', MANUAL)
    for i in range(501):
        store.add(f'Füllaufgabe {i}', MANUAL)
    with monkeypatch.context() as patch:
        patch.setattr(tasks, '_RECALL_OPCODE_BUDGET', 1000)
        assert store.status_for_recall('Frühe Testaufgabe').status == 'coverage_limited'
    assert store.status_for_recall('Frühe Testaufgabe').proof.task_id == old.id


def test_active_receipt_survives_edits_but_not_reopen_at_same_completion_time(tmp_path, monkeypatch):
    from icarus_memory import tasks
    monkeypatch.setattr(tasks, 'now', lambda: AT)
    store = TaskStore(tmp_path / 'tasks.db')
    task = store.add('Testbeleg', MANUAL)
    store.confirm_completion(task.id)
    receipt = store.history(task.id)[0]['sequence']
    for i in range(105):
        store.edit(task.id, title=f'Testbeleg {i}')
    proof = store.status_for_recall_id(task.id).proof
    assert proof.confirmation_event_sequence == receipt == proof.state_event_sequence
    assert proof.task_revision > receipt + 100
    store.reopen(task.id)
    store.complete(task.id, AT)
    proof = store.status_for_recall_id(task.id).proof
    assert datetime.fromisoformat(proof.done_at) == AT
    assert proof.confirmation_event_sequence is None
    assert proof.state_event_sequence > receipt


def conversation(client):
    return '/api/v1/conversations/' + read(client.post('/api/v1/conversations', json={}), 201)['conversation']['id']


def ask(client, url, question, mode='auto'):
    return read(client.post(url + '/messages', json={'message': question, 'answer_mode': mode}), 201)


def test_confirmed_task_status_is_projected_without_new_sources_or_provider_calls(session, monkeypatch):
    from icarus_memory import server

    app, client, provider = session
    def no_question_model(*args, **kwargs):
        raise AssertionError('Typed lookup must take priority before the question model.')
    monkeypatch.setattr(server, '_frage_verstehen', no_question_model)
    task = read(client.post('/api/v1/tasks', json={'title': 'Aster-40: Unterlagen prüfen'}), 201)
    path = f"/api/v1/tasks/{task['id']}"
    read(client.post(path + '/done'))
    receipt, creation = read(client.get(path + '/history'))['items']
    url = conversation(client)
    episodes = app.state.episodes.all_episodes()
    response = ask(client, url, 'Wurde Aster-40: Unterlagen prüfen erledigt?')
    user, assistant = response['messages']
    assert user['content'] == 'Wurde Aster-40: Unterlagen prüfen erledigt?'
    assert 'ausdrücklich bestätigt' in assistant['content']
    assert 'Aster-40: Unterlagen prüfen' in assistant['content']
    link = {'id': task['id'], 'status': 'done', 'sequence': str(receipt['sequence'])}
    assert response['context']['task_link'] == link == assistant['metadata']['context']['task_link']
    assert provider.calls == []
    assert app.state.episodes.all_episodes() == episodes
    assert app.state.claims.all_claims() == []
    assert read(client.get(path + '/history'))['items'] == [receipt, creation]
    stored = app.state.conversations.messages(url.rsplit('/', 1)[1])[-1]
    assert task['title'] not in str(stored.to_dict())
    assert receipt['after']['done_at'] not in str(stored.to_dict())
    assert 'task_link' not in stored.metadata['context']
    assert read(client.get(url))['messages'][-1] == assistant
    read(client.post(path + '/reopen'))
    read(client.post(path + '/done'))
    stale = read(client.get(url))
    assert 'task_link' not in stale['context'] and 'task_status_answer' not in stale['context']
    assert task['title'] not in str(stale['messages'][-1])


def test_typed_task_turn_is_omitted_from_later_model_history(session):
    _, client, provider = session
    task = read(client.post('/api/v1/tasks', json={'title': 'Verlaufssperre Kastanie'}), 201)
    url = conversation(client)
    question = f"Wie ist der Status der Aufgabe {task['id']}?"
    response = ask(client, url, question, 'memory_evidence')
    assert response['context']['task_link']['id'] == task['id']
    ask(client, url, 'Sag Hallo.', 'chat')
    assert provider.calls
    assert question not in str(provider.calls[-1])
    assert task['title'] not in str(provider.calls[-1])
    assert task['id'] not in str(provider.calls[-1])


def test_exact_task_history_route_reads_old_receipt_and_cannot_cross_task_id(session):
    app, client, _ = session
    task = app.state.tasks.add('Alter Verlauf', MANUAL)
    other = app.state.tasks.add('Anderer Verlauf', MANUAL)
    path = f'/api/v1/tasks/{task.id}/history'
    app.state.tasks.confirm_completion(task.id)
    receipt = app.state.tasks.history(task.id)[0]
    for i in range(105):
        app.state.tasks.edit(task.id, title=f'Alter Verlauf {i}')
    assert receipt not in read(client.get(path))['items']
    linked = ask(client, conversation(client), f'Wie ist der Status der Aufgabe {task.id}?')['context']['task_link']
    assert int(linked['sequence']) == receipt['sequence']
    assert read(client.get(path, params={'sequence': linked['sequence']}))['items'] == [receipt]
    assert client.get(f'/api/v1/tasks/{other.id}/history', params={'sequence': receipt['sequence']}).status_code == 404


def test_lowercase_preserves_sharp_s_spelling(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    measure = store.add('Maße prüfen', MANUAL)
    assert store.status_for_recall('Masse prüfen').status == 'not_found'
    assert store.status_for_recall('MAẞE prüfen').proof.task_id == measure.id


def test_question_grammar_preserves_literals_and_rejects_unsupported_intent():
    from icarus_memory.task_status_answers import parse
    assert parse('Habe ich die Aufgabe Ätlas-46: Maß prüfen schon abgeschlossen?').operand == 'Ätlas-46: Maß prüfen'
    assert parse('Wurde „Ätlas-46: Maß prüfen!“ erledigt?').operand == 'Ätlas-46: Maß prüfen!'
    assert parse('Wurde „Originaltext Atlas prüfen“ erledigt?').operand == 'Originaltext Atlas prüfen'
    for question in (
        'Habe ich die Materialliste für LINDENBOGEN-46 schon geprüft?',
        'Ist Aster gestern erledigt?', 'Ist Aster nicht erledigt?', 'Ist das erledigt?',
        'Ist Aster erledigt und ist Kiefer erledigt?', 'Erledige Aster.',
        'Wurde Aster laut der Mail erledigt?',
        'Was steht in den Quellen zu „Ätlas-46: Maß prüfen“?',
    ):
        assert parse(question) is None


def test_missing_ambiguous_and_unproven_lineage_are_local_without_candidate_leak(session):
    app, client, provider = session
    url = conversation(client)
    title = 'Kurzbeleg Aster'
    first = app.state.tasks.add(title, MANUAL)
    other = app.state.tasks.add(title, Provenance(SourceType.CHAT, extracted_by='synthetic'))
    app.state.tasks.drop(other.id)
    ambiguity = ask(client, url, f'Wurde „{title}“ erledigt?')['messages'][-1]
    assert 'nicht eindeutig' in ambiguity['content']
    for sensitive in (first.id, other.id, title):
        assert sensitive not in str(ambiguity)
    withheld = ask(client, url, f'Wie ist der Status der Aufgabe {other.id}?')['messages'][-1]
    assert 'nicht verfügbar' in withheld['content']
    assert other.id not in str(withheld) and title not in str(withheld)
    missing = ask(client, url, 'Wie ist der Status der Aufgabe t-123456789abc?')['messages'][-1]
    assert 'keine gespeicherte Aufgabe' in missing['content']
    assert 'nie' not in missing['content']
    assert provider.calls == []
    dropped = app.state.tasks.add('Eine andere verworfene Aufgabe', MANUAL)
    app.state.tasks.drop(dropped.id, AT)
    response = ask(client, url, f'Wie ist der Status der Aufgabe {dropped.id}?')
    assert response['context']['task_link']['status'] == 'dropped'
    assert 'verworfen' in response['messages'][-1]['content']
    assert 'Erledigungszeitpunkt' not in response['messages'][-1]['content']


def test_exact_id_supports_long_title_without_title_scan(session):
    app, client, _ = session
    title = 'Testtitel ' + ('Ü' * 260)
    task = app.state.tasks.add(title, MANUAL)
    url = conversation(client)
    oversized = ask(client, url, f'Wurde „{title}“ erledigt?')
    assert 'nicht vollständig prüfen' in oversized['messages'][-1]['content']
    assert 'task_link' not in oversized['context']
    exact = ask(client, url, f'Wie ist der Status der Aufgabe {task.id}?')
    assert exact['context']['task_link']['id'] == task.id
    assert title in exact['messages'][-1]['content']


def test_confirmed_readback_is_bounded_and_does_not_copy_question_into_search(session):
    app, client, _ = session
    task = app.state.tasks.add('Suchgrenze Eisenholz', MANUAL)
    url = conversation(client)
    for _ in range(21):
        ask(client, url, f'Ist {task.title} erledigt?')
    view = read(client.get(url))
    typed = view['messages'][1::2]
    assert len(typed) == 21
    assert task.title not in str(typed[0]) and task.id not in str(typed[0])
    assert all(item['metadata']['context']['task_link']['id'] == task.id for item in typed[1:])
    assert view['messages'][0]['content'] == f'Ist {task.title} erledigt?'
    assert task.title not in str(read(client.get('/api/v1/conversations')))
    search = read(client.get('/api/v1/conversations/page', params={'q': task.title}))
    assert search['conversations'] == []


def test_typed_error_retries_locally_and_normal_retry_never_replays_lookup(session, monkeypatch):
    app, client, provider = session
    task = app.state.tasks.add('Wiederholung Eisenholz', MANUAL)
    url = conversation(client)
    question = f'Ist {task.title} erledigt?'
    write = app.state.conversations.add_message
    with monkeypatch.context() as patch:
        def fail_assistant(*args, **kwargs):
            if kwargs.get('metadata', {}).get('context', {}).get('task_status_answer'):
                raise RuntimeError('synthetic write failure')
            return write(*args, **kwargs)
        patch.setattr(app.state.conversations, 'add_message', fail_assistant)
        failure = ask(client, url, question)['messages'][-1]
    assert failure['status'] == 'error' and task.title not in str(failure)
    retry = read(client.post(f"{url}/messages/{failure['id']}/retry"), 201)
    assert retry['context']['task_link']['id'] == task.id
    assert [item['content'] for item in retry['messages'] if item['role'] == 'user'] == [question]
    assert app.state.episodes.all_episodes() == [] and provider.calls == []
    with monkeypatch.context() as patch:
        def offline(*args, **kwargs):
            raise RuntimeError('synthetic provider failure')
        patch.setattr(provider, 'complete', offline)
        failed_chat = ask(client, url, 'Sag Hallo.', 'chat')['messages'][-1]
    assert failed_chat['status'] == 'error'
    repeated = read(client.post(f"{url}/messages/{failed_chat['id']}/retry"), 201)
    assert repeated['messages'][-1]['status'] == 'complete'
    assert question not in str(provider.calls[-1]) and task.id not in str(provider.calls[-1])
    provider.is_local, provider.is_remote = False, True
    ask(client, url, 'Sag Tschüss.', 'chat')
    assert question not in str(provider.calls[-1]) and task.id not in str(provider.calls[-1])


def test_enabled_mcp_cannot_read_local_typed_recall(session, monkeypatch):
    from icarus_memory.mcp import PREFIX, Bridge, Server
    app, client, _ = session
    task = app.state.tasks.add('Nur lokaler Status Fichte', MANUAL)
    url = conversation(client)
    ask(client, url, f'Ist {task.title} erledigt?')
    assert client.get('/tools').status_code == 403
    monkeypatch.setenv('KINGFISHER_MCP_TUER', '1')
    bridge = Server(Bridge('http://testserver', None, client=client))
    tools = bridge.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['result']['tools']
    names = {tool['name'] for tool in tools}
    assert f'{PREFIX}aufgabe_erledigt' in names
    assert not any('task_status' in name or 'aufgabenstatus' in name or 'conversation' in name for name in names)
    result = bridge.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                            'params': {'name': f'{PREFIX}aufgabenstatus', 'arguments': {'id': task.id}}})
    assert 'Unbekanntes Werkzeug' in str(result)
    assert task.title not in str(result) and task.id not in str(result)
    context = bridge.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                             'params': {'name': f'{PREFIX}kontext', 'arguments': {}}})
    assert 'result' in context and task.title not in str(context) and task.id not in str(context)
    assert app.state.episodes.all_episodes() == []


def test_mail_candidate_current_decision_and_older_report_remain_distinct(session):
    import json
    from icarus_memory.connectors.mail import Message
    from icarus_memory.mail_ingestion import remember
    from icarus_memory.providers import Reply
    from icarus_memory.task_detection import TaskDetector
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from messlatte.uhr import eingefrorene_zeit

    app, client, provider = session
    title = 'LINDENBOGEN-46 Materialliste prüfen'
    request_text = f'Bitte die {title} und die Freigabe dokumentieren.'
    older_text = f'{title}: Nur die erste Seite ist geprüft; die Freigabe steht aus.'
    mail_time = datetime.fromisoformat('2026-09-21T11:00:00+02:00')

    class Extraction:
        name = model = 'synthetic-extraction'
        is_local = True

        def complete_json(self, messages, *, max_tokens, schema):
            payload = json.loads(messages[-1]['content'])
            assert request_text in payload['body']
            output = ({'reviews': [{'id': 0, 'kind': 'request_to_recipient', 'title_supported': True}]}
                      if 'candidates' in payload else {'items': [{'title': title, 'quote': request_text}]})
            return Reply(text=json.dumps(output))

    def original(uid, body):
        mail = Message(uid=f'synthetic:8.{uid}', subject='Prüfstatus Lindenbogen',
                       sender='Probe <probe@example.invalid>', date=mail_time,
                       preview=body, unread=False, body=body, account_id='synthetic')
        return remember(app.state.episodes, mail, claims=app.state.claims)['episode']

    with eingefrorene_zeit(AT):
        request = original(1, request_text)
        older = original(2, older_text)
        report = TaskDetector(app.state.episodes, app.state.proposals, Extraction(),
                              app.state.conversation_lock, tasks=app.state.tasks).run(
                                  with_model=True, source_ids=[request['id']])
        assert (report.analyzed, report.proposed, report.failed) == (1, 1, 0)
        candidate, = read(client.get('/api/v1/task-candidates'))
        task = read(client.post(f"/api/v1/task-candidates/{candidate['id']}/accept", json={'title': title}))
        assert task['provenance']['source_ref'] == 'episode:' + request['id']
        source, = WorkingMemoryStore(app.state.episodes).pending(episode_ids=[older['id']])
        assert WorkingMemoryStore(app.state.episodes).commit(source, [
            {'start': 0, 'end': len(source.episode.body), 'kind': 'historical'}], model='synthetic')
        path = f"/api/v1/tasks/{task['id']}"
        read(client.post(path + '/done'))
        episodes = [ep.to_dict() for ep in app.state.episodes.all_episodes()]
        proposals = [p.to_dict() for p in app.state.proposals.all_proposals()]
        url = conversation(client)
        for mode, question in [('auto', f'Ist {title} erledigt?'), ('memory_evidence', f'Wurde „{title}“ erledigt?')]:
            response = ask(client, url, question, mode)
            assert response['context']['task_link']['id'] == task['id']
            assert 'ausdrücklich bestätigt' in response['messages'][-1]['content']
            assert older_text not in str(response['messages'][-1])
        assert provider.calls == []
        assert [ep.to_dict() for ep in app.state.episodes.all_episodes()] == episodes
        assert [p.to_dict() for p in app.state.proposals.all_proposals()] == proposals
        assert app.state.claims.all_claims() == []
        literal = ask(client, conversation(client), 'Was steht in den Quellen zu „Nur die erste Seite ist geprüft“?',
                      'memory_evidence')['messages'][-1]
        assert 'Nur die erste Seite ist geprüft' in literal['content']
        assert literal['metadata']['context']['source_links'][0]['episode_id'] == older['id']
        read(client.post(f"/api/v1/episodes/{request['id']}/ignore"))
        old = read(client.get(url))
        assert 'task_link' not in old['context']
        assert title not in str(old['messages'][-1])
        assert read(client.get(path))['status'] == 'done'
        read(client.post(f"/api/v1/episodes/{request['id']}/reopen"))
        assert 'task_link' not in read(client.get(url))['context']
        assert ask(client, conversation(client), f'Wie ist der Status der Aufgabe {task["id"]}?')['context']['task_link']
        assert app.state.episodes.get(request['id']).body.endswith(request_text)
        assert app.state.episodes.get(older['id']).body.endswith(older_text)


def test_mail_completion_stamp_differs_from_explicit_confirmation_and_does_not_follow_reopen(session, monkeypatch):
    from icarus_memory.aufgaben_post import Lauf
    from tests.test_aufgaben_post import ANNA, ICH, JETZT, LENA, aufgabe, bitte_von_anna, mail
    from messlatte.uhr import eingefrorene_zeit

    app, client, _ = session
    episodes = app.state.episodes
    lauf = Lauf(app.state.tasks, episodes, app.state.proposals, eigene=lambda: [ICH], jetzt=lambda: JETZT)
    monkeypatch.setattr('icarus_memory.aufgaben_post.lauf_fuer', lambda _: lauf)
    lauf.schritt()
    request = bitte_von_anna(episodes)
    task = aufgabe(app.state.tasks, 'Druckdaten an Anna schicken', quelle=request)
    mailed = mail(episodes, 'AW: Druckdaten', 'Ich melde mich.', von=LENA, an=[ANNA],
                  kennung='synthetisch', antwort_auf=['a1'], stunden=2)
    assert lauf.schritt()['vorschlaege'] == 1
    proposal, = read(client.get('/api/v1/aufgaben-post/vorschlaege'))['items']
    url = conversation(client)
    question = f'Wie ist der Status der Aufgabe {task.id}?'
    with eingefrorene_zeit(JETZT):
        assert ask(client, url, question)['context']['task_link']['status'] == 'open'
        read(client.post(f"/api/v1/aufgaben-post/vorschlaege/{proposal['id']}/annehmen"))
        mailed_turn = ask(client, url, question)['messages'][-1]
        assert 'stützt sich auf eine Mail' in mailed_turn['content']
        assert 'ausdrücklich bestätigt' not in mailed_turn['content']
        assert '09:00 Uhr' in mailed_turn['content']
        read(client.post(f'/api/v1/tasks/{task.id}/done'))
        confirmed = ask(client, url, question)['messages'][-1]
        assert '09:00 Uhr' in confirmed['content'] and '11:00 Uhr' in confirmed['content']
        assert 'ausdrücklich bestätigt' in confirmed['content'] and 'Person ist nicht aufgezeichnet' in confirmed['content']
        refs = app.state.conversations.messages(url.rsplit('/', 1)[1])[-1].metadata['context']['task_status_answer']['source_refs']
        assert {ref['episode_id'] for ref in refs} == {request.id, mailed.id}
    read(client.post(f'/api/v1/episodes/{mailed.id}/ignore'))
    assert 'task_link' not in read(client.get(url))['context']
    read(client.post(f'/api/v1/tasks/{task.id}/reopen'))
    app.state.tasks.complete(task.id, mailed.occurred_at)
    generic = ask(client, url, question)['messages'][-1]
    assert 'nicht bekannt' in generic['content']
    assert 'stützt sich auf eine Mail' not in generic['content']
    assert 'ausdrücklich bestätigt' not in generic['content']
    assert generic['metadata']['context']['task_link']['status'] == 'done'


@pytest.mark.parametrize('mutation', ['archive', 'replace', 'ignore'])
def test_attachment_parent_mutation_withholds_link_and_preserves_originals(session, mutation):
    from icarus_memory.episodes import EpisodeKind

    app, client, _ = session
    episodes = app.state.episodes
    key = 'mail:' + 'a' * 64
    provenance = Provenance(SourceType.EMAIL, source_ref='synthetic:mail')
    parent, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetischer Elternbeleg', 'Originalnachricht',
                                provenance, at=AT, source_key=key)
    episodes.advance_source_head(key, None, parent.id)
    attachment_key = key + ':anhang:1'
    child, _ = episodes.record(EpisodeKind.DOCUMENT, 'Synthetischer Anhang', 'Originalanlage', provenance,
                               tags=['anhang', 'mail-parent:' + parent.id], source_key=attachment_key)
    episodes.advance_source_head(attachment_key, None, child.id)
    task = app.state.tasks.add('Anlage kontrollieren', Provenance(SourceType.EMAIL, source_ref='episode:' + child.id))
    default = episodes.belegbarer_snapshot(child.id).support_fingerprint()
    url = conversation(client)
    question = f'Wie ist der Status der Aufgabe {task.id}?'
    assert ask(client, url, question)['context']['task_link']
    if mutation == 'archive':
        episodes.mark_consolidated(parent.id, at=AT)
        assert episodes.archive_before(datetime(2026, 11, 1, tzinfo=timezone.utc)) == 1
        # Existing consumers deliberately permit the archived parent; only task recall has the stricter view.
        assert episodes.belegbarer_snapshot(child.id).support_fingerprint() == default
    elif mutation == 'replace':
        newer, _ = episodes.record(EpisodeKind.MESSAGE, 'Neue Elternfassung', 'Geänderte Nachricht', provenance, source_key=key)
        episodes.advance_source_head(key, parent.id, newer.id)
    else:
        read(client.post(f'/api/v1/episodes/{parent.id}/ignore'))
    assert 'task_link' not in read(client.get(url))['context']
    assert 'task_link' not in ask(client, url, question)['context']
    assert episodes.get(child.id).body == 'Originalanlage'
    assert app.state.tasks.get(task.id).title == task.title


def test_task_id_replacement_does_not_revive_old_saved_response(session):
    app, client, _ = session
    title = 'Ausgetauschte Aufgabe'
    from icarus_memory.episodes import EpisodeKind
    source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Original', 'Aufgabe übernehmen',
                                          Provenance(SourceType.EMAIL))
    old = app.state.tasks.from_suggestion('v-101010101010', title,
        Provenance(SourceType.INFERENCE, source_ref='episode:' + source.id), angelegt={'art': 'automatisch'})
    url = conversation(client)
    question = f'Wie ist der Status der Aufgabe {old.id}?'
    assert ask(client, url, question)['context']['task_link']
    app.state.tasks.anlage_entfernen(old.id)
    new = app.state.tasks.from_suggestion('v-101010101010', title, MANUAL)
    assert new.id == old.id
    assert 'task_link' not in read(client.get(url))['context']
    assert ask(client, url, question)['context']['task_link']['id'] == new.id


def test_history_budget_failure_is_visible_and_does_not_project_unchecked_completion(session, monkeypatch):
    from icarus_memory import tasks

    app, client, _ = session
    task = app.state.tasks.add('Viele Änderungen', MANUAL)
    app.state.tasks.confirm_completion(task.id)
    for i in range(150):
        app.state.tasks.edit(task.id, title=f'Viele Änderungen {i}')
    url = conversation(client)
    question = f'Wie ist der Status der Aufgabe {task.id}?'
    with monkeypatch.context() as patch:
        patch.setattr(tasks, '_RECALL_OPCODE_BUDGET', 1000)
        response = ask(client, url, question)
        assert 'Aufgabenverlauf nicht vollständig prüfen' in response['messages'][-1]['content']
        assert 'task_link' not in response['context']
    assert ask(client, url, question)['context']['task_link']['status'] == 'done'
    assert 'task_link' not in read(client.get(url))['messages'][1]['metadata']['context']


def test_legacy_done_snapshot_retains_saved_time_without_claiming_confirmation(session, tmp_path, monkeypatch):
    import json
    import sqlite3
    from icarus_memory.tasks import Task, TaskStatus, _migrate_v1

    app, client, _ = session
    path = tmp_path / 'legacy.db'
    task = Task(id='t-000000000001', title='Alter erledigter Stand', provenance=MANUAL,
                created_at=AT, status=TaskStatus.DONE, done_at=AT)
    with sqlite3.connect(path) as conn:
        _migrate_v1(conn)
        conn.execute('INSERT INTO tasks (id, created_at, status, title, document) VALUES (?, ?, ?, ?, ?)',
                     (task.id, AT.isoformat(), 'done', task.title, json.dumps(task.to_dict())))
        conn.execute('PRAGMA user_version=1')
    legacy = TaskStore(path)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(app.state, 'tasks', legacy)
            url = conversation(client)
            response = ask(client, url, f'Wie ist der Status der Aufgabe {task.id}?')
            reply = response['messages'][-1]['content']
            assert 'Gespeicherter Erledigungszeitpunkt' in reply
            assert 'nicht bekannt' in reply and 'nicht vollständig belegbar' in reply
            assert 'ausdrücklich bestätigt' not in reply
            assert response['context']['task_link']['status'] == 'done'
    finally:
        legacy.close()


def test_get_revalidates_reference_after_application_restart_without_writes(session):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore, server
    from tests.test_conversation_retraction import _close_app

    app, client, provider = session
    task = app.state.tasks.add('Lesbarer Neustart', MANUAL)
    url = conversation(client)
    answer = ask(client, url, f'Wie ist der Status der Aufgabe {task.id}?')
    restarted = server.create_app(SelfModelStore(MemoryBackend(), subject_id='synthetic'))
    try:
        with TestClient(restarted, headers=client.headers) as new_client:
            raw = [message.to_dict() for message in restarted.state.conversations.messages(url.rsplit('/', 1)[1])]
            assert read(new_client.get(url))['messages'] == answer['messages']
            read(client.post(f'/api/v1/tasks/{task.id}/drop'))
            dropped_history = restarted.state.tasks.history(task.id)
            assert 'task_link' not in read(new_client.get(url))['context']
            assert restarted.state.tasks.history(task.id) == dropped_history
            assert [message.to_dict() for message in restarted.state.conversations.messages(url.rsplit('/', 1)[1])] == raw
            assert restarted.state.episodes.all_episodes() == [] and restarted.state.claims.all_claims() == []
            assert provider.calls == []
    finally:
        _close_app(restarted)


def test_restored_mail_completion_keeps_its_source_proof_without_reviving_a_receipt(session):
    from icarus_memory.episodes import EpisodeKind

    app, client, _ = session
    episodes, tasks = app.state.episodes, app.state.tasks
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Bitte', 'Aster prüfen', Provenance(SourceType.EMAIL))
    completion, _ = episodes.record(EpisodeKind.MESSAGE, 'Antwort', 'Aster geprüft', Provenance(SourceType.EMAIL))
    task = tasks.from_suggestion('v-101010101011', 'Aster prüfen',
        Provenance(SourceType.INFERENCE, source_ref='episode:' + source.id), angelegt={'art': 'automatisch'})
    tasks.post_erledigen(task.id, {'episode_id': completion.id}, at=AT)
    tasks.confirm_completion(task.id)
    question = f'Wie ist der Status der Aufgabe {task.id}?'
    before_restore = conversation(client)
    confirmed = ask(client, before_restore, question)
    assert 'ausdrücklich bestätigt' in confirmed['messages'][-1]['content']

    remember = {'proposal_id': 'v-101010101011', 'episode_id': source.id,
                'titel_schluessel': 'aster', 'zitat_schluessel': 'aster prüfen'}
    # A second restore must still find the completion through the first pair.
    for _ in range(2):
        tasks.anlage_entfernen(task.id, merken=remember)
        tasks.anlage_wiederherstellen(task.id)
    assert 'task_link' not in read(client.get(before_restore))['context']

    restored_url = conversation(client)
    restored = ask(client, restored_url, question)
    assert 'stützt sich auf eine Mail' in restored['messages'][-1]['content']
    assert 'ausdrücklich bestätigt' not in restored['messages'][-1]['content']
    receipt = read(client.get(f'/api/v1/tasks/{task.id}/history', params={
        'sequence': restored['context']['task_link']['sequence']}))['items'][0]
    assert receipt['kind'] == 'auto_restored'

    read(client.post(f'/api/v1/episodes/{completion.id}/ignore'))
    assert 'task_link' not in read(client.get(restored_url))['context']
    fresh = ask(client, conversation(client), question)
    assert 'task_link' not in fresh['context']
    assert 'Erledigungszeitpunkt' not in fresh['messages'][-1]['content']
    assert tasks.get(task.id).status.value == 'done'


@pytest.mark.parametrize('attachment', [False, True], ids=['direct-source', 'attachment-parent'])
def test_archive_and_readmission_never_revive_a_saved_task_answer(session, attachment):
    from icarus_memory.episodes import EpisodeKind

    app, client, _ = session
    episodes = app.state.episodes
    provenance = Provenance(SourceType.EMAIL)
    key = 'mail:' + 'b' * 64
    parent, _ = episodes.record(EpisodeKind.MESSAGE, 'Probe', 'Unveränderte Mail',
                                provenance, at=AT, source_key=key)
    episodes.advance_source_head(key, None, parent.id)
    source = parent
    if attachment:
        source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Anlage', 'Unveränderte Anlage', provenance,
                                   source_key=key + ':anhang:1', tags=['anhang', 'mail-parent:' + parent.id])
        episodes.advance_source_head(key + ':anhang:1', None, source.id)
    task = app.state.tasks.add('Quelle prüfen', Provenance(SourceType.EMAIL, source_ref='episode:' + source.id))
    question = f'Wie ist der Status der Aufgabe {task.id}?'
    url = conversation(client)
    initial = ask(client, url, question)
    assert initial['context']['task_link']['id'] == task.id
    default_fingerprint = episodes.belegbarer_snapshot(source.id).support_fingerprint()
    original_history = app.state.tasks.history(task.id)

    episodes.mark_consolidated(parent.id, at=AT)
    assert episodes.archive_before(datetime(2026, 11, 1, tzinfo=timezone.utc)) == 1
    assert 'task_link' not in read(client.get(url))['context']
    # Use the same time to rule out tying validity to a processing timestamp.
    episodes.mark_consolidated(parent.id, produced=['synthetic-assertion'] if attachment else None, at=AT)
    assert episodes.belegbarer_snapshot(source.id).support_fingerprint() == default_fingerprint
    assert 'task_link' not in read(client.get(url))['context']
    assert ask(client, conversation(client), question)['context']['task_link']['id'] == task.id
    assert episodes.get(source.id).body == source.body
    assert app.state.tasks.history(task.id) == original_history
    assert app.state.claims.all_claims() == []


def test_restored_done_task_with_reused_id_and_unbound_tombstone_withholds_history(session, monkeypatch):
    from icarus_memory import tasks as task_module
    from icarus_memory.episodes import EpisodeKind

    monkeypatch.setattr(task_module, 'now', lambda: AT)
    app, client, _ = session
    episodes, tasks = app.state.episodes, app.state.tasks
    original, _ = episodes.record(EpisodeKind.MESSAGE, 'Bitte', 'Akten prüfen', Provenance(SourceType.EMAIL))
    completed_mail, _ = episodes.record(EpisodeKind.MESSAGE, 'Antwort', 'Akten geprüft', Provenance(SourceType.EMAIL))
    proposal_id = 'v-101010101012'
    provenance = Provenance(SourceType.INFERENCE, source_ref='episode:' + original.id)
    task = tasks.from_suggestion(proposal_id, 'Akten prüfen', provenance, angelegt={'art': 'automatisch'})
    tasks.post_erledigen(task.id, {'episode_id': completed_mail.id}, at=AT)
    tasks.anlage_entfernen(task.id, merken={'proposal_id': proposal_id, 'episode_id': original.id,
                                            'titel_schluessel': 'akten', 'zitat_schluessel': 'akten prüfen'})

    # Reusing the ID and the completion time does not establish which removal
    # belongs to the older stored document.
    other = tasks.from_suggestion(proposal_id, 'Akten prüfen', provenance, angelegt={'art': 'automatisch'})
    tasks.complete(other.id, AT)
    tasks.anlage_entfernen(other.id)
    restored, _ = tasks.anlage_wiederherstellen(task.id)
    assert restored.erledigt_grund['episode_id'] == completed_mail.id
    response = ask(client, conversation(client), f'Wie ist der Status der Aufgabe {task.id}?')
    assert 'Aufgabenverlauf nicht vollständig prüfen' in response['messages'][-1]['content']
    assert 'task_link' not in response['context']
