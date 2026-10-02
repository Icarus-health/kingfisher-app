"""Bedeutungssuche für den Arbeitsstand: lokal, abgeleitet, ausdrücklich eingeschaltet.

Findet eingeordnete Quellenabschnitte, deren Wortlaut nicht mit der Frage
übereinstimmt („Ausweis zum Reinkommen“ → „Zugangskarte“). Die Vektoren sind
ein flüchtiger Zwischenstand im Speicher, kein neues Wahrheitslager: Bei jeder
Suche wird der aktuelle Bestand gelesen; entzogene, berichtigte oder
geänderte Quellen fallen heraus, weil ihr Fingerabdruck sich ändert. Nach einem
Neustart wird neu berechnet. Jeder Fehler lässt die Wortsuche unverändert
arbeiten. Eingeschaltet nur mit ``ICARUS_MEMORY_SEMANTIC=1`` und lokalem Modell.
"""
from __future__ import annotations

import math
import os
import threading
import time

from .working_memory_store import WorkingMemoryStore

MIN_SIMILARITY = 0.55
INVENTORY_LIMIT = 2048
BATCH = 64
TEXT_BYTES = 8000


def _key(ref):
    return (ref['episode_id'], ref['fingerprint'], ref['start'], ref['end'], ref['kind'])


def _unit(vector):
    values = [float(value) for value in vector]
    if not values or any(math.isnan(value) or math.isinf(value) for value in values):
        raise ValueError('invalid embedding')
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        raise ValueError('invalid embedding norm')
    return tuple(value / norm for value in values)


def _text(snapshot, ref):
    episode = snapshot.episode
    text = f"{episode.title[:300]}: {episode.body[ref['start']:ref['end']]}"
    encoded = text.encode('utf-8')[:TEXT_BYTES]
    return encoded.decode('utf-8', errors='ignore')


class WorkingMemorySemantic:
    """Begrenzter Vektor-Zwischenstand über den aktuellen Arbeitsstand."""

    def __init__(self, embedder, *, threshold=MIN_SIMILARITY, limit=INVENTORY_LIMIT):
        if getattr(embedder, 'is_local', False) is not True:
            raise ValueError('only a local embedder is permitted')
        self._embedder = embedder
        self._threshold = threshold
        self._limit = limit
        self._model = getattr(embedder, 'model_key', None)
        self._cache = {}
        self._lock = threading.Lock()
        self.status = 'empty'

    def _refresh(self, store):
        found = store.inventory(self._limit)
        current = {}
        missing = []
        for ref in found['refs']:
            key = _key(ref)
            if key in self._cache:
                current[key] = self._cache[key]
                continue
            snapshot = store.resolve(ref)
            if snapshot is not None:
                missing.append((key, _text(snapshot, ref)))
        # Entzogenes fällt sofort heraus, auch wenn das Einbetten scheitert.
        self._cache = current
        for offset in range(0, len(missing), BATCH):
            batch = missing[offset:offset + BATCH]
            vectors = self._embedder.embed([text for _, text in batch])
            if not isinstance(vectors, (list, tuple)) or len(vectors) != len(batch):
                raise ValueError('embedding batch is incomplete')
            for (key, _), vector in zip(batch, vectors):
                self._cache[key] = _unit(vector)
        if len({len(vector) for vector in self._cache.values()}) > 1:
            raise ValueError('embedding dimensions changed')
        return found['truncated']

    def search(self, episodes, query, limit=12):
        """Referenzen über der Ähnlichkeitsschwelle, ähnlichste zuerst; [] bei Fehlern."""
        if not isinstance(query, str) or not query.strip() or len(query.encode('utf-8')) > TEXT_BYTES:
            return []
        store = WorkingMemoryStore(episodes)
        with self._lock:
            try:
                if getattr(self._embedder, 'model_key', None) != self._model:
                    self._cache.clear()
                    self._model = getattr(self._embedder, 'model_key', None)
                truncated = self._refresh(store)
                if not self._cache:
                    self.status = 'empty'
                    return []
                vectors = self._embedder.embed([query])
                if not isinstance(vectors, (list, tuple)) or len(vectors) != 1:
                    raise ValueError('query embedding is incomplete')
                question = _unit(vectors[0])
                if len(question) != len(next(iter(self._cache.values()))):
                    raise ValueError('query dimensions differ')
            except Exception:
                # Transportfehler verschiedener Adapter; die Wortsuche bleibt.
                self._cache.clear()
                self.status = 'unavailable'
                return []
            scored = sorted(((sum(a * b for a, b in zip(question, vector)), key)
                             for key, vector in self._cache.items()), reverse=True)
            self.status = 'partial' if truncated else 'ok'
        refs = []
        for similarity, key in scored:
            if similarity < self._threshold or len(refs) >= limit:
                break
            ref = dict(zip(('episode_id', 'fingerprint', 'start', 'end', 'kind'), key))
            if store.resolve(ref) is not None:
                refs.append(ref)
        return refs


class _Lazy:
    """Verbindet sich erst bei der ersten Frage; nach Fehlern 30 s Pause."""

    def __init__(self, factory):
        self._factory = factory
        self._search = None
        self._next_attempt = 0.0
        self._lock = threading.Lock()

    def search(self, episodes, query, limit=12):
        with self._lock:
            if self._search is None and time.monotonic() >= self._next_attempt:
                try:
                    self._search = WorkingMemorySemantic(self._factory().__enter__())
                except Exception:
                    self._next_attempt = time.monotonic() + 30
            search = self._search
        return search.search(episodes, query, limit) if search is not None else []


_configured = {}
_configured_lock = threading.Lock()


def for_provider(provider, model=None):
    """Die eingeschaltete Bedeutungssuche für dieses lokale Modell, sonst None."""
    if os.environ.get('ICARUS_MEMORY_SEMANTIC') != '1' or not getattr(provider, 'is_local', False):
        return None
    from urllib.parse import urlsplit, urlunsplit
    base = urlsplit(getattr(provider, 'base_url', 'http://127.0.0.1:11434/v1'))
    endpoint = urlunsplit((base.scheme, base.netloc, '', '', ''))
    trusted = tuple(host.strip() for host in os.environ.get('ICARUS_TRUSTED_LOCAL_MODEL_HOSTS', '').split(',')
                    if host.strip())
    with _configured_lock:
        key = (endpoint, model or '')
        if key not in _configured:
            from .local_embeddings import LocalEmbedder
            _configured[key] = _Lazy(lambda: LocalEmbedder(base_url=endpoint, trusted_local_hosts=trusted,
                                                           timeout=3, model=model))
        return _configured[key]
