"""Nur synthetische Relays: Quellenkontext ergänzen, Originalbelege und Freigaben bewahren."""
import json
from datetime import datetime, timezone
from threading import RLock

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.memory_analysis import interpret
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalStore
from icarus_memory.providers import ProviderError, Reply
from icarus_memory.task_detection import TaskDetector


QUOTE = '> Aufgrund der Nachfrage bitten wir vorab um &Uuml;bersendung Ihrer\r\n> Selbstauskunft.'
BODY = ('Neue Nachricht über ein Portal.\r\n\r\n> Sehr geehrte Damen und Herren,\r\n'
        '> Die Wohnung ist ab 01.01.2027 frei.\r\n' + QUOTE + '\r\n> Freundliche Gr&uuml;&szlig;e')
CONTACTS = [
    {'rolle': 'von', 'adresse': 'relay@notifications.example.test', 'name': 'Anna Beispiel'},
    {'rolle': 'an', 'adresse': 'owner@example.test', 'name': 'Bo Beispiel', 'ich': True},
]


class Reader:
    is_local = True
    name = 'offline'
    model = 'source-context'

    def __init__(self, *, items=None, verdict='request_to_recipient'):
        self.payloads = []
        self.items = [] if items is None else items
        self.verdict = verdict

    def complete_json(self, messages, **kwargs):
        payload = json.loads(messages[1]['content'])
        self.payloads.append(payload)
        if 'candidates' in payload:
            return Reply(text=json.dumps({'reviews': [
                {'id': row['id'], 'kind': self.verdict, 'title_supported': True}
                for row in payload['candidates']]}))
        return Reply(text=json.dumps({'items': self.items}))


@pytest.fixture
def stores(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    yield episodes, proposals
    episodes.close()
    proposals.close()


@pytest.mark.parametrize('occurred', [datetime(2026, 10, 31, 9, tzinfo=timezone.utc), None])
def test_detector_adds_bounded_metadata_without_replacing_unknown_source_time(stores, occurred):
    episodes, proposals = stores
    captured = datetime(2026, 10, 31, 10, tzinfo=timezone.utc)
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, 'Neue Nachricht', BODY,
        Provenance(SourceType.EMAIL, source_ref='private-account:synthetic', captured_at=captured,
                   verbatim='PRIVATE_DUPLICATE_BODY'),
        occurred_at=occurred, contacts=CONTACTS,
        participants=['Anna Beispiel <relay@notifications.example.test>', 'Bo Beispiel <owner@example.test>'])
    reader = Reader()
    result = TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True, limit=1)
    assert result.analyzed == 1 and result.failed == 0
    payload = reader.payloads[0]
    assert payload['body'] == BODY and payload['subject'] == 'Neue Nachricht'
    # Der Store serialisiert Zeiten in der Nutzerzeitzone; der Extraktor muss
    # genau die frisch gelesene Fassung bekommen, ohne Erfassungszeit als Ersatz.
    fresh = episodes.get(episode.id)
    assert payload['source_context'] == {
        'kind': 'message', 'source_type': 'email',
        'occurred_at': fresh.occurred_at.isoformat() if occurred else None,
        'recorded_at': fresh.recorded_at.isoformat(), 'captured_at': '2026-10-31T10:00:00+00:00',
        'participants': ['Anna Beispiel <relay@notifications.example.test>', 'Bo Beispiel <owner@example.test>'],
        'email_sender': 'Anna Beispiel <relay@notifications.example.test>', 'contacts': CONTACTS,
    }
    if occurred:
        assert datetime.fromisoformat(payload['source_context']['occurred_at']) == occurred
    assert 'PRIVATE_DUPLICATE_BODY' not in json.dumps(payload)
    assert 'private-account' not in json.dumps(payload)


def test_direct_extraction_without_context_keeps_existing_payload():
    reader = Reader()
    assert interpret(reader, 'Betreff', BODY) == []
    assert reader.payloads == [{'subject': 'Betreff', 'body': BODY}]


def test_optional_context_is_read_only_and_keeps_raw_quote():
    context = {'kind': 'message', 'occurred_at': None, 'participants': ['Bo Beispiel']}
    reader = Reader(items=[{'title': 'Selbstauskunft übersenden', 'quote': QUOTE}])
    result = interpret(reader, 'Neue Nachricht', BODY, source_context=context)
    assert result == [{'title': 'Selbstauskunft übersenden', 'quote': QUOTE}]
    assert reader.payloads[0]['body'] == BODY
    assert reader.payloads[0]['source_context'] == context
    assert context == {'kind': 'message', 'occurred_at': None, 'participants': ['Bo Beispiel']}


@pytest.mark.parametrize('context', [{'participants': ['x' * 4001]}, {'kind': object()}, []])
def test_invalid_or_oversized_metadata_fails_before_model_call(context):
    reader = Reader()
    with pytest.raises(ProviderError):
        interpret(reader, 'Betreff', BODY, source_context=context)
    assert reader.payloads == []


@pytest.mark.parametrize('verdict', ['unclear', 'other_person', 'marketing'])
@pytest.mark.parametrize('model_quote', [
    QUOTE, 'Aufgrund der Nachfrage bitten wir vorab um Übersendung Ihrer Selbstauskunft.',
])
def test_relay_metadata_does_not_bypass_conservative_task_review(stores, verdict, model_quote):
    episodes, proposals = stores
    episodes.record(EpisodeKind.MESSAGE, 'Neue Nachricht', BODY, Provenance(SourceType.EMAIL),
                    contacts=CONTACTS, occurred_at=datetime(2026, 10, 31, 9, tzinfo=timezone.utc))
    reader = Reader(items=[{'title': 'Selbstauskunft übersenden', 'quote': model_quote}], verdict=verdict)
    result = TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True, limit=1)
    assert result.analyzed == 1 and result.proposed == 0 and result.failed == 0
    assert proposals.pending(ProposalKind.TASK) == []


@pytest.mark.parametrize('model_quote,raw_quote', [
    (QUOTE, QUOTE),
    ('Aufgrund der Nachfrage bitten wir vorab um Übersendung Ihrer Selbstauskunft.', QUOTE[2:]),
])
def test_positive_review_keeps_original_relay_evidence(stores, model_quote, raw_quote):
    episodes, proposals = stores
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Neue Nachricht', BODY, Provenance(SourceType.EMAIL),
                                 contacts=CONTACTS, occurred_at=datetime(2026, 10, 31, 9, tzinfo=timezone.utc))
    reader = Reader(items=[{'title': 'Selbstauskunft übersenden', 'quote': model_quote}])
    result = TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True, limit=1)
    assert result.proposed == 1 and result.failed == 0
    evidence = proposals.pending(ProposalKind.TASK)[0].evidence[0]
    assert evidence.quote == raw_quote and evidence.digest == episode.digest
    assert reader.payloads[1]['candidates'][0]['quote'] == raw_quote
    assert reader.payloads[1]['body'] == BODY
    assert episodes.get(episode.id).body == BODY
