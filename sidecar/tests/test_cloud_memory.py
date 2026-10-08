"""Explicit cloud memory jobs stay bounded to synthetic, current sources."""
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.cloud_memory import CloudMemoryError, CloudMemoryJobs
from icarus_memory.memory_categories import Categories, verify
from icarus_memory.working_memory_store import WorkingMemoryStore, source_fingerprint

AT = datetime(2026, 9, 23, tzinfo=timezone.utc)

class SubscriptionProvider:
    name = "chatgpt"
    model = "subscription-test"
    is_local = False
    is_remote = True

    def __init__(self, on_call=None):
        self.grant_id = "grant-one"
        self._available = True
        self.on_call = on_call
        self.calls = []

    def available(self):
        return self._available

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]["content"])
        self.calls.append(payload)
        if self.on_call:
            self.on_call(payload)
        if "items" in schema["properties"]:
            result = {"items": [{"block_id": item["block_id"], "kind": "fact"}
                               for item in payload["blocks"]]}
        else:
            result = {"categories": [{"category_id": "work", "block_id": "B1"}],
                      "entities": []}
        return type("Reply", (), {"text": json.dumps(result), "tool_calls": []})()

def add_email(episodes, body="Synthetic mail text"):
    episode, created = episodes.record(
        EpisodeKind.MESSAGE, "Synthetic mail", body,
        Provenance(SourceType.EMAIL, source_ref="mail:synthetic:1"), at=AT)
    assert created
    return episode

def setup(tmp_path, *, connected=True, provider=None):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    verify(episodes._conn)
    grant = {"available": connected, "grant_id": "grant-one" if connected else None}
    chosen = provider or SubscriptionProvider()
    jobs = CloudMemoryJobs(episodes, tmp_path / "cloud-jobs.sqlite3",
                          lambda _model: chosen, lambda: dict(grant), threading.RLock())
    return episodes, jobs, grant, chosen

def finish(jobs, job_id):
    jobs._threads[job_id].join(timeout=5)
    assert not jobs._threads[job_id].is_alive()
    return jobs.status(job_id)["job"]

def test_preview_is_metadata_only_and_can_be_created_before_sign_in(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path, connected=False)
    original = add_email(episodes)

    preview = jobs.preview()

    assert preview["count"] == 1
    assert preview["sources"] == [{"id": original.id, "title": "Synthetic mail",
                                   "occurred_at": None}]
    assert provider.calls == []
    assert WorkingMemoryStore(episodes).source_state(original.id) == "pending"

