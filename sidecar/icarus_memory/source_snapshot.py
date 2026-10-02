"""Eine konsistente Quellenaufnahme; kein Selbstmodell und keine Autorisierung."""
from dataclasses import dataclass
from typing import Callable
from datetime import datetime, timezone
import re
from .episodes import Episode, EpisodeKind, EpisodeState, digest_of, source_metadata_digest
from .self_model_basis import digest


@dataclass(frozen=True)
class EpisodeSupportSnapshot:
    episode: Episode
    source_key: str
    metadata_digest: str
    generation: int
    head_id: str | None
    correction_valid: bool = True

    def fingerprint(self):
        return digest({'episode': self.episode.to_dict(), 'source_key': self.source_key,
                       'metadata_digest': self.metadata_digest, 'generation': self.generation,
                       'head_id': self.head_id})

    def support_fingerprint(self):
        # Bearbeitungsbuchhaltung darf eine eben angenommene Aussage nicht entwerten.
        return digest({'id': self.episode.id, 'digest': self.episode.digest,
                       'kind': self.episode.kind.value, 'ignored': self.episode.state is EpisodeState.IGNORED,
                       'source_key': self.source_key, 'metadata_digest': self.metadata_digest,
                       'generation': self.generation, 'head_id': self.head_id})

    def current(self):
        return (self.correction_valid and self.episode.kind is not EpisodeKind.SUMMARY
                and self.episode.state is not EpisodeState.IGNORED
                and (not self.source_key or self.head_id == self.episode.id))


EpisodeSnapshotProvider = Callable[[str], EpisodeSupportSnapshot | None]


def read_snapshot(connection, identifier, parse, *, max_bytes=None, _seen=()):
    if identifier in _seen or len(_seen) >= 8:
        return None
    row = connection.execute('SELECT e.*, h.episode_id AS head_id, (SELECT COUNT(*) FROM source_heads r WHERE r.episode_id=e.id) AS reverse_count, (SELECT MIN(source_key) FROM source_heads r WHERE r.episode_id=e.id) AS reverse_key FROM episodes e '
                             'LEFT JOIN source_heads h ON h.source_key=e.source_key WHERE e.id=?'
                             + (' AND length(CAST(e.document AS BLOB)) <= ?' if max_bytes is not None else ''),
                             (identifier, max_bytes) if max_bytes is not None else (identifier,)).fetchone()
    if row is None:
        return None
    episode = parse(row)
    document = episode.to_dict()
    if (any(document[k] != row[k] for k in ('id','digest','kind','state','body','title','project_id'))
            or any(canonical_instant(document[k]) != canonical_instant(row[k]) for k in ('recorded_at','occurred_at'))
            or episode.digest != digest_of(episode.body)
            or row['reverse_count'] > 1
            or (row['reverse_count'] and row['reverse_key'] != row['source_key'])
            or type(row['support_generation']) is not int or row['support_generation'] < 0
            or (row['source_key'] and row['metadata_digest'] != source_metadata_digest(document))):
        raise ValueError('Inkonsistente Quelle')
    correction_valid = True
    if row['source_key'].startswith('source-correction:'):
        from .model import SourceType
        match = re.fullmatch(r'source-correction:(e-[a-f0-9]{12}):([a-f0-9]{64})',
                            episode.provenance.source_ref or '')
        correction_valid = False
        if (episode.provenance.source_type is SourceType.MANUAL_CORRECTION and match
                and row['source_key'] == 'source-correction:' + match[1]):
            target = read_snapshot(connection, match[1], parse, max_bytes=max_bytes,
                                   _seen=(*_seen, identifier))
            correction_valid = bool(target and target.correction_valid
                and target.episode.state is EpisodeState.IGNORED
                and (not target.source_key or target.head_id == target.episode.id)
                and target.support_fingerprint() == match[2])
    return EpisodeSupportSnapshot(episode, row['source_key'], row['metadata_digest'],
                                  row['support_generation'], row['head_id'], correction_valid)


def quote_matches(quote, body):
    return bool(quote.strip()) and ' '.join(quote.split()).casefold() in ' '.join(body.split()).casefold()


def canonical_instant(value):
    if value is None:
        return None
    # Python 3.10 versteht den vom Modell serialisierten UTC-Suffix Z noch nicht.
    if value.endswith("Z"):
        if "Z" in value[:-1] or not value[-2:-1].isdigit():
            raise ValueError("Ungültige Quellenzeit")
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Quellenzeit benötigt eine Zeitzone')
    return parsed.astimezone(timezone.utc).isoformat()
