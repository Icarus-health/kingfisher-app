"""Route: der Bedarf des Orchesters in der Empfehlung und die Platzprüfung vor dem Laden."""
import pytest

from icarus_memory import device_profile
from tests.ollama_fake import FakeOllama
from tests.test_model_roles_routes import app_und_client, bereit, einrichten, geraet  # noqa: F401  (Fixture, Helfer)


def karte(client):
    return client.get("/api/v1/models/recommendation").json()


def test_die_empfehlung_liefert_den_bedarf_mit(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=210)
    bereit(app, FakeOllama())
    o = karte(client)["orchester"]
    # Tag: gemma4:12b + qwen3.5:9b + tev1:4b (Prüfung) + bge-m3; Nacht: qwen3.5:9b + bge-m3
    assert o["tag_gb"] == pytest.approx(26.7) and o["nacht_gb"] == 12
    assert o["festplatte_frei_gb"] == 210 and o["nutzbar_gb"] == pytest.approx(27.2)
    assert (o["passt_tag"], o["passt_nacht"], o["passt_festplatte"]) == (True, True, True)
    assert o["hinweise"] == []  # die Vorauswahl selbst passt, es gibt nichts zu warnen
    zeilen = {z["rolle"]: z for z in karte(client)["rollen"]}
    assert zeilen["antwort"]["empfohlen"]["name"] == "gemma4:12b" and "tagsüber" in zeilen["antwort"]["orchester_hinweis"]
    assert zeilen["hintergrund"]["empfohlen"]["name"] == "qwen3.5:9b"
    assert zeilen["hintergrund"]["orchester_hinweis"] == ""
    # Die Prüfung gibt zuerst Speicher her, sobald das allein reicht; die Frage bleibt, wie sie war.
    assert zeilen["pruefung"]["empfohlen"]["name"] == "tev1:4b" and "bespoke-minicheck:7b" in zeilen["pruefung"]["orchester_hinweis"]
    assert zeilen["frage"]["orchester_hinweis"] == ""


def test_auf_einem_grossen_geraet_passt_alles_ohne_hinweis(app_und_client):
    app, client = app_und_client
    geraet(client, 128, frei_gb=900)
    bereit(app, FakeOllama())
    o = karte(client)["orchester"]
    assert (o["passt_tag"], o["passt_nacht"], o["passt_festplatte"]) == (True, True, True) and o["hinweise"] == []


def test_knappes_geraet_bekommt_eine_ruhige_warnung_mit_vorschlag(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=12)
    bereit(app, FakeOllama())
    o = karte(client)["orchester"]
    assert o["passt_festplatte"] is False
    text = " ".join(o["hinweise"])
    assert "Festplatte" in text and "frei sind etwa 12 GB" in text and "Kleiner:" in text


def test_was_schon_da_ist_braucht_keinen_neuen_platz(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=5)
    bereit(app, FakeOllama(installiert=["gemma4:12b", "qwen3.5:9b", "tev1:4b", "nemotron-3.5-lightning:30b", "bge-m3"]))
    o = karte(client)["orchester"]
    assert o["festplatte_gb"] == pytest.approx(20.3) and o["festplatte_noch_gb"] == 0
    assert o["passt_festplatte"] is True


def test_unbekannter_platz_wird_nicht_geraten(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=None)
    bereit(app, FakeOllama())
    o = karte(client)["orchester"]
    assert o["festplatte_frei_gb"] is None and o["passt_festplatte"] is None
    assert not any("Festplatte" in h for h in o["hinweise"])


def test_ohne_meldung_des_helfers_wird_dort_gemessen_wo_das_moeglich_ist(app_und_client, monkeypatch):
    app, client = app_und_client
    monkeypatch.setattr(device_profile, "freier_platz_gb", lambda *a, **k: 40.0)
    geraet(client, 32, frei_gb=None)
    bereit(app, FakeOllama())
    assert karte(client)["orchester"]["festplatte_frei_gb"] == 40
    geraet(client, 32, frei_gb=300)  # eine Meldung vom Rechner geht der eigenen Messung vor
    assert karte(client)["orchester"]["festplatte_frei_gb"] == 300


def test_laden_wird_abgelehnt_wenn_der_platz_nicht_reicht(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=6)
    fake = bereit(app)
    r = client.post("/api/v1/models/pull", json={"rolle": "antwort", "bestaetigt": True})
    assert r.status_code == 422
    satz = r.json()["detail"]
    assert "gemma4:12b" in satz and "8 GB Festplatte" in satz and "frei sind etwa 6 GB" in satz
    assert "oder " in satz and "wählen" in satz  # nennt ein kleineres Modell
    assert not any(pfad == "/api/pull" for _, pfad, _ in fake.anfragen)  # nichts wurde geladen


def test_laden_geht_wenn_der_platz_reicht_und_wenn_er_unbekannt_ist(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=20)
    bereit(app)
    r, stand = einrichten(client, app)
    assert r.status_code == 202 and stand["phase"] == "fertig"
    geraet(client, 32, frei_gb=None)
    bereit(app)
    r, _ = einrichten(client, app)
    assert r.status_code == 202  # unbekannt heißt nicht „zu wenig“


def test_uebernehmen_eines_installierten_modells_braucht_keinen_platz(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=1)
    bereit(app, FakeOllama(installiert=["gemma4:12b"]))
    r, stand = einrichten(client, app)
    assert r.status_code == 202 and stand["phase"] == "fertig"


def test_die_grosse_wahl_bleibt_ausdruecklich_moeglich_wenn_sie_einzeln_passt(app_und_client):
    app, client = app_und_client
    geraet(client, 32, frei_gb=500)
    bereit(app)
    r = client.post("/api/v1/models/pull", json={"rolle": "antwort", "modell": "qwen3.6:35b", "bestaetigt": True})
    assert r.status_code == 202
