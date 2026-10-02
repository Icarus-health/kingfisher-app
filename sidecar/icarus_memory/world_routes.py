"""Protected HTTP routes for explicitly registered world sources."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import config
from .model import Kind, Status
from .world_monitor import WorldMonitor


class WorldSourceIn(BaseModel):
    url: str
    label: str
    topics: list[str] = Field(default_factory=list, max_length=10)


def _state(app):
    return getattr(app, "currentstate", None) or app.state


def register_world_routes(app, guard, data_dir):
    state = _state(app)
    import threading
    existing = getattr(app.state, "world_monitor", None)

    def monitor_for_current_state():
        current = _state(app)
        monitor = getattr(app.state, "world_monitor", None)
        if (monitor is None or monitor.settings is not current.settings
                or monitor.episodes is not current.episodes or monitor.claims is not current.claims):
            monitor = WorldMonitor(
                current.settings, current.episodes, current.claims,
                lambda settings: config.save(data_dir(), settings),
                getattr(current, "conversation_lock", None) or getattr(current, "lock", None) or threading.RLock(),
                fetch=getattr(existing, "fetch", None) or getattr(monitor, "fetch", None) or None,
            )
            if monitor.fetch is None:
                from .world_sources import fetch_public_text
                monitor.fetch = fetch_public_text
            app.state.world_monitor = monitor
        return monitor, current

    def goals_for(items: list[dict[str, Any]], current) -> list[dict[str, Any]]:
        store = getattr(current, "store", None)
        if store is None:
            return items
        goals = []
        try:
            active = store.usable()
        except TypeError:
            active = store.usable(None)
        for goal in active:
            if goal.kind is not Kind.GOAL or goal.status is not Status.ACTIVE:
                continue
            if (goal.structured or {}).get("domain") == "habit":
                continue
            goals.append(goal)
        for item in items:
            topics = {str(topic).casefold() for topic in item.get("topics", [])}
            matches = [goal for goal in goals if topics & {str(tag).casefold() for tag in (goal.tags or [])}]
            item["matched_goals"] = [{"id": goal.id, "statement": goal.statement} for goal in matches]
        return items

    @app.get("/api/v1/world", dependencies=guard)
    def world_list():
        monitor, current = monitor_for_current_state()
        return {"items": goals_for(monitor.list(), current)}

    @app.post("/api/v1/world", dependencies=guard, status_code=201)
    def world_add(body: WorldSourceIn):
        if any(len(topic) > 80 for topic in body.topics):
            raise HTTPException(422, "Themen dürfen höchstens 80 Zeichen lang sein.")
        try:
            monitor, _current = monitor_for_current_state()
            result = monitor.add(body.url, body.label, body.topics)
        except Exception as exc:
            raise HTTPException(422, "Die Quelle konnte nicht registriert werden.") from exc
        result["matched_goals"] = []
        return result

    @app.post("/api/v1/world/{source_id}/refresh", dependencies=guard)
    def world_refresh(source_id: str):
        try:
            monitor, current = monitor_for_current_state()
            result = monitor.refresh(source_id)
        except KeyError as exc:
            raise HTTPException(404, "Quelle nicht gefunden.") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"item": goals_for([result], current)[0]}

    @app.post("/api/v1/world/{source_id}/disable", dependencies=guard)
    def world_disable(source_id: str):
        try:
            monitor, current = monitor_for_current_state()
            monitor.disable(source_id)
        except KeyError as exc:
            raise HTTPException(404, "Quelle nicht gefunden.") from exc
        return {"items": goals_for(monitor.list(), current)}

    return monitor_for_current_state()[0]


__all__ = ["register_world_routes"]
