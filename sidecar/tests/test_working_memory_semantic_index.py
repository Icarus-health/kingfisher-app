"""Durable derived vectors must never replace or revive original evidence."""
import importlib
import sqlite3
from datetime import datetime, timezone

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore

MODEL = 'local-test:' + 'a' * 64
OTHER = 'local-test:' + 'b' * 64


def index_for(episodes, model=MODEL):
    try:
        module = importlib.import_module('icarus_memory.working_memory_semantic_index')
    except ModuleNotFoundError:
        pytest.fail('Durable source vector cache is not implemented')
    return module.DurableSemanticIndex(episodes, model)


def add(episodes, text='Die Zugangskarte liegt im Tresor.', *, key='', title='Original'):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, title, text,
        Provenance(SourceType.CHAT, source_ref='chat:local'), source_key=key,
        at=datetime(2026, 10, 8, tzinfo=timezone.utc))
    if key:
        episodes.advance_source_head(key, episodes.source_head(key), episode.id)
    memory = WorkingMemoryStore(episodes)
    snapshot = memory._snapshot(episode.id)
    assert memory.commit(snapshot, [{'start': 0, 'end': len(text), 'kind': 'fact'}], model='classifier')
    return episode


def test_restart_uses_saved_vectors_and_original_db_needs_no_extension(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    original = add(episodes)
    cache = index_for(episodes)
    batch = cache.pending(2)
    assert len(batch.refs) == 1
    assert cache.coverage()['pending'] == 1
    assert cache.commit(batch, [[1., 0., 0.]]) == 1
    cache.close()
    episodes.close()
    # A plain SQLite connection can still read/check the authoritative store.
    with sqlite3.connect(path) as plain:
        assert plain.execute('PRAGMA quick_check').fetchone() == ('ok',)
        assert plain.execute('SELECT count(*) FROM episodes').fetchone() == (1,)
        assert not plain.execute("SELECT name FROM sqlite_master WHERE sql LIKE '%USING vec0%'").fetchall()
    episodes = EpisodeStore(path)
    cache = index_for(episodes)
    assert cache.pending(2).refs == ()
    assert cache.coverage()['indexed'] == 1
    result = cache.search([1., 0., 0.])
    assert result.status == 'ok'
    assert [r['episode_id'] for r in result.refs] == [original.id]
    cache.close()
    episodes.close()


def test_model_change_invalidates_old_handle_and_persisted_vectors(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    original = add(episodes)
    old = index_for(episodes)
    batch = old.pending(1)
    assert old.commit(batch, [[1., 0., 0.]]) == 1
    current = index_for(episodes, OTHER)
    assert current.coverage()['indexed'] == 0
    assert current.search([1., 0.]).status == 'partial'
    with pytest.raises(ValueError, match='model|epoch'):
        old.search([1., 0., 0.])
    with pytest.raises(ValueError, match='model|epoch'):
        old.commit(batch, [[1., 0., 0.]])
    assert current.commit(current.pending(1), [[1., 0.]]) == 1
    assert [r['episode_id'] for r in current.search([1., 0.]).refs] == [original.id]
    old.close(); current.close(); episodes.close()


def test_bad_batch_does_not_lose_existing_vectors_or_skip_pending(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes)
    cache = index_for(episodes)
    cache.commit(cache.pending(1), [[1., 0., 0.]])
    second = add(episodes, 'Die Rechnung ist bezahlt.')
    batch = cache.pending(1)
    for invalid in ([[1., 0.]], [[float('nan'), 0., 1.]], [[0., 0., 0.]], []):
        with pytest.raises(ValueError):
            cache.commit(batch, invalid)
        assert cache.coverage()['indexed'] == 1
        assert cache.pending(1).refs == batch.refs
    assert cache.commit(batch, [[0., 1., 0.]]) == 1
    assert [r['episode_id'] for r in cache.search([0., 1., 0.]).refs] == [second.id]
    cache.close(); episodes.close()


def test_withdrawal_before_pruning_never_returns_old_source(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    old = add(episodes)
    cache = index_for(episodes)
    cache.commit(cache.pending(1), [[1., 0.]])
    episodes.ignore(old.id)
    assert cache.coverage()['indexed'] == 0
    result = cache.search([1., 0.])
    assert result.refs == ()
    assert result.status == 'partial'
    assert cache.prune(1) == 1
    assert cache.search([1., 0.]).status == 'empty'
    cache.close(); episodes.close()


def test_source_changed_during_batch_is_not_committed(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    old = add(episodes, key='mail:one')
    cache = index_for(episodes)
    batch = cache.pending(1)
    current = add(episodes, 'Die Zugangskarte liegt im Schrank.', key='mail:one')
    assert cache.commit(batch, [[1., 0.]]) == 0
    assert cache.coverage()['indexed'] == 0
    assert cache.search([1., 0.]).refs == ()
    next_batch = cache.pending(1)
    assert [r['episode_id'] for r in next_batch.refs] == [current.id]
    cache.close(); episodes.close()


def test_concurrent_stale_batch_cannot_move_cursor_or_duplicate_vectors(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes)
    first = index_for(episodes)
    other = index_for(episodes)
    stale = other.pending(1)
    first.commit(first.pending(1), [[1., 0.]])
    with pytest.raises(ValueError, match='batch|progress'):
        other.commit(stale, [[0., 1.]])
    assert first.coverage()['indexed'] == 1
    assert len(first.search([1., 0.]).refs) == 1
    first.close(); other.close(); episodes.close()


def test_failed_transaction_rolls_back_vector_and_cursor(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes)
    cache = index_for(episodes)
    batch = cache.pending(1)
    cache._conn.execute("CREATE TRIGGER simulate_full_disk BEFORE INSERT ON entries BEGIN SELECT RAISE(ABORT, 'disk full'); END")
    with pytest.raises(sqlite3.DatabaseError):
        cache.commit(batch, [[1., 0.]])
    assert cache.coverage()['indexed'] == 0
    assert cache.pending(1).refs == batch.refs
    cache._conn.execute('DROP TRIGGER simulate_full_disk')
    assert cache.commit(batch, [[1., 0.]]) == 1
    assert len(cache.search([1., 0.]).refs) == 1
    cache.close(); episodes.close()


def test_failure_cooldown_does_not_starve_other_sources(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes); add(episodes, 'Eine zweite Quelle.')
    cache = index_for(episodes)
    batch = cache.pending(1)
    failed_id = batch.refs[0]['episode_id']
    cache.fail(batch)
    next_batch = cache.pending(1)
    assert len(next_batch.refs) == 1
    assert next_batch.refs[0]['episode_id'] != failed_id
    cache.commit(next_batch, [[1., 0.]])
    assert cache.pending(1).refs == ()
    assert cache.coverage()['pending'] == 1
    assert cache.coverage()['failed'] == 1
    module = importlib.import_module('icarus_memory.working_memory_semantic_index')
    now = module.time.time()
    monkeypatch.setattr(module.time, 'time', lambda: now + 301)
    assert cache.pending(1).refs[0]['episode_id'] == failed_id
    cache.close(); episodes.close()


def test_backfill_reaches_old_source_beyond_2048_despite_new_arrivals(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    old = add(episodes)
    memory = WorkingMemoryStore(episodes)
    for group in range(5):
        text = '|'.join(f'Originalabschnitt {group} {n}' for n in range(450))
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, f'Dokument {group}', text,
            Provenance(SourceType.CHAT, source_ref='chat:local'))
        items, start = [], 0
        for part in text.split('|'):
            items.append({'start': start, 'end': start + len(part), 'kind': 'fact'})
            start += len(part) + 1
        assert memory.commit(memory._snapshot(episode.id), items, model='classifier')
    initial = {(r['episode_id'], r['start']) for r in memory.inventory(8192)['refs']}
    assert len(initial) == 2251
    cache = index_for(episodes)
    seen = set()
    for n in range(40):
        batch = cache.pending(64)
        seen.update((r['episode_id'], r['start']) for r in batch.refs)
        cache.commit(batch, [[1., 0.] if r['episode_id'] == old.id else [0., 1.]
                             for r in batch.refs])
        add(episodes, f'Neue Mail {n}')
        if initial <= seen:
            break
    assert initial <= seen
    assert (old.id, 0) in seen
    assert [r['episode_id'] for r in cache.search([1., 0.]).refs] == [old.id]
    cache.close(); episodes.close()


def test_cache_is_separate_per_store_and_contains_no_source_text(tmp_path):
    first = EpisodeStore(tmp_path / 'one.sqlite3')
    second = EpisodeStore(tmp_path / 'two.sqlite3')
    secret = 'Nichtduplizierter Originaltext 47119378.'
    add(first, secret)
    cache = index_for(first); other = index_for(second)
    cache.commit(cache.pending(1), [[1., 0.]])
    assert other.search([1., 0.]).refs == ()
    assert other.coverage()['indexed'] == 0
    assert secret.encode() not in cache.path.read_bytes()
    with pytest.raises(sqlite3.OperationalError, match='readonly'):
        cache._conn.execute("UPDATE originals.episodes SET title='changed'")
    with pytest.raises(sqlite3.OperationalError, match='authorized'):
        cache._conn.load_extension('not-a-library')
    cache.close(); other.close(); first.close(); second.close()


def test_replaced_source_file_forces_cache_reopen(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    add(episodes)
    cache = index_for(episodes)
    replacement = EpisodeStore(tmp_path / 'replacement.sqlite3')
    replacement.close()
    (tmp_path / 'replacement.sqlite3').replace(path)
    with pytest.raises(ValueError, match='replaced|source file'):
        cache.coverage()
    cache.close(); episodes.close()


def test_query_dimension_error_keeps_completed_index(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes)
    cache = index_for(episodes)
    cache.commit(cache.pending(1), [[1., 0.]])
    with pytest.raises(ValueError):
        cache.search([1., 0., 0.])
    assert cache.coverage()['indexed'] == 1
    assert len(cache.search([1., 0.]).refs) == 1
    cache.close(); episodes.close()


def test_corrupt_cache_fails_closed_and_originals_remain_usable(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    original = add(episodes)
    cache = index_for(episodes)
    path = cache.path
    cache.close()
    path.write_bytes(b'broken derived cache, not an original database')
    with pytest.raises(sqlite3.DatabaseError):
        index_for(episodes)
    assert episodes.get(original.id).body == original.body
    assert WorkingMemoryStore(episodes).search('Zugangskarte')['refs'][0]['episode_id'] == original.id
    assert episodes._conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    episodes.close()


def test_unresolved_changed_document_cannot_be_saved_or_returned(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    original = add(episodes)
    cache = index_for(episodes)
    batch = cache.pending(1)
    changed = episodes.get(original.id)
    changed.provenance.source_ref = 'chat:different-origin'
    episodes._put(changed)
    assert cache.commit(batch, [[1., 0.]]) == 0
    assert cache.search([1., 0.]).refs == ()
    assert cache.coverage()['pending'] == 1
    cache.close(); episodes.close()


def test_limit_does_not_claim_all_matching_candidates_were_returned(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    for n in range(6):
        add(episodes, f'Quelle {n}')
    cache = index_for(episodes)
    batch = cache.pending(64)
    cache.commit(batch, [[1., 0.] for _ in batch.refs])
    result = cache.search([1., 0.], limit=2)
    assert len(result.refs) == 2
    assert result.status == 'partial'
    cache.close(); episodes.close()


def test_in_memory_store_and_symlink_cannot_share_persistent_cache(tmp_path):
    episodes = EpisodeStore(':memory:')
    with pytest.raises(ValueError, match='persistent'):
        index_for(episodes)
    episodes.close()
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    target = tmp_path / 'other'
    target.mkdir()
    (tmp_path / '.search-cache').symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        index_for(episodes)
    assert list(target.iterdir()) == []
    episodes.close()


def test_backup_omits_cache_and_restored_originals_rebuild_independently(tmp_path):
    from icarus_memory.backup import snapshot_all, verify_snapshot_set, restore_all
    data = tmp_path / 'data'
    episodes = EpisodeStore(data / 'episodes.sqlite3')
    original = add(episodes)
    cache = index_for(episodes)
    cache.commit(cache.pending(1), [[1., 0.]])
    saved = snapshot_all(data, tmp_path / 'backups')
    names = {r['name'] for r in verify_snapshot_set(saved)}
    assert 'episodes.sqlite3' in names
    assert not any('vectors' in name or 'search-cache' in name for name in names)
    restored = tmp_path / 'restored'
    restore_all(saved, restored)
    reopened = EpisodeStore(restored / 'episodes.sqlite3')
    assert reopened.get(original.id).body == original.body
    derived = index_for(reopened)
    assert derived.coverage()['indexed'] == 0
    assert derived.coverage()['pending'] == 1
    assert cache.coverage()['indexed'] == 1
    derived.close(); reopened.close(); cache.close(); episodes.close()


def test_missing_vector_in_otherwise_valid_cache_is_not_a_complete_index(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes)
    cache = index_for(episodes)
    cache.commit(cache.pending(1), [[1., 0.]])
    cache._conn.execute('DELETE FROM vectors')
    cache._conn.commit()
    cache.close()
    with pytest.raises(sqlite3.DatabaseError, match='inconsistent'):
        index_for(episodes)
    assert WorkingMemoryStore(episodes).search('Zugangskarte')['refs']
    episodes.close()


def test_cycle_horizon_excludes_new_insertions_inside_hash_key_range(tmp_path):
    # New SHA keys can sort before old keys; freezing MAX(hash) alone is not
    # a finite snapshot when incoming volume exceeds the batch rate.
    from icarus_memory.working_memory_store import _item_id
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    for n in range(3):
        add(episodes, f'Ursprüngliche Quelle {n}')
    rows = episodes._conn.execute('SELECT * FROM working_memory_items ORDER BY id').fetchall()
    target_id, target_key = rows[-1]['episode_id'], rows[-1]['id']
    cache = index_for(episodes)
    seen = set()
    for tick in range(4):
        batch = cache.pending(1)
        seen.update(r['episode_id'] for r in batch.refs)
        cache.commit(batch, [[1., 0.] for _ in batch.refs])
        if target_id in seen:
            break
        # Deliberately place new keys ahead of the old high-hash item.
        cursor_key = _item_id(**batch.refs[0]) if batch.refs else ''
        accepted = 0
        for n in range(300):
            incoming = add(episodes, f'Neue Quelle {tick}-{n}')
            key = episodes._conn.execute('SELECT id FROM working_memory_items WHERE episode_id=?', (incoming.id,)).fetchone()[0]
            if cursor_key < key < target_key:
                accepted += 1
            else:
                episodes.ignore(incoming.id)
            if accepted == 2:
                break
        assert accepted == 2
    assert target_id in seen
    cache.close(); episodes.close()


@pytest.mark.parametrize('operation', ['search', 'commit'])
def test_source_replacement_during_operation_fails_closed(tmp_path, monkeypatch, operation):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    add(episodes)
    cache = index_for(episodes)
    batch = cache.pending(1)
    if operation == 'search':
        cache.commit(batch, [[1., 0.]])
    replacement = EpisodeStore(tmp_path / 'replacement.sqlite3')
    replacement.close()
    original_guard = cache._guard
    triggered = []
    def replacing_guard():
        result = original_guard()
        if not triggered:
            triggered.append(True)
            (tmp_path / 'replacement.sqlite3').replace(tmp_path / 'episodes.sqlite3')
        return result
    monkeypatch.setattr(cache, '_guard', replacing_guard)
    with pytest.raises(ValueError, match='source file|replaced'):
        if operation == 'search':
            cache.search([1., 0.])
        else:
            cache.commit(batch, [[1., 0.]])
    cache.close()
    with sqlite3.connect(cache.path) as db:
        assert db.execute('SELECT COUNT(*) FROM entries').fetchone()[0] == (1 if operation == 'search' else 0)
        if operation == 'commit':
            assert db.execute('SELECT dimension FROM progress').fetchone()[0] is None
    episodes.close()
