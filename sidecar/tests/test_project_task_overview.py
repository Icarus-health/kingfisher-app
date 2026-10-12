"""Project totals must describe the whole stored project, not a UI page."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore

P = Provenance(source_type=SourceType.USER_STATED)
AT = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)


def test_totals_cross_list_limits_and_separate_waiting_done_dropped(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    for n in range(205):
        store.add(f'Own {n}', P, project_id='p')
    overdue = store.add('Overdue', P, project_id='p', due=AT - timedelta(hours=1))
    waiting = store.add('Waiting', P, project_id='p', due=AT - timedelta(days=5))
    store.warten_auf(waiting.id, 'Anna', at=AT - timedelta(days=3))
    done = store.add('Done', P, project_id='p'); store.complete(done.id)
    dropped = store.add('Dropped', P, project_id='p'); store.drop(dropped.id)
    store.add('Other project', P, project_id='q', due=AT - timedelta(days=1))
    before = store.history(overdue.id)
    result = store.project_overview('p', at=AT)
    assert result['counts'] == {'mine': 206, 'waiting': 1, 'done': 1, 'dropped': 1, 'overdue': 1, 'undated': 205}
    assert len(result['next_tasks']) == 3
    assert result['next_tasks'][0]['id'] == overdue.id
    assert [t['id'] for t in result['waiting_tasks']] == [waiting.id]
    assert store.history(overdue.id) == before
    store.close()


def test_due_order_uses_instants_and_never_gives_undated_tasks_a_deadline(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    later = store.add('Later', P, project_id='p', due=AT + timedelta(hours=2))
    earlier = store.add('Earlier', P, project_id='p', due=(AT + timedelta(hours=1)).astimezone(timezone(timedelta(hours=3))))
    undated = store.add('No deadline', P, project_id='p')
    result = store.project_overview('p', at=AT)
    assert [t['id'] for t in result['next_tasks']] == [earlier.id, later.id, undated.id]
    assert result['next_tasks'][-1]['due'] is None
    assert result['counts']['overdue'] == 0
    assert result['counts']['undated'] == 1
    store.close()


def test_waiting_preview_oldest_first_and_completed_excluded(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    expected = []
    for days in (1, 5, 3, 2):
        task = store.add(str(days), P, project_id='p')
        store.warten_auf(task.id, 'Alex', at=AT - timedelta(days=days))
        expected.append((days, task.id))
    finished = store.add('Finished waiting', P, project_id='p')
    store.warten_auf(finished.id, 'Alex'); store.complete(finished.id)
    result = store.project_overview('p', at=AT)
    assert [t['id'] for t in result['waiting_tasks']] == [id for _, id in sorted(expected, reverse=True)[:3]]
    assert result['counts']['waiting'] == 4
    assert result['counts']['done'] == 1
    assert result['next_tasks'] == []
    store.close()


def test_overview_api_empty_closed_project_and_missing_project(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()['id']
    response = client.get(f'/api/v1/projects/{project}/task-overview')
    assert response.status_code == 200
    assert response.json()['counts'] == dict.fromkeys(('mine', 'waiting', 'done', 'dropped', 'overdue', 'undated'), 0)
    task = client.post('/api/v1/tasks', json={'title': 'Angebot prüfen', 'project_id': project}).json()['id']
    client.patch(f'/api/v1/projects/{project}', json={'status': 'done'})
    assert client.get(f'/api/v1/projects/{project}/task-overview').json()['next_tasks'][0]['id'] == task
    client.post(f'/api/v1/tasks/{task}/done')
    # Reopen a real SQLite connection, not merely a second request.
    reopened = TaskStore(tmp_path / 'tasks.sqlite3')
    assert reopened.project_overview(project)['counts']['done'] == 1
    reopened.close()
    assert client.get('/api/v1/projects/missing/task-overview').status_code == 404
