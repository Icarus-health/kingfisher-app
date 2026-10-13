from icarus_memory.graph import GraphNode
from icarus_memory.people_quality import annotate_people


def test_company_and_unconfirmed_message_mailbox_do_not_present_as_people():
    originals = [
        GraphNode('company', 'person', 'Example Telecom GmbH <delivery@example.invalid>'),
        GraphNode('service', 'person', 'Example Software <message@example.invalid>'),
        GraphNode('human', 'person', 'Lea Example <lea@example.invalid>'),
    ]
    result = annotate_people(originals)
    assert [n.attributes['quality_category'] for n in result] == ['review', 'review', 'person']
    assert [n.id for n in result] == [n.id for n in originals]
    assert all('quality_category' not in n.attributes for n in originals)


def test_explicit_people_are_preserved_even_when_display_contains_company():
    originals = [GraphNode('confirmed', 'person', 'Lea / Example GmbH <message@example.invalid>',
                           {'identity_resolution': 'explicit_registry'})]
    assert annotate_people(originals)[0].attributes['quality_category'] == 'person'
