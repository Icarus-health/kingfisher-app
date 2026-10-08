"""The full-path report must not award false positives or call cloud endpoints."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import probe_working_memory_end_to_end as probe
from icarus_memory.providers import Reply


def turn(status, ids):
    return SimpleNamespace(reply='synthetic', context={
        'answer_contract': {'status': status},
        'working_answer': {'refs': [{'episode_id': i} for i in ids]},
        'source_links': [{'episode_id': i} for i in ids]})


def test_extra_source_is_not_exact_success():
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'direct'},
                         turn('working_reports', ['e1', 'e2']), {'e1': 'S1', 'e2': 'S2'})
    assert row['retrieved_expected'] and not row['exact_sources'] and not row['selection_pass']


def test_candidate_selection_and_display_are_measured_separately():
    result = turn('working_unknown', [])
    result.context['working_answer']['basis'] = [{'episode_id': 'e1'}]
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'paraphrase'}, result, {'e1': 'S1'})
    assert row['candidate_trace_available'] is True
    assert row['expected_in_candidates'] is True
    assert row['expected_in_selection'] is False
    assert row['expected_in_display'] is False
    assert row['first_missing_stage'] == 'selection'


def test_selected_source_rejected_by_sentence_step_is_a_display_loss():
    result = turn('working_unknown', ['e1'])
    result.context['source_links'] = []
    result.context['working_answer']['basis'] = [{'episode_id': 'e1'}]
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'paraphrase'}, result, {'e1': 'S1'})
    assert row['expected_in_candidates'] is True and row['expected_in_selection'] is True
    assert row['expected_in_display'] is False and row['first_missing_stage'] == 'display'


def test_missing_candidate_trace_does_not_claim_measured_retrieval_loss():
    result = SimpleNamespace(reply='unknown', context={'answer_contract': {'status': 'unknown'}})
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'paraphrase'}, result, {'e1': 'S1'})
    assert row['candidate_trace_available'] is False
    assert row['expected_in_candidates'] is None
    assert row['first_missing_stage'] == 'unobserved'


def test_observed_empty_candidates_are_a_retrieval_loss():
    result = turn('working_unknown', [])
    result.context['working_answer']['basis'] = []
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'paraphrase'}, result, {'e1': 'S1'})
    assert row['candidate_trace_available'] is True
    assert row['expected_in_candidates'] is False and row['first_missing_stage'] == 'retrieval'


@pytest.mark.parametrize('status', ['working_selection_failed', 'working_unavailable', 'local_only'])
def test_error_with_no_sources_is_not_successful_unknown(status):
    row = probe.evaluate({'q': 'q', 'expect': [], 'type': 'unanswerable'}, turn(status, []), {})
    assert row['exact_sources'] and not row['status_ok'] and not row['selection_pass']


def test_unknown_reference_cannot_be_silently_dropped():
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'direct'},
                         turn('working_reports', ['e1', 'mystery']), {'e1': 'S1'})
    assert row['shown_sources'] == ['S1', 'unmapped:mystery']
    assert not row['selection_pass']


@pytest.mark.parametrize('invalid', [{}, 'broken', {'episode_id': None}])
def test_malformed_displayed_reference_blocks_a_successful_score(invalid):
    result = turn('working_reports', ['e1'])
    result.context['source_links'].append(invalid)
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'direct'}, result, {'e1': 'S1'})
    assert not row['references_valid'] and not row['selection_pass']


class Unavailable:
    name = model = 'unavailable'
    is_local = True

    def complete_json(self, *args, **kwargs):
        from icarus_memory.providers import ProviderError
        raise ProviderError('synthetic outage')


def test_meter_retains_synthetic_model_output_for_stage_diagnosis():
    class Synthetic:
        name = model = 'synthetic'
        is_local = True

        def complete_json(self, *args, **kwargs):
            return Reply(text='{"status":"unknown"}')

    meter = probe.Meter(Synthetic())
    meter.complete_json([{'role': 'system', 'content': 'Synthetic selection'}])
    assert meter.outputs(0) == [{'state': 'ok', 'call_kind': 'json',
                                 'reply': '{"status":"unknown"}', 'reply_truncated': False}]


def test_meter_failure_is_recorded_without_invented_reply():
    meter = probe.Meter(Unavailable())
    with pytest.raises(Exception, match='synthetic outage'):
        meter.complete_json([])
    assert meter.outputs(0) == [{'state': 'failed', 'call_kind': 'json'}]


def test_meter_bounds_output_and_marks_truncation():
    class LongSynthetic:
        name = model = 'synthetic'
        is_local = True

        def complete(self, *args, **kwargs):
            return Reply(text='x' * 4100)

    meter = probe.Meter(LongSynthetic())
    meter.complete([])
    output = meter.outputs(0)[0]
    assert len(output['reply']) == 4000 and output['reply_truncated'] is True


def test_model_outage_does_not_earn_successful_unknowns(monkeypatch):
    monkeypatch.delenv('ICARUS_MEMORY_SEMANTIC', raising=False)
    report = probe.run(Unavailable(), sentences=False)
    assert report['score']['unanswerable']['exact_source_and_status'] == 0
    rows = [r for r in report['rows'] if r['type'] == 'unanswerable']
    assert all(r['provider_errors'] > 0 and not r['selection_pass'] for r in rows)


def test_cloud_address_rejected_before_any_request(monkeypatch):
    monkeypatch.setattr(probe.httpx, 'Client', lambda **kw: pytest.fail('Network before address check'))
    with pytest.raises(ValueError, match='loopback'):
        probe.local_provider('m', 'https://api.openai.com/v1')


def test_existing_output_never_overwritten(tmp_path):
    target = tmp_path / 'report.json'
    target.write_text('retained')
    result = subprocess.run([sys.executable, str(Path(probe.__file__)), '--model', 'x',
        '--output', str(target)], capture_output=True, text=True)
    assert result.returncode != 0 and target.read_text() == 'retained'


class AllSources:
    name = model = 'synthetic-offline'
    is_local = True

    def complete_json(self, messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in data['sources']]}))
        return Reply(text='{}')  # real deterministic fallback for question understanding


def test_run_exercises_agent_and_withdrawal_offline(monkeypatch):
    monkeypatch.delenv('ICARUS_MEMORY_SEMANTIC', raising=False)
    monkeypatch.setattr(probe.httpx, 'Client', lambda **kw: pytest.fail('Offline run made a request'))
    report = probe.run(AllSources(), sentences=False, limit=1)
    assert report['synthetic_only'] and report['partial_catalog']
    assert report['catalog_sha256'] == probe.catalog_digest()
    row = report['rows'][0]
    assert row['status'] == 'working_reports' and row['shown_sources'] == ['S1']
    assert row['answer'] and row['calls'] >= 2
    assert report['withdrawal']['checked'] and report['withdrawal']['pass']
    assert report['sentence_verifier'] == 'not_used_quote_mode'
    assert report['diagnostic_version'] == 2
    assert row['candidate_trace_available'] is True
    assert row['expected_in_candidates'] and row['expected_in_selection'] and row['expected_in_display']
    assert row['first_missing_stage'] is None
    assert len(row['model_outputs']) == row['calls']
