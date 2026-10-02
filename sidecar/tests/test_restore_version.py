"""Eine Sicherung kann mit einer gewählten lokalen Version separat geöffnet werden."""
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('restore_version', Path(__file__).resolve().parents[2] / 'scripts/restore_recovery_bundle.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
IMAGE = 'sha256:' + 'a' * 64


def test_explicit_version_is_pinned_without_inspecting_current_container(tmp_path, monkeypatch):
    bundle = tmp_path / 'saved.recovery'
    bundle.write_bytes(b'synthetic')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if command[1:3] == ['image', 'inspect']:
            assert command[-1] == 'kingfisher:previous'
            return SimpleNamespace(stdout=IMAGE+'\n')
        assert command[1] == 'run' and IMAGE in command
        assert '--network' in command and 'none' in command
        assert 'synthetic-password' not in command
        assert 'synthetic-password' in kwargs['input']
        return SimpleNamespace(stdout='')
    monkeypatch.setattr(launcher.subprocess, 'run', run)
    launcher.restore('docker', 'current-app', bundle, tmp_path/'restored', 'synthetic-password', image='kingfisher:previous')
    assert len(calls) == 2
    assert all('current-app' not in call for call in calls)


def test_missing_local_version_does_not_start_or_create_target(tmp_path, monkeypatch):
    bundle = tmp_path/'saved.recovery'
    bundle.write_bytes(b'synthetic')
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(launcher.subprocess, 'run', run)
    target=tmp_path/'new-parent'/'restored'
    with pytest.raises(subprocess.CalledProcessError):
        launcher.restore('docker', None, bundle, target, 'synthetic-password', image='missing-version')
    assert len(calls)==1 and calls[0][1:3]==['image','inspect']
    assert not target.parent.exists()


def test_existing_container_default_remains_supported(monkeypatch):
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=IMAGE)
    monkeypatch.setattr(launcher.subprocess,'run',run)
    assert launcher.resolve_image('docker','current-app')==IMAGE
    assert calls==[['docker','inspect','--format','{{.Image}}','current-app']]


@pytest.mark.parametrize('saved, explicit, missing', [(True, False, False), (False, False, False), (True, True, False), (True, False, True)])
def test_open_app_uses_saved_version_unless_explicitly_overridden(tmp_path, monkeypatch, saved, explicit, missing):
    import sys, json
    old = 'sha256:'+'b'*64
    target=tmp_path/'restored'
    bundle=tmp_path/'saved.recovery'
    bundle.write_bytes(b'synthetic')
    argv=['restore','--container','current','--bundle',str(bundle),'--target',str(target),'--open-app']
    if explicit: argv += ['--image', IMAGE]
    monkeypatch.setattr(sys,'argv',argv)
    monkeypatch.setattr(launcher.getpass,'getpass',lambda _: 'synthetic-password')
    def resolve(docker, container=None, image=None):
        if missing and image == old:
            raise subprocess.CalledProcessError(1, ['docker','image','inspect',old])
        return image or IMAGE
    monkeypatch.setattr(launcher,'resolve_image',resolve)
    def restore(*args, **kwargs):
        target.mkdir()
        if saved: (target/'app-version.json').write_text(json.dumps({'image':old}))
        return target
    monkeypatch.setattr(launcher,'restore',restore)
    installs=[]
    starts=[]
    monkeypatch.setitem(sys.modules,'open_restored_app',SimpleNamespace(
        install=lambda path,image: installs.append(image),
        start=lambda docker,path,image: starts.append(image) or 'http://127.0.0.1:9999'))
    monkeypatch.setattr(launcher.subprocess,'run',lambda *a,**kw: SimpleNamespace(returncode=0))
    launcher.main()
    expected=old if saved and not explicit else IMAGE
    assert installs==starts==([] if missing else [expected])
    assert target.is_dir()
