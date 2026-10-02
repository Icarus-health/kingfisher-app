"""Abschlüsse sind belegte Zustandswechsel, keine falschen Zielangaben."""
import pytest
from fastapi.testclient import TestClient
from icarus_memory.server import create_app


@pytest.mark.parametrize("outcome", ["achieved", "stopped"])
def test_goal_finish_preserves_history_and_removes_open_goal(outcome):
    app = create_app()
    client = TestClient(app)
    goal = client.post('/assertions', json={"statement": "Buch schreiben", "kind": "goal",
        "provenance": {"source_type": "user_stated"}}).json()
    response = client.post(f'/goals/{goal["id"]}/finish', json={"outcome": outcome, "note": "Meine Entscheidung"})
    assert response.status_code == 200
    finished = response.json()
    assert finished['kind'] == 'state'
    assert finished['provenance']['source_type'] == 'user_stated'
    listing = client.get('/goals').json()
    assert listing['items'] == []
    assert listing['completed'][0]['outcome'] == outcome
    assert listing['completed'][0]['note'] == 'Meine Entscheidung'
    history = client.get(f'/assertions/{finished["id"]}/history').json()
    assert [item['status'] for item in history] == ['superseded', 'active']
    assert history[0]['statement'] == 'Buch schreiben'
    before = len(app.state.store.alles())
    assert client.post(f'/goals/{goal["id"]}/finish', json={"outcome": outcome}).status_code == 409
    assert len(app.state.store.alles()) == before
    app.state.store.redact(goal['id'])
    assert client.get('/goals').json()['completed'] == []
    assert finished['id'] not in [a.id for a in app.state.store.usable()]


def test_goal_finish_rejects_non_goal_and_unknown_outcome():
    app = create_app()
    client = TestClient(app)
    assertion = client.post('/assertions', json={"statement": "Eine Angabe", "kind": "state",
        "provenance": {"source_type": "user_stated"}}).json()
    assert client.post(f'/goals/{assertion["id"]}/finish', json={"outcome": "achieved"}).status_code == 409
    assert client.post('/goals/missing/finish', json={"outcome": "invented"}).status_code == 422
    assert len(app.state.store.alles()) == 1


@pytest.mark.parametrize("outcome", ["achieved", "stopped"])
def test_reopen_goal_keeps_completion_and_rejects_duplicate(outcome):
    app = create_app()
    client = TestClient(app)
    goal = client.post('/assertions', json={"statement": "Buch schreiben", "kind": "goal", "tags": ["Buch"],
        "sensitivity": "sensitive", "provenance": {"source_type": "user_stated"}}).json()
    finished = client.post(f'/goals/{goal["id"]}/finish', json={"outcome": outcome}).json()
    response = client.post(f'/goals/{finished["id"]}/reopen')
    assert response.status_code == 200
    reopened = response.json()
    assert reopened['statement'] == 'Buch schreiben'
    assert reopened['tags'] == ['Buch']
    assert reopened['sensitivity'] == 'sensitive'
    assert reopened['id'] != goal['id']
    assert client.get('/goals').json()['completed'] == []
    assert [item['id'] for item in client.get('/goals').json()['items']] == [reopened['id']]
    history = client.get(f'/assertions/{reopened["id"]}/history').json()
    assert [item['id'] for item in history] == [goal['id'], finished['id'], reopened['id']]
    assert history[1]['structured']['goal_outcome'] == outcome
    assert client.post(f'/goals/{finished["id"]}/reopen').status_code == 409
    assert len(app.state.store.alles()) == 3
    app.state.store.redact(goal['id'])
    assert client.get('/goals').json()['items'] == []


def test_reopen_rejects_unrelated_state():
    app = create_app()
    client = TestClient(app)
    assert client.post('/goals/unknown/reopen').status_code == 409
    assert app.state.store.alles() == []
