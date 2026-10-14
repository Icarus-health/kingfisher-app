"""Read-only saved mail views. Browsing never creates a provider reader or model.

Only current, permitted originals are listed. A provider action destination is
exposed only when the stored inbox inventory proves its account and UID.
"""
from contextlib import contextmanager, nullcontext
import re
from fastapi import HTTPException, Query
from .episodes import EpisodeError, EpisodeKind, sql_aktuell
from .model import SourceType

_REF = "COALESCE(json_extract(e.document, '$.provenance.source_ref'), '')"
_ACCOUNT = f"CASE WHEN {_REF} LIKE 'imap:%' OR instr({_REF}, ':') = 0 THEN '' ELSE substr({_REF}, 1, instr({_REF}, ':') - 1) END"
_BASE = f"e.kind='message' AND json_extract(e.document, '$.provenance.source_type')='email' AND {sql_aktuell('e')}"


@contextmanager
def _unicode_search(connection):
    # Connection-local pure function. The store lock covers registration/query
    # and removal; no source or index is written as a side effect of browsing.
    connection.create_function('kf_local_mail_fold', 1, lambda value: str(value or '').casefold(), deterministic=True)
    try:
        yield
    finally:
        connection.create_function('kf_local_mail_fold', 1, None)


def _last_sync(app, account):
    from .mail_stand import gelesen, _zeit
    stored = (getattr(app.state.settings, 'mail_sync_status', {}) or {}).get(account) or {}
    manual = gelesen(app, account) or {}
    known = [_zeit(stored.get('last_success')), _zeit(manual.get('zeit'))]
    latest = max((value for value in known if value is not None), default=None)
    return latest.isoformat() if latest else None


def _remote_uid(store, episode_id, account_id):
    # Archive folder UIDs are not inbox UIDs; no guessed Message-ID mappings.
    exists = store._conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mail_intake_items'").fetchone()
    if not exists or not account_id:
        return None
    rows = store._conn.execute("SELECT account, generation, uid FROM mail_intake_items WHERE episode_id=? AND upper(folder)='INBOX' AND account=? AND status IN ('captured','duplicate') LIMIT 2", (episode_id, account_id)).fetchall()
    if len(rows) != 1 or not re.fullmatch(r'\d+', str(rows[0][1])) or not re.fullmatch(r'\d+', str(rows[0][2])):
        return None
    return f'{account_id}:{rows[0][1]}.{rows[0][2]}'


def _item(store, episode, account_id, labels):
    return {'episode_id': episode.id, 'account_id': account_id,
            'account_label': labels.get(account_id, account_id or 'Gespeicherte Mailquellen'),
            'remote_uid': _remote_uid(store, episode.id, account_id),
            'sender': episode.participants[0] if episode.participants else 'Absender nicht gespeichert',
            'subject': episode.title, 'preview': ' '.join(episode.body[:500].split())[:180],
            'date': episode.occurred_at.isoformat() if episode.occurred_at else None,
            'recorded_at': episode.recorded_at.isoformat(), 'source_ref': episode.provenance.source_ref,
            'truncated': 'source:truncated' in episode.tags, 'state': episode.state.value}


def register(app, guard):
    def labels():
        return {entry.id: entry.label for entry in getattr(app.state.settings, 'mail_accounts', [])}

    @app.get('/api/v1/local-mail', dependencies=guard)
    def page(q: str = Query(default='', max_length=300), account_id: str | None = Query(default=None, max_length=200),
             offset: int = Query(default=0, ge=0, le=1000000), limit: int = Query(default=40, ge=1, le=100)):
        store = app.state.episodes
        account_labels = labels()
        where, params = _BASE, []
        if account_id is not None:
            where += f' AND ({_ACCOUNT})=?'
            params.append(account_id)
        if q.strip():
            where += " AND (instr(kf_local_mail_fold(e.title),?)>0 OR instr(kf_local_mail_fold(e.body),?)>0 OR instr(kf_local_mail_fold(json_extract(e.document,'$.participants')),?)>0)"
            params.extend([q.strip().casefold()] * 3)
        with getattr(app.state, 'conversation_lock', nullcontext()), store._lock, _unicode_search(store._conn):
            total = store._conn.execute(f'SELECT COUNT(*) FROM episodes e WHERE {where}', params).fetchone()[0]
            rows = store._conn.execute(f'SELECT e.document, ({_ACCOUNT}) AS account_id FROM episodes e WHERE {where} ORDER BY datetime(e.occurred_at) DESC, datetime(e.recorded_at) DESC, e.id DESC LIMIT ? OFFSET ?', (*params, limit, offset)).fetchall()
            items = [_item(store, store._from_row(row), row['account_id'], account_labels) for row in rows]
            counts = {row[0]: row[1] for row in store._conn.execute(f'SELECT ({_ACCOUNT}), COUNT(*) FROM episodes e WHERE {_BASE} GROUP BY ({_ACCOUNT})')}
            accounts = [{'id': account, 'label': account_labels.get(account, account or 'Gespeicherte Mailquellen'),
                         'count': counts.get(account, 0), 'last_sync': _last_sync(app, account)}
                        for account in sorted(set(counts) | set(account_labels))]
        return {'items': items, 'accounts': accounts, 'total': total, 'offset': offset, 'limit': limit,
                'has_more': offset + len(items) < total,
                'scope': 'saved_current_mail', 'detail': 'Bereits gespeicherte Mailquellen. Kein vollständiger oder aktueller Postfachstand; nicht gespeicherte Nachrichten fehlen.'}

    @app.get('/api/v1/local-mail/{episode_id}', dependencies=guard)
    def detail(episode_id: str):
        store = app.state.episodes
        with getattr(app.state, 'conversation_lock', nullcontext()), store._lock:
            try:
                episode = store.get(episode_id)
            except (KeyError, EpisodeError):
                raise HTTPException(404, 'Gespeicherte Mail nicht gefunden.') from None
            if episode.kind is not EpisodeKind.MESSAGE or episode.provenance.source_type is not SourceType.EMAIL:
                raise HTTPException(404, 'Gespeicherte Mail nicht gefunden.')
            row = store._conn.execute(f'SELECT ({_ACCOUNT}) AS account_id FROM episodes e WHERE e.id=? AND {_BASE}', (episode_id,)).fetchone()
            if row is None:
                raise HTTPException(409, 'Diese Mailquelle ist ausgeschlossen oder wurde durch eine neuere Fassung ersetzt.')
            item = _item(store, episode, row['account_id'], labels())
            return {**item, 'uid': episode.id, 'from': item['sender'], 'body': episode.body[:20000],
                    'truncated': item['truncated'] or len(episode.body) > 20000,
                    'answer_to': '', 'message_id': '', 'can_reply': False, 'sending_account': '',
                    'source_current': True, 'source_digest': episode.digest}
