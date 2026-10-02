#!/usr/bin/env python3
"""Bounded synthetic prepared-memory diagnostic through the production adapter.

Standalone serial process only. Transport and business-clock overrides differ
from normal app operation and are always restored. No configuration, pull, tools,
external endpoint or personal store access. Semantic judgments require review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
from icarus_memory import agent as agent_module, providers
from memory_probe_support import RecordingProvider, score_retrieval, validate_case
from memory_probe_fixtures import build_fixture, business_clock, case_hash, clock_supplement

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / 'docs/evaluations/memory-quality/development-cases-v1.json'
CATALOGS = {
    'development-v1': 'docs/evaluations/memory-quality/development-cases-v1.json',
    'countercases-v1': 'docs/evaluations/memory-quality/development-countercases-v1.json',
}
CATALOG_MAX_BYTES = 1024 * 1024
CATALOG_MAX_CASES = 100
BASE = 'http://127.0.0.1:11434'
TIMEOUT = httpx.Timeout(60, connect=5, write=10, pool=5)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def _git_bytes(*args):
    try:
        return subprocess.run(['git', *args], cwd=REPO, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True, timeout=5).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Committed catalog blob is unavailable') from exc


def _catalog_cases(raw):
    if len(raw) > CATALOG_MAX_BYTES:
        raise ValueError('Catalog exceeds 1 MiB limit')
    try:
        rows = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError('Catalog is not valid JSON') from exc
    if not isinstance(rows, list):
        raise ValueError('Catalog must contain a JSON array')
    if len(rows) > CATALOG_MAX_CASES:
        raise ValueError('Catalog exceeds 100 case limit')
    cases = {}
    for row in rows:
        validate_case(row)
        if row['id'] in cases:
            raise ValueError('Duplicate catalog case ID')
        cases[row['id']] = row
    return cases


def load_catalog(selector='development-v1'):
    """Load one allowlisted catalog only after matching its current HEAD blob."""
    try:
        relative_path = CATALOGS[selector]
    except KeyError as exc:
        raise ValueError('Unknown catalog selector') from exc
    path = REPO / relative_path
    try:
        working_bytes = path.read_bytes()
    except OSError as exc:
        raise ValueError('Catalog working-tree file is unavailable') from exc
    committed_bytes = _git_bytes('show', 'HEAD:' + relative_path)
    if len(committed_bytes) > CATALOG_MAX_BYTES:
        raise ValueError('Committed catalog exceeds 1 MiB limit')
    if working_bytes != committed_bytes:
        raise ValueError('Catalog working tree differs from current HEAD')
    commit = _git_bytes('rev-parse', 'HEAD').decode('ascii').strip()
    if not commit:
        raise ValueError('Catalog commit is unavailable')
    return _catalog_cases(committed_bytes), {
        'selector': selector,
        'path': relative_path,
        'sha256': hashlib.sha256(committed_bytes).hexdigest(),
        'commit': commit,
    }


def catalog():
    """Compatibility wrapper for callers of the original default catalog API."""
    if CATALOG == REPO / CATALOGS['development-v1']:
        return load_catalog()[0]
    return _catalog_cases(CATALOG.read_bytes())


@contextmanager
def bounded_transport(transport=None):
    # Injectable MockTransport is a Python test seam, never a CLI URL/config knob.
    def factory(timeout=None):
        return httpx.Client(timeout=TIMEOUT, trust_env=False, follow_redirects=False, transport=transport)
    with patch.object(providers, '_http', factory):
        with factory() as client:
            yield client


def metadata(client, model):
    response = client.get(BASE + '/api/tags'); response.raise_for_status()
    installed = next((row for row in response.json()['models'] if row['name'] == model), None)
    if installed is None:
        raise ValueError('Requested model is not installed; pulling is prohibited')
    digest = installed.get('digest')
    if not isinstance(digest, str) or not digest:
        raise ValueError('Installed weight digest is unavailable')
    response = client.get(BASE + '/api/version'); response.raise_for_status()
    version_data = response.json()
    version = version_data.get('version') if isinstance(version_data, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ValueError('Ollama version is unavailable or malformed')
    response = client.post(BASE + '/api/show', json={'model': model}); response.raise_for_status()
    configuration = response.json()
    field_types = {'template': str, 'modelfile': str, 'parameters': str, 'details': dict, 'model_info': dict}
    if (not isinstance(configuration, dict) or not configuration
            or not any(key in configuration for key in field_types)
            or any(not isinstance(configuration[key], kind) for key, kind in field_types.items()
                   if key in configuration)):
        raise ValueError('Ollama model configuration is unavailable or malformed')
    configuration_hash = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    return dict(name=model, weight_digest=digest, ollama_version=version,
                configuration_sha256=configuration_hash,
                effective_runtime_parameters='unknown; production adapter sends no options',
                warm_cold_state='unknown')


def git_state():
    def git(*args):
        return subprocess.run(['git', *args], cwd=REPO, capture_output=True,
                              text=True, check=True, timeout=5).stdout.strip()
    return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain'))}


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def canonical_timestamp(value):
    """Unabhängige Normalisierung nur deklarierter Zeitfelder, niemals Freitext."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('Timestamp must be text or null')
    # Python 3.10 toleriert sonst ein übrig gebliebenes Z vor einem Offset.
    if 'Z' in value:
        if not value.endswith('Z') or 'Z' in value[:-1] or not value[-2:-1].isdigit():
            raise ValueError('Malformed UTC suffix')
        value = value[:-1] + '+00:00'
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return parsed.astimezone(timezone.utc).isoformat()


