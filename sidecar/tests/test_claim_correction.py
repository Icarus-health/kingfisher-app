from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from icarus_memory.server import create_app
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence


@pytest.fixture
def correction_app():
    app = create_app()
    return app, TestClient(app)


def accepted(app, **overrides):
    episode, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Beleg', 'Originale Aussage',
        Provenance(source_type=SourceType.USER_STATED, captured_at=datetime.now(timezone.utc)))
    data = dict(subject_ref='person:test', predicate='status', value='alt', statement='Alte Aussage',
        rationale='Test', scope_ref='project:alt', evidence=[Evidence(episode.id, episode.body, episode.digest)])
    data.update(overrides)
    proposal, _ = app.state.knowledge_service.propose(**data)
    return app.state.knowledge_service.accept(proposal.id, supersedes=[])


def payload(**overrides):
    data = dict(value='neu', statement='Neue Aussage', reason='Kontext war falsch',
        scope_ref='project:neu', target_ref='project:ziel', valid_from='2026-01-01T00:00:00Z',
        valid_until='2027-01-01T00:00:00Z')
    data.update(overrides)
    return data


def test_correction_has_new_evidence_and_preserves_history(correction_app):
    app, client = correction_app
    old = accepted(app)
    dependent = accepted(app, subject_ref='person:dependent', depends_on=[old.id])
    response = client.post(f'/api/v1/memory/claims/{old.id}/correct', json=payload())
    assert response.status_code == 200, response.text
    new = response.json()['claim']
    assert new['supersedes'] == [old.id]
    assert new['subject_ref'] == old.subject_ref and new['predicate'] == old.predicate
    assert new['scope_ref'] == 'project:neu' and new['target_ref'] == 'project:ziel'
    assert new['valid_from'].startswith('2026-01-01')
    assert new['valid_until'].startswith('2027-01-01')
    assert new['evidence'][0]['episode_id'] != old.evidence[0].episode_id
    source = app.state.episodes.get(new['evidence'][0]['episode_id'])
    assert source.provenance.source_type is SourceType.USER_STATED
    assert 'correction_of' in source.body and old.id in source.body
    assert app.state.claims.get(old.id).status.value == 'superseded'
    assert not app.state.claims.is_usable(app.state.claims.get(old.id))
    assert app.state.claims.get(dependent.id).status.value == 'disputed'
    db = app.state.claims._conn.execute('PRAGMA database_list').fetchone()[2]
    reopened = ClaimStore(db)
    assert reopened.get(old.id).superseded_by == new['id']
    assert reopened.get(new['id']).scope_ref == 'project:neu'
    reopened.close()
    assert client.post(f'/api/v1/memory/claims/{old.id}/correct', json=payload()).status_code == 409


def test_other_conflict_is_not_replaced(correction_app):
    app, client = correction_app
    old = accepted(app)
    other = accepted(app, scope_ref='project:neu', value='konflikt')
    response = client.post(f'/api/v1/memory/claims/{old.id}/correct', json=payload())
    assert response.status_code == 409
    assert app.state.claims.get(old.id).status.value == 'active'
    assert app.state.claims.get(other.id).status.value == 'active'
    assert app.state.knowledge_service.pending() == []


@pytest.mark.parametrize('changes', [dict(value=' '), dict(reason=' '), dict(statement=' '),
    dict(scope_ref=' '), dict(valid_from='2028-01-01T00:00:00Z')])
def test_invalid_correction_writes_nothing(correction_app, changes):
    app, client = correction_app
    old = accepted(app)
    before = app.state.episodes.counts()
    response = client.post(f'/api/v1/memory/claims/{old.id}/correct', json=payload(**changes))
    assert response.status_code == 422
    assert app.state.episodes.counts() == before
    assert app.state.claims.get(old.id).status.value == 'active'


def test_generic_accept_cannot_change_scope(correction_app):
    from icarus_memory.claims import ClaimError
    app, _ = correction_app
    old = accepted(app)
    proposal, _ = app.state.knowledge_service.propose(
        subject_ref=old.subject_ref, predicate=old.predicate, value='neu', statement='Neu',
        rationale='Test', scope_ref='project:neu', evidence=old.evidence)
    with pytest.raises(ClaimError):
        app.state.knowledge_service.accept(proposal.id, supersedes=[old.id])
    assert app.state.claims.get(old.id).status.value == 'active'
