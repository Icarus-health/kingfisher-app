"""Artificial stores, real Broker/Protocol; no network, model or personal data."""
import importlib
import json
import threading
import time

from fastapi.testclient import TestClient
import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.harness_broker import Broker
from icarus_memory.model import Provenance, SourceType
from icarus_memory.procedures import ProcedureStore
from icarus_memory.providers import Reply


MODEL = 'kingfisher-qwen3.5:9b-8k'
MODE = 'controlled-local-readonly-v1'
QUESTION = 'Wo liegt die Zugangskarte?'


def api():
    return importlib.import_module('icarus_memory.local_module_controller')


class GatewayFixture:
    def __init__(self):
        self.health_value = dict(status='ok', mode=MODE, model=MODEL,
                                 syntheticOnly=False, instance='a' * 32)
        self.entered, self.release, self.exited = (threading.Event() for _ in range(3))
        self.release.set()
        self.tokens = []
        self.ignore_cancel = False
        self.result = None
        self.error = None
        self.controller = None

    def health(self):
        return dict(self.health_value)

    def run(self, token, question, cancelled, deadline):
        self.tokens.append(token)
        self.entered.set()
        try:
            while not self.release.wait(.01):
                if cancelled.is_set() and not self.ignore_cancel:
                    raise RuntimeError('secret worker/control token diagnostic')
            if self.error:
                raise self.error
            if self.result is not None:
                return self.result
            client = TestClient(self.controller.worker_app())
            headers = {'Authorization': 'Bearer ' + token}
            def call(name, arguments):
                response = client.post('/worker/mcp', headers=headers,
                    json=dict(jsonrpc='2.0', id=1, method='tools/call',
                              params=dict(name=name, arguments=arguments)))
                assert response.status_code == 200, response.text
                return response.json()['result']
            selected = call('skills_select', {})
            found = call('memory_search', {'query': 'Zugangskarte'})
            assert found['isError'] is False
            response = client.post('/worker/v1/chat/completions', headers=headers,
                json=dict(model=MODEL, messages=[dict(role='user', content=question),
                    dict(role='assistant', content='Ich prüfe das Original.'),
                    dict(role='user', content=found['content'][0]['text'])],
                    tools=[], stream=True, max_completion_tokens=256))
            if response.status_code != 200:
                raise RuntimeError('private stale result: ' + response.text)
            return dict(status='complete', text='Die Zugangskarte liegt in Fach A42.',
                        mode=MODE, model=MODEL, syntheticOnly=False, instance='a' * 32)
        finally:
            self.exited.set()


@pytest.fixture
def env(tmp_path):
    episodes = EpisodeStore(tmp_path / 'originals.db')
    skills = ProcedureStore(tmp_path / 'procedures.db')
    source = episodes.record(EpisodeKind.DOCUMENT, 'Künstliches Original',
        'Die Zugangskarte liegt in Fach A42.', Provenance(source_type=SourceType.DOCUMENT))[0]
    outside = episodes.record(EpisodeKind.DOCUMENT, 'Nicht freigegeben',
        'Die Zugangskarte liegt im privaten Safe Z99.', Provenance(source_type=SourceType.DOCUMENT))[0]
    skill = skills.propose(dict(name='kartenfundort', title='Fundort im Original prüfen',
        area='analysis', description='Fundort einer Zugangskarte im Original prüfen.',
        triggers=['zugangskarte'], steps=['Wörtlich suchen.', 'Fundort und Quelle nennen.'],
        positive=QUESTION, negative='Was steht morgen an?'))
    skills.accept(skill['id'])
    clock = [100.0]
    gateway, controllers, infer_calls = GatewayFixture(), [], []
    provider = [None]
    def create(**kwargs):
        module = api()
        if provider[0] is None:
            provider[0] = module.ProviderIdentity(model=MODEL, local=True, revision='provider-v1')
        def infer(identity, messages, tools, permitted):
            assert permitted()
            infer_calls.append((identity, messages, tools))
            return Reply(text='Die Zugangskarte liegt in Fach A42.', model=MODEL)
        controller = module.LocalModuleController(
            Broker(episodes, skills, clock=lambda: clock[0]),
            gateway=gateway, provider=lambda: provider[0], infer=kwargs.pop('infer', infer),
            clock=lambda: clock[0], **kwargs)
        gateway.controller = controller
        controllers.append(controller)
        return controller
    yield dict(episodes=episodes, skills=skills, source=source, outside=outside, skill=skill,
               clock=clock, gateway=gateway, provider=provider, create=create, infer_calls=infer_calls)
    gateway.release.set()
    for controller in controllers:
        controller.close()
    if gateway.entered.is_set():
        assert gateway.exited.wait(3)
    skills.close()
    episodes.close()


