"""A chat source remains available without promoting a model memory write."""

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.policy import Policy
from icarus_memory.providers import Reply, ToolCall
from icarus_memory.server import create_app
from icarus_memory.tools import build_registry


class RepeatingMerkenProvider:
    name = model = "synthetic-merken-loop"
    is_local = True

    def __init__(self):
        self.calls = []
        self.tools_seen = []

    def complete(self, messages, tools):
        self.calls.append(messages)
        self.tools_seen.append(tools)
        return Reply(tool_calls=[ToolCall("merken-1", "merken", {
            "statement": "Der Nutzer möchte wegen des Keramiktests nicht vor 10 Uhr angerufen werden.",
            "kind": "constraint",
        })])


def test_preference_is_kept_as_original_chat_source_but_not_confirmed(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "data"))
    store = SelfModelStore(MemoryBackend(), subject_id="synthetic")
    audit = AuditLog(tmp_path / "agent-audit.sqlite3")
    provider = RepeatingMerkenProvider()
    agent = Agent(store, Policy(), audit, build_registry(store), provider, max_rounds=4)
    app = create_app(store, agent=agent)
    client = TestClient(app)
    text = "Für den Keramiktest bitte erst nach 10 Uhr anrufen; morgens bin ich in der Werkstatt."
    try:
        conversation = client.post("/api/v1/conversations", json={})
        assert conversation.status_code == 201
        conversation_id = conversation.json()["conversation"]["id"]
        response = client.post(f"/api/v1/conversations/{conversation_id}/messages",
            json={"message": text, "answer_mode": "chat"})
        assert response.status_code == 201, response.text

        user, assistant = response.json()["messages"]
        source_id = user["metadata"]["context"]["source_links"][0]["episode_id"]
        source = app.state.episodes.get(source_id)
        assert source.body == text
        assert source.provenance.verbatim == text
        assert assistant["content"] == "Ich habe keine bestätigte Gedächtnisaussage gespeichert."
        assert assistant["metadata"]["used_tools"] == []
        assert assistant["metadata"]["notices"] == []
        assert provider.calls and len(provider.calls) == 1
        assert "merken" not in {item["name"] for item in provider.tools_seen[0]}
        assert store.usable() == []
        assert audit.entries()[0]["outcome"] == "refused"
    finally:
        client.close()
        for name in ("audit", "tasks", "workspace", "episodes", "proposals", "conversations", "claims", "regeln"):
            resource = getattr(app.state, name, None)
            if callable(getattr(resource, "close", None)):
                resource.close()
        audit.close()
