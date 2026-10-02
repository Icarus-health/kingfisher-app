"""Belegdaten sind portabel; ihre Nutzung benötigt eine lokale Entscheidung."""
from dataclasses import dataclass
from copy import deepcopy
from sqlite3 import Error as SqliteError
from uuid import uuid4
from datetime import datetime
import re
from .model import Kind, SourceType
from .proposals import ProposalKind, ProposalState, ProposalError
from .support_types import MAX_EVIDENCE, MAX_ID, MAX_QUOTE, parse_support, identity
from .source_snapshot import quote_matches
from .self_model_basis import digest, _RANK


@dataclass(frozen=True)
class SupportAssessment:
    recognized: str
    complete_private: bool
    usable: bool
    signature: str


def authorization(assertion, support, operation, at):
    return {'version': 1, 'assertion_id': assertion.id,
            'assertion_content_fingerprint': identity(assertion), 'support_hash': digest(support),
            'operation': operation, 'authorization_id': uuid4().hex, 'authorized_at': at.isoformat()}


def valid_authorization(value, assertion, support, *, match_support=True):
    if not (isinstance(value, dict) and set(value) == {'version','assertion_id','assertion_content_fingerprint',
            'support_hash','operation','authorization_id','authorized_at'}
            and type(value['version']) is int and value['version'] == 1
            and value['operation'] in ('acceptance','reassessment')
            and isinstance(value['authorization_id'], str) and re.fullmatch('[0-9a-f]{32}', value['authorization_id'])
            and isinstance(value['authorized_at'], str)
            and value['assertion_id'] == assertion.id
            and value['assertion_content_fingerprint'] == identity(assertion)
            and isinstance(value['support_hash'], str) and re.fullmatch('[0-9a-f]{64}', value['support_hash'])
            and (not match_support or value['support_hash'] == digest(support))):
        return False
    try:
        return datetime.fromisoformat(value['authorized_at']).tzinfo is not None
    except ValueError:
        return False


def corresponds(proposal, assertion):
    return (proposal.kind is ProposalKind.ASSERTION and proposal.state is ProposalState.ACCEPTED
            and proposal.produced == assertion.id and proposal.statement == assertion.statement
            and (proposal.assertion_kind or Kind.STATE) is assertion.kind
            and proposal.supersedes == assertion.supersedes
            and assertion.provenance.source_type is SourceType.INFERENCE)


class EpisodeSupportResolver:
    def __init__(self, proposals, episodes, snapshot_provider=None):
        self.proposals, self.episodes = proposals, episodes
        self.snapshot_provider = snapshot_provider or episodes.support_snapshot

    def build(self, *, at, local, max_sensitivity, prospective=None):
        return SupportBuild(self, at=at, local=local, max_sensitivity=max_sensitivity, prospective=prospective)


class SupportBuild:
    def __init__(self, resolver, *, at, local, max_sensitivity, prospective=None):
        self.resolver, self.at, self.local = resolver, at, local
        self.ceiling = _RANK[max_sensitivity]
        self.prospective = prospective
        self.sources, self.producers, self.results = {}, {}, {}
        self.nodes = set()

    def _reserve(self, kind, identifier):
        key = (kind, identifier)
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= MAX_ID:
            raise ValueError('Ungültige Belegkennung')
        if key not in self.nodes and len(self.nodes) >= 128:
            raise ValueError('Belegbudget überschritten')
        self.nodes.add(key)

    def source(self, identifier):
        self._reserve('source', identifier)
        if identifier not in self.sources:
            self.sources[identifier] = deepcopy(self.resolver.snapshot_provider(identifier))
        return self.sources[identifier]

    def producer(self, assertion):
        if assertion.id not in self.producers:
            self._reserve('lookup', assertion.id)
            values = self.resolver.proposals.accepted_self_model_support(assertion.id)
            for proposal in values:
                self._reserve('producer', proposal.id)
            orphan = self.resolver.episodes.produced_support_links(assertion.id)
            self.producers[assertion.id] = (deepcopy(values), list(orphan))
        return self.producers[assertion.id]

    def capture(self, proposal, *, require_current=True):
        if not 1 <= len(proposal.evidence) <= MAX_EVIDENCE:
            raise ValueError('Belege fehlen oder sind zu umfangreich')
        entries = []
        for evidence in proposal.evidence:
            if (not isinstance(evidence.quote, str) or not 1 <= len(evidence.quote) <= MAX_QUOTE
                    or not evidence.digest):
                raise ValueError('Unvollständiger Beleg')
            snapshot = self.source(evidence.episode_id)
            if (snapshot is None or snapshot.episode.kind.value == 'summary'
                    or snapshot.episode.digest != evidence.digest
                    or not quote_matches(evidence.quote, snapshot.episode.body)
                    or require_current and not snapshot.current()):
                raise ValueError('Originalbeleg ist nicht verfügbar')
            entries.append({'episode_id': evidence.episode_id, 'digest': evidence.digest,
                            'quote': evidence.quote, 'source_key': snapshot.source_key,
                            'metadata_digest': snapshot.metadata_digest, 'support_generation': snapshot.generation})
        return parse_support({'version': 1, 'proposal_id': proposal.id, 'episodes': entries})

    def assess(self, assertion):
        if assertion.id in self.results:
            return self.results[assertion.id]
        try:
            result = self._assess(assertion)
        except (ValueError, TypeError, KeyError, AttributeError, RuntimeError, SqliteError, ProposalError):
            result = SupportAssessment('unknown', False, False, digest('unavailable'))
        self.results[assertion.id] = result
        return result

    def _assess(self, assertion):
        values, orphan = self.producer(assertion)
        if not values:
            recognized = 'orphan' if orphan else 'typed_without_producer' if assertion.episode_support else 'none'
            complete = recognized == 'none' and (assertion.provenance.source_type is not SourceType.INFERENCE or bool(assertion.derived_from))
            return SupportAssessment(recognized, complete, complete, digest([recognized, complete]))
        if len(values) != 1 or not corresponds(values[0], assertion):
            return SupportAssessment('accepted', False, False, digest('ambiguous'))
        proposal = values[0]
        if not self.local or _RANK[proposal.sensitivity] > self.ceiling:
            return SupportAssessment('accepted', False, False, digest('protected'))
        current = self.capture(proposal, require_current=False)
        source_state = [self.sources[e['episode_id']].support_fingerprint() for e in current['episodes']]
        commitment = self.resolver.proposals.support_authorization(proposal.id)
        support = parse_support(assertion.episode_support)
        if commitment is not None and not valid_authorization(commitment, assertion, support, match_support=False):
            return SupportAssessment('accepted', False, False, digest('invalid_authorization'))
        usable = (support == current and valid_authorization(commitment, assertion, support)
                  and all(self.sources[e['episode_id']].current() for e in current['episodes']))
        if self.prospective == assertion.id:
            usable = all(self.sources[e['episode_id']].current() for e in current['episodes'])
        return SupportAssessment('accepted', True, usable, digest({'producer': proposal.to_dict(),
            'commitment': commitment, 'support': support, 'sources': source_state, 'usable': usable}))
