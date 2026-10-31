"""Gespeicherte synthetische Modellantworten dürfen klare Handlungen nicht verschlucken."""
import json
from datetime import datetime, timezone
from threading import RLock

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.memory_analysis import interpret
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalStore
from icarus_memory.providers import Reply
from icarus_memory.task_detection import TaskDetector, for_briefing
from icarus_memory.task_review import hard_details_supported, review_tasks
from tests.test_task_review import Reviewer, verdict

# Aus dem unveränderten synthetischen Kataloglauf vom 31.10.; keine persönlichen Daten.
INVOICE = {'title': 'Überweisung Rechnung 184',
           'quote': 'Bitte überweise die offene Rechnung über 86,40 EUR bis zum 12. November 2026.'}
APPLICATION = {'title': 'Sirius-Antrag bis 2. November 2026 um 18 oder 19 Uhr einreichen',
               'quote': 'Bitte reiche den Sirius-Antrag bis zum 2. November 2026 um 18 oder 19 Uhr ein.'}
APPLICATION_BODY = APPLICATION['quote'] + ' Die Uhrzeit ist noch offen.\n'


class SavedReplies:
    is_local = True
    name = 'synthetic'
    model = 'saved-intake-response'

    def __init__(self, item, kind='request_to_recipient', supported=True):
        self.item, self.kind, self.supported = item, kind, supported

    def complete_json(self, messages, *, max_tokens, schema):
        assert max_tokens <= 1200
        data = json.loads(messages[-1]['content'])
        if 'candidates' in data:
            return Reply(text=json.dumps({'reviews': [verdict(kind=self.kind, supported=self.supported)]}))
        return Reply(text=json.dumps({'items': [self.item]}))


@pytest.mark.parametrize('subject', ['Rechnung 184', 'Offene Rechnung'])
def test_unsupported_invoice_identifier_keeps_only_exact_evidenced_action(subject):
    result = interpret(SavedReplies(INVOICE), subject, INVOICE['quote'])
    assert result == [{'title': INVOICE['quote'], 'quote': INVOICE['quote']}]
    assert hard_details_supported(result[0]['title'], result[0]['quote'])
    assert '184' not in result[0]['title']


def test_saved_unclear_time_review_keeps_direct_request_as_original_wording():
    result = review_tasks(Reviewer([verdict(kind='unclear', supported=False)]),
                          'Sirius: unklare Uhrzeit', APPLICATION_BODY, [APPLICATION])
    assert result == [{'title': APPLICATION['quote'], 'quote': APPLICATION['quote']}]


def test_outgoing_direct_request_with_open_time_does_not_become_own_commitment():
    assert review_tasks(Reviewer([verdict(kind='unclear', supported=False)]),
                        'Sirius', APPLICATION_BODY, [APPLICATION], own_source=True) == []


def test_open_time_review_is_not_tied_to_catalog_project_or_exact_wording():
    quote = 'Bitte sende den Entwurf bis zum 8. Dezember 2026 um 17:30 oder 18:45 Uhr.'
    item = {'title': 'Entwurf senden', 'quote': quote}
    body = quote + '\nDie genaue Uhrzeit steht noch nicht fest.'
    assert review_tasks(Reviewer([verdict(kind='unclear', supported=False)]),
                        'Entwurf', body, [item]) == [{'title': quote, 'quote': quote}]


@pytest.mark.parametrize('prefix,suffix', [
    ('Hallo Lea,\n', ''),
    ('', '\nViele Grüße\nAlex'),
    ('Liebe Lea,\n\n', '\n\nMit freundlichen Grüßen\nAlex Sommer'),
])
def test_normal_mail_framing_keeps_open_time_request_without_rewriting_quote(prefix, suffix):
    body = prefix + APPLICATION_BODY + suffix
    assert review_tasks(Reviewer([verdict(kind='unclear', supported=False)]),
                        'Sirius', body, [APPLICATION]) == [
                            {'title': APPLICATION['quote'], 'quote': APPLICATION['quote']}]


@pytest.mark.parametrize('suffix', [
    '\nViele Grüße\nAlex\nNur falls die Freigabe kommt.',
    '\nViele Grüße\nAlex, nur falls die Freigabe kommt.',
    '\nViele Grüße\nNur Falls Freigabe',
    '\nViele Grüße\nErledigt',
    '\nViele Grüße\nAlex\nAnna ist zuständig.',
    '\nViele Grüße\nAlex\nDer Antrag ist abgesagt.',
    '\nViele Grüße\nAlex\n> Bitte nur nach Freigabe einreichen.',
    '\nViele Grüße\nAlex\nVon: Anna\nGesendet: 30. Oktober 2026\nAn: Lea\nBetreff: Antrag',
])
def test_mail_signature_never_hides_qualifiers_actors_cancellations_or_history(suffix):
    assert review_tasks(Reviewer([verdict(kind='unclear', supported=False)]),
                        'Sirius', 'Hallo Lea,\n' + APPLICATION_BODY + suffix, [APPLICATION]) == []