def begin(controller, source, *, key='request-key-0001', review=None, **changes):
    review = review or controller.prepare(source.id, QUESTION)
    return controller.start(source.id, **(dict(question=QUESTION, review_binding=review['review_binding'],
        source_fingerprint=review['source']['fingerprint'],
        consent=True, idempotency_key=key) | changes))


def terminal(controller, run):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = controller.poll(run['id'])
        if result['status'] != 'running':
            return result
        time.sleep(.005)
    pytest.fail('Artificial controller did not finish in 3 seconds')


def test_one_selected_original_uses_current_skills_local_model_and_literal_evidence(env):
    controller = env['create']()
    original = env['episodes'].get(env['source'].id).to_dict()
    procedures = env['skills'].items()
    review = controller.prepare(env['source'].id, QUESTION)
    assert review['source']['id'] == env['source'].id
    assert 'body' not in review['source']
    run = begin(controller, env['source'], review=review)
    assert run['status'] == 'running'
    result = terminal(controller, run)
    assert result['status'] == 'completed'
    assert result['label'] == 'DRAFT'
    assert result['verified'] is False
    assert result['text'] == 'Die Zugangskarte liegt in Fach A42.'
    assert result['evidence'][0]['quote'] == 'Die Zugangskarte liegt in Fach A42.'
    assert result['evidence'][0]['id'] == env['source'].id
    assert result['evidence'][0]['status'] == 'source_reports_unconfirmed'
    assert env['outside'].id not in json.dumps(result)
    assert 'Z99' not in json.dumps(result)
    assert all(token not in json.dumps(result) for token in env['gateway'].tokens)
    assert len(env['infer_calls']) == 1
    identity, messages, _ = env['infer_calls'][0]
    assert identity.model == MODEL and identity.local is True
    assert 'Fundort im Original prüfen' in messages[0]['content']
    assert env['episodes'].get(env['source'].id).to_dict() == original
    assert env['skills'].items() == procedures


@pytest.mark.parametrize('consent', [False, None, 1, 'true'])
def test_consent_requires_exact_true_without_issuing_or_starting(env, consent):
    controller = env['create']()
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], consent=consent)
    assert error.value.status == 400
    assert not env['gateway'].tokens


def test_review_binds_question_source_skill_provider_and_expiry(env):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    for changes in (dict(question='Andere Frage'), dict(review_binding='invented')):
        with pytest.raises(api().ControllerError) as error:
            begin(controller, env['source'], review=review, **changes)
        assert error.value.status == 409
    with pytest.raises(api().ControllerError):
        begin(controller, env['outside'], review=review)
    env['clock'][0] += 121
    with pytest.raises(api().ControllerError):
        begin(controller, env['source'], review=review)
    assert not env['gateway'].tokens


@pytest.mark.parametrize('change', ['source', 'skill', 'provider', 'runtime'])
def test_dependency_change_after_review_prevents_any_execution(env, change):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    mutate(env, change)
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], review=review)
    assert error.value.status == 409
    assert not env['gateway'].tokens


def mutate(env, change):
    if change == 'source':
        env['episodes'].ignore(env['source'].id)
    elif change == 'skill':
        env['skills'].revoke(env['skill']['id'])
    elif change == 'provider':
        env['provider'][0] = api().ProviderIdentity(model=MODEL, local=True, revision='provider-v2')
    elif change == 'runtime':
        env['gateway'].health_value['instance'] = 'b' * 32
    else:
        raise AssertionError(change)


