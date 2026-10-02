"""Gesprächsbindung, einmalige Freigabe und sichere unklare Ergebnisse."""
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Turn
from icarus_memory.policy import Policy, ActionClass
from icarus_memory.server import create_app


class ActionAgent:
    def __init__(self):
        self.policy = Policy()
        self.executions = 0
        self.fail_after_execution = False

    def load_history(self, history):
        self.history = history

    def send(self, message, *, conversation_source_captured=False):
        args = {"to": "test@example.invalid"}
        action = self.policy.request("test_send", args,
            self.policy.decide("test_send", ActionClass.OUTWARD, args),
            "Testaktion an test@example.invalid\nInhalt: Nur ein isolierter Test.")
        return Turn(reply="Bitte prüfe die Aktion.", approvals=[action])

    def resolve(self, approval_id, granted, confirmation):
        if not granted:
            self.policy.reject(approval_id)
            return Turn(reply="Abgelehnt. Nichts ausgeführt.", approval_outcome="rejected")
        self.policy.grant(approval_id, confirmation)
        self.executions += 1
        if self.fail_after_execution:
            raise RuntimeError("Antwortweg unterbrochen")
        return Turn(reply="Testaktion ausgeführt.", approval_outcome="approved")


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    agent = ActionAgent()
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"), agent=agent)
    client = TestClient(app)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    payload = client.post(f"/api/v1/conversations/{conversation}/messages", json={"message": "Testaktion vorbereiten"}).json()
    action = payload["action_requests"][0]
    url = f'/api/v1/conversations/{conversation}/approvals/{action["id"]}'
    return client, agent, conversation, action, url


def test_action_is_bound_to_conversation_and_only_executes_once(monkeypatch, tmp_path):
    client, agent, conversation, action, url = setup_client(monkeypatch, tmp_path)
    other = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    assert client.post(url.replace(conversation, other), json={"granted": True}).status_code == 404
    assert client.post(url, json={"granted": True, "confirmation": "wrong"}).status_code == 409
    assert agent.executions == 0
    result = client.post(url, json={"granted": True, "confirmation": action["confirmation_phrase"]})
    assert result.status_code == 200
    assert result.json()["context"]["items"] == []
    assert result.json()["action_requests"][0]["state"] == "approved"
    assert result.json()["messages"][-1]["content"] == "Testaktion ausgeführt."
    assert agent.history[0]["content"] == "Testaktion vorbereiten"
    assert client.post(url, json={"granted": True, "confirmation": action["confirmation_phrase"]}).status_code == 409
    assert agent.executions == 1
    assert client.get(f"/api/v1/conversations/{conversation}").json()["action_requests"][0]["state"] == "approved"


def test_rejection_and_expiry_never_execute(monkeypatch, tmp_path):
    client, agent, conversation, action, url = setup_client(monkeypatch, tmp_path)
    result = client.post(url, json={"granted": False})
    assert result.json()["action_requests"][0]["state"] == "rejected"
    assert agent.executions == 0
    payload = client.post(f"/api/v1/conversations/{conversation}/messages", json={"message": "Noch ein Test"}).json()
    new_action = payload["action_requests"][-1]
    agent.policy = Policy()  # Neustart verliert die ausstehende Ausführungsberechtigung.
    assert client.get(f"/api/v1/conversations/{conversation}").json()["action_requests"][-1]["state"] == "expired"
    assert client.post(url.replace(action["id"], new_action["id"]), json={"granted": True}).status_code == 409
    assert agent.executions == 0


def test_unknown_result_cannot_be_retried_as_model_message(monkeypatch, tmp_path):
    client, agent, conversation, action, url = setup_client(monkeypatch, tmp_path)
    agent.fail_after_execution = True
    result = client.post(url, json={"granted": True, "confirmation": action["confirmation_phrase"]}).json()
    assert result["action_requests"][0]["state"] == "unknown"
    failed = result["messages"][-1]
    assert failed["status"] == "error"
    assert client.post(f'/api/v1/conversations/{conversation}/messages/{failed["id"]}/retry').status_code == 409
    assert client.post(url, json={"granted": True}).status_code == 409
    assert agent.executions == 1
