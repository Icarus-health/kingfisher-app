"""Mailrollen für die Einordnung; der erste Beteiligte ist nicht immer der Sprecher."""
import json

import pytest

from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_analysis import UnsupportedSource, interpret
from .test_working_memory_analysis import LocalReader, episode


def payload(source):
    reader = LocalReader({'items': {'B1': 'fact'}})
    interpret(reader, source)
    return json.loads(reader.calls[0][0][1]['content'])


def test_sender_is_explicit_from_role_not_first_recipient():
    source = episode('Anna wird die Übersicht fertigstellen. Der Empfänger muss nichts erledigen.',
        participants=['Lea <lea@example.test>', 'Ben <ben@example.test>'],
        contacts=[{'name': 'Lea', 'adresse': 'lea@example.test', 'rolle': 'an'},
                  {'name': 'Ben', 'adresse': 'ben@example.test', 'rolle': 'von'}])
    assert payload(source)['source']['email_sender'] == 'Ben <ben@example.test>'


def test_legacy_single_email_sender_remains_usable():
    assert payload(episode('Konkrete Aussage.', participants=['Ben <ben@example.test>']))['source']['email_sender'] == 'Ben <ben@example.test>'


def test_multiple_untyped_participants_do_not_invent_a_sender():
    source = episode('Konkrete Aussage.', participants=['Ben', 'Lea'])
    assert payload(source)['source']['email_sender'] == ''


@pytest.mark.parametrize('kind', [SourceType.CHAT, SourceType.DOCUMENT])
def test_nonmail_participant_does_not_become_sender(kind):
    source = episode('Konkrete Aussage.', provenance=Provenance(kind), participants=['Ben'])
    assert 'email_sender' not in payload(source)['source']


def test_new_sender_context_uses_same_honest_metadata_limit():
    reader = LocalReader({'items': {'B1': 'fact'}})
    source = episode('Konkrete Aussage.', participants=[],
        contacts=[{'name': 'B' * 4200, 'adresse': 'ben@example.test', 'rolle': 'von'}])
    with pytest.raises(UnsupportedSource):
        interpret(reader, source)
    assert reader.calls == []
