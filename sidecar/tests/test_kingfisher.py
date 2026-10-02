"""Produktverträge des lokalen Kingfisher-Slices."""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Turn
from icarus_memory.conversations import ConversationStore
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeKind
from icarus_memory.morning import compose, fixture
from icarus_memory.graph import person_id
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence
from icarus_memory.server import create_app


class StubAgent:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.history: list[dict[str, str]] = []

    def load_history(self, messages: list[dict[str, str]]) -> None:
        self.history = messages

    def send(self, message: str, *, conversation_source_captured: bool = False) -> Turn:
        if self.fail:
            raise RuntimeError("Modell nicht erreichbar")
        return Turn(
            reply=f"Antwort auf: {message}",
            context={
                "query": message,
                "generated_at": "2026-09-02T09:00:00+00:00",
                "items": [{
                    "assertion_id": "a-context",
                    "statement": "Kingfisher arbeitet lokal.",
                    "kind": "constraint",
                    "state": "current",
                    "reason": "Bindende Grenze",
                    "source_type": "user_stated",
                    "source_ref": "chat:test",
                    "evidence_at": "2026-09-02T09:00:00+00:00",
                    "confidence": None,
                }],
                "withheld_count": 0,
            },
        )


class MemoryIntentStub(StubAgent):
    """Modell-Doppel: liefert nur bei einer expliziten Merkbitte einen Entwurf."""

    def send(self, message: str, *, conversation_source_captured: bool = False) -> Turn:
        turn = super().send(message, conversation_source_captured=conversation_source_captured)
        if message.startswith("Merke dir:"):
            turn.memory_candidate_drafts.append({
                "subject_type": "person",
                "subject_label": "Dr. Kranz",
                "predicate": "project_role",
                "value": "leitet Projekt Atlas",
                "statement": "Dr. Kranz leitet Projekt Atlas.",
                "rationale": "Als Vorschlag aus deiner ausdrücklich genannten Nachricht.",
            })
        return turn


def test_conversation_migration_and_restart(tmp_path) -> None:
    path = tmp_path / "conversations.sqlite3"
    store = ConversationStore(path)
    conversation = store.create()
    store.add_message(conversation.id, "user", "Was ist heute wichtig?")
    store.add_message(conversation.id, "assistant", "Zwei Punkte.")
    store.close()

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1

    reopened = ConversationStore(path)
    assert reopened.get(conversation.id).title == "Was ist heute wichtig?"
    assert [message.content for message in reopened.messages(conversation.id)] == [
        "Was ist heute wichtig?", "Zwei Punkte."
    ]
    reopened.close()


def test_known_unversioned_conversation_schema_is_upgraded(tmp_path) -> None:
    path = tmp_path / "conversations.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, "
            "conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, "
            "role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, "
            "created_at TEXT NOT NULL, metadata TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO conversations VALUES ('legacy', 'Alt', "
            "'2026-01-01T10:00:00+00:00', '2026-01-01T10:00:00+00:00')"
        )
    store = ConversationStore(path)
    assert store.get("legacy").title == "Alt"
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    store.close()


