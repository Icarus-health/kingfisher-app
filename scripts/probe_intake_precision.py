#!/usr/bin/env python3
"""Bounded synthetic intake evaluation; never opens the personal application store."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.aufgaben_von_selbst import frist_aus
from icarus_memory.memory_analysis import interpret
from icarus_memory.memory_categories import Categories, migrate
from icarus_memory.providers import OpenAICompatible, json_request_deadline
from icarus_memory.task_review import review_tasks

_REQUEST = 'Bitte senden Sie die Unterlagen, idealerweise als PDF.'
_RESTRICTION = 'Bitte stellen Sie keine Rückfragen zum Bearbeitungsstand.'
_PERSONAL = 'Vera König zu Ihrer Wohnungsbewerbung: ' + _REQUEST + ' ' + _RESTRICTION
_NEWS = 'Fachnewsletter: Die neue Studie beschreibt den Einfluss von Bewegung auf die Konzentration. Dies ist allgemeine Fachinformation ohne persönliche Handlungsbitte.'


def _case(identifier, body, persons=(), tasks=0, deadlines=(), required=(), forbidden=()):
    return dict(id=identifier, body=body, source_ref='synthetic-' + identifier + '@example.invalid',
                persons=sorted(persons), task_count=tasks, deadlines=list(deadlines),
                required_topics=list(required), forbidden_topics=list(forbidden))


CASES = (
    _case('optional-portal', 'Wohnungsportal Beispiel\n\nNeue Nachricht in Ihrem Postfach.\n\n' + _PERSONAL,
          ('Vera König',), 1, (None,), ('personal',), ('information',)),
    _case('optional-direct', _PERSONAL, ('Vera König',), 1, (None,), ('personal',), ('information',)),
    _case('explicit-deadline', 'Vera König zu Ihrer Wohnungsbewerbung: Bitte senden Sie die Unterlagen bis zum 5. November 2026 zwingend als PDF.',
          ('Vera König',), 1, ('2026-11-05',), ('personal',), ('information',)),
    _case('newsletter', _NEWS, required=('information',)),
    _case('mixed', _PERSONAL + '\n\n' + _NEWS, ('Vera König',), 1, (None,), ('personal', 'information')),
    _case('appointment-versus-deadline', 'Vera König zu Ihrer Wohnungsbewerbung: Unser Gespräch ist am 7. November 2026. Bitte senden Sie die Unterlagen bis zum 5. November 2026.',
          ('Vera König',), 1, ('2026-11-05',), ('personal',), ('information',)),
    _case('distinct-people', 'Alex Rot arbeitet im Projekt Atlas. Alex Blau arbeitet im Projekt Boreal. Die beiden Personen sind verschiedene Menschen.',
          ('Alex Rot', 'Alex Blau'), required=('work',)),
)


class ProbeBudgetExceeded(RuntimeError):
    pass


class _Counted:
    def __init__(self, provider, max_calls, seconds, before_send):
        self.provider, self.calls = provider, 0
        self.max_calls, self.deadline = max_calls, time.monotonic() + seconds
        self.before_send = before_send

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def complete_json(self, messages, *, max_tokens, schema):
        if self.calls >= self.max_calls or time.monotonic() >= self.deadline:
            raise ProbeBudgetExceeded()
        if self.before_send:
            self.before_send()
        self.calls += 1
        with json_request_deadline(min(self.deadline, time.monotonic() + 45)):
            return self.provider.complete_json(messages, max_tokens=max_tokens, schema=schema)


def evaluate(provider, *, case_ids=None, max_calls=28, seconds=600, _before_send=None):
    """Real store/category/extraction/review code, with synthetic originals only.

    Injected replies can exercise the pipeline but never set live_model_verified.
    The CLI adds positive local-weight evidence only after its guarded live run.
    """
    if not getattr(provider, 'is_local', False):
        raise ValueError('This synthetic probe only accepts local providers')
    if type(max_calls) is not int or not 1 <= max_calls <= 40 or not 0 < seconds <= 900:
        raise ValueError('Invalid bounded probe budget')
    chosen = set(case_ids or [case['id'] for case in CASES])
    if not chosen or not chosen.issubset({case['id'] for case in CASES}):
        raise ValueError('Unknown synthetic case')
    counted = _Counted(provider, max_calls, seconds, _before_send)
    report = dict(status='running', live_model_verified=False, synthetic_only=True,
                  original_store='temporary', model=getattr(provider, 'model', ''), results=[])
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='kf-intake-synthetic-') as temporary:
        for index, case in enumerate(case for case in CASES if case['id'] in chosen):
            store = EpisodeStore(Path(temporary) / (str(index) + '.sqlite3'))
            row = dict(id=case['id'], status='failed', checks={}, original_unchanged=False)
            tick = time.monotonic()
            source = None
            try:
                source, _ = store.record(EpisodeKind.MESSAGE, 'Künstliche Gedächtnisprüfung', case['body'],
                    Provenance(SourceType.EMAIL, source_ref=case['source_ref']),
                    occurred_at=datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
                original = source.to_dict()
                if not store._conn.execute("SELECT 1 FROM sqlite_master WHERE name='memory_category_scan'").fetchone():
                    with store.transaction():
                        migrate(store._conn)
                categories = Categories(store)
                outcome = categories.run(counted, limit=1)
                if not outcome.ok:
                    # Surface the original local failure (including budget exhaustion)
                    # rather than call another model after a failed classification.
                    if counted.calls >= max_calls or time.monotonic() >= counted.deadline:
                        raise ProbeBudgetExceeded()
                    raise RuntimeError('CategoryAnalysisFailed')
                classified = categories.list_for(source.id)
                items = interpret(counted, source.title, source.body, source_context={'occurred_at': '2026-11-02T12:00:00Z'})
                tasks = review_tasks(counted, source.title, source.body, items)
                names = sorted({entry['name'] for entry in classified['entities'] if entry['kind'] == 'person'})
                topics = {entry['id'] for entry in classified['categories']}
                dates = [frist_aus(item['quote'], source.occurred_at) for item in tasks]
                dates = [value.date().isoformat() if value else None for value in dates]
                row.update(person_names=names, topics=sorted(topics), task_titles=[item['title'] for item in tasks],
                           deadlines=dates,
                           checks=dict(persons=names == case['persons'],
                                       tasks=len(tasks) == case['task_count'] and not any('rückfragen' in item['title'].casefold() for item in tasks),
                                       deadlines=dates == case['deadlines'],
                                       categories=set(case['required_topics']).issubset(topics) and not set(case['forbidden_topics']) & topics))
                row['status'] = 'passed' if all(row['checks'].values()) else 'failed'
            except Exception as exc:
                row['error'] = type(exc).__name__
            finally:
                if source is not None:
                    row['original_unchanged'] = store.get(source.id).to_dict() == original
                row['seconds'] = round(time.monotonic() - tick, 3)
                store.close()
            report['results'].append(row)
    report.update(calls=counted.calls, seconds=round(time.monotonic() - started, 3),
                  dataset_sha256=hashlib.sha256(json.dumps(CASES, sort_keys=True).encode()).hexdigest())
    report['status'] = 'passed' if all(row['status'] == 'passed' and row['original_unchanged'] for row in report['results']) else 'failed'
    return report


def _mac_resource_check(model):
    import httpx
    pressure = int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True)) if sys.platform == 'darwin' else 1
    if pressure > 2:
        raise RuntimeError('MemoryReserveUnavailable')
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        response = client.get('http://127.0.0.1:11434/api/ps'); response.raise_for_status()
        if any(row.get('name') not in {model, 'bge-m3:latest'} for row in response.json().get('models', [])):
            raise RuntimeError('AnotherLocalModelIsActive')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', default='kingfisher-qwen3.5:9b-8k')
    parser.add_argument('--case', action='append', choices=[case['id'] for case in CASES])
    args = parser.parse_args(argv)
    from icarus_memory.local_model_guard import verify_local_model
    provider = OpenAICompatible(args.model, 'synthetic-local', 'http://127.0.0.1:11434/v1')
    # Create the report before preflight; resource/model failure is a visible result.
    with Path(args.output).open('x') as output:
        try:
            identity = verify_local_model(provider, expected_num_ctx=8192)
            def before_send():
                _mac_resource_check(args.model)
                if verify_local_model(provider, expected_num_ctx=8192) != identity:
                    raise RuntimeError('LocalModelChanged')
            before_send()
            report = evaluate(provider, case_ids=args.case, _before_send=before_send)
            report.update(live_model_verified=True, local_model_digest=identity.digest)
        except Exception as exc:
            report = dict(status='failed', synthetic_only=True, live_model_verified=False, error=type(exc).__name__)
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({key:report[key] for key in ('status', 'live_model_verified', 'calls', 'seconds', 'error') if key in report}))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
