#!/usr/bin/env python3
"""Measure source-first area pages in an ephemeral synthetic corpus, without models.

python scripts/probe_memory_area_scale.py --sizes 10000,100000 --body-chars 2048 --output report.json

Category results are controlled fixture annotations, not language-model output.
This measures page projection, not mail synchronization or semantic answer quality.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sidecar'))
from icarus_memory import EpisodeStore, EpisodeKind, Provenance, SourceType
from icarus_memory.memory_categories import Categories
from icarus_memory.memory_areas import MemoryAreas


def validate_workload(sizes, body_chars):
    sizes = tuple(sizes)
    if not sizes or any(type(n) is not int or not 64 <= n <= 150000 for n in sizes) or list(sizes) != sorted(set(sizes)):
        raise ValueError('sizes must be unique ascending integers from 64 to 150000')
    if type(body_chars) is not int or not 128 <= body_chars <= 8192:
        raise ValueError('body_chars must be 128..8192')
    return sizes


def run(sizes=(10000,), body_chars=2048, *, progress=None):
    sizes = validate_workload(sizes, body_chars)
    report = {'status': 'running', 'suite': 'memory-area-scale-v1', 'synthetic_only': True,
              'network_used': False, 'models_called': False, 'body_chars': body_chars,
              'annotation': 'controlled work topics; 31 oldest sources manually assigned health',
              'measurements': []}
    if progress:
        progress(report)
    with tempfile.TemporaryDirectory(prefix='kingfisher-area-scale-') as directory:
        store = EpisodeStore(Path(directory) / 'synthetic.sqlite3')
        categories = Categories(store)
        version = categories.taxonomy()['version']
        health_ids = []
        started = time.perf_counter()
        transaction = None
        try:
            for index in range(max(sizes)):
                # Bounded transactions reduce fixture fsync cost; not a live-import throughput claim.
                if index % 250 == 0:
                    transaction = store.transaction()
                    transaction.__enter__()
                body = (f'Arbeit: Künstliche Quelle {index}. ' + 'Erfundene Nachricht für die Größenprüfung. ' * (body_chars // 40 + 1))[:body_chars]
                source, _ = store.record(EpisodeKind.MESSAGE, f'Künstliche Quelle {index}', body,
                    Provenance(SourceType.EMAIL, source_ref=f'synthetic:{index}'),
                    occurred_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
                snapshot = categories.memory._snapshot(source.id)
                assert categories._write(snapshot, version, [('work', 0, 6)], [], 'probe:controlled')
                if index < 31:
                    categories.correct(source.id, ['health'])
                    health_ids.append(source.id)
                if (index + 1) % 250 == 0 or index + 1 in sizes:
                    transaction.__exit__(None, None, None)
                    transaction = None
                    if (index + 1) % 250 and index + 1 < max(sizes):
                        transaction = store.transaction()
                        transaction.__enter__()
                if index + 1 not in sizes:
                    continue
                measurement = {'sources': index + 1, 'cumulative_elapsed_seconds': time.perf_counter() - started, 'pages': {}}
                changes_before = store._conn.total_changes
                for area in (None, 'work', 'health', 'finance', 'other'):
                    elapsed = []
                    for _ in range(3):
                        tick = time.perf_counter()
                        result = MemoryAreas(store).page(limit=25, area=area)
                        elapsed.append(time.perf_counter() - tick)
                    if area == 'health':
                        assert [s['episode_id'] for s in result['sources']] == list(reversed(health_ids))[:25]
                        second = MemoryAreas(store).page(limit=25, area=area, cursor=result['next_cursor'])
                        assert [s['episode_id'] for s in second['sources']] == list(reversed(health_ids))[25:]
                        assert second['next_cursor'] is None
                    elif area == 'finance':
                        assert result['sources'] == [] and result['next_cursor'] is None
                    elif area == 'other':
                        assert result['sources'] == []
                        assert result['scan_limited'] == (index + 1 > 500)
                        assert (result['next_cursor'] is not None) == result['scan_limited']
                    else:
                        assert len(result['sources']) == 25 and result['next_cursor'] is not None
                    measurement['pages'][area or 'all'] = {'seconds': elapsed, 'median_seconds': statistics.median(elapsed),
                        'returned': len(result['sources']), 'checked': result['candidates_checked'],
                        'scan_limited': result['scan_limited'], 'has_more': result['truncated']}
                assert store._conn.total_changes == changes_before, 'read projection wrote to original store'
                measurement['rss_peak_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
                measurement['database_bytes'] = sum(p.stat().st_size for p in Path(directory).glob('synthetic.sqlite3*'))
                report['measurements'].append(measurement)
                if progress:
                    progress(report)
                print(f'{index + 1} synthetic sources projected', file=sys.stderr, flush=True)
            # Source withdrawal must hold after traversing the large unrelated corpus.
            store.ignore(health_ids[-1])
            withdrawn = MemoryAreas(store).page(limit=25, area='health')
            assert health_ids[-1] not in {s['episode_id'] for s in withdrawn['sources']}
            assert [s['episode_id'] for s in withdrawn['sources']] == list(reversed(health_ids[:-1]))[:25]
            report['withdrawal_verified'] = True
            report['status'] = 'passed'
            if progress:
                progress(report)
        finally:
            if transaction is not None:
                transaction.__exit__(*sys.exc_info())
            store.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', default='10000')
    parser.add_argument('--body-chars', type=int, default=2048)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output existiert bereits; wird nicht überschrieben')
    try:
        sizes = validate_workload(tuple(int(n) for n in args.sizes.split(',')), args.body_chars)
    except ValueError as error:
        parser.error(str(error))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**3, 2 * 1024**3))
    # Keep completed checkpoints on failure; exclusive creation protects old reports.
    with args.output.open('x', encoding='utf-8') as stream:
        latest = {}
        def save(report):
            nonlocal latest
            latest = report
            stream.seek(0)
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
        try:
            run(sizes, args.body_chars, progress=save)
        except Exception as error:
            save({**latest, 'status': 'failed', 'error_class': type(error).__name__})
            print(f'Probe failed: {type(error).__name__}; completed checkpoints retained.', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
