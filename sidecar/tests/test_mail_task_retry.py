"""A response lost after saving must not duplicate a manually reviewed mail task."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from icarus_memory.connectors.mail import Message
from icarus_memory.mail_task_suggestions import source_digest
from icarus_memory.server import create_app


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'synthetic-app'))
    app = create_app()
    message = Message(uid='work:1', account_id='work', subject='Bericht',
                      sender='Tom <tom@example.test>', date=None, preview='',
                      unread=False, body='Bitte sende Tom den Bericht bis Freitag.')
    mail = SimpleNamespace(current=message)
    mail.message = lambda uid: mail.current
    app.state.mail = mail
    payload = {'title': 'Bericht an Tom senden', 'waiting_for': 'Lea',
               'source_digest': source_digest(message), 'source_quote': message.body,
               'request_id': 'c86d7171-3baa-4f6c-a2f2-c40809fe336d'}
    with TestClient(app) as client:
        yield app, mail, client, payload


def test_retry_after_lost_response_keeps_one_task(setup):
    app, mail, client, payload = setup
    # The first save completed, but its response did not reach the caller.
    first = client.post('/api/v1/messages/work:1/task', json=payload)
    assert first.status_code == 201, first.text
    retry = client.post('/api/v1/messages/work:1/task', json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()['id'] == first.json()['id']
    assert len(app.state.tasks.all_tasks()) == 1
    assert retry.json()['wartet_auf'] == 'Lea'


def test_retry_after_restart_preserves_completed_task(setup):
    app, mail, client, payload = setup
    first = client.post('/api/v1/messages/work:1/task', json=payload).json()
    app.state.tasks.complete(first['id'])
    app.state.tasks.edit(first['id'], title='Später ausdrücklich bearbeitet')
    restarted = create_app()
    restarted.state.mail = mail
    with TestClient(restarted) as new_client:
        retry = new_client.post('/api/v1/messages/work:1/task', json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()['id'] == first['id']
    assert retry.json()['status'] == 'done'
    assert retry.json()['title'] == 'Später ausdrücklich bearbeitet'
    assert len(restarted.state.tasks.all_tasks()) == 1


@pytest.mark.parametrize('change', [
    {'title': 'Anderer Auftrag'}, {'waiting_for': 'Tom'},
    {'due': '2026-10-12T10:00:00Z'}, {'source_quote': None},
])
def test_saved_request_cannot_be_rebound_to_changed_fields(setup, change):
    app, mail, client, payload = setup
    first = client.post('/api/v1/messages/work:1/task', json=payload)
    assert first.status_code == 201
    retry = client.post('/api/v1/messages/work:1/task', json={**payload, **change})
    assert retry.status_code == 409, retry.text
    assert len(app.state.tasks.all_tasks()) == 1


def test_retry_still_rejects_changed_or_withdrawn_source(setup):
    app, mail, client, payload = setup
    first = client.post('/api/v1/messages/work:1/task', json=payload).json()
    original = mail.current
    mail.current = replace(original, body='Der Bericht ist nicht mehr nötig.')
    assert client.post('/api/v1/messages/work:1/task', json=payload).status_code == 409
    mail.current = original
    episode_id = first['provenance']['source_ref'].removeprefix('episode:')
    app.state.episodes.ignore(episode_id)
    assert client.post('/api/v1/messages/work:1/task', json=payload).status_code == 409
    assert len(app.state.tasks.all_tasks()) == 1


def test_new_explicit_request_may_create_an_identical_task(setup):
    app, mail, client, payload = setup
    first = client.post('/api/v1/messages/work:1/task', json=payload)
    second = client.post('/api/v1/messages/work:1/task', json={**payload,
        'request_id': '754f9a2a-0232-4e5c-b276-21bfdf5631f4'})
    assert first.status_code == second.status_code == 201
    assert first.json()['id'] != second.json()['id']
    assert len(app.state.tasks.all_tasks()) == 2
