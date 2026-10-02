"""Entscheidungsgrundlagen verweisen auf bestätigtes Wissen, ohne Kopien."""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.backends import SqliteBackend
from icarus_memory.claims import ClaimStore
from icarus_memory.model import Kind, Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory import entscheidungen
from icarus_memory.episodes import EpisodeKind
from icarus_memory.proposals import Evidence


def test_claim_correction_shakes_decision_and_links_graph(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    store = SelfModelStore(SqliteBackend(tmp_path / 'model.sqlite3'), subject_id='test')
    app = create_app(store)
    client = TestClient(app)
    episode = app.state.episodes.record(EpisodeKind.MESSAGE, 'Test', 'Kranz arbeitet im Projekt Atlas.', Provenance(source_type=SourceType.USER_STATED))[0]
    candidate = app.state.knowledge_service.propose(subject_ref='person:kranz', predicate='project_role', value='Atlas', statement=episode.body, rationale='Ausdrückliche Angabe', evidence=[Evidence(episode.id, episode.body, episode.digest)])[0]
    assert client.get('/api/v1/decision-basis').json()['items'] == []
    claim = app.state.knowledge_service.accept(candidate.id, supersedes=[])
    basis = client.get('/api/v1/decision-basis').json()['items']
    assert basis[0]['id'] == f'claim:{claim.id}'
    project = client.post('/api/v1/projects', json={'name':'Atlas'}).json()
    response = client.post('/api/v1/decisions', json={'statement':'Kranz koordiniert die nächste Besprechung.', 'claim_ids':[claim.id], 'project_id':project['id']})
    assert response.status_code == 201
    decision = response.json()
    assert not decision['erschuettert'] and not decision['ohne_grundlage']
    assert len(list(store.alles())) == 1  # Kein Wissen ins Selbstmodell kopiert.
    changed = datetime.now(timezone.utc)
    app.state.claims.retract(claim.id, reason='Falsche Zuordnung', at=changed)
    refreshed = client.get('/api/v1/decisions').json()['items'][0]
    assert refreshed['erschuettert']
    assert refreshed['wackler'][0]['annahme_id'] == f'claim:{claim.id}'
    assert refreshed['wackler'][0]['status'] == 'retracted'
    reopened = SelfModelStore(SqliteBackend(tmp_path / 'model.sqlite3'), subject_id='test')
    reopened_claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    assert entscheidungen.alle(reopened, knowledge=reopened_claims)[0].to_dict() == refreshed
    reopened_claims.close()
    assert entscheidungen.erschuettert(store, knowledge=app.state.claims, jetzt=changed + timedelta(days=2))
    assert not entscheidungen.erschuettert(store, knowledge=app.state.claims, jetzt=changed + timedelta(days=31))
    assert any(item['source_ref'] == decision['id'] for item in client.get('/api/v1/morning-briefing').json()['needs_you'])
    assert client.post('/api/v1/decisions', json={'statement':'Veraltet', 'claim_ids':[claim.id]}).status_code == 409
    graph = client.get('/api/v1/memory/graph').json()
    assert any(edge['source'] == f'assertion:{decision["id"]}' and edge['target'] == f'claim:{claim.id}' and edge['relation'] == 'based_on' for edge in graph['edges'])
    result = client.post(f'/api/v1/decisions/{decision["id"]}/retract')
    assert result.json()['status'] == 'retracted'
    assert len(client.get('/api/v1/decisions').json()['items']) == 1
    assert not entscheidungen.erschuettert(store, knowledge=app.state.claims)


def test_assertion_basis_and_invalid_references(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    store = SelfModelStore(MemoryBackend(), subject_id='test')
    basis = store.record('Ich habe freitags Zeit.', Kind.CONSTRAINT, Provenance(source_type=SourceType.USER_STATED))
    client = TestClient(create_app(store))
    result = client.post('/api/v1/decisions', json={'statement':'Ich plane den Termin für Freitag.', 'derived_from':[basis.id]})
    assert result.status_code == 201
    store.retract(basis.id)
    assert client.get('/api/v1/decisions').json()['items'][0]['erschuettert']
    assert client.post('/api/v1/decisions', json={'statement':'   '}).status_code == 422
    assert client.post('/api/v1/decisions', json={'statement':'X', 'claim_ids':['missing']}).status_code == 409
    assert client.post(f'/api/v1/decisions/{basis.id}/retract').status_code == 404
