"""Opt-in, bounded semantic candidates over explicitly selected canonical claims.

The in-memory snapshot is disposable, never a memory store or an authority.
No network/configuration is enabled by importing this module. The application
default remains lexical until German retrieval/answer quality is qualified.
Rank fusion follows Tencent WeKnora's memory/vector.go; see
docs/third-party/weknora.md for the pinned source. The upstream permission
notice is kept here as well so wheel/container distributions retain it:

Copyright (C) 2025 Tencent. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to
do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""
from dataclasses import dataclass
import json
import math

from .claim_index import CANDIDATE_LIMIT
from .knowledge_render import KnowledgeInputBuild, ROW_BYTES, serialize

MIN_COSINE = 0.5  # Development starting point, not a calibrated relevance guarantee.
MAX_DIMENSIONS = 4096


def fuse_rankings(lexical, semantic):
    """Reciprocal rank fusion (k=60), one vote per channel and stable ties."""
    scores = {}
    for ranking in (lexical, semantic):
        for rank, identifier in enumerate(dict.fromkeys(ranking)):
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (60.0 + rank)
    return sorted(scores, key=lambda identifier: -scores[identifier])


def unit_vector(value, dimensions=None):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= MAX_DIMENSIONS:
        raise ValueError('invalid embedding dimensions')
    if dimensions is not None and len(value) != dimensions:
        raise ValueError('embedding space changed')
    try:
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in value):
            raise ValueError('invalid embedding value')
    except OverflowError as exc:
        raise ValueError('invalid embedding value') from exc
    norm = math.hypot(*value)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError('invalid embedding norm')
    return tuple(n / norm for n in value)


def binding(entry):
    return json.dumps(entry, sort_keys=True, allow_nan=False)


def model_key(embedder):
    if getattr(embedder, 'is_local', False) is not True:
        raise ValueError('only a local embedder is permitted')
    key = getattr(embedder, 'model_key', None)
    if not isinstance(key, str) or not key.strip():
        raise ValueError('immutable embedding model identity required')
    return key


@dataclass(frozen=True)
class SemanticRow:
    claim_id: str
    source_binding: str
    vector: tuple[float, ...]


class HybridKnowledgeSearch:
    def __init__(self, rows, embedder, key):
        self._rows = tuple(rows)
        self._embedder = embedder
        self._key = key

    @classmethod
    def prepare(cls, claims, snapshot_provider, claim_ids, embedder):
        """Embed at most 128 expressly selected claims with valid evidence.

        The caller chooses the scope and a bounded local embedding adapter.
        Invalid/oversized claims are omitted; full-store coverage is never implied.
        """
        if not isinstance(claim_ids, (list, tuple)) or len(claim_ids) > CANDIDATE_LIMIT:
            raise ValueError('semantic snapshot exceeds 128 selected claims')
        key = model_key(embedder)
        build = KnowledgeInputBuild(claims, snapshot_provider)
        selected, texts = [], []
        for identifier in dict.fromkeys(claim_ids):
            captured = build.capture(identifier)
            if captured is None:
                continue
            claim, projection, entry = captured
            if len(serialize(projection).encode('utf-8')) > ROW_BYTES:
                continue
            selected.append((claim.id, binding(entry)))
            texts.append('\n'.join((claim.statement, claim.predicate, claim.value)))
        if not selected:
            return cls((), embedder, key)
        vectors = embedder.embed(texts)
        if not isinstance(vectors, (list, tuple)) or len(vectors) != len(selected):
            raise ValueError('embedding batch is incomplete')
        if model_key(embedder) != key:
            raise ValueError('embedding model changed during preparation')
        rows = []
        dimensions = None
        for (identifier, source_binding), vector in zip(selected, vectors):
            unit = unit_vector(vector, dimensions)
            dimensions = len(unit)
            rows.append(SemanticRow(identifier, source_binding, unit))
        return cls(rows, embedder, key)

    def search_context(self, query, claims, snapshot_provider):
        lexical, metadata = claims.search_context(query)
        metadata.update(ranking_mode='lexical', semantic_status='empty_snapshot',
                        semantic_scope='explicit_snapshot', semantic_snapshot_items=len(self._rows),
                        semantic_hits=0, semantic_stale=0, semantic_candidate_ids=[])
        if not self._rows or not query.strip():
            return lexical, metadata
        # Embedding errors cannot disable the already-working lexical path.
        try:
            if model_key(self._embedder) != self._key:
                raise ValueError('embedding model changed')
            if len(query.encode('utf-8')) > ROW_BYTES:
                raise ValueError('embedding query exceeds budget')
            vectors = self._embedder.embed([query])
            if not isinstance(vectors, (list, tuple)) or len(vectors) != 1:
                raise ValueError('query embedding is incomplete')
            vector = unit_vector(vectors[0], len(self._rows[0].vector))
            if model_key(self._embedder) != self._key:
                raise ValueError('embedding model changed during query')
        except Exception:
            # Adapters may use different transport exception hierarchies.
            # This boundary deliberately excludes KeyboardInterrupt/SystemExit.
            metadata['semantic_status'] = 'unavailable'
            return lexical, metadata
        build = KnowledgeInputBuild(claims, snapshot_provider)
        semantic, current = [], {claim.id: claim for claim in lexical}
        for row in self._rows:
            captured = build.capture(row.claim_id)
            if captured is None or binding(captured[2]) != row.source_binding:
                metadata['semantic_stale'] += 1
                continue
            similarity = sum(a * b for a, b in zip(row.vector, vector))
            if similarity >= MIN_COSINE:
                semantic.append((row.claim_id, similarity))
                current[row.claim_id] = captured[0]
        semantic.sort(key=lambda hit: (-hit[1], hit[0]))
        semantic_ids = [identifier for identifier, _ in semantic]
        if not semantic_ids:
            metadata['semantic_status'] = 'no_matches'
            return lexical, metadata
        ranked = fuse_rankings([claim.id for claim in lexical], semantic_ids)
        truncated = len(ranked) > CANDIDATE_LIMIT
        selected = ranked[:CANDIDATE_LIMIT]
        metadata.update(ranking_mode='hybrid', semantic_status='ok', semantic_hits=len(semantic_ids),
                        semantic_candidate_ids=[i for i in selected if i in semantic_ids],
                        candidates_returned=len(selected),
                        candidates_truncated=metadata['candidates_truncated'] or truncated,
                        truncated=metadata['truncated'] or truncated)
        return [current[identifier] for identifier in selected], metadata


class RefreshingKnowledgeSearch:
    """Disposable live cache with explicit bounded coverage and lexical fallback.

    Originals are recaptured on every query, including metadata-only changes and
    time expiry. Only unchanged canonical rows reuse vectors. No permission or
    fact is persisted in this cache; restart rebuilds it from current originals.
    """
    def __init__(self, embedder, *, limit=512):
        import threading
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError('live semantic inventory must be bounded to 1..4096 claims')
        self._embedder, self._limit = embedder, limit
        self._key = model_key(embedder)
        self._cache = {}
        self._lock = threading.Lock()

    @property
    def cached_count(self):
        return len(self._cache)

    def search_context(self, query, claims, snapshot_provider):
        with self._lock:
            identifiers, total = claims.semantic_inventory(self._limit)
            omitted = 0
            try:
                key = model_key(self._embedder)
                if key != self._key:
                    self._cache.clear()
                    self._key = key
                build = KnowledgeInputBuild(claims, snapshot_provider)
                keep, changed = {}, []
                for identifier in identifiers:
                    captured = build.capture(identifier)
                    if captured is None or len(serialize(captured[1]).encode('utf-8')) > ROW_BYTES:
                        omitted += 1
                        continue
                    old = self._cache.get(identifier)
                    if old is not None and old.source_binding == binding(captured[2]):
                        keep[identifier] = old
                    else:
                        changed.append(identifier)
                # Withdrawn/out-of-scope rows are removed even if rebuilding fails.
                self._cache = keep
                for offset in range(0, len(changed), CANDIDATE_LIMIT):
                    batch = HybridKnowledgeSearch.prepare(claims, snapshot_provider,
                        changed[offset:offset + CANDIDATE_LIMIT], self._embedder)
                    keep.update((row.claim_id, row) for row in batch._rows)
                if len({len(row.vector) for row in keep.values()}) > 1:
                    raise ValueError('cached embedding dimensions changed')
                snapshot = HybridKnowledgeSearch(tuple(keep.values()), self._embedder, self._key)
                results, metadata = snapshot.search_context(query, claims, snapshot_provider)
            except Exception:
                self._cache.clear()
                results, metadata = claims.search_context(query)
                metadata.update(ranking_mode='lexical', semantic_status='unavailable', semantic_candidate_ids=[])
            metadata.update(semantic_scope='bounded_live', semantic_inventory_total=total,
                semantic_inventory_limit=self._limit, semantic_snapshot_items=len(self._cache),
                semantic_coverage='partial' if total > len(self._cache) or omitted else 'complete')
            return results, metadata


def configured_search(provider, model=None):
    """Explicit runtime opt-in, with no network request until a local query."""
    import os
    if os.environ.get('ICARUS_MEMORY_SEMANTIC') != '1' or not getattr(provider, 'is_local', False):
        return None
    from urllib.parse import urlsplit, urlunsplit
    from .local_embeddings import LocalEmbedder
    base = urlsplit(getattr(provider, 'base_url', 'http://127.0.0.1:11434/v1'))
    endpoint = urlunsplit((base.scheme, base.netloc, '', '', ''))
    trusted = tuple(host.strip() for host in os.environ.get('ICARUS_TRUSTED_LOCAL_MODEL_HOSTS', '').split(',') if host.strip())
    return LazyLocalSearch(lambda: LocalEmbedder(base_url=endpoint, trusted_local_hosts=trusted, timeout=3, model=model))


class LazyLocalSearch:
    def __init__(self, factory):
        import threading
        self._factory = factory
        self._search = None
        self._next_attempt = 0
        self._lock = threading.Lock()

    def search_context(self, query, claims, snapshot_provider):
        import time
        with self._lock:
            if self._search is None and time.monotonic() >= self._next_attempt:
                try:
                    adapter = self._factory().__enter__()
                    self._search = RefreshingKnowledgeSearch(adapter)
                except Exception:
                    self._next_attempt = time.monotonic() + 30
            if self._search is not None:
                return self._search.search_context(query, claims, snapshot_provider)
            rows, metadata = claims.search_context(query)
            metadata.update(ranking_mode='lexical', semantic_scope='bounded_live',
                            semantic_status='unavailable', semantic_coverage='unknown', semantic_candidate_ids=[])
            return rows, metadata
