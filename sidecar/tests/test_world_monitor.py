from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace

import pytest

from icarus_memory.world_monitor import WorldMonitor


class Episodes:
    def __init__(self):
        self.items = {}
        self.heads = {}
        self.n = 0

    def record(self, kind, title, body, provenance, *, tags, source_key):
        old = self.items.get((source_key, body))
        if old:
            return old, False
        self.n += 1
        episode = SimpleNamespace(id=f"e{self.n}", body=body, provenance=provenance,
                                  digest="sha256:" + sha256(body.encode()).hexdigest())
        self.items[(source_key, body)] = episode
        return episode, True

    def get(self, episode_id):
        return next(episode for episode in self.items.values() if episode.id == episode_id)

    def source_head(self, key):
        return self.heads.get(key)

    def _mail_attachment_descendants(self, episode_id):
        # This fake stores public web excerpts, never mail attachments.
        return []

    def ignore(self, episode_id):
        return episode_id

    def advance_source_head(self, key, expected, episode_id):
        assert self.heads.get(key) == expected
        self.heads[key] = episode_id


class Claims:
    def __init__(self):
        self.invalidated = []

    def invalidate_source(self, episode_id):
        self.invalidated.append(episode_id)


def monitor(fetch):
    settings = SimpleNamespace(world_sources=[])
    episodes, claims = Episodes(), Claims()
    return WorldMonitor(settings, episodes, claims, lambda _settings: None, __import__("threading").RLock(), fetch), episodes, claims


def test_same_content_deduplicates_and_changed_content_invalidates(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    values = iter([{"text": "one", "captured_at": "2026-01-01T00:00:00Z"}, {"text": "one", "captured_at": "2026-01-02T00:00:00Z"}, {"text": "two", "captured_at": "2026-01-03T00:00:00Z"}])
    m, episodes, claims = monitor(lambda _url: next(values))
    source = m.add("https://example.test", "Example", ["topic"])
    m.refresh(source["id"])
    m.refresh(source["id"])
    assert claims.invalidated == []
    m.refresh(source["id"])
    assert claims.invalidated == ["e1"]


def test_disabled_during_fetch_does_not_write(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    m, episodes, _claims = monitor(lambda _url: {"text": "late", "captured_at": "2026-01-01T00:00:00Z"})
    source = m.add("https://example.test", "Example", [])
    original = m.fetch
    def fetch(_url):
        m.disable(source["id"])
        return original(_url)
    m.fetch = fetch
    with pytest.raises(ValueError, match="geändert"):
        m.refresh(source["id"])
    assert episodes.n == 0


def test_failure_preserves_previous_episode_and_is_safe(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    state = [{"text": "kept", "captured_at": "2026-01-01T00:00:00Z"}]
    m, episodes, _claims = monitor(lambda _url: state.pop() if state else (_ for _ in ()).throw(RuntimeError("secret")))
    source = m.add("https://example.test", "Example", [])
    m.refresh(source["id"])
    previous = m.list()[0]
    with pytest.raises(ValueError):
        m.refresh(source["id"])
    assert episodes.n == 1
    listed = m.list()[0]
    assert listed["status"] == "stale"
    assert listed["last_success"] == previous["last_success"]
    assert listed["fetched_url"] == previous["fetched_url"]
    assert listed["source_sha256"] == previous["source_sha256"]
    assert "secret" not in str(listed)


def test_sources_are_independent_and_disable_invalidates(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    m, _episodes, claims = monitor(lambda url: {"text": url, "captured_at": datetime.now(timezone.utc).isoformat()})
    a, b = m.add("https://a.test", "A", []) , m.add("https://b.test", "B", [])
    m.refresh(a["id"]); m.refresh(b["id"]); m.disable(a["id"])
    assert claims.invalidated == ["e1"]
    with pytest.raises(ValueError, match="deaktiviert"):
        m.refresh(a["id"])
    assert m.list()[1]["status"] == "ok"


def test_older_concurrent_refresh_cannot_overwrite_newer(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    m, episodes, _claims = monitor(lambda _url: {"text": "new", "captured_at": datetime.now(timezone.utc).isoformat()})
    source = m.add("https://example.test", "Example", [])
    m.refresh(source["id"])
    old = m.settings.world_sources[0]["episode_id"]
    def older_fetch(_url):
        # Simulate a newer successful commit by another refresh before this
        # refresh reaches its commit check.
        m.settings.world_sources[0]["episode_id"] = "e-newer"
        m.settings.world_sources[0]["last_success"] = "2026-09-08T01:00:00Z"
        return {"text": "older", "captured_at": "2026-09-07T00:00:00Z"}
    m.fetch = older_fetch
    with pytest.raises(ValueError, match="geändert"):
        m.refresh(source["id"])
    assert m.settings.world_sources[0]["episode_id"] == "e-newer"
    assert old == "e1"


def test_malformed_timestamp_is_stale(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    m, _episodes, _claims = monitor(lambda _url: {"text": "x", "captured_at": "bad"})
    source = m.add("https://example.test", "Example", [])
    m.settings.world_sources[0]["last_success"] = "not-a-date"
    assert m.list()[0]["status"] == "stale"
