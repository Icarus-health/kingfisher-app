"""Real Agent/SQLite path with synthetic prepared knowledge and a fake model.

These are recorder integration tests, not inference or ingestion qualification.
"""
import json
from datetime import datetime, timezone

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.policy import Policy
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.providers import Reply
from memory_probe_support import RecordingProvider, score_retrieval


class SyntheticProvider:
    name = 'synthetic'
    model = 'no-inference'
    is_local = True

    def complete(self, messages, tools):
        assert tools == []
        return Reply(text='Unbewertete Testantwort.', model=self.model)


def test_real_agent_records_distinct_claims_and_honors_source_exclusion(tmp_path):
    at = datetime(2026, 9, 13, 7, tzinfo=timezone.utc)
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    audit = AuditLog(tmp_path / 'audit.sqlite3')
    try:
        service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
        rows = []
        for suffix in ('a', 'b'):
            entity = claims.entities.create('person', 'Alex Winter', explicit_id=f'person:alex-{suffix}')
            text = f'Alex Winter: alex@firma-{suffix}.invalid'
            episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetischer Beleg', text,
                                         Provenance(source_type=SourceType.EMAIL,
                                                    source_ref=f'synthetic:{suffix}', captured_at=at), at=at)
            proposal, _ = service.propose(subject_ref=entity['id'], predicate='email',
                                         value=f'alex@firma-{suffix}.invalid', statement=text,
                                         rationale='Expliziter synthetischer Fixturezustand',
                                         evidence=[Evidence(episode.id, text, episode.digest)], at=at)
            claim = service.accept(proposal.id, supersedes=[], at=at)
            rows.append((claim, episode))
        provider = RecordingProvider(SyntheticProvider())
        agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='synthetic'),
                      policy=Policy(), audit=audit, tools={}, provider=provider,
                      knowledge=claims, episodes=episodes, max_rounds=1)
        first = agent.send('Welche Adresse hat Alex Winter?')
        mapping = {f'claim:{claim.id}': f'S{index+1}' for index, (claim, _) in enumerate(rows)}
        actual = {mapping[item['assertion_id']] for item in first.context['items']
                  if item['assertion_id'] in mapping}
        assert score_retrieval({'S1', 'S2'}, set(), actual)['missing'] == []
        request = json.dumps(provider.calls[0]['request'], ensure_ascii=False)
        for claim, episode in rows:
            # Claim IDs are local metadata; the current prompt carries source refs.
            assert episode.provenance.source_ref in request
            assert episode.body in request
        assert rows[0][0].subject_ref != rows[1][0].subject_ref
        assert provider.calls[0]['semantic_verdict'] is None

        episodes.ignore(rows[0][1].id)
        second = agent.send('Welche Adresse hat Alex Winter?')
        actual = {mapping[item['assertion_id']] for item in second.context['items']
                  if item['assertion_id'] in mapping}
        result = score_retrieval({'S2'}, {'S1'}, actual)
        assert result['missing'] == []
        assert result['forbidden_seen'] == []
        request = json.dumps(provider.calls[1]['request'], ensure_ascii=False)
        assert rows[0][1].body not in request
        assert rows[1][1].body in request
    finally:
        audit.close()
        proposals.close()
        claims.close()
        episodes.close()


def test_dependency_chain_survives_reopen_but_not_source_revocation(tmp_path):
    """Reopen actual SQLite files twice; a hidden ancestor still gates retrieval."""
    from contextlib import ExitStack

    at = datetime(2026, 9, 13, 7, tzinfo=timezone.utc)

    def open_stores(stack):
        stores = (EpisodeStore(tmp_path / 'episodes.sqlite3'),
                  ClaimStore(tmp_path / 'knowledge.sqlite3'),
                  ProposalStore(tmp_path / 'proposals.sqlite3'),
                  AuditLog(tmp_path / 'audit.sqlite3'))
        for store in stores:
            stack.callback(store.close)
        return stores

    def query(claims, episodes, audit):
        provider = RecordingProvider(SyntheticProvider())
        agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='synthetic'),
                      policy=Policy(), audit=audit, tools={}, provider=provider,
                      knowledge=claims, episodes=episodes, max_rounds=1)
        turn = agent.send('Was macht Kranz?')
        return ({item['assertion_id'] for item in turn.context['items']},
                json.dumps(provider.calls[0]['request'], ensure_ascii=False))

    with ExitStack() as stack:
        episodes, claims, proposals, audit = open_stores(stack)
        service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
        entity = claims.entities.create('person', 'Kranz', explicit_id='person:kranz')
        rows = []
        for index, text in enumerate(('Der Vertrag wurde bestätigt.',
                                      'Die Projektleitung wurde festgelegt.',
                                      'Kranz leitet das Atlasvorhaben.')):
            episode, _ = episodes.record(
                EpisodeKind.MESSAGE, 'Synthetischer Beleg', text,
                Provenance(source_type=SourceType.EMAIL,
                           source_ref=f'synthetic:chain-{index}', captured_at=at), at=at)
            proposal, _ = service.propose(
                subject_ref=entity['id'], predicate=f'fact-{index}', value=text,
                statement=text, rationale='Vorbereitete synthetische Abhängigkeit',
                evidence=[Evidence(episode.id, text, episode.digest)],
                depends_on=[rows[-1][0].id] if rows else [], at=at)
            rows.append((service.accept(proposal.id, supersedes=[], at=at), episode))
        final_id = f'claim:{rows[-1][0].id}'
        final_text = rows[-1][0].statement
        root_source_id = rows[0][1].id
        ids, request = query(claims, episodes, audit)
        assert final_id in ids and final_text in request

    # Positive control: persistent knowledge works with entirely new stores/Agent.
    with ExitStack() as stack:
        episodes, claims, proposals, audit = open_stores(stack)
        ids, request = query(claims, episodes, audit)
        assert final_id in ids and final_text in request
        assert claims.get(rows[-1][0].id).depends_on == [rows[-2][0].id]
        episodes.ignore(root_source_id)

    # The root does not match the query; its revocation must still remove the leaf.
    with ExitStack() as stack:
        episodes, claims, proposals, audit = open_stores(stack)
        ids, request = query(claims, episodes, audit)
        assert final_id not in ids
        assert final_text not in request
        # Stored history survives exclusion: retrieval, not silent deletion, changed.
        assert claims.get(rows[-1][0].id).statement == final_text
