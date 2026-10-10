"""Own measurements remain immutable source versions, not inferred medical facts."""
import importlib.util
import json
import threading
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, EpisodeStore, ClaimStore, Provenance, SourceType
from icarus_memory.memory_categories import Categories

ROOT = '/api/v1/health/observations'

@pytest.fixture
def health(tmp_path):
    app = FastAPI()
    app.state.episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    app.state.claims = ClaimStore(tmp_path / 'claims.sqlite3')
    app.state.conversation_lock = threading.RLock()
    # Before implementation the genuinely missing endpoint returns 404.
    if importlib.util.find_spec('icarus_memory.health_observations'):
        from icarus_memory.health_observations import register
        register(app, [])
    client = TestClient(app)
    yield client, app.state.episodes, app.state.claims
    client.close()
    app.state.episodes.close()
    app.state.claims.close()


def data(**overrides):
    result = dict(request_id=str(uuid4()), subject='self', metric='Gewicht', value='072,50',
                  unit='kg', observed_at='2023-07-02T09:30:00+02:00', note='Eigene Waage')
    result.update(overrides)
    return result


def create(health, **overrides):
    client, _, _ = health
    response = client.post(ROOT, json=data(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def correction(item, **overrides):
    return data(expected_support_fingerprint=item['support_fingerprint'], **overrides)


def test_capture_preserves_literal_value_offset_and_explicit_person(health):
    client, episodes, _ = health
    item = create(health)
    assert (item['value'], item['unit'], item['observed_at'], item['subject']) == (
        '072,50', 'kg', '2023-07-02T09:30:00+02:00', 'self')
    original = episodes.get(item['id'])
    assert original.kind == EpisodeKind.DOCUMENT
    assert original.provenance.source_type == SourceType.USER_STATED
    assert original.occurred_at == datetime(2023, 7, 2, 7, 30, tzinfo=timezone.utc)
    assert original.recorded_at > original.occurred_at
    assert original.participants == []
    assert json.loads(original.body)['value'] == '072,50'
    assert Categories(episodes).list_for(item['id'])['correction']['categories'] == ['health']
    assert [row['id'] for row in client.get(ROOT).json()['items']] == [item['id']]


def test_retry_after_restart_does_not_duplicate_source(health):
    client, episodes, _ = health
    payload = data()
    first = client.post(ROOT, json=payload)
    assert first.status_code == 201
    from icarus_memory.health_observations import register
    app = FastAPI()
    app.state.episodes = EpisodeStore(episodes._path)
    app.state.claims = health[2]
    app.state.conversation_lock = threading.RLock()
    register(app, [])
    with TestClient(app) as restarted:
        second = restarted.post(ROOT, json=payload)
        assert second.status_code == 200
        assert second.json()['id'] == first.json()['id']
    app.state.episodes.close()
    assert episodes._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 1


def test_reused_nonce_cannot_change_payload_or_revive_withdrawn_source(health):
    client, episodes, _ = health
    payload = data()
    first = client.post(ROOT, json=payload)
    assert first.status_code == 201
    assert client.post(ROOT, json={**payload, 'value': '73'}).status_code == 409
    episodes.ignore(first.json()['id'])
    assert client.post(ROOT, json=payload).status_code == 409
    assert client.get(ROOT).json()['items'] == []


def test_two_equal_measurements_are_not_collapsed(health):
    first, second = create(health), create(health)
    assert first['id'] != second['id']
    assert len(health[0].get(ROOT).json()['items']) == 2


@pytest.mark.parametrize('change', [
    {'subject': 'other'}, {'subject': None}, {'observed_at': '2023-07-02'},
    {'observed_at': '2023-07-02T09:30:00'}, {'value': 'NaN'}, {'value': '1e6'},
    {'value': '1.000,5'}, {'unit': ''}, {'metric': '   '}, {'request_id': 'abc'},
    {'observed_at': '2023-07-02T09:30:00+26:00'}, {'note': '\u0000'},
])
def test_invalid_or_ambiguous_inputs_are_not_recorded(health, change):
    response = health[0].post(ROOT, json=data(**change))
    assert response.status_code == 422
    assert health[1]._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 0


def test_person_must_be_explicit(health):
    payload = data()
    del payload['subject']
    assert health[0].post(ROOT, json=payload).status_code == 422


def test_correction_preserves_original_and_blocks_stale_write(health):
    client, episodes, claims = health
    old = create(health)
    original_body = episodes.get(old['id']).body
    # Existing invalidation is invoked on the actual source, not the new one.
    invalidated = []
    original_invalidate = claims.invalidate_source
    def invalidate(identifier, **kwargs):
        invalidated.append(identifier)
        return original_invalidate(identifier, **kwargs)
    claims.invalidate_source = invalidate
    payload = correction(old, value='71,8')
    changed = client.patch(f"{ROOT}/{old['id']}", json=payload)
    assert changed.status_code == 200, changed.text
    new = changed.json()
    assert new['id'] != old['id'] and new['value'] == '71,8'
    assert old['id'] in invalidated
    assert episodes.get(old['id']).body == original_body
    assert not episodes.support_snapshot(old['id']).current()
    assert [item['id'] for item in client.get(ROOT).json()['items']] == [new['id']]
    assert client.patch(f"{ROOT}/{old['id']}", json=correction(old, value='80')).status_code == 409
    replay = client.patch(f"{ROOT}/{old['id']}", json=payload)
    assert replay.status_code == 200 and replay.json()['id'] == new['id']
    assert episodes._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 2
    history = client.get(f"{ROOT}/{old['id']}/history").json()['items']
    assert {item['id']: item['status'] for item in history} == {old['id']: 'superseded', new['id']: 'current'}
    episodes.ignore(new['id'])
    assert client.patch(f"{ROOT}/{old['id']}", json=payload).status_code == 409
    assert client.patch(f"{ROOT}/{new['id']}", json=correction(new)).status_code == 409
    history = client.get(f"{ROOT}/{old['id']}/history").json()['items']
    assert next(item for item in history if item['id'] == new['id'])['status'] == 'excluded'


def test_correcting_back_to_old_value_creates_new_active_version(health):
    client, episodes, _ = health
    original = create(health)
    new = client.patch(f"{ROOT}/{original['id']}", json=correction(original, value='80')).json()
    restored = client.patch(f"{ROOT}/{new['id']}", json=correction(new, value=original['value']))
    assert restored.status_code == 200
    assert restored.json()['id'] not in {original['id'], new['id']}
    assert not episodes.support_snapshot(original['id']).current()


def test_chronological_page_uses_measurement_time_and_equal_time_ties(health):
    client, _, _ = health
    recent = create(health, observed_at='2025-01-01T09:00:00+01:00')
    older = create(health, observed_at='2020-01-01T09:00:00+01:00')
    tie = create(health, observed_at='2025-01-01T08:00:00Z')
    first = client.get(ROOT, params={'limit': 1}).json()
    assert first['items'][0]['id'] == tie['id']
    second = client.get(ROOT, params={'limit': 1, 'cursor': first['next_cursor']}).json()
    assert second['items'][0]['id'] == recent['id']
    third = client.get(ROOT, params={'limit': 1, 'cursor': second['next_cursor']}).json()
    assert third['items'][0]['id'] == older['id'] and third['next_cursor'] is None


def test_bad_cursor_and_limits_are_rejected(health):
    client, _, _ = health
    for params in ({'cursor': 'garbage'}, {'limit': 0}, {'limit': 51}, {'cursor': '[NaN,1]'}):
        assert client.get(ROOT, params=params).status_code == 422


def test_corrupt_typed_payload_is_not_projected_as_measurement(health):
    client, episodes, _ = health
    good = create(health)
    payload = data(observed_at='2023-01-01T00:00:00Z')
    payload.pop('request_id')
    payload['schema'] = 'health-observation-v1'
    bad, _ = episodes.record(EpisodeKind.DOCUMENT, 'Wrong time', json.dumps(payload),
        Provenance(SourceType.USER_STATED, source_ref='health:manual'),
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        source_key='health-observation:' + str(uuid4()))
    key = episodes._conn.execute('SELECT source_key FROM episodes WHERE id=?', (bad.id,)).fetchone()[0]
    episodes.advance_source_head(key, None, bad.id)
    response = client.get(ROOT).json()
    assert [item['id'] for item in response['items']] == [good['id']]
    assert response['invalid_sources'] == 1


def test_health_read_is_read_only_and_ignores_unrelated_large_texts(health):
    client, episodes, _ = health
    item = create(health)
    episodes.record(EpisodeKind.DOCUMENT, 'Mail', 'other' * 10000, Provenance(SourceType.EMAIL))
    changes = episodes._conn.total_changes
    assert client.get(ROOT).json()['items'][0]['id'] == item['id']
    assert client.get(f"{ROOT}/{item['id']}/history").status_code == 200
    assert episodes._conn.total_changes == changes


def test_categorization_unavailable_does_not_leave_partial_source(health):
    client, episodes, _ = health
    episodes._conn.execute("DELETE FROM memory_category_taxonomy WHERE category_id='health'")
    before = episodes._conn.total_changes
    response = client.post(ROOT, json=data())
    assert response.status_code == 409
    assert 'Gesundheit' in response.json()['detail']
    assert episodes._conn.total_changes == before
    assert episodes._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 0


def test_consolidation_bookkeeping_does_not_hide_own_original(health):
    client, episodes, _ = health
    item = create(health)
    episodes.mark_consolidated(item['id'], produced=['existing:assertion'])
    assert client.get(ROOT).json()['items'][0]['id'] == item['id']
    response = client.patch(f"{ROOT}/{item['id']}", json=correction(item, value='73'))
    assert response.status_code == 200


def test_server_registers_guarded_measurement_routes_without_replacing_healthcheck(health, monkeypatch, tmp_path):
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-health-test')
    app = create_app(episodes=health[1], knowledge=health[2])
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get(ROOT).status_code == 401
        result = client.post(ROOT, headers={'X-Icarus-Token': 'synthetic-health-test'}, json=data())
        assert result.status_code == 201, result.text


def test_correcting_source_disputes_real_accepted_claim_and_dependents(health, tmp_path):
    from icarus_memory import KnowledgeService, ProposalStore
    from icarus_memory.proposals import Evidence
    client, episodes, claims = health
    old = create(health)
    original = episodes.get(old['id'])
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    proposal, _ = service.propose(subject_ref='person:synthetic', predicate='measurement',
        value=old['value'], statement='Synthetic measurement statement', rationale='Explicit synthetic acceptance',
        evidence=[Evidence(original.id, old['value'], original.digest)])
    claim = service.accept(proposal.id, supersedes=[])
    assert claims.get(claim.id).status.value == 'active'
    dependent_proposal, _ = service.propose(subject_ref='person:synthetic', predicate='dependent',
        value='derived', statement='Synthetic dependent statement', rationale='Synthetic dependent',
        evidence=[Evidence(original.id, old['value'], original.digest)], depends_on=[claim.id])
    dependent = service.accept(dependent_proposal.id, supersedes=[])
    result = client.patch(f"{ROOT}/{old['id']}", json=correction(old, value='70'))
    assert result.status_code == 200
    assert claims.get(claim.id).status.value == 'disputed'
    assert claims.get(dependent.id).status.value == 'disputed'
    proposals.close()


def test_page_budget_can_return_empty_continuation_without_losing_older_measurement(health):
    client, episodes, _ = health
    good = create(health, observed_at='2020-01-01T00:00:00Z')
    for index in range(101):
        key = 'health-observation:' + str(uuid4())
        bad, _ = episodes.record(EpisodeKind.DOCUMENT, f'Invalid {index}', '{}',
            Provenance(SourceType.USER_STATED, source_ref='health:manual'),
            occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc), source_key=key)
        episodes.advance_source_head(key, None, bad.id)
    first = client.get(ROOT).json()
    assert first['items'] == [] and first['invalid_sources'] == 100
    assert first['scanned_sources'] == 100 and not first['complete'] and first['next_cursor']
    second = client.get(ROOT, params={'cursor': first['next_cursor']}).json()
    assert [item['id'] for item in second['items']] == [good['id']]
    assert second['invalid_sources'] == 1 and second['complete']


def test_history_has_bounded_continuation_and_cursor_cannot_switch_sources(health):
    client, episodes, _ = health
    old = create(health)
    changed = client.patch(f"{ROOT}/{old['id']}", json=correction(old, value='70')).json()
    page = client.get(f"{ROOT}/{old['id']}/history", params={'limit': 1}).json()
    assert page['items'][0]['id'] == changed['id']
    more = client.get(f"{ROOT}/{old['id']}/history", params={'limit': 1, 'cursor': page['next_cursor']}).json()
    assert more['items'][0]['id'] == old['id'] and more['complete']
    another = create(health)
    assert client.get(f"{ROOT}/{another['id']}/history", params={'limit': 1, 'cursor': page['next_cursor']}).status_code == 422
    assert client.get(ROOT, params={'limit': 1, 'cursor': page['next_cursor']}).status_code == 422


def test_failed_categorization_rolls_back_source_switch_and_original_change(health, monkeypatch):
    client, episodes, _ = health
    old = create(health)
    count = episodes._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0]
    def fail(*args, **kwargs):
        raise RuntimeError('Synthetic storage failure')
    monkeypatch.setattr(Categories, 'correct', fail)
    with pytest.raises(RuntimeError, match='storage failure'):
        client.patch(f"{ROOT}/{old['id']}", json=correction(old, value='70'))
    assert episodes.support_snapshot(old['id']).current()
    assert episodes._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == count