def test_failed_write_rolls_back_for_next_transaction(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    try:
        store.add_message("missing", "user", "wird verworfen")
    except KeyError:
        pass
    conversation = store.create("Danach")
    store.add_message(conversation.id, "user", "funktioniert")
    assert [message.content for message in store.messages(conversation.id)] == ["funktioniert"]
    store.close()


def test_parallel_connections_keep_all_messages(tmp_path) -> None:
    path = tmp_path / "conversations.sqlite3"
    first = ConversationStore(path)
    conversation = first.create("Parallel")
    second = ConversationStore(path)
    barrier = threading.Barrier(2)

    def write(store: ConversationStore, prefix: str) -> None:
        barrier.wait()
        for index in range(10):
            store.add_message(conversation.id, "user", f"{prefix}-{index}")

    threads = [
        threading.Thread(target=write, args=(first, "a")),
        threading.Thread(target=write, args=(second, "b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(first.messages(conversation.id)) == 20
    first.close()
    second.close()


def test_sqlite_fixture_is_deterministic(tmp_path, monkeypatch) -> None:
    path = tmp_path / "morning-fixture.sqlite3"
    monkeypatch.setenv("KINGFISHER_FIXTURE_DB", str(path))
    first = fixture(datetime(2026, 9, 1, tzinfo=timezone.utc))
    second = fixture(datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert first == second
    assert first["generated_at"] == "2025-05-20T07:32:00+02:00"
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM morning_fixture").fetchone()[0] == len(first)


def test_morning_deduplicates_and_sorts() -> None:
    current = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    dashboard = {
        "briefing": {"punkte": [
            {"quelle": "tasks", "ref": "t-1", "text": "Freigabe"},
            {"quelle": "tasks", "ref": "t-1", "text": "Freigabe"},
        ]},
        "calendar": {"items": [
            {"uid": "later", "title": "Später", "start": "2026-09-01T15:00:00+00:00"},
            {"uid": "early", "title": "Früher", "start": "2026-09-01T09:00:00+00:00"},
        ]},
        "mail": {"items": []}, "tasks": {}, "episodes": {}, "proposals": {},
    }
    result = compose(dashboard, now=current, target=date(2026, 9, 1))
    assert result["relevance_count"] == 1
    assert [item["title"] for item in result["later_today"]] == ["Früher", "Später"]
    assert result["needs_you"][0]["id"] == compose(
        dashboard, now=current, target=date(2026, 9, 1)
    )["needs_you"][0]["id"]


def _leeres_dashboard() -> dict:
    return {"briefing": {"punkte": []}, "calendar": {"items": []},
            "mail": {"items": []}, "tasks": {}, "episodes": {}, "proposals": {}}


@pytest.mark.parametrize("stunde,erwartet", [(8, "Guten Morgen."), (14, "Guten Tag.")])
def test_gruss_ohne_namen_ist_neutral(monkeypatch, stunde, erwartet) -> None:
    monkeypatch.delenv("KINGFISHER_USER_NAME", raising=False)
    current = datetime(2026, 9, 1, stunde, 0, tzinfo=timezone.utc)
    result = compose(_leeres_dashboard(), now=current, target=date(2026, 9, 1))
    assert result["greeting"] == erwartet
    assert "," not in result["greeting"] and " ." not in result["greeting"]


def test_gruss_leerer_oder_blanker_name_ist_neutral(monkeypatch) -> None:
    monkeypatch.setenv("KINGFISHER_USER_NAME", "   ")
    current = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    result = compose(_leeres_dashboard(), now=current, target=date(2026, 9, 1))
    assert result["greeting"] == "Guten Morgen."


def test_gruss_mit_gesetztem_namen(monkeypatch) -> None:
    monkeypatch.setenv("KINGFISHER_USER_NAME", "Anna")
    current = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    result = compose(_leeres_dashboard(), now=current, target=date(2026, 9, 1))
    assert result["greeting"] == "Guten Morgen, Anna."


def test_morning_reports_partial_failures_and_day_boundaries() -> None:
    current = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    dashboard = {
        "briefing": {"punkte": []},
        "tasks": {"error": "Aufgaben fehlen"},
        "mail": {"items": [], "error": "Mail fehlt"},
        "calendar": {"items": [
            {"uid": "today", "title": "Heute", "start": "2026-09-01T23:59:00+00:00"},
            {"uid": "tomorrow", "title": "Morgen", "start": "2026-09-02T00:00:00+00:00"},
        ]},
        "episodes": {}, "proposals": {},
    }
    result = compose(dashboard, now=current, target=date(2026, 9, 1))
    assert [item["title"] for item in result["later_today"]] == ["Heute"]
    assert result["partial_failures"] == [
        {"section": "tasks", "message": "Aufgaben fehlen"},
        {"section": "mail", "message": "Mail fehlt"},
    ]


def test_imported_note_is_visible_as_a_source_without_becoming_knowledge(
    tmp_path, monkeypatch
) -> None:
    """Ein lokaler Text wird als Quelle sichtbar, aber nicht als Tatsache.

    Das ist die erste alltagstaugliche Kette: explizit freigegebener Ordner →
    Episode mit Herkunft → Morning-Hinweis. Weder Inhalt noch eine abgeleitete
    Behauptung dürfen dabei still in den Bestand rutschen.
    """
    vault = tmp_path / "Notizen"
    vault.mkdir()
    (vault / "heute.md").write_text(
        "Dr. Kranz sagt: Das Projekt ist fertig.", encoding="utf-8"
    )
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ICARUS_FILE_ROOTS", str(vault))
    client = TestClient(create_app(SelfModelStore(MemoryBackend(), subject_id="test")))

    imported = client.post("/ingest", json={"path": str(vault), "adapter": "markdown"})
    assert imported.status_code == 200
    assert imported.json()["recorded"] == 1

    morning = client.get("/api/v1/morning-briefing").json()
    assert any(item["title"] == "Neue Hinweise" for item in morning["happening_now"])
    assert "Projekt ist fertig" not in str(morning)
    assert client.get("/api/v1/memory/candidates").json() == []
    assert client.app.state.claims.all_claims() == []


def test_morning_marks_memory_clarification_as_an_explicit_decision(
    tmp_path, monkeypatch
) -> None:
    """Widersprüche zählen als Arbeit, aber ihr Inhalt bleibt unveröffentlicht."""
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"))
    episode, _ = app.state.episodes.record(
        kind=EpisodeKind.DOCUMENT,
        title="Besprechungsnotiz",
        body="Dr. Kranz leitet das Projekt Atlas.",
        provenance=Provenance(source_type=SourceType.DOCUMENT, source_ref="note:kranz"),
    )
    service = app.state.knowledge_service
    first, _ = service.propose(
        subject_ref=person_id("Dr. Kranz"),
        predicate="rolle",
        value="leitet Projekt Atlas",
        statement="Dr. Kranz leitet das Projekt Atlas.",
        rationale="Wörtlich belegt.",
        evidence=[Evidence(episode.id, "Dr. Kranz leitet das Projekt Atlas.", episode.digest)],
    )
    service.accept(first.id, supersedes=[])
    follow_up, _ = app.state.episodes.record(
        kind=EpisodeKind.DOCUMENT,
        title="Korrektur",
        body="Dr. Kranz leitet das Projekt Atlas nicht mehr.",
        provenance=Provenance(source_type=SourceType.DOCUMENT, source_ref="note:korrektur"),
    )
    service.propose(
        subject_ref=person_id("Dr. Kranz"),
        predicate="rolle",
        value="ist nicht mehr Projektleitung",
        statement="Dr. Kranz leitet das Projekt Atlas nicht mehr.",
        rationale="Wörtlich belegt.",
        evidence=[Evidence(
            follow_up.id,
            "Dr. Kranz leitet das Projekt Atlas nicht mehr.",
            follow_up.digest,
        )],
    )

    client = TestClient(app)
    dashboard = client.get("/dashboard").json()
    assert len(dashboard["knowledge"]["clarifications"]) == 1
    assert "Kranz" not in str(dashboard["knowledge"])

    morning = client.get("/api/v1/morning-briefing").json()
    clarification = next(item for item in morning["needs_you"] if item["source"] == "knowledge")
    assert clarification["title"] == "Gedächtnis klären"
    assert clarification["source_ref"] == dashboard["knowledge"]["clarifications"][0]["id"]
    assert "Kranz" not in str(clarification)


def test_versioned_api_persists_model_turn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KINGFISHER_FIXTURE", "morning")
    agent = StubAgent()
    from icarus_memory.context import build_context_packet
    from icarus_memory.model import Kind, Sensitivity
    store = SelfModelStore(MemoryBackend(), subject_id="test")
    store.record("Kingfisher arbeitet lokal.", Kind.CONSTRAINT,
                 Provenance(SourceType.USER_STATED, source_ref="chat:test"))
    original_send = agent.send
    def send_with_authoritative_context(message, *, conversation_source_captured=False):
        turn = original_send(message, conversation_source_captured=conversation_source_captured)
        turn.context = build_context_packet(store, message, Sensitivity.NORMAL)[0].to_dict()
        return turn
    monkeypatch.setattr(agent, "send", send_with_authoritative_context)
    app = create_app(store, agent=agent)
    client = TestClient(app)

    briefing = client.get("/api/v1/morning-briefing?date=2025-05-20")
    assert briefing.status_code == 200
    assert briefing.json()["relevance_count"] == 5
    # Ein Test-Stub kann antworten, ist aber kein eingerichteter Provider.
    # Die sichtbare Oberfläche darf den Composer deshalb nicht freischalten.
    assert client.get("/api/v1/status").json() == {"chat": False}

    created = client.post("/api/v1/conversations", json={"title": "Neues Gespräch"})
    conversation_id = created.json()["conversation"]["id"]
    sent = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "Was ist heute wichtig?"},
    )
    assert sent.status_code == 201
    assert [message["status"] for message in sent.json()["messages"]] == ["complete", "complete"]
    assert sent.json()["context"]["items"][0]["statement"] == "Kingfisher arbeitet lokal."

    reloaded = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert reloaded == sent.json()
    assert agent.history == []
    assert client.get("/api/v1/conversations/latest").json()["conversation"]["id"] == conversation_id


def test_conversation_history_is_local_ordered_and_contains_only_a_preview(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"), agent=StubAgent())
    older = app.state.conversations.create("Älteres Gespräch", at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    app.state.conversations.add_message(
        older.id, "user", "Die alte Frage mit einem langen, aber lokalen Verlauf.",
        at=datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
    )
    newer = app.state.conversations.create("Neueres Gespräch", at=datetime(2026, 9, 2, tzinfo=timezone.utc))
    app.state.conversations.add_message(
        newer.id, "assistant", "Die letzte Antwort.", at=datetime(2026, 9, 2, 11, tzinfo=timezone.utc),
    )

    history = TestClient(app).get("/api/v1/conversations").json()["conversations"]
    assert [item["id"] for item in history] == [newer.id, older.id]
    assert history[0]["preview"] == "Die letzte Antwort."
    assert history[0]["message_count"] == 1
    assert "messages" not in history[0]


def test_versioned_task_views_follow_local_task_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"))
    client = TestClient(app)
    mine = client.post("/api/v1/tasks", json={"title": "Eigene Aufgabe"}).json()
    waiting = app.state.tasks.add("Warte auf Rückmeldung", Provenance(source_type=SourceType.USER_STATED))
    app.state.tasks.warten_auf(waiting.id, "Frau Becker")
    done = app.state.tasks.add("Erledigte Aufgabe", Provenance(source_type=SourceType.USER_STATED))
    app.state.tasks.complete(done.id)

    assert [item["id"] for item in client.get("/api/v1/tasks?view=mine").json()["tasks"]] == [mine["id"]]
    assert [item["id"] for item in client.get("/api/v1/tasks?view=waiting").json()["tasks"]] == [waiting.id]
    assert [item["id"] for item in client.get("/api/v1/tasks?view=done").json()["tasks"]] == [done.id]
    assert client.post(f"/api/v1/tasks/{mine['id']}/done").status_code == 200
    assert client.get("/api/v1/tasks?view=mine").json()["tasks"] == []
    reopened = client.post(f"/api/v1/tasks/{mine['id']}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert reopened.json()["done_at"] is None
    assert [item["id"] for item in client.get("/api/v1/tasks?view=mine").json()["tasks"]] == [mine["id"]]
    assert client.post("/api/v1/tasks/nonexistent/reopen").status_code == 404
    assert client.post(f"/api/v1/tasks/{mine['id']}/warten", json={"name": "Testperson"}).status_code == 200
    assert mine['id'] in [item['id'] for item in client.get('/api/v1/tasks?view=waiting').json()['tasks']]
    assert client.post(f"/api/v1/tasks/{mine['id']}/zurueckholen").status_code == 200
    assert mine['id'] in [item['id'] for item in client.get('/api/v1/tasks?view=mine').json()['tasks']]


def test_versioned_message_list_exposes_only_local_inbox_previews(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"))

    class Mail:
        def inbox(self, limit: int = 10):
            assert limit == 30
            return [Message(
                uid="mail-1", subject="Vertrag", sender="Frau Becker",
                date=datetime(2026, 9, 4, 10, tzinfo=timezone.utc),
                preview="Bitte den Entwurf prüfen.", unread=True,
                body="Dieser Volltext darf nicht in die Listenantwort.",
                reply_to="vertraulich@example.test", account_label="Arbeit",
            )]

    app.state.mail = Mail()
    payload = TestClient(app).get("/api/v1/messages").json()
    assert payload["messages"][0] == {
        "id": "mail-1", "subject": "Vertrag", "sender": "Frau Becker",
        "date": payload["messages"][0]["date"], "preview": "Bitte den Entwurf prüfen.",
        "unread": True, "source": "Arbeit", "account_id": "",
        "category": "inbox", "filter_reason": "not_flagged",
    }
    assert datetime.fromisoformat(payload["messages"][0]["date"]).astimezone(timezone.utc) == datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
    assert "Volltext" not in str(payload)
    assert "vertraulich@example.test" not in str(payload)


def test_versioned_message_list_distinguishes_missing_and_unavailable_mail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"))
    client = TestClient(app)

    assert client.get("/api/v1/messages").json()["partial_failure"]["code"] == "not_configured"

    class UnavailableMail:
        def inbox(self, limit: int = 10):
            raise RuntimeError("network details must stay local")

    app.state.mail = UnavailableMail()
    assert client.get("/api/v1/messages").json()["partial_failure"]["code"] == "unavailable"


def test_model_error_stays_visible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    client = TestClient(create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=StubAgent(fail=True)
    ))
    created = client.post("/api/v1/conversations", json={}).json()
    result = client.post(
        f"/api/v1/conversations/{created['conversation']['id']}/messages",
        json={"message": "Bitte antworten"},
    ).json()
    assert result["messages"][-1]["status"] == "error"
    assert "nicht erstellt" in result["messages"][-1]["content"]


def test_status_only_enables_configured_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    agent = StubAgent()
    agent.provider = object()  # type: ignore[attr-defined] - Testdoppel
    client = TestClient(create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=agent
    ))
    assert client.get("/api/v1/status").json() == {"chat": True}


def test_retry_reuses_persisted_question_without_duplication(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    agent = StubAgent(fail=True)
    client = TestClient(create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=agent
    ))
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    failed = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "Bitte antworten"},
    ).json()
    failed_id = failed["messages"][-1]["id"]
    agent.fail = False

    retried = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{failed_id}/retry"
    )

    assert retried.status_code == 201
    messages = retried.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant", "assistant"]
    assert [message["content"] for message in messages].count("Bitte antworten") == 1
    assert messages[-1]["status"] == "complete"
    assert messages[-1]["metadata"]["retry_of"] == failed_id


def test_conversation_memory_candidate_needs_explicit_route_and_persists_source(
    tmp_path, monkeypatch
) -> None:
    """Ein Chat wird nie nebenbei Wissen; der separate Vorschlag bleibt belegbar."""
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=StubAgent()
    )
    client = TestClient(app)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    chat = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "Dr. Kranz leitet Projekt Atlas."},
    ).json()
    source_id = chat["messages"][0]["id"]

    # Ordinary chat is a source, but it does not create a candidate or claim.
    ordinary_sources = app.state.episodes.pending()
    assert len(ordinary_sources) == 1
    assert ordinary_sources[0].kind is EpisodeKind.MESSAGE
    assert ordinary_sources[0].provenance.source_ref == f"conversation:{conversation_id}:message:{source_id}"
    assert app.state.knowledge_service.pending() == []
    assert app.state.claims.all_claims() == []

    proposal_body = {
        "source_message_id": source_id,
        "subject_ref": person_id("Dr. Kranz"),
        "predicate": "project_role",
        "value": "leitet Projekt Atlas",
        "statement": "Dr. Kranz leitet Projekt Atlas.",
        "scope_ref": "project:atlas",
    }
    proposed = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates", json=proposal_body
    )

    assert proposed.status_code == 201
    payload = proposed.json()
    card = payload["memory_candidates"][0]
    assert card["candidate"]["state"] == "pending"
    assert card["candidate"]["evidence"][0]["quote"] == "Dr. Kranz leitet Projekt Atlas."
    assert app.state.claims.all_claims() == []
    episode = app.state.episodes.get(card["candidate"]["evidence"][0]["episode_id"])
    assert episode.id == ordinary_sources[0].id
    assert episode.provenance.source_type is SourceType.CHAT
    assert episode.provenance.source_ref == f"conversation:{conversation_id}:message:{source_id}"
    assert episode.provenance.verbatim == "Dr. Kranz leitet Projekt Atlas."

    rejected = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{card['candidate']['id']}/reject"
    )
    assert rejected.status_code == 200
    assert rejected.json()["memory_candidates"][0]["candidate"]["state"] == "rejected"
    assert app.state.claims.all_claims() == []

    reproposed = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates", json=proposal_body
    )
    assert reproposed.status_code == 201
    renewed_card = reproposed.json()["memory_candidates"][-1]
    accepted = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{renewed_card['candidate']['id']}/accept",
        json={"replace_conflicts": False},
    )
    assert accepted.status_code == 200
    assert accepted.json()["memory_candidates"][-1]["candidate"]["state"] == "accepted"
    assert len(app.state.claims.all_claims()) == 1


