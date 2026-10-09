#!/usr/bin/env python3
"""Standalone offline WAL finalization; no migration, app, restore or unlink.

The host first seals a full stopped raw copy; only its manifest enters the
container. The caller owns writer exclusion for the entire unpublished window.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import data_proof

FORMAT='kingfisher-cold-wal-manifest-v1'

class CheckFailed(RuntimeError):pass

def require(value,code):
    if not value:raise CheckFailed(code)

def _guard(callback):
    try:require(callback is None or callback() is True,'maintenance_window_lost')
    except Exception:raise CheckFailed('maintenance_window_lost') from None

def layout(root):
    root=Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),'data_directory')
    names=sorted(p.name for p in root.glob('*.sqlite3') if '.vor-wiederherstellung-' not in p.name)
    require(names==list(data_proof.DATABASES),'active_database_set')
    for name in names:require((root/name).is_file() and not (root/name).is_symlink(),'unsafe_database')
    allowed={name+suffix for name in names for suffix in ('-wal','-shm')}
    sidecars=[]
    for path in root.iterdir():
        if not path.name.endswith(('-wal','-shm','-journal')):continue
        require(path.name in allowed and path.is_file() and not path.is_symlink(),'foreign_or_rollback_sidecar')
        sidecars.append(path.name)
    for name in names:
        wal=name+'-wal';shm=name+'-shm'
        require((wal in sidecars)==(shm in sidecars),'orphan_sidecar')
    return sorted(sidecars)

def seal_backup(backup_dir,manifest_path):
    """Host-only: read every copied byte; never open any SQLite connection."""
    result={'status':'backup_rejected'}
    try:
        root=Path(backup_dir);target=Path(manifest_path)
        sidecars=layout(root)
        require(target.is_absolute() and not target.resolve().is_relative_to(root.resolve()),'manifest_location')
        require(not target.exists() and not target.is_symlink(),'manifest_exists')
        rows=data_proof.tree_manifest(root)
        require(rows==data_proof.tree_manifest(root),'backup_changed_while_sealing')
        payload={'format':FORMAT,'files':rows,'summary':data_proof.tree_summary(rows)}
        raw=(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        result.update(status='backup_sealed',manifest_sha256=hashlib.sha256(raw).hexdigest(),
                      tree_sha256=payload['summary']['sha256'],entries=len(rows),sidecar_count=len(sidecars))
    except Exception as exc:result['error']=str(exc) if isinstance(exc,(CheckFailed,data_proof.CheckFailed)) else 'backup_seal_failed'
    return result

def _manifest(path,expected):
    require(isinstance(expected,str) and len(expected)==64,'manifest_digest_required')
    path=Path(path);require(path.is_file() and not path.is_symlink(),'manifest_missing')
    raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==expected,'manifest_digest_mismatch')
    content=json.loads(raw)
    require(content.get('format')==FORMAT and isinstance(content.get('files'),list),'manifest_format')
    require(content.get('summary')==data_proof.tree_summary(content['files']),'manifest_summary')
    return content

def _checkpoint(path):
    # mode=rw cannot silently create a missing database. Never change journal_mode
    # or issue DML/DDL. A busy result is a failure, not permission to discard WAL.
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=rw',uri=True,timeout=0)) as db:
        row=db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        require(row==(0,0,0),'checkpoint_busy_or_incomplete')

def run(data_dir,manifest_path,expected_manifest_sha256,*,service_stopped=False,
        unpublished=False,exclusive_writer=False,still_stopped=None):
    result={'status':'rejected_before_checkpoint','migration_permitted':False,'phase':'preconditions'}
    started=False
    try:
        require(service_stopped is True and unpublished is True and exclusive_writer is True,'offline_exclusive_unpublished_required')
        _guard(still_stopped)
        root=Path(data_dir);sidecars=layout(root)
        manifest=_manifest(manifest_path,expected_manifest_sha256)
        require(data_proof.tree_manifest(root)==manifest['files'],'raw_backup_mismatch')
        result.update(phase='logical_before',raw_backup_verified=True,manifest_sha256=expected_manifest_sha256)
        before=data_proof.prove(root,cold=False)  # honors committed WAL; never immutable
        require(before['schema']==19 and before['paused'] is True and before['inspection'] is False,'baseline_contract')
        _guard(still_stopped)
        after_read=layout(root)
        require(set(sidecars)<=set(after_read),'sidecars_disappeared_during_read')
        new_sidecars=set(after_read)-set(sidecars)
        for name in data_proof.DATABASES:
            if name+'-wal' not in new_sidecars:continue
            require((root/(name+'-wal')).stat().st_size==0,'new_wal_not_empty')
            require((root/(name+'-shm')).stat().st_size==32768,'new_shm_shape')
            with (root/name).open('rb') as source:header=source.read(20)
            require(header[:16]==b'SQLite format 3\x00' and header[18:20]==b'\x02\x02','new_sidecar_not_from_wal_database')
        # WAL-aware read-only SQLite may update SHM reader marks. Only that
        # transient metadata may differ after our own read; DB/WAL/aux bytes may not.
        shm_names={name for name in sidecars if name.endswith('-shm')}
        stable=lambda rows:[row for row in rows if row[0] not in shm_names|new_sidecars]
        require(stable(data_proof.tree_manifest(root))==stable(manifest['files']),'changed_before_checkpoint')
        names=[name for name in data_proof.DATABASES if name+'-wal' in after_read]
        for name in names:
            _guard(still_stopped);started=True;result['phase']='checkpoint'
            _checkpoint(root/name)  # includes zero-length WAL; SQLite owns cleanup
        _guard(still_stopped)
        result['phase']='logical_after'
        require(layout(root)==[],'sidecars_remain')
        after=data_proof.prove(root,cold=True)
        require(before=={**after,'tree':None},'logical_inventory_changed')
        _guard(still_stopped)
        result.update(status='wal_finalized',phase='complete',schema=19,checkpointed_databases=len(names),
                      original_count=before['originals']['count'],originals_sha256=before['originals']['sha256'],
                      stored_rows_sha256=before['content_sha256'],database_count=len(before['databases']),
                      background_pause_preserved=True,raw_backup_manifest_sha256=expected_manifest_sha256)
    except Exception as exc:
        result['status']='checkpoint_failed' if started else 'rejected_before_checkpoint'
        result['error']=str(exc) if isinstance(exc,(CheckFailed,data_proof.CheckFailed)) else 'wal_check_failed'
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    scan=sub.add_parser('scan');scan.add_argument('--data-dir',required=True)
    seal=sub.add_parser('seal-backup');seal.add_argument('--backup-dir',required=True);seal.add_argument('--manifest',required=True)
    finish=sub.add_parser('finalize');finish.add_argument('--data-dir',required=True);finish.add_argument('--manifest',required=True);finish.add_argument('--manifest-sha256',required=True)
    for flag in ('service-stopped','unpublished','exclusive-writer'):finish.add_argument('--'+flag,action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='scan':result={'status':'scanned','sidecars':layout(args.data_dir)}
        elif args.action=='seal-backup':result=seal_backup(args.backup_dir,args.manifest)
        else:result=run(args.data_dir,args.manifest,args.manifest_sha256,service_stopped=args.service_stopped,unpublished=args.unpublished,exclusive_writer=args.exclusive_writer)
    except Exception:result={'status':'rejected_before_checkpoint','error':'scan_failed','migration_permitted':False}
    print(json.dumps(result,sort_keys=True));return 0 if result['status'] in ('scanned','backup_sealed','wal_finalized') else 1

if __name__=='__main__':raise SystemExit(main())
