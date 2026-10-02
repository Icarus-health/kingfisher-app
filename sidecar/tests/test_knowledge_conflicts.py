"""A pending alternative may warn about accepted knowledge without becoming fact."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import knowledge_conflicts, knowledge_context
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.knowledge_conflicts import check
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalStore


AT = datetime(2026, 9, 22, 9, tzinfo=timezone.utc)


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_context, "now", lambda: AT)
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "claims.sqlite3")
    service = KnowledgeService(episodes=episodes, proposals=proposals, claims=claims)
    yield episodes, proposals, claims, service
    claims.close()
    proposals.close()
    episodes.close()


def make(memory, *, subject="project:aurora", predicate="deadline", value="22 Sep",
         scope="project:aurora", depends_on=None, valid_until=None, rationale="Synthetic"):
    episodes, _, _, service = memory
    statement = f"{subject}: {value}"
    source, _ = episodes.record(
        EpisodeKind.MESSAGE, "Synthetic source", statement,
        Provenance(source_type=SourceType.EMAIL, source_ref=f"synthetic:{subject}:{value}"),
        at=AT,
    )
    proposal, _ = service.propose(
        subject_ref=subject, predicate=predicate, value=value, statement=statement,
        rationale=rationale, scope_ref=scope, depends_on=depends_on,
        valid_until=valid_until,
        evidence=[Evidence(source.id, statement, source.digest)], at=AT,
    )
    return proposal, source


def accepted(memory, **kwargs):
    _, _, _, service = memory
    proposal, source = make(memory, **kwargs)
    return service.accept(proposal.id, supersedes=[], at=AT), source


def status(memory, ids):
    episodes, proposals, claims, _ = memory
    return check(ids, claims, proposals, episodes)


def test_relevant_pending_conflict_is_a_status_without_candidate_text(memory):
    claim, _ = accepted(memory)
    make(memory, value="26 Sep")
    assert status(memory, [claim.id]) == "conflict"
    assert status(memory, ["claim:" + claim.id]) == "conflict"


def test_unrelated_identity_scope_or_predicate_does_not_block(memory):
    claim, _ = accepted(memory)
    make(memory, subject="project:other", value="26 Sep")
    make(memory, scope="project:other", value="27 Sep")
    make(memory, predicate="owner", value="Mira")
    assert status(memory, [claim.id]) == "clear"


def test_rejected_or_withdrawn_candidate_is_not_current_conflict(memory):
    episodes, _, _, service = memory
    claim, _ = accepted(memory)
    rejected, _ = make(memory, value="26 Sep")
    service.reject(rejected.id)
    withdrawn, source = make(memory, value="27 Sep")
    episodes.ignore(source.id)
    assert status(memory, [claim.id]) == "clear"
    assert withdrawn.id != rejected.id


def test_superseded_candidate_is_not_current_conflict(memory):
    _, proposals, _, _ = memory
    claim, _ = accepted(memory)
    candidate, _ = make(memory, value="26 Sep")
    proposals.supersede(candidate.id, at=AT)
    assert status(memory, [claim.id]) == "clear"


def test_expired_candidate_does_not_block_current_answer(memory, monkeypatch):
    claim, _ = accepted(memory)
    make(memory, value="26 Sep", valid_until=AT + timedelta(seconds=1))
    monkeypatch.setattr(knowledge_context, "now", lambda: AT + timedelta(seconds=2))
    assert status(memory, [claim.id]) == "clear"


def test_missing_candidate_source_is_unchecked(memory):
    episodes, proposals, claims, _ = memory
    claim, _ = accepted(memory)
    _, candidate_source = make(memory, value="26 Sep")
    original = episodes.support_snapshot
    def missing(identifier):
        return None if identifier == candidate_source.id else original(identifier)
    assert check([claim.id], claims, proposals, episodes, snapshot_provider=missing) == "unchecked"


def test_conflict_in_transitive_dependency_is_relevant(memory):
    basis, _ = accepted(memory, subject="project:basis", scope="project:basis")
    dependent, _ = accepted(memory, subject="project:aurora", predicate="status",
                            value="ready", depends_on=[basis.id])
    make(memory, subject="project:basis", scope="project:basis", value="26 Sep")
    assert status(memory, [dependent.id]) == "conflict"


def test_withdrawn_dependency_makes_candidate_unchecked(memory):
    episodes, _, _, _ = memory
    basis, basis_source = accepted(memory, subject="project:basis", scope="project:basis")
    claim, _ = accepted(memory)
    make(memory, value="26 Sep", depends_on=[basis.id])
    episodes.ignore(basis_source.id)
    assert status(memory, [claim.id]) == "unchecked"


def test_exact_subject_query_finds_match_behind_global_oldest_500(memory):
    claim, _ = accepted(memory)
    for index in range(505):
        make(memory, subject=f"project:unrelated-{index}", value=f"other-{index}")
    make(memory, value="26 Sep")
    assert status(memory, [claim.id]) == "conflict"


def test_more_than_500_matching_candidates_is_unchecked(memory):
    claim, _ = accepted(memory)
    for index in range(501):
        make(memory, value=f"alternative-{index}")
    assert status(memory, [claim.id]) == "unchecked"


def test_total_candidate_budget_covers_all_selected_subjects(memory):
    first, _ = accepted(memory, subject="project:a", scope="project:a")
    second, _ = accepted(memory, subject="project:b", scope="project:b")
    for index in range(500):
        make(memory, subject="project:a", scope="project:a", predicate="note",
             value=f"other-{index}")
    make(memory, subject="project:b", scope="project:b", value="26 Sep")
    assert status(memory, [first.id, second.id]) == "unchecked"


def test_oversized_matching_proposal_is_unchecked(memory):
    claim, _ = accepted(memory)
    make(memory, value="26 Sep", rationale="x" * 70000)
    assert status(memory, [claim.id]) == "unchecked"


def test_missing_store_or_invalid_selected_claim_is_unchecked(memory):
    episodes, proposals, claims, _ = memory
    assert check([], claims, proposals, episodes) == "clear"
    assert check(["missing"], claims, proposals, episodes) == "unchecked"
    assert check(["claim:k-1"], claims, None, episodes) == "unchecked"


def test_elapsed_budget_after_tiny_query_cannot_report_clear(memory, monkeypatch):
    claim, _ = accepted(memory)
    calls = 0

    def clock():
        nonlocal calls
        calls += 1
        return 0.0 if calls <= 2 else 2.0

    monkeypatch.setattr(knowledge_conflicts, "monotonic", clock)
    assert status(memory, [claim.id]) == "unchecked"
    assert calls >= 3
