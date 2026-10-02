from __future__ import annotations

import pytest

from icarus_memory.model_routing import (
    Candidate, CHIEF_OF_STAFF_TOOLS, RESEARCH_TOOLS, ROLE_SPECS, RoutingError,
    select_candidate,
)


def candidate(id="local", **overrides):
    values = dict(model="model", is_local=True, capabilities=frozenset({"text"}), quality=80, cost=1, latency=1)
    values.update(overrides)
    return Candidate(id, **values)


def test_filters_capability_locality_availability_and_exclusion():
    assert select_candidate(
        [candidate("cloud", is_local=False), candidate("local", available=True)],
        required=frozenset({"text"}), local_only=True,
    ).id == "local"
    with pytest.raises(RoutingError):
        select_candidate([candidate(capabilities=frozenset({"other"}))], required=frozenset({"text"}), local_only=False)


def test_cost_latency_quality_id_ties_are_deterministic():
    result = select_candidate(
        [candidate("z", cost=2, latency=1), candidate("a", cost=2, latency=1)],
        required=frozenset({"text"}), local_only=True,
    )
    assert result.id == "a"


def test_prefer_quality_changes_order_explicitly():
    result = select_candidate(
        [candidate("cheap", quality=60, cost=0), candidate("good", quality=90, cost=5)],
        required=frozenset({"text"}), local_only=True, prefer_quality=True,
    )
    assert result.id == "good"


def test_invalid_candidate_metadata_fails_closed():
    with pytest.raises(RoutingError):
        Candidate("bad", "model", True, frozenset({"text"}), 101, 0, 0)
    with pytest.raises(RoutingError):
        select_candidate([object()], required=frozenset(), local_only=False)


def test_roles_are_explicit_and_research_is_read_only():
    assert ROLE_SPECS["research"].allowed_tools == RESEARCH_TOOLS
    assert "mail_senden" not in RESEARCH_TOOLS
    assert RESEARCH_TOOLS.issubset(CHIEF_OF_STAFF_TOOLS)