def test_conversation_memory_conflict_requires_visible_replacement(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=StubAgent()
    )
    client = TestClient(app)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]

    def propose_from_chat(text: str, value: str, statement: str) -> str:
        conversation = client.post(
            f"/api/v1/conversations/{conversation_id}/messages", json={"message": text}
        ).json()
        source_id = conversation["messages"][-2]["id"]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/memory-candidates",
            json={
                "source_message_id": source_id,
                "subject_ref": person_id("Dr. Kranz"),
                "predicate": "project_role",
                "value": value,
                "statement": statement,
                "scope_ref": "project:atlas",
            },
        )
        assert response.status_code == 201
        return response.json()["memory_candidates"][-1]["candidate"]["id"]

    first = propose_from_chat(
        "Dr. Kranz leitet Projekt Atlas.", "leitet Projekt Atlas", "Dr. Kranz leitet Projekt Atlas."
    )
    assert client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{first}/accept",
        json={"replace_conflicts": False},
    ).status_code == 200

    second = propose_from_chat(
        "Dr. Kranz leitet Projekt Atlas nicht mehr.",
        "leitet Projekt Atlas nicht mehr",
        "Dr. Kranz leitet Projekt Atlas nicht mehr.",
    )
    unresolved = client.get(f"/api/v1/conversations/{conversation_id}").json()
    second_card = next(
        card for card in unresolved["memory_candidates"] if card["candidate"]["id"] == second
    )
    assert second_card["conflicts"][0]["statement"] == "Dr. Kranz leitet Projekt Atlas."

    blocked = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{second}/accept",
        json={"replace_conflicts": False},
    )
    assert blocked.status_code == 409
    replaced = client.post(
        f"/api/v1/conversations/{conversation_id}/memory-candidates/{second}/accept",
        json={"replace_conflicts": True},
    )
    assert replaced.status_code == 200
    assert next(
        card for card in replaced.json()["memory_candidates"] if card["candidate"]["id"] == second
    )["candidate"]["state"] == "accepted"
    assert len(app.state.claims.by_subject(person_id("Dr. Kranz"))) == 1


