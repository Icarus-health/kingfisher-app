"""Routen: Cloud über Ollama wird wie ein Cloudanbieter behandelt (Einwilligung, nie für Quellen)."""
import pytest

from icarus_memory.model_roles import rollen_von
from tests.ollama_fake import FakeOllama, Verbindungsfehler
from tests.test_model_roles_routes import app_und_client, bereit, geraet  # noqa: F401  (Fixture und Helfer)

CLOUD_MODELL = "deepseek-v4.1-flash:cloud"


@pytest.fixture
def mit_cloud(app_und_client):
    app, client = app_und_client
    fake = bereit(app, FakeOllama(installiert=["standard-modell", "gross:35b", "bge-m3"], cloud=[CLOUD_MODELL]))
    return app, client, fake


def put(client, rolle, **body):
    return client.put(f"/api/v1/models/roles/{rolle}", json=body)


@pytest.mark.parametrize("rolle", ["hintergrund", "einbettung"])
def test_hintergrund_und_einbettung_lehnen_das_cloudmodell_mit_einem_satz_ab(mit_cloud, rolle):
    app, client, _ = mit_cloud
    for body in ({"modell": CLOUD_MODELL}, {"modell": CLOUD_MODELL, "cloud": True, "anbieter": "ollama-cloud",
                                            "einwilligung": True}):
        antwort = put(client, rolle, **body)
        assert antwort.status_code == 422
        satz = antwort.json()["detail"]
        assert CLOUD_MODELL in satz and "Ollamas Cloud" in satz and "auf diesem Rechner" in satz
    assert rolle not in app.state.settings.model_roles  # nichts gespeichert


@pytest.mark.parametrize("rolle", ["frage", "antwort"])
def test_frage_und_antwort_verlangen_die_einwilligung_wie_bei_anderen_cloudanbietern(mit_cloud, rolle):
    app, client, _ = mit_cloud
    antwort = put(client, rolle, modell=CLOUD_MODELL)
    assert antwort.status_code == 422
    assert "Einwilligung" in antwort.json()["detail"] and "Ollama (USA)" in antwort.json()["detail"]
    assert rolle not in app.state.settings.model_roles
    antwort = put(client, rolle, modell=CLOUD_MODELL, einwilligung=True)
    assert antwort.status_code == 200
    gespeichert = app.state.settings.model_roles[rolle]
    assert gespeichert["cloud"] is True and gespeichert["anbieter"] == "ollama-cloud" and gespeichert["cloud_einwilligung"]
    zeile = {z["rolle"]: z for z in antwort.json()["rollen"]}[rolle]
    assert zeile["wirksam"]["modell"] == CLOUD_MODELL
    assert zeile["wirksam"]["lokal"] is False and zeile["wirksam"]["cloud_ueber_ollama"] is True
    assert zeile["wirksam"]["quelle"] == "cloud" and zeile["blockiert"] is None
    # Die Einwilligung gilt nur für diese Rolle.
    andere = {"frage": "antwort", "antwort": "frage"}[rolle]
    assert put(client, andere, modell=CLOUD_MODELL).status_code == 422
    # Cloud aus: die Einwilligung erlischt, die Rolle ist wieder lokal.
    assert put(client, rolle, cloud=False).status_code == 200
    assert rolle not in app.state.settings.model_roles


def test_der_anbieter_ollama_cloud_braucht_ein_cloudmodell(mit_cloud):
    _, client, _ = mit_cloud
    assert put(client, "antwort", modell="gross:35b", cloud=True, anbieter="ollama-cloud", einwilligung=True).status_code == 422
    assert put(client, "antwort", cloud=True, anbieter="ollama-cloud", einwilligung=True).status_code == 422


def test_ein_lokales_modell_geht_weiter_ohne_einwilligung(mit_cloud):
    app, client, _ = mit_cloud
    assert put(client, "hintergrund", modell="gross:35b").status_code == 200
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"