def test_same_key_or_review_replays_once_and_changed_parameters_conflict(env):
    controller = env['create']()
    env['gateway'].release.clear()
    review = controller.prepare(env['source'].id, QUESTION)
    first = begin(controller, env['source'], review=review)
    assert env['gateway'].entered.wait(3)
    assert begin(controller, env['source'], review=review)['id'] == first['id']
    assert begin(controller, env['source'], review=review, key='request-key-0002')['id'] == first['id']
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], review=review, question='Andere Frage')
    assert error.value.status == 409
    other = controller.prepare(env['outside'].id, QUESTION)
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['outside'], review=other)
    assert error.value.status == 409
    assert len(env['gateway'].tokens) == 1


def test_slow_gateway_does_not_block_poll_or_cancel_or_allow_second_thread(env):
    controller = env['create']()
    env['gateway'].release.clear()
    env['gateway'].ignore_cancel = True
    before = time.monotonic()
    run = begin(controller, env['source'])
    assert env['gateway'].entered.wait(3)
    assert controller.poll(run['id'])['status'] == 'running'
    cancelled = controller.cancel(run['id'])
    assert cancelled['status'] == 'cancelled' and 'text' not in cancelled
    assert controller.cancel(run['id'])['status'] == 'cancelled'
    assert time.monotonic() - before < 1
    review = controller.prepare(env['source'].id, QUESTION + ' Erneut.')
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], key='request-key-0002', review=review,
              question=QUESTION + ' Erneut.')
    assert error.value.status == 409
    client = TestClient(controller.worker_app())
    response = client.post('/worker/mcp', headers={'Authorization': 'Bearer ' + env['gateway'].tokens[0]},
                           json=dict(jsonrpc='2.0', id=1, method='tools/list'))
    assert response.status_code == 401
    env['gateway'].release.set()
    assert env['gateway'].exited.wait(3)
    assert controller.poll(run['id'])['status'] == 'cancelled'


@pytest.mark.parametrize('change', ['source', 'skill', 'provider', 'runtime'])
def test_change_during_run_revokes_grant_and_withholds_late_result(env, change):
    controller = env['create']()
    env['gateway'].release.clear()
    env['gateway'].ignore_cancel = True
    run = begin(controller, env['source'])
    assert env['gateway'].entered.wait(3)
    mutate(env, change)
    status = controller.poll(run['id'])
    assert status['status'] == 'stale'
    assert 'text' not in status and 'evidence' not in status
    env['gateway'].release.set()
    assert env['gateway'].exited.wait(3)
    assert controller.poll(run['id'])['status'] == 'stale'


@pytest.mark.parametrize('change', ['source', 'skill', 'provider', 'runtime'])
def test_change_after_completed_result_removes_output_on_next_poll(env, change):
    controller = env['create']()
    run = begin(controller, env['source'])
    assert terminal(controller, run)['status'] == 'completed'
    mutate(env, change)
    status = controller.poll(run['id'])
    assert status['status'] == 'stale'
    assert 'text' not in status and 'evidence' not in status


def test_deadline_revokes_without_waiting_for_a_noncooperative_worker(env):
    controller = env['create']()
    env['gateway'].release.clear()
    env['gateway'].ignore_cancel = True
    run = begin(controller, env['source'])
    assert env['gateway'].entered.wait(3)
    env['clock'][0] += 120
    result = controller.poll(run['id'])
    assert result['status'] == 'timed_out' and 'text' not in result
    env['gateway'].release.set()
    assert env['gateway'].exited.wait(3)
    assert controller.poll(run['id'])['status'] == 'timed_out'


def test_close_revokes_all_and_new_instance_does_not_resurrect_results(env):
    controller = env['create']()
    run = begin(controller, env['source'])
    assert terminal(controller, run)['status'] == 'completed'
    controller.close()
    assert controller.poll(run['id'])['status'] == 'restarted'
    with pytest.raises(api().ControllerError):
        controller.prepare(env['source'].id, QUESTION)
    replacement = env['create']()
    with pytest.raises(api().ControllerError) as error:
        replacement.poll(run['id'])
    assert error.value.status == 404


