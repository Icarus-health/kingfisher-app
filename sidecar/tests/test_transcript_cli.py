"""Exercise the actual local preview process with synthetic files."""
import json
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "preview_transcript.py"


def test_preview_preserves_export_and_returns_timed_segments(tmp_path):
    source = tmp_path / "meeting.srt"
    original = "1\n00:00:01,250 --> 00:00:03,000\nSynthetic meeting note.\n"
    source.write_text(original, encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["segments"] == [{
        "text": "Synthetic meeting note.", "start_ms": 1250,
        "end_ms": 3000, "speaker": None,
    }]
    assert source.read_text(encoding="utf-8") == original
    assert list(tmp_path.iterdir()) == [source]


def test_preview_rejects_invalid_utf8_without_partial_json(tmp_path):
    source = tmp_path / "bad.txt"
    source.write_bytes(b"\xff\xfe")
    result = subprocess.run([sys.executable, str(SCRIPT), str(source)], capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Cannot preview transcript" in result.stderr


def test_preview_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.srt"
    result = subprocess.run([sys.executable, str(SCRIPT), str(missing)], capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Cannot preview transcript" in result.stderr


def test_preview_rejects_unknown_extension_as_format(tmp_path):
    source = tmp_path / "mystery.txtx"
    source.write_text("01:23", encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(source)], capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Cannot preview transcript" in result.stderr


def test_preview_runs_without_site_packages(tmp_path):
    source = tmp_path / 'standalone.txt'
    source.write_text('Independent preview', encoding='utf-8')
    result = subprocess.run([sys.executable, '-I', '-S', str(SCRIPT), str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['segments'][0]['text'] == 'Independent preview'
