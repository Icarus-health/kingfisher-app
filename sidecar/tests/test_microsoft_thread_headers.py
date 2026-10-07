"""Graph must retain the same bounded thread headers as IMAP intake."""
from types import SimpleNamespace
import pytest
from icarus_memory.microsoft_graph import MicrosoftPost


@pytest.mark.parametrize('headers, expected_reply, expected_refs', [
    ([{'name': 'In-Reply-To', 'value': '<parent@test>'},
      {'name': 'rEfErEnCeS', 'value': '<root@test> <parent@test>'}], '<parent@test>', ('<root@test>', '<parent@test>')),
    ([], '', ()),
    ([{'name': 'References', 'value': ' '.join(f'<id{i}@test>' for i in range(80))}], '', tuple(f'<id{i}@test>' for i in range(64))),
])
def test_graph_message_retains_header_relations_without_extra_requests(headers, expected_reply, expected_refs):
    calls = []
    def get(path, params, **kwargs):
        calls.append((path, params))
        return {'internetMessageId': '<self@test>', 'internetMessageHeaders': headers, 'body': {'content': 'Original'}}
    post = MicrosoftPost('me@example.test', SimpleNamespace(holen=get), None)
    message = post._nachricht('immutable-id', '1.42')
    assert message.in_reply_to == expected_reply
    assert message.references == expected_refs
    assert message.message_id == '<self@test>'
    assert len(calls) == 1
