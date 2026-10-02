"""Unresolved alternatives must reach the answer boundary, including races."""
import pytest
import json

from icarus_memory.episodes import EpisodeKind
from icarus_memory.evidence_answer import EvidenceAnswer
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence
from icarus_memory.providers import Reply
from tests.test_context_identity import AT, core
from tests.test_memory_clarification import api, conversation, post


def candidate(app, episodes, *, subject='project:aurora', text='Aurora hat Frist 26. September.'):
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Offene Terminänderung', text,
        Provenance(source_type=SourceType.EMAIL, source_ref='synthetic:change'), at=AT)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=subject,
        predicate='observed_email', value=text, statement=text, rationale='Zu prüfen',
        evidence=[Evidence(source.id, text, source.digest)], at=AT)
    return proposal, source


@pytest.mark.parametrize('path', ['answer_memory', 'send'])
def test_pending_alternative_blocks_confident_answer_without_model(core, api, path):
    agent, provider, episodes, _, accept = core
    app, _ = api
    claim, _ = accept('project:aurora', 'Aurora hat Frist 22. September.')
    proposal, _ = candidate(app, episodes)
    turn = getattr(agent, path)('Welche Frist gilt für Aurora?')
    assert turn.context['answer_contract']['status'] == 'conflict'
    assert turn.context['answer_contract']['selected_assertion_ids'] == []
    assert 'Widerspruch' in turn.reply
    assert '22. September' not in str(turn.to_dict())
    assert '26. September' not in str(turn.to_dict())
    assert provider.calls == []
    assert app.state.proposals.get(proposal.id).state.value == 'pending'
    assert app.state.claims.get(claim.id).status.value == 'active'


@pytest.mark.parametrize('during', ['provider', 'renderer'])
def test_new_pending_conflict_during_selection_discards_old_answer(core, api, monkeypatch, during):
    agent, provider, episodes, _, accept = core
    app, _ = api
    accept('project:aurora', 'Aurora hat Frist 22. September.')
    def choose(*args, **kwargs):
        if during == 'provider':
            candidate(app, episodes)
        return Reply(text='{"version":1,"kind":"evidence","evidence_ids":["E1"]}')
    monkeypatch.setattr(provider, 'complete', choose)
    if during == 'renderer':
        original = EvidenceAnswer.render_readable
        def render(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            candidate(app, episodes)
            return result
        monkeypatch.setattr(EvidenceAnswer, 'render_readable', render)
    turn = agent.answer_memory('Welche Frist gilt für Aurora?')
    assert turn.context['answer_contract']['status'] == 'conflict'
    assert 'September' not in str(turn.to_dict())


def test_clarification_cannot_bypass_new_pending_conflict(core, api):
    agent, provider, episodes, _, accept = core
    app, _ = api
    accept('person:alex-a', 'Alex Einkauf hat Frist 22. September.')
    accept('person:alex-b', 'Alex Schule hat Frist 25. September.')
    prior = agent.answer_memory('Welche Frist gilt für Alex?')
    assert prior.context['answer_contract']['status'] == 'clarify'
    candidate(app, episodes, subject='person:alex-a', text='Alex Einkauf hat Frist 26. September.')
    turn = agent.continue_memory('Einkauf', prior.context)
    assert turn.context['answer_contract']['status'] == 'conflict'
    assert 'September' not in str(turn.to_dict())
    assert provider.calls == []
    # Choosing the other, unrelated identity is still allowed.
    other = agent.continue_memory('Schule', prior.context)
    assert other.context['answer_contract']['status'] == 'evidence'
    assert '25. September' in other.reply


def test_unselected_deadline_conflict_does_not_block_selected_owner(core, api, monkeypatch):
    agent, provider, episodes, _, accept = core
    app, client = api
    accept('project:aurora', 'Aurora hat Frist 22. September.')
    candidate(app, episodes)
    text = 'Mira betreut Aurora.'
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Betreuung', text,
        Provenance(source_type=SourceType.EMAIL, source_ref='synthetic:owner'), at=AT)
    owner, _ = app.state.knowledge_service.propose(subject_ref='project:aurora',
        predicate='owner', value='Mira', statement=text, rationale='Betreuung',
        evidence=[Evidence(source.id, text, source.digest)], at=AT)
    app.state.knowledge_service.accept(owner.id, supersedes=[], at=AT)
    def choose(messages, tools):
        rows = json.loads(messages[1]['content'].split('\n', 1)[1])['evidence']
        selected = next(row['evidence_id'] for row in rows if row['predicate'] == 'owner')
        return Reply(text=json.dumps({'version': 1, 'kind': 'evidence', 'evidence_ids': [selected]}))
    monkeypatch.setattr(provider, 'complete', choose)
    turn = agent.answer_memory('Wer betreut Aurora?')
    assert turn.context['answer_contract']['status'] == 'evidence'
    # Die Frist der anderen Aussage (22. September) erscheint nicht; das Datum des Quellenhinweises schon.
    assert text in turn.reply and '22. September' not in turn.reply
    cid = conversation(client)
    message = post(client, cid, 'Wer betreut Aurora?')
    assert message['metadata']['context']['answer_contract']['status'] == 'evidence'
    assert text in message['content']
    view = client.get(f'/api/v1/conversations/{cid}').json()
    assert [item['statement'] for item in view['context']['items']] == [text]


def test_later_message_without_context_cannot_expose_disputed_sidebar(core, api, monkeypatch):
    _, provider, episodes, _, accept = core
    app, client = api
    accept('project:aurora', 'Aurora hat Frist 22. September.')
    monkeypatch.setattr(provider, 'complete', lambda *args: Reply(
        text='{"version":1,"kind":"evidence","evidence_ids":["E1"]}'))
    cid = conversation(client)
    post(client, cid, 'Welche Frist gilt für Aurora?')
    candidate(app, episodes)
    app.state.conversations.add_message(cid, 'assistant', 'Eine allgemeine Rückfrage.', metadata={})
    view = client.get(f'/api/v1/conversations/{cid}').json()
    assert view['context']['items'] == []
    assert view['context']['answer_contract']['status'] == 'conflict'
    assert '22. September' not in str(view)
