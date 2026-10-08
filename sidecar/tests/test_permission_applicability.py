"""Applicability qualifiers belong to the permission clause they qualify."""
import json
from datetime import datetime, timezone

from icarus_memory import satzpruefung_modell
from icarus_memory.providers import Reply
from icarus_memory.satzantwort import AntwortBeleg, formulieren
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen


R508_RULE = 'Für Auftrag R-508 ist vor der Reinigung ausschließlich ein trockenes Tuch erlaubt.'
SOLVENT_BAN = 'Lösungsmittel dürfen nicht eingesetzt werden.'
R508_SOURCE = R508_RULE + ' ' + SOLVENT_BAN
UNSCOPED_TOWELS = 'Für Auftrag R-508 sind nur trockene Tücher erlaubt.'
QUALIFIED_TOWELS = 'Vor der Reinigung von Auftrag R-508 darf nur ein trockenes Tuch verwendet werden.'


def _check(sentence, *sources):
    belege = {str(index): Beleg(str(index), text) for index, text in enumerate(sources or (R508_SOURCE,), 1)}
    return satz_pruefen(Satz(sentence, tuple(belege)), belege)


def test_permission_paraphrase_cannot_drop_precleaning_applicability():
    assert not _check(UNSCOPED_TOWELS).bestanden


def test_exact_and_supported_qualified_permission_wordings_pass():
    assert _check(R508_RULE).bestanden
    assert _check(QUALIFIED_TOWELS).bestanden


def test_independent_solvent_ban_does_not_inherit_cleaning_scope():
    assert _check(SOLVENT_BAN).bestanden


def test_same_id_and_permission_word_do_not_link_an_independent_solvent_rule():
    source = R508_RULE + ' Für Auftrag R-508 dürfen Lösungsmittel nicht eingesetzt werden.'
    sentence = 'Für Auftrag R-508 dürfen Lösungsmittel nicht eingesetzt werden.'
    assert _check(sentence, source).bestanden


def test_shared_case_id_does_not_transfer_scope_to_an_unrelated_invoice_clause():
    source = R508_RULE + ' Die Rechnung für R-508 wurde am Dienstag freigegeben.'
    assert _check('Die Rechnung für R-508 wurde am Dienstag freigegeben.', source).bestanden


def test_temporal_relation_cannot_be_reversed_for_the_same_permission():
    sentence = 'Nach der Reinigung von Auftrag R-508 darf nur ein trockenes Tuch verwendet werden.'
    assert not _check(sentence).bestanden


def test_while_scope_is_preserved_as_a_temporal_qualifier():
    source = 'Für Auftrag R-508 ist ein trockenes Tuch während der Reinigung erlaubt.'
    assert not _check(UNSCOPED_TOWELS, source).bestanden
    assert _check(source, source).bestanden


def test_another_explicitly_supported_time_context_remains_allowed():
    source = ('Vor der Reinigung ist ein trockenes Tuch erlaubt. '
              'Nach der Wartung ist ein trockenes Tuch erlaubt.')
    assert _check('Nach der Wartung ist ein trockenes Tuch erlaubt.', source).bestanden


def test_scope_from_an_unrelated_action_in_the_same_source_cannot_be_borrowed():
    source = R508_RULE + ' Für Auftrag R-508 sind Lösungsmittel während der Wartung erlaubt.'
    sentence = 'Für Auftrag R-508 ist während der Wartung ausschließlich ein trockenes Tuch erlaubt.'
    assert not _check(sentence, source).bestanden


def test_scope_in_a_separate_answer_clause_cannot_qualify_a_permission():
    source = R508_RULE + ' Vor der Reinigung werden die Lösungsmittel getrennt gelagert.'
    sentence = ('Vor der Reinigung werden die Lösungsmittel getrennt gelagert und '
                'für Auftrag R-508 sind nur trockene Tücher erlaubt.')
    assert not _check(sentence, source).bestanden


def test_other_case_condition_cannot_be_borrowed_for_the_requested_permission():
    other_case = 'Für Auftrag R-509 ist während der Wartung ausschließlich ein trockenes Tuch erlaubt.'
    borrowed_scope = 'Für Auftrag R-508 ist während der Wartung ausschließlich ein trockenes Tuch erlaubt.'
    assert not _check(borrowed_scope, R508_RULE, other_case).bestanden


class _SentenceModel:
    is_local = True
    name = 'fixture'
    model = 'fixture'

    def complete_json(self, messages, **kwargs):
        return Reply(text=json.dumps({'status': 'antwort', 'saetze': [
            {'text': UNSCOPED_TOWELS, 'belege': [1]},
            {'text': SOLVENT_BAN, 'belege': [1]},
        ]}))


class _AlwaysYesChecker:
    is_local = True
    model = 'qwen3.5:4b'

    def __init__(self):
        self.checked = []

    def complete_json(self, messages, **kwargs):
        self.checked.append(satzpruefung_modell.satz_der_anfrage(messages))
        return Reply(text='{"urteil":"ja"}', model=self.model)


def test_an_always_yes_model_gate_cannot_rescue_a_broadened_permission():
    checker = _AlwaysYesChecker()
    source = AntwortBeleg(
        nummer=1,
        ref={'episode_id': 'episode-r508', 'fingerprint': 'fingerprint', 'start': 0, 'end': len(R508_SOURCE),
             'kind': 'fact'},
        rolle='Quelle',
        episode_id='episode-r508',
        titel='Reinigung R-508',
        kopf='Reinigung R-508.txt',
        text=R508_SOURCE,
        zeit=None,
        pruef_text=R508_SOURCE,
    )
    attempt = formulieren(
        'Darf man R-508 mit Lösungsmittel reinigen?',
        [source],
        _SentenceModel(),
        jetzt=datetime(2026, 10, 8, tzinfo=timezone.utc),
        pruefung=satzpruefung_modell.tor('an', checker),
    )

    assert attempt.status == 'saetze'
    assert [sentence.text for sentence in attempt.saetze] == [SOLVENT_BAN]
    assert [sentence.roh for sentence in attempt.verworfen] == [UNSCOPED_TOWELS]
    assert checker.checked == [SOLVENT_BAN]
