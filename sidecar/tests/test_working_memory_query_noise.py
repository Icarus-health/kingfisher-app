"""Fragewörter dürfen weder Scheinbelege liefern noch ältere Sachtreffer verdrängen."""
from contextlib import closing

import pytest

from icarus_memory import EpisodeStore
from icarus_memory.source_candidates import zusammenfuehren
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_working_memory_store import source


def einordnen(episodes, text):
    episode = source(episodes, text)
    store = WorkingMemoryStore(episodes)
    snapshot = store.pending(episode_ids=[episode.id])[0]
    assert store.commit(snapshot, [{"start": 0, "end": len(text), "kind": "fact"}], model="synthetisch")
    return episode


@pytest.mark.parametrize("question,text", [
    ("Welche Blutgruppe habe ich?", "Ich habe den Entwurf verschickt."),
    ("Wie lautet die PIN meiner Bankkarte?", "Meiner Einschätzung nach bleibt der Entwurf offen."),
    ("Wann war die Mondlandung?", "Der Entwurf war fertig."),
])
def test_reine_funktionsworttreffer_liefern_keinen_beleg(tmp_path, question, text):
    with closing(EpisodeStore(tmp_path / "episodes.sqlite3")) as episodes:
        einordnen(episodes, text)
        store = WorkingMemoryStore(episodes)
        assert store.search(question)["refs"] == []
        assert zusammenfuehren(store, question, limit=16).refs == []


def test_aelterer_wortformtreffer_wird_nicht_von_fragewoertern_verdrangt(tmp_path):
    with closing(EpisodeStore(tmp_path / "episodes.sqlite3")) as episodes:
        expected = einordnen(episodes, "Der Vertrag blieb ohne Freigabe.")
        for i in range(70):
            einordnen(episodes, f"Der Entwurf Nummer {i} war fertig.")
        store = WorkingMemoryStore(episodes)
        question = "Was war der Stand des Vertrags?"
        assert [ref["episode_id"] for ref in store.search(question, limit=1)["refs"]] == [expected.id]
        assert [ref["episode_id"] for ref in zusammenfuehren(store, question, limit=16).refs] == [expected.id]


def test_funktionsworttreffer_aendern_nicht_die_antwortgrundlage(tmp_path):
    with closing(EpisodeStore(tmp_path / "episodes.sqlite3")) as episodes:
        einordnen(episodes, "Das Quasararchiv enthält drei Akten.")
        store = WorkingMemoryStore(episodes)
        question = "Was habe ich zum Quasararchiv?"
        before = store.candidate_signature(question)
        einordnen(episodes, "Ich habe die Tür geschlossen.")
        assert store.candidate_signature(question) == before
        einordnen(episodes, "Das Quasararchiv enthält jetzt vier Akten.")
        assert store.candidate_signature(question) != before


def test_fragewoerter_verbrauchen_nicht_das_begriffsbudget():
    terms, _, limited = WorkingMemoryStore.query_terms(
        "alle allen allem aber auch als bei beim bis dann dazu damit denn doch dort "
        "ein einer eines einem etwas eigentlich habe haben hatte hatten Quasararchiv")
    assert terms == ["quasararchiv"]
    assert limited is False


def test_sachtreffer_bleiben_bei_entzug_und_abgewahltem_bereich_gesperrt(tmp_path):
    with closing(EpisodeStore(tmp_path / "episodes.sqlite3")) as episodes:
        target = einordnen(episodes, "Der Vertrag war offen.")
        other = einordnen(episodes, "Ich habe einen Entwurf.")
        store = WorkingMemoryStore(episodes)
        question = "Was war der Stand des Vertrags?"
        assert store.search(question, episode_ids=[other.id])["refs"] == []
        ref = store.search(question)["refs"][0]
        episodes.ignore(target.id)
        assert store.resolve(ref) is None
        assert zusammenfuehren(store, question, limit=16).refs == []
