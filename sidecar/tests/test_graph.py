"""Der Gedächtnisgraph verbindet belegte Quellen, ohne Wahrheit zu erfinden."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.backends import MemoryBackend
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.graph import (
    build,
    entity_directory,
    person_id,
    person_profile,
    project_profile,
)
from icarus_memory.model import Kind, Provenance, SourceType
from icarus_memory.policy import Policy
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from icarus_memory.tasks import TaskStore
from icarus_memory.tools import build_registry
from icarus_memory.workspace import WorkspaceStore

JETZT = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)


def _prov(source: SourceType = SourceType.EMAIL, ref: str = "mail:1") -> Provenance:
    return Provenance(source_type=source, source_ref=ref, captured_at=JETZT)


def _stores(tmp_path: Path):
    return (
        EpisodeStore(tmp_path / "episodes.sqlite3"),
        WorkspaceStore(tmp_path / "workspace.sqlite3"),
        TaskStore(tmp_path / "tasks.sqlite3"),
        SelfModelStore(MemoryBackend(), subject_id="local"),
    )


def test_eine_person_kann_mehrere_belegte_projektkontexte_haben(tmp_path: Path) -> None:
    episodes, workspace, tasks, store = _stores(tmp_path)
    vdd = workspace.add_project("VDD Digitalisierung", _prov(SourceType.USER_STATED))
    ir = workspace.add_project("IR-Kliniken", _prov(SourceType.USER_STATED))
    for project, ref in ((vdd, "mail:vdd"), (ir, "meeting:ir")):
        episodes.record(
            EpisodeKind.MESSAGE,
            project.name,
            f"Eine Aussage zu {project.name}, deren Wahrheit noch nicht bestätigt ist.",
            _prov(ref=ref),
            participants=["Dr. Kranz"],
            project_id=project.id,
        )

    result = build(
        episodes=episodes, workspace=workspace, tasks=tasks, store=store, at=JETZT
    ).to_dict()

    people = [n for n in result["nodes"] if n["kind"] == "person"]
    assert len(people) == 1
    involved = [
        e for e in result["edges"]
        if e["source"] == person_id("dr. kranz") and e["relation"] == "involved_in"
    ]
    assert {e["scope"] for e in involved} == {vdd.id, ir.id}
    assert all(e["evidence_refs"] for e in involved)


def test_mailinhalt_wird_nicht_als_fachliche_beziehung_behauptet(tmp_path: Path) -> None:
    episodes, workspace, tasks, store = _stores(tmp_path)
    episodes.record(
        EpisodeKind.MESSAGE,
        "Mail",
        "Dr. Kranz schreibt, er sei Geschäftsführer der Beispiel GmbH.",
        _prov(),
        participants=["Dr. Kranz"],
    )

    result = build(
        episodes=episodes, workspace=workspace, tasks=tasks, store=store, at=JETZT
    ).to_dict()

    assert {e["relation"] for e in result["edges"]} == {"participated_in"}
    assert not any("Beispiel GmbH" in n["label"] for n in result["nodes"])


def test_personenprofil_zeigt_kontexte_und_quellen_statt_freitextdeutung(
    tmp_path: Path,
) -> None:
    episodes, workspace, tasks, store = _stores(tmp_path)
    project = workspace.add_project("Kingfisher", _prov(SourceType.USER_STATED))
    episode, _ = episodes.record(
        EpisodeKind.INTERACTION,
        "Projektgespräch",
        "Wir haben über den nächsten Prototyp gesprochen.",
        _prov(SourceType.CHAT, "chat:42"),
        participants=["Jörn Probe"],
        project_id=project.id,
        tags=["UI"],
        occurred_at=JETZT,
    )

    profile = person_profile(
        "jörn probe",
        episodes=episodes,
        workspace=workspace,
        tasks=tasks,
        store=store,
        at=JETZT,
    )

    assert profile is not None
    assert profile["contexts"][0]["project"]["name"] == "Kingfisher"
    assert profile["contexts"][0]["evidence_refs"] == [f"episode:{episode.id}"]
    assert profile["interactions"][0]["source_ref"] == "chat:42"
    assert "body" not in profile["interactions"][0]


def test_entitaetsverzeichnis_ist_belegt_und_deterministisch(tmp_path: Path) -> None:
    episodes, workspace, tasks, store = _stores(tmp_path)
    project = workspace.add_project("Kingfisher", _prov(SourceType.USER_STATED))
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE,
        "Projektgespräch",
        "Der aktuelle Stand wurde besprochen.",
        _prov(SourceType.CHAT, "conversation:42"),
        participants=["Dr. Kranz"],
        project_id=project.id,
        tags=["Gedächtnis"],
        occurred_at=JETZT,
    )
    decision = store.record(
        "Kingfisher bleibt lokal.",
        Kind.DECISION,
        _prov(SourceType.USER_STATED, "decision:local"),
    )

    directory = entity_directory(
        build(
            episodes=episodes,
            workspace=workspace,
            tasks=tasks,
            store=store,
            at=JETZT,
        )
    )

    assert [(item["kind"], item["label"]) for item in directory] == [
        ("decision", decision.statement),
        ("person", "Dr. Kranz"),
        ("project", "Kingfisher"),
        ("topic", "Gedächtnis"),
    ]
    person = next(item for item in directory if item["id"] == person_id("Dr. Kranz"))
    assert person["connection_count"] == 3
    assert person["sources"] == [{
        "node_id": f"episode:{episode.id}",
        "source_type": "chat",
        "source_ref": "conversation:42",
        "occurred_at": JETZT.astimezone().isoformat(),
    }]


def test_projektakte_buendelt_team_aufgaben_notizen_und_episoden(tmp_path: Path) -> None:
    episodes, workspace, tasks, store = _stores(tmp_path)
    project = workspace.add_project("Kingfisher", _prov(SourceType.USER_STATED))
    episodes.record(
        EpisodeKind.MESSAGE,
        "Jour fixe",
        "Status besprochen.",
        _prov(),
        participants=["Dr. Kranz"],
        project_id=project.id,
    )
    tasks.add("Prototyp prüfen", _prov(SourceType.USER_STATED), project_id=project.id)
    workspace.add_note(
        "Entwurf",
        "Arbeitsstand",
        _prov(SourceType.DOCUMENT, "note.md"),
        project_id=project.id,
    )

    profile = project_profile(
        project.id, episodes=episodes, workspace=workspace, tasks=tasks
    )

    assert [p["name"] for p in profile["people"]] == ["Dr. Kranz"]
    assert [t["title"] for t in profile["tasks"]] == ["Prototyp prüfen"]
    assert [n["title"] for n in profile["notes"]] == ["Entwurf"]
    assert [e["title"] for e in profile["episodes"]] == ["Jour fixe"]


def test_profile_trennt_aktuellen_claim_von_ersetzter_historie(tmp_path: Path) -> None:
    """Korrekturen bleiben prüfbar, ohne als zweiter aktueller Stand zu gelten."""
    episodes, workspace, tasks, store = _stores(tmp_path)
    project = workspace.add_project("Kingfisher", _prov(SourceType.USER_STATED))
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE,
        "Gespräch",
        "Dr. Kranz leitet Kingfisher nicht mehr.",
        _prov(SourceType.CHAT, "conversation:42"),
        participants=["Dr. Kranz"],
        project_id=project.id,
    )
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    knowledge = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)

    first, _ = knowledge.propose(
        subject_ref=person_id("Dr. Kranz"),
        predicate="project_role",
        value="leitet Kingfisher",
        statement="Dr. Kranz leitet Kingfisher.",
        rationale="Vom Nutzer bestätigt.",
        evidence=[Evidence(episode.id, episode.body, episode.digest)],
        at=JETZT,
    )
    old_claim = knowledge.accept(first.id, supersedes=[], at=JETZT)
    second, _ = knowledge.propose(
        subject_ref=person_id("Dr. Kranz"),
        predicate="project_role",
        value="leitet Kingfisher nicht mehr",
        statement="Dr. Kranz leitet Kingfisher nicht mehr.",
        rationale="Vom Nutzer korrigiert.",
        evidence=[Evidence(episode.id, episode.body, episode.digest)],
        at=JETZT,
    )
    current_claim = knowledge.accept(second.id, supersedes=[old_claim.id], at=JETZT)
    project_candidate, _ = knowledge.propose(
        subject_ref=f"project:{project.id}",
        predicate="phase",
        value="laufend",
        statement="Kingfisher ist laufend.",
        rationale="Vom Nutzer bestätigt.",
        evidence=[Evidence(episode.id, episode.body, episode.digest)],
        at=JETZT,
    )
    project_claim = knowledge.accept(project_candidate.id, supersedes=[], at=JETZT)

    person = person_profile(
        "Dr. Kranz",
        episodes=episodes,
        workspace=workspace,
        tasks=tasks,
        store=store,
        knowledge=claims,
        at=JETZT,
    )
    project_profile_data = project_profile(
        project.id,
        episodes=episodes,
        workspace=workspace,
        tasks=tasks,
        knowledge=claims,
    )

    assert person is not None
    assert [item["id"] for item in person["claims"]] == [current_claim.id]
    assert [item["id"] for item in person["claim_history"]] == [old_claim.id]
    assert person["claims"][0]["evidence"][0]["episode_id"] == episode.id
    assert [item["id"] for item in project_profile_data["claims"]] == [project_claim.id]
    assert project_profile_data["claim_history"] == []


def test_entscheidung_verweist_auf_ihre_grundlage(tmp_path: Path) -> None:
    episodes, workspace, tasks, store = _stores(tmp_path)
    basis = store.record(
        "SQLite bleibt lokal.", Kind.CONSTRAINT, _prov(SourceType.USER_STATED)
    )
    decision = store.record(
        "Kingfisher läuft in Docker.",
        Kind.DECISION,
        _prov(SourceType.USER_STATED),
        derived_from=[basis.id],
    )

    result = build(
        episodes=episodes, workspace=workspace, tasks=tasks, store=store, at=JETZT
    ).to_dict()
    edge = next(e for e in result["edges"] if e["relation"] == "based_on")

    assert edge["source"] == f"assertion:{decision.id}"
    assert edge["target"] == f"assertion:{basis.id}"
    assert edge["state"] == "confirmed"


def test_graph_und_profile_sind_geschuetzte_lese_api(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    episodes, workspace, tasks, store = _stores(tmp_path)
    audit = AuditLog(tmp_path / "audit.sqlite3")
    project = workspace.add_project("Kingfisher", _prov(SourceType.USER_STATED))
    episodes.record(
        EpisodeKind.MESSAGE,
        "Gespräch",
        "Status.",
        _prov(),
        participants=["Dr. Kranz"],
        project_id=project.id,
    )
    agent = Agent(store, Policy(), audit, build_registry(store, task_store=tasks))
    app = create_app(
        store=store,
        agent=agent,
        audit=audit,
        tasks=tasks,
        workspace=workspace,
        episodes=episodes,
    )
    client = TestClient(app)

    graph_response = client.get("/api/v1/memory/graph")
    entities_response = client.get("/api/v1/memory/entities")
    person_response = client.get("/api/v1/memory/people/Dr.%20Kranz")
    project_response = client.get(f"/api/v1/memory/projects/{project.id}")

    assert graph_response.status_code == 200
    assert graph_response.json()["authority"] == "projection"
    assert entities_response.status_code == 200
    assert entities_response.json()["authority"] == "projection"
    assert {item["kind"] for item in entities_response.json()["entities"]} == {
        "person", "project"
    }
    assert person_response.status_code == 200
    assert project_response.status_code == 200
    assert client.post("/api/v1/memory/graph", json={}).status_code == 405


def test_project_profile_includes_target_and_context_relations_without_name_inference(tmp_path):
    episodes, workspace, tasks, store = _stores(tmp_path)
    project=workspace.add_project('Atlas',_prov())
    other=workspace.add_project('Atlas',_prov())
    proposals=ProposalStore(tmp_path/'proposals.sqlite3')
    claims=ClaimStore(tmp_path/'knowledge.sqlite3')
    service=KnowledgeService(proposals=proposals,claims=claims,episodes=episodes)
    accepted=[]
    for index,(target,scope) in enumerate([(f'project:{project.id}',None),(None,project.id),(None,f'project:{project.id}'),(f'project:{other.id}',None)]):
        person=claims.entities.create('person','Alex')
        episode,_=episodes.record(EpisodeKind.MESSAGE,'Beleg',f'Belegter Projektbezug {index}.',_prov())
        proposal,_=service.propose(subject_ref=person['id'],target_ref=target,scope_ref=scope,predicate='works_on',value='Mitarbeit',statement=episode.body,rationale='Explizite Zuordnung',evidence=[Evidence(episode.id,episode.body,episode.digest)])
        accepted.append(service.accept(proposal.id,supersedes=[]))
    def profile():
        return project_profile(project.id,episodes=episodes,workspace=workspace,tasks=tasks,knowledge=claims)
    assert {item['id'] for item in profile()['claims']}=={item.id for item in accepted[:3]}
    assert {item['id'] for item in profile()['people']} == {item.subject_ref for item in accepted[:3]}
    assert all(item['identity_resolution'] == 'explicit_registry' for item in profile()['people'])
    claims.retract(accepted[0].id,reason='Zuordnung korrigiert')
    changed=profile()
    assert {item['id'] for item in changed['claims']}=={item.id for item in accepted[1:3]}
    assert {item['id'] for item in changed['people']} == {item.subject_ref for item in accepted[1:3]}
    assert [item['id'] for item in changed['claim_history']]==[accepted[0].id]
    assert changed['claim_history'][0]['evidence'][0]['episode_id']==accepted[0].evidence[0].episode_id


def test_ignored_source_stops_contributing_to_graph_and_profiles(tmp_path):
    episodes, workspace, tasks, store = _stores(tmp_path)
    project = workspace.add_project('Atlas', _prov())
    removed, _ = episodes.record(EpisodeKind.DOCUMENT, 'Entzogener Beleg',
        'Nur diese Quelle ordnet Alex und Robin Atlas zu.', _prov(),
        participants=['Alex', 'Robin'], project_id=project.id, tags=['Entzogenes Thema'])
    kept, _ = episodes.record(EpisodeKind.MESSAGE, 'Verbleibender Kontakt',
        'Alex bleibt ohne Projektbezug bekannt.', _prov(ref='mail:2'), participants=['Alex'])
    episodes.ignore(removed.id)
    profile = person_profile('Alex', episodes=episodes, workspace=workspace, tasks=tasks, store=store)
    assert profile['person']['episoden_anzahl'] == 1
    assert profile['contexts'] == []
    assert [item['id'] for item in profile['interactions']] == [kept.id]
    assert 'Entzogenes Thema' not in profile['person']['themen']
    assert person_profile('Robin', episodes=episodes, workspace=workspace, tasks=tasks, store=store) is None
    project_data = project_profile(project.id, episodes=episodes, workspace=workspace, tasks=tasks)
    assert project_data['people'] == [] and project_data['episodes'] == []
    graph = build(episodes=episodes, workspace=workspace, tasks=tasks, store=store).to_dict()
    assert all(node['id'] not in {person_id('Robin'), f'episode:{removed.id}'} for node in graph['nodes'])
    assert all(f'episode:{removed.id}' not in edge['evidence_refs'] for edge in graph['edges'])
    assert episodes.get(removed.id).body == removed.body  # Herkunft bleibt prüfbar erhalten.
