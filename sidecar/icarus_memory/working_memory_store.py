"""Bounded, retractable working interpretations of original episodes.

The sidecar stores source fingerprints, character ranges, categories and
SHA-256 hashes of lexical terms. Source text stays in Episodes and is read
again whenever a reference is resolved.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Any, Sequence

from .episodes import (CHAT_LOOKUP_TAG, IGNORIERTE_ZUSTAENDE, QUELLEN_ARTEN, EpisodeState, sql_aktuelle_fassung,
                       sql_geltend, sql_nicht_ausgeblendet, sql_nicht_ignoriert, sql_quelle,
                       sql_rohquelle, sql_sichtbar)
from . import logbuch
from .lexical import terms_v1
from .source_index import FUNKTIONSWOERTER
from .source_snapshot import EpisodeSupportSnapshot, canonical_instant, read_snapshot
from .word_forms import alternatives, synonym_alternatives
from .working_memory_words import candidate_words, query_words


#: Obergrenze der Einordnung je Quelle (Zeichen). Längere Quellen gehen in Abschnitten durch das Modell
#: (`abschnitte.py`); darüber wird nicht mehr eingeordnet, und das Logbuch vermerkt es.
MAX_SOURCE_CHARS = 200_000
#: Wie viel Text ein Bericht an das Modell je Quelle trägt (Vorschläge, Berichtigung): unverändert 12.000.
MAX_BERICHT_CHARS = 12_000
#: Größe des Dokuments einer Quelle in der Datenbank, die noch gelesen wird (200.000 Zeichen, auch mit Umlauten).
MAX_SNAPSHOT_BYTES = 768 * 1024
#: Ab dieser Größe des Dokuments (Bytes, rund 6.000 Zeichen Text mit Metadaten) läuft eine Quelle in mehreren Abschnitten.
#: Bei gleicher Trefferzahl geht in der Wortsuche eine kürzere Quelle vor: Eine lange hat viele Absätze, und irgendeiner
#: trifft immer, auch bei allgemeinen Wörtern wie „Termin“ oder „morgen“.
LANGE_QUELLE_BYTES = 9_000
#: Verweise je Quelle: bis 2.000 Absätze (`abschnitte.MAX_EINHEITEN`).
MAX_ITEMS = 2_000
SCAN_BUDGET = 500
SEARCH_BUDGET = 500
MAX_QUERY_TERMS = 16
MAX_RESULTS = 64
REPORT_SCAN_BUDGET = 500
RETRY_SECONDS = 300
ANALYSIS_VERSION = 1
KINDS = frozenset({"request", "commitment", "conditional", "change", "status",
                   "fact", "uncertain", "historical"})


def _fingerprint_payload(snapshot: EpisodeSupportSnapshot) -> dict[str, Any]:
    episode = snapshot.episode
    return {
        "id": episode.id, "digest": episode.digest, "kind": episode.kind.value,
        "title": episode.title, "body": episode.body,
        "provenance": episode.provenance.to_dict(),
        "recorded_at": canonical_instant(episode.recorded_at.isoformat()),
        "occurred_at": canonical_instant(episode.occurred_at.isoformat()) if episode.occurred_at else None,
        "participants": episode.participants,
        "tags": episode.tags, "source_key": snapshot.source_key,
        "metadata_digest": snapshot.metadata_digest,
        "generation": snapshot.generation, "head_id": snapshot.head_id,
        "ignored": episode.state is EpisodeState.IGNORED,
    }


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def source_fingerprint(snapshot: EpisodeSupportSnapshot) -> str:
    """Identify visible original evidence, excluding consolidation bookkeeping.

    Die Projektzuordnung gehört nicht dazu: Sie ist eine Ablage des Nutzers,
    kein Teil des Belegs. Wer eine Quelle einem Projekt zuordnet, soll ihre
    Einordnung nicht verlieren und nicht auf ein erneutes Einordnen warten.
    """
    return _digest(_fingerprint_payload(snapshot))


def _legacy_fingerprint(snapshot: EpisodeSupportSnapshot) -> str:
    """Fingerabdruck vor Migration 9, als die Projektzuordnung noch dazugehörte."""
    return _digest({**_fingerprint_payload(snapshot), "project_id": snapshot.episode.project_id})


def rekey_without_project(connection, parse) -> None:
    """Migration 9: gespeicherte Einordnungen auf den neuen Fingerabdruck umschlüsseln.

    Nur Einträge, deren gespeicherter Fingerabdruck exakt zum heutigen Stand
    der Quelle passt, werden übertragen. Alles andere bleibt unverändert und
    wird wie bisher beim nächsten Durchlauf neu bewertet. Kein Modellaufruf,
    kein Quelltext wird gespeichert.
    """
    rows = connection.execute(
        "SELECT episode_id,fingerprint FROM working_memory_sources").fetchall()
    changed = False
    for episode_id, stored in rows:
        try:
            snapshot = read_snapshot(connection, episode_id, parse, max_bytes=MAX_SNAPSHOT_BYTES)
        except ValueError:
            continue
        if snapshot is None or _legacy_fingerprint(snapshot) != stored:
            continue
        fingerprint = source_fingerprint(snapshot)
        if fingerprint == stored:
            continue
        items = connection.execute(
            "SELECT id,start,end,kind FROM working_memory_items WHERE episode_id=? AND fingerprint=?",
            (episode_id, stored)).fetchall()
        for old_id, start, end, kind in items:
            new_id = _item_id(episode_id, fingerprint, start, end, kind)
            connection.execute(
                "UPDATE working_memory_items SET id=?,fingerprint=? WHERE id=?",
                (new_id, fingerprint, old_id))
            connection.execute(
                "UPDATE working_memory_tokens SET item_id=? WHERE item_id=?", (new_id, old_id))
        connection.execute(
            "UPDATE working_memory_sources SET fingerprint=? WHERE episode_id=?",
            (fingerprint, episode_id))
        changed = True
    if changed:
        connection.execute("UPDATE working_memory_scan SET revision=revision+1 WHERE id=1")


def _hash_term(term: str) -> str:
    return hashlib.sha256(term.encode("utf-8")).hexdigest()


def hex_key(digest: str) -> int:
    """Die ersten 8 Byte eines SHA-256-Hex-Werts als vorzeichenbehaftete 64-Bit-Zahl."""
    return int.from_bytes(bytes.fromhex(digest[:16]), "big", signed=True)


def _term_key(term: str) -> int:
    # Ein Suchschlüssel, kein Klartext. Eine seltene Kollision liefert höchstens
    # einen zusätzlichen Kandidaten; angezeigt wird nur, was die Auswahl im
    # Originaltext bestätigt.
    return hex_key(_hash_term(term))


def compact_index(connection) -> None:
    """Migration 10: Suchindex mit ganzzahligen Schlüsseln statt Hex-Text.

    Überträgt jeden bestehenden Eintrag; kein Modellaufruf, kein Klartext.
    Suchreihenfolge und Kandidatensignatur bleiben unverändert.
    """
    connection.execute("ALTER TABLE working_memory_items ADD COLUMN key INTEGER")
    for (identifier,) in connection.execute("SELECT id FROM working_memory_items").fetchall():
        connection.execute("UPDATE working_memory_items SET key=? WHERE id=?",
                           (hex_key(identifier), identifier))
    connection.execute("CREATE UNIQUE INDEX idx_working_memory_items_key ON working_memory_items(key)")
    connection.execute("""CREATE TABLE working_memory_terms (
        term INTEGER NOT NULL, item INTEGER NOT NULL,
        PRIMARY KEY(term, item)) WITHOUT ROWID""")
    connection.execute("CREATE INDEX idx_working_memory_terms_item ON working_memory_terms(item)")
    cursor = connection.execute("SELECT item_id, token_hash FROM working_memory_tokens")
    while rows := cursor.fetchmany(5000):
        connection.executemany(
            "INSERT OR IGNORE INTO working_memory_terms(term,item) VALUES(?,?)",
            [(hex_key(token), hex_key(item)) for item, token in rows])
    connection.execute("DROP TABLE working_memory_tokens")


def _item_id(episode_id: str, fingerprint: str, start: int, end: int, kind: str) -> str:
    encoded = json.dumps([episode_id, fingerprint, start, end, kind], separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class WorkingMemoryStore:
    def __init__(self, episodes):
        self.episodes = episodes

    def revision(self) -> int:
        """Durable index change counter for validating saved answer selections."""
        with self.episodes._lock:
            return self.episodes._conn.execute(
                "SELECT revision FROM working_memory_scan WHERE id=1").fetchone()[0]

    def _advance_revision(self) -> None:
        self.episodes._conn.execute(
            "UPDATE working_memory_scan SET revision=revision+1 WHERE id=1")

    def _snapshot(self, episode_id: str) -> EpisodeSupportSnapshot | None:
        try:
            return read_snapshot(self.episodes._conn, episode_id, self.episodes._from_row,
                                 max_bytes=MAX_SNAPSHOT_BYTES)
        except ValueError:
            return None

    @staticmethod
    def _eligible(snapshot: EpisodeSupportSnapshot | None) -> bool:
        return bool(snapshot and snapshot.current() and snapshot.episode.kind in QUELLEN_ARTEN
                    and CHAT_LOOKUP_TAG not in snapshot.episode.tags)

    def _status(self, episode_id: str):
        return self.episodes._conn.execute(
            "SELECT fingerprint,status,retry_after,analysis_version FROM working_memory_sources WHERE episode_id=?",
            (episode_id,)).fetchone()

    def source_state(self, episode_id: str) -> str:
        """Fresh, read-only state for one original; never equate saved with indexed."""
        with self.episodes._lock:
            size = self.episodes._conn.execute(
                'SELECT state,length(CAST(document AS BLOB)) FROM episodes WHERE id=?',
                (episode_id,)).fetchone()
            if size is None or size[0] in IGNORIERTE_ZUSTAENDE:
                return 'excluded'
            if size[1] > MAX_SNAPSHOT_BYTES:
                return 'deferred'
            snapshot = self._snapshot(episode_id)
            if not self._eligible(snapshot):
                return 'excluded'
            row = self._status(episode_id)
            if row and row[1] == 'dismissed':
                return 'dismissed'
            if row and row[0] == source_fingerprint(snapshot):
                if row[1] == 'complete':
                    if row[3] != ANALYSIS_VERSION:
                        return 'pending'
                    found = self.episodes._conn.execute(
                        'SELECT 1 FROM working_memory_items WHERE episode_id=? AND fingerprint=? LIMIT 1',
                        (episode_id, row[0])).fetchone()
                    return 'complete' if found else 'empty'
                return row[1]
            return 'deferred' if len(snapshot.episode.body) > MAX_SOURCE_CHARS else 'pending'

    def _scan_rows(self, cursor: str, budget: int = SCAN_BUDGET):
        """One bounded, wrapping page of current source identifiers and sizes."""
        query = ("SELECT id,length(CAST(document AS BLOB)) AS document_bytes FROM episodes "
                 f"WHERE id>? AND {sql_rohquelle()} "
                 "ORDER BY id LIMIT ?")
        rows = self.episodes._conn.execute(query, (cursor, budget)).fetchall()
        if len(rows) < budget and cursor:
            rows += self.episodes._conn.execute(
                "SELECT id,length(CAST(document AS BLOB)) AS document_bytes FROM episodes "
                f"WHERE id<=? AND {sql_rohquelle()} "
                "ORDER BY id LIMIT ?", (cursor, budget - len(rows))).fetchall()
        return rows

    def is_current(self, snapshot: EpisodeSupportSnapshot) -> bool:
        with self.episodes._lock:
            current = self._snapshot(snapshot.episode.id)
            return bool(self._eligible(current) and
                        source_fingerprint(current) == source_fingerprint(snapshot))

    def pending(self, limit: int = 10, *, episode_ids: Sequence[str] | None = None) -> list[EpisodeSupportSnapshot]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        result = []
        now = time.time()
        with self.episodes.transaction():
            if episode_ids is None:
                cursor = self.episodes._conn.execute(
                    "SELECT cursor FROM working_memory_scan WHERE id=1").fetchone()[0]
                candidates = self._scan_rows(cursor)
                last_seen = cursor
            else:
                candidates = []
                for episode_id in dict.fromkeys(episode_ids):
                    candidate = self.episodes._conn.execute(
                        "SELECT id,length(CAST(document AS BLOB)) AS document_bytes FROM episodes "
                        f"WHERE id=? AND {sql_rohquelle()}",
                        (episode_id,)).fetchone()
                    if candidate is not None:
                        candidates.append(candidate)
            for candidate in candidates:
                episode_id = candidate["id"]
                if episode_ids is None:
                    last_seen = episode_id
                row = self._status(episode_id)
                if row and row[1] == "dismissed":
                    continue
                if candidate["document_bytes"] > MAX_SNAPSHOT_BYTES:
                    if not row or row[1] != "deferred" or row[0] != "":
                        self._set_status(episode_id, "", "deferred", "")
                        logbuch.vermerke("zu_lang", sorte="quelle", anzahl=1)
                    continue
                snapshot = self._snapshot(episode_id)
                if not self._eligible(snapshot):
                    continue
                fingerprint = source_fingerprint(snapshot)
                if row and row[0] == fingerprint:
                    if row[1] == "complete" and row[3] == ANALYSIS_VERSION:
                        continue
                    if row[1] == "deferred":
                        continue
                    if row[1] == "failed" and (row[2] or 0) > now:
                        continue
                    if row[1] == "complete" and (row[2] or 0) > now:
                        continue
                if len(snapshot.episode.body) > MAX_SOURCE_CHARS:
                    if (row and row[1] == "complete" and row[0] == fingerprint
                            and row[3] != ANALYSIS_VERSION):
                        # Preserve the prior searchable interpretation while the
                        # oversized stale source waits for its next bounded attempt.
                        self.episodes._conn.execute(
                            "UPDATE working_memory_sources SET retry_after=? WHERE episode_id=?",
                            (now + RETRY_SECONDS, episode_id))
                        continue
                    # Nicht still übergehen: einmal je Fassung der Quelle steht es im Logbuch (siehe oben: `continue`).
                    self._set_status(snapshot.episode.id, fingerprint, "deferred", "")
                    logbuch.vermerke("zu_lang", sorte="quelle", anzahl=1)
                    continue
                result.append(snapshot)
                if len(result) >= limit:
                    break
            if episode_ids is None:
                self.episodes._conn.execute(
                    "UPDATE working_memory_scan SET cursor=? WHERE id=1", (last_seen,))
        return result

    def _set_status(self, episode_id: str, fingerprint: str, status: str,
                    model: str, retry_after: float | None = None,
                    analysis_version: int | None = None) -> None:
        if analysis_version is None:
            analysis_version = ANALYSIS_VERSION
        self.episodes._conn.execute(
            "INSERT INTO working_memory_sources(episode_id,fingerprint,status,model,retry_after,analysis_version) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(episode_id) DO UPDATE SET "
            "fingerprint=excluded.fingerprint,status=excluded.status,model=excluded.model,"
            "retry_after=excluded.retry_after,analysis_version=excluded.analysis_version",
            (episode_id, fingerprint, status, model, retry_after, analysis_version))
        self.episodes._conn.execute(
            "INSERT INTO mail_intake_analysis(episode_id,generation,status) "
            "SELECT id,support_generation,? FROM episodes WHERE id=? "
            "ON CONFLICT(episode_id) DO UPDATE SET generation=excluded.generation,status=excluded.status",
            (status, episode_id))

    def _delete_items(self, episode_id: str) -> None:
        self.episodes._conn.execute(
            "DELETE FROM working_memory_terms WHERE item IN "
            "(SELECT key FROM working_memory_items WHERE episode_id=?)", (episode_id,))
        self.episodes._conn.execute(
            "DELETE FROM working_memory_items WHERE episode_id=?", (episode_id,))

    def commit(self, snapshot: EpisodeSupportSnapshot, items: list[dict[str, Any]],
               *, model: str, explicit_recheck: bool = False) -> bool:
        if type(model) is not str or not model or len(model) > 200:
            raise ValueError("model identifier required (max 200 chars)")
        if type(items) is not list or len(items) > MAX_ITEMS:
            raise ValueError(f"items must be a list of at most {MAX_ITEMS} references")
        if not self._eligible(snapshot):
            return False
        body = snapshot.episode.body
        if len(body) > MAX_SOURCE_CHARS:
            return False
        normalized = []
        seen = set()
        for item in items:
            if type(item) is not dict or set(item) != {"start", "end", "kind"}:
                raise ValueError("item must contain only start, end and kind")
            start, end, kind = item["start"], item["end"], item["kind"]
            if (type(start) is not int or type(end) is not int or
                    not 0 <= start < end <= len(body) or kind not in KINDS or
                    not body[start:end].strip()):
                raise ValueError("invalid source range or interpretation kind")
            identity = (start, end, kind)
            if identity in seen:
                raise ValueError("duplicate source reference")
            seen.add(identity)
            normalized.append(identity)
        fingerprint = source_fingerprint(snapshot)
        with self.episodes.transaction():
            current = self._snapshot(snapshot.episode.id)
            row = self._status(snapshot.episode.id)
            if (not self._eligible(current) or source_fingerprint(current) != fingerprint or
                    (row and row[1] == "dismissed")):
                return False
            if (not explicit_recheck and row and row[1] == "complete" and row[0] == fingerprint
                    and row[3] == ANALYSIS_VERSION):
                return False
            self._delete_items(snapshot.episode.id)
            self._set_status(snapshot.episode.id, fingerprint, "complete", model)
            for start, end, kind in normalized:
                item_id = _item_id(snapshot.episode.id, fingerprint, start, end, kind)
                self.episodes._conn.execute(
                    "INSERT INTO working_memory_items(id,episode_id,fingerprint,start,end,kind,key) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (item_id, snapshot.episode.id, fingerprint, start, end, kind, hex_key(item_id)))
                searchable = (snapshot.episode.title + " " +
                              " ".join(snapshot.episode.participants) + " " + body[start:end])
                tokens = terms_v1(searchable)
                # Broader suffix matches are a separate, lower-priority channel.
                # Do not derive fragments from email addresses or participants.
                tokens |= candidate_words(snapshot.episode.title[:300] + ' ' + body[start:end])
                self.episodes._conn.executemany(
                    "INSERT OR IGNORE INTO working_memory_terms(term,item) VALUES(?,?)",
                    ((_term_key(token), hex_key(item_id)) for token in tokens))
            self._advance_revision()
        return True

    def fail(self, snapshot: EpisodeSupportSnapshot) -> bool:
        """Defer a transient failed local-model run for five minutes."""
        with self.episodes.transaction():
            current = self._snapshot(snapshot.episode.id)
            row = self._status(snapshot.episode.id)
            if (not self._eligible(current) or
                    source_fingerprint(current) != source_fingerprint(snapshot) or
                    (row and (row[1] == "dismissed" or
                              (row[1] == "complete" and row[0] == source_fingerprint(current)
                               and row[3] == ANALYSIS_VERSION)))):
                return False
            if row and row[1] == "complete" and row[0] == source_fingerprint(current):
                # Keep the prior version visible; only delay the failed refresh.
                self.episodes._conn.execute(
                    "UPDATE working_memory_sources SET retry_after=? WHERE episode_id=?",
                    (time.time() + RETRY_SECONDS, snapshot.episode.id))
                return True
            self._delete_items(snapshot.episode.id)
            self._set_status(snapshot.episode.id, source_fingerprint(current),
                             "failed", "", time.time() + RETRY_SECONDS)
            return True

    def defer(self, snapshot: EpisodeSupportSnapshot) -> bool:
        """Record a deterministic processing gap until this source changes."""
        with self.episodes.transaction():
            current = self._snapshot(snapshot.episode.id)
            if (not self._eligible(current) or
                    source_fingerprint(current) != source_fingerprint(snapshot)):
                return False
            row = self._status(snapshot.episode.id)
            if row and (row[1] == "dismissed" or
                        (row[0] == source_fingerprint(current) and
                         (row[1] == "deferred" or
                          (row[1] == "complete" and row[3] == ANALYSIS_VERSION)))):
                return False
            if (row and row[1] == "complete" and
                    row[0] == source_fingerprint(current)):
                # Deterministic inability to refresh is still not permission to
                # discard the old reference; recheck after the normal cooldown.
                self.episodes._conn.execute(
                    "UPDATE working_memory_sources SET retry_after=? WHERE episode_id=?",
                    (time.time() + RETRY_SECONDS, snapshot.episode.id))
                return True
            self._delete_items(snapshot.episode.id)
            self._set_status(snapshot.episode.id, source_fingerprint(current),
                             "deferred", "")
            return True

    def dismiss(self, episode_id: str) -> bool:
        """Explicit rejection is sticky across reopen and model changes."""
        with self.episodes.transaction():
            current = self._snapshot(episode_id)
            exists = self.episodes._conn.execute(
                "SELECT 1 FROM episodes WHERE id=?", (episode_id,)).fetchone()
            if not exists:
                return False
            row = self._status(episode_id)
            if row and row[1] == "dismissed":
                return False
            self._delete_items(episode_id)
            self._set_status(episode_id, source_fingerprint(current) if current else "", "dismissed", "")
            self._advance_revision()
            return True

    def resolve(self, ref: dict[str, Any]) -> EpisodeSupportSnapshot | None:
        if (type(ref) is not dict or set(ref) !=
                {"episode_id", "fingerprint", "start", "end", "kind"} or
                type(ref["episode_id"]) is not str or type(ref["fingerprint"]) is not str or
                type(ref["start"]) is not int or type(ref["end"]) is not int or
                type(ref["kind"]) is not str or ref["kind"] not in KINDS):
            return None
        with self.episodes._lock:
            row = self.episodes._conn.execute(
                "SELECT 1 FROM working_memory_items i JOIN working_memory_sources s "
                "ON s.episode_id=i.episode_id WHERE i.episode_id=? AND i.fingerprint=? "
                "AND i.start=? AND i.end=? AND i.kind=? AND s.status='complete' "
                "AND s.fingerprint=i.fingerprint",
                (ref["episode_id"], ref["fingerprint"], ref["start"], ref["end"], ref["kind"])).fetchone()
            if row is None:
                return None
            snapshot = self._snapshot(ref["episode_id"])
            if not self._eligible(snapshot) or source_fingerprint(snapshot) != ref["fingerprint"]:
                return None
            if not 0 <= ref["start"] < ref["end"] <= len(snapshot.episode.body):
                return None
            return snapshot

    def best_reference(self, episode_id: str, words) -> dict[str, Any] | None:
        """Der Abschnitt einer Quelle, der die meisten Suchwörter enthält, als geprüfter Verweis.

        Für Quellen, die der Volltextindex findet, ohne dass die Wortsuche einen
        Abschnitt nannte. Gleichstand: der frühere Abschnitt. ``None``, wenn die
        Quelle nicht (mehr) vollständig eingeordnet oder nicht aktuell ist.
        Suchwörter werden wie im Index gefaltet verglichen.
        """
        from .source_index import falte
        with self.episodes._lock:
            rows = self.episodes._conn.execute(
                "SELECT i.fingerprint,i.start,i.end,i.kind FROM working_memory_items i "
                "JOIN working_memory_sources s ON s.episode_id=i.episode_id "
                "WHERE i.episode_id=? AND s.status='complete' AND s.fingerprint=i.fingerprint "
                "ORDER BY i.start,i.end,i.id", (episode_id,)).fetchall()
            snapshot = self._snapshot(episode_id) if rows else None
            if not self._eligible(snapshot):
                return None
            body = snapshot.episode.body
            gesucht = [falte(word) for word in words]
            best, best_score = None, -1
            for row in rows:
                if not 0 <= row["start"] < row["end"] <= len(body):
                    continue
                text = falte(body[row["start"]:row["end"]])
                score = sum(1 for word in gesucht if word and word in text)
                if score > best_score:
                    best, best_score = row, score
            if best is None:
                return None
            ref = {"episode_id": episode_id, "fingerprint": best["fingerprint"],
                   "start": best["start"], "end": best["end"], "kind": best["kind"]}
            return ref if self.resolve(ref) is not None else None

    def source_refs(self, *, since: datetime | None = None,
                    episode_ids: Sequence[str] | None = None,
                    limit: int = MAX_RESULTS) -> dict[str, Any]:
        """Select complete, current-index reference rows without query terms.

        Exactly one scope is required: a recording-time cutoff or explicitly
        selected episode identifiers. References are revalidated by callers
        with :meth:`resolve` before source text is displayed.
        """
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("limit must be 1..64")
        if (since is None) == (episode_ids is None):
            raise ValueError("provide exactly one of since or episode_ids")
        params: list[Any]
        where = ["s.status='complete'", "s.fingerprint=i.fingerprint",
                 sql_sichtbar('e')]
        if since is not None:
            if (not isinstance(since, datetime) or since.tzinfo is None
                    or since.utcoffset() is None):
                raise ValueError("since must be a timezone-aware datetime")
            where.append("julianday(e.recorded_at)>=julianday(?)")
            params = [since.isoformat()]
        else:
            if (isinstance(episode_ids, (str, bytes)) or not isinstance(episode_ids, Sequence)
                    or not 1 <= len(episode_ids) <= 100
                    or any(type(value) is not str or not value for value in episode_ids)):
                raise ValueError("episode_ids must contain 1..100 non-empty identifiers")
            unique_ids = list(dict.fromkeys(episode_ids))
            where.append("e.id IN (" + ",".join("?" for _ in unique_ids) + ")")
            params = unique_ids
        sql = (
            "SELECT i.episode_id,i.fingerprint,i.start,i.end,i.kind "
            "FROM working_memory_items i "
            "JOIN working_memory_sources s ON s.episode_id=i.episode_id "
            "JOIN episodes e ON e.id=i.episode_id WHERE " + " AND ".join(where) +
            " ORDER BY julianday(e.recorded_at) DESC,e.id DESC,i.start,i.end,i.kind,i.id LIMIT ?"
        )
        with self.episodes._lock:
            rows = self.episodes._conn.execute(sql, (*params, REPORT_SCAN_BUDGET)).fetchall()

        truncated = len(rows) == REPORT_SCAN_BUDGET
        refs: list[dict[str, Any]] = []
        index = 0
        while index < len(rows):
            episode_id = rows[index]["episode_id"]
            end = index + 1
            while end < len(rows) and rows[end]["episode_id"] == episode_id:
                end += 1
            group = rows[index:end]
            # At the SQLite work boundary the final group may continue beyond
            # this page. Omit that group conservatively instead of reporting
            # only some of a source's current references.
            if len(rows) == REPORT_SCAN_BUDGET and end == len(rows):
                truncated = True
                break
            elif len(refs) + len(group) <= limit:
                refs.extend({key: row[key] for key in
                             ("episode_id", "fingerprint", "start", "end", "kind")}
                            for row in group)
            else:
                truncated = True
                break
            index = end
        if index < len(rows):
            truncated = True
        return {"refs": refs, "truncated": truncated}

    def classification_state(self, episode_ids: Sequence[str]) -> dict[str, int]:
        """Einordnungsstand dieser Quellen, über dieselbe Menge wie :meth:`items_for`.

        `eingeordnet`: fertig; `offen`: noch nicht oder erneut an der Reihe;
        `ausgeschlossen`: zu groß oder abgelehnt, wird nicht eingeordnet.
        Archivierte, ignorierte, ältere Fassungen und eigene Suchfragen zählen
        nirgends, so wie sie auch in der Mappe nicht stehen.
        """
        ids = list(dict.fromkeys(value for value in episode_ids if isinstance(value, str)))
        state = {"eingeordnet": 0, "offen": 0, "ausgeschlossen": 0}
        analysis_version = ANALYSIS_VERSION
        with self.episodes._lock:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                rows = self.episodes._conn.execute(
                    "SELECT COALESCE(s.status, '') AS status, s.analysis_version, COUNT(*) AS n FROM episodes e "
                    "LEFT JOIN working_memory_sources s ON s.episode_id=e.id "
                    f"WHERE {sql_sichtbar('e')} AND {sql_aktuelle_fassung('e')} "
                    "AND NOT EXISTS (SELECT 1 FROM json_each(e.document, '$.tags') AS tag WHERE tag.value = ?) "
                    f"AND e.id IN ({','.join('?' for _ in chunk)}) "
                    "GROUP BY COALESCE(s.status, ''), s.analysis_version",
                    (CHAT_LOOKUP_TAG, *chunk)).fetchall()
                for row in rows:
                    key = ("eingeordnet" if row["status"] == "complete"
                           and row["analysis_version"] == analysis_version else
                           "ausgeschlossen" if row["status"] in ("deferred", "dismissed") else "offen")
                    state[key] += row["n"]
        return state

    def items_for(self, episode_ids: Sequence[str], kinds: Sequence[str], *,
                  limit: int = 8, offset: int = 0) -> dict[str, Any]:
        """Eingeordnete Abschnitte bestimmter Arten zu diesen Quellen.

        Für die Mappe: neueste Quelle zuerst, seitenweise, dazu die Gesamtzahl
        und wie viele aus archivierten (verdichteten) Quellen stammen, damit
        eine Begrenzung angezeigt statt still vorgenommen wird. Was sich hier
        prüfen lässt, wird hier ausgeschlossen: andere Arten, ältere
        Fassungen, eigene Suchfragen, Quellen mit abgeleiteten Aussagen.
        Aufrufer prüfen jede Referenz dennoch mit :meth:`resolve`.
        """
        wanted = [kind for kind in kinds if kind in KINDS]
        ids = list(dict.fromkeys(value for value in episode_ids if isinstance(value, str)))
        if (not wanted or not ids or type(limit) is not int or not 1 <= limit <= MAX_RESULTS
                or type(offset) is not int or offset < 0):
            return {"refs": [], "total": 0, "archived": 0}
        rows: list[Any] = []
        total = archived = 0
        with self.episodes._lock:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                base = (
                    "FROM working_memory_items i JOIN working_memory_sources s ON s.episode_id=i.episode_id "
                    "JOIN episodes e ON e.id=i.episode_id WHERE s.status='complete' "
                    f"AND s.fingerprint=i.fingerprint AND {sql_quelle('e')} "
                    f"AND {sql_aktuelle_fassung('e')} "
                    "AND NOT EXISTS (SELECT 1 FROM json_each(e.document, '$.tags') AS tag WHERE tag.value = ?) "
                    "AND NOT EXISTS (SELECT 1 FROM episode_produced_assertions p WHERE p.episode_id = e.id) "
                    f"AND i.kind IN ({','.join('?' for _ in wanted)}) "
                    f"AND i.episode_id IN ({','.join('?' for _ in chunk)})")
                params = (CHAT_LOOKUP_TAG, *wanted, *chunk)
                archived += self.episodes._conn.execute(
                    f"SELECT COUNT(*) {base} AND e.state = 'archived'", params).fetchone()[0]
                where = f"{base} AND {sql_nicht_ausgeblendet('e')}"
                total += self.episodes._conn.execute(f"SELECT COUNT(*) {where}", params).fetchone()[0]
                rows += self.episodes._conn.execute(
                    "SELECT i.episode_id,i.fingerprint,i.start,i.end,i.kind,"
                    f"julianday(COALESCE(e.occurred_at,e.recorded_at)) AS moment {where} "
                    "ORDER BY moment DESC, i.episode_id, i.start LIMIT ?",
                    (*params, offset + limit)).fetchall()
        rows.sort(key=lambda row: (-(row["moment"] or 0), row["episode_id"], row["start"]))
        refs = [{key: row[key] for key in ("episode_id", "fingerprint", "start", "end", "kind")}
                for row in rows[offset:offset + limit]]
        return {"refs": refs, "total": total, "archived": archived}

    def items_all(self, episode_ids: Sequence[str], kinds: Sequence[str], *, limit: int = 5000) -> dict[str, Any]:
        """Alle eingeordneten Abschnitte dieser Quellen in einem Durchgang, neueste Quelle zuerst.

        Wie :meth:`items_for` (gleiche Bedingungen), aber ohne Seiten: Die Akte
        einer Sache braucht jeden Abschnitt, um Erledigtes und Überholtes zu
        erkennen. `truncated` sagt, ob `limit` erreicht wurde; die Verweise
        sind dann die jüngsten. Aufrufer prüfen jede Referenz mit :meth:`resolve`.
        """
        wanted = [kind for kind in kinds if kind in KINDS]
        ids = list(dict.fromkeys(value for value in episode_ids if isinstance(value, str)))
        if not wanted or not ids or type(limit) is not int or limit < 1:
            return {"refs": [], "truncated": False}
        rows: list[Any] = []
        with self.episodes._lock:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                rows += self.episodes._conn.execute(
                    "SELECT i.episode_id,i.fingerprint,i.start,i.end,i.kind,"
                    "julianday(COALESCE(e.occurred_at,e.recorded_at)) AS moment "
                    "FROM working_memory_items i JOIN working_memory_sources s ON s.episode_id=i.episode_id "
                    "JOIN episodes e ON e.id=i.episode_id WHERE s.status='complete' "
                    f"AND s.fingerprint=i.fingerprint AND {sql_sichtbar('e')} "
                    f"AND {sql_aktuelle_fassung('e')} "
                    "AND NOT EXISTS (SELECT 1 FROM json_each(e.document, '$.tags') AS tag WHERE tag.value = ?) "
                    "AND NOT EXISTS (SELECT 1 FROM episode_produced_assertions p WHERE p.episode_id = e.id) "
                    f"AND i.kind IN ({','.join('?' for _ in wanted)}) "
                    f"AND i.episode_id IN ({','.join('?' for _ in chunk)})",
                    (CHAT_LOOKUP_TAG, *wanted, *chunk)).fetchall()
        rows.sort(key=lambda row: (-(row["moment"] or 0), row["episode_id"], row["start"]))
        refs = [{key: row[key] for key in ("episode_id", "fingerprint", "start", "end", "kind")}
                for row in rows[:limit]]
        return {"refs": refs, "truncated": len(rows) > limit}

    def einordnungsstand(self, episode_ids: Sequence[str]) -> dict[str, str]:
        """Je Quelle eine Kurzkennung ihrer Einordnung (Status, Fassung, Modell, Abschnitte mit Art und Stelle).

        Ändert sich die Einordnung einer Quelle, ändert sich ihre Kennung; abgeleitete
        Ansichten (Akten) erkennen daran, dass sie neu rechnen müssen. Quellen ohne
        Einordnung fehlen im Ergebnis.
        """
        ids = list(dict.fromkeys(value for value in episode_ids if isinstance(value, str)))
        stand: dict[str, str] = {}
        with self.episodes._lock:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                for row in self.episodes._conn.execute(
                        "SELECT s.episode_id, s.status, s.fingerprint, s.model, s.analysis_version, "
                        "(SELECT group_concat(kind || start || '-' || end) FROM (SELECT i.kind, i.start, i.end "
                        "FROM working_memory_items i WHERE i.episode_id=s.episode_id "
                        "AND i.fingerprint=s.fingerprint ORDER BY i.start, i.end, i.kind)) AS n "
                        "FROM working_memory_sources s "
                        f"WHERE s.episode_id IN ({','.join('?' for _ in chunk)})", chunk):
                    stand[row["episode_id"]] = (
                        f"{row['status']}:{row['fingerprint']}:{row['model']}:"
                        f"{row['analysis_version']}:{row['n']}")
        return stand

    def inventory(self, limit: int = 2048) -> dict[str, Any]:
        """Aktuelle eingeordnete Abschnitte, neueste zuerst, ohne Suchbegriffe.

        Nur für abgeleitete Suchverfahren (etwa Bedeutungssuche). Jeder Treffer
        wird vor der Anzeige wie jede andere Referenz mit :meth:`resolve` geprüft.
        """
        if type(limit) is not int or not 1 <= limit <= 8192:
            raise ValueError("limit must be 1..8192")
        with self.episodes._lock:
            rows = self.episodes._conn.execute(
                "SELECT i.episode_id,i.fingerprint,i.start,i.end,i.kind "
                "FROM working_memory_items i "
                "JOIN working_memory_sources s ON s.episode_id=i.episode_id "
                "JOIN episodes e ON e.id=i.episode_id "
                "WHERE s.status='complete' AND s.fingerprint=i.fingerprint "
                f"AND {sql_nicht_ausgeblendet('e')} "
                "ORDER BY julianday(e.recorded_at) DESC, e.id DESC, i.start, i.end, i.kind LIMIT ?",
                (limit + 1,)).fetchall()
        return {"refs": [dict(row) for row in rows[:limit]], "truncated": len(rows) > limit}

    def _matching_refs(self, words: set[str], budget: int, episode_ids: Sequence[str] | None = None):
        if not words or (episode_ids is not None and not episode_ids):
            return
        scope, scoped = "", ()
        if episode_ids is not None:
            scoped = tuple(dict.fromkeys(episode_ids))
            scope = "AND i.episode_id IN (" + ",".join("?" for _ in scoped) + ") "
        hashes = sorted({_term_key(word) for word in words})
        placeholders = ",".join("?" for _ in hashes)
        offset = 0
        while offset < budget:
            rows = self.episodes._conn.execute(
                "SELECT i.episode_id,i.fingerprint,i.start,i.end,i.kind "
                "FROM working_memory_terms t JOIN working_memory_items i ON i.key=t.item "
                "JOIN working_memory_sources s ON s.episode_id=i.episode_id "
                "JOIN episodes e ON e.id=i.episode_id "
                "WHERE t.term IN (" + placeholders + ") AND s.status='complete' "
                f"AND {sql_nicht_ignoriert('e')} " + scope +
                "AND s.fingerprint=i.fingerprint GROUP BY i.id "
                "ORDER BY COUNT(*) DESC, length(CAST(e.document AS BLOB)) > ?, e.occurred_at IS NULL, e.occurred_at DESC, "
                "e.recorded_at DESC, i.episode_id, i.start, i.id LIMIT ? OFFSET ?",
                (*hashes, *scoped, LANGE_QUELLE_BYTES, min(200, budget - offset), offset)).fetchall()
            if not rows:
                return
            for row in rows:
                yield dict(row)
            offset += len(rows)

    def search(self, query: str, limit: int = 12, *,
               episode_ids: Sequence[str] | None = None, je_quelle: int | None = None) -> dict[str, Any]:
        """Wortsuche, optional nur in den genannten Quellen (höchstens 500).

        Mit `je_quelle` liefert die Suche aus einer Quelle höchstens so viele Verweise (die besten, die Reihenfolge der
        Treffer bleibt). Eine lange Quelle in vielen Abschnitten (`abschnitte.py`) belegte sonst mit ihren Verweisen
        den ganzen Platz, und die kurzen Quellen, die die Frage ebenso treffen, kämen nicht mehr vor. Ohne Angabe
        ist die Zahl nicht begrenzt.
        """
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("limit must be 1..64")
        if je_quelle is not None and (type(je_quelle) is not int or je_quelle < 1):
            raise ValueError("je_quelle must be a positive number")
        terms, expanded, query_truncated = self._query_terms(query)
        refs = []
        seen = set()
        je = {}
        examined = 0
        gelesen = 0
        # Überzählige Verweise einer Quelle zählen nicht als geprüft, die Zahl der gelesenen Zeilen bleibt begrenzt.
        lese_grenze = SEARCH_BUDGET if je_quelle is None else SEARCH_BUDGET * 4
        with self.episodes._lock:
            for words in (set(terms), expanded, query_words(set(terms) | expanded)):
                for ref in self._matching_refs(words, lese_grenze - gelesen, episode_ids):
                    gelesen += 1
                    identity = (ref["episode_id"], ref["fingerprint"], ref["start"], ref["end"], ref["kind"])
                    if identity in seen:
                        examined += 1
                        continue
                    seen.add(identity)
                    if je_quelle is not None and je.get(ref["episode_id"], 0) >= je_quelle:
                        continue
                    examined += 1
                    if self.resolve(ref) is None:
                        continue
                    je[ref["episode_id"]] = je.get(ref["episode_id"], 0) + 1
                    refs.append(ref)
                    if len(refs) > limit:
                        return {"refs": refs[:limit], "truncated": True}
                    if examined >= SEARCH_BUDGET:
                        return {"refs": refs, "truncated": True}
                if examined >= SEARCH_BUDGET or gelesen >= lese_grenze:
                    return {"refs": refs, "truncated": True}
        return {"refs": refs, "truncated": query_truncated}

    @staticmethod
    def _query_terms(query: str) -> tuple[list[str], set[str], bool]:
        if type(query) is not str:
            raise ValueError("query must be text")
        # Beide Suchstufen verwenden dieselben Sachwörter. Sonst verdrängen
        # „habe“ oder „war“ echte Wortformtreffer und liefern Scheinbelege.
        # Nur die Anfrage ändern; gespeicherte Tokens und Originale bleiben gleich.
        all_terms = sorted(terms_v1(query) - FUNKTIONSWOERTER)
        terms = all_terms[:MAX_QUERY_TERMS]
        forms = set().union(*(alternatives(term) for term in terms)) - set(terms)
        synonyms = set().union(*(synonym_alternatives(term) for term in terms)) - set(terms) - forms
        return terms, forms | synonyms, len(all_terms) > MAX_QUERY_TERMS

    # Öffentlich für `absatzauswahl.py`: dieselbe Zerlegung der Frage wie die Wortsuche (Wörter, Wortformen, Synonyme).
    query_terms = _query_terms

    def candidate_signature(self, query: str, *, episode_ids: Sequence[str] | None = None) -> str:
        """Hash every indexed candidate for this query, independent of result limit.

        The index is read without source bodies. If more than 500 items match,
        the global revision conservatively invalidates this oversized query.
        Individual references still require fresh resolution before display.
        """
        terms, expanded, query_truncated = self._query_terms(query)
        words = set(terms) | expanded
        words |= query_words(words)
        rows = []
        overflow_revision = None
        with self.episodes._lock:
            scope, scoped = "", ()
            if episode_ids is not None:
                scoped = tuple(dict.fromkeys(episode_ids))
                scope = "AND i.episode_id IN (" + ",".join("?" for _ in scoped) + ") "
            if words and (episode_ids is None or scoped):
                hashes = sorted({_term_key(word) for word in words})
                placeholders = ",".join("?" for _ in hashes)
                rows = self.episodes._conn.execute(
                    "SELECT i.id,i.fingerprint,i.kind,s.analysis_version FROM working_memory_terms t "
                    "JOIN working_memory_items i ON i.key=t.item "
                    "JOIN working_memory_sources s ON s.episode_id=i.episode_id "
                    "JOIN episodes e ON e.id=i.episode_id "
                    "WHERE t.term IN (" + placeholders + ") AND s.status='complete' "
                    f"AND {sql_nicht_ignoriert('e')} " + scope +
                    "AND s.fingerprint=i.fingerprint GROUP BY i.id ORDER BY i.id LIMIT 501",
                    (*hashes, *scoped)).fetchall()
            if len(rows) > 500:
                overflow_revision = self.revision()
        payload = ["working-memory-candidates-v3", terms, sorted(expanded),
                   query_truncated, [tuple(row) for row in rows[:500]], overflow_revision]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                              .encode("utf-8")).hexdigest()

    def progress(self) -> dict[str, int]:
        """Genaue Zählung für die Fortschrittsanzeige, ohne Quelltexte zu lesen.

        Zählt aktuelle Nachrichten und Dokumente (ohne ausgeschlossene, ohne
        überholte Fassungen und ohne Gesprächs-Nachschlagequellen) und deren
        gespeicherten Einordnungsstand. Eine ältere Analyseversion bleibt bis
        zur erneuten Einordnung offen; Quellenänderungen prüft der begrenzte
        Quellenscan.
        """
        eligible = (f"{sql_geltend('e')} "
                    "AND e.document NOT LIKE ?")
        lookup = f'%"{CHAT_LOOKUP_TAG}"%'
        with self.episodes._lock:
            total = self.episodes._conn.execute(
                f"SELECT COUNT(*) FROM episodes e WHERE {eligible}", (lookup,)).fetchone()[0]
            rows = self.episodes._conn.execute(
                f"SELECT s.status, s.analysis_version, COUNT(*) FROM working_memory_sources s JOIN episodes e "
                f"ON e.id=s.episode_id WHERE {eligible} GROUP BY s.status,s.analysis_version", (lookup,)).fetchall()
        counts = {"complete": 0, "failed": 0, "deferred": 0, "dismissed": 0}
        for status, version, count in rows:
            if status == "complete" and version != ANALYSIS_VERSION:
                continue
            counts[status] += count
        done = counts.get("complete", 0)
        skipped = counts.get("deferred", 0) + counts.get("dismissed", 0)
        return {"total": total, "done": done, "skipped": skipped,
                "retry": counts.get("failed", 0), "remaining": max(0, total - done - skipped)}

    def coverage(self) -> dict[str, int | bool]:
        """Bounded status sample; truncated signals additional current sources."""
        counts = {"complete": 0, "failed": 0, "deferred": 0,
                  "dismissed": 0, "pending": 0}
        with self.episodes._lock:
            rows = self.episodes._conn.execute(
                "SELECT id,length(CAST(document AS BLOB)) AS document_bytes FROM episodes "
                f"WHERE {sql_rohquelle()} ORDER BY id LIMIT ?",
                (SCAN_BUDGET + 1,)).fetchall()
            for candidate in rows[:SCAN_BUDGET]:
                row = self._status(candidate["id"])
                if row and row[1] == "dismissed":
                    counts["dismissed"] += 1
                elif candidate["document_bytes"] > MAX_SNAPSHOT_BYTES:
                    counts["deferred"] += 1
                else:
                    snapshot = self._snapshot(candidate["id"])
                    if not self._eligible(snapshot):
                        continue
                    if row and row[0] == source_fingerprint(snapshot):
                        status = ("pending" if row[1] == "complete" and
                                  row[3] != ANALYSIS_VERSION else row[1])
                        counts[status] += 1
                    elif len(snapshot.episode.body) > MAX_SOURCE_CHARS:
                        counts["deferred"] += 1
                    else:
                        counts["pending"] += 1
        counts["truncated"] = len(rows) > SCAN_BUDGET
        return counts
