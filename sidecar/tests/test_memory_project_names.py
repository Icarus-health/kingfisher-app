"""Vom Nutzer zugeordnete Projekte helfen beim Finden, ohne etwas zu behaupten."""
import json

import pytest

from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.working_memory_answers import (
    MAX_REFS, _fresh, choices, choose, mentioned_projects, prepare, render)
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation
from tests.test_working_memory_flow import run_working

PROJECTS = [('p-mainz', 'Mainz'), ('p-orion', 'Orion'), ('p-ab', 'AB')]


class Selector:
    """Wählt alles und merkt sich, was das Modell zu sehen bekam."""
    is_local = True

    def __init__(self, status='source_reports'):
        self.status, self.rows = status, None

    def complete_json(self, messages, **kwargs):
        self.rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': self.status, 'ids': [row['id'] for row in self.rows]}))


@pytest.fixture
def stores(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield episodes, claims
    claims.close()
    episodes.close()


def _source(episodes, body, *, title='Nachricht', project=None):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, title, body, Provenance(SourceType.EMAIL),
                                 participants=['Anna <anna@example.test>'], project_id=project)
    assert WorkingMemoryStore(episodes).commit(
        episodes.support_snapshot(episode.id), [{'start': 0, 'end': len(body), 'kind': 'fact'}],
        model='synthetic')
    return episode


def test_project_names_are_recognized_as_whole_words():
    assert mentioned_projects('Was gibt es Neues zu Mainz?', PROJECTS) == ['p-mainz']
    assert mentioned_projects('Wie steht der mainzer Entwurf?', PROJECTS) == ['p-mainz']
    assert mentioned_projects('Mainz oder Orion?', PROJECTS) == ['p-mainz', 'p-orion']
    assert mentioned_projects('Was sagen die Mainzelmännchen?', PROJECTS) == []
    assert mentioned_projects('Gibt es AB-Termine?', PROJECTS) == []
    assert mentioned_projects('Mainz?', [('p', None), ('q', '  ')]) == []


def test_question_with_project_name_finds_assigned_source_without_the_word(stores):
    episodes, claims = stores
    assigned = _source(episodes, 'Die Druckfreigabe kommt am Donnerstag.', project='p-mainz')
    _source(episodes, 'Orion braucht noch die Freigabe.', project='p-orion')
    question = 'Was gibt es Neues zu Mainz?'
    assert WorkingMemoryStore(episodes).search(question)['refs'] == []

    without = prepare(question, episodes, claims, Selector())
    assert without is None  # ohne Projektverzeichnis bleibt es bei der Wortsuche

    selector = Selector()
    answer = prepare(question, episodes, claims, selector, projects=PROJECTS)
    assert answer['project_scope'] == ['p-mainz']
    assert [ref['episode_id'] for ref in answer['refs']] == [assigned.id]
    assert selector.rows[0]['project'] == 'Mainz'
    text, _, status = render(answer, episodes, claims)
    assert 'Druckfreigabe' in text
    assert 'Zugeordnet: Projekt Mainz' in text and 'Orion' not in text

    episodes.link_project(assigned.id, None)
    assert not _fresh(answer, episodes, claims)


def test_project_sources_come_before_word_hits_elsewhere(stores):
    episodes, claims = stores
    elsewhere = [_source(episodes, f'Der Entwurf {n} liegt bei Orion.', project='p-orion') for n in range(MAX_REFS + 4)]
    inside = _source(episodes, 'Der Entwurf für die Messe ist fertig.', project='p-mainz')
    quiet = _source(episodes, 'Die Druckerei hat bestätigt.', project='p-mainz')
    answer = prepare('Wie weit ist der Entwurf in Mainz?', episodes, claims, Selector(), projects=PROJECTS)
    ids = [ref['episode_id'] for ref in answer['basis']]
    assert ids[:2] == [inside.id, quiet.id]
    assert len(ids) == MAX_REFS and answer['limited'] is True
    assert set(ids[2:]) <= {e.id for e in elsewhere}


def test_rows_without_directory_keep_opaque_id_only(stores):
    episodes, claims = stores
    _source(episodes, 'Die Druckfreigabe kommt am Donnerstag.', project='p-mainz')
    selector = Selector()
    prepare('Wann kommt die Druckfreigabe?', episodes, claims, selector)
    assert 'project' not in selector.rows[0] and selector.rows[0]['project_id'] == 'p-mainz'


def test_project_choice_offers_project_names(stores):
    episodes, claims = stores
    mainz = _source(episodes, 'Die Abnahme ist am 3. Oktober 2026.', title='Abnahme', project='p-mainz')
    orion = _source(episodes, 'Die Abnahme ist am 9. Oktober 2026.', title='Abnahme', project='p-orion')
    answer = prepare('Wann ist die Abnahme?', episodes, claims, Selector('needs_project_choice'),
                     projects=PROJECTS)
    assert answer['uncertainty'] == 'scope'
    labels = [option['label'] for option in choices(answer, episodes)]
    assert sorted(labels) == ['Projekt Mainz', 'Projekt Orion']
    chosen = choose(answer, labels.index('Projekt Orion'), episodes, claims)
    assert [ref['episode_id'] for ref in chosen['refs']] == [orion.id]
    text, _, _ = render(chosen, episodes, claims)
    assert '9. Oktober' in text and '3. Oktober' not in text and mainz.id not in text


def test_conversation_routes_project_question_to_memory(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        project = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        body = 'Die Druckfreigabe kommt am Donnerstag, 1. Oktober 2026.'

        def complete_json(messages, *, max_tokens, schema):
            data = json.loads(messages[-1]['content'])
            if 'blocks' in data:
                return Reply(text=json.dumps({'items': [
                    {'block_id': block['block_id'], 'kind': 'fact'} for block in data['blocks']]}))
            assert [row.get('project') for row in data['sources']] == ['Mainz']
            return Reply(text=json.dumps({'status': 'source_reports',
                                          'ids': [row['id'] for row in data['sources']]}))
        provider.complete_json = complete_json
        response = client.post('/api/v1/sources/documents', json={'filename': 'druck.txt', 'body': body})
        source = response.json()['id']
        run_working(app)
        conversation = _conversation(client)
        before = _ask(client, conversation, 'Was gibt es Neues zu Mainz?')
        assert 'Druckfreigabe' not in before['content']

        client.put(f'/api/v1/episodes/{source}/project', json={'project_id': project.id})
        reply = _ask(client, conversation, 'Was gibt es Neues zu Mainz?')
        assert 'Druckfreigabe' in reply['content']
        # Das Projekt ist gemeint: Die Antwort ist sein Stand der Dinge, und die
        # zugeordnete Quelle steht darin mit ihrem Link.
        assert reply['content'].startswith('Projekt Mainz · Stand der Dinge')
        assert [link['episode_id'] for link in reply['metadata']['context']['source_links']] == [source]
    finally:
        client.close()
        _close_app(app)
