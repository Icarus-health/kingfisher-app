"""Synthetic only; committed-WAL fixtures use disposable child processes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
import data_proof
import wal_finalize as helper


def seed(root):
    root.mkdir()
    for name in data_proof.DATABASES:
        with sqlite3.connect(root/name) as db:
            db.execute('CREATE TABLE example(id INTEGER PRIMARY KEY, value TEXT)')
            db.execute("INSERT INTO example VALUES (1,'synthetic')")
            if name=='episodes.sqlite3':
                db.execute('CREATE TABLE episodes(id TEXT PRIMARY KEY,digest TEXT,body TEXT,document TEXT)')
                db.execute('CREATE TABLE memory_category_sources(episode_id TEXT PRIMARY KEY,status TEXT)')
                db.execute('PRAGMA user_version=19')
    (root/'hintergrund.json').write_text('{"pausiert":true}')
    (root/'einstellungen.json').write_text('{"synthetic":true}')
    (root/'extra-original.txt').write_text('synthetic auxiliary')


def crash_with_committed_wal(root):
    code='''import sqlite3,os,sys,hashlib
c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA wal_autocheckpoint=0')
body='Synthetic WAL original.'
c.execute('INSERT INTO episodes VALUES(?,?,?,?)',('wal-id','sha256:'+hashlib.sha256(body.encode()).hexdigest(),body,'{}'))
c.execute("INSERT INTO memory_category_sources VALUES('wal-id','failed')");c.commit();os._exit(0)
'''
    subprocess.run([sys.executable,'-c',code,str(root/'episodes.sqlite3')],check=True)
    assert (root/'episodes.sqlite3-wal').stat().st_size>0


@pytest.fixture
def frozen(tmp_path):
    source=tmp_path/'data';seed(source);crash_with_committed_wal(source)
    backup=tmp_path/'cold-copy';shutil.copytree(source,backup)
    manifest=tmp_path/'cold-manifest.json'
    sealed=helper.seal_backup(backup,manifest)
    assert sealed['status']=='backup_sealed'
    return source,backup,manifest,sealed['manifest_sha256']


def reseal(frozen):
    source,backup,manifest,digest=frozen
    shutil.rmtree(backup);shutil.copytree(source,backup);manifest.unlink()
    sealed=helper.seal_backup(backup,manifest)
    return source,backup,manifest,sealed['manifest_sha256']


def run(frozen,**kw):
    source,backup,manifest,digest=frozen
    return helper.run(source,manifest,digest,service_stopped=True,unpublished=True,exclusive_writer=True,**kw)


def test_committed_wal_is_preserved_and_no_history_restore(frozen):
    source,backup,manifest,digest=frozen
    # Main-file-only immutable read demonstrably lacks the committed WAL row.
    with sqlite3.connect((source/'episodes.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        assert db.execute('SELECT count(*) FROM episodes').fetchone()[0]==0
    before=data_proof.prove(source,cold=False)
    assert before['originals']['count']==1
    frozen=reseal(frozen)  # the deliberate diagnostic read above updates SHM reader marks
    backup_before=data_proof.tree_manifest(backup)
    result=run(frozen)
    assert result['status']=='wal_finalized' and result['migration_permitted'] is False,result
    assert result['schema']==19 and result['original_count']==1
    after=data_proof.prove(source,cold=True)
    assert before=={**after,'tree':None}
    assert data_proof.tree_manifest(backup)==backup_before
    assert not list(source.glob('*-wal')) and not list(source.glob('*-shm'))
    assert 'wal-id' not in json.dumps(result) and 'Synthetic WAL original' not in json.dumps(result)


@pytest.mark.parametrize('kind',['missing_manifest','corrupt_manifest','wrong_digest','missing_file','corrupt_backup'])
def test_backup_proof_failures_do_not_open_write_connections(frozen,monkeypatch,kind):
    source,backup,manifest,digest=frozen
    if kind=='missing_manifest':manifest.unlink()
    elif kind=='corrupt_manifest':manifest.write_text('{}')
    elif kind=='wrong_digest':frozen=(source,backup,manifest,'0'*64)
    elif kind=='missing_file':(source/'extra-original.txt').unlink()
    elif kind=='corrupt_backup':
        (backup/'extra-original.txt').write_text('corrupt')
        manifest.unlink();sealed=helper.seal_backup(backup,manifest);frozen=(source,backup,manifest,sealed['manifest_sha256'])
    before=data_proof.tree_manifest(source)
    monkeypatch.setattr(helper,'_checkpoint',lambda *a:(_ for _ in ()).throw(AssertionError('checkpoint must not run')))
    result=run(frozen)
    assert result['status']=='rejected_before_checkpoint'
    assert data_proof.tree_manifest(source)==before


def test_missing_backup_cannot_be_sealed(tmp_path):
    result=helper.seal_backup(tmp_path/'missing',tmp_path/'manifest.json')
    assert result['status']=='backup_rejected' and not (tmp_path/'manifest.json').exists()


@pytest.mark.parametrize('name',['foreign.sqlite3-wal','episodes.sqlite3-journal','regeln.sqlite3-shm'])
def test_foreign_rollback_or_orphan_sidecars_are_rejected(frozen,name):
    source,backup,manifest,digest=frozen
    path=source/name;path.write_bytes(b'')
    result=run(frozen)
    assert result['status']=='rejected_before_checkpoint' and path.exists()


def test_zero_length_wal_still_uses_sqlite_and_requires_close(tmp_path):
    source=tmp_path/'data';seed(source)
    subprocess.run([sys.executable,'-c',"import sqlite3,sys,os;c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.execute(\"INSERT INTO example VALUES(2,'wal')\");c.commit();c.execute('PRAGMA wal_checkpoint(TRUNCATE)');os._exit(0)",str(source/'regeln.sqlite3')],check=True)
    assert (source/'regeln.sqlite3-wal').stat().st_size==0
    backup=tmp_path/'backup';shutil.copytree(source,backup);manifest=tmp_path/'manifest.json'
    sealed=helper.seal_backup(backup,manifest)
    result=helper.run(source,manifest,sealed['manifest_sha256'],service_stopped=True,unpublished=True,exclusive_writer=True)
    assert result['status']=='wal_finalized' and result['checkpointed_databases']==1,result
    assert not (source/'regeln.sqlite3-wal').exists() and not (source/'regeln.sqlite3-shm').exists()


def test_active_sqlite_writer_is_rejected_without_unlink(frozen):
    source,backup,manifest,digest=frozen
    db=sqlite3.connect(source/'episodes.sqlite3');db.execute('BEGIN IMMEDIATE')
    frozen=reseal(frozen)
    try:
        result=run(frozen)
        assert result['status']=='checkpoint_failed' and result['migration_permitted'] is False,result
        assert (source/'episodes.sqlite3-wal').exists()
    finally:db.rollback();db.close()


def test_withdrawn_maintenance_does_not_start_checkpoint(frozen,monkeypatch):
    monkeypatch.setattr(helper,'_checkpoint',lambda *a:(_ for _ in ()).throw(AssertionError('must not run')))
    result=run(frozen,still_stopped=lambda:False)
    assert result['status']=='rejected_before_checkpoint'


@pytest.mark.parametrize('change',['body','settings_pause','schema','inspection'])
def test_invalid_baseline_rejected(frozen,change):
    source,backup,manifest,digest=frozen
    if change=='settings_pause':(source/'hintergrund.json').write_text('{"pausiert":false}')
    elif change=='inspection':(source/'restore-state.json').write_text('{"mode":"inspection"}')
    else:
        with sqlite3.connect(source/'episodes.sqlite3') as db:
            if change=='body':db.execute("UPDATE episodes SET body='corrupt'")
            else:db.execute('PRAGMA user_version=20')
    shutil.rmtree(backup);shutil.copytree(source,backup);manifest.unlink()
    sealed=helper.seal_backup(backup,manifest)
    result=helper.run(source,manifest,sealed['manifest_sha256'],service_stopped=True,unpublished=True,exclusive_writer=True)
    assert result['status']=='rejected_before_checkpoint'


def test_post_checkpoint_row_change_is_closed_failure(frozen,monkeypatch):
    original=helper._checkpoint
    def changed(path):
        original(path)
        db=sqlite3.connect(path)
        try:db.execute("UPDATE example SET value='changed'");db.commit()
        finally:db.close()
    monkeypatch.setattr(helper,'_checkpoint',changed)
    result=run(frozen)
    assert result['status']=='checkpoint_failed' and result['error']=='logical_inventory_changed',result


def test_requires_all_attestations(frozen):
    source,backup,manifest,digest=frozen
    result=helper.run(source,manifest,digest)
    assert result['status']=='rejected_before_checkpoint'


def test_import_is_inert(monkeypatch):
    import importlib
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:(_ for _ in ()).throw(AssertionError('connect on import')))
    importlib.reload(helper)


def test_real_episode_schema19_with_original_committed_only_in_wal(tmp_path,monkeypatch):
    from icarus_memory import episodes as epmod
    source=tmp_path/'actual-schema19';seed(source);(source/'episodes.sqlite3').unlink()
    with monkeypatch.context() as patch:
        patch.setattr(epmod,'_MIGRATIONS',epmod._MIGRATIONS[:19])
        store=epmod.EpisodeStore(source/'episodes.sqlite3');store.close()
    code='''import sqlite3,os,sys
from icarus_memory import episodes as ep,EpisodeKind,Provenance,SourceType
ep._MIGRATIONS=ep._MIGRATIONS[:19]
c=sqlite3.connect(sys.argv[1]);c.execute('PRAGMA journal_mode=WAL');c.close()
s=ep.EpisodeStore(sys.argv[1]);s._conn.execute('PRAGMA wal_autocheckpoint=0')
s.record(EpisodeKind.MESSAGE,'Synthetic title','Real synthetic schema19 original.',Provenance(SourceType.EMAIL,source_ref='synthetic:wal'))
os._exit(0)
'''
    subprocess.run([sys.executable,'-c',code,str(source/'episodes.sqlite3')],check=True)
    with sqlite3.connect((source/'episodes.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        assert db.execute('SELECT count(*) FROM episodes').fetchone()[0]==0
    backup=tmp_path/'backup';shutil.copytree(source,backup);manifest=tmp_path/'manifest'
    seal=helper.seal_backup(backup,manifest)
    result=helper.run(source,manifest,seal['manifest_sha256'],service_stopped=True,unpublished=True,exclusive_writer=True)
    assert result['status']=='wal_finalized' and result['original_count']==1,result
    with sqlite3.connect((source/'episodes.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        epmod._MIGRATIONS[18].verify(db)
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert db.execute('SELECT body FROM episodes').fetchone()[0]=='Real synthetic schema19 original.'


def test_seal_opens_no_sqlite_and_preserves_every_raw_byte(frozen,monkeypatch,tmp_path):
    source,backup,manifest,digest=frozen
    before=data_proof.tree_manifest(backup)
    monkeypatch.setattr(sqlite3,'connect',lambda *a,**k:(_ for _ in ()).throw(AssertionError('SQLite forbidden while sealing')))
    assert helper.seal_backup(backup,tmp_path/'new-manifest')['status']=='backup_sealed'
    assert data_proof.tree_manifest(backup)==before


def test_all17_persistent_wal_modes_close_sidecars_created_by_own_read(tmp_path):
    source=tmp_path/'data';seed(source)
    for name in data_proof.DATABASES:
        db=sqlite3.connect(source/name)
        try:db.execute('PRAGMA journal_mode=WAL')
        finally:db.close()
    assert not list(source.glob('*-wal'))
    crash_with_committed_wal(source)
    assert [p.name for p in source.glob('*-wal')]==['episodes.sqlite3-wal']
    backup=tmp_path/'backup';shutil.copytree(source,backup);manifest=tmp_path/'manifest'
    sealed=helper.seal_backup(backup,manifest)
    result=helper.run(source,manifest,sealed['manifest_sha256'],service_stopped=True,unpublished=True,exclusive_writer=True)
    assert result['status']=='wal_finalized' and result['checkpointed_databases']==17,result
    assert result['original_count']==1
    assert not list(source.glob('*-wal')) and not list(source.glob('*-shm'))
    assert data_proof.prove(source,cold=True)['originals']['count']==1


def test_nonzero_wal_appearing_during_own_read_is_never_accepted(frozen,monkeypatch):
    source,backup,manifest,digest=frozen
    original=data_proof.prove
    def read_then_extra_wal(*args,**kwargs):
        result=original(*args,**kwargs)
        (source/'regeln.sqlite3-wal').write_bytes(b'foreign nonempty WAL')
        (source/'regeln.sqlite3-shm').write_bytes(b'\0'*32768)
        return result
    monkeypatch.setattr(data_proof,'prove',read_then_extra_wal)
    result=run(frozen)
    assert result['status']=='rejected_before_checkpoint' and result['error']=='new_wal_not_empty'
    assert (source/'regeln.sqlite3-wal').read_bytes()==b'foreign nonempty WAL'
