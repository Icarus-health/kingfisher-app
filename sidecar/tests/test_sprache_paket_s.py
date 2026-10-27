"""Paket S der Persona-Prüfung (26.10.2026): Sprache und Kleinigkeiten.

Nur synthetische Daten. Jeder Abschnitt nennt den Befund aus `docs/runs/2026-10-26-persona-pruefung/README.md`,
Abschnitt 6, oder den offenen Rest eines vorigen Pakets.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, bereiche, config
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

ICH = "lea.hartmann.nordlicht@gmail.com"
PRIVAT_ICH = "lea.hartmann.privat@gmail.com"


def _app(tmp_path, monkeypatch, **mehr):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    daten = {
        "mail_accounts": [
            {"id": "mail-kunde", "label": ICH, "imap_host": "imap.gmail.com", "user": ICH, "sender": ICH},
            {"id": "mail-privat", "label": PRIVAT_ICH, "imap_host": "imap.gmail.com", "user": PRIVAT_ICH,
             "sender": PRIVAT_ICH},
        ],
        **mehr,
    }
    (tmp_path / config.DATEINAME).write_text(json.dumps(daten), encoding="utf-8")
    return create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"),
        audit=AuditLog(tmp_path / "audit.sqlite3"),
        tasks=TaskStore(tmp_path / "tasks.sqlite3"),
        workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
        episodes=EpisodeStore(tmp_path / "episodes.sqlite3"),
    )


_NUMMER = [0]


def _mail(app, konto: str, von: str, text: str, *, an: str = "", ich: bool = False, projekt: str | None = None):
    _NUMMER[0] += 1
    kontakte = [{"adresse": von, "name": von.split("@")[0], "rolle": "von", "ich": ich}]
    if an:
        kontakte.append({"adresse": an, "name": an.split("@")[0], "rolle": "an", "ich": False})
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, f"Betreff {_NUMMER[0]}", text,
        Provenance(source_type=SourceType.EMAIL, source_ref=f"{konto}:<s{_NUMMER[0]}@probe.example>"),
        contacts=kontakte, occurred_at=datetime(2026, 10, 20, 9, _NUMMER[0] % 60, tzinfo=timezone.utc))
    if projekt:
        app.state.episodes.link_project(episode.id, projekt)
    return episode


# -- Befund 3: Bereichsvorschlag folgt dem Inhalt, nicht nur der Domäne ---------------------------------------------


def test_eine_mail_von_einem_geschaeftspartner_klingt_nach_arbeit() -> None:
    signatur = "Hallo Lea, anbei die Agenda.\n\nPetra Sander\nLeiterin Controlling\nNordlicht Werke GmbH"
    assert bereiche.mail_einschaetzen("petra.sander@nordlicht-werke.example", signatur) == "arbeit"
    assert bereiche.mail_einschaetzen("sven.albers@nordlicht-werke.example",
                                      "Frau Hartmann,\ndie Kostenbasis liegt im Datenraum.") == "arbeit"
    assert bereiche.mail_einschaetzen("petra.sander@nordlicht-werke.example", "Hallo Lea, Passt 10 Uhr?",
                                      projekt=True) == "arbeit"
    # Selbstständige mit Gmail und Firmensignatur.
    assert bereiche.mail_einschaetzen("uwe.hofmann@gmail.com", "Sehr geehrte Frau Hartmann,\n…\nHofmann Spedition GmbH",
                                      ) == "arbeit"


def test_freunde_einladungen_und_firmen_an_privatkunden_klingen_nicht_nach_arbeit() -> None:
    assert bereiche.mail_einschaetzen("mara.hartmann@web.example", "Hi Lea, bringst du den Kuchen mit?") == "privat"
    # Eine Einladung einer Organisation ohne zweites Zeichen: weder noch.
    assert bereiche.mail_einschaetzen("nina@hackathon-wiesbaden.example",
                                      "Hallo Lea, wir laden dich herzlich zum Hackathon ein.") is None
    # Eine Firma, die einer Privatkundin schreibt, ist kein Geschäftspartner – auch förmlich und mit GmbH.
    assert bereiche.mail_einschaetzen("j.becker@stadtwerke.example",
                                      "Sehr geehrte Frau Hartmann,\nIhre Jahresabrechnung …\nStadtwerke GmbH") is None
    assert bereiche.mail_einschaetzen("noreply@shop.example", "Sehr geehrte Frau Hartmann, Mit freundlichen Grüßen") is None
    assert bereiche.mail_einschaetzen("kein-at-zeichen", "Frau Hartmann,") is None


def test_gmail_eines_grosskunden_bekommt_arbeit_und_nicht_privat(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    projekt = app.state.workspace.add_project("Restrukturierung Nordlicht", Provenance(SourceType.USER_STATED))
    for text in ("Hallo Lea, anbei die Agenda für den Kick-off.", "Hallo Lea, der Datenraum ist freigeschaltet.",
                 "Hallo Lea, die Interviews sind für KW 40 geplant."):
        _mail(app, "mail-kunde", "petra.sander@nordlicht-werke.example", text, projekt=projekt.id)
    _mail(app, "mail-kunde", "sven.albers@nordlicht-werke.example", "Frau Hartmann, die Kostenbasis liegt im Datenraum.")
    _mail(app, "mail-kunde", "petra.sander@nordlicht-werke.example", "Hallo Lea, passt Donnerstag 10 Uhr?")
    # Privat: Freunde, Familie, eine Einladung.
    _mail(app, "mail-privat", "mara.hartmann@web.example", "Hi Lea, bringst du am Samstag den Kuchen mit?")
    _mail(app, "mail-privat", "nina@hackathon-wiesbaden.example", "Hallo Lea, wir laden dich zum Hackathon ein.")
    _mail(app, "mail-privat", "ole@hackathon-wiesbaden.example", "Hallo Lea, wir suchen noch Mentorinnen.")
    postfaecher = {p["id"]: p for p in TestClient(app).get("/api/v1/konten").json()["postfaecher"]}
    kunde, privat = postfaecher["mail-kunde"]["vorschlag"], postfaecher["mail-privat"]["vorschlag"]
    assert kunde["bereich"] == "arbeit", kunde
    assert "Geschäftspartner" in kunde["grund"] and "nordlicht-werke.example" in kunde["grund"]
    assert privat["bereich"] == "privat", privat


def test_gemischt_oder_noch_nichts_gelesen_fragt_statt_zu_raten(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    # Kunde: noch nichts gelesen. Privat: zwei Geschäftspartner, zwei Freunde.
    _mail(app, "mail-privat", "petra.sander@nordlicht-werke.example", "Frau Hartmann, anbei das Angebot.")
    _mail(app, "mail-privat", "dana.weiss@weiss-moebel.example", "Frau Hartmann, der Abschluss liegt vor.")
    _mail(app, "mail-privat", "mara.hartmann@web.example", "Hi Lea, Samstag?")
    _mail(app, "mail-privat", "felix@posteo.example", "Hi Lea, Sonntag?")
    konten = TestClient(app).get("/api/v1/konten").json()
    postfaecher = {p["id"]: p for p in konten["postfaecher"]}
    assert postfaecher["mail-kunde"]["vorschlag"] is None
    assert postfaecher["mail-privat"]["vorschlag"] is None


def test_alle_vorschlaege_uebernehmen_sortiert_den_kunden_nicht_nach_privat(tmp_path, monkeypatch) -> None:
    """Der Weg des Befunds: „Alle Vorschläge übernehmen“ nimmt, was die Übersicht vorschlägt."""
    app = _app(tmp_path, monkeypatch)
    for teil in ("Agenda", "Datenraum", "Interviews"):
        _mail(app, "mail-kunde", "petra.sander@nordlicht-werke.example",
              f"Hallo Lea,\nanbei: {teil}.\n\nPetra Sander\nNordlicht Werke GmbH")
    client = TestClient(app)
    zuordnung = {p["id"]: p["vorschlag"]["bereich"] for p in client.get("/api/v1/konten").json()["postfaecher"]
                 if p["vorschlag"]}
    assert zuordnung == {"mail-kunde": "arbeit"}
    client.put("/api/v1/konten/bereich", json={"zuordnung": zuordnung})
    assert config.load(tmp_path).konten["bereich_je_konto"] == {"mail-kunde": "arbeit"}


def test_eigene_antworten_an_eine_firma_machen_sie_zum_geschaeftspartner(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    _mail(app, "mail-kunde", "katrin.vogel@lahnwerke.example", "Hallo Lea, wann passt es dir?")
    _mail(app, "mail-kunde", "mehmet.aydin@lahnwerke.example", "Hallo Lea, die Absatzdaten liegen bei.")
    _mail(app, "mail-kunde", ICH, "Hallo Katrin, Dienstag passt.", an="katrin.vogel@lahnwerke.example", ich=True)
    inhalt = bereiche.inhalt_des_postfachs(app, "mail-kunde")
    assert inhalt.beruflich >= 2 and inhalt.privat == 0
    # Gegenprobe: ohne eigene Antwort sind dieselben Mails weder noch.
    (tmp_path / "zwei").mkdir()
    app2 = _app(tmp_path / "zwei", monkeypatch)
    _mail(app2, "mail-kunde", "katrin.vogel@lahnwerke.example", "Hallo Lea, wann passt es dir?")
    _mail(app2, "mail-kunde", "mehmet.aydin@lahnwerke.example", "Hallo Lea, die Absatzdaten liegen bei.")
    assert bereiche.inhalt_des_postfachs(app2, "mail-kunde").beruflich == 0


def test_kalender_derselben_adresse_folgt_dem_inhalt_des_postfachs(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch, calendar_sources=[
        {"id": "calendar-kunde", "label": "Kalender", "kind": "caldav", "url": "https://dav.example/", "user": ICH}])
    for teil in ("Agenda", "Datenraum"):
        _mail(app, "mail-kunde", "petra.sander@nordlicht-werke.example", f"Frau Hartmann,\nanbei: {teil}.\nNordlicht Werke GmbH")
    kalender = TestClient(app).get("/api/v1/konten").json()["kalender"]
    assert kalender[0]["vorschlag"]["bereich"] == "arbeit"


# -- Befund 5: Cloud-Modell vorbelegt, als Liste ----------------------------------------------------------------------


def test_jeder_cloudanbieter_hat_ein_vorbelegtes_modell_in_alltagsworten(tmp_path, monkeypatch) -> None:
    import re

    from icarus_memory.cloud_access_routes import CloudAccessIn
    from icarus_memory.model_roles_routes import _MODELLNAME
    antwort = TestClient(_app(tmp_path, monkeypatch)).get("/api/v1/models/cloud-access").json()
    muster = re.compile(CloudAccessIn.model_fields["model"].metadata[0].pattern)
    for anbieter in antwort["providers"]:
        modelle = anbieter["modelle"]
        assert modelle, anbieter["id"]
        assert modelle[0]["titel"].startswith("Empfohlen"), anbieter["id"]
        for modell in modelle:
            # Speicherbar (Feld) und als Rollenmodell gültig (Mistral, OpenRouter verlangen einen Namen).
            assert muster.fullmatch(modell["id"]) and _MODELLNAME.fullmatch(modell["id"]), modell
            assert modell["id"] not in modell["titel"], "der Titel sagt, wofür es taugt, nicht die Kennung"
