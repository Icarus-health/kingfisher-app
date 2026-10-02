"""Literal discovery over current raw source bodies."""

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.source_search import search


@pytest.fixture
def episodes(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    yield store
    store.close()


def put(episodes, body, *, title="Source", kind=EpisodeKind.DOCUMENT, key=""):
    source = Provenance(source_type=SourceType.DOCUMENT)
    episode, created = episodes.record(kind, title, body, source, source_key=key)
    assert created
    return episode


def test_search_matches_body_literally_with_unicode_casefold(episodes):
    found = put(episodes, "Die STRASSE führt hier entlang.")
    put(episodes, "No match", title="Straße in title")
    assert search(episodes, "straße") == {
        "ids": [found.id], "truncated": False, "budget_exhausted": False,
        "oversize_skipped": False, "normalization": "literal-casefold-v1",
    }


@pytest.mark.parametrize("literal,body", [("%_x", "Sign %_x here"), ("a_b", "Use a_b")])
def test_sql_wildcards_are_plain_characters(episodes, literal, body):
    found = put(episodes, body)
    put(episodes, "A different body")
    assert search(episodes, literal)["ids"] == [found.id]


def test_ignored_summary_and_previous_version_are_excluded(episodes):
    ignored = put(episodes, "needle ignored")
    episodes.ignore(ignored.id)
    put(episodes, "needle summary", kind=EpisodeKind.SUMMARY)
    old = put(episodes, "needle old", key="folder/a")
    new = put(episodes, "needle new", key="folder/a")
    episodes.advance_source_head("folder/a", None, old.id)
    episodes.advance_source_head("folder/a", old.id, new.id)
    assert search(episodes, "needle")["ids"] == [new.id]


def test_unkeyed_old_source_is_not_lost_behind_recent_rows(episodes):
    old = put(episodes, "rare phrase buried in old source")
    for number in range(601):
        put(episodes, f"Unrelated recent body {number}")
    assert search(episodes, "rare phrase")["ids"] == [old.id]


def test_result_is_capped_and_reports_more_matches(episodes):
    for number in range(21):
        put(episodes, f"common phrase {number}")
    result = search(episodes, "common phrase")
    assert len(result["ids"]) == 20
    assert len(set(result["ids"])) == 20
    assert result["truncated"] is True
    assert result["budget_exhausted"] is False


def test_oversize_sources_are_skipped_and_reported(episodes):
    put(episodes, "oversized body " + "x" * (512 * 1024))
    large_document = put(episodes, "oversized document")
    large_document.tags = ["x" * (768 * 1024)]
    episodes._put(large_document)
    normal = put(episodes, "oversized normal")
    result = search(episodes, "oversized")
    assert result["ids"] == [normal.id]
    assert result["oversize_skipped"] is True


@pytest.mark.parametrize("literal", ["", "ab", "x" * 121, "bad\nline", "bad\x00text", "bad\x85text"])
def test_invalid_literal_is_rejected(episodes, literal):
    with pytest.raises(ValueError):
        search(episodes, literal)


def test_budget_exceeded_while_confirming_discards_partial_ids(episodes, monkeypatch):
    import icarus_memory.source_search as source_search

    put(episodes, "needle first")
    put(episodes, "needle second")
    monkeypatch.setattr(source_search, "_MAX_SECONDS", 0)
    result = source_search.search(episodes, "needle")
    assert result["ids"] == []
    assert result["budget_exhausted"] is True
    monkeypatch.setattr(source_search, "_MAX_SECONDS", 0.5)
    assert len(source_search.search(episodes, "needle")["ids"]) == 2


def test_more_candidates_than_can_be_confirmed_are_reported_not_cut_silently(episodes, monkeypatch):
    import icarus_memory.source_search as source_search

    for number in range(5):
        put(episodes, f"needle {number}")
    monkeypatch.setattr(source_search, "_MAX_KANDIDATEN", 3)
    result = source_search.search(episodes, "needle")
    assert result["ids"] == [] and result["budget_exhausted"] is True


def test_accent_folding_of_the_index_does_not_widen_the_literal_semantics(episodes):
    """Der Index faltet Akzente; die Suche bestätigt am Original (casefold, sonst buchstäblich)."""
    put(episodes, "Äpfel und Birnen")
    plain = put(episodes, "Apfel und Birnen")
    assert search(episodes, "Apfel")["ids"] == [plain.id]


def test_large_store_is_searched_completely_within_budget(episodes):
    """Früher endete die lineare Suche bei großem Bestand leer; der Index braucht kein Budget je Quelle."""
    for number in range(3000):
        put(episodes, f"Alltagsmail Nummer {number} ohne Besonderheit")
    target = put(episodes, "Hier steht die Kennung Quasar-4711 im Text")
    result = search(episodes, "Quasar-4711")
    assert result["ids"] == [target.id]
    assert result["budget_exhausted"] is False


def test_literal_too_short_after_folding_reports_incomplete(episodes):
    put(episodes, "e\u0301x steht hier")
    result = search(episodes, "e\u0301x")
    assert result["ids"] == [] and result["budget_exhausted"] is True


def test_very_common_literal_stops_after_the_first_twenty_confirmed_hits(episodes):
    """Ein häufiges Wort liest nicht den ganzen Bestand: 21 bestätigte Treffer genügen."""
    for number in range(2500):
        put(episodes, f"Alltagsmail {number} mit der Rechnung im Text")
    result = search(episodes, "Rechnung")
    assert len(result["ids"]) == 20 and result["truncated"] is True
    assert result["budget_exhausted"] is False