def test_used_correction_nonce_cannot_be_reused_for_another_value(health):
    client, _, _ = health
    old = create(health)
    payload = correction(old, value='70')
    new = client.patch(f"{ROOT}/{old['id']}", json=payload).json()
    assert client.patch(f"{ROOT}/{new['id']}", json=correction(new, request_id=payload['request_id'], value='71')).status_code == 409


def test_measurement_order_and_pagination_preserve_microseconds(health):
    client, _, _ = health
    latest = create(health, observed_at='2023-07-02T09:30:00.000100+00:00')
    earlier = create(health, observed_at='2023-07-02T09:30:00.000001+00:00')
    first = client.get(ROOT, params={'limit': 1}).json()
    assert first['items'][0]['id'] == latest['id']
    second = client.get(ROOT, params={'limit': 1, 'cursor': first['next_cursor']}).json()
    assert second['items'][0]['id'] == earlier['id'] and second['complete']


def test_unchanged_correction_does_not_create_version_or_invalidate_claims(health):
    client, episodes, claims = health
    old = create(health)
    before = episodes._conn.total_changes
    revision = claims.revision
    result = client.patch(f"{ROOT}/{old['id']}", json=correction(old))
    assert result.status_code == 200
    assert result.json()['id'] == old['id']
    assert episodes._conn.total_changes == before
    assert claims.revision == revision