def expected_knowledge_v3(claim, episode):
    return {'format': 'knowledge-context-v3', 'assertion_id': 'claim:' + claim['id'],
            **{key: claim[key] for key in ('statement', 'subject_ref', 'target_ref', 'scope_ref', 'predicate', 'value')},
            'claim_created_at': canonical_timestamp(claim['created_at']),
            'valid_from': canonical_timestamp(claim['valid_from']), 'valid_until': canonical_timestamp(claim['valid_until']),
            'primary_evidence': {'episode_id': episode['id'], 'digest': episode['digest'],
                'source_type': episode['provenance']['source_type'], 'source_ref': episode['provenance']['source_ref'],
                'occurred_at': canonical_timestamp(episode['occurred_at']),
                'recorded_at': canonical_timestamp(episode['recorded_at'])}}


def normalize_record(record):
    if not isinstance(record, dict) or record.get('format') != 'knowledge-context-v3':
        return record
    for key in ('claim_created_at', 'valid_from', 'valid_until'):
        if key in record:
            record[key] = canonical_timestamp(record[key])
    source = record.get('primary_evidence')
    if isinstance(source, dict):
        for key in ('occurred_at', 'recorded_at'):
            if key in source:
                source[key] = canonical_timestamp(source[key])
    return record


def delivered_context(fixture, turn, calls):
    """Reconcile declared context and exact fixture-backed payload in both directions.

    Provenance-qualified complete knowledge records identify claims. Complete source
    text identifies additional exposure, including history leakage, but never turns
    a name-token match into retrieval. Unattributable knowledge records fail review.
    """
    manifest = json.loads(fixture.expected_manifest)
    actual, context_sources, mismatched, other = set(), set(), [], []
    declared = {}
    for item in turn.context.get('items', []):
        identifier = item.get('assertion_id', '')
        if not identifier.startswith('claim:') or identifier[6:] not in fixture.claim_ids:
            other.append(item)
            continue
        claim_id = identifier[6:]
        declared[claim_id] = item
        claim = manifest['claims'][claim_id]
        context_sources.update(fixture.source_ids[e['episode_id']] for e in claim['evidence'])
    messages = [(call_index, message_index, message['content'])
                for call_index, call in enumerate(calls)
                for message_index, message in enumerate(call['request']['messages'])
                if isinstance(message.get('content'), str)]
    remaining = {(call_index, index): text for call_index, index, text in messages}
    structured_records = []
    for call_index, index, text in messages:
        for line in text.splitlines():
            if not line.startswith('- [knowledge] {'):
                continue
            try:
                record = normalize_record(json.loads(line.removeprefix('- [knowledge] '), object_pairs_hook=unique_keys))
            except ValueError:
                continue
            if isinstance(record, dict) and record.get('format') in {'knowledge-context-v2', 'knowledge-context-v3'}:
                structured_records.append((call_index, index, line, record))
    actual_claims = []
    matched_claim_ids = set()
    source_matches = {}
    for claim_id, fixture_id in fixture.claim_ids.items():
        claim = manifest['claims'][claim_id]
        if not claim['evidence']:
            continue
        episode = manifest['sources'][claim['evidence'][0]['episode_id']]
        source = episode['provenance']['source_type']
        if episode['provenance']['source_ref']:
            source += ' ' + episode['provenance']['source_ref']
        prefix = f"- [knowledge] {claim['statement']} (Quelle: {source}; Auswahl: "
        pattern = re.compile(r'(?m)^' + re.escape(prefix) + r'[^\n]*\)(?=\n|$)')
        expected_record = {'format': 'knowledge-context-v2', 'assertion_id': 'claim:' + claim_id,
                           'statement': claim['statement'], 'subject_ref': claim['subject_ref'],
                           'target_ref': claim['target_ref'], 'scope_ref': claim['scope_ref'],
                           'source_type': episode['provenance']['source_type'],
                           'source_ref': episode['provenance']['source_ref']}
        expected_v3 = expected_knowledge_v3(claim, episode)
        identity_locations = []
        for call_index, index, line, record in structured_records:
            expected = expected_v3 if record['format'] == 'knowledge-context-v3' else expected_record
            if (set(record) == set(expected) | {'reason'} and isinstance(record['reason'], str)
                    and all(record[key] == value for key, value in expected.items())):
                identity_locations.append({'call': call_index, 'message': index})
                remaining[(call_index, index)] = remaining[(call_index, index)].replace(line, '')
        locations = list(identity_locations)
        for call_index, index, text in messages:
            matches = list(pattern.finditer(text))
            if matches:
                locations.append({'call': call_index, 'message': index})
                for match in matches:
                    remaining[(call_index, index)] = remaining[(call_index, index)].replace(match.group(), '')
        if locations:
            matched_claim_ids.add(claim_id)
            sources = {fixture.source_ids[e['episode_id']] for e in claim['evidence']}
            actual.update(sources)
            actual_claims.append({'physical_id': claim_id, 'fixture_id': fixture_id,
                                  'source_ids': sorted(sources), 'statement': claim['statement'],
                                  'evidence': [dict(physical_source_id=e['episode_id'],
                                                    fixture_source_id=fixture.source_ids[e['episode_id']],
                                                    quote=e['quote']) for e in claim['evidence']],
                                  'payload_locations': locations,
                                  'identity_payload_locations': identity_locations,
                                  'identity_refs': {key: expected_record[key] for key in
                                      ('subject_ref', 'target_ref', 'scope_ref')} if identity_locations else None})
            for evidence in claim['evidence']:
                source_matches.setdefault(evidence['episode_id'], set()).add('provenance_qualified_claim')
    # Independently detect complete raw sources, even without any selected claim.
    # This also catches explicit source text in other input messages/history.
    raw_source_locations = {}
    for physical_id, fixture_id in fixture.source_ids.items():
        body = manifest['sources'][physical_id]['body']
        locations = [{'call': call_index, 'message': index} for call_index, index, text in messages
                     if body and (body in text or json.dumps(body, ensure_ascii=False) in text)]
        if locations:
            actual.add(fixture_id)
            source_matches.setdefault(physical_id, set()).add('complete_source_text')
            raw_source_locations[physical_id] = locations
    # Forward check still verifies the precise declared record/reason in context.
    context_blocks = [call['request']['messages'][1]['content'] for call in calls
                      if len(call['request']['messages']) > 1]
    for claim_id, item in declared.items():
        source = item['source_type'] + (f" {item['source_ref']}" if item.get('source_ref') else '')
        line = f"- [knowledge] {item['statement']} (Quelle: {source}; Auswahl: {item['reason']})"
        declared_record = {'format': 'knowledge-context-v2', **{key: item.get(key) for key in
            ('assertion_id', 'statement', 'subject_ref', 'target_ref', 'scope_ref', 'source_type', 'source_ref', 'reason')}}
        if 'knowledge_projection' in item:
            declared_record = item['knowledge_projection']
        structured_match = any(index == 1 and record == declared_record
                               for _, index, _, record in structured_records)
        declared_match = (structured_match if 'subject_ref' in item
                          else any(line in block for block in context_blocks))
        if claim_id not in matched_claim_ids or not declared_match:
            mismatched.append(claim_id)
    undeclared_claims = sorted(matched_claim_ids - declared.keys())
    undeclared_sources = sorted(actual - context_sources)
    unattributed = [{'call': call_index, 'message': index, 'line': line}
                    for (call_index, index), text in remaining.items()
                    for line in text.splitlines() if line.startswith('- [knowledge]')]
    integrity = bool(mismatched or undeclared_claims or undeclared_sources or unattributed)
    return dict(expected_manifest=manifest, expected_manifest_sha256=hashlib.sha256(fixture.expected_manifest.encode()).hexdigest(),
                provider_source_ids=sorted(actual), selected_context_source_ids=sorted(context_sources),
                delivered_claims=actual_claims, payload_mismatch_claim_ids=mismatched,
                payload_undeclared_claim_ids=undeclared_claims,
                payload_undeclared_source_ids=undeclared_sources,
                payload_unattributed_knowledge=unattributed, payload_integrity_failure=integrity,
                payload_source_matches=[dict(physical_id=key, fixture_id=fixture.source_ids[key],
                    matched_by=sorted(value), raw_text_locations=raw_source_locations.get(key, []))
                    for key, value in sorted(source_matches.items())],
                other_context_items=other,
                calendar_source_ids=sorted(turn.context.get('calendar', {}).get('source_ids', []))
                    if turn.context.get('answer_mode') == 'calendar_data' else [])