@pytest.mark.parametrize('bad', [
    dict(status='ok'), dict(status='ok', syntheticOnly=True, mode=MODE, model=MODEL, instance='a'*32),
    dict(status='ok', syntheticOnly=False, mode='artificial', model=MODEL, instance='a'*32),
    dict(status='ok', syntheticOnly=False, mode=MODE, model='cloud', instance='a'*32),
])
def test_current_synthetic_runtime_cannot_be_quietly_used_as_production(env, bad):
    controller = env['create']()
    env['gateway'].health_value = bad
    with pytest.raises(api().ControllerError) as error:
        controller.prepare(env['source'].id, QUESTION)
    assert error.value.status == 503
    assert not env['gateway'].tokens


@pytest.mark.parametrize('change', [dict(local=False), dict(model='other-cloud'), dict(revision='')])
def test_only_current_fixed_local_provider_is_admitted(env, change):
    controller = env['create']()
    env['provider'][0] = api().ProviderIdentity(**(dict(model=MODEL, local=True, revision='provider-v1') | change))
    with pytest.raises(api().ControllerError) as error:
        controller.prepare(env['source'].id, QUESTION)
    assert error.value.status == 503
    assert not env['gateway'].tokens


@pytest.mark.parametrize('result', [
    dict(status='complete', text='secret unverified synthetic', syntheticOnly=True),
    dict(status='complete', text='x' * 32001, mode=MODE, model=MODEL, syntheticOnly=False, instance='a'*32),
    dict(status='complete', text=' ', mode=MODE, model=MODEL, syntheticOnly=False, instance='a'*32),
    dict(status='complete', text='secret worker output', mode=MODE, model=MODEL, syntheticOnly=False, instance='b'*32),
])
def test_invalid_worker_result_is_withheld_without_exposing_raw_diagnostics(env, result):
    controller = env['create']()
    env['gateway'].result = result
    finished = terminal(controller, begin(controller, env['source']))
    assert finished['status'] == 'failed'
    assert 'text' not in finished
    assert 'secret' not in json.dumps(finished)


def test_exception_is_sanitized_without_retry_or_plaintext_result_persistence(env):
    controller = env['create']()
    env['gateway'].error = RuntimeError('private-source secret-api-key master-token')
    run = begin(controller, env['source'])
    finished = terminal(controller, run)
    assert finished['status'] == 'failed'
    assert 'private' not in json.dumps(finished) and 'secret' not in json.dumps(finished)
    assert len(env['gateway'].tokens) == 1
    assert len(env['episodes'].all_episodes()) == 2


def test_bounded_retention_eviction_and_review_expiry_do_not_accumulate_results(env):
    controller = env['create'](max_jobs=2, max_reviews=2, retention=30)
    runs = []
    for number in range(3):
        review = controller.prepare(env['source'].id, QUESTION + str(number))
        run = begin(controller, env['source'], key=f'request-key-000{number}', review=review,
                    question=QUESTION + str(number))
        assert terminal(controller, run)['status'] == 'completed'
        runs.append(run)
    with pytest.raises(api().ControllerError) as error:
        controller.poll(runs[0]['id'])
    assert error.value.status == 404
    env['clock'][0] += 31
    with pytest.raises(api().ControllerError) as error:
        controller.poll(runs[-1]['id'])
    assert error.value.status == 404


def test_no_evidence_is_invented_when_worker_did_not_read_original(env):
    controller = env['create']()
    env['gateway'].result = dict(status='complete', text='Ein ungeprüfter Entwurf.',
        mode=MODE, model=MODEL, syntheticOnly=False, instance='a'*32)
    result = terminal(controller, begin(controller, env['source']))
    assert result['status'] == 'failed'
    assert 'text' not in result and 'evidence' not in result


