"""Worker-level privacy and retry contracts over the real SQLite stores."""
import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_worker import run


AT = datetime(2026, 9, 23, tzinfo=timezone.utc)


class FakeLocalProvider:
    is_local = True
    name = "test-local"
    base_url = "http://127.0.0.1:11434"
    model_digest = "test-digest"

    def __init__(self, *, model="model-a", on_call=None):
        self.model = model
        self.on_call = on_call
        self.calls = []

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[1]["content"])
        self.calls.append(payload)
        if self.on_call:
            self.on_call(payload)
        items = [
            {"block_id": f"B{index}", "kind": "fact"}
            for index, _ in enumerate(payload["blocks"], 1)
        ]
        return type("Reply", (), {"text": json.dumps({"items": items}), "tool_calls": []})()


class FakeCloudProvider(FakeLocalProvider):
    is_local = False


def add_source(episodes, body, *, tags=()):
    episode, created = episodes.record(
        EpisodeKind.MESSAGE,
        "Source",
        body,
        Provenance(SourceType.CHAT, source_ref="chat:test"),
        at=AT,
        tags=list(tags),
    )
    assert created
    return episode


def refs(memory, query="source"):
    return memory.search(query)["refs"]


@pytest.mark.parametrize('failure', ['malformed', 'exception'])
@pytest.mark.parametrize('background, budget, expected', [(True, 3, 1), (False, 2, 2)])
def test_failed_model_attempts_consume_the_packet_budget(tmp_path, failure, background, budget, expected):
    from contextlib import nullcontext
    from icarus_memory.hintergrund import als_hintergrund
    from icarus_memory.working_memory_worker import Zwischenstand

    class Failing(FakeLocalProvider):
        def complete_json(self, messages, *, max_tokens, schema):
            self.calls.append(json.loads(messages[1]['content']))
            if failure == 'exception':
                raise RuntimeError('synthetic model failure after generation')
            return SimpleNamespace(text='invalid JSON after expensive model generation', tool_calls=[])

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    originals = [add_source(episodes, f'Synthetic source {number}.') for number in range(5)]
    provider = Failing()
    stand = Zwischenstand()
    try:
        with als_hintergrund() if background else nullcontext():
            report = run(episodes, provider, threading.RLock(), stand=stand, abschnitte_je_lauf=budget)
        assert not report.ok
        assert len(provider.calls) == expected
        memory = WorkingMemoryStore(episodes)
        assert memory.coverage()['failed'] == expected
        assert len(memory.pending()) == 5 - expected
        assert [episodes.get(item.id).body for item in originals] == [f'Synthetic source {number}.' for number in range(5)]
        resumed = FakeLocalProvider()
        with als_hintergrund():
            run(episodes, resumed, threading.RLock(), stand=stand)
        assert len(resumed.calls) == 1
        assert memory.coverage()['complete'] == 1
    finally:
        episodes.close()


def test_unsupported_source_without_a_model_call_does_not_consume_background_budget(tmp_path):
    from icarus_memory.hintergrund import als_hintergrund
    from icarus_memory.working_memory_worker import Zwischenstand

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    truncated = add_source(episodes, 'Truncated synthetic source.', tags=['source:truncated'])
    supported = add_source(episodes, 'Supported synthetic source.')
    provider = FakeLocalProvider()
    try:
        with als_hintergrund():
            run(episodes, provider, threading.RLock(), stand=Zwischenstand(), source_ids=[truncated.id, supported.id])
        assert len(provider.calls) == 1
        memory = WorkingMemoryStore(episodes)
        assert memory.source_state(truncated.id) == 'deferred'
        assert memory.source_state(supported.id) == 'complete'
    finally:
        episodes.close()


