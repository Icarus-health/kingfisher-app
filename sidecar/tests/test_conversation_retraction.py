"""Conversation memory cards expose and can correct their live claim status."""

from __future__ import annotations

from fastapi.testclient import TestClient

from icarus_memory.agent import Turn
from icarus_memory.backends import MemoryBackend
from icarus_memory.conversation_memory import capture
from icarus_memory.proposals import Evidence
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore


class StubAgent:
    def load_history(self, messages: list[dict[str, str]]) -> None:
        pass

    def send(self, message: str) -> Turn:
        return Turn(reply=f"Antwort auf: {message}")


def _make_app(tmp_path, monkeypatch, *, token: str | None = None):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    if token is None:
        monkeypatch.delenv("ICARUS_SIDECAR_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", token)
    return create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=StubAgent()
    )


def _close_app(app) -> None:
    for name in ("audit", "tasks", "workspace", "episodes", "proposals", "conversations", "claims", "regeln"):
        store = getattr(app.state, name, None)
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _candidate(client: TestClient, conversation_id: str, *, value: str = "Atlas") -> str:
    source = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": f"Kranz arbeitet an {value}."},
    ).json()
    source_id = source["messages"][0]["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates",
        json={
            "source_message_id": source_id,
            "subject_ref": "person:kranz",
            "predicate": "works_on",
            "value": value,
            "statement": f"Kranz arbeitet an {value}.",
        },
    )
    assert response.status_code == 201
    return response.json()["memory_candidates"][-1]["candidate"]["id"]


def test_accepted_candidate_retracts_and_status_survives_reload(tmp_path, monkeypatch) -> None:
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    proposal_id = _candidate(client, conversation_id)

    accepted = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{proposal_id}/accept",
        json={"replace_conflicts": False},
    )
    assert accepted.status_code == 200
    card = next(item for item in accepted.json()["memory_candidates"] if item["candidate"]["id"] == proposal_id)
    assert card["candidate"]["state"] == "accepted"
    assert card["claim"]["proposal_id"] == proposal_id
    assert card["claim"]["status"] == "active"
    assert card["claim_usable"] is True
    claim_id = card["claim"]["id"]
    # Simulate a previously persisted assistant turn whose context included
    # this claim. Retraction must update the displayed context while leaving
    # the transcript itself intact.
    app.state.conversations.add_message(
        conversation_id,
        "assistant",
        "Historische Antwort",
        metadata={
            "context": {
                "query": "Kranz",
                "generated_at": "2026-09-01T10:00:00+00:00",
                "items": [{"assertion_id": f"claim:{claim_id}", "statement": "Kranz arbeitet an Atlas."}],
                "withheld_count": 0,
            }
        },
    )

    retracted = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{proposal_id}/retract",
        json={"reason": "Die Zuordnung war falsch."},
    )
    assert retracted.status_code == 200
    card = next(item for item in retracted.json()["memory_candidates"] if item["candidate"]["id"] == proposal_id)
    assert card["candidate"]["state"] == "accepted"
    assert card["claim"]["id"] == claim_id
    assert card["claim"]["status"] == "retracted"
    assert card["claim_usable"] is False
    assert retracted.json()["context"]["items"] == []
    assert any(item["content"] == "Historische Antwort" for item in retracted.json()["messages"])
    _close_app(app)

    restarted = _make_app(tmp_path, monkeypatch)
    try:
        restored = TestClient(restarted).get(f"/api/v1/conversations/{conversation_id}")
        assert restored.status_code == 200
        card = restored.json()["memory_candidates"][0]
        assert card["candidate"]["state"] == "accepted"
        assert card["claim"]["status"] == "retracted"
        assert card["claim_usable"] is False
        assert restored.json()["context"]["items"] == []
        assert any(item["content"] == "Historische Antwort" for item in restored.json()["messages"])
    finally:
        _close_app(restarted)


def test_retract_protects_foreign_conversation_and_pending_candidates(tmp_path, monkeypatch) -> None:
    app = _make_app(tmp_path, monkeypatch)
    try:
        client = TestClient(app)
        first = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
        second = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
        proposal_id = _candidate(client, first)
        foreign = client.post(
            f"/api/v1/conversations/{second}/memory-candidates/{proposal_id}/retract",
            json={"reason": "Fremder Zugriff"},
        )
        assert foreign.status_code == 404
        assert client.get(f"/api/v1/conversations/{first}").json()["memory_candidates"][0]["claim"] is None

        pending_id = _candidate(client, first, value="Luna")
        pending = client.post(
            f"/api/v1/conversations/{first}/memory-candidates/{pending_id}/retract",
            json={"reason": "Noch nicht angenommen"},
        )
        assert pending.status_code == 409
        pending_card = next(
            item for item in client.get(f"/api/v1/conversations/{first}").json()["memory_candidates"]
            if item["candidate"]["id"] == pending_id
        )
        assert pending_card["candidate"]["state"] == "pending"
        assert pending_card["claim"] is None
        assert pending_card["claim_usable"] is False
    finally:
        _close_app(app)


def test_retract_route_requires_sidecar_authentication(tmp_path, monkeypatch) -> None:
    app = _make_app(tmp_path, monkeypatch, token="secret")
    try:
        response = TestClient(app).post(
            "/api/v1/conversations/c-any/memory-candidates/v-any/retract",
            json={"reason": "Kein Token"},
        )
        assert response.status_code == 401
    finally:
        _close_app(app)


def test_retracting_base_claim_marks_dependent_card_unusable(tmp_path, monkeypatch) -> None:
    app = _make_app(tmp_path, monkeypatch)
    try:
        client = TestClient(app)
        conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
        base_id = _candidate(client, conversation_id, value="Atlas")
        accepted = client.post(
            f"/api/v1/conversations/{conversation_id}/memory-candidates/{base_id}/accept",
            json={"replace_conflicts": False},
        ).json()
        base_card = next(item for item in accepted["memory_candidates"] if item["candidate"]["id"] == base_id)
        base_claim_id = base_card["claim"]["id"]

        source = app.state.conversations.add_message(
            conversation_id, "user", "Kranz ist die Kontaktperson für Atlas."
        )
        episode, _ = capture(app.state.episodes, conversation_id, source)
        dependent, _ = app.state.knowledge_service.propose(
            subject_ref="project:atlas",
            predicate="contact",
            value="person:kranz",
            statement="Kranz ist die Kontaktperson für Atlas.",
            rationale="Abgeleitet aus der bestätigten Arbeitsbeziehung.",
            depends_on=[base_claim_id],
            evidence=[Evidence(episode.id, source.content, episode.digest)],
        )
        app.state.conversations.add_message(
            conversation_id,
            "assistant",
            "Gedächtnisvorschlag",
            metadata={"memory_candidate_id": dependent.id, "memory_source_message_id": source.id},
        )
        app.state.knowledge_service.accept(dependent.id, supersedes=[])

        retracted = client.post(
            f"/api/v1/conversations/{conversation_id}/memory-candidates/{base_id}/retract",
            json={"reason": "Grundlage korrigiert."},
        )
        assert retracted.status_code == 200
        dependent_card = next(
            item for item in retracted.json()["memory_candidates"] if item["candidate"]["id"] == dependent.id
        )
        assert dependent_card["candidate"]["state"] == "accepted"
        assert dependent_card["claim"]["status"] == "disputed"
        assert dependent_card["claim_usable"] is False
    finally:
        _close_app(app)
