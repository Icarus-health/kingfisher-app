"""Invoice dates and unresolved choices are not executable payment deadlines."""
from datetime import datetime, timezone
import pytest

from icarus_memory.akten_arten import fristen_finden

REFERENCE = datetime(2099, 10, 1, tzinfo=timezone.utc)


def test_invoice_issue_date_does_not_become_second_payment_deadline():
    body = 'Bitte überweisen Sie 49,00 EUR für die Rechnung vom 20. Oktober 2099 bis zum 30. Oktober 2099.'
    result = fristen_finden(body, REFERENCE)
    assert [r.datum.isoformat() for r in result] == ['2099-10-30']
    assert result[0].satz in body


@pytest.mark.parametrize('body', [
    'Bitte überweisen Sie den Betrag der am 20. Oktober 2099 ausgestellten Rechnung bis zum 30. Oktober 2099.',
    'Bitte überweisen Sie den Betrag der am 20. Oktober 2099 erhaltenen Rechnung bis zum 30. Oktober 2099.',
    'Bitte überweisen Sie den Betrag für die Leistung am 20. Oktober 2099 bis zum 30. Oktober 2099.',
])
def test_issue_or_service_date_with_am_is_not_the_payment_date(body):
    assert [r.datum.isoformat() for r in fristen_finden(body, REFERENCE)] == ['2099-10-30']


@pytest.mark.parametrize('body', [
    'Die Rechnung ist fällig zum 30. Oktober 2099.',
    'Zahlbar: 30. Oktober 2099.',
    'Bitte überweisen Sie den Betrag bis spätestens zum 30. Oktober 2099.',
    'Bitte überweisen Sie den Betrag am 30. Oktober 2099.',
    'Bitte überweisen Sie 49,00 EUR am 30. Oktober 2099.',
    'Der Betrag ist zum 30. Oktober 2099 zu zahlen.',
    'Der Betrag ist am 30. Oktober 2099 zur Zahlung fällig.',
])
def test_unambiguous_payment_forms_stay_supported(body):
    assert [r.datum.isoformat() for r in fristen_finden(body, REFERENCE)] == ['2099-10-30']


def test_unresolved_alternative_dates_do_not_become_two_payment_tasks():
    body = 'Der Betrag ist am 20. Oktober 2099 oder am 30. Oktober 2099 fällig; welche Frist gilt, ist ungeklärt.'
    assert fristen_finden(body, REFERENCE) == []


@pytest.mark.parametrize('wording', ['noch nicht bezahlt', 'unbezahlt'])
def test_unpaid_invoice_is_not_misread_as_completed(wording):
    body = f'Die Rechnung ist {wording}; bitte überweisen Sie 49,00 EUR bis zum 30. Oktober 2099.'
    assert [r.datum.isoformat() for r in fristen_finden(body, REFERENCE)] == ['2099-10-30']


@pytest.mark.parametrize('body', [
    'Falls die Freigabe eintrifft, überweisen Sie bitte 49,00 EUR bis zum 30. Oktober 2099.',
    'Bitte überweisen Sie 49,00 EUR bis zum 30. Oktober 2099, sofern die Rechnung noch nicht bezahlt ist.',
    'Die Rechnung vom 20. Oktober 2099 ist noch zu zahlen.',
])
def test_conditional_or_non_deadline_dates_stay_open_in_original_source(body):
    assert fristen_finden(body, REFERENCE) == []
