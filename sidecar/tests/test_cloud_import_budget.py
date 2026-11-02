"""Synthetic durable accounting only; never grants a personal application budget."""
import concurrent.futures
import importlib
import json
import sqlite3
import threading

import pytest


def module():
    return importlib.import_module('icarus_memory.cloud_import_budget')


def budget(tmp_path, cap=1_000_000):
    ledger = module().MistralSourceBudget(tmp_path / 'budget.sqlite3')
    if cap:
        ledger.set_total_cap(cap, ledger.status()['revision'])
    return ledger


def reserve(ledger, **overrides):
    state = ledger.status()
    arguments = dict(job_id='synthetic-job', model=module().MODEL, context_limit=262144,
                     max_tokens=1200, budget_id=state['budget_id'], revision=state['revision'],
                     price_id=state['price_id'])
    arguments.update(overrides)
    return ledger.reserve(**arguments)


def code(error, expected):
    assert error.value.code == expected
    assert str(error.value) == expected


def test_new_budget_has_zero_authority_and_no_source_data(tmp_path):
    ledger = budget(tmp_path, cap=0)
    state = ledger.status()
    assert state | {} == state
    assert state['provider'] == 'mistral' and state['currency'] == 'USD'
    assert state['cap_microusd'] == state['spent_microusd'] == state['held_microusd'] == 0
    assert state['remaining_microusd'] == 0 and not state['ready']
    assert state['blocked_reason'] == 'budget_exhausted'
    with pytest.raises(module().MistralBudgetError) as error:
        reserve(ledger)
    code(error, 'budget_exhausted')


def test_cas_same_cap_is_idempotent_and_money_is_strict(tmp_path):
    ledger = budget(tmp_path, cap=0)
    first = ledger.status()
    assert ledger.set_total_cap(0, first['revision']) == first
    changed = ledger.set_total_cap(1000, first['revision'])
    assert changed['revision'] == first['revision'] + 1
    with pytest.raises(module().MistralBudgetError) as error:
        ledger.set_total_cap(2000, first['revision'])
    code(error, 'budget_changed')
    for value in (True, 1.0, -1, 1_000_000_001, '1000'):
        with pytest.raises(module().MistralBudgetError):
            ledger.set_total_cap(value, changed['revision'])
    for value in (True, 1.0, '2'):
        with pytest.raises(module().MistralBudgetError):
            ledger.set_total_cap(1000, value)
    assert ledger.set_total_cap(1_000_000_000, changed['revision'])['cap_microusd'] == 1_000_000_000


def test_reserve_rounding_settlement_and_every_followup_is_cumulative(tmp_path):
    ledger = budget(tmp_path)
    request = reserve(ledger)
    state = ledger.status()
    assert state['held_microusd'] == 44046
    assert not state['ready'] and state['blocked_reason'] == 'budget_busy'
    assert ledger.matches(state['budget_id'], state['revision'], state['price_id'])
    ledger.dispatch(request)
    ledger.settle(request, 1, 1, 2)
    assert ledger.status()['spent_microusd'] == 1
    assert ledger.status()['held_microusd'] == 0
    followup = reserve(ledger, job_id='repair')
    ledger.dispatch(followup)
    ledger.settle(followup, 10, 10, 20)
    assert ledger.status()['spent_microusd'] == 10  # ceil(.825) + ceil(8.25)
    assert ledger.status()['remaining_microusd'] == 999990
    with pytest.raises(module().MistralBudgetError):
        ledger.set_total_cap(9, ledger.status()['revision'])


def test_two_independent_connections_admit_only_one_last_cent(tmp_path):
    first = budget(tmp_path, cap=44046)
    second = module().MistralSourceBudget(tmp_path / 'budget.sqlite3')
    barrier = threading.Barrier(2)
    def attempt(ledger):
        barrier.wait()
        try:
            return ('reserved', reserve(ledger))
        except module().MistralBudgetError as error:
            return ('blocked', error.code)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (first, second)))
    assert sorted(result[0] for result in outcomes) == ['blocked', 'reserved']
    assert first.status()['held_microusd'] == 44046


