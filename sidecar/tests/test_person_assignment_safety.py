"""A literal company/service label is not a human, even if the model says so."""
import pytest

from tests.test_memory_categories import Local, setup, source
from tests.test_people_quality import person
from icarus_memory.people_quality import annotate_people


@pytest.mark.parametrize('label', [
    'Amazon Digital Germany GmbH', 'Example Inc', 'Example Ltd', 'Example LLC',
    'Rechnungsstellung', 'Rechnungsabteilung', 'Customer Service', 'Customer Support',
])
def test_organization_and_service_names_do_not_enter_automatic_people_view(tmp_path, label):
    episodes, categories = setup(tmp_path)
    body = f'{label} versendet eine Nachricht. Anna Kranz prüft die Rechnung.'
    item = source(episodes, body)
    before = item.to_dict()
    anna = body.index('Anna Kranz')
    provider = Local(result={'categories': [], 'entities': [
        {'kind': 'person', 'name': label, 'start': 0, 'end': len(label), 'role': 'mentioned'},
        {'kind': 'person', 'name': 'Anna Kranz', 'start': anna, 'end': anna+10, 'role': 'mentioned'},
    ]})
    assert categories.run(provider).ok
    result = categories.list_for(item.id)
    assert [e['name'] for e in result['entities'] if e['kind']=='person'] == ['Anna Kranz']
    assert episodes.get(item.id).to_dict() == before
    # Repeated reads apply the same guard to persisted automatic mentions.
    assert [e['name'] for e in categories.list_for(item.id)['entities'] if e['kind']=='person'] == ['Anna Kranz']
    episodes.close()


@pytest.mark.parametrize('label', ['Amazon Digital Germany GmbH', 'Rechnungsstellung', 'Customer Service'])
def test_legacy_people_projection_flags_unconfirmed_labels_without_changing_confirmed_identity(label):
    unknown, confirmed = person('unknown', label), person('confirmed', label, True)
    result = annotate_people([unknown, confirmed])
    assert [n.attributes['quality_category'] for n in result] == ['review', 'person']
    assert result[0].attributes['duplicate_ids'] == []
    assert 'quality_category' not in unknown.attributes
    assert [n.id for n in result] == ['unknown', 'confirmed']
