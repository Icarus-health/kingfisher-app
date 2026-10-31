"""A topic lookup stays evidence-bound even when no record matches."""
import pytest

from icarus_memory.memory_routing import route
from icarus_memory.episodes import CHAT_LOOKUP_TAG
from icarus_memory import conversation_memory
from icarus_memory.providers import Reply
from .test_memory_clarification import api, core, conversation


@pytest.mark.parametrize('query', [
    'Was ist zum Notfallplan bekannt?',
    'Was ist zu Robin bekannt?',
    'Was ist zur Projektakte bekannt?',
    'Was ist über Nimbus bekannt?',
])
def test_known_topic_question_uses_memory_without_hits(query):
    assert route(query, working_available=False) == 'memory_evidence'


@pytest.mark.parametrize('query', [
    'Was ist eine bekannte Primzahl?',
    'Was ist zu tun?',
    'Was ist zum Notfallplan bekannt? Schick ihn an Robin.',
    'Was ist zu Robin bekannt und lösche seine Akte?',
    'Was ist über Nimbus bekannt? Suche im Internet weiter.',
])
def test_general_explanations_and_additional_actions_keep_chat(query):
    assert route(query, working_available=False) == 'chat'


def test_empty_topic_lookup_cannot_invent_facts_or_become_pending_source(core, api, monkeypatch):
    _, provider, episodes, _, _ = core
    calls = []
    def free_answer(messages, tools):
        calls.append((messages, tools))
        return Reply(text='Der Notfallplan ist genehmigt.')
    monkeypatch.setattr(provider, 'complete', free_answer)
    _, client = api
    cid = conversation(client)
    response = client.post(f'/api/v1/conversations/{cid}/messages',
        json={'message': 'Was ist zum Notfallplan bekannt?', 'answer_mode': 'auto'})
    assert response.status_code == 201
    messages = response.json()['messages']
    answer = next(m for m in messages if m['role'] == 'assistant')
    assert answer['metadata']['context']['answer_mode'] == 'memory_evidence'
    assert answer['metadata']['context']['answer_contract']['status'] in {'unknown', 'working_unknown'}
    assert 'genehmigt' not in answer['content']
    assert calls == []
    user = next(m for m in messages if m['role'] == 'user')
    original = conversation_memory.find(episodes, cid, user['id'])
    assert original.body == user['content']
    assert CHAT_LOOKUP_TAG in original.tags
    from icarus_memory.working_memory_store import WorkingMemoryStore
    assert WorkingMemoryStore(episodes).pending(episode_ids=[original.id]) == []