def test_filter_reaches_old_measurements_beyond_other_metrics_and_units(health):
    client, _, _ = health
    old = create(health, observed_at='2020-01-01T09:00:00Z')
    for n in range(105):
        create(health, metric='Puls', unit='bpm')
    create(health, metric='Gewicht', unit='lb')
    result = client.get(ROOT, params={'metric': ' gewicht ', 'unit': 'kg'}).json()
    assert [item['id'] for item in result['items']] == [old['id']]
    assert result['scanned_sources'] == 1 and result['complete']


def test_filter_cursor_cannot_switch_metric_or_case_sensitive_unit(health):
    client, _, _ = health
    create(health, metric='Signal', unit='mV')
    create(health, metric='Signal', unit='mV')
    create(health, metric='Signal', unit='MV')
    first = client.get(ROOT, params={'limit': 1, 'metric': 'Signal', 'unit': 'mV'}).json()
    assert first['next_cursor']
    for changed in ({'metric': 'Puls', 'unit': 'mV'}, {'metric': 'Signal', 'unit': 'MV'}, {}):
        assert client.get(ROOT, params={'limit': 1, 'cursor': first['next_cursor'], **changed}).status_code == 422
    second = client.get(ROOT, params={'limit': 1, 'metric': 'SIGNAL', 'unit': 'mV', 'cursor': first['next_cursor']}).json()
    assert len(second['items']) == 1 and second['complete']


def test_filtered_source_withdrawal_correction_and_bad_body_remain_checked(health):
    client, episodes, _ = health
    old = create(health)
    changed = client.patch(f"{ROOT}/{old['id']}", json=correction(old, metric='Puls', unit='bpm')).json()
    assert client.get(ROOT, params={'metric': 'Gewicht', 'unit': 'kg'}).json()['items'] == []
    episodes.ignore(changed['id'])
    assert client.get(ROOT, params={'metric': 'Puls', 'unit': 'bpm'}).json()['items'] == []
    bad = create(health)
    with episodes._lock:
        episodes._conn.execute("UPDATE episodes SET body=? WHERE id=?", ('not json', bad['id']))
        episodes._conn.commit()
    response = client.get(ROOT, params={'metric': 'Gewicht', 'unit': 'kg'})
    assert response.status_code == 200 and response.json()['items'] == []


def test_measurement_filters_reject_control_characters_and_overlong_fields(health):
    client, _, _ = health
    for params in ({'metric': 'a'*101}, {'unit': 'a'*41}, {'metric': 'Puls\n'}, {'unit': 'k\tg'}):
        assert client.get(ROOT, params=params).status_code == 422
