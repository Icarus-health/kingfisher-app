"""HTTP regression coverage for literal answers from uploaded source documents."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from icarus_memory.claims import KnowledgeService
from icarus_memory.proposals import Evidence
from icarus_memory.server import create_app
from tests.test_context_identity import AT, core
from tests.test_conversation_retraction import _close_app
from tests.test_knowledge_time import change_source


QUESTION = 'Was steht zu "AURORA-4711" in meinen Quellen?'
TITLE = "vertragsnotiz-privat.txt"
EXCERPT = (
    "AURORA-4711: Mira prüft den Termin nur, wenn die Freigabe bis Freitag kommt; "
    "sonst bleibt er offen."
)


def _upload(client: TestClient, body: str = f"Vorgang\n\n{EXCERPT}\n") -> str:
    response = client.post(
        "/api/v1/sources/documents",
        json={"filename": TITLE, "body": body},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _conversation(client: TestClient) -> str:
    response = client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    return response.json()["conversation"]["id"]


def _ask(client: TestClient, conversation_id: str, question: str = QUESTION) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": question, "answer_mode": "auto"},
    )
    assert response.status_code == 201
    return response.json()["messages"][-1]


def _api(core, tmp_path, monkeypatch):
    agent, provider, *_ = core
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "source-answer-api"))
    monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", "local-owner-token")
    app = create_app(agent._store, agent=agent)
    client = TestClient(app, headers={"X-Icarus-Token": "local-owner-token"})
    return app, client, provider


def test_eingeordnete_originalquelle_bleibt_ohne_modellauswahl_abrufbar(core, tmp_path, monkeypatch):
    """Wörtliche Anzeige braucht weder Fragenmodell noch Auswahlmodell."""
    from icarus_memory.providers import ProviderError
    from icarus_memory.working_memory_store import WorkingMemoryStore

    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        source_id = _upload(client)
        store = WorkingMemoryStore(app.state.episodes)
        snapshot = store.pending(episode_ids=[source_id])[0]
        assert store.commit(snapshot, [{"start": 0, "end": len(snapshot.episode.body), "kind": "conditional"}],
                            model="synthetisch")
        calls = []

        def unavailable(*args, **kwargs):
            calls.append(True)
            raise ProviderError("Synthetisch ausgeschaltetes Modell")

        monkeypatch.setattr(provider, 'complete', unavailable)
        monkeypatch.setattr(provider, 'complete_json', unavailable, raising=False)
        conversation_id = _conversation(client)
        answer = _ask(client, conversation_id)
        context = answer['metadata']['context']
        assert context['answer_contract']['status'] == 'source_report'
        assert context['answer_contract']['model_called'] is False
        assert context['source_answer']['refs'][0]['episode_id'] == source_id
        assert EXCERPT in answer['content']
        assert calls == []
        app.state.episodes.ignore(source_id)
        reopened = client.get(f"/api/v1/conversations/{conversation_id}")
        assert reopened.status_code == 200
        assert EXCERPT not in str(reopened.json())
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('question', [QUESTION, 'Suche in meinen Quellen nach "AURORA-4711".'])
def test_raw_document_answer_is_projected_from_neutral_persisted_references(
    core, tmp_path, monkeypatch, question
):
    agent, provider, _, claims, _ = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        source_id = _upload(client)
        conversation_id = _conversation(client)
        claim_revision = claims.revision
        proposal_counts = app.state.proposals.counts()
        self_model_before = agent._store._backend.all()

        posted = _ask(client, conversation_id, question)
        context = posted["metadata"]["context"]
        source_answer = context["source_answer"]
        assert source_answer["version"] == 1
        assert source_answer["refs"]
        assert source_answer["refs"][0]["episode_id"] == source_id
        assert source_answer["refs"][0]["fingerprint"]
        assert source_answer["refs"][0]["start"] < source_answer["refs"][0]["end"]
        assert source_answer["coverage"]
        assert context["answer_contract"]["status"] == "source_report"
        assert EXCERPT in posted["content"]
        assert "Quelle berichtet" in posted["content"]
        assert "nicht bestätigt" in posted["content"]
        assert "nur, wenn die Freigabe bis Freitag kommt" in posted["content"]
        assert provider.calls == []
        assert claims.revision == claim_revision
        assert app.state.proposals.counts() == proposal_counts
        assert agent._store._backend.all() == self_model_before

        stored = next(
            item for item in app.state.conversations.messages(conversation_id)
            if item.role == "assistant"
        )
        assert EXCERPT not in stored.content
        assert TITLE not in stored.content
        assert EXCERPT not in str(stored.metadata)
        assert TITLE not in str(stored.metadata)

        reopened = client.get(f"/api/v1/conversations/{conversation_id}")
        assert reopened.status_code == 200
        projected = reopened.json()["messages"][-1]
        assert EXCERPT in projected["content"]
        assert projected["metadata"]["context"]["source_answer"]["refs"] == source_answer["refs"]
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)


def test_ignored_source_invalidates_saved_answer_and_explicit_reopen_allows_new_answer(
    core, tmp_path, monkeypatch
):
    _, provider, _, claims, _ = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        source_id = _upload(client)
        conversation_id = _conversation(client)
        original = _ask(client, conversation_id)
        assert EXCERPT in original["content"]

        ignored = client.post(f"/api/v1/episodes/{source_id}/ignore")
        assert ignored.status_code == 200
        current = client.get(f"/api/v1/conversations/{conversation_id}")
        assert current.status_code == 200
        current_text = str(current.json())
        assert EXCERPT not in current_text
        assert TITLE not in current_text
        listing = client.get("/api/v1/conversations")
        assert listing.status_code == 200
        assert EXCERPT not in str(listing.json())
        assert TITLE not in str(listing.json())

        reopened = client.post(f"/api/v1/episodes/{source_id}/reopen")
        assert reopened.status_code == 200
        after_reopen = client.get(f"/api/v1/conversations/{conversation_id}")
        assert after_reopen.status_code == 200
        assert EXCERPT not in str(after_reopen.json())
        assert TITLE not in str(after_reopen.json())
        later = _ask(client, conversation_id, QUESTION + " Bitte prüfe erneut.")
        assert EXCERPT in later["content"]
        assert "source_report" == later["metadata"]["context"]["answer_contract"]["status"]
        assert provider.calls == []
        assert claims.revision == 0
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)


def test_source_fingerprint_change_without_claim_revision_invalidates_old_projection(
    core, tmp_path, monkeypatch
):
    _, provider, episodes, claims, _ = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        source_id = _upload(client)
        conversation_id = _conversation(client)
        original = _ask(client, conversation_id)
        revision = claims.revision

        change_source(episodes, source_id, source_ref="upload:changed-private-ref.txt")
        assert claims.revision == revision

        current = client.get(f"/api/v1/conversations/{conversation_id}")
        assert current.status_code == 200
        assert EXCERPT not in str(current.json())
        assert TITLE not in str(current.json())
        assert provider.calls == []
        assert EXCERPT in original["content"]
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)


def test_saved_source_answer_never_enters_later_unrelated_provider_history(
    core, tmp_path, monkeypatch
):
    agent, provider, *_ = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _upload(client)
        conversation_id = _conversation(client)
        _ask(client, conversation_id)
        saved = client.get(f"/api/v1/conversations/{conversation_id}").json()["messages"]
        history = [
            {"role": item["role"], "content": item["content"],
             "context": item.get("metadata", {}).get("context")}
            for item in saved
            if item["role"] in {"user", "assistant"}
        ]

        agent.load_history(history)
        agent.send("How should I plan a quiet weekend?")

        assert provider.calls
        assert EXCERPT not in str(provider.calls[-1])
        assert TITLE not in str(provider.calls[-1])
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)


def test_remote_provider_configuration_cannot_read_raw_source_documents(
    core, tmp_path, monkeypatch
):
    _, provider, *_ = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _upload(client)
        conversation_id = _conversation(client)
        provider.is_local = False

        answer = _ask(client, conversation_id)

        assert EXCERPT not in answer["content"]
        assert TITLE not in answer["content"]
        assert answer["metadata"]["context"].get("source_answer") is None
        assert provider.calls == []
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)


def test_source_upload_requires_local_owner_authentication(core, tmp_path, monkeypatch):
    agent, *_ = core
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "source-answer-unauthenticated"))
    monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", "local-owner-token")
    app = create_app(agent._store, agent=agent)
    try:
        response = TestClient(app).post(
            "/api/v1/sources/documents",
            json={"filename": TITLE, "body": f"Vorgang\n\n{EXCERPT}\n"},
        )
        assert response.status_code == 401
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)


def test_ignored_source_stays_withdrawn_from_saved_answers_after_app_restart(
    core, tmp_path, monkeypatch
):
    agent, *_ = core
    app, client, _ = _api(core, tmp_path, monkeypatch)
    data_dir = tmp_path / "source-answer-api"
    try:
        source_id = _upload(client)
        conversation_id = _conversation(client)
        assert EXCERPT in _ask(client, conversation_id)["content"]
        ignored = client.post(f"/api/v1/episodes/{source_id}/ignore")
        assert ignored.status_code == 200
        app.state.episodes = app.state.claims = None
        _close_app(app)

        monkeypatch.setenv("ICARUS_DATA_DIR", str(data_dir))
        restarted = create_app(agent._store, agent=agent)
        try:
            restarted_client = TestClient(
                restarted, headers={"X-Icarus-Token": "local-owner-token"}
            )
            response = restarted_client.get(f"/api/v1/conversations/{conversation_id}")
            assert response.status_code == 200
            assert EXCERPT not in str(response.json())
            assert TITLE not in str(response.json())
        finally:
            restarted.state.episodes = restarted.state.claims = None
            _close_app(restarted)
    finally:
        if getattr(app.state, "conversations", None) is not None:
            app.state.episodes = app.state.claims = None
            _close_app(app)


def test_retracted_claim_does_not_fall_back_to_its_raw_source(core, tmp_path, monkeypatch):
    agent, provider, _, claims, _ = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        source_id = _upload(client)
        original_source = app.state.episodes.get(source_id)
        service = KnowledgeService(
            episodes=app.state.episodes,
            claims=claims,
            proposals=app.state.proposals,
        )
        proposal, _ = service.propose(
            subject_ref="project:aurora-4711",
            predicate="review_status",
            value="not confirmed",
            statement="The AURORA-4711 appointment is not confirmed.",
            evidence=[Evidence(source_id, EXCERPT, original_source.digest)],
            rationale="Synthetic regression setup",
            at=AT,
        )
        claim = service.accept(proposal.id, supersedes=[], at=AT)
        claims.retract(claim.id, reason="Synthetic regression withdrawal", at=AT)
        revision = claims.revision

        conversation_id = _conversation(client)
        answer = _ask(client, conversation_id)
        assert EXCERPT not in answer["content"]
        source_answer = answer["metadata"]["context"]["source_answer"]
        assert source_answer["refs"] == []
        assert source_answer["coverage"]["deferred_count"] == 1
        assert answer["metadata"]["context"]["answer_contract"]["status"] != "source_report"
        assert provider.calls == []
        assert claims.revision == revision
        assert agent._store._backend.all() == []
    finally:
        app.state.episodes = app.state.claims = None
        _close_app(app)
