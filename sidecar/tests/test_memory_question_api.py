"""Questions displayed on Today use guarded, source-current local decisions."""
from tests.test_lint_routes import api  # noqa: F401
from tests.test_context_identity import core  # noqa: F401
from tests.test_memory_questions import _active_claim, _candidate


def test_question_http_roundtrip_and_stale_choice(api):
    app, client = api
    claim, _ = _active_claim(app, 'person:synthetic')
    candidate, source = _candidate(app, claim.subject_ref, 'Synthetic replacement quote.', 'new')
    response = client.get('/api/v1/memory/questions')
    assert response.status_code == 200
    [question] = response.json()['items']
    path = f'/api/v1/memory/questions/{question["id"]}/resolve'
    assert client.post(path, json={'stand': '0' * 64, 'proposal_id': candidate.id}).status_code == 409
    result = client.post(path, json={'stand': question['stand'], 'proposal_id': candidate.id})
    assert result.status_code == 200 and result.json()['decision'] == 'accepted'
    assert client.get('/api/v1/memory/questions').json()['items'] == []
    assert client.post(path, json={'stand': question['stand'], 'proposal_id': candidate.id}).status_code == 409
    assert client.get('/api/v1/memory/questions', headers={'X-Icarus-Token': 'wrong'}).status_code in (401, 403)
