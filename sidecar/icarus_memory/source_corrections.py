"""Vollständige eigene Berichtigung einer unbestätigten Quelle.

Das Original bleibt unverändert gespeichert, wird aber ausgeschlossen. Die
vom Nutzer geschriebene Fassung hat eigene Herkunft und Aufnahmezeit. Es entstehen
weder bestätigte Aussagen noch eine neue Ablage für persönliche Fakten.
"""
from .episodes import EpisodeError, EpisodeKind, EpisodeState
from .model import Provenance, SourceType, now
from .working_memory_store import MAX_BERICHT_CHARS, WorkingMemoryStore, source_fingerprint


def snapshot(episodes, claims, episode_id):
    current = episodes.support_snapshot(episode_id)
    if (not WorkingMemoryStore._eligible(current)
            or current.episode.state is EpisodeState.ARCHIVED
            or current.episode.produced
            or not claims.source_is_unclaimed(episode_id)
            or 'source:truncated' in current.episode.tags
            or len(current.episode.body) > MAX_BERICHT_CHARS):
        raise EpisodeError('Diese Quelle ist nicht direkt berichtbar. Bitte ihren aktuellen Stand bzw. bestätigte Aussagen prüfen.')
    return current


def preview(episodes, claims, episode_id):
    current = snapshot(episodes, claims, episode_id)
    return {'fingerprint': source_fingerprint(current), 'body': current.episode.body,
            'title': current.episode.title,
            'source_time': current.episode.occurred_at.isoformat() if current.episode.occurred_at else None}


def _items(episodes, current, body):
    """Eine Berichtigung ist vollständig neu formulierte Quelle ohne Modell.

    Selbst wörtlich gleiche Sätze können durch einen anderen Absatz widerrufen
    sein. Alte Abschnittsarten werden daher nie in die Fassung übernommen.
    """
    return [{'start': 0, 'end': len(body), 'kind': 'change'}]


def correct(episodes, claims, episode_id, fingerprint, body):
    body = body.strip()
    if not body or len(body) > MAX_BERICHT_CHARS:
        raise ValueError('Bitte eine vollständige Angabe mit höchstens 12.000 Zeichen eingeben.')
    with episodes.transaction():
        current = snapshot(episodes, claims, episode_id)
        if source_fingerprint(current) != fingerprint:
            raise EpisodeError('Die Quelle hat sich verändert. Bitte erneut öffnen.')
        if body == current.episode.body.strip():
            raise ValueError('Die Angabe wurde nicht verändert.')
        moment = now()
        key = f'source-correction:{episode_id}'
        if episodes.source_head(key) is not None:
            raise EpisodeError('Zu dieser Quelle gibt es bereits eine Berichtigung. Bitte dort fortfahren.')
        items = _items(episodes, current, body)
        episodes.ignore(episode_id)
        target_fingerprint = episodes.support_snapshot(episode_id).support_fingerprint()
        correction, created = episodes.record(
            EpisodeKind.MESSAGE, f'Deine Berichtigung: {current.episode.title[:250]}', body,
            Provenance(SourceType.MANUAL_CORRECTION, source_ref=f'{key}:{target_fingerprint}',
                       captured_at=moment, verbatim=body),
            # Der Zeitpunkt der Eingabe ist kein belegter Zeitbezug aller
            # übernommenen Sätze (etwa „morgen“ in einer älteren Nachricht).
            at=moment, source_key=key, tags=['source:correction'],
            # Die Berichtigung bleibt dort abgelegt, wo das Original lag.
            project_id=current.episode.project_id,
        )
        if not created or episodes.source_head(key) is not None:
            raise EpisodeError('Zu diesem Stand gibt es bereits eine Berichtigung. Bitte erneut öffnen.')
        # Alle Änderungen gehören zur selben Episoden-Transaktion; `advance_source_head` tritt ihr bei
        # (verschachtelte Schreibvorgänge nutzen die äußere Transaktion) und hält den Suchindex aktuell.
        episodes.advance_source_head(key, None, correction.id)
        memory = WorkingMemoryStore(episodes)
        if not memory.commit(episodes.support_snapshot(correction.id), items,
                             model='user:source-correction'):
            raise EpisodeError('Die Berichtigung konnte nicht aufgenommen werden.')
        return correction.id