def adjudicate(result, *, verdict, failure_labels, rationale, helpful_clarification=None):
    """Explicit reviewer annotation, never inferred from source overlap or keywords."""
    if verdict not in {'pass', 'fail', 'review_required'} or not rationale.strip():
        raise ValueError('A verdict and explicit review rationale are required')
    result['review'] = dict(verdict=verdict, failure_labels=list(failure_labels), rationale=rationale,
                            helpful_clarification=helpful_clarification)
    result['semantic_verdict'] = verdict


def reference_identity_payload(fixture, case, sources):
    """Only current prepared mappings backed entirely by delivered sources.

    This diagnostic is not Agent retrieval or a rights qualification. It adds no
    mutable registry labels, aliases, merges or historical assertion mappings.
    """
    from icarus_memory.context import KNOWLEDGE_IDENTITY_NOTE
    from icarus_memory.knowledge_context import evidence_chain_available
    permitted = {row['id'] for row in sources}
    claims = {key: fixture.claims.get(key) for key in fixture.claim_ids}
    def eligible(identifier, seen=frozenset()):
        if identifier in seen or identifier not in claims:
            return False
        claim = claims[identifier]
        if (not fixture.claims.is_usable(claim)
                or not evidence_chain_available(claim, fixture.claims, fixture.episodes)
                or not {fixture.source_ids[e.episode_id] for e in claim.evidence} <= permitted):
            return False
        return all(eligible(ref, seen | {identifier}) for ref in claim.depends_on)
    mappings = []
    for identifier, claim in claims.items():
        if eligible(identifier):
            mappings.append({'id': fixture.claim_ids[identifier], 'subject_ref': claim.subject_ref,
                             'target_ref': claim.target_ref, 'scope_ref': claim.scope_ref,
                             'source_ids': sorted({fixture.source_ids[e.episode_id] for e in claim.evidence})})
    refs = {row[key] for row in mappings for key in ('subject_ref', 'target_ref', 'scope_ref') if row[key]}
    entities = [{'id': row['id'], 'kind': row['kind']} for row in case['entities'] if row['id'] in refs]
    return {'format': 'reference-identity-context-v1', 'sources': sources, 'claims': mappings,
            'entities': entities, 'identity_semantics': KNOWLEDGE_IDENTITY_NOTE}


