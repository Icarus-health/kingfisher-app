from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.proposals import ProposalStore
from icarus_memory.server import create_app


NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def app(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    return create_app(SelfModelStore(MemoryBackend(), "test"), episodes=episodes,
                      proposals=proposals, knowledge=claims)


def test_schedule_world_failure_does_not_block_learning_or_accept_claim(app, monkeypatch):
    from icarus_memory.habits import check_in, create_habit
    from icarus_memory import world_monitor

    habit = create_habit(app.state.store, "Lesen", 3)
    current = datetime.now(timezone.utc)
    for offset in (1, 2, 3):
        day = (current - timedelta(days=offset)).date().isoformat()
        check_in(app.state.store, app.state.episodes, habit.id, day, at=current)
    app.state.settings.schedule.enabled = True
    app.state.settings.world_sources.append({
        "id": "world-test", "url": "https://example.com/feed", "label": "Testquelle",
        "topics": ["Kingfisher"], "enabled": True, "episode_id": None,
        "last_success": None, "error": None, "truncated": False,
    })
    monkeypatch.setattr(world_monitor, "fetch_public_text", lambda _url: (_ for _ in ()).throw(OSError("offline")))
    response = TestClient(app).post("/schedule/run")
    assert response.status_code == 200
    jobs = {job["name"]: job for job in response.json()["jobs"]}
    assert jobs["world:world-test"]["ok"] is False
    assert jobs["lernen"]["ok"] is True
    assert any(p.proposed_by.startswith("habit-pattern:") for p in app.state.proposals.all_proposals(-1))
    assert app.state.claims.by_subject(f"habit:{habit.id}", include_inactive=True) == []
