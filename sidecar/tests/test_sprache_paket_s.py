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


# -- Befund 1: Kalender-Abo nicht abrufbar, in einem Satz -------------------------------------------------------------


def test_abo_ohne_freigabe_sagt_was_los_ist_und_was_zu_tun_ist() -> None:
    import httpx
    import pytest

    from icarus_memory.connectors.calendar import CalendarError
    from icarus_memory.connectors.collections import ICalendarSubscription

    def antwort(status):
        return httpx.MockTransport(lambda request: httpx.Response(status, text="nein"))

    for status, teil in ((403, "nicht mehr freigegeben"), (401, "nicht mehr freigegeben"), (404, "gibt es ihn nicht mehr"),
                         (503, "versucht es von selbst wieder")):
        with pytest.raises(CalendarError) as fehler:
            ICalendarSubscription("https://kalender.example/abo.ics", transport=antwort(status)).events()
        satz = str(fehler.value)
        assert satz.startswith("Der Kalender lässt sich") and teil in satz, satz
        for fachwort in ("iCalendar", "Forbidden", "403", "HTTP", "Abo nicht erreichbar"):
            assert fachwort not in satz, (fachwort, satz)

    def kein_netz(request):
        raise httpx.ConnectError("keine Verbindung")
    with pytest.raises(CalendarError) as fehler:
        ICalendarSubscription("https://kalender.example/abo.ics", transport=httpx.MockTransport(kein_netz)).events()
    assert "nicht erreichbar" in str(fehler.value) and "keine Verbindung" not in str(fehler.value)


# -- Befund 2: Kalendername ohne Server ------------------------------------------------------------------------------


def test_ein_gefundener_kalender_heisst_nach_seinem_namen_nicht_nach_dem_server() -> None:
    from icarus_memory.kalender_anmeldung import kalender_name
    assert kalender_name("", "Privat", "lena@eigene-domain.example", []) == "Privat"
    assert kalender_name("GMX", "Privat", "lena@gmx.de", []) == "GMX: Privat"
    # Schon vergeben (zweites Konto mit „Privat“): die Adresse dahinter, nie der Server.
    zweiter = kalender_name("", "Privat", "praxis@praxis-fehr.example", ["privat"])
    assert zweiter == "Privat · praxis@praxis-fehr.example"
    assert kalender_name("", "  ", "a@b.example", []) == "Kalender"


# -- Befund 6: Texte ------------------------------------------------------------------------------------------------


