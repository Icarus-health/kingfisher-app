"""Historische Kenntnis aus bestätigten Aussagen und ihrem Änderungsjournal.

Kein neuer Faktenbestand. Heutiger Quellenentzug bleibt auch bei einer Frage
nach gestern wirksam. Fehlende Altjournale werden nicht rückwirkend erfunden.
"""
from datetime import datetime, timezone
import base64
import hashlib
import json
import math

from .episodes import EpisodeError, EpisodeKind, EpisodeState
from .model import Status


def aware(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Der historische Zeitpunkt braucht eine Zeitzone.")
    return value


# Cursors are opaque navigation state, never authorization. Every page checks
# current evidence permissions again. Anchored high-water marks exclude normal
# later inserts and reject deleted/reused ceiling rows. This is best-effort
# navigation across live stores, not a transaction snapshot.
SCAN_BUDGET = 2000


def query_key(kind, *parts):
    return hashlib.sha256(json.dumps([kind, *parts], separators=(",", ":")).encode()).hexdigest()


def time_key(value):
    return aware(value).astimezone(timezone.utc).isoformat()


def encode_cursor(query, position, ceilings, anchors):
    data = {"v": 2, "q": query, "p": list(position), "h": list(ceilings), "a": list(anchors)}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def decode_cursor(cursor, query, ceiling_count):
    try:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 2048:
            raise ValueError()
        data = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
        if set(data) != {"v", "q", "p", "h", "a"} or type(data["v"]) is not int or data["v"] != 2 or data["q"] != query:
            raise ValueError()
        position, ceilings, anchors = data["p"], data["h"], data["a"]
        if (not isinstance(position, list) or len(position) != 2
                or type(position[0]) not in (int, float)
                or not 1721425.5 <= position[0] < 5373484.5
                or not math.isfinite(position[0])
                or not isinstance(position[1], str) or not 1 <= len(position[1]) <= 300
                or not isinstance(ceilings, list) or len(ceilings) != ceiling_count
                or any(type(n) is not int or n < 0 or n > 2**63 - 1 for n in ceilings)):
            raise ValueError()
        if (not isinstance(anchors, list) or len(anchors) != ceiling_count
                or any((anchor is not None if ceiling == 0 else
                        not isinstance(anchor, str) or len(anchor) != 64
                        or any(char not in "0123456789abcdef" for char in anchor))
                       for ceiling, anchor in zip(ceilings, anchors))):
            raise ValueError()
        position[0] = float(position[0])
        return position, ceilings, anchors
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError) as exc:
        raise ValueError("Ungültiger Cursor oder Cursor für eine andere Abfrage.") from exc


def ceiling_anchor(conn, table, column, ceiling):
    """Bind a numeric ceiling to its immutable row identity, under store lock."""
    if ceiling == 0:
        return None
    fields = "*" if table == "knowledge_changes" else "id"
    row = conn.execute(f"SELECT {fields} FROM {table} WHERE {column}=?", (ceiling,)).fetchone()
    if row is None:
        return None
    return hashlib.sha256(json.dumps(list(row), separators=(",", ":")).encode()).hexdigest()


def validate_anchor(conn, table, column, ceiling, anchor):
    if ceiling_anchor(conn, table, column, ceiling) != anchor:
        raise ValueError("Der Cursor ist veraltet: Eine Grenzzeile wurde gelöscht oder ersetzt. Bitte den Abruf neu beginnen.")


