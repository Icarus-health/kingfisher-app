"""Ausdrückliche Zielabschlüsse im bestehenden Selbstmodell, ohne zweite Ablage."""
from .model import Kind, Provenance, SourceType, Status
from .store import ConflictError, SelfModelStore


def finish(store: SelfModelStore, goal_id: str, outcome: str, note: str = ""):
    if outcome not in ("achieved", "stopped"):
        raise ValueError("Unbekannter Zielabschluss.")
    goal = next((item for item in store.usable() if item.id == goal_id), None)
    if goal is None or goal.kind is not Kind.GOAL:
        raise ConflictError("Dieses Ziel ist nicht mehr offen. Bitte neu laden.")
    label = "Ziel erreicht" if outcome == "achieved" else "Ziel wird nicht mehr verfolgt"
    statement = f"{label}: {goal.statement}"
    if note.strip():
        statement += f" Begründung: {note.strip()}"
    return store.record(
        statement, Kind.STATE,
        Provenance(source_type=SourceType.USER_STATED, source_ref="ui:goals", verbatim=statement),
        supersedes=[goal.id], derived_from=[goal.id], sensitivity=goal.sensitivity, tags=goal.tags,
        structured={"goal_outcome": outcome, "goal_id": goal.id, "note": note.strip()},
    )


def completed(store: SelfModelStore) -> list[dict]:
    all_items = {item.id: item for item in store.alles()}
    result = []
    for item in store.usable():
        data = item.structured or {}
        if item.kind is not Kind.STATE or data.get("goal_outcome") not in ("achieved", "stopped"):
            continue
        goal = all_items.get(data.get("goal_id"))
        if goal is None or goal.kind is not Kind.GOAL or goal.status is Status.REDACTED:
            continue
        result.append({"id": item.id, "goal_id": goal.id, "statement": goal.statement,
                       "outcome": data["goal_outcome"], "note": data.get("note", ""),
                       "recorded_at": item.recorded_at.isoformat()})
    return sorted(result, key=lambda item: item["recorded_at"], reverse=True)


def reopen(store: SelfModelStore, completion_id: str):
    completion = next((item for item in store.usable() if item.id == completion_id), None)
    data = completion.structured if completion else None
    if completion is None or completion.kind is not Kind.STATE or not data or data.get("goal_outcome") not in ("achieved", "stopped"):
        raise ConflictError("Dieser Abschluss ist nicht mehr aktuell. Bitte neu laden.")
    goal = next((item for item in store.alles() if item.id == data.get("goal_id")), None)
    if goal is None or goal.kind is not Kind.GOAL or goal.status is not Status.SUPERSEDED:
        raise ConflictError("Die ursprüngliche Zielangabe ist nicht mehr verfügbar.")
    return store.record(
        goal.statement, Kind.GOAL,
        Provenance(source_type=SourceType.USER_STATED, source_ref="ui:goals:reopen",
                   verbatim=f"Ziel wieder aufnehmen: {goal.statement}"),
        supersedes=[completion.id], derived_from=[completion.id],
        sensitivity=goal.sensitivity, tags=goal.tags,
    )
