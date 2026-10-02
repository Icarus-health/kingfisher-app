"""Per-turn chat evidence and source withdrawal across saved conversations."""

from __future__ import annotations

from types import SimpleNamespace
import threading
import json

import pytest

from fastapi.testclient import TestClient

from icarus_memory.agent import Turn
from icarus_memory.agent import Agent
from icarus_memory.backends import MemoryBackend
from icarus_memory import conversation_memory
from icarus_memory.conversation_memory import find, stamp
from icarus_memory.episodes import CHAT_LOOKUP_TAG, EpisodeKind, digest_of
from icarus_memory.model import Provenance, SourceType
from icarus_memory.policy import ActionClass, Policy
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.source_search import search as search_sources
from icarus_memory.store import SelfModelStore
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_worker import run as run_working_memory
from tests.test_working_memory_worker import FakeLocalProvider
from tests.test_context_identity import core
from tests.test_source_answers_http import _api


class EchoAgent:
    def __init__(self, *, action=False, draft=False, local=False, fail_once=False):
        self.histories = []
        self.action = action
        self.draft = draft
        self.provider = SimpleNamespace(is_local=local, model="test")
        self.policy = Policy()
        self.executions = 0
        self.receipts = []
        self.fail_once = fail_once
        self.before_send = None

    def load_history(self, history):
        self.histories.append(history)

    def send(self, message, *, conversation_source_captured=False):
        self.receipts.append(conversation_source_captured)
        if self.before_send is not None:
            self.before_send(message)
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("synthetic failure")
        if self.action:
            args = {"value": message}
            approval = self.policy.request("test_action", args,
                self.policy.decide("test_action", ActionClass.OUTWARD, args),
                f"Aktion mit {message}")
            return Turn(reply=f"Prüfe Aktion: {message}", approvals=[approval])
        turn = Turn(reply=f"Antwort: {message}")
        if self.draft and message.startswith("Merke"):
            turn.memory_candidate_drafts = [{"subject_type": "person", "subject_label": "Kranz",
                "predicate": "works_on", "value": "Atlas", "statement": "Kranz arbeitet an Atlas."}]
        return turn

    def resolve(self, approval_id, granted, confirmation):
        if granted:
            self.policy.grant(approval_id, confirmation)
            self.executions += 1
            return Turn(reply="Aktion ausgeführt.", approval_outcome="approved")
        self.policy.reject(approval_id)
        return Turn(reply="Abgelehnt: vertraulicher Kontext Quasar123", approval_outcome="rejected")


def app_client(tmp_path, monkeypatch, agent=None):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    agent = agent or EchoAgent()
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"), agent=agent)
    return app, TestClient(app), agent


def close(app):
    for name in ("audit", "tasks", "workspace", "episodes", "proposals", "conversations", "claims", "regeln"):
        store = getattr(app.state, name, None)
        if callable(getattr(store, "close", None)):
            store.close()


def new_conversation(client):
    return client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]


