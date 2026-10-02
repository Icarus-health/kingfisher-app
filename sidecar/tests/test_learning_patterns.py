from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeState, digest_of
from icarus_memory.learning_patterns import detect_patterns


NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


def episode(i, days, *, tags=("habit:deep work",), body=None, kind=EpisodeKind.OBSERVATION,
            state=EpisodeState.NEW):
    occurred = NOW - timedelta(days=days)
    body = body or f"Beobachtung {i}"
    return SimpleNamespace(id=f"e-{i}", kind=kind, state=state, tags=list(tags), body=body,
                           digest=digest_of(body), occurred_at=occurred, recorded_at=occurred,
                           reference_time=lambda: occurred)


def test_detects_only_explicit_tag_and_distinct_days():
    result = detect_patterns([episode(i, i) for i in (1, 3, 5)] + [episode("implicit", 2, tags=("deep work",))], now=NOW)
    assert len(result) == 1
    assert result[0]["label"] == "deep work"
    assert result[0]["observed_days"] == 3
    assert len(result[0]["evidence"]) == 3
    assert result[0]["window_start"] == "2026-08-09"
    assert result[0]["window_end"] == "2026-09-08"


def test_ignores_stale_future_duplicates_summary_and_ignored():
    values = [episode(i, i) for i in (1, 2, 3)]
    values += [episode("old", 31), episode("future", -1), episode("duplicate", 2),
               episode("summary", 4, kind=EpisodeKind.SUMMARY),
               episode("ignored", 5, state=EpisodeState.IGNORED)]
    values[-3].id = "e-2"
    assert len(detect_patterns(values, now=NOW)[0]["evidence"]) == 3


def test_requires_minimum_days_and_is_deterministic():
    values = [episode(i, i, body=f"Text {i}") for i in (1, 3, 5)]
    first = detect_patterns(values, now=NOW)
    second = detect_patterns(list(reversed(values)), now=NOW)
    assert first == second
    changed = detect_patterns(values[:-1] + [episode(5, 5, body="Changed")], now=NOW)
    assert changed[0]["id"] != first[0]["id"]
    assert detect_patterns(values[:2], now=NOW, min_days=3) == []


def test_rejects_bad_parameters_and_oversized_input():
    with pytest.raises(ValueError): detect_patterns([], now=NOW, window_days=0)
    with pytest.raises(ValueError): detect_patterns([], now=NOW, min_days=0)
    with pytest.raises(ValueError): detect_patterns([], now=NOW, min_days=31)
    with pytest.raises(ValueError): detect_patterns((episode(i, 1) for i in range(2001)), now=NOW)


def test_quotes_are_nonempty_and_bounded():
    result = detect_patterns([episode(i, i, body="x" * 1000) for i in (1, 3, 5)], now=NOW)
    assert 0 < len(result[0]["evidence"][0]["quote"]) <= 280
