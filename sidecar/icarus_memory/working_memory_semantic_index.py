"""Rebuildable source vectors, separate from authoritative episode databases.

This storage component does not call models or activate background work.
Structural coverage counts eligible classified keys, not answer correctness.
"""
from __future__ import annotations

import math
import os
import re
import sqlite3
import struct
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .episodes import CHAT_LOOKUP_TAG, sql_sichtbar
from .working_memory_semantic import SemanticSearchResult
from .working_memory_store import ANALYSIS_VERSION, WorkingMemoryStore, _item_id

FORMAT = 1
MAX_BATCH = 64
RETRY_SECONDS = 300
REF_FIELDS = ('episode_id', 'fingerprint', 'start', 'end', 'kind')


@dataclass(frozen=True)
class IndexBatch:
    refs: tuple[dict, ...]
    token: tuple[str, int]
    before: int
    cursor: int
    ceiling: int
    positions: tuple[int, ...]


def _vector(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 8192:
        raise ValueError('invalid embedding dimension')
    if any(type(v) not in (int, float) for v in values):
        raise ValueError('invalid embedding values')
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError('invalid embedding norm')
    return struct.pack(f'<{len(values)}f', *(v / norm for v in values))


class DurableSemanticIndex:
    """Own one cache connection; caller closes/reopens it at restore boundaries."""

    def __init__(self, episodes, model_key: str):
        if not isinstance(model_key, str) or not re.fullmatch(r'[^\s]{1,400}:[a-f0-9]{64}', model_key):
            raise ValueError('exact model name and digest required')
        source = Path(episodes._path)
        if str(source) == ':memory:' or not source.is_file() or source.is_symlink():
            raise ValueError('persistent source file required')
        self._source = source.resolve()
        stat = self._source.stat()
        self._file_identity = (stat.st_dev, stat.st_ino)
        directory = self._source.parent / '.search-cache'
        if directory.is_symlink():
            raise ValueError('cache directory must not be a symlink')
        directory.mkdir(mode=0o700, exist_ok=True)
        self.path = directory / (self._source.name + '.vectors.sqlite3')
        if self.path.is_symlink():
            raise ValueError('cache file must not be a symlink')
        self._store = WorkingMemoryStore(episodes)
        self._model = model_key
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, timeout=3, check_same_thread=False, uri=True)
        os.chmod(self.path, 0o600)
        self._conn.row_factory = sqlite3.Row
        try:
            # Imports/loads only when this optional component is constructed.
            import sqlite_vec
            self._conn.enable_load_extension(True)
            try:
                sqlite_vec.load(self._conn)
            finally:
                self._conn.enable_load_extension(False)
            self._conn.execute('PRAGMA cache_size=-8192')
            self._conn.execute('PRAGMA foreign_keys=ON')
            self._conn.execute('ATTACH DATABASE ? AS originals', (self._source.as_uri() + '?mode=ro',))
            self._schema()
            self._view()
            with self._transaction(write=True, guard=False):
                row = self._conn.execute('SELECT * FROM progress WHERE id=1').fetchone()
                if row['format'] != FORMAT:
                    raise ValueError('unsupported cache format')
                if row['model'] != model_key:
                    self._conn.execute('DROP TABLE IF EXISTS vectors')
                    self._conn.execute('DELETE FROM entries')
                    self._conn.execute('DELETE FROM failures')
                    self._conn.execute("UPDATE progress SET model=?,epoch=?,sequence=sequence+1,dimension=NULL,cursor=0,ceiling=0,updated=NULL WHERE id=1",
                                       (model_key, uuid.uuid4().hex))
                self._epoch = self._conn.execute('SELECT epoch FROM progress WHERE id=1').fetchone()[0]
                dimension = self._conn.execute('SELECT dimension FROM progress WHERE id=1').fetchone()[0]
                if dimension is None:
                    inconsistent = self._conn.execute('SELECT 1 FROM entries LIMIT 1').fetchone()
                else:
                    inconsistent = self._conn.execute('''SELECT 1 FROM entries c
                        WHERE NOT EXISTS (SELECT 1 FROM vectors v WHERE v.rowid=c.vector_id) LIMIT 1''').fetchone()
                    if not inconsistent:
                        inconsistent = self._conn.execute('''SELECT rowid FROM vectors
                            EXCEPT SELECT vector_id FROM entries LIMIT 1''').fetchone()
                if inconsistent:
                    raise sqlite3.DatabaseError('inconsistent derived vector cache; rebuild required')
        except Exception:
            self._conn.close()
            raise

    def _schema(self):
        with self._conn:
            self._conn.execute('''CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY CHECK(id=1), format INTEGER NOT NULL,
                model TEXT NOT NULL, epoch TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0,
                dimension INTEGER, cursor INTEGER NOT NULL DEFAULT 0, ceiling INTEGER NOT NULL DEFAULT 0,
                updated REAL)''')
            self._conn.execute('INSERT OR IGNORE INTO progress(id,format,model,epoch) VALUES(1,?,?,?)',
                               (FORMAT, self._model, uuid.uuid4().hex))
            self._conn.execute('''CREATE TABLE IF NOT EXISTS entries (
                vector_id INTEGER PRIMARY KEY, item_key TEXT NOT NULL UNIQUE,
                episode_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                start INTEGER NOT NULL, end INTEGER NOT NULL, kind TEXT NOT NULL,
                source_digest TEXT NOT NULL, generation INTEGER NOT NULL)''')
            self._conn.execute('CREATE TABLE IF NOT EXISTS failures(item_key TEXT PRIMARY KEY, retry_after REAL NOT NULL)')

    def _view(self):
        # Use the shared source kind/state definition. Heads are explicitly
        # qualified because the authoritative store is attached read-only.
        tag = CHAT_LOOKUP_TAG.replace("'", "''")
        self._conn.execute(f'''CREATE TEMP VIEW eligible AS
            SELECT i.rowid AS ordinal,i.*,e.digest AS source_digest,e.support_generation AS generation
            FROM originals.working_memory_items i
            JOIN originals.working_memory_sources s ON s.episode_id=i.episode_id
            JOIN originals.episodes e ON e.id=i.episode_id
            LEFT JOIN originals.source_heads h ON h.source_key=e.source_key
            WHERE s.status='complete' AND s.fingerprint=i.fingerprint
              AND s.analysis_version={ANALYSIS_VERSION} AND {sql_sichtbar('e')}
              AND (e.source_key='' OR h.episode_id=e.id)
              AND NOT EXISTS (SELECT 1 FROM json_each(e.document,'$.tags') t WHERE t.value='{tag}')''')

    def _guard(self):
        stat = self._source.stat()
        if (stat.st_dev, stat.st_ino) != self._file_identity:
            raise ValueError('source file replaced; reopen cache and EpisodeStore')
        row = self._conn.execute('SELECT * FROM progress WHERE id=1').fetchone()
        if row['model'] != self._model or row['epoch'] != self._epoch or row['format'] != FORMAT:
            raise ValueError('cache model epoch changed; reopen')
        return row

    @contextmanager
    def _transaction(self, *, write=False, guard=True):
        # Same order everywhere; no model/network call holds either lock.
        with self._store.episodes._lock, self._lock:
            self._conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                row = self._guard() if guard else None
                yield row
                if guard:
                    # An external restore can replace the path while both
                    # SQLite handles still read its old inode. Abort before
                    # returning evidence or publishing derived progress.
                    self._guard()
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise

    def close(self):
        with self._lock:
            self._conn.close()

    @staticmethod
    def _match():
        return 'c.item_key=i.id AND c.source_digest=i.source_digest AND c.generation=i.generation'

    def _coverage(self):
        row = self._conn.execute(f'''SELECT COUNT(*) AS total,COUNT(c.vector_id) AS indexed,
            COUNT(f.item_key) AS failed FROM eligible i
            LEFT JOIN entries c ON {self._match()}
            LEFT JOIN failures f ON f.item_key=i.id AND c.vector_id IS NULL''').fetchone()
        return dict(row) | {'pending': row['total'] - row['indexed']}

    def coverage(self):
        """Structural eligible-key counts; source resolution remains mandatory."""
        with self._transaction() as row:
            return self._coverage() | {'model_key': self._model, 'updated_at': row['updated']}

    def pending(self, limit=MAX_BATCH):
        if type(limit) is not int or not 1 <= limit <= MAX_BATCH:
            raise ValueError('batch limit must be 1..64')
        with self._transaction(write=True) as progress:
            before, ceiling, sequence = progress['cursor'], progress['ceiling'], progress['sequence']
            def select():
                return self._conn.execute(f'''SELECT i.* FROM eligible i
                    LEFT JOIN entries c ON {self._match()}
                    LEFT JOIN failures f ON f.item_key=i.id
                    WHERE c.vector_id IS NULL AND (f.retry_after IS NULL OR f.retry_after<=?)
                      AND i.ordinal>? AND i.ordinal<=? ORDER BY i.ordinal LIMIT ?''',
                    (time.time(), before, ceiling, limit)).fetchall()
            rows = select() if ceiling else []
            if not rows:
                # Freeze a finite cycle. New arrivals cannot keep pushing its
                # upper boundary outward and starving older pending keys.
                before = 0
                ceiling = self._conn.execute('SELECT COALESCE(MAX(ordinal),0) FROM eligible').fetchone()[0]
                sequence += 1
                self._conn.execute('UPDATE progress SET cursor=?,ceiling=?,sequence=? WHERE id=1',
                                   (before, ceiling, sequence))
                rows = select()
            refs = tuple({key: row[key] for key in REF_FIELDS} for row in rows)
            return IndexBatch(refs, (self._epoch, sequence), before,
                              rows[-1]['ordinal'] if rows else before, ceiling, tuple(row['ordinal'] for row in rows))

    def _check_batch(self, batch, progress):
        if (not isinstance(batch, IndexBatch) or batch.token != (self._epoch, progress['sequence'])
                or batch.before != progress['cursor'] or batch.ceiling != progress['ceiling']):
            raise ValueError('stale batch progress')
        if len(batch.refs) > MAX_BATCH:
            raise ValueError('invalid batch size')
        keys = [_item_id(**ref) for ref in batch.refs]
        if (len(set(keys)) != len(keys) or len(batch.positions) != len(keys)
                or any(type(p) is not int or not batch.before < p <= batch.ceiling for p in batch.positions)
                or tuple(sorted(set(batch.positions))) != batch.positions
                or batch.cursor != (batch.positions[-1] if keys else batch.before)):
            raise ValueError('invalid batch cursor')
        for key, position in zip(keys, batch.positions):
            row = self._conn.execute('SELECT id FROM originals.working_memory_items WHERE rowid=?', (position,)).fetchone()
            if row is not None and row[0] != key:
                raise ValueError('stale batch item position')
        return keys

    def _advance(self, batch):
        self._conn.execute('UPDATE progress SET cursor=?,sequence=sequence+1,updated=? WHERE id=1',
                           (batch.cursor, time.time()))

    def commit(self, batch, vectors):
        if not isinstance(vectors, (list, tuple)) or len(vectors) != len(batch.refs):
            raise ValueError('incomplete embedding batch')
        packed = [_vector(v) for v in vectors]
        dimensions = {len(v) for v in vectors}
        if len(dimensions) > 1:
            raise ValueError('embedding dimensions differ')
        with self._transaction(write=True) as progress:
            keys = self._check_batch(batch, progress)
            dimension = next(iter(dimensions), None)
            if progress['dimension'] is not None and dimension is not None and dimension != progress['dimension']:
                raise ValueError('embedding dimensions changed for same model')
            if progress['dimension'] is None and dimension is not None:
                self._conn.execute(f'CREATE VIRTUAL TABLE vectors USING vec0(embedding float[{dimension}] distance_metric=cosine)')
                self._conn.execute('UPDATE progress SET dimension=? WHERE id=1', (dimension,))
            committed = 0
            for ref, key, vector in zip(batch.refs, keys, packed):
                snapshot = self._store.resolve(ref)
                current = self._conn.execute('SELECT * FROM eligible WHERE id=?', (key,)).fetchone()
                if snapshot is None or current is None:
                    self._conn.execute('INSERT OR REPLACE INTO failures VALUES(?,?)', (key, time.time() + RETRY_SECONDS))
                    continue
                previous = self._conn.execute('SELECT vector_id FROM entries WHERE item_key=?', (key,)).fetchone()
                if previous:
                    self._conn.execute('DELETE FROM vectors WHERE rowid=?', (previous[0],))
                    self._conn.execute('DELETE FROM entries WHERE vector_id=?', (previous[0],))
                inserted = self._conn.execute('''INSERT INTO entries(item_key,episode_id,fingerprint,start,end,kind,source_digest,generation)
                    VALUES(?,?,?,?,?,?,?,?)''', (key, *(ref[k] for k in REF_FIELDS), current['source_digest'], current['generation']))
                self._conn.execute('INSERT INTO vectors(rowid,embedding) VALUES(?,?)', (inserted.lastrowid, vector))
                self._conn.execute('DELETE FROM failures WHERE item_key=?', (key,))
                committed += 1
            self._advance(batch)
            return committed

    def fail(self, batch):
        """Advance this failed batch without discarding successful older work."""
        with self._transaction(write=True) as progress:
            keys = self._check_batch(batch, progress)
            self._conn.executemany('INSERT OR REPLACE INTO failures VALUES(?,?)',
                                   ((key, time.time() + RETRY_SECONDS) for key in keys))
            self._advance(batch)

    def prune(self, limit=MAX_BATCH):
        if type(limit) is not int or not 1 <= limit <= MAX_BATCH:
            raise ValueError('prune limit must be 1..64')
        with self._transaction(write=True):
            rows = self._conn.execute(f'''SELECT vector_id FROM entries c
                WHERE NOT EXISTS (SELECT 1 FROM eligible i WHERE {self._match()})
                ORDER BY vector_id LIMIT ?''', (limit,)).fetchall()
            for row in rows:
                self._conn.execute('DELETE FROM vectors WHERE rowid=?', (row[0],))
                self._conn.execute('DELETE FROM entries WHERE vector_id=?', (row[0],))
            return len(rows)

    def search(self, vector, *, limit=12, threshold=0.55):
        if type(limit) is not int or not 1 <= limit <= MAX_BATCH:
            raise ValueError('search limit must be 1..64')
        if type(threshold) not in (float, int) or not math.isfinite(threshold) or not -1 <= threshold <= 1:
            raise ValueError('invalid similarity threshold')
        packed = _vector(vector)
        with self._transaction() as progress:
            counts = self._coverage()
            status = 'partial' if counts['pending'] else ('ok' if counts['total'] else 'empty')
            if progress['dimension'] is None:
                return SemanticSearchResult((), status)
            if len(vector) != progress['dimension']:
                raise ValueError('query dimensions differ')
            budget = limit * 4 + 1
            rows = self._conn.execute('''SELECT c.*,v.distance FROM vectors v
                JOIN entries c ON c.vector_id=v.rowid
                WHERE v.embedding MATCH ? AND k=? ORDER BY distance''', (packed, budget)).fetchall()
            refs = []
            for row in rows:
                if row['distance'] > 1 - threshold:
                    break
                ref = {key: row[key] for key in REF_FIELDS}
                current = self._conn.execute('SELECT 1 FROM eligible i WHERE i.id=? AND i.source_digest=? AND i.generation=?',
                                             (row['item_key'], row['source_digest'], row['generation'])).fetchone()
                if current is None or self._store.resolve(ref) is None:
                    status = 'partial'
                    continue
                if len(refs) == limit:
                    status = 'partial'
                    break
                refs.append(ref)
            # Validation ran against the source lock as well as this SQLite
            # snapshot. Consumers re-resolve once more at display boundaries.
            return SemanticSearchResult(tuple(refs), status)
