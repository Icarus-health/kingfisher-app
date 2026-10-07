"""Projektzuordnung ist Ablage, kein Beleg: Sie darf keine Einordnung entwerten."""
from datetime import datetime, timezone

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.working_memory_store import (
    WorkingMemoryStore, _item_id, _legacy_fingerprint, source_fingerprint)
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.working_memory_legacy import downgrade_terms
from tests.test_source_partial_correction import LIEFERUNG, _correct, partial  # noqa: F401 - Fixture


AT = datetime(2026, 9, 23, tzinfo=timezone.utc)
BODY = 'Bitte sende die Orion-Rechnung bis Freitag.'


def _source(episodes, body=BODY, *, key=''):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Mail', body,
                                 Provenance(SourceType.CHAT, source_ref='chat:local'),
                                 source_key=key, at=AT)
    if key:
        episodes.advance_source_head(key, episodes.source_head(key), episode.id)
    return episode


def _interpreted(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    memory = WorkingMemoryStore(episodes)
    episode = _source(episodes)
    assert memory.commit(memory.pending()[0], [{'start': 0, 'end': len(BODY), 'kind': 'request'}],
                         model='local-v1')
    return episodes, memory, episode


def test_project_link_keeps_interpretation_and_refs(tmp_path):
    episodes, memory, episode = _interpreted(tmp_path)
    ref = memory.search('Orion')['refs'][0]
    episodes.link_project(episode.id, 'p-orion')
    assert memory.pending() == []
    assert memory.resolve(ref).episode.project_id == 'p-orion'
    assert memory.search('Orion')['refs'] == [ref]
    episodes.link_project(episode.id, None)
    assert memory.resolve(ref) is not None


def test_new_source_version_stays_in_project(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    first = _source(episodes, key='document:orion.txt')
    episodes.link_project(first.id, 'p-orion')
    second = _source(episodes, BODY + ' Danke.', key='document:orion.txt')
    assert second.id != first.id
    assert episodes.get(second.id).project_id == 'p-orion'
    unrelated = _source(episodes, 'Andere Datei', key='document:andere.txt')
    assert unrelated.project_id is None


def test_migration_rekeys_legacy_fingerprints_without_reinterpretation(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    episodes, memory, episode = _interpreted(tmp_path)
    episodes.link_project(episode.id, 'p-orion')
    stale = _source(episodes, 'Ben ruft wegen Orion an.')
    assert memory.commit(memory.pending()[0], [{'start': 0, 'end': 24, 'kind': 'status'}], model='a')
    conn = episodes._conn
    downgrade_terms(conn, 9)
    # Stand vor Migration 9 nachbilden: Fingerabdruck und Item-IDs mit Projekt.
    snapshot = episodes.support_snapshot(episode.id)
    legacy, current = _legacy_fingerprint(snapshot), source_fingerprint(snapshot)
    assert legacy != current
    for identifier, start, end, kind in conn.execute(
            'SELECT id,start,end,kind FROM working_memory_items WHERE episode_id=?', (episode.id,)).fetchall():
        old = _item_id(episode.id, legacy, start, end, kind)
        conn.execute('UPDATE working_memory_items SET id=?,fingerprint=? WHERE id=?', (old, legacy, identifier))
        conn.execute('UPDATE working_memory_tokens SET item_id=? WHERE item_id=?', (old, identifier))
    conn.execute('UPDATE working_memory_sources SET fingerprint=? WHERE episode_id=?', (legacy, episode.id))
    # Ein veralteter Eintrag passt zu keinem Fingerabdruck und bleibt, wie er ist.
    conn.execute("UPDATE working_memory_sources SET fingerprint='veraltet' WHERE episode_id=?", (stale.id,))
    conn.execute('PRAGMA user_version=8')
    conn.commit()
    episodes.close()

    reopened = EpisodeStore(path)
    memory = WorkingMemoryStore(reopened)
    row = reopened._conn.execute('SELECT fingerprint,status FROM working_memory_sources WHERE episode_id=?',
                                 (episode.id,)).fetchone()
    assert tuple(row) == (current, 'complete')
    ref = memory.search('Rechnung')['refs'][0]
    assert ref['fingerprint'] == current and memory.resolve(ref).episode.id == episode.id
    assert [s.episode.id for s in memory.pending()] == [stale.id]
    assert reopened._conn.execute('PRAGMA user_version').fetchone()[0] == 18


def test_api_links_source_to_project_and_back(partial):
    app, client, source = partial
    project = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
    memory = WorkingMemoryStore(app.state.episodes)
    before = app.state.episodes._conn.execute(
        'SELECT fingerprint FROM working_memory_sources WHERE episode_id=?', (source,)).fetchone()[0]

    response = client.put(f'/api/v1/episodes/{source}/project', json={'project_id': project.id})
    assert response.status_code == 200 and response.json()['project_id'] == project.id
    assert client.get(f'/api/v1/episodes/{source}').json()['project_id'] == project.id
    assert [e.id for e in app.state.episodes.by_project(project.id)] == [source]
    assert source_fingerprint(app.state.episodes.support_snapshot(source)) == before
    assert memory.pending() == []
    assert any(entry['tool'] == 'quelle_projekt_zuordnen' for entry in app.state.audit.entries())

    assert client.put(f'/api/v1/episodes/{source}/project', json={'project_id': 'p-unbekannt'}).status_code == 404
    assert client.put('/api/v1/episodes/e-unbekannt/project', json={'project_id': None}).status_code == 404
    assert app.state.episodes.get(source).project_id == project.id

    response = client.put(f'/api/v1/episodes/{source}/project', json={'project_id': None})
    assert response.status_code == 200 and response.json()['project_id'] is None


def test_correction_stays_in_project(partial):
    app, client, source = partial
    project = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
    client.put(f'/api/v1/episodes/{source}/project', json={'project_id': project.id})
    original = app.state.episodes.get(source).body
    correction = _correct(client, source, original.replace('25. September', '28. September'))
    assert app.state.episodes.get(correction).project_id == project.id
    assert LIEFERUNG not in app.state.episodes.get(correction).body
