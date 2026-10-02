"""Vom erkannten Versprechen zur ausdrücklich bestätigten Aufgabe."""
from fastapi.testclient import TestClient
import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalState


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    episode, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Angebot', 'Ich schicke das Angebot.', Provenance(source_type=SourceType.EMAIL))
    app.state.proposals.record_task_analysis(episode.id, episode.digest,
        [{'title': 'Angebot nachhalten', 'quote': episode.body}], proposed_by='test/local')
    candidate = app.state.proposals.pending(ProposalKind.TASK)[0]
    return app, TestClient(app), episode, candidate


def test_accept_creates_one_waiting_task_with_source_and_repeated_click_keeps_it(env):
    app, client, episode, candidate = env
    assert app.state.tasks.all_tasks() == []
    assert len(client.get('/api/v1/task-candidates').json()) == 1
    url = f'/api/v1/task-candidates/{candidate.id}/accept'
    response = client.post(url, json={'title': 'Angebot prüfen', 'waiting_for': 'Alex'})
    assert response.status_code == 200, response.text
    task = response.json()
    assert task['wartet_auf'] == 'Alex'
    assert task['provenance']['source_ref'] == f'episode:{episode.id}'
    assert task['provenance']['verbatim'] == episode.body
    assert client.post(url, json={'title': 'Geändert', 'waiting_for': 'Bea'}).json() == task
    assert len(app.state.tasks.all_tasks()) == 1
    assert client.get('/api/v1/task-candidates').json() == []
    assert list(app.state.store.alles()) == []
    assert app.state.claims.all_claims() == []


def test_source_revocation_and_invalid_project_leave_no_task(env):
    app, client, episode, candidate = env
    url = f'/api/v1/task-candidates/{candidate.id}/accept'
    assert client.post(url, json={'title': 'Prüfen', 'project_id': 'missing'}).status_code == 422
    app.state.episodes.ignore(episode.id)
    assert client.post(url, json={'title': 'Prüfen'}).status_code == 409
    assert app.state.tasks.all_tasks() == []
    assert client.get('/api/v1/task-candidates').json() == []
    assert app.state.proposals.get(candidate.id).state is ProposalState.SUPERSEDED


def test_rejected_candidate_cannot_be_accepted(env):
    app, client, episode, candidate = env
    root = f'/api/v1/task-candidates/{candidate.id}'
    assert client.post(root + '/reject').status_code == 200
    assert client.post(root + '/reject').status_code == 200
    assert client.post(root + '/accept', json={'title': 'Prüfen'}).status_code == 409
    assert app.state.tasks.all_tasks() == []


def test_interrupted_acceptance_recovers_without_duplicate_or_edit(env, monkeypatch):
    app, client, episode, candidate = env
    original = app.state.proposals.accept
    def fail(*args, **kwargs):
        raise RuntimeError('Simulierter Abbruch nach dem Speichern der Aufgabe')
    monkeypatch.setattr(app.state.proposals, 'accept', fail)
    url = f'/api/v1/task-candidates/{candidate.id}/accept'
    with pytest.raises(RuntimeError):
        client.post(url, json={'title': 'Original', 'waiting_for': 'Alex'})
    task = app.state.tasks.all_tasks()[0]
    assert client.post(f'/api/v1/task-candidates/{candidate.id}/reject').status_code == 409
    monkeypatch.setattr(app.state.proposals, 'accept', original)
    app.state.episodes.ignore(episode.id)
    assert client.get('/api/v1/task-candidates').json() == []
    assert app.state.proposals.get(candidate.id).state is ProposalState.ACCEPTED
    result = client.post(url, json={'title': 'Andere Eingabe'}).json()
    assert result['id'] == task.id
    assert result['title'] == 'Original'
    assert result['wartet_auf'] == 'Alex'
    assert len(app.state.tasks.all_tasks()) == 1


