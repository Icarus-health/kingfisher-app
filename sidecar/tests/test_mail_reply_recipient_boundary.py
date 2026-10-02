"""Ein fremdes Reply-To darf kein früheres Absenderwissen freigeben."""
import json
from dataclasses import replace

import pytest
from fastapi import HTTPException

from tests.test_mail_conversation_flow import (
    memory_reply_app, suggest_memory_reply, prepare_suggested, approval_urls,
)
from tests.test_conversation_retraction import _close_app


@pytest.fixture
def setup(tmp_path, monkeypatch):
    app, first, second, episode, client = memory_reply_app(tmp_path, monkeypatch)
    yield app, first, second, episode, client
    client.close()
    _close_app(app)


@pytest.mark.parametrize('reply_to', [
    'other@example.invalid',
    'sender@example.invalid, other@example.invalid',
    'Kein Empfänger',
    'sender@example.invalid\r\nBcc: other@example.invalid',
])
def test_other_or_ambiguous_recipient_never_gets_prior_sources(setup, reply_to):
    app, first, second, episode, client = setup
    second.item = replace(second.item, reply_to=reply_to)
    original = app.state.agent.provider.complete_json
    seen = []
    def inspect_input(messages, **kwargs):
        seen.append(json.dumps(messages, ensure_ascii=False))
        return original(messages, **kwargs)
    app.state.agent.provider.complete_json = inspect_input
    response = client.post('/api/v1/messages/work:1/reply-suggestion', json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['sources'] == [] and result['context_token'] is None
    assert result['basis'] == 'message_and_instruction'
    assert result['source_status'] == 'recipient_scope'
    assert all(episode.body not in request for request in seen)
    assert first.sent == second.sent == []


@pytest.mark.parametrize('reply_to', ['', 'Alex <SENDER@example.invalid>'])
def test_same_single_recipient_keeps_useful_source_context(setup, reply_to):
    app, _, second, episode, client = setup
    second.item = replace(second.item, reply_to=reply_to)
    suggestion = suggest_memory_reply(client)
    assert suggestion['sources'][0]['episode_id'] == episode.id
    assert second.sent == []


def test_ambiguous_sender_does_not_authorize_first_parsed_address(setup):
    app, _, second, episode, client = setup
    second.item = replace(second.item, sender='sender@example.invalid, other@example.invalid',
                          reply_to='sender@example.invalid')
    response = client.post('/api/v1/messages/work:1/reply-suggestion', json={})
    assert response.status_code == 200
    assert response.json()['sources'] == []
    assert response.json()['context_token'] is None


@pytest.mark.parametrize('route', [0, 1])
def test_reply_address_change_blocks_already_queued_source_reply(setup, route):
    app, _, second, _, client = setup
    second.item = replace(second.item, reply_to='sender@example.invalid')
    payload, action = prepare_suggested(client, suggest_memory_reply(client))
    second.item = replace(second.item, reply_to='other@example.invalid')
    response = client.post(approval_urls(payload, action)[route],
                           json={'granted': True, 'confirmation': 'sender@example.invalid'})
    assert response.status_code == 409
    assert second.sent == []


@pytest.mark.parametrize('boundary', [None, {'account': 'work', 'address': 'other@example.invalid'},
                                      {'account': 'private', 'address': 'sender@example.invalid'}])
def test_saved_context_without_matching_recipient_boundary_is_hidden(setup, boundary):
    from icarus_memory.mail_reply_suggestions import validate_context, sources_eligible
    app, _, second, _, client = setup
    second.item = replace(second.item, reply_to='sender@example.invalid')
    token = suggest_memory_reply(client)['context_token']
    context = validate_context(app, token)
    if boundary is None:
        context.pop('recipient_scope', None)
    else:
        context['recipient_scope'] = boundary
    assert not sources_eligible(app, context)


def test_two_different_mail_snapshots_cannot_queue_source_reply(setup):
    """Erster Abruf liefert fremdes Reply-To, die Quellenprüfung wieder das alte."""
    app, _, second, _, client = setup
    second.item = replace(second.item, reply_to='sender@example.invalid')
    suggestion = suggest_memory_reply(client)
    original = second.item
    changed = [replace(original, reply_to='other@example.invalid')]
    second.message = lambda uid: changed.pop(0) if changed else original
    response = client.post('/api/v1/messages/work:1/reply', json={
        'body': suggestion['body'], 'context_token': suggestion['context_token']})
    assert response.status_code == 409
    assert client.get('/approvals').json() == []
    assert second.sent == []


@pytest.mark.parametrize('change', ['recipient', 'account'])
def test_final_sink_checks_actual_payload_scope_even_with_matching_execution_copy(setup, change):
    """Der letzte Versandweg prüft den tatsächlichen Empfänger, nicht nur zwei Kopien."""
    from icarus_memory.server import _mail_sink
    app, first, second, _, client = setup
    second.item = replace(second.item, reply_to='sender@example.invalid')
    suggestion = suggest_memory_reply(client)
    payload = {'to': 'sender@example.invalid', 'account_id': 'work', 'subject': 'Re: Projekt Atlas',
               'body': suggestion['body'], 'in_reply_to': second.item.message_id}
    payload['to' if change == 'recipient' else 'account_id'] = 'other@example.invalid' if change == 'recipient' else 'private'
    app.state.mail_reply_execution.token = suggestion['context_token']
    app.state.mail_reply_execution.arguments = dict(payload)
    with pytest.raises(HTTPException) as error:
        _mail_sink(app)(payload)
    assert error.value.status_code == 409
    assert first.sent == second.sent == []
