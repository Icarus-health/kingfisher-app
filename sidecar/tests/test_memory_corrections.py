"""Korrekturen müssen bis zum Modellkontext und über Neustarts wirken."""
from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from icarus_memory import claims as claims_module
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.backends import MemoryBackend
from icarus_memory.claims import ClaimStore, KnowledgeService, ClaimError
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType, now
from icarus_memory.policy import Policy
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.providers import Reply, ToolCall
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from icarus_memory.tools import build_registry


class LocalProvider:
    name = "local-test"
    model = "test"
    is_local = True

    def __init__(self):
        self.seen = []
        self.on_complete = None

    def complete(self, messages, tools):
        self.seen.append(messages)
        if self.on_complete:
            return self.on_complete()
        return Reply(text="Alte Antwort: Kranz gehört zum Projekt Atlas.")


@pytest.fixture
def setup_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    store = SelfModelStore(MemoryBackend(), subject_id="local")
    audit = AuditLog(tmp_path / "audit.sqlite3")
    provider = LocalProvider()
    agent = Agent(store, Policy(), audit, build_registry(store), provider=provider,
                  knowledge=claims, episodes=episodes)
    app = create_app(store=store, agent=agent, audit=audit, episodes=episodes,
                     proposals=proposals, knowledge=claims)
    yield episodes, claims, service, agent, provider, TestClient(app)
    claims.close()
    proposals.close()
    episodes.close()
    audit.close()


def accept(episodes, service, **extra):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, "Quelle", "Kranz gehört zum Projekt Atlas.",
                                 Provenance(source_type=SourceType.USER_STATED, source_ref="test"))
    proposal, _ = service.propose(subject_ref="person:kranz", predicate="works_on", value="Atlas",
                                  statement=episode.body, rationale="Explizite Nutzerangabe",
                                  evidence=[Evidence(episode.id, episode.body, episode.digest)], **extra)
    return service.accept(proposal.id, supersedes=[])


