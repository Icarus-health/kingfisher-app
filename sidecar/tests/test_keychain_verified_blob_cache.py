"""Real encryption; only verified identical bytes/passphrase may reuse decoding."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from icarus_memory import crypto, secrets
from icarus_memory.secrets import Keychain, PASSPHRASE_ENV

KEY = 'MISTRAL_API_KEY'
SALT = 'CLOUD_IMPORT_MISTRAL_REVISION'
PASSWORD = 'synthetic-verified-cache-passphrase'


def prepared(tmp_path, monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, PASSWORD)
    keys = Keychain(data_dir=tmp_path)
    keys.set(KEY, 'synthetic-key-one')
    keys.set(SALT, 'synthetic-salt-one')
    return keys


def count_derivations(monkeypatch):
    calls = []
    original = crypto.derive
    def derive(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(crypto, 'derive', derive)
    return calls


def test_unchanged_get_reads_actual_bytes_but_derives_only_once(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    calls = count_derivations(monkeypatch)
    reads = []
    original = os.fdopen
    def fdopen(*args, **kwargs):
        stream = original(*args, **kwargs)
        read = stream.read
        def read_bytes(*read_args, **read_kwargs):
            reads.append(1)
            return read(*read_args, **read_kwargs)
        stream.read = read_bytes
        return stream
    monkeypatch.setattr(os, 'fdopen', fdopen)
    assert keys.get(KEY) == 'synthetic-key-one'
    assert keys.get(SALT) == 'synthetic-salt-one'
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == 1
    assert len(reads) == 3


def test_returned_mapping_mutation_cannot_poison_authenticated_cache(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    calls = count_derivations(monkeypatch)
    first = keys._read_file()
    first[KEY] = 'synthetic-forged-key'
    first.clear()
    assert keys.get(KEY) == 'synthetic-key-one'
    assert keys._read_file()[SALT] == 'synthetic-salt-one'
    assert len(calls) == 1


def test_same_length_and_mtime_external_blob_replacement_is_observed(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    old_bytes = keys.secrets_path.read_bytes()
    old_stat = keys.secrets_path.stat()
    replacement = crypto.seal_json({KEY: 'synthetic-key-two', SALT: 'synthetic-salt-two'}, PASSWORD, secrets.SECRETS_MAGIC).encode()
    assert len(replacement) == len(old_bytes) and replacement != old_bytes
    calls = count_derivations(monkeypatch)
    keys.secrets_path.write_bytes(replacement)
    os.utime(keys.secrets_path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    assert keys.secrets_path.stat().st_mtime_ns == old_stat.st_mtime_ns
    assert keys.get(KEY) == 'synthetic-key-two'
    assert keys.get(SALT) == 'synthetic-salt-two'
    assert len(calls) == 1


def test_changed_passphrase_fails_closed_then_requires_fresh_authentication(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    calls = count_derivations(monkeypatch)
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-wrong-passphrase')
    assert keys.get(KEY) is None
    monkeypatch.setenv(PASSPHRASE_ENV, PASSWORD)
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == 2


def test_missing_passphrase_clears_previous_authenticated_entry(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    calls = count_derivations(monkeypatch)
    monkeypatch.delenv(PASSPHRASE_ENV)
    assert keys.get(KEY) is None
    monkeypatch.setenv(PASSPHRASE_ENV, PASSWORD)
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == 1


@pytest.mark.parametrize('bad', ['{broken', '[]', '{"format":"other"}', 'invalid_mac', 'deep_json', 'invalid_iterations'])
def test_malformed_or_tampered_blob_clears_old_authority_and_restored_blob_reauthenticates(tmp_path, monkeypatch, bad):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    original = keys.secrets_path.read_bytes()
    if bad in {'invalid_mac', 'invalid_iterations'}:
        envelope = json.loads(original)
        if bad == 'invalid_mac':
            envelope['tag'] = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        else:
            envelope['kdf']['iterations'] = 2**100
        broken = json.dumps(envelope).encode()
    elif bad == 'deep_json':
        broken = b'[' * 2000 + b'0' + b']' * 2000
    else:
        broken = bad.encode()
    calls = count_derivations(monkeypatch)
    keys.secrets_path.write_bytes(broken)
    assert keys.get(KEY) is None
    after_failure = len(calls)
    keys.secrets_path.write_bytes(original)
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == after_failure + 1


@pytest.mark.parametrize('failure', ['removed', 'read_error'])
def test_missing_or_unreadable_file_clears_old_entry(tmp_path, monkeypatch, failure):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    original = keys.secrets_path.read_bytes()
    calls = count_derivations(monkeypatch)
    if failure == 'removed':
        keys.secrets_path.unlink()
        assert keys.get(KEY) is None
        keys.secrets_path.write_bytes(original)
    else:
        original_open = os.fdopen
        def unreadable(*args, **kwargs):
            stream = original_open(*args, **kwargs)
            def failed_read(*read_args, **read_kwargs):
                raise OSError('synthetic unreadable file')
            stream.read = failed_read
            return stream
        with monkeypatch.context() as nested:
            nested.setattr(os, 'fdopen', unreadable)
            assert keys.get(KEY) is None
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == 1


def test_successful_write_and_delete_invalidate_previously_verified_blob(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    calls = count_derivations(monkeypatch)
    keys.set(KEY, 'synthetic-key-two')
    after_write = len(calls)
    assert keys.get(KEY) == 'synthetic-key-two'
    assert len(calls) == after_write + 1
    assert keys.get(KEY) == 'synthetic-key-two'
    assert len(calls) == after_write + 1
    keys.delete(KEY)
    after_delete = len(calls)
    assert keys.get(KEY) is None
    assert keys.get(SALT) == 'synthetic-salt-one'
    assert len(calls) == after_delete + 1


@pytest.mark.parametrize('operation', ['set', 'delete', 'delete_missing'])
def test_failed_write_and_even_noop_delete_clear_cached_blob(tmp_path, monkeypatch, operation):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    calls = count_derivations(monkeypatch)
    def fail(*args, **kwargs):
        raise OSError('synthetic failed atomic write')
    with monkeypatch.context() as nested:
        nested.setattr(secrets, 'write_text_atomic', fail)
        if operation == 'delete_missing':
            keys.delete('SYNTHETIC_ABSENT_KEY')
        else:
            with pytest.raises(OSError):
                if operation == 'set':
                    keys.set(KEY, 'synthetic-key-two')
                else:
                    keys.delete(KEY)
    before_get = len(calls)
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == before_get + 1


def test_concurrent_get_waits_for_same_instance_save_and_returns_new_authority(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    entered, release, read_finished = threading.Event(), threading.Event(), threading.Event()
    original = secrets.write_text_atomic
    def blocked_write(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(*args, **kwargs)
    monkeypatch.setattr(secrets, 'write_text_atomic', blocked_write)
    result, errors = [], []
    def save():
        try:
            keys.set(KEY, 'synthetic-key-two')
        except BaseException as exc:
            errors.append(type(exc).__name__)
    def read():
        result.append(keys.get(KEY))
        read_finished.set()
    writer = threading.Thread(target=save)
    reader = threading.Thread(target=read)
    writer.start()
    assert entered.wait(2)
    try:
        reader.start()
        assert not read_finished.wait(.05), 'get returned old authority during an unfinished save'
    finally:
        release.set()
        writer.join(2)
        reader.join(2)
    assert not writer.is_alive() and not reader.is_alive()
    assert errors == [] and result == ['synthetic-key-two']


def test_concurrent_reads_of_bad_external_blob_never_reuse_old_authority(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    keys.secrets_path.write_bytes(b'{broken')
    results = []
    threads = [threading.Thread(target=lambda: results.append(keys.get(KEY))) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
    assert all(not thread.is_alive() for thread in threads)
    assert results == [None] * 4


def test_native_backend_reads_are_not_cached_or_redirected_through_files(tmp_path, monkeypatch):
    keys = Keychain(data_dir=tmp_path)
    keys._backend = 'macos'
    results = iter(['synthetic-native-one', 'synthetic-native-two'])
    calls = []
    def run(command):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=next(results))
    monkeypatch.setattr(secrets, '_run', run)
    monkeypatch.setattr(keys, '_read_file', lambda: pytest.fail('Native storage must not use file cache'))
    assert keys.get(KEY) == 'synthetic-native-one'
    assert keys.get(KEY) == 'synthetic-native-two'
    assert len(calls) == 2


def test_verified_entries_are_private_to_each_keychain_instance(tmp_path, monkeypatch):
    first = prepared(tmp_path, monkeypatch)
    second = Keychain(data_dir=tmp_path)
    calls = count_derivations(monkeypatch)
    assert first.get(KEY) == 'synthetic-key-one'
    assert second.get(KEY) == 'synthetic-key-one'
    assert first.get(SALT) == second.get(SALT) == 'synthetic-salt-one'
    assert len(calls) == 2


@pytest.mark.parametrize('change', ['key', 'salt', 'delete_key', 'delete_salt'])
def test_source_revision_immediately_observes_other_instance_key_or_salt_changes(tmp_path, monkeypatch, change):
    from icarus_memory.cloud_import_provider import credential_status
    keys = prepared(tmp_path, monkeypatch)
    settings = SimpleNamespace(cloud_models={})
    environment = {KEY: 'synthetic-key-one'}
    before = credential_status(keys, settings, environment, provider='mistral')
    assert before['available']
    other = Keychain(data_dir=tmp_path)
    if change == 'key':
        other.set(KEY, 'synthetic-key-two')
        environment[KEY] = 'synthetic-key-two'
    elif change == 'salt':
        other.set(SALT, 'synthetic-salt-two')
    else:
        other.delete(KEY if change == 'delete_key' else SALT)
    after = credential_status(keys, settings, environment, provider='mistral')
    if change.startswith('delete_'):
        assert not after['available'] and after['credential_revision'] is None
    else:
        assert after['available'] and after['credential_revision'] != before['credential_revision']


def fifo_read_result_without_leaving_blocked_thread(keys):
    """Record the original deadline, then release a broken implementation safely."""
    result, errors = [], []
    def read():
        try:
            result.append(keys.get(KEY))
        except BaseException as exc:
            errors.append(type(exc).__name__)
    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    thread.join(.25)
    blocked = thread.is_alive()
    if blocked:
        # The RED implementation blocks opening the FIFO for reading. A bounded
        # synthetic writer lets it return so no test worker/thread is stranded.
        writer = os.open(keys.secrets_path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(writer, b'{broken')
        finally:
            os.close(writer)
        thread.join(2)
    assert not thread.is_alive(), 'synthetic FIFO reader did not terminate after cleanup'
    return blocked, result, errors


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='FIFO path is POSIX-only')
@pytest.mark.parametrize('linked', [False, True])
def test_nonregular_fifo_is_rejected_without_blocking_and_clears_cache(tmp_path, monkeypatch, linked):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    original = keys.secrets_path.read_bytes()
    calls = count_derivations(monkeypatch)
    keys.secrets_path.unlink()
    if linked:
        target = tmp_path / 'synthetic-fifo-target'
        os.mkfifo(target, 0o600)
        keys.secrets_path.symlink_to(target.name)
    else:
        os.mkfifo(keys.secrets_path, 0o600)
    blocked, result, errors = fifo_read_result_without_leaving_blocked_thread(keys)
    keys.secrets_path.unlink()
    keys.secrets_path.write_bytes(original)
    assert not blocked, 'file-keychain read blocked on a nonregular FIFO'
    assert result == [None] and errors == []
    assert keys.get(KEY) == 'synthetic-key-one'
    assert len(calls) == 1, 'nonregular rejection must invalidate previously authenticated bytes'


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='FIFO path is POSIX-only')
def test_regular_to_fifo_replacement_between_path_check_and_open_is_rejected(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    original = keys.secrets_path.read_bytes()
    original_is_file = Path.is_file
    replaced = []
    def replace_after_check(path):
        result = original_is_file(path)
        if path == keys.secrets_path and not replaced:
            replaced.append(1)
            path.unlink()
            os.mkfifo(path, 0o600)
        return result
    monkeypatch.setattr(Path, 'is_file', replace_after_check)
    blocked, result, errors = fifo_read_result_without_leaving_blocked_thread(keys)
    if replaced:
        keys.secrets_path.unlink()
        keys.secrets_path.write_bytes(original)
    assert replaced == [1]
    assert not blocked, 'a path-only regular-file check must not permit a blocking FIFO race'
    assert result == [None] and errors == []


def test_existing_regular_file_symlink_remains_allowed(tmp_path, monkeypatch):
    keys = prepared(tmp_path, monkeypatch)
    assert keys.get(KEY) == 'synthetic-key-one'
    target = tmp_path / 'synthetic-linked-encrypted-key-file'
    keys.secrets_path.rename(target)
    keys.secrets_path.symlink_to(target.name)
    assert keys.secrets_path.is_file()
    assert keys.get(KEY) == 'synthetic-key-one'
    assert Keychain(data_dir=tmp_path).get(SALT) == 'synthetic-salt-one'
