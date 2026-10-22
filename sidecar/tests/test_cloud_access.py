"""Preparation stores separate encrypted credentials without activating inference."""
import os
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from icarus_memory import config
from icarus_memory.secrets import PASSPHRASE_ENV, KeychainError
from icarus_memory.server import create_app


@pytest.fixture
def prepared(monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-encryption-passphrase-only')
    app = create_app()
    with TestClient(app) as client:
        yield app, client


def test_save_is_encrypted_write_only_separate_and_does_not_activate(prepared, monkeypatch):
    app, client = prepared
    from icarus_memory.providers import OpenAICompatible
    monkeypatch.setattr(OpenAICompatible, 'complete', lambda *a, **k: pytest.fail('No inference during preparation'))
    roles = deepcopy(app.state.settings.model_roles)
    for provider, name in [('mistral', 'MISTRAL_API_KEY'), ('openrouter', 'OPENROUTER_API_KEY'), ('anthropic', 'ICARUS_PREPARED_ANTHROPIC_API_KEY'), ('openai', 'ICARUS_PREPARED_OPENAI_API_KEY')]:
        secret = 'synthetic-' + provider + '-secret'
        response = client.put('/api/v1/models/cloud-access/' + provider, json={'api_key': secret, 'model': 'synthetic-model'})
        assert response.status_code == 200, response.text
        assert secret not in response.text
        assert app.state.keychain.get(name) == secret
        assert secret not in app.state.keychain.secrets_path.read_text()
        assert secret not in config.path_for(config.Path(os.environ['ICARUS_DATA_DIR'])).read_text()
    assert app.state.settings.model_roles == roles
    status = client.get('/api/v1/models/cloud-access').json()
    assert status['storage_available']
    assert all(p['key_present'] for p in status['providers'])
    assert {p['endpoint'] for p in status['providers']} == {'https://api.eu.mistral.ai/v1', 'https://eu.openrouter.ai/api/v1', 'https://api.anthropic.com/v1', 'https://api.openai.com/v1'}
    assert client.delete('/api/v1/models/cloud-access/mistral').status_code == 200
    assert app.state.keychain.get('MISTRAL_API_KEY') is None
    assert app.state.keychain.get('OPENROUTER_API_KEY')


def test_unavailable_or_failed_storage_never_reports_success(monkeypatch, prepared):
    app, client = prepared
    def fail(*a):
        raise KeychainError('synthetic provider failure')
    monkeypatch.setattr(app.state.keychain, 'set', fail)
    response = client.put('/api/v1/models/cloud-access/mistral', json={'api_key': 'synthetic', 'model': ''})
    assert response.status_code == 409
    assert not os.environ.get('MISTRAL_API_KEY')
    assert not app.state.settings.cloud_models


def test_key_change_revokes_existing_consent_and_failed_config_save_rolls_back(prepared, monkeypatch):
    app, client = prepared
    path = '/api/v1/models/cloud-access/mistral'
    assert client.put(path, json={'api_key': 'synthetic-old', 'model': 'synthetic-model'}).status_code == 200
    app.state.settings.model_roles['antwort'] = {'cloud': True, 'anbieter': 'mistral', 'modell': 'synthetic-model', 'cloud_einwilligung': '2026-10-07T00:00:00Z'}
    assert client.put(path, json={'api_key': 'synthetic-new', 'model': 'synthetic-model'}).status_code == 200
    assert not app.state.settings.model_roles.get('antwort', {}).get('cloud')
    def fail(*a):
        raise OSError('synthetic full disk')
    monkeypatch.setattr(config, 'save', fail)
    response = client.put(path, json={'api_key': 'synthetic-third', 'model': 'other'})
    assert response.status_code == 409
    assert app.state.keychain.get('MISTRAL_API_KEY') == os.environ['MISTRAL_API_KEY'] == 'synthetic-new'
    assert app.state.settings.cloud_models['mistral'] == 'synthetic-model'


def test_validation_auth_and_no_persistent_storage(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-auth-token')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/models/cloud-access').status_code == 401
        headers = {'X-Icarus-Token': 'synthetic-auth-token'}
        assert client.get('/api/v1/models/cloud-access', headers=headers).json()['storage_available'] is False
        assert client.put('/api/v1/models/cloud-access/mistral', headers=headers, json={'api_key': 'synthetic', 'model': ''}).status_code == 409
        assert client.put('/api/v1/models/cloud-access/unknown', headers=headers, json={'model': ''}).status_code == 404
        assert client.put('/api/v1/models/cloud-access/mistral', headers=headers, json={'api_key': 'synthetic\ninvalid', 'model': ''}).status_code == 422


def test_malformed_input_never_echoes_credentials(prepared):
    _, client = prepared
    for body in ({'api_key': 'synthetic-sensitive', 'model': 'bad model'},
                 {'api_key': {'synthetic-sensitive': True}, 'model': ''},
                 {'api_key': 'synthetic-sensitive\ninvalid', 'model': ''}):
        response = client.put('/api/v1/models/cloud-access/mistral', json=body)
        assert response.status_code == 422
        assert 'synthetic-sensitive' not in response.text


def test_consent_revocation_cannot_fall_through_to_a_cloud_default(prepared):
    app, client = prepared
    from icarus_memory.model_roles import lese_wahlen, provider_fuer
    from icarus_memory.providers import OpenAICompatible
    path = '/api/v1/models/cloud-access/mistral'
    assert client.put(path, json={'api_key': 'synthetic-old', 'model': 'synthetic-model'}).status_code == 200
    app.state.settings.model_roles['antwort'] = {'cloud': True, 'anbieter': 'mistral', 'modell': 'synthetic-model', 'cloud_einwilligung': '2026-10-07T00:00:00Z'}
    assert client.delete(path).status_code == 200
    remote_default = OpenAICompatible('synthetic-other-vendor', 'synthetic-other-key')
    assert provider_fuer('antwort', remote_default, lese_wahlen(app.state.settings.model_roles)) is None
    # Persisted revocation must also survive a restart.
    settings = config.load(config.Path(os.environ['ICARUS_DATA_DIR']))
    assert provider_fuer('antwort', remote_default, lese_wahlen(settings.model_roles)) is None


def test_model_only_save_retains_the_active_environment_override(prepared, monkeypatch):
    app, client = prepared
    app.state.keychain.set('MISTRAL_API_KEY', 'synthetic-stale-stored')
    monkeypatch.setenv('MISTRAL_API_KEY', 'synthetic-active-override')
    assert client.put('/api/v1/models/cloud-access/mistral', json={'model': 'new-model'}).status_code == 200
    assert os.environ['MISTRAL_API_KEY'] == 'synthetic-active-override'


def test_regional_roles_require_model_key_and_explicit_consent(prepared):
    app, client = prepared
    from icarus_memory.model_roles import rollen_von
    from tests.ollama_fake import FakeOllama
    app.state.ollama_transport = FakeOllama().transport
    app.state.ollama_inventar.vergiss()
    access = '/api/v1/models/cloud-access/mistral'
    role = '/api/v1/models/roles/antwort'
    assert client.put(role, json={'cloud': True, 'anbieter': 'mistral'}).status_code == 422
    assert client.put(access, json={'api_key': 'synthetic-only', 'model': ''}).status_code == 200
    assert client.put(role, json={'cloud': True, 'anbieter': 'mistral', 'einwilligung': True}).status_code == 422
    assert client.put(access, json={'model': 'synthetic-model'}).status_code == 200
    assert client.put(role, json={'cloud': True, 'anbieter': 'mistral', 'einwilligung': True}).status_code == 200
    provider = rollen_von(app).provider('antwort')
    assert provider.base_url == 'https://api.eu.mistral.ai/v1' and provider.model == 'synthetic-model'
    for name in ('hintergrund', 'einbettung', 'pruefung'):
        assert client.put('/api/v1/models/roles/' + name, json={'cloud': True, 'anbieter': 'mistral', 'einwilligung': True}).status_code == 422
    assert client.put(role, json={'cloud': False}).status_code == 200
    assert app.state.settings.model_roles['antwort']['local_only'] is True


def test_local_only_revocation_rejects_unverified_ollama_cloud_model():
    from icarus_memory.model_roles import RollenWahl, provider_fuer
    from icarus_memory.ollama_inventar import UNBEKANNT
    from icarus_memory.providers import OpenAICompatible
    class UnknownInventory:
        def art(self, *args):
            return UNBEKANNT
    standard = OpenAICompatible('synthetic:cloud', base_url='http://localhost:11434/v1')
    assert provider_fuer('antwort', standard, {'antwort': RollenWahl(local_only=True)}, inventar=UnknownInventory()) is None


@pytest.mark.parametrize('consent', ['', '2026-10-07T00:00:00Z'])
def test_regional_choice_with_missing_credentials_never_falls_back_to_global_cloud(consent):
    from icarus_memory.model_roles import RollenWahl, provider_fuer
    from icarus_memory.providers import OpenAICompatible
    default = OpenAICompatible('synthetic-global', 'synthetic-default-key')
    selected = RollenWahl(cloud=True, anbieter='mistral', modell='synthetic-model', cloud_einwilligung=consent)
    assert provider_fuer('antwort', default, {'antwort': selected}, {}) is None


def test_rebuild_failure_cannot_leave_a_revoked_captured_provider_active(prepared, monkeypatch):
    app, client = prepared
    from icarus_memory.providers import OpenAICompatible
    import icarus_memory.server as server
    path = '/api/v1/models/cloud-access/mistral'
    assert client.put(path, json={'api_key': 'synthetic-old', 'model': 'synthetic-model'}).status_code == 200
    app.state.settings.model_roles['antwort'] = {'cloud': True, 'anbieter': 'mistral', 'modell': 'synthetic-model', 'cloud_einwilligung': '2026-10-07T00:00:00Z'}
    app.state.agent._provider = OpenAICompatible('synthetic-model', 'synthetic-old', base_url='https://api.eu.mistral.ai/v1')
    def fail(*args):
        raise RuntimeError('synthetic rebuild failure')
    monkeypatch.setattr(server, '_build_agent', fail)
    response = client.delete(path)
    assert response.status_code == 409
    assert app.state.agent.provider is None
    assert app.state.agent._frage_anbieter() is None


def test_anthropic_preparation_rotates_opaque_revision_without_enabling_roles(prepared, monkeypatch):
    from icarus_memory.cloud_import_provider import credential_status
    app, client = prepared
    roles = deepcopy(app.state.settings.model_roles)
    path = '/api/v1/models/cloud-access/anthropic'
    assert client.put(path, json={'api_key':'synthetic-first', 'model':'claude-synthetic'}).status_code == 200
    first = credential_status(app.state.keychain, app.state.settings)
    assert first['available']
    assert client.put(path, json={'model':'claude-synthetic'}).status_code == 200
    assert credential_status(app.state.keychain, app.state.settings) == first
    assert client.delete(path).status_code == 200
    assert not credential_status(app.state.keychain, app.state.settings)['available']
    assert client.put(path, json={'api_key':'synthetic-first', 'model':'claude-synthetic'}).status_code == 200
    assert credential_status(app.state.keychain, app.state.settings)['credential_revision'] != first['credential_revision']
    assert app.state.settings.model_roles == roles
    status = client.get('/api/v1/models/cloud-access').json()
    for item in status['providers']:
        assert item['privacy']['checked_at'] == '2026-10-19'
        assert item['privacy']['sources']
    assert 'nicht ausschließlich' in next(item for item in status['providers'] if item['id'] == 'anthropic')['privacy']['region']
    assert 'UK' in next(item for item in status['providers'] if item['id'] == 'openrouter')['privacy']['region']


def test_anthropic_import_route_preview_start_and_key_revocation_are_source_scoped(prepared, monkeypatch):
    import json
    import httpx
    from icarus_memory import EpisodeKind, Provenance, SourceType
    from icarus_memory.cloud_import_provider import AnthropicImportProvider
    app, client = prepared
    sends = []
    def handler(request):
        payload = json.loads(request.content)
        sends.append(payload)
        schema = payload['tools'][0]['input_schema']
        source = json.loads(payload['messages'][-1]['content'])
        result = ({'items': [{'block_id': block['block_id'], 'kind':'fact'} for block in source['blocks']]}
                  if 'items' in schema['properties'] else {'categories': [], 'entities': []})
        return httpx.Response(200, json={'stop_reason':'tool_use', 'content':[{'type':'tool_use', 'name':'memory_result', 'input':result}]})
    monkeypatch.setattr(AnthropicImportProvider, '_client', lambda self: httpx.Client(transport=httpx.MockTransport(handler)))
    original, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Synthetic route mail', 'Synthetic private route source', Provenance(SourceType.EMAIL, source_ref='synthetic-route'))
    assert client.put('/api/v1/models/cloud-access/anthropic', json={'api_key':'synthetic-route-key', 'model':'claude-synthetic'}).status_code == 200
    preview = client.post('/api/v1/memory/cloud/preview', json={'provider':'anthropic', 'source_ids':[original.id]})
    assert preview.status_code == 200, preview.text
    assert preview.json()['provider'] == 'anthropic'
    assert sends == []
    body = {'preview_id':preview.json()['preview_id'], 'provider':'anthropic', 'model':'claude-synthetic', 'consent':False}
    assert client.post('/api/v1/memory/cloud/start', json=body).status_code == 409
    body['consent'] = True
    started = client.post('/api/v1/memory/cloud/start', json=body)
    assert started.status_code == 200, started.text
    job_id = started.json()['job']['id']
    app.state.cloud_memory_jobs._threads[job_id].join(30)
    assert not app.state.cloud_memory_jobs._threads[job_id].is_alive()
    status = client.get('/api/v1/memory/cloud/status').json()['job']
    assert status['state'] == 'complete', status
    assert status['provider'] == 'anthropic'
    assert len(sends) == 2
    assert b'synthetic-route-key' not in app.state.cloud_memory_jobs.path.read_bytes()
    assert b'Synthetic private route source' not in app.state.cloud_memory_jobs.path.read_bytes()
    preview = client.post('/api/v1/memory/cloud/preview', json={'provider':'anthropic'}).json()
    assert client.delete('/api/v1/models/cloud-access/anthropic').status_code == 200
    body['preview_id'] = preview['preview_id']
    assert client.post('/api/v1/memory/cloud/start', json=body).status_code == 409
    assert len(sends) == 2


def test_preparing_mainstream_keys_never_switches_default_provider_even_after_restart(prepared):
    from icarus_memory.providers import from_env
    from icarus_memory.secrets import load_into_env
    app, client = prepared
    assert from_env() is None
    for identifier in ('anthropic','openai'):
        assert client.put('/api/v1/models/cloud-access/' + identifier,
                          json={'api_key':'synthetic-' + identifier, 'model':'synthetic-model'}).status_code == 200
    assert not os.environ.get('ANTHROPIC_API_KEY')
    assert not os.environ.get('OPENAI_API_KEY')
    assert from_env() is None
    for name in ('ICARUS_PREPARED_ANTHROPIC_API_KEY','ICARUS_PREPARED_OPENAI_API_KEY'):
        os.environ.pop(name, None)
    load_into_env(app.state.keychain)
    assert from_env() is None
    reloaded = config.load(config.Path(os.environ['ICARUS_DATA_DIR']))
    assert reloaded.cloud_models['anthropic'] == 'synthetic-model'
    assert reloaded.cloud_models['openai'] == 'synthetic-model'
    assert reloaded.model_roles == app.state.settings.model_roles


@pytest.mark.parametrize('identifier', ['anthropic','openai'])
def test_prepared_keys_require_separate_role_consent_and_leave_background_local(prepared, identifier):
    from icarus_memory.model_roles import rollen_von
    from icarus_memory.providers import from_env
    app, client = prepared
    assert client.put('/api/v1/models/cloud-access/' + identifier,
                      json={'api_key':'synthetic-key', 'model':'synthetic-model'}).status_code == 200
    assert from_env() is None
    for role in ('einbettung','pruefung'):
        assert client.put('/api/v1/models/roles/' + role,
                          json={'cloud':True, 'anbieter':identifier, 'einwilligung':True}).status_code == 422
    # Der Hintergrund nimmt nur Anthropic, mit eigener Einwilligung; der Anbieter der Rolle bleibt dabei lokal oder None.
    from icarus_memory import hintergrund_cloud
    hintergrund = client.put('/api/v1/models/roles/hintergrund',
                             json={'cloud':True, 'anbieter':identifier, 'einwilligung':True})
    assert hintergrund.status_code == (200 if identifier == 'anthropic' else 422), hintergrund.text
    assert rollen_von(app).provider('hintergrund') is None
    assert (rollen_von(app).hintergrund_cloud_wahl() is not None) is (identifier == 'anthropic')
    assert (hintergrund_cloud.anbieter(app) is not None) is (identifier == 'anthropic')
    assert client.put('/api/v1/models/roles/antwort', json={'cloud':True,'anbieter':identifier}).status_code == 422
    assert client.put('/api/v1/models/roles/antwort',
                      json={'cloud':True,'anbieter':identifier,'modell':'synthetic-model','einwilligung':True}).status_code == 200
    provider = rollen_von(app).provider('antwort')
    assert provider.name == identifier and not provider.is_local
    assert provider.model == 'synthetic-model'
    assert from_env() is None


def test_preparation_preserves_explicit_legacy_default_key(prepared, monkeypatch):
    from icarus_memory.providers import from_env
    _, client = prepared
    monkeypatch.setenv('ICARUS_PROVIDER','anthropic')
    monkeypatch.setenv('ANTHROPIC_API_KEY','synthetic-explicit-legacy')
    assert client.put('/api/v1/models/cloud-access/anthropic',
                      json={'api_key':'synthetic-prepared','model':'synthetic-model'}).status_code == 200
    assert from_env()._key == 'synthetic-explicit-legacy'
    assert client.delete('/api/v1/models/cloud-access/anthropic').status_code == 200
    assert from_env()._key == 'synthetic-explicit-legacy'
