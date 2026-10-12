"""Bounded, read-only checks for new messages in a task's exact mail thread."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .episodes import sql_aktuell
from .mail_timeline import REPLY, SELF, _token
from .model import SourceType

FOLLOWUP_REASON = (
    "Seit dem Festhalten der Aufgabe wurde eine weitere Nachricht im Verlauf erfasst. "
    "Bitte prüfen, ob die Aufgabe noch so gilt."
)
LIMIT_REASON = (
    "Der Mailverlauf konnte für diese Aufgabe nicht vollständig geprüft werden. "
    "Bitte selbst prüfen, ob die Aufgabe noch gilt."
)
CLASSIFICATION_LIMIT_REASON = (
    "Bei einigen verknüpften Quellen ließ sich nicht sicher einordnen, "
    "ob sie zu einem Mailverlauf gehören."
)
MAX_TASKS = 200
CLASSIFICATION_CHUNK_SIZE = 200
MAX_CLASSIFICATION_TASKS = 5000
MAX_THREAD_ROWS = 5000
MAX_HOPS = 8
MAX_TOKENS_PER_TASK = 500
MAX_FRONTIER_TAGS = 400
MAX_QUERY_STEPS = 1_000_000
PROGRESS_OPCODES = 1000


@dataclass
class TaskSourceReviewResult:
    by_task: dict[str, dict[str, str | None]]
    coverage_limited: bool = False


def _iso_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def review_tasks(episodes, tasks: Iterable) -> TaskSourceReviewResult:
    """Return ephemeral review metadata, never reading message bodies or writing task state.

    The caps are deliberate. If any cap can hide a match, the affected
    task receives an explicit incomplete-review note instead of a false clean result.
    """
    linked: list[tuple[object, str]] = []
    for task in tasks:
        if getattr(task.status, "value", task.status) != "open":
            continue
        ref = task.provenance.source_ref or ""
        if ref.startswith("episode:"):
            linked.append((task, ref.removeprefix("episode:")))
    if not linked:
        return TaskSourceReviewResult({})

    reviews: dict[str, dict[str, str | None]] = {}
    classifiable = linked[:MAX_CLASSIFICATION_TASKS]
    coverage_limited = len(linked) > MAX_CLASSIFICATION_TASKS
    source_rows: dict[str, tuple[list[str], str | None]] = {}
    remaining_steps = MAX_QUERY_STEPS

    def progress() -> int:
        nonlocal remaining_steps
        remaining_steps -= PROGRESS_OPCODES
        return int(remaining_steps < 0)

    def bounded_fetchall(query: str, params: list) -> list:
        episodes._conn.set_progress_handler(progress, PROGRESS_OPCODES)
        try:
            return episodes._conn.execute(query, params).fetchall()
        finally:
            episodes._conn.set_progress_handler(None, 0)

    with episodes._lock:
        for start in range(0, len(classifiable), CLASSIFICATION_CHUNK_SIZE):
            chunk = classifiable[start:start + CLASSIFICATION_CHUNK_SIZE]
            ids = list(dict.fromkeys(source_id for _, source_id in chunk))
            if not ids:
                continue
            placeholders = ",".join("?" for _ in ids)
            try:
                rows = bounded_fetchall(
                    "SELECT e.id, json_extract(e.document,'$.tags'), "
                    "json_extract(e.document,'$.provenance.source_type'), "
                    "json_extract(e.document,'$.provenance.source_ref') "
                    f"FROM episodes e WHERE e.id IN ({placeholders}) AND {sql_aktuell('e')} "
                    "AND json_extract(e.document,'$.kind')='message' "
                    "AND json_extract(e.document,'$.provenance.source_type')='email'",
                    ids,
                )
            except sqlite3.OperationalError as exc:
                if "interrupted" not in str(exc).lower():
                    raise
                coverage_limited = True
                break
            for episode_id, raw_tags, source_type, source_ref in rows:
                try:
                    tags = json.loads(raw_tags or "[]")
                except (TypeError, json.JSONDecodeError):
                    tags = []
                if source_type == SourceType.EMAIL.value:
                    source_rows[episode_id] = (tags if isinstance(tags, list) else [], source_ref)

        mail_tasks = [(task, source_id) for task, source_id in classifiable
                      if source_id in source_rows]
        detailed = mail_tasks[:MAX_TASKS]
        for task, _ in mail_tasks[MAX_TASKS:]:
            reviews[task.id] = {"reason": LIMIT_REASON, "followup_episode_id": None}
        contexts: dict[str, dict] = {}
        frontier: dict[str, set[str]] = {}
        for task, source_id in detailed:
            source = source_rows.get(source_id)
            created = _iso_datetime(task.created_at.isoformat() if task.created_at else None)
            if source is None or created is None:
                continue
            tags, source_ref = source
            self_tags = [tag for tag in tags if isinstance(tag, str) and tag.startswith(SELF)]
            if not self_tags:
                # Legacy email sources kept the account and RFC Message-ID in source_ref.
                match = re.fullmatch(r"(.+):(<[^<>\s]{1,500}>)", source_ref or "")
                if match:
                    self_tags = [SELF + _token(*match.groups())]
            if not self_tags:
                reviews[task.id] = {"reason": LIMIT_REASON, "followup_episode_id": None}
                continue
            source_tags = [tag for tag in tags if isinstance(tag, str)]
            if not any(tag.startswith(SELF) for tag in source_tags):
                source_tags.extend(self_tags)
            seeds = {
                tag[len(prefix):]
                for tag in source_tags
                for prefix in (SELF, REPLY)
                if tag.startswith(prefix)
            }
            contexts[task.id] = {
                "source_id": source_id,
                "created": created,
                "seen": set(seeds),
                "followups": [],
                "incomplete": False,
            }
            for token in seeds:
                frontier.setdefault(token, set()).add(task.id)

        if not frontier:
            return TaskSourceReviewResult(reviews, coverage_limited)

        # Expand the exact, account-scoped header component in both directions:
        # a message's own ID and every referenced ID are equivalent connection
        # tokens. Task membership travels with each token to prevent batch leakage.
        for hop in range(MAX_HOPS):
            if not frontier:
                break
            ordered_tags = sorted(frontier)
            if len(ordered_tags) > MAX_FRONTIER_TAGS:
                for tag in ordered_tags[MAX_FRONTIER_TAGS:]:
                    for task_id in frontier[tag]:
                        contexts[task_id]["incomplete"] = True
                frontier = {tag: frontier[tag] for tag in ordered_tags[:MAX_FRONTIER_TAGS]}
            tokens = sorted(frontier)
            wanted = [prefix + token for token in tokens for prefix in (SELF, REPLY)]
            reply_placeholders = ",".join("?" for _ in wanted)
            try:
                reply_rows = bounded_fetchall(
                    "SELECT e.id, j.value, e.recorded_at, json_extract(e.document,'$.tags') "
                    "FROM episode_mail_headers j JOIN episodes e ON e.id=j.episode_id "
                    f"WHERE {sql_aktuell('e')} AND e.kind='message' "
                    "AND json_extract(e.document,'$.provenance.source_type')='email' "
                    f"AND j.value IN ({reply_placeholders}) "
                    "ORDER BY julianday(e.recorded_at) DESC, e.id DESC LIMIT ?",
                    [*wanted, MAX_THREAD_ROWS + 1],
                )
            except sqlite3.OperationalError as exc:
                if "interrupted" not in str(exc).lower():
                    raise
                for task_ids in frontier.values():
                    for task_id in task_ids:
                        contexts[task_id]["incomplete"] = True
                break
            truncated = len(reply_rows) >= MAX_THREAD_ROWS + 1
            if truncated:
                for task_ids in frontier.values():
                    for task_id in task_ids:
                        contexts[task_id]["incomplete"] = True

            next_frontier: dict[str, set[str]] = {}
            for episode_id, matched_tag, recorded, raw_tags in reply_rows[:MAX_THREAD_ROWS]:
                matched_token = next((matched_tag[len(prefix):] for prefix in (SELF, REPLY)
                                      if isinstance(matched_tag, str) and matched_tag.startswith(prefix)), None)
                if matched_token is None:
                    continue
                when = _iso_datetime(recorded)
                try:
                    tags = json.loads(raw_tags or "[]")
                except (TypeError, json.JSONDecodeError):
                    tags = []
                self_tags = [tag for tag in tags
                             if isinstance(tag, str) and tag.startswith(SELF)] if isinstance(tags, list) else []
                thread_tokens = {
                    tag[len(prefix):]
                    for tag in tags if isinstance(tag, str)
                    for prefix in (SELF, REPLY)
                    if tag.startswith(prefix)
                } if isinstance(tags, list) else set()
                for task_id in frontier.get(matched_token, ()):
                    context = contexts[task_id]
                    if episode_id != context["source_id"] and when is not None and when > context["created"]:
                        context["followups"].append((when, episode_id))
                    for next_token in thread_tokens:
                        if next_token in context["seen"]:
                            continue
                        if len(context["seen"]) >= MAX_TOKENS_PER_TASK:
                            context["incomplete"] = True
                            continue
                        context["seen"].add(next_token)
                        next_frontier.setdefault(next_token, set()).add(task_id)

            if hop == MAX_HOPS - 1 and next_frontier:
                for task_ids in next_frontier.values():
                    for task_id in task_ids:
                        contexts[task_id]["incomplete"] = True
            frontier = next_frontier

    for task_id, context in contexts.items():
        followups = context["followups"]
        if followups:
            _, episode_id = max(followups)
            reviews[task_id] = {"reason": FOLLOWUP_REASON, "followup_episode_id": episode_id}
        elif context["incomplete"]:
            reviews[task_id] = {"reason": LIMIT_REASON, "followup_episode_id": None}
    return TaskSourceReviewResult(reviews, coverage_limited)