def test_der_gruss_folgt_der_tageszeit_in_der_zeitzone_des_nutzers() -> None:
    from datetime import date
    from zoneinfo import ZoneInfo

    from icarus_memory.morning import compose, gruss
    leer = {"briefing": {"punkte": []}, "calendar": {"items": []}, "mail": {"items": []}, "tasks": {}, "episodes": {},
            "proposals": {}}
    # 18:47 UTC ist am 26.10.2026 in Berlin 19:47: Abend, nicht „Guten Tag“.
    abends = datetime(2026, 10, 26, 18, 47, tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Berlin"))
    assert abends.hour == 19
    assert compose(leer, now=abends, target=date(2026, 10, 26), nutzername="Helga")["greeting"] == "Guten Abend, Helga."
    assert [gruss(h) for h in (0, 3, 4, 11, 12, 17, 18, 23)] == [
        "Guten Abend", "Guten Abend", "Guten Morgen", "Guten Morgen", "Guten Tag", "Guten Tag", "Guten Abend", "Guten Abend"]


def test_heute_gruesst_ohne_angabe_in_der_eingestellten_zeitzone(tmp_path, monkeypatch) -> None:
    """Der Container läuft in UTC; der Gruß richtet sich nach der Zeitzone des Nutzers."""
    from zoneinfo import ZoneInfo

    from icarus_memory.morning import gruss
    monkeypatch.setenv("KINGFISHER_TIMEZONE", "Pacific/Auckland")
    app = _app(tmp_path, monkeypatch)
    erwartet = gruss(datetime.now(timezone.utc).astimezone(ZoneInfo("Pacific/Auckland")).hour)
    antwort = TestClient(app).get("/api/v1/morning-briefing?post=false").json()["greeting"]
    assert antwort.startswith(erwartet), (antwort, erwartet)


def test_zwei_klaerungen_auf_heute_tragen_je_einen_eigenen_titel_ohne_namen_und_wert() -> None:
    from datetime import date

    from icarus_memory.morning import compose, klaerung_titel
    leer = {"briefing": {"punkte": []}, "calendar": {"items": []}, "mail": {"items": []}, "tasks": {}, "episodes": {},
            "proposals": {}}
    leer["knowledge"] = {"clarifications": [{"id": "c:1", "merkmal": "rolle"}, {"id": "c:2", "merkmal": "address"},
                                            {"id": "c:3", "merkmal": "Lieferanschrift laut Kranz GmbH"},
                                            {"id": "c:4", "merkmal": "x_7f"}]}
    jetzt = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)
    titel = [p["title"] for p in compose(leer, now=jetzt, target=date(2026, 10, 26))["needs_you"]
             if p["source"] == "knowledge"]
    alle = [klaerung_titel(m) for m in ("rolle", "address", "Lieferanschrift laut Kranz GmbH", "x_7f")]
    assert alle[:2] == ["Angabe klären: Rolle", "Angabe klären: Anschrift"]
    # Ein freies Merkmal kann aus der fremden Quelle stammen: es steht nicht auf Heute.
    assert alle[2] == alle[3] == "Gedächtnis klären"
    # Heute zeigt drei; gleiche Titel werden durchgezählt.
    assert len(set(titel)) == len(titel), titel
    assert all("Kranz" not in t for t in titel)


# -- Befund 7: Aufgabensuche findet Projektnamen ---------------------------------------------------------------------


def test_die_aufgabensuche_findet_auch_den_namen_des_projekts(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    nordlicht = app.state.workspace.add_project("Restrukturierung Nordlicht", Provenance(SourceType.USER_STATED))
    weiss = app.state.workspace.add_project("Interim-Controlling Weiss", Provenance(SourceType.USER_STATED))
    app.state.tasks.add("Folien zur Kostenanalyse schicken", Provenance(SourceType.USER_STATED), project_id=nordlicht.id)
    app.state.tasks.add("Interviews planen", Provenance(SourceType.USER_STATED), project_id=nordlicht.id)
    app.state.tasks.add("Monatsabschluss prüfen", Provenance(SourceType.USER_STATED), project_id=weiss.id)
    app.state.tasks.add("Nordlicht-Rechnung ablegen", Provenance(SourceType.USER_STATED))
    client = TestClient(app)

    def titel(q):
        antwort = client.get("/api/v1/tasks", params={"q": q})
        assert antwort.status_code == 200, antwort.text
        return sorted(t["title"] for t in antwort.json()["tasks"])

    assert titel("nordlicht") == ["Folien zur Kostenanalyse schicken", "Interviews planen", "Nordlicht-Rechnung ablegen"]
    assert titel("Weiss") == ["Monatsabschluss prüfen"]
    # Mehrere Wörter: jedes muss passen, im Titel oder im Projekt.
    assert titel("nordlicht folien") == ["Folien zur Kostenanalyse schicken"]
    # Gegenrichtung: ein Wort, das weder im Titel noch im Projekt steht, findet nichts.
    assert titel("lahnwerke") == []
    assert client.get("/api/v1/tasks", params={"q": "nordlicht"}).json()["total"] == 3


def test_mehr_unter_neu_eingegangen_fuehrt_zu_den_neuen_mails() -> None:
    from datetime import date, timedelta

    from icarus_memory.morning import compose
    jetzt = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)

    def dashboard(mails: int, quellen: int) -> dict:
        return {"briefing": {"punkte": []}, "calendar": {"items": []}, "tasks": {}, "episodes": {}, "proposals": {},
                "mail": {"items": [{"uid": f"m{i}", "subject": f"Mail {i}", "unread": True,
                                    "date": (jetzt - timedelta(minutes=10 + i)).isoformat()} for i in range(mails)]},
                "working_memory": {"items": [{"episode_id": f"e{i}", "title": f"Quelle {i}", "kinds": [],
                                              "source_type": "email", "source_ref": f"mail-a:<q{i}@x.example>",
                                              "occurred_at": (jetzt - timedelta(minutes=30 + i)).isoformat(),
                                              "recorded_at": jetzt.isoformat()} for i in range(quellen)]}}

    assert compose(dashboard(5, 0), now=jetzt, target=date(2026, 10, 26))["neu_mehr"] == "nachrichten"
    assert compose(dashboard(5, 4), now=jetzt, target=date(2026, 10, 26))["neu_mehr"] == "nachrichten"
    assert compose(dashboard(1, 4), now=jetzt, target=date(2026, 10, 26))["neu_mehr"] == "gedaechtnis"
    # Genau drei Mails, keine weiteren Quellen: kein „Mehr“.
    assert compose(dashboard(3, 0), now=jetzt, target=date(2026, 10, 26))["neu_mehr"] is None