def run_attempt(case, root, provider, mode='agent', result=None):
    if mode not in {'agent', 'reference_context', 'reference_identity_context'}:
        raise ValueError('Unknown diagnostic mode')
    validate_case(case)
    result = result if result is not None else {}
    recorder = RecordingProvider(provider)
    started = time.monotonic()
    result.update(case_id=case['id'], scenario_id=case['scenario_id'], question=case['question'],
                  case_sha256=case_hash(case), mode=mode,
                  fixture_mode=case['fixture_mode'], status='incomplete', started_at=timestamp(),
                  semantic_verdict='review_required', severity=case['severity'],
                  expected_source_ids=case['expected_source_ids'], forbidden_source_ids=case['forbidden_source_ids'],
                  rubric_required=case['required'], rubric_forbidden=case['forbidden'],
                  diagnostic_clock_override=True, clock_utc=case['clock_utc'], timezone=case['timezone'],
                  clock_prompt_supplement=clock_supplement(case),
                  diagnostic_difference='Scoped clock and system-prompt supplement; empty self model and tools; prepared claims, no extraction',
                  helpful_clarification='review_required', failure_labels=[])
    fixture = None
    stage = 'fixture_setup' if mode in {'agent', 'reference_identity_context'} else 'reference_provider'
    try:
        with business_clock(case):
            result['diagnostic_system_prompt'] = agent_module.SYSTEM_PROMPT
            if mode == 'agent':
                fixture = build_fixture(case, root, recorder)
                result['knowledge_payload_version'] = 3
                result['expected_manifest'] = json.loads(fixture.expected_manifest)
                result['expected_manifest_sha256'] = hashlib.sha256(fixture.expected_manifest.encode()).hexdigest()
                stage = 'agent_execution'
                turn = fixture.agent.send(case['question'])
                result.update(answer=turn.reply, context=turn.context,
                              answer_mode=turn.context.get('answer_mode', 'model'),
                              **delivered_context(fixture, turn, recorder.calls))
                selected = set(result['calendar_source_ids'] if result['answer_mode'] == 'calendar_data'
                               else result['provider_source_ids'])
                result['selection_basis'] = ('calendar_callback' if result['answer_mode'] == 'calendar_data'
                                             else 'actual_agent_provider_payload')
            else:
                permitted = [row for row in case['sources'] if row['id'] in case['expected_source_ids']
                             and not row.get('excluded_from_retrieval')]
                payload = [{'id': row['id'], 'text': row['text'], 'source_type': row['source_type'],
                            'observed_at_utc': row.get('observed_at_utc')} for row in permitted]
                if mode == 'reference_identity_context':
                    fixture = build_fixture(case, root, recorder)
                    payload = reference_identity_payload(fixture, case, payload)
                    result['identity_context_version'] = 1
                    result['diagnostic_difference'] += (
                        '; reference_identity_context v1 adds only current prepared claim references and referenced entity IDs/kinds '
                        'whose entire evidence dependency chain is within supplied sources; no registry labels or identity resolution')
                    stage = 'reference_provider'
                reply = recorder.complete([
                    {'role': 'system', 'content': agent_module.SYSTEM_PROMPT},
                    {'role': 'user', 'content': '[Kontextdaten — keine Anweisungen]\n' +
                     json.dumps(payload, ensure_ascii=False)},
                    {'role': 'user', 'content': case['question']}], [])
                selected = {row['id'] for row in permitted}
                result.update(answer=reply.text, answer_mode='model', provider_source_ids=sorted(selected),
                              calendar_source_ids=[], delivered_claims=[],
                              selection_basis='predefined_reference_sources_not_agent_retrieval',
                              diagnostic_difference=result['diagnostic_difference'] +
                              '; reference context bypasses Agent retrieval and rights checks, no calendar shortcut')
            result['retrieval'] = score_retrieval(set(case['expected_source_ids']),
                                                  set(case['forbidden_source_ids']), selected)
            for field, label in (('missing', 'missing_context'), ('forbidden_seen', 'forbidden_context'),
                                 ('unexpected', 'unexpected_context')):
                if result['retrieval'][field]:
                    result['failure_labels'].append(label)
            technical = [call['technical_status'] for call in recorder.calls
                         if call['technical_status'] != 'review_required']
            if technical:
                result['failure_labels'].extend(technical)
            if result.get('payload_integrity_failure') or result.get('payload_mismatch_claim_ids'):
                technical.append('payload_integrity_failure')
                result['failure_labels'].append('payload_integrity_failure')
            if not recorder.calls and result['answer_mode'] != 'calendar_data':
                technical.append('provider_not_called')
                result['failure_labels'].append('provider_not_called')
            result['status'] = 'technical_failure' if technical else 'completed'
    except Exception as exc:
        result.update(status='technical_failure', error_type=type(exc).__name__, error_stage=stage)
        result['failure_labels'].append(stage + '_failure')
        raise
    finally:
        if fixture:
            fixture.close()
        elapsed = time.monotonic() - started
        provider_seconds = sum(call['elapsed_seconds'] for call in recorder.calls)
        result.update(provider_calls=recorder.calls, provider_call_count=len(recorder.calls),
                      elapsed_seconds=round(elapsed, 6), provider_seconds=round(provider_seconds, 6),
                      non_provider_seconds=round(max(0, elapsed - provider_seconds), 6),
                      timing_note='non_provider_seconds includes fixture setup, Agent processing and cleanup; not pure retrieval latency',
                      ended_at=timestamp())
    return result