def send(client, conversation_id, message, **extra):
    response = client.post(f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": message, "answer_mode": "chat", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_ordinary_turn_has_source_and_local_queue_once(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch, EchoAgent(local=True))
    try:
        queued = []
        app.state.scheduler = SimpleNamespace(request_working_memory=queued.append)
        app.state.settings.schedule.enabled = True
        app.state.settings.schedule.with_model = True
        conversation_id = new_conversation(client)
        observed_before_send = []
        def assert_source_already_captured(message):
            latest = app.state.conversations.messages(conversation_id)[-1]
            episode = find(app.state.episodes, conversation_id, latest.id)
            observed_before_send.append(bool(episode and episode.body == message
                and stamp(app.state.episodes, episode.id)))
        agent.before_send = assert_source_already_captured
        result = send(client, conversation_id, "Ich arbeite an Atlas.", conversation_source_captured=False)
        assert agent.receipts == [True]
        assert observed_before_send == [True]
        user = result["messages"][0]
        episode_id = user["metadata"]["context"]["source_links"][0]["episode_id"]
        episode = app.state.episodes.get(episode_id)
        assert episode.provenance.source_type is SourceType.CHAT
        assert episode.provenance.source_ref == f"conversation:{conversation_id}:message:{user['id']}"
        assert episode.provenance.verbatim == user["content"]
        assert episode.body == user["content"]
        assert episode.occurred_at == episode.provenance.captured_at
        assert queued == [episode_id]
        assert len(app.state.episodes.all_episodes()) == 1
        assert result["messages"][1]["content"] == "Antwort: Ich arbeite an Atlas."
        revision = app.state.claims.revision
        run_working_memory(app.state.episodes, FakeLocalProvider(), threading.RLock())
        assert WorkingMemoryStore(app.state.episodes).search("Atlas")["refs"]
        assert app.state.claims.revision == revision
    finally:
        close(app)


def test_withdrawn_early_turn_removes_derived_replies_and_history_after_restart(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch)
    conversation_id = new_conversation(client)
    first = send(client, conversation_id, "Mein Code ist Quasar123.")
    episode_id = first["messages"][0]["metadata"]["context"]["source_links"][0]["episode_id"]
    send(client, conversation_id, "Wiederhole meinen Code.")
    assert any("Quasar123" in item["content"] for item in agent.histories[-1])
    assert client.post(f"/api/v1/episodes/{episode_id}/ignore").status_code == 200
    hidden = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert all("Quasar123" not in item["content"] for item in hidden["messages"])
    assert "Quasar123" not in hidden["conversation"]["title"]
    listing = client.get("/api/v1/conversations").json()["conversations"]
    assert "Quasar123" not in str(listing)
    close(app)

    restarted, new_client, new_agent = app_client(tmp_path, monkeypatch)
    try:
        send(new_client, conversation_id, "Ein anderes Thema.")
        assert all("Quasar123" not in item["content"] for item in new_agent.histories[-1])
        assert "Wiederhole meinen Code" in str(new_agent.histories[-1])
        second = new_client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert all("Quasar123" not in item["content"] for item in second["messages"])
    finally:
        close(restarted)


def test_reopen_does_not_revive_old_reply_or_approval(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch, EchoAgent(action=True))
    try:
        conversation_id = new_conversation(client)
        result = send(client, conversation_id, "Quasar123")
        episode_id = result["messages"][0]["metadata"]["context"]["source_links"][0]["episode_id"]
        action = result["action_requests"][0]
        before = stamp(app.state.episodes, episode_id)
        assert client.post(f"/api/v1/episodes/{episode_id}/ignore").status_code == 200
        assert client.post(f"/api/v1/episodes/{episode_id}/reopen").status_code == 200
        assert stamp(app.state.episodes, episode_id) != before
        restored = client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert restored["messages"][0]["content"] == "Quasar123"
        assert restored["messages"][1]["content"] != "Prüfe Aktion: Quasar123"
        assert restored["action_requests"][0]["state"] == "expired"
        url = f"/api/v1/conversations/{conversation_id}/approvals/{action['id']}"
        assert client.post(url, json={"granted": True, "confirmation": action["confirmation_phrase"]}).status_code == 409
        assert client.post(f"/approvals/{action['id']}",
            json={"granted": True, "confirmation": action["confirmation_phrase"]}).status_code == 409
        assert agent.executions == 0
    finally:
        close(app)


def test_legacy_unstamped_approval_stays_invalid_after_reopen(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch, EchoAgent(action=True))
    try:
        conversation_id = new_conversation(client)
        user = app.state.conversations.add_message(conversation_id, "user", "Quasar123")
        ref = f"conversation:{conversation_id}:message:{user.id}"
        episode, _ = app.state.episodes.record(
            EpisodeKind.MESSAGE, "Gesprächsausschnitt für Gedächtnisvorschlag",
            f"{ref}\n\n{user.content}",
            Provenance(SourceType.CHAT, ref, captured_at=user.created_at,
                       verbatim=user.content), occurred_at=user.created_at)
        args = {"value": user.content}
        approval = agent.policy.request("test_action", args,
            agent.policy.decide("test_action", ActionClass.OUTWARD, args),
            f"Aktion mit {user.content}")
        app.state.conversations.add_message(conversation_id, "assistant", "Prüfe Aktion: Quasar123",
            metadata={"approvals": [approval.to_dict()]})
        before = client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert before["action_requests"][0]["state"] == "pending"
        assert client.post(f"/api/v1/episodes/{episode.id}/ignore").status_code == 200
        assert client.post(f"/api/v1/episodes/{episode.id}/reopen").status_code == 200
        after = client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert "Quasar123" not in after["messages"][1]["content"]
        assert after["action_requests"][0]["state"] == "expired"
        assert "Quasar123" not in after["action_requests"][0]["dry_run"]
        assert not client.get("/approvals").json()
        assert client.post(f"/approvals/{approval.id}", json={"granted": True,
            "confirmation": approval.confirmation_phrase}).status_code == 409
        assert agent.executions == 0
    finally:
        close(app)


def test_explicit_merke_reuses_source_and_retains_hints(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch, EchoAgent(draft=True))
    try:
        conversation_id = new_conversation(client)
        result = send(client, conversation_id, "Merke dir: Kranz arbeitet an Atlas.", conversation_source_captured=False)
        assert agent.receipts == [True]
        assert len(app.state.episodes.all_episodes()) == 1
        episode = find(app.state.episodes, conversation_id, result["messages"][0]["id"])
        assert episode is not None and episode.participants == ["Kranz"]
        assert result["messages"][1]["content"].startswith("Antwort:")
        assert result["memory_candidates"]
        assert app.state.claims.revision == 0
    finally:
        close(app)


def test_retry_reuses_only_the_stamped_conversation_source(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch, EchoAgent(fail_once=True))
    try:
        conversation_id = new_conversation(client)
        observed_before_send = []

        def assert_source_already_captured(message):
            latest = next(item for item in reversed(app.state.conversations.messages(conversation_id))
                if item.role == "user")
            episode = find(app.state.episodes, conversation_id, latest.id)
            observed_before_send.append(bool(episode and episode.body == message
                and stamp(app.state.episodes, episode.id)))

        agent.before_send = assert_source_already_captured
        failed = send(client, conversation_id, "Ich arbeite an Atlas.")
        error = failed["messages"][-1]
        assert error["status"] == "error"
        retried = client.post(
            f"/api/v1/conversations/{conversation_id}/messages/{error['id']}/retry"
        )
        assert retried.status_code == 201, retried.text
        assert agent.receipts == [True, True]
        assert observed_before_send == [True, True]
    finally:
        close(app)


def test_unusable_source_stamp_does_not_issue_capture_receipt(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch)
    try:
        monkeypatch.setattr(conversation_memory, "usable", lambda episodes, stamp: False)
        conversation_id = new_conversation(client)
        send(client, conversation_id, "Ich arbeite an Atlas.")
        assert agent.receipts == [False]
    finally:
        close(app)


def test_http_capture_is_present_before_real_agent_provider_call(tmp_path, monkeypatch):
    app, client, _ = app_client(tmp_path, monkeypatch)
    try:
        conversation_id = new_conversation(client)

        class CaptureCheckingProvider:
            name = "synthetic"
            model = "synthetic"
            is_local = False

            def __init__(self):
                self.system = None
                self.source_seen = False

            def complete(self, messages, tools):
                latest = next(item for item in reversed(app.state.conversations.messages(conversation_id))
                    if item.role == "user")
                source = find(app.state.episodes, conversation_id, latest.id)
                self.source_seen = bool(source and source.body == latest.content
                    and stamp(app.state.episodes, source.id))
                self.system = messages[0]["content"]
                return Reply(text="Synthetische Antwort.")

        provider = CaptureCheckingProvider()
        app.state.agent = Agent(
            store=app.state.store, policy=Policy(), audit=app.state.audit,
            tools={}, provider=provider, knowledge=app.state.claims,
            episodes=app.state.episodes,
            snapshot_provider=app.state.episodes.support_snapshot,
        )

        response = send(client, conversation_id, "Ich arbeite an Atlas.", conversation_source_captured=False)
        assert provider.source_seen is True
        assert "bereits als korrigierbare Gesprächsquelle aufgenommen" in provider.system
        assert "keine bestätigte Wissensaussage" in provider.system
        assert "automatisch eingeordnet wurde" in provider.system
        assert response["messages"][1]["content"] == "Synthetische Antwort."
    finally:
        close(app)


def test_other_conversation_never_receives_first_conversation(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch)
    try:
        first_id = new_conversation(client)
        first = send(client, first_id, "Quasar123 gehört nur hierher.")
        episode_id = first["messages"][0]["metadata"]["context"]["source_links"][0]["episode_id"]
        second_id = new_conversation(client)
        send(client, second_id, "Ein anderer Kontext.")
        assert "Quasar123" not in str(agent.histories[-1])
        assert client.post(f"/api/v1/episodes/{episode_id}/ignore").status_code == 200
        send(client, first_id, "Neuer Cloud-Aufruf.")
        assert "Quasar123" not in str(agent.histories[-1])
    finally:
        close(app)


def test_local_source_history_is_omitted_on_cloud_transition(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        conversation_id = new_conversation(client)
        send(client, conversation_id, "Mein lokaler Code ist Quasar123.")
        assert provider.calls and provider.is_local
        assert "Quasar123" in str(provider.calls[-1])
        provider.calls.clear()
        provider.is_local = False
        send(client, conversation_id, "Wie spät ist es?")
        assert provider.calls
        assert "Quasar123" not in str(provider.calls[-1])
    finally:
        close(app)


def test_memory_lookup_turn_is_kept_but_not_its_own_evidence(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        conversation_id = new_conversation(client)
        question = 'Was steht zu "Quasar123" in meinen Quellen?'
        response = client.post(f"/api/v1/conversations/{conversation_id}/messages",
            json={"message": question, "answer_mode": "auto"})
        assert response.status_code == 201
        user = response.json()["messages"][0]
        episode = find(app.state.episodes, conversation_id, user["id"])
        assert episode is not None and episode.body == question
        assert CHAT_LOOKUP_TAG in episode.tags
        assert not WorkingMemoryStore(app.state.episodes).pending(episode_ids=[episode.id])
        assert search_sources(app.state.episodes, "Quasar123")["ids"] == []
    finally:
        close(app)


def test_changed_source_head_cannot_relabel_old_user_text(tmp_path, monkeypatch):
    app, client, agent = app_client(tmp_path, monkeypatch)
    try:
        conversation_id = new_conversation(client)
        first = send(client, conversation_id, "Quasar123 bleibt privat.")
        user = first["messages"][0]
        original = find(app.state.episodes, conversation_id, user["id"])
        ref = original.provenance.source_ref
        replacement, _ = app.state.episodes.record(EpisodeKind.MESSAGE, "Gesprächsausschnitt",
            "Ein anderer Inhalt.", Provenance(SourceType.CHAT, ref,
                captured_at=original.occurred_at, verbatim="Ein anderer Inhalt."),
            occurred_at=original.occurred_at, source_key=ref)
        app.state.episodes.advance_source_head(ref, original.id, replacement.id)
        projected = client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert "Quasar123" not in str(projected)
        send(client, conversation_id, "Neue Frage.")
        assert "Quasar123" not in str(agent.histories[-1])
    finally:
        close(app)


@pytest.mark.parametrize("change", ["head", "same_id"])
def test_candidate_card_and_accept_close_when_source_changes(tmp_path, monkeypatch, change):
    app, client, _ = app_client(tmp_path, monkeypatch)
    try:
        conversation_id = new_conversation(client)
        posted = send(client, conversation_id, "Quasar123 gehört Kranz.")
        user = posted["messages"][0]
        proposed = client.post(f"/api/v1/conversations/{conversation_id}/memory-candidates",
            json={"source_message_id": user["id"], "subject_ref": "person:kranz",
                  "predicate": "code", "value": "Quasar123",
                  "statement": "Kranz nutzt Quasar123."})
        assert proposed.status_code == 201
        card = proposed.json()["memory_candidates"][0]
        assert card["candidate"]["evidence"][0]["quote"] == user["content"]
        source = find(app.state.episodes, conversation_id, user["id"])
        ref = source.provenance.source_ref
        if change == "head":
            replacement, _ = app.state.episodes.record(EpisodeKind.MESSAGE, "Gesprächsausschnitt",
                "Ein anderer Inhalt.", Provenance(SourceType.CHAT, ref,
                    captured_at=source.occurred_at, verbatim="Ein anderer Inhalt."),
                occurred_at=source.occurred_at, source_key=ref)
            app.state.episodes.advance_source_head(ref, source.id, replacement.id)
        else:
            # A damaged/migrated row may retain the same ID while its content
            # changes. The card must not show the old quote or allow approval.
            document = source.to_dict()
            document["body"] = "Ein anderer Inhalt."
            document["digest"] = digest_of(document["body"])
            document["provenance"]["verbatim"] = document["body"]
            with app.state.episodes._lock, app.state.episodes._conn:
                app.state.episodes._conn.execute(
                    "UPDATE episodes SET body=?, digest=?, document=? WHERE id=?",
                    (document["body"], document["digest"],
                     json.dumps(document, ensure_ascii=False), source.id),
                )
        payload = client.get(f"/api/v1/conversations/{conversation_id}").json()
        assert payload["memory_candidates"] == []
        assert "Quasar123" not in str(payload)
        assert client.post(f"/api/v1/conversations/{conversation_id}/memory-candidates/"
            f"{card['candidate']['id']}/accept", json={"replace_conflicts": False}).status_code == 409
    finally:
        close(app)
