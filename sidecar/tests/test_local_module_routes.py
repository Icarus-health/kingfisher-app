"""HTTP boundary with artificial canonical stores; no network, app or model."""
import asyncio
import importlib
import json
import threading
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import httpx
import pytest

from icarus_memory.local_module_controller import ControllerError, MODEL
from icarus_memory.restore_boundary import RuntimeBoundary, mark_pending
from tests.test_local_module_controller import env, QUESTION


PREFIX = '/api/v1/modules/local-source'
TOKEN = 'artificial-ui-credential'
HEADERS = {'X-Icarus-Token': TOKEN}


def app_for(factory, *, boundary=None):
    app = FastAPI()
    async def authorized(request: Request):
        if request.headers.get('X-Icarus-Token') != TOKEN:
            raise HTTPException(401, 'Nicht angemeldet.')
    importlib.import_module('icarus_memory.local_module_routes').register(
        app, [Depends(authorized)], controller_factory=factory, boundary=boundary)
    @app.get('/pulse')
    async def pulse():
        return {'ok': True}
    return app


@pytest.fixture
def http(env):
    controller = env['create']()
    factories = []
    def factory():
        factories.append(threading.get_ident())
        return controller
    app = app_for(factory)
    with TestClient(app) as client:
        yield dict(app=app, client=client, controller=controller, factories=factories, env=env)


def post(http, path, body):
    return http['client'].post(PREFIX + path, headers=HEADERS, json=body)


def prepare(http, **changes):
    return post(http, '/prepare', dict(source_id=http['env']['source'].id, question=QUESTION) | changes)


def start_body(http, review=None, **changes):
    if review is None:
        review = prepare(http).json()
    return dict(source_id=http['env']['source'].id, question=QUESTION,
                source_fingerprint=review['source']['fingerprint'], review_binding=review['review_binding'],
                consent=True, idempotency_key='request-key-0001') | changes


def finished(http, run):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        response = http['client'].get(PREFIX + '/runs/' + run['id'], headers=HEADERS)
        assert response.status_code == 200, response.text
        if response.json()['status'] != 'running':
            return response.json()
        time.sleep(.005)
    pytest.fail('artificial run did not finish')


@pytest.mark.parametrize('method,path,body', [
    ('GET', '/status', None), ('POST', '/prepare', {}), ('POST', '/start', {}),
    ('GET', '/runs/' + 'a'*32, None), ('POST', '/runs/' + 'a'*32 + '/cancel', None),
])
def test_authentication_precedes_factory_and_validation(http, method, path, body):
    response = http['client'].request(method, PREFIX + path, json=body)
    assert response.status_code == 401
    assert http['factories'] == []
    assert not http['env']['gateway'].tokens and not http['env']['infer_calls']


def test_status_and_prepare_never_infer_or_claim_runtime_health(http):
    http['env']['gateway'].health_value['syntheticOnly'] = True
    status = http['client'].get(PREFIX + '/status', headers=HEADERS)
    assert status.status_code == 200
    data = status.json()
    assert data['status'] == 'configured'
    assert data['runtime'] == {'status': 'idle', 'busy': False, 'model': MODEL}
    assert 'verified' not in data and 'healthy' not in data and 'ready' not in data
    assert prepare(http).status_code == 503  # Occupancy was never a readiness proof.
    http['env']['gateway'].health_value['syntheticOnly'] = False
    review = prepare(http)
    assert review.status_code == 200
    assert review.json()['source']['id'] == http['env']['source'].id
    assert len(review.json()['review_binding']) == 43
    assert not http['env']['gateway'].tokens and not http['env']['infer_calls']


def test_absent_runtime_is_explicit_without_creating_another_controller():
    with TestClient(app_for(lambda: None)) as client:
        response = client.get(PREFIX + '/status', headers=HEADERS)
        assert response.status_code == 200
        assert response.json()['status'] == 'not_installed'
        assert client.post(PREFIX + '/prepare', headers=HEADERS,
                           json=dict(source_id='artificial-source', question=QUESTION)).status_code == 503


