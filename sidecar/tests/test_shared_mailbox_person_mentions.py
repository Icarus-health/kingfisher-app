"""A literal person mention does not establish who owns a shared mailbox."""
import json
from contextlib import closing

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.identitaet import Verzeichnis
from icarus_memory.memory_categories import Categories
from icarus_memory.providers import Reply
from tests.test_person_pronoun_candidates import CandidateModel


def message(episodes, name, mailbox='auftragsplanung'):
    return episodes.record(
        EpisodeKind.MESSAGE, 'Synthetic shared mailbox', f'{name} prüft den Termin.',
        Provenance(SourceType.EMAIL, source_ref='synthetic-shared-mailbox'),
        participants=[f'{name} <{mailbox}@firma.example>'],
    )[0]


@pytest.mark.parametrize('mode', ['absolute', 'block_quote'])
@pytest.mark.parametrize('mailbox', ['auftragsplanung', 'auftragsabwicklung', 'info'])
@pytest.mark.parametrize('name', ['Anna Beispiel', 'Jörg Kranz'])
def test_literal_human_display_name_remains_only_a_body_mention(tmp_path, mode, mailbox, name):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        item = message(episodes, name, mailbox)
        original = item.to_dict()
        categories = Categories(episodes)

        assert categories.run(CandidateModel([name], mode), source_ids=[item.id]).ok

        entities = categories.list_for(item.id)['entities']
        assert [(entity['name'], entity['role'], entity['quote']) for entity in entities] == [
            (name, 'mentioned', name),
        ]
        assert [entry['name'] for entry in categories.person_mentions()['items']] == [name]
        assert Verzeichnis.aus([item]).adressen_zum_namen(name) == []
        assert episodes.get(item.id).to_dict() == original


@pytest.mark.parametrize('name', [
    'Auftragsplanung', 'Auftrags Planung', 'Kunden Service', 'Acme Team', 'Acme Service',
    'Beispiel GmbH', 'Acme & Co', 'Ihre',
])
def test_service_company_and_pronoun_display_labels_stay_filtered(tmp_path, name):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        item = message(episodes, name)
        categories = Categories(episodes)

        assert categories.run(CandidateModel([name]), source_ids=[item.id]).ok

        assert categories.list_for(item.id)['entities'] == []
        assert categories.person_mentions()['items'] == []


def test_saved_shared_mailbox_sender_span_reopens_only_as_a_body_mention(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    with closing(EpisodeStore(path)) as episodes:
        item = message(episodes, 'Anna Beispiel')
        original = item.to_dict()
        categories = Categories(episodes)
        assert categories.run(CandidateModel(['Anna Beispiel']), source_ids=[item.id]).ok
        with episodes.transaction():
            episodes._conn.execute(
                "UPDATE memory_category_entities SET role='sender' WHERE episode_id=?", (item.id,),
            )

    with closing(EpisodeStore(path)) as reopened:
        categories = Categories(reopened)
        assert [(entity['name'], entity['role']) for entity in categories.list_for(item.id)['entities']] == [
            ('Anna Beispiel', 'mentioned'),
        ]
        assert categories.person_mentions()['items'][0]['role'] == 'mentioned'
        assert reopened._conn.execute(
            'SELECT role FROM memory_category_entities WHERE episode_id=?', (item.id,),
        ).fetchone()[0] == 'sender'
        assert reopened.get(item.id).to_dict() == original


def test_shared_mailbox_human_display_name_cannot_claim_sender_role(tmp_path):
    class ClaimedSender(CandidateModel):
        def complete_json(self, messages, **kwargs):
            result = json.loads(super().complete_json(messages, **kwargs).text)
            result['entities'][0]['role'] = 'sender'
            return Reply(text=json.dumps(result))

    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        item = message(episodes, 'Anna Beispiel')
        categories = Categories(episodes)

        assert not categories.run(ClaimedSender(['Anna Beispiel'], 'absolute'), source_ids=[item.id]).ok

        assert categories.list_for(item.id)['entities'] == []
