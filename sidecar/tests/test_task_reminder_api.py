"""Reminders are task dates, not changed deadlines or completed work."""
from fastapi.testclient import TestClient
from icarus_memory.server import create_app


def test_reminder_api_retains_deadline_waiting_and_other_fields():
    app = create_app()
    with TestClient(app) as client:
        task = client.post('/api/v1/tasks', json={'title': 'Synthetic follow-up',
                           'due': '2030-01-01T12:00:00Z', 'notes': 'Keep'}).json()
        path = '/api/v1/tasks/' + task['id']
        client.post(path + '/warten', json={'name': 'Synthetic person'})
        result = client.patch(path, json={'remind_at': '2020-01-01T09:00:00Z'})
        assert result.status_code == 200
        assert result.json()['remind_at'] is not None
        assert result.json()['due'] == task['due']
        assert result.json()['wartet_auf'] == 'Synthetic person'
        response = client.get('/api/v1/tasks/reminders')
        assert response.status_code == 200
        assert [t['id'] for t in response.json()['items']] == [task['id']]
        client.patch(path, json={'notes': 'Still no reminder change'})
        assert client.get(path).json()['remind_at'] is not None
        client.patch(path, json={'remind_at': None})
        assert client.get('/api/v1/tasks/reminders').json()['items'] == []
        assert client.get(path).json()['status'] == 'open'
        assert client.get(path).json()['due'] == task['due']


def test_reminder_api_list_limit_does_not_hide_old_unlisted_task():
    app = create_app()
    with TestClient(app) as client:
        for n in range(205):
            task = client.post('/api/v1/tasks', json={'title': f'Synthetic {n}'}).json()
        client.patch('/api/v1/tasks/' + task['id'], json={'remind_at': '2020-01-01T00:00:00Z'})
        assert task['id'] not in {t['id'] for t in client.get('/api/v1/tasks').json()['tasks']}
        result = client.get('/api/v1/tasks/reminders').json()
        assert [t['id'] for t in result['items']] == [task['id']]
        assert result['truncated'] is False
        assert client.get('/api/v1/tasks/reminders?limit=0').status_code == 422


def test_old_today_reminder_does_not_clear_a_newer_reminder():
    app = create_app()
    with TestClient(app) as client:
        task = client.post('/api/v1/tasks', json={'title': 'Synthetic stale view'}).json()
        path = '/api/v1/tasks/' + task['id']
        old = client.patch(path, json={'remind_at': '2020-01-01T09:00:00Z'}).json()
        new = client.patch(path, json={'remind_at': '2030-01-01T09:00:00Z'}).json()
        response = client.patch(path, json={'remind_at': None, 'expected_remind_at': old['remind_at']})
        assert response.status_code == 409
        assert client.get(path).json()['remind_at'] == new['remind_at']
        assert client.patch(path, json={'remind_at': None, 'expected_remind_at': new['remind_at']}).status_code == 200


def test_a_completed_task_cannot_receive_a_new_active_reminder():
    app = create_app()
    with TestClient(app) as client:
        task = client.post('/api/v1/tasks', json={'title': 'Synthetic completed follow-up'}).json()
        path = '/api/v1/tasks/' + task['id']
        task = client.patch(path, json={'remind_at': '2020-01-01T09:00:00Z'}).json()
        client.post(path + '/done')
        response = client.patch(path, json={'remind_at': '2030-01-01T09:00:00Z', 'expected_remind_at': task['remind_at']})
        assert response.status_code == 409
        assert client.get(path).json()['remind_at'] == task['remind_at']
