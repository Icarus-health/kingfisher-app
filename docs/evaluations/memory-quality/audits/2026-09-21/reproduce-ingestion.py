"""Synthetic intake audit. No model/network access or existing user data."""
from contextlib import ExitStack
from datetime import datetime, timezone
from email.message import EmailMessage
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='intake-', dir=ROOT) as directory:
    os.environ['ICARUS_DATA_DIR'] = directory
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.claims import ClaimStore
    from icarus_memory.consolidation import Consolidator
    from icarus_memory.connectors.mail import Message, FULL_BODY_LIMIT, _body
    from icarus_memory.document_text import docx_text
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.mail_ingestion import remember
    from icarus_memory.memory_routes import coverage
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.policy import Policy
    from icarus_memory.proposals import ProposalKind, ProposalStore
    from icarus_memory.providers import Reply
    from icarus_memory.server import create_app
    from icarus_memory.task_detection import TaskDetector

    root = Path(directory)
    output = {}
    with ExitStack() as stack:
        episodes = EpisodeStore(root / 'sources.sqlite3'); stack.callback(episodes.close)
        proposals = ProposalStore(root / 'candidates.sqlite3'); stack.callback(proposals.close)
        claims = ClaimStore(root / 'knowledge.sqlite3'); stack.callback(claims.close)
        audit = AuditLog(root / 'synthetic-audit.sqlite3'); stack.callback(audit.close)
        store = SelfModelStore(MemoryBackend(), subject_id='synthetic')
        app = create_app(store, episodes=episodes, proposals=proposals, knowledge=claims, audit=audit)
        client = TestClient(app)
        p1 = client.post('/api/v1/projects', json={'name': 'Synthetic One'}).json()['id']
        p2 = client.post('/api/v1/projects', json={'name': 'Synthetic Two'}).json()['id']
        body = 'Aurora Kontakt: Kira arbeitet bei Beispiel.'
        first = client.post('/api/v1/sources/documents', json={
            'filename': 'one.txt', 'body': body, 'project_id': p1}).json()
        second = client.post('/api/v1/sources/documents', json={
            'filename': 'two.txt', 'body': body, 'project_id': p2}).json()
        output['upload_second_location'] = dict(first=first, second=second,
            second_project_has_source=bool(episodes.by_project(p2)),
            stored_source_refs=[e.provenance.source_ref for e in episodes.all_episodes()])

        class KnowledgeReader:
            name = model = 'synthetic'
            is_local = True
            calls = 0
            def complete(self, messages, tools):
                self.calls += 1
                assert tools == []
                return Reply(text=json.dumps({'vorschlaege': [{
                    'aussage': 'Kira arbeitet bei Beispiel.', 'art': 'relationship',
                    'zitat': 'Kira arbeitet bei Beispiel.'}]}))
        provider = KnowledgeReader()
        agent = Agent(store=store, policy=Policy(), audit=audit, tools={}, provider=provider,
            knowledge=claims, episodes=episodes, max_rounds=1)
        before = agent.answer_memory('Wo arbeitet Kira?')
        consolidation = Consolidator(store, episodes, proposals, provider)
        report = consolidation.run()
        accepted = consolidation.accept(proposals.pending(ProposalKind.ASSERTION)[0].id)
        after = agent.answer_memory('Wo arbeitet Kira?')
        output['raw_to_memory_answer'] = {
            'raw_search_ids': [e.id for e in episodes.search('Kira')],
            'before': {'reply': before.reply, 'contract': before.context['answer_contract']},
            'consolidation': report.to_dict(), 'accepted_self_model_id': accepted.id,
            'after': {'reply': after.reply, 'contract': after.context['answer_contract']},
            'claim_count': len(claims.all_claims()), 'self_model_count': len(store.usable()),
        }

    with ExitStack() as stack:
        episodes = EpisodeStore(root / 'mail-sources.sqlite3'); stack.callback(episodes.close)
        proposals = ProposalStore(root / 'mail-candidates.sqlite3'); stack.callback(proposals.close)
        original = EmailMessage()
        original.set_content('Hintergrund ohne Auftrag.\n' * 1000 + 'Bitte TAIL_ONLY die Vertragsfrist prüfen.')
        original.add_attachment(b'Bitte ATTACHMENT_ONLY pruefen.', maintype='text', subtype='plain', filename='task.txt')
        parsed = _body(original, limit=FULL_BODY_LIMIT + 1)
        message = Message(uid='work:7.1', subject='Synthetic long mail', sender='sender@example.invalid',
            date=datetime.now(timezone.utc), preview='', unread=True, account_id='work',
            body=parsed[:FULL_BODY_LIMIT], truncated=len(parsed) > FULL_BODY_LIMIT)
        result = remember(episodes, message)
        source = episodes.get(result['episode']['id'])
        class EmptyReader:
            name = model = 'synthetic-empty'
            is_local = True
            def complete(self, messages, tools):
                assert tools == []
                return Reply(text='{"items": []}')
        detector = TaskDetector(episodes, proposals, EmptyReader(), RLock())
        for _ in range(10):
            detector.run(with_model=True, limit=1)
            snapshot = proposals.memory_analysis.snapshot(source.id)
            if snapshot and snapshot['state'] == 'completed':
                break
        output['truncated_mail_analysis'] = {
            'stored_characters': len(source.body), 'tags': source.tags,
            'tail_present': 'TAIL_ONLY' in source.body,
            'attachment_present': 'ATTACHMENT_ONLY' in source.body,
            'analysis': proposals.memory_analysis.snapshot(source.id),
            'coverage': coverage(episodes, proposals),
        }

    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    archive = BytesIO()
    with ZipFile(archive, 'w') as docx:
        docx.writestr('word/document.xml', f'<w:document xmlns:w="{ns}"><w:body><w:p><w:r><w:t>BODY_ONLY</w:t></w:r></w:p></w:body></w:document>')
        docx.writestr('word/header1.xml', f'<w:hdr xmlns:w="{ns}"><w:p><w:r><w:t>HEADER_ONLY</w:t></w:r></w:p></w:hdr>')
        docx.writestr('word/footnotes.xml', f'<w:footnotes xmlns:w="{ns}"><w:footnote w:id="1"><w:p><w:r><w:t>FOOTNOTE_ONLY</w:t></w:r></w:p></w:footnote></w:footnotes>')
    extracted = docx_text(archive.getvalue())
    output['docx_components'] = {'preview_body': extracted, 'header_present': 'HEADER_ONLY' in extracted,
        'footnote_present': 'FOOTNOTE_ONLY' in extracted}
    print(json.dumps(output, ensure_ascii=False, indent=2))
