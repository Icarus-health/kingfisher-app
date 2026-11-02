"""Missing deadline evidence is uncertainty, not proof of archive-wide absence."""
import json
from contextlib import ExitStack, closing

import pytest

from icarus_memory import EpisodeStore
from icarus_memory.claims import ClaimStore
from icarus_memory.providers import Reply
from icarus_memory import working_memory_answers as answers
from icarus_memory.working_memory_store import WorkingMemoryStore
from .test_working_memory_store import source


@pytest.fixture
def memory(tmp_path):
    with ExitStack() as stack:
        episodes = stack.enter_context(closing(EpisodeStore(tmp_path / 'episodes.sqlite3')))
        claims = stack.enter_context(closing(ClaimStore(tmp_path / 'knowledge.sqlite3')))
        yield episodes, claims


class Selector:
    is_local = True

    def __init__(self, *, select=False):
        self.select = select

    def complete_json(self, messages, **kwargs):
        rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': 'source_reports' if self.select else 'no_relevant_sources',
                                      'ids': [row['id'] for row in rows] if self.select else []}))


def record(memory, text):
    episodes, _ = memory
    ep = source(episodes, text)
    assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(ep.id),
        [{'start': 0, 'end': len(text), 'kind': 'conditional'}], model='synthetic')
    return ep


def ask(memory, question, *, select=False, **kwargs):
    episodes, claims = memory
    result = answers.prepare(question, episodes, claims, Selector(select=select),
                             semantic_search=None, **kwargs)
    assert result is not None
    return result, answers.render(result, episodes, claims)


@pytest.mark.parametrize('question', [
    'Gibt es ein konkretes Rücksendedatum für den Erfassungsbogen?',
    'Bis wann muss ich den Erfassungsbogen zurücksenden?',
    'Welche Frist gilt für den Erfassungsbogen?',
    'What is the deadline for the Erfassungsbogen?',
])
def test_unknown_deadline_explains_unproven_date_without_claiming_absence(memory, question):
    record(memory, 'Bitte den Erfassungsbogen zurücksenden, sobald er vollständig ausgefüllt ist.')
    result, (text, links, status) = ask(memory, question)
    assert result['status'] == 'unknown' and status == 'working_unknown'
    assert 'erfragte Angabe' in text and 'nicht belegen' in text
    assert 'keine Information vor' not in text
    assert result['refs'] == [] and links == []  # Never promote an unselected candidate.


def test_pending_sources_keep_coverage_warning_with_scoped_deadline_explanation(memory):
    record(memory, 'Bitte den Erfassungsbogen zurücksenden, sobald er ausgefüllt ist.')
    source(memory[0], 'Der Erfassungsbogen liegt in einer noch nicht eingeordneten Nachricht.')
    _, (text, _, status) = ask(memory, 'Gibt es ein Rücksendedatum für den Erfassungsbogen?')
    assert status == 'working_unknown'
    assert 'erfragte Angabe' in text and 'nicht belegen' in text
    assert 'Belegabschnitt' in text and 'unvollständig' in text


def test_reported_condition_stays_a_condition_and_retains_original_link(memory):
    body = 'Bitte den Erfassungsbogen zurücksenden, sobald die Freigabe vorliegt.'
    ep = record(memory, body)
    result, (text, links, status) = ask(memory, 'Welche Frist gilt für den Erfassungsbogen?', select=True)
    assert status == 'working_reports'
    assert body in text and 'sobald die Freigabe vorliegt' in text
    assert [ref['episode_id'] for ref in result['refs']] == [ep.id]
    assert any(link['episode_id'] == ep.id for link in links)
    assert 'Fristdatum konnte ich' not in text  # No blanket absence claim on positive reports.


def test_source_withdrawal_invalidates_even_a_scoped_unknown_explanation(memory):
    ep = record(memory, 'Bitte den Erfassungsbogen zurücksenden, sobald er ausgefüllt ist.')
    result, _ = ask(memory, 'Gibt es ein Rücksendedatum für den Erfassungsbogen?')
    memory[0].ignore(ep.id)
    text, links, status = answers.render(result, *memory)
    assert status == 'working_unavailable' and links == []
    assert 'Fristdatum' not in text


@pytest.mark.parametrize('question', [
    'Wo liegt der Erfassungsbogen?',
    'Welcher Beschäftigungsbeginn steht im Erfassungsbogen?',
    'Wer hat die Frist für den Erfassungsbogen festgelegt?',
    'Who set the deadline for the Erfassungsbogen?',
    'Warum wurde die Abgabefrist für den Erfassungsbogen verlängert?',
    'Wie lang ist die Rücksendefrist für den Erfassungsbogen?',
    'Kannst du sagen, wer die Deadline für den Erfassungsbogen festgelegt hat?',
    'Bis wann kann ich zum Erfassungsbogen anrufen?',
])
def test_other_missing_fields_do_not_become_deadline_questions(memory, question):
    record(memory, 'Der Erfassungsbogen wird nach Freigabe zurückgegeben.')
    _, (text, _, status) = ask(memory, question)
    assert status == 'working_unknown'
    assert 'Fristdatum' not in text and 'erfragte Angabe' in text


def test_other_date_field_does_not_become_an_invented_deadline(memory):
    record(memory, 'Erfassungsbogen: Beschäftigungsbeginn 09.12.2026; Rücksendung nach Freigabe.')
    _, (text, links, status) = ask(memory, 'Gibt es ein Rücksendedatum für den Erfassungsbogen?')
    assert status == 'working_unknown'
    assert 'erfragte Angabe' in text and '09.12.2026' not in text and links == []
