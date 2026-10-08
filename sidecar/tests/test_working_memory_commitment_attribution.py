"""Commitments in source text must not become commitments by the Kingfisher user."""
import json
from datetime import datetime

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory import satzantwort, working_memory_answers


def test_commitment_citation_warns_that_the_quoted_speaker_needs_checking(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    try:
        # The outer sender is not necessarily the speaker of a quoted message.
        source, _ = episodes.record(
            EpisodeKind.MESSAGE, "Weitergeleitete Nachricht",
            "Von Kai: Ich sende die Unterlagen bis Freitag.",
            Provenance(SourceType.EMAIL), participants=["Nora Beck <nora@example.test>"])
        memory = WorkingMemoryStore(episodes)
        assert memory.commit(episodes.support_snapshot(source.id), [
            {"start": 0, "end": len(source.body), "kind": "commitment"}], model="synthetic")
        refs = memory.search("Unterlagen")['refs']

        lines, links = working_memory_answers._zitate(
            {"refs": refs, "akten": {}, "kennzeichnung": {}}, episodes, fallback=False)

        heading = next(line for line in lines if "Weitergeleitete Nachricht" in line)
        assert "Urheber" in heading and "prüfen" in heading
        assert "von Nora Beck" not in heading
        assert links[0]["episode_id"] == source.id
    finally:
        episodes.close()


def test_sentence_answer_contract_keeps_source_speaker_distinct_from_user():
    source = satzantwort.AntwortBeleg(
        1, {}, "Zusage", "e1", "Weitergeleitete Nachricht",
        "Weitergeleitete Nachricht; von Nora Beck", "Von Kai: Ich sende die Unterlagen bis Freitag.", None)
    messages = satzantwort.nachrichten("Wer hat die Unterlagen zugesagt?", [source], datetime(2026, 10, 8))
    instruction = " ".join(messages[0]["content"].casefold().split())
    payload = json.loads(messages[1]["content"])
    assert payload["belege"][0]["quelle"] == "Weitergeleitete Nachricht; von Nora Beck"
    assert payload["belege"][0]["text"] == "Von Kai: Ich sende die Unterlagen bis Freitag."
    assert "belegt keine zusage des nutzers" in instruction
    assert "sprecher zu" in instruction
    assert "absender im belegkopf allein genügt dafür nicht" in instruction
