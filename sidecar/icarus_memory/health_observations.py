"""Explicit own measurements over immutable originals and existing source heads.

No medical interpretation, automatic subject linkage, scheduler or model calls.
Navigation is bounded and live: withdrawals are checked again on every page.
"""
from datetime import datetime, timezone
import base64
import json
import re
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .episodes import EpisodeKind, EpisodeState, sql_geltend
from .memory_categories import Categories
from .memory_history import query_key, ceiling_anchor, validate_anchor
from .model import Provenance, SourceType
from .source_snapshot import read_snapshot
from .source_versions import track_source

PREFIX = 'health-observation:'
SCHEMA = 'health-observation-v1'
MAX_BYTES = 32_000
SCAN = 100


class Fields(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    subject: Literal['self']
    metric: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=32, pattern=r'^[+-]?[0-9]+(?:[.,][0-9]+)?$')
    unit: str = Field(min_length=1, max_length=40)
    observed_at: str = Field(min_length=20, max_length=40)
    note: str = Field(default='', max_length=4000)

    @field_validator('metric', 'unit', 'note')
    @classmethod
    def readable(cls, value, info):
        if (info.field_name != 'note' and not value.strip()) or any(
            ord(c) < 32 and not (info.field_name == 'note' and c in '\n\t') for c in value):
            raise ValueError('Bitte lesbaren Text angeben.')
        return value

    @field_validator('observed_at')
    @classmethod
    def aware_time(cls, value):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
            raise ValueError('Messzeit benötigt Datum, Uhrzeit und Zeitzone.')
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.utcoffset() is None:
            raise ValueError('Messzeit benötigt eine Zeitzone.')
        try:
            stamp.astimezone(timezone.utc)
        except OverflowError:
            raise ValueError('Messzeit liegt außerhalb des unterstützten Zeitraums.') from None
        return value


class ObservationIn(Fields):
    # A textual canonical UUID; accept UUID spellings, normalize for all keys.
    request_id: str = Field(min_length=1, max_length=40)

    @field_validator('request_id')
    @classmethod
    def nonce(cls, value):
        return str(UUID(value))


class CorrectionIn(ObservationIn):
    expected_support_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')


def _body(fields):
    value = {key: getattr(fields, key) for key in Fields.model_fields}
    return json.dumps({'schema': SCHEMA, **value}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _snapshot(episodes, identifier, *, current=True):
    # Unlike a RAG excerpt, an original measurement remains visible after
    # consolidation bookkeeping. Every original/body/metadata/head is verified.
    snapshot = read_snapshot(episodes._conn, identifier, episodes._from_row, max_bytes=MAX_BYTES)
    if snapshot is None or (current and not snapshot.current()):
        return None
    episode = snapshot.episode
    if (not snapshot.source_key.startswith(PREFIX) or episode.kind is not EpisodeKind.DOCUMENT
            or episode.provenance.source_type is not SourceType.USER_STATED
            or episode.provenance.source_ref != 'health:manual'):
        raise ValueError('Keine eigene Messquelle.')
    UUID(snapshot.source_key[len(PREFIX):])
    payload = json.loads(episode.body)
    if type(payload) is not dict or payload.pop('schema', None) != SCHEMA:
        raise ValueError('Unbekanntes Messformat.')
    fields = Fields.model_validate(payload)
    if datetime.fromisoformat(fields.observed_at.replace('Z', '+00:00')) != episode.occurred_at:
        raise ValueError('Messzeit und Originalquelle widersprechen sich.')
    return snapshot, fields


def _item(pair):
    snapshot, fields = pair
    episode = snapshot.episode
    status = ('superseded' if snapshot.head_id != episode.id else
              'excluded' if not snapshot.current() else 'current')
    result = {**fields.model_dump(), 'id': episode.id, 'recorded_at': episode.recorded_at.isoformat(),
              'status': status, 'support_fingerprint': snapshot.support_fingerprint() if status == 'current' else None}
    return result


def _category_available(episodes):
    if not any(item['id'] == 'health' for item in Categories(episodes).taxonomy()['items']):
        raise HTTPException(409, 'Die Kategorie Gesundheit ist nicht verfügbar. Bitte zuerst die Gedächtniskategorien prüfen.')


def _record(episodes, fields, key):
    return episodes.record(EpisodeKind.DOCUMENT, fields.metric, _body(fields),
        Provenance(SourceType.USER_STATED, source_ref='health:manual'),
        occurred_at=datetime.fromisoformat(fields.observed_at.replace('Z', '+00:00')),
        source_key=key, tags=[SCHEMA, 'health:subject:self', 'health:change:' + fields.request_id])[0]


def _same_change(pair, body):
    snapshot, _ = pair
    return (snapshot.episode.body == _body(body)
            and 'health:change:' + body.request_id in snapshot.episode.tags)


def _lookup(episodes, identifier, *, current=True):
    try:
        pair = _snapshot(episodes, identifier, current=current)
    except (ValueError, TypeError, KeyError, ValidationError):
        pair = None
    if pair is None:
        raise HTTPException(409, 'Die Messquelle ist nicht mehr unverändert verfügbar. Bitte den Verlauf neu laden.')
    return pair


def _instant_us(value):
    """Exact signed microseconds, without SQLite's millisecond/float rounding."""
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.utcoffset() is None:
            return None
        delta = stamp.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None


def _cursor(query, position, ceiling, anchor):
    value = {'v': 1, 'q': query, 'p': list(position), 'h': ceiling, 'a': anchor}
    return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).decode().rstrip('=')


