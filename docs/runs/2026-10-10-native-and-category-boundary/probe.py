"""Synthetic category boundary probe; no network, model, or personal store.

Run from the repository root with its test Python. The deliberately wrong
model answer demonstrates a limitation, not a successful quality benchmark.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sidecar"))

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.memory_categories import Categories
from icarus_memory.providers import Reply


class FixedAnswer:
    is_local = True
    name = model = "synthetic-category-boundary"

    def __init__(self, mode, block="B1"):
        self.entity_anchor_mode = mode
        self.block = block
        self.calls = 0

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls += 1
        return Reply(text=json.dumps({
            "categories": [{"category_id": "work", "block_id": self.block}],
            "entities": [],
        }))


def probe(mode):
    with tempfile.TemporaryDirectory(prefix="kf-category-boundary-") as folder:
        with closing(EpisodeStore(Path(folder) / "episodes.sqlite3")) as episodes:
            categories = Categories(episodes)
            item, created = episodes.record(
                EpisodeKind.MESSAGE, "Synthetischer Werbe-Newsletter",
                "Unser öffentlicher Newsletter: Heute gibt es neue Sommerfarben. "
                "Sie erhalten diese Werbung als Abonnent. Jetzt abbestellen.",
                Provenance(SourceType.CHAT, source_ref="synthetic:newsletter"),
            )
            assert created
            original = item.to_dict()
            provider = FixedAnswer(mode)
            assert categories.run(provider, source_ids=[item.id]).ok
            automatic = categories.list_for(item.id)
            # The validator proves the supplied span exists, not that work is
            # the right meaning. Record that limitation explicitly.
            assert [x["id"] for x in automatic["categories"]] == ["work"]
            assert automatic["categories"][0]["origin"] == "automatic"
            assert automatic["categories"][0]["evidence"][0]["quote"] == item.body

            categories.correct(item.id, ["information"])
            assert categories.request_recheck([item.id]) == 1
            assert categories.run(provider, source_ids=[item.id]).ok
            corrected = categories.list_for(item.id)
            assert provider.calls == 2
            assert [x["id"] for x in corrected["categories"]] == ["information"]
            assert corrected["categories"][0]["origin"] == "user"
            assert episodes.get(item.id).to_dict() == original

            episodes.ignore(item.id)
            withdrawn = categories.list_for(item.id)
            assert withdrawn["status"] == "excluded"
            assert withdrawn["categories"] == withdrawn["entities"] == []
            assert episodes.get(item.id).body == original["body"]

            invalid, _ = episodes.record(
                EpisodeKind.MESSAGE, "Synthetische Kontrolle", "Ein anderer Originaltext.",
                Provenance(SourceType.CHAT, source_ref="synthetic:invalid-block"),
            )
            assert not categories.run(FixedAnswer(mode, "B404"), source_ids=[invalid.id]).ok
            rejected = categories.list_for(invalid.id)
            assert rejected["status"] == "failed"
            assert rejected["categories"] == rejected["entities"] == []
            return {
                "mode": mode,
                "wrong_but_source_anchored_work_hint_accepted": True,
                "semantic_category_quality_proven": False,
                "user_correction_survives_recheck": True,
                "original_unchanged_before_withdrawal": True,
                "withdrawal_hides_hints_and_keeps_body": True,
                "nonexistent_evidence_block_rejected": True,
                "real_model_calls": 0,
            }


if __name__ == "__main__":
    print(json.dumps({
        "source_sha256": hashlib.sha256(
            (ROOT / "sidecar/icarus_memory/memory_categories.py").read_bytes()
        ).hexdigest(),
        "personal_data_used": False,
        "results": [probe(mode) for mode in ("absolute", "block_quote")],
    }, ensure_ascii=False, indent=2))
