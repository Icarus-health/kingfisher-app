"""Startfreigaben prüfen, ohne Docker oder den echten Datenbestand anzufassen."""
from pathlib import Path
import os
import subprocess

import pytest


@pytest.fixture
def launcher(tmp_path):
    root = Path(__file__).resolve().parents[2]
    (tmp_path / 'Makefile').write_text((root / 'Makefile').read_text())
    (tmp_path / '.kingfisher.env').write_text('SYNTHETIC=yes\n')
    executable = tmp_path / 'fake-compose'
    executable.write_text('#!/bin/sh\ncat > compose-input\nexit 23\n')
    executable.chmod(0o700)
    return tmp_path


def run_start(path, folder=None):
    env = {**os.environ, 'NOTIZEN': folder or ''}
    return subprocess.run(
        ['make', '--no-print-directory', 'start', 'COMPOSE=./fake-compose'],
        cwd=path, env=env, text=True, capture_output=True, timeout=10,
    )


@pytest.mark.parametrize('saved', [False, True])
@pytest.mark.parametrize('alias', [False, True])
def test_root_rejected_before_docker_and_preserves_source(launcher, saved, alias):
    folder = '/'
    if alias:
        link = launcher / 'root-link'
        link.symlink_to('/', target_is_directory=True)
        folder = str(link)
    source = launcher / '.kingfisher.sources'
    original = folder + '\n' if saved else '/previous-source\n'
    source.write_text(original)
    result = run_start(launcher, None if saved else folder)
    assert result.returncode != 0
    assert 'gesamte Rechner' in result.stdout
    assert not (launcher / 'compose-input').exists()
    assert source.read_text() == original


def test_explicit_folder_with_spaces_and_apostrophe_is_read_only(launcher):
    folder = launcher / "Lenas 'Notizen'"
    folder.mkdir()
    result = run_start(launcher, str(folder))
    # Der Fake beendet vor Healthcheck und Browserstart.
    assert result.returncode != 0
    yaml = (launcher / 'compose-input').read_text()
    escaped = str(folder.resolve()).replace("'", "''")
    assert f"'{escaped}:/notizen:ro'" in yaml
    assert (launcher / '.kingfisher.sources').read_text() == str(folder.resolve()) + '\n'
