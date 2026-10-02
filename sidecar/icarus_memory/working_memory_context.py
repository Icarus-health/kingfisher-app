"""Read-only reports of current, automatically indexed original sources."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from .working_memory_store import MAX_BERICHT_CHARS, WorkingMemoryStore

MAX_REPORT_SOURCES = 5
MAX_REPORT_TEXT = 24_000


def reports(episodes, claims, *, since: datetime | None = None,
            episode_ids: Sequence[str] | None = None,
            limit: int = MAX_REPORT_SOURCES) -> dict:
    """Return bounded source reports, never inferred or confirmed facts.

    ``since`` filters by source recording time. Explicit episode identifiers
    can select older material. Current index references and source eligibility
    are checked again before the full original text is included.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_REPORT_SOURCES:
        raise ValueError("limit must be 1..5")
    store = WorkingMemoryStore(episodes)
    selected = store.source_refs(since=since, episode_ids=episode_ids)
    grouped: dict[str, list[dict]] = {}
    for ref in selected["refs"]:
        grouped.setdefault(ref["episode_id"], []).append(ref)

    items = []
    used_chars = 0
    truncated = bool(selected["truncated"])
    requested = set(episode_ids or ())
    for episode_id, refs in grouped.items():
        if len(items) >= limit:
            truncated = True
            break
        snapshots = [store.resolve(ref) for ref in refs]
        if (any(snapshot is None for snapshot in snapshots)
                or len({snapshot.episode.digest for snapshot in snapshots if snapshot}) != 1):
            truncated = True
            continue
        snapshot = snapshots[0]
        episode = snapshot.episode
        if episode.produced or not claims.source_is_unclaimed(episode_id):
            truncated = True
            continue
        body = episode.body
        if len(body) > MAX_BERICHT_CHARS or used_chars + len(body) > MAX_REPORT_TEXT:
            truncated = True
            continue
        items.append({
            "episode_id": episode.id,
            "title": episode.title,
            "body": body,
            "kinds": sorted({ref["kind"] for ref in refs}),
            "occurred_at": episode.occurred_at.isoformat() if episode.occurred_at else None,
            "recorded_at": episode.recorded_at.isoformat(),
            "source_ref": episode.provenance.source_ref,
            "source_type": episode.provenance.source_type.value,
            "confirmation": "source_report",
        })
        used_chars += len(body)

    if requested and requested - set(grouped):
        truncated = True
    return {"items": items, "truncated": truncated}


__all__ = ["reports"]
