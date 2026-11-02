"""Compile real native lifecycle code with synthetic command/HTTP boundaries; never launch Docker."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def native_main_service(tmp_path_factory):
    if sys.platform != 'darwin':
        pytest.skip('Native startup requires macOS Security')
    compiler = shutil.which('swiftc')
    if not compiler:
        pytest.skip('Swift compiler unavailable')
    build = tmp_path_factory.mktemp('native-main-service-build')
    app = ROOT / 'macos/App'
    sources = sorted((app / 'Logic').glob('*.swift')) + [app / name for name in
        ('Paths.swift', 'Docker.swift', 'Updater.swift', 'Startup.swift')]
    sources.append(ROOT / 'macos/tests/main_service/main.swift')
    binary = build / 'main-service'
    result = subprocess.run([compiler, '-module-cache-path', str(build / 'cache'),
                             *map(str, sources), '-o', str(binary)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    return binary


def run_native(binary, tmp_path, scenario):
    # No inherited credentials, application paths or real Docker process enter the native fixture.
    result = subprocess.run([str(binary), scenario, str(tmp_path)],
                            env={'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path),
                                 'TMPDIR': str(tmp_path)},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['unexpected'] == []
    return report


@pytest.mark.parametrize('scenario, expected', [
    ('multiple', 'main-container'), ('main-only', 'main-container'),
    ('worker-only', 'none'), ('lookup-failed', 'none'),
])
def test_project_lookup_never_selects_optional_worker(native_main_service, tmp_path, scenario, expected):
    report = run_native(native_main_service, tmp_path, scenario)
    assert report['outcome'] == expected


def test_key_adoption_uses_main_container_when_worker_is_listed_first(native_main_service, tmp_path):
    report = run_native(native_main_service, tmp_path, 'adopt-keys')
    assert report['outcome'] == 'synthetic-main-token'
    assert 'ICARUS_SECRETS_PASSPHRASE=synthetic-main-passphrase' in report['environment']
    inspections = [event[-1] for event in report['events'] if event[0] == 'inspect']
    assert inspections == ['main-container', 'main-container']


@pytest.mark.parametrize('scenario, pulls', [
    ('startup-existing', []), ('startup-first', [['pull', 'kingfisher']]),
])
def test_startup_selects_only_main_service_without_dependencies(native_main_service, tmp_path, scenario, pulls):
    report = run_native(native_main_service, tmp_path, scenario)
    assert report['worker_started'] is False
    assert report['worker_pulled'] is False
    assert [event for event in report['events'] if event[0] == 'pull'] == pulls
    assert [event for event in report['events'] if event[0] == 'up'] == [['up', '-d', '--no-deps', 'kingfisher']]
    # The fake intentionally stops at health readiness, before any Mac app discovery.
    assert report['outcome'].startswith('failed(')


def test_update_does_not_pull_or_start_optional_service(native_main_service, tmp_path):
    report = run_native(native_main_service, tmp_path, 'update-success')
    assert report['outcome'] == 'updated'
    assert report['worker_started'] is False
    assert report['worker_pulled'] is False
    assert [event for event in report['events'] if event[0] in ('backup', 'pull', 'up')] == [
        ['backup'], ['pull', 'kingfisher'], ['up', '-d', '--no-deps', 'kingfisher']]
    assert 'ICARUS_SIDECAR_TOKEN=synthetic-token' in report['environment']
    assert 'ICARUS_SECRETS_PASSPHRASE=synthetic-passphrase' in report['environment']


def test_failed_update_restores_offline_and_restarts_only_exact_previous_main_image(native_main_service, tmp_path):
    report = run_native(native_main_service, tmp_path, 'update-rollback')
    assert report['outcome'].startswith('rolledBack(')
    assert report['worker_started'] is False
    assert report['worker_pulled'] is False
    operations = [event for event in report['events'] if event[0] in ('backup', 'pull', 'up', 'stop', 'run')]
    assert operations == [
        ['backup'], ['pull', 'kingfisher'], ['up', '-d', '--no-deps', 'kingfisher'],
        ['stop', 'kingfisher'],
        ['run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'kingfisher',
         '-m', 'icarus_memory.update_restore', 'vor-update-20261008T120000Z'],
        ['up', '-d', '--no-deps', 'kingfisher']]
    assert report['image_id'] == 'sha256:' + 'a' * 64
    assert report['image'] == 'kingfisher:rollback-aaaaaaaaaaaaaaaa'


def test_rollback_rejects_wrong_previous_image(native_main_service, tmp_path):
    report = run_native(native_main_service, tmp_path, 'rollback-wrong-image')
    assert report['outcome'] == 'broken'
