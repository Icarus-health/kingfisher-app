"""Actual synthetic SQLite WAL through the same fake-Docker installer flow."""
from pathlib import Path
import json
import subprocess
import sys
import sqlite3

from test_orchestrator import FakeSystem
import orchestrator as installer
import data_proof


def add_wal(fake):
    code="""import os,sqlite3,sys,hashlib
c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA wal_autocheckpoint=0')
b='Synthetic second original.'
c.execute('INSERT INTO episodes VALUES(?,?,?,?)',('wal-second','sha256:'+hashlib.sha256(b.encode()).hexdigest(),b,'{}'));c.commit();os._exit(0)
"""
    subprocess.run([sys.executable,'-c',code,str(fake.data/'episodes.sqlite3')],check=True)


def test_wal_raw_copy_seal_checkpoint_precedes_clean_proof_and_migration(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake)
    result=installer.run(fake.config,fake)
    assert result['status']=='installed' and result['original_count']==2,result
    backup=Path(fake.config['backup'])
    assert (backup/'data-with-journals/episodes.sqlite3-wal').stat().st_size>0
    assert not (backup/'data/episodes.sqlite3-wal').exists()
    assert (backup/'raw-data-manifest.json').is_file()
    calls=fake.calls
    raw=next(i for i,c in enumerate(calls) if c[:2]==['docker','cp'] and c[-1].endswith('/data-with-journals'))
    finish=next(i for i,c in enumerate(calls) if c[:2]==['docker','create'] and 'finalize' in c)
    canonical=next(i for i,c in enumerate(calls) if c[:2]==['docker','cp'] and c[-1].endswith('/data'))
    migration=next(i for i,c in enumerate(calls) if c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c))
    assert raw<finish<canonical<migration
    assert not any(c[:2]==['docker','cp'] and c[2].endswith('/data-with-journals') for c in calls)


def test_no_wal_keeps_existing_copy_and_preflight_path(tmp_path):
    fake=FakeSystem(tmp_path)
    assert installer.run(fake.config,fake)['status']=='installed'
    assert not (Path(fake.config['backup'])/'data-with-journals').exists()
    assert not any(c[:2]==['docker','create'] and 'finalize' in c for c in fake.calls)


def test_ambiguous_wal_result_never_migrates_or_publishes(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake);fake.wal_fail=True
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.published and not fake.started
    assert any(c[:2]==['docker','create'] and 'finalize' in c for c in fake.calls)
    assert not any(c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c) for c in fake.calls)


def test_raw_copy_tamper_blocks_wal_writes_and_migration(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake);original=fake.run
    def tamper(argv):
        result=original(argv)
        if argv[:2]==['docker','cp'] and argv[-1].endswith('/data-with-journals'):
            (Path(argv[-1])/'auxiliary-original.txt').write_text('changed backup')
        return result
    fake.run=tamper
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.published
    assert (fake.data/'episodes.sqlite3-wal').stat().st_size>0
    assert not any(c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c) for c in fake.calls)


def test_zero_wal_actual_blocker_shape_is_finalized_before_preflight(tmp_path):
    fake=FakeSystem(tmp_path)
    code="import os,sys,sqlite3;c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute(\"INSERT INTO example VALUES(2,'synthetic')\");c.commit();c.execute('PRAGMA wal_checkpoint(TRUNCATE)');os._exit(0)"
    subprocess.run([sys.executable,'-c',code,str(fake.data/'regeln.sqlite3')],check=True)
    assert (fake.data/'regeln.sqlite3-wal').stat().st_size==0
    assert (fake.data/'regeln.sqlite3-shm').stat().st_size==32768
    result=installer.run(fake.config,fake)
    assert result['status']=='installed' and result['wal_preparation']=='verified',result
    raw=Path(fake.config['backup'])/'data-with-journals'
    assert (raw/'regeln.sqlite3-wal').stat().st_size==0
    assert (raw/'regeln.sqlite3-shm').stat().st_size==32768
    # After publication, ordinary WAL-aware reads may create fresh sidecars.
    # The immutable cold copy made before migration must be clean.
    assert not (Path(fake.config['backup'])/'data/regeln.sqlite3-wal').exists()


def test_maintenance_loss_in_wal_step_blocks_migration_and_publish(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake)
    def guarded(argv,check):
        name=argv[3];command=fake.oneshots[name]['argv']
        check();result=fake.run(argv)
        if 'finalize' in command:fake.maintenance_error='native_or_launcher_active'
        check();return result
    fake.guarded_run=guarded
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.published and not fake.started
    assert not any(c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c) for c in fake.calls)


def test_active_writer_in_wal_step_cannot_be_ignored(tmp_path):
    fake=FakeSystem(tmp_path);add_wal(fake)
    db=sqlite3.connect(fake.data/'episodes.sqlite3');db.execute('BEGIN IMMEDIATE')
    try:
        result=installer.run(fake.config,fake)
        assert result['status']=='stopped_manual_review' and not fake.published
        assert not any(c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c) for c in fake.calls)
    finally:db.rollback();db.close()
