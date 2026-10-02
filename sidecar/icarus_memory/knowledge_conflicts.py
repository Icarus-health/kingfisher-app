"""Bounded, source-checked warning for pending alternatives to accepted knowledge.

This is a status gate, not a source of answer text. A pending proposal never
becomes an accepted fact or a model input through this module.
"""
from __future__ import annotations

from time import monotonic

from . import knowledge_context
from .claims import ClaimError, statements_conflict
from .episodes import EpisodeError, EpisodeKind, EpisodeState
from .knowledge_render import KnowledgeInputBuild
from .proposals import ProposalError, ProposalKind, ProposalState
from .source_snapshot import quote_matches


CONFLICT_MESSAGE = (
    "Zu dieser gespeicherten Aussage gibt es einen noch ungeklärten möglichen Widerspruch. "
    "Bitte prüfe die Alternativen im Gedächtnis, bevor du dich darauf verlässt."
)
UNCHECKED_MESSAGE = (
    "Ob zu dieser gespeicherten Aussage ein offener Widerspruch vorliegt, "
    "konnte ich gerade nicht vollständig prüfen. Bitte prüfe das Gedächtnis."
)
MESSAGES = {"conflict": CONFLICT_MESSAGE, "unchecked": UNCHECKED_MESSAGE}


def _candidate_evidence(candidate, build, at, source_snapshots) -> str:
    """Return valid, withdrawn, or unchecked without returning source content."""
    if not candidate.evidence:
        return "unchecked"
    try:
        if ((candidate.valid_from is not None and at < candidate.valid_from)
                or (candidate.valid_until is not None and at >= candidate.valid_until)):
            return "withdrawn"
        for dependency_id in candidate.depends_on:
            dependency = build.claim(dependency_id)
            if not build.claims.is_usable(dependency, at=at):
                return "withdrawn"
            if build.capture(dependency_id) is None:
                return "unchecked"
        for evidence in candidate.evidence:
            if evidence.episode_id not in source_snapshots:
                if len(source_snapshots) >= 128 or build.snapshot_provider is None:
                    return "unchecked"
                source_snapshots[evidence.episode_id] = build.snapshot_provider(evidence.episode_id)
            snapshot = source_snapshots[evidence.episode_id]
            if snapshot is None or snapshot.episode.id != evidence.episode_id:
                return "unchecked"
            source = snapshot.episode
            if (source.state is EpisodeState.IGNORED
                    or source.kind is EpisodeKind.SUMMARY
                    or not snapshot.current()):
                return "withdrawn"
            if (not evidence.digest or evidence.digest != source.digest
                    or not quote_matches(evidence.quote, source.body)):
                return "unchecked"
        return "valid"
    except (ClaimError, EpisodeError, ValueError, TypeError, AttributeError,
            OverflowError, LookupError):
        return "unchecked"


def check(claim_ids, claims, proposals, episodes, *, snapshot_provider=None) -> str:
    """Check exact selected claim IDs: clear, conflict, or unchecked.

    The gate is conservative when the bounded scan or source validation cannot
    establish an answer. Each call starts with a fresh source and claim build.
    """
    if not isinstance(claim_ids, (list, tuple)):
        return "unchecked"
    if not claim_ids:
        return "clear"
    if (len(claim_ids) > 128 or claims is None or proposals is None
            or episodes is None):
        return "unchecked"
    ids = [item.removeprefix("claim:") if isinstance(item, str) else "" for item in claim_ids]
    if any(not item for item in ids):
        return "unchecked"
    deadline = monotonic() + 1.0
    scan_calls = 0

    def scan_exhausted() -> bool:
        # SQLite calls this every 1,000 VM steps. The count is shared across
        # all exact subject queries in this answer, not reset for each group.
        nonlocal scan_calls
        scan_calls += 1
        return scan_calls > 2000 or monotonic() >= deadline

    at = knowledge_context.now()
    build = KnowledgeInputBuild(
        claims, snapshot_provider or getattr(episodes, "support_snapshot", None), at=at
    )
    source_snapshots = {}
    try:
        roots = []
        for identifier in dict.fromkeys(ids):
            captured = build.capture(identifier)
            if captured is None:
                return "unchecked"
            roots.append(captured[0])
        # Include transitive dependencies: a pending correction of a premise
        # matters to an answer derived from that premise.
        relevant = dict.fromkeys(root.id for root in roots)
        remaining = [dependency for root in roots for dependency in root.depends_on]
        while remaining:
            identifier = remaining.pop()
            if identifier in relevant:
                continue
            if len(relevant) >= 128:
                return "unchecked"
            captured = build.capture(identifier)
            if captured is None:
                return "unchecked"
            dependency = captured[0]
            relevant[identifier] = None
            remaining.extend(dependency.depends_on)
        active = [build.claim(identifier) for identifier in relevant]
        groups = sorted({(claim.subject_ref, claim.scope_ref) for claim in active},
                        key=lambda item: (item[0], item[1] or ""))
        remaining_candidates = 500
        for subject_ref, scope_ref in groups:
            candidates, complete = proposals.pending_knowledge_for_subject(
                subject_ref, scope_ref, limit=remaining_candidates,
                scan_guard=scan_exhausted,
            )
            if not complete:
                return "unchecked"
            remaining_candidates -= len(candidates)
            matching_claims = [claim for claim in active
                               if claim.subject_ref == subject_ref and claim.scope_ref == scope_ref]
            for candidate in candidates:
                if (candidate.kind is not ProposalKind.KNOWLEDGE
                        or candidate.state is not ProposalState.PENDING):
                    return "unchecked"
                if not any(statements_conflict(candidate, claim) for claim in matching_claims):
                    continue
                status = _candidate_evidence(candidate, build, at, source_snapshots)
                if status == "valid":
                    return "unchecked" if scan_exhausted() else "conflict"
                if status == "unchecked":
                    return "unchecked"
        return "unchecked" if scan_exhausted() else "clear"
    except (ClaimError, EpisodeError, ProposalError, ValueError, TypeError,
            AttributeError, OverflowError, LookupError):
        return "unchecked"


__all__ = ["check", "CONFLICT_MESSAGE", "UNCHECKED_MESSAGE", "MESSAGES"]
