"""Nennt die Frage eine Person: alle ihre Quellen sind Kandidaten, Gleichnamige bleiben getrennt.

Zusicherungen (Sabotageproben in docs/evaluations/messlatte/C3-identitaet.md):

1. „Frau Reinhardt“, „Dr. Reinhardt“ und „Claudia“ finden die Quellen unter ihrer
   Adresse, auch die eigenen Antworten an sie und Namen ohne Adresse.
2. Zwei Menschen gleichen Namens werden nicht gemischt; ohne Unterscheidungsmerkmal
   fragt Kingfisher mit beiden zurück, mit Merkmal gilt nur der eine.
3. Die Quellen der genannten Person stehen in der Kandidatenauswahl.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from icarus_memory import personenfrage, working_memory_answers
from icarus_memory.bedeutungen import bedeutungen
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore

AT = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
ICH = "lea@hartmann-beratung.example"
CLAUDIA = "Dr. Claudia Reinhardt <c.reinhardt@ludgerus-klinik.example>"


@pytest.fixture
def episodes(tmp_path: Path) -> EpisodeStore:
    return EpisodeStore(tmp_path / "episodes.sqlite3")


def _quelle(episodes, titel, text, beteiligte, *, art=SourceType.EMAIL):
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, titel, text, Provenance(art, f"ref:{titel}", AT),
        occurred_at=AT, participants=beteiligte)
    return episode


@pytest.fixture
def reinhardt(episodes):
    ids = {
        "von": _quelle(episodes, "Auftrag Screening", "Ich beauftrage Sie mit dem Screening.", [CLAUDIA, ICH]).id,
        "an": _quelle(episodes, "AW: Auftrag Screening", "Danke, gern.", [f"Lea Hartmann <{ICH}>", CLAUDIA]).id,
        "name": _quelle(episodes, "Projektgespräch", "Wir sprechen über das Screening.",
                        ["Claudia Reinhardt"], art=SourceType.DOCUMENT).id,
        "fremd": _quelle(episodes, "Newsletter", "Nichts Persönliches.", ["Kurt Kranz <kurt@x.example>"]).id,
    }
    return ids


# -- 1. Alias und Adresse -----------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Welche offenen Punkte gibt es mit Frau Reinhardt?",
    "Wer ist eigentlich Dr. Reinhardt, und was haben wir miteinander zu tun?",
    "Seit wann kenne ich Claudia Reinhardt?",
    "Was hat Claudia gesagt?",
])
def test_person_wird_ueber_alias_gefunden_mit_allen_quellen(episodes, reinhardt, frage):
    quellen = personenfrage.kandidatenquellen(frage, episodes, eigene=[ICH])
    assert reinhardt["von"] in quellen
    assert reinhardt["an"] in quellen  # die eigene Antwort an sie
    assert reinhardt["fremd"] not in quellen


def test_name_ohne_adresse_kommt_dazu_wenn_nur_eine_person_ihn_traegt(episodes, reinhardt):
    quellen = personenfrage.kandidatenquellen("Was hat Claudia Reinhardt gesagt?", episodes, eigene=[ICH])
    assert reinhardt["name"] in quellen


def test_frage_ohne_person_liefert_keine_kandidaten(episodes, reinhardt):
    assert personenfrage.kandidatenquellen("Was steht in der Rechnung?", episodes, eigene=[ICH]) == []


# -- 2. Gleichnamige ------------------------------------------------------------

@pytest.fixture
def winter(episodes):
    catering = "Alex Winter <alex.winter@winter-catering.example>"
    institut = "Alex Winter <alex.winter@ifeh-hessen.example>"
    return {
        "catering": _quelle(episodes, "Preisanpassung und Probeverkostung", "38 Euro pro Person", [catering, ICH]).id,
        "catering2": _quelle(episodes, "Angebot Verpflegung", "34 Euro pro Person", [catering, ICH]).id,
        "institut": _quelle(episodes, "Bitte um Feedback zum Fragebogen", "Bis zum 16. Oktober", [institut, ICH]).id,
        "institut2": _quelle(episodes, "Einladung Gastvortrag am Institut", "Gastvortrag im November", [institut, ICH]).id,
    }


@pytest.mark.parametrize("frage", ["Was ist mit Alex Winter?", "Für welche Firma arbeitet Alex Winter?"])
def test_gleicher_name_ohne_merkmal_gehoert_in_die_rueckfrage(episodes, winter, frage):
    unklar = personenfrage.unklare_person(frage, episodes, eigene=[ICH])
    assert unklar is not None
    assert {k.adresse for k in unklar.kandidaten} == {
        "alex.winter@winter-catering.example", "alex.winter@ifeh-hessen.example"}


@pytest.mark.parametrize("frage,quelle,andere", [
    ("Was kostet das Catering von Alex Winter pro Person?", "catering", "institut"),
    ("Bis wann soll ich Alex Winter vom Institut Feedback zum Fragebogen geben?", "institut", "catering"),
    ("Welche E-Mail-Adresse hat Alex Winter vom Catering?", "catering", "institut2"),
])
def test_mit_merkmal_gilt_nur_die_eine_person(episodes, winter, frage, quelle, andere):
    assert personenfrage.unklare_person(frage, episodes, eigene=[ICH]) is None
    quellen = personenfrage.kandidatenquellen(frage, episodes, eigene=[ICH])
    assert winter[quelle] in quellen
    assert winter[andere] not in quellen


def test_ohne_merkmal_sind_die_quellen_beider_kandidaten(episodes, winter):
    quellen = personenfrage.kandidatenquellen("Was ist mit Alex Winter?", episodes, eigene=[ICH])
    assert set(winter.values()) <= set(quellen)


def test_verschiedene_namen_ohne_gemeinsame_adresse_sind_keine_rueckfrage(episodes):
    _quelle(episodes, "A", "x", ["Claudia Reinhardt <c@x.example>"])
    _quelle(episodes, "B", "y", ["Peter Reinhardt <p@y.example>"])
    assert personenfrage.unklare_person("Was ist mit Frau Reinhardt?", episodes) is None
    # Ein Teilname, der zwei verschiedene Namen trifft, wird nicht geraten: keine Personenquellen.
    assert personenfrage.kandidatenquellen("Was ist mit Frau Reinhardt?", episodes) == []
    # Der ganze Name trifft genau eine Person.
    assert len(personenfrage.kandidatenquellen("Was ist mit Peter Reinhardt?", episodes)) == 1


def test_bedeutungen_bieten_beide_personen_unterscheidbar_an(episodes, winter):
    ergebnis = bedeutungen("Alex Winter", episodes=episodes, projects=[])
    absender = [m for m in ergebnis["bedeutungen"] if m["art"] == "absender"]
    assert len(absender) == 2
    labels = {m["label"] for m in absender}
    assert len(labels) == 2 and all("(" in label for label in labels)
    text = " ".join(m["label"] + " " + m["detail"] for m in absender).casefold()
    assert "catering" in text and "gastvortrag" in text  # die letzten Betreffe erklären, wer wer ist


# -- 3. Kandidatenauswahl -------------------------------------------------------

def test_quellen_der_person_stehen_in_der_kandidatenauswahl(episodes):
    memory = WorkingMemoryStore(episodes)
    genannt = _quelle(episodes, "Angebot", "Das Angebot liegt bei 5 Euro.", [CLAUDIA])
    andere = _quelle(episodes, "Notiz", "Ohne Wort der Frage.", ["Kurt Kranz <kurt@x.example>"])
    for snapshot in memory.pending():
        assert memory.commit(snapshot, [{"start": 0, "end": len(snapshot.episode.body), "kind": "fact"}], model="t")
    ohne, _ = working_memory_answers._ordered_refs("Angebot", episodes, [])
    assert {r["episode_id"] for r in ohne} == {genannt.id}
    mit, _ = working_memory_answers._ordered_refs("Angebot", episodes, [], person_ids=[genannt.id, andere.id])
    assert {r["episode_id"] for r in mit} == {genannt.id, andere.id}


def test_mit_zeitraum_zaehlen_nur_die_quellen_der_person_aus_dem_zeitraum(episodes):
    from datetime import timedelta
    memory = WorkingMemoryStore(episodes)
    alt, _ = episodes.record(EpisodeKind.MESSAGE, "Alt", "Ohne Stichwort.", Provenance(SourceType.EMAIL, "ref:alt", AT),
                             occurred_at=AT - timedelta(days=90), participants=[CLAUDIA])
    neu, _ = episodes.record(EpisodeKind.MESSAGE, "Neu", "Auch ohne Stichwort.", Provenance(SourceType.EMAIL, "ref:neu", AT),
                             occurred_at=AT - timedelta(days=2), participants=[CLAUDIA])
    for snapshot in memory.pending():
        assert memory.commit(snapshot, [{"start": 0, "end": len(snapshot.episode.body), "kind": "fact"}], model="t")
    zeitraum = (AT - timedelta(days=7), AT + timedelta(days=1))
    refs, _ = working_memory_answers._ordered_refs("Was wollte sie?", episodes, [], None, zeitraum,
                                                   person_ids=[alt.id, neu.id])
    assert {r["episode_id"] for r in refs} == {neu.id}
    refs, _ = working_memory_answers._ordered_refs("Was wollte sie?", episodes, [], None, None,
                                                   person_ids=[alt.id, neu.id])
    assert {r["episode_id"] for r in refs} == {alt.id, neu.id}
