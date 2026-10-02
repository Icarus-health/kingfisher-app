"""Excluding evidence invalidates knowledge and keeps its audit history."""
from fastapi.testclient import TestClient
import pytest

from icarus_memory.model import Status
from tests.test_claims import memory, _episode, _propose, JETZT
from tests.test_conversation_retraction import _make_app, _close_app, _candidate


def test_source_exclusion_invalidates_transitive_dependents_and_is_idempotent(memory):
    episodes, proposals, claims, service = memory
    source = _episode(episodes)
    root = service.accept(_propose(service, source).id, supersedes=[], at=JETZT)
    other = _episode(episodes, "Kranz kennt Atlas.")
    dependent = service.accept(_propose(service, other, predicate="knows", depends_on=[root.id]).id, supersedes=[], at=JETZT)
    transitive = service.accept(_propose(service, other, predicate="supports", depends_on=[dependent.id]).id, supersedes=[], at=JETZT)
    unaffected = service.accept(_propose(service, other, predicate="mentions").id, supersedes=[], at=JETZT)
    revision = claims.revision
    claims.invalidate_source(source.id)
    assert claims.revision == revision + 3
    for original in (root, dependent, transitive):
        current = claims.get(original.id)
        assert current.status is Status.DISPUTED
        assert not claims.is_usable(current)
        assert current.statement == original.statement
        assert current.evidence == original.evidence
    assert claims.is_usable(claims.get(unaffected.id))
    claims.invalidate_source(source.id)
    assert claims.revision == revision + 3


def test_invalidation_rolls_back_status_and_journal_together(memory, monkeypatch):
    episodes, proposals, claims, service = memory
    source = _episode(episodes)
    root = service.accept(_propose(service, source).id, supersedes=[], at=JETZT)
    revision = claims.revision
    def fail(*args):
        raise RuntimeError("journal unavailable")
    monkeypatch.setattr(claims, "_change", fail)
    with pytest.raises(RuntimeError):
        claims.invalidate_source(source.id)
    assert claims.get(root.id).status is Status.ACTIVE
    assert claims.revision == revision


def test_ignore_clears_context_and_survives_restart(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    proposal = _candidate(client, conversation)
    accepted = client.post(f"/api/v1/conversations/{conversation}/memory-candidates/{proposal}/accept", json={"replace_conflicts": False})
    claim = accepted.json()["memory_candidates"][0]["claim"]
    app.state.conversations.add_message(conversation, "assistant", "Historische Antwort", metadata={"context": {"items": [{"assertion_id": f"claim:{claim['id']}", "statement": claim["statement"]}], "memory_revision": app.state.claims.revision}})
    source_id = claim["evidence"][0]["episode_id"]
    assert client.post(f"/episodes/{source_id}/ignore").status_code == 200
    revision = app.state.claims.revision
    assert client.post(f"/episodes/{source_id}/ignore").status_code == 200
    assert app.state.claims.revision == revision
    snapshot = client.get(f"/api/v1/conversations/{conversation}").json()
    assert snapshot["context"]["items"] == []
    assert app.state.claims.get(claim["id"]).status is Status.DISPUTED
    assert snapshot["memory_candidates"] == []
    assert "Kranz arbeitet an Atlas" not in str(snapshot)
    assert "Historische Antwort" not in str(snapshot)
    _close_app(app)
    restarted = _make_app(tmp_path, monkeypatch)
    try:
        restored = TestClient(restarted).get(f"/api/v1/conversations/{conversation}").json()
        assert restored["context"]["items"] == []
        assert restarted.state.claims.get(claim["id"]).status is Status.DISPUTED
        assert restored["memory_candidates"] == []
        assert "Kranz arbeitet an Atlas" not in str(restored)
        assert "Historische Antwort" not in str(restored)
    finally:
        _close_app(restarted)


def test_archiving_does_not_reactivate_excluded_evidence(memory):
    from datetime import timedelta
    from icarus_memory.episodes import EpisodeState
    from icarus_memory.claims import ClaimError
    episodes, proposals, claims, service = memory
    source = _episode(episodes)
    proposal = _propose(service, source)
    episodes.ignore(source.id)
    episodes.archive_before(JETZT + timedelta(days=1))
    assert episodes.get(source.id).state is EpisodeState.IGNORED
    with pytest.raises(ClaimError):
        service.accept(proposal.id, supersedes=[], at=JETZT)


def test_failed_episode_write_still_excludes_claims(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app, raise_server_exceptions=False)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    proposal = _candidate(client, conversation)
    accepted = client.post(f"/api/v1/conversations/{conversation}/memory-candidates/{proposal}/accept", json={"replace_conflicts": False})
    claim = accepted.json()["memory_candidates"][0]["claim"]
    source = claim["evidence"][0]["episode_id"]
    original = app.state.episodes.ignore
    def fail(*args):
        raise RuntimeError("episode write unavailable")
    monkeypatch.setattr(app.state.episodes, "ignore", fail)
    assert client.post(f"/episodes/{source}/ignore").status_code == 500
    assert app.state.claims.get(claim["id"]).status is Status.DISPUTED
    monkeypatch.setattr(app.state.episodes, "ignore", original)
    assert client.post(f"/episodes/{source}/ignore").status_code == 200
    _close_app(app)


@pytest.mark.parametrize("route", ["conversation", "generic"])
def test_knowledge_acceptance_holds_same_lock_as_exclusion(tmp_path, monkeypatch, route):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]
    proposal = _candidate(client, conversation)
    original = app.state.knowledge_service.accept
    seen = []
    def checked(*args, **kwargs):
        seen.append(app.state.conversation_lock.locked())
        return original(*args, **kwargs)
    monkeypatch.setattr(app.state.knowledge_service, "accept", checked)
    url = (f"/api/v1/conversations/{conversation}/memory-candidates/{proposal}/accept"
           if route == "conversation" else f"/api/v1/memory/candidates/{proposal}/accept")
    assert client.post(url, json={}).status_code == 200
    assert seen == [True]
    _close_app(app)


