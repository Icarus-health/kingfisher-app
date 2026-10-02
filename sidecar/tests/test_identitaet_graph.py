"""Identität im Graphen, in Profilen und beim Zusammenführen (Etappe C3).

Zusicherungen:

1. Im Graphen ist eine Adresse ein Knoten, gleich unter wie vielen Namen sie schrieb; zwei
   Adressen mit gleichem Namen sind zwei Knoten, die die Prüfung als mögliche Dubletten nennt.
2. Die Zusammenführung zweier Gleichnamiger durch den Nutzer ist umkehrbar; der Graph danach
   ist der Graph davor.
3. Das Profil eines Namens, der zwei Menschen gehört, wird nicht gemischt: 409 mit beiden;
   die Adresse wählt aus.
4. Aufgaben „wartet auf Alex Winter“ werden keinem der beiden zugeschrieben.
5. Wer nacheinander unter zwei Adressen schreibt (Arbeitgeberwechsel), löst keine erzwungene
   Rückfrage aus; wer gleichzeitig unter zweien schreibt, schon.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory import personen, personenfrage
from icarus_memory.backends import MemoryBackend
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.graph import build, person_id_fuer, person_profile
from icarus_memory.model import Provenance, SourceType
from icarus_memory.person_merges import preview, project
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

JETZT = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
CATERING = "Alex Winter <alex.winter@winter-catering.example>"
INSTITUT = "Alex Winter <alex.winter@ifeh-hessen.example>"


def _stores(tmp_path: Path):
    return (EpisodeStore(tmp_path / "episodes.sqlite3"), WorkspaceStore(tmp_path / "workspace.sqlite3"),
            TaskStore(tmp_path / "tasks.sqlite3"), SelfModelStore(MemoryBackend(), subject_id="local"))


def _mail(episodes, titel, beteiligte, *, tage=0):
    return episodes.record(
        EpisodeKind.MESSAGE, titel, f"Text zu {titel}", Provenance(SourceType.EMAIL, f"mail:{titel}", JETZT),
        occurred_at=JETZT - timedelta(days=tage), participants=beteiligte)[0]


def _graph(stores, **kwargs):
    episodes, workspace, tasks, store = stores
    return build(episodes=episodes, workspace=workspace, tasks=tasks, store=store, at=JETZT, **kwargs)


def _personen(graph):
    return [n for n in graph.nodes if n.kind == "person"]


# -- 1. Knoten über Adressen -----------------------------------------------------

def test_eine_adresse_ist_ein_knoten_zwei_adressen_zwei_knoten(tmp_path):
    stores = _stores(tmp_path)
    episodes = stores[0]
    _mail(episodes, "A", ['"Keller, Anna" <anna@x.example>', "lea@h.example"])
    _mail(episodes, "B", ["Anna Keller <anna@x.example>"])
    _mail(episodes, "C", [CATERING])
    _mail(episodes, "D", [INSTITUT])
    graph = _graph(stores, eigene=["lea@h.example"])
    knoten = {n.id: n for n in _personen(graph)}
    assert set(knoten) == {person_id_fuer("a:anna@x.example"), person_id_fuer("a:alex.winter@winter-catering.example"),
                           person_id_fuer("a:alex.winter@ifeh-hessen.example")}
    anna = knoten[person_id_fuer("a:anna@x.example")]
    assert anna.attributes["addresses"] == ["anna@x.example"]
    assert set(anna.attributes["names"]) == {"Keller, Anna", "Anna Keller"}
    # Die Prüfung nennt die beiden Winters als mögliche Dubletten; sie führt nichts zusammen.
    winters = [n for n in knoten.values() if n.label.startswith("Alex Winter")]
    assert all(len(n.attributes["duplicate_ids"]) == 1 and n.attributes["duplicate_reason"] == "same_name"
               for n in winters)


def test_name_ohne_adresse_haengt_am_eindeutigen_traeger_im_graphen(tmp_path):
    stores = _stores(tmp_path)
    episodes = stores[0]
    _mail(episodes, "A", ["Anna Keller <anna@x.example>"])
    _mail(episodes, "B", ["Keller, Anna"])
    assert [n.id for n in _personen(_graph(stores))] == [person_id_fuer("a:anna@x.example")]


# -- 2. Zusammenführung umkehrbar -----------------------------------------------------

def test_zusammenfuehrung_der_gleichnamigen_ist_umkehrbar(tmp_path):
    stores = _stores(tmp_path)
    episodes = stores[0]
    _mail(episodes, "C", [CATERING])
    _mail(episodes, "D", [INSTITUT])
    roh = _graph(stores)
    vorher = roh.to_dict()
    ids = [n.id for n in _personen(roh)]
    assert len(ids) == 2
    knowledge = ClaimStore(tmp_path / "knowledge.sqlite3")
    record = knowledge.person_merges.confirm(preview(roh, ids, "Alex Winter"), confirmed=True)
    zusammen = project(roh, knowledge.person_merges.list())
    assert [n.label for n in _personen(zusammen)] == ["Alex Winter"]
    knowledge.person_merges.undo(record["id"], confirmed=True)
    assert project(roh, knowledge.person_merges.list()).to_dict() == vorher
    assert roh.to_dict() == vorher  # die Quellen selbst blieben unberührt


# -- 3. Profil ---------------------------------------------------------------------------

def test_profil_eines_mehrdeutigen_namens_mischt_nicht(tmp_path):
    stores = _stores(tmp_path)
    episodes, workspace, tasks, store = stores
    _mail(episodes, "C", [CATERING])
    _mail(episodes, "D", [INSTITUT])
    with pytest.raises(personen.Mehrdeutig) as fehler:
        person_profile("Alex Winter", episodes=episodes, workspace=workspace, tasks=tasks, store=store, at=JETZT)
    assert len(fehler.value.kandidaten) == 2
    profil = person_profile("alex.winter@ifeh-hessen.example", episodes=episodes, workspace=workspace,
                            tasks=tasks, store=store, at=JETZT)
    assert [i["source_ref"] for i in profil["interactions"]] == ["mail:D"]
    assert profil["person"]["adressen"] == ["alex.winter@ifeh-hessen.example"]
    assert profil["id"] == person_id_fuer("a:alex.winter@ifeh-hessen.example")


def test_api_meldet_mehrdeutigen_namen_als_409_mit_beiden_adressen(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app()
    client = TestClient(app)
    _mail(app.state.episodes, "C", [CATERING])
    _mail(app.state.episodes, "D", [INSTITUT])
    antwort = client.get("/api/v1/memory/people/Alex%20Winter")
    assert antwort.status_code == 409
    assert "winter-catering.example" in antwort.json()["detail"] and "ifeh-hessen.example" in antwort.json()["detail"]
    assert client.get("/api/v1/memory/people/alex.winter%40ifeh-hessen.example").status_code == 200
    liste = client.get("/people").json()
    assert {p["adressen"][0] for p in liste} == {"alex.winter@winter-catering.example", "alex.winter@ifeh-hessen.example"}
    assert all(p["unterscheidung"] in p["anzeige"] for p in liste)


# -- 4. Aufgaben ------------------------------------------------------------------------

def test_wartet_auf_gleichnamige_wird_keinem_zugeschrieben(tmp_path):
    stores = _stores(tmp_path)
    episodes, _, tasks, store = stores
    _mail(episodes, "C", [CATERING])
    _mail(episodes, "D", [INSTITUT])
    _mail(episodes, "E", ["Anna Keller <anna@x.example>"])
    aufgabe = tasks.add("Angebot prüfen", Provenance(SourceType.USER_STATED, "u", JETZT))
    aufgabe2 = tasks.add("Rückmeldung abwarten", Provenance(SourceType.USER_STATED, "u2", JETZT))
    tasks.warten_auf(aufgabe.id, "Alex Winter")
    tasks.warten_auf(aufgabe2.id, "Anna Keller")
    menschen = {m.id: m for m in personen.alle(episodes=episodes, tasks=tasks, store=store, jetzt=JETZT)}
    assert menschen["a:alex.winter@winter-catering.example"].offene_aufgaben == []
    assert menschen["a:alex.winter@ifeh-hessen.example"].offene_aufgaben == []
    assert [a["title"] for a in menschen["a:anna@x.example"].offene_aufgaben] == ["Rückmeldung abwarten"]


# -- 5. Nacheinander oder gleichzeitig ------------------------------------------------

def test_adresswechsel_nacheinander_erzwingt_keine_rueckfrage(tmp_path):
    episodes = _stores(tmp_path)[0]
    for tage, adresse in ((300, "j.krueger@kreisklinik.example"), (250, "j.krueger@kreisklinik.example"),
                          (100, "j.krueger@vitalzentrum.example"), (60, "j.krueger@vitalzentrum.example")):
        _mail(episodes, f"K{tage}", [f"Jasmin Krüger <{adresse}>"], tage=tage)
    assert personenfrage.unklare_person("Wo arbeitet Jasmin Krüger jetzt?", episodes) is None
    # Beide Adressen bleiben getrennte Personen; beide Quellenmengen sind Kandidaten.
    assert len(personen.alle(episodes=episodes, jetzt=JETZT)) == 2
    assert len(personenfrage.kandidatenquellen("Wo arbeitet Jasmin Krüger jetzt?", episodes)) == 4


def test_gleichzeitige_gleichnamige_erzwingen_die_rueckfrage(tmp_path):
    episodes = _stores(tmp_path)[0]
    for tage, adresse in ((300, "a@catering.example"), (200, "a@institut.example"),
                          (100, "a@catering.example"), (50, "a@institut.example")):
        _mail(episodes, f"W{tage}", [f"Alex Winter <{adresse}>"], tage=tage)
    assert personenfrage.unklare_person("Was ist mit Alex Winter?", episodes) is not None
