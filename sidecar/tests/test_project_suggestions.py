"""Projektvorschläge aus eigenen Zuordnungen: angezeigt, nie selbst angewendet."""
import pytest
from fastapi.testclient import TestClient

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.project_suggestions import for_episode, same_sender
from icarus_memory.server import create_app
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app


@pytest.fixture
def app_client(core, tmp_path, monkeypatch):  # noqa: F811
    agent, *_ = core
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'token')
    app = create_app(agent._store, agent=agent)
    client = TestClient(app, headers={'X-Icarus-Token': 'token'})
    yield app, client
    client.close()
    _close_app(app)


def mail(app, n, sender='Anna Keller <anna@example.test>', account='work', project=None, participants=None):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, f'Mail {n}', f'Inhalt {n}',
        Provenance(SourceType.EMAIL, source_ref=f'{account}:<{n}@example.test>'),
        participants=participants or [sender], project_id=project)
    return episode


def projects(app):
    make = lambda name: app.state.workspace.add_project(name, Provenance(SourceType.USER_STATED)).id
    return make('Mainz'), make('Orion')


def test_same_sender_means_same_account_and_single_sender(app_client):
    app, _ = app_client
    target = mail(app, 1)
    peer = mail(app, 2, sender='ANNA@example.test')
    mail(app, 3, account='privat')
    mail(app, 4, participants=['anna@example.test', 'ben@example.test'])
    ignored = mail(app, 5)
    app.state.episodes.ignore(ignored.id)
    mail(app, 6, sender='anna2@example.test')
    assert [e.id for e in same_sender(app.state.episodes, target)] == [peer.id]


def test_suggestion_needs_two_agreeing_assignments(app_client):
    app, _ = app_client
    mainz, orion = projects(app)
    names = {mainz: 'Mainz', orion: 'Orion'}
    target = mail(app, 1)
    mail(app, 2, project=mainz)
    assert for_episode(app.state.episodes, target, names)['suggestion'] is None
    mail(app, 3, project=mainz)
    mail(app, 4)
    found = for_episode(app.state.episodes, target, names)
    assert found == {'suggestion': {'project_id': mainz, 'name': 'Mainz', 'count': 2},
                     'unassigned_peers': 1, 'sender': 'Anna Keller'}
    mail(app, 5, project=orion)
    assert for_episode(app.state.episodes, target, names)['suggestion'] is None
    app.state.episodes.link_project(target.id, mainz)
    assert for_episode(app.state.episodes, app.state.episodes.get(target.id), names)['suggestion'] is None


def test_same_sender_assignment_only_on_click_and_undo_respects_later_changes(app_client):
    app, client = app_client
    mainz, orion = projects(app)
    target = mail(app, 1)
    loose = [mail(app, n) for n in (2, 3)]
    elsewhere = mail(app, 4, project=orion)
    other = mail(app, 5, sender='ben@example.test')
    assert client.get(f'/api/v1/episodes/{target.id}/project-suggestion').json()['unassigned_peers'] == 2
    assert client.put(f'/api/v1/episodes/{target.id}/project', json={'project_id': mainz}).status_code == 200
    # Die übrigen Mails bleiben ohne Projekt, bis der Nutzer zustimmt.
    assert all(app.state.episodes.get(e.id).project_id is None for e in loose)

    response = client.post(f'/api/v1/episodes/{target.id}/project/same-sender', json={'project_id': mainz})
    assert response.status_code == 200 and sorted(response.json()['changed']) == sorted(e.id for e in loose)
    assert app.state.episodes.get(elsewhere.id).project_id == orion
    assert app.state.episodes.get(other.id).project_id is None
    assert any(entry['tool'] == 'quellen_projekt_zuordnen' for entry in app.state.audit.entries())

    app.state.episodes.link_project(loose[0].id, orion)  # zwischendurch selbst umgehängt
    undo = client.put('/api/v1/episodes/projects', json={
        'episode_ids': response.json()['changed'], 'project_id': None, 'only_if_project_id': mainz})
    assert undo.json()['changed'] == [loose[1].id]
    assert app.state.episodes.get(loose[0].id).project_id == orion
    assert app.state.episodes.get(loose[1].id).project_id is None

    assert client.post(f'/api/v1/episodes/{target.id}/project/same-sender', json={'project_id': None}).status_code == 422
    assert client.post(f'/api/v1/episodes/{target.id}/project/same-sender', json={'project_id': 'p-x'}).status_code == 404
    assert client.get('/api/v1/episodes/e-unbekannt/project-suggestion').status_code == 404
