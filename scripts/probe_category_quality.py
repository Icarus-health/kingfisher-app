#!/usr/bin/env python3
"""Measure the eight synthetic category/person cases through the real product.

Only a proven local Ollama model on loopback is accepted. No personal store,
credentials, model download, daemon startup, cloud fallback, or app change.
This does not measure task extraction, identity resolution or answer quality.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sidecar'))
from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.ollama_inventar import LOKAL, OllamaInventar
from icarus_memory.providers import OpenAICompatible, is_local_endpoint
from icarus_memory.memory_categories import Categories
from icarus_memory.model_recommendation import normalisiere

CATALOG = ROOT / 'docs/runs/2026-10-10-native-and-category-boundary/quality-cases.json'


def load_catalog():
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw)
    cases = catalog.get('cases') if isinstance(catalog, dict) else None
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError('Invalid catalog: exactly eight cases are required')
    identifiers = set()
    for case in cases:
        if not isinstance(case, dict) or any(
                not isinstance(case.get(key), str) or not case[key].strip() for key in ('id', 'body')):
            raise ValueError('Invalid catalog: nonempty ID and body are required')
        if case['id'] in identifiers:
            raise ValueError('Invalid catalog: duplicate case ID')
        identifiers.add(case['id'])
        for key in ('required_categories', 'forbidden_categories', 'required_people'):
            values = case.get(key)
            if (not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values)
                    or len(set(values)) != len(values)):
                raise ValueError('Invalid catalog: unique expectation lists are required')
        if set(case['required_categories']) & set(case['forbidden_categories']):
            raise ValueError('Invalid catalog: contradictory categories')
        if not case['required_categories']:
            raise ValueError('Invalid catalog: each case requires a category expectation')
    return cases, hashlib.sha256(raw).hexdigest()


def local_root(base_url):
    parsed = urlparse(base_url)
    if (parsed.scheme != 'http' or not is_local_endpoint(base_url)
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/v1'):
        raise ValueError('Only a credential-free HTTP loopback Ollama /v1 endpoint is accepted')
    # Also reject malformed ports before any client is constructed.
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid local port')
    return base_url.rstrip('/')[:-3]


def local_provider(model, base_url):
    provider = OpenAICompatible(model, api_key='ollama', base_url=base_url)
    provider._verified_local_transport = True
    return provider


class Counted:
    def __init__(self, provider):
        self.inner = provider
        self.model = provider.model
        self.name = provider.name
        self.is_local = provider.is_local
        self.entity_anchor_mode = provider.entity_anchor_mode
        self.calls = 0

    def complete_json(self, messages, **kwargs):
        self.calls += 1
        return self.inner.complete_json(messages, **kwargs)


def evaluate(provider, case):
    with tempfile.TemporaryDirectory(prefix='kingfisher-synthetic-category-') as folder:
        with closing(EpisodeStore(Path(folder) / 'episodes.sqlite3')) as episodes:
            item, created = episodes.record(EpisodeKind.MESSAGE, case['id'], case['body'],
                                           Provenance(SourceType.EMAIL, source_ref='synthetic:' + case['id']))
            assert created
            original = item.to_dict()
            categories = Categories(episodes)
            categories.run(provider, source_ids=[item.id])
            state = categories.list_for(item.id)
            actual = {row['id'] for row in state['categories']}
            people = {row['name'] for row in state['entities'] if row['kind'] == 'person'}
            missing = sorted(set(case['required_categories']) - actual)
            forbidden = sorted(set(case['forbidden_categories']) & actual)
            unexpected = sorted(actual - set(case['required_categories']))
            missing_people = sorted(set(case['required_people']) - people)
            extra_people = sorted(people - set(case['required_people']))
            unchanged = episodes.get(item.id).to_dict() == original
            return {'id': case['id'], 'source_status': state['status'],
                    'failure_code': state.get('failure_code'),
                    'categories': sorted(actual), 'people': sorted(people),
                    'missing_categories': missing, 'forbidden_categories_found': forbidden,
                    'unexpected_categories': unexpected,
                    'missing_people': missing_people, 'unexpected_people': extra_people,
                    'original_unchanged': unchanged,
                    'meets_requirements': (state['status'] in {'complete', 'empty'} and unchanged
                                           and not (missing or unexpected or missing_people or extra_people))}


def run(model, *, base_url='http://127.0.0.1:11434/v1', client_factory=None, provider_factory=local_provider):
    root = local_root(base_url)
    if not isinstance(model, str) or not model.strip():
        raise ValueError('A named model is required')
    cases, catalog_digest = load_catalog()
    report = {'scope': 'category_and_person_mentions_only', 'personal_data_used': False,
              'scoring': 'exact_category_and_person_sets_from_manual_fixture',
              'model': model, 'catalog_sha256': catalog_digest,
              'product_category_sha256': hashlib.sha256((ROOT / 'sidecar/icarus_memory/memory_categories.py').read_bytes()).hexdigest(),
              'cases_planned': len(cases), 'cases_attempted': 0, 'cases_evaluated': 0, 'cases_meeting_requirements': 0,
              'model_calls_attempted': 0, 'model_run_completed': False, 'results': [],
              'status': 'not_run', 'reason': None}
    client_factory = client_factory or (lambda: httpx.Client(timeout=3, trust_env=False, follow_redirects=False))
    inventory = OllamaInventar(lambda: root, client_factory, ttl=0, fehler_ttl=0)
    provider = None
    started = time.monotonic()
    for case in cases:
        # Recheck before each case: a daemon/model can change during the run.
        installed = inventory.installiert(root)
        proven_local = installed is not None and any(
            normalisiere(name) == normalisiere(model) and kind == LOKAL
            for name, kind in installed.items())
        if not proven_local:
            report['reason'] = 'ollama_unreachable' if installed is None else 'model_not_proven_local'
            report['status'] = 'interrupted' if report['results'] else 'not_run'
            break
        if provider is None:
            provider = Counted(provider_factory(model, base_url))
            if not provider.is_local:
                raise ValueError('Provider must remain local')
        result = evaluate(provider, case)
        report['results'].append(result)
        report['model_calls_attempted'] = provider.calls
        if result['failure_code'] in {'provider_error', 'internal_error'}:
            report['reason'] = 'model_inference_failed' if result['failure_code'] == 'provider_error' else 'product_error'
            report['status'] = 'interrupted' if len(report['results']) > 1 else 'not_run'
            break
    report['cases_attempted'] = len(report['results'])
    report['cases_evaluated'] = sum(row['failure_code'] not in {'provider_error', 'internal_error'} for row in report['results'])
    report['cases_meeting_requirements'] = sum(row['meets_requirements'] for row in report['results'])
    report['model_run_completed'] = report['cases_evaluated'] == len(cases)
    if report['model_run_completed']:
        report['status'] = 'evaluated'
    report['seconds'] = round(time.monotonic() - started, 3)
    return report


def write_report(path, report):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:11434/v1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Report already exists; choose a fresh path')
    try:
        report = run(args.model, base_url=args.base_url)
        write_report(args.output, report)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({key: report[key] for key in ('status', 'reason', 'cases_evaluated', 'cases_planned',
                                                   'cases_meeting_requirements', 'model_calls_attempted')}))
    return 2 if not report['model_run_completed'] else 0 if report['cases_meeting_requirements'] == report['cases_planned'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
