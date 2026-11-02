#!/usr/bin/env python3
"""Explicit <=1 USD artificial-only Mistral EU source-package preparation.

No default cloud authority and no application startup, saved credentials or
personal data paths. Source jobs classify working-memory blocks and optional
persons/categories; they do not run task extraction/review or deadline checks.
Consequently this runner can never return a full quality pass or CLI exit 0.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import uuid

import httpx

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.cloud_import_budget import ENDPOINT, MODEL, MistralBudgetError, MistralSourceBudget
from icarus_memory.cloud_memory import CloudMemoryJobs
from icarus_memory.mistral_import_provider import MistralImportProvider
from probe_intake_precision import CASES

KEY_ENV = 'KINGFISHER_ARTIFICIAL_MISTRAL_API_KEY'
_DATASET_SHA256 = '5d1d15390f03db316d534d5fa339c7f7f04a3678b7839810ecbbac137db8aadc'
_CASE_IDS = ('optional-portal', 'optional-direct', 'explicit-deadline', 'newsletter',
             'mixed', 'appointment-versus-deadline', 'distinct-people')
_MAX_REQUESTS = 21  # Seven classifications + seven category calls + bounded evidence repairs.
_MAX_SECONDS = 600
_IO_TIMEOUT = 30


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _validate(allow_artificial_cloud, cap_microusd, max_requests, seconds):
    # All authorization and frozen-scope checks precede even a temporary store.
    if allow_artificial_cloud is not True:
        raise ValueError('Explicit artificial cloud approval is required')
    if type(cap_microusd) is not int or not 1 <= cap_microusd <= 1_000_000:
        raise ValueError('An explicit integer cap between 1 and 1000000 micro-USD is required')
    if (type(max_requests) is not int or not 1 <= max_requests <= _MAX_REQUESTS
            or type(seconds) not in {int, float} or not 0 < seconds <= _MAX_SECONDS):
        raise ValueError('Invalid artificial request or time bound')
    if (tuple(case['id'] for case in CASES) != _CASE_IDS or _digest(CASES) != _DATASET_SHA256
            or any(case['source_ref'] != 'synthetic-' + case['id'] + '@example.invalid' for case in CASES)):
        raise ValueError('The seven frozen artificial originals have changed')
    key = os.environ.get(KEY_ENV)
    if not isinstance(key, str) or not key.strip():
        raise ValueError('The dedicated artificial Mistral key is required')
    return key


class _BoundedStream(httpx.SyncByteStream):
    def __init__(self, stream, guard):
        self.stream, self.guard = stream, guard

    def __iter__(self):
        for chunk in self.stream:
            self.guard()
            yield chunk

    def close(self):
        self.stream.close()


class _Transport(httpx.BaseTransport):
    def __init__(self, run, transport):
        self.run, self.transport = run, transport

    def handle_request(self, request):
        self.run.guard()
        target = str(request.url)
        expected = {'GET': ENDPOINT + '/models', 'POST': ENDPOINT + '/chat/completions'}
        if expected.get(request.method) != target:
            raise MistralBudgetError('invalid_request')
        if request.method == 'POST':
            if self.run.posts >= self.run.max_requests:
                raise MistralBudgetError('permission_changed')
            self.run.posts += 1
        else:
            if self.run.gets:
                raise MistralBudgetError('metadata_unavailable')
            self.run.gets += 1
        # Finite per-I/O phase timeout, additionally checked against the run
        # deadline before dispatch and on each received chunk. No SDK retries.
        timeout = min(_IO_TIMEOUT, max(0.001, self.run.deadline - time.monotonic()))
        request.extensions['timeout'] = dict(connect=timeout, read=timeout, write=timeout, pool=timeout)
        response = self.transport.handle_request(request)
        response.stream = _BoundedStream(response.stream, self.run.guard)
        return response

    def close(self):
        self.transport.close()


class _Run:
    def __init__(self, episodes, originals, key, max_requests, seconds, transport):
        self.episodes, self.originals, self.key = episodes, originals, key
        self.max_requests, self.deadline = max_requests, time.monotonic() + seconds
        self.transport, self.posts, self.gets = transport, 0, 0
        self.revision = uuid.uuid4().hex

    def intact(self):
        with self.episodes._lock:
            ids = {row[0] for row in self.episodes._conn.execute('SELECT id FROM episodes')}
            return (ids == set(self.originals) and len(ids) == 7
                    and all(self.episodes.get(identifier).to_dict() == original
                            for identifier, original in self.originals.items()))

    def current(self):
        return (time.monotonic() < self.deadline and self.intact()
                and os.environ.get(KEY_ENV) == self.key)

    def guard(self):
        if not self.current():
            raise MistralBudgetError('permission_changed')

    def credential(self, identifier):
        return {'available': identifier == 'mistral' and self.current(), 'model': MODEL,
                'credential_revision': self.revision}


class _Provider(MistralImportProvider):
    """Adds runner bounds around the unchanged real source transport/ledger."""
    def __init__(self, *args, run, **kwargs):
        self.run = run
        super().__init__(*args, **kwargs)

    def _client(self):
        transport = (self.run.transport if self.run.transport is not None
                     else httpx.HTTPTransport(retries=0, trust_env=False))
        return httpx.Client(transport=_Transport(self.run, transport), timeout=_IO_TIMEOUT,
                            trust_env=False, follow_redirects=False)

    def complete_json_guarded(self, *args, **kwargs):
        self.run.guard()
        if self.run.posts >= self.run.max_requests:
            # Stop before creating or dispatching an unaffordable extra request.
            raise MistralBudgetError('permission_changed')
        return super().complete_json_guarded(*args, **kwargs)


def _accounting(path):
    # Read only this run's explicitly created temporary ledger. Its verified
    # manifest and settled numeric usage are authoritative, never guessed rates
    # or token counts inferred from text length.
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        manifest = dict(connection.execute('SELECT * FROM mistral_price_manifests').fetchone())
        rows = [dict(row) for row in connection.execute('SELECT * FROM mistral_reservations')]
    settled = [row for row in rows if row['state'] == 'settled']
    return {'manifest': manifest,
            'verified_context_limits': sorted({row['context_limit'] for row in rows}),
            'usage': {key: sum(row[key] for row in settled)
                      for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
            'usage_complete': len(settled) == len(rows),
            'reservations': [{key: row[key] for key in ('state', 'context_limit', 'requested_max_tokens',
                              'reserved_microusd', 'settled_microusd', 'prompt_tokens',
                              'completion_tokens', 'total_tokens')} for row in rows]}


def evaluate(*, allow_artificial_cloud=False, cap_microusd=None, max_requests=_MAX_REQUESTS,
             seconds=_MAX_SECONDS, _http_transport=None):
    """Run the exact seven originals through real CloudMemoryJobs preview/start.

    `_http_transport` is solely an injected HTTP test boundary; its presence is
    explicit in the report and cannot certify a live model. No provider, main
    store, credential file, data-directory or arbitrary source input is accepted.
    """
    key = _validate(allow_artificial_cloud, cap_microusd, max_requests, seconds)
    if _http_transport is not None and not isinstance(_http_transport, httpx.BaseTransport):
        raise ValueError('An injected HTTP transport must be a bounded test transport')
    started = time.monotonic()
    report = dict(status='incomplete', quality_status='incomplete', execution_status='incomplete',
                  synthetic_only=True, injected_http=_http_transport is not None,
                  live_model_verified=False, original_store='temporary', model=MODEL, endpoint=ENDPOINT,
                  dataset_sha256=_DATASET_SHA256, tasks='not_evaluated', deadlines='not_evaluated',
                  max_requests=max_requests, max_seconds=seconds, io_timeout_seconds=_IO_TIMEOUT)
    with tempfile.TemporaryDirectory(prefix='kf-mistral-artificial-') as temporary:
        directory = Path(temporary)
        episodes = EpisodeStore(directory / 'artificial-originals.sqlite3')
        originals, selected = {}, []
        jobs = run = job_id = budget = None
        try:
            for case in CASES:
                source, created = episodes.record(EpisodeKind.MESSAGE, 'Künstliche Gedächtnisprüfung', case['body'],
                    Provenance(SourceType.EMAIL, source_ref=case['source_ref']),
                    occurred_at=datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
                if not created or source.id in originals:
                    raise ValueError('Artificial originals must be exactly seven unique sources')
                originals[source.id] = source.to_dict()
                selected.append((case, source.id))
            run = _Run(episodes, originals, key, max_requests, seconds, _http_transport)
            run.guard()
            budget = MistralSourceBudget(directory / 'mistral-source-budget.sqlite3')
            budget.set_total_cap(cap_microusd, budget.status()['revision'])

            def factory(identifier, model, **binding):
                run.guard()
                if identifier != 'mistral' or model != MODEL:
                    raise ValueError('Only the pinned artificial Mistral source model is permitted')
                return _Provider(model, key, run.revision,
                    lambda: run.revision if run.current() else None,
                    budget=budget, run=run, **binding)

            def no_fallback(*_args):
                raise ValueError('No alternate artificial provider is permitted')

            jobs = CloudMemoryJobs(episodes, directory / 'artificial-jobs.sqlite3', no_fallback, lambda: {},
                                  api_provider_factory=factory, credential_status=run.credential,
                                  mistral_budget=budget)
            ids = [identifier for _, identifier in selected]
            preview = jobs.preview(source_ids=ids, provider='mistral')
            if preview['count'] != 7 or {row['id'] for row in preview['sources']} != set(ids):
                raise ValueError('Artificial preview must bind exactly seven original IDs')
            run.guard()
            job_id = jobs.start(preview['preview_id'], MODEL, True, source_ids=ids, provider='mistral')['job']['id']
            worker = jobs._threads[job_id]
            while worker.is_alive():
                if time.monotonic() >= run.deadline:
                    jobs.pause(job_id, revoke=True)
                worker.join(0.05)
        except (Exception, KeyboardInterrupt) as exc:
            report['error'] = type(exc).__name__
        finally:
            # Revoke and finish a dispatched, bounded request before closing or
            # deleting this run's store. Never resume/retry an incomplete job.
            if jobs is not None and job_id is not None:
                worker = jobs._threads[job_id]
                if worker.is_alive():
                    jobs.pause(job_id, revoke=True)
                    worker.join()
                report['job'] = jobs.status(job_id)['job']
            report['results'] = []
            for case, identifier in selected:
                classified = jobs.categories.list_for(identifier) if jobs is not None else {'categories': [], 'entities': []}
                names = sorted({row['name'] for row in classified['entities'] if row['kind'] == 'person'})
                topics = {row['id'] for row in classified['categories']}
                checks = {'persons': names == case['persons'],
                          'categories': set(case['required_topics']).issubset(topics)
                                        and not set(case['forbidden_topics']) & topics}
                report['results'].append({'id': case['id'], 'source_id': identifier,
                    'source_sha256': _digest(originals[identifier]),
                    'body_sha256': hashlib.sha256(case['body'].encode()).hexdigest(),
                    'person_names': names, 'topics': sorted(topics), 'checks': checks,
                    'working_memory_state': jobs.memory.source_state(identifier) if jobs is not None else 'pending',
                    'original_unchanged': episodes.get(identifier).to_dict() == originals[identifier]})
            report.update(source_ids=[identifier for _, identifier in selected], selected_source_count=len(selected),
                          original_count=episodes._conn.execute('SELECT COUNT(*) FROM episodes').fetchone()[0],
                          originals_unchanged=bool(run is not None and run.intact()),
                          inference_requests=run.posts if run else 0, metadata_requests=run.gets if run else 0)
            if budget is not None:
                try:
                    report.update(budget=budget.status(), **_accounting(budget.path))
                except Exception:
                    report['accounting_status'] = 'unavailable'
            episodes.close()
    job = report.get('job', {})
    complete = (job.get('state') == 'complete' and job.get('completed') == 7
                and report['originals_unchanged'] and report.get('usage_complete') is True)
    report['execution_status'] = 'execution_complete' if complete else 'incomplete'
    passed = complete and all(all(row['checks'].values()) for row in report['results'])
    report['persons_categories_status'] = 'passed' if passed else 'failed'
    if not passed:
        report['quality_status'] = report['status'] = 'failed'
    report['seconds'] = round(time.monotonic() - started, 3)
    # Actual paid endpoint execution is distinct from injected transport and
    # never implies persons, tasks or deadlines passed their quality checks.
    report['live_model_verified'] = _http_transport is None and complete
    return report


def _cap(value):
    if not re.fullmatch(r'(?:0|1)(?:\.[0-9]{1,6})?', value):
        raise ValueError('Use an explicit USD decimal cap with at most six places, at most 1 USD')
    result = int(Decimal(value) * 1_000_000)
    if not 1 <= result <= 1_000_000:
        raise ValueError('The artificial cap must be greater than zero and at most 1 USD')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-artificial-cloud', action='store_true')
    parser.add_argument('--cap-usd')  # Deliberately no monetary default.
    parser.add_argument('--max-requests', type=int, default=_MAX_REQUESTS)
    parser.add_argument('--seconds', type=int, default=_MAX_SECONDS)
    args = parser.parse_args(argv)
    try:
        cap = _cap(args.cap_usd) if args.cap_usd is not None else None
        _validate(args.allow_artificial_cloud, cap, args.max_requests, args.seconds)
        target = Path(args.output)
        with target.open('x') as stream:
            json.dump({'status': 'started', 'synthetic_only': True, 'live_model_verified': False}, stream)
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'blocked', 'error': type(exc).__name__}))
        return 2
    try:
        report = evaluate(allow_artificial_cloud=args.allow_artificial_cloud, cap_microusd=cap,
                          max_requests=args.max_requests, seconds=args.seconds)
    except (Exception, KeyboardInterrupt) as exc:
        report = {'status': 'failed', 'synthetic_only': True, 'live_model_verified': False, 'error': type(exc).__name__}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'execution_status', 'quality_status',
                                                  'live_model_verified', 'inference_requests') if key in report}))
    return 1  # No full task/deadline quality acceptance is implemented here.


if __name__ == '__main__':
    raise SystemExit(main())
