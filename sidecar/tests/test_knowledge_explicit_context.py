"""Explicit contact context ranks evidence without guessing identities."""
import pytest

from icarus_memory.knowledge_search import HybridKnowledgeSearch
from tests.test_context import _knowledge_agent
from tests.test_knowledge_context_relevance import _ConstantEmbedder


@pytest.mark.parametrize('hybrid', [False, True])
def test_explicit_person_context_prefers_match_without_discarding_other_record(tmp_path, hybrid):
    agent, provider, episodes, accept = _knowledge_agent(tmp_path)
    target, _ = accept('Alex Winter im Einkauf ist unter einkauf@example.invalid erreichbar.')
    other, _ = accept('Alex Winter an der Schule ist unter schule@example.invalid erreichbar.')
    if hybrid:
        agent._knowledge_search = HybridKnowledgeSearch.prepare(
            agent._knowledge, episodes.support_snapshot, [target.id, other.id], _ConstantEmbedder())
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + target.id, 'claim:' + other.id}
    assert turn.context['items'][0]['assertion_id'] == 'claim:' + target.id
    assert target.statement in str(provider.messages[-1])
    assert other.statement in str(provider.messages[-1])
    assert agent._knowledge.get(other.id).subject_ref == other.subject_ref
    assert turn.context['knowledge_retrieval']['explicit_context_preferred'] == 1


@pytest.mark.parametrize('question', [
    'Welche Adresse gehört zu Alex Winter?',
    'Vergleiche Alex Winter aus dem Einkauf und aus der Schule.',
    'Wo erreiche ich Alex Winter, aber nicht aus dem Einkauf?',
    'Welche Nachricht hat Alex Winter über den Einkauf geschrieben?',
    'Arbeitet Alex Winter im Einkauf?',
    'Welche Belege zeigen, dass Alex Winter im Einkauf arbeitet?',
    'Wer weiß, ob Alex Winter im Einkauf arbeitet?',
    'Wer behauptet, Alex Winter im Einkauf sei erreichbar?',
    'Welche Belege gibt es dafür, Alex Winter im Einkauf zu verorten?',
    'Wo erreiche ich Alex Winter aus dem Einkauf bzw. aus der Schule?',
    'Wo erreiche ich Alex Winter aus dem Einkauf beziehungsweise aus der Schule?',
])
def test_no_context_choice_for_ambiguity_negation_comparison_or_content_query(tmp_path, question):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Alex Winter im Einkauf ist unter einkauf@example.invalid erreichbar.')
    second, _ = accept('Alex Winter an der Schule ist unter schule@example.invalid erreichbar.')
    turn = agent.send(question)
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + first.id, 'claim:' + second.id}
    assert turn.context['knowledge_retrieval']['explicit_context_preferred'] == 0


def test_unknown_context_is_not_assumed_to_belong_to_other_person(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    target, _ = accept('Alex Winter im Einkauf sendet den Entwurf.')
    unknown, _ = accept('Alex Winter sendet eine Nachricht.')
    turn = agent.send('Was hat Alex Winter aus dem Einkauf gesendet?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + target.id, 'claim:' + unknown.id}


def test_multiple_people_with_requested_context_stay_distinct(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Alex Winter im Einkauf ist unter eins@example.invalid erreichbar.')
    second, _ = accept('Alex Winter im Einkauf ist unter zwei@example.invalid erreichbar.')
    other, _ = accept('Alex Winter an der Schule ist unter schule@example.invalid erreichbar.')
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['subject_ref'] for i in turn.context['items']} == {first.subject_ref, second.subject_ref, other.subject_ref}
    assert {i['subject_ref'] for i in turn.context['items'][:2]} == {first.subject_ref, second.subject_ref}


@pytest.mark.parametrize('unusable', ['withdrawn', 'dependency', 'oversized'])
def test_unusable_scope_evidence_does_not_suppress_remaining_evidence(tmp_path, unusable):
    agent, _, episodes, accept = _knowledge_agent(tmp_path)
    root, source = accept('Freigabe der Rollenübersicht.')
    text = 'Alex Winter im Einkauf sendet den Entwurf.'
    if unusable == 'oversized':
        text += ' X' * 5000
    target, target_source = accept(text, [root.id] if unusable == 'dependency' else [])
    other, _ = accept('Alex Winter an der Schule ist unter schule@example.invalid erreichbar.')
    if unusable == 'withdrawn':
        episodes.ignore(target_source.id)
    if unusable == 'dependency':
        episodes.ignore(source.id)
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + other.id}


def test_unrelated_name_and_context_are_not_suppressed(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Alex Winter im Einkauf ist erreichbar.')
    other, _ = accept('Vera König ist für den Einkauf ebenfalls erreichbar.')
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + first.id, 'claim:' + other.id}


def test_same_confirmed_identity_keeps_both_contexts(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Alex Winter im Einkauf ist erreichbar.')
    second, _ = accept('Alex Winter an der Schule ist ebenfalls erreichbar.', subject_ref=first.subject_ref, predicate="school_contact")
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + first.id, 'claim:' + second.id}


@pytest.mark.parametrize('other_text', [
    'Alex Winter an der Schule arbeitet nicht mehr dort, sondern im Einkauf.',
    'Alex Winter an der Schule und Alex Winter im Einkauf senden den Entwurf gemeinsam.',
    'Alex Winter an der Schule arbeitete früher im Einkauf.',
])
def test_mixed_or_changed_context_remains_evidence(tmp_path, other_text):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Alex Winter im Einkauf ist erreichbar.')
    second, _ = accept(other_text)
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + first.id, 'claim:' + second.id}


@pytest.mark.parametrize('other_text', [
    'Alex Winter bei Siemens ist als Einkaufsleiter unter alex@example.invalid erreichbar.',
    'Alex Winter in Berlin ist als Einkaufsleiter unter alex@example.invalid erreichbar.',
])
def test_compatible_context_is_not_proof_of_a_different_person(tmp_path, other_text):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    first, _ = accept('Alex Winter im Einkauf ist unter einkauf@example.invalid erreichbar.')
    second, _ = accept(other_text)
    turn = agent.send('Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert {i['assertion_id'] for i in turn.context['items']} == {'claim:' + first.id, 'claim:' + second.id}
    assert second.statement in str(provider.messages[-1])
