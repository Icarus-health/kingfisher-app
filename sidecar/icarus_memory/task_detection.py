"""Fortlaufende lokale Aufgabenerkennung aus ausdrücklich aufgenommenen Rohquellen.

Die Prüfung hat ihren eigenen Fortschritt: Wissensverdichtung und Zusagenerkennung
müssen dieselbe Quelle unabhängig ansehen können. Nur Vorschläge werden gespeichert.
"""
from dataclasses import dataclass
from typing import Callable

from .episodes import AUSGEBLENDETE_ZUSTAENDE, ROHQUELLEN, EpisodeError
from .memory_analysis import interpret, segment, model_key
from .proposals import ProposalKind
from .task_review import REVIEW_MARKER, current_task_context, task_context_matches
from .model import SourceType
from .hintergrund import BackgroundInterrupted


@dataclass
class DetectionReport:
    analyzed: int = 0
    proposed: int = 0
    failed: int = 0
    superseded: int = 0
    available: bool = False
    cancelled: bool = False


class TaskDetector:
    def __init__(self, episodes, proposals, provider, lock, tasks=None):
        self.episodes = episodes
        self.proposals = proposals
        self.provider = provider
        self.lock = lock
        self.tasks = tasks

    def expire_sources(self) -> int:
        """Offene Vorschläge aus entzogenen Quellen sichtbar außer Kraft setzen."""
        count = 0
        with self.lock:
            for proposal in self.proposals.pending(ProposalKind.TASK, limit=-1):
                existing = self.tasks.get(f't-suggestion-{proposal.id}') if self.tasks is not None else None
                if existing is not None:
                    # Ein Abbruch nach der ausdrücklichen Aufgabenübernahme darf
                    # beim nächsten Lauf nicht als Quellenentzug umgedeutet werden.
                    self.proposals.accept(proposal.id, produced=existing.id)
                    continue
                valid = bool(proposal.evidence) and task_context_matches(proposal, self.episodes)
                for evidence in proposal.evidence:
                    try:
                        episode = self.episodes.get(evidence.episode_id)
                        valid = valid and episode.state not in AUSGEBLENDETE_ZUSTAENDE and episode.digest == evidence.digest and evidence.quote in episode.body
                    except EpisodeError:
                        valid = False
                if not valid:
                    self.proposals.supersede(proposal.id)
                    count += 1
        return count

    def run(self, *, with_model: bool, limit: int = 10, rechecks_only: bool = False, permitted: Callable[[], bool] = lambda: True) -> DetectionReport:
        # Der kurze Takt liest nur die Wiedervorlage; Anzeige/Übernahme prüfen Quellen weiterhin frisch.
        report = DetectionReport(superseded=0 if rechecks_only else self.expire_sources())
        if not with_model or self.provider is None or not getattr(self.provider, 'is_local', False):
            return report
        report.available = True
        attempted = 0
        cursor = self.proposals.task_scan_cursor()
        budget = max(0, min(limit, 20))
        priority_budget = budget if rechecks_only else self.episodes.task_recheck_budget(budget)

        def work():
            # Höchstens eine begrenzte Queue-Seite; im Bestandslauf das halbe Modellbudget.
            # Der kurze Takt nutzt nur die Queue. Im Bestandslauf mit Budget 1 wechselt die Spur dauerhaft.
            if priority_budget:
                for row in self.episodes.task_rechecks():
                    if attempted >= priority_budget:
                        break
                    try:
                        snapshot = self.episodes.get(row['id'])
                    except EpisodeError:
                        self.episodes.finish_task_recheck(row, completed=True)
                        continue
                    yield snapshot, row
            while not rechecks_only and attempted < budget:
                batch = self.episodes.analysis_batch(cursor)
                if not batch:
                    self.proposals.advance_task_scan('')
                    return
                for snapshot in batch:
                    yield snapshot, None

        for snapshot, recheck in work():
            if recheck is None:
                cursor = snapshot.id
            with self.lock:
                if not permitted():
                    report.cancelled = True
                    return report
                current = self.episodes.get(snapshot.id)
                if current.state in AUSGEBLENDETE_ZUSTAENDE or current.kind not in ROHQUELLEN:
                    if recheck is not None:
                        self.episodes.finish_task_recheck(recheck, completed=True)
                    continue
                from .model import SourceType
                if current.provenance.source_type is SourceType.EMAIL and 'source:truncated' in current.tags:
                    report.failed += 1
                    if recheck is not None:
                        self.episodes.finish_task_recheck(recheck, completed=False)
                    continue
                context = current_task_context(self.episodes, current.id)
                if context is None:
                    if recheck is not None:
                        self.episodes.finish_task_recheck(recheck, completed=True)
                    continue
                job = self.proposals.memory_analysis.acquire(current, self.provider, context=context)
                if job is None:
                    if recheck is not None:
                        complete = self.proposals.memory_analysis.completed(current, self.provider, context=context)
                        self.episodes.finish_task_recheck(recheck, completed=complete)
                    continue
            attempted += 1
            result = None
            try:
                # Den Schreiblock nicht während eines langsamen Modellaufrufs halten.
                text, end = segment(current.body, job['offset'])
                items = interpret(self.provider, current.title, text)
                # Mail tasks need a semantic check with the complete mail,
                # not only the extraction segment. Foreign promises are
                # not silently converted into the recipient's own work.
                if current.provenance.source_type is SourceType.EMAIL and items:
                    with self.lock:
                        fresh = self.episodes.get(current.id)
                        if (not permitted() or fresh.state in AUSGEBLENDETE_ZUSTAENDE
                                or fresh.digest != current.digest or fresh.contacts != current.contacts or fresh.tags != current.tags
                                or model_key(self.provider) != job['model']
                                or current_task_context(self.episodes, current.id) != context):
                            self.proposals.memory_analysis.abandon(job, state='cancelled')
                            report.cancelled = True
                            return report
                    from .task_review import review_tasks
                    own_source = any(contact.get('rolle') == 'von' and contact.get('ich') is True
                                     for contact in current.contacts)
                    items = review_tasks(self.provider, current.title, current.body, items, own_source=own_source)
            except BackgroundInterrupted:
                self.proposals.memory_analysis.abandon(job, state='cancelled')
                raise
            except Exception:
                # Fehler bleiben erneut prüfbar, ohne fremde Texte im Status.
                report.failed += 1
                self.proposals.memory_analysis.abandon(job)
            else:
                with self.lock:
                    if not permitted():
                        self.proposals.memory_analysis.abandon(job, state='cancelled')
                        report.cancelled = True
                        return report
                    fresh = self.episodes.get(current.id)
                    if (fresh.state not in AUSGEBLENDETE_ZUSTAENDE and fresh.digest == current.digest
                            and fresh.contacts == current.contacts and fresh.tags == current.tags
                            and model_key(self.provider) == job['model']
                            and current_task_context(self.episodes, current.id) == context):
                        try:
                            result = self.proposals.memory_analysis.finish(
                                job, items, end,
                                proposed_by=f"{getattr(self.provider, 'name', 'local')}/{getattr(self.provider, 'model', '')}"
                                            + (REVIEW_MARKER if current.provenance.source_type is SourceType.EMAIL else ''),
                            )
                        except Exception:
                            self.proposals.memory_analysis.abandon(job)
                            raise
                        if result is not None:
                            report.proposed += result[0]
                            report.analyzed += int(result[1])
                    else:
                        self.proposals.memory_analysis.abandon(job, state='cancelled')
            if recheck is not None:
                self.episodes.finish_task_recheck(recheck, completed=result is not None and result[1])
            else:
                self.proposals.advance_task_scan(cursor)
            if attempted >= budget:
                break
        return report