def test_reopen_requires_explicit_action_and_does_not_confirm_old_claims(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    conversation = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    proposal = _candidate(client, conversation)
    accepted = client.post(f'/api/v1/conversations/{conversation}/memory-candidates/{proposal}/accept', json={}).json()
    claim = accepted['memory_candidates'][0]['claim']
    source = claim['evidence'][0]['episode_id']
    original = app.state.episodes.get(source).to_dict()
    assert client.post(f'/episodes/{source}/ignore').status_code == 200
    result = client.post(f'/api/v1/episodes/{source}/reopen')
    assert result.status_code == 200
    assert result.json()['state'] == 'new'
    assert result.json()['body'] == original['body']
    assert result.json()['digest'] == original['digest']
    assert app.state.claims.get(claim['id']).status is Status.DISPUTED
    assert not app.state.claims.is_usable(app.state.claims.get(claim['id']))
    revision = app.state.claims.revision
    assert client.post(f'/api/v1/episodes/{source}/reopen').status_code == 200
    assert app.state.claims.revision == revision
    _close_app(app)
    app = _make_app(tmp_path, monkeypatch)
    assert app.state.episodes.get(source).state.value == 'new'
    assert not app.state.claims.is_usable(app.state.claims.get(claim['id']))
    assert TestClient(app).get(f'/api/v1/conversations/{conversation}').json()['context']['items'] == []
    _close_app(app)


def test_superseded_source_cannot_be_reopened(memory):
    from icarus_memory import EpisodeKind, Provenance, SourceType
    from icarus_memory.episodes import EpisodeError
    episodes, proposals, claims, service = memory
    provenance = Provenance(source_type=SourceType.DOCUMENT)
    old = episodes.record(EpisodeKind.DOCUMENT, 'Quelle', 'Alt', provenance, source_key='file')[0]
    new = episodes.record(EpisodeKind.DOCUMENT, 'Quelle', 'Neu', provenance, source_key='file')[0]
    episodes.advance_source_head('file', None, new.id)
    episodes.ignore(old.id)
    with pytest.raises(EpisodeError): episodes.reopen(old.id)
    assert episodes.get(old.id).state.value == 'ignored'


def test_failed_reopen_audit_keeps_source_excluded(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app, raise_server_exceptions=False)
    source = client.post('/episodes', json={'title': 'Quelle', 'body': 'Rohtext'}).json()['id']
    client.post(f'/episodes/{source}/ignore')
    def fail(*args, **kwargs): raise RuntimeError('audit unavailable')
    monkeypatch.setattr(app.state.audit, 'record', fail)
    assert client.post(f'/api/v1/episodes/{source}/reopen').status_code == 500
    assert app.state.episodes.get(source).state.value == 'ignored'
    _close_app(app)
