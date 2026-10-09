"""A bounded ban before acceptance must not override the later written-order rule."""
import copy
import json
from datetime import datetime, timezone

from icarus_memory import satzpruefung_modell, working_memory_answers
from icarus_memory.providers import Reply
from icarus_memory.satzantwort import AntwortBeleg, formulieren
from icarus_memory.satzpruefung import (Beleg, Satz, _bedingung_verloren, bedingte_regeln,
                                        bedingte_regeln_fuer_antwort, satz_pruefen)
from tests.test_bezuege import welt
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _conversation, _upload
from tests.test_working_memory_flow import run_working


PRE_BAN = 'Die Steuerung darf bis zur formellen Abnahme nicht zurückgesetzt werden.'
ARCHIVE = 'Nach der Abnahme wird das Messprotokoll archiviert.'
POST_RULE = ('Ein Zurücksetzen nach der Abnahme ist nur zulässig, wenn die '
             'diensthabende Technikerin es schriftlich anordnet.')
IA08_SOURCE = f'{PRE_BAN} {ARCHIVE} {POST_RULE}'
QUESTION = 'Ist ein Zurücksetzen nach der formellen Abnahme automatisch erlaubt?'
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def _check(sentence, source=IA08_SOURCE):
    evidence = {'1': Beleg('1', source)}
    return satz_pruefen(Satz(sentence, ('1',)), evidence)


def test_exact_post_acceptance_rule_survives_unrelated_preacceptance_negation():
    assert _check(PRE_BAN).bestanden
    assert _check(POST_RULE).bestanden


