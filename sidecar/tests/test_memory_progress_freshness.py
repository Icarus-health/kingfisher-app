"""Metadata changes must immediately reopen classification and semantic coverage."""
import pytest

from icarus_memory import EpisodeStore
from icarus_memory.episodes import CHAT_LOOKUP_TAG
from icarus_memory.working_memory_store import MAX_SNAPSHOT_BYTES, SCAN_BUDGET, WorkingMemoryStore
from tests.test_working_memory_semantic_index import add
from tests.test_working_memory_semantic_service import setup
from tests.test_mail_intake import Reader
from icarus_memory.mail_intake import Intake


def amend(episodes, episode):
    episodes.add_contacts(episode.id,
        [{'name': 'Nora Beispiel', 'adresse': 'nora@example.test', 'rolle': 'sender'}],
        ['Nora Beispiel'])


def classify(memory, episode):
    snapshot = memory.pending(episode_ids=[episode.id])[0]
    assert memory.commit(snapshot, [{'start': 0, 'end': len(episode.body), 'kind': 'fact'}], model='synthetic')


def test_person_metadata_change_immediately_reopens_progress_and_semantic_source_gap(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    try:
        original = add(episodes)
        memory = WorkingMemoryStore(episodes)
        assert memory.progress()['done'] == 1
        assert service.coverage()['source_pending'] == 0
        amend(episodes, original)
        assert memory.source_state(original.id) == 'pending'
        assert memory.progress()['done'] == 0
        assert memory.progress()['remaining'] == 1
        assert service.coverage()['source_pending'] == 1
        assert embedder.entered == 0  # Reading status never loads a model.
        classify(memory, original)
        assert memory.progress()['done'] == 1
        assert service.coverage()['source_pending'] == 0
    finally:
        service.close(); episodes.close()


def test_stale_interpretation_is_not_reembedded_or_reported_search_complete(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    try:
        original = add(episodes)
        assert service.index_batch().ok
        assert service.coverage()['indexed'] == 1
        before = list(embedder.inputs)
        amend(episodes, original)
        status = service.coverage()
        assert status['status'] == 'partial' and status['source_pending'] == 1
        assert status['total'] == 0 and status['indexed'] == 0
        assert service.index_batch().ok
        assert embedder.inputs == before
        result = service.search_with_status(episodes, 'Wo ist mein Ausweis?')
        assert result.refs == () and result.status == 'partial'
        classify(WorkingMemoryStore(episodes), original)
        assert service.index_batch().ok
        assert service.coverage()['status'] == 'indexed'
        assert service.search_with_status(episodes, 'Wo ist mein Ausweis?').refs[0]['episode_id'] == original.id
        episodes.ignore(original.id)
        assert service.search_with_status(episodes, 'Wo ist mein Ausweis?').refs == ()
    finally:
        service.close(); episodes.close()


@pytest.mark.parametrize('state', ['failed', 'deferred'])
def test_old_failure_or_deferral_no_longer_describes_amended_source(tmp_path, state):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        original = add(episodes)
        memory = WorkingMemoryStore(episodes)
        # A fresh failed/deferred run for the changed source, through normal APIs.
        amend(episodes, original)
        snapshot = memory.pending(episode_ids=[original.id])[0]
        assert (memory.fail(snapshot) if state == 'failed' else memory.defer(snapshot))
        assert memory.progress()['retry' if state == 'failed' else 'skipped'] == 1
        episodes.add_contacts(original.id, [], ['Lina Beispiel'])
        progress = memory.progress()
        assert progress['retry'] == 0 and progress['skipped'] == 0
        assert progress['remaining'] == 1
    finally:
        episodes.close()


def test_intentional_dismissal_stays_excluded_after_metadata_change(tmp_path):
    episodes, _, service = setup(tmp_path)
    try:
        original = add(episodes)
        memory = WorkingMemoryStore(episodes)
        assert memory.dismiss(original.id)
        amend(episodes, original)
        assert memory.progress() == {'total': 1, 'done': 0, 'skipped': 1, 'retry': 0, 'remaining': 0}
        assert service.coverage()['source_pending'] == 0
        assert memory.pending(episode_ids=[original.id]) == []
    finally:
        service.close(); episodes.close()


def test_legacy_missing_marker_is_revalidated_without_reclassifying_or_losing_references(tmp_path):
    episodes, embedder, service = setup(tmp_path)
    try:
        original = add(episodes)
        memory = WorkingMemoryStore(episodes)
        reference = memory.search('Zugangskarte')['refs'][0]
        with episodes.transaction():
            episodes._conn.execute('DELETE FROM mail_intake_analysis WHERE episode_id=?', (original.id,))
        assert memory.progress()['remaining'] == 1
        assert service.coverage()['source_pending'] == 1
        assert memory.pending(episode_ids=[original.id]) == []
        assert memory.progress()['done'] == 1
        assert service.coverage()['source_pending'] == 0
        assert memory.resolve(reference).episode.body == original.body
        assert embedder.entered == 0 and embedder.inputs == []
    finally:
        service.close(); episodes.close()


def test_missing_legacy_marker_cannot_bless_changed_interpretation(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        original = add(episodes)
        memory = WorkingMemoryStore(episodes)
        with episodes.transaction():
            episodes._conn.execute('DELETE FROM mail_intake_analysis WHERE episode_id=?', (original.id,))
        amend(episodes, original)
        assert memory.pending(episode_ids=[original.id])[0].episode.id == original.id
        assert memory.progress()['done'] == 0 and memory.progress()['remaining'] == 1
    finally:
        episodes.close()


def test_progress_is_structural_and_legacy_revalidation_keeps_the_scan_budget(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        memory = WorkingMemoryStore(episodes)
        for number in range(SCAN_BUDGET + 3):
            add(episodes, f'Quelle {number}')
        with episodes.transaction():
            episodes._conn.execute('DELETE FROM mail_intake_analysis')
        original_snapshot = memory._snapshot
        reads = []
        def observed(identifier):
            reads.append(identifier)
            return original_snapshot(identifier)
        monkeypatch.setattr(memory, '_snapshot', observed)
        assert memory.progress()['remaining'] == SCAN_BUDGET + 3
        assert reads == []
        assert memory.pending() == []
        assert len(reads) == SCAN_BUDGET
        assert memory.progress()['remaining'] == 3
        reads.clear()
        assert memory.pending() == []
        assert len(reads) <= SCAN_BUDGET
        assert memory.progress()['remaining'] == 0
    finally:
        episodes.close()


def test_oversized_deterministic_gap_can_refresh_without_reading_a_snapshot(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        original = add(episodes)
        # Metadata may be large even when the body is short. This uses a normal
        # metadata mutation, not database tampering.
        episodes.add_mail_headers(original.id, ['oversized:' + 'x' * MAX_SNAPSHOT_BYTES])
        memory = WorkingMemoryStore(episodes)
        assert memory.pending() == []
        assert memory.progress()['skipped'] == 1
        amend(episodes, original)
        assert memory.progress()['remaining'] == 1
        assert memory.pending() == []
        assert memory.progress()['skipped'] == 1 and memory.progress()['remaining'] == 0
    finally:
        episodes.close()


@pytest.mark.parametrize('body', [CHAT_LOOKUP_TAG, f'Anleitung zum Kennzeichen {CHAT_LOOKUP_TAG}.'])
def test_lookup_marker_mentioned_in_original_text_does_not_hide_a_normal_source(tmp_path, body):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        add(episodes, body)
        assert WorkingMemoryStore(episodes).progress()['total'] == 1
    finally:
        episodes.close()


def test_legacy_sticky_dismissal_recovers_mail_status_without_reclassifying(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        intake = Intake(episodes)
        reader = Reader()
        reader.count = 1
        intake.start('a', ['INBOX'])
        original = episodes.get(intake.step('a', reader, batch=1)[0])
        memory = WorkingMemoryStore(episodes)
        assert memory.dismiss(original.id)
        with episodes.transaction():
            episodes._conn.execute('DELETE FROM mail_intake_analysis WHERE episode_id=?', (original.id,))
        amend(episodes, original)
        assert memory.pending() == []
        assert intake.status('a')['folders'][0]['excluded'] == 1
        assert memory.source_state(original.id) == 'dismissed'
    finally:
        episodes.close()
