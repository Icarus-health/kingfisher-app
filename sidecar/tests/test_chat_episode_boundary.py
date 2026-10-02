"""A chat model cannot create a paraphrased episode beside its captured source."""

from fastapi.testclient import TestClient
import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.policy import Policy
from icarus_memory.providers import Reply, ToolCall
from icarus_memory.server import create_app
from icarus_memory.tools import build_registry


ORIGINAL = "Ich arbeite an Atlas und bereite die Keramikprüfung vor."


class PlaceholderAgent:
    provider = None

    def load_history(self, history):
        self.history = history

    def send(self, message, *, conversation_source_captured=False):
        raise AssertionError("placeholder agent must be replaced before requests")


class RepeatingEpisodeProvider:
    name = "synthetic"
    model = "synthetic-episode-draft"
    is_local = True

    def __init__(self, art):
        self.art = art
        self.calls = []
        self.tools_seen = []

    def complete(self, messages, tools):
        self.calls.append(messages)
        self.tools_seen.append(tools)
        return Reply(tool_calls=[ToolCall("episode-1", "episode_festhalten", {
            "titel": f"Modellparaphrase-{self.art}-Echo991",
            "text": f"ModellparaphraseEcho991: Die Person leitet Projekt Atlas ({self.art}).",
            "art": self.art,
        })])


def make_agent(app, provider):
    return Agent(
        store=app.state.store,
        policy=Policy(),
        audit=app.state.audit,
        tools=build_registry(app.state.store, episodes=app.state.episodes),
        provider=provider,
        knowledge=app.state.claims,
        episodes=app.state.episodes,
        snapshot_provider=app.state.episodes.support_snapshot,
        max_rounds=4,
    )


def close_app(app):
    for name in ("audit", "tasks", "workspace", "episodes", "proposals",
                 "conversations", "claims", "regeln"):
        store = getattr(app.state, name, None)
        close = getattr(store, "close", None)
        if callable(close):
            close()


@pytest.mark.parametrize("art", ["message", "document"])
def test_chat_cannot_make_paraphrase_episode_survive_source_withdrawal(tmp_path, monkeypatch, art):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "data"))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="synthetic"), agent=PlaceholderAgent())
    provider = RepeatingEpisodeProvider(art)
    agent = make_agent(app, provider)
    app.state.agent = agent
    client = TestClient(app)
    token = "ModellparaphraseEcho991"
    try:
        conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"message": ORIGINAL, "answer_mode": "chat"},
        )
        assert response.status_code == 201, response.text
        user, assistant = response.json()["messages"]

        # The server-created original is the only episode; `produced` is not
        # an AI-origin marker and must not be used to make this distinction.
        episodes = app.state.episodes.all_episodes()
        assert len(episodes) == 1
        source = episodes[0]
        assert source.body == ORIGINAL
        assert source.provenance.verbatim == ORIGINAL
        assert source.provenance.source_ref == (
            f"conversation:{conversation_id}:message:{user['id']}"
        )
        assert token not in str(episodes)
        assert app.state.episodes.search(token) == []

        assert len(provider.calls) == 1  # defensive refusal, no model retry loop
        assert "episode_festhalten" not in {item["name"] for item in provider.tools_seen[0]}
        assert assistant["metadata"]["used_tools"] == []
        assert assistant["metadata"]["approvals"] == []
        assert any(entry["tool"] == "episode_festhalten" and entry["outcome"] == "refused"
                   for entry in app.state.audit.entries())

        ignored = client.post(f"/api/v1/episodes/{source.id}/ignore")
        assert ignored.status_code == 200
        visible = client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert token not in str(visible)
        assert app.state.episodes.search(token) == []
    finally:
        client.close()
        close_app(app)


def test_episode_tool_route_no_longer_writes_for_external_callers(tmp_path, monkeypatch, mcp_tuer_offen):
    # Die Werkzeugroute ist die MCP-Tür: Ein Aufrufer von außen schreibt nicht
    # ohne Vorschlag in den Bestand, auch nicht als Rohmaterial.
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "data"))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="synthetic"), agent=PlaceholderAgent())
    agent = make_agent(app, RepeatingEpisodeProvider("document"))
    app.state.agent = agent
    client = TestClient(app)
    try:
        assert "episode_festhalten" in {tool["name"] for tool in agent.tool_schemas()}
        response = client.post("/tools/episode_festhalten", json={
            "titel": "Ausdrücklich festgehaltene synthetische Beobachtung",
            "text": "Vom direkten Nutzer-Werkzeugweg angefordert.",
            "art": "observation",
        })
        assert response.status_code == 200, response.text
        assert response.json()["ok"] is False
        assert not any(e.title == "Ausdrücklich festgehaltene synthetische Beobachtung"
                       for e in app.state.episodes.all_episodes())
    finally:
        client.close()
        close_app(app)