def test_same_window_prohibition_still_blocks_the_written_order_rule():
    source = ('Nach der Abnahme darf die Steuerung nicht zurückgesetzt werden. '
              + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_same_clause_negation_still_blocks_a_positive_rewrite():
    source = 'Die Steuerung darf nicht zurückgesetzt werden.'
    assert not _check('Die Steuerung darf zurückgesetzt werden.', source).bestanden


def test_same_postacceptance_window_prohibition_still_blocks_positive_rule():
    source = ('Nach der Abnahme darf die Steuerung nicht zurückgesetzt werden. '
              + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_bounded_negation_in_another_source_cannot_be_overridden_by_exact_rule():
    sources = {'1': Beleg('1', PRE_BAN), '2': Beleg('2', POST_RULE)}
    verdict = satz_pruefen(Satz(POST_RULE, ('1', '2')), sources)
    assert not verdict.bestanden


def test_boundary_exception_requires_the_same_event_wording():
    source = (PRE_BAN + ' Ein Zurücksetzen nach der Wartung ist nur zulässig, '
              'wenn die diensthabende Technikerin es schriftlich anordnet.')
    sentence = 'Ein Zurücksetzen nach der Wartung ist nur zulässig, wenn die diensthabende Technikerin es schriftlich anordnet.'
    assert not _check(sentence, source).bestanden


def test_negation_that_already_applies_after_the_same_event_is_not_waived():
    source = ('Nach der Abnahme und bis zum Prüfende darf die Steuerung nicht zurückgesetzt werden. '
              + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_boundary_on_unrelated_coordinated_action_does_not_bound_the_reset_ban():
    source = ('Die Steuerung darf nicht zurückgesetzt werden und das Messprotokoll bleibt gesperrt '
              'bis zur formellen Abnahme. ' + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_another_action_after_a_different_event_does_not_bound_the_reset_ban():
    source = ('Die Steuerung darf nach der Freigabe nicht zurückgesetzt werden und '
              'das Messprotokoll bleibt gesperrt bis zur formellen Abnahme. ' + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_boundary_for_a_different_object_does_not_bound_the_reset_ban():
    source = ('Die Steuerung darf bis zur formellen Abnahme des Messprotokolls nicht zurückgesetzt werden. '
              'Ein Zurücksetzen nach der formellen Abnahme der Steuerung ist nur zulässig, wenn die '
              'diensthabende Technikerin es schriftlich anordnet.')
    sentence = ('Ein Zurücksetzen nach der formellen Abnahme der Steuerung ist nur zulässig, wenn die '
                'diensthabende Technikerin es schriftlich anordnet.')
    assert not _check(sentence, source).bestanden


def test_unparsed_relative_boundary_qualification_fails_closed():
    source = ('Die Steuerung darf bis zur Abnahme, die im Prüfprotokoll dokumentiert ist, '
              'nicht zurückgesetzt werden. ' + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_relative_qualification_of_the_positive_boundary_fails_closed():
    post = ('Ein Zurücksetzen nach der formellen Abnahme, die das Messprotokoll betrifft, '
            'ist nur zulässig, wenn die diensthabende Technikerin es schriftlich anordnet.')
    assert not _check(post, PRE_BAN + ' ' + post).bestanden


def test_boundary_from_an_alternative_action_clause_is_not_borrowed():
    source = ('Die Steuerung darf nicht zurückgesetzt werden oder das Messprotokoll bleibt gesperrt '
              'bis zur formellen Abnahme. ' + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_one_bounded_negative_clause_does_not_waive_another_unbounded_clause():
    source = ('Die Steuerung darf nicht zurückgesetzt werden und das Messprotokoll darf bis zur '
              'formellen Abnahme nicht freigegeben werden. ' + POST_RULE)
    assert not _check(POST_RULE, source).bestanden


def test_different_explicit_acceptance_adjectives_are_not_the_same_boundary():
    source = ('Bis zur vorläufigen Abnahme darf die Steuerung nicht zurückgesetzt werden. '
              'Ein Zurücksetzen nach der endgültigen Abnahme ist nur zulässig, wenn die '
              'diensthabende Technikerin es schriftlich anordnet.')
    sentence = ('Ein Zurücksetzen nach der endgültigen Abnahme ist nur zulässig, wenn die '
                'diensthabende Technikerin es schriftlich anordnet.')
    assert not _check(sentence, source).bestanden


def test_embedded_quoted_permission_does_not_create_an_exact_clause_exception():
    quoted = f'Der Bericht zitiert: „{POST_RULE}“.'
    source = f'{PRE_BAN} {quoted}'
    assert not _check(POST_RULE, source).bestanden


def test_matching_explicit_boundary_adjectives_allow_the_separate_post_rule():
    source = ('Bis zur formellen Abnahme darf die Steuerung nicht zurückgesetzt werden. '
              'Ein Zurücksetzen nach der formellen Abnahme ist nur zulässig, wenn die '
              'diensthabende Technikerin es schriftlich anordnet.')
    sentence = ('Ein Zurücksetzen nach der formellen Abnahme ist nur zulässig, wenn die '
                'diensthabende Technikerin es schriftlich anordnet.')
    assert _check(sentence, source).bestanden


def test_written_order_condition_cannot_be_changed_or_removed():
    fabricated = ('Ein Zurücksetzen nach der Abnahme ist nur zulässig, wenn der '
                  'diensthabende Techniker es mündlich anordnet.')
    unconditional = 'Ein Zurücksetzen nach der Abnahme ist erlaubt.'
    assert not _check(fabricated).bestanden
    assert not _check(unconditional).bestanden


def test_new_coverage_rule_form_does_not_change_existing_passive_rule_api():
    evidence = Beleg('1', IA08_SOURCE)
    assert bedingte_regeln(IA08_SOURCE) == ()
    assert POST_RULE.lower().rstrip('.') in bedingte_regeln_fuer_antwort(IA08_SOURCE)
    # The answer path fails closed for any paraphrase when a cited source has
    # a recognized conditional permission rule; quote fallback preserves it.
    assert _bedingung_verloren('Das Messprotokoll wird nach der Abnahme archiviert.', [evidence])


def test_conditional_permission_source_requires_literal_answer_sentences():
    evidence = [Beleg('1', IA08_SOURCE)]
    for paraphrase in ('Es darf zurückgesetzt werden.', 'Es ist zulässig.',
                       'Ein Zurücksetzen ist erfolgt.'):
        assert _bedingung_verloren(paraphrase, evidence), paraphrase
    assert _bedingung_verloren(POST_RULE, evidence) is None


class _SentenceModel:
    is_local = True
    name = model = 'synthetic-answer'

    def __init__(self, sentences=None):
        self.sentences = sentences or [PRE_BAN, POST_RULE]

    def complete_json(self, messages, **kwargs):
        return Reply(text=json.dumps({'status': 'antwort', 'saetze': [
            {'text': sentence, 'belege': [1]} for sentence in self.sentences
        ]}))


class _Checker:
    is_local = True
    model = 'synthetic-checker'

    def __init__(self, reject=None):
        self.reject = reject
        self.checked = []

    def complete_json(self, messages, **kwargs):
        request = json.loads(messages[-1]['content'])
        sentence = request['satz']
        self.checked.append(sentence)
        verdict = 'nein' if self.reject and sentence == self.reject else 'ja'
        return Reply(text=json.dumps({'urteil': verdict}), model=self.model)


def _answer_evidence():
    return AntwortBeleg(
        nummer=1,
        ref={'episode_id': 'episode-ia08', 'fingerprint': 'fingerprint', 'start': 0,
             'end': len(IA08_SOURCE), 'kind': 'fact'},
        rolle='Quelle', episode_id='episode-ia08', titel='Abnahme', kopf='Abnahme.txt',
        text=IA08_SOURCE, zeit=None, pruef_text=IA08_SOURCE)


def test_always_yes_gate_cannot_hide_same_paragraph_status():
    checker = _Checker()
    result = formulieren(QUESTION, [_answer_evidence()], _SentenceModel(), jetzt=NOW,
                         pruefung=satzpruefung_modell.tor('an', checker))

    assert result.status == 'zitate'
    assert checker.checked == [PRE_BAN, POST_RULE]


def test_always_yes_gate_keeps_the_complete_original_paragraph():
    checker = _Checker()
    result = formulieren(QUESTION, [_answer_evidence()], _SentenceModel([IA08_SOURCE]), jetzt=NOW,
                         pruefung=satzpruefung_modell.tor('an', checker))
    assert result.status == 'saetze'
    assert [sentence.text for sentence in result.saetze] == [IA08_SOURCE]
    assert checker.checked == [IA08_SOURCE]


def test_rejecting_second_gate_falls_back_when_it_drops_the_governing_rule():
    checker = _Checker(reject=POST_RULE)
    result = formulieren(QUESTION, [_answer_evidence()], _SentenceModel(), jetzt=NOW,
                         pruefung=satzpruefung_modell.tor('an', checker))

    assert checker.checked == [PRE_BAN, POST_RULE]
    assert result.status == 'zitate'
    assert 'vollständige sichtbare Originalstelle' in result.grund
    assert any(sentence.roh == POST_RULE for sentence in result.verworfen)


def _script_provider(provider, sentences=None):
    def complete_json(messages, *, max_tokens=256, schema=None):
        data = json.loads(messages[-1]['content'])
        if 'blocks' in data:
            return Reply(text=json.dumps({'items': [
                {'block_id': block['block_id'], 'kind': 'conditional'} for block in data['blocks']]}))
        if 'sources' in data:
            return Reply(text=json.dumps({'status': 'reports', 'ids': [row['id'] for row in data['sources']]}))
        if 'anliegen' in data:
            return Reply(text=json.dumps({'status': 'antwort', 'saetze': [
                {'text': sentence, 'belege': [1]} for sentence in (sentences or [PRE_BAN, POST_RULE])]}))
        raise AssertionError(f'unexpected synthetic provider request: {list(data)}')
    provider.complete_json = complete_json


def test_uploaded_http_answer_and_saved_projection_keep_post_acceptance_condition(
        core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    app.state.agent._working_memory_search = None
    _script_provider(provider, sentences=[IA08_SOURCE])
    try:
        source_id = _upload(client, IA08_SOURCE)
        run_working(app)
        conversation = _conversation(client)
        response = client.post(
            f'/api/v1/conversations/{conversation}/messages',
            json={'message': QUESTION, 'answer_mode': 'memory_evidence', 'new_question': True})
        assert response.status_code == 201, response.text
        assistant = response.json()['messages'][-1]
        context = assistant['metadata']['context']
        assert context['answer_contract']['status'] == 'working_reports'
        assert context['working_answer']['refs'][0]['episode_id'] == source_id
        assert PRE_BAN in assistant['content'] and POST_RULE in assistant['content']

        # Reloading projects the saved answer in this same app; actual store
        # reopen is covered separately by the paragraph-context tests.
        reopened = client.get(f'/api/v1/conversations/{conversation}')
        assert reopened.status_code == 200
        projected = reopened.json()['messages'][-1]
        assert PRE_BAN in projected['content'] and POST_RULE in projected['content']
        assert projected['metadata']['context']['answer_contract']['status'] == 'working_reports'

        # A legacy snapshot that had dropped the rejected rule must no longer look complete.
        legacy = copy.deepcopy(assistant)
        stored = legacy['metadata']['context']['working_answer']['satzantwort']
        stored['saetze'][0].update(roh=PRE_BAN, text=PRE_BAN)
        stored['verworfen'] = 1
        projected_legacy = working_memory_answers.project_message(
            legacy, app.state.episodes, app.state.claims)
        assert projected_legacy['metadata']['context']['answer_contract']['status'] == 'working_reports'
        assert IA08_SOURCE in projected_legacy['content']
    finally:
        client.close()
        _close_app(app)
