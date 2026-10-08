"""A previously opened finding cannot confirm withdrawn or replaced evidence."""
from icarus_memory.lint_routes import _anreichern
from tests.test_lint_routes import api, fristen, offen  # noqa: F401
from tests.test_lint_routes import angenommen
from tests.test_context_identity import core  # noqa: F401
import pytest


@pytest.mark.parametrize('status', ['erledigt', 'abgewiesen'])
@pytest.mark.parametrize('with_stand', [True, False])
def test_stale_status_action_cannot_dismiss_withdrawn_finding(api, status, with_stand):
    app, client = api
    _, _, newer = fristen(app)
    client.post('/api/v1/lint')
    [finding] = offen(client)
    app.state.episodes.ignore(newer.id)
    response = client.patch(f'/api/v1/lint/befunde/{finding["id"]}',
                            json={'status': status, **({'stand': finding['stand']} if with_stand else {})})
    assert response.status_code == 409
    assert app.state.lint_befunde.get(finding['id'])['status'] == 'offen'


def test_withdrawn_source_rejects_already_open_decision_without_writes(api):
    app, client = api
    _, _, newer = fristen(app)
    client.post('/api/v1/lint')
    [finding] = offen(client)
    app.state.episodes.ignore(newer.id)
    revision = app.state.claims.revision
    response = client.post(f'/api/v1/lint/befunde/{finding["id"]}/entscheiden', json={'wahl': 'neu'})
    assert response.status_code == 409
    assert app.state.claims.revision == revision
    assert app.state.lint_befunde.get(finding['id'])['status'] == 'offen'


def test_outdated_view_is_rejected_before_confirming(api):
    app, client = api
    fristen(app)
    client.post('/api/v1/lint')
    [finding] = offen(client)
    assert finding['stand']
    response = client.post(f'/api/v1/lint/befunde/{finding["id"]}/entscheiden',
                           json={'wahl': 'neu', 'stand': 'outdated'})
    assert response.status_code == 409
    assert app.state.lint_befunde.get(finding['id'])['status'] == 'offen'
    assert client.post(f'/api/v1/lint/befunde/{finding["id"]}/entscheiden',
                       json={'wahl': 'neu', 'stand': finding['stand']}).status_code == 200


def test_keep_old_does_not_keep_a_retracted_claim(api):
    app, client = api
    claim, _ = angenommen(app)
    client.post('/api/v1/lint')
    [finding] = offen(client)
    app.state.claims.retract(claim.id, reason='Synthetic correction')
    response = client.post(f'/api/v1/lint/befunde/{finding["id"]}/entscheiden', json={'wahl': 'alt'})
    assert response.status_code == 409
    assert app.state.lint_befunde.get(finding['id'])['status'] == 'offen'


def test_evidence_quotes_are_original_and_import_date_is_separate(api):
    app, client = api
    _, older, newer = fristen(app)
    client.post('/api/v1/lint')
    [finding] = offen(client)
    for evidence in finding['belege']:
        episode = app.state.episodes.get(evidence['episode_id'])
        assert evidence['zitat'] and evidence['zitat'] in episode.body
        assert evidence['digest'] == episode.digest
        assert evidence['datum'] == episode.occurred_at.isoformat()
        assert evidence['recorded_at'] == episode.recorded_at.isoformat()
    # A source with no occurrence time must not acquire its import timestamp.
    raw = app.state.lint_befunde.get(finding['id'])
    from dataclasses import replace
    original = app.state.episodes.get
    app.state.episodes.get = lambda id: replace(original(id), occurred_at=None)
    try:
        [undated] = _anreichern(app, [raw])
        assert all(evidence['datum'] is None for evidence in undated['belege'])
    finally:
        app.state.episodes.get = original
