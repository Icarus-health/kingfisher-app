"""Offline catalog-selection contracts at the real runner HTTP boundary."""
import hashlib
import json
from pathlib import Path
import subprocess

import httpx
import pytest

import probe_memory_pipeline as runner


def mock_transport(requests):
    def handler(request):
        requests.append(request)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [
                {'name': 'fixture-model', 'digest': 'synthetic-digest'}]})
        if request.url.path == '/api/version':
            return httpx.Response(200, json={'version': 'synthetic-version'})
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'template': 'synthetic', 'parameters': 'synthetic'})
        assert request.url.path == '/v1/chat/completions'
        return httpx.Response(200, json={'choices': [
            {'message': {'role': 'assistant', 'content': 'Synthetic answer'}}]})
    return httpx.MockTransport(handler)


def test_countercase_catalog_selects_its_case_at_the_real_adapter_boundary_and_records_blob_metadata(tmp_path):
    requests = []
    output = tmp_path / 'countercase.json'

    assert runner.main([
        '--catalog', 'countercases-v1', '--model', 'fixture-model',
        '--case', 'm3-sent-confirmed-01', '--output', str(output),
    ], transport=mock_transport(requests)) == 0

    report = json.loads(output.read_text())
    expected_bytes = (runner.REPO / 'docs/evaluations/memory-quality/development-countercases-v1.json').read_bytes()
    expected = {
        'selector': 'countercases-v1',
        'path': 'docs/evaluations/memory-quality/development-countercases-v1.json',
        'sha256': hashlib.sha256(expected_bytes).hexdigest(),
        'commit': runner.git_state()['commit'],
    }
    assert report['catalog'] == expected
    assert report['results'][0]['case_id'] == 'm3-sent-confirmed-01'
    assert report['results'][0]['catalog'] == expected
    assert [request.url.path for request in requests].count('/v1/chat/completions') == 1


def test_default_catalog_keeps_the_existing_development_case_behavior(tmp_path):
    requests = []
    output = tmp_path / 'development.json'

    assert runner.main([
        '--model', 'fixture-model', '--case', 'same-name-01', '--output', str(output),
    ], transport=mock_transport(requests)) == 0

    report = json.loads(output.read_text())
    assert report['suite'] == 'memory-pipeline-development-v1'
    assert report['catalog']['selector'] == 'development-v1'
    assert report['results'][0]['case_id'] == 'same-name-01'
    assert [request.url.path for request in requests].count('/v1/chat/completions') == 1


def test_catalog_wrapper_keeps_the_existing_replaceable_default_path(tmp_path, monkeypatch):
    source = json.loads((Path(__file__).resolve().parents[1] / 'docs/evaluations/memory-quality' /
                         'development-cases-v1.json').read_text())
    source[0]['id'] = 'compatibility-case'
    replacement = tmp_path / 'replacement.json'
    replacement.write_text(json.dumps([source[0]]))
    monkeypatch.setattr(runner, 'CATALOG', replacement)

    assert list(runner.catalog()) == ['compatibility-case']


def temporary_catalog_repo(tmp_path, monkeypatch, content):
    repo = tmp_path / 'repo'
    relative = 'docs/evaluations/memory-quality/development-cases-v1.json'
    path = repo / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    for command in (
        ['git', 'init', str(repo)],
        ['git', '-C', str(repo), 'add', relative],
        ['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
         'commit', '-m', 'catalog fixture'],
    ):
        subprocess.run(command, check=True, capture_output=True)
    monkeypatch.setattr(runner, 'REPO', repo)
    monkeypatch.setitem(runner.CATALOGS, 'development-v1', relative)
    return path


def test_dirty_catalog_is_rejected_before_any_local_model_request(tmp_path, monkeypatch):
    source = (Path(__file__).resolve().parents[1] / 'docs/evaluations/memory-quality' /
              'development-cases-v1.json').read_bytes()
    path = temporary_catalog_repo(tmp_path, monkeypatch, source)
    path.write_bytes(source + b'\n')
    requests = []

    with pytest.raises(ValueError, match='differs'):
        runner.main(['--model', 'fixture-model', '--case', 'same-name-01',
                     '--output', str(tmp_path / 'dirty.json')], transport=mock_transport(requests))

    assert requests == []


@pytest.mark.parametrize('content', [
    b'[{"id":"duplicate","id":"duplicate"}]',
    b'[{}]',
    b'[' + b','.join(b'{}' for _ in range(101)) + b']',
])
def test_invalid_committed_catalog_is_rejected_before_any_local_model_request(tmp_path, monkeypatch, content):
    temporary_catalog_repo(tmp_path, monkeypatch, content)
    requests = []

    with pytest.raises(ValueError):
        runner.main(['--model', 'fixture-model', '--case', 'anything',
                     '--output', str(tmp_path / 'invalid.json')], transport=mock_transport(requests))

    assert requests == []


def test_duplicate_case_ids_in_a_committed_catalog_are_rejected_before_any_local_model_request(tmp_path, monkeypatch):
    source = json.loads((Path(__file__).resolve().parents[1] / 'docs/evaluations/memory-quality' /
                         'development-cases-v1.json').read_text())
    content = json.dumps([source[0], source[0]]).encode()
    temporary_catalog_repo(tmp_path, monkeypatch, content)
    requests = []

    with pytest.raises(ValueError, match='Duplicate catalog case ID'):
        runner.main(['--model', 'fixture-model', '--case', 'ambiguous-mainz-01',
                     '--output', str(tmp_path / 'duplicates.json')], transport=mock_transport(requests))

    assert requests == []


def test_unknown_catalog_or_case_is_rejected_before_any_local_model_request(tmp_path):
    for arguments in (
        ['--catalog', 'unknown-v1', '--case', 'same-name-01'],
        ['--catalog', 'countercases-v1', '--case', 'same-name-01'],
    ):
        requests = []
        with pytest.raises(SystemExit):
            runner.main(['--model', 'fixture-model', '--output', str(tmp_path / 'no-request.json'), *arguments],
                        transport=mock_transport(requests))
        assert requests == []
