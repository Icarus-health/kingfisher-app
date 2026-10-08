"""Product semantic work is durable, bounded, local and permission-aware."""
import importlib
import threading

import pytest

from icarus_memory import EpisodeStore
from icarus_memory.hintergrund import ModellAmpel, als_hintergrund, BackgroundInterrupted
from tests.test_working_memory_semantic_index import add, MODEL, OTHER


class Embedder:
    is_local = True
    model_key = MODEL
    def __init__(self, episodes, permission_lock, ampel):
        self.episodes = episodes
        self.permission_lock = permission_lock
        self.ampel = ampel
        self.inputs = []
        self.entered = 0
        self.fail = False
        self.after_embed = lambda: None
    def __enter__(self):
        self.entered += 1
        assert sum(self.ampel.belegt().values()) > 0
        return self
    def __exit__(self, *_):
        pass
    def embed(self, texts):
        # A different thread must acquire both locks while this external
        # operation is running. RLock._is_owned alone misses other owners.
        locks_free = []
        def check():
            for lock in (self.permission_lock, self.episodes._lock):
                free = lock.acquire(blocking=False)
                locks_free.append(free)
                if free:
                    lock.release()
        thread = threading.Thread(target=check)
        thread.start(); thread.join(2)
        assert locks_free == [True, True]
        assert sum(self.ampel.belegt().values()) > 0
        self.inputs.append(list(texts))
        if self.fail:
            raise RuntimeError('private response must not leak')
        vectors = [[1., 0.] if ('Karte' in t or 'Zugang' in t or 'Ausweis' in t) else [0., 1.] for t in texts]
        self.after_embed()
        return vectors


def setup(tmp_path, **kwargs):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    lock, ampel = threading.Lock(), ModellAmpel()
    embedder = Embedder(episodes, lock, ampel)
    try:
        module = importlib.import_module('icarus_memory.working_memory_semantic_service')
    except ModuleNotFoundError:
        pytest.fail('Durable product semantic service is not implemented')
    service = module.SemanticService(episodes, lambda: embedder, permission_lock=lock, ampel=ampel, **kwargs)
    return episodes, embedder, service


