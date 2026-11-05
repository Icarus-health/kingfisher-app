"""Responsibility classification across pages, readers, and mail changes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import briefing, kommendes
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskChangedError, TaskRequestConflict, TaskStore

AT = datetime(2025, 1, 2, 12, tzinfo=timezone.utc)
P = Provenance(SourceType.USER_STATED)
OTHER = {"decision": "person", "address": "alex@example.invalid", "label": "Alex"}


def decide(store, task, owner=None):
    return store.change_responsibility(
        task.id, request_id=f"synthetic-{task.id}",
        expected_revision=store.responsibility_snapshot(task.id)["revision"],
        operation="set" if owner else "reset", decision=owner,
    )


def populate(store, project_id="synthetic"):
    def add(title, days):
        return store.add(title, P, due=AT - timedelta(days=days), project_id=project_id)
    other, unknown, own, waiting = (add(title, days) for title, days in (
        ("Andere Ausführung", 5), ("Ungeklärte Ausführung", 4),
        ("Eigene Ausführung", 1), ("Eigene Aufgabe mit Abhängigkeit", 3)))
    decide(store, other, OTHER)
    decide(store, unknown)
    decide(store, own, {"decision": "self"})
    decide(store, waiting, {"decision": "self"})
    store.warten_auf(waiting.id, "Sam", at=AT - timedelta(days=12))
    return other, unknown, own, waiting


def test_pages_and_project_counters_follow_decisions(monkeypatch, tmp_path):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        project = client.post("/api/v1/projects", json={"name": "Synthetic"}).json()["id"]
        store = app.state.tasks
        other, unknown, own, waiting = populate(store, project)
        next_other = store.add("Weitere fremde Aufgabe", P, project_id=project)
        decide(store, next_other, OTHER)
        store.warten_auf(next_other.id, "Tami", at=AT - timedelta(days=2))

        def page(view, **options):
            response = client.get("/api/v1/tasks", params={"view": view, "project_id": project,
                                                         "limit": 1, **options})
            assert response.status_code == 200, response.json()
            return response.json()

        mine = page("mine")
        assert [t["id"] for t in mine["tasks"]] == [own.id]
        assert mine["total"] == 1
        assert mine["tasks"][0]["user_actionable"] is True
        others = page("others")
        assert others["total"] == 2 and others["tasks"][0]["id"] == other.id
        assert page("others", cursor=others["next_cursor"])["tasks"][0]["id"] == next_other.id
        assert page("unassigned")["tasks"][0]["id"] == unknown.id
        assert page("waiting")["total"] == 2
        assert page("waiting")["tasks"][0]["id"] == waiting.id
        counts = client.get(f"/api/v1/projects/{project}/task-overview").json()["counts"]
        assert (counts["mine"], counts["overdue"], counts["waiting"], counts["others"], counts["unassigned"]) == (1, 1, 2, 2, 1)
        store.change_responsibility(other.id, request_id="synthetic-cursor-change",
            expected_revision=store.responsibility_snapshot(other.id)["revision"], operation="reset")
        stale_page = client.get("/api/v1/tasks", params={"view": "others", "project_id": project,
                                                        "limit": 1, "cursor": others["next_cursor"]})
        assert stale_page.status_code == 409 and page("others")["total"] == 1


def test_briefing_and_coming_dates_exclude_personal_work_but_keep_waiting(tmp_path):
    with_store = TaskStore(tmp_path / "readers.db")
    try:
        other, unknown, own, waiting = populate(with_store)
        tasks = with_store.open_tasks()
        assert [t.id for t in tasks if t.is_overdue(AT)] == [own.id]
        result = briefing.erstelle({"tasks": {"items": [t.to_dict() for t in tasks]}}, jetzt=AT)
        assert any(p.ref == own.id for p in result.punkte)
        assert any(p.ref == waiting.id and p.quelle == "wartet" for p in result.punkte)
        assert not {other.id, unknown.id}.intersection(p.ref for p in result.punkte)
        today = with_store.add("Heute fällig bei anderen", P, due=AT + timedelta(hours=1))
        decide(with_store, today, OTHER)
        today_only = briefing.erstelle({"tasks": {"items": [with_store.get(today.id).to_dict()]}}, jetzt=AT)
        assert not today_only.punkte
        assert [t.id for t in with_store.due_within(at=AT)] == [own.id]
        app = SimpleNamespace(state=SimpleNamespace(tasks=with_store))
        own_lines, waiting_lines = kommendes._aufgaben(app, AT - timedelta(days=10), AT, timezone.utc, AT)
        assert len(own_lines) == 1 and own.title in own_lines[0]
        assert len(waiting_lines) == 1 and "wartet auf Sam" in waiting_lines[0]
    finally:
        with_store.close()


def test_final_post_write_rejects_corrected_owner_and_stale_self(tmp_path):
    store = TaskStore(tmp_path / "race.db")
    writer = TaskStore(tmp_path / "race.db")
    try:
        task = store.add("Synthetische Druckdaten", P)
        seen = store.responsibility_snapshot(task.id)["revision"]
        correction = decide(writer, task, OTHER)
        with pytest.raises(ValueError, match="offene Aufgabe"):
            store.post_erledigen(task.id, {"episode_id": "synthetic-mail"})
        with pytest.raises(TaskChangedError):
            store.post_erledigen(task.id, {"episode_id": "synthetic-mail"}, expected_revision=seen)
        assert store.responsibility_snapshot(task.id)["revision"] == correction["revision"]
        assert store.get(task.id).responsibility["address"] == OTHER["address"]
    finally:
        writer.close()
        store.close()


def test_reanalysis_same_citation_preserves_corrected_task_across_restart(tmp_path):
    path = tmp_path / "reanalysis.db"
    store = TaskStore(path)
    source = Provenance(SourceType.EMAIL, source_ref="episode:synthetic", verbatim="Ein bestimmter Quellensatz")
    original = store.from_suggestion("original", "Ursprünglicher Titel", source)
    decide(store, original, OTHER)
    store.close()
    store = TaskStore(path)
    try:
        with pytest.raises(TaskRequestConflict):
            store.from_suggestion("different-analysis", "Andere Handlung aus demselben Satz", source)
        retry = store.from_suggestion("original", "Neu analysierter Titel", source)
        assert retry.id == original.id and retry.title == original.title
        assert retry.responsibility["address"] == OTHER["address"]
        assert retry.provenance == original.provenance
        assert len(store.mit_quelle(source.source_ref)) == 1
        distinct = Provenance(SourceType.EMAIL, source_ref=source.source_ref, verbatim="Zweite, getrennte Aufgabe")
        assert store.from_suggestion("different-citation", "Andere Aufgabe", distinct,
                                     source_text=f"{source.verbatim}. {distinct.verbatim}.").id != original.id
    finally:
        store.close()


def test_confirmed_address_overlap_is_a_visible_conflict_only(monkeypatch, tmp_path):
    from icarus_memory.config import MailAccountSettings

    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        task = app.state.tasks.add("Eigene Adresse prüfen", P)
        saved = decide(app.state.tasks, task, OTHER)
        path = f"/api/v1/tasks/{task.id}/responsibility"
        assert client.get(path).json()["own_address_overlap"] is False
        app.state.settings.mail_accounts.append(MailAccountSettings(
            id="synthetic", label="Probe", imap_host="example.invalid", user="Alex@Example.Invalid"))
        response = client.get(path).json()
        assert response["own_address_overlap"] is True
        assert response["task"]["responsibility"] == saved["task"].responsibility
        assert response["revision"] == saved["revision"] and response["task"]["user_actionable"] is False


def test_graph_project_person_and_open_points_keep_their_distinct_roles(monkeypatch, tmp_path):
    from icarus_memory import graph, offene_punkte, personen
    from icarus_memory.akten_routes import aufgaben_zu
    from icarus_memory.episodes import EpisodeKind

    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        project = client.post("/api/v1/projects", json={"name": "Synthetic Roles"}).json()["id"]
        app.state.episodes.record(EpisodeKind.MESSAGE, "Synthetische Mail", "Quelle", P,
            participants=["Alex <alex@example.invalid>", "Alex <alex.two@example.invalid>"], occurred_at=AT)
        task = app.state.tasks.add("Synthetische Prüfung", P, project_id=project, due=AT)
        decide(app.state.tasks, task, OTHER)
        view = graph.build(episodes=app.state.episodes, workspace=app.state.workspace, tasks=app.state.tasks,
                           store=app.state.store, at=AT).to_dict()
        [node] = [n for n in view["nodes"] if n["id"] == f"task:{task.id}"]
        assert node["attributes"]["responsibility_label"] == "Alex <alex@example.invalid>"
        assert not any(edge["source"] == node["id"] and edge["relation"] == "waiting_on" for edge in view["edges"])
        profile = graph.project_profile(project, episodes=app.state.episodes, workspace=app.state.workspace,
                                        tasks=app.state.tasks)
        assert profile["tasks"][0]["responsibility"]["address"] == OTHER["address"]
        directory = personen.alle(episodes=app.state.episodes, tasks=app.state.tasks, jetzt=AT)
        by_address = {address: person for person in directory for address in person.adressen}
        assert [t["id"] for t in by_address[OTHER["address"]].offene_aufgaben] == [task.id]
        assert by_address["alex.two@example.invalid"].offene_aufgaben == []
        assert [t.id for t in aufgaben_zu(app, SimpleNamespace(beschriftung=lambda _: "Alex"),
                                           "person:a:alex@example.invalid", [])] == [task.id]
        dossier = client.get(f"/api/v1/memory/projects/{project}/einzelheiten").json()
        [entry] = dossier["aufgaben"]["eintraege"]
        assert entry["id"] == task.id and not entry["overdue"]
        assert entry["responsibility_label"] == "Alex <alex@example.invalid>"
        text, links = offene_punkte.als_text({"gesamt": 1, "punkte": [{
            "text": "Ich habe die Prüfung zugesagt.", "art": "Zusage", "richtung": "von_mir",
            "episode_id": "synthetic-source", "aufgabe": {"id": task.id, "responsibility_label": entry["responsibility_label"]},
        }]}, "zugesagt")
        assert "eigene Zusage" in text and "Bestätigte Zuständigkeit der verknüpften Aufgabe: Alex <alex@example.invalid>" in text
        assert links[0]["episode_id"] == "synthetic-source"


@pytest.mark.parametrize("old_quote,new_quote,source_text,requires_review", [
    ("ABCX", "CXYZ", "ABCX | CXYZ | ABCXYZ", True),  # first occurrences are disjoint
    ("ABCX", "XYZ", "ABCXXYZ", False),  # exact adjacency is disjoint
    ("ABCX", "XYZ", "ABCX " * 129 + "XYZ", True),  # occurrence budget cannot prove disjointness
    ("ABCX", "XYZ", "ABCX" + " " * 256_000 + "XYZ", True),  # source budget
    ("ABCX", "XYZ", "XYZ", True),  # old citation absent from the supplied text
    ("ABCX", "XYZ", None, True),  # no complete source text
    (None, "XYZ", "ABCXXYZ", True),  # prior corrected task did not have a citation
])
def test_source_span_review_limits_are_fail_closed(tmp_path, old_quote, new_quote, source_text, requires_review):
    store = TaskStore(tmp_path / "bounded-citations.db")
    try:
        source_ref = "episode:synthetic-bounded"
        previous = store.from_suggestion("previous", "Ursprüngliche Aufgabe",
            Provenance(SourceType.EMAIL, source_ref=source_ref, verbatim=old_quote))
        decide(store, previous)
        incoming = Provenance(SourceType.EMAIL, source_ref=source_ref, verbatim=new_quote)
        if requires_review:
            with pytest.raises(TaskRequestConflict, match="Quellenstelle"):
                store.from_suggestion("incoming", "Neue Formulierung", incoming, source_text=source_text)
            assert len(store.open_tasks()) == 1
        else:
            created = store.from_suggestion("incoming", "Getrennte Aufgabe", incoming, source_text=source_text)
            assert created.id != previous.id and created.user_actionable
    finally:
        store.close()