def test_pilot_and_bulk_upgrade_local_complete_source_then_bulk_skips_cloud_complete(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    episode = add_email(episodes)
    memory = WorkingMemoryStore(episodes)
    with episodes._lock:
        snapshot = memory._snapshot(episode.id)
    assert memory.commit(snapshot, [], model="local-model")

    pilot = jobs.preview("pilot", source_ids=[episode.id])
    assert pilot["count"] == 1
    assert pilot["sampling_note"] == "Es werden nur die ausdrücklich ausgewählten Quellen geprüft."
    started = jobs.start(pilot["preview_id"], "subscription-test", True)
    assert finish(jobs, started["job"]["id"])["state"] == "complete"
    with episodes._lock:
        remote = episodes._conn.execute(
            "SELECT model,status FROM working_memory_sources WHERE episode_id=?", (episode.id,)
        ).fetchone()
    assert remote[0] == "chatgpt:subscription-test"
    assert remote[1] == "complete"

    bulk = jobs.preview("bulk", source_ids=[episode.id])
    assert bulk["count"] == 0
    assert provider.calls  # Both classification and category/entity extraction ran.

def test_bulk_preview_pages_past_two_thousand_cloud_complete_sources(tmp_path):
    episodes, jobs, _, _ = setup(tmp_path)
    [add_email(episodes, f"Synthetic mail {number}").id for number in range(2005)]
    memory = WorkingMemoryStore(episodes)
    categories = Categories(episodes)
    with episodes._lock:
        ordered = [row[0] for row in episodes._conn.execute(
            "SELECT id FROM episodes ORDER BY rowid DESC LIMIT 2000").fetchall()]
    for episode_id in ordered:
        with episodes._lock:
            snapshot = memory._snapshot(episode_id)
        fingerprint = source_fingerprint(snapshot)
        assert memory.commit(snapshot, [], model="chatgpt:subscription-test")
        with episodes.transaction():
            categories._set_status(episode_id, fingerprint, 1, "complete", "chatgpt:subscription-test")

    first_page = jobs.preview("bulk")

    assert first_page["candidate_scan_limit"] == 2000
    assert first_page["candidate_count"] == 0
    assert first_page["count"] == 0
    assert first_page["next_cursor"] is not None
    assert "höchstens 2000" in first_page["sampling_note"]

    next_page = jobs.preview("bulk", cursor=first_page["next_cursor"])
    assert next_page["candidate_count"] == 5
    assert next_page["count"] == 5
    assert next_page["next_cursor"] is None

def test_cursor_advances_after_selected_prefix_without_skipping_unselected_sources(tmp_path):
    episodes, jobs, _, _ = setup(tmp_path)
    expected = {add_email(episodes, f"Synthetic page {number}").id for number in range(8)}
    cursor = None
    selected = []
    while True:
        page = jobs.preview("bulk", limit=3, cursor=cursor)
        selected.extend(item["id"] for item in page["sources"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert set(selected) == expected
    assert len(selected) == len(expected)

def test_pilot_runs_both_derived_layers_and_keeps_original_and_correction(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    original = add_email(episodes, "Synthetic mail about the Atlas project.")
    original_dict = episodes.get(original.id).to_dict()
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])

    assert result["state"] == "complete"
    assert result["requests"] == 2
    assert WorkingMemoryStore(episodes).source_state(original.id) == "complete"
    categories = Categories(episodes)
    assert categories.list_for(original.id)["categories"]
    categories.correct(original.id, ["personal"])

    recheck = jobs.preview("recheck", [original.id])
    resumed = jobs.start(recheck["preview_id"], "subscription-test", True)
    refreshed = finish(jobs, resumed["job"]["id"])

    assert refreshed["state"] == "complete"
    assert episodes.get(original.id).to_dict() == original_dict
    assert [item["id"] for item in categories.list_for(original.id)["categories"]] == ["personal"]
    assert categories.list_for(original.id)["correction"]["stale"] is False
    assert categories.taxonomy()["version"] == 1

def test_changed_source_is_rejected_before_any_provider_call(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    episode = add_email(episodes)
    preview = jobs.preview()
    episodes.ignore(episode.id)

    with pytest.raises(CloudMemoryError, match="geändert oder zurückgezogen"):
        jobs.start(preview["preview_id"], "subscription-test", True)
    assert provider.calls == []

def test_grant_revoked_during_call_stops_before_commit_or_next_call(tmp_path):
    episodes, jobs, grant, provider = setup(tmp_path)
    episode = add_email(episodes)

    def revoke(_payload):
        grant["available"] = False

    provider.on_call = revoke
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])

    assert result["state"] == "stopped"
    assert len(provider.calls) == 1
    assert WorkingMemoryStore(episodes).source_state(episode.id) == "pending"

def test_quota_error_pauses_job_without_second_provider_or_fallback(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    add_email(episodes)
    factory_calls = []
    jobs.provider_factory = lambda model: (factory_calls.append(model), provider)[1]
    provider.on_call = lambda _payload: (_ for _ in ()).throw(RuntimeError("subscription quota reached"))
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])

    assert result["state"] == "paused"
    assert "Kontingent" in result["stop_reason"]
    assert factory_calls == ["subscription-test"]
    assert len(provider.calls) == 1
    provider.on_call = None
    jobs.resume(result["id"])
    resumed = finish(jobs, result["id"])
    assert resumed["state"] == "complete"
    assert resumed["requests"] == 3
    assert factory_calls == ["subscription-test", "subscription-test"]


