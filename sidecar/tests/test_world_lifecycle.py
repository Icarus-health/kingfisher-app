from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeStore
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.server import create_app
from icarus_memory.world_monitor import WorldMonitor


NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


def test_identical_text_at_changed_redirect_keeps_distinct_original_provenance(tmp_path, monkeypatch):
    from icarus_memory.config import Settings
    monkeypatch.setattr('icarus_memory.world_monitor._validate_url', lambda url: url)
    episodes = EpisodeStore(tmp_path / 'redirect-episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'redirect-claims.sqlite3')
    try:
        version = {'url': 'https://example.org/first', 'text': 'Unchanged source text',
                   'captured_at': '2026-10-01T09:00:00+00:00'}
        import threading
        monitor = WorldMonitor(Settings(), episodes, claims, lambda _: None, threading.RLock(),
                               fetch=lambda _: dict(version))
        source = monitor.add('https://example.org/start', 'Public source', [])
        first = monitor.refresh(source['id'])
        # Simulate the pre-URL-aware metadata of an installed older database.
        from icarus_memory.episodes import source_metadata_digest
        old_document = episodes.get(first['episode_id']).to_dict()
        old_document.pop('provenance')
        episodes._conn.execute('UPDATE episodes SET metadata_digest=? WHERE id=?',
                               (source_metadata_digest(old_document), first['episode_id']))
        assert monitor.refresh(source['id'])['episode_id'] == first['episode_id']
        version.update(url='https://example.org/second', captured_at='2026-10-02T09:00:00+00:00')
        second = monitor.refresh(source['id'])
        assert second['episode_id'] != first['episode_id']
        old, new = episodes.get(first['episode_id']), episodes.get(second['episode_id'])
        assert old.body == new.body and old.digest == new.digest
        assert old.provenance.source_ref == 'https://example.org/first'
        assert new.provenance.source_ref == second['fetched_url'] == 'https://example.org/second'
        assert new.provenance.captured_at.isoformat() == second['last_success']
        assert old.state.value == 'ignored'
    finally:
        claims.close()
        episodes.close()


def test_refresh_cannot_reactivate_a_withdrawn_public_version(tmp_path, monkeypatch):
    from icarus_memory.config import Settings
    import threading
    monkeypatch.setattr('icarus_memory.world_monitor._validate_url', lambda url: url)
    episodes = EpisodeStore(tmp_path / 'cycle-episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'cycle-claims.sqlite3')
    try:
        version = {'text': 'Version A', 'captured_at': NOW.isoformat()}
        monitor = WorldMonitor(Settings(), episodes, claims, lambda _: None,
                               threading.RLock(), fetch=lambda _: dict(version))
        source = monitor.add('https://example.org/source', 'Public source', [])
        first = monitor.refresh(source['id'])
        version['text'] = 'Version B'
        second = monitor.refresh(source['id'])
        assert episodes.get(first['episode_id']).state.value == 'ignored'
        version['text'] = 'Version A'
        with pytest.raises(ValueError, match='zurückgezogen'):
            monitor.refresh(source['id'])
        assert episodes.source_head('world:' + source['id']) == second['episode_id']
        assert monitor.list()[0]['episode_id'] == second['episode_id']
        assert episodes.get(second['episode_id']).state.value != 'ignored'
    finally:
        claims.close()
        episodes.close()


def test_world_source_versions_claims_and_disable_are_real(tmp_path, monkeypatch):
    # Der Sicherheitscheck löst auch bei einem Fake-Fetch die öffentliche
    # Adresse auf. DNS ist hier kein Teil des getesteten Lebenszyklus.
    import socket
    from icarus_memory import security
    def public_example(host, port, *, proto):
        assert host == 'example.com' and proto == socket.IPPROTO_TCP
        return [(socket.AF_INET, socket.SOCK_STREAM, proto, '', ('93.184.215.14', port))]
    monkeypatch.setattr(security.socket, 'getaddrinfo', public_example)
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    store = SelfModelStore(MemoryBackend(), "test")
    app = create_app(store, episodes=episodes, knowledge=claims, proposals=proposals)
    versions = [{"text": "Regelung v1", "captured_at": NOW.isoformat()}]
    monitor = WorldMonitor(app.state.settings, episodes, claims, lambda _settings: None,
                           app.state.conversation_lock, fetch=lambda _url: versions[0])
    source = monitor.add("https://example.com/regeln", "Regelwerk", ["Regulierung"])
    first = monitor.refresh(source["id"])
    old = episodes.get(first["episode_id"])
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    proposal, _ = service.propose(
        subject_ref="project:test", predicate="regulatory_state", value="v1",
        statement="Das Regelwerk liegt in Fassung v1 vor.", rationale="Öffentliche Quelle.",
        evidence=[Evidence(old.id, old.body, old.digest)], proposed_by="test", at=NOW,
    )
    claim = service.accept(proposal.id, supersedes=[], at=NOW)
    same = monitor.refresh(source["id"])
    assert same["episode_id"] == old.id
    versions[0] = {"text": "Regelung v2", "captured_at": NOW.isoformat()}
    changed = monitor.refresh(source["id"])
    assert changed["episode_id"] != old.id
    assert episodes.get(old.id).state.value == "ignored"
    assert claims.get(claim.id).status.value != "active"
    monitor.disable(source["id"])
    assert episodes.get(changed["episode_id"]).state.value == "ignored"
    assert monitor.list()[0]["enabled"] is False


def test_world_and_learning_routes_require_app_token(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", "world-secret")
    app = create_app(SelfModelStore(MemoryBackend(), "test"),
                     episodes=EpisodeStore(tmp_path / "episodes.sqlite3"),
                     proposals=ProposalStore(tmp_path / "proposals.sqlite3"),
                     knowledge=ClaimStore(tmp_path / "claims.sqlite3"))
    client = TestClient(app)
    assert client.get("/api/v1/world").status_code == 401
    assert client.post("/api/v1/world", json={"url": "https://example.com", "label": "Public"}).status_code == 401
    assert client.get("/api/v1/habits").status_code == 401
    assert client.post("/api/v1/learning/scan").status_code == 401
