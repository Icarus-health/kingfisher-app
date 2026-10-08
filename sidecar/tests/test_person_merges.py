"""Confirmed grouping preserves every original source and can be undone."""
import pytest
from icarus_memory.claims import ClaimStore
from icarus_memory.entities import EntityError
from icarus_memory.graph import GraphNode, GraphEdge, KnowledgeGraph
from icarus_memory.model import now


def raw_graph():
    return KnowledgeGraph([
        GraphNode('person:a', 'person', 'Ada <ada@example.org>'),
        GraphNode('person:b', 'person', '<ada@example.org>'),
        GraphNode('episode:e', 'episode', 'Original message'),
    ], [GraphEdge('edge:1', 'person:a', 'episode:e', 'participated_in', ('episode:e',)),
        GraphEdge('edge:2', 'person:b', 'episode:e', 'participated_in', ('episode:e',))], now())


def test_confirm_persist_project_and_undo_without_changing_sources(tmp_path):
    from icarus_memory.person_merges import preview, project
    store = ClaimStore(tmp_path / 'knowledge.sqlite3')
    raw = raw_graph()
    before = raw.to_dict()
    proposed = preview(raw, ['person:a', 'person:b'], 'Ada')
    assert proposed['evidence_count'] == 1
    with pytest.raises(EntityError):
        store.person_merges.confirm(proposed, confirmed=False)
    record = store.person_merges.confirm(proposed, confirmed=True)
    store.close()
    reopened = ClaimStore(tmp_path / 'knowledge.sqlite3')
    result = project(raw, reopened.person_merges.list())
    assert [n.label for n in result.nodes if n.kind == 'person'] == ['Ada']
    assert {e.source for e in result.edges} == {record['id']}
    assert [e.evidence_refs for e in result.edges] == [('episode:e',)]
    assert {origin['source'] for origin in result.edges[0].to_dict()['original_edges']} == {'person:a', 'person:b'}
    assert raw.to_dict() == before
    with pytest.raises(EntityError):
        reopened.person_merges.undo(record['id'], confirmed=False)
    reopened.person_merges.undo(record['id'], confirmed=True)
    assert project(raw, reopened.person_merges.list()).to_dict() == before
    assert len(reopened.person_merges.list()) == 1
    assert reopened.person_merges.list()[0]['undone_at']


def test_overlap_rejected_across_connections(tmp_path):
    from icarus_memory.person_merges import preview
    path = tmp_path / 'knowledge.sqlite3'
    one, two = ClaimStore(path), ClaimStore(path)
    proposed = preview(raw_graph(), ['person:a', 'person:b'], 'Ada')
    one.person_merges.confirm(proposed, confirmed=True)
    with pytest.raises(EntityError):
        two.person_merges.confirm(proposed, confirmed=True)
    assert len(two.person_merges.list()) == 1


def test_preview_rejects_missing_nonperson_repeated_and_technical_ids():
    from icarus_memory.person_merges import preview
    raw = raw_graph()
    for ids in [['person:a'], ['person:a', 'person:a'], ['person:a', 'missing'], ['person:a', 'episode:e']]:
        with pytest.raises(EntityError):
            preview(raw, ids, 'Ada')
    raw.nodes.append(GraphNode('person:bot', 'person', 'noreply@example.org', {'quality_category':'automated'}))
    with pytest.raises(EntityError):
        preview(raw, ['person:a', 'person:bot'], 'Ada')


def test_preview_token_changes_with_sources_and_labels_but_not_clock():
    from icarus_memory.person_merges import preview
    raw = raw_graph()
    p = preview(raw, ['person:a', 'person:b'], 'Ada')
    assert preview(raw_graph(), ['person:b', 'person:a'], 'Ada')['preview_token'] == p['preview_token']
    assert preview(raw, ['person:a', 'person:b'], 'Other')['preview_token'] != p['preview_token']
    raw.edges.append(GraphEdge('edge:3', 'person:a', 'episode:e', 'mentioned_in', ('episode:e',)))
    assert preview(raw, ['person:a', 'person:b'], 'Ada')['preview_token'] != p['preview_token']


