"""Synthetic conditions must survive overconfident block classification."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from icarus_memory.mail_quote_history import guard as history_guard
from icarus_memory.working_memory_conditions import guard


def episode(body):
    return SimpleNamespace(body=body, kind="message", provenance={"source_type": "email"})


def item(body, kind="request", *, text=None):
    text = body if text is None else text
    start = body.index(text)
    return {"start": start, "end": start + len(text), "kind": kind}


@pytest.mark.parametrize("kind", ["request", "commitment"])
@pytest.mark.parametrize("body", [
    "Wenn Sie den Auftrag übernehmen möchten, freuen wir uns über Rückmeldung. "
    "Sollte der Termin nicht passen, können Sie sich ebenfalls melden.",
    "Falls die Freigabe vorliegt, sende ich die Unterlagen.",
    "Sofern die Prüfung abgeschlossen ist, schicken Sie mir bitte die Rechnung.",
    "Sollte der Termin passen, bestätigen Sie ihn bitte.",
    "Sollten Parkgebühren anfallen, übernehmen wir diese.",
    "Wenn die Lieferung kommt,\n\ndann rufe ich an.",
    "Wenn der Entwurf freigegeben ist, sende ich die Rechnung. Nicht vorher.",
])
def test_explicit_condition_cannot_become_an_unconditional_action(body, kind):
    result = guard(episode(body), [item(body, kind)])
    assert result == [{"start": 0, "end": len(body), "kind": "conditional"}]


@pytest.mark.parametrize("body", [
    "Bitte melden Sie sich, falls Sie den Auftrag übernehmen möchten.",
    "Bitte geben Sie Rückmeldung, sofern Sie das Angebot annehmen möchten.",
    "Bitte melden Sie sich, wenn Sie den Auftrag übernehmen möchten.",
    "Bitte melden Sie sich, falls Sie den Auftrag nicht übernehmen möchten.",
])
def test_response_request_keeps_a_postposed_offer_acceptance_condition(body):
    assert guard(episode(body), [item(body)]) == [
        {"start": 0, "end": len(body), "kind": "conditional"}]


@pytest.mark.parametrize("body", [
    "Wenn Sie mir bitte bis Freitag die Rechnung zusenden, wäre ich Ihnen dankbar.",
    "Wenn Sie uns bitte die Rechnung zusenden, wären wir Ihnen sehr dankbar.",
])
def test_polite_request_grammar_does_not_remove_an_unconditional_request(body):
    original = item(body)
    assert guard(episode(body), [original]) == [original]


def test_polite_wording_does_not_erase_a_real_condition_for_a_sender_promise():
    body = "Wenn Sie mir bitte vorab Ihre Zustimmung geben, sende ich die Rechnung."
    assert guard(episode(body), [item(body, "commitment")])[0]["kind"] == "conditional"


def test_complete_offer_block_remains_conditional_despite_nested_clause_and_polite_response():
    body = ("Wenn Sie den konkreten Auftrag übernehmen möchten, freuen wir uns über eine zeitnahe Rückmeldung. "
            "Sollte der genannte Termin für Sie nicht passen, Sie aber grundsätzlich Interesse an weiteren "
            "Aufträgen im Bereich Projektplanung haben, können Sie sich ebenfalls gerne bei uns melden.")
    assert guard(episode(body), [item(body)]) == [
        {"start": 0, "end": len(body), "kind": "conditional"}]


def test_quoted_postposed_offer_wording_inside_a_separate_request_is_not_its_condition():
    body = ("Bitte übernehmen Sie den Satz 'Bitte melden Sie sich, falls Sie den Auftrag übernehmen möchten' "
            "in die Vorlage.")
    original = item(body)
    assert guard(episode(body), [original]) == [original]


@pytest.mark.parametrize("body", [
    "Wenn Sie Fragen haben, rufen Sie mich an.",
    "Falls Sie nicht teilnehmen möchten, müssen Sie nichts zurücksenden.",
    "Wenn Sie keine Fragen haben, ist keine Rückmeldung erforderlich.",
    "Sofern die Freigabe nicht vorliegt, werde ich keine Rechnung senden.",
])
def test_optional_contact_and_negated_conditions_do_not_fabricate_obligations(body):
    assert guard(episode(body), [item(body)])[0]["kind"] == "conditional"


@pytest.mark.parametrize("body", [
    "Wenn Sie am 12. November Zeit haben, bestätigen Sie den Termin bitte.",
    "Falls am 12. November Parkgebühren anfallen, übernehmen wir diese.",
])
def test_a_date_inside_the_antecedent_does_not_hide_the_condition(body):
    assert guard(episode(body), [item(body)])[0]["kind"] == "conditional"


def test_a_sentence_after_a_date_in_the_consequence_stays_independent():
    body = ("Wenn Sie Zeit haben, bestätigen Sie den Termin bis zum 12. "
            "Bitte senden Sie mir die Rechnung in jedem Fall.")
    assert guard(episode(body), [item(body)])[0]["kind"] == "uncertain"


@pytest.mark.parametrize("body,kind", [
    ("Bitte senden Sie mir den Bericht bis Freitag.", "request"),
    ("Bitte rufen Sie heute nicht an.", "request"),
    ("Ich sende Ihnen die Unterlagen bis Freitag.", "commitment"),
    ("Bitte verwenden Sie den Satz 'Wenn Sie Fragen haben' in der Vorlage.", "request"),
    ("Bitte antworten Sie unabhängig davon, ob Sie den Auftrag übernehmen möchten.", "request"),
    ("Bitte senden Sie mir den Bericht, wenn möglich als PDF.", "request"),
    ("Sollte ich mich dazu bereits verpflichtet haben?", "request"),
])
def test_clear_independent_actions_and_embedded_phrases_are_unchanged(body, kind):
    original = item(body, kind)
    assert guard(episode(body), [original]) == [original]


@pytest.mark.parametrize("body", [
    "Wenn Sie den Auftrag übernehmen möchten, melden Sie sich bitte. "
    "Bitte senden Sie mir außerdem die bereits fällige Rechnung.",
    "Bitte senden Sie mir heute die Rechnung. Falls Sie Fragen haben, rufen Sie mich an.",
    "Die Fahrtkosten werden erstattet. Falls Parkgebühren anfallen, übernehmen wir diese.",
    "Wenn Sie kommen können, bestätigen Sie bitte; senden Sie mir die Rechnung unabhängig davon.",
    "Wenn der Termin passt, sagen Sie zu, aber senden Sie die Unterlagen auf jeden Fall.",
])
@pytest.mark.parametrize("kind", ["request", "commitment"])
def test_mixed_scope_is_uncertain_without_splitting_or_rewriting_the_block(body, kind):
    assert guard(episode(body), [item(body, kind)]) == [
        {"start": 0, "end": len(body), "kind": "uncertain"}]


def test_a_condition_does_not_spread_to_an_unrelated_paragraph():
    conditional = "Wenn Sie den Auftrag übernehmen möchten, melden Sie sich bitte."
    independent = "Bitte senden Sie mir die bereits fällige Rechnung bis Freitag."
    body = conditional + "\n\n" + independent
    original = [item(body, text=conditional), item(body, text=independent)]
    result = guard(episode(body), original)
    assert [row["kind"] for row in result] == ["conditional", "request"]
    assert [(row["start"], row["end"]) for row in result] == [
        (0, len(conditional)), (len(conditional) + 2, len(body))]


def test_offer_context_does_not_claim_acceptance_or_reassign_sender_commitments():
    paragraphs = [
        "Wir möchten Ihnen für die Veranstaltung einen Auftrag anbieten.",
        "Für die Durchführung stellen wir Ihnen die Materialien zur Verfügung.",
        "Falls Sie den Auftrag annehmen, erstatten wir die Fahrtkosten.",
        "Bitte teilen Sie uns unabhängig davon Ihre neue Rechnungsadresse mit.",
    ]
    body = "\n\n".join(paragraphs)
    original = [item(body, kind, text=text) for text, kind in zip(
        paragraphs, ["fact", "commitment", "commitment", "request"])]
    assert [row["kind"] for row in guard(episode(body), original)] == [
        "fact", "commitment", "conditional", "request"]


@pytest.mark.parametrize("previous", [
    "Gerne können wir Sie in unseren Mailverteiler aufnehmen.",
    "Wenn Sie möchten, nehmen wir Sie in den Verteiler auf.",
    "Unsere Verteiler haben unterschiedliche Themen. Sie können frei selbst entscheiden, "
    "ob Sie Nachrichten aus einem Verteiler erhalten wollen.",
])
@pytest.mark.parametrize("kind", ["request", "commitment"])
def test_enrollment_details_continue_only_the_direct_explicit_voluntary_list_offer(previous, kind):
    needed = "Für die Aufnahme benötigen wir Ihre E-Mail-Adresse und eine Themenauswahl."
    body = previous + "\n\n" + needed
    original = [item(body, "fact", text=previous), item(body, kind, text=needed)]
    before = deepcopy(original)
    result = guard(episode(body), original)
    assert result == [before[0], dict(before[1], kind="conditional")]
    assert original == before
    assert body[result[1]["start"]:result[1]["end"]] == needed


@pytest.mark.parametrize("previous", [
    "Die Aufnahme in den Sicherheitsverteiler ist für alle Beschäftigten verpflichtend.",
    "Sie müssen sich vor Arbeitsbeginn in diesem Verteiler registrieren.",
    "Sie haben die Aufnahme in den Verteiler bereits bestätigt.",
    "Gerne können wir Sie zu einem kostenlosen Vortrag einladen.",
])
def test_required_confirmed_or_unrelated_registration_does_not_inherit_a_condition(previous):
    needed = "Für die Aufnahme benötigen wir Ihren Namen und die Personalnummer."
    body = previous + "\n\n" + needed
    original = [item(body, "fact", text=previous), item(body, text=needed)]
    assert guard(episode(body), original) == original


def test_list_context_without_explicit_choice_is_uncertain_rather_than_an_invented_opt_in():
    previous = "Wir führen einen Verteiler für Projektmitteilungen."
    needed = "Für die Aufnahme benötigen wir Ihre E-Mail-Adresse."
    body = previous + "\n\n" + needed
    assert guard(episode(body), [item(body, text=needed)]) == [
        dict(item(body, text=needed), kind="uncertain")]


def test_enrollment_offer_does_not_condition_an_independent_follow_up_task():
    previous = "Gerne können wir Sie in unseren Mailverteiler aufnehmen."
    needed = "Bitte senden Sie die fällige Rechnung bis Freitag."
    body = previous + "\n\n" + needed
    original = [item(body, text=needed)]
    assert guard(episode(body), original) == original


def test_enrollment_offer_does_not_skip_an_intervening_paragraph():
    body = ("Gerne können wir Sie in unseren Mailverteiler aufnehmen.\n\n"
            "Der nächste Kurs beginnt am Montag.\n\n"
            "Für die Aufnahme benötigen wir Ihren Namen.")
    needed = "Für die Aufnahme benötigen wir Ihren Namen."
    original = [item(body, text=needed)]
    assert guard(episode(body), original) == original


def test_enrollment_details_and_an_independent_request_share_only_an_uncertain_block():
    previous = "Gerne können wir Sie in unseren Mailverteiler aufnehmen."
    needed = ("Für die Aufnahme benötigen wir Ihre E-Mail-Adresse. "
              "Bitte senden Sie die fällige Rechnung bis Freitag.")
    body = previous + "\n\n" + needed
    assert guard(episode(body), [item(body, text=needed)]) == [
        dict(item(body, text=needed), kind="uncertain")]


def test_historical_list_offer_cannot_condition_a_current_registration_request():
    previous = "Gerne können wir Sie in unseren Mailverteiler aufnehmen."
    needed = "Für die Aufnahme benötigen wir Ihren Namen."
    body = previous + "\n\n" + needed
    original = [item(body, "historical", text=previous), item(body, text=needed)]
    assert guard(episode(body), original) == original


def test_quoted_list_offer_is_not_current_context_even_outside_the_returned_items():
    body = ("Am 6. Juli 2026 schrieb Ada <ada@example.test>:\n\n"
            "> Gerne können wir Sie in unseren Mailverteiler aufnehmen.\n\n"
            "Für die Aufnahme benötigen wir Ihren Namen.")
    needed = "Für die Aufnahme benötigen wir Ihren Namen."
    original = [item(body, text=needed)]
    assert guard(episode(body), original) == original


@pytest.mark.parametrize("body", [
    "Die Anmeldung ist ausschließlich über das Kursportal möglich.",
    "Anmeldung ist nur schriftlich per Formular möglich.",
    "*Registrierung:*\r\nEs ist nur eine digitale Registrierung über das Veranstaltungsportal "
    "\r\n<https://events.example.test/zugang> möglich.",
    "**Anmeldung:**\nEine Anmeldung ist nur online über das Portal möglich.",
    "Die Registrierung ist per E-Mail möglich.",
])
def test_impersonal_registration_route_is_a_fact_not_a_personal_request(body):
    original = item(body)
    assert guard(episode(body), [original]) == [dict(original, kind="fact")]


@pytest.mark.parametrize("body", [
    "Bitte melden Sie sich über das Kursportal an.",
    "Bitte beachten Sie: Die Anmeldung ist nur über das Kursportal möglich.",
    "Sie müssen sich bis Freitag über das Kursportal anmelden.",
    "Die Anmeldung ist verpflichtend und nur über das Kursportal möglich.",
    "Die Anmeldung zum Pflichttermin ist nur über das Kursportal möglich.",
    "Eine Anmeldung ist nur über das Portal möglich. Bitte senden Sie mir die Bestätigung.",
    "Die Anmeldung ist nur über das Portal möglich; senden Sie uns bitte das Formular.",
    "Die Anmeldung ist erforderlich; nur eine Registrierung über das Portal ist möglich.",
])
def test_real_requests_obligations_and_mixed_registration_blocks_are_not_reclassified_as_info(body):
    original = item(body)
    assert guard(episode(body), [original]) == [original]


@pytest.mark.parametrize("body,kind", [
    ("Wir melden Sie verbindlich zum gebuchten Kurs an.", "commitment"),
    ("Ihre Anmeldung ist bestätigt.", "status"),
    ("Die Anmeldung ist ausschließlich über das Kursportal möglich.", "historical"),
    ("Die Anmeldung ist ausschließlich über das Kursportal möglich.", "conditional"),
])
def test_registration_route_rule_does_not_reinterpret_booking_commitments_or_other_kinds(body, kind):
    original = item(body, kind)
    assert guard(episode(body), [original]) == [original]


def test_registration_info_keeps_its_original_offset_and_does_not_hide_other_paragraphs():
    paragraphs = ["Bitte prüfen Sie die Einladung.",
                  "Die Registrierung ist ausschließlich über das Portal möglich.",
                  "Bitte senden Sie die fällige Rechnung."]
    body = "\n\n".join(paragraphs)
    original = [item(body, text=text) for text in paragraphs]
    before = deepcopy(original)
    source = episode(body)
    result = guard(source, original)
    assert result == [before[0], dict(before[1], kind="fact"), before[2]]
    assert original == before and source.body == body
    assert body[result[1]["start"]:result[1]["end"]] == paragraphs[1]


@pytest.mark.parametrize("kind", ["historical", "status", "fact", "uncertain", "irrelevant", "conditional"])
def test_guard_never_promotes_or_reinterprets_non_action_classifications(kind):
    body = "Wenn Sie den Auftrag übernehmen möchten, melden Sie sich bitte."
    original = item(body, kind)
    assert guard(episode(body), [original]) == [original]


def test_quote_history_remains_authoritative_before_condition_preservation():
    current = "Wenn Sie den neuen Auftrag übernehmen möchten, melden Sie sich bitte."
    old = "Wenn Sie den alten Auftrag übernehmen möchten, bestätigen Sie bitte."
    body = (current + "\n\nVon: Ada <ada@example.test>\n"
            "Gesendet: Montag, 6. Juli 2026 09:30\nAn: Bo <bo@example.test>\n"
            "Betreff: Altes Angebot\n\n" + old)
    original = [item(body, text=current), item(body, text=old)]
    assert [row["kind"] for row in guard(episode(body), history_guard(episode(body), original))] == [
        "conditional", "historical"]


def test_original_offsets_source_and_classifications_are_not_mutated():
    text = "Falls die Freigabe nicht vorliegt, sende ich keine Rechnung."
    body = "Vorspann.\r\n\r\n  " + text + "  \r\n\r\nNachsatz."
    source = episode(body)
    original = [dict(item(body, "commitment", text=text), source_label="synthetic")]
    before = deepcopy(original)
    result = guard(source, original)
    assert original == before
    assert source.body == body
    assert result == [dict(before[0], kind="conditional")]
    assert body[result[0]["start"]:result[0]["end"]] == text



@pytest.mark.parametrize('body', [
    'Die Anmeldung ist nur über das Portal möglich. Lade den Ausweis hoch; danach ist die Teilnahme möglich.',
    'Die Anmeldung ist über das Portal möglich. Sende den Beleg bis Freitag; danach ist die Erstattung möglich.',
    'Die Anmeldung ist per Portal möglich; lade den Ausweis hoch, danach ist die Teilnahme möglich.',
    'Die Anmeldung ist über das Portal möglich.Sende den Beleg, danach ist die Erstattung möglich.',
])
def test_route_rule_cannot_swallow_a_following_imperative_even_without_personal_pronoun(body):
    original = item(body)
    assert guard(episode(body), [original]) == [original]


@pytest.mark.parametrize('body', [
    'Die Anmeldung ist über das Portal möglich, sende den Beleg bis Freitag, dann ist die Erstattung möglich.',
    'Die Anmeldung ist nur möglich über https://events.example.test/zugang; lade den Ausweis hoch, danach ist die Teilnahme möglich.',
    'Die Anmeldung ist über das Portal sende den Beleg und bestätige den Auftrag möglich.',
])
def test_procedure_exception_requires_just_a_route_without_additional_action_clauses(body):
    original = item(body)
    assert guard(episode(body), [original]) == [original]
