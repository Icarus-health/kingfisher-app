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
