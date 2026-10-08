#!/usr/bin/env python3
"""Synthetic end-to-end memory diagnostic; no application settings or user data.

Calls the real Agent.answer_memory path, including question understanding,
selection, rendering and optional sentence verification. Exact source selection
is measured automatically; the saved prose still needs independent review.
This is retrieval evaluation after deterministic indexing, NOT ingestion QA.
Only an installed Ollama model on a literal loopback endpoint is allowed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sidecar'))
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.policy import Policy
from icarus_memory.providers import OpenAICompatible, is_local_endpoint
from icarus_memory.satzpruefung_modell import tor
from icarus_memory import working_memory_answers
from probe_working_memory_paraphrase import build, catalog_digest


class Meter:
    """Count calls while preserving the actual local transport identity."""
    def __init__(self, inner):
        self.inner = inner
        self.name, self.model = inner.name, inner.model
        self.is_local = inner.is_local
        self.base_url = getattr(inner, 'base_url', '')
        self.calls = 0
        self.events = []
        self._lock = threading.Lock()
        if callable(getattr(inner, 'complete_json', None)):
            self.complete_json = self._json

    def _json(self, *args, **kwargs):
        return self._call(lambda: self.inner.complete_json(*args, **kwargs))

    def complete(self, *args, **kwargs):
        return self._call(lambda: self.inner.complete(*args, **kwargs))

    def _call(self, operation):
        event = {'state': 'pending'}
        with self._lock:
            self.calls += 1
            self.events.append(event)
        try:
            result = operation()
        except Exception:
            with self._lock:
                event['state'] = 'failed'
            raise
        with self._lock:
            event['state'] = 'ok'
        return result

    def outcomes(self, start):
        with self._lock:
            return Counter(event['state'] for event in self.events[start:])


def local_provider(model, base_url):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'http' or not is_local_endpoint(base_url)
            or parsed.hostname == 'localhost' or parsed.username or parsed.password
            or parsed.path.rstrip('/') != '/v1' or parsed.query or parsed.fragment):
        raise ValueError('Use a literal loopback Ollama HTTP endpoint ending in /v1')
    origin = urlunsplit((parsed.scheme, parsed.netloc, '', '', ''))
    # Never ask Ollama to download or use a cloud alias; inspect installed weights first.
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
        response = client.get(origin + '/api/tags')
        response.raise_for_status()
        wanted = model if ':' in model else model + ':latest'
        found = next((r for r in response.json()['models'] if r.get('name') == wanted), None)
        if (not found or len(found.get('digest', '')) != 64 or found.get('remote_host')
                or found.get('remote_model') or wanted.endswith('-cloud')):
            raise ValueError('Installed local weights required; no download or cloud model permitted')
        shown = client.post(origin + '/api/show', json={'model': model})
        shown.raise_for_status()
        info = shown.json()
        if info.get('remote_host') or info.get('remote_model') or not info.get('model_info'):
            raise ValueError('The model must have inspectable local weights')
    provider = OpenAICompatible(model, api_key='ollama', base_url=base_url)
    provider._verified_local_transport = True
    return provider


def evaluate(item, turn, alias):
    context = turn.context
    working = context.get('working_answer', {})
    status = context.get('answer_contract', {}).get('status', 'missing_contract')
    valid = True
    def names(refs):
        nonlocal valid
        if not isinstance(refs, list):
            valid = False
            return ['invalid_reference_container']
        found = set()
        for index, ref in enumerate(refs):
            if (not isinstance(ref, dict) or not isinstance(ref.get('episode_id'), str)
                    or not ref['episode_id']):
                valid = False
                found.add(f'invalid_reference:{index}')
            else:
                found.add(alias.get(ref['episode_id'], 'unmapped:' + ref['episode_id']))
        return sorted(found)
    selected = names(working.get('refs', []))
    shown = names(context.get('source_links', []))
    expected = sorted(item['expect'])
    unknown = status in {'unknown', 'working_unknown'}
    status_ok = unknown if not expected else status == 'working_reports'
    exact = shown == expected
    candidates = names(working.get('basis', []))
    return {'q': item['q'], 'type': item['type'], 'expect': expected, 'status': status,
            'candidate_sources': candidates, 'selected_sources': selected, 'references_valid': valid,
            'shown_sources': shown, 'exact_sources': exact, 'status_ok': status_ok,
            'retrieved_expected': bool(expected) and set(expected) <= set(shown),
            'selection_pass': exact and status_ok and valid, 'answer': turn.reply,
            'question_understanding': working.get('anfrage'), 'search': working.get('search'),
            'sentence_answer': working.get('satzantwort'), 'times': context.get('zeiten')}


def run(provider, *, sentences=True, limit=None):
    if not getattr(provider, 'is_local', False):
        raise ValueError('Only a local provider is allowed')
    metered = Meter(provider)
    with tempfile.TemporaryDirectory(prefix='kingfisher-e2e-') as directory:
        catalog, episodes, store, alias = build(directory)
        claims = ClaimStore(Path(directory) / 'claims.sqlite3')
        audit = AuditLog(Path(directory) / 'audit.sqlite3')
        withdrawal = {'checked': False, 'pass': False}
        rows, saved = [], None
        try:
            for item in catalog['questions'][:limit]:
                # Each question is independent; prior conversation must not leak answers.
                agent = Agent(SelfModelStore(MemoryBackend(), 'synthetic'), Policy(), audit, {},
                              provider=metered, episodes=episodes, knowledge=claims)
                agent._frage_anbieter = lambda: metered
                agent._saetze = sentences
                agent._pruefung = lambda: tor('an', metered)
                calls, started = metered.calls, time.perf_counter()
                turn = agent.answer_memory(item['q'])
                row = evaluate(item, turn, alias)
                row.update(seconds=round(time.perf_counter() - started, 3), calls=metered.calls - calls)
                outcomes = metered.outcomes(calls)
                row.update(provider_errors=outcomes['failed'], provider_pending=outcomes['pending'])
                row['selection_pass'] &= not (row['provider_errors'] or row['provider_pending'])
                rows.append(row)
                print(f"{len(rows)}/{min(limit or 36, 36)} {item['type']} {row['status']} "
                      f"sources={row['shown_sources']} {row['seconds']}s", file=sys.stderr, flush=True)
                answer = turn.context.get('working_answer')
                if saved is None and answer and answer.get('refs') and row['status'] == 'working_reports':
                    saved = answer
            if saved is not None:
                # Reopen a previously rendered answer after withdrawing its originals.
                for identifier in {r['episode_id'] for r in saved['refs']}:
                    episodes.ignore(identifier)
                text, links, status = working_memory_answers.render(saved, episodes, claims)
                withdrawal = {'checked': True, 'pass': status == 'working_unavailable' and not links,
                              'status': status, 'answer': text}
        finally:
            audit.close()
            claims.close()
            episodes.close()
    scores = {}
    for kind in ('direct', 'paraphrase', 'unanswerable'):
        part = [r for r in rows if r['type'] == kind]
        scores[kind] = {'n': len(part), 'exact_displayed_sources': sum(r['exact_sources'] for r in part),
                        'exact_source_and_status': sum(r['selection_pass'] for r in part),
                        'statuses': dict(Counter(r['status'] for r in part))}
    return {'suite': 'working-memory-end-to-end-v1', 'synthetic_only': True,
            'catalog_sha256': catalog_digest(), 'partial_catalog': len(rows) != len(catalog['questions']),
            'model': metered.model, 'endpoint': metered.base_url, 'calls': metered.calls,
            'sentence_verifier': 'same_model_local' if sentences else 'not_used_quote_mode',
            'prose_correctness': 'not_automatically_scored_requires_independent_review',
            'status_criterion': 'answerable_rows_require_reports; safe_clarifications_count_separately_in_statuses; '
                                'catalog_has_source_gold_only_not_semantic_status_gold',
            'ingestion': 'deterministic_indexing_not_model_ingestion',
            'score': scores, 'rows': rows, 'withdrawal': withdrawal}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:11434/v1')
    parser.add_argument('--quotes', action='store_true', help='Quote selection only, no sentence generation')
    parser.add_argument('--limit', type=int, choices=range(1, 37), help='Partial catalog, explicitly labeled')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Ausgabe existiert bereits; nichts überschrieben')
    provider = local_provider(args.model, args.base_url)
    report = run(provider, sentences=not args.quotes, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'score': report['score'], 'calls': report['calls'], 'withdrawal': report['withdrawal']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
