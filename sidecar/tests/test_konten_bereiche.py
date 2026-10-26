"""Konten und Bereiche (Paket K, docs/66-automatik.md): Name, Bereich mit Vorschlag, Stand, Vererbung, Filtergrundlage.

Nur synthetische Konten (example-Domänen und Gmail-Adressen ohne echte Zugänge); kein Netz.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, bereiche, config, konten_routes
from icarus_memory.audit import AuditLog
from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.connectors.mail import MailConnector
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore


def _einstellungen(tmp_path, **mehr) -> None:
    daten = {
        "mail_accounts": [
            {"id": "mail-a", "label": "Gmail / Google Workspace", "imap_host": "imap.gmail.com",
             "user": "anna.probe@gmail.com", "sender": "anna.probe@gmail.com"},
            {"id": "mail-b", "label": "Gmail / Google Workspace", "imap_host": "imap.gmail.com",
             "user": "familie.probe@gmail.com", "sender": "familie.probe@gmail.com"},
            {"id": "mail-c", "label": "Firma", "imap_host": "imap.firma.example",
             "user": "anna@firma.example", "sender": "anna@firma.example"},
        ],
        "calendar_sources": [
            {"id": "calendar-arbeit", "label": "Arbeit", "kind": "ical", "url": "https://kalender.example/"},
            {"id": "calendar-x", "label": "Kalender", "kind": "caldav", "url": "https://dav.firma.example/",
             "user": "anna@firma.example"},
        ],
        **mehr,
    }
    (tmp_path / config.DATEINAME).write_text(json.dumps(daten), encoding="utf-8")


def _app(tmp_path, monkeypatch, **mehr):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    _einstellungen(tmp_path, **mehr)
    return create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"),
        audit=AuditLog(tmp_path / "audit.sqlite3"),
        tasks=TaskStore(tmp_path / "tasks.sqlite3"),
        workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
        episodes=EpisodeStore(tmp_path / "episodes.sqlite3"),
    )


def _mail(app, konto: str, nummer: int, project_id: str | None = None):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, f"Betreff {nummer}", f"Text {nummer}",
        Provenance(source_type=SourceType.EMAIL, source_ref=f"{konto}:<m{nummer}@probe.example>"),
        occurred_at=datetime(2026, 10, 20, 9, nummer, tzinfo=timezone.utc))
    if project_id:
        app.state.episodes.link_project(episode.id, project_id)
    return episode


# -- Vorschlag --------------------------------------------------------------------------------------------------------


def test_vorschlag_postfach_privat_arbeit_und_ohne_adresse_keiner() -> None:
    assert bereiche.vorschlag_postfach("anna.probe@gmail.com").bereich == "privat"
    assert "gmail.com" in bereiche.vorschlag_postfach("anna.probe@gmail.com").grund
    assert bereiche.vorschlag_postfach("anna@web.de").bereich == "privat"
    assert bereiche.vorschlag_postfach("anna@firma.example").bereich == "arbeit"
    assert bereiche.vorschlag_postfach("") is None
    assert bereiche.vorschlag_postfach("kein-at-zeichen") is None


def test_vorschlag_kalender_aus_name_konto_oder_adresse_sonst_keiner() -> None:
    assert bereiche.vorschlag_kalender("Arbeit").bereich == "arbeit"
    assert bereiche.vorschlag_kalender("Familie").bereich == "privat"
    assert bereiche.vorschlag_kalender("Team-Termine").bereich == "arbeit"
    # Ohne Hinweis kein Vorschlag statt Raten.
    assert bereiche.vorschlag_kalender("Kalender") is None
    assert bereiche.vorschlag_kalender("Feiertage in Deutschland") is None
    # Widersprüchlicher Name: auch kein Raten.
    assert bereiche.vorschlag_kalender("Arbeit und Familie") is None
    konto = bereiche.vorschlag_kalender("Kalender", konto=("Firma", "arbeit"))
    assert konto.bereich == "arbeit" and "Firma" in konto.grund
    assert bereiche.vorschlag_kalender("Kalender", adresse="anna.probe@gmail.com").bereich == "privat"


# -- Vererbung --------------------------------------------------------------------------------------------------------


def test_referenzen_ergeben_das_konto() -> None:
    assert bereiche.quelle_von_referenz("mail-a:<m1@probe.example>") == "mail-a"
    assert bereiche.quelle_von_referenz("mail-a:<m1@probe.example>#anhang:1:x.pdf") == "mail-a"
    assert bereiche.quelle_von_referenz("calendar:calendar-x:uid-1") == "calendar-x"
    assert bereiche.quelle_von_referenz("calendar:mac-calendar/abc123:uid") == "mac-calendar/abc123"
    assert bereiche.quelle_von_referenz("imap:17") is None
    assert bereiche.quelle_von_referenz("<m1@probe.example>") is None
    assert bereiche.quelle_von_referenz(None) is None


def test_nur_bestaetigtes_vererbt_sich(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    episode = _mail(app, "mail-a", 1)
    # Vorschlag „Privat“ liegt vor, ist aber nicht bestätigt: keine Wirkung.
    assert bereiche.bereich_einer_episode(app, episode.id) is None
    bereiche.setze_bereich(app.state.settings, "mail-a", "privat")
    assert bereiche.bereich_einer_episode(app, episode.id) == "privat"


def test_mac_kalender_erbt_ueber_seine_gedaechtnisquelle(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    from icarus_memory.calendar_memory import herkunft, quelle_fuer_mac
    bereiche.setze_bereich(app.state.settings, "mac-calendar:ABC-1", "privat")
    assert bereiche.bereich_einer_referenz(app.state.settings, herkunft(quelle_fuer_mac("ABC-1"), "u1")) == "privat"
    termin = {"uid": "mac-calendar:u1", "source_id": "mac-calendar", "view_source_id": "mac-calendar:ABC-1"}
    assert bereiche.bereich_eines_termins(app.state.settings, termin) == "privat"


def test_aufgabe_erbt_von_quelle_sonst_vom_projekt(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    s = app.state.settings
    bereiche.setze_bereich(s, "mail-a", "privat")
    bereiche.setze_bereich(s, "mail-c", "arbeit")
    projekt = app.state.workspace.add_project("Umzug", Provenance(SourceType.USER_STATED), area="Privat")
    mail = _mail(app, "mail-c", 1)
    aus_mail = app.state.tasks.add("Angebot prüfen", Provenance(SourceType.USER_STATED, source_ref=f"episode:{mail.id}"),
                                   project_id=projekt.id)
    nur_projekt = app.state.tasks.add("Kisten kaufen", Provenance(SourceType.USER_STATED), project_id=projekt.id)
    ohne = app.state.tasks.add("Irgendwas", Provenance(SourceType.USER_STATED))
    # Die Quelle geht vor: Die Mail kam ins Firmenpostfach, auch wenn das Projekt privat ist.
    assert bereiche.bereich_einer_aufgabe(app, aus_mail) == "arbeit"
    assert bereiche.bereich_einer_aufgabe(app, nur_projekt) == "privat"
    assert bereiche.bereich_einer_aufgabe(app, ohne) is None


def test_projekt_ohne_area_nimmt_den_ueberwiegenden_bereich_seiner_quellen(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    s = app.state.settings
    bereiche.setze_bereich(s, "mail-a", "privat")
    bereiche.setze_bereich(s, "mail-c", "arbeit")
    klar = app.state.workspace.add_project("Messe", Provenance(SourceType.USER_STATED))
    for n in range(3):
        _mail(app, "mail-c", n, klar.id)
    _mail(app, "mail-a", 9, klar.id)
    patt = app.state.workspace.add_project("Patt", Provenance(SourceType.USER_STATED))
    _mail(app, "mail-c", 20, patt.id)
    _mail(app, "mail-a", 21, patt.id)
    leer = app.state.workspace.add_project("Leer", Provenance(SourceType.USER_STATED))
    assert bereiche.bereich_eines_projekts(app, klar.id) == "arbeit"
    assert bereiche.bereich_eines_projekts(app, patt.id) is None
    assert bereiche.bereich_eines_projekts(app, leer.id) is None


def test_geburtstage_sind_privat_und_unbekannte_quellen_ohne_bereich() -> None:
    s = config.Settings()
    assert bereiche.bereich_eines_termins(s, {"art": "geburtstag"}) == "privat"
    assert bereiche.bereich_eines_termins(s, {"source_id": "calendar-unbekannt"}) is None


# -- API --------------------------------------------------------------------------------------------------------------


def test_zwei_gmail_konten_heissen_nach_ihrer_adresse(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    namen = [e.label for e in app.state.settings.mail_accounts]
    assert namen == ["anna.probe@gmail.com", "familie.probe@gmail.com", "Firma"]
    # Gespeichert, nicht nur angezeigt.
    gespeichert = json.loads((tmp_path / config.DATEINAME).read_text(encoding="utf-8"))
    assert [e["label"] for e in gespeichert["mail_accounts"]][:2] == ["anna.probe@gmail.com", "familie.probe@gmail.com"]


def test_konten_zeigen_vorschlag_mit_grund_und_bestaetigen_vererbt(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    konten = client.get("/api/v1/konten").json()
    postfaecher = {p["id"]: p for p in konten["postfaecher"]}
    assert postfaecher["mail-a"]["bereich"] is None
    assert postfaecher["mail-a"]["vorschlag"]["bereich"] == "privat"
    assert postfaecher["mail-c"]["vorschlag"]["bereich"] == "arbeit"
    kalender = {k["id"]: k for k in konten["kalender"]}
    assert kalender["calendar-arbeit"]["vorschlag"]["bereich"] == "arbeit"
    assert kalender["calendar-x"]["vorschlag"]["bereich"] == "arbeit"  # gehört zum Firmenpostfach
    assert konten["in_gebrauch"] == []
    assert [b["id"] for b in konten["bereiche"]] == ["arbeit", "privat"]

    antwort = client.put("/api/v1/konten/bereich", json={"zuordnung": {"mail-a": "privat", "mail-c": "arbeit"}})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["vorher"] == {"mail-a": None, "mail-c": None}
    assert daten["in_gebrauch"] == ["arbeit", "privat"]
    bestaetigt = {p["id"]: p for p in daten["postfaecher"]}
    assert bestaetigt["mail-a"]["bereich"] == "privat" and bestaetigt["mail-a"]["vorschlag"] is None
    # Rückgängig ist dieselbe Route mit dem Vorwert.
    zurueck = client.put("/api/v1/konten/bereich", json={"zuordnung": daten["vorher"]}).json()
    assert {p["id"]: p["bereich"] for p in zurueck["postfaecher"]}["mail-a"] is None
    # Bleibt nach einem Neustart: Es steht in der Datei.
    client.put("/api/v1/konten/bereich", json={"zuordnung": {"mail-c": "arbeit"}})
    assert config.load(tmp_path).konten["bereich_je_konto"] == {"mail-c": "arbeit"}


def test_bereich_unbekannt_oder_konto_unbekannt_wird_abgelehnt(tmp_path, monkeypatch) -> None:
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.put("/api/v1/konten/bereich", json={"zuordnung": {"mail-a": "garten"}}).status_code == 422
    assert client.put("/api/v1/konten/bereich", json={"zuordnung": {"mail-zz": "privat"}}).status_code == 404
    assert "bereich_je_konto" not in config.load(tmp_path).konten


def test_eigener_bereich_anlegen_und_zuordnen(tmp_path, monkeypatch) -> None:
    client = TestClient(_app(tmp_path, monkeypatch))
    neu = client.post("/api/v1/bereiche", json={"name": "Verein"}).json()
    assert neu["neu"] == "eigen-verein"
    assert neu["bereiche"][-1] == {"id": "eigen-verein", "name": "Verein", "eigen": True}
    # Gleicher Name: derselbe Bereich, kein zweiter.
    assert client.post("/api/v1/bereiche", json={"name": "verein"}).json()["neu"] == "eigen-verein"
    assert client.post("/api/v1/bereiche", json={"name": "  "}).status_code == 422
    assert client.put("/api/v1/konten/bereich",
                      json={"zuordnung": {"calendar-x": "eigen-verein"}}).json()["in_gebrauch"] == ["eigen-verein"]


def test_umbenennen_eindeutig_und_mit_vorwert(tmp_path, monkeypatch) -> None:
    client = TestClient(_app(tmp_path, monkeypatch))
    antwort = client.put("/api/v1/konten/name", json={"id": "mail-a", "name": "  Anna   privat "})
    assert antwort.status_code == 200
    assert antwort.json()["vorher"] == "anna.probe@gmail.com"
    assert {p["id"]: p["name"] for p in antwort.json()["postfaecher"]}["mail-a"] == "Anna privat"
    assert config.load(tmp_path).mail_accounts[0].label == "Anna privat"
    doppelt = client.put("/api/v1/konten/name", json={"id": "mail-b", "name": "anna PRIVAT"})
    assert doppelt.status_code == 409 and "anderes Postfach" in doppelt.json()["detail"]
    assert client.put("/api/v1/konten/name", json={"id": "mail-b", "name": " "}).status_code == 422
    assert client.put("/api/v1/konten/name", json={"id": "calendar-x", "name": "Büro"}).status_code == 200
    assert client.put("/api/v1/konten/name", json={"id": "mail-zz", "name": "X"}).status_code == 404
    assert client.put("/api/v1/konten/name", json={"id": "mac-calendar:A", "name": "X"}).status_code == 409


def test_ausgeblendete_kalender_bleiben_gespeichert(tmp_path, monkeypatch) -> None:
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.put("/api/v1/kalender/ausgeblendet",
                      json={"ids": ["calendar-x", "calendar-x", "mac-calendar:A"]}).json()["ausgeblendet"] == [
        "calendar-x", "mac-calendar:A"]
    assert client.get("/api/v1/konten").json()["ausgeblendet"] == ["calendar-x", "mac-calendar:A"]
    assert config.load(tmp_path).konten["kalender_ausgeblendet"] == ["calendar-x", "mac-calendar:A"]


def test_doppeltes_passwort_postfach_wird_erkannt(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MailConnector, "pruefe_anmeldung", lambda self, timeout=8.0: pytest.fail("nicht anmelden"))
    client = TestClient(_app(tmp_path, monkeypatch))
    antwort = client.post("/api/v1/integrations/mail", json={
        "label": "Gmail / Google Workspace", "imap_host": "IMAP.gmail.com", "user": "Anna.Probe@gmail.com",
        "sender": "anna.probe@gmail.com", "password": "nur-fuer-den-test"})
    assert antwort.status_code == 409
    assert antwort.json()["detail"] == "Dieses Postfach ist schon verbunden: anna.probe@gmail.com. Kingfisher liest es bereits."
    assert len(config.load(tmp_path).mail_accounts) == 3


def test_neues_postfach_bekommt_einen_eindeutigen_namen(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MailConnector, "pruefe_anmeldung", lambda self, timeout=8.0: None)
    client = TestClient(_app(tmp_path, monkeypatch))
    antwort = client.post("/api/v1/integrations/mail", json={
        "label": "Firma", "imap_host": "imap.gmail.com", "user": "dritte.probe@gmail.com",
        "sender": "dritte.probe@gmail.com", "password": "nur-fuer-den-test"})
    assert antwort.status_code == 201
    assert antwort.json()["mail_accounts"][-1]["label"] == "dritte.probe@gmail.com"


def test_eindeutiger_name_faellt_auf_adresse_und_zahl_zurueck() -> None:
    assert konten_routes.eindeutiger_name(["A"], "B", "b@x.example") == "B"
    assert konten_routes.eindeutiger_name(["B"], "B", "b@x.example") == "b@x.example"
    assert konten_routes.eindeutiger_name(["B", "b@x.example"], "B", "b@x.example") == "b@x.example (2)"


# -- Stand ------------------------------------------------------------------------------------------------------------


def test_stand_in_einem_satz() -> None:
    jetzt = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    vor4 = (jetzt - timedelta(minutes=4)).isoformat()
    gut = konten_routes.kurzer_mailstand({"zustand": "aktuell", "satz": "…", "zuletzt": vor4}, "Firma", jetzt)
    assert gut == {"satz": "Zuletzt gelesen vor 4 Min.", "art": "gut", "verweis": None}
    fehler = konten_routes.kurzer_mailstand({
        "zustand": "fehler", "verweis": "zugaenge", "zuletzt": None,
        "satz": "Postfach Firma lässt Kingfisher nicht mehr hinein: Die Anmeldung ist abgelaufen. Melde dich neu an."},
        "Firma", jetzt)
    assert fehler["art"] == "fehler" and fehler["verweis"] == "zugaenge"
    assert fehler["satz"].startswith("Lässt Kingfisher nicht mehr hinein")
    liest = konten_routes.kurzer_mailstand({"zustand": "liest", "satz": "Postfach Firma wird gelesen: 3 von 9 Mails.",
                                             "zuletzt": None}, "Firma", jetzt)
    assert liest == {"satz": "Wird gelesen: 3 von 9 Mails.", "art": "laeuft", "verweis": None}
    assert konten_routes.vor(jetzt - timedelta(seconds=10), jetzt) == "gerade eben"
    assert konten_routes.vor(jetzt - timedelta(hours=2), jetzt) == "vor 2 Std."


def test_postfach_und_kalender_zeigen_ihren_stand(tmp_path, monkeypatch) -> None:
    jetzt = datetime.now(timezone.utc)
    app = _app(tmp_path, monkeypatch, mail_sync_status={
        "mail-c": {"last_success": (jetzt - timedelta(minutes=4)).isoformat(), "last_report": {"recorded": 0}}})
    # Ein Kalender liest, der andere scheitert: beides steht beim jeweiligen Kalender.
    class Gut:
        def events(self, days=7, at=None):
            return [Event(uid="t1", summary="Messe", start=jetzt + timedelta(hours=1), end=jetzt + timedelta(hours=2))]

    class Kaputt:
        def events(self, days=7, at=None):
            raise RuntimeError("geht nicht")
    app.state.calendar = CalendarCollection([NamedCalendar("calendar-arbeit", "Arbeit", Gut()),
                                             NamedCalendar("calendar-x", "Kalender", Kaputt())])
    monkeypatch.setattr("icarus_memory.server._integration_secret", lambda app, kind, kennung: "geheim")
    monkeypatch.setattr("icarus_memory.mail_stand._verbunden", lambda app, konto: True)
    client = TestClient(app)
    bereiche.setze_bereich(app.state.settings, "calendar-arbeit", "arbeit")
    termine = client.get("/api/v1/calendar", params={"days": 2}).json()["items"]
    assert [t["bereich"] for t in termine if t["summary"] == "Messe"] == ["arbeit"]
    konten = client.get("/api/v1/konten").json()
    postfach = {p["id"]: p for p in konten["postfaecher"]}["mail-c"]
    assert postfach["stand"]["satz"] in {"Zuletzt gelesen vor 4 Min.", "Zuletzt gelesen vor 5 Min."}
    kalender = {k["id"]: k for k in konten["kalender"]}
    assert kalender["calendar-arbeit"]["stand"] == {"satz": "Zuletzt gelesen gerade eben.", "art": "gut", "verweis": None}
    assert kalender["calendar-x"]["stand"]["art"] == "fehler"
    assert "versucht es von selbst wieder" in kalender["calendar-x"]["stand"]["satz"]


# -- Felder in den Antworten ------------------------------------------------------------------------------------------


def test_aufgaben_projekte_und_mails_tragen_ihren_bereich(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    client = TestClient(app)
    client.put("/api/v1/konten/bereich", json={"zuordnung": {"mail-a": "privat", "mail-c": "arbeit"}})
    projekt = app.state.workspace.add_project("Messe", Provenance(SourceType.USER_STATED))
    mail = _mail(app, "mail-c", 1, projekt.id)
    _mail(app, "mail-a", 2)
    app.state.tasks.add("Stand buchen", Provenance(SourceType.USER_STATED, source_ref=f"episode:{mail.id}"))
    app.state.tasks.add("Ohne Quelle", Provenance(SourceType.USER_STATED), project_id=projekt.id)
    aufgaben = client.get("/api/v1/tasks").json()["tasks"]
    assert {a["title"]: a["bereich"] for a in aufgaben} == {"Stand buchen": "arbeit", "Ohne Quelle": "arbeit"}
    assert {p["name"]: p["bereich"] for p in client.get("/api/v1/projects").json()} == {"Messe": "arbeit"}
    mails = client.get("/api/v1/local-mail").json()["items"]
    assert sorted((m["account_id"], m["bereich"]) for m in mails) == [("mail-a", "privat"), ("mail-c", "arbeit")]
