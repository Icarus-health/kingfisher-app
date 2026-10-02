"""Editing task details updates the durable task without losing its identity."""

from datetime import datetime

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
from tests.test_conversation_retraction import _close_app


def test_task_edit_keeps_omitted_fields_and_records_durable_history(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="task-edit"))
    client = TestClient(app)
    project = client.post("/api/v1/projects", json={"name": "Atlas"}).json()
    task = client.post("/api/v1/tasks", json={
        "title": "Angebot prüfen", "due": "2026-10-02T21:59:00+00:00",
        "notes": "Preis und Laufzeit prüfen", "project_id": project["id"],
    }).json()
    client.post(f"/api/v1/tasks/{task['id']}/warten", json={"name": "Anna"})
    before = client.get(f"/api/v1/tasks/{task['id']}/history").json()["items"]

    edited = client.patch(f"/api/v1/tasks/{task['id']}", json={
        "title": "Angebot mit Anna abstimmen", "notes": "Preis, Laufzeit und Rabatt prüfen",
    })
    assert edited.status_code == 200
    current = edited.json()
    assert current["title"] == "Angebot mit Anna abstimmen"
    assert current["notes"] == "Preis, Laufzeit und Rabatt prüfen"
    assert current["due"] is not None
    assert datetime.fromisoformat(current["due"]) == datetime.fromisoformat("2026-10-02T21:59:00+00:00")
    assert current["project_id"] == project["id"]
    assert current["wartet_auf"] == "Anna"
    assert current["provenance"] == task["provenance"]
    assert current["created_at"] == task["created_at"]

    history = client.get(f"/api/v1/tasks/{task['id']}/history").json()["items"]
    assert len(history) == len(before) + 1
    assert history[0]["kind"] == "edited"
    assert history[0]["before"]["wartet_auf"] == "Anna"
    assert history[0]["after"]["wartet_auf"] == "Anna"
    assert "title" not in history[0]["before"] and "notes" not in history[0]["after"]

    # Omitted fields remain untouched; explicit null clears optional fields.
    cleared = client.patch(f"/api/v1/tasks/{task['id']}", json={"due": None, "notes": None})
    assert cleared.status_code == 200
    assert cleared.json()["due"] is None and cleared.json()["notes"] is None
    no_op = client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "Angebot mit Anna abstimmen"})
    assert no_op.status_code == 200
    history_after_noop = client.get(f"/api/v1/tasks/{task['id']}/history").json()["items"]
    assert len(history_after_noop) == len(history) + 1  # clearing was one edit; no-op added none
    assert history_after_noop[0]["kind"] == "edited"

    assert client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "   "}).status_code == 422
    assert client.patch("/api/v1/tasks/missing", json={"title": "Existiert nicht"}).status_code == 404
    client.close()
    _close_app(app)

    restarted = create_app(SelfModelStore(MemoryBackend(), subject_id="task-edit"))
    with TestClient(restarted) as after:
        loaded = after.get("/api/v1/tasks?view=waiting").json()["tasks"][0]
        assert loaded["id"] == task["id"]
        assert loaded["title"] == "Angebot mit Anna abstimmen"
        assert loaded["due"] is None and loaded["notes"] is None
        assert loaded["wartet_auf"] == "Anna"
        assert after.get(f"/api/v1/tasks/{task['id']}/history").json()["items"][0]["kind"] == "edited"
    _close_app(restarted)
