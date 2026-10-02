"""Joined, local-only pilot flow across mail, tasks, calendar and approval."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Turn
from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import sync_account
from icarus_memory.policy import ActionClass, Policy
from icarus_memory.proposals import ProposalKind
from icarus_memory.server import create_app
from tests.test_conversation_retraction import _close_app


class Mailbox:
    """One synthetic message; no IMAP connection or credentials."""

    def __init__(self):
        self.item = Message(
            uid="pilot-1",
            subject="Atlas: Angebot bis Freitag",
            sender="anna@example.invalid",
            date=datetime(2026, 9, 28, 8, tzinfo=timezone.utc),
            preview="Bitte prüfe das Angebot für den Atlas-Termin.",
            unread=True,
            body="Bitte prüfe das Angebot für den Atlas-Termin bis Freitag.",
        )

    def pending_uids(self, after=None, limit=50):
        return ["pilot-1"] if after is None else []

    def message(self, uid):
        assert uid == self.item.uid
        return self.item


class Calendar:
    """Fixed synthetic event for both calendar APIs and question answers."""

    def __init__(self):
        start = datetime.now(timezone.utc) + timedelta(hours=2)
        self.event = Event("atlas-review", "Atlas-Angebot prüfen", start, start + timedelta(hours=1))

    def events(self, **kwargs):
        return [self.event]

    def read(self):
        now = datetime.now(timezone.utc)
        return {
            "enabled": True,
            "selected": ["pilot-calendar"],
            "status": "granted",
            "synced_at": now.isoformat(),
            "range_from": (now - timedelta(minutes=1)).isoformat(),
            "range_to": (now + timedelta(days=8)).isoformat(),
            "events": [{
                "uid": "atlas-review",
                "source_id": "pilot-calendar",
                "summary": "Atlas-Angebot prüfen",
                "start": self.event.start.isoformat(),
                "end": self.event.end.isoformat(),
                "source_label": "Synthetischer Pilotkalender",
                "all_day": False,
            }],
        }


class CalendarOnlyProvider:
    """Selects the real local-calendar answer path and forbids inference."""

    is_local = True
    model = "synthetic-calendar-only"

    def complete(self, messages, tools):
        raise AssertionError("The deterministic calendar question must not call a model")


class LocalPilotAgent:
    """Use the real Agent for read-only questions and a counting action sink."""

    def __init__(self, delegate):
        self.delegate = delegate
        self.policy = Policy()
        self.executions = 0

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def load_history(self, history):
        self.delegate.load_history(history)

    def send(self, message, *, conversation_source_captured=False):
        if message != "prepare the isolated pilot action":
            return self.delegate.send(message, conversation_source_captured=conversation_source_captured)
        args = {"to": "pilot@example.invalid", "body": "Synthetic action only"}
        action = self.policy.request(
            "pilot_action", args,
            self.policy.decide("pilot_action", ActionClass.OUTWARD, args),
            "Synthetic action to pilot@example.invalid; no external send.",
        )
        return Turn(reply="Review the synthetic action.", approvals=[action])

    def resolve(self, approval_id, granted, confirmation):
        if not granted:
            self.policy.reject(approval_id)
            return Turn(reply="Rejected. Nothing executed.", approval_outcome="rejected")
        self.policy.grant(approval_id, confirmation)
        self.executions += 1
        return Turn(reply="Synthetic action completed.", approval_outcome="approved")


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="pilot"))
    calendar = Calendar()
    app.state.calendar = CalendarCollection([NamedCalendar("pilot-calendar", "Pilot", calendar)])
    # The real Agent's calendar question path consumes the selected local
    # snapshot; the read-only calendar page/preparation uses CalendarCollection.
    app.state.mac_calendar = calendar
    app.state.agent._provider = CalendarOnlyProvider()
    app.state.agent = LocalPilotAgent(app.state.agent)
    return app


def test_synthetic_core_flow_survives_restart_without_duplicate_effects(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    mailbox = Mailbox()

    first_sync = sync_account(app.state.episodes, "pilot-account", mailbox,
                              claims=app.state.claims)
    assert first_sync == {"recorded": 1, "duplicates": 0, "cursor": "pilot-1"}
    # Resolve the captured source by its account-scoped provenance.
    episode = next(item for item in app.state.episodes.all_episodes()
                   if item.provenance.source_type.value == "email")
    assert episode.provenance.source_ref.endswith("pilot-1")
    assert episode.body == mailbox.item.body

    repeated_sync = sync_account(app.state.episodes, "pilot-account", mailbox,
                                 claims=app.state.claims)
    assert repeated_sync["recorded"] == 0
    assert repeated_sync["duplicates"] == 0
    assert len([item for item in app.state.episodes.all_episodes()
                if item.provenance.source_ref.endswith("pilot-1")]) == 1

    project = client.post("/api/v1/projects", json={"name": "Atlas"}).json()
    candidate_count = app.state.proposals.record_task_analysis(
        episode.id, episode.digest,
        [{"title": "Review Atlas offer", "quote": "prüfe das Angebot"}],
        proposed_by="synthetic-pilot-extractor",
    )
    assert candidate_count == 1
    assert app.state.proposals.record_task_analysis(
        episode.id, episode.digest,
        [{"title": "Review Atlas offer", "quote": "prüfe das Angebot"}],
        proposed_by="synthetic-pilot-extractor",
    ) == 0
    # Importing the same message again must not mint a second candidate.
    assert sync_account(app.state.episodes, "pilot-account", mailbox,
                        claims=app.state.claims)["recorded"] == 0
    assert len(app.state.proposals.pending(ProposalKind.TASK)) == 1

    calendar_payload = client.get("/api/v1/calendar").json()
    assert calendar_payload["items"][0]["uid"] == "pilot-calendar:atlas-review"
    briefing = client.get("/api/v1/morning-briefing").json()
    candidate_item = next(item for item in briefing["needs_you"]
                          if item["source"] == "zusage")
    assert candidate_item["title"] == "Review Atlas offer"
    accepted = client.post(f"/api/v1/task-candidates/{candidate_item['source_ref']}/accept",
                           json={"title": candidate_item["title"], "project_id": project["id"]})
    assert accepted.status_code == 200
    task_id = accepted.json()["id"]
    assert accepted.json()["provenance"]["source_ref"] == f"episode:{episode.id}"
    duplicate_accept = client.post(
        f"/api/v1/task-candidates/{candidate_item['source_ref']}/accept",
        json={"title": candidate_item["title"], "project_id": project["id"]},
    )
    assert duplicate_accept.status_code == 200
    assert duplicate_accept.json()["id"] == task_id
    assert len(client.get("/api/v1/tasks").json()["tasks"]) == 1

    prepared = client.get("/api/v1/calendar/preparation", params={
        "uid": "pilot-calendar:atlas-review", "project_id": project["id"],
    })
    assert prepared.status_code == 200
    assert [task["id"] for task in prepared.json()["tasks"]] == [task_id]

    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    mail_question = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": 'Was steht zu "Atlas-Termin" in meinen Quellen?',
              "answer_mode": "memory_evidence"},
    )
    assert mail_question.status_code == 201
    mail_answer = mail_question.json()["messages"][-1]
    assert mailbox.item.body in mail_answer["content"]
    assert mail_answer["metadata"]["context"]["answer_contract"]["status"] == "source_report"

    question = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "Was steht als Nächstes an?", "answer_mode": "chat"},
    )
    assert question.status_code == 201
    assert "Atlas\\-Angebot prüfen" in question.json()["messages"][-1]["content"]
    assert question.json()["context"]["answer_mode"] == "calendar_data"

    action_turn = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "prepare the isolated pilot action", "answer_mode": "chat"},
    ).json()
    action = action_turn["action_requests"][0]
    approval_url = f"/api/v1/conversations/{conversation_id}/approvals/{action['id']}"
    assert client.post(approval_url, json={"granted": True, "confirmation": "wrong"}).status_code == 409
    assert app.state.agent.executions == 0
    approved = client.post(approval_url, json={
        "granted": True, "confirmation": action["confirmation_phrase"],
    })
    assert approved.status_code == 200
    assert approved.json()["action_requests"][0]["state"] == "approved"
    assert app.state.agent.executions == 1
    assert client.post(approval_url, json={
        "granted": True, "confirmation": action["confirmation_phrase"],
    }).status_code == 409
    assert app.state.agent.executions == 1
    client.close()
    _close_app(app)

    # Fresh app and SQLite connections prove persisted source, cursor, task,
    # briefing outcome, conversation answer and completed approval record.
    restarted = _app(tmp_path, monkeypatch)
    with TestClient(restarted) as after:
        assert restarted.state.episodes.mail_cursor("pilot-account") == "pilot-1"
        mail_sources = [item for item in restarted.state.episodes.all_episodes()
                        if item.provenance.source_type.value == "email"]
        assert len(mail_sources) == 1
        assert mail_sources[0].id == episode.id
        assert [task["id"] for task in after.get("/api/v1/tasks").json()["tasks"]] == [task_id]
        assert after.get(f"/api/v1/conversations/{conversation_id}").json()["action_requests"][0]["state"] == "approved"
        reopened = after.get(f"/api/v1/conversations/{conversation_id}").json()
        assert any("Atlas\\-Angebot prüfen" in message["content"]
                   for message in reopened["messages"])
        assert after.post(approval_url, json={
            "granted": True, "confirmation": action["confirmation_phrase"],
        }).status_code == 409
    _close_app(restarted)
