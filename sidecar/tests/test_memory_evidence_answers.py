"""Real Agent/SQLite boundaries for the explicit evidence-only answer path."""
import copy
import json
from datetime import timedelta

import pytest
from tests.test_context_identity import core, AT
from tests.test_knowledge_time import change_source
from icarus_memory import knowledge_context
from icarus_memory.agent import EgressBlocked
from icarus_memory.providers import Reply, ProviderError, ToolCall


def choose(messages,tools):
    assert tools==[]
    return Reply(text=json.dumps({'version':1,'kind':'evidence','evidence_ids':['E1']}))


def test_accepted_paraphrase_is_labelled_as_stored_claim_not_source_quote(core, tmp_path, monkeypatch):
    from icarus_memory.claims import KnowledgeService
    from icarus_memory.proposals import Evidence, ProposalStore
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    agent, provider, episodes, claims, _ = core
    claims.entities.create('project', 'Aurora', explicit_id='project:aurora')
    original = 'Mira: Wenn die Freigabe kommt, prüfe ich Aurora am Freitag; bis dahin gibt es keine feste Zusage.'
    paraphrase = 'Mira prüft Aurora am Freitag nur nach Freigabe; eine feste Zusage liegt noch nicht vor.'
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetic source', original,
        Provenance(source_type=SourceType.EMAIL, source_ref='synthetic:aurora'), at=AT)
    proposals = ProposalStore(tmp_path / 'paraphrase-proposals.sqlite3')
    try:
        service = KnowledgeService(episodes=episodes, claims=claims, proposals=proposals)
        candidate, _ = service.propose(subject_ref='project:aurora', predicate='review_status',
            value='bedingt, keine feste Zusage', statement=paraphrase,
            evidence=[Evidence(source.id, original, source.digest)], rationale='Approved paraphrase', at=AT)
        service.accept(candidate.id, supersedes=[], at=AT)
    finally:
        proposals.close()
    monkeypatch.setattr(provider, 'complete', choose)
    turn = agent.answer_memory('Was wissen wir über Aurora?')
    assert turn.context['answer_contract']['status'] == 'evidence'
    assert 'Gespeicherte Aussage: ' + paraphrase in turn.reply
    assert 'Gespeicherter Wert: bedingt, keine feste Zusage' in turn.reply
    assert 'Quelle [1]: E-Mail „Synthetic source“' in turn.reply
    assert 'synthetic:aurora' not in turn.reply
    assert turn.context['quellen'][0]['source_ref'] == 'synthetic:aurora'
    assert turn.context['quellen'][0]['assertion_id'] == turn.context['answer_contract']['selected_assertion_ids'][0]
    assert '"' + paraphrase + '"' not in turn.reply
    assert 'In den ausgewählten Belegen steht:' not in turn.reply
    assert 'Wert laut Quelle:' not in turn.reply
    assert turn.context['answer_contract']['semantic_validation'] is False


@pytest.mark.parametrize('outcome', ['evidence', 'invalid', 'error', 'withdrawn', 'tools'])
def test_bounded_selection_preserves_validation_and_withdrawal(core, monkeypatch, outcome):
    agent, provider, episodes, claims, accept = core
    claim, source = accept('project:aurora', 'Aurora ORIGINAL_BOUND_SECRET wurde nicht versendet.')
    calls = []
    def bounded(messages, *, max_tokens, schema):
        calls.append(messages)
        assert max_tokens == 256
        assert schema['additionalProperties'] is False
        assert schema['properties']['evidence_ids']['items']['enum'] == ['E1']
        assert 'ORIGINAL_BOUND_SECRET' in json.dumps(messages)
        if outcome == 'error':
            raise ProviderError('private transport details')
        if outcome == 'withdrawn':
            change_source(episodes, source.id, source_ref='synthetic:changed')
        if outcome == 'invalid':
            return Reply(text='{"version":1,"kind":"evidence","evidence_ids":["E99"]}')
        if outcome == 'tools':
            return Reply(text='FORGED_SUCCESS', tool_calls=[ToolCall('x', 'send_mail', {})])
        return choose(messages, [])
    monkeypatch.setattr(provider, 'complete_json', bounded, raising=False)
    monkeypatch.setattr(provider, 'complete', lambda *a: pytest.fail('unbounded completion or retry'))
    turn = agent.answer_memory('Was wissen wir über Aurora?')
    assert len(calls) == 1
    assert turn.context['answer_contract']['status'] == (
        'invalidated' if outcome == 'withdrawn' else 'evidence' if outcome == 'evidence' else 'fallback')
    assert turn.used_tools == [] and turn.approvals == []
    assert 'private transport details' not in turn.reply and 'FORGED_SUCCESS' not in turn.reply
    if outcome == 'withdrawn':
        assert 'ORIGINAL_BOUND_SECRET' not in turn.reply
        assert turn.context['items'] == []
        assert turn.context['answer_contract']['selected_assertion_ids'] == []
    else:
        assert turn.context['answer_contract']['selected_assertion_ids'] == ['claim:' + claim.id]