@pytest.mark.parametrize('changes', [
    {'source_id': 1}, {'source_id': True}, {'source_id': ''}, {'source_id': 's'*81},
    {'question': None}, {'question': []}, {'question': 1}, {'question': ''},
    {'question': '   '}, {'question': 'q'*1201}, {'model': 'private-model'},
    {'provider_url': 'https://private.invalid'}, {'api_key': 'secret-credential'},
    {'path': '/private/data'}, {'sources': ['one', 'two']},
])
def test_prepare_rejects_extra_fields_and_coercions_without_reflection(http, changes):
    response = prepare(http, **changes)
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'InvalidRequest'
    assert 'private' not in response.text and 'secret' not in response.text
    assert http['factories'] == []


@pytest.mark.parametrize('body', [
    '[]', 'null', 'true', '{', '{"source_id":"a","source_id":"b","question":"q"}',
    '{"source_id":"a","question":NaN}',
])
def test_malformed_json_is_bounded_and_sanitized_before_factory(http, body):
    response = http['client'].post(PREFIX + '/prepare', headers=HEADERS | {'Content-Type': 'application/json'},
                                   content=body)
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'InvalidRequest'
    assert http['factories'] == []


def test_oversized_streamed_body_is_refused_before_factory(http):
    response = http['client'].post(PREFIX + '/prepare', headers=HEADERS | {'Content-Type': 'application/json'},
        content=iter([b'{"source_id":"a","question":"', b'private-secret'*1000, b'"}']))
    assert response.status_code == 413
    assert 'private' not in response.text and 'secret' not in response.text
    assert http['factories'] == []


def test_content_type_and_unrecognized_query_do_not_select_provider(http):
    response = http['client'].post(PREFIX + '/prepare', headers=HEADERS | {'Content-Type': 'text/plain'},
                                   content='{"source_id":"a","question":"private-secret"}')
    assert response.status_code == 415
    response = http['client'].get(PREFIX + '/status?provider_url=private-secret', headers=HEADERS)
    assert response.status_code == 400
    assert 'private' not in response.text and 'secret' not in response.text
    assert http['factories'] == []


@pytest.mark.parametrize('consent', [False, None, 1, 'true'])
def test_start_requires_exact_consent_before_issuing_run(http, consent):
    body = start_body(http, consent=consent)
    response = post(http, '/start', body)
    assert response.status_code == 400
    assert not http['env']['gateway'].tokens


@pytest.mark.parametrize('changes', [
    {'idempotency_key': ''}, {'idempotency_key': 12345678}, {'idempotency_key': 'x'*81},
    {'source_fingerprint': 123}, {'source_fingerprint': 'q'*64}, {'review_binding': 'bad'},
    {'consent': True, 'model': MODEL}, {'source_id': ['one']},
])
def test_start_has_strict_closed_json_shape(http, changes):
    response = post(http, '/start', start_body(http, **changes))
    assert response.status_code == 400
    assert not http['env']['gateway'].tokens


def test_explicit_source_binding_idempotency_and_draft_evidence_preserve_canonical_stores(http):
    episodes_before = '\n'.join(http['env']['episodes']._conn.iterdump())
    procedures_before = http['env']['skills'].items()
    body = start_body(http)
    response = post(http, '/start', body)
    assert response.status_code == 200, response.text
    result = finished(http, response.json())
    assert result['status'] == 'completed' and result['label'] == 'DRAFT' and result['verified'] is False
    assert result['evidence'][0]['id'] == http['env']['source'].id
    assert http['env']['outside'].id not in json.dumps(result)
    assert all(token not in json.dumps(result) for token in http['env']['gateway'].tokens)
    replay = post(http, '/start', body)
    assert replay.status_code == 200 and replay.json()['id'] == result['id']
    changed = post(http, '/start', body | {'question': QUESTION + ' geändert'})
    assert changed.status_code == 409 and changed.json()['detail']['code'] == 'ReviewChanged'
    assert len(http['env']['gateway'].tokens) == 1
    assert '\n'.join(http['env']['episodes']._conn.iterdump()) == episodes_before
    assert http['env']['skills'].items() == procedures_before