def snapshot(store, episodes, known_at, *, valid_at=None, reference=None, limit=100, cursor=None):
    from .claims import ClaimError
    known_at = aware(known_at)
    valid_at = aware(valid_at) if valid_at is not None else known_at
    if not 1 <= limit <= 500:
        raise ValueError("Der historische Abruf ist auf 1 bis 500 Aussagen begrenzt.")
    gaps = {"missing_history": 0, "unavailable_evidence": 0, "unknown_validity": 0}
    query = query_key("as-known", str(store._path.resolve()), time_key(known_at), time_key(valid_at), reference, limit)
    continuation = decode_cursor(cursor, query, 2) if cursor is not None else None
    cache = {}
    events = {}

    def load(claim_id):
        if claim_id not in cache:
            cache[claim_id] = store.get(claim_id)
        if claim_id not in events:
            events[claim_id] = []
            for direction in ("ASC", "DESC"):
                row = store._conn.execute(
                    "SELECT action FROM knowledge_changes WHERE claim_id=? "
                    "AND julianday(created_at)<=julianday(?) AND revision<=? "
                    f"ORDER BY revision {direction} LIMIT 1",
                    (claim_id, known_at.isoformat(), ceilings[1])).fetchone()
                if row is not None:
                    events[claim_id].append(row)
        return cache[claim_id]

    def allowed(claim_id, seen=frozenset()):
        if claim_id in seen:
            return False
        try:
            claim = load(claim_id)
        except ClaimError:
            return False
        if claim.status is Status.REDACTED:
            gaps["unavailable_evidence"] += 1
            return False
        if claim.created_at > known_at:
            return False
        history = events[claim_id]
        if not history or history[0]["action"] != "accepted":
            gaps["missing_history"] += 1
            return False
        if history[-1]["action"] != "accepted":
            return False
        if ((claim.valid_from is not None and valid_at < claim.valid_from)
                or (claim.valid_until is not None and valid_at >= claim.valid_until)):
            return False
        if not claim.evidence:
            gaps["unavailable_evidence"] += 1
            return False
        for evidence in claim.evidence:
            try:
                source = episodes.get(evidence.episode_id)
                if (source.state is EpisodeState.IGNORED
                        or source.kind is EpisodeKind.SUMMARY or source.digest != evidence.digest):
                    raise EpisodeError("Quelle nicht verfügbar")
            except EpisodeError:
                gaps["unavailable_evidence"] += 1
                return False
        return all(allowed(ref, seen | {claim_id}) for ref in claim.depends_on)

    with store._lock:
        ceilings = continuation[1] if continuation else [
            store._conn.execute("SELECT COALESCE(MAX(rowid),0) FROM knowledge_claims").fetchone()[0],
            store._conn.execute("SELECT COALESCE(MAX(revision),0) FROM knowledge_changes").fetchone()[0],
        ]
        anchors = continuation[2] if continuation else [
            ceiling_anchor(store._conn, "knowledge_claims", "rowid", ceilings[0]),
            ceiling_anchor(store._conn, "knowledge_changes", "revision", ceilings[1]),
        ]
        for table, column, ceiling, anchor in zip(
                ("knowledge_claims", "knowledge_changes"), ("rowid", "revision"), ceilings, anchors):
            validate_anchor(store._conn, table, column, ceiling, anchor)
        params = [known_at.isoformat(), ceilings[0]]
        sql = "SELECT document,julianday(created_at) AS sort_time,id FROM knowledge_claims WHERE julianday(created_at)<=julianday(?) AND rowid<=?"
        if reference:
            sql += " AND (subject_ref=? OR scope_ref=? OR json_extract(document,'$.target_ref')=?)"
            params.extend([reference] * 3)
        if continuation:
            stamp, identifier = continuation[0]
            sql += " AND (julianday(created_at)<? OR (julianday(created_at)=? AND id>?))"
            params.extend([stamp, stamp, identifier])
        sql += " ORDER BY julianday(created_at) DESC,id LIMIT ?"
        params.append(SCAN_BUDGET + 1)
        rows = store._conn.execute(sql, params).fetchall()
        items = []
        scanned = 0
        position = None
        for row in rows[:SCAN_BUDGET]:
            scanned += 1
            position = (row["sort_time"], row["id"])
            claim = store._from_row(row)
            cache[claim.id] = claim
            if not allowed(claim.id):
                continue
            if claim.valid_from is None:
                gaps["unknown_validity"] += 1
            # Der heutige Status und spätere Nachfolger gehören nicht in den
            # damaligen Stand. Die Historie wird ausdrücklich separat benannt.
            items.append({
                "id": claim.id, "statement": claim.statement,
                "subject_ref": claim.subject_ref, "predicate": claim.predicate,
                "value": claim.value, "target_ref": claim.target_ref,
                "scope_ref": claim.scope_ref, "status_at_knowledge_time": "accepted",
                "recorded_at": claim.created_at.isoformat(),
                "valid_from": claim.valid_from.isoformat() if claim.valid_from else None,
                "valid_until": claim.valid_until.isoformat() if claim.valid_until else None,
                "validity_known": claim.valid_from is not None,
                "evidence": [e.to_dict() for e in claim.evidence],
                "depends_on": list(claim.depends_on),
            })
            if len(items) == limit:
                break
        truncated = len(rows) > scanned
        budget_truncated = truncated and scanned == SCAN_BUDGET
        next_cursor = encode_cursor(query, position, ceilings, anchors) if truncated else None
    return {"known_at": known_at.isoformat(), "valid_at": valid_at.isoformat(),
            "items": items, "gaps": gaps, "truncated": truncated,
            "next_cursor": next_cursor, "scanned": scanned, "budget_truncated": budget_truncated,
            "gap_scope": "page", "consistency": "best_effort_navigation",
            "scope": "Bestätigte Aussagen im lokalen Bestand; heutige Quellenrechte gelten."}
