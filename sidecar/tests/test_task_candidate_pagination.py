from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"))
    with TestClient(app) as test_client:
        yield app, test_client
    app.state.scheduler.stop()


def add_candidate(app, name, occurred_at):
    body = f"Bitte prüfe den Vorgang {name}."
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, f"Nachricht {name}", body,
        Provenance(source_type=SourceType.EMAIL, source_ref=f"test:{name}"),
        occurred_at=occurred_at,
    )
    app.state.proposals.record_task_analysis(
        episode.id, episode.digest,
        [{"title": f"Vorgang {name} prüfen", "quote": body}],
        proposed_by="test/local",
    )
    return episode


def test_page_reaches_every_candidate_past_the_legacy_first_hundred(client):
    app, http = client
    now = datetime.now(timezone.utc)
    for index in range(105):
        add_candidate(app, str(index), now - timedelta(minutes=index))

    pages = [http.get("/api/v1/task-candidates/page", params={"limit": 25, "offset": offset})
             for offset in (0, 25, 50, 75, 100)]

    assert all(response.status_code == 200 for response in pages)
    payloads = [response.json() for response in pages]
    assert [page["total"] for page in payloads] == [105] * 5
    assert len({page["generation"] for page in payloads}) == 1
    assert [len(page["items"]) for page in payloads] == [25, 25, 25, 25, 5]
    assert [page["has_more"] for page in payloads] == [True, True, True, True, False]
    assert len({item["id"] for page in payloads for item in page["items"]}) == 105
    # The existing unpaged endpoint remains available for older app clients.
    assert isinstance(http.get("/api/v1/task-candidates").json(), list)


def test_page_generation_rejects_offset_after_an_earlier_candidate_is_removed(client):
    app, http = client
    now = datetime.now(timezone.utc)
    candidates = [add_candidate(app, str(index), now - timedelta(minutes=index)) for index in range(3)]
    first = http.get("/api/v1/task-candidates/page", params={"limit": 2, "offset": 0}).json()
    assert first["generation"]
    removed_id = first["items"][0]["id"]
    later_id = next(candidate for candidate in candidates if candidate.id not in {
        item["evidence"][0]["episode_id"] for item in first["items"]
    }).id

    assert http.post(f"/api/v1/task-candidates/{removed_id}/reject").status_code == 200
    stale = http.get("/api/v1/task-candidates/page", params={
        "limit": 2, "offset": 2, "generation": first["generation"],
    })

    assert stale.status_code == 409
    assert stale.json()["detail"] == "Die Prüfliste hat sich geändert. Bitte die erste Seite neu laden."
    refreshed = http.get("/api/v1/task-candidates/page", params={"limit": 2, "offset": 0}).json()
    assert refreshed["total"] == 2
    assert later_id in {item["evidence"][0]["episode_id"] for item in refreshed["items"]}


def test_page_omits_pending_proposal_if_its_suggestion_task_already_exists(client):
    app, http = client
    episode = add_candidate(app, "orphan-task", datetime.now(timezone.utc))
    proposal = next(batch[0] for batch in app.state.proposals.pending_batches(ProposalKind.TASK))
    app.state.tasks.from_suggestion(proposal.id, "Schon gespeichert",
        Provenance(source_type=SourceType.USER_STATED, source_ref=f"episode:{episode.id}",
                   captured_at=datetime.now(timezone.utc)))

    response = http.get("/api/v1/task-candidates/page")

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_page_temporal_filters_and_total_only_include_valid_sources(client):
    app, http = client
    now = datetime.now(timezone.utc)
    recent = add_candidate(app, "recent", now - timedelta(hours=2))
    old = add_candidate(app, "old", now - timedelta(days=30))
    unknown = add_candidate(app, "unknown", None)
    revoked = add_candidate(app, "revoked", now - timedelta(hours=1))
    app.state.episodes.ignore(revoked.id)

    all_items = http.get("/api/v1/task-candidates/page", params={"temporal": "all"}).json()
    recent_items = http.get("/api/v1/task-candidates/page", params={"temporal": "recent"}).json()
    review_items = http.get("/api/v1/task-candidates/page", params={"temporal": "review"}).json()

    assert all_items["total"] == 3
    assert {item["temporal_status"] for item in recent_items["items"]} == {"recent"}
    assert {item["temporal_status"] for item in review_items["items"]} == {"old", "unknown"}
    assert {item["evidence"][0]["episode_id"] for item in all_items["items"]} == {recent.id, old.id, unknown.id}
    assert revoked.id not in str(all_items)


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 250001}, {"temporal": "invalid"},
])
def test_page_rejects_malformed_bounds_and_temporal_filter(client, params):
    _, http = client
    response = http.get("/api/v1/task-candidates/page", params=params)
    assert response.status_code == 422