def test_prepared_binding_cannot_be_transferred_to_another_source(http):
    response = post(http, '/start', start_body(http, source_id=http['env']['outside'].id))
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'ReviewChanged'
    assert not http['env']['gateway'].tokens


def test_withdrawn_original_withholds_previously_completed_text(http):
    run = post(http, '/start', start_body(http)).json()
    assert finished(http, run)['status'] == 'completed'
    http['env']['episodes'].ignore(http['env']['source'].id)
    response = http['client'].get(PREFIX + '/runs/' + run['id'], headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['status'] == 'stale'
    assert 'text' not in response.json() and 'evidence' not in response.json()


def test_cancel_revokes_work_even_when_restore_boundary_blocks_new_operations(http, tmp_path):
    boundary = RuntimeBoundary(tmp_path / 'boundary')
    with TestClient(app_for(lambda: http['controller'], boundary=boundary)) as client:
        http['env']['gateway'].release.clear()
        review = client.post(PREFIX + '/prepare', headers=HEADERS,
                             json=dict(source_id=http['env']['source'].id, question=QUESTION)).json()
        run = client.post(PREFIX + '/start', headers=HEADERS, json=start_body(http, review)).json()
        assert http['env']['gateway'].entered.wait(3)
        mark_pending(boundary.directory, 'artificial restore')
        for method, path, body in [('POST', '/prepare', dict(source_id='source', question=QUESTION)),
                                   ('POST', '/start', start_body(http, review)),
                                   ('GET', '/runs/' + run['id'], None)]:
            response = client.request(method, PREFIX + path, headers=HEADERS, json=body)
            assert response.status_code == 503
            assert 'text' not in response.json()
        cancelled = client.post(PREFIX + '/runs/' + run['id'] + '/cancel', headers=HEADERS)
        assert cancelled.status_code == 200
        assert cancelled.json()['status'] == 'cancelled'
        assert 'text' not in cancelled.json() and 'evidence' not in cancelled.json()
        assert http['env']['gateway'].exited.wait(3)


def test_exclusive_update_rejects_new_operation_without_queued_admission(http, tmp_path):
    boundary = RuntimeBoundary(tmp_path / 'boundary')
    assert boundary.try_enter(exclusive=True)
    try:
        with TestClient(app_for(lambda: pytest.fail('factory reached update boundary'), boundary=boundary)) as client:
            response = client.post(PREFIX + '/prepare', headers=HEADERS,
                                   json=dict(source_id='source', question=QUESTION))
            assert response.status_code == 503
    finally:
        boundary.leave(exclusive=True)


def test_boundary_change_during_poll_withholds_result(http):
    run = post(http, '/start', start_body(http)).json()
    assert finished(http, run)['status'] == 'completed'
    class Boundary:
        blocked = False
        def check(self):
            if self.blocked:
                raise RuntimeError('private-secret restore state')
    boundary = Boundary()
    poll = http['controller'].poll
    def crossing(identifier):
        result = poll(identifier)
        boundary.blocked = True
        return result
    http['controller'].poll = crossing
    with TestClient(app_for(lambda: http['controller'], boundary=boundary)) as client:
        response = client.get(PREFIX + '/runs/' + run['id'], headers=HEADERS)
    assert response.status_code == 503
    assert 'text' not in response.json() and 'Fach A42' not in response.text and 'secret' not in response.text


@pytest.mark.parametrize('code,status', [('ReviewChanged',409), ('Busy',409), ('Capacity',429),
                                        ('NotFound',404), ('Unavailable',503), ('Failed',503)])
def test_controller_errors_use_fixed_safe_statuses_and_messages(http, code, status):
    def fail(*_args, **_kwargs):
        error = ControllerError(status, code)
        error.args = ('private-source secret-key',)
        raise error
    http['controller'].prepare = fail
    response = prepare(http)
    assert response.status_code == status
    assert response.json()['detail']['code'] == code
    assert 'private' not in response.text and 'secret' not in response.text


def test_unknown_factory_failure_does_not_expose_diagnostics_or_try_fallback():
    attempts = []
    def broken():
        attempts.append(True)
        raise RuntimeError('private-source secret-key https://provider.invalid')
    with TestClient(app_for(broken)) as client:
        response = client.get(PREFIX + '/status', headers=HEADERS)
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'Unavailable'
    assert len(attempts) == 1
    assert 'private' not in response.text and 'secret' not in response.text and 'provider' not in response.text


def test_blocking_factory_and_manager_work_leave_event_loop_responsive(http):
    async def scenario():
        entered, release = threading.Event(), threading.Event()
        def factory():
            entered.set()
            assert release.wait(3)
            return http['controller']
        app = app_for(factory)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://artificial') as client:
            task = asyncio.create_task(client.get(PREFIX + '/status', headers=HEADERS))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                response = await asyncio.wait_for(client.get('/pulse'), timeout=.5)
                assert response.json() == {'ok': True}
            finally:
                release.set()
            assert (await task).status_code == 200
        health = http['env']['gateway'].health
        entered.clear(); release.clear()
        def slow_health():
            entered.set()
            assert release.wait(3)
            return health()
        http['env']['gateway'].health = slow_health
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=http['app']), base_url='http://artificial') as client:
            task = asyncio.create_task(client.post(PREFIX + '/prepare', headers=HEADERS,
                json=dict(source_id=http['env']['source'].id, question=QUESTION)))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                assert (await asyncio.wait_for(client.get('/pulse'), timeout=.5)).json() == {'ok': True}
            finally:
                release.set()
            assert (await task).status_code == 200
    asyncio.run(scenario())


