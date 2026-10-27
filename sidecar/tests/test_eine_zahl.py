"""Eine Zahl je Begriff (Persona-Prüfung, Paket Z1, 27.10.2026).

Zusicherungen:
1. „Braucht dich heute“ ist eine Regel (`zaehlung.heute_dran`): offen, bei dir (nicht „wartet auf“), fällig heute oder
   früher nach dem Kalendertag des Nutzers. Wartendes, Erledigtes, Morgiges zählt nicht.
2. Das Briefing zählt damit: `zaehlung.aufgaben` ist genau diese Zahl, auch wenn der Punkt „Heute sind N Aufgaben
   fällig“ hinter die drei sichtbaren Punkte rutscht; `weitere` zählt die übrigen Punkte, auch die abgeschnittenen.
   Eine wartende, überfällige Aufgabe steht in keinem der beiden Aufgabenpunkte.
3. Heute (`/api/v1/morning-briefing`) und Aufgaben (`/api/v1/tasks`, `heute_dran`) nennen dieselbe Zahl, und sie ist
   die Zahl der Zeilen unter „Überfällig“ und „Heute“ in der Liste.
4. Der Bereichsfilter filtert im Sidecar: Zahl am Segment (`total`), Liste und Projektüberblick sind dieselbe Auswahl;
   über einer leeren Liste steht keine „1“.
Nur synthetische Daten.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, bereiche, briefing, config, morning, zaehlung
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeStore
from icarus_memory import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

BERLIN = timezone(timedelta(hours=2))
JETZT = datetime(2026, 9, 29, 7, 35, tzinfo=BERLIN)


def aufgabe(kennung: str, *, due: datetime | str | None, status: str = "open", wartet: str | None = None,
            overdue: bool | None = None) -> dict:
    wert = due.isoformat() if isinstance(due, datetime) else due
    return {"id": kennung, "title": f"Aufgabe {kennung}", "due": wert, "status": status, "wartet_auf": wartet,
            "overdue": overdue if overdue is not None else bool(isinstance(due, datetime) and due < JETZT)}


# -- 1. Die Regel ---------------------------------------------------------------------------------------------------


def test_braucht_dich_heute_ist_offen_bei_dir_und_heute_oder_frueher_faellig() -> None:
    aufgaben = [
        aufgabe("gestern", due=JETZT - timedelta(days=1)),
        aufgabe("heute-frueh", due=JETZT.replace(hour=6)),
        aufgabe("heute-abend", due=JETZT.replace(hour=23, minute=59)),
        aufgabe("datum", due="2026-09-29"),
        aufgabe("utc-heute", due="2026-09-28T23:30:00+00:00"),  # 01:30 in Berlin
        aufgabe("morgen", due=JETZT + timedelta(days=1)),
        aufgabe("ohne", due=None),
        aufgabe("wartet", due=JETZT - timedelta(days=2), wartet="Uwe"),
        aufgabe("erledigt", due=JETZT - timedelta(days=2), status="done"),
        aufgabe("verworfen", due=JETZT - timedelta(days=2), status="dropped"),
    ]
    dran = [a["id"] for a in zaehlung.heute_dran(aufgaben, JETZT)]
    assert dran == ["gestern", "heute-frueh", "heute-abend", "datum", "utc-heute"]
    assert [a["id"] for a in aufgaben if zaehlung.ist_ueberfaellig(a, JETZT)] == ["gestern"]


# -- 2. Das Briefing zählt damit -------------------------------------------------------------------------------------


def _daten(aufgaben: list[dict]) -> dict:
    return {"tasks": {"items": aufgaben, "overdue": 0}, "calendar": {"items": []}, "mail": {"items": [], "unread": 0},
            "episodes": {"pending": 0}, "memory": {"count": 0, "recent": []}}


def _lage_der_assistentin() -> tuple[dict, list[dict]]:
    """Wie bei der Persona: sieben überfällige, eine heute fällige, eine wartende, dazu ein Termin und ein Vorschlag."""
    aufgaben = [aufgabe(f"u{i}", due=JETZT - timedelta(days=i + 1)) for i in range(7)]
    aufgaben += [aufgabe("h1", due=JETZT.replace(hour=23, minute=59)),
                 aufgabe("w1", due=JETZT - timedelta(days=3), wartet="Uwe Hofmann")]
    daten = _daten(aufgaben)
    daten["calendar"]["items"] = [{"uid": "e1", "summary": "Lenkungskreis", "start": (JETZT + timedelta(hours=2)).isoformat()}]
    daten["task_candidates"] = {"items": [{"id": "p1", "statement": "Folien schicken", "sender": "Petra"}], "pending": 1}
    return daten, aufgaben


def test_briefing_zaehlt_aufgaben_mit_der_einen_regel_auch_hinter_den_drei_punkten() -> None:
    daten, aufgaben = _lage_der_assistentin()
    b = briefing.erstelle(daten, jetzt=JETZT)
    assert len(b.punkte) == briefing.MAX_PUNKTE
    # „Heute sind … fällig“ ist hinter die drei sichtbaren Punkte gerutscht; gezählt wird es trotzdem.
    assert all("Heute fällig" not in p.text for p in b.punkte)
    assert b.zaehlung == {"aufgaben": 8, "weitere": 2}
    assert b.zaehlung["aufgaben"] == len(zaehlung.heute_dran(aufgaben, JETZT))
    assert b.to_dict()["zaehlung"] == {"aufgaben": 8, "weitere": 2}


def test_wartende_aufgabe_steht_in_keinem_aufgabenpunkt() -> None:
    daten = _daten([aufgabe("w", due=JETZT - timedelta(days=3), wartet="Uwe"),
                    aufgabe("w2", due=JETZT.replace(hour=20), wartet="Uwe")])
    b = briefing.erstelle(daten, jetzt=JETZT)
    assert b.punkte == []
    assert b.zaehlung == {"aufgaben": 0, "weitere": 0}


def test_heute_faellig_als_ein_punkt_zaehlt_jede_aufgabe() -> None:
    daten = _daten([aufgabe("a", due=JETZT.replace(hour=9)), aufgabe("b", due=JETZT.replace(hour=18)),
                    aufgabe("c", due=JETZT - timedelta(days=4))])
    b = briefing.erstelle(daten, jetzt=JETZT)
    gruppe = next(p for p in b.punkte if p.text.startswith("Heute sind"))
    assert gruppe.text == "Heute sind 2 Aufgaben fällig." and gruppe.anzahl == 2
    ueber = next(p for p in b.punkte if p.text.startswith("Seit dem"))
    assert ueber.anzahl == 1
    assert b.zaehlung == {"aufgaben": 3, "weitere": 0}
    assert [p["anzahl"] for p in b.to_dict()["punkte"]] == [p.anzahl for p in b.punkte]


def test_verlaufspruefung_einer_faelligen_aufgabe_zaehlt_nicht_doppelt() -> None:
    erste = aufgabe("u1", due=JETZT - timedelta(days=5))
    zweite = aufgabe("u2", due=JETZT - timedelta(days=2))
    zweite["source_review"] = {"reason": "Eine neue Mail im Verlauf."}
    spaeter = aufgabe("z", due=JETZT + timedelta(days=9))
    spaeter["source_review"] = {"reason": "Eine neue Mail im Verlauf."}
    b = briefing.erstelle(_daten([erste, zweite, spaeter]), jetzt=JETZT)
    # u2 gehört zu den Aufgaben von heute, z ist ein weiterer Punkt.
    assert b.zaehlung == {"aufgaben": 2, "weitere": 1}


def test_heute_traegt_anzahl_und_zaehlung_weiter() -> None:
    daten, _ = _lage_der_assistentin()
    daten["briefing"] = briefing.erstelle(daten, jetzt=JETZT).to_dict()
    daten["projects"] = {"items": []}
    daten["knowledge"] = {"clarifications": [{"id": "k1"}]}
    ergebnis = morning.compose(daten, now=JETZT, target=JETZT.date(), wetter=lambda: None)
    # Die Klärung ist ein weiterer Punkt; die sichtbaren Zeilen tragen, wofür sie stehen.
    assert ergebnis["braucht_dich"] == {"aufgaben": 8, "weitere": 3}
    assert all(isinstance(item["anzahl"], int) and item["anzahl"] >= 1 for item in ergebnis["needs_you"])


# -- 3. und 4. Über die Routen ---------------------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KINGFISHER_TIMEZONE", "Europe/Berlin")
    monkeypatch.delenv("ICARUS_SIDECAR_TOKEN", raising=False)
    (tmp_path / config.DATEINAME).write_text(json.dumps({"mail_accounts": [
        {"id": "mail-arbeit", "label": "Firma", "imap_host": "imap.firma.example", "user": "lea@firma.example",
         "sender": "lea@firma.example"},
        {"id": "mail-privat", "label": "Privat", "imap_host": "imap.privat.example", "user": "lea@privat.example",
         "sender": "lea@privat.example"}]}), encoding="utf-8")
    anwendung = create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"), audit=AuditLog(tmp_path / "audit.sqlite3"),
        tasks=TaskStore(tmp_path / "tasks.sqlite3"), workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
        episodes=EpisodeStore(tmp_path / "episodes.sqlite3"))
    bereiche.setze_bereich(anwendung.state.settings, "mail-arbeit", "arbeit")
    bereiche.setze_bereich(anwendung.state.settings, "mail-privat", "privat")
    return anwendung


def _mail(app, konto: str, nummer: int, project_id: str | None = None):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, f"Betreff {nummer}", f"Text {nummer}",
        Provenance(source_type=SourceType.EMAIL, source_ref=f"{konto}:<z{nummer}@probe.example>"),
        occurred_at=datetime(2026, 10, 20, 9, nummer, tzinfo=timezone.utc))
    if project_id:
        app.state.episodes.link_project(episode.id, project_id)
    return episode


def _bestand(app) -> dict[str, str]:
    jetzt = datetime.now(timezone.utc)
    hand = Provenance(SourceType.USER_STATED)
    tasks = app.state.tasks
    projekt = app.state.workspace.add_project("Nordlicht", hand)
    for nummer in range(3):
        _mail(app, "mail-arbeit", nummer, projekt.id)
    privat_mail = _mail(app, "mail-privat", 9)
    for tage in (1, 3, 8):
        tasks.add(f"Überfällig {tage}", hand, due=jetzt - timedelta(days=tage))
    tasks.add("Privat überfällig", Provenance(SourceType.USER_STATED, source_ref=f"episode:{privat_mail.id}"),
              due=jetzt - timedelta(days=2))
    tasks.add("Projekt offen", hand, project_id=projekt.id, due=jetzt + timedelta(days=4))
    w = tasks.add("Wartet überfällig", hand, due=jetzt - timedelta(days=2))
    tasks.warten_auf(w.id, "Uwe")
    erledigt = tasks.add("Erledigt", hand, due=jetzt - timedelta(days=1))
    tasks.complete(erledigt.id)
    return {"projekt": projekt.id}


def test_heute_und_aufgaben_nennen_dieselbe_zahl(app) -> None:
    _bestand(app)
    with TestClient(app) as client:
        heute = client.get("/api/v1/morning-briefing", params={"post": "false"}).json()
        liste = client.get("/api/v1/tasks", params={"view": "mine", "limit": 200}).json()
    jetzt = datetime.now(BERLIN)
    in_der_liste = len(zaehlung.heute_dran(liste["tasks"], jetzt))
    assert heute["braucht_dich"]["aufgaben"] == liste["heute_dran"] == in_der_liste == 4


def test_heute_dran_zaehlt_ganze_auswahl_nicht_die_seite(app) -> None:
    _bestand(app)
    with TestClient(app) as client:
        seite = client.get("/api/v1/tasks", params={"view": "mine", "limit": 1}).json()
        privat = client.get("/api/v1/tasks", params={"view": "mine", "bereich": "privat"}).json()
        warten = client.get("/api/v1/tasks", params={"view": "waiting"}).json()
    assert len(seite["tasks"]) == 1 and seite["heute_dran"] == 4
    assert privat["heute_dran"] == 1
    assert "heute_dran" not in warten


def test_bereichsfilter_zaehlt_und_listet_dieselbe_auswahl(app) -> None:
    ids = _bestand(app)
    with TestClient(app) as client:
        for bereich in ("alle", "arbeit", "privat"):
            for view in ("mine", "waiting", "done"):
                for projekt in ("", ids["projekt"]):
                    params = {"view": view, "limit": 200, "bereich": bereich, **({"project_id": projekt} if projekt else {})}
                    antwort = client.get("/api/v1/tasks", params=params).json()
                    assert antwort["total"] == len(antwort["tasks"]), params
                    assert all(bereich == "alle" or t["bereich"] == bereich for t in antwort["tasks"]), params
        # Projekt Nordlicht ist Arbeit: unter „Privat“ zählt es nichts, und der Überblick sagt dasselbe.
        privat = client.get("/api/v1/tasks", params={"view": "mine", "project_id": ids["projekt"], "bereich": "privat"}).json()
        ueberblick = client.get(f"/api/v1/projects/{ids['projekt']}/task-overview", params={"bereich": "privat"}).json()
        arbeit = client.get(f"/api/v1/projects/{ids['projekt']}/task-overview", params={"bereich": "arbeit"}).json()
        ganz = client.get(f"/api/v1/projects/{ids['projekt']}/task-overview").json()
    assert privat["total"] == 0 and privat["tasks"] == []
    assert ueberblick["counts"]["mine"] == 0 and ueberblick["next_tasks"] == []
    assert arbeit["counts"] == ganz["counts"] and arbeit["counts"]["mine"] == 1


def test_bereich_mit_blaettern_bleibt_dieselbe_auswahl(app) -> None:
    _bestand(app)
    with TestClient(app) as client:
        erste = client.get("/api/v1/tasks", params={"view": "mine", "limit": 2, "bereich": "alle"}).json()
        zweite = client.get("/api/v1/tasks", params={"view": "mine", "limit": 2, "bereich": "alle",
                                                      "cursor": erste["next_cursor"]}).json()
        falsch = client.get("/api/v1/tasks", params={"view": "mine", "limit": 2, "bereich": "privat",
                                                      "cursor": erste["next_cursor"]})
    assert erste["total"] == zweite["total"] == 5
    assert not {t["id"] for t in erste["tasks"]} & {t["id"] for t in zweite["tasks"]}
    # Ein Cursor gilt nur für die Auswahl, aus der er stammt.
    assert falsch.status_code == 409
