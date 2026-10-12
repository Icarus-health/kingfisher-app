"""Turn explicit habit observations into evidence-backed knowledge proposals."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .habits import list_habits
from .episodes import AUSGEBLENDETE_ZUSTAENDE
from .learning_patterns import detect_patterns
from .proposals import Evidence, Proposal, ProposalState


def propose_patterns(store: Any, episodes: Any, proposals: Any,
                     knowledge_service: Any, *, at: datetime) -> list[Proposal]:
    """Propose observed patterns for active habits; never write a claim."""
    habits = {item["id"]: item for item in list_habits(store, episodes, at)}
    active_ids = set(habits)
    # Bound each habit independently; a large unrelated mail archive must not
    # prevent learning from a few explicitly recorded check-ins.
    grouped = {habit_id: [] for habit_id in active_ids}
    start = at - timedelta(days=30)
    for episode in episodes.tagged_raw([f"habit:{habit_id}" for habit_id in active_ids]):
        if episode.state in AUSGEBLENDETE_ZUSTAENDE:
            continue
        if not start <= episode.reference_time() <= at:
            continue
        for tag in episode.tags or []:
            if tag.startswith("habit:") and tag[6:] in grouped:
                grouped[tag[6:]].append(episode)
    candidates = [pattern for values in grouped.values()
                  for pattern in detect_patterns(values, now=at)]
    current: set[str] = set()
    result: list[Proposal] = []
    prior_patterns = proposals.from_origin_prefix("habit-pattern:")
    newest = {}
    for prior in prior_patterns:
        newest.setdefault(prior.proposed_by, prior)
    for pattern in candidates:
        label_id = pattern["label"]
        if label_id not in active_ids:
            continue
        habit = habits[label_id]
        proposed_by = f"habit-pattern:{pattern['id']}"
        current.add(proposed_by)
        prior = newest.get(proposed_by)
        if prior is not None:
            result.append(prior)
            continue
        evidence = [Evidence(item["episode_id"], item["quote"], item["digest"])
                    for item in pattern["evidence"]]
        statement = (f"Für Gewohnheit {habit['label']} wurden im Zeitraum "
                     f"{pattern['window_start']} bis {pattern['window_end']} "
                     f"an {pattern['observed_days']} Tagen Einträge erfasst.")
        proposal, _ = knowledge_service.propose(
            subject_ref=f"habit:{label_id}",
            predicate="observed_pattern",
            value=(f"{pattern['window_start']}..{pattern['window_end']}; "
                   f"{pattern['observed_days']} beobachtete Tage"),
            statement=statement,
            rationale=("Beobachtung; keine Aussage über unerfasste Tage oder "
                       "dauerhafte Eigenschaften."),
            evidence=evidence,
            proposed_by=proposed_by,
            at=at,
        )
        result.append(proposal)
    for prior in prior_patterns:
        if (prior.proposed_by.startswith("habit-pattern:")
                and prior.state is ProposalState.PENDING
                and prior.proposed_by not in current):
            proposals.supersede(prior.id, at=at)
    return result


__all__ = ["propose_patterns"]
