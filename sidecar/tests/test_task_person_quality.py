"""Personenvorauswahl: technische Absender und ausdrückliche Alternativen bleiben offen."""
from datetime import datetime, timezone
from email.utils import formataddr
from threading import RLock

import pytest

from icarus_memory.aufgaben_von_selbst import Durchlauf, person_der_quelle
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.graph import GraphNode
from icarus_memory.model import Provenance, SourceType
from icarus_memory.people_quality import annotate_people
from icarus_memory.proposals import ProposalKind, ProposalStore
from icarus_memory.task_candidates import TaskCandidates
from icarus_memory.task_review import current_task_context
from icarus_memory.tasks import TaskStore


OWN = 'owner@example.test'
BODY = 'Bitte senden Sie uns Ihre Selbstauskunft.'


@pytest.fixture
def stores(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    yield episodes, proposals, tasks
    for store in (episodes, proposals, tasks):
        store.close()


def source(stores, name, address):
    episodes, proposals, _ = stores
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Neue Nachricht', BODY,
        Provenance(SourceType.EMAIL), occurred_at=datetime.now(timezone.utc),
        participants=[formataddr((name, address)), 'Owner <owner@example.test>'],
        contacts=[{'rolle': 'von', 'adresse': address, 'name': name},
                  {'rolle': 'an', 'adresse': OWN, 'name': 'Owner', 'ich': True}])
    with proposals.transaction():
        proposals._record_task_candidates(episode.id, episode.digest,
            [{'title': 'Selbstauskunft senden', 'quote': BODY}], proposed_by='synthetic/task-review-v1',
            task_context=current_task_context(episodes, episode.id))
    return episode, proposals.pending(ProposalKind.TASK)[0]


@pytest.mark.parametrize('name,address', [
    ('Anna, Beate oder Chris Beispiel', 'anbieter.random@nachrichten.portal.example'),
    ('Anna oder Beate Beispiel', 'anbieter.random@nachrichten.portal.example'),
    ('Anna or Beate Example', 'sender@example.test'),
    ('Anna Beispiel', 'pay@example.test'),
    ('Anna Beispiel', 'campaign-updates@example.test'),
    ('Anna Beispiel', 'service@example.test'),
    ('Firma GmbH', 'kontaktperson@example.test'),
    ('example.test', 'kontaktperson@example.test'),
    ('Unbekannter Absender', 'kontaktperson@example.test'),
])
def test_unresolved_sender_has_no_prefill_or_implicit_person_on_acceptance(stores, name, address):
    episodes, proposals, tasks = stores
    episode, proposal = source(stores, name, address)
    before = episodes.get(episode.id).to_dict()
    lock = RLock()
    run = Durchlauf(tasks, episodes, proposals, lock=lock, eigene=lambda: [OWN])
    assert person_der_quelle(episode, [OWN]) == ('bitte', None)
    assert run.vorbefuellt(proposal) == {'person_vorschlag': None, 'frist_vorschlag': None}
    task = TaskCandidates(episodes, proposals, tasks, None, lock).accept(
        proposal.id, title=proposal.statement, eigene=[OWN])
    assert task.person is None and task.due is None
    assert task.title == 'Selbstauskunft senden' and task.provenance.verbatim == BODY
    assert episodes.get(episode.id).to_dict() == before


@pytest.mark.parametrize('name', ['Keller, Anna', 'Anna Oder', 'Anna Or', 'Or, Anna',
                                  'Roderich Beispiel', 'Anne-Marie Kühn'])
def test_unambiguous_personal_names_remain_prefilled_and_accepted(stores, name):
    episodes, proposals, tasks = stores
    episode, proposal = source(stores, name, 'anna@example.test')
    expected = {'adresse': 'anna@example.test', 'name': name}
    assert person_der_quelle(episode, [OWN]) == ('bitte', expected)
    task = TaskCandidates(episodes, proposals, tasks, None, RLock()).accept(
        proposal.id, title=proposal.statement, eigene=[OWN])
    assert task.person == expected


def test_own_promise_keeps_its_unambiguous_recipient(stores):
    episodes, _, _ = stores
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Eigene Zusage', 'Ich sende dir die Unterlagen.',
        Provenance(SourceType.EMAIL), contacts=[
            {'rolle': 'von', 'adresse': OWN, 'name': 'Owner', 'ich': True},
            {'rolle': 'an', 'adresse': 'anna@example.test', 'name': 'Anna Oder'}])
    assert person_der_quelle(episode, [OWN]) == ('zusage', {'adresse': 'anna@example.test', 'name': 'Anna Oder'})


def test_explicit_user_person_selection_still_overrides_unresolved_sender(stores):
    episodes, proposals, tasks = stores
    _, proposal = source(stores, 'Anna oder Beate Beispiel', 'relay@example.test')
    selected = {'adresse': 'anna@example.test', 'name': 'Anna Beispiel'}
    task = TaskCandidates(episodes, proposals, tasks, None, RLock()).accept(
        proposal.id, title=proposal.statement, eigene=[OWN], person=selected)
    assert task.person == selected


def test_rfc_quoted_alternative_name_needs_review_but_confirmed_identity_has_priority():
    label = formataddr(('Anna, Beate oder Chris Beispiel', 'relay@example.test'))
    nodes = [GraphNode('a', 'person', label),
             GraphNode('b', 'person', label, {'identity_resolution': 'explicit_registry'})]
    before = [node.to_dict() for node in nodes]
    assert [node.attributes['quality_category'] for node in annotate_people(nodes)] == ['review', 'person']
    assert [node.to_dict() for node in nodes] == before
