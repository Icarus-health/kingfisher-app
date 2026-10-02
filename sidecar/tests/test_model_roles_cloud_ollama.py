"""Cloud über Ollama: ein Modell mit `remote_host` ist Cloud, auch wenn der Endpunkt Loopback ist."""
from datetime import datetime, timezone

import httpx
import pytest

from icarus_memory.model_roles import (
    OLLAMA_CLOUD, ROLLEN, STANDARD_EINBETTUNG, Rollen, RollenWahl, anbieter_fuer_frage, provider_fuer,
)
from icarus_memory.ollama_inventar import OllamaInventar
from icarus_memory.providers import Anthropic, OpenAICompatible
from tests.ollama_fake import FakeOllama, Verbindungsfehler

JETZT = datetime.now(timezone.utc).isoformat(timespec="seconds")
CLOUD_MODELL = "deepseek-v4.1-flash:cloud"
LOKALES = "klein:4b"


def lokal(modell=LOKALES):
    return OpenAICompatible(modell, api_key="ollama", base_url="http://localhost:11434/v1")


def inventar(transport=None, fake=None):
    fake = fake or FakeOllama(installiert=[LOKALES, "bge-m3", "gross:35b", "std:9b"], cloud=[CLOUD_MODELL])
    return OllamaInventar(lambda: "http://localhost:11434",
                          lambda: httpx.Client(transport=transport or fake.transport)), fake


def einwilligung(modell=CLOUD_MODELL):
    return RollenWahl(modell=modell, cloud=True, anbieter=OLLAMA_CLOUD, cloud_einwilligung=JETZT)


def test_das_cloudmodell_ist_ein_cloudanbieter_nur_mit_einwilligung_fuer_frage_und_antwort():
    inv, _ = inventar()
    for rolle in ("frage", "antwort"):
        anbieter = provider_fuer(rolle, lokal(), {rolle: einwilligung()}, {}, inv)
        assert anbieter.model == CLOUD_MODELL and anbieter.is_local is False and anbieter.ueber_ollama_cloud
        assert anbieter.base_url == "http://localhost:11434/v1"  # der Weg führt über das lokale Ollama


@pytest.mark.parametrize("rolle", ["hintergrund", "einbettung"])
def test_hintergrund_und_einbettung_bekommen_das_cloudmodell_nie(rolle):
    inv, _ = inventar()
    ohne = RollenWahl(modell=CLOUD_MODELL)  # als „lokal“ gewählt
    assert provider_fuer(rolle, lokal(), {rolle: ohne}, {}, inv) is None
    # auch mit Einwilligung, auch per Handeintrag: für diese Rollen gibt es keine Cloud.
    mit = provider_fuer(rolle, lokal(), {rolle: einwilligung()}, {}, inv)
    assert mit is None or (mit.model != CLOUD_MODELL and mit.is_local)


@pytest.mark.parametrize("rolle", ["frage", "antwort"])
def test_ohne_einwilligung_kein_cloudmodell_und_nie_stillschweigend_dasselbe_modell(rolle):
    inv, _ = inventar()
    ohne = RollenWahl(modell=CLOUD_MODELL)
    standard = lokal()
    anbieter = provider_fuer(rolle, standard, {rolle: ohne}, {}, inv)
    assert anbieter is standard  # Rückfall auf das belegt lokale Standardmodell
    unbestaetigt = RollenWahl(modell=CLOUD_MODELL, cloud=True, anbieter=OLLAMA_CLOUD)
    assert provider_fuer(rolle, standard, {rolle: unbestaetigt}, {}, inv) is standard
    kaputt = RollenWahl(modell=CLOUD_MODELL, cloud=True, anbieter=OLLAMA_CLOUD, cloud_einwilligung="gestern")
    assert provider_fuer(rolle, standard, {rolle: kaputt}, {}, inv) is standard
    # Ist auch der Standard ein Cloudmodell, bleibt nichts: lieber kein Modell.
    assert provider_fuer(rolle, lokal(CLOUD_MODELL), {rolle: ohne}, {}, inv) is None


def test_die_einwilligung_einer_rolle_gilt_nicht_fuer_die_andere():
    inv, _ = inventar()
    wahlen = {"antwort": einwilligung()}
    assert provider_fuer("antwort", lokal(), wahlen, {}, inv).model == CLOUD_MODELL
    assert provider_fuer("frage", lokal(), wahlen, {}, inv).model == LOKALES
    assert provider_fuer("hintergrund", lokal(), wahlen, {}, inv).model == LOKALES


@pytest.mark.parametrize("rolle", sorted(ROLLEN))
def test_alle_rollen_ein_lokales_modell_bleibt_lokal(rolle):
    inv, _ = inventar()
    anbieter = provider_fuer(rolle, lokal(), {rolle: RollenWahl(modell="gross:35b")}, {}, inv)
    assert anbieter.model == "gross:35b" and anbieter.is_local and not getattr(anbieter, "ueber_ollama_cloud", False)