BRIEFING_ITEMS = 3


def _absender(episode) -> str | None:
    """Anzeigename des Absenders, sonst die Adresse; nur bei Mails."""
    from email.utils import parseaddr
    from .model import SourceType
    if episode.provenance.source_type is not SourceType.EMAIL or not episode.participants:
        return None
    name, address = parseaddr(episode.participants[0])
    return (name or address or '').strip() or None


def candidate_batches(proposals, episodes, *, now=None):
    """Valid evidence plus separate source/import time; no persisted record is rewritten."""
    from datetime import datetime, timezone
    from .mail_timeline import timings, ReplyIndex
    now = now or datetime.now(timezone.utc)
    relations = ReplyIndex(episodes)
    for batch in proposals.pending_batches(ProposalKind.TASK):
        valid = []
        for proposal in batch:
            if len(proposal.evidence) != 1:
                continue
            evidence = proposal.evidence[0]
            try:
                episode = episodes.get(evidence.episode_id)
            except EpisodeError:
                continue
            if (episode.state in AUSGEBLENDETE_ZUSTAENDE or episode.digest != evidence.digest
                    or not evidence.quote or evidence.quote not in episode.body
                    or not task_context_matches(proposal, episodes)):
                continue
            valid.append((proposal, episode))
        temporal = timings(episodes, [e for _, e in valid], now=now, relations=relations)
        yield [(p, e, temporal[e.id]) for p, e in valid]


def for_briefing(proposals, episodes, *, limit: int = BRIEFING_ITEMS, now=None) -> dict:
    """Only recent non-inventory suggestions compete for today's attention.

    Historical, undated and followed-up requests stay in the explicit review queue.
    Even a recent source is a suggestion, never proof of an outstanding obligation.
    """
    items, pending, review_pending = [], 0, 0
    for batch in candidate_batches(proposals, episodes, now=now):
        for proposal, episode, timing in batch:
            if timing['temporal_status'] != 'recent':
                review_pending += 1
                continue
            pending += 1
            items.append({
                'id': proposal.id, 'statement': proposal.statement, 'quote': proposal.evidence[0].quote,
                'episode_id': episode.id, 'sender': _absender(episode), **timing,
                'review_required': episode.provenance.source_type is SourceType.EMAIL
                    and (proposal.task_context is None or not proposal.proposed_by.endswith(REVIEW_MARKER)),
            })
            # Keep memory bounded even when a large inventory produced many candidates.
            items.sort(key=lambda item: item['received_at'] or '', reverse=True)
            items = items[:max(0, limit)]
    return {'pending': pending, 'review_pending': review_pending, 'items': items, 'error': None}
