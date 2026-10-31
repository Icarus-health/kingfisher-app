"""Widersprechender Judge darf eine eng belegte eigene Zusage nur zur Prüfung erhalten."""
import json
from datetime import datetime, timezone
from threading import RLock

import pytest

from icarus_memory.aufgaben_von_selbst import pruefen
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalStore
from icarus_memory.providers import Reply
from icarus_memory.task_detection import TaskDetector, for_briefing
from icarus_memory.task_review import REVIEW_MARKER, review_tasks


# Wortlaut aus dem öffentlichen synthetischen FINAL-I-Lauf, keine persönlichen Daten.
PROMISE = 'Ich werde dir die Kalkulation für Projekt Ceder bis zum 3. November 2026 um 15:30 Uhr senden.'
ITEM = {'title': 'Kalkulation für Projekt Ceder senden', 'quote': PROMISE}
CONTACTS = [{'rolle': 'von', 'adresse': 'lea@example.test', 'ich': True},
            {'rolle': 'an', 'adresse': 'nora@example.test', 'ich': False}]


class SavedReplies:
    is_local = True
    name = 'synthetic'
    model = 'saved-own-promise'

    def __init__(self, item=ITEM, *, kind='information', supported=False):
        self.item, self.kind, self.supported = item, kind, supported
        self.review_hook = lambda: None

    def complete_json(self, messages, **kwargs):
        payload = json.loads(messages[1]['content'])
        if 'candidates' in payload:
            self.review_hook()
            return Reply(text=json.dumps({'reviews': [
                {'id': 0, 'kind': self.kind, 'title_supported': self.supported}]}))
        return Reply(text=json.dumps({'items': [self.item]}))


@pytest.fixture
def memory(tmp_path):
    episodes, proposals = EpisodeStore(tmp_path / 'episodes.sqlite3'), ProposalStore(tmp_path / 'proposals.sqlite3')
    yield episodes, proposals
    episodes.close()
    proposals.close()


def source(episodes, body=PROMISE + '\n', *, contacts=None, title='Eigene Zusage'):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, title, body, Provenance(SourceType.EMAIL),
        contacts=CONTACTS if contacts is None else contacts, occurred_at=datetime.now(timezone.utc),
        source_key='synthetic:own-promise')
    episodes.advance_source_head('synthetic:own-promise', None, episode.id)
    return episode


def test_final_i_own_promise_is_retained_only_as_manual_original_evidence(memory):
    episodes, proposals = memory
    episode = source(episodes)
    report = TaskDetector(episodes, proposals, SavedReplies(), RLock()).run(with_model=True)
    assert (report.analyzed, report.proposed, report.failed) == (1, 1, 0)
    [candidate] = proposals.pending(ProposalKind.TASK)
    assert candidate.statement == PROMISE
    assert candidate.evidence[0].quote == PROMISE and candidate.evidence[0].digest == episode.digest
    assert REVIEW_MARKER not in candidate.proposed_by
    assert for_briefing(proposals, episodes)['items'][0]['review_required'] is True
    decision = pruefen(candidate, episodes.get(episode.id), eigene=['lea@example.test'],
        jetzt=datetime.now(timezone.utc), zeitstatus='recent', aus_bestand=False,
        dublette=False, zurueckgenommen=False)
    assert decision.eindeutig is False and decision.kuerzel == 'ungeprueft'
    assert episodes.get(episode.id).body == PROMISE + '\n'


@pytest.mark.parametrize('body', [
    'Ich werde dir die Kalkulation nicht senden.',
    'Ich werde dir die Kalkulation nie senden.',
    'Ich werde dir die Kalkulation niemals senden.',
    'Ich werde dir weder die Kalkulation noch die Unterlagen senden.',
    'Ich werde dir die Kalkulation weder senden noch schicken.',
    'Ich werde dir keine Kalkulation senden.',
    'Ich werde dir die Kalkulation nur nach Freigabe senden.',
    'Wenn du zustimmst, werde ich dir die Kalkulation senden.',
    'Ich werde dir die Kalkulation vielleicht senden.',
    'Ich werde dir die Kalkulation nach der Prüfung senden.',
    'Ich werde dir die Kalkulation bei Zustimmung senden.',
    'Ich werde dir die Kalkulation und Nora wird die Unterlagen senden.',
    'Ich werde dir die Kalkulation senden bevor Nora die Unterlagen liefern.',
    'Ich werde die Angabe er werde senden schicken.',
    'Ich werde dir die Kalkulation von Nora senden.',
    'Ich werde dir die Kalkulation laut Nora senden.',
    'Ich werde dir die von Nora zugesagte Kalkulation senden.',
    'Ich werde dir die Kalkulation, die Nora zugesagt hat, senden.',
    'Ich werde dir die Zusage für Projekt Beispiel senden.',
    'Nora sagt: ' + PROMISE,
    '> ' + PROMISE,
    '„' + PROMISE + '“',
    'Weitergeleitete Nachricht\n' + PROMISE,
    PROMISE + ' Das ist meine Zusage.',
    PROMISE + '\nViele Grüße\nLea',
    'Hallo Nora,\n' + PROMISE,
    PROMISE + '\nVon: Nora\nGesendet: 30.10.2026\nAn: Lea\nBetreff: Alt',
])
def test_qualifiers_reports_quotes_or_additional_text_never_gain_retention(memory, body):
    episodes, proposals = memory
    episode = source(episodes, body)
    item = {'title': body, 'quote': body}
    assert review_tasks(SavedReplies(item), 'Eigene Zusage', body, [item],
                        own_source=True, episode=episode) == []


