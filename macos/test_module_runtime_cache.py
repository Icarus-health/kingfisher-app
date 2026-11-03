"""Native public-cache contracts, using synthetic HTTP/process/files and no installed app state."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def runtime_cache_binary(tmp_path_factory):
    if sys.platform != 'darwin' or not shutil.which('swiftc'):
        pytest.skip('Native runtime preparation requires macOS Swift')
    build = tmp_path_factory.mktemp('module-runtime-cache-build')
    sources = [ROOT / 'macos/App/Logic/ModuleRuntimeContract.swift',
               ROOT / 'macos/App/ModuleRuntimeCache.swift', ROOT / 'macos/App/Paths.swift',
               ROOT / 'macos/tests/module_runtime_cache/main.swift']
    binary = build / 'cache-contract'
    result = subprocess.run(['swiftc', '-module-cache-path', str(build / 'modules'),
                             *map(str, sources), '-o', str(binary)],
                            capture_output=True, text=True, timeout=120)
    (build / 'compile.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    return binary


@pytest.mark.parametrize('scenario', [
    'pins', 'builder', 'invalid-images', 'archive-paths', 'inventory', 'escaping-link',
    'special-file', 'hard-link', 'cache-hit', 'cache-tamper', 'extra-file',
    'manifest-fifo', 'resource-fifo', 'hash-fifo',
    'verified-existing', 'verified-existing-digest', 'verified-existing-deleted', 'verified-existing-path',
    'publish-cancel', 'publish-deadline', 'publish-commit-cancel', 'publish-commit-deadline',
    'publish-cleanup-retry', 'publish-existing',
    'resource-tamper', 'root-symlink', 'manifest-mode', 'mutable-manifest', 'staging-metadata', 'cleanup-scope', 'cancelled', 'wrong-download',
    'http-status', 'http-redirect', 'http-length', 'http-cancelled', 'http-active-cancel',
    'process-environment', 'process-cancelled', 'process-active-cancel', 'process-timeout',
])
def test_runtime_cache_boundary(runtime_cache_binary, tmp_path, scenario):
    result = subprocess.run([str(runtime_cache_binary), scenario, str(tmp_path), str(ROOT)],
                            env={'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path), 'TMPDIR': str(tmp_path)},
                            capture_output=True, text=True, timeout=2 if 'fifo' in scenario else 20)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report == {'passed': scenario}
