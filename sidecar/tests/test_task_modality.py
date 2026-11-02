"""Optional source details and communication rules are not new obligations."""
import json
import pytest

from icarus_memory.memory_analysis import interpret
from icarus_memory.providers import Reply
from icarus_memory.task_review import hard_details_supported, review_tasks


class SemanticReply:
    is_local = True
    name = 'synthetic-review'
    model = 'synthetic-review'

    def __init__(self, data):
        self.data = data
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append(messages)
        return Reply(text=json.dumps(self.data))


@pytest.mark.parametrize('title,quote,want', [
    ('Unterlagen als PDF senden', 'Bitte senden Sie die Unterlagen, idealerweise als PDF.', False),
    ('Unterlagen als PDF senden', 'Bitte senden Sie die Unterlagen, vorzugsweise als PDF.', False),
    ('Unterlagen als PDF senden', 'Bitte senden Sie die Unterlagen nach Möglichkeit als PDF.', False),
    ('Unterlagen als PDF senden', 'Bitte senden Sie die Unterlagen, wenn möglich als PDF.', False),
    ('Unterlagen senden', 'Bitte senden Sie die Unterlagen, idealerweise als PDF.', True),
    ('Unterlagen idealerweise als PDF senden', 'Bitte senden Sie die Unterlagen, idealerweise als PDF.', True),
    ('Unterlagen als PDF senden', 'Bitte senden Sie die Unterlagen zwingend als PDF.', True),
    ('Unterlagen als PDF senden, idealerweise digital', 'Bitte senden Sie die Unterlagen, idealerweise als PDF.', False),
    ('Unterlagen als PDF und idealerweise als PDF senden', 'Bitte senden Sie die Unterlagen, idealerweise als PDF.', False),
    ('Papierbericht abgeben', 'Bitte den Papierbericht abgeben. Den Plan idealerweise digital mitsenden.', True),
    ('Bericht morgen senden', 'Bitte den Bericht senden, idealerweise morgen.', False),
    ('Bericht senden', 'Bitte den Bericht senden, idealerweise morgen.', True),
    ('Unterlagen als PDF senden', 'Bitte senden Sie die Unterlagen, wenn m&ouml;glich als PDF.', False),
])
def test_optional_attribute_cannot_be_promoted_to_unconditional(title, quote, want):
    assert hard_details_supported(title, quote) is want


def test_extraction_keeps_real_request_and_exact_optional_qualifier():
    quote = 'Bitte senden Sie die Selbstauskunft und drei Gehaltsabrechnungen, idealerweise als PDF.'
    provider = SemanticReply({'items': [{'title': 'Selbstauskunft und drei Gehaltsabrechnungen als PDF senden', 'quote': quote}]})
    assert interpret(provider, 'Unterlagen', quote) == [{'title': quote, 'quote': quote}]


def test_positive_semantic_verdict_does_not_override_optional_attribute_guard():
    quote = 'Bitte senden Sie die Unterlagen, idealerweise als PDF.'
    provider = SemanticReply({'reviews': [{'id': 0, 'kind': 'request_to_recipient', 'title_supported': True}]})
    assert review_tasks(provider, 'Unterlagen', quote, [{'title': 'Unterlagen als PDF senden', 'quote': quote}]) == []


def test_communication_constraint_stays_source_context_not_a_separate_task():
    request = 'Bitte senden Sie die Unterlagen.'
    restriction = 'Bitte stellen Sie keine Rückfragen zum Bearbeitungsstand.'
    body = request + '\n' + restriction
    items = [{'title': 'Unterlagen senden', 'quote': request},
             {'title': 'Keine Rückfragen zum Bearbeitungsstand stellen', 'quote': restriction}]
    provider = SemanticReply({'reviews': [
        {'id': 0, 'kind': 'request_to_recipient', 'title_supported': True},
        {'id': 1, 'kind': 'communication_constraint', 'title_supported': True}]})
    assert review_tasks(provider, 'Unterlagen', body, items) == [items[0]]
    assert json.loads(provider.calls[0][1]['content'])['body'] == body


@pytest.mark.parametrize('quote,title', [
    ('Bitte warte auf die Freigabe.', 'Auf Freigabe warten'),
    ('Bitte geben Sie keine Dokumente an Dritte weiter.', 'Keine Dokumente an Dritte weitergeben'),
])
def test_operational_waiting_and_negative_duties_keep_existing_review(quote, title):
    item = {'title': title, 'quote': quote}
    provider = SemanticReply({'reviews': [{'id': 0, 'kind': 'request_to_recipient', 'title_supported': True}]})
    assert review_tasks(provider, 'Vorgehen', quote, [item]) == [item]


@pytest.mark.parametrize('quote', [
    'Bitte senden Sie die Unterlagen, idealerweise\nals PDF.',
    'Bitte senden Sie die Unterlagen, idealerweise\r\n> als PDF.',
    'Bitte senden Sie die Unterlagen als PDF, wenn möglich.',
    'Bitte senden Sie die Unterlagen als PDF (wenn möglich).',
])
def test_wrapped_or_postposed_optional_format_stays_optional(quote):
    assert not hard_details_supported('Unterlagen als PDF senden', quote)
    assert hard_details_supported(quote, quote)


def test_optional_scope_does_not_cross_independent_paragraph():
    quote = 'Bitte senden Sie die Unterlagen als PDF.\n\nDen Plan idealerweise als Excel-Datei.'
    assert hard_details_supported('Unterlagen als PDF senden', quote)


def test_communication_constraint_is_terminal_before_own_promise_retention(tmp_path):
    from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    quote = 'Ich werde die Unterlagen senden.'
    episode, _ = store.record(EpisodeKind.MESSAGE, 'Versand', quote,
        Provenance(SourceType.EMAIL, source_ref='synthetic-own-mail'),
        contacts=[{'rolle': 'von', 'adresse': 'owner@example.invalid', 'name': 'Owner', 'ich': True}])
    item = {'title': 'Unterlagen senden', 'quote': quote}
    fallback = SemanticReply({'reviews': [{'id': 0, 'kind': 'information', 'title_supported': False}]})
    assert review_tasks(fallback, episode.title, quote, [item], own_source=True, episode=episode)
    constraint = SemanticReply({'reviews': [{'id': 0, 'kind': 'communication_constraint', 'title_supported': False}]})
    assert review_tasks(constraint, episode.title, quote, [item], own_source=True, episode=episode) == []
    assert store.get(episode.id).body == quote
    store.close()