@pytest.mark.parametrize('change', ['source', 'provider', 'procedure'])
def test_dependency_changes_during_final_scope_collection_withhold_completed_text(env, monkeypatch, change):
    controller = env['create']()
    run = begin(controller, env['source'])
    assert terminal(controller, run)['status'] == 'completed'
    caller = threading.get_ident()
    changed = []
    method = 'current' if change == 'procedure' else 'select'
    original = getattr(env['skills'], method)

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        if threading.get_ident() == caller and not changed:
            changed.append(True)
            if change == 'source':
                env['episodes'].ignore(env['source'].id)
            elif change == 'provider':
                env['provider'][0] = api().ProviderIdentity(model=MODEL, local=True, revision='replacement')
            else:
                env['skills'].revoke(env['skill']['id'])
        return result

    monkeypatch.setattr(env['skills'], method, mutate)
    result = controller.poll(run['id'])
    assert changed
    assert result['status'] == 'stale'
    assert 'text' not in result and 'evidence' not in result


def test_wrong_reply_provider_model_is_withheld_through_actual_protocol(env):
    controller = env['create'](infer=lambda *_args: Reply(text='Cloud-fallback-private', model='cloud'))
    result = terminal(controller, begin(controller, env['source']))
    assert result['status'] == 'failed'
    assert 'Cloud' not in json.dumps(result)


def test_provider_change_is_checked_at_tool_boundary_before_any_more_text(env):
    controller = env['create']()
    env['gateway'].release.clear()
    run = begin(controller, env['source'])
    assert env['gateway'].entered.wait(3)
    mutate(env, 'provider')
    client = TestClient(controller.worker_app())
    response = client.post('/worker/mcp', headers={'Authorization': 'Bearer ' + env['gateway'].tokens[0]},
        json=dict(jsonrpc='2.0', id=1, method='tools/call',
                  params=dict(name='memory_search', arguments={'query': 'Zugangskarte'})))
    assert response.status_code == 401
    assert 'A42' not in response.text
    assert controller.poll(run['id'])['status'] == 'stale'


def test_cancelled_transport_does_not_release_slot_before_owned_slow_inference_exits(env):
    infer_entered, infer_release, infer_exited = (threading.Event() for _ in range(3))
    def slow_infer(_identity, _messages, _tools, _permitted):
        infer_entered.set()
        try:
            assert infer_release.wait(3)
            return Reply(text='Late revoked model result', model=MODEL)
        finally:
            infer_exited.set()
    controller = env['create'](infer=slow_infer)
    gateway = env['gateway']
    requests = []
    def detached_transport(token, question, cancelled, deadline):
        gateway.tokens.append(token)
        def perform():
            requests.append(TestClient(controller.worker_app()).post('/worker/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + token},
                json=dict(model=MODEL, messages=[dict(role='user', content=question)],
                          stream=True, tools=[])))
        worker = threading.Thread(target=perform)
        worker.start()
        assert infer_entered.wait(3)
        gateway.entered.set()
        assert cancelled.wait(3)
        gateway.exited.set()
        raise TimeoutError('transport closed while infer still running')
    gateway.run = detached_transport
    try:
        run = begin(controller, env['source'])
        assert gateway.entered.wait(3)
        cancelled = controller.cancel(run['id'])
        assert cancelled['execution_pending'] is True
        assert gateway.exited.wait(3)
        status = controller.runtime_status()
        assert status['busy'] is True and status['status'] == 'cancelling'
        review = controller.prepare(env['source'].id, QUESTION + ' neu')
        with pytest.raises(api().ControllerError) as error:
            begin(controller, env['source'], key='request-key-0002', review=review,
                  question=QUESTION + ' neu')
        assert error.value.status == 409
        close = controller.close(wait_seconds=.01)
        assert close['status'] == 'stopping' and close['busy'] is True
    finally:
        infer_release.set()
    assert infer_exited.wait(3)
    end = time.monotonic() + 3
    while time.monotonic() < end and controller.runtime_status()['busy']:
        time.sleep(.005)
    assert controller.runtime_status() == dict(status='stopped', busy=False, model=MODEL)
    assert controller.poll(run['id'])['status'] == 'cancelled'
    assert 'text' not in controller.poll(run['id'])


