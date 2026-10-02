"""A clarification chooses current original evidence, never an inferred identity."""
import copy
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from icarus_memory import knowledge_context
from icarus_memory.evidence_answer import EvidenceAnswer
from icarus_memory.server import create_app
from .test_context_identity import AT, core
from .test_knowledge_time import change_source
from .test_conversation_retraction import _close_app


def pending(core):
    agent, provider, episodes, claims, accept = core
    first, source = accept('person:alex-purchase', 'Alex Winter im Einkauf: buying@example.invalid.',
                           until=AT + timedelta(seconds=10))
    second, other = accept('person:alex-school', 'Alex Winter an der Schule: school@example.invalid.')
    turn = agent.answer_memory('Welche Adresse hat Alex Winter?')
    assert turn.context['answer_contract']['status'] == 'clarify'
    return turn, first, source, second, other


@pytest.mark.parametrize('choice', ['den Alex aus dem Einkauf', 'Einkauf', '[1]', 'Nummer 1'])
def test_followup_returns_only_chosen_original_without_model_or_actions(core, choice):
    agent, provider, *_ = core
    previous, first, _, _, _ = pending(core)
    # Retrieval order is deliberately irrelevant to the natural-language cases.
    if '1' in choice:
        expected = previous.context['items'][0]['statement']
    else:
        expected = 'Alex Winter im Einkauf: buying@example.invalid.'
    history = copy.deepcopy(agent._history)
    assert hasattr(agent, 'continue_memory'), 'Source-bound clarification continuation is missing'
    turn = agent.continue_memory(choice, previous.context)
    assert turn.context['answer_contract']['status'] == 'evidence'
    assert expected in turn.reply
    assert len(turn.context['items']) == 1
    assert turn.context['items'][0]['statement'] == expected
    assert len(turn.context['knowledge_inputs']) == 1
    assert provider.calls == [] and agent._history == history
    assert turn.used_tools == [] and turn.approvals == []
    assert 'PRIVATE-REGISTRY-LABEL' not in turn.reply


@pytest.mark.parametrize('choice', ['Alex', 'nicht Einkauf', 'Einkauf oder Schule',
    'Einkauf und schick ihm eine Mail', 'Nummer 9', 'person:alex-purchase',
    'buying@example.invalid', 'Nummer 1, aber nicht den Einkauf', 'Schule Einkauf'])
def test_ambiguous_or_unsupported_clue_repeats_current_choices(core, choice):
    agent, provider, *_ = core
    previous, *_ = pending(core)
    turn = agent.continue_memory(choice, previous.context)
    assert turn.context['answer_contract']['status'] == 'clarify'
    assert 'buying@example.invalid' in turn.reply and 'school@example.invalid' in turn.reply
    assert provider.calls == [] and turn.used_tools == []


@pytest.mark.parametrize('change', ['withdraw_selected', 'withdraw_other', 'metadata', 'expire', 'revision'])
def test_all_previous_choices_must_remain_current(core, monkeypatch, change):
    agent, provider, episodes, claims, _ = core
    previous, first, source, second, other = pending(core)
    if change == 'withdraw_selected': episodes.ignore(source.id)
    elif change == 'withdraw_other': episodes.ignore(other.id)
    elif change == 'metadata': change_source(episodes, other.id, source_ref='synthetic:changed')
    elif change == 'expire': monkeypatch.setattr(knowledge_context, 'now', lambda: AT + timedelta(seconds=11))
    else: claims.retract(second.id, reason='Synthetic withdrawal', at=AT)
    turn = agent.continue_memory('Einkauf', previous.context)
    assert turn.context['answer_contract']['status'] == 'invalidated'
    assert turn.context['items'] == [] and turn.context['knowledge_inputs'] == {}
    assert turn.context['answer_contract']['selected_assertion_ids'] == []
    assert 'example.invalid' not in str(turn.to_dict())
    assert provider.calls == []


