"""Protokoll der Antwortzeiten (`GET /api/v1/antwortzeiten`) und der Schalter für die Sätze."""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory import config
from icarus_memory.server import create_app


@pytest.fixture
def app_und_client(monkeypatch):
    monkeypatch.setenv("ICARUS_PROVIDER", "ollama")
    monkeypatch.setenv("ICARUS_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("ICARUS_MODEL", "standard-modell")
    app = create_app()
    with TestClient(app) as client:
        yield app, client


def antwort_mit(app, zeiten, *, text="Text, der nie ins Protokoll gehört"):
    konversation = app.state.conversations.create("Zeit")
    app.state.conversations.add_message(konversation.id, "user", "Frage, die nie ins Protokoll gehört")
    app.state.conversations.add_message(konversation.id, "assistant", text, metadata={
        "context": {"working_answer": {"query": "x", "zeiten": zeiten}, "answer_mode": "memory_evidence"}})


# -- Protokoll -------------------------------------------------------------------------------------------


def test_ohne_antworten_ist_das_protokoll_leer_und_ehrlich(app_und_client):
    _, client = app_und_client
    daten = client.get("/api/v1/antwortzeiten").json()
    assert daten["antworten"] == 0 and daten["abschnitte"] == {}
    assert daten["ziel_s"] == 8.0 and daten["saetze"] == "an"
    assert daten["modelle"]["antwort"] == "standard-modell"
    assert daten["modelle"]["frage"] is None, "ohne Zuweisung versteht der Rückfall die Frage, ohne Modell"


def test_median_und_90_prozent_wert_je_abschnitt_aus_den_gespeicherten_gespraechen(app_und_client):
    app, client = app_und_client
    for i in range(1, 11):
        antwort_mit(app, {"suche": 0.1 * i, "antwort_modell": 1.0, "saetze_modell": float(i), "gesamt": i + 1.1})
    antwort_mit(app, {"suche": 0.2, "gesamt": 0.5})  # ohne Sätze: zählt nur dort, wo gemessen wurde
    daten = client.get("/api/v1/antwortzeiten").json()
    assert daten["antworten"] == 11
    assert daten["abschnitte"]["saetze_modell"] == {"median": 5.5, "p90": 9.0, "anzahl": 10}
    assert daten["abschnitte"]["suche"]["anzahl"] == 11
    assert daten["abschnitte"]["gesamt"]["anzahl"] == 11
    assert "frage" not in daten["abschnitte"]


def test_nur_die_letzten_50_zaehlen_und_kaputtes_wird_uebersprungen(app_und_client):
    app, client = app_und_client
    antwort_mit(app, {"gesamt": 500.0})  # die älteste fällt heraus
    antwort_mit(app, {"gesamt": "schnell"})
    antwort_mit(app, "keine Zahlen")
    for _ in range(50):
        antwort_mit(app, {"gesamt": 2.0})
    daten = client.get("/api/v1/antwortzeiten").json()
    assert daten["antworten"] == 50
    assert daten["abschnitte"]["gesamt"] == {"median": 2.0, "p90": 2.0, "anzahl": 50}


def test_das_protokoll_enthaelt_weder_frage_noch_antworttext(app_und_client):
    app, client = app_und_client
    antwort_mit(app, {"gesamt": 3.0})
    assert "nie ins Protokoll" not in client.get("/api/v1/antwortzeiten").text


def test_die_route_verlangt_den_zugang_wie_jede_andere(monkeypatch):
    monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", "geheim")
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/antwortzeiten").status_code in (401, 403)
        assert client.get("/api/v1/antwortzeiten", headers={"X-Icarus-Token": "geheim"}).status_code == 200


# -- Schalter --------------------------------------------------------------------------------------------


def test_schalter_steht_vorgabemaessig_an_und_wirkt_am_agenten_nach_dem_umschalten(app_und_client):
    app, client = app_und_client
    assert client.get("/api/v1/models/roles").json()["saetze"] == "an"
    assert app.state.agent._saetze_an() is True
    assert client.put("/api/v1/models/saetze", json={"saetze": "aus"}).json() == {"saetze": "aus"}
    assert app.state.agent._saetze_an() is False, "der Agent ist neu gebaut und kennt den Schalter"
    assert client.get("/api/v1/models/roles").json()["saetze"] == "aus"
    assert client.get("/api/v1/antwortzeiten").json()["saetze"] == "aus"
    assert config.load(Path(os.environ["ICARUS_DATA_DIR"])).antwort_saetze == "aus", "bleibt nach dem Neustart"
    assert client.put("/api/v1/models/saetze", json={"saetze": "an"}).json() == {"saetze": "an"}
    assert app.state.agent._saetze_an() is True


def test_schalter_nimmt_nur_an_oder_aus(app_und_client):
    _, client = app_und_client
    for falsch in ({"saetze": "vielleicht"}, {"saetze": True}, {}):
        assert client.put("/api/v1/models/saetze", json=falsch).status_code == 422


def test_unbekannter_wert_in_der_datei_gilt_als_an():
    assert config.Settings.from_dict({"antwort_saetze": "kaputt"}).antwort_saetze == "an"
    assert config.Settings.from_dict({"antwort_saetze": "aus"}).antwort_saetze == "aus"
    assert config.Settings.from_dict({}).antwort_saetze == "an"


# -- Zweites Tor (Prüfmodell) ------------------------------------------------------------------------------


def test_ohne_pruefmodell_ist_das_tor_still_aus_und_die_einstellung_sagt_es(app_und_client):
    app, client = app_und_client
    stand = client.get("/api/v1/antwortzeiten").json()["pruefung"]
    assert stand == {"schalter": "an", "zustand": "kein_modell", "modell": None}
    assert app.state.agent._pruef_tor().zustand == "kein_modell"
    assert client.get("/api/v1/models/roles").json()["satzpruefung"]["zustand"] == "kein_modell"


def test_mit_pruefmodell_ist_das_tor_an_und_der_schalter_wirkt_ab_der_naechsten_frage(app_und_client):
    app, client = app_und_client
    from tests.ollama_fake import FakeOllama
    app.state.ollama_transport = FakeOllama(installiert=["standard-modell", "bespoke-minicheck:7b"]).transport
    app.state.ollama_inventar.vergiss()
    app.state.settings.model_roles["pruefung"] = {"modell": "bespoke-minicheck:7b"}
    assert client.get("/api/v1/antwortzeiten").json()["pruefung"] == {
        "schalter": "an", "zustand": "an", "modell": "bespoke-minicheck:7b"}
    tor = app.state.agent._pruef_tor()
    assert tor.aktiv and tor.anbieter.model == "bespoke-minicheck:7b" and tor.anbieter.is_local
    aus = client.put("/api/v1/models/satzpruefung", json={"satzpruefung": "aus"}).json()
    assert aus == {"schalter": "aus", "zustand": "aus", "modell": "bespoke-minicheck:7b"}
    assert app.state.agent._pruef_tor().zustand == "aus"
    assert config.load(Path(os.environ["ICARUS_DATA_DIR"])).satzpruefung_modell == "aus", "bleibt nach dem Neustart"
    assert client.put("/api/v1/models/satzpruefung", json={"satzpruefung": "an"}).json()["zustand"] == "an"


def test_satzpruefung_nimmt_nur_an_oder_aus_und_unbekanntes_gilt_als_an(app_und_client):
    _, client = app_und_client
    for falsch in ({"satzpruefung": "vielleicht"}, {"satzpruefung": False}, {}):
        assert client.put("/api/v1/models/satzpruefung", json=falsch).status_code == 422
    assert config.Settings.from_dict({"satzpruefung_modell": "kaputt"}).satzpruefung_modell == "an"
    assert config.Settings.from_dict({"satzpruefung_modell": "aus"}).satzpruefung_modell == "aus"