def test_query_never_embeds_sources_and_restart_reuses_background_work(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    original = add(episodes)
    question = 'Wo ist mein Ausweis?'
    empty = service.search_with_status(episodes, question)
    assert empty.refs == () and empty.status == 'partial'
    assert embedder.inputs == []
    assert service.index_batch().ok
    assert len(embedder.inputs) == 1
    assert original.body in embedder.inputs[0][0]
    result = service.search_with_status(episodes, question)
    assert result.refs[0]['episode_id'] == original.id
    assert embedder.inputs[-1] == [question]
    service.close(); episodes.close()
    episodes, next_embedder, service = setup(tmp_path)
    result = service.search_with_status(episodes, question)
    assert result.refs[0]['episode_id'] == original.id
    assert next_embedder.inputs == [[question]]
    service.close(); episodes.close()


def test_status_reads_do_not_connect_or_load_a_model(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    assert service.coverage()['status'] == 'unavailable'
    assert embedder.entered == 0 and embedder.inputs == []
    add(episodes)
    service.index_batch()
    before = embedder.entered
    for _ in range(3):
        status = service.coverage()
        assert status['indexed'] == 1 and status['status'] == 'indexed'
    assert embedder.entered == before
    service.close(); episodes.close()


def test_each_batch_obeys_source_and_utf8_budget_without_losing_tail(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    for n in range(12):
        add(episodes, f'Quelle {n} ' + 'ü' * 6000)
    service.index_batch()
    assert 1 <= len(embedder.inputs[0]) <= 8
    assert sum(len(t.encode('utf-8')) for t in embedder.inputs[0]) <= 16384
    assert service.coverage()['pending'] > 0
    for _ in range(12):
        service.index_batch()
        if service.coverage()['pending'] == 0:
            break
    assert service.coverage()['indexed'] == 12
    service.close(); episodes.close()


def test_permission_changed_during_embedding_does_not_commit_or_defer(tmp_path):
    allowed = [True]
    episodes, embedder, service = setup(tmp_path)
    add(episodes)
    embedder.after_embed = lambda: allowed.__setitem__(0, False)
    result = service.index_batch(permitted=lambda: allowed[0])
    assert result.ok
    status = service.coverage()
    assert status['indexed'] == 0 and status['pending'] == 1 and status['failed'] == 0
    embedder.after_embed = lambda: None
    allowed[0] = True
    assert service.index_batch(permitted=lambda: allowed[0]).ok
    assert service.coverage()['indexed'] == 1
    service.close(); episodes.close()


def test_configuration_changed_during_query_drops_old_results(tmp_path):
    configuration = ['one']
    episodes, embedder, service = setup(tmp_path, configuration=lambda: configuration[0])
    add(episodes)
    service.index_batch()
    embedder.after_embed = lambda: configuration.__setitem__(0, 'two')
    result = service.search_with_status(episodes, 'Wo ist mein Ausweis?')
    assert result.refs == () and result.status == 'unavailable'
    service.close(); episodes.close()


def test_changed_model_digest_requires_new_background_vectors(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    add(episodes)
    service.index_batch()
    embedder.model_key = OTHER
    before = len(embedder.inputs)
    result = service.search_with_status(episodes, 'Wo ist mein Ausweis?')
    assert result.refs == () and result.status == 'partial'
    assert len(embedder.inputs) == before
    service.index_batch()
    assert service.search_with_status(episodes, 'Wo ist mein Ausweis?').refs
    service.close(); episodes.close()


def test_transport_failure_preserves_successful_vectors_and_failure_is_sanitized(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    original = add(episodes)
    service.index_batch()
    add(episodes, 'Eine zweite Karte wird neu bereitgestellt.')
    embedder.fail = True
    result = service.index_batch()
    assert not result.ok and 'private response' not in result.detail
    assert service.coverage()['indexed'] == 1
    assert service.coverage()['pending'] == 1
    assert service.coverage()['failed'] == 1
    assert episodes.get(original.id).body == original.body
    service.close(); episodes.close()


def test_background_energy_interruption_does_not_mark_source_failed(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    add(episodes)
    with als_hintergrund(lambda: 'akku'):
        with pytest.raises(BackgroundInterrupted):
            service.index_batch()
    assert embedder.entered == 0 and embedder.inputs == []
    assert service.coverage()['failed'] in (None, 0)
    service.index_batch()
    assert service.coverage()['indexed'] == 1
    service.close(); episodes.close()


def test_disabled_and_remote_adapters_never_receive_source_text(tmp_path):
    enabled = [False]
    episodes, embedder, service = setup(tmp_path, enabled=lambda: enabled[0])
    add(episodes)
    assert service.coverage()['status'] == 'disabled'
    assert service.index_batch().ok
    assert embedder.entered == 0 and embedder.inputs == []
    enabled[0] = True
    embedder.is_local = False
    assert not service.index_batch().ok
    assert embedder.entered == 0 and embedder.inputs == []
    service.close(); episodes.close()


def test_unclassified_source_makes_full_vector_index_partial(tmp_path):
    from icarus_memory import EpisodeKind, Provenance, SourceType
    episodes, embedder, service = setup(tmp_path)
    add(episodes)
    service.index_batch()
    episodes.record(EpisodeKind.MESSAGE, 'Noch offen', 'Eine zweite Karte ist im Büro.', Provenance(SourceType.CHAT))
    result = service.search_with_status(episodes, 'Wo ist mein Ausweis?')
    assert result.refs and result.status == 'partial'
    assert service.coverage()['status'] == 'partial'
    service.close(); episodes.close()


def test_closed_service_and_different_store_cannot_reuse_vectors(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    add(episodes); service.index_batch()
    other = EpisodeStore(tmp_path / 'other.sqlite3')
    assert service.search_with_status(other, 'Wo ist mein Ausweis?').status == 'unavailable'
    service.close()
    before = embedder.entered
    assert service.search_with_status(episodes, 'Wo ist mein Ausweis?').status == 'unavailable'
    assert embedder.entered == before
    other.close(); episodes.close()


def test_status_does_not_certify_old_configuration_as_current(tmp_path):
    configuration = ['one']
    episodes, embedder, service = setup(tmp_path, configuration=lambda: configuration[0])
    add(episodes); service.index_batch()
    before = embedder.entered
    configuration[0] = 'two'
    assert service.coverage()['status'] == 'unavailable'
    assert embedder.entered == before
    service.close(); episodes.close()


def test_pruning_removes_obsolete_failed_hashes_in_bounded_batches(tmp_path):
    from icarus_memory.working_memory_semantic_index import DurableSemanticIndex
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    originals = [add(episodes, f'Quelle {n}') for n in range(5)]
    index = DurableSemanticIndex(episodes, MODEL)
    index.fail(index.pending(8))
    for original in originals:
        episodes.ignore(original.id)
    assert index._conn.execute('SELECT COUNT(*) FROM failures').fetchone()[0] == 5
    index.prune(2)
    assert index._conn.execute('SELECT COUNT(*) FROM failures').fetchone()[0] == 3
    index.prune(2)
    assert index._conn.execute('SELECT COUNT(*) FROM failures').fetchone()[0] == 1
    index.close(); episodes.close()


def test_plain_permission_lock_does_not_deadlock_background_operation(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    service._permission_lock = embedder.permission_lock = threading.Lock()
    add(episodes)
    results = []
    thread = threading.Thread(target=lambda: results.append(service.index_batch()), daemon=True)
    thread.start(); thread.join(3)
    assert not thread.is_alive(), 'nested permission-lock acquisition deadlocked'
    assert results[0].ok and service.coverage()['indexed'] == 1
    service.close(); episodes.close()


def test_query_can_run_under_existing_conversation_lock(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    service._permission_lock = embedder.permission_lock = threading.Lock()
    add(episodes)
    # No vectors yet, so no transport is necessary for this caller-lock test.
    results = []
    def query():
        with service._permission_lock:
            results.append(service.search_with_status(episodes, 'Wo ist mein Ausweis?'))
    thread = threading.Thread(target=query, daemon=True)
    thread.start(); thread.join(3)
    assert not thread.is_alive(), 'foreground caller already owns the conversation lock'
    assert results[0].status == 'partial'
    service.close(); episodes.close()


def test_request_reuses_question_vector_only_within_same_model_and_query(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    add(episodes); service.index_batch()
    before = len(embedder.inputs)
    with service.request():
        assert service.search_with_status(episodes, 'Wo ist mein Ausweis?', 1).refs
        assert service.search_with_status(episodes, 'Wo ist mein Ausweis?', 16).refs
        assert len(embedder.inputs) == before + 1
        service.search_with_status(episodes, 'Wo ist meine Karte?', 16)
        assert len(embedder.inputs) == before + 2
    service.search_with_status(episodes, 'Wo ist mein Ausweis?', 16)
    assert len(embedder.inputs) == before + 3
    service.close(); episodes.close()


def test_background_releases_model_slot_before_waiting_for_conversation_commit(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    add(episodes)
    model_done, foreground_owns = threading.Event(), threading.Event()
    def after():
        model_done.set()
        assert foreground_owns.wait(2)
    embedder.after_embed = after
    results = []
    background = threading.Thread(target=lambda: results.append(service.index_batch()), daemon=True)
    def foreground():
        assert model_done.wait(2)
        with service._permission_lock:
            foreground_owns.set()
            results.append(service.search_with_status(episodes, 'Wo ist mein Ausweis?'))
    question = threading.Thread(target=foreground, daemon=True)
    background.start(); question.start()
    background.join(3); question.join(3)
    assert not background.is_alive() and not question.is_alive(), 'model/permission lock inversion'
    assert service.coverage()['indexed'] == 1
    service.close(); episodes.close()
