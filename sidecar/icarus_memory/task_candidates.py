"""Ausdrückliche Übernahme belegter Vorschläge in die eine Aufgabenablage."""
from .episodes import AUSGEBLENDETE_ZUSTAENDE, QUELLEN_ARTEN
from .model import Provenance, SourceType, now
from .proposals import ProposalError, ProposalKind, ProposalState
from .task_review import task_context_matches


class TaskCandidates:
    def __init__(self, episodes, proposals, tasks, workspace, lock):
        self.episodes = episodes
        self.proposals = proposals
        self.tasks = tasks
        self.workspace = workspace
        self.lock = lock

    def accept(self, proposal_id, *, title, project_id=None, due=None, waiting_for=None):
        title = title.strip()
        waiting = waiting_for.strip() if waiting_for is not None else None
        if not title or len(title) > 4096 or (waiting is not None and (not waiting or len(waiting) > 1024)):
            raise ValueError('Aufgabe und gegebenenfalls wartende Person dürfen nicht leer sein.')
        with self.lock:
            candidate = self.proposals.get(proposal_id)
            if candidate.kind is not ProposalKind.TASK:
                raise ProposalError('Dies ist kein Aufgabenvorschlag.')
            if candidate.state is ProposalState.ACCEPTED:
                existing = self.tasks.get(candidate.produced)
                if existing is None:
                    raise ProposalError('Die übernommene Aufgabe ist nicht verfügbar.')
                return existing
            if candidate.state is not ProposalState.PENDING:
                raise ProposalError('Der Vorschlag ist nicht mehr offen.')
            # Die Aufgabe kann vor einem Abbruch bereits gespeichert worden sein.
            # Wiederholen darf sie weder verändern noch doppelt anlegen.
            existing = self.tasks.get(f't-suggestion-{candidate.id}')
            if existing is not None:
                self.proposals.accept(candidate.id, produced=existing.id)
                return existing
            if len(candidate.evidence) != 1:
                raise ProposalError('Der Vorschlag braucht genau eine überprüfbare Quelle.')
            evidence = candidate.evidence[0]
            episode = self.episodes.get(evidence.episode_id)
            if (episode.state in AUSGEBLENDETE_ZUSTAENDE or episode.kind not in QUELLEN_ARTEN
                    or episode.digest != evidence.digest or not evidence.quote or evidence.quote not in episode.body
                    or not task_context_matches(candidate, self.episodes)):
                raise ProposalError('Die Quelle ist nicht mehr gültig. Bitte erneut prüfen.')
            if project_id:
                self.workspace.project(project_id)
            task = self.tasks.from_suggestion(
                candidate.id, title,
                Provenance(source_type=SourceType.USER_STATED, source_ref=f'episode:{episode.id}',
                           captured_at=now(), verbatim=evidence.quote),
                due=due, project_id=project_id, waiting_for=waiting,
            )
            self.proposals.accept(candidate.id, produced=task.id)
            return task

    def reject(self, proposal_id):
        with self.lock:
            candidate = self.proposals.get(proposal_id)
            if candidate.kind is not ProposalKind.TASK:
                raise ProposalError('Dies ist kein Aufgabenvorschlag.')
            if candidate.state is ProposalState.REJECTED:
                return candidate
            if self.tasks.get(f't-suggestion-{candidate.id}') is not None:
                raise ProposalError('Diese Aufgabe wurde bereits übernommen. Bitte die Aufgabe öffnen.')
            return self.proposals.reject(candidate.id)
