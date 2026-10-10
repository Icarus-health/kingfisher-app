"""Actual native coordinator with synthetic consent/recognition/speech; no microphone or OS permission."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.skipif(shutil.which('swiftc') is None, reason='Swift unavailable')
def test_native_voice_contract(tmp_path):
    binary = tmp_path / 'voice-contract'
    command = ['swiftc', '-module-cache-path', str(tmp_path / 'modules'),
               str(ROOT / 'macos/Shared/NativeVoice.swift'),
               str(ROOT / 'macos/tests/voice/main.swift'), '-o', str(binary)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Native voice contract passed' in result.stdout
