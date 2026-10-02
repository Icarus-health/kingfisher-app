from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.graph import person_id
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_context import reports

AT = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)


def record(episodes, text, *, seconds=0):
    return episodes.record(EpisodeKind.MESSAGE, "Quelle", text,
        Provenance(SourceType.CHAT, source_ref=f"chat:{seconds}"),
        at=AT + timedelta(seconds=seconds))[0]


def complete(episodes, episode, spans=None):
    store = WorkingMemoryStore(episodes)
    spans = spans or [(0, len(episode.body), "fact")]
    snapshot = store.pending(episode_ids=[episode.id])[0]
    assert store.commit(snapshot, [dict(start=start, end=end, kind=kind)
                                  for start, end, kind in spans], model="local-test")


def test_explicit_report_keeps_full_conditional_source_and_all_reference_kinds(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    try:
        text = "Wenn der Entwurf freigegeben ist, sende ich die Rechnung. Nicht vorher."
        episode = record(episodes, text, seconds=-9000)
        complete(episodes, episode, [(0, len(text), "conditional"), (0, 5, "historical")])
        result = reports(episodes, claims, episode_ids=[episode.id])
        assert len(result["items"]) == 1 and result["truncated"] is False
        item = result["items"][0]
        assert item["episode_id"] == episode.id and item["body"] == text
        assert item["kinds"] == ["conditional", "historical"]
        assert datetime.fromisoformat(item["recorded_at"]) == episode.recorded_at
        assert item["source_ref"] == "chat:-9000"
        assert item["confirmation"] == "source_report"
    finally:
        claims.close()
        episodes.close()


def test_recent_report_uses_recorded_time_and_excludes_stale_ignored_and_produced(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    try:
        since = AT - timedelta(days=1)
        stale = record(episodes, "Veraltet", seconds=-90000)
        changed = record(episodes, "Quelle mit geändertem Kopf", seconds=0)
        ignored = record(episodes, "Zurückgezogen", seconds=1)
        produced = record(episodes, "Abgeleitet", seconds=2)
        dismissed = record(episodes, "Ausdrücklich verworfen", seconds=2.5)
        recent = record(episodes, "Wenn Rückmeldung kommt, antworte ich.", seconds=3)
        for episode in (stale, changed, ignored, produced, dismissed, recent):
            complete(episodes, episode)
        changed.provenance.source_ref = "chat:changed"
        episodes._put(changed)
        episodes.ignore(ignored.id)
        assert WorkingMemoryStore(episodes).dismiss(dismissed.id)
        produced.produced = ["assertion:already-derived"]
        episodes._put(produced)
        result = reports(episodes, claims, since=since)
        assert [item["episode_id"] for item in result["items"]] == [recent.id]
        assert result["items"][0]["body"].startswith("Wenn Rückmeldung")
        assert result["items"][0]["confirmation"] == "source_report"
    finally:
        claims.close()
        episodes.close()


def test_report_omits_sources_with_claimed_evidence(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    try:
        claimed = record(episodes, "Alex leitet das Projekt Atlas.")
        unclaimed = record(episodes, "Wenn Alex antwortet, plane ich weiter.", seconds=1)
        for episode in (claimed, unclaimed):
            complete(episodes, episode)
        candidate, _ = service.propose(
            subject_ref=person_id("Alex"), predicate="leads", value="Atlas",
            statement=claimed.body, rationale="Quelle", evidence=[Evidence(claimed.id, claimed.body, claimed.digest)],
            proposed_by="test", at=AT)
        service.accept(candidate.id, supersedes=[], at=AT)
        result = reports(episodes, claims, episode_ids=[claimed.id, unclaimed.id])
        assert [item["episode_id"] for item in result["items"]] == [unclaimed.id]
        assert result["truncated"]
    finally:
        claims.close()
        proposals.close()
        episodes.close()


def test_reports_are_bounded_by_source_count_and_total_original_text(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    try:
        ids = []
        for index in range(7):
            text = (f"Quelle {index} " + "A" * 9990) if index < 4 else f"Quelle {index}"
            episode = record(episodes, text, seconds=index)
            complete(episodes, episode)
            ids.append(episode.id)
        result = reports(episodes, claims, episode_ids=ids, limit=5)
        assert 1 <= len(result["items"]) <= 5
        assert all(len(item["body"]) <= 12000 for item in result["items"])
        assert sum(len(item["body"]) for item in result["items"]) <= 24000
        assert result["truncated"]
    finally:
        claims.close()
        episodes.close()


def test_store_reference_selection_caps_rows_and_requires_one_selection_mode(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    store = WorkingMemoryStore(episodes)
    try:
        for index in range(70):
            episode = record(episodes, f"Quelle {index}", seconds=index)
            complete(episodes, episode)
        result = store.source_refs(since=AT - timedelta(days=1))
        assert len(result["refs"]) <= 64
        assert result["truncated"]
        with pytest.raises(ValueError):
            store.source_refs()
        with pytest.raises(ValueError):
            store.source_refs(since=AT, episode_ids=["one"])
        with pytest.raises(ValueError):
            store.source_refs(episode_ids=[str(index) for index in range(101)])
        with pytest.raises(ValueError):
            store.source_refs(since=datetime(2026, 9, 23))
    finally:
        episodes.close()


def test_reference_scan_budget_never_returns_partial_source_groups(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    store = WorkingMemoryStore(episodes)
    try:
        for source_index in range(22):
            episode = record(episodes, f"{source_index:02}" + "x" * 28, seconds=source_index)
            complete(episodes, episode, [(index, index + 1, "fact") for index in range(24)])
        result = store.source_refs(since=AT - timedelta(days=1))
        counts = {}
        for ref in result["refs"]:
            counts[ref["episode_id"]] = counts.get(ref["episode_id"], 0) + 1
        assert result["truncated"]
        assert len(result["refs"]) <= 64
        assert all(count == 24 for count in counts.values())
    finally:
        episodes.close()
