"""Reine Wissensprojektion und begrenzte Aufnahme exakt geprüfter Originale.

Aufnahme und Neuprüfung verwenden getrennte Builds; Generationen belegen nur
Kontinuität der gelieferten Quellen, niemals eine neue Freigabe alter Claims.
"""
import copy
import hashlib
import json

from . import knowledge_context
from .claims import ClaimError
from .episodes import EpisodeError
from .source_snapshot import canonical_instant

FORMAT = 'knowledge-context-v3'
PREFIX = '- [knowledge] '
ROW_BYTES = 8 * 1024
TOTAL_BYTES = 32 * 1024
TIME_NOTE = ('claim_created_at ist die Annahmezeit der Aussage; recorded_at ist die Importzeit der Quelle. '
             'occurred_at ist ausschließlich ihre Ereigniszeit und bleibt bei unbekannter Zeit null. '
             'Gültigkeit gilt ab valid_from einschließlich bis valid_until ausschließlich. '
             'primary_evidence ist der erste gespeicherte Beleg, keine vollständige Chronologie.')


def instant(value):
    return canonical_instant(value.isoformat()) if value is not None else None


def project(claim, snapshot, reason):
    episode = snapshot.episode
    return {'format': FORMAT, 'assertion_id': 'claim:' + claim.id,
            'statement': claim.statement, 'subject_ref': claim.subject_ref,
            'target_ref': claim.target_ref, 'scope_ref': claim.scope_ref,
            'predicate': claim.predicate, 'value': claim.value,
            'claim_created_at': instant(claim.created_at),
            'valid_from': instant(claim.valid_from), 'valid_until': instant(claim.valid_until),
            'primary_evidence': {'episode_id': episode.id, 'digest': episode.digest,
                'source_type': episode.provenance.source_type.value,
                'source_ref': episode.provenance.source_ref,
                'occurred_at': instant(episode.occurred_at), 'recorded_at': instant(episode.recorded_at)},
            'reason': reason}


def valid_projection(value):
    fields = {'format', 'assertion_id', 'statement', 'subject_ref', 'target_ref', 'scope_ref',
              'predicate', 'value', 'claim_created_at', 'valid_from', 'valid_until', 'primary_evidence', 'reason'}
    source_fields = {'episode_id', 'digest', 'source_type', 'source_ref', 'occurred_at', 'recorded_at'}
    if not isinstance(value, dict) or set(value) != fields or value['format'] != FORMAT:
        return False
    source = value['primary_evidence']
    if not isinstance(source, dict) or set(source) != source_fields:
        return False
    if (any(not isinstance(value[key], str) for key in
            ('assertion_id', 'statement', 'subject_ref', 'predicate', 'value', 'reason'))
            or any(value[key] is not None and not isinstance(value[key], str) for key in ('target_ref', 'scope_ref'))
            or any(not isinstance(source[key], str) or not source[key] for key in ('episode_id', 'digest', 'source_type'))
            or (source['source_ref'] is not None and not isinstance(source['source_ref'], str))
            or value['claim_created_at'] is None or source['recorded_at'] is None):
        return False
    try:
        return (all(canonical_instant(value[key]) == value[key] for key in ('claim_created_at', 'valid_from', 'valid_until'))
                and all(canonical_instant(source[key]) == source[key] for key in ('occurred_at', 'recorded_at')))
    except (ValueError, TypeError, AttributeError):
        return False


def serialize(projection):
    return json.dumps(projection, ensure_ascii=False, allow_nan=False)


def signature(projection, generations):
    semantic = {key: value for key, value in projection.items() if key not in {'reason', 'format'}}
    return {'version': 1, 'claim_id': projection['assertion_id'][6:],
            'primary_episode_id': projection['primary_evidence']['episode_id'],
            'projection_sha256': hashlib.sha256(json.dumps(semantic, ensure_ascii=False, sort_keys=True,
                                                         allow_nan=False).encode()).hexdigest(),
            'source_generations': dict(sorted(generations.items()))}


class KnowledgeInputBuild:
    """128 Claims und separat 128 Originale je Aufbau, ohne Verdrängung."""
    def __init__(self, claims, snapshot_provider, *, at=None):
        self.claims = claims
        self.snapshot_provider = snapshot_provider
        self.at = at or knowledge_context.now()
        self._claims = {}
        self._sources = {}

    def claim(self, identifier):
        if identifier not in self._claims:
            if len(self._claims) >= 128:
                raise ValueError('Wissensbudget für Claims ausgeschöpft')
            self._claims[identifier] = None
            self._claims[identifier] = copy.deepcopy(self.claims.get(identifier))
        value = self._claims[identifier]
        if value is None or value.id != identifier:
            raise ValueError('Claim nicht verfügbar')
        return value

    def source(self, identifier):
        if identifier not in self._sources:
            if len(self._sources) >= 128 or self.snapshot_provider is None:
                raise ValueError('Originalbudget ausgeschöpft oder Aufnahme fehlt')
            self._sources[identifier] = None
            self._sources[identifier] = copy.deepcopy(self.snapshot_provider(identifier))
        value = self._sources[identifier]
        if (value is None or value.episode.id != identifier or not value.current()
                or type(value.generation) is not int or value.generation < 0):
            raise ValueError('Original nicht verfügbar')
        return value

    def capture(self, identifier, reason=''):
        generations = {}
        def source(identifier):
            snapshot = self.source(identifier)
            generations[identifier] = snapshot.generation
            return snapshot.episode
        try:
            claim = self.claim(identifier)
            if not knowledge_context.evidence_chain_available(claim, self.claims, None,
                    at=self.at, claim_resolver=self.claim, source_resolver=source):
                return None
            projection = project(claim, self.source(claim.evidence[0].episode_id), reason)
            return claim, projection, signature(projection, generations)
        except (ClaimError, EpisodeError, ValueError, TypeError, AttributeError, OverflowError):
            return None
