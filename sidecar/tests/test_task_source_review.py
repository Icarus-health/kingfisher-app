from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.mail_timeline import thread_tags
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.server import create_app

_TODAY = object()

def _app(tmp_path):
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="task-source-review"))
    return app, TestClient(app)


def _mail(account, message_id, *, references=()):
    message = SimpleNamespace(account_id=account, message_id=message_id,
                              in_reply_to="", references=references)
    tags = thread_tags(message)
    return message, tags


def _record(app, account, message_id, *, references=(), occurred, recorded, source_key=""):
    message, tags = _mail(account, message_id, references=references)
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, "Mail", f"synthetischer Inhalt {message_id}",
        Provenance(source_type=SourceType.EMAIL,
                   source_ref=f"{account}:{message_id}", captured_at=occurred),
        occurred_at=occurred, tags=tags, at=recorded, source_key=source_key,
    )
    return episode


def _task(app, source, *, created, due=_TODAY):
    if due is _TODAY:
        due = datetime.combine(date.today(), time.min, datetime.now().astimezone().tzinfo)
    return app.state.tasks.add(
        "Rückmeldung nachhalten",
        Provenance(source_type=SourceType.USER_STATED, source_ref=f"episode:{source.id}",
                   verbatim="Bitte Rückmeldung geben."),
        due=due, at=created,
    )


def test_newly_recorded_exact_thread_message_is_visible_without_mutating_task(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=2)
    sent = confirmed - timedelta(days=40)
    original = _record(app, "acct-a", "<original@local>", occurred=sent, recorded=confirmed - timedelta(minutes=5))
    task = _task(app, original, created=confirmed)
    reply = _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
                    occurred=sent - timedelta(days=2), recorded=confirmed + timedelta(minutes=1))

    before = app.state.tasks.get(task.id).to_dict()
    history_before = app.state.tasks.history(task.id)
    from icarus_memory.task_source_review import review_tasks
    assert review_tasks(app.state.episodes, [task]).by_task
    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert item["source_review"] == {
        "reason": "Seit dem Festhalten der Aufgabe wurde eine weitere Nachricht im Verlauf erfasst. Bitte prüfen, ob die Aufgabe noch so gilt.",
        "followup_episode_id": reply.id,
    }
    assert any(item["source_review"]["reason"] in point["text"]
               for point in dashboard["briefing"]["punkte"])

    morning = client.get("/api/v1/morning-briefing", params={"post": "false"}).json()
    card = next(item for item in morning["needs_you"] if item.get("source_ref") == task.id)
    assert card["reason"] == item["source_review"]["reason"]
    assert card["detail"] == item["source_review"]["reason"]
    assert card["action"] == "Verlauf prüfen"
    assert card["episode_id"] == reply.id

    source_response = client.get(f"/api/v1/tasks/{task.id}/source")
    assert source_response.status_code == 200
    assert source_response.json()["source_review"] == item["source_review"]
    assert app.state.tasks.get(task.id).to_dict() == before
    assert app.state.tasks.history(task.id) == history_before


