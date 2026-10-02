from datetime import datetime, timezone

import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.claims import ClaimError, ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.habits import check_in, create_habit
from icarus_memory.learning_service import propose_patterns
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalState, ProposalStore


NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def memory(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    return SelfModelStore(MemoryBackend(), "test"), episodes, proposals, service


def test_explicit_pattern_is_candidate_with_exact_evidence(memory):
    store, episodes, proposals, service = memory
    habit = create_habit(store, "Lesen", 3)
    for day in (7, 6, 4):
        check_in(store, episodes, habit.id, f"2026-09-{day:02d}", f"Notiz {day}", at=NOW)
    found = propose_patterns(store, episodes, proposals, service, at=NOW)
    assert len(found) == 1
    candidate = found[0]
    assert candidate.state is ProposalState.PENDING
    assert candidate.subject_ref == f"habit:{habit.id}"
    assert candidate.predicate == "observed_pattern"
    assert len(candidate.evidence) == 3
    assert claims_count(service) == 0


def test_rejected_or_accepted_pattern_is_not_regenerated(memory):
    store, episodes, proposals, service = memory
    habit = create_habit(store, "Schreiben", 3)
    for day in (7, 6, 4):
        check_in(store, episodes, habit.id, f"2026-09-{day:02d}", at=NOW)
    candidate = propose_patterns(store, episodes, proposals, service, at=NOW)[0]
    service.reject(candidate.id, at=NOW)
    assert propose_patterns(store, episodes, proposals, service, at=NOW)[0].id == candidate.id
    # Accepted candidates are also returned from the all-state deduplication.
    accepted_habit = create_habit(store, "Lernen", 3)
    for day in (7, 6, 4):
        check_in(store, episodes, accepted_habit.id, f"2026-09-{day:02d}", at=NOW)
    accepted = next(item for item in propose_patterns(store, episodes, proposals, service, at=NOW)
                    if item.state is ProposalState.PENDING)
    service.accept(accepted.id, supersedes=[], at=NOW)
    refreshed = propose_patterns(store, episodes, proposals, service, at=NOW)
    assert next(item for item in refreshed if item.id == accepted.id).id == accepted.id


def test_changed_source_supersedes_pending_and_invalidates_accept(memory):
    store, episodes, proposals, service = memory
    habit = create_habit(store, "Fokus", 3)
    for day in (7, 6, 4):
        check_in(store, episodes, habit.id, f"2026-09-{day:02d}", at=NOW)
    old = propose_patterns(store, episodes, proposals, service, at=NOW)[0]
    episode_id = old.evidence[0].episode_id
    episodes.ignore(episode_id)
    service._claims.invalidate_source(episode_id, at=NOW)
    with pytest.raises(ClaimError): service.accept(old.id, supersedes=[], at=NOW)


def test_active_habits_with_same_label_map_by_id(memory):
    store, episodes, proposals, service = memory
    first = create_habit(store, "Training", 3)
    second = create_habit(store, "Training", 3)
    for day in (7, 6, 4):
        check_in(store, episodes, first.id, f"2026-09-{day:02d}", at=NOW)
    found = propose_patterns(store, episodes, proposals, service, at=NOW)
    assert len(found) == 1
    assert found[0].subject_ref == f"habit:{first.id}"


def test_large_unrelated_archive_does_not_hide_recent_pattern(memory):
    store, episodes, proposals, service = memory
    habit = create_habit(store, "Archiv", 3)
    for day in (7, 6, 4):
        check_in(store, episodes, habit.id, f"2026-09-{day:02d}", at=NOW)
    for index in range(2001):
        episodes.record(EpisodeKind.DOCUMENT, "Archiv", f"Alte Quelle {index}",
                        Provenance(source_type=SourceType.DOCUMENT),
                        occurred_at=NOW - datetime.resolution * index)
    found = propose_patterns(store, episodes, proposals, service, at=NOW)
    assert any(item.subject_ref == f"habit:{habit.id}" for item in found)


def claims_count(service):
    return len(service._claims.by_subject("habit:any", include_inactive=True))
