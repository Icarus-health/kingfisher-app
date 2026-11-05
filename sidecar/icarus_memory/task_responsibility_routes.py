"""Guarded, explicit responsibility decisions for a saved task."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .task_responsibility import MAX_SEQUENCE, ResponsibilityLookupIncomplete
from .tasks import TaskChangedError, TaskRequestConflict


class _OwnerIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["self", "person"]
    address: str | None = Field(default=None, max_length=254)
    label: str | None = Field(default=None, max_length=120)


class _ResponsibilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1, le=MAX_SEQUENCE)
    confirmed: StrictBool
    operation: Literal["set", "reset", "undo"]
    owner: _OwnerIn | None = None
    target_event_sequence: int | None = Field(default=None, ge=1, le=MAX_SEQUENCE)


def _response(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {**snapshot, "task": snapshot["task"].to_dict()}


def register_task_responsibility_routes(app: FastAPI, guard: list[Any]) -> None:
    @app.get("/api/v1/tasks/{task_id}/responsibility", dependencies=guard)
    def get_responsibility(task_id: str) -> dict[str, Any]:
        try:
            return _response(app.state.tasks.responsibility_snapshot(task_id))
        except KeyError as exc:
            raise HTTPException(404, "Aufgabe nicht gefunden.") from exc
        except ResponsibilityLookupIncomplete as exc:
            raise HTTPException(503, "Aufgabenverlauf konnte nicht vollständig geprüft werden.") from exc

    @app.post("/api/v1/tasks/{task_id}/responsibility", dependencies=guard)
    def change_responsibility(task_id: str, body: _ResponsibilityIn) -> dict[str, Any]:
        if not body.confirmed:
            raise HTTPException(422, "Bitte die Zuständigkeit ausdrücklich bestätigen.")
        fields = body.model_fields_set
        if (("owner" in fields) != (body.operation == "set")
                or ("target_event_sequence" in fields) != (body.operation == "undo")):
            raise HTTPException(422, "Ungültige Änderung der Zuständigkeit.")
        try:
            return _response(app.state.tasks.change_responsibility(
                task_id, request_id=body.request_id, expected_revision=body.expected_revision,
                operation=body.operation, decision=body.owner.model_dump(exclude_unset=True) if body.owner else None,
                target_event_sequence=body.target_event_sequence,
            ))
        except KeyError as exc:
            raise HTTPException(404, "Aufgabe nicht gefunden.") from exc
        except (TaskChangedError, TaskRequestConflict) as exc:
            raise HTTPException(409, str(exc)) from exc
        except ResponsibilityLookupIncomplete as exc:
            raise HTTPException(503, "Aufgabenverlauf konnte nicht vollständig geprüft werden.") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
