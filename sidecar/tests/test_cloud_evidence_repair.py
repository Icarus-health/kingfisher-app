"""Synthetic HTTP integration: evidence correction keeps every cloud boundary."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.cloud_import_provider import AnthropicImportProvider
from icarus_memory.cloud_memory import CloudMemoryJobs
from icarus_memory.memory_categories import Categories, _blocks, _quote_sections, _remote_fragments
from icarus_memory.working_memory_analysis import abschnitte_der
from icarus_memory.working_memory_store import source_fingerprint
from tests.test_memory_categories import Local


def evidence(block="B1", *, role="mentioned", kind="organization", name="Example.de"):
    return {"kind": kind, "name": name, "block_id": block,
            "occurrence": 1, "role": role}


def proposal(entity):
    return {"categories": [{"category_id": "finance", "block_id": "B1"}],
            "entities": [entity]}


@pytest.fixture
def cloud(tmp_path, monkeypatch):
    stores = []

    def make(*, model="claude-sonnet-5-5", body=None):
        episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
        stores.append(episodes)
        source = episodes.record(
            EpisodeKind.MESSAGE, "Synthetic evidence source",
            body or "Beleg https://example.de.\n\nExample.de ist ein Handelsname.",
            Provenance(SourceType.EMAIL, source_ref="mail:synthetic-evidence"),
            occurred_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )[0]
        credential = {"available": True, "credential_revision": "revision-one", "model": model}
        provider = AnthropicImportProvider(
            model, "synthetic-key", "revision-one", lambda: credential["credential_revision"])
        jobs = CloudMemoryJobs(
            episodes, tmp_path / "cloud-jobs.sqlite3", lambda _: pytest.fail("No fallback"),
            lambda: {}, api_provider_factory=lambda *_: provider,
            credential_status=lambda _: dict(credential))
        harness = SimpleNamespace(episodes=episodes, source=source, credential=credential,
                                  provider=provider, jobs=jobs, calls=[], preparations=0,
                                  category_calls=0, before_client=lambda _: None,
                                  category_answer=lambda _, n: proposal(evidence("B1" if n == 1 else "B2")))

        def handler(request):
            packet = json.loads(request.content)
            schema = (packet["output_config"]["format"]["schema"] if model == "claude-sonnet-5-5"
                      else packet["tools"][0]["input_schema"])
            payload = json.loads(packet["messages"][-1]["content"])
            harness.calls.append((packet, payload, schema))
            if "items" in schema["properties"]:
                answer = {"items": {b["block_id"]: "fact" for b in payload["blocks"]}}
            else:
                harness.category_calls += 1
                answer = harness.category_answer(payload, harness.category_calls)
            if model == "claude-sonnet-5-5":
                return httpx.Response(200, json={"stop_reason": "end_turn", "content": [
                    {"type": "text", "text": json.dumps(answer, ensure_ascii=False)}]})
            return httpx.Response(200, json={"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "name": "memory_result", "input": answer}]})

        def client(_):
            harness.preparations += 1
            harness.before_client(harness.preparations)
            return httpx.Client(transport=httpx.MockTransport(handler), trust_env=False,
                                follow_redirects=False)

        monkeypatch.setattr(AnthropicImportProvider, "_client", client)
        return harness

    yield make
    for store in stores:
        store.close()


def finish(harness, job_id):
    harness.jobs._threads[job_id].join(timeout=5)
    assert not harness.jobs._threads[job_id].is_alive()
    return harness.jobs.status(job_id)["job"]


def start(harness, preview=None):
    preview = preview or harness.jobs.preview(source_ids=[harness.source.id], provider="anthropic")
    started = harness.jobs.start(preview["preview_id"], harness.provider.model, True,
                                 provider="anthropic")
    return finish(harness, started["job"]["id"])


@pytest.mark.parametrize("model", ["claude-synthetic", "claude-sonnet-5-5"])
def test_native_cloud_correction_is_counted_and_commits_only_fresh_exact_evidence(cloud, model):
    h = cloud(model=model)
    original = deepcopy(h.source.to_dict())
    job = start(h)
    assert job["state"] == "complete", job
    assert job["requests"] == len(h.calls) == 3
    assert job["completed"] == 1 and job["failed"] == 0
    first, corrected = h.calls[1], h.calls[2]
    assert first[1]["blocks"] == corrected[1]["blocks"]
    assert first[2] == corrected[2]
    assert corrected[1]["validation_failure"] == {
        "code": "invalid_entity_evidence", "reason": "entity_missing"}
    assert corrected[1]["rejected_output"] == proposal(evidence("B1"))
    stored = Categories(h.episodes).list_for(h.source.id)
    assert len(stored["categories"]) == 1
    assert [(e["name"], e["start"]) for e in stored["entities"]] == [
        ("Example.de", h.source.body.index("Example.de"))]
    assert h.episodes.get(h.source.id).to_dict() == original


@pytest.mark.parametrize("revoked", ["source", "credential", "consent"])
def test_native_cloud_guard_blocks_correction_during_client_preparation(cloud, revoked):
    h = cloud()

    def revoke(preparation):
        if preparation != 3:
            return
        if revoked == "source":
            h.episodes.ignore(h.source.id)
        elif revoked == "credential":
            h.credential["credential_revision"] = "revision-two"
        else:
            h.jobs.pause(h.jobs._latest_id(), revoke=True)

    h.before_client = revoke
    job = start(h)
    assert job["state"] == "stopped", job
    assert h.preparations == 3  # The corrective path was reached.
    assert job["requests"] == len(h.calls) == 2
    assert not Categories(h.episodes).list_for(h.source.id)["entities"]


def test_native_cloud_second_bad_answer_remains_a_gap_and_preserves_prior_categories(cloud):
    h = cloud()
    categories = Categories(h.episodes)
    assert categories.run(Local(result={"categories": [{"category_id": "work", "block_id": "B1"}],
                                        "entities": []})).ok
    categories.correct(h.source.id, ["personal"])
    prior = deepcopy(categories.list_for(h.source.id))
    h.category_answer = lambda *_: proposal(evidence("B1"))
    job = start(h)
    assert job["state"] == "complete_with_gaps", job
    assert job["completed"] == 0 and job["failed"] == 1
    assert job["requests"] == len(h.calls) == 3
    assert job["issues"][0]["reason"] == "entity_missing"
    stored = categories.list_for(h.source.id)
    assert stored["categories"] == prior["categories"]
    assert stored["entities"] == prior["entities"]
    assert stored["correction"] == prior["correction"]


def test_native_cloud_legacy_job_budget_is_not_widened_for_correction(cloud):
    h = cloud()
    snapshot = h.jobs._snapshot(h.source.id)
    with h.jobs._connect() as db:
        db.execute("""INSERT INTO cloud_memory_jobs
            (id,purpose,model,grant_id,source_ids,fingerprints,source_limit,state,consent,
             position,requests,completed,failed,stop_reason,created_at,updated_at,
             provider,credential_revision,request_limit)
            VALUES(?,?,?,?,?,?,1,'paused',1,0,0,0,0,'',1,1,'anthropic','revision-one',2)""",
            ("legacy-capped", "pilot", h.provider.model, "", json.dumps([h.source.id]),
             json.dumps({h.source.id: source_fingerprint(snapshot)})))
    h.jobs.resume("legacy-capped")
    job = finish(h, "legacy-capped")
    assert job["state"] == "stopped", job
    assert job["request_limit"] == job["requests"] == len(h.calls) == 2
    assert not Categories(h.episodes).list_for(h.source.id)["entities"]


def test_native_cloud_old_preview_keeps_its_original_request_cap(cloud):
    body = "\n\n".join(["URL https://example.de.", "Example.de"] + [f"Absatz {i}" for i in range(88)])
    h = cloud(body=body)
    classifications = len(abschnitte_der(h.source))
    sections = len(_quote_sections(body, _remote_fragments(body, _blocks(body))))
    old_cap = classifications + sections
    assert old_cap > 4
    preview = h.jobs.preview(source_ids=[h.source.id], provider="anthropic")
    with h.jobs._connect() as db:
        stored = json.loads(db.execute("SELECT sources FROM cloud_memory_previews WHERE id=?",
                                       (preview["preview_id"],)).fetchone()[0])
        stored[0]["planned_requests"] = old_cap
        db.execute("UPDATE cloud_memory_previews SET sources=? WHERE id=?",
                   (json.dumps(stored), preview["preview_id"]))
    h.category_answer = lambda payload, n: (proposal(evidence("B1" if n == 1 else "B2"))
                                           if n <= 2 else {"categories": [], "entities": []})
    job = start(h, preview)
    assert job["state"] == "stopped", job
    assert job["request_limit"] == job["requests"] == len(h.calls) == old_cap
    assert not Categories(h.episodes).list_for(h.source.id)["entities"]


@pytest.mark.parametrize("bad", [
    proposal(evidence("B2", role="sender")),
    proposal(evidence("B2", kind="unsupported")),
    {"categories": [], "entities": [{**evidence("B2"), "extra": "untrusted"}]},
    {"categories": [{"category_id": "unknown", "block_id": "B1"}], "entities": []},
    {"categories": [], "entities": "not a list"},
])
def test_native_cloud_non_anchor_failures_do_not_trigger_correction(cloud, bad):
    h = cloud()
    h.category_answer = lambda *_: bad
    job = start(h)
    assert job["state"] == "complete_with_gaps", job
    assert job["requests"] == len(h.calls) == 2
    assert job["completed"] == 0 and job["failed"] == 1


@pytest.mark.parametrize("bad", [
    proposal(evidence("B1", role="sender")),
    proposal(evidence("B1", kind="unsupported")),
    {"categories": [], "entities": [evidence("B1"), evidence("B2", role="sender")]},
    {"categories": [], "entities": [evidence("B1"), evidence("B2", kind="unsupported")]},
])
def test_native_cloud_schema_and_sender_failures_cannot_hide_behind_a_missing_anchor(cloud, bad):
    h = cloud()
    h.category_answer = lambda *_: bad
    job = start(h)
    assert job["state"] == "complete_with_gaps", job
    assert job["requests"] == len(h.calls) == 2
