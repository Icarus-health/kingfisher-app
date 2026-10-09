"""Dekodierte Mailnamen müssen auch über die Personenfrage auffindbar sein."""
from datetime import datetime, timezone

from icarus_memory import personenfrage
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
# Vollständig kodierter Name: Weder Vor- noch Nachname trifft den rohen Vorfilter.
HEADER = "=?utf-8?b?TcO8bGxlciwgSmFu?="


def test_legacy_encoded_name_is_found_by_name_and_question_without_touching_source(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    try:
        mail, _ = store.record(EpisodeKind.MESSAGE, "Alter Mailkopf", "Originalinhalt.",
                              Provenance(SourceType.EMAIL, "synthetic:old", NOW),
                              participants=[HEADER + " <jan@one.example>"], at=NOW)
        before = mail.to_dict()
        assert store.participant_ids("Müller, Jan") == [mail.id]
        assert store.addresses_for_name("Müller, Jan") == ["jan@one.example"]
        assert personenfrage.kandidatenquellen("Was hat Jan Müller gesagt?", store) == [mail.id]
        assert store.get(mail.id).to_dict() == before
        store.ignore(mail.id)
        assert store.participant_ids("Müller, Jan") == []
        assert store.addresses_for_name("Müller, Jan") == []
        assert personenfrage.kandidatenquellen("Was hat Jan Müller gesagt?", store) == []
    finally:
        store.close()


def test_decoded_question_keeps_two_addresses_ambiguous_and_ignores_literal_note(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    try:
        for addr in ("jan@one.example", "jan@two.example"):
            store.record(EpisodeKind.MESSAGE, "Kopf " + addr, "Inhalt " + addr,
                         Provenance(SourceType.EMAIL, "synthetic:" + addr, NOW),
                         participants=[HEADER + " <" + addr + ">"], at=NOW)
        note, _ = store.record(EpisodeKind.DOCUMENT, "Wörtlicher Text", "Literal.",
                               Provenance(SourceType.DOCUMENT, "synthetic:note", NOW),
                               participants=[HEADER + " <literal@three.example>"], at=NOW)
        assert store.addresses_for_name("Müller, Jan") == ["jan@one.example", "jan@two.example"]
        mentions = personenfrage.erwaehnte("Was hat Jan Müller gesagt?", store)
        assert len(mentions) == 1
        assert {candidate.adresse for candidate in mentions[0].kandidaten} == {"jan@one.example", "jan@two.example"}
        assert all(note.id not in candidate.quellen for candidate in mentions[0].kandidaten)
    finally:
        store.close()
