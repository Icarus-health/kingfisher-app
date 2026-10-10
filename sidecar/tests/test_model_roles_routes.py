"""Routen: Empfehlung je Rolle, Rollenwahl mit Cloud-Einwilligung, Einrichten mit Fake-Ollama."""
import pytest
from fastapi.testclient import TestClient

from icarus_memory import config, device_profile
from icarus_memory.model_roles import rollen_von
from icarus_memory.server import create_app
from tests.ollama_fake import FakeOllama, Verbindungsfehler


def geraet(client, gb=32, plattform="macos", frei_gb=500):
    """Meldet ein Gerät; `frei_gb=None` meldet keinen Festplattenplatz (dann ist er unbekannt)."""
    bericht = {"platform": plattform, "chip": "Apple M2 Max", "memory_bytes": gb * 1024**3}
    if frei_gb is not None:
        bericht["disk_free_bytes"] = int(frei_gb * 1024**3)
    r = client.post("/api/v1/device/profile", json=bericht)
    assert r.status_code == 200, r.text


@pytest.fixture
def app_und_client(monkeypatch):
    # Der freie Platz dieses Testrechners soll nichts entscheiden: ohne Meldung ist er unbekannt.
    monkeypatch.setattr(device_profile, "freier_platz_gb", lambda *a, **k: None)
    monkeypatch.setenv("ICARUS_PROVIDER", "ollama")
    monkeypatch.setenv("ICARUS_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("ICARUS_MODEL", "standard-modell")
    app = create_app()
    # Ein lokales Ollama mit den Modellen, die die Tests wählen; gewählte Modelle müssen belegt lokal sein.
    app.state.ollama_transport = FakeOllama(installiert=["standard-modell", "gross:35b", "mittel:9b", "klein:4b"]).transport
    app.state.ollama_inventar.vergiss()  # beim Aufbau der App hat das Inventar schon ohne Attrappe gefragt
    with TestClient(app) as client:
        yield app, client


def bereit(app, fake=None, bestanden=True):
    fake = fake or FakeOllama()
    app.state.ollama_transport = fake.transport
    app.state.ollama_inventar.vergiss()
    app.state.modell_pruefung = lambda modell, rolle: {
        "verifiziert": bestanden, "latenz_ms": 12,
        "profil": {"model": modell, "endpoint": "http://127.0.0.1:11434/v1", "verified": bestanden,
                   "capabilities": ["text", "tools"], "latency_ms": 12, "size_bytes": 1,
                   "checked_at": "2026-09-29T00:00:00+00:00"} if rolle != "einbettung" else None}
    return fake


# -- Empfehlung --------------------------------------------------------------------------------


def test_empfehlung_je_rolle_mit_status_und_bestaetigung(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    bereit(app, FakeOllama(installiert=["bge-m3:latest"]))
    daten = client.get("/api/v1/models/recommendation").json()
    assert daten["geraet"]["stufe_gb"] == 32 and daten["ollama"]["erreichbar"] is True
    rollen = {z["rolle"]: z for z in daten["rollen"]}
    assert list(rollen) == ["frage", "antwort", "pruefung", "hintergrund", "einbettung"]
    # 32 GB: das große Mixture-of-Experts-Modell würde tagsüber mit Frage und Suche nicht zusammen passen.
    assert rollen["antwort"]["empfohlen"]["name"] == "qwen3.5:9b"
    assert "qwen3.6:35b" in rollen["antwort"]["orchester_hinweis"]
    assert "Minuten" in rollen["antwort"]["empfohlen"]["bestaetigung"]
    assert rollen["einbettung"]["status"] == "eingerichtet"  # bge-m3 wird schon genutzt
    assert rollen["antwort"]["status"] == "fehlt"
    assert "Messlatte" in daten["hinweis"]


def test_standardmodell_das_der_empfehlung_entspricht_gilt_als_eingerichtet(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    bereit(app, FakeOllama(installiert=["standard-modell", "qwen3.5:9b"]))
    rollen = {z["rolle"]: z for z in client.get("/api/v1/models/recommendation").json()["rollen"]}
    assert rollen["antwort"]["status"] == "installiert"  # installiert, aber noch nicht übernommen
    app.state.agent.provider.model = "qwen3.5:9b"
    rollen = {z["rolle"]: z for z in client.get("/api/v1/models/recommendation").json()["rollen"]}
    assert rollen["antwort"]["status"] == "eingerichtet"


def test_ollama_nicht_erreichbar_ist_kein_fehler_der_empfehlung(app_und_client):
    app, client = app_und_client
    app.state.ollama_transport = Verbindungsfehler().transport
    daten = client.get("/api/v1/models/recommendation").json()
    assert daten["ollama"] == {"erreichbar": False, "installiert": [], "cloud_ueber_ollama": []}
    assert daten["geraet"]["bekannt"] is False and daten["geraet"]["stufe_gb"] == 8
    assert {z["status"] for z in daten["rollen"]} == {"fehlt"}


# -- Rollenwahl und Cloud ---------------------------------------------------------------------


def test_lokales_modell_je_rolle_wirkt_und_bleibt_gespeichert(app_und_client):
    app, client = app_und_client
    r = client.put("/api/v1/models/roles/hintergrund", json={"modell": "gross:35b"})
    assert r.status_code == 200
    zeile = {z["rolle"]: z for z in r.json()["rollen"]}["hintergrund"]
    assert zeile["wirksam"] == {"modell": "gross:35b", "lokal": True, "quelle": "eigene_wahl", "cloud_ueber_ollama": False}
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"
    assert app.state.agent.provider.model == "standard-modell"  # das Gespräch bleibt unberührt
    assert config.load(config.Path(__import__("os").environ["ICARUS_DATA_DIR"])).model_roles["hintergrund"]["modell"] == "gross:35b"
    # „Wie Standard“ zurücksetzen entfernt die Wahl.
    client.put("/api/v1/models/roles/hintergrund", json={"modell": ""})
    assert "hintergrund" not in app.state.settings.model_roles


def test_modellname_wird_geprueft(app_und_client):
    _, client = app_und_client
    assert client.put("/api/v1/models/roles/frage", json={"modell": "a b; rm -rf"}).status_code == 422
    assert client.put("/api/v1/models/roles/unbekannt", json={"modell": "x"}).status_code == 404


def test_cloud_braucht_ausdrueckliche_einwilligung_je_rolle(app_und_client, monkeypatch):
    app, client = app_und_client
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    r = client.put("/api/v1/models/roles/antwort", json={"cloud": True, "anbieter": "anthropic"})
    assert r.status_code == 422 and "Einwilligung" in r.json()["detail"]
    assert "antwort" not in app.state.settings.model_roles  # nichts gespeichert
    r = client.put("/api/v1/models/roles/antwort", json={"cloud": True, "anbieter": "anthropic", "einwilligung": True})
    assert r.status_code == 200
    gespeichert = app.state.settings.model_roles["antwort"]
    assert gespeichert["cloud"] and gespeichert["cloud_einwilligung"]  # Zeitstempel
    zeile = {z["rolle"]: z for z in r.json()["rollen"]}
    assert zeile["antwort"]["wirksam"]["quelle"] == "cloud" and zeile["antwort"]["wirksam"]["lokal"] is False
    assert app.state.agent.provider.name == "anthropic"
    # Die Einwilligung gilt nur für diese Rolle.
    assert zeile["frage"]["wirksam"]["quelle"] == "standard" and zeile["frage"]["wirksam"]["lokal"] is True
    assert client.put("/api/v1/models/roles/frage", json={"cloud": True, "anbieter": "anthropic"}).status_code == 422
    # Cloud aus: Einwilligung erlischt, Gespräch wieder lokal.
    r = client.put("/api/v1/models/roles/antwort", json={"cloud": False})
    assert r.status_code == 200 and "antwort" not in app.state.settings.model_roles
    assert app.state.agent.provider.is_local


def test_bestehende_einwilligung_wird_nicht_still_auf_anderen_anbieter_uebertragen(app_und_client, monkeypatch):
    app, client = app_und_client
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    client.put("/api/v1/models/roles/frage", json={"cloud": True, "anbieter": "anthropic", "einwilligung": True})
    r = client.put("/api/v1/models/roles/frage", json={"anbieter": "openai"})
    assert r.status_code == 422 and app.state.settings.model_roles["frage"]["anbieter"] == "anthropic"
    assert client.put("/api/v1/models/roles/frage", json={"anbieter": "openai", "einwilligung": True}).status_code == 200


@pytest.mark.parametrize("rolle", ["hintergrund", "einbettung"])
def test_hintergrund_und_einbettung_lassen_keine_cloud_zu(app_und_client, rolle, monkeypatch):
    app, client = app_und_client
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    r = client.put(f"/api/v1/models/roles/{rolle}", json={"cloud": True, "anbieter": "anthropic", "einwilligung": True})
    assert r.status_code == 422 and "auf diesem Rechner" in r.json()["detail"]
    assert rolle not in app.state.settings.model_roles


def test_handeintrag_der_cloud_fuer_hintergrund_wirkt_nicht(app_und_client, monkeypatch):
    app, client = app_und_client
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    app.state.settings.model_roles["hintergrund"] = {"cloud": True, "anbieter": "anthropic",
                                                     "cloud_einwilligung": "2026-09-29T10:00:00+00:00"}
    assert rollen_von(app).provider("hintergrund").is_local


def test_ohne_rollenkonfiguration_bleibt_alles_wie_heute(app_und_client):
    app, client = app_und_client
    assert app.state.settings.model_roles == {}
    for rolle in ("frage", "antwort", "hintergrund", "einbettung"):
        assert rollen_von(app).provider(rolle) is app.state.agent.provider
    # Der Verdichter wird beim Aufbau der App gebaut, als das Inventar noch keine Attrappe kannte.
    from icarus_memory.agent_verdrahtung import baue_hintergrund
    baue_hintergrund(app)
    assert app.state.consolidator._provider is app.state.agent.provider


def test_neubau_des_agenten_verteilt_rollen_auf_die_arbeiter(app_und_client):
    app, client = app_und_client
    client.put("/api/v1/models/roles/hintergrund", json={"modell": "gross:35b"})
    assert app.state.consolidator._provider.model == "gross:35b"
    assert app.state.summarizer._provider.model == "gross:35b"
    client.put("/api/v1/models/roles/antwort", json={"modell": "mittel:9b"})
    assert app.state.agent.provider.model == "mittel:9b"
    assert app.state.standard_provider.model == "standard-modell"
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"


# -- Einrichten -------------------------------------------------------------------------------


def einrichten(client, app, rolle="antwort", **extra):
    r = client.post("/api/v1/models/pull", json={"rolle": rolle, "bestaetigt": True, **extra})
    if r.status_code != 202:
        return r, None
    app.state.pull_manager.warte()
    return r, client.get(f"/api/v1/models/pull/{r.json()['id']}").json()


def test_einrichten_laedt_prueft_und_uebernimmt_das_modell(app_und_client):
    app, client = app_und_client
    geraet(client, 128)
    fake = bereit(app)
    r, stand = einrichten(client, app)
    assert r.json()["modell"] == "qwen3.6:35b"
    assert stand["phase"] == "fertig" and stand["ergebnis"]["uebernommen"] is True
    assert app.state.settings.model_roles["antwort"] == {"modell": "qwen3.6:35b", "cloud": False,
                                                         "anbieter": "", "cloud_einwilligung": ""}
    assert app.state.agent.provider.model == "qwen3.6:35b"
    assert any(p["model"] == "qwen3.6:35b" for p in app.state.settings.routing_profiles)
    assert ("POST", "/api/pull", {"model": "qwen3.6:35b", "stream": True}) in fake.anfragen
    rollen = {z["rolle"]: z for z in client.get("/api/v1/models/recommendation").json()["rollen"]}
    assert rollen["antwort"]["status"] == "eingerichtet"


def test_einrichten_der_einbettung_setzt_nur_das_modell_der_rolle(app_und_client):
    app, client = app_und_client
    bereit(app)
    _, stand = einrichten(client, app, "einbettung")
    assert stand["phase"] == "fertig"
    assert app.state.settings.model_roles["einbettung"]["modell"] == "bge-m3"
    assert app.state.settings.routing_profiles == []
    assert app.state.agent.provider.model == "standard-modell"


def test_ohne_bestaetigung_wird_nichts_geladen(app_und_client):
    app, client = app_und_client
    fake = bereit(app)
    r = client.post("/api/v1/models/pull", json={"rolle": "antwort"})
    assert r.status_code == 422 and "GB" in r.json()["detail"] and "Minuten" in r.json()["detail"]
    r = client.post("/api/v1/models/pull", json={"rolle": "antwort", "bestaetigt": False})
    assert r.status_code == 422
    assert not any(pfad == "/api/pull" for _, pfad, _ in fake.anfragen)
    assert client.get("/api/v1/models/pull").json() == {"aktuell": None}


def test_nur_katalogmodelle_dieser_rolle_und_dieses_geraets(app_und_client):
    app, client = app_und_client
    geraet(client, 16)
    fake = bereit(app)
    for modell in ("llama3.1:70b", "qwen3.6:35b", "../../etc/passwd"):
        r = client.post("/api/v1/models/pull", json={"rolle": "antwort", "modell": modell, "bestaetigt": True})
        assert r.status_code == 422, modell
    assert client.post("/api/v1/models/pull", json={"rolle": "nachrichten", "bestaetigt": True}).status_code == 404
    assert not any(pfad == "/api/pull" for _, pfad, _ in fake.anfragen)


def test_alternative_der_empfehlung_ist_erlaubt(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    bereit(app)
    r, stand = einrichten(client, app, modell="gemma4:12b")
    assert r.status_code == 202 and stand["phase"] == "fertig" and app.state.agent.provider.model == "gemma4:12b"


def test_zu_wenig_arbeitsspeicher_wird_vorher_erklaert(app_und_client, monkeypatch):
    app, client = app_und_client
    geraet(client, 8)
    bereit(app)
    from icarus_memory import model_recommendation as m
    gross = m.KatalogEintrag("antwort", (8,), "zu-gross:70b", 40.0, 45.0, "dicht", "Zu groß.")
    monkeypatch.setattr(m, "KATALOG", (*[e for e in m.KATALOG if not (e.rolle == "antwort" and 8 in e.stufen)], gross))
    r = client.post("/api/v1/models/pull", json={"rolle": "antwort", "bestaetigt": True})
    assert r.status_code == 422 and "Arbeitsspeicher" in r.json()["detail"] and "kleineres" in r.json()["detail"]


def test_ladefehler_erscheinen_mit_grund_und_naechstem_schritt(app_und_client):
    app, client = app_und_client
    bereit(app, FakeOllama(modus="fehler_platz"))
    _, stand = einrichten(client, app)
    assert stand["phase"] == "fehler" and "Speicherplatz" in stand["fehler"]["grund"]
    assert stand["fehler"]["naechster_schritt"]
    assert "antwort" not in app.state.settings.model_roles  # nichts halb übernommen
    assert app.state.agent.provider.model == "standard-modell"


def test_kein_ollama_beim_einrichten(app_und_client):
    app, client = app_und_client
    bereit(app)
    app.state.ollama_transport = Verbindungsfehler().transport
    _, stand = einrichten(client, app)
    assert stand["phase"] == "fehler" and "nicht erreichbar" in stand["fehler"]["grund"]


def test_nicht_bestandene_pruefung_uebernimmt_das_modell_nicht(app_und_client):
    app, client = app_und_client
    bereit(app, bestanden=False)
    _, stand = einrichten(client, app)
    assert stand["phase"] == "fehler" and "nicht übernommen" in stand["fehler"]["grund"]
    assert "antwort" not in app.state.settings.model_roles
    assert app.state.settings.routing_profiles == []


def test_zweiter_ladevorgang_waehrend_des_ersten_wird_abgewiesen(app_und_client):
    import threading
    app, client = app_und_client
    frei = threading.Event()
    bereit(app, FakeOllama(warte=frei))
    r = client.post("/api/v1/models/pull", json={"rolle": "antwort", "bestaetigt": True})
    assert r.status_code == 202
    assert client.get("/api/v1/models/pull").json()["aktuell"]["id"] == r.json()["id"]
    zweiter = client.post("/api/v1/models/pull", json={"rolle": "frage", "bestaetigt": True})
    assert zweiter.status_code == 409 and "warten" in zweiter.json()["detail"]
    frei.set()
    app.state.pull_manager.warte()
    assert client.get(f"/api/v1/models/pull/{r.json()['id']}").json()["phase"] == "fertig"
    assert client.get("/api/v1/models/pull/unbekannt").status_code == 404


def test_echte_einbettungspruefung_mit_fake_ollama(app_und_client):
    """Ohne Stub: Der Weg über /api/embed bestätigt das Modell (Attrappe liefert einen Vektor)."""
    app, client = app_und_client
    fake = FakeOllama()
    app.state.ollama_transport = fake.transport
    r, stand = einrichten(client, app, "einbettung")
    assert stand["phase"] == "fertig" and stand["ergebnis"]["geprueft"] is True
    assert any(pfad == "/api/embed" for _, pfad, _ in fake.anfragen)