@pytest.mark.parametrize('location', ['factory', 'controller', 'boundary'])
def test_unexpected_http_exception_from_dependency_is_sanitized(http, location, monkeypatch):
    def fail():
        raise HTTPException(418, 'private-source secret-provider-credential')
    with monkeypatch.context() as patch:
        factory = lambda: http['controller']
        boundary = None
        if location == 'factory':
            factory = fail
        elif location == 'controller':
            patch.setattr(http['controller'], 'runtime_status', fail)
        else:
            class Boundary:
                check = staticmethod(fail)
            boundary = Boundary()
        with TestClient(app_for(factory, boundary=boundary)) as client:
            response = client.get(PREFIX + '/status', headers=HEADERS)
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'Unavailable'
    assert 'private' not in response.text and 'secret' not in response.text


def test_failed_gateway_run_exposes_no_raw_error_or_canonical_write(http):
    before = '\n'.join(http['env']['episodes']._conn.iterdump())
    http['env']['gateway'].error = RuntimeError('private-source secret-worker-grant')
    run = post(http, '/start', start_body(http)).json()
    result = finished(http, run)
    assert result['status'] == 'failed'
    assert result['error'] == 'Failed'
    assert 'text' not in result and 'evidence' not in result
    assert 'private' not in json.dumps(result) and 'secret' not in json.dumps(result)
    assert '\n'.join(http['env']['episodes']._conn.iterdump()) == before


@pytest.mark.parametrize('method,path,body', [
    ('GET', '/runs/' + 'a'*81, None),
    ('POST', '/runs/not-a-run/cancel', None),
    ('GET', '/status', {'api_key': 'private-secret'}),
    ('POST', '/runs/' + 'a'*32 + '/cancel', {'provider_url': 'private-secret'}),
])
def test_run_ids_and_no_argument_routes_are_bounded_before_factory(http, method, path, body):
    response = http['client'].request(method, PREFIX + path, headers=HEADERS, json=body)
    assert response.status_code == 400
    assert 'private' not in response.text and 'secret' not in response.text
    assert http['factories'] == []


def test_stream_reader_exception_never_reflects_raw_request_diagnostics(http, monkeypatch):
    async def failed_stream(_request):
        raise HTTPException(418, 'private-source secret-request-data')
        yield b''
    with monkeypatch.context() as patch:
        patch.setattr(Request, 'stream', failed_stream)
        response = http['client'].get(PREFIX + '/status', headers=HEADERS)
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'InvalidRequest'
    assert 'private' not in response.text and 'secret' not in response.text
    assert http['factories'] == []
