import json
import stat
from pathlib import Path
import pytest
from icarus_memory.backup import BackupError
from icarus_memory.crypto import DecryptionError, seal_json, unseal_json
from icarus_memory.mac_calendar import MacCalendar
from icarus_memory.recovery_bundle import export_bundle, restore_bundle, MAGIC
from icarus_memory.tasks import TaskStore
from icarus_memory.model import Provenance, SourceType

PASSWORD = 'synthetic-recovery-password'


def sample(tmp_path):
    data = tmp_path / 'data'
    tasks = TaskStore(data / 'tasks.sqlite3')
    task = tasks.add('Erhaltene Aufgabe', Provenance(source_type=SourceType.USER_STATED))
    tasks.close()
    MacCalendar(data / 'mac-calendar.sqlite3').enable()
    config = tmp_path / 'private.env'
    config.write_text('ICARUS_SECRETS_PASSPHRASE=synthetic-store-password\n')
    (data / 'schluessel.icarus').write_text('synthetic-encrypted-keys')
    bundle = export_bundle(data, config, tmp_path / 'safe.kingfisher', PASSWORD)
    return bundle, task


def test_all_data_and_configuration_restore_to_new_target(tmp_path):
    bundle, task = sample(tmp_path)
    assert 'synthetic-store-password' not in bundle.read_text()
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o600
    result = restore_bundle(bundle, tmp_path / 'restored', PASSWORD)
    restored = TaskStore(result / 'data/tasks.sqlite3')
    assert restored.get(task.id).title == task.title
    restored.close()
    assert MacCalendar(result / 'data/mac-calendar.sqlite3').read()['enabled']
    assert 'synthetic-store-password' in (result / 'settings.env').read_text()
    assert (result / 'data/schluessel.icarus').read_text() == 'synthetic-encrypted-keys'
    with pytest.raises(BackupError):
        restore_bundle(bundle, result, PASSWORD)


def test_wrong_password_tampering_and_path_escape_leave_no_target(tmp_path):
    bundle, _ = sample(tmp_path)
    target = tmp_path / 'restored'
    with pytest.raises(DecryptionError):
        restore_bundle(bundle, target, 'wrong-password')
    assert not target.exists()
    payload = unseal_json(bundle.read_text(), PASSWORD)
    payload['files']['../escape'] = 'eA=='
    bundle.write_text(seal_json(payload, PASSWORD, MAGIC))
    with pytest.raises(BackupError):
        restore_bundle(bundle, target, PASSWORD)
    assert not target.exists() and not (tmp_path / 'escape').exists()
    envelope = json.loads(bundle.read_text())
    envelope['tag'] = 'AA=='
    bundle.write_text(json.dumps(envelope))
    with pytest.raises(DecryptionError):
        restore_bundle(bundle, target, PASSWORD)
    assert not target.exists()


def test_invalid_manifest_content_cleans_partial_restore(tmp_path):
    bundle, _ = sample(tmp_path)
    payload = unseal_json(bundle.read_text(), PASSWORD)
    payload['files']['tasks.sqlite3'] = 'bm90LWEtZGF0YWJhc2U='
    bundle.write_text(seal_json(payload, PASSWORD, MAGIC))
    with pytest.raises(BackupError):
        restore_bundle(bundle, tmp_path / 'restored', PASSWORD)
    assert not (tmp_path / 'restored').exists()
    assert not list(tmp_path.glob('.kingfisher-restore-*'))


def test_cli_wrong_password_is_concise_and_leaves_data_alone(tmp_path, monkeypatch, capsys):
    import sys
    from icarus_memory.recovery_bundle import main
    bundle, _ = sample(tmp_path)
    target = tmp_path / 'restored'
    monkeypatch.setattr(sys, 'argv', ['recovery', 'restore', '--bundle', str(bundle), '--target', str(target)])
    monkeypatch.setattr('getpass.getpass', lambda _: 'wrong-password')
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    output = capsys.readouterr()
    assert 'Passwort prüfen' in output.err
    assert 'Traceback' not in output.err
    assert not target.exists()


def test_app_version_is_encrypted_restored_and_optional(tmp_path):
    bundle, _ = sample(tmp_path)
    legacy = restore_bundle(bundle, tmp_path/'legacy', PASSWORD)
    assert not (legacy/'app-version.json').exists()
    image = 'sha256:'+'a'*64
    versioned = export_bundle(legacy/'data', legacy/'settings.env', tmp_path/'versioned.recovery', PASSWORD, image_id=image)
    assert image not in versioned.read_text()
    restored = restore_bundle(versioned, tmp_path/'versioned', PASSWORD)
    assert json.loads((restored/'app-version.json').read_text()) == {'image':image}
    assert stat.S_IMODE((restored/'app-version.json').stat().st_mode)==0o600


@pytest.mark.parametrize('image', ['latest', '../escape', {'image':'invalid'}, 'sha256:'+'x'*64])
def test_invalid_saved_version_is_rejected_before_writing(tmp_path, image):
    bundle, _ = sample(tmp_path)
    payload=unseal_json(bundle.read_text(), PASSWORD)
    payload['app_image']=image
    bundle.write_text(seal_json(payload, PASSWORD, MAGIC))
    with pytest.raises(BackupError, match='App-Version'):
        restore_bundle(bundle, tmp_path/'restored', PASSWORD)
    assert not (tmp_path/'restored').exists()
