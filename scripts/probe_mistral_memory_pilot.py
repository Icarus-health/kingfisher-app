#!/usr/bin/env python3
"""Frozen ten-mail artificial pilot. Default: offline preview, never an API call.

Run from the repository with PYTHONPATH=sidecar:scripts:. . A paid run additionally
requires --run, --allow-artificial-cloud, an explicit --cap-usd <=1 and the dedicated
artificial key environment variable. No saved credentials or application startup.
Answers/retrieval and semantic acceptance are deliberately not implemented here.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import tempfile
import threading
import time

import httpx

from icarus_memory import EpisodeStore
from icarus_memory.cloud_memory import CloudMemoryJobs
from icarus_memory.cloud_import_budget import ENDPOINT, MODEL, MistralSourceBudget, MistralBudgetError
from icarus_memory.mistral_import_provider import _MAX_RESPONSE_BYTES
from icarus_memory.proposals import ProposalStore
from icarus_memory.tasks import TaskStore
from messlatte.uhr import eingefrorene_zeit
from probe_mistral_source_package import _Run as GuardedRun, _Provider, _Transport, _accounting, _cap, KEY_ENV

CATALOG = Path(__file__).resolve().parents[1] / 'docs/fixtures/memory-acceptance-20261104/pilot-v2/catalog.json'
CATALOG_SHA256 = '036fbf45fe33b7329f49c60e6183d13126daa8731bc922545cd7333d2a63f388'
SOURCES_SHA256 = 'd77f0f45dd8b38733485e81e43a3d21d8923b03d31ea4be8061f89503b2b3241'
FREEZE_SHA256 = '728f6fdffca11866d2f49b24fbf784b88b858c90c11434503d23076046cffe95'
MAX_REQUESTS, MAX_SECONDS = 60, 600


def _sources():
    # Hash gold as opaque bytes; only the separately frozen source file is parsed.
    names = {'catalog.json', 'sources.json', 'reference.json', 'README.md'}
    def read(name):
        path = CATALOG.with_name(name)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
            raise ValueError('Invalid frozen pilot file')
        return path.read_bytes()
    freeze = read('freeze.json')
    if hashlib.sha256(freeze).hexdigest() != FREEZE_SHA256:
        raise ValueError('The frozen pilot manifest changed')
    manifest = json.loads(freeze)
    if set(manifest['files']) != names:
        raise ValueError('Unknown frozen pilot files')
    checked = {}
    for name in sorted(names):
        checked[name] = read(name)
        if hashlib.sha256(checked[name]).hexdigest() != manifest['files'][name]:
            raise ValueError('The frozen pilot file changed: ' + name)
    return json.loads(checked['sources.json'])


def _bounds(cap_microusd, max_requests, seconds, *, required=False):
    if ((required or cap_microusd is not None) and
            (type(cap_microusd) is not int or not 1 <= cap_microusd <= 1000000)):
        raise ValueError('Explicit integer cap of 1..1000000 micro-USD required')
    if (type(max_requests) is not int or not 1 <= max_requests <= MAX_REQUESTS
            or type(seconds) not in (int, float) or not 0 < seconds <= MAX_SECONDS):
        raise ValueError('Invalid request or elapsed-time bound')


class _Run(GuardedRun):
    """Same transport/credential/deadline contract, bound to this ten-source set."""
    def __init__(self, episodes, originals, key, max_requests, deadline, transport):
        # The reused transport admits one metadata GET separately from POSTs.
        # This CLI's cap includes both, reserving that one GET in advance.
        super().__init__(episodes, originals, key, max_requests - 1, 0, transport)
        self.deadline = deadline
        self.source_keys = dict(episodes._conn.execute('SELECT id,source_key FROM episodes'))

    def intact(self):
        try:
            with self.episodes._lock:
                keys = dict(self.episodes._conn.execute('SELECT id,source_key FROM episodes'))
                return (len(keys) == 10 and keys == self.source_keys and set(keys) == set(self.originals)
                        and all(self.episodes.get(i).to_dict() == source for i, source in self.originals.items()))
        except Exception:
            return False


def _http_exchange(transport, request, result, abandoned, deadline):
    """Only HTTP objects, bytes and a mailbox; no Run, Job, Store or callback.

    A dispatched remote operation cannot be canceled reliably. After the waiter
    times out it may finish this one exchange, but cannot dispatch or settle one.
    Its bounded response is discarded; the existing ledger retains worst-case hold.
    """
    response = None
    try:
        if abandoned.is_set() or time.monotonic() >= deadline:
            raise httpx.ReadTimeout('Artificial run deadline')
        transport = transport if transport is not None else httpx.HTTPTransport(retries=0, trust_env=False)
        # A queued thread or transport construction may outlive the waiter.
        # Only exchanges already begun may finish after the local cutoff.
        if abandoned.is_set() or time.monotonic() >= deadline:
            raise httpx.ReadTimeout('Artificial run deadline')
        response = transport.handle_request(request)
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if abandoned.is_set() or size > _MAX_RESPONSE_BYTES:
                raise httpx.ReadError('Artificial exchange stopped')
            chunks.append(chunk)
        # Materialize and close in this thread. No later response stream can
        # retain the outer guarded transport or reach its stores after cleanup.
        headers = [(k, v) for k, v in response.headers.multi_items()
                   if k.lower() not in {'content-encoding', 'content-length', 'transfer-encoding'}]
        value = httpx.Response(response.status_code, headers=headers, content=b''.join(chunks))
    except Exception as exc:
        value = exc
    finally:
        try:
            if response is not None:
                response.close()
            if transport is not None:
                transport.close()
        except Exception:
            value = httpx.ReadError('Artificial transport cleanup failed')
    if not abandoned.is_set():
        result.put(value)


class _DeadlineHTTP(httpx.BaseTransport):
    def __init__(self, deadline, transport):
        self.deadline, self.transport = deadline, transport

    def handle_request(self, request):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise httpx.ReadTimeout('Artificial run deadline')
        result, abandoned = queue.Queue(maxsize=1), threading.Event()
        threading.Thread(target=_http_exchange, args=(self.transport, request, result, abandoned, self.deadline),
                         daemon=True, name='artificial-http-only').start()
        try:
            value = result.get(timeout=remaining)
        except queue.Empty:
            abandoned.set()
            raise httpx.ReadTimeout('Artificial run deadline') from None
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        # Raw transport lifecycle belongs solely to its HTTP thread.
        pass


class _PilotProvider(_Provider):
    def _client(self):
        # Leave a small part of the same total budget for local hold/receipt writes.
        return httpx.Client(transport=_Transport(self.run, _DeadlineHTTP(self.run.deadline - 0.05, self.run.transport)),
                            timeout=30, trust_env=False, follow_redirects=False)


def _check_originals(episodes, sources, mapping):
    """Compare the complete frozen mail meaning/identity before trusting intake."""
    folder_uids = {}
    owner, account = sources['owner']['address'], 'synthetic-pilot'
    for source in sources['mails']:
        episode = episodes.get(mapping[source['id']])
        folder = source.get('folder', 'INBOX')
        folder_uids[folder] = folder_uids.get(folder, 0) + 1
        uid = folder_uids[folder]
        contacts = [{'name': person['name'], 'adresse': person['address'], 'rolle': role,
                     'ich': person['address'] == owner}
                    for role, person in [('von', source['sender']), *[('an', p) for p in source['recipients']]]]
        participants = [f"{c['name']} <{c['adresse']}>" for c in contacts if c['rolle'] == 'von' or not c['ich']]
        message_id = f"<{source['id']}@messlatte.example>"
        token = lambda value: hashlib.sha256((account + '\0' + value).encode()).hexdigest()
        tags = ['mail:message:' + token(message_id)]
        if source.get('reply_to'):
            tags.append('mail:reply:' + token(f"<{source['reply_to']}@messlatte.example>"))
        headers = [tag for tag in episode.tags if not tag.startswith('mail:attachments:')]
        captured = episodes._conn.execute('SELECT folder,generation,uid FROM mail_intake_items '
            'WHERE account=? AND episode_id=?', (account, episode.id)).fetchall()
        identity = f'1.{uid}' if folder == 'INBOX' else json.dumps([folder, f'1.{uid}'])
        key = 'mail:' + hashlib.sha256(json.dumps([account, identity]).encode()).hexdigest()
        key_row = episodes._conn.execute('SELECT source_key FROM episodes WHERE id=?', (episode.id,)).fetchone()
        body = source['body'].replace('\r\n', '\n')
        body += '' if body.endswith('\n') else '\n'  # EmailMessage text/plain trailing newline only.
        if (episode.title != source['title'] or episode.body != body or episode.contacts != contacts
                or episode.participants != participants or headers != tags
                or episode.occurred_at != datetime.fromisoformat(source['at'])
                or episode.provenance.captured_at != datetime.fromisoformat(source['at'])
                or episode.provenance.source_ref != account + ':' + message_id
                or episode.provenance.source_type.value != 'email' or episode.kind.value != 'message'
                or episode.recorded_at != datetime.fromisoformat(sources['clock'])
                or episode.project_id is not None or episode.state.value != 'new'
                or key_row is None or key_row[0] != key
                or episodes.source_head(key) != episode.id
                or [(str(r[0]), str(r[1]), int(r[2])) for r in captured] != [(folder, '1', uid)]):
            raise ValueError('Intake changed frozen original metadata or body')


def _intake(episodes, sources):
    """Real RFC822 reader/intake; only IMAP transport is artificial. No classifier."""
    from mail_intake_quality import to_mail
    from messlatte.postfach import Postfach, postfach_installieren, quelle_aus_message_id
    from icarus_memory.connectors.mail import MailConfig, MailConnector
    from icarus_memory.mail_intake import Intake
    mailbox = Postfach()
    for source in sources['mails']:
        mailbox.ablegen_mail(to_mail(source, sources['owner']))
    intake = Intake(episodes)
    intake.start('synthetic-pilot', ['INBOX', 'Sent'])
    with postfach_installieren(mailbox):
        reader = MailConnector(MailConfig(imap_host='imap.messlatte.example',
            username=sources['owner']['address'], password='unused-artificial-transport'))
        for _ in range(20):
            intake.step('synthetic-pilot', reader, batch=50)
            folders = intake.status('synthetic-pilot')['folders']
            if folders and all(f['inventory_complete'] and not f['pending'] and not f['live_pending'] for f in folders):
                break
    originals = episodes.all_episodes()
    mapping = {quelle_aus_message_id(e.provenance.source_ref): e.id for e in originals}
    if len(originals) != 10 or set(mapping) != {s['id'] for s in sources['mails']}:
        raise ValueError('Intake did not preserve exactly ten artificial mails')
    _check_originals(episodes, sources, mapping)
    return mapping


def preview(*, cap_microusd=None, max_requests=MAX_REQUESTS, seconds=MAX_SECONDS, _started=None):
    return _evaluate(offline=True, cap_microusd=cap_microusd, max_requests=max_requests, seconds=seconds,
                     started=_started)


def evaluate(*, allow_artificial_cloud=False, cap_microusd=None,
             max_requests=MAX_REQUESTS, seconds=MAX_SECONDS, _http_transport=None, _started=None):
    started = time.monotonic() if _started is None else _started
    _bounds(cap_microusd, max_requests, seconds, required=True)
    if allow_artificial_cloud is not True:
        raise ValueError('Explicit artificial cloud approval required')
    key = os.environ.get(KEY_ENV)
    if not isinstance(key, str) or not key.strip():
        raise ValueError('The dedicated artificial key is required')
    if _http_transport is not None and not isinstance(_http_transport, httpx.BaseTransport):
        raise ValueError('Invalid injected HTTP transport')
    return _evaluate(offline=False, key=key, cap_microusd=cap_microusd,
                     max_requests=max_requests, seconds=seconds, transport=_http_transport, started=started)


def _evaluate(*, offline, cap_microusd, max_requests, seconds, key=None, transport=None, started=None):
    now = time.monotonic()
    started = now if started is None else started
    if type(started) not in (int, float) or not math.isfinite(started) or started > now:
        raise ValueError('Invalid monotonic start time')
    deadline = started + seconds
    _bounds(cap_microusd, max_requests, seconds)
    sources = _sources()
    clock = datetime.fromisoformat(sources['clock'])
    report = dict(status='offline_preview' if offline else 'requires_review',
        execution_status='not_run' if offline else 'incomplete', semantic_grade='requires_review',
        questions='not_run', synthetic_only=True, injected_http=transport is not None,
        live_model_verified=False, model=MODEL, endpoint=ENDPOINT, catalog_sha256=CATALOG_SHA256,
        sources_sha256=SOURCES_SHA256, freeze_sha256=FREEZE_SHA256,
        scenario_clock=sources['clock'], original_store='temporary',
        max_requests=max_requests, max_seconds=seconds, cap_microusd=cap_microusd,
        request_limit_semantics='total HTTP: metadata GET plus inference POSTs',
        limits=dict(maximum_cap_microusd=1000000, maximum_requests=60, maximum_seconds=600),
        stages=['source_classification', 'persons_categories', 'task_extraction', 'task_semantic_review'],
        acceptance='No retrieval, native, attachment, full acceptance or bulk-import pass.',
        timeout_scope='Preparation, dispatch and HTTP waiting share one monotonic deadline. Local filesystem operations have no OS watchdog.',
        timeout_billing='A remote dispatched request can continue after timeout; unknown usage remains held at the reserved worst-case cost. No server-side cancellation is claimed.',
        mail_transport='synthetic RFC822 IMAP; real MailConnector and Intake; no preclassification')
    with ExitStack() as scope:
        cleanup = ExitStack()
        directory = Path(tempfile.mkdtemp(prefix='kf-mistral-pilot-'))
        cleanup.callback(shutil.rmtree, directory)
        scope.callback(cleanup.close)
        # Existing scenario freeze leaves time.time and monotonic (budget/leases) real.
        scope.enter_context(eingefrorene_zeit(clock))
        episodes = EpisodeStore(directory / 'originals.sqlite3'); cleanup.callback(episodes.close)
        proposals = ProposalStore(directory / 'proposals.sqlite3'); cleanup.callback(proposals.close)
        tasks = TaskStore(directory / 'tasks.sqlite3'); cleanup.callback(tasks.close)
        mapping = _intake(episodes, sources)
        originals = {i: episodes.get(i).to_dict() for i in mapping.values()}
        run = _Run(episodes, originals, key, max_requests, deadline, transport)
        budget = MistralSourceBudget(directory / 'mistral-budget.sqlite3')
        if not offline:
            budget.set_total_cap(cap_microusd, budget.status()['revision'])

        def no_fallback(*_a):
            raise ValueError('No fallback provider permitted')

        def factory(identifier, model, **binding):
            if offline:
                raise ValueError('Offline preview cannot construct a provider')
            run.guard()
            if identifier != 'mistral' or model != MODEL:
                raise ValueError('Only pinned Mistral source model permitted')
            return _PilotProvider(model, key, run.revision, lambda: run.revision if run.current() else None,
                             budget=budget, run=run, **binding)

        jobs = CloudMemoryJobs(episodes, directory / 'jobs.sqlite3', no_fallback, lambda: {},
            api_provider_factory=factory, credential_status=(lambda _: {'available': False, 'model': MODEL})
            if offline else run.credential, mistral_budget=budget, proposals=proposals, tasks=tasks)
        # Never derive this receipt from potentially removed/changed rows later.
        report['sources'] = [{**source, 'source_id': mapping[source['id']],
            'planned_request_upper_bound': jobs._planned_requests(episodes.get(mapping[source['id']]), include_tasks=True),
            'original': originals[mapping[source['id']]]} for source in sources['mails']]
        job_id = None
        try:
            ids = list(mapping.values())
            report['preview'] = jobs.preview(source_ids=ids, provider='mistral', include_tasks=True)
            if report['preview']['count'] != 10 or {s['id'] for s in report['preview']['sources']} != set(ids):
                raise ValueError('Preview must bind all ten originals')
            if not offline:
                run.guard()
                job_id = jobs.start(report['preview']['preview_id'], MODEL, True, source_ids=ids, provider='mistral')['job']['id']
                worker = jobs._threads[job_id]
                while worker.is_alive() and time.monotonic() < deadline:
                    worker.join(min(0.05, max(0, deadline - time.monotonic())))
        except (Exception, KeyboardInterrupt) as exc:
            report['error'] = type(exc).__name__
        finally:
            if job_id is not None:
                worker = jobs._threads[job_id]
                if worker.is_alive():
                    jobs.pause(job_id, revoke=True)
                    # No unbounded join. If a local filesystem operation itself
                    # stalls, keep its stores alive until that worker finishes.
                    if worker.is_alive():
                        retained = cleanup.pop_all()
                        receipt_done = threading.Event()
                        scope.callback(receipt_done.set)
                        def finish_cleanup():
                            worker.join()
                            receipt_done.wait()
                            retained.close()
                        threading.Thread(target=finish_cleanup, daemon=True, name='artificial-store-cleanup').start()
                        report['worker_cleanup_pending'] = True
            errors = report.setdefault('receipt_errors', {})
            def read(field, callback, default=None):
                try:
                    return callback()
                except Exception as exc:
                    errors[field] = type(exc).__name__
                    return default
            # Independent accounting survives any per-source/result read failure.
            report.update(inference_requests=run.posts, metadata_requests=run.gets,
                          originals_unchanged=run.intact(), deadline_exhausted=time.monotonic() >= deadline - 0.05)
            report['budget'] = read('budget', budget.status)
            accounting = read('accounting', lambda: _accounting(budget.path))
            if accounting is not None:
                report.update(accounting)
            else:
                report.update(accounting_status='unavailable', usage_complete=False,
                              reconciliation_required=True, unverified_cost_upper_bound_microusd=cap_microusd)
            if job_id is not None:
                report['job'] = read('job', lambda: jobs.status(job_id)['job'], {})
            from icarus_memory.aufgaben_von_selbst import Durchlauf
            from icarus_memory.task_detection import candidate_batches
            helper = Durchlauf(tasks, episodes, proposals, eigene=lambda: [sources['owner']['address']], jetzt=lambda: clock)
            report['results'] = []
            for source in sources['mails']:
                identifier = mapping[source['id']]
                current = read('original:' + source['id'], lambda: episodes.get(identifier).to_dict())
                exists = read('exists:' + source['id'], lambda: episodes._conn.execute(
                    'SELECT 1 FROM episodes WHERE id=?', (identifier,)).fetchone())
                integrity = ('unchanged' if current == originals[identifier] else
                             'changed' if current is not None else
                             'missing' if exists is None and 'exists:' + source['id'] not in errors else 'unavailable')
                report['results'].append(dict(id=source['id'], source_id=identifier, integrity=integrity,
                    original_unchanged=integrity == 'unchanged',
                    working_memory_state=read('classification:' + identifier, lambda: jobs.memory.source_state(identifier)),
                    classification_refs=read('refs:' + identifier, lambda: jobs.memory.source_refs(episode_ids=[identifier])),
                    persons_categories=read('categories:' + identifier, lambda: jobs.categories.list_for(identifier))))
            report['task_proposals'] = read('proposals', lambda: [p.to_dict() for p in proposals.all_proposals()])
            def deadlines():
                rows = []
                for batch in candidate_batches(proposals, episodes, now=clock):
                    for proposal, episode, timing in batch:
                        prefill = helper.vorbefuellt(proposal)
                        rows.append(dict(proposal_id=proposal.id, source_id=episode.id,
                            due=prefill.get('frist_vorschlag'), prefill=prefill, timing=timing))
                return rows
            report['deadline_suggestions'] = read('deadlines', deadlines)
            report['automatic_tasks'] = read('automatic_tasks', lambda: [t.to_dict() for t in tasks.all_tasks()])
    complete = (report.get('job', {}).get('state') == 'complete'
                and report.get('job', {}).get('completed') == 10 and report['originals_unchanged']
                and report['usage_complete'] and report['automatic_tasks'] == []
                and not report.get('worker_cleanup_pending') and not report.get('receipt_errors'))
    if not offline:
        report['execution_status'] = 'execution_complete' if complete else 'incomplete'
        report['live_model_verified'] = transport is None and complete
    report['seconds'] = round(time.monotonic() - started, 3)
    return report


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--allow-artificial-cloud', action='store_true')
    parser.add_argument('--cap-usd')
    parser.add_argument('--max-requests', type=int, default=MAX_REQUESTS)
    parser.add_argument('--seconds', type=int, default=MAX_SECONDS)
    args = parser.parse_args(argv)
    target = None
    try:
        cap = _cap(args.cap_usd) if args.cap_usd is not None else None
        _bounds(cap, args.max_requests, args.seconds, required=args.run)
        _sources()
        if args.run and (not args.allow_artificial_cloud or not os.environ.get(KEY_ENV, '').strip()):
            raise ValueError('Explicit cloud authority and dedicated key required')
        if args.output:
            target = Path(args.output)
            with target.open('x') as stream:
                json.dump({'status': 'started', 'synthetic_only': True}, stream)
        elif args.run:
            raise ValueError('A new output file is required for paid execution')
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'blocked', 'error': type(exc).__name__})); return 2
    try:
        options = dict(cap_microusd=cap, max_requests=args.max_requests, seconds=args.seconds, _started=started)
        report = evaluate(allow_artificial_cloud=args.allow_artificial_cloud, **options) if args.run else preview(**options)
    except (Exception, KeyboardInterrupt) as exc:
        report = {'status': 'failed', 'error': type(exc).__name__, 'semantic_grade': 'requires_review'}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if target:
        target.write_text(rendered)
    else:
        print(rendered)
    return 1 if args.run or report.get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
