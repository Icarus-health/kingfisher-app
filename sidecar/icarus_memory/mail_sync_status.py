"""Sanitized, restart-persistent status for scheduled mailbox synchronization."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SAFE_CODES = frozenset({"unavailable", "credentials_missing", "cancelled"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state(settings: Any, account_id: str) -> dict[str, Any]:
    statuses = getattr(settings, "mail_sync_status", None)
    if not isinstance(statuses, dict):
        statuses = {}
        settings.mail_sync_status = statuses
    current = statuses.get(account_id)
    if not isinstance(current, dict):
        current = {"consecutive_failures": 0}
        statuses[account_id] = current
    return current


def record_attempt(settings: Any, account_id: str) -> dict[str, Any]:
    """Record a sanitized UTC attempt marker and return the mutable status."""
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id must be non-empty")
    current = _state(settings, account_id)
    current["last_attempt"] = _now()
    current.setdefault("consecutive_failures", 0)
    return current


def record_success(settings: Any, account_id: str, report: Any) -> dict[str, Any]:
    """Record success and only the numeric counts safe for UI status."""
    current = record_attempt(settings, account_id)
    current["last_success"] = current["last_attempt"]
    current["consecutive_failures"] = 0
    if isinstance(report, dict):
        current["last_report"] = {
            name: int(report.get(name, 0))
            for name in ("recorded", "duplicates", "filtered")
            if (name != "filtered" or name in report) and isinstance(report.get(name, 0), int) and not isinstance(report.get(name, 0), bool)
        }
    else:
        current["last_report"] = {}
    current.pop("last_failure", None)
    return current


def record_failure(settings: Any, account_id: str, code: str = "unavailable") -> dict[str, Any]:
    """Record one of the bounded failure classes without exception details."""
    if code not in SAFE_CODES:
        raise ValueError("unsupported mail sync status code")
    current = record_attempt(settings, account_id)
    current["consecutive_failures"] = int(current.get("consecutive_failures", 0)) + 1
    current["last_failure"] = code
    return current


__all__ = ["SAFE_CODES", "record_attempt", "record_success", "record_failure"]
