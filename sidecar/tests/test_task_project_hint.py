from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.server import create_app


def test_explicit_source_project_prefills_one_confirmation_without_model(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()
    episode, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Atlas', 'Bitte prüfe den Vertragsentwurf.', Provenance(source_type=SourceType.EMAIL))
    app.state.episodes.link_project(episode.id, project['id'])
    app.state.proposals.record_task_analysis(episode.id, episode.digest, [{'title': 'Vertrag prüfen', 'quote': episode.body}], proposed_by='test/local')
    page = client.get('/api/v1/task-candidates/page').json()
    hint = page['items'][0].get('project_suggestion')
    assert hint is not None
    assert hint['project_id'] == project['id']
    assert hint['origin'] == 'user_source'
    assert client.get('/api/v1/task-candidates/page').json()['items'][0]['project_suggestion'] == hint
    app.state.episodes.ignore(episode.id)
    assert client.get('/api/v1/task-candidates/page').json()['items'] == []


def test_local_hint_is_cached_and_invalidated_before_display(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from icarus_memory.providers import Reply
    from icarus_memory.task_project_hints import TaskProjectHints
    import threading
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()
    source, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Atlas Vertrag', 'Bitte prüfe den Atlas Vertrag.', Provenance(source_type=SourceType.DOCUMENT))
    app.state.proposals.record_task_analysis(source.id, source.digest, [{'title': 'Vertrag prüfen', 'quote': source.body}], proposed_by='test/local')
    candidate = app.state.proposals.pending(ProposalKind.TASK)[0]
    calls = []
    def complete(messages, tools):
        calls.append(messages)
        return Reply(text=json.dumps({'project_id': project['id'], 'new_project_name': None,
                                     'reason': 'Atlas Vertrag in der Quelle', 'quote': source.body}))
    service = TaskProjectHints(app.state.episodes, app.state.proposals, app.state.workspace, app.state.workspace_views, threading.RLock())
    assert service.prepare(SimpleNamespace(is_local=False, complete=complete)) == 0
    assert service.visible(candidate) is None
    service.prepare(SimpleNamespace(is_local=True, complete=complete))
    assert service.visible(candidate)['project_id'] == project['id']
    assert client.get('/api/v1/task-candidates/page').json()['items'][0]['project_suggestion']['origin'] == 'local_model'
    service.prepare(SimpleNamespace(is_local=True, complete=complete))
    assert len(calls) == 1
    app.state.episodes.ignore(source.id)
    assert service.visible(candidate) is None
    assert client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title':'Prüfen', 'new_project_name':'Neu'}).status_code == 409
    assert len(client.get('/api/v1/projects').json()) == 1


def test_confirmed_new_project_and_task_are_replay_safe(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    client = TestClient(app)
    source, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Bericht', 'Bitte prüfe den Vertragsentwurf.', Provenance(source_type=SourceType.DOCUMENT))
    app.state.proposals.record_task_analysis(source.id, source.digest, [{'title':'Prüfen', 'quote':source.body}], proposed_by='test/local')
    candidate = app.state.proposals.pending(ProposalKind.TASK)[0]
    url = f'/api/v1/task-candidates/{candidate.id}/accept'
    accepted = client.post(url, json={'title':'Prüfen', 'new_project_name':'Atlas'}).json()
    assert accepted['project_id'].startswith('p-task-')
    assert client.post(url, json={'title':'Andere Eingabe', 'new_project_name':'Anderes'}).json() == accepted
    assert len(app.state.workspace.projects()) == 1
    assert len(app.state.tasks.all_tasks()) == 1
