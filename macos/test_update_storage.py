"""Exercise the compiled native updater, replacing only external Docker/HTTP boundaries."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
GIB = 1024**3
GOOD = dict(root_available_bytes=8*GIB, root_available_inodes=10000,
            data_available_bytes=8*GIB, data_available_inodes=10000,
            backup_bytes=10*1024**2, backup_files=10)

@pytest.fixture(scope='module')
def native_updater(tmp_path_factory):
    compiler = shutil.which('swiftc')
    if not compiler:
        pytest.skip('Swift compiler unavailable')
    binary = tmp_path_factory.mktemp('native-update-build') / 'updater'
    app = REPO / 'macos/App'
    sources = sorted((app / 'Logic').glob('*.swift')) + [app / name for name in
        ('Paths.swift', 'Docker.swift', 'Updater.swift')]
    sources.append(REPO / 'macos/tests/update_storage/main.swift')
    result = subprocess.run([compiler, '-module-cache-path', str(binary.parent/'cache'), *map(str, sources), '-o', str(binary)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return binary

FAKE_DOCKER = r'''
import json, os, pathlib, sys
root = pathlib.Path(os.environ['FIXTURE_DIR'])
args = sys.argv[1:]
def record(event):
    with (root/'trace').open('a') as stream: stream.write(event+'\n')
if args[:1] == ['compose']:
    if 'ps' in args: print('container-test')
    elif 'pull' in args:
        record('pull'); (root/'pulled').touch()
    elif 'up' in args:
        record('restart')
        text = (root/'kingfisher.env').read_text()
        image = [line.split('=',1)[1] for line in text.splitlines() if line.startswith('KINGFISHER_IMAGE=')][-1]
        (root/'image').write_text(image)
    else: record('other-compose')
elif args[:1] == ['inspect']:
    if args[2] == '{{json .Mounts}}': print('[]')
    else: print('sha256:'+'a'*64+'|'+(root/'image').read_text())
elif args[:2] == ['image','tag']: record('pin')
elif args[:1] == ['exec']:
    record('probe')
    phase = 'after' if (root/'pulled').exists() else 'before'
    status = json.loads((root/'status.json').read_text())[phase]
    if status is None: sys.exit(2)
    print(json.dumps(status))
else: sys.exit(1)
'''

def run_update(native_updater, tmp_path, before, after=None, missing_probe=False):
    env_text = ('# retained user configuration\nICARUS_SIDECAR_TOKEN=test-token\n'
                'ICARUS_SECRETS_PASSPHRASE=test-passphrase\n'
                'KINGFISHER_IMAGE=ghcr.io/icarus-health/kingfisher-app:1.0.0\n')
    (tmp_path/'kingfisher.env').write_text(env_text)
    (tmp_path/'compose.yaml').write_text('services: {}\n')
    if not missing_probe:
        shutil.copy(REPO/'scripts/kingfisher_update_storage.py', tmp_path/'update-storage-probe.py')
    (tmp_path/'image').write_text('ghcr.io/icarus-health/kingfisher-app:1.0.0')
    (tmp_path/'trace').touch()
    (tmp_path/'status.json').write_text(json.dumps({'before':before, 'after':after if after is not None else before}))
    docker = tmp_path/'docker'
    docker.write_text('#!'+sys.executable+'\n'+FAKE_DOCKER)
    docker.chmod(0o755)
    result = subprocess.run([str(native_updater)], env={**os.environ,'FIXTURE_DIR':str(tmp_path)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return result.stdout, (tmp_path/'trace').read_text().splitlines(), env_text

@pytest.mark.parametrize('status', [None, {**GOOD,'root_available_bytes':0},
    {**GOOD,'data_available_bytes':0}, {**GOOD,'root_available_inodes':0},
    {**GOOD,'data_available_inodes':0}, {**GOOD,'backup_bytes':True},
    {**GOOD,'backup_files':2**64-1}, {**GOOD,'root_available_bytes':-1},
    {**GOOD,'data_available_bytes':'999999999999'}, {**GOOD,'backup_bytes':1.5}])
def test_initial_capacity_failure_preserves_running_version(native_updater, tmp_path, status):
    output, trace, original = run_update(native_updater,tmp_path,status)
    assert output.strip() != 'updated'
    assert 'backup' not in trace and 'pull' not in trace and 'restart' not in trace and 'pin' not in trace
    assert (tmp_path/'kingfisher.env').read_text() == original

@pytest.mark.parametrize('after', [{**GOOD,'root_available_bytes':0},
                                  {**GOOD,'data_available_inodes':0}, None])
def test_post_pull_failure_does_not_switch_or_restart(native_updater, tmp_path, after):
    # Write an explicit unavailable second measurement after fixture preparation.
    output, trace, original = run_update(native_updater,tmp_path,GOOD,after=after if after is not None else {})
    assert output.strip() != 'updated'
    assert trace.count('backup') == 1 and trace.count('pull') == 1
    assert 'restart' not in trace and 'other-compose' not in trace
    assert (tmp_path/'kingfisher.env').read_text() == original


def test_missing_packaged_probe_blocks_update(native_updater,tmp_path):
    output, trace, original = run_update(native_updater,tmp_path,GOOD,missing_probe=True)
    assert output.strip() != 'updated'
    assert not trace or set(trace) <= {'probe'}
    assert (tmp_path/'kingfisher.env').read_text() == original


def test_sufficient_capacity_updates_normally(native_updater,tmp_path):
    output, trace, _ = run_update(native_updater,tmp_path,GOOD)
    assert output.strip() == 'updated'
    assert trace == ['probe','pin','backup','pull','probe','restart']
    assert 'KINGFISHER_IMAGE=ghcr.io/icarus-health/kingfisher-app:1.0.1' in (tmp_path/'kingfisher.env').read_text()


@pytest.mark.parametrize('before', [True, False])
@pytest.mark.parametrize('changes', [
    {}, {'root_available_bytes':512*1024**2-1}, {'root_available_bytes':512*1024**2},
    {'root_available_inodes':63}, {'root_available_inodes':64},
    {'data_available_bytes':512*1024**2+30*1024**2-1},
    {'data_available_bytes':512*1024**2+30*1024**2},
    {'data_available_bytes':512*1024**2+20*1024**2-1},
    {'data_available_bytes':512*1024**2+20*1024**2},
    {'data_available_inodes':93}, {'data_available_inodes':94},
    {'data_available_inodes':83}, {'data_available_inodes':84},
    {'backup_bytes':True}, {'backup_bytes':1.0}, {'backup_files':2**64},
    {'backup_bytes':2**64-1}, {'backup_files':2**64-1},
    {'root_available_bytes':2**64-1}, {'extra':0}, {'backup_files':-1}
])
def test_native_policy_agrees_with_cli(native_updater, before, changes):
    import runpy
    policy = runpy.run_path(str(REPO/'scripts/kingfisher_update_storage.py'))['evaluate_status']
    status = {**GOOD, **changes}
    expected = policy(status, before_backup=before) or 'ok'
    native = subprocess.run([str(native_updater),json.dumps(status),'before' if before else 'after'],
                            capture_output=True,text=True,timeout=5)
    assert native.returncode == 0, native.stderr
    names = {'lowSpace':'low_space','lowInodes':'low_inodes'}
    assert names.get(native.stdout.strip(),native.stdout.strip()) == expected
