"""Synthetic Docker cp mode semantics; never execute Docker or read private files."""
import json
import stat
from pathlib import Path

import orchestrator as installer
from test_orchestrator import FakeSystem
from test_wal_hook import add_wal


def test_non_image_owned_0600_manifest_must_be_staged_readable_to_image_user(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake)
    observations=[];original=fake.run
    def inspect_copy(argv):
        if argv[:2]==['docker','cp'] and ':' in argv[3] and argv[3].endswith('/raw-data-manifest.json'):
            source=Path(argv[2])
            observations.append((source,source.parent,stat.S_IMODE(source.stat().st_mode),stat.S_IMODE(source.parent.stat().st_mode)))
        return original(argv)
    fake.run=inspect_copy
    result=installer.run(fake.config,fake)
    assert result['status']=='installed',result
    assert len(observations)==1
    staged,parent,file_mode,dir_mode=observations[0]
    assert file_mode==0o644 and dir_mode==0o700
    assert not staged.exists() and not parent.exists()
    manifest=Path(fake.config['backup'])/'raw-data-manifest.json'
    assert stat.S_IMODE(manifest.stat().st_mode)==0o600
    assert all(mode==0o644 for mode in fake.copy_modes.values())
    assert not any('--user' in call or '-u' in call for call in fake.calls if call[:2]==['docker','create'])


def test_staging_preserves_bytes_and_original_mode_and_cleans_on_error(tmp_path):
    source=tmp_path/'metadata.json';source.write_text('{"only":"synthetic hash metadata"}');source.chmod(0o600)
    parent=None
    try:
        with installer.readable_staging((source,)) as staged:
            parent=staged[0].parent
            assert staged[0].read_bytes()==source.read_bytes()
            assert stat.S_IMODE(staged[0].stat().st_mode)==0o644
            assert stat.S_IMODE(parent.stat().st_mode)==0o700
            raise RuntimeError('synthetic cp failure')
    except RuntimeError:pass
    assert not parent.exists() and stat.S_IMODE(source.stat().st_mode)==0o600


def test_copy_error_removes_private_staging_and_never_publishes(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake);original=fake.run;parents=[]
    def fail_manifest_copy(argv):
        if argv[:2]==['docker','cp'] and argv[3].endswith('/raw-data-manifest.json'):
            parents.append(Path(argv[2]).parent)
            return 1,b''
        return original(argv)
    fake.run=fail_manifest_copy
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.published and not fake.started
    assert parents and all(not parent.exists() for parent in parents)
    assert stat.S_IMODE((Path(fake.config['backup'])/'raw-data-manifest.json').stat().st_mode)==0o600
    assert not any(call[:2]==['docker','create'] and any(item.endswith('/preflight.py') for item in call) for call in fake.calls)


def test_image_user_override_is_rejected_before_a_oneshot_runs(tmp_path):
    fake=FakeSystem(tmp_path);original=fake.run
    def wrong_user(argv):
        code,raw=original(argv)
        if argv[:2]==['docker','inspect'] and argv[2] in fake.oneshots:
            rows=json.loads(raw);rows[0]['Config']['User']='root';raw=json.dumps(rows).encode()
        return code,raw
    fake.run=wrong_user
    result=installer.run(fake.config,fake)
    assert result['status']=='prepare_failed' and result['error']=='oneshot_user_changed'
    assert not any(call[:3]==['docker','start','-a'] for call in fake.calls)
