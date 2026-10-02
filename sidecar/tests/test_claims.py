"""Allgemeines Wissen bleibt Kandidat, bis der Nutzer es bestätigt."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.backends import MemoryBackend
from icarus_memory import claims as claims_module
from icarus_memory.claims import ClaimError, ClaimStore, KnowledgeService
from icarus_memory.consolidation import Consolidator
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.graph import person_id
from icarus_memory.model import Provenance, SourceType
from icarus_memory.policy import Policy
from icarus_memory.proposals import (
    Evidence,
    ProposalKind,
    ProposalState,
    ProposalStore,
    fingerprint,
)
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from icarus_memory.tasks import TaskStore
from icarus_memory.tools import build_registry
from icarus_memory.workspace import WorkspaceStore

JETZT = datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)


def test_legacy_fingerprint_bleibt_bytegenau_stabil() -> None:
    assert fingerprint(
        ProposalKind.ASSERTION,
        "  Aussage   Eins ",
        ["b", "a"],
    ) == "assertion|aussage eins|a,b"


@pytest.fixture
def memory(tmp_path: Path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    return episodes, proposals, claims, service


def _episode(episodes: EpisodeStore, body: str = "Dr. Kranz arbeitet im Projekt Atlas."):
    return episodes.record(
        EpisodeKind.MESSAGE,
        "Gespräch",
        body,
        Provenance(
            source_type=SourceType.EMAIL,
            source_ref="mail:42",
            captured_at=JETZT,
        ),
        participants=["Dr. Kranz"],
        occurred_at=JETZT,
    )[0]


def _propose(service: KnowledgeService, episode, **changes):
    data = {
        "subject_ref": person_id("Dr. Kranz"),
        "predicate": "project_role",
        "value": "Projekt Atlas",
        "statement": "Dr. Kranz arbeitet im Projekt Atlas.",
        "rationale": "Wurde in der Mail so angegeben.",
        "evidence": [Evidence(episode.id, episode.body, episode.digest)],
        "scope_ref": "project:atlas",
        "confidence": 0.8,
        "proposed_by": "test",
        "at": JETZT,
    }
    data.update(changes)
    return service.propose(**data)[0]


def test_kandidat_ist_noch_keine_bestaetigte_aussage(memory) -> None:
    episodes, proposals, claims, service = memory
    candidate = _propose(service, _episode(episodes))

    assert candidate.state is ProposalState.PENDING
    assert claims.all_claims() == []


def test_beleg_muss_digest_und_echtes_zitat_enthalten(memory) -> None:
    episodes, proposals, claims, service = memory
    episode = _episode(episodes)

    with pytest.raises(ClaimError, match="Digest"):
        _propose(
            service,
            episode,
            evidence=[Evidence(episode.id, episode.body, "sha256:falsch")],
        )
    with pytest.raises(ClaimError, match="Zitat"):
        _propose(
            service,
            episode,
            evidence=[Evidence(episode.id, "Hat niemand gesagt.", episode.digest)],
        )


def test_ausdrueckliche_annahme_erzeugt_append_only_wissen(memory) -> None:
    episodes, proposals, claims, service = memory
    candidate = _propose(service, _episode(episodes))

    claim = service.accept(candidate.id, supersedes=[], at=JETZT)

    assert claim.subject_ref == person_id("Dr. Kranz")
    assert claims.get(claim.id).evidence[0].episode_id.startswith("e-")
    assert proposals.get(candidate.id).produced == claim.id
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        claims._conn.execute(  # noqa: SLF001 - der Trigger ist der Vertragsgegenstand
            "UPDATE knowledge_claims SET value = 'Manipuliert' WHERE id = ?",
            (claim.id,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        claims._conn.execute(  # noqa: SLF001 - auch der tatsächliche Leseweg zählt
            "UPDATE knowledge_claims SET document = json_set(document, '$.value', 'Manipuliert') "
            "WHERE id = ?",
            (claim.id,),
        )


def test_v1_wissensspeicher_erhaelt_den_dokumentschutz_beim_upgrade(tmp_path: Path) -> None:
    """Ein vorhandener lokaler Bestand wird additiv auf den neuen Vertrag gehoben."""
    path = tmp_path / "knowledge.sqlite3"
    with sqlite3.connect(path) as connection:
        claims_module._migrate_v1(connection)  # echte v1, kein herabgestuftes v3-Schema
        connection.execute("PRAGMA user_version = 1")
        connection.commit()

    upgraded = ClaimStore(path)
    try:
        with sqlite3.connect(path) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
            trigger = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                "AND name = 'trg_claims_immutable'"
            ).fetchone()[0]
            assert "json_remove" in trigger
    finally:
        upgraded.close()


def test_doppelte_gleichzeitige_annahme_erzeugt_nur_eine_aussage(memory) -> None:
    episodes, proposals, claims, service = memory
    candidate = _propose(service, _episode(episodes))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: service.accept(candidate.id, supersedes=[], at=JETZT),
                range(2),
            )
        )

    assert results[0].id == results[1].id
    assert len(claims.all_claims()) == 1


def test_widerspruch_bleibt_offen_bis_alter_stand_explizit_ersetzt_wird(memory) -> None:
    episodes, proposals, claims, service = memory
    first_episode = _episode(episodes)
    first = _propose(service, first_episode)
    old_claim = service.accept(first.id, supersedes=[], at=JETZT)

    second_episode = _episode(
        episodes, "Dr. Kranz arbeitet nicht mehr im Projekt Atlas."
    )
    second = _propose(
        service,
        second_episode,
        value="Nicht mehr beteiligt",
        statement="Dr. Kranz arbeitet nicht mehr im Projekt Atlas.",
        evidence=[Evidence(second_episode.id, second_episode.body, second_episode.digest)],
    )

    clarifications = service.clarifications()
    assert clarifications[0]["active_claims"][0]["id"] == old_claim.id
    with pytest.raises(ClaimError, match="ausdrücklich"):
        service.accept(second.id, supersedes=[], at=JETZT)

    new_claim = service.accept(second.id, supersedes=[old_claim.id], at=JETZT)
    assert claims.get(old_claim.id).superseded_by == new_claim.id
    assert [item.id for item in claims.by_subject(person_id("Dr. Kranz"))] == [new_claim.id]


def test_unterschiedliche_kontexte_sind_kein_widerspruch(memory) -> None:
    episodes, proposals, claims, service = memory
    episode = _episode(episodes)
    first = _propose(service, episode, scope_ref="project:atlas")
    service.accept(first.id, supersedes=[], at=JETZT)
    other_episode = _episode(episodes, "Dr. Kranz ist privat ein Freund.")
    other = _propose(
        service,
        other_episode,
        value="Freund",
        statement="Dr. Kranz ist privat ein Freund.",
        scope_ref="private",
        evidence=[Evidence(other_episode.id, other_episode.body, other_episode.digest)],
    )

    assert service.clarifications() == []
    service.accept(other.id, supersedes=[], at=JETZT)
    assert len(claims.by_subject(person_id("Dr. Kranz"))) == 2


def test_zwei_offene_kandidaten_werden_als_klaerung_gezeigt(memory) -> None:
    episodes, proposals, claims, service = memory
    first_episode = _episode(episodes)
    _propose(service, first_episode)
    second_episode = _episode(episodes, "Dr. Kranz leitet das Projekt Atlas.")
    _propose(
        service,
        second_episode,
        value="Projektleitung Atlas",
        statement="Dr. Kranz leitet das Projekt Atlas.",
        evidence=[Evidence(second_episode.id, second_episode.body, second_episode.digest)],
    )

    clarifications = service.clarifications()

    assert len(clarifications) == 1
    assert len(clarifications[0]["candidates"]) == 2
    assert clarifications[0]["decision_required"] is True


def test_api_fuehrt_vom_belegten_kandidaten_zur_bestaetigten_aussage(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    tasks = TaskStore(tmp_path / "tasks.sqlite3")
    workspace = WorkspaceStore(tmp_path / "workspace.sqlite3")
    store = SelfModelStore(MemoryBackend(), subject_id="local")
    audit = AuditLog(tmp_path / "audit.sqlite3")
    agent = Agent(store, Policy(), audit, build_registry(store, task_store=tasks))
    app = create_app(
        store=store,
        agent=agent,
        audit=audit,
        tasks=tasks,
        workspace=workspace,
        episodes=episodes,
        proposals=proposals,
        knowledge=claims,
    )
    app.state.consolidator = Consolidator(
        store=store,
        episodes=episodes,
        proposals=proposals,
        provider=agent.provider,
    )
    client = TestClient(app)
    episode = _episode(episodes)
    payload = {
        "subject_ref": person_id("Dr. Kranz"),
        "predicate": "project_role",
        "value": "Projekt Atlas",
        "statement": "Dr. Kranz arbeitet im Projekt Atlas.",
        "scope_ref": "project:atlas",
        "confidence": 0.8,
        "evidence": [{
            "episode_id": episode.id,
            "quote": episode.body,
            "digest": episode.digest,
        }],
    }

    proposed = client.post("/api/v1/memory/candidates", json=payload)
    proposal_id = proposed.json()["candidate"]["id"]
    accepted = client.post(
        f"/api/v1/memory/candidates/{proposal_id}/accept",
        json={"supersedes": []},
    )

    assert proposed.status_code == 201
    assert accepted.status_code == 200
    assert accepted.json()["subject_ref"] == person_id("Dr. Kranz")
    graph = client.get("/api/v1/memory/graph").json()
    assert any(node["kind"] == "claim" for node in graph["nodes"])


def test_alter_selbstmodell_accept_pflegt_keine_entitaetsaussage_ein(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    store = SelfModelStore(MemoryBackend(), subject_id="local")
    audit = AuditLog(tmp_path / "audit.sqlite3")
    agent = Agent(store, Policy(), audit, build_registry(store))
    app = create_app(
        store=store,
        agent=agent,
        audit=audit,
        episodes=episodes,
        proposals=proposals,
        knowledge=claims,
    )
    app.state.consolidator = Consolidator(
        store=store,
        episodes=episodes,
        proposals=proposals,
        provider=agent.provider,
    )
    episode = _episode(episodes)
    candidate = _propose(app.state.knowledge_service, episode)
    client = TestClient(app)

    response = client.post(f"/proposals/{candidate.id}/accept")

    assert response.status_code == 409
    assert store.alles() == []
    assert claims.all_claims() == []