def test_racing_replay_acknowledges_and_binds_both_idempotency_keys(env):
    controller = env['create']()
    gateway = env['gateway']
    gateway.release.clear()
    review = controller.prepare(env['source'].id, QUESTION)
    entered = {name: threading.Event() for name in ('first', 'second')}
    release = {name: threading.Event() for name in entered}
    done = {name: threading.Event() for name in entered}
    responses, errors = {}, []
    original_health = gateway.health
    def health():
        name = threading.current_thread().name
        if name in entered:
            entered[name].set()
            assert release[name].wait(3)
        return original_health()
    gateway.health = health
    def start(name):
        try:
            responses[name] = begin(controller, env['source'], review=review, key=f'request-key-{name}')
        except Exception as error:
            errors.append(error)
        finally:
            done[name].set()
    tasks = [threading.Thread(target=start, args=(name,), name=name) for name in entered]
    for task in tasks:
        task.start()
    try:
        assert all(event.wait(3) for event in entered.values())
        release['first'].set()
        assert done['first'].wait(3)
        release['second'].set()
        assert done['second'].wait(3)
        assert not errors
        assert responses['first']['id'] == responses['second']['id']
        gateway.release.set()
        assert terminal(controller, responses['first'])['status'] == 'completed'
        changed = controller.prepare(env['source'].id, QUESTION + ' neu')
        with pytest.raises(api().ControllerError) as error:
            begin(controller, env['source'], review=changed, key='request-key-second', question=QUESTION + ' neu')
        assert error.value.status == 409
    finally:
        for event in release.values():
            event.set()
        gateway.release.set()
        for task in tasks:
            task.join(3)


def test_review_expiring_while_health_is_checked_does_not_start_a_job(env):
    controller = env['create']()
    review = controller.prepare(env['source'].id, QUESTION)
    env['clock'][0] = 219.0
    original_health = env['gateway'].health
    def health():
        env['clock'][0] = 222.0
        return original_health()
    env['gateway'].health = health
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], review=review)
    assert error.value.status == 409
    assert not env['gateway'].tokens


def test_review_evicted_while_health_is_checked_does_not_start_a_job(env):
    controller = env['create'](max_reviews=1)
    review = controller.prepare(env['source'].id, QUESTION)
    original_health = env['gateway'].health
    evicted = [False]
    def health():
        if not evicted[0]:
            evicted[0] = True
            controller.prepare(env['source'].id, QUESTION + ' ersetzt')
        return original_health()
    env['gateway'].health = health
    with pytest.raises(api().ControllerError) as error:
        begin(controller, env['source'], review=review)
    assert error.value.status == 409
    assert not env['gateway'].tokens


def test_cancel_between_final_tool_check_and_receipt_append_clears_terminal_evidence(env):
    controller = env['create']()
    env['gateway'].release.clear()
    run = begin(controller, env['source'])
    assert env['gateway'].entered.wait(3)
    owned = controller._owned_job
    checks, retained = [0], []
    def interleaved(token):
        job = owned(token)
        checks[0] += 1
        if checks[0] == 3:  # authorize, before tool, after tool
            retained.append(job)
            controller.cancel(run['id'])
        return job
    controller._owned_job = interleaved
    response = TestClient(controller.worker_app()).post('/worker/mcp',
        headers={'Authorization': 'Bearer ' + env['gateway'].tokens[0]},
        json=dict(jsonrpc='2.0', id=1, method='tools/call',
                  params=dict(name='memory_search', arguments={'query': 'Zugangskarte'})))
    assert len(retained) == 1
    assert retained[0].evidence == [] and retained[0].text is None
    assert response.json()['result']['isError'] is True
    assert controller.poll(run['id'])['status'] == 'cancelled'


@pytest.mark.parametrize('change', ['source', 'skill', 'provider'])
def test_result_poll_rechecks_local_scope_after_blocking_gateway_health(env, change):
    controller = env['create']()
    run = begin(controller, env['source'])
    assert terminal(controller, run)['status'] == 'completed'
    health = env['gateway'].health
    mutated = [False]
    def interleaved_health():
        if not mutated[0]:
            mutated[0] = True
            mutate(env, change)
        return health()
    env['gateway'].health = interleaved_health
    result = controller.poll(run['id'])
    assert result['status'] == 'stale'
    assert 'text' not in result and 'evidence' not in result
