"""Synthetic local UI check with deterministic provider; no personal data or LLM."""
import json
import os
from datetime import datetime, timezone
from threading import RLock
import uvicorn
from icarus_memory.server import create_app
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.proposals import Evidence
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import remember
from icarus_memory.task_detection import TaskDetector


class Reader:
    name = model = 'synthetic-audit'
    is_local = True

    def complete(self, messages, tools):
        return Reply(text='{"items": []}', model=self.model)

    def complete_json(self, messages, **kwargs):
        schema = kwargs.get('schema', {})
        if 'items' in schema.get('properties', {}):
            return Reply(text='{"items": []}', model=self.model)
        if 'points' in schema.get('properties', {}):
            sources = [json.loads(m['content'].split('\n', 1)[1]) for m in messages[2:-1]]
            source = sources[0]
            return Reply(text=json.dumps({'points': [{'text': 'Laut Quelle wurde Planung besprochen.',
                'citations': [{'source_id': source['source_id'], 'quote': source['text'][:80]}]}],
                'questions': [], 'conflicts': []}), model=self.model)
        return Reply(text='{"version":1,"kind":"evidence","evidence_ids":["E1"]}', model=self.model)


app = create_app()
app.state.agent._provider = Reader()
if not app.state.episodes.all_episodes():
    source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Undatierte Planungsnotiz',
        'Wir treffen uns Freitag zur Planung.',
        Provenance(SourceType.EMAIL, source_ref='synthetic:lea'), participants=['Lea'])
    original = 'Mira: Wenn die Freigabe kommt, prüfe ich Aurora am Freitag. Es gibt noch keine feste Zusage.'
    source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Bedingte Zusage', original,
        Provenance(SourceType.EMAIL, source_ref='synthetic:aurora'))
    app.state.claims.entities.create('project', 'Aurora', explicit_id='project:aurora')
    proposal, _ = app.state.knowledge_service.propose(subject_ref='project:aurora',
        predicate='review_status', value='bedingt, keine feste Zusage',
        statement='Mira prüft Aurora nur nach Freigabe; eine feste Zusage liegt noch nicht vor.',
        rationale='Synthetic accepted paraphrase', evidence=[Evidence(source.id, original, source.digest)])
    app.state.knowledge_service.accept(proposal.id, supersedes=[])
    remember(app.state.episodes, Message(uid='audit:1', subject='Gekürzte Beispielmail',
        sender='test@example.invalid', date=None, preview='', unread=True,
        account_id='synthetic', body='Nur der empfangene Ausschnitt.', truncated=True))
    TaskDetector(app.state.episodes, app.state.proposals, Reader(), RLock()).run(with_model=True)

uvicorn.run(app, host=os.environ.get('AUDIT_HOST', '127.0.0.1'),
            port=int(os.environ.get('AUDIT_PORT', '18996')), log_level='warning')