# -- Offener Rest aus D: eingetragene öffentliche Seiten unter „Was Kingfisher darf“ ---------------------------------


def test_eingetragene_oeffentliche_seiten_ruft_der_zeitplan_nur_mit_schalter_ab(tmp_path, monkeypatch) -> None:
    from icarus_memory import world_monitor
    app = _app(tmp_path, monkeypatch)
    app.state.settings.schedule.enabled = True
    app.state.settings.world_sources.append({
        "id": "world-test", "url": "https://example.com/feed", "label": "Testquelle", "topics": [], "enabled": True,
        "episode_id": None, "last_success": None, "error": None, "truncated": False})
    abrufe: list[str] = []

    def abruf(url):
        abrufe.append(url)
        raise OSError("Probe: kein Netz")
    monkeypatch.setattr(world_monitor, "fetch_public_text", abruf)
    client = TestClient(app)
    assert client.get("/api/v1/darf/quellen").json() == {"an": True, "anzahl": 1}
    # Vorgabe an: wer eine Seite einträgt, will sie lesen.
    client.post("/schedule/run")
    assert abrufe == ["https://example.com/feed"]
    # Aus: Der Zeitplan ruft nichts mehr ab, und es bleibt nach dem Neustart aus.
    assert client.put("/api/v1/darf/quellen", json={"an": False}).json() == {"an": False, "anzahl": 1}
    jobs = {job["name"] for job in client.post("/schedule/run").json()["jobs"]}
    assert abrufe == ["https://example.com/feed"] and "world:world-test" not in jobs
    assert config.load(tmp_path).quellen_abruf == "aus"
    # Wieder an: der nächste Lauf ruft wieder ab.
    client.put("/api/v1/darf/quellen", json={"an": True})
    client.post("/schedule/run")
    assert len(abrufe) == 2


# -- Offener Rest aus A-I: „Viertel nach“ und „Viertel vor“ in der Satzprüfung -----------------------------------------


import pytest  # noqa: E402

from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen  # noqa: E402

_QZ = datetime(2026, 10, 23, 19, 48, tzinfo=timezone.utc)


def _urteil(satz: str, quelle: str):
    return satz_pruefen(Satz(satz, ("q",)), {"q": Beleg("q", quelle, _QZ)})


