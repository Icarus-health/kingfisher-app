"""Exercise native leave acknowledgement without starting a window."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_leave_requires_exact_ack_and_completes_once(tmp_path):
    compiler = shutil.which('swiftc')
    if not compiler:
        pytest.skip('Swift compiler unavailable')
    binary = tmp_path / 'draft-leave'
    result = subprocess.run([compiler, '-module-cache-path', str(tmp_path / 'cache'),
        str(ROOT / 'macos/Shared/DraftLeaveAttempt.swift'),
        str(ROOT / 'macos/tests/draft_leave/main.swift'), '-o', str(binary)],
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert 'timeout boundaries passed' in result.stdout
