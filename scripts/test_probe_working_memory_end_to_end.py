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


@pytest.mark.parametrize('status', ['working_selection_failed', 'working_unavailable', 'local_only'])
def test_error_with_no_sources_is_not_successful_unknown(status):
    row = probe.evaluate({'q': 'q', 'expect': [], 'type': 'unanswerable'}, turn(status, []), {})
    assert row['exact_sources'] and not row['status_ok'] and not row['selection_pass']


def test_unknown_reference_cannot_be_silently_dropped():
    row = probe.evaluate({'q': 'q', 'expect': ['S1'], 'type': 'direct'},
                         turn('working_reports', ['e1', 'mystery']), {'e1': 'S1'})
    assert row['shown_sources'] == ['S1', 'unmapped:mystery']
    assert not row['selection_pass']


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
