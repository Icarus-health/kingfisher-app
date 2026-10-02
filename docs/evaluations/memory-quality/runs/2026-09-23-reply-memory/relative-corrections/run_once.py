"""One locked, synthetic local-model qualification; no product state is used."""

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import OpenAICompatible
from icarus_memory.working_memory_analysis import interpret
from icarus_memory.working_memory_answers import prepare, render
from icarus_memory.working_memory_store import WorkingMemoryStore


HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
RESULT_PATH = HERE / "results.json"
if RESULT_PATH.exists():
    raise SystemExit("Do not overwrite the archived first run")
PROVIDER = OpenAICompatible("qwen3.5:4b", base_url="http://127.0.0.1:11434/v1")
assert PROVIDER.is_local

results = {
    "model": PROVIDER.model,
    "base_url": PROVIDER.base_url,
    "expected_file": str(HERE / "expected.json"),
    "started_at": datetime.now().astimezone().isoformat(),
    "sources": [],
    "questions": [],
    "raw_calls": [],
}


def save():
    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


real_complete_json = PROVIDER.complete_json


def capture(messages, *, max_tokens=256, schema=None):
    payload = json.loads(messages[-1]["content"])
    kind = "classification" if "blocks" in payload else "selection"
    started = time.perf_counter()
    try:
        reply = real_complete_json(messages, max_tokens=max_tokens, schema=schema)
        results["raw_calls"].append({
            "kind": kind,
            "source_title": payload.get("title"),
            "question": payload.get("question"),
            "latency_s": round(time.perf_counter() - started, 3),
            "text": reply.text,
        })
        save()
        return reply
    except Exception as error:
        results["raw_calls"].append({
            "kind": kind,
            "source_title": payload.get("title"),
            "question": payload.get("question"),
            "latency_s": round(time.perf_counter() - started, 3),
            "error": type(error).__name__ + ": " + str(error),
        })
        save()
        raise


PROVIDER.complete_json = capture

with tempfile.TemporaryDirectory(prefix="working-memory-qualification-", dir=HERE) as folder:
    episodes = EpisodeStore(Path(folder) / "episodes.sqlite")
    claims = ClaimStore(Path(folder) / "claims.sqlite")
    memory = WorkingMemoryStore(episodes)
    try:
        for source in EXPECTED["sources"]:
            started = time.perf_counter()
            source_key = "synthetic:working-memory:" + source["id"]
            kind = EpisodeKind.DOCUMENT if source["id"] in {"S10", "S11", "S12"} else EpisodeKind.MESSAGE
            provenance = Provenance(
                SourceType.DOCUMENT if kind == EpisodeKind.DOCUMENT else SourceType.EMAIL,
                source_ref=source_key,
            )
            occurred_at = datetime.fromisoformat(source["occurred_at"]) if source["occurred_at"] else None
            entry = {"id": source["id"], "title": source["title"]}
            try:
                episode, created = episodes.record(
                    kind, source["title"], source["body"], provenance,
                    occurred_at=occurred_at, participants=source["participants"],
                    source_key=source_key,
                )
                assert created
                episodes.advance_source_head(source_key, None, episode.id)
                snapshot = episodes.support_snapshot(episode.id)
                items = interpret(PROVIDER, episode)
                committed = memory.commit(snapshot, items, model=PROVIDER.model)
                entry.update({"episode_id": episode.id, "items": [
                    {"kind": item["kind"], "text": episode.body[item["start"]:item["end"]]}
                    for item in items], "committed": committed})
            except Exception as error:
                entry["error"] = type(error).__name__ + ": " + str(error)
            entry["latency_s"] = round(time.perf_counter() - started, 3)
            results["sources"].append(entry)
            save()

        source_id_by_episode = {entry["episode_id"]: entry["id"] for entry in results["sources"] if "episode_id" in entry}
        for question in EXPECTED["questions"]:
            started = time.perf_counter()
            outcome = {"id": question["id"], "question": question["text"]}
            try:
                prepared = prepare(question["text"], episodes, claims, PROVIDER)
                if prepared is None:
                    outcome.update({"prepared": None, "rendered": None})
                else:
                    displayed, links, contract = render(prepared, episodes, claims)
                    outcome.update({
                        "status": prepared["status"],
                        "uncertainty": prepared["uncertainty"],
                        "candidate_source_ids": [source_id_by_episode.get(ref["episode_id"], ref["episode_id"]) for ref in prepared["basis"]],
                        "selected_source_ids": [source_id_by_episode.get(ref["episode_id"], ref["episode_id"]) for ref in prepared["refs"]],
                        "rendered": displayed,
                        "links": links,
                        "contract": contract,
                        "limited": prepared["limited"],
                    })
            except Exception as error:
                outcome["error"] = type(error).__name__ + ": " + str(error)
            outcome["latency_s"] = round(time.perf_counter() - started, 3)
            results["questions"].append(outcome)
            save()
    finally:
        claims.close()
        episodes.close()

results["finished_at"] = datetime.now().astimezone().isoformat()
save()
print(str(RESULT_PATH))