def test_wired_schedule_proposes_only_with_local_model(env):
    from types import SimpleNamespace
    from icarus_memory.server import _wire_scheduler
    from icarus_memory.providers import Reply
    import json
    app, client, episode, candidate = env
    text = 'Bitte prüfe den neuen Vertragsentwurf.'
    fresh, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Vertrag', text, Provenance(source_type=SourceType.DOCUMENT))
    calls = []
    def complete(messages, tools):
        calls.append(messages)
        body = json.loads(messages[1]['content'])['body']
        return Reply(text=json.dumps({'items': [{'title': 'Vertrag prüfen', 'quote': text}] if text in body else []}))
    app.state.agent = SimpleNamespace(provider=SimpleNamespace(is_local=True, name='test', model='local', complete=complete))
    _wire_scheduler(app)
    assert app.state.scheduler._run_task_detection(False).ok
    assert calls == []
    result = app.state.scheduler._run_task_detection(True)
    assert result.ok
    # Der alte Checkpoint hatte keinen Umfangsnachweis; er wird einmal mit
    # dem neuen Schema ausgewertet, ohne den bestehenden Vorschlag zu ändern.
    assert len(calls) == 2
    assert len(app.state.proposals.pending(ProposalKind.TASK)) == 2
    assert app.state.tasks.all_tasks() == []
    assert app.state.claims.all_claims() == []
    assert app.state.scheduler._run_task_detection(True).ok
    assert len(calls) == 2


def test_wired_schedule_discards_result_after_model_switch(env):
    from types import SimpleNamespace
    from icarus_memory.server import _wire_scheduler
    from icarus_memory.providers import Reply
    import json
    app, client, episode, candidate = env
    text = 'Bitte prüfe den neuen Vertragsentwurf.'
    fresh, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Vertrag', text, Provenance(source_type=SourceType.DOCUMENT))
    def complete(messages, tools):
        app.state.agent = SimpleNamespace(provider=None)
        return Reply(text=json.dumps({'items': [{'title': 'Vertrag prüfen', 'quote': text}]}))
    app.state.agent = SimpleNamespace(provider=SimpleNamespace(is_local=True, name='test', model='local', complete=complete))
    _wire_scheduler(app)
    result = app.state.scheduler._run_task_detection(True)
    assert 'gestoppt' in result.detail
    assert len(app.state.proposals.pending(ProposalKind.TASK)) == 1
    assert not app.state.proposals.task_analysis_done(fresh.id, fresh.digest)


@pytest.mark.parametrize('list_first', [False, True])
def test_archived_source_cannot_create_a_new_task(env, list_first):
    """Auch ein alter Übernahmeknopf darf keine archivierte Quelle reaktivieren."""
    from datetime import timedelta
    from icarus_memory.model import now
    app, client, episode, candidate = env
    app.state.episodes.mark_consolidated(episode.id)
    assert app.state.episodes.archive_before(now() + timedelta(days=1)) == 1
    if list_first:
        assert client.get('/api/v1/task-candidates').json() == []
        assert app.state.proposals.get(candidate.id).state is ProposalState.SUPERSEDED
    response = client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title': 'Angebot prüfen'})
    assert response.status_code == 409
    assert app.state.tasks.all_tasks() == []
    assert app.state.episodes.get(episode.id).body == 'Ich schicke das Angebot.'


def test_archiving_source_preserves_an_explicitly_adopted_task(env):
    """Quellenarchivierung ist kein Widerruf einer eigenen Aufgabenentscheidung."""
    from datetime import timedelta
    from icarus_memory.model import now
    app, client, episode, candidate = env
    url = f'/api/v1/task-candidates/{candidate.id}/accept'
    accepted = client.post(url, json={'title': 'Angebot prüfen'}).json()
    app.state.episodes.mark_consolidated(episode.id)
    assert app.state.episodes.archive_before(now() + timedelta(days=1)) == 1
    assert client.get('/api/v1/task-candidates').json() == []
    assert client.post(url, json={'title': 'Nicht überschreiben'}).json() == accepted
    assert len(app.state.tasks.all_tasks()) == 1
