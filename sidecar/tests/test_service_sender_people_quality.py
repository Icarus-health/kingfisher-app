"""Qualität technischer Mail-Absender ohne Verlust der Quellenprojektion prüfen."""
from datetime import datetime, timezone

import pytest

from icarus_memory import identitaet
from icarus_memory.backends import MemoryBackend
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.graph import GraphNode, build, person_id_fuer
from icarus_memory.model import Provenance, SourceType
from icarus_memory.people_quality import annotate_people, ist_sammelpostfach, lokalteil
from icarus_memory.store import SelfModelStore
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

JETZT = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _person(kennung, label, aufloesung="exact_normalized_name"):
    return GraphNode(kennung, "person", label, {"identity_resolution": aufloesung})


@pytest.mark.parametrize("lokal", [
    "do_not_reply", "do-not-reply", "do.not.reply",
    "do_not_reply+ticket", "do-not-reply+ticket", "do.not.reply+ticket",
])
def test_do_not_reply_varianten_sind_automatisiert_auch_mit_plus_tag(lokal):
    assert ist_sammelpostfach(lokalteil(f"{lokal}@mail.example"))

    [markiert] = annotate_people([_person("service", f"System <{lokal}@mail.example>")])

    assert markiert.attributes["quality_category"] == "automated"
    assert markiert.attributes["duplicate_ids"] == []


@pytest.mark.parametrize("lokal", ["cs-auto", "cs_auto", "cs.auto"])
def test_cs_auto_schreibweisen_bleiben_pruefbeduerftige_servicepostfaecher(lokal):
    [markiert] = annotate_people([_person("service", f"Kundenservice <{lokal}+fall@mail.example>")])

    assert ist_sammelpostfach(lokalteil(f"{lokal}+fall@mail.example"))
    assert markiert.attributes["quality_category"] == "review"
    assert markiert.attributes["duplicate_ids"] == []


@pytest.mark.parametrize("lokal", ["anna.service", "auto", "anna.auto", "cs.autumn", "mechanics"])
def test_personliche_aehnliche_adressen_bleiben_personen(lokal):
    [markiert] = annotate_people([_person("person", f"Anna <{lokal}@mail.example>")])

    assert not ist_sammelpostfach(lokalteil(f"{lokal}@mail.example"))
    assert markiert.attributes["quality_category"] == "person"


@pytest.mark.parametrize("lokal, erwartet", [
    ("do_not_reply", "automated"), ("cs-auto", "review"),
    ("do-not-reply", "automated"), ("cs_auto", "review"),
    ("do.not.reply", "automated"), ("cs.auto", "review"),
])
@pytest.mark.parametrize("aufloesung", ["explicit_registry", "confirmed_group"])
def test_explizite_registry_und_bestaetigte_gruppe_bleiben_unberuehrt(lokal, erwartet, aufloesung):
    [ungeprueft] = annotate_people([_person("unreviewed", f"Anzeigename <{lokal}@mail.example>")])
    [markiert] = annotate_people([_person("confirmed", f"Anzeigename <{lokal}@mail.example>", aufloesung)])

    assert ungeprueft.attributes["quality_category"] == erwartet
    assert markiert.attributes["quality_category"] == "person"
    assert markiert.attributes["quality_reason"] == ""
    assert markiert.attributes["duplicate_ids"] == []


@pytest.mark.parametrize("lokal", ["do_not_reply", "cs-auto"])
def test_service_alias_loest_bare_personennamen_nicht_als_mensch_auf(lokal):
    adresse = f"{lokal}@mail.example"
    verzeichnis = identitaet.Verzeichnis.aus([
        {"participants": [f"Alex Beispiel <{adresse}>"]},
    ])

    assert verzeichnis.adressen_zum_namen("Alex Beispiel") == []
    assert verzeichnis.aufloesen(identitaet.Nennung("Alex Beispiel", "")).schluessel == "n:alex beispiel"


@pytest.mark.parametrize(("adresse", "anzeige", "kategorie"), [
    ("do_not_reply+fall@mail.example", "Systemdienst", "automated"),
    ("cs-auto+fall@mail.example", "Alex Beispiel", "review"),
])
def test_graph_haelt_service_anzeige_aber_keinen_namensalias_oder_quellenverlust(
        tmp_path, adresse, anzeige, kategorie):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    workspace = WorkspaceStore(tmp_path / "workspace.sqlite3")
    tasks = TaskStore(tmp_path / "tasks.sqlite3")
    model = SelfModelStore(MemoryBackend(), subject_id="synthetic")
    participant = f"{anzeige} <{adresse}>"
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE,
        "Synthetische Benachrichtigung",
        "Künstlicher Nachrichtentext ohne personenbezogene Daten.",
        Provenance(SourceType.EMAIL, f"synthetic:{lokalteil(adresse)}", JETZT),
        occurred_at=JETZT,
        participants=[participant],
        at=JETZT,
    )
    original = episodes.get(episode.id).to_dict()

    result = build(episodes=episodes, workspace=workspace, tasks=tasks, store=model, at=JETZT)

    person_id = person_id_fuer(f"a:{adresse}")
    person = next(node for node in result.nodes if node.id == person_id)
    edge = next(edge for edge in result.edges
                if edge.source == person_id and edge.target == f"episode:{episode.id}"
                and edge.relation == "participated_in")
    assert person.id == person_id
    assert person.attributes["quality_category"] == kategorie
    assert person.attributes["addresses"] == [adresse]
    assert person.attributes["names"] == []
    assert person.label == f"{anzeige} <{adresse}>"
    assert edge.evidence_refs == (f"episode:{episode.id}",)
    assert episodes.get(episode.id).to_dict() == original
    assert original["participants"] == [participant]
    assert original["body"] == "Künstlicher Nachrichtentext ohne personenbezogene Daten."
