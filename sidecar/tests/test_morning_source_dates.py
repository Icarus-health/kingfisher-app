from datetime import datetime, timezone

from icarus_memory.morning import compose


def test_morning_activity_preserves_available_source_and_capture_times():
    source_time = datetime(2026, 10, 6, 8, tzinfo=timezone.utc).isoformat()
    capture_time = datetime(2026, 10, 7, 7, tzinfo=timezone.utc).isoformat()
    now = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
    dashboard = {
        "mail": {"items": [{"uid": "mail-1", "subject": "Bericht", "from": "Anna",
                             "unread": True, "date": source_time}]},
        "working_memory": {"items": [{"episode_id": "episode-1", "title": "Protokoll",
                                        "source_type": "email", "source_ref": "mail-2", "kinds": [],
                                        "occurred_at": source_time, "recorded_at": capture_time}]},
    }

    result = compose(dashboard, now=now, target=now.date())

    by_source = {item["source"]: item for item in result["happening_now"]}
    assert by_source["mail"]["occurred_at"] == source_time
    assert by_source["mail"].get("recorded_at") is None
    assert by_source["working_memory"]["occurred_at"] == source_time
    assert by_source["working_memory"]["recorded_at"] == capture_time


def test_morning_activity_keeps_missing_source_time_explicitly_unknown():
    now = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
    dashboard = {"mail": {"items": [{"uid": "mail-1", "unread": True, "date": None}]}}

    result = compose(dashboard, now=now, target=now.date())

    [item] = result["happening_now"]
    assert item["source"] == "mail"
    assert item.get("occurred_at") is None
    assert item.get("recorded_at") is None