@pytest.mark.parametrize('transition', ['reserved', 'dispatched', 'held'])
def test_restart_conservatively_holds_every_unfinished_request(tmp_path, transition):
    first = budget(tmp_path)
    request = reserve(first)
    if transition != 'reserved':
        first.dispatch(request)
    if transition == 'held':
        first.hold(request)
    restarted = module().MistralSourceBudget(tmp_path / 'budget.sqlite3')
    status = restarted.status()
    assert status['held_microusd'] == 44046 and status['reconciliation_required']
    assert status['blocked_reason'] == 'budget_uncertain'
    changed = restarted.set_total_cap(2_000_000, status['revision'])
    assert not changed['ready'] and changed['reconciliation_required']
    assert not restarted.matches(changed['budget_id'], changed['revision'], changed['price_id'])
    for operation in (lambda: restarted.cancel_unsent(request), lambda: restarted.dispatch(request),
                      lambda: restarted.settle(request, 1, 1, 2), lambda: reserve(restarted)):
        with pytest.raises(module().MistralBudgetError):
            operation()


def test_known_unsent_can_cancel_but_dispatch_cannot_refund_or_retry(tmp_path):
    ledger = budget(tmp_path)
    cancelled = reserve(ledger)
    ledger.cancel_unsent(cancelled)
    assert ledger.status()['held_microusd'] == 0
    for operation in (ledger.cancel_unsent, ledger.dispatch, ledger.hold):
        with pytest.raises(module().MistralBudgetError):
            operation(cancelled)
    request = reserve(ledger)
    ledger.dispatch(request)
    with pytest.raises(module().MistralBudgetError):
        ledger.cancel_unsent(request)
    assert ledger.status()['held_microusd'] == 44046
    ledger.settle(request, 1, 0, 1)
    with pytest.raises(module().MistralBudgetError):
        ledger.settle(request, 1, 0, 1)
    restarted = module().MistralSourceBudget(tmp_path / 'budget.sqlite3')
    assert restarted.status()['spent_microusd'] == 1 and not restarted.status()['reconciliation_required']


@pytest.mark.parametrize('usage', [(True, 1, 2), (1.0, 1, 2), (1, -1, 0), (1, 2, 4),
                                   (262145, 1, 262146), (1, 1201, 1202), (None, 0, 0)])
def test_invalid_usage_stays_fully_reserved_and_blocks_future_traffic(tmp_path, usage):
    ledger = budget(tmp_path)
    request = reserve(ledger)
    ledger.dispatch(request)
    with pytest.raises(module().MistralBudgetError) as error:
        ledger.settle(request, *usage)
    code(error, 'budget_uncertain')
    assert ledger.status()['held_microusd'] == 44046
    assert ledger.status()['reconciliation_required']


def test_cap_revocation_and_expiry_cannot_stop_settling_already_billed_usage(tmp_path, monkeypatch):
    ledger = budget(tmp_path)
    previous = ledger.status()
    request = reserve(ledger)
    ledger.dispatch(request)
    ledger.set_total_cap(44046, previous['revision'])
    assert not ledger.matches(previous['budget_id'], previous['revision'], previous['price_id'])
    monkeypatch.setattr(module(), '_now', lambda: 1_800_000_000)
    ledger.settle(request, 100, 20, 120)
    assert ledger.status()['spent_microusd'] == 30
    assert ledger.status()['blocked_reason'] == 'pricing_changed'


def test_pinned_price_manifest_cannot_silently_change(tmp_path):
    ledger = budget(tmp_path)
    status = ledger.status()
    with sqlite3.connect(tmp_path / 'budget.sqlite3') as connection:
        connection.execute('UPDATE mistral_price_manifests SET input_microusd_per_million=1')
    assert ledger.status()['blocked_reason'] == 'pricing_changed'
    assert not ledger.matches(status['budget_id'], status['revision'], status['price_id'])
    with pytest.raises(module().MistralBudgetError):
        reserve(ledger)


def test_closed_errors_and_durable_rows_never_store_credentials_or_source_text(tmp_path):
    ledger = budget(tmp_path)
    request = reserve(ledger)
    ledger.dispatch(request)
    ledger.hold(request)
    with sqlite3.connect(tmp_path / 'budget.sqlite3') as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        dump = json.dumps({name: connection.execute(f'SELECT * FROM {name}').fetchall() for name, in tables})
    assert 'synthetic-secret' not in dump and 'Synthetic private source' not in dump
    with pytest.raises(ValueError):
        module().MistralBudgetError('synthetic-secret')
