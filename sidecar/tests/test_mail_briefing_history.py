"""Der kurze Mailüberblick liest die aktuelle Nachricht vor belegter Zitat-Historie."""
from icarus_memory.mail_briefing import _passages

CURRENT = 'Bitte geben Sie den Beitrag Ende Oktober ab.'
HEADER = '\n\nVon: Tim Faber <tim@example.test>\n\nGesendet: Dienstag, 7. Juli 2020 10:00\n\nAn: Nora Becker\n\nBetreff: Früherer Entwurf\n\n'


def test_dated_outlook_history_cannot_replace_the_current_request():
    body = CURRENT + HEADER + 'Bitte vereinbaren Sie damals einen Termin.\n\n' + ('Alte Korrespondenz.\n\n' * 600)
    passages, incomplete = _passages(body)
    assert passages == [CURRENT]
    assert incomplete  # Ausgeblendeter Verlauf kann Bedingungen der aktuellen Antwort tragen.
    assert all(p in body for p in passages)


def test_ambiguous_undated_header_does_not_hide_source_content():
    body = CURRENT + HEADER.replace('Dienstag, 7. Juli 2020 10:00', 'vor einiger Zeit') + 'Es gilt eine zusätzliche Bedingung.'
    passages, _ = _passages(body)
    assert 'Es gilt eine zusätzliche Bedingung.' in passages


def test_inline_reply_keeps_unquoted_current_text_without_joining_fragments():
    first = 'Der Entwurf ist noch nicht freigegeben.'
    last = 'Bitte noch keine Veröffentlichung vorbereiten.'
    body = first + '\n\nAm 7. Juli 2020 schrieb Tim:\n> Der alte Entwurf wurde freigegeben.\n\n' + last
    passages, incomplete = _passages(body)
    assert passages == [first, last]
    assert incomplete  # Eine Antwort nach entferntem Zitat kann von dessen Bedingung abhaengen.
    assert all(p in body for p in passages)


def test_large_current_message_remains_incomplete_despite_quoted_history():
    current = ('Eine aktuelle Information.\n\n' * 400) + CURRENT
    passages, incomplete = _passages(current + HEADER + 'Eine alte Bitte.')
    assert incomplete
    assert 'Eine alte Bitte.' not in passages
    assert all(p in current for p in passages)


def test_inline_reply_after_a_quoted_condition_cannot_be_complete():
    body = ('Am 7. Juli 2020 schrieb Tim:\n'
            '> Wenn die Freigabe vorliegt, soll ich veröffentlichen?\n'
            'Ja, bitte veröffentlichen.\n')
    passages, incomplete = _passages(body)
    assert passages == ['Ja, bitte veröffentlichen.']
    assert incomplete


def test_top_posted_reply_cannot_lose_its_quoted_condition_silently():
    body = ('Ja, bitte veröffentlichen.\n\nAm 7. Juli 2020 schrieb Tim:\n'
            '> Wenn die Freigabe vorliegt, soll ich veröffentlichen?\n')
    passages, incomplete = _passages(body)
    assert passages == ['Ja, bitte veröffentlichen.']
    assert incomplete
