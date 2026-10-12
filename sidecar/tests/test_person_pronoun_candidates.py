"""Model-quoted function words must not create person hints or erase originals."""
import json
from contextlib import closing

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.memory_categories import Categories, _interpret
from icarus_memory.providers import Reply


class CandidateModel:
    is_local = True
    name = model = 'synthetic-person-candidates'

    def __init__(self, names, mode='block_quote', kinds=None):
        self.names, self.entity_anchor_mode = names, mode
        self.kinds = kinds or {}

    def complete_json(self, messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        block = payload['blocks'][0]
        items = []
        for name in self.names:
            item = {'kind': self.kinds.get(name, 'person'), 'name': name, 'role': 'mentioned'}
            if self.entity_anchor_mode == 'block_quote':
                item['block_id'] = block['block_id']
            else:
                item['start'] = block['start'] + block['text'].index(name)
                item['end'] = item['start'] + len(name)
            items.append(item)
        return Reply(text=json.dumps({'categories': [{'category_id': 'work', 'block_id': block['block_id']}], 'entities': items}))


def source(episodes, body, participants=()):
    return episodes.record(EpisodeKind.MESSAGE, 'Synthetic person candidates', body,
                           Provenance(SourceType.EMAIL), participants=list(participants))[0]


@pytest.mark.parametrize('mode', ['block_quote', 'absolute'])
@pytest.mark.parametrize('word', ['Ihre', 'Sie', 'Ihnen', 'Wir', 'Ich', 'Du', 'Er', 'Ihrer', 'Sich'])
def test_standalone_pronouns_are_not_people_and_other_evidence_survives(tmp_path, mode, word):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, f'{word} prüfen den Entwurf. Anna Kranz liefert die Unterlagen.')
        original = item.to_dict()
        cats = Categories(episodes)
        assert cats.run(CandidateModel([word, 'Anna Kranz'], mode), source_ids=[item.id]).ok
        result = cats.list_for(item.id)
        assert [e['name'] for e in result['entities']] == ['Anna Kranz']
        assert [c['id'] for c in result['categories']] == ['work']
        assert [m['name'] for m in cats.person_mentions()['items']] == ['Anna Kranz']
        assert episodes.get(item.id).to_dict() == original


def test_preexisting_pronoun_span_is_hidden_after_reopen_without_deleting_saved_evidence(tmp_path):
    path = tmp_path/'episodes.sqlite3'
    with closing(EpisodeStore(path)) as episodes:
        item = source(episodes, 'Ihre Buchung bestätigt Anna Kranz.')
        cats = Categories(episodes)
        assert cats.run(CandidateModel(['Anna Kranz']), source_ids=[item.id]).ok
        fingerprint = episodes._conn.execute('SELECT fingerprint FROM memory_category_sources WHERE episode_id=?', (item.id,)).fetchone()[0]
        with episodes.transaction():
            episodes._conn.execute('INSERT INTO memory_category_entities VALUES(?,?,?,?,?,?)', (item.id, fingerprint, 'person', 0, 4, 'mentioned'))
        original = item.to_dict()
    with closing(EpisodeStore(path)) as reopened:
        cats = Categories(reopened)
        assert [e['name'] for e in cats.list_for(item.id)['entities']] == ['Anna Kranz']
        assert [m['name'] for m in cats.person_mentions()['items']] == ['Anna Kranz']
        assert reopened._conn.execute('SELECT COUNT(*) FROM memory_category_entities WHERE episode_id=?', (item.id,)).fetchone()[0] == 2
        assert reopened.get(item.id).to_dict() == original


@pytest.mark.parametrize('name', ['Siebert', 'Anne Sie', 'Alex', 'Lê', 'Ihre AG'])
def test_complete_names_short_names_and_non_person_entities_are_not_blacklisted(tmp_path, name):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, f'{name} liefert die Unterlagen.')
        model = CandidateModel([name], kinds={name: 'organization'} if name == 'Ihre AG' else {})
        cats = Categories(episodes)
        assert cats.run(model, source_ids=[item.id]).ok
        assert [e['name'] for e in cats.list_for(item.id)['entities']] == [name]


@pytest.mark.parametrize('mode', ['block_quote', 'absolute'])
def test_rare_single_name_with_explicit_non_generic_mail_anchor_is_retained(tmp_path, mode):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, 'Sie liefert die Unterlagen.', ['Sie <sie@example.test>'])
        cats = Categories(episodes)
        assert cats.run(CandidateModel(['Sie'], mode), source_ids=[item.id]).ok
        assert [e['name'] for e in cats.list_for(item.id)['entities']] == ['Sie']


def test_generic_mailbox_does_not_turn_a_pronoun_display_name_into_a_person(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, 'Ihre Buchung ist eingegangen.', ['Ihre <info@example.test>'])
        cats = Categories(episodes)
        assert cats.run(CandidateModel(['Ihre']), source_ids=[item.id]).ok
        assert cats.list_for(item.id)['entities'] == []


def test_explicit_recipient_name_is_preserved_without_sender_role_or_identity_inference(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = episodes.record(EpisodeKind.MESSAGE, 'Synthetic addressed name', 'Sie liefert die Unterlagen.', Provenance(SourceType.EMAIL), contacts=[{'rolle':'von','name':'Anna Kranz','adresse':'anna@example.test'}, {'rolle':'an','name':'Sie','adresse':'sie@example.test'}])[0]
        cats = Categories(episodes)
        assert cats.run(CandidateModel(['Sie']), source_ids=[item.id]).ok
        assert [(e['name'], e['role']) for e in cats.list_for(item.id)['entities']] == [('Sie', 'mentioned')]


@pytest.mark.parametrize('body', ['Zitat: Von: Sie <sie@example.test> bestätigt.', 'Sie <sie@example.test> liefert die Unterlagen.'])
def test_raw_or_quoted_body_address_does_not_create_contact_exception(tmp_path, body):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, body)
        cats = Categories(episodes)
        assert cats.run(CandidateModel(['Sie']), source_ids=[item.id]).ok
        assert cats.list_for(item.id)['entities'] == []


def test_mailbox_without_valid_address_does_not_create_name_exception(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, 'Sie liefert die Unterlagen.', ['Sie <invalid>'])
        cats = Categories(episodes)
        assert cats.run(CandidateModel(['Sie']), source_ids=[item.id]).ok
        assert cats.list_for(item.id)['entities'] == []


def test_explicitly_permitted_remote_quote_path_uses_same_filter_without_network(tmp_path):
    from types import SimpleNamespace
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        item = source(episodes, 'Ihre Buchung bestätigt Anna Kranz.')
        model = CandidateModel(['Ihre', 'Anna Kranz']);model.is_local = False
        policy = SimpleNamespace(permits=lambda provider, episode: True)
        topics, entities = _interpret(model, item, Categories(episodes).taxonomy()['items'], policy)
        assert [item.body[start:end] for kind, start, end, role in entities] == ['Anna Kranz']
        assert [topic[0] for topic in topics] == ['work']
