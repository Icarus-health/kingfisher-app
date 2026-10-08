from icarus_memory.graph import GraphNode


def person(id,label,explicit=False):
    return GraphNode(id,'person',label,{'identity_resolution':'explicit_registry' if explicit else 'exact_normalized_name'})


def test_same_mailbox_is_only_a_candidate_and_ids_are_preserved():
    from icarus_memory.people_quality import annotate_people
    nodes=[person('a','Lea Example <lea@example.org>'),person('b','"Lea" <LEA@example.org>')]
    result=annotate_people(nodes)
    assert [n.id for n in result]==['a','b']
    assert result[0].attributes['duplicate_ids']==['b']
    assert result[0].attributes['duplicate_reason']=='same_mailbox'
    assert 'duplicate_ids' not in nodes[0].attributes


def test_shared_notification_sender_never_groups_apparent_people():
    from icarus_memory.people_quality import annotate_people
    nodes=[person('a','Lea (Google Docs) <comments-noreply@docs.google.com>'),person('b','Alex (Google Docs) <comments-noreply@docs.google.com>')]
    result=annotate_people(nodes)
    assert all(n.attributes['quality_category']=='automated' for n in result)
    assert all(n.attributes['duplicate_ids']==[] for n in result)


def test_explicit_person_is_not_reclassified_and_test_label_is_reviewable():
    from icarus_memory.people_quality import annotate_people
    result=annotate_people([person('a','Noreply <noreply@example.org>',True),person('b','Alex (Integrationstest)',True)])
    assert result[0].attributes['quality_category']=='person'
    assert result[1].attributes['quality_category']=='review'


def test_confirmed_identity_mapping_is_not_reclassified_as_service_mailbox():
    from icarus_memory.people_quality import annotate_people
    node=GraphNode('group','person','Ava <service@example.org>',{'identity_resolution':'confirmed_group'})
    result=annotate_people([node])[0]
    assert result.attributes['quality_category']=='person'
    assert result.attributes['quality_reason']==''
    assert result.attributes['duplicate_ids']==[]


def test_same_name_different_addresses_remains_two_review_candidates():
    from icarus_memory.people_quality import annotate_people
    result=annotate_people([person('a','Alex Example <one@example.org>'),person('b','Alex Example <two@example.org>')])
    assert result[0].attributes['duplicate_reason']=='same_name'
    assert len(result)==2


def test_non_people_untouched_and_generic_address_needs_review():
    from icarus_memory.people_quality import annotate_people
    project=GraphNode('p','project','One')
    result=annotate_people([project,person('a','Support <support@example.org>'),person('b','one@example.org, two@example.org')])
    assert result[0] is project
    assert all(n.attributes['quality_category']=='review' for n in result[1:])


def test_tagged_technical_addresses_are_not_people():
    from icarus_memory.people_quality import annotate_people
    result=annotate_people([person('a','notifications+123@example.org'),person('b','noreply+ticket@example.org'),person('c','support+foo@example.org')])
    assert [n.attributes['quality_category'] for n in result]==['automated','automated','review']


def test_composed_german_and_platform_mailboxes_are_review_not_people():
    from icarus_memory.people_quality import annotate_people
    labels = [
        '1&1 Kundenservice <versand-service@1und1.de>',
        '1&1 Rechnungsstelle <rechnungsstelle@1und1.de>',
        'Payments <payments-update@example.org>',
        'Orders <order-update@example.org>',
        'Shipping <shipment-tracking@example.org>',
        'Marketplace <marketplace-messages@example.org>',
    ]
    result = annotate_people([person(str(index), label) for index, label in enumerate(labels)])
    assert [node.attributes['quality_category'] for node in result] == ['review'] * len(labels)
    assert all(node.attributes['duplicate_ids'] == [] for node in result)


def test_personal_mailbox_is_preserved_but_marketplace_relay_needs_confirmation():
    from icarus_memory.people_quality import annotate_people
    result = annotate_people([
        person('address', 'Anna Service <anna.service@example.org>'),
        person('relay', 'Jane Doe <marketplace-messages@example.org>'),
        person('explicit', 'Marketplace <marketplace-messages@example.org>', True),
    ])
    assert [node.attributes['quality_category'] for node in result] == ['person', 'review', 'person']
    assert all(node.attributes['duplicate_ids'] == [] for node in result)


def test_duplicate_groups_are_symmetric_without_transitive_identity_guess():
    from icarus_memory.people_quality import annotate_people
    result=annotate_people([person('a','Alex <a@example.org>'),person('b','Alex <b@example.org>'),person('c','Other <b@example.org>')])
    by_id={n.id:n for n in result}
    for n in result:
        for peer in n.attributes['duplicate_ids']:
            assert n.id in by_id[peer].attributes['duplicate_ids']