@pytest.mark.parametrize('finish_reason', ['stop', 'length'])
def test_real_provider_sends_closed_schema_and_rejects_incomplete_selection(core, monkeypatch, finish_reason):
    from icarus_memory.providers import OpenAICompatible
    agent, _, episodes, claims, accept = core
    accept('project:aurora', 'Aurora wurde nicht versendet.')
    requests, timeouts = [], []
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'choices': [{'finish_reason': finish_reason,
                                 'message': {'content': choose([], []).text}}]}
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            requests.append(kwargs['json'])
            return Response()
    monkeypatch.setattr('icarus_memory.providers._http',
                        lambda timeout=120: (timeouts.append(timeout) or Client()))
    agent = agent.scoped(OpenAICompatible('synthetic', base_url='http://127.0.0.1:11434/v1'), frozenset())
    turn = agent.answer_memory('Was wissen wir über Aurora?')
    assert len(requests) == 1 and timeouts == [30.0]
    assert requests[0]['max_tokens'] == 256 and requests[0]['reasoning_effort'] == 'none'
    assert 'tools' not in requests[0]
    assert requests[0]['response_format']['json_schema']['schema']['properties']['evidence_ids']['items']['enum'] == ['E1']
    assert turn.context['answer_contract']['status'] == ('evidence' if finish_reason == 'stop' else 'fallback')
    assert 'nicht versendet' in turn.reply


@pytest.mark.parametrize('bounded', [False, True])
def test_routed_local_provider_preserves_actual_selection_capability(core, monkeypatch, bounded):
    from icarus_memory.routing_provider import RoutedProvider
    agent, provider, episodes, claims, accept = core
    accept('project:aurora', 'Aurora wurde nicht versendet.')
    calls = []
    def legacy(messages, tools):
        calls.append('legacy')
        return choose(messages, tools)
    monkeypatch.setattr(provider, 'complete', legacy)
    if bounded:
        def select_json(messages, **kwargs):
            calls.append('bounded')
            raise ProviderError('failed bounded request')
        monkeypatch.setattr(provider, 'complete_json', select_json, raising=False)
    agent = agent.scoped(RoutedProvider(provider, []), frozenset())
    turn = agent.answer_memory('Was wissen wir über Aurora?')
    assert calls == ['bounded' if bounded else 'legacy']
    assert turn.context['answer_contract']['status'] == ('fallback' if bounded else 'evidence')


def test_answer_preserves_original_fields_and_sources_without_model_prose(core,monkeypatch):
    agent,provider,episodes,claims,accept=core
    claim,source=accept('project:aurora','Aurora verschoben auf den 22.09.2026 um 14:00 Europe/Berlin.')
    monkeypatch.setattr(provider,'complete',choose)
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Wann ist Aurora?')
    assert '22.09.2026' in turn.reply and '14:00' in turn.reply and 'Europe/Berlin' in turn.reply
    assert 'synthetic:1' not in turn.reply and 'Quelle [1]: E-Mail „Synthetic source“' in turn.reply
    assert [q['source_ref'] for q in turn.context['quellen']]==['synthetic:1']
    assert turn.context['answer_contract']['status']=='evidence'
    assert turn.context['answer_contract']['selected_assertion_ids']==['claim:'+claim.id]
    assert turn.context['answer_contract']['semantic_validation'] is False
    assert turn.approvals==[] and turn.used_tools==[] and turn.memory_candidate_drafts==[]


def test_ambiguous_records_force_choice_and_never_call_model(core):
    agent,provider,episodes,claims,accept=core
    accept('person:alex-buying','Alex im Einkauf: buying@example.invalid.')
    accept('person:alex-school','Alex an der Schule: school@example.invalid.')
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Welche Adresse hat Alex?')
    assert provider.calls==[]
    assert 'Einkauf' in turn.reply and 'Schule' in turn.reply
    assert turn.context['answer_contract']['status']=='clarify'
    assert 'synthetic:' not in turn.reply and turn.reply.count('Quelle [') == 2
    assert {q['source_ref'] for q in turn.context['quellen']} == {'synthetic:1', 'synthetic:2'}


