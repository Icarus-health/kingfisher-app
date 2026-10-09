"""An exact after-event permission must not inherit a separate before-event ban."""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort
from icarus_memory.providers import Reply
from icarus_memory.satzantwort import AntwortBeleg, formulieren
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
BEFORE = 'Vor der Abnahme darf die Abdeckung nicht entfernt werden.'
AFTER = 'Erst nach der Abnahme darf sie entfernt werden.'


def check(sentence, *sources):
    evidence = {str(n): Beleg(str(n), text) for n, text in enumerate(sources, 1)}
    return satz_pruefen(Satz(sentence, tuple(evidence)), evidence)


@pytest.mark.parametrize(('before', 'after'), [
    (BEFORE, AFTER),
    ('Der Trichterdeckel darf vor dem Wiegen nicht abgenommen werden.',
     'Erst nach dem Wiegen darf der Trichterdeckel abgenommen werden.'),
    ('Vor der Wartung darf der Sensor nicht aktiviert werden.',
     'Nach der Wartung darf der Sensor aktiviert werden.'),
    ('Die Pumpe darf vor der Dichtheitsprüfung nicht eingeschaltet werden.',
     'Die Pumpe darf erst nach der Dichtheitsprüfung eingeschaltet werden.'),
    ('Vor der formellen Abnahme darf die Abdeckung nicht entfernt werden.',
     'Erst nach der formellen Abnahme darf die Abdeckung entfernt werden.'),
    ('Sicherheit: Vor der Abnahme darf die Abdeckung nicht entfernt werden.',
     'Freigabe: Erst nach der Abnahme darf die Abdeckung entfernt werden.'),
    (BEFORE, 'Erst nach der Abnahme darf die Abdeckung entfernt werden, wenn die Technikerin zustimmt.'),
])
def test_exact_permission_after_same_event_keeps_its_own_window(before, after):
    assert check(after, before + ' ' + after).bestanden


@pytest.mark.parametrize(('before', 'after'), [
    ('Nach der Abnahme darf die Abdeckung nicht entfernt werden.', AFTER),
    ('Die Abdeckung darf nicht entfernt werden.', AFTER),
    (BEFORE, 'Erst nach der Wartung darf sie entfernt werden.'),
    ('Vor der vorläufigen Abnahme darf die Abdeckung nicht entfernt werden.',
     'Erst nach der endgültigen Abnahme darf sie entfernt werden.'),
    ('Vor der Abnahme des Motors darf die Abdeckung nicht entfernt werden.', AFTER),
    (BEFORE, 'Erst nach der Abnahme des Motors darf sie entfernt werden.'),
    ('Vor der Abnahme, die das Messprotokoll betrifft, darf die Abdeckung nicht entfernt werden.', AFTER),
    (BEFORE, 'Erst nach der Abnahme, die das Messprotokoll betrifft, darf sie entfernt werden.'),
    ('Die Abdeckung darf nicht entfernt werden und das Protokoll bleibt vor der Abnahme gesperrt.', AFTER),
    ('Vor der Abnahme bleibt das Protokoll gesperrt und die Abdeckung darf nicht entfernt werden.', AFTER),
    ('Die Abdeckung darf vor der Abnahme nicht entfernt werden und der Motor darf nicht gestartet werden.', AFTER),
    ('Die Abdeckung vor der Abnahme darf nicht entfernt werden.', AFTER),
    ('Die Abdeckung darf nicht vor der Abnahme entfernt werden.', AFTER),
])
def test_unparsed_or_overlapping_prohibition_is_never_waived(before, after):
    assert not check(after, before + ' ' + after).bestanden


def test_before_ban_in_another_source_cannot_be_waived():
    assert not check(AFTER, BEFORE, AFTER).bestanden


def test_additional_unbounded_ban_still_blocks_exact_after_permission():
    assert not check(AFTER, BEFORE + ' Die Abdeckung darf nicht entfernt werden. ' + AFTER).bestanden


