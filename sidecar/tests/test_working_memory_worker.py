"""Worker-level privacy and retry contracts over the real SQLite stores."""
import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

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
