"""Hintergrundarbeit läuft nie über die Cloud, auch wenn das Gespräch (Rolle `antwort`) dort läuft.

Verdichtung, Zusammenfassung, Einordnung und Personenüberblick lesen alle Quellen. Sie
bekommen den Anbieter der Rolle `hintergrund` (`model_roles`), und der ist lokal oder `None`.
Alles nur mit synthetischen Daten und einem Spion statt eines Netzzugriffs.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory.backends import MemoryBackend
from icarus_memory.model_roles import hintergrund_anbieter, provider_fuer, rollen_von
from icarus_memory.person_digests import choose_provider
from icarus_memory.providers import Anthropic, OpenAICompatible, Reply
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from tests.ollama_fake import FakeOllama

JETZT = datetime.now(timezone.utc).isoformat(timespec="seconds")


class CloudSpion:
    """Ein Anbieter, der nicht lokal ist und jeden Aufruf mitschreibt."""

    name = "cloud"
    model = "cloud-modell"
    is_local = False

    def __init__(self):
        self.aufrufe = []

    def complete(self, messages, tools):  # noqa: ANN001
        self.aufrufe.append(messages)
        return Reply(text='{"vorschlaege": []}', model=self.model)

    def complete_json(self, messages, **_):  # noqa: ANN003
        self.aufrufe.append(messages)
        return Reply(text="{}", model=self.model)


class Agent:
    def __init__(self, provider):
        self.provider = provider

    def reset(self):
        pass


def lokal(modell="lokal-1"):
    return OpenAICompatible(modell, api_key="ollama", base_url="http://localhost:11434/v1")


@pytest.fixture
def cloud_app(tmp_path):
    spion = CloudSpion()
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"), agent=Agent(spion))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield app, client, spion
    for name in ("audit", "tasks", "workspace", "episodes", "proposals", "conversations", "claims", "regeln"):
        speicher = getattr(app.state, name, None)
        if callable(getattr(speicher, "close", None)):
            speicher.close()


def test_cloudstandard_bekommt_keine_hintergrundrolle_aber_das_gespraech_behaelt_ihn():
    cloud = Anthropic("claude-x", "k")
    assert provider_fuer("hintergrund", cloud, {}) is None
    assert provider_fuer("einbettung", cloud, {}) is None
    assert provider_fuer("antwort", cloud, {}) is cloud
    assert provider_fuer("frage", cloud, {}) is cloud


def test_verdichtung_und_zusammenfassung_fragen_keine_cloud(cloud_app):
    app, client, spion = cloud_app
    assert app.state.consolidator._provider is None and app.state.summarizer._provider is None
    client.post("/episodes", json={"title": "Notiz", "body": "Vertraulicher synthetischer Inhalt."})
    antwort = client.post("/consolidate", json={"with_model": True}).json()
    assert antwort["used_model"] is False
    client.post("/summaries/run", json={"with_model": True})
    assert spion.aufrufe == []


def test_hintergrund_anbieter_ist_der_der_rolle_nicht_der_des_gespraechs(cloud_app):
    app, _client, spion = cloud_app
    assert app.state.agent.provider is spion
    assert hintergrund_anbieter(app) is None


def test_personenueberblick_nimmt_das_lokale_modell_auch_wenn_das_gespraech_in_der_cloud_laeuft():
    standard = lokal("standard-lokal")
    cloud = CloudSpion()
    zustand = SimpleNamespace(
        settings=SimpleNamespace(routing_profiles=[], model_roles={
            "antwort": {"modell": "claude-x", "cloud": True, "anbieter": "anthropic", "cloud_einwilligung": JETZT}}),
        standard_provider=standard, agent=SimpleNamespace(provider=cloud),
        ollama_transport=FakeOllama(installiert=["standard-lokal"]).transport)  # das lokale Modell ist belegt lokal
    app = SimpleNamespace(state=zustand)
    assert choose_provider(app) is standard
    assert choose_provider(app) is not zustand.agent.provider


def test_personenueberblick_ohne_lokales_modell_bekommt_keinen_anbieter():
    zustand = SimpleNamespace(settings=SimpleNamespace(routing_profiles=[], model_roles={}),
                              agent=SimpleNamespace(provider=CloudSpion()))
    assert choose_provider(SimpleNamespace(state=zustand)) is None


def test_hintergrundstatus_folgt_der_rolle_nicht_dem_gespraech():
    standard = lokal("standard-lokal")
    zustand = SimpleNamespace(settings=SimpleNamespace(model_roles={
        "antwort": {"modell": "claude-x", "cloud": True, "anbieter": "anthropic", "cloud_einwilligung": JETZT}}),
        standard_provider=standard, agent=SimpleNamespace(provider=CloudSpion()),
        ollama_transport=FakeOllama(installiert=["standard-lokal"]).transport)
    assert rollen_von(SimpleNamespace(state=zustand)).provider("hintergrund") is standard
