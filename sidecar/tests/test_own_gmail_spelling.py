"""Eigene Gmail-Schreibweisen; fremde Kontaktanker bleiben wörtlich."""
from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from types import SimpleNamespace

import pytest

from icarus_memory import identitaet, kontakte, mail_ingestion, personen
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import eigene_mail
from icarus_memory.task_review import current_task_context
from icarus_memory.fristlage import richtung
from icarus_memory.aufgaben_von_selbst import beteiligte
from icarus_memory.proposals import ProposalStore, ProposalKind
from icarus_memory.task_detection import TaskDetector
from .test_own_promise_retention import SavedReplies


NOW = datetime(2026, 10, 31, 10, tzinfo=timezone.utc)


def message(sender='lea.hartmann@gmail.com', own=('leahartmann@gmail.com',)):
    return Message(uid='11.50', subject='Unterlagen', sender=f'Lea Hartmann <{sender}>',
                   date=NOW, body='Ich schicke die Unterlagen morgen.', preview='', unread=False,
                   account_id='a', message_id='<50@synthetic.example>', own_addresses=own)


@pytest.mark.parametrize('sender,own', [
    ('lea.hartmann@gmail.com', 'leahartmann@gmail.com'),
    ('leahartmann@gmail.com', 'lea.hartmann@gmail.com'),
    ('L.E.A.Hartmann@GMAIL.COM', 'lea.hartmann@gmail.com'),
])
def test_verified_own_gmail_spelling_is_self(sender, own):
    row = kontakte.kontakt(f'Lea Hartmann <{sender}>', 'von', eigene=(own,))
    assert row['ich'] is True
    assert row['adresse'] == sender.casefold()
    assert eigene_mail(message(sender, (own,))) is True


@pytest.mark.parametrize('sender,own', [
    ('lea.hartmann@work.example', 'leahartmann@work.example'),
    ('lea.hartmann@gmail.com.evil.example', 'leahartmann@gmail.com'),
    ('lea.hartmann2@gmail.com', 'leahartmann@gmail.com'),
    ('lea.hartmann@gmail.com', 'leahartmann@other.example'),
    ('lea.hartmann+news@gmail.com', 'leahartmann@gmail.com'),
])
def test_other_addresses_do_not_become_self(sender, own):
    assert kontakte.kontakt(sender, 'von', eigene=(own,))['ich'] is False
    assert eigene_mail(message(sender, (own,))) is False


def test_old_contact_projection_uses_current_verified_own_address_without_rewriting():
    document = {'provenance': {'source_type': 'email'},
                'contacts': [{'name': 'Lea Hartmann', 'adresse': 'lea.hartmann@gmail.com',
                              'rolle': 'von', 'ich': False}], 'participants': []}
    assert identitaet.nennungen(document, eigene=['leahartmann@gmail.com'])[0].ich is True
    assert document['contacts'][0]['ich'] is False


def test_deadline_direction_uses_same_own_gmail_rule():
    assert richtung(['Lea <lea.hartmann@gmail.com>'], ['leahartmann@gmail.com']) == 'von_mir'
    assert richtung(['Lea <lea.hartmann@work.example>'], ['leahartmann@work.example']) == 'an_mich'


@pytest.mark.parametrize('contacts', [[], [
    {'name': 'Lea', 'adresse': 'lea.hartmann@gmail.com', 'rolle': 'von', 'ich': False},
]])
def test_task_direction_uses_same_own_gmail_rule(contacts):
    source = SimpleNamespace(contacts=contacts, participants=['Lea <lea.hartmann@gmail.com>'])
    assert beteiligte(source, ['leahartmann@gmail.com']).von_mir is True


@pytest.mark.parametrize('sender,expected', [('lea.hartmann@gmail.com', 1), ('anna.hartmann@gmail.com', 0)])
def test_mail_to_task_review_keeps_own_source_binding(tmp_path, sender, expected):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        mail = message(sender)
        mail_ingestion.remember(store, mail)
        provider = SavedReplies({'title': mail.body, 'quote': mail.body}, kind='own_commitment', supported=True)
        report = TaskDetector(store, proposals, provider, RLock()).run(with_model=True)
        assert report.failed == 0 and report.proposed == expected
        assert len(proposals.pending(ProposalKind.TASK)) == expected
    finally:
        proposals.close()
        store.close()


def test_foreign_gmail_addresses_keep_separate_person_anchors(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        mail_ingestion.remember(store, message('anna.keller@gmail.com', ()))
        mail_ingestion.remember(store, replace(message('annakeller@gmail.com', ()),
                                               uid='11.51', message_id='<51@synthetic.example>'))
        found = personen.alle(episodes=store, eigene=['leahartmann@gmail.com'], jetzt=NOW)
        assert {p.id for p in found} == {'a:anna.keller@gmail.com', 'a:annakeller@gmail.com'}
    finally:
        store.close()


def test_full_refresh_promotes_derived_self_flag_without_duplicate_or_original_change(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        old = mail_ingestion.remember(store, message(own=()))['episode']
        old_context = current_task_context(store, old['id'])
        assert old['contacts'][0]['ich'] is False
        observed = mail_ingestion.remember(store, message())
        current = store.get(old['id'])
        assert observed['episode']['id'] == old['id']
        assert observed['new'] is False
        assert current.contacts[0]['ich'] is True
        assert current_task_context(store, current.id) != old_context
        for field in ('body', 'digest', 'title', 'occurred_at', 'recorded_at', 'provenance'):
            assert current.to_dict()[field] == old[field]
        fresh_context = current_task_context(store, current.id)
        assert mail_ingestion.remember(store, message())['episode']['id'] == current.id
        assert current_task_context(store, current.id) == fresh_context
        assert sum(store.counts().values()) == 1
    finally:
        store.close()


@pytest.mark.parametrize("previous_truncated", [False, True])
def test_partial_refresh_does_not_promote_existing_contact_metadata(tmp_path, previous_truncated):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        old = mail_ingestion.remember(store, replace(message(own=()), truncated=previous_truncated))['episode']
        before = current_task_context(store, old['id'])
        mail_ingestion.remember(store, replace(message(), truncated=True))
        assert store.get(old['id']).contacts[0]['ich'] is False
        assert current_task_context(store, old['id']) == before
    finally:
        store.close()
