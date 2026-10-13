"""Bounded, read-only literal lookup in currently available original sources."""
import json

from .episodes import AUSGEBLENDETE_ZUSTAENDE, CHAT_LOOKUP_TAG, sql_geltend
from .workspace import WorkspaceError


SOURCE_SCAN_LIMIT = 5000
NOTE_SCAN_LIMIT = 5000


def literal_span(text: str, folded_query: str) -> tuple[int, int] | None:
    """Find a caseless literal and map expanding Unicode folds back to the original."""
    folded_start = text.casefold().find(folded_query)
    if folded_start < 0:
        return None
    folded_end = folded_start + len(folded_query)
    offset = 0
    start = None
    for index, character in enumerate(text):
        next_offset = offset + len(character.casefold())
        if start is None and next_offset > folded_start:
            start = index
        if next_offset >= folded_end:
            return start, index + 1
        offset = next_offset
    return None


def excerpt_bounds(body: str, span: tuple[int, int] | None) -> tuple[int, int]:
    if span is None:
        return 0, min(400, len(body))
    # Unicode folds can expand a 200-character query past 400 original
    # characters. Keep the match start visible even in that edge case.
    context = max(0, (400 - (span[1] - span[0])) // 2)
    start = max(0, span[0] - context)
    return start, min(len(body), start + 400)


def note_search(workspace, folded: str, limit: int) -> tuple[list[dict], int, bool]:
    """Current workspace documents, newest edit first; no historical note revisions."""
    items, scanned, truncated = [], 0, False
    if workspace is None:
        return items, scanned, truncated
    with workspace._lock:
        rows = workspace._conn.execute(
            "SELECT n.id,n.title,n.body FROM notes n "
            "WHERE NOT EXISTS (SELECT 1 FROM json_each(n.document,'$.tags') tag WHERE tag.value=?) "
            "ORDER BY julianday(n.updated_at) DESC,n.id DESC LIMIT ?",
            (CHAT_LOOKUP_TAG, NOTE_SCAN_LIMIT + 1)).fetchall()
    # WorkspaceStore has a non-reentrant lock; its public note reader takes it itself.
    for row in rows:
        if scanned == NOTE_SCAN_LIMIT:
            truncated = True
            break
        scanned += 1
        if not any(folded in text.casefold() for text in (row['title'], row['body'])):
            continue
        try:
            note = workspace.note(row['id'])
        except (WorkspaceError, ValueError):
            truncated = True
            continue
        if CHAT_LOOKUP_TAG in note.tags:
            continue
        span = literal_span(note.body, folded)
        if span is None and folded not in note.title.casefold():
            continue
        if len(items) == limit:
            truncated = True
            break
        start, end = excerpt_bounds(note.body, span)
        items.append({
            'note_id': note.id, 'title': note.title,
            'quote': note.body[start:end], 'start': start, 'end': end,
            'source_type': 'workspace_note', 'occurred_at': None,
            'recorded_at': note.updated_at.isoformat(),
        })
    return items, scanned, truncated


def source_search(episodes, query: str, limit: int = 20, workspace=None) -> dict:
    """No model/index/queue work. A no-hit result describes only this bounded scan."""
    clean = query.strip()
    if not 2 <= len(clean) <= 200 or len(query) > 200 or not 1 <= limit <= 50:
        raise ValueError('Suchtext benötigt 2 bis 200 Zeichen; höchstens 50 Treffer.')
    folded = clean.casefold()
    items = []
    scanned = 0
    truncated = False
    # Same source/current-head and own-lookup exclusions as EpisodeStore.mentions.
    # The central UI includes ordinary conversation input and hides archived originals.
    # SQL LIKE is deliberately avoided:
    # Unicode casefold and literal punctuation must have the same meaning everywhere.
    with episodes._lock:
        cursor = episodes._conn.execute(
            "SELECT e.id,e.title,e.body,json_extract(e.document,'$.participants') AS participants "
            f"FROM episodes e WHERE {sql_geltend('e')} AND e.state != 'archived' "
            "AND NOT EXISTS (SELECT 1 FROM json_each(e.document,'$.tags') tag WHERE tag.value=?) "
            "ORDER BY COALESCE(e.occurred_at,e.recorded_at) DESC,e.id DESC LIMIT ?",
            (CHAT_LOOKUP_TAG, SOURCE_SCAN_LIMIT + 1))
        try:
            for row in cursor:
                if scanned == SOURCE_SCAN_LIMIT:
                    truncated = True
                    break
                scanned += 1
                participants = json.loads(row['participants']) if row['participants'] else []
                if not any(folded in text.casefold() for text in
                           (row['title'], row['body'], *participants)):
                    continue
                # Re-read the original and its support after candidate selection. This
                # also validates corrections, attachment parents, and original digests.
                try:
                    snapshot = episodes.support_snapshot(row['id'])
                except ValueError:
                    truncated = True  # inconsistent evidence is omitted, never displayed
                    continue
                if snapshot is None or not snapshot.current():
                    continue
                episode = snapshot.episode
                if (episode.state in AUSGEBLENDETE_ZUSTAENDE
                        or CHAT_LOOKUP_TAG in episode.tags):
                    continue
                span = literal_span(episode.body, folded)
                if span is None and not any(folded in text.casefold() for text in
                                            (episode.title, *episode.participants)):
                    continue
                if len(items) == limit:
                    truncated = True
                    break
                start, end = excerpt_bounds(episode.body, span)
                truncated = truncated or 'source:truncated' in episode.tags
                items.append({
                    'episode_id': episode.id, 'title': episode.title,
                    'quote': episode.body[start:end], 'start': start, 'end': end,
                    'occurred_at': episode.occurred_at.isoformat() if episode.occurred_at else None,
                    'recorded_at': episode.recorded_at.isoformat(),
                    'source_type': episode.provenance.source_type.value,
                })
        finally:
            cursor.close()
    note_items, note_scanned, note_truncated = note_search(workspace, folded, limit - len(items))
    truncated = truncated or note_truncated
    # Notes may take time to scan: check source support once more before returning
    # original excerpts. This is live navigation, not a cross-store snapshot.
    with episodes._lock:
        available = []
        for item in items:
            try:
                snapshot = episodes.support_snapshot(item['episode_id'])
            except ValueError:
                snapshot = None
            if (snapshot is None or not snapshot.current()
                    or snapshot.episode.state in AUSGEBLENDETE_ZUSTAENDE
                    or CHAT_LOOKUP_TAG in snapshot.episode.tags
                    or snapshot.episode.title != item['title']
                    or snapshot.episode.body[item['start']:item['end']] != item['quote']
                    or not any(folded in text.casefold() for text in
                               (snapshot.episode.title, snapshot.episode.body, *snapshot.episode.participants))):
                truncated = True
                continue
            available.append(item)
        items = available
    return {
        'query': clean, 'items': items, 'note_items': note_items, 'truncated': truncated,
        'scanned': scanned, 'scan_limit': SOURCE_SCAN_LIMIT,
        'note_scanned': note_scanned, 'note_scan_limit': NOTE_SCAN_LIMIT,
        'scope': (
            f'Wörtliche Suche ohne Beachtung der Groß-/Kleinschreibung im aufgenommenen Originaltext, '
            f'Titel und Beteiligten der höchstens {SOURCE_SCAN_LIMIT} jüngsten verfügbaren aktuellen Quellen. '
            f'Zusätzlich die höchstens {NOTE_SCAN_LIMIT} zuletzt bearbeiteten aktuellen Arbeitsnotizen. '
            f'Quellen zuerst, Notizen danach im verbleibenden gemeinsamen Trefferlimit von {limit}. '
            'Bei Treffern nur in Titel oder Beteiligten zeigt das Zitat den Textanfang. '
            'Gesprächseingaben sind eigene Gesprächsbeiträge; Arbeitsnotizen sind bearbeitbare Dokumente. '
            'Keine semantische Deutung oder Bestätigung von Tatsachen; nicht angebundene Quellen und '
            'fehlender Originaltext sind nicht enthalten. Begrenzte Ergebnisse sind gekennzeichnet.'
        ),
    }