def test_only_explicit_memory_request_turns_model_draft_into_candidate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), agent=MemoryIntentStub()
    )
    client = TestClient(app)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]

    ordinary = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "Dr. Kranz leitet Projekt Atlas."},
    )
    assert ordinary.status_code == 201
    assert ordinary.json()["memory_candidates"] == []
    ordinary_source_id = ordinary.json()["messages"][0]["metadata"]["context"]["source_links"][0]["episode_id"]
    assert [episode.id for episode in app.state.episodes.pending()] == [ordinary_source_id]
    assert app.state.claims.all_claims() == []

    explicit = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": "Merke dir: Dr. Kranz leitet Projekt Atlas."},
    )
    assert explicit.status_code == 201
    card = explicit.json()["memory_candidates"][0]
    assert card["candidate"]["state"] == "pending"
    assert card["candidate"]["subject_ref"] == person_id("Dr. Kranz")
    assert card["candidate"]["evidence"][0]["quote"] == "Merke dir: Dr. Kranz leitet Projekt Atlas."
    episode = app.state.episodes.get(card["candidate"]["evidence"][0]["episode_id"])
    assert episode.id != ordinary_source_id
    assert {item.id for item in app.state.episodes.pending()} == {ordinary_source_id, episode.id}
    assert episode.participants == ["Dr. Kranz"]
    graph_data = client.get("/api/v1/memory/graph").json()
    assert any(
        node["id"] == person_id("Dr. Kranz") and node["label"] == "Dr. Kranz"
        for node in graph_data["nodes"]
    )
    assert app.state.claims.all_claims() == []


def test_morning_reports_failed_read_sections_without_internal_details():
    current = datetime(2026, 9, 1, 8, tzinfo=timezone.utc)
    sections = ('projects', 'decisions', 'goals', 'episodes', 'proposals', 'knowledge', 'memory')
    dashboard = {name: {'error': 'private implementation detail'} for name in sections}
    dashboard['briefing_error'] = 'private implementation detail'
    result = compose(dashboard, now=current, target=current.date())
    assert {item['section'] for item in result['partial_failures']} == {*sections, 'briefing'}
    assert all('private implementation detail' not in item['message'] for item in result['partial_failures'])
