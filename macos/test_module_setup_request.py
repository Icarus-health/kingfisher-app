"""No downloaded SDK, Docker, keys or app are used to test the native bridge."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_module_setup_cannot_select_authority(tmp_path):
    compiler = shutil.which('swiftc')
    if not compiler:
        pytest.skip('Swift compiler unavailable')
    binary = tmp_path / 'bridge'
    compiled = subprocess.run([compiler, '-module-cache-path', str(tmp_path / 'cache'),
        str(ROOT / 'macos/App/Logic/ModuleSetupRequest.swift'),
        str(ROOT / 'macos/tests/module_setup/main.swift'), '-o', str(binary)],
        text=True, capture_output=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '25 closed-request cases and cancellation passed'