@pytest.mark.parametrize('bad', ['Ich habe die Mail versendet!', '{"version":1,"kind":"evidence","evidence_ids":["E999"]}'])
def test_invalid_model_output_is_not_published(core,monkeypatch,bad):
    agent,provider,episodes,claims,accept=core
    accept('project:aurora','Aurora ist nur vorbereitet; Versand unbekannt.')
    monkeypatch.setattr(provider,'complete',lambda messages,tools:Reply(text=bad))
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Wurde Aurora versendet?')
    assert bad not in turn.reply
    assert turn.context['answer_contract']['status']=='fallback'
    assert 'Versand unbekannt' in turn.reply and 'synthetic:1' not in turn.reply
    assert [q['source_ref'] for q in turn.context['quellen']] == ['synthetic:1']


@pytest.mark.parametrize('phase',['before','during','error'])
def test_source_change_suppresses_originals_and_model_selection(core,monkeypatch,phase):
    agent,provider,episodes,claims,accept=core
    _,source=accept('project:aurora','Aurora SECRET_BEFORE_CHANGE 22.09.2026 14:00.')
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    if phase=='before':
        original=agent._knowledge_context_items
        def changed(query):
            items=original(query);change_source(episodes,source.id,source_ref='synthetic:changed');return items
        monkeypatch.setattr(agent,'_knowledge_context_items',changed)
    else:
        def changed(messages,tools):
            change_source(episodes,source.id,source_ref='synthetic:changed')
            if phase=='error':raise ProviderError('private exception')
            return choose(messages,tools)
        monkeypatch.setattr(provider,'complete',changed)
    turn=agent.answer_memory('Wann ist Aurora?')
    assert turn.context['invalidated'] is True
    assert turn.context['items']==[]
    assert 'knowledge_retrieval' not in turn.context
    assert turn.context['knowledge_inputs']=={}
    assert turn.context['answer_contract']['selected_assertion_ids']==[]
    assert 'SECRET_BEFORE_CHANGE' not in turn.reply
    assert 'private exception' not in turn.reply
    if phase=='before':assert provider.calls==[]


def test_time_expiry_during_inference_invalidates_without_revision_change(core,monkeypatch):
    agent,provider,episodes,claims,accept=core
    accept('project:aurora','Aurora SECRET_EXPIRED.',until=AT+timedelta(seconds=1))
    revision=claims.revision
    def expires(messages,tools):
        monkeypatch.setattr(knowledge_context,'now',lambda:AT+timedelta(seconds=2))
        return choose(messages,tools)
    monkeypatch.setattr(provider,'complete',expires)
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Was ist mit Aurora?')
    assert claims.revision==revision
    assert turn.context['invalidated']
    assert 'SECRET_EXPIRED' not in turn.reply


def test_remote_provider_never_receives_or_displays_memory(core):
    agent,provider,episodes,claims,accept=core
    accept('project:aurora','Aurora LOCAL_SECRET.')
    provider.is_local=False
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Was ist mit Aurora?')
    assert provider.calls==[] and 'LOCAL_SECRET' not in turn.reply
    assert turn.context['answer_contract']['status']=='local_only'


def test_read_only_mode_cannot_execute_model_tools_or_mutate_history(core,monkeypatch):
    agent,provider,episodes,claims,accept=core
    accept('project:aurora','Aurora vorbereiten.')
    agent._history=[{'role':'assistant','content':'UNSUPPORTED_OLD_CLAIM'}]
    history=copy.deepcopy(agent._history)
    def tool_request(messages,tools):
        assert tools==[] and 'UNSUPPORTED_OLD_CLAIM' not in json.dumps(messages)
        return Reply(text='SEND_SUCCESS',tool_calls=[ToolCall('x','unknown',{})])
    monkeypatch.setattr(provider,'complete',tool_request)
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Was ist mit Aurora?')
    assert 'SEND_SUCCESS' not in turn.reply
    assert turn.used_tools==[] and turn.approvals==[]
    assert turn.context['answer_contract']['status']=='fallback'
    assert agent._history==history


def test_empty_memory_is_bounded_unknown_and_uses_no_model(core):
    agent,provider,*_=core
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Welche Farbe hat mein Fahrrad?')
    assert provider.calls==[]
    assert turn.context['answer_contract']['status']=='unknown'
    assert turn.context['items']==[]


