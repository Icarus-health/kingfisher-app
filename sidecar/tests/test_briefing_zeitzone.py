"""Der Briefing-Kopf nennt die eingestellte Zeitzone, nicht die des Rechners (Fremdprobe 2, Befund 9)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory.connectors.calendar import Event
from icarus_memory import server
from icarus_memory.server import create_app


def test_ohne_angabe_gilt_die_eingestellte_zeitzone(monkeypatch, tmp_path):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setenv('TZ', 'UTC')  # der Container läuft in UTC
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()['timezone'] == 'Europe/Berlin'
        monkeypatch.setenv('KINGFISHER_TIMEZONE', 'America/New_York')
        assert client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()['timezone'] == 'America/New_York'
        # Wer ausdrücklich eine Zone nennt, bekommt sie (Schnittstelle unverändert).
        assert client.get('/api/v1/morning-briefing', params={'timezone': 'UTC', 'post': 'false'}).json()['timezone'] == 'UTC'


def test_die_oberflaeche_schickt_keine_zeitzone_des_browsers():
    from pathlib import Path
    api = (Path(__file__).resolve().parents[2] / 'app' / 'kingfisher' / 'src' / 'api.ts').read_text(encoding='utf-8')
    zeile = next(z for z in api.splitlines() if z.strip().startswith('morning:'))
    assert 'resolvedOptions' not in zeile and 'timezone=' not in zeile


@pytest.mark.parametrize(("utc_now", "event_utc"), [
    (datetime(2026, 7, 1, 20, 30, tzinfo=timezone.utc), datetime(2026, 7, 1, 21, 0, tzinfo=timezone.utc)),
    (datetime(2026, 1, 1, 20, 30, tzinfo=timezone.utc), datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc)),
    (datetime(2026, 6, 1, 23, 30, tzinfo=timezone.utc), datetime(2026, 6, 1, 23, 45, tzinfo=timezone.utc)),
])
def test_morning_event_sentence_uses_the_same_resolved_zone_as_its_timeline(
    monkeypatch, tmp_path, utc_now, event_utc,
):
    """Summer, winter, and local date rollover must agree across both views."""
    original_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("ICARUS_SIDECAR_TOKEN", raising=False)
        monkeypatch.setenv("KINGFISHER_TIMEZONE", "Europe/Berlin")

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_now.astimezone(tz) if tz else utc_now.replace(tzinfo=None)

        class Calendar:
            last_errors = {}

            def events(self, **_kwargs):
                return [Event("fixed-event", "Testtermin", event_utc,
                              event_utc + timedelta(minutes=30))]

        monkeypatch.setattr(server, "datetime", FrozenDateTime)
        app = create_app()
        app.state.calendar = Calendar()
        with TestClient(app) as client:
            result = client.get("/api/v1/morning-briefing", params={
                "timezone": "Europe/Berlin", "post": "false",
            }).json()

        event_row = next(item for item in result["later_today"] if item["title"] == "Testtermin")
        sentence = next(item["title"] for item in result["needs_you"] if item["source"] == "termin")
        hour, minute = event_row["time"].split(":")
        assert f"Um {int(hour)}:{minute} Uhr" in sentence
        assert result["timezone"] == "Europe/Berlin"
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


def test_morning_classifies_task_due_dates_by_local_day_at_midnight(
    monkeypatch, tmp_path,
):
    """UTC yesterday can be today in Berlin, and UTC today can be tomorrow."""
    from icarus_memory import tasks as task_module

    original_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    utc_now = datetime(2026, 6, 1, 22, 30, tzinfo=timezone.utc)
    try:
        monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("ICARUS_SIDECAR_TOKEN", raising=False)
        monkeypatch.setenv("KINGFISHER_TIMEZONE", "Europe/Berlin")

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_now.astimezone(tz) if tz else utc_now.replace(tzinfo=None)

        monkeypatch.setattr(server, "datetime", FrozenDateTime)
        monkeypatch.setattr(task_module, "now", lambda: utc_now)
        app = create_app()
        with TestClient(app) as client:
            for title, due in (
                ("Heute lokal", "2026-06-01T23:00:00+00:00"),
                ("Morgen lokal", "2026-06-02T22:30:00+00:00"),
                ("Gestern lokal", "2026-06-01T21:30:00+00:00"),
            ):
                response = client.post("/api/v1/tasks", json={"title": title, "due": due})
                assert response.status_code == 201
            result = client.get("/api/v1/morning-briefing", params={
                "timezone": "Europe/Berlin", "post": "false",
            }).json()

        task_items = [item for item in result["needs_you"] if item["source"] == "aufgabe"]
        today = next(item for item in task_items if item["title"] == "Heute lokal")
        yesterday = next(item for item in task_items if item["title"] == "Gestern lokal")
        assert "Heute fällig: „Heute lokal“" in today["reason"]
        assert "Seit dem 1. Juni wartet „Gestern lokal“" in yesterday["reason"]
        assert all(item["title"] != "Morgen lokal" for item in task_items)
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


def test_date_only_and_naive_task_dates_keep_their_written_civil_day():
    from icarus_memory.briefing import _heute_faellig

    berlin_now = datetime(2026, 6, 2, 0, 30, tzinfo=timezone(timedelta(hours=2)))
    tasks = [
        {"id": "date-only", "due": "2026-06-02", "overdue": False},
        {"id": "naive", "due": "2026-06-02T00:15:00", "overdue": False},
        {"id": "aware-utc", "due": "2026-06-01T23:00:00+00:00", "overdue": False},
        {"id": "tomorrow", "due": "2026-06-02T22:30:00+00:00", "overdue": False},
    ]

    assert {task["id"] for task in _heute_faellig(tasks, berlin_now)} == {
        "date-only", "naive", "aware-utc",
    }
