"""Synthetic prepared-memory fixtures; never load application configuration.

The scoped diagnostic clock patches only this standalone evaluator process.
Callers must run attempts serially. Prepared claims do not test extraction.
"""
from __future__ import annotations

import copy
import hashlib
import json
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory import agent as agent_module
from icarus_memory import claims, context, knowledge_context, model
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.policy import Policy
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.providers import Provider
from memory_probe_support import validate_case


def case_hash(case):
    return hashlib.sha256(json.dumps(case, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def clock_supplement(case):
    return ('\nDiagnostischer Geschäftszeitpunkt: ' + case['clock_utc'] +
            '; Geschäftszeitzone: ' + case['timezone'] +
            '. Relative Zeitangaben wie heute beziehen sich auf diesen Zeitpunkt. '
            'Dies ist eine synthetische Diagnose, keine Freigabe für Aktionen.')


@contextmanager
def business_clock(case):
    """Restore all imported clock functions and the exact system prompt on exit."""
    moment = utc(case['clock_utc'])
    with ExitStack() as stack:
        for module in (model, claims, context, knowledge_context, agent_module):
            stack.enter_context(patch.object(module, 'now', lambda: moment))
        stack.enter_context(patch.object(agent_module, 'SYSTEM_PROMPT',
                                        agent_module.SYSTEM_PROMPT + clock_supplement(case)))
        yield


@dataclass
class ProbeFixture:
    agent: Agent
    source_ids: dict[str, str]
    claim_ids: dict[str, str]
    episodes: EpisodeStore
    claims: ClaimStore
    proposals: ProposalStore
    audit: AuditLog
    expected_manifest: str

    def close(self):
        # Each store owns a separate SQLite connection.
        for store in (self.audit, self.claims, self.proposals, self.episodes):
            store.close()


def build_fixture(case: dict, root: Path, provider: Provider) -> ProbeFixture:
    validate_case(case)
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Fixture root must not be a symlink')
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'fixture.json'
    if any(path.is_symlink() for path in root.iterdir()):
        raise ValueError('Fixture files must not be symlinks')
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if manifest is not None and manifest['case_sha256'] != case_hash(case):
        raise ValueError('Fixture belongs to another case')
    if manifest is None and any(root.iterdir()):
        raise ValueError('New fixture requires an empty directory')
    with ExitStack() as cleanup:
        episodes = EpisodeStore(root / 'episodes.sqlite3'); cleanup.callback(episodes.close)
        proposals = ProposalStore(root / 'proposals.sqlite3'); cleanup.callback(proposals.close)
        claim_store = ClaimStore(root / 'claims.sqlite3'); cleanup.callback(claim_store.close)
        audit = AuditLog(root / 'audit.sqlite3'); cleanup.callback(audit.close)
        source_ids, claim_ids = {}, {}
        if manifest is not None:
            source_ids, claim_ids = manifest['source_ids'], manifest['claim_ids']
            for identifier in source_ids:
                episodes.get(identifier)
            for identifier in claim_ids:
                claim_store.get(identifier)
        else:
            with business_clock(case):
                moment = utc(case['clock_utc'])
                for entity in case['entities']:
                    claim_store.entities.create(entity['kind'], entity['label'], explicit_id=entity['id'])
                sources = {}
                for source in case['sources']:
                    observed = utc(source.get('observed_at_utc', case['clock_utc']))
                    kind = EpisodeKind.DOCUMENT if source['source_type'] == 'document' else EpisodeKind.MESSAGE
                    episode, _ = episodes.record(kind, 'Synthetic ' + source['id'], source['text'],
                        Provenance(source_type=SourceType(source['source_type']),
                                   source_ref=f"synthetic:{case['id']}:{source['id']}", captured_at=observed),
                        at=observed)
                    if episode.id in source_ids:
                        raise ValueError('Unsupported aliased fixture sources: distinct IDs deduplicate to one episode')
                    source_ids[episode.id] = source['id']
                    sources[source['id']] = episode
                service = KnowledgeService(episodes=episodes, proposals=proposals, claims=claim_store)
                pending = list(case['assertions'])
                created = {}
                while pending:
                    ready = next((row for row in pending if set(row.get('depends_on_assertion_ids', []) +
                        row.get('supersedes_assertion_ids', [])) <= created.keys()), None)
                    if ready is None:
                        raise ValueError('Unresolvable assertion dependencies')
                    episode = sources[ready['source_id']]
                    statement = ready.get('statement', episode.body)
                    quote = ready.get('quote', episode.body)
                    if quote not in episode.body:
                        raise ValueError('Prepared quote must occur in the named source')
                    proposal, _ = service.propose(subject_ref=ready['subject_ref'], predicate=ready['predicate'],
                        value=ready['value'], statement=statement, rationale='Explicit synthetic prepared claim',
                        evidence=[Evidence(episode.id, quote, episode.digest)],
                        depends_on=[created[key] for key in ready.get('depends_on_assertion_ids', [])],
                        valid_from=utc(ready['valid_from_utc']) if ready.get('valid_from_utc') else None,
                        valid_until=utc(ready['valid_to_utc']) if ready.get('valid_to_utc') else None, at=moment)
                    claim = service.accept(proposal.id,
                        supersedes=[created[key] for key in ready.get('supersedes_assertion_ids', [])], at=moment)
                    created[ready['id']] = claim.id
                    claim_ids[claim.id] = ready['id']
                    pending.remove(ready)
                for source in case['sources']:
                    if source.get('excluded_from_retrieval'):
                        episodes.ignore(sources[source['id']].id)
                manifest_path.write_text(json.dumps(dict(case_sha256=case_hash(case),
                                                        source_ids=source_ids, claim_ids=claim_ids)))
                manifest_path.chmod(0o600)
        callback = copy.deepcopy(case.get('calendar_callback'))
        agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='synthetic-probe'),
                      policy=Policy(), audit=audit, tools={}, provider=provider,
                      knowledge=claim_store, episodes=episodes, max_rounds=1,
                      calendar_context=(lambda: copy.deepcopy(callback)) if callback else None)
        # Vor Ausführung eingefrorene kanonische Zeilen, unabhängig vom Produktionsrenderer.
        expected_manifest = json.dumps({'version': 1,
            'claims': {key: claim_store.get(key).to_dict() for key in claim_ids},
            'sources': {key: episodes.get(key).to_dict() for key in source_ids}},
            sort_keys=True, ensure_ascii=False)
        result = ProbeFixture(agent, source_ids, claim_ids, episodes, claim_store, proposals, audit, expected_manifest)
        cleanup.pop_all()
        return result
