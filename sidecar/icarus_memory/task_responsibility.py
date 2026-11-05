"""Canonical commands for a local user's decision about one task."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from .episodes import mail_address

RESPONSIBILITY_KINDS = {
    "set": "responsibility_confirmed",
    "reset": "responsibility_reset",
    "undo": "responsibility_undone",
}
MAX_SEQUENCE = 2**63 - 1
_MAX_CITATION_TEXT = 256_000
_MAX_OCCURRENCE_STEPS = 128
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
_LOCAL_PART = re.compile(r"[\w!#$%&'*+\-/=?^`{|}~]+(?:\.[\w!#$%&'*+\-/=?^`{|}~]+)*")
_DOMAIN_LABEL = re.compile(r"[^\W_](?:(?:[^\W_]|-){0,61}[^\W_])?")


class ResponsibilityLookupIncomplete(RuntimeError):
    """A bounded history scan could not establish the current state or receipt."""


def citations_may_overlap(previous: str, incoming: str, source_text: str | None) -> bool:
    """Hold a changed citation for review unless its positions are provably disjoint."""
    if not previous or not incoming or max(len(previous), len(incoming)) > _MAX_CITATION_TEXT:
        return True
    if previous in incoming or incoming in previous:
        return True
    if source_text is None or len(source_text) > _MAX_CITATION_TEXT:
        return True
    earlier, later = source_text.find(previous), source_text.find(incoming)
    if earlier < 0 or later < 0:
        return True

    # Walk the two ordered occurrence streams. Check all possible positions
    # within the budget because a quote may appear more than once in one source.
    for _ in range(_MAX_OCCURRENCE_STEPS):
        if earlier + len(previous) <= later:
            earlier = source_text.find(previous, earlier + 1)
            if earlier < 0:
                return False
        elif later + len(incoming) <= earlier:
            later = source_text.find(incoming, later + 1)
            if later < 0:
                return False
        else:
            return True
    return True


def _sequence(value: object) -> bool:
    return type(value) is int and 1 <= value <= MAX_SEQUENCE


def _bounded_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        return None
    if any(unicodedata.category(char).startswith("C") for char in value):
        return None
    return value.strip() or None


def unknown_responsibility() -> dict[str, Any]:
    return {"version": 1, "decision": "unknown", "address": None, "label": None}


def _owner(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        if value.get("decision") == "self" and value.keys() == {"decision"}:
            return {**unknown_responsibility(), "decision": "self"}
        if value.get("decision") == "person" and value.keys() <= {"decision", "address", "label"}:
            raw = _bounded_text(value.get("address"), 254)
            if raw and raw.count("@") == 1:
                # Contact identity uses the existing normalization. Accept a bare
                # address only: extracting one from a header could change the choice.
                address = mail_address(raw)
                local, _, domain = raw.partition("@")
                if (address == raw.casefold() and len(address) <= 254 and len(local) <= 64
                        and _LOCAL_PART.fullmatch(local) and "." in domain
                        and all(_DOMAIN_LABEL.fullmatch(part) for part in domain.split("."))):
                    label = _bounded_text(value.get("label"), 120)
                    if "label" in value and label is None:
                        raise ValueError("Der Anzeigename muss 1 bis 120 Zeichen enthalten.")
                    return {"version": 1, "decision": "person", "address": address, "label": label}
    raise ValueError("Bitte „Ich“ oder eine Person mit vollständiger Mailadresse auswählen.")


def responsibility_command(
    request_id: str, expected_revision: int, operation: str,
    decision: dict[str, Any] | None, target_event_sequence: int | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return the canonical new state (resolved later for undo) and bounded receipt."""
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        raise ValueError("Ungültige Auftragskennung.")
    if not _sequence(expected_revision):
        raise ValueError("Ungültige Aufgabenrevision.")
    if operation == "set" and target_event_sequence is None:
        state = _owner(decision)
    elif operation == "reset" and decision is None and target_event_sequence is None:
        state = unknown_responsibility()
    elif operation == "undo" and decision is None and _sequence(target_event_sequence):
        state = None
    else:
        raise ValueError("Ungültige Änderung der Zuständigkeit.")
    canonical = json.dumps([operation, expected_revision, state, target_event_sequence], sort_keys=True)
    receipt = {"request_id": request_id, "digest": hashlib.sha256(canonical.encode()).hexdigest()}
    if target_event_sequence is not None:
        receipt["target_event_sequence"] = target_event_sequence
    return state, receipt
