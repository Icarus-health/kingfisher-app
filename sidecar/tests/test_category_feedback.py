"""Explicit topic feedback stays bound to the version the user reviewed."""
import threading
from contextlib import closing
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.mail_intake_routes import register
from icarus_memory.memory_categories import Categories


@pytest.fixture
def feedback(tmp_path):
    with closing(EpisodeStore(tmp_path / "episodes.sqlite3")) as episodes:
        item, _ = episodes.record(EpisodeKind.MESSAGE, "Synthetischer Newsletter",
            "Eine allgemeine Softwaremeldung, ohne persönlichen Auftrag.",
            Provenance(SourceType.CHAT, source_ref="synthetic:feedback"))
        app = FastAPI()
        app.state.episodes = episodes
        app.state.conversation_lock = threading.RLock()
        app.state.settings = SimpleNamespace()
        register(app, [], lambda: tmp_path, lambda _: None)
        with TestClient(app) as client:
            yield episodes, Categories(episodes), client, item


def read(client, item):
    response = client.get(f"/api/v1/episodes/{item.id}/categories")
    assert response.status_code == 200
    return response.json()


def save(client, item, revision, categories):
    return client.put(f"/api/v1/episodes/{item.id}/categories",
        json={"categories": categories, "expected_revision": revision})


def test_feedback_survives_new_store_view_without_changing_original(feedback):
    episodes, _, client, item = feedback
    original = episodes.get(item.id).to_dict()
    revision = read(client, item)["revision"]
    assert len(revision) == 64
    response = save(client, item, revision, ["information"])
    assert response.status_code == 200
    result = Categories(episodes).list_for(item.id)
    assert result["categories"][0]["origin"] == "user"
    assert result["categories"][0]["id"] == "information"
    assert result["revision"] != revision
    assert episodes.get(item.id).to_dict() == original


@pytest.mark.parametrize("change", ["source", "correction", "taxonomy", "withdrawal"])
def test_stale_feedback_is_rejected_without_overwriting_newer_state(feedback, change):
    episodes, categories, client, item = feedback
    revision = read(client, item)["revision"]
    if change == "source":
        changed = episodes.get(item.id)
        changed.participants = ["Ein anderer synthetischer Beteiligter"]
        episodes._put(changed)
    elif change == "correction":
        categories.correct(item.id, ["finance"])
    elif change == "taxonomy":
        categories.add_category("synthetic_test", "Synthetischer Bereich")
    else:
        episodes.ignore(item.id)
    original = episodes.get(item.id).to_dict()
    before = categories.list_for(item.id)
    response = save(client, item, revision, ["information"])
    assert response.status_code == 409
    assert categories.list_for(item.id) == before
    assert episodes.get(item.id).to_dict() == original


def test_latest_revision_can_clear_a_source_without_deleting_it(feedback):
    episodes, _, client, item = feedback
    first = save(client, item, read(client, item)["revision"], ["work", "information"])
    assert first.status_code == 200
    cleared = save(client, item, first.json()["revision"], [])
    assert cleared.status_code == 200
    assert cleared.json()["categories"] == []
    assert cleared.json()["correction"]["categories"] == []
    assert episodes.get(item.id).body == item.body


def test_existing_unguarded_client_remains_compatible(feedback):
    _, _, client, item = feedback
    response = client.put(f"/api/v1/episodes/{item.id}/categories",
        json={"categories": ["information"]})
    assert response.status_code == 200
    assert response.json()["categories"][0]["id"] == "information"


def test_feedback_and_review_revision_survive_database_reopen(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    with closing(EpisodeStore(path)) as episodes:
        item, _ = episodes.record(EpisodeKind.MESSAGE, "Synthetische Quelle",
            "Allgemeine Information.", Provenance(SourceType.CHAT, source_ref="synthetic:reopen"))
        categories = Categories(episodes)
        categories.correct(item.id, ["information"],
            expected_revision=categories.list_for(item.id)["revision"])
        saved = categories.list_for(item.id)
        original = episodes.get(item.id).to_dict()
    with closing(EpisodeStore(path)) as reopened:
        assert Categories(reopened).list_for(item.id) == saved
        assert reopened.get(item.id).to_dict() == original


@pytest.mark.parametrize("revision", ["", "not-a-revision", "G" * 64])
def test_malformed_feedback_revision_is_not_ignored(feedback, revision):
    _, categories, client, item = feedback
    before = categories.list_for(item.id)
    assert save(client, item, revision, ["information"]).status_code == 422
    assert categories.list_for(item.id) == before