def test_quota_on_category_call_propagates_and_resumes_same_cloud_job(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    add_email(episodes)
    provider.on_call = lambda payload: (
        (_ for _ in ()).throw(RuntimeError("subscription quota reached"))
        if "taxonomy" in payload else None
    )
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    paused = finish(jobs, started["job"]["id"])

    assert paused["state"] == "paused"
    assert paused["requests"] == 2
    assert paused["completed"] == 0
    assert paused["failed"] == 0
    provider.on_call = None
    jobs.resume(paused["id"])
    finished = finish(jobs, paused["id"])
    assert finished["state"] == "complete"
    assert finished["requests"] == 4

def _assert_lock_available(lock):
    assert lock.acquire(blocking=False)
    lock.release()

class CountingBoundary:
    def __init__(self):
        self.calls = 0

    @contextmanager
    def operation(self):
        self.calls += 1
        yield

def test_restore_boundary_failure_blocks_source_processing_and_writes(tmp_path):
    from icarus_memory.restore_boundary import RestorePending

    episodes, jobs, _, provider = setup(tmp_path)
    episode = add_email(episodes)
    boundary = CountingBoundary()

    @contextmanager
    def fails_before_worker():
        boundary.calls += 1
        if boundary.calls == 3:
            raise RestorePending("restore pending")
        yield

    boundary.operation = fails_before_worker
    jobs._runtime_boundary = boundary
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])
    assert result["state"] == "stopped"
    assert provider.calls == []
    assert WorkingMemoryStore(episodes).source_state(episode.id) == "pending"

def test_bulk_accepts_101_sources_after_pilot_and_uses_larger_budget(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    ids = [add_email(episodes, f"Synthetic message {number}").id for number in range(101)]
    with jobs._connect() as db:
        now = 1.0
        db.execute("""INSERT INTO cloud_memory_jobs
            (id,purpose,model,grant_id,source_ids,fingerprints,source_limit,state,consent,
             position,requests,completed,failed,stop_reason,created_at,updated_at)
            VALUES('prior-pilot','pilot','subscription-test','grant-one','[]','{}',100,
                   'complete',1,100,200,100,0,'',?,?)""", (now, now))
    with pytest.raises(CloudMemoryError, match="100 konkrete Quellen"):
        jobs.preview("pilot", source_ids=ids)

    preview = jobs.preview("bulk", source_ids=ids)
    assert preview["count"] == 101
    assert len(preview["sources"]) == 10
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])

    assert result["state"] == "complete"
    assert result["selected"] == 101
    assert result["source_limit"] == 1000
    assert result["request_limit"] == 4000
    assert result["requests"] == 202
    assert len(provider.calls) == 202

@pytest.mark.parametrize("withdraw", [False, True])
def test_changed_or_withdrawn_source_during_call_never_commits(tmp_path, withdraw):
    episodes, jobs, _, provider = setup(tmp_path)
    episode = add_email(episodes)

    def change(_payload):
        if withdraw:
            episodes.ignore(episode.id)
        else:
            changed = episodes.get(episode.id)
            changed.body += " changed after preview"
            episodes._put(changed)

    provider.on_call = change
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])

    assert result["state"] == "stopped"
    assert len(provider.calls) == 1
    assert WorkingMemoryStore(episodes).search("Synthetic")["refs"] == []

def test_shared_permission_lock_is_released_before_provider_network_call(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    add_email(episodes)
    jobs.permission_lock = threading.Lock()
    provider.on_call = lambda _payload: _assert_lock_available(jobs.permission_lock)
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])
    assert result["state"] == "complete"

def _assert_lock_available(lock):
    assert lock.acquire(blocking=False)
    lock.release()

