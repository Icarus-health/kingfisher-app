"""The local launcher never inherits the old process's provider authority."""
import os
import sys
from types import SimpleNamespace

from .test_recovery_working_runtime import working_data, environment


def test_launcher_uses_clean_child_environment_and_loopback_only(tmp_path, monkeypatch):
    from icarus_memory import recovery_workspace_cli as cli
    data = working_data(tmp_path)
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-inherited-key')
    monkeypatch.setenv('KF_HARNESS_MODE', 'synthetic-old-harness')
    monkeypatch.setenv('HTTPS_PROXY', 'https://synthetic.invalid')
    seen = []
    def run(argv, **kwargs):
        seen.append((argv, kwargs))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(cli.subprocess, 'run', run)
    assert cli.main(['serve', '--folder', str(data.parent), '--port', '8895']) == 0
    assert len(seen) == 1
    argv, options = seen[0]
    assert argv[:3] == [sys.executable, '-m', 'uvicorn']
    assert argv[argv.index('--host') + 1] == '127.0.0.1'
    assert argv[argv.index('--port') + 1] == '8895'
    assert 'OPENAI_API_KEY' not in options['env']
    assert 'KF_HARNESS_MODE' not in options['env']
    assert 'HTTPS_PROXY' not in options['env']
    assert options['env']['ICARUS_RECOVERY_BOOT_ID'] == 'a' * 32
    assert os.environ['OPENAI_API_KEY'] == 'synthetic-inherited-key'


def test_launcher_refuses_unbound_configuration_without_starting(tmp_path, monkeypatch, capsys):
    from icarus_memory import recovery_workspace_cli as cli
    data = working_data(tmp_path)
    (tmp_path / 'settings.env').write_text('OPENAI_API_KEY=private-value\n')
    def forbidden(*args, **kwargs):
        raise AssertionError('Must not start a child from historical environment')
    monkeypatch.setattr(cli.subprocess, 'run', forbidden)
    assert cli.main(['serve', '--folder', str(tmp_path)]) != 0
    assert 'private-value' not in capsys.readouterr().out


def test_explicit_container_mode_binds_inside_container_only(tmp_path, monkeypatch):
    from icarus_memory import recovery_workspace_cli as cli
    data = working_data(tmp_path)
    marker = tmp_path / '.dockerenv'
    marker.touch()
    monkeypatch.setattr(cli, 'CONTAINER_MARKER', marker, raising=False)
    calls = []
    monkeypatch.setattr(cli.subprocess, 'run', lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0))
    assert cli.main(['serve', '--folder', str(data.parent), '--port', '8890', '--container']) == 0
    assert calls[0][calls[0].index('--host') + 1] == '0.0.0.0'


def test_container_bind_on_native_host_refuses_without_child(tmp_path, monkeypatch):
    from icarus_memory import recovery_workspace_cli as cli
    data = working_data(tmp_path)
    monkeypatch.setattr(cli, 'CONTAINER_MARKER', tmp_path / 'absent-marker', raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('Container bind must never run on the native host')
    monkeypatch.setattr(cli.subprocess, 'run', forbidden)
    assert cli.main(['serve', '--folder', str(data.parent), '--container']) == 1


def test_clean_container_start_finds_packaged_ui_without_inherited_environment(tmp_path, monkeypatch):
    from icarus_memory import server
    monkeypatch.delenv(server.UI_ENV, raising=False)
    # Simulate an installed wheel, without the repository's Vite build fallback.
    module = tmp_path / 'wheel' / 'icarus_memory' / 'server.py'
    monkeypatch.setattr(server, '__file__', str(module))
    assets = tmp_path / 'packaged-ui'
    assets.mkdir()
    (assets / 'index.html').write_text('<main>Kingfisher</main>')
    monkeypatch.setattr(server, 'PACKAGED_UI_DIR', assets, raising=False)
    assert server._ui_dir() == assets
