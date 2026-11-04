"""A bounded model correction must never replace strict original evidence."""
import json

import pytest

from icarus_memory.memory_categories import SourceValidationError, _DEFAULTS, _interpret
from icarus_memory.providers import ProviderError, Reply
from icarus_memory.source_processing_policy import ExplicitSourcePolicy
from .test_memory_categories import setup, source, RemoteQuoteProvider, run_remote


class RepairProvider(RemoteQuoteProvider):
    category_evidence_repair = True


def entity(block='B1', name='Example.de', occurrence=1):
    return {'kind': 'organization', 'name': name, 'block_id': block,
            'occurrence': occurrence, 'role': 'mentioned'}


def result(*entities, category='finance'):
    return {'categories': [{'category_id': category, 'block_id': 'B1'}],
            'entities': list(entities)}


def interpret(provider, item, permitted=lambda: True):
    policy = ExplicitSourcePolicy(provider, item.id, lambda _episode: permitted())
    taxonomy = [{'id': r[0], 'label': r[1], 'description': r[2]} for r in _DEFAULTS]
    return _interpret(provider, item, taxonomy, policy=policy)


def test_wrong_block_gets_one_fresh_model_correction_with_identical_originals(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, 'Besuche https://example.de.\n\nExample.de ist ein Handelsname.\n\nExample.de')
    provider = RepairProvider(lambda payload, call: result(entity('B1' if call == 1 else 'B2')))
    assert run_remote(categories, item, provider).ok
    assert len(provider.calls) == 2
    first, second = [call[0] for call in provider.calls]
    assert first['blocks'] == second['blocks']
    assert second['validation_failure']['reason'] == 'entity_missing'
    assert second['rejected_output'] == result(entity('B1'))
    stored = categories.list_for(item.id)
    assert len(stored['categories']) == 1  # rejected attempt must not leak topics
    assert [(x['name'], x['start']) for x in stored['entities']] == [
        ('Example.de', item.body.index('Example.de'))]


@pytest.mark.parametrize('bad', [entity('B1'), entity('B2', 'EXAMPLE.DE'), entity('B2', occurrence=9)])
def test_invalid_correction_is_not_reanchored_normalized_or_retried(tmp_path, bad):
    episodes, _ = setup(tmp_path)
    item = source(episodes, 'URL https://example.de\n\nExample.de und Example.de')
    provider = RepairProvider(lambda payload, call: result(bad))
    with pytest.raises(SourceValidationError):
        interpret(provider, item)
    assert len(provider.calls) == 2


def test_uncorrected_second_section_stores_neither_partial_nor_rejected_results(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, '\n\n'.join(['Example.de'] + [f'Block {i}' for i in range(24)]))
    provider = RepairProvider(lambda payload, call: result(entity(name='Example.de' if call == 1 else 'Missing')))
    assert not run_remote(categories, item, provider).ok
    assert len(provider.calls) == 3
    assert categories.list_for(item.id)['entities'] == []
    assert categories.list_for(item.id)['categories'] == []


def test_revocation_prevents_correction_send(tmp_path):
    episodes, _ = setup(tmp_path)
    item = source(episodes, 'URL https://example.de\n\nExample.de')
    allowed = [True]
    def answer(payload, call):
        allowed[0] = False
        return result(entity('B1'))
    provider = RepairProvider(answer)
    with pytest.raises(ProviderError):
        interpret(provider, item, lambda: allowed[0])
    assert len(provider.calls) == 1


def test_valid_result_requires_no_second_request_and_non_opted_provider_stays_strict(tmp_path):
    episodes, _ = setup(tmp_path)
    item = source(episodes, 'Example.de')
    provider = RepairProvider(lambda payload, call: result(entity()))
    assert interpret(provider, item)[1]
    assert len(provider.calls) == 1
    old = RemoteQuoteProvider(lambda payload, call: result(entity(name='Missing')))
    with pytest.raises(SourceValidationError):
        interpret(old, item)
    assert len(old.calls) == 1