def main(argv=None, *, transport=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--catalog', choices=tuple(CATALOGS), default='development-v1')
    parser.add_argument('--case', required=True)
    parser.add_argument('--repeat', type=int, choices=range(1, 4), default=1)
    parser.add_argument('--mode', choices=('agent', 'reference_context', 'reference_identity_context'), default='agent')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    cases, catalog_metadata = load_catalog(args.catalog)
    if args.case not in cases:
        parser.error('argument --case: invalid choice: ' + repr(args.case))
    record = dict(suite='memory-pipeline-development-v1', status='incomplete', started_at=timestamp(),
                  results=[], provider='OpenAICompatible', endpoint=BASE + '/v1', mode=args.mode,
                  catalog=catalog_metadata,
                  transport_override={'trust_env': False, 'follow_redirects': False,
                                      'timeout_seconds': dict(connect=5, read=60, write=10, pool=5),
                                      'content_retries': 0},
                  semantic_qualification=False, metadata_after=None, metadata_stable=None)
    # Existing output is rejected before any model or metadata request.
    with args.output.open('x', encoding='utf-8') as output:
        os.fchmod(output.fileno(), 0o600)
        def save():
            output.seek(0); json.dump(record, output, ensure_ascii=False, indent=2)
            output.truncate(); output.flush(); os.fsync(output.fileno())
        save()
        stage = 'git_metadata'
        try:
            record['git'] = git_state()
            with bounded_transport(transport) as client:
                stage = 'metadata_before'
                record['metadata_before'] = metadata(client, args.model)
                save()
                for repeat in range(args.repeat):
                    stage = 'attempt'
                    attempt = {'repeat': repeat + 1, 'status': 'incomplete', 'catalog': catalog_metadata}
                    record['results'].append(attempt); save()
                    try:
                        with tempfile.TemporaryDirectory(prefix='kingfisher-synthetic-probe-') as root:
                            provider = providers.OpenAICompatible(model=args.model, api_key='synthetic-local-probe',
                                                                  base_url=BASE + '/v1')
                            run_attempt(cases[args.case], Path(root), provider, args.mode, attempt)
                    finally:
                        save()
                stage = 'metadata_after'
                record['metadata_after'] = metadata(client, args.model)
                record['metadata_stable'] = record['metadata_before'] == record['metadata_after']
                if not record['metadata_stable']:
                    for attempt in record['results']:
                        attempt['failure_labels'].append('metadata_changed')
                record['status'] = ('completed' if record['metadata_stable'] and
                                    all(row['status'] == 'completed' for row in record['results'])
                                    else 'incomplete')
        except KeyboardInterrupt:
            record['error_type'] = 'KeyboardInterrupt'
            record['error_stage'] = stage
        except Exception as exc:
            # No raw model configuration or potentially private error payloads.
            record['error_type'] = type(exc).__name__
            record['error_stage'] = stage
        finally:
            record['ended_at'] = timestamp(); save()
    return 0 if record['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
