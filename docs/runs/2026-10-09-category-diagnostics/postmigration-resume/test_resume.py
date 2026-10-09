"""Synthetic already-migrated state; no Docker/model/private actions."""
from pathlib import Path
import json
import shutil
import sqlite3

import pytest
import orchestrator as original
import data_proof
from fake_system import FakeSystem
import resume
import postmigration_proof


def prepared(tmp_path):
    fake=FakeSystem(tmp_path);fake.container_running=False
    cfg=fake.config;backup=Path(cfg['backup']);backup.mkdir()
    shutil.copytree(fake.data,backup/'data')
    (backup/'kingfisher.env').write_bytes(Path(cfg['env']).read_bytes())
    cold=data_proof.prove(backup/'data',cold=True)
    (backup/'cold-proof.json').write_text(json.dumps(cold))
    migration={'status':'migrated','publish_allowed':True,'snapshot_verified':True,'patch_sha256':original.PATCH_SHA,'outdated':[]}
    (backup/'migration-result.json').write_text(json.dumps(migration))
    cfg['migration_result_sha256']=original.sha(backup/'migration-result.json')
    cfg['cold_proof_sha256']=original.sha(backup/'cold-proof.json')
    metadata={'version':original.VERSION,'image_id':original.IMAGE_ID,'old_image_id':'sha256:'+'a'*64,
              'volume_identity':{'Name':original.VOLUME,'Driver':'local','Mountpoint':'/volume/synthetic','Options':None},
              'package_sha256':cfg['manifest_sha256'],'preflight_sha256':original.PREFLIGHT_SHA}
    (backup/'metadata.json').write_text(json.dumps(metadata))
    with sqlite3.connect(fake.data/'episodes.sqlite3') as db:
        db.execute('ALTER TABLE memory_category_sources ADD COLUMN failure_code TEXT');db.execute('PRAGMA user_version=20')
    db.close()
    base=fake.run
    def run(argv):
        if argv[:3]==['docker','start','-a'] and any(x.endswith('/postmigration_proof.py') for x in fake.oneshots[argv[3]]['argv']):
            fake.calls.append(list(argv));row=fake.oneshots[argv[3]]
            try:answer=postmigration_proof.prove(fake.data);row['exit']=0
            except Exception:answer={'error':'postmigration_proof_failed'};row['exit']=1
            return row['exit'],json.dumps(answer).encode()
        return base(argv)
    fake.run=run
    return fake,cfg,backup


def test_resume_statically_proves_before_publish_runtime_probe_only_after_health(tmp_path):
    fake,cfg,backup=prepared(tmp_path)
    result=resume.run(cfg,fake)
    assert result['status']=='installed' and result['original_count']==1,result
    compose=next(i for i,c in enumerate(fake.calls) if c[:2]==['docker','compose'])
    native=next(i for i,c in enumerate(fake.calls) if c[0]==cfg['native_probe'])
    health=next(i for i,c in enumerate(fake.calls) if c[0]=='HTTP')
    assert compose<health<native
    assert not fake.started and not any(c[:2]==['docker','stop'] for c in fake.calls)
    assert not any(any(part.endswith('/preflight.py') or part.endswith('/wal_finalize.py') for part in c) for c in fake.calls if c[:2]==['docker','create'])
    assert Path(cfg['env']).read_text().startswith('KINGFISHER_IMAGE='+original.IMAGE+'\n')
    assert (backup/'data/episodes.sqlite3').exists()


@pytest.mark.parametrize('fault',['migration_sha','cold_backup','non_null_failure','changed_rows','active_writer'])
def test_five_prepublication_failures_never_publish_or_start_old(tmp_path,fault):
    fake,cfg,backup=prepared(tmp_path)
    if fault=='migration_sha':cfg['migration_result_sha256']='0'*64
    elif fault=='cold_backup':(backup/'data/extra-original.txt').write_text('new unexpected file')
    elif fault=='non_null_failure':
        with sqlite3.connect(fake.data/'episodes.sqlite3') as db:db.execute("UPDATE memory_category_sources SET failure_code='provider_error'")
    elif fault=='changed_rows':
        with sqlite3.connect(fake.data/'episodes.sqlite3') as db:db.execute("UPDATE example SET value='changed'")
    else:fake.container_running=True
    result=resume.run(cfg,fake)
    assert result['status']=='stopped_schema20_manual_review' and not fake.published and not fake.started,result
    assert 'KINGFISHER_IMAGE=old:19' in Path(cfg['env']).read_text()


def test_postpublication_failure_keeps_new_compatible_image_and_current_data(tmp_path):
    fake,cfg,backup=prepared(tmp_path);fake.fail_health=True
    result=resume.run(cfg,fake)
    assert result['status']=='forward_repair_required' and fake.published and not fake.started
    assert original.IMAGE in Path(cfg['env']).read_text()
    with sqlite3.connect(fake.data/'episodes.sqlite3') as db:assert db.execute('PRAGMA user_version').fetchone()[0]==20


def test_wal_aware_schema20_proof_sees_committed_failure_code(tmp_path):
    fake,cfg,backup=prepared(tmp_path)
    db=sqlite3.connect(fake.data/'episodes.sqlite3');db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0')
    db.execute("UPDATE memory_category_sources SET failure_code='provider_error'");db.commit()
    try:
        with pytest.raises(data_proof.CheckFailed,match='non_null_old_failure_code'):postmigration_proof.prove(fake.data)
    finally:db.close()
