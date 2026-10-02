#!/usr/bin/env python3
"""Synthetic German retrieval comparison. No chat inference or personal stores.

PYTHONPATH=sidecar .venv/bin/python scripts/probe_hybrid_memory.py --output /tmp/new.json
The installed bge-m3 model is used on fixed loopback only, without downloads.
Ten predefined development cases, two arms each; no semantic answer qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import httpx
from icarus_memory.knowledge_search import HybridKnowledgeSearch
from icarus_memory.providers import Reply
from memory_probe_fixtures import build_fixture, business_clock
from memory_probe_support import RecordingProvider, score_retrieval
from probe_memory_pipeline import delivered_context


from icarus_memory.local_embeddings import LocalEmbedder


DOCUMENTS = [
    'Der Zuschuss für das Atlasvorhaben wurde bewilligt.',
    'Die Dienstreise nach München erfolgt mit der Bahn.',
    'Am Dienstag findet eine Besprechung zur Personalplanung statt.',
    'Der Hersteller übernimmt Reparaturen innerhalb von zwei Jahren.',
    'Alex Winter im Einkauf ist unter einkauf@example.invalid erreichbar.',
    'Alex Winter an der Schule ist unter schule@example.invalid erreichbar.',
    'Der Entwurf der Nachricht wurde vorbereitet. Ein Versand ist nicht belegt.',
    'Die Präsentation wurde abgesagt.',
    'Für das Atlasvorhaben war zuvor ein Zuschuss beantragt. Eine Bewilligung lag damals nicht vor.',
]


def cases():
    questions = [
        ('funding', 'Welche Finanzierung ist genehmigt?', ['S1']),
        ('travel', 'Welches Verkehrsmittel nutzen wir auf dem Weg in die bayerische Landeshauptstadt?', ['S2']),
        ('staffing', 'Was steht zur Planung der Belegschaft an?', ['S3']),
        ('repairs', 'Welche Frist gilt für Instandsetzungen?', ['S4']),
        ('ambiguous', 'Welche Adresse gehört zu Alex Winter?', ['S5', 'S6']),
        ('specific', 'Wo erreiche ich Alex Winter aus dem Einkauf?', ['S5']),
        ('action', 'Wurde die Nachricht abgeschickt?', ['S7']),
        ('absent', 'Welche Farbe hat mein Fahrrad?', []),
        ('withdrawn', 'Welche Finanzierung ist genehmigt?', []),
        ('expired', 'Welche Finanzierung ist genehmigt?', []),
    ]
    result = []
    for name, question, expected in questions:
        sources = [dict(id=f'S{i}', text=text, source_type='document') for i, text in enumerate(DOCUMENTS, 1)]
        assertions = [dict(id=f'C{i}', subject_ref=f'topic:record-{i}', predicate='observed_note',
                           value=text, source_id=f'S{i}') for i, text in enumerate(DOCUMENTS, 1)]
        # Old application status is explicitly expired in every case.
        assertions[8]['valid_to_utc'] = '2026-09-12T00:00:00Z'
        if name == 'withdrawn':
            sources[0].update(excluded_from_retrieval=True, exclusion_reason='Synthetic withdrawal')
        if name == 'expired': assertions[0]['valid_to_utc'] = '2026-09-12T00:00:00Z'
        result.append(dict(id='hybrid-' + name, scenario_id=name, split='development', fixture_mode='prepared_memory',
            clock_utc='2026-09-13T07:00:00Z', timezone='Europe/Berlin', question=question, sources=sources,
            entities=[dict(id=f'topic:record-{i}', kind='topic', label=f'Synthetic record {i}') for i in range(1, 10)],
            assertions=assertions, expected_source_ids=expected,
            forbidden_source_ids=['S9'] + (['S1'] if name in {'withdrawn', 'expired'} else []),
            required=['Expected original evidence reaches actual provider input.'],
            forbidden=['Unavailable evidence reaches provider input.'], severity='retrieval'))
    return result


class CaptureOnly:
    is_local = True
    name = 'synthetic-capture-only'
    model = 'no-chat-model'

    def complete(self, messages, tools):
        if tools: raise ValueError('Diagnostic must have no tools')
        return Reply(text='Synthetic payload capture; no answer evaluated.', model=self.model)


def compare(embedder, dataset, *, results=None, checkpoint=lambda: None):
    results = [] if results is None else results
    deadline = time.monotonic() + 300
    with tempfile.TemporaryDirectory(prefix='kingfisher-hybrid-synthetic-') as temporary:
        for case in dataset:
            if time.monotonic() >= deadline:
                break
            fixture = build_fixture(case, Path(temporary) / case['id'], CaptureOnly())
            try:
                with business_clock(case):
                    start = time.monotonic()
                    search = HybridKnowledgeSearch.prepare(fixture.claims, fixture.episodes.support_snapshot,
                                                           list(fixture.claim_ids), embedder)
                    preparation = time.monotonic() - start
                    for mode in ('lexical', 'hybrid'):
                        recorder = RecordingProvider(CaptureOnly())
                        agent = fixture.agent.scoped(recorder, frozenset())
                        agent._knowledge_search = search if mode == 'hybrid' else None
                        start = time.monotonic()
                        turn = agent.send(case['question'])
                        elapsed = time.monotonic() - start
                        delivery = delivered_context(fixture, turn, recorder.calls)
                        score = score_retrieval(expected=set(case['expected_source_ids']),
                                                actual=set(delivery['provider_source_ids']),
                                                forbidden=set(case['forbidden_source_ids']))
                        results.append(dict(case_id=case['id'], mode=mode, question=case['question'],
                            preparation_seconds=preparation, retrieval_seconds=elapsed,
                            actual_source_ids=delivery['provider_source_ids'], expected_source_ids=case['expected_source_ids'],
                            retrieval=score, payload_mismatch_claim_ids=delivery['payload_mismatch_claim_ids'],
                            metadata=turn.context.get('knowledge_retrieval'), provider_calls=recorder.calls,
                            answer_quality='not_evaluated'))
                        checkpoint()
            finally:
                fixture.close()
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    dataset = cases()  # Frozen before any model request, including negative controls.
    manifest = json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode()
    report = dict(format='hybrid-memory-development-v1', qualification=False, planned_attempts=20,
                  dataset_sha256=hashlib.sha256(manifest).hexdigest(), cases=dataset,
                  git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  chat_model_calls=0, local_embedding_only=True, results=[], status='started')
    # Reserve an exclusive result before any network call; failures leave a visible record.
    with args.output.open('x', encoding='utf-8') as stream:
        def checkpoint():
            stream.seek(0); json.dump(report, stream, ensure_ascii=False, indent=2); stream.truncate(); stream.flush()
        checkpoint()
        try:
            with LocalEmbedder() as embedder:
                report['model_key'] = embedder.model_key
                compare(embedder, dataset, results=report['results'], checkpoint=checkpoint)
                report['weights_unchanged'] = embedder.identity() == embedder.model_key
                report['status'] = 'completed' if len(report['results']) == 20 and report['weights_unchanged'] else 'incomplete'
        except (Exception, KeyboardInterrupt) as exc:
            report.update(status='failed', error=type(exc).__name__)
            raise
        finally:
            checkpoint()
    print(json.dumps({key: value for key, value in report.items() if key not in {'cases', 'results'}}, ensure_ascii=False))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
