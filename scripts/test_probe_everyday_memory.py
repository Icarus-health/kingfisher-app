import hashlib
import json

import pytest

import probe_everyday_memory as everyday
from icarus_memory import local_embeddings
from probe_everyday_memory import RETRIEVAL_ARMS, cases, main, run
from memory_probe_support import validate_case


def test_frozen_new_cases_include_negative_retrieval_and_distinct_action_states():
    for mode,count in [('retrieval',22),('meaning',8)]:
        dataset=cases(mode)
        assert len(dataset)==len({c['id'] for c in dataset})==count
        for case in dataset:validate_case(case)
    assert sum(not c['expected_source_ids'] for c in cases('retrieval'))==2


def _forbidden(*args, **kwargs):
    raise AssertionError('This must not be constructed for a lexical-only run')


class _FakeEmbedder:
    """Simulates an installed local embedder without any network access."""
    is_local = True
    model_key = 'synthetic-embedder-key'

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def identity(self):
        return self.model_key

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_lexical_only_runs_offline_without_embedder_or_network(monkeypatch, tmp_path):
    # Blocks embedding initialization at three layers: the two names the
    # retrieval loop calls, and the network client the real LocalEmbedder
    # would open, so a regression cannot sneak past a single guard.
    monkeypatch.setattr(everyday, 'LocalEmbedder', _forbidden)
    monkeypatch.setattr(everyday, 'RefreshingKnowledgeSearch', _forbidden)
    monkeypatch.setattr(local_embeddings.httpx, 'Client', _forbidden)
    output = tmp_path / 'lexical.json'
    assert run('retrieval', str(output), 'unused-model', lexical_only=True) == 0
    report = json.loads(output.read_text())
    assert report['status'] == 'completed'
    assert report['arms_selected'] == ['lexical']
    assert report['arms_skipped'] == ['live_cold', 'live_warm']
    assert report['embedding_initialized'] is False
    assert 'embedding_model_key' not in report
    assert report['dataset_sha256'] == hashlib.sha256(
        json.dumps(cases('retrieval'), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_lexical_only_evaluates_all_22_cases_exactly_once(monkeypatch, tmp_path):
    monkeypatch.setattr(everyday, 'LocalEmbedder', _forbidden)
    output = tmp_path / 'once.json'
    assert run('retrieval', str(output), 'unused-model', lexical_only=True) == 0
    report = json.loads(output.read_text())
    assert [row['arm'] for row in report['results']] == ['lexical'] * 22
    assert sorted(row['case_id'] for row in report['results']) == sorted(c['id'] for c in cases('retrieval'))


def test_lexical_arm_result_is_sourced_from_delivered_provider_context(monkeypatch, tmp_path):
    """A bare search-candidate check would miss a provider-payload leak or drop;
    the reported source IDs must come from delivered_context's reconciliation."""
    monkeypatch.setattr(everyday, 'LocalEmbedder', _forbidden)
    real_delivered_context = everyday.delivered_context
    sentinel = ['synthetic-marker-from-delivered-context-only']
    seen = []

    def spy(fixture, turn, calls):
        result = real_delivered_context(fixture, turn, calls)
        seen.append(result)
        if len(seen) == 1:
            result = dict(result)
            result['provider_source_ids'] = sentinel
        return result

    monkeypatch.setattr(everyday, 'delivered_context', spy)
    output = tmp_path / 'sentinel.json'
    assert run('retrieval', str(output), 'unused-model', lexical_only=True) == 0
    report = json.loads(output.read_text())
    assert report['results'][0]['actual_source_ids'] == sentinel
    assert report['results'][1]['actual_source_ids'] != sentinel


def test_default_arms_remain_testable_with_simulated_embedder(monkeypatch, tmp_path):
    monkeypatch.setattr(everyday, 'LocalEmbedder', _FakeEmbedder)
    output = tmp_path / 'default.json'
    assert run('retrieval', str(output), 'unused-model') == 0
    report = json.loads(output.read_text())
    assert report['status'] == 'completed'
    assert report['arms_selected'] == list(RETRIEVAL_ARMS)
    assert report['arms_skipped'] == []
    assert report['embedding_initialized'] is True
    assert report['embedding_model_key'] == 'synthetic-embedder-key'
    assert {row['arm'] for row in report['results']} == {'lexical', 'live_cold', 'live_warm'}
    assert len(report['results']) == 22 * 3


def test_embedder_initialization_failure_reports_embedding_initialized_false(monkeypatch, tmp_path):
    """embedding_initialized must reflect whether __enter__ actually succeeded,
    not merely whether it was attempted -- a failed report must not claim it."""
    class ExplodingEmbedder:
        def __enter__(self):
            raise ConnectionError('synthetic: no local Ollama')
    monkeypatch.setattr(everyday, 'LocalEmbedder', lambda *a, **k: ExplodingEmbedder())
    output = tmp_path / 'embedder-failure.json'
    assert run('retrieval', str(output), 'unused-model') == 1
    report = json.loads(output.read_text())
    assert report['status'] == 'failed'
    assert report['error_type'] == 'ConnectionError'
    assert report['embedding_initialized'] is False
    assert report['results'] == []
    assert 'embedding_model_key' not in report


def test_lexical_only_failure_mid_run_is_reported_as_failed_not_success(monkeypatch, tmp_path):
    monkeypatch.setattr(everyday, 'LocalEmbedder', _forbidden)
    real_build_fixture = everyday.build_fixture
    built = []

    def flaky(case, root, provider):
        built.append(case['id'])
        if len(built) == 3:
            raise RuntimeError('synthetic interruption')
        return real_build_fixture(case, root, provider)

    monkeypatch.setattr(everyday, 'build_fixture', flaky)
    output = tmp_path / 'partial.json'
    assert run('retrieval', str(output), 'unused-model', lexical_only=True) == 1
    report = json.loads(output.read_text())
    assert report['status'] == 'failed'
    assert report['error_type'] == 'RuntimeError'
    assert len(report['results']) == 2


def test_existing_output_file_is_never_overwritten(tmp_path):
    output = tmp_path / 'existing.json'
    output.write_text('preserve-me')
    with pytest.raises(FileExistsError):
        run('retrieval', str(output), 'unused-model', lexical_only=True)
    assert output.read_text() == 'preserve-me'


def test_lexical_only_requires_retrieval_mode():
    with pytest.raises(ValueError):
        run('meaning', 'unused-output-path', 'unused-model', lexical_only=True)


def test_cli_rejects_lexical_only_with_meaning_mode(tmp_path):
    output = tmp_path / 'rejected.json'
    with pytest.raises(SystemExit):
        main(['--mode', 'meaning', '--output', str(output), '--lexical-only'])
    assert not output.exists()


def test_cli_lexical_only_flag_reaches_run(monkeypatch, tmp_path):
    monkeypatch.setattr(everyday, 'LocalEmbedder', _forbidden)
    output = tmp_path / 'cli.json'
    assert main(['--mode', 'retrieval', '--lexical-only', '--output', str(output)]) == 0
    report = json.loads(output.read_text())
    assert report['arms_selected'] == ['lexical']
