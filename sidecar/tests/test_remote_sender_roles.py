"""Cloud extrahiert Namen; die Mailkopf-Rolle bestimmt ausschließlich der Code."""
import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType
from tests.test_memory_categories import RemoteQuoteProvider, run_remote, setup


def email(episodes, body, *, participants=None, contacts=None):
    item, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetische Rollenprobe', body,
        Provenance(SourceType.EMAIL, source_ref='synthetic-roles'),
        participants=participants or [], contacts=contacts or [])
    return item


def answer(name, *, role='mentioned'):
    return RemoteQuoteProvider(lambda _payload, _number: {
        'categories': [{'category_id': 'work', 'block_id': 'B1'}],
        'entities': [{'kind': 'person', 'name': name, 'block_id': 'B1',
                      'occurrence': 1, 'role': role}]})


def test_remote_mentions_do_not_merge_with_the_separately_known_envelope_sender(tmp_path):
    episodes, categories = setup(tmp_path)
    item = email(episodes, 'Anna Kranz bittet Ben um den Bericht.',
        participants=['Ben Mayer <ben@example.org>', 'Anna Kranz <anna@example.org>'],
        contacts=[{'name': 'Ben Mayer', 'adresse': 'ben@example.org', 'rolle': 'an'},
                  {'name': 'Anna Kranz', 'adresse': 'anna@example.org', 'rolle': 'von'}])
    provider = answer('Anna Kranz')
    assert run_remote(categories, item, provider).ok
    assert categories.list_for(item.id)['entities'][0]['role'] == 'mentioned'
    assert provider.calls[0][1]['properties']['entities']['items']['properties']['role'] == {'type': 'string', 'const': 'mentioned'}


def test_remote_cannot_claim_sender_even_when_name_matches_envelope(tmp_path):
    episodes, categories = setup(tmp_path)
    item = email(episodes, 'Anna Kranz bittet um Antwort.',
        participants=['Anna Kranz <anna@example.org>'])
    assert not run_remote(categories, item, answer('Anna Kranz', role='sender')).ok
    result = categories.list_for(item.id)
    assert result['entities'] == result['categories'] == []


@pytest.mark.parametrize('name,participants,contacts,body', [
    ('Anna', ['Anna Kranz <anna@example.org>'], [], 'Anna bittet um Antwort.'),
    ('Ben Mayer', ['Ben Mayer <ben@example.org>', 'Anna Kranz <anna@example.org>'],
     [{'name':'Ben Mayer','adresse':'ben@example.org','rolle':'cc'},
      {'name':'Anna Kranz','adresse':'anna@example.org','rolle':'von'}], 'Ben Mayer antwortet im Verlauf.'),
    ('Anna Kranz', [], [], 'Von: Anna Kranz <anna@example.org>\n\nEin zitierter Brief.'),
    ('Anna Kranz', ['Anna Kranz <anna@example.org>', 'Ben Mayer <ben@example.org>'], [], 'Anna Kranz wird erwähnt.'),
])
def test_partial_recipient_body_header_and_unknown_roles_remain_mentions(tmp_path, name, participants, contacts, body):
    episodes, categories = setup(tmp_path)
    item = email(episodes, body, participants=participants, contacts=contacts)
    assert run_remote(categories, item, answer(name)).ok
    assert categories.list_for(item.id)['entities'][0]['role'] == 'mentioned'


@pytest.mark.parametrize('participants,contacts', [
    (['=?UTF-8?Q?J=C3=B6rg_Kranz?= <joerg@example.org>'], []),
    ([], [{'name':'Jörg Kranz','adresse':'joerg@example.org','rolle':'von'}]),
])
def test_encoded_and_contact_only_sender_does_not_claim_mention_identity(tmp_path, participants, contacts):
    episodes, categories = setup(tmp_path)
    item = email(episodes, 'Jörg Kranz bittet um Prüfung.', participants=participants, contacts=contacts)
    assert run_remote(categories, item, answer('Jörg Kranz')).ok
    assert categories.list_for(item.id)['entities'][0]['role'] == 'mentioned'


def test_contact_only_generic_sender_is_never_promoted_to_person(tmp_path):
    episodes, categories = setup(tmp_path)
    item = email(episodes, 'Acme Service informiert über ein Update.',
        contacts=[{'name':'Acme Service','adresse':'support@example.org','rolle':'von'}])
    assert run_remote(categories, item, answer('Acme Service')).ok
    assert categories.list_for(item.id)['entities'] == []


def test_quoted_namesake_is_not_promoted_to_sender_even_with_same_named_envelope(tmp_path):
    episodes, categories = setup(tmp_path)
    body = 'Anna Kranz leitet weiter.\n\n> Eine andere Anna Kranz hat zugesagt.'
    item = email(episodes, body, participants=['Anna Kranz <outer@example.org>'])
    provider = RemoteQuoteProvider(lambda _payload, _number: {
        'categories': [], 'entities': [{'kind':'person','name':'Anna Kranz',
            'block_id':'B2','occurrence':1,'role':'mentioned'}]})
    assert run_remote(categories, item, provider).ok
    entity = categories.list_for(item.id)['entities'][0]
    assert entity['start'] == body.rindex('Anna Kranz')
    assert entity['role'] == 'mentioned'
    from icarus_memory.kontakte import absender_text
    assert absender_text(item.participants, item.contacts) == 'Anna Kranz <outer@example.org>'
