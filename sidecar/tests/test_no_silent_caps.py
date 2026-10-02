"""Ältere Quellen fallen nicht still aus Graph, Akten, Verzeichnis und Urteil.

Früher lasen diese Ansichten nur die neuesten 5000 (Urteil: 500) Quellen.
Bei ein paar Jahren Mail verschwanden ältere Kontakte, Projektquellen und die
letzte Spur eines Vorhabens, ohne dass es irgendwo stand.
"""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import Kind, MemoryBackend, Provenance, SelfModelStore, SourceType
from icarus_memory import graph, personen, urteil
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

JETZT = datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc)
NEUERE = 5001
ALTE = 'Alte Bekannte <alt@example.test>'


@pytest.fixture(scope='module')
def bestand(tmp_path_factory):
    path = tmp_path_factory.mktemp('caps')
    episodes = EpisodeStore(path / 'episodes.sqlite3')
    workspace = WorkspaceStore(path / 'workspace.sqlite3')
    tasks = TaskStore(path / 'tasks.sqlite3')
    store = SelfModelStore(MemoryBackend(), subject_id='t')
    project = workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
    # Die älteste Quelle: einzige Spur der alten Bekannten und des Vorhabens.
    oldest, _ = episodes.record(EpisodeKind.MESSAGE, 'Umstellung', 'Die Umstellung läuft an.',
                                Provenance(SourceType.EMAIL, source_ref='mail:<alt>'),
                                occurred_at=JETZT - timedelta(days=50), participants=[ALTE],
                                tags=['umstellung'], project_id=project.id)
    for n in range(NEUERE):
        episodes.record(EpisodeKind.MESSAGE, f'Mail {n}', f'Neuere Nachricht {n}.',
                        Provenance(SourceType.EMAIL, source_ref=f'mail:<{n}>'),
                        occurred_at=JETZT - timedelta(minutes=n + 1),
                        participants=['Viel Schreiber <viel@example.test>'], project_id=project.id)
    store.record('Die Praxisumstellung abschließen.', Kind.GOAL,
                 Provenance(source_type=SourceType.USER_STATED, captured_at=JETZT),
                 tags=['umstellung'], at=JETZT - timedelta(days=120))
    yield episodes, workspace, tasks, store, project, oldest
    episodes.close()


def test_graph_keeps_oldest_source_and_person(bestand):
    episodes, workspace, tasks, store, _, oldest = bestand
    built = graph.build(episodes=episodes, workspace=workspace, tasks=tasks, store=store, at=JETZT).to_dict()
    ids = {node['id'] for node in built['nodes']}
    assert graph.person_id('Alte Bekannte') in ids or any(
        node['label'].startswith('Alte Bekannte') for node in built['nodes'] if node['kind'] == 'person')
    assert any(oldest.id in node['id'] for node in built['nodes'])


def test_person_profile_and_directory_reach_the_oldest_contact(bestand):
    episodes, workspace, tasks, store, _, oldest = bestand
    directory = personen.alle(episodes=episodes, tasks=tasks, store=store, workspace=workspace, jetzt=JETZT)
    assert any(person.name.startswith('Alte Bekannte') for person in directory)
    name = next(person.name for person in directory if person.name.startswith('Alte Bekannte'))
    profile = graph.person_profile(name, episodes=episodes, workspace=workspace, tasks=tasks,
                                   store=store, at=JETZT)
    assert [item['id'] for item in profile['interactions']] == [oldest.id]


def test_project_profile_lists_every_source_newest_first(bestand):
    episodes, workspace, tasks, _, project, oldest = bestand
    profile = graph.project_profile(project.id, episodes=episodes, workspace=workspace, tasks=tasks)
    assert len(profile['episodes']) == NEUERE + 1
    assert profile['episodes'][-1]['id'] == oldest.id
    assert any(person['name'].startswith('Alte Bekannte') for person in profile['people'])


def test_goal_behind_many_newer_sources_is_still_judged(bestand):
    episodes, _, tasks, store, _, _ = bestand
    [vorhaben] = urteil.vorhaben(store=store, episodes=episodes, tasks=tasks, jetzt=JETZT)
    assert vorhaben.letzte_regung is not None
    assert vorhaben.tage_still(JETZT) == 50
    assert vorhaben.schlaeft(JETZT)


def test_each_episode_reads_everything_in_pages(bestand):
    episodes = bestand[0]
    assert sum(1 for _ in episodes.each_episode(page=700)) == NEUERE + 1