def test_revoked_during_model_call_never_writes_references(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    episode = add_source(episodes, "A source to revoke")

    def revoke(_payload):
        episodes.ignore(episode.id)

    provider = FakeLocalProvider(on_call=revoke)
    run(episodes, provider, threading.RLock())

    assert len(provider.calls) == 1
    assert refs(WorkingMemoryStore(episodes)) == []


def test_permission_revoked_during_model_call_prevents_commit(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    add_source(episodes, "A source whose permission changes")
    permission = {"allowed": True}

    def revoke_permission(_payload):
        permission["allowed"] = False

    provider = FakeLocalProvider(on_call=revoke_permission)
    run(episodes, provider, threading.RLock(), permitted=lambda: permission["allowed"])

    assert len(provider.calls) == 1
    assert refs(WorkingMemoryStore(episodes)) == []


def test_later_revoked_source_in_preloaded_batch_is_not_sent_to_provider(tmp_path, monkeypatch):
    import icarus_memory.episodes as episode_module

    identifiers = iter(("000000000001", "000000000002"))
    monkeypatch.setattr(episode_module.uuid, "uuid4",
                        lambda: SimpleNamespace(hex=next(identifiers)))
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    first = add_source(episodes, "First source")
    later = add_source(episodes, "Later source")

    def revoke_later(_payload):
        episodes.ignore(later.id)

    provider = FakeLocalProvider(on_call=revoke_later)
    run(episodes, provider, threading.RLock(), limit=2)

    assert len(provider.calls) == 1
    assert provider.calls[0]["blocks"][0]["text"] == "First source"
    assert refs(WorkingMemoryStore(episodes), "first")
    assert refs(WorkingMemoryStore(episodes), "later") == []


def test_truncated_source_is_deferred_without_repeating_model_attempt(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    add_source(episodes, "Part of a source", tags=["source:truncated"])
    provider = FakeLocalProvider()

    first = run(episodes, provider, threading.RLock())
    second = run(episodes, provider, threading.RLock())

    assert provider.calls == []
    assert "unvollständiger" in first.detail
    assert "0 Quellen" in second.detail
    assert WorkingMemoryStore(episodes).coverage()["deferred"] == 1


def test_cloud_provider_receives_no_input_and_cannot_write_state(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    add_source(episodes, "Private source text")
    provider = FakeCloudProvider()

    run(episodes, provider, threading.RLock())

    memory = WorkingMemoryStore(episodes)
    assert provider.calls == []
    assert memory.pending()
    assert memory.coverage()["complete"] == 0
    assert refs(memory) == []


def test_complete_source_survives_restart_and_model_swap_without_reclassification(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    episode = add_source(episodes, "A source already classified")
    first_provider = FakeLocalProvider(model="model-a")

    run(episodes, first_provider, threading.RLock())
    assert len(first_provider.calls) == 1
    assert refs(WorkingMemoryStore(episodes), "already")
    episodes.close()

    reopened = EpisodeStore(path)
    swapped_provider = FakeLocalProvider(model="model-b")
    run(reopened, swapped_provider, threading.RLock())

    assert swapped_provider.calls == []
    assert refs(WorkingMemoryStore(reopened), "already")[0]["episode_id"] == episode.id


def test_outdated_refresh_failure_keeps_old_reference_and_obeys_retry_backoff(tmp_path, monkeypatch):
    import icarus_memory.working_memory_store as store_module

    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    episode = add_source(episodes, "Orion needs review")
    memory = WorkingMemoryStore(episodes)
    old = memory.pending()[0]
    assert memory.commit(old, [{"start": 0, "end": len(episode.body), "kind": "request"}], model="local-v0")
    old_ref = refs(memory, "Orion")[0]
    revision_before_refresh = memory.revision()
    confirmed, _ = episodes.record(
        EpisodeKind.SUMMARY, "Confirmed claim", "Unrelated confirmed claim",
        Provenance(SourceType.USER_STATED, source_ref="user:confirmed"), at=AT)
    episodes.mark_consolidated(confirmed.id, produced=["confirmed-claim-1"])
    with episodes.transaction():
        claims_before = episodes._conn.execute(
            "SELECT assertion_id,episode_id FROM episode_produced_assertions ORDER BY assertion_id").fetchall()
    with episodes.transaction():
        episodes._conn.execute(
            "UPDATE working_memory_sources SET analysis_version=0 WHERE episode_id=?", (episode.id,))
    saved_selection_signature = memory.candidate_signature("Orion")

    def fail(_payload):
        raise RuntimeError("temporary local model failure")

    failed_provider = FakeLocalProvider(on_call=fail)
    run(episodes, failed_provider, threading.RLock())
    assert len(failed_provider.calls) == 1
    assert memory.source_state(episode.id) == "pending"
    assert memory.pending() == []
    assert memory.resolve(old_ref).episode.body == episode.body
    assert refs(memory, "Orion")[0]["kind"] == "request"
    assert memory.progress()["done"] == 0
    assert memory.progress()["remaining"] == 1
    assert memory.coverage()["pending"] == 1
    assert memory.revision() == revision_before_refresh

    real_time = store_module.time.time
    monkeypatch.setattr(store_module.time, "time", lambda: real_time() + 301)
    refreshed_provider = FakeLocalProvider()
    run(episodes, refreshed_provider, threading.RLock())
    assert len(refreshed_provider.calls) == 1
    assert memory.progress()["done"] == 1
    assert memory.progress()["remaining"] == 0
    assert refs(memory, "Orion")[0]["kind"] == "fact"
    assert memory.resolve(old_ref) is None
    assert memory.revision() == revision_before_refresh + 1
    assert memory.candidate_signature("Orion") != saved_selection_signature
    assert episodes.get(episode.id).body == "Orion needs review"
    claims_after = episodes._conn.execute(
        "SELECT assertion_id,episode_id FROM episode_produced_assertions ORDER BY assertion_id").fetchall()
    assert [tuple(row) for row in claims_after] == [tuple(row) for row in claims_before]


def test_outdated_dismissal_is_sticky_and_source_changes_still_withdraw_old_refs(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    episode = add_source(episodes, "Orion source")
    memory = WorkingMemoryStore(episodes)
    snapshot = memory.pending()[0]
    assert memory.commit(snapshot, [{"start": 0, "end": len(episode.body), "kind": "fact"}], model="local-v1")
    old_ref = refs(memory, "Orion")[0]
    with episodes.transaction():
        episodes._conn.execute(
            "UPDATE working_memory_sources SET analysis_version=0 WHERE episode_id=?", (episode.id,))
    assert memory.dismiss(episode.id)
    assert memory.source_state(episode.id) == "dismissed"
    assert memory.pending() == []
    assert memory.resolve(old_ref) is None
