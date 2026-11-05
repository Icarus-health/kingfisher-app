"""Responsibility decisions on synthetic tasks and the actual guarded route."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskChangedError, TaskRequestConflict, TaskStore

SOURCE = Provenance(source_type=SourceType.EMAIL, source_ref="synthetic:calibration-mail",
                    verbatim="Synthetic source report, not a confirmed owner")
DUE = datetime(2031, 3, 1, tzinfo=timezone.utc)
SELF = {"version": 1, "decision": "self", "address": None, "label": None}
UNKNOWN = {"version": 1, "decision": "unknown", "address": None, "label": None}


@pytest.fixture
def store(tmp_path):
    db = TaskStore(tmp_path / "task-responsibility.db")
    try:
        yield db
    finally:
        db.close()


def set_owner(db, task_id, request_id, revision, **decision):
    return db.change_responsibility(task_id, request_id=request_id, expected_revision=revision,
                                    operation="set", decision=decision or {"decision": "self"})


def test_explicit_decision_survives_restart_and_changes_only_responsibility(store, tmp_path):
    task = store.from_suggestion("calibration-fixture", "Kalibrierprotokoll korrigieren", SOURCE,
                                 due=DUE, person={"adresse": "niko@example.invalid", "name": "Niko"})
    before = store.warten_auf(task.id, "Ersatzteil von Tami")
    snapshot = store.responsibility_snapshot(task.id)
    assert snapshot["task"].responsibility is None
    assert snapshot["responsibility_event_sequence"] is None
    self_result = set_owner(store, task.id, "synthetic-self", snapshot["revision"])
    assert self_result["task"].responsibility == SELF
    first = set_owner(store, task.id, "synthetic-one", self_result["revision"],
                      decision="person", address="  Alex.ONE@EXAMPLE.INVALID  ", label="Alex Test")
    assert first["task"].responsibility == {
        "version": 1, "decision": "person", "address": "alex.one@example.invalid", "label": "Alex Test",
    }
    second = set_owner(store, task.id, "synthetic-two", first["revision"],
                       decision="person", address="alex.two@example.invalid", label="Alex Test")
    after = second["task"]
    assert after.responsibility["address"] == "alex.two@example.invalid"
    for field in ("provenance", "person", "title", "due", "wartet_auf", "wartet_seit", "status", "created_at"):
        assert getattr(after, field) == getattr(before, field)
    assert second["revision"] == second["applied_event_sequence"] == second["responsibility_event_sequence"]
    assert second["replayed"] is False
    with sqlite3.connect(tmp_path / "task-responsibility.db") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    restarted = TaskStore(tmp_path / "task-responsibility.db")
    try:
        edit = restarted.edit(task.id, title="Neues Kalibrierprotokoll", due=None)
        assert edit.responsibility == after.responsibility
        current = restarted.responsibility_snapshot(task.id)
        assert current["revision"] > second["revision"]
        assert current["responsibility_event_sequence"] == second["applied_event_sequence"]
        reset = restarted.change_responsibility(task.id, request_id="synthetic-reset",
                                                expected_revision=current["revision"], operation="reset")
        assert reset["task"].responsibility == UNKNOWN
    finally:
        restarted.close()
    assert store.get(task.id).responsibility == UNKNOWN


def test_replay_reads_current_task_and_detects_conflict_beyond_history_page(store):
    task = store.add("Messgerät beschriften", SOURCE)
    revision = store.responsibility_snapshot(task.id)["revision"]
    first = set_owner(store, task.id, "synthetic-old", revision,
                      decision="person", address=" Alex@Example.Invalid ")
    same_state = set_owner(store, task.id, "synthetic-new", first["revision"],
                           decision="person", address="alex@example.invalid")
    assert same_state["applied_event_sequence"] > first["applied_event_sequence"]
    for i in range(105):
        store.edit(task.id, notes=f"synthetic detail {i}")
    current = store.change_responsibility(task.id, request_id="synthetic-reset",
                                          expected_revision=store.responsibility_snapshot(task.id)["revision"],
                                          operation="reset")
    assert first["applied_event_sequence"] not in {event["sequence"] for event in store.history(task.id)}
    replay = set_owner(store, task.id, "synthetic-old", revision, decision="person", address="alex@example.invalid")
    assert replay["task"].responsibility == UNKNOWN
    assert replay["revision"] == replay["responsibility_event_sequence"] == current["revision"]
    assert replay["applied_event_sequence"] == first["applied_event_sequence"]
    assert replay["replayed"] is True
    with pytest.raises(TaskRequestConflict):
        set_owner(store, task.id, "synthetic-old", revision)
    assert store.responsibility_snapshot(task.id)["revision"] == current["revision"]


def test_undo_requires_current_revision_and_latest_transition(store):
    task = store.add("Prüfsiegel nummerieren", SOURCE)
    rev = store.responsibility_snapshot(task.id)["revision"]
    one = set_owner(store, task.id, "synthetic-first", rev)
    store.warten_auf(task.id, "Rückmeldung der Werkstatt")
    waiting_rev = store.responsibility_snapshot(task.id)["revision"]

    def undo(request, revision, target):
        return store.change_responsibility(task.id, request_id=request, expected_revision=revision,
                                           operation="undo", target_event_sequence=target)

    with pytest.raises(TaskChangedError):
        undo("synthetic-undo", one["revision"], one["applied_event_sequence"])
    undone = undo("synthetic-undo", waiting_rev, one["applied_event_sequence"])
    assert undone["task"].responsibility == UNKNOWN
    assert undone["task"].wartet_auf == "Rückmeldung der Werkstatt"
    assert undo("synthetic-undo", waiting_rev, one["applied_event_sequence"])["replayed"] is True
    with pytest.raises(TaskChangedError):
        undo("synthetic-undo-again", undone["revision"], one["applied_event_sequence"])
    self_result = set_owner(store, task.id, "synthetic-self-again", undone["revision"])
    reset = store.change_responsibility(task.id, request_id="synthetic-reset", expected_revision=self_result["revision"],
                                        operation="reset")
    reset_again = store.change_responsibility(task.id, request_id="synthetic-reset-again",
                                              expected_revision=reset["revision"], operation="reset")
    assert reset_again["task"].responsibility == UNKNOWN
    assert reset_again["revision"] > reset["revision"]
    restored_unknown = undo("synthetic-undo-second-reset", reset_again["revision"], reset_again["revision"])
    assert restored_unknown["task"].responsibility == UNKNOWN

    self_result = set_owner(store, task.id, "synthetic-self-third", restored_unknown["revision"])
    reset = store.change_responsibility(task.id, request_id="synthetic-final-reset",
                                        expected_revision=self_result["revision"], operation="reset")
    restored = undo("synthetic-undo-reset", reset["revision"], reset["applied_event_sequence"])
    assert restored["task"].responsibility == SELF
    assert restored["task"].wartet_auf == "Rückmeldung der Werkstatt"


def test_two_connections_compare_and_write_against_same_revision(store, tmp_path):
    task = store.add("Endanschlag dokumentieren", SOURCE)
    revision = store.responsibility_snapshot(task.id)["revision"]
    barrier = Barrier(2)
    other = TaskStore(tmp_path / "task-responsibility.db")

    def submit(index, db):
        barrier.wait(timeout=3)
        try:
            return set_owner(db, task.id, f"synthetic-parallel-{index}", revision)
        except TaskChangedError:
            return None

    try:
        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(submit, 1, store)
            second = pool.submit(submit, 2, other)
            assert sum(result.result() is not None for result in (first, second)) == 1
    finally:
        other.close()
    assert len(store.history(task.id)) == 2
    assert store.get(task.id).responsibility == SELF


def test_failed_receipt_insert_rolls_back_document_and_request(store):
    task = store.add("Messprotokoll ausdrucken", SOURCE)
    revision = store.responsibility_snapshot(task.id)["revision"]
    store._conn.execute(
        "CREATE TRIGGER fail_responsibility BEFORE INSERT ON task_events "
        "BEGIN SELECT RAISE(ABORT, 'synthetic history error'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="synthetic history error"):
        set_owner(store, task.id, "synthetic-retry", revision)
    assert store.get(task.id).responsibility is None
    assert store.responsibility_snapshot(task.id)["revision"] == revision
    store._conn.execute("DROP TRIGGER fail_responsibility")
    assert set_owner(store, task.id, "synthetic-retry", revision)["replayed"] is False


def test_old_task_without_responsibility_preserves_completed_proof(store):
    task = store.add("Altes Abschlussprotokoll", Provenance(source_type=SourceType.USER_STATED))
    store.confirm_completion(task.id)
    # Simulate the exact old JSON shape without changing immutable history in place.
    store._conn.execute("UPDATE tasks SET document = json_remove(document, '$.responsibility') WHERE id = ?", (task.id,))
    store._conn.commit()
    status = store.status_for_recall_id(task.id).proof
    assert status is not None and status.confirmation_event_sequence is not None
    snapshot = store.responsibility_snapshot(task.id)
    assert snapshot["task"].responsibility is None
    assert snapshot["responsibility_event_sequence"] is None
    owner = set_owner(store, task.id, "synthetic-closed-task", snapshot["revision"])
    latest = store.status_for_recall_id(task.id).proof
    assert latest is not None and latest.state.value == "done"
    assert latest.confirmation_event_sequence == status.confirmation_event_sequence
    assert latest.state_event_sequence == status.state_event_sequence
    assert latest.task_revision == owner["revision"]


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", "synthetic-responsibility-token")
    app = create_app()
    with TestClient(app, headers={"X-Icarus-Token": "synthetic-responsibility-token"}) as client:
        task = app.state.tasks.add("Lehrenhalter prüfen", SOURCE, due=DUE)
        path = f"/api/v1/tasks/{task.id}/responsibility"
        yield app, client, task, path


def test_guarded_api_persists_confirmed_decision_and_bounded_event(api):
    app, client, task, path = api
    assert client.get(path, headers={"X-Icarus-Token": "wrong"}).status_code == 401
    assert client.post(path, headers={"X-Icarus-Token": "wrong"}, json={}).status_code == 401
    snapshot = client.get(path)
    assert snapshot.status_code == 200
    before = snapshot.json()
    assert before["task"]["responsibility"] is None
    payload = {"request_id": "synthetic-api", "expected_revision": before["revision"],
               "confirmed": True, "operation": "set", "owner": {"decision": "person", "address": "kim@example.invalid"}}
    response = client.post(path, json=payload)
    assert response.status_code == 200
    saved = response.json()
    assert saved["task"]["responsibility"] == {
        "version": 1, "decision": "person", "address": "kim@example.invalid", "label": None,
    }
    assert saved["task"]["provenance"] == before["task"]["provenance"]
    assert client.get(path).json() == {
        key: saved[key] for key in ("task", "revision", "responsibility_event_sequence", "own_address_overlap")
    }
    event = app.state.tasks.history_event(task.id, saved["applied_event_sequence"])
    assert event["kind"] == "responsibility_confirmed"
    assert event["actor_id"] is None
    serialized = json.dumps(event)
    assert "Synthetic source report" not in serialized and task.title not in serialized
    assert "provenance" not in event["after"]
    receipt = event["after"]["responsibility_operation"]
    assert receipt["request_id"] == payload["request_id"]
    assert len(receipt["digest"]) == 64
    assert set(receipt) == {"request_id", "digest"}
    assert client.post(path, json={**payload, "operation": "reset", "owner": {"decision": "self"}}).status_code == 422
    assert client.post(path, json={**payload, "owner": {"decision": "self"}}).status_code == 409
    assert client.post(path, json={**payload, "request_id": "synthetic-stale"}).status_code == 409
    assert client.post(path, json=payload).json()["replayed"] is True
    missing = "/api/v1/tasks/t-000000000000/responsibility"
    assert client.get(missing).status_code == 404
    assert client.post(missing, json=payload).status_code == 404


def test_api_rejects_malformed_or_unconfirmed_commands_without_event(api):
    app, client, task, path = api
    revision = app.state.tasks.history(task.id)[0]["sequence"]
    base = {"request_id": "synthetic-invalid", "expected_revision": revision,
            "confirmed": True, "operation": "set", "owner": {"decision": "self"}}
    variants = (
        {"confirmed": False}, {"confirmed": 1}, {"confirmed": "true"},
        {"expected_revision": True}, {"expected_revision": str(revision)}, {"expected_revision": 2**63},
        {"request_id": ""}, {"request_id": "a b"}, {"request_id": "a" * 101}, {"request_id": 7},
        {"actor_id": "synthetic-forged"}, {"target_event_sequence": None},
        {"owner": {"decision": "self", "address": None}}, {"owner": {"decision": "self", "label": "Alex"}},
        {"owner": {"decision": "person", "label": "Alex"}}, {"owner": {"decision": "person", "address": " "}},
        {"owner": {"decision": "person", "address": "Alex"}}, {"owner": {"decision": "person", "address": "a@"}},
        {"owner": {"decision": "person", "address": "Alex <a@example.invalid>"}},
        {"owner": {"decision": "person", "address": "a@example.invalid\n"}},
        {"owner": {"decision": "person", "address": "a@example.invalid", "label": "x" * 121}},
        {"owner": {"decision": "person", "address": "x" * 255 + "@example.invalid"}},
        {"owner": {"decision": "unknown"}}, {"owner": {"decision": "self", "version": 1}},
        {"operation": "undo"}, {"operation": "reset", "owner": None},
    )
    for variant in variants:
        assert client.post(path, json={**base, **variant}).status_code == 422, variant
    assert [event["sequence"] for event in app.state.tasks.history(task.id)] == [revision]


def test_lookup_budget_exhaustion_is_retryable_and_does_not_write(api, monkeypatch):
    from icarus_memory import tasks

    app, client, task, path = api
    revision = app.state.tasks.history(task.id)[0]["sequence"]
    base = {"request_id": "synthetic-budget", "expected_revision": revision,
            "confirmed": True, "operation": "set", "owner": {"decision": "self"}}
    with monkeypatch.context() as bounded:
        bounded.setattr(tasks, "_RECALL_OPCODE_BUDGET", 1)
        bounded.setattr(tasks, "_RECALL_PROGRESS_STEPS", 1)
        response = client.post(path, json=base)
        assert response.status_code == 503
    assert [event["sequence"] for event in app.state.tasks.history(task.id)] == [revision]
    assert client.post(path, json=base).status_code == 200


def test_restoring_same_task_preserves_decision_and_receipt(store):
    proposal_id = "synthetic-restored"
    task = store.from_suggestion(proposal_id, "Drehmoment prüfen", SOURCE, angelegt={"art": "automatisch"})
    revision = store.responsibility_snapshot(task.id)["revision"]
    decision = store.change_responsibility(task.id, request_id="synthetic-preserved",
                                           expected_revision=revision, operation="reset")
    store.anlage_entfernen(task.id, merken={"proposal_id": proposal_id, "episode_id": "synthetic",
                                          "titel_schluessel": "synthetic", "zitat_schluessel": "synthetic"})
    with pytest.raises(KeyError):
        store.responsibility_snapshot(task.id)
    with pytest.raises(KeyError):
        store.change_responsibility(task.id, request_id="synthetic-preserved",
                                    expected_revision=revision, operation="reset")
    restored, _ = store.anlage_wiederherstellen(task.id)
    assert restored.responsibility == UNKNOWN
    replay = store.change_responsibility(task.id, request_id="synthetic-preserved",
                                          expected_revision=revision, operation="reset")
    assert replay["replayed"] is True
    assert replay["responsibility_event_sequence"] == decision["applied_event_sequence"]
    assert replay["revision"] > decision["revision"]


def test_reused_task_id_never_replays_old_incarnation_or_borrows_its_undo(store, monkeypatch):
    from icarus_memory import tasks

    # Both removed snapshots have the same tracked values, including creation time.
    monkeypatch.setattr(tasks, "now", lambda: DUE)
    proposal_id = "synthetic-reused"
    task = store.from_suggestion(proposal_id, "Spannung prüfen", SOURCE, angelegt={"art": "automatisch"})
    revision = store.responsibility_snapshot(task.id)["revision"]
    old = set_owner(store, task.id, "synthetic-first-incarnation", revision)
    store.anlage_entfernen(task.id, merken={"proposal_id": proposal_id, "episode_id": "synthetic",
                                          "titel_schluessel": "synthetic", "zitat_schluessel": "synthetic"})
    recreated = store.from_suggestion(proposal_id, "Spannung prüfen", SOURCE, angelegt={"art": "automatisch"})
    assert recreated.id == task.id
    fresh = store.responsibility_snapshot(task.id)
    assert fresh["task"].responsibility is fresh["responsibility_event_sequence"] is None
    with pytest.raises(TaskRequestConflict):
        set_owner(store, task.id, "synthetic-first-incarnation", revision)
    new = set_owner(store, task.id, "synthetic-second-incarnation", fresh["revision"])
    assert new["responsibility_event_sequence"] != old["responsibility_event_sequence"]
    store.anlage_entfernen(task.id)
    restored, _ = store.anlage_wiederherstellen(task.id)
    assert restored.responsibility == SELF
    snapshot = store.responsibility_snapshot(task.id)
    assert snapshot["responsibility_event_sequence"] is None
    with pytest.raises(TaskRequestConflict):
        set_owner(store, task.id, "synthetic-second-incarnation", fresh["revision"])
    with pytest.raises(TaskChangedError):
        store.change_responsibility(task.id, request_id="synthetic-wrong-incarnation-undo",
                                    expected_revision=snapshot["revision"], operation="undo",
                                    target_event_sequence=new["applied_event_sequence"])


def test_fresh_tombstone_after_id_reuse_keeps_current_receipt_and_undo(store, monkeypatch):
    from icarus_memory import tasks

    # A repeated clock value cannot distinguish the two incarnations.
    monkeypatch.setattr(tasks, "now", lambda: DUE)
    proposal_id = "synthetic-fresh-tombstone"
    remember = {"proposal_id": proposal_id, "episode_id": "synthetic",
                "titel_schluessel": "synthetic", "zitat_schluessel": "synthetic"}
    first = store.from_suggestion(proposal_id, "Prüfstand sichern", SOURCE, angelegt={"art": "automatisch"})
    original_revision = store.responsibility_snapshot(first.id)["revision"]
    store.change_responsibility(first.id, request_id="synthetic-original-tombstone",
                                expected_revision=original_revision, operation="reset")
    store.anlage_entfernen(first.id, merken=remember)
    current = store.from_suggestion(proposal_id, "Prüfstand sichern", SOURCE, angelegt={"art": "automatisch"})
    assert current.id == first.id
    revision = store.responsibility_snapshot(current.id)["revision"]
    decision = store.change_responsibility(current.id, request_id="synthetic-current-tombstone",
                                           expected_revision=revision, operation="reset")
    store.anlage_entfernen(current.id, merken=remember)
    store.anlage_wiederherstellen(current.id)
    snapshot = store.responsibility_snapshot(current.id)
    assert snapshot["task"].responsibility == UNKNOWN
    assert snapshot["responsibility_event_sequence"] == decision["applied_event_sequence"]
    replay = store.change_responsibility(current.id, request_id="synthetic-current-tombstone",
                                          expected_revision=revision, operation="reset")
    assert replay["replayed"] is True
    assert replay["revision"] == snapshot["revision"]
    with pytest.raises(TaskRequestConflict):
        store.change_responsibility(current.id, request_id="synthetic-original-tombstone",
                                    expected_revision=original_revision, operation="reset")
    undo = store.change_responsibility(current.id, request_id="synthetic-undo-current-tombstone",
                                        expected_revision=snapshot["revision"], operation="undo",
                                        target_event_sequence=decision["applied_event_sequence"])
    assert undo["task"].responsibility == UNKNOWN
    assert undo["applied_event_sequence"] > snapshot["revision"]
