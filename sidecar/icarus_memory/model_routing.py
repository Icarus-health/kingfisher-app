"""Deterministic, fail-closed selection of a model candidate.

This module deliberately has no provider or network knowledge.  A caller may
record the returned candidate and the inputs as part of its handoff audit.
"""

from __future__ import annotations

from dataclasses import dataclass


class RoutingError(ValueError):
    """Routing could not produce a safe, valid candidate."""


@dataclass(frozen=True)
class Candidate:
    id: str
    model: str
    is_local: bool
    capabilities: frozenset[str]
    quality: int
    cost: int
    latency: int
    available: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise RoutingError("candidate id must be a non-empty string")
        if not isinstance(self.model, str) or not self.model.strip():
            raise RoutingError("candidate model must be a non-empty string")
        if not isinstance(self.is_local, bool) or not isinstance(self.available, bool):
            raise RoutingError("candidate locality and availability must be boolean")
        if not isinstance(self.capabilities, frozenset) or any(
            not isinstance(capability, str) or not capability.strip()
            for capability in self.capabilities
        ):
            raise RoutingError("candidate capabilities must be a frozenset of names")
        if isinstance(self.quality, bool) or not isinstance(self.quality, int) or not 0 <= self.quality <= 100:
            raise RoutingError("candidate quality must be an integer from 0 to 100")
        for name, value in (("cost", self.cost), ("latency", self.latency)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RoutingError(f"candidate {name} must be a non-negative integer")


@dataclass(frozen=True)
class RoleSpec:
    name: str
    allowed_tools: frozenset[str]


# Names correspond to the current build_registry() contract in tools.py.
RESEARCH_TOOLS = frozenset({
    "aktuelle_zeit", "aufgaben", "datei_lesen", "episode_lesen",
    "episoden_suchen", "gedaechtnis_suchen", "notizen_suchen", "notiz_lesen",
    "projekt_stand", "projekte", "termine", "web_abruf",
})

CHIEF_OF_STAFF_TOOLS = frozenset({
    *RESEARCH_TOOLS,
    "aufgabe_anlegen", "aufgabe_erledigt", "notiz_anlegen", "projekt_anlegen",
    "projekt_status", "termin_anlegen", "gedaechtnis_vorschlagen",
})

ROLE_SPECS = {
    "chief_of_staff": RoleSpec("chief_of_staff", CHIEF_OF_STAFF_TOOLS),
    "research": RoleSpec("research", RESEARCH_TOOLS),
}

# Convenient named exports for callers that do not need the registry mapping.
chief_of_staff = ROLE_SPECS["chief_of_staff"]
research = ROLE_SPECS["research"]


def select_candidate(
    candidates: list[Candidate] | tuple[Candidate, ...],
    *,
    required: frozenset[str],
    local_only: bool,
    min_quality: int = 0,
    prefer_quality: bool = False,
    excluded: frozenset[str] = frozenset(),
) -> Candidate:
    """Select the best eligible candidate using stable, inspectable ordering."""
    if not isinstance(required, frozenset) or any(not isinstance(x, str) or not x.strip() for x in required):
        raise RoutingError("required capabilities must be a frozenset of names")
    if not isinstance(excluded, frozenset) or any(not isinstance(x, str) for x in excluded):
        raise RoutingError("excluded candidate ids must be a frozenset of strings")
    if not isinstance(local_only, bool) or isinstance(min_quality, bool) or not isinstance(min_quality, int) or not 0 <= min_quality <= 100:
        raise RoutingError("invalid routing constraints")
    if not isinstance(candidates, (list, tuple)):
        raise RoutingError("candidates must be a list or tuple")
    # Validate every supplied record before filtering: malformed metadata must
    # never be hidden by availability, locality, or exclusion.
    for candidate in candidates:
        if not isinstance(candidate, Candidate):
            raise RoutingError("all candidates must be Candidate records")

    eligible = [
        candidate for candidate in candidates
        if candidate.available
        and (not local_only or candidate.is_local)
        and candidate.quality >= min_quality
        and required.issubset(candidate.capabilities)
        and candidate.id not in excluded
    ]
    if not eligible:
        raise RoutingError("no eligible model candidate")
    if prefer_quality:
        key = lambda c: (-c.quality, c.cost, c.latency, c.id)
    else:
        key = lambda c: (c.cost, c.latency, -c.quality, c.id)
    return min(eligible, key=key)


__all__ = [
    "Candidate", "RoutingError", "RoleSpec", "ROLE_SPECS",
    "RESEARCH_TOOLS", "CHIEF_OF_STAFF_TOOLS", "chief_of_staff", "research",
    "select_candidate",
]
