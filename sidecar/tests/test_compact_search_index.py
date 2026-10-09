"""Der kompakte Suchindex findet dasselbe wie vorher, nur kleiner."""
from datetime import datetime, timezone

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.working_memory_legacy import downgrade_terms

AT = datetime(2026, 9, 23, tzinfo=timezone.utc)
BODIES = ['Bitte sende die Orion-Rechnung bis Freitag.',
          'Anna liefert den Prüfbericht für Mainz am 3. Oktober.',
          'Die Rechnung für Atlas ist bezahlt.']
QUESTIONS = ['Rechnung', 'Wann liefert Anna den Prüfbericht?', 'Prüfberichte', 'Orion']


def _store(path):
    episodes = EpisodeStore(path)
    memory = WorkingMemoryStore(episodes)
    for body in BODIES:
        episodes.record(EpisodeKind.MESSAGE, 'Mail', body, Provenance(SourceType.CHAT, source_ref='chat:local'),
                        at=AT)
    for snapshot in memory.pending():
        body = snapshot.episode.body
        assert memory.commit(snapshot, [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='t')
    return episodes, memory


def _terms(episodes):
    return episodes._conn.execute('SELECT term, item FROM working_memory_terms').fetchall()


def test_index_holds_only_integer_keys(tmp_path):
    episodes, _ = _store(tmp_path / 'e.sqlite3')
    rows = _terms(episodes)
    assert rows and all(type(term) is int and type(item) is int for term, item in rows)
    keys = [row[0] for row in episodes._conn.execute('SELECT key FROM working_memory_items')]
    assert len(set(keys)) == len(keys) and all(type(key) is int for key in keys)
    episodes.close()


def test_reinterpretation_replaces_terms_instead_of_adding(tmp_path):
    episodes, memory = _store(tmp_path / 'e.sqlite3')
    before = len(_terms(episodes))
    source = memory.search('Orion')['refs'][0]['episode_id']
    episodes.link_project(source, None)  # keine Änderung am Beleg
    snapshot = episodes.support_snapshot(source)
    # Neu einordnen nach Verwerfen und Wiederzulassen: alte Begriffe verschwinden.
    memory._delete_items(source)
    assert len(_terms(episodes)) < before
    with episodes.transaction():
        episodes._conn.execute('DELETE FROM working_memory_sources WHERE episode_id=?', (source,))
    assert memory.commit(snapshot, [{'start': 0, 'end': len(snapshot.episode.body), 'kind': 'request'}], model='t')
    assert len(_terms(episodes)) == before
    assert not episodes._conn.execute(
        'SELECT 1 FROM working_memory_terms t LEFT JOIN working_memory_items i ON i.key=t.item '
        'WHERE i.id IS NULL').fetchall()
    episodes.close()


def test_migration_keeps_results_and_candidate_signatures(tmp_path):
    path = tmp_path / 'e.sqlite3'
    episodes, memory = _store(path)
    expected = {q: (memory.search(q), memory.candidate_signature(q)) for q in QUESTIONS}
    downgrade_terms(episodes._conn, 9)
    episodes.close()
    reopened = EpisodeStore(path)
    memory = WorkingMemoryStore(reopened)
    assert {q: (memory.search(q), memory.candidate_signature(q)) for q in QUESTIONS} == expected
    assert reopened._conn.execute('PRAGMA user_version').fetchone()[0] == 20
    assert not reopened._conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='working_memory_tokens'").fetchall()
    reopened.close()
