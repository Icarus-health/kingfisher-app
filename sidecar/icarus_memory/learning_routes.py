"""Protected HTTP routes for explicit habits and learning proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .source_versions import invalidate_with_corrections
from . import habits
from .claims import ClaimError
from .learning_service import propose_patterns
from .proposals import ProposalError, ProposalState
from .store import ConflictError


class HabitIn(BaseModel):
    label: str = Field(min_length=1, max_length=4000)
    target_per_week: int = Field(ge=1, le=7)


class CheckinIn(BaseModel):
    day: str = Field(min_length=1)
    note: str = Field(default="", max_length=4000)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _learning_items(app: FastAPI) -> list[dict[str, Any]]:
    result = []
    for proposal in app.state.proposals.from_origin_prefix("habit-pattern:"):
        if not proposal.proposed_by.startswith("habit-pattern:"):
            continue
        item = proposal.to_dict()
        claim = None
        if proposal.produced:
            try:
                claim = app.state.claims.get(proposal.produced).to_dict()
            except Exception:  # stale/deleted claim remains an auditable proposal
                claim = None
        item["claim"] = claim
        result.append(item)
    return sorted(result, key=lambda item: item["created_at"], reverse=True)


def register_learning_routes(app: FastAPI, guard: list[Any]) -> None:
    dependencies = guard

    @app.get("/api/v1/habits", dependencies=dependencies)
    def get_habits() -> dict[str, Any]:
        return {"items": habits.list_habits(app.state.store, app.state.episodes, _now())}

    @app.post("/api/v1/habits", dependencies=dependencies, status_code=201)
    def post_habit(body: HabitIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                return habits.create_habit(app.state.store, body.label, body.target_per_week).to_dict()
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/habits/{habit_id}/checkins", dependencies=dependencies)
    def post_checkin(habit_id: str, body: CheckinIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                return habits.check_in(app.state.store, app.state.episodes, habit_id, body.day, body.note, at=_now())
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except ConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/habits/{habit_id}/retract", dependencies=dependencies)
    def post_retract_habit(habit_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                return habits.retract_habit(app.state.store, habit_id).to_dict()
            except ConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/habits/checkins/{episode_id}/retract", dependencies=dependencies)
    def post_retract_checkin(episode_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                episode = app.state.episodes.get(episode_id)
                if not any(str(tag).startswith("habit:") for tag in (episode.tags or [])):
                    raise ConflictError("Dies ist kein Gewohnheits-Check-in.")
                invalidate_with_corrections(app.state.episodes, app.state.claims, episode_id, at=_now())
                return habits.retract_checkin(app.state.episodes, episode_id).to_dict()
            except ConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=404, detail="Check-in nicht gefunden.") from exc

    @app.get("/api/v1/learning", dependencies=dependencies)
    def get_learning() -> dict[str, Any]:
        return {"items": _learning_items(app)}

    @app.post("/api/v1/learning/scan", dependencies=dependencies)
    def scan_learning() -> dict[str, Any]:
        with app.state.conversation_lock:
            found = propose_patterns(app.state.store, app.state.episodes, app.state.proposals,
                                     app.state.knowledge_service, at=_now())
            return {"items": [item.to_dict() for item in found]}

    @app.post("/api/v1/learning/{proposal_id}/accept", dependencies=dependencies)
    def accept_learning(proposal_id: str) -> dict[str, Any]:
        try:
            proposal = app.state.proposals.get(proposal_id)
            if not proposal.proposed_by.startswith("habit-pattern:"):
                raise HTTPException(status_code=404, detail="Lernvorschlag nicht gefunden.")
            with app.state.conversation_lock:
                current = propose_patterns(app.state.store, app.state.episodes, app.state.proposals,
                                            app.state.knowledge_service, at=_now())
                current_ids = {item.id for item in current}
                if proposal_id not in current_ids:
                    raise HTTPException(status_code=409, detail="Der Vorschlag ist nicht mehr aktuell.")
                claim = app.state.knowledge_service.accept(proposal_id, supersedes=[], at=_now())
                return claim.to_dict()
        except HTTPException:
            raise
        except ProposalError as exc:
            raise HTTPException(status_code=404, detail="Lernvorschlag nicht gefunden.") from exc
        except (ClaimError, ConflictError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/learning/{proposal_id}/reject", dependencies=dependencies)
    def reject_learning(proposal_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                proposal = app.state.proposals.get(proposal_id)
                if not proposal.proposed_by.startswith("habit-pattern:"):
                    raise HTTPException(status_code=404, detail="Lernvorschlag nicht gefunden.")
                return app.state.knowledge_service.reject(proposal_id).to_dict()
            except HTTPException:
                raise
            except ProposalError as exc:
                raise HTTPException(status_code=404, detail="Lernvorschlag nicht gefunden.") from exc
            except ClaimError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc


__all__ = ["register_learning_routes"]