def test_ein_cloudmodell_als_standard_geht_nie_an_hintergrund_und_nie_ohne_einwilligung_an_die_antwort():
    inv, _ = inventar()
    cloud_standard = lokal(CLOUD_MODELL)
    for rolle in ("hintergrund", "einbettung"):
        assert provider_fuer(rolle, cloud_standard, {}, {}, inv) is (cloud_standard if rolle == "einbettung" else None)
    assert provider_fuer("antwort", cloud_standard, {}, {}, inv) is None
    assert provider_fuer("frage", cloud_standard, {}, {}, inv) is None


def test_ist_das_modell_doch_lokal_gilt_die_einwilligung_nicht_als_cloud():
    inv, _ = inventar()
    anbieter = provider_fuer("antwort", lokal(), {"antwort": einwilligung("gross:35b")}, {}, inv)
    assert anbieter.is_local and not getattr(anbieter, "ueber_ollama_cloud", False)


@pytest.mark.parametrize("rolle", sorted(ROLLEN))
def test_ollama_stumm_ist_nicht_lokal(rolle):
    """Fail closed: Wer nicht belegen kann, dass ein gewähltes Modell lokal ist, bekommt es für Rohquellen nicht."""
    inv, _ = inventar(transport=Verbindungsfehler().transport)
    anbieter = provider_fuer(rolle, lokal(), {rolle: RollenWahl(modell="gross:35b")}, {}, inv)
    if ROLLEN[rolle].cloud_moeglich:
        assert anbieter is not None and anbieter.model != "gross:35b"  # Rückfall auf den Standard, nie das ungeprüfte Modell
    else:
        assert anbieter is None
    if rolle == "hintergrund":
        assert provider_fuer(rolle, lokal(), {}, {}, inv) is None


def test_ohne_inventar_prueft_provider_fuer_nur_den_endpunkt_wie_bisher():
    assert provider_fuer("hintergrund", lokal(), {"hintergrund": RollenWahl(modell=CLOUD_MODELL)}, {}).model == CLOUD_MODELL


def test_cloudstandard_bleibt_fuer_hintergrund_ausgeschlossen():
    inv, _ = inventar()
    assert provider_fuer("hintergrund", Anthropic("claude-x", "k"), {}, {}, inv) is None


def test_frage_nimmt_das_cloudmodell_nur_mit_einwilligung():
    inv, _ = inventar()
    rollen = Rollen({"frage": einwilligung()}, lambda: lokal(), inventar=inv)
    assert anbieter_fuer_frage(rollen).model == CLOUD_MODELL
    rollen = Rollen({"frage": RollenWahl(modell=CLOUD_MODELL)}, lambda: lokal(), inventar=inv)
    assert anbieter_fuer_frage(rollen).model == LOKALES


def test_einbettung_nimmt_das_cloudmodell_nie():
    inv, _ = inventar()
    rollen = Rollen({"einbettung": RollenWahl(modell=CLOUD_MODELL)}, lambda: lokal(), inventar=inv)
    assert rollen.provider("einbettung") is None and rollen.einbettung_modell() == STANDARD_EINBETTUNG
    gut = Rollen({"einbettung": RollenWahl(modell="gross:35b")}, lambda: lokal(), inventar=inv)
    assert gut.einbettung_modell() == "gross:35b" and gut.provider("einbettung").is_local


def test_cloud_modell_im_weg_benennt_das_modell_nur_wenn_es_blockiert():
    inv, _ = inventar()
    rollen = Rollen({"hintergrund": RollenWahl(modell=CLOUD_MODELL), "antwort": einwilligung()}, lambda: lokal(), inventar=inv)
    assert rollen.cloud_modell_im_weg("hintergrund") == CLOUD_MODELL
    assert rollen.cloud_modell_im_weg("antwort") is None  # gewollt, mit Einwilligung
    assert rollen.cloud_modell_im_weg("frage") is None
    assert Rollen({}, lambda: lokal(), inventar=inv).cloud_modell_im_weg("hintergrund") is None


def test_stabiles_objekt_solange_sich_die_art_nicht_aendert_und_neu_bei_aenderung():
    fake = FakeOllama(installiert=["gross:35b"])
    inv, _ = inventar(fake=fake)
    standard = lokal()
    rollen = Rollen({"hintergrund": RollenWahl(modell="gross:35b")}, lambda: standard, inventar=inv)
    erster = rollen.provider("hintergrund")
    inv.vergiss()
    assert rollen.provider("hintergrund") is erster  # Läufe im Hintergrund erkennen ihren Anbieter wieder
    fake.installiert.remove("gross:35b")
    fake.cloud.append("gross:35b")  # dasselbe Tag ist jetzt ein Cloudmodell
    inv.vergiss()
    assert rollen.provider("hintergrund") is None
