"""A concurrently created destination must survive the native restore path."""
from pathlib import Path

import pytest

from icarus_memory import Provenance, SourceType, TaskStore
from icarus_memory.recovery_bundle import export_bundle, restore_bundle


def test_restore_cannot_replace_target_created_after_last_exists_check(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    store = TaskStore(source / 'tasks.sqlite3')
    store.add('Künstliche Aufgabe', Provenance(source_type=SourceType.USER_STATED))
    store.close()
    env = tmp_path / 'historical.env'
    env.write_text('ICARUS_SIDECAR_TOKEN=synthetic-token\n')
    bundle = export_bundle(source, env, tmp_path / 'synthetic.icarus', 'synthetic-password-1234')
    target = tmp_path / 'new-copy'
    exists = Path.exists
    checks = 0
    def racing_exists(path):
        nonlocal checks
        if path == target:
            checks += 1
            if checks == 2:
                target.mkdir()  # appeared after the last observed absence
                return False
        return exists(path)
    monkeypatch.setattr(Path, 'exists', racing_exists)
    with pytest.raises(OSError):
        restore_bundle(bundle, target, 'synthetic-password-1234')
    assert target.is_dir() and list(target.iterdir()) == []
    assert bundle.exists()
    assert not list(tmp_path.glob('.kingfisher-restore-*'))
