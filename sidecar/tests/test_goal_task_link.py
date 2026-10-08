"""A task keeps its explicit link to the goal it advances."""
import json
from fastapi.testclient import TestClient

from icarus_memory.model import Kind, Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore


def test_goal_id_round_trips_and_legacy_tasks_remain_unlinked(tmp_path):
    store = TaskStore(tmp_path / "tasks.db")
    legacy = store.add("Existing task", Provenance(source_type=SourceType.USER_STATED))
    linked = store.add("Write outline", Provenance(source_type=SourceType.USER_STATED), goal_id="a-goal")
    legacy_document = json.loads(store._conn.execute(
        "SELECT document FROM tasks WHERE id = ?", (legacy.id,)
    ).fetchone()[0])
    legacy_document.pop("goal_id")
    store._conn.execute("UPDATE tasks SET document = ? WHERE id = ?", (json.dumps(legacy_document), legacy.id))
    store._conn.close()

    reopened = TaskStore(tmp_path / "tasks.db")
    assert reopened.get(linked.id).goal_id == "a-goal"
    assert reopened.get(legacy.id).goal_id is None
    assert reopened.history(linked.id)[0]["after"]["goal_id"] == "a-goal"
    reopened._conn.close()


def test_task_api_accepts_only_open_goals_and_keeps_link_after_finish():
    app = create_app()
    with TestClient(app) as client:
        goal = client.post('/api/v1/assertions', json={
            'statement': 'Buch schreiben', 'kind': 'goal',
            'provenance': {'source_type': 'user_stated'},
        }).json()
        linked = client.post('/api/v1/tasks', json={
            'title': 'Kapitelplan erstellen', 'goal_id': goal['id'],
        })
        assert linked.status_code == 201
        assert linked.json()['goal_id'] == goal['id']
        assert client.get(f"/api/v1/tasks/{linked.json()['id']}").json()['goal_id'] == goal['id']

        finished = client.post(f"/api/v1/goals/{goal['id']}/finish", json={'outcome': 'achieved'})
        assert finished.status_code == 200
        assert client.get(f"/api/v1/tasks/{linked.json()['id']}").json()['goal_id'] == goal['id']

        legacy = client.post('/api/v1/tasks', json={'title': 'Unlinked task'})
        assert legacy.status_code == 201
        assert legacy.json()['goal_id'] is None


def test_task_api_rejects_missing_retracted_finished_and_non_goal_references():
    app = create_app()
    with TestClient(app) as client:
        non_goal = client.post('/api/v1/assertions', json={
            'statement': 'Heute müde', 'kind': 'state',
            'provenance': {'source_type': 'user_stated'},
        }).json()
        finished_goal = client.post('/api/v1/assertions', json={
            'statement': 'Altes Ziel', 'kind': 'goal',
            'provenance': {'source_type': 'user_stated'},
        }).json()
        client.post(f"/api/v1/goals/{finished_goal['id']}/finish", json={'outcome': 'stopped'})
        retracted_goal = client.post('/api/v1/assertions', json={
            'statement': 'Widerrufenes Ziel', 'kind': 'goal',
            'provenance': {'source_type': 'user_stated'},
        }).json()
        client.post(f"/api/v1/assertions/{retracted_goal['id']}/retract", json={'reason': 'Falsch'})
        habit = client.post('/api/v1/habits', json={'label': 'Lesen', 'target_per_week': 3}).json()

        for goal_id in ('missing', non_goal['id'], finished_goal['id'], retracted_goal['id'], habit['id']):
            response = client.post('/api/v1/tasks', json={'title': 'Nicht anlegen', 'goal_id': goal_id})
            assert response.status_code == 409, goal_id
        assert client.get('/api/v1/tasks?view=mine').json()['total'] == 0