def test_same_record_with_multiple_sources_is_not_identity_ambiguity(core,monkeypatch,tmp_path):
    agent,provider,episodes,claims,accept=core
    accept('person:sam','Sam geschäftlich work@example.invalid.')
    from icarus_memory.claims import KnowledgeService
    from icarus_memory.proposals import Evidence, ProposalStore
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    text='Sam privat personal@example.invalid.'
    episode,_=episodes.record(EpisodeKind.MESSAGE,'Synthetic',text,
        Provenance(source_type=SourceType.EMAIL,source_ref='synthetic:second'),at=AT)
    proposals=ProposalStore(tmp_path/'second-proposals.sqlite3')
    try:
        service=KnowledgeService(episodes=episodes,proposals=proposals,claims=claims)
        proposal,_=service.propose(subject_ref='person:sam',predicate='private_email',value=text,
            statement=text,evidence=[Evidence(episode.id,text,episode.digest)],rationale='Synthetic',at=AT)
        service.accept(proposal.id,supersedes=[],at=AT)
    finally:
        proposals.close()
    seen=[]
    def complete(messages,tools):
        seen.append(messages);return choose(messages,tools)
    monkeypatch.setattr(provider,'complete',complete)
    assert hasattr(agent,'answer_memory'), 'Explicit validated memory-answer path missing'
    turn=agent.answer_memory('Welche Adresse hat Sam?')
    assert len(seen)==1
    assert turn.context['answer_contract']['status']=='evidence'


def test_egress_guard_stops_provider(core,monkeypatch):
    agent,provider,_,_,accept=core
    accept('project:aurora','Aurora confidential text.')
    def blocked(messages):
        raise EgressBlocked('blocked')
    monkeypatch.setattr(agent,'assert_egress_allowed',blocked)
    with pytest.raises(EgressBlocked):
        agent.answer_memory('Aurora?')
    assert provider.calls==[]


def test_provider_failure_returns_only_originals(core,monkeypatch):
    agent,provider,_,_,accept=core
    accept('project:aurora','Aurora source only.')
    def fails(messages,tools):
        raise ProviderError('PRIVATE_PROVIDER_DETAILS')
    monkeypatch.setattr(provider,'complete',fails)
    turn=agent.answer_memory('Aurora?')
    assert turn.context['answer_contract']['status']=='fallback'
    assert 'Aurora source only' in turn.reply
    assert 'PRIVATE_PROVIDER_DETAILS' not in str(turn.to_dict())


@pytest.mark.parametrize('question',[None,'', ' ', 'x'*20001])
def test_invalid_question_never_calls_provider(core,question):
    agent,provider,*_=core
    with pytest.raises(ValueError):agent.answer_memory(question)
    assert provider.calls==[]


def test_missing_provider_does_not_retrieve_memory(core,monkeypatch):
    agent,*_=core
    agent._provider=None
    def forbidden(question):raise AssertionError('must not retrieve')
    monkeypatch.setattr(agent,'_knowledge_context_items',forbidden)
    turn=agent.answer_memory('Aurora?')
    assert turn.context['items']==[]
    assert turn.context['answer_contract']['model_called'] is False


@pytest.mark.parametrize('original', [
    'Falls wir Atlas versenden würden, könnte Mira ihn prüfen.',
    'Bitte versende Atlas; Versand ist nicht bestätigt.',
    'Wir haben entschieden, Atlas morgen zu versenden.',
    'Mira schrieb: Ich habe Atlas am 19. September versendet.',
    'Atlas wurde ausdrücklich nicht versendet.',
    'Ob Atlas versendet wurde, ist unbekannt.',
    'Mira zitiert Jan: Atlas wurde versendet. Mira hat es nicht geprüft.',
    'Mira bevorzugt kurze Berichte für Atlas. Die Vorliebe des Nutzers ist unbekannt.',
])
def test_action_states_and_attribution_are_original_evidence_not_new_facts(core,monkeypatch,original):
    agent,provider,episodes,claims,accept=core
    claim,source=accept('project:atlas',original)
    monkeypatch.setattr(provider,'complete',choose)
    before=[a.to_dict() for a in agent._store.export().assertions]
    turn=agent.answer_memory('Was wissen wir über Atlas?')
    assert original in turn.reply
    assert turn.context['answer_contract']['status']=='evidence'
    assert turn.context['answer_contract']['semantic_validation'] is False
    assert not(turn.used_tools or turn.approvals or turn.memory_candidate_drafts)
    assert [a.to_dict() for a in agent._store.export().assertions]==before
