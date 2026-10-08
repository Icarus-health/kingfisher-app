"""App-scoped local meaning search; sources are embedded only by a bounded job."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager, nullcontext
from dataclasses import replace

from .episodes import CHAT_LOOKUP_TAG, sql_geltend, sql_nicht_ausgeblendet
from .hintergrund import AMPEL
from .scheduler import JobResult
from .working_memory_semantic import SemanticSearchResult, TEXT_BYTES, _text
from .working_memory_semantic_index import DurableSemanticIndex
from .working_memory_store import ANALYSIS_VERSION, WorkingMemoryStore

BATCH_SOURCES = 8
BATCH_BYTES = 16384
RETRY_SECONDS = 30


class _Changed(Exception):
    """Permission/configuration changed; never a source processing failure."""


class SemanticService:
    def __init__(self, episodes, factory, *, configuration=lambda: (), enabled=lambda: True,
                 permission_lock=None, ampel=None):
        self.episodes = episodes
        self._store = WorkingMemoryStore(episodes)
        self._factory = factory
        self._configuration = configuration
        self._enabled = enabled
        self._permission_lock = permission_lock or threading.RLock()
        self._ampel = ampel or AMPEL
        self._lock = threading.RLock()
        self._index = None
        self._model_key = None
        self._checked_at = None
        self._bound_configuration = None
        self._closed = False
        self._error = False
        self._retry_at = 0.0
        self._request = threading.local()

    @contextmanager
    def request(self):
        """Reuse question vectors, never source selections, in one HTTP turn."""
        previous = getattr(self._request, 'vectors', None)
        self._request.vectors = {}
        try:
            yield
        finally:
            self._request.vectors = previous

    def _check(self, expected, permitted):
        if self._closed or not self._enabled() or not permitted() or self._configuration() != expected:
            raise _Changed()

    @contextmanager
    def _operation(self, permitted, *, foreground=False):
        # Foreground callers already serialize the conversation. Do not
        # acquire that non-reentrant lock twice. Background capture/commit
        # uses it explicitly, and releases it throughout model transport.
        with nullcontext() if foreground else self._permission_lock:
            expected = self._configuration()
            self._check(expected, permitted)
        # No source/service lock over transport. The foreground caller owns
        # its existing conversation serialization; background work owns none.
        with self._ampel.aufruf():
            self._check(expected, permitted)
            with self._lock:
                if time.monotonic() < self._retry_at:
                    raise RuntimeError('embedding temporarily unavailable')
            adapter = self._factory()
            if getattr(adapter, 'is_local', False) is not True:
                raise ValueError('local embedding adapter required')
            with adapter as embedder:
                if getattr(embedder, 'is_local', False) is not True:
                    raise ValueError('local embedding adapter required')
                self._check(expected, permitted)
                key = embedder.model_key
                with self._lock:
                    if self._closed:
                        raise _Changed()
                    if self._index is None or key != self._model_key:
                        if self._index is not None:
                            self._index.close()
                            self._index = None
                        self._index = DurableSemanticIndex(self.episodes, key)
                        self._model_key = key
                    index = self._index
                    self._checked_at = time.time()
                    self._bound_configuration = expected
                yield embedder, index, expected
                self._check(expected, permitted)

    def _success(self):
        with self._lock:
            self._error = False
            self._retry_at = 0.0

    def _failure(self):
        with self._lock:
            self._error = True
            self._retry_at = time.monotonic() + RETRY_SECONDS

    def _source_pending(self):
        # Structural source classification count, no snapshots/model calls.
        # Dismissal is intentional exclusion; deferred/failed remains a gap.
        with self.episodes._lock:
            return self.episodes._conn.execute(f'''SELECT COUNT(*) FROM episodes e
                LEFT JOIN working_memory_sources s ON s.episode_id=e.id
                WHERE {sql_geltend('e')} AND {sql_nicht_ausgeblendet('e')}
                  AND NOT EXISTS (SELECT 1 FROM json_each(e.document,'$.tags') t WHERE t.value=?)
                  AND (s.status IS NULL OR (s.status!='dismissed'
                       AND (s.status!='complete' OR s.analysis_version!=?)))''',
                (CHAT_LOOKUP_TAG, ANALYSIS_VERSION)).fetchone()[0]

    def coverage(self):
        with self._lock:
            index, key, checked, error = self._index, self._model_key, self._checked_at, self._error
            closed = self._closed
            bound = self._bound_configuration
        base = {'status': 'unavailable', 'model_key': key, 'identity_checked_at': checked,
                'total': None, 'indexed': None, 'pending': None, 'failed': None,
                'updated_at': None, 'source_pending': None}
        if closed or not self._enabled():
            return base | {'status': 'disabled'}
        try:
            source_pending = self._source_pending()
            base['source_pending'] = source_pending
            if index is not None:
                counts = index.coverage()
                base.update(counts)
                base['status'] = ('unavailable' if error or bound != self._configuration() else
                                  'partial' if counts['pending'] or source_pending else 'indexed')
        except Exception:
            base['status'] = 'unavailable'
        return base

    def search(self, episodes, query, limit=12):
        return list(self.search_with_status(episodes, query, limit).refs)

    def search_with_status(self, episodes, query, limit=12):
        if (episodes is not self.episodes or not isinstance(query, str) or not query.strip()
                or len(query.encode('utf-8')) > TEXT_BYTES):
            return SemanticSearchResult((), 'unavailable')
        try:
            with self._operation(lambda: True, foreground=True) as (embedder, index, expected):
                counts = index.coverage()
                if not counts['indexed']:
                    result = SemanticSearchResult((), 'partial' if counts['pending'] else 'empty')
                else:
                    cache = getattr(self._request, 'vectors', None)
                    cache_key = (embedder.model_key, query)
                    vector = cache.get(cache_key) if cache is not None else None
                    if vector is None:
                        vectors = embedder.embed([query])
                        if not isinstance(vectors, (list, tuple)) or len(vectors) != 1:
                            raise ValueError('incomplete query embedding')
                        vector = vectors[0]
                    self._check(expected, lambda: True)
                    # Always query and resolve against live source state,
                    # including when routing already used the same vector.
                    result = index.search(vector, limit=limit)
                    if cache is not None:
                        cache[cache_key] = tuple(vector)
                if result.status in {'ok', 'empty'} and self._source_pending():
                    result = SemanticSearchResult(result.refs, 'partial')
            self._success()
            return result
        except _Changed:
            return SemanticSearchResult((), 'unavailable')
        except Exception:
            self._failure()
            return SemanticSearchResult((), 'unavailable')

    @staticmethod
    def _prefix(batch, count):
        return replace(batch, refs=batch.refs[:count], positions=batch.positions[:count],
                       cursor=batch.positions[count - 1])

    def index_batch(self, *, permitted=lambda: True):
        batch = index = expected = None
        try:
            with self._operation(permitted) as (embedder, index, expected):
                index.prune(BATCH_SOURCES)
                batch = index.pending(BATCH_SOURCES)
                if not batch.refs:
                    self._success()
                    return JobResult('bedeutungssuche', True, 'Vorhandene Einordnungen sind für die Bedeutungssuche vorbereitet.')
                texts, byte_count = [], 0
                for ref in batch.refs:
                    snapshot = self._store.resolve(ref)
                    if snapshot is None:
                        break
                    text = _text(snapshot, ref)
                    size = len(text.encode('utf-8'))
                    if byte_count + size > BATCH_BYTES:
                        break
                    texts.append(text)
                    byte_count += size
                if not texts:
                    batch = self._prefix(batch, 1)
                    vectors = None
                else:
                    batch = self._prefix(batch, len(texts))
                    self._check(expected, permitted)
                    vectors = embedder.embed(texts)
            # Release AMPEL before taking the conversation lock: a question
            # may own that lock while waiting for our model slot to finish.
            with self._permission_lock:
                self._check(expected, permitted)
                if vectors is None:
                    index.fail(batch)
                    return JobResult('bedeutungssuche', False, 'Ein Quellenabschnitt konnte nicht geprüft werden; erneuter Versuch folgt.')
                else:
                    completed = index.commit(batch, vectors)
            self._success()
            return JobResult('bedeutungssuche', True, f'{completed} Quellenabschnitte für die Bedeutungssuche vorbereitet.')
        except _Changed:
            return JobResult('bedeutungssuche', True, 'Bedeutungssuche nach geänderter Freigabe pausiert.')
        except Exception:
            if batch is not None and index is not None:
                try:
                    with self._permission_lock:
                        self._check(expected, permitted)
                        index.fail(batch)
                except Exception:
                    pass
            self._failure()
            return JobResult('bedeutungssuche', False, 'Bedeutungssuche vorübergehend nicht verfügbar; vorhandene Originale bleiben erhalten.')

    def close(self):
        with self._lock:
            self._closed = True
            index, self._index = self._index, None
        if index is not None:
            index.close()
