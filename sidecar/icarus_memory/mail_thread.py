"""Bounded, read-only source chronology; headers are hints, never proof of truth."""
from datetime import timezone
import sqlite3

from .episodes import EpisodeState, digest_of, sql_aktuell
from .mail_ingestion import source_key_for_message
from .mail_task_suggestions import source_digest
from .mail_timeline import SELF, REPLY, thread_tags

MAX_TEXT = 6000
MAX_TOKENS = 512
MAX_HOPS = 8
MAX_QUERY_STEPS = 1_000_000


def _tokens(tags):
    return {tag[len(prefix):] for tag in tags for prefix in (SELF, REPLY) if tag.startswith(prefix)}


def _date(value):
    return value.astimezone(timezone.utc).isoformat() if value is not None and value.tzinfo is not None else None


def thread_context(episodes, message, *, limit=20):
    """Inspect stored current sources only; never fetch, ingest or infer completion.

    Caller holds the same conversation lock as source withdrawal. Exact,
    account-scoped header tokens prevent accidental subject/name clustering.
    Missing headers, missing imports and forged headers remain possible.
    """
    if not 2 <= limit <= 50:
        raise ValueError('thread limit must be between 2 and 50')
    key = source_key_for_message(message)
    head_id = episodes.source_head(key)
    head = episodes.get(head_id) if head_id else None
    base = {'uid': message.uid, 'source_digest': source_digest(message),
            'scope': 'stored_header_links', 'status': 'ready', 'limited': False,
            'detail': 'Geöffnete Mail und bereits gespeicherte Nachrichten mit passenden Antwortbezügen. '
                      'Kein vollständiger Postfachverlauf: Nicht alle Nachrichten müssen schon aufgenommen sein. '
                      'Angaben aus Nachrichten bleiben unbestätigt.', 'items': []}
    if head is not None and head.state is EpisodeState.IGNORED:
        return {**base, 'status': 'excluded', 'detail': 'Die geöffnete Quelle ist vom Gedächtnis ausgeschlossen.'}
    text = message.body or message.preview or ''
    current = {'episode_id': head_id if head and head.digest == digest_of(text) else None,
               'support_generation': episodes.support_snapshot(head_id).generation if head else None,
               'current': True, 'title': message.subject or '(Ohne Betreff)', 'sender': message.sender,
               'occurred_at': _date(message.date), 'recorded_at': _date(head.recorded_at) if head else None,
               'text': text[:MAX_TEXT], 'truncated': bool(message.truncated) or len(text) > MAX_TEXT}
    items = [current]
    tokens = _tokens(thread_tags(message))
    visited = {head_id} if head_id else set()
    limited = current['truncated']
    remaining_steps = MAX_QUERY_STEPS

    def progress():
        nonlocal remaining_steps
        remaining_steps -= 1000
        return int(remaining_steps < 0)
    # Keep one bounded result set per expansion. No scan or model call outside
    # the stored source relation, no unbounded materialization of the mailbox.
    for hop in range(MAX_HOPS):
        if not tokens:
            break
        if len(tokens) > MAX_TOKENS:
            limited = True
            tokens = set(sorted(tokens)[:MAX_TOKENS])
        wanted = [prefix + token for token in sorted(tokens) for prefix in (SELF, REPLY)]
        query = ('SELECT e.id FROM episodes e WHERE ' + sql_aktuell('e')
                 + " AND json_extract(e.document,'$.provenance.source_type')='email'"
                 + " AND EXISTS (SELECT 1 FROM json_each(e.document,'$.tags') j WHERE j.value IN ("
                 + ','.join('?' for _ in wanted) + '))')
        params = list(wanted)
        if visited:
            query += ' AND e.id NOT IN (' + ','.join('?' for _ in visited) + ')'
            params += sorted(visited)
        query += ' ORDER BY e.id LIMIT ?'
        params.append(limit - len(items) + 1)
        try:
            with episodes._lock:
                episodes._conn.set_progress_handler(progress, 1000)
                try:
                    rows = episodes._conn.execute(query, params).fetchall()
                finally:
                    episodes._conn.set_progress_handler(None, 0)
        except sqlite3.OperationalError as exc:
            if 'interrupted' not in str(exc).lower():
                raise
            limited = True
            break
        space = limit - len(items)
        if len(rows) > space:
            limited = True
        for row in rows[:space]:
            episode = episodes.get(row[0])
            visited.add(episode.id)
            tokens.update(_tokens(episode.tags))
            cropped = len(episode.body) > MAX_TEXT or 'source:truncated' in episode.tags
            limited = limited or cropped
            items.append({'episode_id': episode.id, 'current': False, 'title': episode.title,
                          'support_generation': episodes.support_snapshot(episode.id).generation,
                          'sender': episode.participants[0] if episode.participants else '',
                          'occurred_at': _date(episode.occurred_at), 'recorded_at': _date(episode.recorded_at),
                          'text': episode.body[:MAX_TEXT], 'truncated': cropped})
        if len(rows) > space or not rows:
            break
        if hop == MAX_HOPS - 1:
            limited = True
    items.sort(key=lambda item: (item['occurred_at'] is None, item['occurred_at'] or '', item['episode_id'] or ''))
    return {**base, 'items': items, 'limited': bool(limited)}