def test_resume_waits_for_paused_inflight_worker_to_exit(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    add_email(episodes)
    entered, release = threading.Event(), threading.Event()

    def blocked(_payload):
        entered.set()
        assert release.wait(3)

    provider.on_call = blocked
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    job_id = started["job"]["id"]
    assert entered.wait(2)
    jobs.pause(job_id)
    with pytest.raises(CloudMemoryError, match="laufende Anfrage"):
        jobs.resume(job_id)
    release.set()
    jobs._threads[job_id].join(timeout=5)
    assert jobs.status(job_id)["job"]["state"] == "paused"
    provider.on_call = None
    resumed = jobs.resume(job_id)
    assert finish(jobs, job_id)["state"] == "complete"


def test_pause_during_provider_preparation_blocks_late_http_send(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    add_email(episodes)
    prepared, release = threading.Event(), threading.Event()
    http_sends = []

    def guarded(messages, *, max_tokens, schema, before_send, still_permitted):
        prepared.set()
        assert release.wait(3)
        if not still_permitted():
            raise RuntimeError("permission changed during provider preparation")
        before_send()
        http_sends.append(True)
        return provider.complete_json(messages, max_tokens=max_tokens, schema=schema)

    provider.complete_json_guarded = guarded
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    job_id = started["job"]["id"]
    assert prepared.wait(2)
    jobs.pause(job_id)
    release.set()
    jobs._threads[job_id].join(timeout=5)

    paused = jobs.status(job_id)["job"]
    assert paused["state"] == "paused"
    assert paused["requests"] == 0
    assert http_sends == []

class CountingBoundary:
    def __init__(self):
        self.calls = 0

    @contextmanager
    def operation(self):
        self.calls += 1
        yield

def test_runtime_boundary_covers_preview_start_and_each_source(tmp_path):
    episodes, jobs, _, _ = setup(tmp_path)
    add_email(episodes)
    boundary = CountingBoundary()
    jobs._runtime_boundary = boundary
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    assert finish(jobs, started["job"]["id"])["state"] == "complete"
    assert boundary.calls == 3

def test_restart_recovers_running_job_as_paused_without_traffic(tmp_path):
    episodes, jobs, grant, provider = setup(tmp_path)
    add_email(episodes)
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    job_id = started["job"]["id"]
    jobs._threads[job_id].join(timeout=5)
    with jobs._connect() as db:
        db.execute("UPDATE cloud_memory_jobs SET state='running' WHERE id=?", (job_id,))

    recovered = CloudMemoryJobs(episodes, tmp_path / "cloud-jobs.sqlite3",
                                lambda _model: provider, lambda: dict(grant), threading.RLock())

    assert recovered.status(job_id)["job"]["state"] == "paused"
    call_count = len(provider.calls)
    assert len(provider.calls) == call_count

def test_failed_provider_call_is_never_counted_as_completed(tmp_path):
    episodes, jobs, _, provider = setup(tmp_path)
    add_email(episodes)
    provider.on_call = lambda _payload: (_ for _ in ()).throw(RuntimeError("synthetic failure"))
    preview = jobs.preview()
    started = jobs.start(preview["preview_id"], "subscription-test", True)
    result = finish(jobs, started["job"]["id"])

    assert result["state"] == "stopped"
    assert result["completed"] == 0
    assert result["failed"] == 1

def test_bulk_requires_a_completed_pilot(tmp_path):
    episodes, jobs, _, _ = setup(tmp_path)
    add_email(episodes)
    preview = jobs.preview("bulk")

    with pytest.raises(CloudMemoryError, match="Pilot muss abgeschlossen"):
        jobs.start(preview["preview_id"], "subscription-test", True)

def test_remote_provider_is_never_accepted_by_local_worker_without_scope(tmp_path):
    from icarus_memory.working_memory_worker import run

    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    add_email(episodes)
    provider = SubscriptionProvider()
    run(episodes, provider, threading.RLock())
    assert provider.calls == []
