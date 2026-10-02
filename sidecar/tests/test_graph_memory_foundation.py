"""Produktverträge für Beziehungen, Zeitverlauf, Abhängigkeiten und Graphen."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from icarus_memory.backends import MemoryBackend
from icarus_memory.claims import ClaimError, ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.graph import build
from icarus_memory.model import Provenance, SourceType, Status
from icarus_memory.proposals import Evidence, ProposalStore, ProposalState
from icarus_memory.store import SelfModelStore
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore


UTC = timezone.utc
AT = datetime(2026, 9, 5, 10, tzinfo=UTC)


def _memory(path: Path):
    episodes = EpisodeStore(path / "episodes.sqlite3")
    proposals = ProposalStore(path / "proposals.sqlite3")
    claims = ClaimStore(path / "knowledge.sqlite3")
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    return episodes, proposals, claims, service


def _episode(episodes: EpisodeStore, body: str) -> Any:
    return episodes.record(
        EpisodeKind.MESSAGE,
        "Beleg",
        body,
        Provenance(
            source_type=SourceType.EMAIL,
            source_ref=f"mail:{body}",
            captured_at=AT,
        ),
        participants=["Ada"],
        occurred_at=AT,
    )[0]


def _propose(
    service: KnowledgeService,
    episodes: EpisodeStore,
    *,
    subject_ref: str = "person:ada",
    predicate: str = "works_on",
    value: str = "Atlas",
    target_ref: str | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    depends_on: list[str] | None = None,
    statement: str | None = None,
):
    text = statement or f"{subject_ref} {predicate} {value}"
    episode = _episode(episodes, text)
    return service.propose(
        subject_ref=subject_ref,
        predicate=predicate,
        value=value,
        statement=text,
        rationale="Im Beleg genannt.",
        evidence=[Evidence(episode.id, episode.body, episode.digest)],
        target_ref=target_ref,
        valid_from=valid_from,
        valid_until=valid_until,
        depends_on=depends_on,
        at=AT,
    )[0]


def test_multiple_work_targets_remain_active_and_pending(tmp_path: Path) -> None:
    episodes, proposals, claims, service = _memory(tmp_path)
    first = _propose(service, episodes, value="Atlas", target_ref="project:atlas")
    first_claim = service.accept(first.id, supersedes=[], at=AT)

    second = _propose(service, episodes, value="Lumen", target_ref="project:lumen")
    assert claims.conflicts_for(second) == []
    assert proposals.get(second.id).state is ProposalState.PENDING
    assert claims.get(first_claim.id).status is Status.ACTIVE

    second_claim = service.accept(second.id, supersedes=[], at=AT)
    assert claims.get(first_claim.id).status is Status.ACTIVE
    assert claims.get(second_claim.id).status is Status.ACTIVE


def test_status_aliases_require_explicit_replacement(tmp_path: Path) -> None:
    episodes, _, claims, service = _memory(tmp_path)
    first = _propose(service, episodes, predicate="hat_status", value="aktiv")
    old = service.accept(first.id, supersedes=[], at=AT)
    second = _propose(service, episodes, predicate="status", value="pausiert")

    assert [item.id for item in claims.conflicts_for(second)] == [old.id]
    with pytest.raises(ClaimError, match="ausdrücklich"):
        service.accept(second.id, supersedes=[], at=AT)

    replacement = service.accept(second.id, supersedes=[old.id], at=AT)
    assert claims.get(old.id).status is Status.SUPERSEDED
    assert claims.get(replacement.id).status is Status.ACTIVE


def test_nonoverlapping_history_is_currently_filterable(tmp_path: Path) -> None:
    episodes, _, claims, service = _memory(tmp_path)
    first_start = AT - timedelta(days=4)
    first_end = AT - timedelta(days=2)
    second_start = first_end
    second_end = AT + timedelta(days=2)

    first = _propose(
        service,
        episodes,
        predicate="status",
        value="aktiv",
        valid_from=first_start,
        valid_until=first_end,
    )
    first_claim = service.accept(first.id, supersedes=[], at=AT)
    second = _propose(
        service,
        episodes,
        predicate="status",
        value="pausiert",
        valid_from=second_start,
        valid_until=second_end,
    )
    assert claims.conflicts_for(second) == []
    second_claim = service.accept(second.id, supersedes=[], at=AT)

    assert {item.id for item in claims.all_claims(include_inactive=False, at=first_start + timedelta(hours=1))} == {first_claim.id}
    assert {item.id for item in claims.all_claims(include_inactive=False, at=second_start + timedelta(hours=1))} == {second_claim.id}


def test_multivalue_can_be_explicitly_replaced_when_requested(tmp_path: Path) -> None:
    episodes, _, claims, service = _memory(tmp_path)
    first = _propose(service, episodes, value="Atlas", target_ref="project:atlas")
    old = service.accept(first.id, supersedes=[], at=AT)
    renamed = _propose(
        service,
        episodes,
        value="Atlas Relaunch",
        target_ref="project:atlas",
    )

    assert claims.conflicts_for(renamed) == []
    replacement = service.accept(renamed.id, supersedes=[old.id], at=AT)
    assert claims.get(old.id).status is Status.SUPERSEDED
    assert claims.get(replacement.id).status is Status.ACTIVE


def test_retraction_marks_dependency_chain_disputed_after_restart(tmp_path: Path) -> None:
    episodes, proposals, claims, service = _memory(tmp_path)
    base = _propose(service, episodes, predicate="status", value="basis")
    base_claim = service.accept(base.id, supersedes=[], at=AT)
    dependent = _propose(
        service,
        episodes,
        predicate="derived_from",
        value="ableitung eins",
        depends_on=[base_claim.id],
    )
    dependent_claim = service.accept(dependent.id, supersedes=[], at=AT)
    transitive = _propose(
        service,
        episodes,
        predicate="derived_next",
        value="ableitung zwei",
        depends_on=[dependent_claim.id],
    )
    transitive_claim = service.accept(transitive.id, supersedes=[], at=AT)
    claims.close()
    proposals.close()

    restarted = ClaimStore(tmp_path / "knowledge.sqlite3")
    retracted = restarted.retract(base_claim.id, reason="Die Grundlage war falsch.", at=AT)
    assert retracted.status is Status.RETRACTED
    assert restarted.get(dependent_claim.id).status is Status.DISPUTED
    assert restarted.get(transitive_claim.id).status is Status.DISPUTED
    assert {item["claim_id"] for item in restarted.changes()} >= {
        base_claim.id,
        dependent_claim.id,
        transitive_claim.id,
    }
    restarted.close()


def test_stale_dependency_is_rejected_at_acceptance(tmp_path: Path) -> None:
    episodes, _, claims, service = _memory(tmp_path)
    base = _propose(
        service,
        episodes,
        predicate="status",
        value="nur historisch",
        valid_from=AT - timedelta(days=2),
        valid_until=AT - timedelta(days=1),
    )
    base_claim = service.accept(base.id, supersedes=[], at=AT)
    candidate = _propose(
        service,
        episodes,
        predicate="derived_from",
        value="stale ableitung",
        depends_on=[base_claim.id],
    )

    with pytest.raises(ClaimError, match="nicht mehr gültig"):
        service.accept(candidate.id, supersedes=[], at=AT)
    assert claims.get(base_claim.id).status is Status.ACTIVE


def test_conflicting_candidates_on_two_connections_only_one_wins(tmp_path: Path) -> None:
    episodes, proposals, claims, service = _memory(tmp_path)
    first = _propose(service, episodes, predicate="status", value="aktiv")
    second = _propose(service, episodes, predicate="status", value="pausiert")
    episodes.close()
    proposals.close()
    claims.close()

    def accept(proposal_id: str):
        local_episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
        local_proposals = ProposalStore(tmp_path / "proposals.sqlite3")
        local_claims = ClaimStore(tmp_path / "knowledge.sqlite3")
        local_service = KnowledgeService(
            proposals=local_proposals,
            claims=local_claims,
            episodes=local_episodes,
        )
        try:
            return ("accepted", local_service.accept(proposal_id, supersedes=[], at=AT))
        except ClaimError as exc:
            return ("rejected", str(exc))
        finally:
            local_episodes.close()
            local_proposals.close()
            local_claims.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(accept, (first.id, second.id)))

    assert [item[0] for item in results].count("accepted") == 1
    assert [item[0] for item in results].count("rejected") == 1
    final = ClaimStore(tmp_path / "knowledge.sqlite3")
    assert len(final.all_claims()) == 1
    final.close()


def test_registered_entity_graph_edge_survives_target_rename(tmp_path: Path) -> None:
    episodes, _, claims, service = _memory(tmp_path)
    person = claims.entities.create("person", "Ada", explicit_id="person:ada")
    project = claims.entities.create("project", "Atlas", explicit_id="project:atlas")
    candidate = _propose(
        service,
        episodes,
        subject_ref=person["id"],
        value="Atlas",
        target_ref=project["id"],
    )
    service.accept(candidate.id, supersedes=[], at=AT)

    workspace = WorkspaceStore(tmp_path / "workspace.sqlite3")
    tasks = TaskStore(tmp_path / "tasks.sqlite3")
    self_model = SelfModelStore(MemoryBackend(), subject_id="local")
    before = build(
        episodes=episodes,
        workspace=workspace,
        tasks=tasks,
        store=self_model,
        knowledge=claims,
        at=AT,
    )
    direct_before = [
        edge for edge in before.edges
        if edge.source == person["id"] and edge.target == project["id"]
    ]
    assert len(direct_before) == 1
    assert direct_before[0].relation == "works_on"
    assert next(node for node in before.nodes if node.id == project["id"]).label == "Atlas"

    renamed = claims.entities.rename(project["id"], "Atlas Relaunch")
    after = build(
        episodes=episodes,
        workspace=workspace,
        tasks=tasks,
        store=self_model,
        knowledge=claims,
        at=AT,
    )
    direct_after = [
        edge for edge in after.edges
        if edge.source == person["id"] and edge.target == renamed["id"]
    ]
    assert len(direct_after) == 1
    assert direct_after[0].id == direct_before[0].id
    assert next(node for node in after.nodes if node.id == renamed["id"]).label == "Atlas Relaunch"
    claims.close()
    episodes.close()
    workspace.close()
    tasks.close()
