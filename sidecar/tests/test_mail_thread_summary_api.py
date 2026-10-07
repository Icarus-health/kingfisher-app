"""The HTTP boundary rechecks the whole thread, not just the opened body."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import local_model_guard, mail_briefing
from icarus_memory.mail_ingestion import remember
from icarus_memory.server import create_app
from tests.test_mail_thread import mail
from tests.test_mail_thread_summary import Model


@pytest.fixture
def runtime(monkeypatch):
    app = create_app()
    model = Model()
    opened = mail('2', mid='<new@test>', reply='<old@test>', day=2, body='Die Prüfung entfällt. Bitte nichts versenden.')
    old = remember(app.state.episodes, mail('1', mid='<old@test>', day=1))['episode']
    messages = {'opened': opened, 'reads': 0}
    def read(uid):
        messages['reads'] += 1
        return messages['opened']
    app.state.mail = SimpleNamespace(message=read)
    monkeypatch.setattr(mail_briefing, '_provider', lambda app: model)
    monkeypatch.setattr(local_model_guard, 'verify_local_model', lambda provider, **kw:
        local_model_guard.LocalModelIdentity(provider.model, 'a' * 64))
    with TestClient(app) as client:
        yield app, client, model, messages, old


def snapshot(client):
    return client.get('/api/v1/messages/work:2/thread').json()['context_fingerprint']


def test_summary_is_read_only_and_bound_to_every_thread_source(runtime):
    app, client, model, messages, old = runtime
    stand = snapshot(client)
    before = app.state.episodes.counts()
    messages['reads'] = 0
    response = client.post('/api/v1/messages/work:2/thread-summary', json={'context_fingerprint': stand})
    assert response.status_code == 200
    result = response.json()
    assert result['context_fingerprint'] == stand
    assert result['selection_review'] == 'proposed' and result['semantic_validation'] is False
    assert result['items'][0]['quote'] == messages['opened'].body
    assert len(model.calls) == 1
    assert messages['reads'] == 2  # guard checks do not repeatedly download the mail
    assert app.state.episodes.counts() == before
    assert app.state.tasks.open_tasks() == []


def test_changed_thread_is_rejected_before_model(runtime):
    app, client, model, messages, old = runtime
    stand = snapshot(client)
    app.state.episodes.ignore(old['id'])
    response = client.post('/api/v1/messages/work:2/thread-summary', json={'context_fingerprint': stand})
    assert response.status_code == 409
    assert model.calls == []


def test_withdraw_and_reopen_requires_a_fresh_thread_snapshot(runtime):
    app, client, model, messages, old = runtime
    stand = snapshot(client)
    app.state.episodes.ignore(old['id'])
    app.state.episodes.reopen(old['id'])
    response = client.post('/api/v1/messages/work:2/thread-summary', json={'context_fingerprint': stand})
    assert response.status_code == 409
    assert model.calls == []


@pytest.mark.parametrize('change', ['withdraw', 'body', 'reader'])
def test_changes_during_model_never_return_old_quotes(runtime, change):
    app, client, model, messages, old = runtime
    stand = snapshot(client)
    def effect():
        if change == 'withdraw':
            app.state.episodes.ignore(old['id'])
        elif change == 'body':
            messages['opened'] = replace(messages['opened'], body='Die Nachricht wurde geändert.')
        else:
            app.state.mail = SimpleNamespace(message=lambda uid: messages['opened'])
    model.effect = effect
    response = client.post('/api/v1/messages/work:2/thread-summary', json={'context_fingerprint': stand})
    assert response.status_code == 409
    assert 'Die Prüfung entfällt' not in response.text


def test_cloud_provider_never_gets_thread_data(runtime):
    app, client, model, messages, old = runtime
    model.is_local = False
    response = client.post('/api/v1/messages/work:2/thread-summary', json={'context_fingerprint': snapshot(client)})
    assert response.status_code == 200
    assert response.json()['available'] is False
    assert response.json()['items'] == []
    assert model.calls == []