@pytest.mark.parametrize('contacts', [[],
    [{'rolle': 'von', 'adresse': 'other@example.test', 'ich': False}],
    [{'rolle': 'von', 'ich': True}],
    CONTACTS + [{'rolle': 'von', 'adresse': 'other@example.test', 'ich': False}],
])
def test_own_flag_without_unique_structured_own_mail_sender_cannot_retain(memory, contacts):
    episodes, _ = memory
    episode = source(episodes, contacts=contacts)
    assert review_tasks(SavedReplies(), 'Eigene Zusage', episode.body, [ITEM],
                        own_source=True, episode=episode) == []


def test_no_episode_or_non_own_flag_cannot_gain_retention(memory):
    assert review_tasks(SavedReplies(), 'Eigene Zusage', PROMISE, [ITEM], own_source=True) == []
    episodes, _ = memory
    episode = source(episodes)
    assert review_tasks(SavedReplies(), 'Eigene Zusage', episode.body, [ITEM],
                        own_source=False, episode=episode) == []


def test_forward_subject_does_not_gain_retention(memory):
    episodes, _ = memory
    episode = source(episodes, title='WG: Alte Zusage')
    assert review_tasks(SavedReplies(), episode.title, episode.body, [ITEM],
                        own_source=True, episode=episode) == []


@pytest.mark.parametrize('subject', ['Absage meiner Zusage', 'Meine Zusage widerrufen',
                                    'Versand storniert', 'Zusage zurückgezogen'])
def test_withdrawing_subject_cannot_be_lost_when_positive_body_is_retained(memory, subject):
    episodes, _ = memory
    episode = source(episodes, title=subject)
    assert review_tasks(SavedReplies(), subject, episode.body, [ITEM],
                        own_source=True, episode=episode) == []


def test_caller_cannot_hide_original_forward_subject_for_retention(memory):
    episodes, _ = memory
    episode = source(episodes, title='WG: Alte Zusage')
    assert review_tasks(SavedReplies(), 'Eigene Zusage', episode.body, [ITEM],
                        own_source=True, episode=episode) == []


@pytest.mark.parametrize('change', ['ignore', 'contacts', 'replace'])
def test_retained_candidate_cannot_survive_source_change_during_review(memory, change):
    episodes, proposals = memory
    episode = source(episodes)
    provider = SavedReplies()
    def alter():
        if change == 'ignore':
            episodes.ignore(episode.id)
        elif change == 'contacts':
            episodes.add_contacts(episode.id, [{'rolle': 'cc', 'adresse': 'third@example.test'}])
        else:
            replacement, _ = episodes.record(EpisodeKind.MESSAGE, episode.title, 'Die Zusage ist widerrufen.',
                episode.provenance, source_key='synthetic:own-promise')
            episodes.advance_source_head('synthetic:own-promise', episode.id, replacement.id)
    provider.review_hook = alter
    TaskDetector(episodes, proposals, provider, RLock()).run(with_model=True)
    assert proposals.pending(ProposalKind.TASK) == []


def test_positive_judge_keeps_existing_supported_title_and_review_marker(memory):
    episodes, proposals = memory
    source(episodes)
    provider = SavedReplies(kind='own_commitment', supported=True)
    assert TaskDetector(episodes, proposals, provider, RLock()).run(with_model=True).proposed == 1
    [candidate] = proposals.pending(ProposalKind.TASK)
    assert candidate.statement == ITEM['title'] and candidate.proposed_by.endswith(REVIEW_MARKER)