def test_api_preview_confirmation_staleness_and_undo(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app()
    client = TestClient(app)
    episodes = app.state.episodes
    for i, label in enumerate(['Ada <ada@example.org>', 'Ada <ada@privat.example>']):
        episodes.record(EpisodeKind.MESSAGE, f'Message {i}', f'Body {i}',
                        Provenance(source_type=SourceType.EMAIL, source_ref=f'mail:{i}', captured_at=now()),
                        participants=[label])
    graph_before = client.get('/api/v1/memory/graph').json()
    ids = [n['id'] for n in graph_before['nodes'] if n['kind'] == 'person']
    base = '/api/v1/memory/person-merges'
    body = {'member_ids': ids, 'label': 'Ada'}
    response = client.post(base + '/preview', json=body)
    assert response.status_code == 200
    token = response.json()['preview_token']
    assert client.post(base, json={**body, 'preview_token': token}).status_code == 422
    assert client.post(base, json={**body, 'preview_token': 'stale', 'confirmed': True}).status_code == 409
    response = client.post(base, json={**body, 'preview_token': token, 'confirmed': True})
    assert response.status_code == 201
    merge_id = response.json()['id']
    assert len(client.get(base).json()['merges']) == 1
    merged = client.get('/api/v1/memory/graph').json()
    assert [n['id'] for n in merged['nodes'] if n['kind'] == 'person'] == [merge_id]
    # Every original source profile is still readable, including full body.
    assert client.get('/api/v1/memory/people/Ada%20%3Cada%40example.org%3E').status_code == 200
    assert client.post(base, json={**body, 'preview_token': token, 'confirmed': True}).status_code == 409
    assert client.post(base + f'/{merge_id}/undo', json={'confirmed': False}).status_code == 409
    assert client.post(base + f'/{merge_id}/undo', json={'confirmed': True}).status_code == 200
    after = client.get('/api/v1/memory/graph').json()
    assert after['nodes'] == graph_before['nodes']
    assert after['edges'] == graph_before['edges']
    assert client.get(base).json()['merges'][0]['undone_at']


def test_group_projection_does_not_resurrect_removed_sources(tmp_path):
    from icarus_memory.person_merges import preview, project
    store = ClaimStore(tmp_path / 'knowledge.sqlite3')
    raw = raw_graph()
    record = store.person_merges.confirm(preview(raw, ['person:a', 'person:b'], 'Ada'), confirmed=True)
    empty = KnowledgeGraph([], [], now())
    assert project(empty, [record]).nodes == []


def test_confirmed_service_mailbox_group_survives_in_people_projection(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType, now

    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app()
    client = TestClient(app)
    episodes = app.state.episodes
    for i, participant in enumerate([
        'Alex Winter <service@example.org>',
        'Alex Winter <alex@example.org>',
    ]):
        episodes.record(EpisodeKind.MESSAGE, f'Message {i}', f'Body {i}',
                        Provenance(source_type=SourceType.EMAIL, source_ref=f'mail:{i}', captured_at=now()),
                        participants=[participant])
    graph = client.get('/api/v1/memory/graph').json()
    members = [node for node in graph['nodes'] if node['kind'] == 'person']
    app.state.claims.person_merges.confirm({'members': members, 'label': 'Alex Winter'}, confirmed=True)

    people = client.get('/people').json()

    assert len(people) == 1
    assert people[0]['name'] == 'Alex Winter'
    assert set(people[0]['adressen']) == {'service@example.org', 'alex@example.org'}
    assert people[0]['id'].startswith('merge:')
    profile = client.get('/people/Alex%20Winter').json()
    assert profile['id'] == people[0]['id']
    assert set(profile['adressen']) == {'service@example.org', 'alex@example.org'}
    assert [episode.participants for episode in episodes.each_episode()] == [
        ['Alex Winter <service@example.org>'], ['Alex Winter <alex@example.org>']
    ]
    app.state.claims.person_merges.undo(people[0]['id'], confirmed=True)
    after_undo = client.get('/people').json()
    assert len(after_undo) == 1
    assert after_undo[0]['adressen'] == ['alex@example.org']


def test_all_merge_routes_require_auth(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'test-only-token')
    client = TestClient(create_app())
    base = '/api/v1/memory/person-merges'
    assert client.get(base).status_code == 401
    for path in [base, base + '/preview', base + '/merge:missing/undo']:
        assert client.post(path, json={}).status_code == 401
    assert client.get(base, headers={'X-Icarus-Token': 'test-only-token'}).status_code == 200


def test_partial_group_does_not_leave_false_duplicate_hint(tmp_path):
    from icarus_memory.people_quality import annotate_people
    from icarus_memory.person_merges import preview, project
    raw = raw_graph()
    raw.nodes.append(GraphNode('person:c', 'person', 'Dr Ada <ada@example.org>'))
    raw.nodes = annotate_people(raw.nodes)
    store = ClaimStore(tmp_path / 'knowledge.sqlite3')
    record = store.person_merges.confirm(preview(raw, ['person:a', 'person:b'], 'Ada'), confirmed=True)
    result = project(raw, [record])
    remaining = next(node for node in result.nodes if node.id == 'person:c')
    assert remaining.attributes['duplicate_ids'] == []


def test_internal_member_relationship_keeps_evidence_without_self_loop(tmp_path):
    from icarus_memory.person_merges import preview, project
    raw = raw_graph()
    raw.edges.append(GraphEdge('internal', 'person:a', 'person:b', 'works_with', ('episode:e',), state='active'))
    store = ClaimStore(tmp_path / 'knowledge.sqlite3')
    record = store.person_merges.confirm(preview(raw, ['person:a', 'person:b'], 'Ada'), confirmed=True)
    result = project(raw, [record])
    assert all(edge.source != edge.target for edge in result.edges)
    merged = next(node for node in result.nodes if node.id == record['id'])
    assert merged.attributes['internal_relations'][0]['evidence_refs'] == ['episode:e']
    assert merged.attributes['internal_relations'][0]['source'] == 'person:a'
