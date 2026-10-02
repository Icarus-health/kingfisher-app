"""Inventar des lokalen Ollama: lokal oder Cloud über Ollama, kurz gemerkt, fail closed."""
import httpx
import pytest

from icarus_memory.ollama_inventar import CLOUD, LOKAL, UNBEKANNT, OllamaInventar, ist_cloud_name
from tests.ollama_fake import FakeOllama, Verbindungsfehler

WURZEL = "http://localhost:11434"


class Uhr:
    def __init__(self):
        self.jetzt = 1000.0

    def __call__(self):
        return self.jetzt


def inventar(transport, uhr=None):
    return OllamaInventar(lambda: WURZEL, lambda: httpx.Client(transport=transport), uhr=uhr or Uhr())


def test_lokal_ist_gguf_mit_digest_und_cloud_ist_alles_andere():
    fake = FakeOllama(installiert=["klein:4b"], cloud=["deepseek-v4.1-flash:cloud"])
    inv = inventar(fake.transport)
    assert inv.art("klein:4b") == LOKAL and inv.ist_lokal("klein:4b")
    assert inv.art("deepseek-v4.1-flash:cloud") == CLOUD


def test_installiert_nennt_die_namen_wie_ollama_sie_nennt():
    fake = FakeOllama(installiert=["klein:4b", "bge-m3"], cloud=["x:cloud"])
    assert inventar(fake.transport).installiert() == {"klein:4b": LOKAL, "bge-m3:latest": LOKAL, "x:cloud": CLOUD}
    assert inventar(fake.transport).art("bge-m3") == LOKAL  # `bge-m3` und `bge-m3:latest` sind dasselbe Modell


def test_remote_host_allein_genuegt_auch_ohne_cloud_im_namen():
    def antwort(request):
        return httpx.Response(200, json={"models": [
            {"name": "getarnt:7b", "digest": "0" * 64, "details": {"format": "gguf"}, "remote_host": "https://ollama.com:443"},
            {"name": "getarnt2:7b", "digest": "0" * 64, "details": {"format": "gguf"}, "remote_model": "x"},
            {"name": "ohnegguf:7b", "digest": "0" * 64, "details": {"format": ""}},
            {"name": "ohnedigest:7b", "digest": "", "details": {"format": "gguf"}}]})
    inv = inventar(httpx.MockTransport(antwort))
    assert {inv.art(n) for n in ("getarnt:7b", "getarnt2:7b", "ohnegguf:7b", "ohnedigest:7b")} == {CLOUD}


@pytest.mark.parametrize("name", ["deepseek-v4.1-flash:cloud", "gpt-oss:120b-cloud", "Nutzer/x:CLOUD"])
def test_cloud_im_tag_verraet_das_modell(name):
    assert ist_cloud_name(name)


@pytest.mark.parametrize("name", ["qwen3.5:4b", "cloudy:7b", "bge-m3", "nutzer/cloud:latest"])
def test_gewoehnliche_namen_sind_nicht_verdaechtig(name):
    assert not ist_cloud_name(name)


def test_show_nur_wenn_die_zeile_keine_einzelheiten_hat():
    anfragen = []

    def antwort(request):
        anfragen.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": "voll:4b", "digest": "0" * 64, "details": {"format": "gguf"}},
                {"name": "knapp:4b", "digest": "0" * 64},
                {"name": "knapp-fern:4b", "digest": "0" * 64}]})
        assert request.url.path == "/api/show"
        return httpx.Response(200, json={"details": {"format": "gguf"}} if b"knapp:4b" in request.content
                              else {"remote_host": "https://ollama.com:443"})
    inv = inventar(httpx.MockTransport(antwort))
    assert inv.installiert() == {"voll:4b": LOKAL, "knapp:4b": LOKAL, "knapp-fern:4b": CLOUD}
    assert anfragen.count("/api/show") == 2  # nicht für `voll`


def test_show_fehler_heisst_nicht_belegt_lokal():
    def antwort(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "knapp:4b", "digest": "0" * 64}]})
        return httpx.Response(500)
    assert inventar(httpx.MockTransport(antwort)).art("knapp:4b") == CLOUD


@pytest.mark.parametrize("transport", [
    Verbindungsfehler().transport,
    httpx.MockTransport(lambda r: httpx.Response(500)),
    httpx.MockTransport(lambda r: httpx.Response(200, content=b"kein json")),
    httpx.MockTransport(lambda r: httpx.Response(200, json={"models": "kaputt"})),
    httpx.MockTransport(lambda r: httpx.Response(200, json=[1])),
])
def test_fehler_ist_unbekannt_und_unbekannt_ist_nicht_lokal(transport):
    inv = inventar(transport)
    assert inv.installiert() is None
    assert inv.art("klein:4b") == UNBEKANNT and not inv.ist_lokal("klein:4b")


def test_nicht_installiertes_modell_ist_unbekannt():
    assert inventar(FakeOllama(installiert=["klein:4b"]).transport).art("anderes:4b") == UNBEKANNT


def test_antwort_wird_30_sekunden_gemerkt_dann_neu_gelesen():
    fake, uhr = FakeOllama(installiert=["klein:4b"]), Uhr()
    inv = inventar(fake.transport, uhr)
    assert inv.art("klein:4b") == LOKAL and inv.art("klein:4b") == LOKAL
    assert len(fake.anfragen) == 1
    fake.installiert.append("neu:4b")
    uhr.jetzt += 29
    assert inv.art("neu:4b") == UNBEKANNT and len(fake.anfragen) == 1
    uhr.jetzt += 2
    assert inv.art("neu:4b") == LOKAL and len(fake.anfragen) == 2


def test_ein_ausfall_wird_nur_kurz_gemerkt_und_erholt_sich():
    fake, uhr = FakeOllama(installiert=["klein:4b"]), Uhr()
    ausfall = {"an": True}

    def antwort(request):
        if ausfall["an"]:
            raise httpx.ConnectError("aus", request=request)
        return fake._handle(request)
    inv = inventar(httpx.MockTransport(antwort), uhr)
    assert inv.art("klein:4b") == UNBEKANNT
    ausfall["an"] = False
    assert inv.art("klein:4b") == UNBEKANNT  # noch gemerkt, kein Trommelfeuer auf ein totes Ollama
    uhr.jetzt += 6
    assert inv.art("klein:4b") == LOKAL


def test_vergiss_liest_sofort_neu():
    fake = FakeOllama(installiert=["klein:4b"])
    inv = inventar(fake.transport)
    inv.art("klein:4b")
    fake.installiert.append("neu:4b")
    inv.vergiss()
    assert inv.art("neu:4b") == LOKAL


def test_je_adresse_getrennt():
    fake = FakeOllama(installiert=["klein:4b"])
    inv = inventar(fake.transport)
    inv.art("klein:4b")
    inv.art("klein:4b", "http://anderer-host:11434")
    assert len(fake.anfragen) == 2
