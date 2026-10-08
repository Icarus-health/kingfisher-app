"""List all matching tasks without hidden global caps or stale offset pages."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore

P = Provenance(source_type=SourceType.USER_STATED)


def test_view_filters_before_page_limit_and_every_page_is_reachable(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    for n in range(205):
        task = store.add(f'Waiting {n}', P)
        store.warten_auf(task.id, 'Anna')
    expected = {store.add(f'My {n}', P).id for n in range(103)}
    seen, cursor = [], None
    while True:
        page = store.page('mine', limit=25, cursor=cursor)
        assert page['total'] == 103
        assert len(page['tasks']) <= 25
        seen.extend(t['id'] for t in page['tasks'])
        cursor = page['next_cursor']
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 103
    assert set(seen) == expected
    waiting = store.page('waiting', q='Anna', limit=25)
    assert waiting['total'] == 205 and len(waiting['tasks']) == 25
    store.close()


def test_completed_and_project_search_are_not_limited_by_other_tasks(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    target = store.add('Straße prüfen 100%_fertig', P, notes='Änderung des Angebots', project_id='project-a')
    store.complete(target.id)
    for n in range(505):
        store.add(f'Unrelated {n}', P, project_id='project-b')
    page = store.page('done', q='STRASSE ÄNDERUNG 100%_', project_id='project-a')
    assert [t['id'] for t in page['tasks']] == [target.id]
    assert page['total'] == 1 and page['next_cursor'] is None
    assert store.page('done', q='STRASSE', project_id='project-b')['total'] == 0
    store.close()


def test_changed_or_reused_cursor_is_rejected_across_store_connections(tmp_path):
    path = tmp_path / 'tasks.db'
    store = TaskStore(path)
    first = store.add('Offer', P)
    store.add('Second offer', P)
    cursor = store.page('mine', limit=1)['next_cursor']
    for kwargs in ({'view': 'done'}, {'view': 'mine', 'q': 'offer'}, {'view': 'mine', 'limit': 2}):
        with pytest.raises(ValueError):
            store.page(cursor=cursor, **({'limit': 1} | kwargs))
    other = TaskStore(path)
    other.edit(first.id, title='Changed offer')
    with pytest.raises(ValueError, match='geändert'):
        store.page('mine', limit=1, cursor=cursor)
    assert store.page('mine', limit=1)['total'] == 2
    other.close()
    store.close()


def test_page_order_uses_actual_due_instants_and_stable_ties(tmp_path):
    store = TaskStore(tmp_path / 'tasks.db')
    later = store.add('Later', P, due=datetime(2030, 1, 1, 9, tzinfo=timezone.utc))
    earlier = store.add('Earlier', P, due=datetime(2030, 1, 1, 10, tzinfo=timezone(timedelta(hours=2))))
    assert [t['id'] for t in store.page('mine')['tasks']] == [earlier.id, later.id]
    for bad in ('', 'not-json', 'e30='):
        with pytest.raises(ValueError):
            store.page('mine', cursor=bad)
    for bad in (0, 201, True):
        with pytest.raises(ValueError):
            store.page('mine', limit=bad)
    store.close()


def test_task_page_api_exposes_counts_search_and_changed_snapshot():
    app = create_app()
    with TestClient(app) as client:
        a = app.state.tasks.add('Angebot prüfen', P)
        app.state.tasks.add('Angebot senden', P)
        response = client.get('/api/v1/tasks', params={'q': 'Angebot', 'limit': 1})
        assert response.status_code == 200
        page = response.json()
        assert page['total'] == 2 and page['next_cursor']
        app.state.tasks.complete(a.id)
        assert client.get('/api/v1/tasks', params={'q': 'Angebot', 'limit': 1, 'cursor': page['next_cursor']}).status_code == 409
        assert client.get('/api/v1/tasks', params={'cursor': 'invalid'}).status_code == 422
        assert client.get('/api/v1/tasks', params={'q': 'x' * 201}).status_code == 422
