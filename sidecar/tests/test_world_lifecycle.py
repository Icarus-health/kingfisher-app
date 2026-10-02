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