def test_changed_wording_cannot_borrow_the_new_boundary_exception():
    assert not check('Die Abdeckung darf entfernt werden.', BEFORE + ' ' + AFTER).bestanden


def test_embedded_quote_is_not_a_standalone_after_permission():
    source = BEFORE + ' Der Bericht zitiert: „' + AFTER + '“.'
    assert not check(AFTER, source).bestanden


@pytest.mark.parametrize('quote', [('„', '“'), ('"', '"'), ("'", "'"), ('‚', '‘'), ('‹', '›'), ('`', '`')])
def test_inner_sentence_in_a_multisentence_old_quote_does_not_become_permission(quote):
    source = BEFORE + ' Der Bericht zitiert eine alte Anweisung: ' + quote[0] + (
        'Zuerst wird das Datum notiert. ' + AFTER + ' Diese Anweisung ist nicht verbindlich.') + quote[1]
    assert not check(AFTER, source).bestanden


@pytest.mark.parametrize('ending', ['?', '?!', '!?', '.?', '.!?'])
def test_permission_question_cannot_be_reused_as_a_statement(ending):
    assert not check(AFTER, BEFORE + ' ' + AFTER.rstrip('.') + ending).bestanden


def test_changed_additional_condition_is_rejected():
    after = 'Erst nach der Abnahme darf sie entfernt werden, wenn die Technikerin schriftlich zustimmt.'
    changed = 'Erst nach der Abnahme darf sie entfernt werden, wenn die Technikerin mündlich zustimmt.'
    assert not check(changed, BEFORE + ' ' + after).bestanden
    assert not check(AFTER, BEFORE + ' ' + after).bestanden


class SelectBoth:
    is_local = True
    name = model = 'synthetic-original-selector'

    def complete_json(self, messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        source = data['belege'][0]
        return Reply(text=json.dumps({'status': 'antwort', 'originalstellen': [
            {'beleg': source['nr'], 'satz': s['nr']} for s in source['originalsaetze']]}))


def test_source_selection_retains_both_windows_without_rejection_notice():
    body = BEFORE + ' ' + AFTER
    evidence = AntwortBeleg(1, {}, 'conditional', 'synthetic', 'Abdeckung', '', body, None)
    result = formulieren('Darf die Abdeckung vor der Abnahme entfernt werden?', [evidence], SelectBoth(), jetzt=NOW)
    assert result.status == 'saetze'
    assert [s.text for s in result.saetze] == [BEFORE + ' ' + AFTER]
    assert not result.verworfen


def test_source_supported_saved_permission_survives_store_reopen_and_withdrawal(tmp_path):
    from icarus_memory import EpisodeStore, EpisodeKind, Provenance, SourceType, working_memory_answers
    from icarus_memory.claims import ClaimStore
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from tests.test_satzantwort import Skript

    body = BEFORE + ' ' + AFTER
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Abdeckung', body, Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id),
            [{'start': 0, 'end': len(body), 'kind': 'conditional'}], model='synthetic')
        provider = Skript({'status': 'antwort', 'saetze': [{'text': body, 'belege': [1]}]})
        answer = working_memory_answers.prepare('Was steht zur Abdeckung?', episodes, claims, provider, saetze=True)
        saved = answer['satzantwort']
        assert saved['status'] == 'saetze'
    finally:
        claims.close()
        episodes.close()
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        restored = satzantwort.wiederherstellen(saved, episodes, claims)
        assert restored is not None
        assert [s.text for s in restored.saetze] == [body]
        # Keep the old single-window payload as an explicit negative control:
        # it must not outlive the new complete-paragraph contract after reopen.
        from copy import deepcopy
        incomplete = deepcopy(saved)
        incomplete['saetze'][0].update(roh=AFTER, text=AFTER)
        assert satzantwort.wiederherstellen(incomplete, episodes, claims) is None
        episodes.ignore(source.id)
        assert satzantwort.wiederherstellen(saved, episodes, claims) is None
        assert episodes.get(source.id).body == body
    finally:
        claims.close()
        episodes.close()
