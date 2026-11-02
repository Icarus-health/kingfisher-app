"""Durable, cumulative Mistral source allowance, deliberately outside backups.

Only integer micro-USD are authoritative. A dispatched request can settle once;
ambiguous dispatch is a permanent hold until a future explicit reconciliation.
There is deliberately no reset, refund, manifest-update or reconciliation API.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .providers import ProviderError

MODEL = 'mistral-small-2603'
ENDPOINT = 'https://api.eu.mistral.ai/v1'
PRICE_ID = 'mistral-small-2603-eu-20261102'
PRICE_VALID_UNTIL = '2026-12-02'
# Bundled public regional price verification, 2026-11-02; expiry is midnight UTC.
_PRICE = (PRICE_ID, MODEL, ENDPOINT, 165000, 660000, '2026-11-02', PRICE_VALID_UNTIL)
_PRICE_EXPIRY = 1796169600  # 2026-12-02T00:00:00Z
_MAX_CAP = 1_000_000_000


class MistralBudgetError(ProviderError):
    """Closed public reason only: never provider bodies, inputs or exceptions."""
    CODES = frozenset({'budget_exhausted', 'budget_uncertain', 'budget_busy',
                       'budget_changed', 'budget_unavailable', 'pricing_changed',
                       'credential_changed', 'permission_changed', 'invalid_request',
                       'metadata_unavailable', 'provider_rejected', 'response_invalid',
                       'invalid_transition'})

    def __init__(self, code):
        if code not in self.CODES:
            raise ValueError('Unknown Mistral error code')
        self.code = code
        super().__init__(code)


def _now():
    return time.time()


def _integer(value, minimum=0, maximum=2**31 - 1):
    return type(value) is int and minimum <= value <= maximum


def _cost(prompt, completion):
    return (prompt * _PRICE[3] + completion * _PRICE[4] + 999999) // 1000000


class MistralSourceBudget:
    """Construct once per app. Reconstructing conservatively holds unfinished rows.

    Every operation opens an independent SQLite connection. BEGIN IMMEDIATE is
    the admission lock across instances and processes, not a Python mutex.
    """
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._transaction() as connection:
                connection.execute('''CREATE TABLE IF NOT EXISTS mistral_budget (
                    id TEXT PRIMARY KEY, cap_microusd INTEGER NOT NULL DEFAULT 0
                      CHECK(typeof(cap_microusd)='integer' AND cap_microusd BETWEEN 0 AND 1000000000),
                    revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=1),
                    created_at REAL NOT NULL, updated_at REAL NOT NULL)''')
                connection.execute('''CREATE TABLE IF NOT EXISTS mistral_price_manifests (
                    id TEXT PRIMARY KEY, model TEXT NOT NULL, endpoint TEXT NOT NULL,
                    input_microusd_per_million INTEGER NOT NULL,
                    output_microusd_per_million INTEGER NOT NULL,
                    verified_at TEXT NOT NULL, valid_until TEXT NOT NULL)''')
                connection.execute('''CREATE TABLE IF NOT EXISTS mistral_reservations (
                    id TEXT PRIMARY KEY, budget_id TEXT NOT NULL REFERENCES mistral_budget(id),
                    job_id TEXT NOT NULL, price_id TEXT NOT NULL REFERENCES mistral_price_manifests(id),
                    model TEXT NOT NULL, context_limit INTEGER NOT NULL CHECK(context_limit>0),
                    requested_max_tokens INTEGER NOT NULL CHECK(requested_max_tokens BETWEEN 64 AND 1200),
                    reserved_microusd INTEGER NOT NULL CHECK(typeof(reserved_microusd)='integer' AND reserved_microusd>=0),
                    settled_microusd INTEGER CHECK(settled_microusd IS NULL OR
                      (typeof(settled_microusd)='integer' AND settled_microusd>=0)),
                    state TEXT NOT NULL CHECK(state IN ('reserved','dispatched','held','settled','cancelled')),
                    prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL)''')
                connection.execute('CREATE INDEX IF NOT EXISTS mistral_reservations_state ON mistral_reservations(budget_id,state)')
                connection.execute('CREATE INDEX IF NOT EXISTS mistral_reservations_job ON mistral_reservations(job_id)')
                now = _now()
                if not connection.execute('SELECT 1 FROM mistral_budget').fetchone():
                    connection.execute('INSERT INTO mistral_budget VALUES (?,0,1,?,?)',
                                       (uuid.uuid4().hex, now, now))
                connection.execute('INSERT OR IGNORE INTO mistral_price_manifests VALUES (?,?,?,?,?,?,?)', _PRICE)
                connection.execute("UPDATE mistral_reservations SET state='held',updated_at=? WHERE state IN ('reserved','dispatched')", (now,))
        except OSError:
            raise MistralBudgetError('budget_unavailable') from None

    @contextmanager
    def _transaction(self):
        connection = None
        try:
            connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except sqlite3.Error:
            if connection is not None:
                connection.rollback()
            raise MistralBudgetError('budget_unavailable') from None
        except BaseException:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def _status(self, connection):
        budgets = connection.execute('SELECT * FROM mistral_budget').fetchall()
        if len(budgets) != 1:
            raise MistralBudgetError('budget_unavailable')
        budget = budgets[0]
        price = connection.execute('SELECT * FROM mistral_price_manifests').fetchall()
        pricing_valid = len(price) == 1 and tuple(price[0]) == _PRICE and _now() < _PRICE_EXPIRY
        totals = connection.execute('''SELECT
            COALESCE(SUM(CASE WHEN state='settled' THEN settled_microusd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN state IN ('reserved','dispatched','held') THEN reserved_microusd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN state='held' THEN 1 ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN state IN ('reserved','dispatched') THEN 1 ELSE 0 END),0)
            FROM mistral_reservations WHERE budget_id=?''', (budget['id'],)).fetchone()
        spent, held, uncertain, busy = totals
        remaining = budget['cap_microusd'] - spent - held
        if remaining < 0:
            raise MistralBudgetError('budget_unavailable')
        reason = ('budget_uncertain' if uncertain else 'pricing_changed' if not pricing_valid else
                  'budget_busy' if busy else 'budget_exhausted' if remaining == 0 else None)
        return dict(provider='mistral', currency='USD', budget_id=budget['id'], revision=budget['revision'],
                    price_id=PRICE_ID, price_valid_until=PRICE_VALID_UNTIL,
                    cap_microusd=budget['cap_microusd'], spent_microusd=spent,
                    held_microusd=held, remaining_microusd=remaining,
                    reconciliation_required=bool(uncertain), ready=reason is None, blocked_reason=reason)

    def status(self):
        with self._transaction() as connection:
            return self._status(connection)

    def set_total_cap(self, cap_microusd, expected_revision):
        if not _integer(cap_microusd, maximum=_MAX_CAP) or not _integer(expected_revision, minimum=1):
            raise MistralBudgetError('invalid_request')
        with self._transaction() as connection:
            state = self._status(connection)
            if state['revision'] != expected_revision:
                raise MistralBudgetError('budget_changed')
            if cap_microusd < state['spent_microusd'] + state['held_microusd']:
                raise MistralBudgetError('budget_exhausted')
            if cap_microusd != state['cap_microusd']:
                connection.execute('UPDATE mistral_budget SET cap_microusd=?,revision=revision+1,updated_at=? WHERE id=?',
                                   (cap_microusd, _now(), state['budget_id']))
            return self._status(connection)

    @staticmethod
    def _matches(state, budget_id, revision, price_id):
        return (type(budget_id) is str and type(revision) is int and type(price_id) is str
                and state['budget_id'] == budget_id and state['revision'] == revision
                and state['price_id'] == price_id
                and state['blocked_reason'] not in {'budget_uncertain', 'pricing_changed'})

    def matches(self, budget_id, revision, price_id):
        # A request's own reserved/dispatched amount must not revoke its callback.
        with self._transaction() as connection:
            return self._matches(self._status(connection), budget_id, revision, price_id)

    def reserve(self, job_id, model, context_limit, max_tokens, *, budget_id, revision, price_id):
        if (model != MODEL or not _integer(context_limit, minimum=1)
                or not _integer(max_tokens, minimum=64, maximum=1200)
                or type(job_id) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,128}', job_id) is None):
            raise MistralBudgetError('invalid_request')
        with self._transaction() as connection:
            state = self._status(connection)
            if not self._matches(state, budget_id, revision, price_id):
                raise MistralBudgetError(state['blocked_reason'] if state['blocked_reason'] in
                                         {'budget_uncertain', 'pricing_changed'} else 'budget_changed')
            if state['blocked_reason'] is not None:
                raise MistralBudgetError(state['blocked_reason'])
            amount = _cost(context_limit, max_tokens)
            if amount > state['remaining_microusd']:
                raise MistralBudgetError('budget_exhausted')
            reservation = uuid.uuid4().hex
            now = _now()
            connection.execute('''INSERT INTO mistral_reservations
                (id,budget_id,job_id,price_id,model,context_limit,requested_max_tokens,
                 reserved_microusd,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,'reserved',?,?)''',
                               (reservation, budget_id, job_id, price_id, model, context_limit,
                                max_tokens, amount, now, now))
            return reservation

    @staticmethod
    def _row(connection, reservation):
        if type(reservation) is not str:
            raise MistralBudgetError('invalid_transition')
        row = connection.execute('SELECT * FROM mistral_reservations WHERE id=?', (reservation,)).fetchone()
        if row is None:
            raise MistralBudgetError('invalid_transition')
        return row

    def _transition(self, reservation, allowed, target):
        with self._transaction() as connection:
            row = self._row(connection, reservation)
            if row['state'] not in allowed:
                raise MistralBudgetError('invalid_transition')
            connection.execute('UPDATE mistral_reservations SET state=?,updated_at=? WHERE id=?',
                               (target, _now(), reservation))

    def dispatch(self, reservation):
        self._transition(reservation, {'reserved'}, 'dispatched')

    def cancel_unsent(self, reservation):
        self._transition(reservation, {'reserved'}, 'cancelled')

    def hold(self, reservation):
        self._transition(reservation, {'reserved', 'dispatched', 'held'}, 'held')

    def settle(self, reservation, prompt_tokens, completion_tokens, total_tokens):
        invalid = False
        with self._transaction() as connection:
            row = self._row(connection, reservation)
            if row['state'] != 'dispatched':
                raise MistralBudgetError('invalid_transition')
            valid = (all(_integer(value) for value in (prompt_tokens, completion_tokens, total_tokens))
                     and prompt_tokens + completion_tokens == total_tokens
                     and prompt_tokens <= row['context_limit']
                     and completion_tokens <= row['requested_max_tokens'])
            amount = _cost(prompt_tokens, completion_tokens) if valid else None
            if not valid or amount > row['reserved_microusd']:
                connection.execute("UPDATE mistral_reservations SET state='held',updated_at=? WHERE id=?",
                                   (_now(), reservation))
                invalid = True
            else:
                # No current permission/revision/expiry check: observed billing
                # remains real after revocation; content admission is separate.
                connection.execute('''UPDATE mistral_reservations SET state='settled',settled_microusd=?,
                    prompt_tokens=?,completion_tokens=?,total_tokens=?,updated_at=? WHERE id=?''',
                                   (amount, prompt_tokens, completion_tokens, total_tokens, _now(), reservation))
        if invalid:
            raise MistralBudgetError('budget_uncertain')
