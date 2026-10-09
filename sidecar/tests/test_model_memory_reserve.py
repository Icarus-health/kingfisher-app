"""The device guidance must also bound setup and parallel-model planning."""
import pytest
from dataclasses import asdict

from icarus_memory.device_profile import save_device_profile
from icarus_memory.hintergrund import speicher_reicht
from icarus_memory.model_recommendation import (
    Geraet, empfehle_alle, geraet_aus_profil, orchester_bedarf,
)
from tests.test_model_roles_routes import app_und_client, bereit, geraet  # noqa: F401


@pytest.mark.parametrize('gb', [8, 16, 24, 31.9, 32, 64, 128])
def test_shared_host_budget_matches_device_guidance(tmp_path, gb):
    profile = save_device_profile(tmp_path, {'platform': 'macos', 'chip': 'Test',
                                            'memory_bytes': round(gb * 1024**3)})
    g = geraet_aus_profil(profile)
    need = orchester_bedarf(empfehle_alle(g), g)
    assert need['nutzbar_gb'] == profile['guidance']['model_budget_gb']
    assert need['nutzbar_gb'] + profile['guidance']['headroom_gb'] == pytest.approx(profile['memory_gb'])


def test_32gb_mac_default_leaves_the_advertised_os_reserve():
    g = Geraet('macos', 'Test', 32)
    need = orchester_bedarf(empfehle_alle(g), g)
    assert need['tag_gb'] <= 19.2
    assert need['nacht_gb'] <= 19.2
    assert need['passt_tag'] is True and need['passt_nacht'] is True


def test_dedicated_gpu_budget_remains_separate_from_host_reserve():
    g = Geraet('linux', None, 64, 24)
    assert orchester_bedarf({}, g)['nutzbar_gb'] == pytest.approx(24 * .85)


def test_parallel_models_cannot_use_the_os_reserve():
    assert not speicher_reicht(32, ['qwen3.5:9b', 'gemma4:12b'])  # 20 GB > 19.2
    assert speicher_reicht(64, ['qwen3.5:9b', 'gemma4:12b'])


def test_manual_setup_rejects_model_that_uses_the_os_reserve(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    fake = bereit(app)
    before = dict(app.state.settings.model_roles)
    response = client.post('/api/v1/models/pull', json={'rolle':'antwort', 'modell':'qwen3.6:35b', 'bestaetigt':True})
    assert response.status_code == 422
    assert not any(path == '/api/pull' for _, path, _ in fake.anfragen)
    assert app.state.settings.model_roles == before


def test_small_host_is_not_promised_a_full_local_setup(app_und_client):
    app, client = app_und_client
    geraet(client, 8)
    fake = bereit(app)
    response = client.post('/api/v1/models/laden', json={'bestaetigt':True})
    assert response.status_code == 422
    assert not any(path == '/api/pull' for _, path, _ in fake.anfragen)


def test_32gb_plan_reuses_question_model_before_shrinking_answer_and_validator():
    g=Geraet('macos','Synthetic',32)
    recommended=empfehle_alle(g)
    assert recommended['antwort'].modell.name == 'qwen3.5:9b'
    assert recommended['frage'].modell.name == 'qwen3.5:9b'
    assert recommended['pruefung'].modell.name == 'bespoke-minicheck:7b'
    need=orchester_bedarf(recommended,g)
    assert need['tag_gb'] == 18 and need['passt_tag'] is True


@pytest.mark.parametrize("role", ["antwort", "frage", "pruefung"])
def test_expert_role_selection_cannot_bypass_host_reserve(app_und_client,role):
    app,client=app_und_client
    geraet(client,32)
    fake=bereit(app)
    before=dict(app.state.settings.model_roles)
    response=client.put(f'/api/v1/models/roles/{role}',json={'modell':'qwen3.6:35b'})
    assert response.status_code==422
    assert app.state.settings.model_roles==before
    assert not any(path in ('/api/pull','/api/chat') for _,path,_ in fake.anfragen)


@pytest.mark.parametrize('path',['/api/v1/setup','/setup'])
def test_standard_model_setup_rejects_oversize_before_any_setting_is_changed(app_und_client,path,monkeypatch):
    app,client=app_und_client
    geraet(client,32)
    bereit(app)
    monkeypatch.delenv('ICARUS_MODEL')
    before=asdict(app.state.settings)
    response=client.put(path,json={'provider':'ollama','model':'qwen3.6:35b','onboarded':True})
    assert response.status_code==422
    assert asdict(app.state.settings)==before


def test_external_local_provider_override_cannot_bypass_reserve(app_und_client, monkeypatch):
    app, client = app_und_client
    geraet(client, 32)
    app.state.settings.provider = 'openai'
    monkeypatch.delenv('ICARUS_MODEL')
    before = asdict(app.state.settings)
    response = client.put('/api/v1/setup', json={'model': 'qwen3.6:35b'})
    assert response.status_code == 422
    assert asdict(app.state.settings) == before


def test_external_model_override_cannot_bypass_reserve(app_und_client, monkeypatch):
    app, client = app_und_client
    geraet(client, 32)
    monkeypatch.setenv('ICARUS_MODEL', 'qwen3.6:35b')
    before = asdict(app.state.settings)
    response = client.put('/api/v1/setup', json={'provider': 'openai', 'model': 'gpt-4.1-mini'})
    assert response.status_code == 422
    assert asdict(app.state.settings) == before


def test_replaced_settings_environment_does_not_retain_old_model(app_und_client, monkeypatch):
    app, client = app_und_client
    geraet(client, 32)
    monkeypatch.setenv('ICARUS_MODEL', 'qwen3.6:35b')
    app.state.env_from_settings = ['ICARUS_MODEL']
    response = client.put('/api/v1/setup', json={'provider': 'ollama', 'model': 'qwen3.5:9b'})
    assert response.status_code == 200
    assert app.state.agent.provider.model == 'qwen3.5:9b'


def test_loopback_compatible_model_also_respects_host_reserve(app_und_client, monkeypatch):
    app, client = app_und_client
    geraet(client, 32)
    monkeypatch.delenv('ICARUS_MODEL')
    app.state.env_from_settings = ['ICARUS_PROVIDER', 'ICARUS_BASE_URL']
    before = asdict(app.state.settings)
    response = client.put('/api/v1/setup', json={'provider': 'kompatibel', 'endpoint': 'http://127.0.0.1:1234/v1', 'model': 'qwen3.6:35b'})
    assert response.status_code == 422
    assert asdict(app.state.settings) == before


@pytest.mark.parametrize('endpoint, expected', [
    ('http://127.0.0.1:1234/v1', 422),
    ('https://synthetic-provider.example/v1', 200),
])
def test_endpoint_only_change_checks_local_model_without_limiting_cloud(app_und_client, monkeypatch, endpoint, expected):
    app, client = app_und_client
    geraet(client, 32)
    monkeypatch.setenv('ICARUS_MODEL', 'qwen3.6:35b')
    monkeypatch.setenv('ICARUS_PROVIDER', 'kompatibel')
    app.state.env_from_settings = ['ICARUS_BASE_URL']
    before = asdict(app.state.settings)
    response = client.put('/api/v1/setup', json={'endpoint': endpoint})
    assert response.status_code == expected
    if expected == 422:
        assert asdict(app.state.settings) == before
    else:
        assert app.state.agent.provider.base_url == endpoint
