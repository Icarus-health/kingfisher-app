"""The local connection must change the active answer, not just its displayed role."""
import pytest
from fastapi.testclient import TestClient

from icarus_memory import config
from icarus_memory import ollama_inventar
from icarus_memory.server import create_app
from tests.ollama_fake import FakeOllama, Verbindungsfehler


@pytest.fixture
def connection(monkeypatch):
    monkeypatch.setenv('ICARUS_PROVIDER', 'ollama')
    monkeypatch.setenv('ICARUS_BASE_URL', 'http://127.0.0.1:11434/v1')
    monkeypatch.setenv('ICARUS_MODEL', 'qwen3.5:4b')
    fake = FakeOllama(installiert=['qwen3.5:4b', 'qwen3.5:9b'])
    original = ollama_inventar.inventar_von
    def fake_inventory(app):
        # _build_agent reads the inventory during create_app, before fixture injection.
        if not hasattr(app.state, 'ollama_transport'):
            app.state.ollama_transport = fake.transport
        return original(app)
    monkeypatch.setattr(ollama_inventar, 'inventar_von', fake_inventory)
    app = create_app()
    # Subsequent tests may intentionally substitute an unreachable or cloud inventory.
    monkeypatch.setattr(ollama_inventar, 'inventar_von', original)
    app.state.ollama_inventar.vergiss()
    with TestClient(app) as client:
        yield app, client


def test_local_answer_choice_rebuilds_the_actual_agent_with_verified_inventory(connection):
    app, client = connection
    app.state.settings.model_roles = {
        'antwort': {'modell': 'missing:12b', 'local_only': True},
        'hintergrund': {'modell': 'qwen3.5:4b', 'cloud': False},
    }
    response = client.put('/api/v1/models/roles/antwort', json={'modell': 'qwen3.5:9b', 'cloud': False})
    assert response.status_code == 200, response.text
    answer = next(row for row in response.json()['rollen'] if row['rolle'] == 'antwort')
    assert answer['wirksam']['modell'] == 'qwen3.5:9b' and answer['wirksam']['lokal'] is True
    # The old code displayed the correct role while building an agent with no provider.
    setup = client.get('/api/v1/setup').json()
    assert setup['status']['model'] == 'qwen3.5:9b'
    assert app.state.agent.provider is not None and app.state.agent.provider.model == 'qwen3.5:9b'
    saved = config.load(config.Path(__import__('os').environ['ICARUS_DATA_DIR']))
    assert saved.model_roles['antwort']['local_only'] is True
    assert saved.model_roles['hintergrund'] == {'modell': 'qwen3.5:4b', 'cloud': False}


def test_explicit_local_answer_choice_never_falls_back_to_unverified_standard(connection):
    app, client = connection
    app.state.ollama_transport = Verbindungsfehler().transport
    app.state.ollama_inventar.vergiss()
    response = client.put('/api/v1/models/roles/antwort', json={
        'modell': 'qwen3.5:9b', 'cloud': False, 'local_only': True})
    assert response.status_code == 200, response.text
    assert app.state.agent.provider is None
    assert client.get('/api/v1/setup').json()['status']['chat'] is False
    assert app.state.settings.model_roles['antwort']['local_only'] is True


def test_local_answer_rejects_ollama_cloud_without_mutating_existing_choice(connection):
    app, client = connection
    app.state.ollama_transport = FakeOllama(installiert=['qwen3.5:4b'], cloud=['qwen:cloud']).transport
    app.state.ollama_inventar.vergiss()
    before = dict(app.state.settings.model_roles)
    response = client.put('/api/v1/models/roles/antwort', json={
        'modell': 'qwen:cloud', 'cloud': False, 'local_only': True})
    assert response.status_code == 422
    assert app.state.settings.model_roles == before


def test_local_only_and_cloud_cannot_be_enabled_together(connection, monkeypatch):
    app, client = connection
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'synthetic-not-a-real-key')
    before = dict(app.state.settings.model_roles)
    response = client.put('/api/v1/models/roles/antwort', json={
        'cloud': True, 'anbieter': 'anthropic', 'einwilligung': True, 'local_only': True})
    assert response.status_code == 422
    assert app.state.settings.model_roles == before
