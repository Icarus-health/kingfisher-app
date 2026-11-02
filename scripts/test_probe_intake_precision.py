"""The probe measures real analysis boundaries, never fixture-based model quality."""
import json
import pytest
from icarus_memory.providers import Reply
import probe_intake_precision as probe


class Synthetic:
    is_local = True
    name = 'synthetic'
    model = 'fixture-not-a-live-model'
    entity_anchor_mode = 'block_quote'

    def __init__(self, wrong_topic=False):
        self.calls = 0
        self.wrong_topic = wrong_topic

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls += 1
        data = json.loads(messages[-1]['content'])
        if 'blocks' in data:
            block = next(b['block_id'] for b in data['blocks'] if 'Vera König' in b['text'])
            result = {'entities': [{'kind': 'person', 'name': 'Vera König', 'block_id': block, 'role': 'mentioned'}],
                      'categories': [{'category_id': 'personal', 'block_id': block}]}
            if self.wrong_topic:
                result['categories'].append({'category_id': 'information', 'block_id': 'B1'})
        elif 'candidates' in data:
            result = {'reviews': [{'id': item['id'], 'kind': 'communication_constraint' if 'Rückfragen' in item['quote'] else 'request_to_recipient', 'title_supported': True} for item in data['candidates']]}
        else:
            result = {'items': [{'title': 'Unterlagen als PDF senden', 'quote': 'Bitte senden Sie die Unterlagen, idealerweise als PDF.'},
                                {'title': 'Keine Rückfragen stellen', 'quote': 'Bitte stellen Sie keine Rückfragen zum Bearbeitungsstand.'}]}
        return Reply(text=json.dumps(result))


def test_probe_uses_real_extraction_review_category_and_exact_sources():
    provider = Synthetic()
    report = probe.evaluate(provider, case_ids=['optional-portal'])
    row = report['results'][0]
    assert row['task_titles'] == ['Bitte senden Sie die Unterlagen, idealerweise als PDF.']
    assert row['person_names'] == ['Vera König']
    assert row['deadlines'] == [None]
    assert row['original_unchanged'] is True
    assert row['checks'] == {'persons': True, 'tasks': True, 'deadlines': True, 'categories': True}
    assert report['status'] == 'passed'
    assert report['live_model_verified'] is False
    assert provider.calls == 3


def test_wrong_wrapper_topic_is_reported_as_quality_failure():
    report = probe.evaluate(Synthetic(wrong_topic=True), case_ids=['optional-portal'])
    assert report['status'] == 'failed'
    assert report['results'][0]['checks']['categories'] is False
    assert report['results'][0]['original_unchanged'] is True


def test_remote_provider_rejected_before_any_content_or_call():
    provider = Synthetic()
    provider.is_local = False
    with pytest.raises(ValueError):
        probe.evaluate(provider)
    assert provider.calls == 0


def test_budget_exhaustion_is_visible_and_never_a_pass():
    provider = Synthetic()
    report = probe.evaluate(provider, case_ids=['optional-portal'], max_calls=1)
    assert report['status'] == 'failed'
    assert report['calls'] == provider.calls == 1
    assert report['results'][0]['status'] == 'failed'
    assert report['results'][0]['error'] == 'ProbeBudgetExceeded'


def test_fixture_cases_are_fixed_unique_and_have_no_personal_store_parameter():
    assert len(probe.CASES) == 7
    assert len({case['id'] for case in probe.CASES}) == 7
    assert all('example.invalid' in case['source_ref'] for case in probe.CASES)
