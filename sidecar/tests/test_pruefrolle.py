"""Rolle `pruefung` (zweites Tor der Satzprüfung): nur mit Zuweisung, nur lokal, nie Cloud, nie der Standard."""
from datetime import datetime, timezone

import httpx

from icarus_memory.model_roles import ROLLEN, Rollen, anbieter_fuer_pruefung, lese_wahlen, provider_fuer
from icarus_memory.ollama_inventar import OllamaInventar
from icarus_memory.providers import Anthropic, OpenAICompatible
from tests.ollama_fake import FakeOllama

JETZT = datetime.now(timezone.utc).isoformat(timespec="seconds")


def lokal(modell="standard-lokal"):
    return OpenAICompatible(modell, api_key="ollama", base_url="http://localhost:11434/v1")


def rollen(roh, standard=None, inventar=None):
    return Rollen(lese_wahlen(roh), lambda: standard, umgebung={}, inventar=inventar)


def test_die_rolle_ist_immer_lokal():
    assert ROLLEN["pruefung"].cloud_moeglich is False


def test_ohne_zuweisung_gibt_es_kein_pruefmodell_auch_nicht_den_standard():
    assert anbieter_fuer_pruefung(rollen({}, lokal())) is None
    assert anbieter_fuer_pruefung(rollen({"antwort": {"modell": "gross"}}, lokal())) is None


def test_mit_zuweisung_ein_lokaler_anbieter_mit_dem_gewaehlten_modell():
    anbieter = anbieter_fuer_pruefung(rollen({"pruefung": {"modell": "bespoke-minicheck:7b"}}, lokal()))
    assert anbieter is not None and anbieter.is_local and anbieter.model == "bespoke-minicheck:7b"


def test_eine_cloudwahl_wird_nie_zum_pruefmodell():
    roh = {"pruefung": {"cloud": True, "anbieter": "anthropic", "cloud_einwilligung": JETZT}}
    assert anbieter_fuer_pruefung(rollen(roh, lokal())) is None
    # Auch ein Standard in der Cloud gibt der Rolle nichts heraus.
    assert provider_fuer("pruefung", Anthropic("claude-x", "k"), {}) is None


def test_ein_cloud_ueber_ollama_modell_ist_kein_pruefmodell():
    fake = FakeOllama(installiert=["bespoke-minicheck:7b"], cloud=["pruef-modell:cloud"])
    inventar = OllamaInventar(lambda: "http://localhost:11434", lambda: httpx.Client(transport=fake.transport))
    assert anbieter_fuer_pruefung(rollen({"pruefung": {"modell": "pruef-modell:cloud"}}, lokal(), inventar)) is None
    # Gegenprobe: dasselbe Inventar lässt das belegt lokale Modell durch.
    assert anbieter_fuer_pruefung(rollen({"pruefung": {"modell": "bespoke-minicheck:7b"}}, lokal(), inventar)) is not None