def test_retracted_fact_and_old_reply_do_not_reenter_model_history(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    claim = accept(episodes, service)
    first = agent.send("Was weißt du über Kranz und Atlas?")
    assert any(item["assertion_id"] == f"claim:{claim.id}" for item in first.context["items"])
    claims.retract(claim.id, reason="Falsche Zuordnung")
    second = agent.send("Welche Projekte sind bekannt?")
    assert all(item["assertion_id"] != f"claim:{claim.id}" for item in second.context["items"])
    assert not any(item["role"] == "assistant" for item in provider.seen[-1])
    assert "Kranz gehört" not in provider.seen[-1][0]["content"]


def test_correction_during_generation_discards_reply_and_tool_calls(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    claim = accept(episodes, service)
    def correction():
        claims.retract(claim.id, reason="Während Generierung korrigiert")
        return Reply(text="Veraltete Antwort", tool_calls=[ToolCall("1", "aktuelle_zeit", {})])
    provider.on_complete = correction
    turn = agent.send("Was weißt du über Kranz?")
    assert "Veraltete Antwort" not in turn.reply
    assert turn.used_tools == []
    assert turn.approvals == []
    assert turn.context["invalidated"] is True


def test_persisted_transcript_remains_visible_but_stale_reply_is_not_context(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    claim = accept(episodes, service)
    conversation = client.post("/api/v1/conversations", json={}).json()
    cid = conversation["conversation"]["id"]
    first = client.post(f"/api/v1/conversations/{cid}/messages", json={"message": "Was weißt du über Kranz?"})
    assert first.status_code == 201
    retract = client.post(f"/api/v1/memory/claims/{claim.id}/retract", json={"reason": "Falsche Zuordnung"})
    assert retract.status_code == 200
    second = client.post(f"/api/v1/conversations/{cid}/messages", json={"message": "Welche Projekte kennst du?"})
    assert second.status_code == 201
    assert not any(item["role"] == "assistant" for item in provider.seen[-1])
    assert any("Alte Antwort" in item["content"] for item in second.json()["messages"])


def test_expired_dependency_is_unusable_without_a_mutation(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    moment = now()
    basis = accept(episodes, service, valid_until=moment + timedelta(days=1))
    derived = accept(episodes, service, depends_on=[basis.id])
    future = moment + timedelta(days=2)
    assert {basis.id, derived.id}.issubset({item.id for item in claims.all_claims(include_inactive=False, at=moment)})
    assert claims.all_claims(include_inactive=False, at=future) == []


def test_v2_document_survives_upgrade_and_can_be_retracted(tmp_path):
    path = tmp_path / "knowledge.sqlite3"
    data = {"id": "k-old", "proposal_id": "v-old", "subject_ref": "person:old", "predicate": "status",
            "value": "active", "statement": "Alte Aussage", "scope_ref": None, "confidence": None,
            "status": "active", "evidence": [], "created_at": now().isoformat(),
            "supersedes": [], "superseded_by": None}
    with sqlite3.connect(path) as connection:
        claims_module._migrate_v1(connection)
        claims_module._migrate_v2(connection)
        connection.execute("PRAGMA user_version=2")
        connection.execute("INSERT INTO knowledge_claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (data["id"], data["proposal_id"], data["subject_ref"], data["predicate"], data["value"],
                            None, data["statement"], "[]", data["created_at"], data["status"], json.dumps(data)))
    claims = ClaimStore(path)
    assert claims.get("k-old").target_ref is None
    claims.retract("k-old", reason="Korrektur nach Upgrade")
    claims.close()
    reopened = ClaimStore(path)
    assert reopened.get("k-old").status.value == "retracted"
    assert reopened.changes()[0]["reason"] == "Korrektur nach Upgrade"
    reopened.close()


def test_generated_summary_cannot_become_evidence(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    summary, _ = episodes.record(EpisodeKind.SUMMARY, "Zusammenfassung", "Kranz leitet Atlas.",
                                 Provenance(source_type=SourceType.INFERENCE, source_ref="model"))
    with pytest.raises(ClaimError, match="Zusammenfassungen"):
        service.propose(subject_ref="person:kranz", predicate="has_role", value="Leitung",
                        statement=summary.body, rationale="Modellverdichtung",
                        evidence=[Evidence(summary.id, summary.body, summary.digest)])


def test_registry_http_identity_source_binding_and_rename(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    first = client.post("/api/v1/memory/registry", json={"kind": "person", "label": "Alex"}).json()
    second = client.post("/api/v1/memory/registry", json={"kind": "person", "label": "Alex"}).json()
    assert first["id"] != second["id"]
    found = client.get("/api/v1/memory/registry", params={"label": "Alex"}).json()["entities"]
    assert len(found) == 2
    source = {"source": "contacts", "account": "work", "native_id": "42"}
    assert client.post(f"/api/v1/memory/registry/{first['id']}/sources", json=source).status_code == 200
    assert client.post(f"/api/v1/memory/registry/{second['id']}/sources", json=source).status_code == 409
    assert client.request("DELETE", f"/api/v1/memory/registry/{second['id']}/sources", json=source).status_code == 409
    renamed = client.patch(f"/api/v1/memory/registry/{first['id']}", json={"label": "Alex Kranz"}).json()
    assert renamed["id"] == first["id"]
    assert client.get(f"/api/v1/memory/registry/{first['id']}").json()["entity"]["label"] == "Alex Kranz"
    assert client.request("DELETE", f"/api/v1/memory/registry/{first['id']}/sources", json=source).status_code == 200
    assert claims.entities.get(first["id"]) is not None


def test_backup_preserves_identity_bindings_and_correction_journal(setup_memory, tmp_path):
    from icarus_memory.backup import snapshot_all, restore_all
    episodes, claims, service, agent, provider, client = setup_memory
    entity = claims.entities.create("person", "Alex")
    claims.entities.link_source(entity["id"], "contacts", "work", "42")
    claim = accept(episodes, service)
    claims.retract(claim.id, reason="Falscher Kontakt")
    saved = snapshot_all(tmp_path, tmp_path / "backups")
    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    restore_all(saved, restored_dir)
    restored = ClaimStore(restored_dir / "knowledge.sqlite3")
    assert restored.entities.resolve_source("contacts", "work", "42")["id"] == entity["id"]
    assert restored.get(claim.id).status.value == "retracted"
    assert restored.revision == claims.revision
    assert restored.changes() == claims.changes()
    restored.close()


def test_registry_profiles_keep_namesakes_and_incoming_relations_separate(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    first = claims.entities.create("person", "Alex")
    second = claims.entities.create("person", "Alex")
    project = claims.entities.create("project", "Atlas")
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, "Quelle", "Alex arbeitet an Atlas.",
        Provenance(source_type=SourceType.USER_STATED, source_ref="test:profiles"),
    )
    proposal, _ = service.propose(
        subject_ref=first["id"], predicate="works_on", value="Atlas",
        target_ref=project["id"], statement=episode.body, rationale="Explizit zugeordnet",
        evidence=[Evidence(episode.id, episode.body, episode.digest)],
    )
    claim = service.accept(proposal.id, supersedes=[])
    def profile(entity):
        response = client.get(f"/api/v1/memory/registry/{entity['id']}")
        assert response.status_code == 200
        return response.json()
    assert [c["id"] for c in profile(first)["claims"]] == [claim.id]
    assert profile(second)["claims"] == []
    assert [c["id"] for c in profile(project)["claims"]] == [claim.id]
    claims.entities.rename(first["id"], "Alex Kranz")
    assert profile(first)["entity"]["label"] == "Alex Kranz"
    assert profile(second)["entity"]["label"] == "Alex"
    claims.retract(claim.id, reason="Falsche Zuordnung")
    for entity in (first, project):
        assert profile(entity)["claims"] == []
        assert [c["id"] for c in profile(entity)["claim_history"]] == [claim.id]


def test_identity_clarification_sources_namesakes_and_persistent_claims(setup_memory, tmp_path):
    episodes, claims, service, agent, provider, client = setup_memory
    first = claims.entities.create("person", "Alex")
    second = claims.entities.create("person", "Alex")
    claims.entities.create("project", "Alex")  # Same label, different kind is not a namesake.
    own_source = {"source": "contacts", "account": "work", "native_id": "42"}
    other_source = {"source": "contacts", "account": "private", "native_id": "42"}
    retained_source = {"source": "mail", "account": "work", "native_id": "42"}
    for entity, source in ((first, own_source), (second, other_source), (first, retained_source)):
        response = client.post(f"/api/v1/memory/registry/{entity['id']}/sources", json=source)
        assert response.status_code == 200
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, "Quelle", "Alex arbeitet an Atlas.",
        Provenance(source_type=SourceType.USER_STATED, source_ref="test:clarification"),
    )
    proposal, _ = service.propose(
        subject_ref=first["id"], predicate="works_on", value="Atlas",
        statement=episode.body, rationale="Explizit zugeordnet",
        evidence=[Evidence(episode.id, episode.body, episode.digest)],
    )
    claim = service.accept(proposal.id, supersedes=[])

    def profile(entity):
        response = client.get(f"/api/v1/memory/registry/{entity['id']}")
        assert response.status_code == 200
        return response.json()

    before_revision = claims.revision
    assert profile(first)["sources"] == [own_source, retained_source]
    assert profile(second)["sources"] == [other_source]
    assert [item["id"] for item in profile(first)["same_name_entities"]] == [second["id"]]
    assert [item["id"] for item in profile(second)["same_name_entities"]] == [first["id"]]
    assert claims.revision == before_revision
    assert client.request("DELETE", f"/api/v1/memory/registry/{second['id']}/sources",
                          json=own_source).status_code == 409
    assert profile(first)["sources"] == [own_source, retained_source]

    response = client.patch(f"/api/v1/memory/registry/{first['id']}", json={"label": "Alex Kranz"})
    assert response.status_code == 200
    assert response.json()["id"] == first["id"]
    assert profile(first)["same_name_entities"] == []
    assert profile(second)["same_name_entities"] == []
    assert client.request("DELETE", f"/api/v1/memory/registry/{first['id']}/sources",
                          json=own_source).status_code == 200
    assert profile(first)["sources"] == [retained_source]
    assert profile(second)["sources"] == [other_source]
    # Unlinking an import identity does not silently retract established knowledge.
    assert [item["id"] for item in profile(first)["claims"]] == [claim.id]
    assert claims.get(claim.id).subject_ref == first["id"]
    assert claims.get(claim.id).status.value == "active"

    reopened = ClaimStore(tmp_path / "knowledge.sqlite3")
    try:
        assert reopened.entities.get(first["id"])["label"] == "Alex Kranz"
        assert reopened.entities.resolve_source(**own_source) is None
        assert reopened.entities.resolve_source(**other_source)["id"] == second["id"]
        assert reopened.entities.sources(first["id"]) == [retained_source]
        assert reopened.get(claim.id).subject_ref == first["id"]
        assert reopened.get(claim.id).status.value == "active"
    finally:
        reopened.close()


def test_registry_profile_resolves_exact_related_identities_and_history(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    person = claims.entities.create('person', 'Alex')
    other = claims.entities.create('person', 'Alex')
    project = claims.entities.create('project', 'Atlas')
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Beziehung', 'Alex berät Alex bei Atlas.',
        Provenance(source_type=SourceType.USER_STATED))
    proposal, _ = service.propose(subject_ref=person['id'], target_ref=other['id'],
        scope_ref=project['id'], predicate='advises', value='Beratung',
        statement=episode.body, rationale='Ausdrücklich zugeordnet',
        evidence=[Evidence(episode.id, episode.body, episode.digest)])
    claim = service.accept(proposal.id, supersedes=[])
    url=f"/api/v1/memory/registry/{person['id']}"
    data=client.get(url).json()
    assert set(data['related_entities']) == {person['id'], other['id'], project['id']}
    context = client.get(f"/api/v1/memory/registry/{project['id']}").json()
    assert [item['id'] for item in context['claims']] == [claim.id]
    assert data['related_entities'][person['id']]['label'] == 'Alex'
    assert data['related_entities'][other['id']]['label'] == 'Alex'
    claims.entities.rename(other['id'], 'Alex Kranz')
    claims.retract(claim.id, reason='Beziehung beendet')
    data=client.get(url).json()
    assert data['claims'] == []
    assert data['claim_history'][0]['id'] == claim.id
    assert data['related_entities'][other['id']]['label'] == 'Alex Kranz'

    context = client.get(f"/api/v1/memory/registry/{project['id']}").json()
    assert context['claims'] == []
    assert context['claim_history'][0]['id'] == claim.id


def test_registry_profile_resolves_workspace_project_references_without_name_matching(setup_memory):
    episodes, claims, service, agent, provider, client = setup_memory
    person = claims.entities.create('person', 'Alex')
    project = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()
    other = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Projektbeleg', 'Alex arbeitet an Atlas.',
        Provenance(source_type=SourceType.USER_STATED))
    proposal, _ = service.propose(subject_ref=person['id'], target_ref='project:'+project['id'],
        scope_ref=project['id'], predicate='works_on', value='Mitarbeit', statement=episode.body,
        rationale='Explizite Zuordnung', evidence=[Evidence(episode.id, episode.body, episode.digest)])
    claim = service.accept(proposal.id, supersedes=[])
    def profile():
        return client.get('/api/v1/memory/registry/'+person['id']).json()
    data = profile()
    for ref in ('project:'+project['id'], project['id']):
        assert data['related_entities'][ref]['label'] == 'Atlas'
        assert data['related_entities'][ref]['workspace_project_id'] == project['id']
    assert other['id'] not in data['related_entities']
    assert claims.entities.get('project:'+project['id']) is None  # Keine zweite Projektablage.
    claims.retract(claim.id, reason='Zuordnung beendet')
    assert profile()['claim_history'][0]['id'] == claim.id
    assert profile()['related_entities'][project['id']]['workspace_project_id'] == project['id']
