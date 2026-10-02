from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr("icarus_memory.learning_routes._now", lambda: datetime(2026, 9, 8, 12, tzinfo=timezone.utc))

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.proposals import ProposalStore
from icarus_memory.server import create_app


def _client(tmp_path, token=None):
    if token:
        import os
        os.environ["ICARUS_SIDECAR_TOKEN"] = token
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    app = create_app(SelfModelStore(MemoryBackend(), "test"), episodes=episodes,
                     proposals=proposals, knowledge=claims)
    if token:
        os.environ.pop("ICARUS_SIDECAR_TOKEN", None)
    return TestClient(app)


def test_routes_are_protected(tmp_path):
    client = _client(tmp_path, "secret")
    assert client.get("/api/v1/habits").status_code == 401


def test_habit_checkins_scan_and_accept_end_to_end(tmp_path):
    client = _client(tmp_path)
    habit = client.post("/api/v1/habits", json={"label": "Lesen", "target_per_week": 3})
    assert habit.status_code == 201
    habit_id = habit.json()["id"]
    for day in ("2026-09-04", "2026-09-06", "2026-09-07"):
        assert client.post(f"/api/v1/habits/{habit_id}/checkins", json={"day": day}).status_code == 200
    assert client.get("/api/v1/habits").json()["items"][0]["checkins"] == 1
    scan = client.post("/api/v1/learning/scan")
    assert scan.status_code == 200
    proposal = scan.json()["items"][0]
    assert proposal["state"] == "pending"
    accepted = client.post(f"/api/v1/learning/{proposal['id']}/accept")
    assert accepted.status_code == 200
    assert client.get("/api/v1/learning").json()["items"][0]["claim"]["subject_ref"] == f"habit:{habit_id}"


def test_withdrawn_source_makes_old_learning_unacceptable(tmp_path):
    client = _client(tmp_path)
    habit_id = client.post("/api/v1/habits", json={"label": "Fokus", "target_per_week": 3}).json()["id"]
    for day in ("2026-09-04", "2026-09-06", "2026-09-07"):
        client.post(f"/api/v1/habits/{habit_id}/checkins", json={"day": day})
    proposal = client.post("/api/v1/learning/scan").json()["items"][0]
    episode_id = proposal["evidence"][0]["episode_id"]
    assert client.post(f"/api/v1/habits/checkins/{episode_id}/retract").status_code == 200
    assert client.post(f"/api/v1/learning/{proposal['id']}/accept").status_code == 409


def test_accepted_learning_reflects_withdrawn_evidence(tmp_path):
    client = _client(tmp_path)
    habit_id = client.post("/api/v1/habits", json={"label": "Gehen", "target_per_week": 3}).json()["id"]
    for day in ("2026-09-04", "2026-09-06", "2026-09-07"):
        client.post(f"/api/v1/habits/{habit_id}/checkins", json={"day": day})
    proposal = client.post("/api/v1/learning/scan").json()["items"][0]
    accepted = client.post(f"/api/v1/learning/{proposal['id']}/accept")
    assert accepted.status_code == 200 and accepted.json()["status"] == "active"
    episode_id = proposal["evidence"][0]["episode_id"]
    assert client.post(f"/api/v1/habits/checkins/{episode_id}/retract").status_code == 200
    reflected = client.get("/api/v1/learning").json()["items"][0]["claim"]
    assert reflected["status"] != "active"


def test_invalid_input_is_422(tmp_path):
    client = _client(tmp_path)
    assert client.post("/api/v1/habits", json={"label": "x", "target_per_week": 8}).status_code == 422
