"""HTTP regressions for pending contradictions against accepted memory."""

from __future__ import annotations

import json

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.proposals import Evidence
from tests.test_context_identity import AT, core
from tests.test_memory_clarification import api, conversation, post


QUESTION = "Welche Frist gilt für Aurora?"
OLD_DEADLINE = "22. September"
PENDING_DEADLINE = "26. September"
OLD_STATEMENT = f"Für Aurora gilt als Frist der {OLD_DEADLINE}."
PENDING_STATEMENT = f"Für Aurora gilt als Frist der {PENDING_DEADLINE}."
PENDING_SOURCE_TEXT = f"E-Mail: Die Frist für Aurora ist der {PENDING_DEADLINE}."


def _accept_deadline(core):
    _, _, _, _, accept = core
    return accept("project:aurora", OLD_STATEMENT)


def _propose_pending(app, text: str = PENDING_STATEMENT):
    source, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE,
        "Synthetic pending source",
        PENDING_SOURCE_TEXT,
        Provenance(source_type=SourceType.EMAIL, source_ref="synthetic:pending-aurora"),
        at=AT,
    )
    proposal, _ = app.state.knowledge_service.propose(
        subject_ref="project:aurora",
        predicate="observed_email",
        value=text,
        statement=text,
        evidence=[Evidence(source.id, PENDING_SOURCE_TEXT, source.digest)],
        rationale="Synthetic pending contradiction",
        at=AT,
    )
    return proposal, source


def _auto(client, conversation_id: str, question: str = QUESTION, **fields):
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": question, "answer_mode": "auto", **fields},
    )
    assert response.status_code == 201
    return response.json()["messages"][-1]


def _select_e1(messages, *, max_tokens, schema):
    assert max_tokens == 256
    assert schema["properties"]["evidence_ids"]["items"]["enum"] == ["E1"]
    return Reply(text=json.dumps({"version": 1, "kind": "evidence", "evidence_ids": ["E1"]}))


def _enable_e1(provider):
    def complete_json(messages, *, max_tokens, schema):
        provider.calls.append(messages)
        return _select_e1(messages, max_tokens=max_tokens, schema=schema)

    provider.complete_json = complete_json


def _assert_conflict(message):
    context = message["metadata"]["context"]
    contract = context["answer_contract"]
    assert contract["status"] == "conflict"
    assert contract["selected_assertion_ids"] == []
    assert context["items"] == []
    assert contract["model_called"] is False
    assert "Widerspruch" in json.dumps(message, ensure_ascii=False)
    assert OLD_DEADLINE not in json.dumps(message, ensure_ascii=False)
    assert PENDING_DEADLINE not in json.dumps(message, ensure_ascii=False)


def test_auto_memory_question_fails_closed_on_pending_conflict(core, api):
    _, provider, _, claims, _ = core
    accepted, _ = _accept_deadline(core)
    app, client = api
    _propose_pending(app)
    identifier = conversation(client)

    answer = _auto(client, identifier)

    _assert_conflict(answer)
    assert provider.calls == []
    assert claims.get(accepted.id).id == accepted.id
    assert app.state.knowledge_service.pending()


def test_saved_answer_is_reprojected_during_conflict_and_restored_after_rejection(core, api):
    agent, provider, *_ = core
    accepted, _ = _accept_deadline(core)
    app, client = api
    _enable_e1(provider)
    identifier = conversation(client)

    original = post(client, identifier, QUESTION)
    assert original["metadata"]["context"]["answer_contract"]["status"] == "evidence"
    assert OLD_DEADLINE in original["content"]
    stored_before = next(
        message for message in app.state.conversations.messages(identifier)
        if message.role == "assistant"
    )
    assert OLD_DEADLINE in stored_before.content

    proposal, _ = _propose_pending(app)
    projected = client.get(f"/api/v1/conversations/{identifier}")
    assert projected.status_code == 200
    projected_message = projected.json()["messages"][-1]
    _assert_conflict(projected_message)
    assert OLD_DEADLINE not in json.dumps(projected_message, ensure_ascii=False)
    assert OLD_DEADLINE in stored_before.content  # The audit record remains unchanged.

    listing = client.get("/api/v1/conversations")
    assert listing.status_code == 200
    summary = next(item for item in listing.json()["conversations"] if item["id"] == identifier)
    assert summary["preview"] == "Gedächtnisantwort — beim Öffnen erneut geprüft."

    app.state.knowledge_service.reject(proposal.id)
    restored = client.get(f"/api/v1/conversations/{identifier}")
    assert restored.status_code == 200
    restored_message = restored.json()["messages"][-1]
    assert restored_message["metadata"]["context"]["answer_contract"]["status"] == "evidence"
    assert OLD_DEADLINE in restored_message["content"]
    assert restored_message["metadata"]["context"]["answer_contract"]["selected_assertion_ids"] == [
        "claim:" + accepted.id
    ]
    assert provider.calls


def test_ignoring_pending_source_allows_fresh_evidence_answer_without_source_leak(core, api):
    _, provider, episodes, _, _ = core
    accepted, _ = _accept_deadline(core)
    app, client = api
    proposal, source = _propose_pending(app)
    episodes.ignore(source.id)
    _enable_e1(provider)
    identifier = conversation(client)

    answer = _auto(client, identifier, new_question=True)

    context = answer["metadata"]["context"]
    assert context["answer_contract"]["status"] == "evidence"
    assert context["answer_contract"]["selected_assertion_ids"] == ["claim:" + accepted.id]
    assert OLD_DEADLINE in answer["content"]
    assert PENDING_DEADLINE not in json.dumps(answer, ensure_ascii=False)
    assert PENDING_SOURCE_TEXT not in json.dumps(answer, ensure_ascii=False)
    assert provider.calls
    assert app.state.knowledge_service.pending()  # Ignoring the source never accepts the candidate.
    assert app.state.proposals.get(proposal.id).state.value == "pending"


def test_withdrawing_accepted_source_invalidates_saved_answer_without_old_text(core, api):
    _, provider, episodes, _, _ = core
    _, source = _accept_deadline(core)
    app, client = api
    _enable_e1(provider)
    identifier = conversation(client)
    original = post(client, identifier, QUESTION)
    assert OLD_DEADLINE in original["content"]

    episodes.ignore(source.id)
    reopened = client.get(f"/api/v1/conversations/{identifier}")
    assert reopened.status_code == 200
    message = reopened.json()["messages"][-1]
    context = message["metadata"]["context"]
    assert context["answer_contract"]["status"] == "invalidated"
    assert context["items"] == []
    assert context["answer_contract"]["selected_assertion_ids"] == []
    assert OLD_DEADLINE not in json.dumps(message, ensure_ascii=False)
    assert provider.calls


def test_conflict_turn_does_not_send_stale_deadline_in_later_chat_input(core, api):
    agent, provider, *_ = core
    _accept_deadline(core)
    app, client = api
    _enable_e1(provider)
    identifier = conversation(client)
    original = post(client, identifier, QUESTION)
    assert OLD_DEADLINE in original["content"]
    _propose_pending(app)

    conflict = _auto(client, identifier, new_question=True)
    _assert_conflict(conflict)
    provider.calls.clear()
    response = client.post(
        f"/api/v1/conversations/{identifier}/messages",
        json={"message": "How should I plan a quiet weekend?", "answer_mode": "chat"},
    )
    assert response.status_code == 201
    assert provider.calls
    assert OLD_DEADLINE not in json.dumps(provider.calls[-1], ensure_ascii=False)
