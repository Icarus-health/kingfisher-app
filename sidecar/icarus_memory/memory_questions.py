"""Source-current question projection and explicit resolution for knowledge conflicts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from .claims import ClaimError
from .knowledge_render import KnowledgeInputBuild
from .model import now
from .proposals import ProposalError, ProposalKind, ProposalState


MAX_QUESTIONS = 50


def _is_lint_candidate(candidate: Any) -> bool:
    source = str(getattr(candidate, "proposed_by", "")).strip().casefold()
    return source == "lint" or source.startswith("lint:") or source == "user:lint" or source.startswith("user:lint:")


def _sources(service: Any, evidence_items: list[Any]) -> tuple[list[dict[str, Any]], dict[str, int]] | None:
    sources: dict[tuple[str, str, str], dict[str, Any]] = {}
    ids = {evidence.episode_id for evidence in evidence_items}
    if service._episodes.usable_ids(ids) != ids:
        return None
    generations: dict[str, int] = {}
    snapshots: dict[str, Any] = {}
    for evidence in evidence_items:
        try:
            service._validate(evidence)
            snapshot = snapshots.get(evidence.episode_id)
            if snapshot is None:
                snapshot = service._episodes.support_snapshot(evidence.episode_id)
                snapshots[evidence.episode_id] = snapshot
            if (snapshot is None or snapshot.episode.id != evidence.episode_id
                    or not snapshot.current() or type(snapshot.generation) is not int):
                return None
            episode = snapshot.episode
            generations[evidence.episode_id] = snapshot.generation
        except ClaimError:
            return None
        key = (evidence.episode_id, evidence.digest, evidence.quote)
        sources[key] = {
            "episode_id": episode.id,
            "title": episode.title,
            "quote": evidence.quote,
            "occurred_at": episode.occurred_at.isoformat() if episode.occurred_at else None,
            "recorded_at": episode.recorded_at.isoformat(),
        }
    if not sources:
        return None
    return [sources[key] for key in sorted(sources)], dict(sorted(generations.items()))


def _dependency_generations(service: Any, dependency_ids: list[str], *, at: datetime) -> dict[str, int] | None:
    """Capture the full, currently supported evidence chain behind each dependency."""
    if not dependency_ids:
        return {}
    build = KnowledgeInputBuild(service._claims, service._episodes.support_snapshot, at=at)
    generations: dict[str, int] = {}
    try:
        for identifier in sorted(set(dependency_ids)):
            captured = build.capture(identifier)
            if captured is None:
                return None
            generations.update(captured[2]["source_generations"])
    except (ClaimError, ValueError, TypeError, AttributeError, OverflowError):
        return None
    return dict(sorted(generations.items()))


def _candidate_is_current(candidate: Any, *, at: datetime) -> bool:
    return ((candidate.valid_from is None or candidate.valid_from <= at)
            and (candidate.valid_until is None or at < candidate.valid_until))


def _current_questions(app: Any, *, at: datetime) -> list[dict[str, Any]]:
    service = app.state.knowledge_service
    pending_by_id = {candidate.id: candidate for candidate in service.pending()}
    questions: list[dict[str, Any]] = []
    for raw in service.clarifications():
        candidates: list[dict[str, Any]] = []
        support_fingerprints: dict[str, Any] = {"candidates": {}, "active_claims": {}}
        for candidate_id in {item["id"] for item in raw["candidates"]}:
            candidate = pending_by_id.get(candidate_id)
            if candidate is None:
                continue
            if candidate.kind is not ProposalKind.KNOWLEDGE or _is_lint_candidate(candidate):
                continue
            if not _candidate_is_current(candidate, at=at):
                continue
            source_result = _sources(service, candidate.evidence)
            dependency_generations = _dependency_generations(service, candidate.depends_on, at=at)
            if source_result is not None and dependency_generations is not None:
                sources, source_generations = source_result
                candidates.append({**candidate.to_dict(), "sources": sources})
                support_fingerprints["candidates"][candidate.id] = {
                    "sources": source_generations,
                    "dependencies": dependency_generations,
                }

        active_claims: list[dict[str, Any]] = []
        for raw_claim in raw["active_claims"]:
            claim = app.state.claims.get(raw_claim["id"])
            if not claim.usable(at) or not app.state.claims.is_usable(claim, at=at):
                continue
            captured = KnowledgeInputBuild(
                service._claims, service._episodes.support_snapshot, at=at
            ).capture(claim.id)
            source_result = _sources(service, claim.evidence)
            if captured is not None and source_result is not None:
                sources, source_generations = source_result
                active_claims.append({**claim.to_dict(), "sources": sources})
                support_fingerprints["active_claims"][claim.id] = {
                    "sources": source_generations,
                    "chain": captured[2]["source_generations"],
                }

        candidates.sort(key=lambda item: item["id"])
        active_claims.sort(key=lambda item: item["id"])

        if not candidates or not (len(candidates) > 1 or active_claims):
            continue

        # Bind the choice to the complete visible conflict set and its exact,
        # currently validated source projections. No friendly-name lookup.
        stand_payload = {
            "subject_ref": raw["subject_ref"],
            "predicate": raw["predicate"],
            "scope_ref": raw["scope_ref"],
            "candidates": candidates,
            "active_claims": active_claims,
            "support_fingerprints": support_fingerprints,
        }
        stand = hashlib.sha256(json.dumps(
            stand_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        questions.append({
            "id": raw["id"],
            "stand": stand,
            "subject_ref": raw["subject_ref"],
            "predicate": raw["predicate"],
            "scope_ref": raw["scope_ref"],
            "candidates": candidates,
            "active_claims": active_claims,
            "decision_required": True,
        })
    return sorted(questions, key=lambda item: item["id"])[:MAX_QUESTIONS + 1]


def list_questions(app: Any) -> list[dict[str, Any]]:
    """List bounded conflict questions whose candidates and active evidence are current."""
    with app.state.conversation_lock:
        return _current_questions(app, at=now())


def resolve_question(
    app: Any,
    question_id: str,
    *,
    stand: str,
    proposal_id: str | None,
) -> dict[str, Any]:
    """Resolve only the exact, still-current question the user reviewed.

    Choosing a candidate accepts that explicit proposal and supersedes only
    the active claims shown in the current question. ``None`` means keep an
    existing active claim and reject the displayed pending candidates; it
    never creates a fact.
    """
    with app.state.conversation_lock:
        moment = now()
        question = next((item for item in _current_questions(app, at=moment)
                         if item["id"] == question_id), None)
        if question is None or question["stand"] != stand:
            raise HTTPException(status_code=409, detail="Die Klärung oder ihre Quelle hat sich geändert. Bitte neu prüfen.")

        candidate_ids = {item["id"] for item in question["candidates"]}
        active_ids = sorted(item["id"] for item in question["active_claims"])
        service = app.state.knowledge_service
        if proposal_id is not None:
            if proposal_id not in candidate_ids:
                raise HTTPException(status_code=409, detail="Der gewählte Vorschlag gehört nicht mehr zu dieser Klärung.")
            try:
                claim = service.accept(proposal_id, supersedes=active_ids, at=moment)
            except (ClaimError, ProposalError) as exc:
                raise HTTPException(status_code=409, detail="Die Klärung ist nicht mehr aktuell. Bitte neu prüfen.") from exc
            return {"id": question_id, "decision": "accepted", "claim": claim.to_dict()}

        if not active_ids:
            raise HTTPException(status_code=409, detail="Es gibt keine aktuell bestätigte Aussage zum Beibehalten.")
        try:
            for candidate_id in candidate_ids:
                service.reject(candidate_id, at=moment)
        except ProposalError as exc:
            raise HTTPException(status_code=409, detail="Die Klärung ist nicht mehr aktuell. Bitte neu prüfen.") from exc
        return {"id": question_id, "decision": "kept", "claim_ids": active_ids}


__all__ = ["list_questions", "resolve_question"]