def test_accepted_mail_candidate_with_user_stated_task_provenance_is_reviewed(tmp_path):
    app, client = _app(tmp_path)
    captured = datetime.now(timezone.utc) - timedelta(hours=1)
    original, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, "Mail", "Bitte Rückmeldung zur Anfrage geben.",
        Provenance(source_type=SourceType.EMAIL, source_ref="acct-a:<original@local>",
                   captured_at=captured),
        occurred_at=captured, tags=thread_tags(SimpleNamespace(
            account_id="acct-a", message_id="<original@local>", in_reply_to="", references=())),
        at=captured,
    )
    app.state.proposals.record_task_analysis(
        original.id, original.digest,
        [{"title": "Rückmeldung geben", "quote": original.body}], proposed_by="test/local",
    )
    proposal = app.state.proposals.pending(ProposalKind.TASK)[0]
    accepted = client.post(f"/api/v1/task-candidates/{proposal.id}/accept",
                           json={"title": proposal.statement}).json()
    task = app.state.tasks.get(accepted["id"])
    assert task.provenance.source_type is SourceType.USER_STATED
    later = _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
                    occurred=captured - timedelta(days=1), recorded=task.created_at + timedelta(seconds=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert item["source_review"]["followup_episode_id"] == later.id


def test_message_recorded_before_confirmation_never_creates_review_even_if_sent_later(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(minutes=1)
    original = _record(app, "acct-a", "<original@local>", occurred=confirmed - timedelta(days=2),
                       recorded=confirmed - timedelta(hours=2))
    _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
            occurred=confirmed + timedelta(days=1), recorded=confirmed - timedelta(minutes=2))
    task = _task(app, original, created=confirmed)
    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert "source_review" not in item
    assert not any("Seit dem Festhalten der Aufgabe" in point["text"]
                   for point in dashboard["briefing"]["punkte"])


def test_later_reply_reachable_only_through_preconfirmation_message_is_reviewed(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    original = _record(app, "acct-a", "<a@local>", occurred=confirmed - timedelta(days=4),
                       recorded=confirmed - timedelta(minutes=20))
    _record(app, "acct-a", "<b@local>", references=("<a@local>",),
            occurred=confirmed - timedelta(days=3), recorded=confirmed - timedelta(minutes=10))
    task = _task(app, original, created=confirmed)
    later = _record(app, "acct-a", "<c@local>", references=("<b@local>",),
                    occurred=confirmed - timedelta(days=2), recorded=confirmed + timedelta(minutes=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert item["source_review"]["followup_episode_id"] == later.id


def test_batch_thread_expansion_keeps_connected_ids_scoped_per_task(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    first_source = _record(app, "acct-a", "<first@local>", occurred=confirmed,
                           recorded=confirmed - timedelta(minutes=20))
    unrelated_source = _record(app, "acct-a", "<unrelated@local>", occurred=confirmed,
                               recorded=confirmed - timedelta(minutes=18))
    first_task = _task(app, first_source, created=confirmed)
    unrelated_task = _task(app, unrelated_source, created=confirmed + timedelta(seconds=1))
    _record(app, "acct-a", "<middle@local>", references=("<first@local>",),
            occurred=confirmed, recorded=confirmed - timedelta(minutes=10))
    last = _record(app, "acct-a", "<last@local>", references=("<middle@local>",),
                   occurred=confirmed, recorded=confirmed + timedelta(minutes=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    by_id = {item["id"]: item for item in dashboard["tasks"]["items"]}
    assert by_id[first_task.id]["source_review"]["followup_episode_id"] == last.id
    assert "source_review" not in by_id[unrelated_task.id]


def test_new_sibling_reply_is_connected_through_source_references(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    parent = _record(app, "acct-a", "<parent@local>", occurred=confirmed - timedelta(days=4),
                     recorded=confirmed - timedelta(minutes=20))
    source = _record(app, "acct-a", "<task-source@local>", references=("<parent@local>",),
                     occurred=confirmed - timedelta(days=3), recorded=confirmed - timedelta(minutes=10))
    task = _task(app, source, created=confirmed)
    sibling = _record(app, "acct-a", "<sibling@local>", references=("<parent@local>",),
                      occurred=confirmed - timedelta(days=2), recorded=confirmed + timedelta(minutes=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert item["source_review"]["followup_episode_id"] == sibling.id


def test_late_imported_predecessor_is_part_of_thread_review(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    source = _record(app, "acct-a", "<task-source@local>", references=("<not-yet-imported@local>",),
                     occurred=confirmed - timedelta(days=3), recorded=confirmed - timedelta(minutes=10))
    task = _task(app, source, created=confirmed)
    predecessor = _record(app, "acct-a", "<not-yet-imported@local>",
                          occurred=confirmed - timedelta(days=4), recorded=confirmed + timedelta(minutes=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert item["source_review"]["followup_episode_id"] == predecessor.id


def test_other_account_same_message_id_and_same_subject_are_not_thread_matches(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    original = _record(app, "acct-a", "<same@local>", occurred=confirmed, recorded=confirmed - timedelta(minutes=5))
    task = _task(app, original, created=confirmed)
    _record(app, "acct-b", "<reply@local>", references=("<same@local>",),
            occurred=confirmed, recorded=confirmed + timedelta(minutes=1))
    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert "source_review" not in item


def test_ignored_followup_and_replaced_original_do_not_create_review(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    original = _record(app, "acct-a", "<original@local>", occurred=confirmed, recorded=confirmed - timedelta(minutes=5))
    task = _task(app, original, created=confirmed)
    reply = _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
                    occurred=confirmed, recorded=confirmed + timedelta(minutes=1))
    app.state.episodes.ignore(reply.id)
    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert "source_review" not in item


def test_review_gets_a_briefing_point_without_due_date_or_single_due_card(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=2)
    original = _record(app, "acct-a", "<original@local>", occurred=confirmed,
                       recorded=confirmed - timedelta(minutes=5))
    undated = _task(app, original, created=confirmed, due=None)
    future = _task(app, original, created=confirmed + timedelta(seconds=1),
                   due=datetime.now().astimezone() + timedelta(days=30))
    grouped_a = _task(app, original, created=confirmed + timedelta(seconds=2))
    grouped_b = _task(app, original, created=confirmed + timedelta(seconds=3))
    _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
            occurred=confirmed - timedelta(days=20), recorded=confirmed + timedelta(minutes=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    reviewed = [task for task in dashboard["tasks"]["items"] if task.get("source_review")]
    assert {task["id"] for task in reviewed} == {undated.id, future.id, grouped_a.id, grouped_b.id}
    points = dashboard["briefing"]["punkte"]
    assert len([point for point in points if "Seit dem Festhalten der Aufgabe" in point["text"]]) == 3
    assert any("1 weitere Aufgaben benötigen eine Verlaufsprüfung" in point["text"] for point in points)


def test_capped_thread_lookup_says_incomplete_instead_of_clean(tmp_path, monkeypatch):
    import icarus_memory.task_source_review as source_review
    monkeypatch.setattr(source_review, "MAX_THREAD_ROWS", 1)
    app, _ = _app(tmp_path)
    base = datetime.now(timezone.utc)
    original = _record(app, "acct-a", "<original@local>", occurred=base,
                       recorded=base - timedelta(minutes=10))
    _record(app, "acct-a", "<reply-one@local>", references=("<original@local>",),
            occurred=base, recorded=base + timedelta(minutes=1))
    _record(app, "acct-a", "<reply-two@local>", references=("<original@local>",),
            occurred=base, recorded=base + timedelta(minutes=2))
    task = _task(app, original, created=base + timedelta(minutes=3))

    review = source_review.review_tasks(app.state.episodes, [task]).by_task[task.id]
    assert review == {"reason": source_review.LIMIT_REASON, "followup_episode_id": None}


def test_task_lookup_cap_marks_unchecked_tasks_incomplete(tmp_path, monkeypatch):
    import icarus_memory.task_source_review as source_review
    monkeypatch.setattr(source_review, "MAX_TASKS", 1)
    app, _ = _app(tmp_path)
    base = datetime.now(timezone.utc)
    original = _record(app, "acct-a", "<original@local>", occurred=base,
                       recorded=base - timedelta(minutes=1))
    first = _task(app, original, created=base)
    second = _task(app, original, created=base + timedelta(seconds=1))

    reviews = source_review.review_tasks(app.state.episodes, [first, second]).by_task
    assert reviews == {second.id: {"reason": source_review.LIMIT_REASON, "followup_episode_id": None}}


def test_frontier_parameter_cap_marks_omitted_thread_as_incomplete(tmp_path, monkeypatch):
    import icarus_memory.task_source_review as source_review
    monkeypatch.setattr(source_review, "MAX_FRONTIER_TAGS", 1)
    app, _ = _app(tmp_path)
    base = datetime.now(timezone.utc)
    first_source = _record(app, "acct-a", "<first@local>", occurred=base,
                           recorded=base - timedelta(minutes=2))
    second_source = _record(app, "acct-a", "<second@local>", occurred=base,
                            recorded=base - timedelta(minutes=1))
    first = _task(app, first_source, created=base)
    second = _task(app, second_source, created=base + timedelta(seconds=1))

    reviews = source_review.review_tasks(app.state.episodes, [first, second]).by_task
    assert len(reviews) == 1
    assert next(iter(reviews.values())) == {
        "reason": source_review.LIMIT_REASON, "followup_episode_id": None,
    }


def test_sqlite_vm_budget_interruption_is_incomplete_and_handler_is_reset(tmp_path, monkeypatch):
    import icarus_memory.task_source_review as source_review
    app, _ = _app(tmp_path)
    base = datetime.now(timezone.utc)
    original = _record(app, "acct-a", "<original@local>", occurred=base,
                       recorded=base - timedelta(minutes=1))
    task = _task(app, original, created=base)
    reply = _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
                    occurred=base, recorded=base + timedelta(minutes=1))

    monkeypatch.setattr(source_review, "MAX_QUERY_STEPS", 0)
    monkeypatch.setattr(source_review, "PROGRESS_OPCODES", 1)
    limited = source_review.review_tasks(app.state.episodes, [task])
    # We could not safely classify the source under this budget, so the result
    # is a global coverage notice rather than an unsupported mail-specific claim.
    assert limited.coverage_limited is True
    assert limited.by_task == {}
    assert app.state.episodes._conn.execute("SELECT count(*) FROM episodes").fetchone()[0] >= 2

    monkeypatch.setattr(source_review, "MAX_QUERY_STEPS", 1_000_000)
    monkeypatch.setattr(source_review, "PROGRESS_OPCODES", 1000)
    reviewed = source_review.review_tasks(app.state.episodes, [task]).by_task
    assert reviewed[task.id]["followup_episode_id"] == reply.id
    assert app.state.episodes._conn.execute("SELECT count(*) FROM episodes").fetchone()[0] >= 2


def test_document_sourced_task_does_not_get_a_mail_thread_warning(tmp_path, monkeypatch):
    import icarus_memory.task_source_review as source_review
    monkeypatch.setattr(source_review, "MAX_TASKS", 0)
    app, _ = _app(tmp_path)
    document, _ = app.state.episodes.record(
        EpisodeKind.DOCUMENT, "Notiz", "Bitte später prüfen.",
        Provenance(source_type=SourceType.DOCUMENT),
    )
    task = app.state.tasks.add(
        "Notiz prüfen", Provenance(source_type=SourceType.DOCUMENT,
                                    source_ref=f"episode:{document.id}"),
    )
    assert source_review.review_tasks(app.state.episodes, [task]).by_task == {}


def test_classification_limit_is_visible_in_morning_without_false_mail_warning(tmp_path, monkeypatch):
    import icarus_memory.task_source_review as source_review
    monkeypatch.setattr(source_review, "MAX_CLASSIFICATION_TASKS", 0)
    app, client = _app(tmp_path)
    document, _ = app.state.episodes.record(
        EpisodeKind.DOCUMENT, "Notiz", "Bitte später prüfen.",
        Provenance(source_type=SourceType.DOCUMENT),
    )
    task = app.state.tasks.add(
        "Notiz prüfen", Provenance(source_type=SourceType.USER_STATED,
                                    source_ref=f"episode:{document.id}"),
    )

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert "source_review" not in item
    assert dashboard["tasks"]["source_review_coverage"] == {
        "complete": False, "reason": source_review.CLASSIFICATION_LIMIT_REASON,
    }

    morning = client.get("/api/v1/morning-briefing", params={"post": "false"}).json()
    coverage = next(item for item in morning["partial_failures"]
                    if item["section"] == "source_review")
    assert coverage["message"] == source_review.CLASSIFICATION_LIMIT_REASON
    assert not any(item.get("source_ref") == task.id and
                   item.get("reason") == source_review.FOLLOWUP_REASON
                   for item in morning["needs_you"])


def test_replaced_original_source_is_not_used_for_thread_review(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    original = _record(app, "acct-a", "<original@local>", occurred=confirmed,
                       recorded=confirmed - timedelta(minutes=5), source_key="mail-source-a")
    app.state.episodes.advance_source_head("mail-source-a", None, original.id)
    task = _task(app, original, created=confirmed)
    _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
            occurred=confirmed, recorded=confirmed + timedelta(minutes=1))
    replacement, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, "Mail", "geänderte Originalquelle",
        Provenance(source_type=SourceType.EMAIL,
                   source_ref="acct-a:<original@local>", captured_at=confirmed),
        occurred_at=confirmed, tags=thread_tags(SimpleNamespace(
            account_id="acct-a", message_id="<original@local>", in_reply_to="", references=())),
        at=confirmed + timedelta(minutes=2), source_key="mail-source-a",
    )
    assert replacement.id != original.id
    app.state.episodes.advance_source_head("mail-source-a", original.id, replacement.id)
    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    item = next(item for item in dashboard["tasks"]["items"] if item["id"] == task.id)
    assert "source_review" not in item


def test_waiting_task_keeps_waiting_card_semantics_when_review_is_needed(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    original = _record(app, "acct-a", "<original@local>", occurred=confirmed,
                       recorded=confirmed - timedelta(minutes=5))
    task = _task(app, original, created=confirmed, due=None)
    app.state.tasks.warten_auf(task.id, "Lea", at=confirmed)
    _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
            occurred=confirmed, recorded=confirmed + timedelta(minutes=1))

    dashboard = client.get("/dashboard", params={"post": "false"}).json()
    review_point = next(point for point in dashboard["briefing"]["punkte"] if point["ref"] == task.id)
    assert review_point["quelle"] == "wartet"
    assert dashboard["tasks"]["wartend"][0]["source_review"]["followup_episode_id"]
    morning = client.get("/api/v1/morning-briefing", params={"post": "false"}).json()
    card = next(item for item in morning["needs_you"] if item["source_ref"] == task.id)
    assert card["source"] == "wartet"


def test_closed_task_does_not_receive_an_open_followup_prompt(tmp_path):
    app, client = _app(tmp_path)
    confirmed = datetime.now(timezone.utc) - timedelta(hours=1)
    original = _record(app, "acct-a", "<original@local>", occurred=confirmed,
                       recorded=confirmed - timedelta(minutes=5))
    task = _task(app, original, created=confirmed)
    app.state.tasks.complete(task.id)
    _record(app, "acct-a", "<reply@local>", references=("<original@local>",),
            occurred=confirmed, recorded=confirmed + timedelta(minutes=1))

    source_response = client.get(f"/api/v1/tasks/{task.id}/source")
    assert source_response.status_code == 200
    assert "source_review" not in source_response.json()
