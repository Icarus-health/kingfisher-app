"""Explicit habits backed by the existing self-model and episode stores."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeKind
from .model import Kind, Provenance, Sensitivity, SourceType, Status
from .store import ConflictError, SelfModelStore


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Zeitpunkte müssen eine Zeitzone tragen.")
    return value.astimezone(timezone.utc)


def _active(store: SelfModelStore, at: datetime) -> list[Any]:
    return [a for a in store.usable(at) if a.kind is Kind.GOAL
            and a.status is Status.ACTIVE and (a.structured or {}).get("domain") == "habit"]


def create_habit(store: SelfModelStore, label: str, target_per_week: int):
    label = str(label).strip()
    if not label:
        raise ValueError("Eine Gewohnheit braucht eine Bezeichnung.")
    if (not isinstance(target_per_week, int) or isinstance(target_per_week, bool)
            or not 1 <= target_per_week <= 7):
        raise ValueError("target_per_week muss zwischen 1 und 7 liegen.")
    return store.record(
        f"Gewohnheit: {label}", Kind.GOAL,
        Provenance(source_type=SourceType.USER_STATED, source_ref="ui:habits",
                   verbatim=f"Gewohnheit: {label}"),
        sensitivity=Sensitivity.SENSITIVE,
        structured={"domain": "habit", "label": label, "target_per_week": target_per_week},
    )


def _week(at: datetime) -> tuple[date, date]:
    day = _utc(at).date()
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def _checkin_records(episodes: Any, habit_id: str, start: date, end: date,
                     reference: datetime) -> list[dict[str, str]]:
    records = {}
    for episode in episodes.tagged_raw([f"habit:{habit_id}"]):
        if getattr(episode, "kind", None) is EpisodeKind.SUMMARY or getattr(episode, "state", None) in AUSGEBLENDETE_ZUSTAENDE:
            continue
        if f"habit:{habit_id}" not in (getattr(episode, "tags", []) or []):
            continue
        try:
            moment = _utc(episode.reference_time())
            day = moment.date()
        except (AttributeError, TypeError, ValueError):
            continue
        if moment <= reference and start <= day <= end:
            records[day.isoformat()] = {"episode_id": str(episode.id), "day": day.isoformat()}
    return [records[key] for key in sorted(records)]


def list_habits(store: SelfModelStore, episodes: Any, at: datetime) -> list[dict[str, Any]]:
    reference = _utc(at)
    start, end = _week(reference)
    result = []
    for habit in _active(store, reference):
        content = habit.structured or {}
        records = _checkin_records(episodes, habit.id, start, end, reference)
        days = {date.fromisoformat(record['day']) for record in records}
        result.append({
            "id": habit.id,
            "label": content["label"],
            "target_per_week": content["target_per_week"],
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "checkins": len(days),
            "observed_days": sorted(day.isoformat() for day in days),
            "checkin_records": records,
        })
    return sorted(result, key=lambda item: (item["label"].casefold(), item["id"]))


def check_in(store: SelfModelStore, episodes: Any, habit_id: str, day: str,
             note: str = "", *, at: datetime | None = None) -> dict[str, Any]:
    reference = _utc(at or datetime.now(timezone.utc))
    try:
        checked_day = date.fromisoformat(day)
    except (TypeError, ValueError) as exc:
        raise ValueError("day muss YYYY-MM-DD sein.") from exc
    if not isinstance(day, str) or day != checked_day.isoformat():
        raise ValueError("day muss kanonisch als YYYY-MM-DD angegeben werden.")
    if checked_day > reference.date():
        raise ValueError("Ein Check-in in der Zukunft ist nicht möglich.")
    habit = next((item for item in _active(store, reference) if item.id == habit_id), None)
    if habit is None:
        raise ConflictError("Diese Gewohnheit ist nicht mehr aktiv.")
    content = habit.structured or {}
    source_ref = f"habit:{habit.id}:{checked_day.isoformat()}"
    existing = episodes.by_source_ref(source_ref)
    if existing is not None:
        if existing.state in AUSGEBLENDETE_ZUSTAENDE:
            raise ConflictError("Dieser Check-in wurde zurückgenommen. Die Quelle muss ausdrücklich wieder zugelassen werden.")
        return {"created": False, "habit_id": habit.id, "day": checked_day.isoformat(), "episode": existing.to_dict()}
    text = str(note).strip() or f"Check-in: {content['label']}"
    occurred = reference if checked_day == reference.date() else datetime.combine(checked_day, time(12), tzinfo=timezone.utc)
    episode, created = episodes.record(
        EpisodeKind.OBSERVATION, f"Check-in: {content['label']}", text,
        Provenance(source_type=SourceType.USER_STATED, source_ref=source_ref, captured_at=reference,
                   verbatim=text), occurred_at=occurred, at=reference,
        tags=[f"habit:{habit.id}"], source_key=source_ref,
    )
    return {"created": created, "habit_id": habit.id, "day": checked_day.isoformat(), "episode": episode.to_dict()}


def retract_habit(store: SelfModelStore, habit_id: str):
    habit = next((item for item in store.usable() if item.id == habit_id
                  and item.kind is Kind.GOAL
                  and (item.structured or {}).get("domain") == "habit"), None)
    if habit is None:
        raise ConflictError("Diese Gewohnheit ist nicht mehr aktiv.")
    return store.retract(habit.id)


def retract_checkin(episodes: Any, episode_id: str):
    """Exclude an incorrect check-in while retaining its raw evidence."""
    episode = episodes.get(episode_id)
    if not any(str(tag).startswith("habit:") for tag in (getattr(episode, "tags", []) or [])):
        raise ConflictError("Dies ist kein Gewohnheits-Check-in.")
    return episodes.ignore(episode_id)


__all__ = ["create_habit", "list_habits", "check_in", "retract_habit", "retract_checkin"]
