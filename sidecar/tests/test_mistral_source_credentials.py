"""Mistral source preparation is encrypted, independent and completely offline."""
import json
import os
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from icarus_memory import config
from icarus_memory.cloud_import_provider import credential_status
from icarus_memory.secrets import PASSPHRASE_ENV
from icarus_memory.server import create_app

MODEL = 'mistral-small-2603'
SALT = 'CLOUD_IMPORT_MISTRAL_REVISION'


def test_mistral_source_status_requires_encrypted_active_key_and_source_salt():
    class Keys:
        available = True
        values = {'MISTRAL_API_KEY': 'synthetic-source-key', SALT: 'synthetic-source-salt'}
        def get(self, name):
            return self.values.get(name)
    class Settings:
        cloud_models = {'mistral': 'ordinary-chat-model'}
    keys = Keys()
    env = {'MISTRAL_API_KEY': 'synthetic-source-key'}
    first = credential_status(keys, Settings(), env, provider='mistral')
    assert first['available'] and first['model'] == MODEL
    assert 'synthetic-source-key' not in json.dumps(first)
    Settings.cloud_models['mistral'] = 'another-chat-model'
    assert credential_status(keys, Settings(), env, provider='mistral') == first
    Settings.cloud_models.clear()
    assert credential_status(keys, Settings(), env, provider='mistral') == first
    assert not credential_status(keys, Settings(), {'MISTRAL_API_KEY': 'override'}, provider='mistral')['available']
    keys.values.pop(SALT)
    assert not credential_status(keys, Settings(), env, provider='mistral')['available']
    keys.values.pop('MISTRAL_API_KEY')
    assert not credential_status(keys, Settings(), env, provider='mistral')['available']


def test_mistral_save_rotates_source_salt_only_for_key_changes_and_delete(monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-source-passphrase')
    # Block the actual HTTP boundary without interfering with TestClient.
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda *a, **kw: pytest.fail('No provider probes'))
    app = create_app()
    with TestClient(app) as client:
        roles = deepcopy(app.state.settings.model_roles)
        path = '/api/v1/models/cloud-access/mistral'
        assert client.put(path, json={'api_key': 'synthetic-first', 'model': 'chat-model'}).status_code == 200
        first = credential_status(app.state.keychain, app.state.settings, provider='mistral')
        salt = app.state.keychain.get(SALT)
        assert first['available'] and salt
        assert client.put(path, json={'model': 'other-chat-model'}).status_code == 200
        assert app.state.keychain.get(SALT) == salt
        assert credential_status(app.state.keychain, app.state.settings, provider='mistral') == first
        status = client.get('/api/v1/models/cloud-access').json()
        mistral = next(item for item in status['providers'] if item['id'] == 'mistral')
        assert mistral['model'] == 'other-chat-model' and mistral['import_model'] == MODEL and mistral['import_available']
        assert app.state.settings.model_roles == roles
        assert client.put(path, json={'api_key': 'synthetic-second', 'model': 'other-chat-model'}).status_code == 200
        assert app.state.keychain.get(SALT) != salt
        assert client.delete(path).status_code == 200
        assert app.state.keychain.get(SALT) is None
        assert not credential_status(app.state.keychain, app.state.settings, provider='mistral')['available']
        assert client.put(path, json={'api_key': 'synthetic-first', 'model': 'chat-model'}).status_code == 200
        assert credential_status(app.state.keychain, app.state.settings, provider='mistral') != first
        assert 'synthetic-first' not in app.state.keychain.secrets_path.read_text()


def test_mistral_failed_save_and_delete_restore_source_salt_and_active_key(monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-source-passphrase')
    app = create_app()
    with TestClient(app) as client:
        path = '/api/v1/models/cloud-access/mistral'
        assert client.put(path, json={'api_key': 'synthetic-first', 'model': 'chat-model'}).status_code == 200
        first = credential_status(app.state.keychain, app.state.settings, provider='mistral')
        salt = app.state.keychain.get(SALT)
        def fail(*args):
            raise OSError('synthetic config failure')
        monkeypatch.setattr(config, 'save', fail)
        assert client.put(path, json={'api_key': 'synthetic-second', 'model': 'new-chat'}).status_code == 409
        assert client.delete(path).status_code == 409
        assert app.state.keychain.get(SALT) == salt
        assert app.state.keychain.get('MISTRAL_API_KEY') == os.environ['MISTRAL_API_KEY'] == 'synthetic-first'
        assert credential_status(app.state.keychain, app.state.settings, provider='mistral') == first
