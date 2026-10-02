"""Bounded iterative lineage traversal, shared by status and evidence checks."""
from collections.abc import Callable
from typing import Any


def validate_chain(claim: Any, load: Callable, check: Callable, *, max_claims: int = 128,
                   excluded: frozenset[str] = frozenset()) -> bool:
    pending = [(claim, False)]
    visiting: set[str] = set()
    verified: set[str] = set()
    while pending:
        current, leaving = pending.pop()
        identifier = current if isinstance(current, str) else current.id
        if leaving:
            visiting.remove(identifier)
            verified.add(identifier)
            continue
        if identifier in verified:
            continue
        if identifier in excluded or identifier in visiting or len(visiting) + len(verified) >= max_claims:
            return False
        if isinstance(current, str):
            current = load(current)
        if not check(current):
            return False
        dependencies = set(current.depends_on)
        if len(dependencies | visiting | verified | {identifier}) > max_claims:
            return False
        visiting.add(identifier)
        pending.append((current, True))
        pending.extend((dependency, False) for dependency in dependencies)
    return True
