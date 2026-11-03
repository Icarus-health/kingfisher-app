"""Actual local guard/profile/provider, artificial HTTP only; no model is run."""
from copy import deepcopy
import importlib
import json
import threading
import time

import httpx
import pytest

from icarus_memory.harness_broker import BridgeError
from icarus_memory.local_module_controller import MODEL
from icarus_memory.providers import OpenAICompatible


def api():
    return importlib.import_module('icarus_memory.local_module_model')


@pytest.fixture
def fixture(monkeypatch):
    from icarus_memory import hintergrund, ollama_memory
    ampel = hintergrund.ModellAmpel()
    monkeypatch.setattr(hintergrund, 'AMPEL', ampel)
    monkeypatch.setattr(ollama_memory, '_MANAGED_MODEL_LOCK', threading.RLock())
    monkeypatch.setenv('ICARUS_OLLAMA_8K_PROFILE', MODEL)
    ordinary = OpenAICompatible(MODEL, base_url='http://127.0.0.1:11434/v1', api_key='artificial-key-sentinel')
    state = dict(provider=ordinary,
        tags={'models': [{'name': MODEL, 'digest': 'a' * 64, 'size': 100000, 'details': {'format': 'gguf'}}]},
        show={'details': {'format': 'gguf'}, 'capabilities': ['completion'],
              'model_info': {'general.architecture': 'qwen3', 'general.parameter_count': 9000000000},
              'parameters': 'num_ctx 8192'}, version='0.40.13', allowed=True, hook=None,
        response={'done': True, 'done_reason': 'stop', 'message': {'content': 'Künstlicher Entwurf.'},
                  'prompt_eval_count': 100, 'eval_count': 12})
    requests, occupancy, timeouts = [], [], []
    def handler(request):
        body = json.loads(request.content) if request.content else None
        requests.append((request.url.path, body, str(request.url)))
        if state['hook'] is not None:
            state['hook'](request)
        path = request.url.path
        if path == '/api/tags':
            return httpx.Response(200, json=state['tags'])
        if path == '/api/show':
            assert body == {'model': MODEL}
            return httpx.Response(200, json=state['show'])
        if path == '/api/version':
            return httpx.Response(200, json={'version': state['version']})
        if path == '/api/ps':
            return httpx.Response(200, json={'models': []})
        if path == '/api/chat':
            occupancy.append(ampel.belegt())
            return httpx.Response(200, json=state['response'])
        pytest.fail('Unexpected model-loading/fallback request: ' + path)
    original = httpx.Client
    def client(**kwargs):
        assert kwargs.get('trust_env') is False
        assert kwargs.get('follow_redirects') is False
        timeouts.append(kwargs.get('timeout'))
        return original(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(httpx, 'Client', client)
    shared = threading.Lock()
    def create(boundary=None):
        return api().VerifiedModuleModel(lambda: state['provider'], shared, boundary=boundary)
    yield dict(state=state, requests=requests, occupancy=occupancy, timeouts=timeouts, create=create,
               ordinary=ordinary, shared=shared, ampel=ampel)
    assert ampel.belegt() == {'vorne': 0, 'hinten': 0}
    assert shared.acquire(blocking=False)
    shared.release()


def inference(model, expected, fixture):
    return model.infer(expected, [{'role': 'user', 'content': 'ARTIFICIAL_SOURCE_SENTINEL'}], [],
                       lambda: fixture['state']['allowed'])


def chats(fixture):
    return [body for path, body, _url in fixture['requests'] if path == '/api/chat']


def test_identity_positively_verifies_fixed_weights_profile_without_model_loading(fixture):
    before = deepcopy(vars(fixture['ordinary']))
    model = fixture['create']()
    identity = model.identity()
    assert identity.model == MODEL and identity.local is True
    assert len(identity.revision) == 64
    assert '127.0.0.1' not in identity.revision and 'sentinel' not in identity.revision
    assert model.identity() == identity
    assert {path for path, _body, _url in fixture['requests']} == {'/api/tags', '/api/show', '/api/version'}
    assert vars(fixture['ordinary']) == before


def test_verified_inference_reuses_one_ampel_permit_and_never_mutates_ordinary_provider(fixture):
    model = fixture['create']()
    before = deepcopy(vars(fixture['ordinary']))
    identity = model.identity()
    reply = inference(model, identity, fixture)
    assert reply.text == 'Künstlicher Entwurf.' and reply.model == MODEL
    # The closed worker protocol permits at most 256 output tokens. Ordinary
    # chat defaults (1024 tokens / temperature1) must not leak into fact review.
    assert chats(fixture)[0]['options']['num_predict'] == 256
    assert chats(fixture)[0]['options']['temperature'] == 0
    assert fixture['occupancy'] == [{'vorne': 1, 'hinten': 0}]
    assert len(chats(fixture)) == 1
    body = chats(fixture)[0]
    assert body['model'] == MODEL and body['truncate'] is False and body['shift'] is False
    assert body['options']['num_ctx'] == 8192
    assert body['messages'][0]['content'] == 'ARTIFICIAL_SOURCE_SENTINEL'
    assert vars(fixture['ordinary']) == before
    assert all(0 < float(timeout) <= 60 for timeout in fixture['timeouts'])


@pytest.mark.parametrize('invalid', ['fake', 'subclass', 'remote', 'wrong_model', 'unselected',
    'cloud_tags', 'cloud_show', 'no_weights', 'bad_digest', 'wrong_context', 'duplicate_context', 'old_version'])
def test_unproven_provider_never_loads_model_or_receives_source(fixture, monkeypatch, invalid):
    state = fixture['state']
    if invalid == 'fake':
        state['provider'] = type('Fake', (), dict(model=MODEL, is_local=True))()
    elif invalid == 'subclass':
        class Other(OpenAICompatible):
            pass
        state['provider'] = Other(MODEL, base_url='http://127.0.0.1:11434/v1')
    elif invalid == 'remote':
        state['provider']._base = 'https://remote.invalid/v1'
    elif invalid == 'wrong_model':
        state['provider'].model = 'other-cloud'
    elif invalid == 'unselected':
        monkeypatch.delenv('ICARUS_OLLAMA_8K_PROFILE')
    elif invalid == 'cloud_tags':
        state['tags']['models'][0]['remote_model'] = 'cloud-model'
    elif invalid == 'cloud_show':
        state['show']['remote_host'] = 'https://remote.invalid'
    elif invalid == 'no_weights':
        state['tags']['models'][0]['size'] = 0
    elif invalid == 'bad_digest':
        state['tags']['models'][0]['digest'] = ''
    elif invalid == 'wrong_context':
        state['show']['parameters'] = 'num_ctx 32768'
    elif invalid == 'duplicate_context':
        state['show']['parameters'] = 'num_ctx 8192\nnum_ctx 8192'
    elif invalid == 'old_version':
        state['version'] = '0.40.12'
    model = fixture['create']()
    with pytest.raises(BridgeError) as error:
        model.identity()
    assert 'remote' not in str(error.value) and 'sentinel' not in str(error.value)
    assert not chats(fixture)
    assert not any('ARTIFICIAL_SOURCE_SENTINEL' in str(body) for _path, body, _url in fixture['requests'])


@pytest.mark.parametrize('change', ['object', 'endpoint', 'key', 'trust', 'digest', 'context', 'flag'])
def test_reviewed_identity_rejects_provider_configuration_or_weights_swap_before_source(fixture, monkeypatch, change):
    model = fixture['create']()
    identity = model.identity()
    state = fixture['state']
    if change == 'object':
        state['provider'] = OpenAICompatible(MODEL, base_url=state['provider'].base_url)
    elif change == 'endpoint':
        state['provider']._base = 'http://localhost:11434/v1'
    elif change == 'key':
        state['provider']._key = 'changed-artificial-key'
    elif change == 'trust':
        state['provider']._trusted_local_hosts = ('host.docker.internal',)
    elif change == 'digest':
        state['tags']['models'][0]['digest'] = 'b' * 64
    elif change == 'context':
        state['show']['parameters'] = 'num_ctx 32768'
    elif change == 'flag':
        monkeypatch.delenv('ICARUS_OLLAMA_8K_PROFILE')
    with pytest.raises(BridgeError):
        inference(model, identity, fixture)
    assert not chats(fixture)


@pytest.mark.parametrize('change', ['cancel', 'object', 'digest', 'context'])
def test_change_during_inference_withholds_reply_and_cleans_all_permits(fixture, change):
    model = fixture['create']()
    identity = model.identity()
    def mutate(request):
        if request.url.path != '/api/chat':
            return
        state = fixture['state']
        if change == 'cancel':
            state['allowed'] = False
        elif change == 'object':
            state['provider'] = OpenAICompatible(MODEL, base_url=state['provider'].base_url)
        elif change == 'digest':
            state['tags']['models'][0]['digest'] = 'b' * 64
        else:
            state['show']['parameters'] = 'num_ctx 32768'
    fixture['state']['hook'] = mutate
    with pytest.raises(BridgeError):
        inference(model, identity, fixture)
    assert len(chats(fixture)) == 1


def test_cancel_before_entry_sends_no_source_or_model_preparation(fixture):
    model = fixture['create']()
    identity = model.identity()
    fixture['requests'].clear()
    fixture['state']['allowed'] = False
    with pytest.raises(BridgeError):
        inference(model, identity, fixture)
    assert fixture['requests'] == []


@pytest.mark.parametrize('busy', ['conversation', 'foreground', 'background', 'memory', 'boundary'])
def test_busy_shared_capacity_rejects_without_waiting_or_model_loading(fixture, busy):
    from icarus_memory import ollama_memory
    model = fixture['create']()
    identity = model.identity()
    ready, release = threading.Event(), threading.Event()
    def occupy():
        if busy == 'conversation':
            context = fixture['shared']
        elif busy == 'foreground':
            context = fixture['ampel'].vordergrund()
        elif busy == 'background':
            context = fixture['ampel'].hintergrund()
        else:
            context = ollama_memory.try_managed_model()
        with context:
            ready.set()
            assert release.wait(3)
    if busy == 'boundary':
        class Boundary:
            def check(self):
                pass
            def try_enter(self):
                return False
            def leave(self):
                pytest.fail('unowned boundary must never be released')
        model = fixture['create'](Boundary())
    else:
        task = threading.Thread(target=occupy)
        task.start()
        assert ready.wait(3)
    try:
        before = time.monotonic()
        with pytest.raises(BridgeError):
            inference(model, identity, fixture)
        assert time.monotonic() - before < .3
        assert not chats(fixture)
    finally:
        release.set()
        if busy != 'boundary':
            task.join(3)


def test_three_racing_callbacks_start_only_one_physical_model_request(fixture):
    model = fixture['create']()
    identity = model.identity()
    entered, release = threading.Event(), threading.Event()
    def block(request):
        if request.url.path == '/api/chat':
            entered.set()
            assert release.wait(3)
    fixture['state']['hook'] = block
    results, errors = [], []
    def perform():
        try:
            results.append(inference(model, identity, fixture))
        except BridgeError as error:
            errors.append(str(error))
    first = threading.Thread(target=perform)
    first.start()
    try:
        assert entered.wait(3)
        others = [threading.Thread(target=perform) for _ in range(2)]
        for task in others:
            task.start()
        for task in others:
            task.join(.5)
        assert all(not task.is_alive() for task in others)
        assert len(errors) == 2
        assert len(chats(fixture)) == 1
        fixture['state']['allowed'] = False
        # Cancellation does not release locks while the artificial request is blocked.
        assert not fixture['shared'].acquire(blocking=False)
        assert fixture['ampel'].belegt() == {'vorne': 1, 'hinten': 0}
    finally:
        release.set()
        first.join(3)
    assert results == [] and len(errors) == 3


def test_provider_error_is_sanitized_and_never_retried_or_falls_back(fixture):
    model = fixture['create']()
    identity = model.identity()
    def fail(request):
        if request.url.path == '/api/chat':
            raise httpx.ReadTimeout('artificial-key-sentinel private source http://local-secret')
    fixture['state']['hook'] = fail
    with pytest.raises(BridgeError) as error:
        inference(model, identity, fixture)
    assert 'sentinel' not in str(error.value) and 'http' not in str(error.value)
    assert len(chats(fixture)) == 1


def test_native_tool_definitions_and_returned_ids_survive_verified_adapter(fixture):
    model = fixture['create']()
    identity = model.identity()
    fixture['state']['response']['message'] = {'content': '', 'tool_calls': [dict(
        id='synthetic-call', function={'name': 'mcp__kingfisher__selected_original', 'arguments': {}})]}
    tools = [dict(name='mcp__kingfisher__selected_original', description='Read selected original only.',
                  parameters={'type': 'object', 'properties': {}, 'additionalProperties': False})]
    result = model.infer(identity, [{'role': 'user', 'content': 'Synthetic question'}], tools, lambda: True)
    assert result.tool_calls[0].id == 'synthetic-call'
    assert result.tool_calls[0].name == 'mcp__kingfisher__selected_original'
    assert result.tool_calls[0].arguments == {}
    assert chats(fixture)[0]['tools'] == [{'type': 'function', 'function': tools[0]}]


@pytest.mark.parametrize('stage', ['metadata', 'preparation', 'response'])
def test_shared_deadline_prevents_late_loading_or_result_release(fixture, monkeypatch, stage):
    from types import SimpleNamespace
    from icarus_memory import providers
    module = api()
    clock = [time.monotonic()]
    fake_time = SimpleNamespace(monotonic=lambda: clock[0])
    monkeypatch.setattr(module, 'time', fake_time)
    monkeypatch.setattr(providers, 'time', fake_time)
    model = fixture['create']()
    identity = model.identity()
    path = {'metadata': '/api/tags', 'preparation': '/api/ps', 'response': '/api/chat'}[stage]
    def expire(request):
        if request.url.path == path:
            clock[0] += 61
    fixture['state']['hook'] = expire
    with pytest.raises(BridgeError):
        inference(model, identity, fixture)
    assert len(chats(fixture)) == (1 if stage == 'response' else 0)


def test_existing_narrower_deadline_is_not_extended_for_source_transport(fixture):
    from icarus_memory.providers import json_request_deadline
    model = fixture['create']()
    identity = model.identity()
    with json_request_deadline(time.monotonic() + 1):
        assert inference(model, identity, fixture).model == MODEL
    assert any(0 < float(timeout) < 1 for timeout in fixture['timeouts'])


def test_metadata_redirect_cannot_escape_to_another_endpoint(monkeypatch):
    monkeypatch.setenv('ICARUS_OLLAMA_8K_PROFILE', MODEL)
    provider = OpenAICompatible(MODEL, base_url='http://127.0.0.1:11434/v1')
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(307, headers={'location': 'https://remote.invalid/api/tags'})
    real_client = httpx.Client
    def client(**kwargs):
        assert kwargs.get('trust_env') is False and kwargs.get('follow_redirects') is False
        return real_client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(httpx, 'Client', client)
    model = api().VerifiedModuleModel(lambda: provider, threading.Lock())
    with pytest.raises(BridgeError) as error:
        model.identity()
    assert len(requests) == 1 and requests[0].url.host == '127.0.0.1'
    assert 'http' not in str(error.value) and 'remote' not in str(error.value)


def test_boundary_lease_is_balanced_and_rechecked_before_result_release(fixture):
    state = {'readers': 0, 'revoked': False}
    class Boundary:
        def check(self):
            if state['revoked']:
                raise RuntimeError('private restore details')
        def try_enter(self):
            state['readers'] += 1
            return True
        def leave(self):
            state['readers'] -= 1
    model = fixture['create'](Boundary())
    identity = model.identity()
    assert state['readers'] == 0
    def revoke(request):
        if request.url.path == '/api/chat':
            assert state['readers'] == 1
            state['revoked'] = True
    fixture['state']['hook'] = revoke
    with pytest.raises(BridgeError) as error:
        inference(model, identity, fixture)
    assert state['readers'] == 0
    assert 'private' not in str(error.value)