def test_transport_errors_are_not_retried(tmp_path):
    episodes, _ = setup(tmp_path)
    item = source(episodes, 'Example.de')
    provider = RepairProvider(lambda payload, call: (_ for _ in ()).throw(ProviderError('offline')))
    with pytest.raises(ProviderError):
        interpret(provider, item)
    assert len(provider.calls) == 1


def test_repair_identifies_each_bad_anchor_without_selecting_replacements(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, 'Projekt Nord\u00a0Stern mit Example.de.')
    bad = result(entity(name='Nord Stern'), entity(name='Invented Person'),
                 entity('source', 'Example.de'), entity(name='Example.de'))
    def answer(payload, call):
        if call == 1:
            return bad
        assert payload['validation_failure']['entity_errors'] == [
            {'index': 0, 'reason': 'entity_missing'},
            {'index': 1, 'reason': 'entity_missing'},
            {'index': 2, 'reason': 'entity_span'},
        ]
        assert payload['rejected_output'] == bad
        assert payload['blocks'] == [{'block_id': 'B1', 'text': item.body}]
        return result(entity(name='Nord\u00a0Stern'), entity(name='Example.de'))
    provider = RepairProvider(answer)
    assert run_remote(categories, item, provider).ok
    assert len(provider.calls) == 2
    assert [row['name'] for row in categories.list_for(item.id)['entities']] == [
        'Nord\u00a0Stern', 'Example.de']


@pytest.mark.parametrize('space', ['\u00a0', '\u202f'])
def test_invisible_source_whitespace_is_visible_in_json_but_preserved_exactly(tmp_path, space):
    episodes, categories = setup(tmp_path)
    name = f'Nord{space}Stern'
    item = source(episodes, f'{name} ist ein Handelsname.')
    original = item.to_dict()
    class VisibleProvider(RepairProvider):
        def complete_json(self, messages, **kwargs):
            raw = messages[-1]['content']
            assert space not in raw
            assert ('\\u%04x' % ord(space)) in raw
            assert json.loads(raw)['blocks'][0]['text'] == item.body
            return super().complete_json(messages, **kwargs)
    provider = VisibleProvider(lambda payload, call: result(
        entity(name='Nord Stern' if call == 1 else name)))
    assert run_remote(categories, item, provider).ok
    assert len(provider.calls) == 2
    saved = categories.list_for(item.id)['entities'][0]
    assert saved['name'] == name
    assert item.body[saved['start']:saved['end']] == name
    assert episodes.get(item.id).to_dict() == original


def test_local_large_unicode_source_still_fits_verified_8k_input_budget(tmp_path):
    from icarus_memory.providers import OpenAICompatible
    from icarus_memory.local_context_profile import _native_payload
    episodes, _ = setup(tmp_path)
    body = '\n\n'.join(['Nord\u00a0Stern\u00a0liefert\u00a0die\u00a0Unterlagen. ' * 67] * 3)
    item = source(episodes, body)
    actual = OpenAICompatible('kingfisher-qwen3.5:9b-8k', 'artificial', 'http://127.0.0.1:11434/v1')
    class LocalCapture:
        is_local = True
        entity_anchor_mode = 'block_quote'
        def complete_json(self, messages, *, max_tokens, schema):
            # Pure payload builders only: no transport, profile lookup or inference.
            payload = actual._json_payload(messages, max_tokens, schema)
            _native_payload(actual, payload)
            return Reply(text='{"categories":[],"entities":[]}')
    taxonomy = [{'id': r[0], 'label': r[1], 'description': r[2]} for r in _DEFAULTS]
    assert _interpret(LocalCapture(), item, taxonomy) == ([], [])
    assert episodes.get(item.id).body == body


def test_repair_feedback_includes_duplicate_after_earlier_missing_anchor(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, 'Example.de ist ein Handelsname.')
    def answer(payload, call):
        if call == 1:
            return result(entity(name='Missing'), entity(), entity())
        assert payload['validation_failure']['entity_errors'] == [
            {'index': 0, 'reason': 'entity_missing'},
            {'index': 2, 'reason': 'entity_duplicate'},
        ]
        return result(entity())
    provider = RepairProvider(answer)
    assert run_remote(categories, item, provider).ok
    assert len(provider.calls) == 2
    assert len(categories.list_for(item.id)['entities']) == 1
