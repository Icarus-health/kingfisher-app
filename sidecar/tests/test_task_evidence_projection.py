"""Previously cached positive reviews cannot bypass today's literal checks."""
from datetime import datetime, timezone
import json

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.providers import Reply
from icarus_memory.memory_analysis import interpret
from icarus_memory.task_detection import for_briefing
from icarus_memory.task_review import current_task_context
from tests.test_local_mail_workflow import env as saved_mail_env, root


def test_cached_positive_verdict_stays_visible_but_requires_review_without_record_changes(saved_mail_env):
    app, client, _, calls, provider = saved_mail_env
    source = app.state.episodes.record(EpisodeKind.MESSAGE, 'Auftrag', 'Bitte ruf Anna Kranz an.',
        Provenance(source_type=SourceType.EMAIL), occurred_at=datetime.now(timezone.utc))[0]
    job = app.state.proposals.memory_analysis.acquire(source, provider,
        context=current_task_context(app.state.episodes, source.id))
    app.state.proposals.memory_analysis.finish(job,
        [{'title': 'Ben Kruse anrufen', 'quote': source.body}],
        len(source.body), proposed_by='test/local/task-review-v1')
    proposal = app.state.proposals.pending(ProposalKind.TASK)[0]
    before = proposal.to_dict()
    assert client.get(root(source)).json()['items'][0]['review_required'] is True
    assert for_briefing(app.state.proposals, app.state.episodes)['items'][0]['review_required'] is True
    assert app.state.proposals.get(proposal.id).to_dict() == before
    assert calls == [] and app.state.tasks.all_tasks() == []


def test_non_mail_extraction_replaces_invented_title_with_unchanged_original():
    class Local:
        is_local = True
        def complete(self, messages, tools):
            return Reply(text=json.dumps({'items': [
                {'title': 'Ben Kruse anrufen', 'quote': 'Bitte ruf Anna Kranz an.'},
                {'title': 'Entwurf prüfen', 'quote': 'Bitte prüfe den Entwurf.'},
            ]}))
    assert interpret(Local(), 'Notiz', 'Bitte ruf Anna Kranz an. Bitte prüfe den Entwurf.') == [
        {'title': 'Bitte ruf Anna Kranz an.', 'quote': 'Bitte ruf Anna Kranz an.'},
        {'title': 'Entwurf prüfen', 'quote': 'Bitte prüfe den Entwurf.'}]