def test_invalidation_during_render_suppresses_selection(core, monkeypatch):
    agent, _, episodes, *_ = core
    previous, _, _, _, other = pending(core)
    original = EvidenceAnswer.render_readable
    def changing(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        episodes.ignore(other.id)
        return result
    monkeypatch.setattr(EvidenceAnswer, 'render_readable', changing)
    turn = agent.continue_memory('Einkauf', previous.context)
    assert turn.context['answer_contract']['status'] == 'invalidated'
    assert 'example.invalid' not in str(turn.to_dict())


@pytest.mark.parametrize('tamper', ['lineage', 'order', 'projection', 'status', 'missing'])
def test_malformed_pending_context_fails_closed(core, tamper):
    agent, *_ = core
    previous, *_ = pending(core)
    context = copy.deepcopy(previous.context)
    if tamper == 'lineage': context['knowledge_inputs'] = {}
    elif tamper == 'order': context['answer_contract']['selected_assertion_ids'].reverse()
    elif tamper == 'projection': context['items'][0]['knowledge_projection']['statement'] = 'FORGED'
    elif tamper == 'status': context['answer_contract']['status'] = 'evidence'
    else: context = None
    turn = agent.continue_memory('1', context)
    assert turn.context['answer_contract']['status'] == 'invalidated'
    assert 'example.invalid' not in str(turn.to_dict()) and 'FORGED' not in str(turn.to_dict())


def test_remote_followup_never_returns_pending_local_data(core):
    agent, provider, *_ = core
    previous, *_ = pending(core)
    provider.is_local = False
    turn = agent.continue_memory('Einkauf', previous.context)
    assert turn.context['answer_contract']['status'] == 'local_only'
    assert 'example.invalid' not in str(turn.to_dict()) and provider.calls == []


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    agent, _, episodes, claims, _ = core
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'api'))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    app = create_app(agent._store, agent=agent)
    # create_app reuses the actual Agent's canonical temporary stores.
    yield app, TestClient(app)
    # core owns these two stores.
    app.state.episodes = app.state.claims = None
    _close_app(app)


def conversation(client):
    return client.post('/api/v1/conversations', json={}).json()['conversation']['id']


def post(client, identifier, message, **fields):
    response = client.post(f'/api/v1/conversations/{identifier}/messages',
        json={'message': message, 'answer_mode': 'memory_evidence', **fields})
    assert response.status_code == 201
    return response.json()['messages'][-1]


def test_api_continuation_uses_only_immediate_same_conversation_context(core, api):
    pending(core)
    app, client = api
    one, two = conversation(client), conversation(client)
    first = post(client, one, 'Welche Adresse hat Alex Winter?')
    assert first['metadata']['context']['answer_contract']['status'] == 'clarify'
    foreign = post(client, two, '1')
    assert foreign['metadata']['context']['answer_contract']['status'] == 'unknown'
    # A GET/reopen must not remove the pending clarification.
    assert client.get(f'/api/v1/conversations/{one}').status_code == 200
    selected = post(client, one, 'den Alex aus dem Einkauf')
    assert 'buying@example.invalid' in selected['content']
    assert 'school@example.invalid' not in selected['content']
    assert selected['metadata']['context']['answer_contract']['status'] == 'evidence'
    again = post(client, one, '1')
    assert again['metadata']['context']['answer_contract']['status'] == 'unknown'


def test_api_new_question_can_leave_pending_clarification(core, api):
    pending(core)
    _, client = api
    identifier = conversation(client)
    post(client, identifier, 'Alex Winter?')
    result = post(client, identifier, 'Fahrradfarbe?', new_question=True)
    assert result['metadata']['context']['answer_contract']['status'] == 'unknown'
    assert 'example.invalid' not in result['content']


def test_api_revision_change_is_explicitly_invalidated_not_silently_retrieved(core, api):
    _, _, episodes, _, _ = core
    _, _, source, _, _ = pending(core)
    _, client = api
    identifier = conversation(client)
    post(client, identifier, 'Alex Winter?')
    episodes.ignore(source.id)
    result = post(client, identifier, 'Einkauf')
    assert result['metadata']['context']['answer_contract']['status'] == 'invalidated'
    assert 'example.invalid' not in result['content']