def test_die_vorauswahl_bietet_cloudmodelle_nicht_als_lokal_an(mit_cloud):
    _, client, _ = mit_cloud
    daten = client.get("/api/v1/models/recommendation").json()
    assert CLOUD_MODELL not in daten["ollama"]["installiert"]
    assert daten["ollama"]["cloud_ueber_ollama"] == [CLOUD_MODELL]
    assert "gross:35b" in daten["ollama"]["installiert"]
    rollen = client.get("/api/v1/models/roles").json()
    assert rollen["ollama_cloud"]["modelle"] == [CLOUD_MODELL] and "Ollama" in rollen["ollama_cloud"]["hinweis"]
    assert "ollama-cloud" not in {a["id"] for a in rollen["anbieter"]}


def test_handeintrag_als_lokal_wirkt_nicht_und_die_karte_sagt_warum(mit_cloud):
    app, client, _ = mit_cloud
    app.state.settings.model_roles["hintergrund"] = {"modell": CLOUD_MODELL, "cloud": False, "anbieter": "",
                                                     "cloud_einwilligung": ""}
    assert rollen_von(app).provider("hintergrund") is None
    zeile = {z["rolle"]: z for z in client.get("/api/v1/models/roles").json()["rollen"]}["hintergrund"]
    assert zeile["wirksam"]["modell"] is None and zeile["wirksam"]["quelle"] == "keins"
    assert CLOUD_MODELL in zeile["blockiert"] and "Ollamas Cloud" in zeile["blockiert"]
    app.state.settings.model_roles["antwort"] = {"modell": CLOUD_MODELL, "cloud": False, "anbieter": "",
                                                 "cloud_einwilligung": ""}
    zeile = {z["rolle"]: z for z in client.get("/api/v1/models/roles").json()["rollen"]}["antwort"]
    assert "ohne deine Einwilligung" in zeile["blockiert"] and zeile["wirksam"]["modell"] == "standard-modell"


def test_einbettung_mit_handeintrag_faellt_auf_die_vorgabe_zurueck(mit_cloud):
    app, client, _ = mit_cloud
    app.state.settings.model_roles["einbettung"] = {"modell": CLOUD_MODELL, "cloud": False, "anbieter": "",
                                                    "cloud_einwilligung": ""}
    zeile = {z["rolle"]: z for z in client.get("/api/v1/models/roles").json()["rollen"]}["einbettung"]
    assert zeile["wirksam"]["modell"] == "bge-m3:latest" and zeile["wirksam"]["quelle"] == "standard"
    assert rollen_von(app).provider("einbettung") is None


def test_gesundheitsstatus_meldet_cloud_ueber_ollama_getrennt(mit_cloud):
    app, client, _ = mit_cloud
    app.state.settings.model_roles["hintergrund"] = {"modell": CLOUD_MODELL, "cloud": False, "anbieter": "",
                                                     "cloud_einwilligung": ""}
    automation = client.get("/api/v1/memory/automation").json()
    assert automation["state"] == "cloud_ueber_ollama" and automation["cloud_modell"] == CLOUD_MODELL
    assert automation["model"] is None
    # `wrong_model` bleibt dem echten Cloudanbieter vorbehalten; hier ist es eine eigene Meldung.
    app.state.settings.model_roles.pop("hintergrund")
    assert client.get("/api/v1/memory/automation").json()["state"] != "cloud_ueber_ollama"


def test_posteingangsstatus_nennt_den_grund(mit_cloud):
    app, client, _ = mit_cloud
    assert client.get("/api/v1/mail/intake").json()["analysis_blocked"] is None
    app.state.settings.model_roles["hintergrund"] = {"modell": CLOUD_MODELL, "cloud": False, "anbieter": "",
                                                     "cloud_einwilligung": ""}
    antwort = client.get("/api/v1/mail/intake").json()
    assert antwort["analysis_blocked"] == "cloud_ueber_ollama" and antwort["analysis_active"] is False


def test_ollama_stumm_ein_gewaehltes_modell_ist_fuer_quellen_nicht_belegt_lokal(mit_cloud):
    app, client, _ = mit_cloud
    assert put(client, "hintergrund", modell="gross:35b").status_code == 200
    app.state.ollama_transport = Verbindungsfehler().transport
    app.state.ollama_inventar.vergiss()
    assert rollen_von(app).provider("hintergrund") is None
    app.state.ollama_transport = FakeOllama(installiert=["standard-modell", "gross:35b"]).transport
    app.state.ollama_inventar.vergiss()
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"
