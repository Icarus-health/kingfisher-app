"""Validate source chains at retrieval time without changing stored knowledge.

Archiving retained originals is not revocation. Ignored sources and generated
summaries cannot establish facts. A dependency's own sources must still hold,
including dependencies which do not match the conversation's search terms.
"""
from __future__ import annotations

from datetime import datetime

from .claims import Claim, ClaimError, ClaimStore
from .episodes import EpisodeError, EpisodeKind, EpisodeState, EpisodeStore
from .model import Status, now
from .claim_traversal import validate_chain
from .source_snapshot import quote_matches


def evidence_chain_available(
    claim: Claim, claims: ClaimStore, episodes: EpisodeStore,
    *, at: datetime | None = None, max_claims: int = 128, mode: str = "current",
    claim_resolver=None, source_resolver=None,
) -> bool:
    """Fail closed on missing evidence, cycles or an oversized dependency graph.

    Iterative DFS avoids a recursion-limit crash and permits shared ancestors.
    The budget bounds distinct claims, not evidence completeness: every evidence
    entry belonging to a visited claim must pass before it can be supplied.
    """
    if mode not in {"current", "historical"}:
        raise ValueError("Unknown evidence validation mode")
    moment = at or now()

    def check(current: Claim) -> bool:
        if (current.status is Status.REDACTED
                or (mode == "current" and not current.usable(moment))
                or not current.evidence):
            return False
        for evidence in current.evidence:
            source = (source_resolver or episodes.get)(evidence.episode_id)
            if (source.state is EpisodeState.IGNORED
                    or source.kind is EpisodeKind.SUMMARY
                    or not evidence.digest or source.digest != evidence.digest
                    or not quote_matches(evidence.quote, source.body)):
                return False
        return True

    try:
        return validate_chain(claim, claim_resolver or claims.get, check, max_claims=max_claims)
    except (ClaimError, EpisodeError, ValueError, TypeError, AttributeError):
        return False
