from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.habits import check_in, create_habit, list_habits, retract_habit, retract_checkin
from icarus_memory.store import ConflictError


NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def stores(tmp_path):
    return SelfModelStore(MemoryBackend(), "test"), EpisodeStore(tmp_path / "episodes.sqlite3")


def test_create_and_list_weekly_progress(stores):
    store, episodes = stores
    habit = create_habit(store, "Lesen", 3)
    assert habit.sensitivity.value == "sensitive"
    check_in(store, episodes, habit.id, "2026-09-07", at=NOW)
    check_in(store, episodes, habit.id, "2026-09-08", "Kapitel zwei", at=NOW)
    item = list_habits(store, episodes, NOW)[0]
    assert item["label"] == "Lesen"
    assert item["target_per_week"] == 3
    assert item["checkins"] == 2
    assert item["observed_days"] == ["2026-09-07", "2026-09-08"]


def test_checkin_is_idempotent_per_habit_day_and_keeps_source(stores):
    store, episodes = stores
    habit = create_habit(store, "Laufen", 2)
    first = check_in(store, episodes, habit.id, "2026-09-08", "5 km", at=NOW)
    second = check_in(store, episodes, habit.id, "2026-09-08", "andere Notiz", at=NOW)
    assert first["created"] is True
    assert second["created"] is False
    assert len(episodes.all_episodes()) == 1
    assert f"habit:{habit.id}" in episodes.get(first["episode"]["id"]).tags
    assert episodes.get(first["episode"]["id"]).tags == [f"habit:{habit.id}"]


def test_rejects_future_bad_dates_and_bad_targets(stores):
    store, episodes = stores
    with pytest.raises(ValueError): create_habit(store, "", 3)
    with pytest.raises(ValueError): create_habit(store, "x", 0)
    with pytest.raises(ValueError): create_habit(store, "x", 8)
    habit = create_habit(store, "x", 1)
    with pytest.raises(ValueError): check_in(store, episodes, habit.id, "2026-09-09", at=NOW)
    with pytest.raises(ValueError): check_in(store, episodes, habit.id, "morgen", at=NOW)


def test_retraction_hides_habit_but_retains_checkin_evidence(stores):
    store, episodes = stores
    habit = create_habit(store, "Meditation", 4)
    check_in(store, episodes, habit.id, "2026-09-07", at=NOW)
    retract_habit(store, habit.id)
    assert list_habits(store, episodes, NOW) == []
    assert len(episodes.all_episodes()) == 1
    with pytest.raises(ConflictError): check_in(store, episodes, habit.id, "2026-09-08", at=NOW)


def test_missing_or_retracted_habit_rejected(stores):
    store, episodes = stores
    with pytest.raises(ConflictError): check_in(store, episodes, "missing", "2026-09-08", at=NOW)
    with pytest.raises(ConflictError): retract_habit(store, "missing")


def test_same_label_habits_stay_separate(stores):
    store, episodes = stores
    first = create_habit(store, "Training", 2)
    second = create_habit(store, "Training", 4)
    check_in(store, episodes, first.id, "2026-09-08", at=NOW)
    rows = list_habits(store, episodes, NOW)
    assert {row["id"] for row in rows} == {first.id, second.id}
    assert next(row for row in rows if row["id"] == first.id)["checkins"] == 1
    assert next(row for row in rows if row["id"] == second.id)["checkins"] == 0


def test_today_uses_reference_time_and_future_forgery_is_ignored(stores):
    store, episodes = stores
    habit = create_habit(store, "Schreiben", 1)
    today = check_in(store, episodes, habit.id, "2026-09-08", at=NOW)
    assert episodes.get(today["episode"]["id"]).occurred_at == NOW
    forged = check_in(store, episodes, habit.id, "2026-09-07", at=NOW)
    episode = episodes.get(forged["episode"]["id"])
    episode.occurred_at = NOW + timedelta(days=1)
    episodes._put(episode)
    assert list_habits(store, episodes, NOW)[0]["checkins"] == 1


def test_ignored_checkin_is_not_progress_but_remains_in_store(stores):
    store, episodes = stores
    habit = create_habit(store, "Ruhe", 1)
    checked = check_in(store, episodes, habit.id, "2026-09-08", at=NOW)
    retract_checkin(episodes, checked["episode"]["id"])
    assert list_habits(store, episodes, NOW)[0]["checkins"] == 0
    assert episodes.get(checked["episode"]["id"]).state.value == "ignored"
    with pytest.raises(ConflictError):
        check_in(store, episodes, habit.id, "2026-09-08", at=NOW)


def test_noncanonical_dates_are_rejected(stores):
    store, episodes = stores
    habit = create_habit(store, "Fokus", 1)
    with pytest.raises(ValueError): check_in(store, episodes, habit.id, "2026-9-8", at=NOW)
