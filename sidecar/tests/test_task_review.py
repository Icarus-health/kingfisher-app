"""A literal quotation is insufficient to turn information into an own task."""
import json

import pytest

from icarus_memory.providers import ProviderError, Reply
from icarus_memory.task_review import review_tasks


class Reviewer:
    is_local = True

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.calls = []

    def complete_json(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return Reply(text=json.dumps({'reviews': self.verdicts}))


def verdict(identifier=0, kind='request_to_recipient', supported=True):
    return {'id': identifier, 'kind': kind, 'title_supported': supported}


@pytest.mark.parametrize('kind,supported,expected', [
    ('request_to_recipient', True, True),
    ('own_commitment', True, True),
    ('information', True, False),
    ('marketing', True, False),
    ('other_person', True, False),
    ('unclear', True, False),
    ('request_to_recipient', False, False),
])
def test_only_explicit_own_actions_with_supported_titles_survive(kind, supported, expected):
    provider = Reviewer([verdict(kind=kind, supported=supported)])
    item = {'title': 'Bericht senden', 'quote': 'Bitte sende den Bericht.'}
    assert review_tasks(provider, 'Bericht', item['quote'], [item], own_source=kind == 'own_commitment') == ([item] if expected else [])
    payload = json.loads(provider.calls[0][0][1]['content'])
    assert payload['body'] == item['quote']
    assert payload['candidates'][0] == {'id': 0, **item}


def test_whole_context_including_cancellation_reaches_reviewer():
    provider = Reviewer([verdict(kind='information')])
    body = 'Bitte sende den Bericht.\n\nUpdate: Nicht mehr senden, der Auftrag entfällt.'
    item = {'title': 'Bericht senden', 'quote': 'Bitte sende den Bericht.'}
    assert review_tasks(provider, 'Update', body, [item]) == []
    assert json.loads(provider.calls[0][0][1]['content'])['body'] == body


@pytest.mark.parametrize('verdicts', [[], [verdict(), verdict()], [verdict(True)],
    [verdict(7)], [verdict(kind='new')], [verdict(supported='true')],
    [{**verdict(), 'quote': 'invented'}]])
def test_missing_duplicate_unknown_or_ill_typed_verdict_fails_closed(verdicts):
    provider = Reviewer(verdicts)
    with pytest.raises(ProviderError):
        review_tasks(provider, 'Bericht', 'Bitte sende den Bericht.',
                     [{'title': 'Bericht senden', 'quote': 'Bitte sende den Bericht.'}])


def test_no_candidates_means_no_extra_model_call():
    provider = Reviewer([])
    assert review_tasks(provider, 'Info', 'Nur Information.', []) == []
    assert provider.calls == []


def test_cloud_or_cropped_context_cannot_pass_review():
    provider = Reviewer([verdict()])
    item = {'title': 'Bericht senden', 'quote': 'Bitte sende den Bericht.'}
    provider.is_local = False
    with pytest.raises(ProviderError):
        review_tasks(provider, 'Info', item['quote'], [item])
    provider.is_local = True
    with pytest.raises(ProviderError):
        review_tasks(provider, 'Info', item['quote'] + 'x' * 20000, [item])
    assert provider.calls == []


def test_other_person_commitment_is_not_accepted_as_own_without_source_identity():
    provider = Reviewer([verdict(kind='own_commitment')])
    item = {'title': 'Bericht senden', 'quote': 'Ich sende den Bericht.'}
    assert review_tasks(provider, 'Bericht', item['quote'], [item], own_source=False) == []


def test_unquoted_or_excess_candidates_are_rejected_before_inference():
    provider = Reviewer([verdict()])
    with pytest.raises(ProviderError):
        review_tasks(provider, 'Info', 'Nur Information.', [{'title': 'Senden', 'quote': 'Bitte senden.'}])
    assert provider.calls == []