def test_normal_mail_framing_does_not_turn_outgoing_request_into_own_commitment():
    assert review_tasks(Reviewer([verdict(kind='unclear', supported=False)]),
                        'Sirius', 'Hallo Lea,\n' + APPLICATION_BODY + '\nViele Grüße\nAlex',
                        [APPLICATION], own_source=True) == []


@pytest.mark.parametrize('kind,expected', [('request_to_recipient', 1), ('other_person', 0)])
def test_invoice_repair_still_requires_semantic_ownership_review(tmp_path, kind, expected):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        episodes.record(EpisodeKind.MESSAGE, 'Rechnung 184', INVOICE['quote'],
            Provenance(source_type=SourceType.EMAIL))
        detector = TaskDetector(episodes, proposals, SavedReplies(INVOICE, kind=kind), RLock())
        assert detector.run(with_model=True).proposed == expected
        rows = proposals.pending(ProposalKind.TASK)
        assert len(rows) == expected
        if rows:
            assert rows[0].statement == INVOICE['quote']
            assert rows[0].evidence[0].quote == INVOICE['quote']
    finally:
        proposals.close()
        episodes.close()


def test_old_empty_checkpoint_is_rechecked_after_candidate_repair(tmp_path, monkeypatch):
    from icarus_memory import memory_analysis
    from icarus_memory.task_review import current_task_context
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        episode = episodes.record(EpisodeKind.MESSAGE, 'Rechnung 184', INVOICE['quote'],
            Provenance(source_type=SourceType.EMAIL))[0]
        provider = SavedReplies(INVOICE)
        with monkeypatch.context() as old:
            old.setattr(memory_analysis, 'VERSION', 'requests-v3')
            job = proposals.memory_analysis.acquire(episode, provider,
                context=current_task_context(episodes, episode.id))
            proposals.memory_analysis.finish(job, [], len(episode.body), proposed_by='synthetic/old')
        detector = TaskDetector(episodes, proposals, provider, RLock())
        assert detector.run(with_model=True).proposed == 1
        assert detector.run(with_model=True).proposed == 0
    finally:
        proposals.close()
        episodes.close()


@pytest.mark.parametrize('body,kind', [
    ('Anna sagt: ' + APPLICATION_BODY, 'unclear'),
    ('> ' + APPLICATION_BODY, 'unclear'),
    (APPLICATION_BODY + 'Anna oder du sollt das machen; wer zuständig ist, ist noch offen.', 'unclear'),
    (APPLICATION_BODY + 'Update: Der Antrag ist abgesagt.', 'unclear'),
    (APPLICATION_BODY, 'other_person'),
    (APPLICATION_BODY, 'marketing'),
])
def test_open_time_does_not_override_unclear_ownership_quotes_or_negative_context(body, kind):
    assert review_tasks(Reviewer([verdict(kind=kind, supported=False)]),
                        'Sirius', body, [APPLICATION]) == []


@pytest.mark.parametrize('change', ['ignore', 'replace'])
@pytest.mark.parametrize('body', [APPLICATION_BODY, 'Hallo Lea,\n' + APPLICATION_BODY + '\nViele Grüße\nAlex'])
def test_retained_time_candidate_needs_review_and_source_stays_bound(tmp_path, change, body):
    from icarus_memory.aufgaben_von_selbst import frist_aus, pruefen
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        at = datetime.now(timezone.utc)
        episode = episodes.record(EpisodeKind.MESSAGE, 'Sirius: unklare Uhrzeit', body,
            Provenance(source_type=SourceType.EMAIL), occurred_at=at, source_key='synthetic:sirius')[0]
        episodes.advance_source_head('synthetic:sirius', None, episode.id)
        provider = SavedReplies(APPLICATION, kind='unclear', supported=False)
        detector = TaskDetector(episodes, proposals, provider, RLock())
        report = detector.run(with_model=True)
        assert (report.proposed, report.failed) == (1, 0)
        [candidate] = proposals.pending(ProposalKind.TASK)
        assert candidate.statement == APPLICATION['quote']
        assert candidate.evidence[0].quote == APPLICATION['quote']
        assert candidate.evidence[0].digest == episode.digest
        assert for_briefing(proposals, episodes)['items'][0]['review_required'] is True
        decision = pruefen(candidate, episode, eigene=(), jetzt=at, zeitstatus='recent',
            aus_bestand=False, dublette=False, zurueckgenommen=False)
        assert decision.eindeutig is False and decision.kuerzel == 'ungeprueft'
        assert frist_aus(candidate.evidence[0].quote, at) is None
        assert detector.run(with_model=True).proposed == 0
        assert len(proposals.pending(ProposalKind.TASK)) == 1
        if change == 'ignore':
            episodes.ignore(episode.id)
        else:
            replacement = episodes.record(EpisodeKind.MESSAGE, episode.title, 'Der Antrag ist abgesagt.',
                episode.provenance, source_key='synthetic:sirius')[0]
            episodes.advance_source_head('synthetic:sirius', episode.id, replacement.id)
        assert for_briefing(proposals, episodes)['items'] == []
        assert detector.expire_sources() == 1
    finally:
        proposals.close()
        episodes.close()
