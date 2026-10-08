"""Bounded, source-first projections for the four memory areas.

The views are read-only. They expose only current original sources and
fingerprint-current category projections; they never trigger analysis.
"""
from __future__ import annotations

import sqlite3

from .episodes import sql_geltend, sql_rohquelle

AREA_VIEWS = (
    {"id": "work", "label": "Arbeit & Projekte"},
    {"id": "personal", "label": "Privat & Familie"},
    {"id": "health", "label": "Gesundheit"},
    {"id": "finance", "label": "Finanzen & Verträge"},
)
MAX_AREAS_PAGE = 100
MAX_AREA_SCAN = 500
MAX_AREA_TITLE = 240
MAX_AREA_EVIDENCE = 240
MAX_CATEGORY_IDS = 64
HEALTH = ("health", "Gesundheit", "Gesundheit und medizinische Angelegenheiten")


def ensure_health_taxonomy(connection: sqlite3.Connection) -> bool:
    """Add the health category without invalidating existing source analysis.

    A user-defined category with ID ``health`` wins. If the taxonomy is full,
    migration succeeds and the health view is explicitly marked unavailable.
    """
    row = connection.execute(
        "SELECT taxonomy_version,corpus_version FROM memory_category_scan WHERE id=1"
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("Die Taxonomieversion fehlt.")
    version = row[0]
    current = connection.execute(
        "SELECT DISTINCT category_id FROM memory_category_taxonomy WHERE version<=?",
        (version,),
    ).fetchall()
    identifiers = {item[0] for item in current}
    if "health" in identifiers or len(identifiers) >= MAX_CATEGORY_IDS:
        return False
    next_version = version + 1
    connection.execute(
        "INSERT INTO memory_category_taxonomy(category_id,version,label,description) VALUES(?,?,?,?)",
        (HEALTH[0], next_version, HEALTH[1], HEALTH[2]),
    )
    # Taxonomy visibility changes, but old source analyses remain current.
    connection.execute(
        "UPDATE memory_category_scan SET taxonomy_version=? WHERE id=1", (next_version,)
    )
    return True


def verify_health_taxonomy(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT taxonomy_version FROM memory_category_scan WHERE id=1"
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("Die Taxonomieversion fehlt.")
    identifiers = {item[0] for item in connection.execute(
        "SELECT DISTINCT category_id FROM memory_category_taxonomy WHERE version<=?", (row[0],)
    )}
    if len(identifiers) < MAX_CATEGORY_IDS and "health" not in identifiers:
        raise sqlite3.DatabaseError("Die Gesundheitskategorie fehlt trotz freiem Taxonomieplatz.")


class MemoryAreas:
    """A cursor-paginated projection of current original sources and categories."""

    def __init__(self, episodes):
        self.episodes = episodes

    def page(self, *, limit: int = 50, cursor: int | None = None,
             area: str | None = None) -> dict:
        if type(limit) is not int or not 1 <= limit <= MAX_AREAS_PAGE:
            raise ValueError("limit must be 1..100")
        if cursor is not None and (type(cursor) is not int or cursor < 1):
            raise ValueError("cursor must be a positive row ID")
        area_ids = {item['id'] for item in AREA_VIEWS}
        if area is not None and area not in area_ids | {'other'}:
            raise ValueError('unknown memory area')

        from .memory_categories import Categories

        categories = Categories(self.episodes)
        with self.episodes._lock:
            where = f"{sql_geltend('episodes')} AND {sql_rohquelle('episodes')}"
            params = []
            if area in area_ids:
                # This is candidate selection, not evidence validation. Explicit
                # corrections override automatic topics even when now stale.
                where += """ AND (
                    EXISTS (SELECT 1 FROM memory_category_corrections c,
                        json_each(c.categories) j WHERE c.episode_id=episodes.id AND j.value=?)
                    OR (NOT EXISTS (SELECT 1 FROM memory_category_corrections c
                        WHERE c.episode_id=episodes.id) AND EXISTS (
                        SELECT 1 FROM memory_category_topics t
                        WHERE t.episode_id=episodes.id AND t.category_id=?)))"""
                params.extend([area, area])
            if cursor is not None:
                where += " AND episodes.rowid < ?"
                params.append(cursor)
            scan_limit = MAX_AREA_SCAN if area is not None else limit + 1
            candidates = self.episodes._conn.execute(
                "SELECT episodes.rowid AS source_rowid,episodes.id,episodes.title,episodes.occurred_at "
                f"FROM episodes WHERE {where} ORDER BY episodes.rowid DESC LIMIT ?",
                (*params, scan_limit + 1),
            ).fetchall()
            rows = []
            scanned = 0
            last_scanned = None
            for row in candidates[:scan_limit]:
                projection = categories.list_for(row['id'])
                scanned += 1
                last_scanned = row['source_rowid']
                ids = {item['id'] for item in projection['categories']}
                if area in area_ids and area not in ids:
                    continue
                if area == 'other' and projection['status'] == 'complete' and ids and ids <= area_ids:
                    continue
                rows.append((row, projection))
                if len(rows) > limit:
                    break
            scan_limited = len(rows) <= limit and len(candidates) > scan_limit
            has_more = len(rows) > limit or scan_limited
            rows = rows[:limit]
            next_cursor = (last_scanned if scan_limited else rows[-1][0]['source_rowid']) if has_more else None
            sources = []
            for row, projection in rows:
                shaped_categories = []
                for category in projection.get("categories", []):
                    evidence = []
                    for item in category.get("evidence", [])[:1]:
                        quote = item.get("quote")
                        if not isinstance(quote, str):
                            continue
                        evidence.append({
                            "start": item.get("start"),
                            "end": item.get("end"),
                            "quote": quote[:MAX_AREA_EVIDENCE],
                            "quote_truncated": len(quote) > MAX_AREA_EVIDENCE,
                        })
                    shaped_categories.append({
                        "id": category.get("id"),
                        "label": category.get("label"),
                        "origin": category.get("origin"),
                        "evidence": evidence,
                    })
                title = row["title"] if isinstance(row["title"], str) else ""
                occurred_at = row["occurred_at"]
                sources.append({
                    "episode_id": row["id"],
                    "title": title[:MAX_AREA_TITLE],
                    "occurred_at": occurred_at if isinstance(occurred_at, str) else None,
                    "status": projection.get("status", "pending"),
                    "categories": shaped_categories,
                })
            taxonomy = categories.taxonomy()
            taxonomy_version = taxonomy["version"]
            available_ids = {item["id"] for item in taxonomy["items"]}

        return {
            "areas": [{**area, "available": area["id"] in available_ids} for area in AREA_VIEWS],
            "sources": sources,
            "taxonomy_version": taxonomy_version,
            "scanned_count": len(sources),
            "counts_scope": "page",
            "area": area,
            "selection_scope": "corpus" if area is not None else "page",
            "scan_limited": scan_limited,
            "candidates_checked": scanned,
            "next_cursor": next_cursor,
            "truncated": has_more,
        }
