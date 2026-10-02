"""Der Mac-Sicherungsstarter startet die App auch nach fehlgeschlagener Sicherung."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('recovery_launcher', Path(__file__).resolve().parents[2] / 'scripts/create_recovery_bundle.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize('running', [True, False])
@pytest.mark.parametrize('fail', [True, False])
def test_restart_and_no_password_in_arguments(tmp_path, monkeypatch, running, fail):
    config = tmp_path / 'settings.env'
    config.write_text('ICARUS_SIDECAR_TOKEN=test-token\nICARUS_SECRETS_PASSPHRASE=test-key-passphrase\n')
    calls = []
    password = 'synthetic-secure-password'
    def call(docker, arguments, **kwargs):
        calls.append(arguments)
        assert password not in json.dumps(arguments)
        if arguments[0] == 'inspect':
            return SimpleNamespace(stdout=json.dumps({'image':'sha256:test', 'running':running, 'env':config.read_text().splitlines(),
                'mounts':[{'Destination':'/data','Type':'volume','Name':'synthetic-data'}]}))
        if '-i' in arguments:
            assert json.loads(kwargs['input'])['password'] == password
            assert '--network' in arguments and 'none' in arguments
            if fail:
                raise subprocess.CalledProcessError(1, arguments)
        return SimpleNamespace(stdout='')
    monkeypatch.setattr(launcher, 'docker_call', call)
    if fail:
        with pytest.raises(subprocess.CalledProcessError):
            launcher.backup('docker', 'test', config, tmp_path / 'out', password)
    else:
        output = launcher.backup('docker', 'test', config, tmp_path / 'out', password)
        assert output.suffix == '.recovery'
    assert (['stop','test'] in calls) is running
    assert (['start','test'] in calls) is running
    if running:
        assert calls[-2] == ['start','test']
        assert calls[-1][:2] == ['exec','test']


def test_parallel_backup_is_rejected_before_stopping_app(tmp_path, monkeypatch):
    import fcntl
    config = tmp_path / 'settings.env'
    config.write_text('SYNTHETIC=yes')
    with config.with_suffix('.env.recovery.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(launcher, 'docker_call', lambda *args, **kwargs: pytest.fail('Docker darf nicht gestartet werden'))
        with pytest.raises(ValueError, match='bereits'):
            launcher.backup('docker','test',config,tmp_path/'out','synthetic-secure-password')


@pytest.mark.parametrize('change', ['wrong-passphrase', 'missing-passphrase', 'wrong-provider', 'duplicate'])
def test_mismatched_configuration_is_rejected_before_stop(tmp_path, monkeypatch, change):
    config = tmp_path / 'settings.env'
    original = 'ICARUS_SIDECAR_TOKEN=test-token\nICARUS_SECRETS_PASSPHRASE=correct-passphrase\nICARUS_MODEL=local-model\n'
    altered = original
    if change == 'wrong-passphrase': altered = original.replace('correct-passphrase', 'wrong-passphrase')
    if change == 'missing-passphrase': altered = original.replace('ICARUS_SECRETS_PASSPHRASE=correct-passphrase\n', '')
    if change == 'wrong-provider': altered = original.replace('local-model', 'other-model')
    if change == 'duplicate': altered += 'ICARUS_MODEL=local-model\n'
    config.write_text(altered)
    calls = []
    def call(docker, arguments, **kwargs):
        calls.append(arguments[0])
        assert arguments[0] == 'inspect', 'Die App darf noch nicht angehalten werden.'
        return SimpleNamespace(stdout=json.dumps({'image':'sha256:test','running':True,
            'env':original.splitlines(), 'mounts':[]}))
    monkeypatch.setattr(launcher, 'docker_call', call)
    with pytest.raises(ValueError) as error:
        launcher.backup('docker','test',config,tmp_path/'out','synthetic-secure-password')
    assert 'correct-passphrase' not in str(error.value) and 'wrong-passphrase' not in str(error.value)
    assert calls == ['inspect'] and not (tmp_path/'out').exists()


def test_configuration_values_are_literal_and_allow_empty_values(tmp_path):
    config = tmp_path/'settings.env'
    values = ['ICARUS_SIDECAR_TOKEN=test-token', 'ICARUS_SECRETS_PASSPHRASE=literal-$(not-a-command)', 'ICARUS_MODEL=']
    config.write_text('# Kommentar\n'+'\n'.join(values)+'\n')
    launcher.validate_configuration(config, values + ['PATH=/usr/bin'])


def test_backup_uses_validated_copy_when_original_changes(tmp_path, monkeypatch):
    config = tmp_path/'settings.env'
    original = 'ICARUS_SIDECAR_TOKEN=test-token\nICARUS_SECRETS_PASSPHRASE=correct-passphrase\n'
    config.write_text(original)
    def call(docker, arguments, **kwargs):
        if arguments[0] == 'inspect':
            config.write_text('ICARUS_SECRETS_PASSPHRASE=changed\n')
            return SimpleNamespace(stdout=json.dumps({'image':'sha256:test','running':False,
                'env':original.splitlines(), 'mounts':[{'Destination':'/data','Type':'volume','Name':'test'}]}))
        if '-i' in arguments:
            mount = next(arg for arg in arguments if 'target=/configuration,' in arg)
            path = Path(mount.split('source=',1)[1].split(',target=',1)[0])
            assert path != config and path.read_text() == original
            assert path.stat().st_mode & 0o777 == 0o600
        return SimpleNamespace(stdout='')
    monkeypatch.setattr(launcher, 'docker_call', call)
    launcher.backup('docker','test',config,tmp_path/'out','synthetic-secure-password')
    assert not list(tmp_path.glob('.kingfisher-backup-*'))
