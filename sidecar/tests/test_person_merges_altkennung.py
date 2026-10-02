"""Zusammenführungen aus der Zeit vor C3 (Kennung aus dem Teilnehmertext) gelten weiter.

Zusicherungen: Ein Bestand, den der Nutzer vor der Umstellung zusammengeführt hat,
zeigt die Zusammenführung danach mit ihren Mitgliedern (jetzt Adress-Kennungen).
Die alte Kennung bleibt am Mitglied gespeichert. Die Übertragung ist idempotent
und rührt Aufgehobenes nicht an. Was sich nicht abbilden lässt, bleibt sichtbar
als „nicht mehr zuordenbar“. Aufheben bleibt möglich und stellt den Stand vor der
Zusammenführung her.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from icarus_memory import graph, person_merge_altkennung as alt
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.backends import MemoryBackend
from icarus_memory.store import SelfModelStore
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

AT = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
ALEX_CATERING = "Alex Winter <alex@winter-catering.example>"
ALEX_INSTITUT = "Alex Winter <alex.winter@ifeh-hessen.example>"


@pytest.fixture
def bestand(tmp_path):
    """Ein Bestand aus der Zeit vor C3: Mails nur mit Teilnehmertexten, ohne Empfängerrollen."""
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    knowledge = ClaimStore(tmp_path / "knowledge.sqlite3")
    for nummer, texte in enumerate([[ALEX_CATERING], [ALEX_INSTITUT], ["Keller, Anna <anna@x.example>"],
                                    ["Anna Keller <anna@x.example>"], ["Herr Roth"]]):
        episodes.record(EpisodeKind.MESSAGE, f"Betreff {nummer}", f"Text {nummer}",
                        Provenance(SourceType.EMAIL, f"k:{nummer}", AT), occurred_at=AT, participants=texte)
    yield SimpleNamespace(episodes=episodes, knowledge=knowledge, tmp=tmp_path)
    episodes.close()
    knowledge.close()



def alte_kennung(text):
    """Was die Namensprojektion vor C3 als Kennung vergab."""
    return graph.person_id(text)


def alt_gespeichert(bestand, texte, label="Alex Winter"):
    """Legt eine Zusammenführung so ab, wie sie vor C3 gespeichert wurde: Mitglieder mit alten Kennungen."""
    mitglieder = [{"id": alte_kennung(t), "kind": "person", "label": t,
                   "attributes": {"identity_resolution": "exact_normalized_name"}} for t in texte]
    return bestand.knowledge.person_merges.confirm({"label": label, "members": mitglieder}, confirmed=True)


def bauen(bestand, **kw):
    """Der Graph wie beim Lesen der Personenansicht (mit Zusammenführungen)."""
    return graph.build(episodes=bestand.episodes, workspace=WorkspaceStore(bestand.tmp / "workspace.sqlite3"),
                       tasks=TaskStore(bestand.tmp / "tasks.sqlite3"),
                       store=SelfModelStore(MemoryBackend(), subject_id="local"),
                       knowledge=bestand.knowledge, at=AT, **kw)


def personen(g):
    return [n for n in g.nodes if n.kind == "person"]


def test_alte_zusammenfuehrung_zeigt_nach_der_umstellung_ihre_mitglieder(bestand):
    merge = alt_gespeichert(bestand, [ALEX_CATERING, ALEX_INSTITUT])
    g = bauen(bestand)
    gruppe = next(n for n in personen(g) if n.id == merge["id"])
    assert gruppe.attributes["identity_resolution"] == "confirmed_group"
    adressen = {graph.person_id_fuer("a:alex@winter-catering.example"),
                graph.person_id_fuer("a:alex.winter@ifeh-hessen.example")}
    assert set(gruppe.attributes["member_ids"]) == adressen
    assert gruppe.attributes["unassigned_members"] == []
    # Die beiden Einzelpersonen sind in der Gruppe aufgegangen; ihre Quellen hängen an der Gruppe.
    assert not adressen & {n.id for n in personen(g)}
    assert {e.source for e in g.edges if e.relation == "participated_in"} >= {merge["id"]}


def test_alte_kennung_bleibt_am_mitglied_gespeichert(bestand):
    merge = alt_gespeichert(bestand, [ALEX_CATERING, ALEX_INSTITUT])
    bauen(bestand)
    gespeichert = next(r for r in bestand.knowledge.person_merges.list() if r["id"] == merge["id"])
    assert gespeichert["label"] == "Alex Winter"
    mitglieder = {m["id"]: m for m in gespeichert["members"]}
    katering = mitglieder[graph.person_id_fuer("a:alex@winter-catering.example")]
    assert katering["alt_ids"] == [alte_kennung(ALEX_CATERING)]
    assert katering["alt_label"] == ALEX_CATERING
    assert "alex@winter-catering.example" in katering["label"]


def test_uebertragung_ist_idempotent(bestand):
    alt_gespeichert(bestand, [ALEX_CATERING, ALEX_INSTITUT])
    bauen(bestand)
    danach = json.dumps(bestand.knowledge.person_merges.list(), sort_keys=True)
    bauen(bestand)
    assert json.dumps(bestand.knowledge.person_merges.list(), sort_keys=True) == danach
    assert alt.nachziehen(bestand.knowledge.person_merges, bestand.episodes, erneut=True) == 0
    assert json.dumps(bestand.knowledge.person_merges.list(), sort_keys=True) == danach


def test_zwei_alte_namensformen_derselben_adresse_werden_ein_mitglied(bestand):
    # Vor C3 zwei Personen („Keller, Anna“ und „Anna Keller“), heute eine: keine Doppelung in der Gruppe.
    merge = alt_gespeichert(bestand, ["Keller, Anna <anna@x.example>", "Anna Keller <anna@x.example>"], "Anna Keller")
    g = bauen(bestand)
    mitglied, = [r for r in bestand.knowledge.person_merges.list() if r["id"] == merge["id"]][0]["members"]
    assert mitglied["id"] == graph.person_id_fuer("a:anna@x.example")
    assert set(mitglied["alt_ids"]) == {alte_kennung("Keller, Anna <anna@x.example>"),
                                        alte_kennung("Anna Keller <anna@x.example>")}
    assert next(n for n in personen(g) if n.id == merge["id"]).attributes["unassigned_members"] == []


def test_name_ohne_adresse_behaelt_seine_kennung(bestand):
    roth = alte_kennung("Herr Roth")
    assert roth == graph.person_id_fuer("n:herr roth")
    merge = alt_gespeichert(bestand, [ALEX_CATERING, "Herr Roth"], "Roth/Winter")
    bauen(bestand)
    ids = {m["id"] for r in bestand.knowledge.person_merges.list() if r["id"] == merge["id"] for m in r["members"]}
    assert roth in ids


def test_nicht_abbildbares_mitglied_bleibt_sichtbar_und_nicht_still_verschwunden(bestand):
    fremd = {"id": "person:0123456789abcdef", "kind": "person", "label": "Ehemalige Quelle <weg@x.example>"}
    catering = {"id": alte_kennung(ALEX_CATERING), "kind": "person", "label": ALEX_CATERING}
    merge = bestand.knowledge.person_merges.confirm({"label": "Alex", "members": [catering, fremd]}, confirmed=True)
    g = bauen(bestand)
    gruppe = next(n for n in personen(g) if n.id == merge["id"])
    assert gruppe.attributes["member_ids"] == [graph.person_id_fuer("a:alex@winter-catering.example")]
    verloren, = gruppe.attributes["unassigned_members"]
    assert verloren["id"] == fremd["id"] and verloren["reason"] == "Nicht mehr zuordenbar"
    gespeichert = {m["id"]: m for r in bestand.knowledge.person_merges.list() for m in r["members"]}
    assert gespeichert[fremd["id"]]["nicht_zuordenbar"] is True
    assert gespeichert[fremd["id"]]["grund"] == alt.GRUND_KEINE
    assert gespeichert[fremd["id"]]["label"] == fremd["label"]


def test_gruppe_ganz_ohne_zuordenbare_mitglieder_bleibt_als_gruppe_sichtbar(bestand):
    a = {"id": "person:aaaaaaaaaaaaaaaa", "kind": "person", "label": "A"}
    b = {"id": "person:bbbbbbbbbbbbbbbb", "kind": "person", "label": "B"}
    merge = bestand.knowledge.person_merges.confirm({"label": "Alt", "members": [a, b]}, confirmed=True)
    gruppe = next(n for n in personen(bauen(bestand)) if n.id == merge["id"])
    assert gruppe.attributes["member_ids"] == []
    assert [m["id"] for m in gruppe.attributes["unassigned_members"]] == [a["id"], b["id"]]


def test_eigene_adresse_ist_nicht_mehr_zuordenbar(bestand):
    ich = "Lea Hartmann <lea@hartmann-beratung.example>"
    bestand.episodes.record(EpisodeKind.MESSAGE, "Ich", "Text", Provenance(SourceType.EMAIL, "k:ich", AT),
                            occurred_at=AT, participants=[ich])
    merge = alt_gespeichert(bestand, [ALEX_CATERING, ich], "Alex und ich")
    bauen(bestand, eigene=["lea@hartmann-beratung.example"])
    gespeichert = next(r for r in bestand.knowledge.person_merges.list() if r["id"] == merge["id"])
    assert [m["nicht_zuordenbar"] for m in gespeichert["members"] if m.get("nicht_zuordenbar")] == [True]


def test_eigene_adresse_gilt_auch_ohne_vorgegebene_kennungen_nicht_als_person(bestand):
    ich = "Lea Hartmann <lea@hartmann-beratung.example>"
    bestand.episodes.record(EpisodeKind.MESSAGE, "Ich", "Text", Provenance(SourceType.EMAIL, "k:ich", AT),
                            occurred_at=AT, participants=[ich])
    merge = alt_gespeichert(bestand, [ALEX_CATERING, ich], "Alex und ich")
    assert alt.nachziehen(bestand.knowledge.person_merges, bestand.episodes,
                          eigene=["lea@hartmann-beratung.example"]) == 1
    gespeichert = next(r for r in bestand.knowledge.person_merges.list() if r["id"] == merge["id"])
    verloren, = [m for m in gespeichert["members"] if m.get("nicht_zuordenbar")]
    assert verloren["id"] == alte_kennung(ich) and verloren["grund"] == alt.GRUND_KEINE


def test_mehrdeutige_alte_kennung_wird_nicht_geraten():
    karte = {"person:alt": {"a1": "A1", "a2": "A2"}}
    record = {"id": "merge:1", "undone_at": None, "members": [{"id": "person:alt", "label": "Alt"}]}
    neu = alt.uebersetzen([record], karte, {"a1", "a2"})["merge:1"]
    assert neu[0]["nicht_zuordenbar"] and neu[0]["grund"] == alt.GRUND_MEHRERE and neu[0]["id"] == "person:alt"


def test_aufgehobene_zusammenfuehrung_wird_nicht_angefasst(bestand):
    merge = alt_gespeichert(bestand, [ALEX_CATERING, ALEX_INSTITUT])
    bestand.knowledge.person_merges.undo(merge["id"], confirmed=True)
    vorher = bestand.knowledge.person_merges.list()
    bauen(bestand)
    assert bestand.knowledge.person_merges.list() == vorher


def test_aufheben_stellt_die_einzelnen_personen_wieder_her(bestand):
    vorher = {n.id for n in personen(bauen(bestand))}
    merge = alt_gespeichert(bestand, [ALEX_CATERING, ALEX_INSTITUT])
    zusammen = {n.id for n in personen(bauen(bestand))}
    assert merge["id"] in zusammen and len(zusammen) == len(vorher) - 1
    bestand.knowledge.person_merges.undo(merge["id"], confirmed=True)
    assert {n.id for n in personen(bauen(bestand))} == vorher
    assert bestand.knowledge.person_merges.list()[0]["undone_at"]


def test_neuer_bestand_mit_heutigen_kennungen_wird_nicht_veraendert(bestand):
    """Eine nach C3 angelegte Zusammenführung braucht keine Übersetzung und löst keinen Scan aus."""
    g = bauen(bestand, group_people=False)
    ids = [graph.person_id_fuer("a:alex@winter-catering.example"), graph.person_id_fuer("a:alex.winter@ifeh-hessen.example")]
    knoten = {n.id: n for n in g.nodes}
    bestand.knowledge.person_merges.confirm(
        {"label": "Alex", "members": [knoten[i].to_dict() for i in ids]}, confirmed=True)
    vorher = json.dumps(bestand.knowledge.person_merges.list(), sort_keys=True)
    scans = []
    original = bestand.episodes.each_episode
    bestand.episodes.each_episode = lambda *a, **k: (scans.append(1), original(*a, **k))[1]
    bekannt = {n.id for n in g.nodes if n.kind == "person"}
    assert alt.nachziehen(bestand.knowledge.person_merges, bestand.episodes, bekannt=bekannt) == 0
    assert scans == [] and json.dumps(bestand.knowledge.person_merges.list(), sort_keys=True) == vorher


def test_api_zeigt_uebersetzte_zusammenfuehrung(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app()
    for nummer, text in enumerate([ALEX_CATERING, ALEX_INSTITUT]):
        app.state.episodes.record(EpisodeKind.MESSAGE, f"B{nummer}", f"T{nummer}",
                                  Provenance(SourceType.EMAIL, f"k:{nummer}", AT), occurred_at=AT, participants=[text])
    mitglieder = [{"id": alte_kennung(t), "kind": "person", "label": t} for t in (ALEX_CATERING, ALEX_INSTITUT)]
    merge = app.state.claims.person_merges.confirm({"label": "Alex Winter", "members": mitglieder}, confirmed=True)
    client = TestClient(app)
    knoten = client.get("/api/v1/memory/graph").json()["nodes"]
    assert [n["id"] for n in knoten if n["kind"] == "person"] == [merge["id"]]
    liste = client.get("/api/v1/memory/person-merges").json()["merges"]
    assert {m["id"] for m in liste[0]["members"]} == {graph.person_id_fuer("a:alex@winter-catering.example"),
                                                       graph.person_id_fuer("a:alex.winter@ifeh-hessen.example")}