def _decode(cursor, query):
    try:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 2048:
            raise ValueError()
        value = json.loads(base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True))
        if (type(value) is not dict or set(value) != {'v', 'q', 'p', 'h', 'a'}
                or type(value['v']) is not int or value['v'] != 1 or value['q'] != query
                or type(value['h']) is not int or not 1 <= value['h'] <= 2**63 - 1
                or not isinstance(value['a'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['a'])
                or type(value['p']) is not list or len(value['p']) != 2
                or any(type(n) is not int for n in value['p'])
                or not -62_135_596_800_000_000 <= value['p'][0] <= 253_402_300_799_999_999
                or not 1 <= value['p'][1] <= value['h']):
            raise ValueError()
        return value['p'], value['h'], value['a']
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        raise ValueError('Ungültiger Cursor oder Cursor für einen anderen Messverlauf.') from None


def _page(episodes, *, limit, cursor=None, key=None):
    query = query_key('health-history-v1' if key else 'health-current-v1', str(episodes._path.resolve()), limit, key)
    after = _decode(cursor, query) if cursor is not None else None
    with episodes._lock:
        ceiling = after[1] if after else episodes._conn.execute('SELECT COALESCE(MAX(rowid),0) FROM episodes').fetchone()[0]
        anchor = after[2] if after else ceiling_anchor(episodes._conn, 'episodes', 'rowid', ceiling)
        validate_anchor(episodes._conn, 'episodes', 'rowid', ceiling, anchor)
        episodes._conn.create_function('_health_instant_us', 1, _instant_us, deterministic=True)
        stamp = 'recorded_at' if key else 'occurred_at'
        instant = f'_health_instant_us(e.{stamp})'
        source = 'episodes e' if key else 'source_heads h JOIN episodes e ON e.id=h.episode_id'
        sql = f'SELECT e.id,e.rowid AS pos,{instant} AS stamp FROM {source} WHERE e.rowid<=? '
        params = [ceiling]
        if key:
            sql += 'AND e.source_key=? '
            params.append(key)
        else:
            sql += f'AND h.source_key>=? AND h.source_key<? AND {sql_geltend("e")} '
            params.extend([PREFIX, PREFIX[:-1] + ';'])
        if after:
            sql += f'AND ({instant}<? OR ({instant}=? AND e.rowid<?)) '
            params.extend([after[0][0], after[0][0], after[0][1]])
        sql += f'AND {instant} IS NOT NULL ORDER BY stamp DESC,pos DESC LIMIT ?'
        params.append(SCAN + 1)
        rows = episodes._conn.execute(sql, params).fetchall()
        items, invalid, scanned, last = [], 0, 0, None
        for row in rows[:SCAN]:
            last = row
            scanned += 1
            try:
                pair = _snapshot(episodes, row['id'], current=key is None)
                if pair is None:
                    invalid += 1
                    continue
                items.append(_item(pair))
            except (ValueError, TypeError, KeyError, ValidationError):
                invalid += 1
            if len(items) == limit:
                break
        more = last is not None and len(rows) > scanned
        next_cursor = _cursor(query, [last['stamp'], last['pos']], ceiling, anchor) if more else None
        return {'items': items, 'next_cursor': next_cursor, 'scanned_sources': scanned,
                'invalid_sources': invalid, 'scan_limit': SCAN, 'complete': next_cursor is None}


def register(app, guard):
    @app.post('/api/v1/health/observations', dependencies=guard, status_code=201)
    def capture(body: ObservationIn, response: Response):
        episodes = app.state.episodes
        with app.state.conversation_lock, episodes.transaction():
            key = PREFIX + body.request_id
            head = episodes.source_head(key)
            if head:
                pair = _lookup(episodes, head)
                if not _same_change(pair, body):
                    raise HTTPException(409, 'Diese Kennung gehört zu einer anderen oder bereits korrigierten Angabe.')
                response.status_code = 200
                return _item(pair)
            _category_available(episodes)
            episode = _record(episodes, body, key)
            episodes.advance_source_head(key, None, episode.id)
            Categories(episodes).correct(episode.id, ['health'])
            return _item(_lookup(episodes, episode.id))

    @app.patch('/api/v1/health/observations/{identifier}', dependencies=guard)
    def correct(identifier: str, body: CorrectionIn):
        episodes = app.state.episodes
        with app.state.conversation_lock, episodes.transaction():
            old, _ = _lookup(episodes, identifier, current=False)
            head = episodes.source_head(old.source_key)
            if head != identifier:
                pair = _lookup(episodes, head)
                if _same_change(pair, body):
                    return _item(pair)
                raise HTTPException(409, 'Die Angabe wurde inzwischen geändert. Deine Eingabe wurde nicht gespeichert.')
            pair = _lookup(episodes, identifier)
            if pair[0].support_fingerprint() != body.expected_support_fingerprint:
                raise HTTPException(409, 'Die Angabe wurde inzwischen geändert. Bitte den Verlauf neu laden.')
            if pair[0].episode.body == _body(body):
                return _item(pair)
            reused = episodes._conn.execute(
                "SELECT 1 FROM episodes e,json_each(e.document,'$.tags') t WHERE e.source_key=? AND t.value=? LIMIT 1",
                (old.source_key, 'health:change:' + body.request_id)).fetchone()
            if reused:
                raise HTTPException(409, 'Diese Änderungskennung wurde bereits für eine andere Fassung verwendet.')
            _category_available(episodes)
            episode = _record(episodes, body, old.source_key)
            track_source(episodes, app.state.claims, old.source_key, episode)
            Categories(episodes).correct(episode.id, ['health'])
            return _item(_lookup(episodes, episode.id))

    @app.get('/api/v1/health/observations', dependencies=guard)
    def observations(limit: int = Query(default=25, ge=1, le=50), cursor: str | None = Query(default=None, max_length=2048)):
        with app.state.conversation_lock:
            try:
                return _page(app.state.episodes, limit=limit, cursor=cursor)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None

    @app.get('/api/v1/health/observations/{identifier}/history', dependencies=guard)
    def history(identifier: str, limit: int = Query(default=25, ge=1, le=50), cursor: str | None = Query(default=None, max_length=2048)):
        episodes = app.state.episodes
        with app.state.conversation_lock, episodes._lock:
            snapshot, _ = _lookup(episodes, identifier, current=False)
            try:
                return _page(episodes, limit=limit, cursor=cursor, key=snapshot.source_key)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