@pytest.mark.parametrize(("quelle", "satz"), [
    ("Wir treffen uns um Viertel nach sieben abends am Tor.", "Wir treffen uns um 19:15 Uhr am Tor."),
    ("Wir treffen uns um 19:15 Uhr am Tor.", "Wir treffen uns um Viertel nach sieben abends am Tor."),
    ("Abfahrt um Viertel vor acht morgens am Tor.", "Die Abfahrt ist um 7:45 Uhr am Tor."),
    ("Die Abfahrt ist um 7:45 Uhr am Tor.", "Abfahrt um Viertel vor acht morgens am Tor."),
    # Ohne Tageszeit: nur, wenn der Beleg genau eine Lesart trägt oder denselben Wortlaut.
    ("Wir treffen uns um 18:15 Uhr am Tor.", "Wir treffen uns um Viertel nach sechs am Tor."),
    ("Wir treffen uns um Viertel vor neun am Tor.", "Wir treffen uns um Viertel vor neun am Tor."),
    ("Wir treffen uns um 12:45 Uhr am Tor.", "Wir treffen uns um Viertel vor eins am Tor."),
])
def test_viertel_nach_und_viertel_vor_bestehen_wo_eindeutig(quelle, satz) -> None:
    urteil = _urteil(satz, quelle)
    assert urteil.bestanden, urteil


@pytest.mark.parametrize(("quelle", "satz"), [
    # Gegenrichtung: eine falsche Zeit fällt weiter.
    ("Wir treffen uns um 19:15 Uhr am Tor.", "Wir treffen uns um Viertel vor sieben abends am Tor."),
    ("Wir treffen uns um 19:45 Uhr am Tor.", "Wir treffen uns um Viertel nach sieben abends am Tor."),
    ("Wir treffen uns um Viertel nach sieben abends am Tor.", "Wir treffen uns um 7:15 Uhr am Tor."),
    ("Wir treffen uns um Viertel nach sieben am Tor.", "Wir treffen uns um 19:15 Uhr am Tor."),
    ("Wir treffen uns um 18:15 Uhr und um 6:15 Uhr am Tor.", "Wir treffen uns um Viertel nach sechs am Tor."),
    ("Wir treffen uns um 18:30 Uhr am Tor.", "Wir treffen uns um Viertel nach sechs am Tor."),
])
def test_falsche_viertelstunde_faellt_weiter(quelle, satz) -> None:
    urteil = _urteil(satz, quelle)
    assert not urteil.bestanden
    # Verworfen an der Uhrzeit, nicht an etwas anderem (sonst fiele der Satz aus dem falschen Grund).
    assert urteil.gruende and not any("gibt es nicht" in g for g in urteil.gruende), urteil.gruende


# -- Offener Rest aus A-II: „zuletzt“ ist höchstens jetzt ------------------------------------------------------------


def test_zuletzt_unter_mit_wem_zaehlt_keine_kuenftigen_termine(tmp_path) -> None:
    from datetime import timedelta

    from icarus_memory.vorbereitung import teilnehmer
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    jetzt = datetime.now(timezone.utc)
    anna = "Anna Keller <anna.keller@kanzlei.example>"
    for titel, zeit in (("Mail von Anna", jetzt - timedelta(days=3)), ("Termin im Dezember", jetzt + timedelta(days=47))):
        episodes.record(EpisodeKind.MESSAGE if titel.startswith("Mail") else EpisodeKind.EVENT, titel, titel,
                        Provenance(source_type=SourceType.EMAIL if titel.startswith("Mail") else SourceType.CALENDAR,
                                   source_ref=f"probe:{titel}"), participants=[anna], occurred_at=zeit)
    index = episodes.participants_for_addresses(["anna.keller@kanzlei.example"])
    zeile = teilnehmer([anna], index=index)[0]
    assert zeile["kontakte"] == 2, "der künftige Termin bleibt eine Quelle"
    zuletzt = datetime.fromisoformat(zeile["zuletzt"])
    assert zuletzt <= jetzt and (jetzt - zuletzt) < timedelta(days=4), zeile["zuletzt"]
    # Nur Künftiges: kein „zuletzt“.
    bert = "Bert Probe <bert@kanzlei.example>"
    episodes.record(EpisodeKind.EVENT, "Nur künftig", "Nur künftig", Provenance(source_type=SourceType.CALENDAR,
                    source_ref="probe:kuenftig"), participants=[bert], occurred_at=jetzt + timedelta(days=5))
    assert teilnehmer([bert], index=episodes.participants_for_addresses(["bert@kanzlei.example"]))[0]["zuletzt"] is None
