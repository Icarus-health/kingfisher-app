"""Rollenauflösung: Rückfall auf den Standard, Cloud nur mit Einwilligung je Rolle."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from icarus_memory.model_roles import (
    ROLLEN, Rollen, RollenWahl, einbettung_modell, einwilligung_gueltig, lese_wahlen,
    lokaler_endpunkt, ollama_wurzel, provider_fuer, rollen_von,
)
from icarus_memory.providers import Anthropic, OpenAICompatible
from tests.ollama_fake import FakeOllama

JETZT = datetime.now(timezone.utc).isoformat(timespec="seconds")
UMGEBUNG = {"ANTHROPIC_API_KEY": "k-anthropic", "OPENAI_API_KEY": "k-openai"}


def lokal(modell="standard-lokal"):
    return OpenAICompatible(modell, api_key="ollama", base_url="http://localhost:11434/v1")


def cloud_standard():
    return Anthropic("claude-standard", "k")


def test_ohne_konfiguration_ist_alles_der_standard():
    standard = lokal()
    for rolle in ROLLEN:
        assert provider_fuer(rolle, standard, {}) is standard
    assert provider_fuer("antwort", None, {}) is None
    with pytest.raises(KeyError):
        provider_fuer("nachrichten", standard, {})


def test_leere_wahl_und_kaputte_eintraege_fallen_zurueck():
    standard = lokal()
    wahlen = lese_wahlen({"antwort": {}, "frage": "kaputt", "unbekannt": {"modell": "x"},
                          "hintergrund": {"modell": 5, "cloud": "ja"}})
    assert wahlen == {}
    assert lese_wahlen(None) == {} and lese_wahlen([1]) == {}
    assert provider_fuer("antwort", standard, wahlen) is standard


def test_lokales_modell_je_rolle_behaelt_endpunkt_und_bleibt_lokal():
    standard = lokal()
    wahlen = {"hintergrund": RollenWahl(modell="gross:35b")}
    hintergrund = provider_fuer("hintergrund", standard, wahlen)
    assert hintergrund.model == "gross:35b" and hintergrund.is_local
    assert hintergrund.base_url == standard.base_url and standard.model == "standard-lokal"
    assert provider_fuer("antwort", standard, wahlen) is standard  # andere Rollen unberührt


def test_lokales_rollenmodell_auch_ohne_standard_und_bei_cloud_standard():
    for standard in (None, cloud_standard()):
        anbieter = provider_fuer("antwort", standard, {"antwort": RollenWahl(modell="klein:4b")},
                                 {"ICARUS_TRUSTED_LOCAL_MODEL_HOSTS": "host.docker.internal"})
        assert anbieter.model == "klein:4b" and anbieter.is_local
        assert anbieter.base_url == "http://host.docker.internal:11434/v1"


def test_cloud_ohne_einwilligung_wird_ignoriert():
    standard = lokal()
    ohne = RollenWahl(cloud=True, anbieter="anthropic")
    assert provider_fuer("antwort", standard, {"antwort": ohne}, UMGEBUNG) is standard
    kaputt = RollenWahl(cloud=True, anbieter="anthropic", cloud_einwilligung="gestern")
    assert provider_fuer("antwort", standard, {"antwort": kaputt}, UMGEBUNG) is standard
    ohne_anbieter = RollenWahl(cloud=True, cloud_einwilligung=JETZT)
    assert provider_fuer("antwort", standard, {"antwort": ohne_anbieter}, UMGEBUNG) is standard


def test_cloud_mit_einwilligung_je_rolle():
    standard = lokal()
    wahl = RollenWahl(modell="claude-x", cloud=True, anbieter="anthropic", cloud_einwilligung=JETZT)
    wahlen = {"antwort": wahl}
    cloud = provider_fuer("antwort", standard, wahlen, UMGEBUNG)
    assert isinstance(cloud, Anthropic) and cloud.model == "claude-x" and not cloud.is_local
    # Die Einwilligung gilt nur für diese Rolle.
    assert provider_fuer("frage", standard, wahlen, UMGEBUNG) is standard
    assert provider_fuer("hintergrund", standard, wahlen, UMGEBUNG) is standard
    # Ohne Schlüssel gilt der Standard, nie ein kaputter Cloudanbieter.
    assert provider_fuer("antwort", standard, wahlen, {}) is standard


def test_openai_cloudrolle_nutzt_eigenes_standardmodell():
    wahl = RollenWahl(cloud=True, anbieter="openai", cloud_einwilligung=JETZT)
    anbieter = provider_fuer("frage", None, {"frage": wahl}, UMGEBUNG)
    assert isinstance(anbieter, OpenAICompatible) and not anbieter.is_local and anbieter.model


@pytest.mark.parametrize("rolle", ["hintergrund", "einbettung"])
def test_hintergrund_und_einbettung_bleiben_lokal_auch_mit_handeintrag(rolle):
    standard = lokal()
    wahl = RollenWahl(modell="gross:35b", cloud=True, anbieter="anthropic", cloud_einwilligung=JETZT)
    assert not einwilligung_gueltig(rolle, wahl)
    anbieter = provider_fuer(rolle, standard, {rolle: wahl}, UMGEBUNG)
    assert anbieter is standard and anbieter.is_local
    # Ein Cloudstandard wird für diese Rollen nie ausgegeben: lieber kein Modell als Rohquellen in der Cloud.
    assert provider_fuer(rolle, cloud_standard(), {rolle: wahl}, UMGEBUNG) is None
    assert provider_fuer(rolle, cloud_standard(), {}, UMGEBUNG) is None


def test_einbettungsmodell_und_endpunkt():
    assert einbettung_modell({}) == "bge-m3:latest"
    assert einbettung_modell({"einbettung": RollenWahl(modell="anderes-emb")}) == "anderes-emb"
    assert ollama_wurzel("http://h:11434/v1/") == "http://h:11434"
    assert lokaler_endpunkt(lokal(), {}) == "http://localhost:11434/v1"
    assert lokaler_endpunkt(None, {}) == "http://localhost:11434/v1"


def test_rollen_cache_liefert_stabile_objekte_und_erneuert_bei_neuem_standard():
    aktuell = {"p": lokal()}
    rollen = Rollen({"hintergrund": RollenWahl(modell="gross:35b")}, lambda: aktuell["p"])
    erster = rollen.provider("hintergrund")
    assert rollen.provider("hintergrund") is erster  # Identitätsvergleich der Hintergrundläufe trägt
    aktuell["p"] = lokal("anderer-standard")
    assert rollen.provider("hintergrund") is not erster


def test_leere_rollen_geben_den_lebenden_agentenanbieter():
    zustand = SimpleNamespace(settings=SimpleNamespace(model_roles={}), agent=SimpleNamespace(provider=lokal("a")),
                              ollama_transport=FakeOllama(installiert=["a", "b", "std", "gross:35b"]).transport)
    app = SimpleNamespace(state=zustand)
    assert rollen_von(app).provider("hintergrund") is zustand.agent.provider
    zustand.agent.provider = lokal("b")  # Tests und Wechsel ersetzen den Anbieter zur Laufzeit
    assert rollen_von(app).provider("hintergrund") is zustand.agent.provider
    zustand.settings.model_roles = {"hintergrund": {"modell": "gross:35b"}}
    zustand.standard_provider = lokal("std")
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"
