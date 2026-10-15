"""Synthetic mail quote boundaries remain authoritative across model sections."""
import json
from types import SimpleNamespace

import pytest

from icarus_memory.providers import Reply
from icarus_memory.working_memory_analysis import interpret
from tests.test_working_memory_analysis import episode


class RequestReader:
    is_local = True
    def __init__(self, kind="request"):
        self.calls = []
        self.kind = kind
    def complete_json(self, messages, **kwargs):
        blocks = json.loads(messages[1]['content'])['blocks']
        self.calls.append(blocks)
        return Reply(text=json.dumps({'items': [
            {'block_id': block['block_id'],
             'kind': 'irrelevant' if 'SIGNATURE_ONLY' in block['text'] else self.kind}
            for block in blocks]}))


def item_for(body, items, needle):
    start = body.index(needle)
    return next(item for item in items if item['start'] <= start < item['end'])


@pytest.mark.parametrize('separator', ['\n', '\r\n', '\r\n\r\n'])
@pytest.mark.parametrize('model_kind', ['request', 'status', 'commitment'])
def test_outlook_history_survives_section_boundaries(separator, model_kind):
    header = separator.join(['Von: Ada <ada@example.test>',
                             'Gesendet: Montag, 6. Juli 2026 09:30',
                             'An: Bo <bo@example.test>', 'Betreff: Frühere Anfrage'])
    current = 'Bitte das Manuskript Ende Oktober zusenden.'
    old = ['Alter Kontext %d: ' % n + 'weitere Information. ' * 65 for n in range(12)]
    body = current + '\n\n' + header + '\n\n' + '\n\n'.join(old) + '\n\nBitte den alten Termin bestätigen.\n\nSIGNATURE_ONLY'
    reader = RequestReader(model_kind)
    items = interpret(reader, episode(body))
    assert len(reader.calls) > 1
    assert item_for(body, items, current)['kind'] == model_kind
    assert all(item_for(body, items, text)['kind'] == 'historical' for text in old)
    assert item_for(body, items, 'Bitte den alten Termin')['kind'] == 'historical'
    assert not any('SIGNATURE_ONLY' in body[item['start']:item['end']] for item in items)
    assert body[items[0]['start']:items[0]['end']] == current


@pytest.mark.parametrize('header', [
    'Am Mo., 6. Juli 2026 um 09:30 schrieb Ada <ada@example.test>:',
    'On Mon, Jul 6, 2026 at 9:30 AM Ada <ada@example.test> wrote:',
    'Am Mo., 6. Juli 2026 um 09:30 schrieb Ada\r\n<ada@example.test>:',
])
def test_dated_quoted_reply_keeps_unquoted_inline_reply_current(header):
    body = ('Bitte heute prüfen.\n\n' + header + '\n\n> Bitte den alten Termin bestätigen.'
            '\n\n> Frühere Zusage bleibt im Verlauf.\n\nMeine aktuelle Antwort folgt morgen.')
    items = interpret(RequestReader(), episode(body))
    assert item_for(body, items, '> Bitte')['kind'] == 'historical'
    assert item_for(body, items, '> Frühere')['kind'] == 'historical'
    assert item_for(body, items, 'Meine aktuelle Antwort')['kind'] == 'request'


def test_mixed_block_is_uncertain_and_never_hides_current_request_as_history():
    body = ('Bitte jetzt prüfen.\nVon: Ada <ada@example.test>\n'
            'Gesendet: 06.07.2026 09:30\nAn: Bo <bo@example.test>\nBetreff: Alt\nBitte früher prüfen.')
    items = interpret(RequestReader(), episode(body))
    assert len(items) == 1 and items[0]['kind'] == 'uncertain'
    assert body[items[0]['start']:items[0]['end']] == body


@pytest.mark.parametrize('body', [
    'Bitte Ende Oktober liefern.\n\nMit freundlichen Grüßen\nAda',
    'Von: Nutzen und Risiken\n\nBitte aktuell prüfen.',
    'Am besten schrieb Ada den Entwurf:\n\n> Bitte prüfen.',
    'Gesendet: 06.07.2026\nAn: Ada\nBetreff: Aufgabe\n\nBitte prüfen.',
    'Von: Ada\nGesendet: irgendwann\nAn: Bo\nBetreff: Aufgabe\n\nBitte prüfen.',
    'Am 6. Juli 2026 schrieb Ada:\n\nBitte aktuell prüfen.',
])
def test_loose_words_signatures_and_unquoted_text_never_create_history(body):
    assert all(item['kind'] == 'request' for item in interpret(RequestReader(), episode(body)))


@pytest.mark.parametrize('kind,source_type', [('document', 'email'), ('document', 'document'), ('message', 'chat')])
def test_documents_and_non_mail_messages_are_not_reinterpreted(kind, source_type):
    body = ('Von: Ada\nGesendet: 06.07.2026\nAn: Bo\nBetreff: Beispiel\n\nBitte prüfen.')
    provenance = SimpleNamespace(to_dict=lambda: {'source_type': source_type})
    assert all(item['kind'] == 'request' for item in interpret(
        RequestReader(), episode(body, kind=kind, provenance=provenance)))


def test_quoted_outlook_header_does_not_swallow_unquoted_inline_response():
    body = ('Bitte heute prüfen.\n\n> Von: Ada <ada@example.test>\n'
            '> Gesendet: 06.07.2026 09:30\n> An: Bo <bo@example.test>\n> Betreff: Alt\n\n'
            '> Bitte den alten Termin bestätigen.\n\nMeine aktuelle Antwort folgt morgen.')
    items = interpret(RequestReader(), episode(body))
    assert item_for(body, items, '> Bitte')['kind'] == 'historical'
    assert item_for(body, items, 'Meine aktuelle Antwort')['kind'] == 'request'
