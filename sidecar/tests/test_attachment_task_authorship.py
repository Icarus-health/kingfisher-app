"""Transportkontakte belegen nicht den Sprecher eines weitergereichten Dokuments."""
from datetime import datetime, timezone
from threading import RLock

import pytest

from icarus_memory import anhaenge
from icarus_memory.aufgaben_von_selbst import Durchlauf, person_der_quelle, pruefen
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_ingestion import remember
from icarus_memory.proposals import ProposalStore, ProposalKind
from icarus_memory.task_detection import TaskDetector
from icarus_memory.tasks import TaskStore
from .test_mail_docx_attachments import word, message, DOCX_MIME
from .test_own_promise_retention import SavedReplies


QUOTE = 'Ich werde dir die Kalkulation senden.'


@pytest.fixture(params=['docx', 'pdf'])
def document_mail(tmp_path, request):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    now = datetime.now(timezone.utc)
    if request.param == 'docx':
        attachment, = anhaenge.aus_mail(message(('Fremder-Entwurf.docx', word(text=QUOTE), DOCX_MIME)))
    else:
        attachment = anhaenge.Anhang('Fremder-Entwurf.pdf', 'pdf', anhaenge.GELESEN, (QUOTE,), 1)
    mail = Message(uid='a:7.1', subject='Fremder Entwurf zur Prüfung',
        sender='Lea <lea.hartmann@gmail.com>', date=now, preview='', unread=False,
        body='Anbei ein fremder Entwurf zur Prüfung, keine eigene Zusage.', account_id='a',
        message_id='<actor-probe@example.invalid>', own_addresses=('leahartmann@gmail.com',),
        recipients=({'name': 'Nora', 'adresse': 'nora@example.invalid', 'rolle': 'an'},),
        anhaenge=(attachment,))
    child_id, = remember(episodes, mail)['anhaenge']
    try:
        yield episodes, proposals, tasks, child_id, now
    finally:
        tasks.close()
        proposals.close()
        episodes.close()


def test_parent_sender_does_not_prove_document_authorship(document_mail):
    episodes, proposals, _, child_id, _ = document_mail
    provider = SavedReplies({'title': QUOTE, 'quote': QUOTE}, kind='own_commitment', supported=True)
    result = TaskDetector(episodes, proposals, provider, RLock()).run(
        with_model=True, quellenfilter=lambda e: e.id == child_id)
    assert result.failed == 0 and result.proposed == 0
    assert proposals.pending(ProposalKind.TASK) == []
    assert QUOTE in episodes.get(child_id).body
    assert episodes.get(child_id).contacts[0]['ich'] is True  # Transportkontakt bleibt erhalten.


def test_attachment_candidate_keeps_manual_responsibility_even_with_positive_judge(document_mail):
    episodes, proposals, tasks, child_id, now = document_mail
    provider = SavedReplies({'title': QUOTE, 'quote': QUOTE}, kind='request_to_recipient', supported=True)
    result = TaskDetector(episodes, proposals, provider, RLock()).run(
        with_model=True, quellenfilter=lambda e: e.id == child_id)
    assert result.failed == 0 and result.proposed == 1
    candidate, = proposals.pending(ProposalKind.TASK)
    child = episodes.get(child_id)
    assert person_der_quelle(child, ['leahartmann@gmail.com']) == (None, None)
    verdict = pruefen(candidate, child, eigene=['leahartmann@gmail.com'], jetzt=now,
                      zeitstatus='recent', aus_bestand=False, dublette=False, zurueckgenommen=False)
    assert verdict.eindeutig is False
    runner = Durchlauf(tasks, episodes, proposals, eigene=lambda: ['leahartmann@gmail.com'], jetzt=lambda: now)
    runner.schritt()
    assert tasks.open_tasks(limit=None) == []
    assert len(proposals.pending(ProposalKind.TASK)) == 1
