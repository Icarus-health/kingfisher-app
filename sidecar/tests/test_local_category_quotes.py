"""Local entity extraction needs exact original quotations, not model-counted offsets."""
import json
from contextlib import closing

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.local_model_guard import VerifiedLocalProvider
from icarus_memory.memory_categories import Categories, _interpret
from icarus_memory.providers import OpenAICompatible, ProviderError, Reply


class LocalQuotes:
    is_local = True
    entity_anchor_mode = 'block_quote'
    name = model = 'synthetic-quote-model'

    def __init__(self, answer, on_call=lambda: None):
        self.answer, self.on_call, self.calls = answer, on_call, []

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]['content'])
        self.calls.append((payload, schema))
        self.on_call()
        return Reply(text=json.dumps(self.answer))


def original(episodes, text):
    return episodes.record(EpisodeKind.DOCUMENT, 'Synthetische Originalnotiz', text,
                           Provenance(SourceType.CHAT, source_ref='synthetic:local-quotes'))[0]


def entity(name, **extra):
    return {'kind': 'person', 'name': name, 'block_id': 'B1',
            'role': 'mentioned', **extra}


def result(*entities):
    return {'categories': [{'category_id': 'work', 'block_id': 'B1'}], 'entities': list(entities)}


def test_local_transport_selects_quote_anchors_and_guard_preserves_them():
    local = OpenAICompatible('installed-model', base_url='http://127.0.0.1:11434/v1')
    cloud = OpenAICompatible('remote-model')
    assert local.entity_anchor_mode == 'block_quote'
    assert VerifiedLocalProvider(local).entity_anchor_mode == 'block_quote'
    assert cloud.entity_anchor_mode == 'absolute'


def test_local_quote_extracts_unicode_name_with_code_resolved_offset(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, '🐦 Notiz: Lene Kühn prüft den Entwurf.')
        before = source.to_dict()
        provider = LocalQuotes(result(entity('Lene Kühn')))
        categories = Categories(episodes)
        assert categories.run(provider, source_ids=[source.id]).ok
        found = categories.list_for(source.id)['entities']
        assert [(x['name'], x['start'], x['end'], x['role']) for x in found] == [
            ('Lene Kühn', 9, 18, 'mentioned')]
        assert episodes.get(source.id).to_dict() == before
        payload, schema = provider.calls[0]
        assert 'start' not in payload['blocks'][0] and 'end' not in payload['blocks'][0]
        assert schema['properties']['entities']['items']['required'] == [
            'kind', 'name', 'block_id', 'role']


@pytest.mark.parametrize('bad', [entity('Erfundene Person'), entity('Lene Kühn', block_id='B2'),
                                entity('Lene Kühn', role='sender')])
def test_local_quotes_reject_missing_occurrence_or_invented_sender(tmp_path, bad):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, 'Lene Kühn prüft den Entwurf.')
        categories = Categories(episodes)
        assert not categories.run(LocalQuotes(result(bad)), source_ids=[source.id]).ok
        assert categories.list_for(source.id)['entities'] == []
        assert categories.list_for(source.id)['categories'] == []


def test_local_quotes_do_not_expand_existing_source_limit(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, 'a' * 12001)
        provider = LocalQuotes(result())
        categories = Categories(episodes)
        categories.run(provider, source_ids=[source.id])
        assert provider.calls == []
        assert categories.list_for(source.id)['status'] == 'deferred'


def test_local_quote_commit_still_checks_source_withdrawal(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, 'Lene Kühn prüft den Entwurf.')
        provider = LocalQuotes(result(entity('Lene Kühn')), on_call=lambda: episodes.ignore(source.id))
        categories = Categories(episodes)
        categories.run(provider, source_ids=[source.id])
        assert provider.calls
        assert categories.list_for(source.id)['entities'] == []


def test_remote_quote_mode_still_requires_explicit_source_permission(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, 'Lene Kühn prüft den Entwurf.')
        provider = LocalQuotes(result(entity('Lene Kühn')))
        provider.is_local = False
        with pytest.raises(ProviderError):
            _interpret(provider, source, Categories(episodes).taxonomy()['items'])
        assert provider.calls == []


def test_local_unique_quotes_preserve_two_distinct_people_without_counting_occurrences(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, 'Nachricht: Lene Kühn liefert, Leon Kühn prüft.')
        categories = Categories(episodes)
        provider = LocalQuotes(result(entity('Lene Kühn'), entity('Leon Kühn')))
        assert categories.run(provider, source_ids=[source.id]).ok
        assert [item['quote'] for item in categories.list_for(source.id)['entities']] == ['Lene Kühn', 'Leon Kühn']
        schema = provider.calls[0][1]
        assert list(schema['properties'])[0] == 'entities'
        assert 'occurrence' not in schema['properties']['entities']['items']['properties']


def test_local_unique_quotes_refuse_a_repeated_name_in_one_block(tmp_path):
    with closing(EpisodeStore(tmp_path/'episodes.sqlite3')) as episodes:
        source = original(episodes, 'Lene Kühn liefert; später meldet Lene Kühn den Versand.')
        provider = LocalQuotes(result(entity('Lene Kühn')))
        categories = Categories(episodes)
        assert not categories.run(provider, source_ids=[source.id]).ok
        assert provider.calls
        assert categories.list_for(source.id)['entities'] == []