def test_api_explicit_chat_does_not_implicitly_select_pending_memory(core, api):
    pending(core)
    _, client = api
    identifier = conversation(client)
    post(client, identifier, 'Alex Winter?')
    response = client.post(f'/api/v1/conversations/{identifier}/messages', json={'message': '1', 'answer_mode': 'chat'})
    result = response.json()['messages'][-1]
    assert result['content'] == 'Synthetische Antwort.'
    assert 'answer_contract' not in result['metadata']['context']
    # The intervening default-chat turn also retires the earlier clarification.
    assert post(client, identifier, '1')['metadata']['context']['answer_contract']['status'] == 'unknown'


def test_api_reopens_sqlite_pending_context_without_agent_state(core, api):
    from icarus_memory.conversations import ConversationStore
    pending(core)
    app, client = api
    identifier = conversation(client)
    post(client, identifier, 'Alex Winter?')
    database = app.state.conversations._conn.execute('PRAGMA database_list').fetchone()[2]
    app.state.conversations.close()
    app.state.conversations = ConversationStore(database)
    app.state.agent = app.state.agent.scoped(provider=core[1], allowed_tools=[])
    result = post(client, identifier, 'Einkauf')
    assert result['metadata']['context']['answer_contract']['status'] == 'evidence'
    assert 'buying@example.invalid' in result['content'] and 'school@example.invalid' not in result['content']


def test_retry_of_memory_error_cannot_silently_switch_to_tool_enabled_chat(core, api, monkeypatch):
    pending(core)
    app, client = api
    identifier = conversation(client)
    post(client, identifier, 'Alex Winter?')
    original = app.state.agent.continue_memory
    def fail(*args): raise RuntimeError('synthetic temporary failure')
    monkeypatch.setattr(app.state.agent, 'continue_memory', fail)
    failed = post(client, identifier, 'Einkauf')
    assert failed['status'] == 'error'
    monkeypatch.setattr(app.state.agent, 'continue_memory', original)
    response = client.post(f"/api/v1/conversations/{identifier}/messages/{failed['id']}/retry")
    assert response.status_code == 201
    result = response.json()['messages'][-1]
    assert result['metadata']['context']['answer_contract']['status'] == 'evidence'
    assert 'buying@example.invalid' in result['content'] and core[1].calls == []


def test_transitive_source_withdrawal_invalidates_even_unselected_choice(core):
    agent, _, episodes, _, accept = core
    basis, basis_source = accept('project:basis', 'Eigenständige Grundlage.')
    accept('person:one', 'Alex Einkauf.', depends_on=[basis.id])
    accept('person:two', 'Alex Schule.')
    previous = agent.answer_memory('Alex?')
    episodes.ignore(basis_source.id)
    result = agent.continue_memory('Schule', previous.context)
    assert result.context['answer_contract']['status'] == 'invalidated'
    assert 'Alex' not in str(result.to_dict())


def test_same_person_different_scopes_still_requires_unique_visible_choice(core):
    agent, provider, _, _, accept = core
    accept('person:alex', 'Alex arbeitet hier.', scope='project:a')
    accept('person:alex', 'Alex arbeitet hier.', scope='project:b')
    previous = agent.answer_memory('Alex?')
    result = agent.continue_memory('Alex', previous.context)
    assert result.context['answer_contract']['status'] == 'clarify'
    assert len(result.context['items']) == 2 and provider.calls == []


def test_negated_source_is_not_used_as_positive_literal_clue(core):
    agent, provider, _, _, accept = core
    accept('person:one', 'Alex arbeitet nicht im Einkauf.')
    accept('person:two', 'Alex arbeitet an der Schule.')
    previous = agent.answer_memory('Alex?')
    result = agent.continue_memory('Einkauf', previous.context)
    assert result.context['answer_contract']['status'] == 'clarify' and provider.calls == []
