"""Ausdrückliche Übernahme belegter Vorschläge in die eine Aufgabenablage."""
from .episodes import AUSGEBLENDETE_ZUSTAENDE, QUELLEN_ARTEN
from .model import Provenance, SourceType, now
from .proposals import ProposalError, ProposalKind, ProposalState
from .task_review import task_context_matches
from .tasks import CORRECTED_CITATION_REVIEW, TaskRequestConflict


class TaskCandidates:
    def __init__(self, episodes, proposals, tasks, workspace, lock):
        self.episodes = episodes
        self.proposals = proposals
        self.tasks = tasks
        self.workspace = workspace
        self.lock = lock

    def amend_title(self, proposal_id, *, title, expected_statement, expected_episode_id,
                    expected_digest, expected_task_context):
        """Korrigiert nur einen offenen, quellgebundenen Titel; legt keine Aufgabe an."""
        from . import logbuch
        from .task_review import current_task_context, hard_details_supported

        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 4096:
            raise ValueError('Der Aufgabentitel darf nicht leer oder zu lang sein.')
        title = title.strip()
        # Gleiche Reihenfolge wie die anderen quellgebundenen Schreibpfade:
        # Anwendung → Quellenreservierung → Vorschlagstransaktion. BEGIN
        # IMMEDIATE hält auch andere SQLite-Verbindungen bis zum Commit fern.
        with self.lock, self.episodes.transaction(), self.proposals.transaction():
            candidate = self.proposals.get(proposal_id)
            if (candidate.kind is not ProposalKind.TASK or len(candidate.evidence) != 1
                    or not candidate.task_context or candidate.produced is not None
                    or candidate.statement != expected_statement
                    or candidate.task_context != expected_task_context
                    or candidate.evidence[0].episode_id != expected_episode_id
                    or candidate.evidence[0].digest != expected_digest):
                raise ProposalError('Der Aufgabenvorschlag hat sich geändert. Bitte erneut prüfen.')
            if self.tasks.get(f't-suggestion-{candidate.id}') is not None:
                raise ProposalError('Diese Aufgabe wurde bereits übernommen. Bitte die Aufgabe öffnen.')

            def source_current():
                try:
                    snapshot = self.episodes.belegbarer_snapshot(expected_episode_id)
                    if snapshot is None:
                        return False
                    episode = snapshot.episode
                    return (episode.state not in AUSGEBLENDETE_ZUSTAENDE
                        and 'source:truncated' not in episode.tags
                        and episode.digest == expected_digest
                        and bool(candidate.evidence[0].quote)
                        and candidate.evidence[0].quote in episode.body
                        and current_task_context(self.episodes, episode.id) == expected_task_context)
                except (ValueError, LookupError):
                    return False

            if not source_current():
                raise ProposalError('Die Quelle ist nicht mehr gültig. Bitte erneut prüfen.')
            if title != candidate.statement and not hard_details_supported(title, candidate.evidence[0].quote):
                raise ValueError('Der korrigierte Titel enthält nicht belegte Angaben.')
            result = self.proposals.amend_pending_task_title(proposal_id, title=title,
                expected_statement=expected_statement, expected_episode_id=expected_episode_id,
                expected_digest=expected_digest, expected_task_context=expected_task_context)
            # Unmittelbar vor dem Vorschlags-Commit; Fehler nehmen beide
            # Vorschlagsänderungen zurück. Die Quellenreservierung bleibt offen.
            if not source_current():
                raise ProposalError('Die Quelle hat sich geändert. Bitte erneut prüfen.')
            changed = candidate.state is ProposalState.PENDING and result.id != candidate.id
        if changed:
            logbuch.vermerke('aufgabenvorschlag_titel_korrigiert', id=proposal_id, nachfolger=result.id)
        return result

    def accept(self, proposal_id, *, title, project_id=None, new_project_name=None, due=None, waiting_for=None,
               person=None, angelegt=None, zuordnung_aus_vorschlag=False, eigene=()):
        """Übernimmt einen belegten Vorschlag. Die Person (wer bittet, wem zugesagt wurde) ergibt sich aus der Quelle,
        wenn sie nicht mitkommt; `zuordnung_aus_vorschlag` übernimmt das vorgeschlagene Projekt (Quelle oder
        Absenderregel), wenn keines gewählt ist (Heute, `aufgaben_von_selbst.py`)."""
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
            from .task_deadline_review import deadline_review
            review = deadline_review(self.episodes, candidate, episode)
            if review is not None:
                raise ProposalError(review['temporal_reason'])
            from .aufgaben_von_selbst import Durchlauf, person_der_quelle
            if person is None:
                person = person_der_quelle(episode, eigene)[1]
            if zuordnung_aus_vorschlag and not project_id and new_project_name is None:
                projekt = Durchlauf(self.tasks, self.episodes, self.proposals, workspace=self.workspace).projekt(
                    candidate, episode)
                project_id = projekt['project_id'] if projekt else None
            # A reanalysis can have a new proposal ID. A shared quotation alone
            # is ambiguous, so use the accepted proposal's original statement.
            source_text = None if 'source:truncated' in episode.tags else episode.body
            proven_retry_id = self._proven_retry_id(candidate, evidence, source_text)
            create_project = None
            if proven_retry_id is not None:
                project_id = None  # Existing task and project assignment are preserved.
            elif new_project_name is not None:
                name = new_project_name.strip()
                if project_id or not 1 <= len(name) <= 200:
                    raise ValueError('Bitte ein vorhandenes oder ein neues Projekt wählen.')
                def create_project() -> str:
                    return self.workspace.project_from_task_suggestion(candidate.id, name,
                        Provenance(source_type=SourceType.USER_STATED, source_ref=f'episode:{episode.id}',
                                   captured_at=now(), verbatim=evidence.quote)).id
            if project_id:
                if not self.workspace.project(project_id).is_open():
                    raise ProposalError('Das Projekt ist inzwischen abgeschlossen. Bitte neu zuordnen.')
            task = self.tasks.from_suggestion(
                candidate.id, title,
                Provenance(source_type=SourceType.USER_STATED, source_ref=f'episode:{episode.id}',
                           captured_at=now(), verbatim=evidence.quote),
                due=due, project_id=project_id, waiting_for=waiting, person=person, angelegt=angelegt,
                proven_retry_id=proven_retry_id, create_project=create_project, source_text=source_text,
            )
            self.proposals.accept(candidate.id, produced=task.id)
            return task

    def _proven_retry_id(self, candidate, evidence, source_text):
        prefix = "t-suggestion-"
        corrected = self.tasks.corrected_source_citations(f"episode:{evidence.episode_id}", evidence.quote, source_text)
        if not corrected:
            return None
        exact = [task_id for task_id, quote in corrected if quote == evidence.quote]
        if len(exact) == 1 and exact[0].startswith(prefix):
            task_id = exact[0]
            try:
                original = self.proposals.get(task_id[len(prefix):])
            except ProposalError:
                original = None
            if (original is not None and original.kind is ProposalKind.TASK and original.state is ProposalState.ACCEPTED
                    and original.produced == task_id and original.statement == candidate.statement
                    and len(original.evidence) == 1
                    and original.evidence[0].episode_id == evidence.episode_id
                    and original.evidence[0].quote == evidence.quote):
                return task_id
        raise TaskRequestConflict(CORRECTED_CITATION_REVIEW)

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
