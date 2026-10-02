"""Fortlaufende lokale Aufgabenerkennung aus ausdrücklich aufgenommenen Rohquellen.

Die Prüfung hat ihren eigenen Fortschritt: Wissensverdichtung und Zusagenerkennung
müssen dieselbe Quelle unabhängig ansehen können. Nur Vorschläge werden gespeichert.
"""
from dataclasses import dataclass
from typing import Callable

from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeError
from .memory_analysis import interpret, segment, model_key
from .proposals import ProposalKind


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
                valid = bool(proposal.evidence)
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

    def run(self, *, with_model: bool, limit: int = 10, permitted: Callable[[], bool] = lambda: True) -> DetectionReport:
        report = DetectionReport(superseded=self.expire_sources())
        if not with_model or self.provider is None or not getattr(self.provider, 'is_local', False):
            return report
        report.available = True
        attempted = 0
        cursor = self.proposals.task_scan_cursor()
        while attempted < max(0, min(limit, 20)):
            batch = self.episodes.analysis_batch(cursor)
            if not batch:
                self.proposals.advance_task_scan('')
                break
            for snapshot in batch:
                cursor = snapshot.id
                with self.lock:
                    if not permitted():
                        report.cancelled = True
                        return report
                    current = self.episodes.get(snapshot.id)
                    if current.state in AUSGEBLENDETE_ZUSTAENDE:
                        continue
                    job = self.proposals.memory_analysis.acquire(current, self.provider)
                    if job is None:
                        continue
                attempted += 1
                try:
                    # Den Schreiblock nicht während eines langsamen Modellaufrufs halten.
                    text, end = segment(current.body, job['offset'])
                    items = interpret(self.provider, current.title, text)
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
                                and model_key(self.provider) == job['model']):
                            try:
                                result = self.proposals.memory_analysis.finish(
                                    job, items, end,
                                    proposed_by=f"{getattr(self.provider, 'name', 'local')}/{getattr(self.provider, 'model', '')}",
                                )
                            except Exception:
                                self.proposals.memory_analysis.abandon(job)
                                raise
                            if result is not None:
                                report.proposed += result[0]
                                report.analyzed += int(result[1])
                        else:
                            self.proposals.memory_analysis.abandon(job, state='cancelled')
                self.proposals.advance_task_scan(cursor)
                if attempted >= max(0, min(limit, 20)):
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


def for_briefing(proposals, episodes, *, limit: int = BRIEFING_ITEMS) -> dict:
    """Offene Aufgabenvorschläge mit Herkunft, nur lesend.

    Wer schreibt und wann, steht nicht im Vorschlag, sondern in der Quelle.
    Ein Vorschlag, dessen Quelle ausgeschlossen oder verändert ist, wird hier
    nur übersprungen; außer Kraft setzt ihn weiterhin `expire_sources`.
    Die Ältesten zuerst: Sie warten am längsten.
    """
    items, pending = [], 0
    for proposal in proposals.pending(ProposalKind.TASK, limit=200):
        evidence = proposal.evidence[0] if proposal.evidence else None
        if evidence is None:
            continue
        try:
            episode = episodes.get(evidence.episode_id)
        except EpisodeError:
            continue
        if (episode.state in AUSGEBLENDETE_ZUSTAENDE
                or episode.digest != evidence.digest or evidence.quote not in episode.body):
            continue
        pending += 1
        if len(items) < limit:
            received = episode.occurred_at or episode.recorded_at
            items.append({
                'id': proposal.id,
                'statement': proposal.statement,
                'quote': evidence.quote,
                'episode_id': episode.id,
                'sender': _absender(episode),
                'received_at': received.isoformat() if received else None,
            })
    return {'pending': pending, 'items': items, 'error': None}
