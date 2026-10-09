#!/usr/bin/env python3
"""Read-only, standard-library data evidence. Never imports Kingfisher or providers."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3

DATABASES = tuple(sorted(('audit','calendar-actions','cloud-memory-jobs','conversations','episodes','gespraeche','knowledge','lint','logbuch','mac-calendar','proposals','recovery-status','regeln','rueckmeldungen','self-model','tasks','workspace')))
DATABASES = tuple(name + '.sqlite3' for name in DATABASES)
BACKUP_AUX = ('einstellungen.json','schluessel.icarus')

class CheckFailed(RuntimeError): pass

def require(value, code):
    if not value: raise CheckFailed(code)

def sha_bytes(data): return hashlib.sha256(data).hexdigest()

def sha_file(path):
    out=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): out.update(block)
    return out.hexdigest()

def feed(out, row):
    values=[('blob',v.hex()) if isinstance(v,bytes) else (type(v).__name__,v) for v in row]
    encoded=json.dumps(values,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    out.update(len(encoded).to_bytes(8,'big'));out.update(encoded)

def quote(name): return '"'+name.replace('"','""')+'"'

def tree_manifest(root):
    rows=[]
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in sorted(dirs+files):
            path=Path(base)/name;rel=path.relative_to(root).as_posix()
            if path.is_symlink(): rows.append([rel,'symlink',os.readlink(path)])
            elif path.is_file(): rows.append([rel,'file',path.stat().st_size,sha_file(path)])
            elif path.is_dir(): rows.append([rel,'directory'])
            else: raise CheckFailed('unsupported_tree_entry')
    rows.sort(key=lambda row:row[0])
    return rows

def tree_summary(rows):
    return {'entries':len(rows),'bytes':sum(row[2] for row in rows if row[1]=='file'),
            'sha256':sha_bytes(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode())}

def measure(root):
    root=Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),'data_directory')
    total=0
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in files:
            path=Path(base)/name
            if not path.is_symlink(): total+=path.stat().st_size
    snapshot=sum((root/name).stat().st_size for name in DATABASES+BACKUP_AUX
                 if name!='recovery-status.sqlite3' and (root/name).is_file())
    info=os.statvfs(root)
    return {'tree_bytes':total,'snapshot_bytes':snapshot,'free_bytes':info.f_bavail*info.f_frsize,'free_inodes':info.f_favail}

def prove(root,*,cold):
    root=Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),'data_directory')
    # Recovery retains displaced stores. Only the 17 fixed live stores are active.
    names=sorted(path.name for path in root.glob('*.sqlite3') if '.vor-wiederherstellung-' not in path.name)
    require(names==list(DATABASES),'active_database_set')
    content=hashlib.sha256();originals=hashlib.sha256();count=0;schema=None
    for name in names:
        path=root/name; require(path.is_file() and not path.is_symlink(),'unsafe_database')
        if cold:
            require(not any((root/(name+suffix)).exists() or (root/(name+suffix)).is_symlink()
                            for suffix in ('-wal','-shm','-journal')),'database_not_cleanly_closed')
        uri=path.resolve().as_uri()+'?mode=ro'+('&immutable=1' if cold else '')
        with closing(sqlite3.connect(uri,uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            require(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'quick_check_failed')
            version=db.execute('PRAGMA user_version').fetchone()[0]
            feed(content,(name,version if name!='episodes.sqlite3' else '19-or-20'))
            if name=='episodes.sqlite3':
                schema=version;require(schema in (19,20),'episode_schema')
                for ident,digest,body,document in db.execute('SELECT id,digest,body,document FROM episodes ORDER BY id'):
                    require(isinstance(body,str) and digest=='sha256:'+sha_bytes(body.encode()),'original_digest_mismatch')
                    feed(originals,(ident,digest,body,document));count+=1
                if version==20 and cold:
                    fields=db.execute('PRAGMA table_info(memory_category_sources)').fetchall()
                    field=next((row for row in fields if row[1]=='failure_code'),None)
                    require(field is not None and field[2:]==('TEXT',0,None,0),'failure_column_contract')
                    require(db.execute('SELECT count(*) FROM memory_category_sources WHERE failure_code IS NOT NULL').fetchone()[0]==0,'non_null_old_failure_code')
            tables=db.execute("SELECT name,sql FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            for table,sql in tables:
                if str(sql).lstrip().upper().startswith('CREATE VIRTUAL TABLE'):continue
                info=db.execute('PRAGMA table_info('+quote(table)+')').fetchall()
                columns=[row[1] for row in info if not (name=='episodes.sqlite3' and table=='memory_category_sources' and row[1]=='failure_code')]
                keys=[row[1] for row in sorted(info,key=lambda row:row[5]) if row[5]]
                order=','.join(map(quote,keys)) if keys else 'rowid'
                feed(content,(name,table,*columns))
                for row in db.execute('SELECT '+','.join(map(quote,columns))+' FROM '+quote(table)+' ORDER BY '+order):feed(content,row)
    settings=root/'einstellungen.json';background=root/'hintergrund.json'
    require(settings.is_file() and background.is_file() and not settings.is_symlink() and not background.is_symlink(),'settings_missing')
    json.loads(settings.read_text());paused=json.loads(background.read_text()).get('pausiert') is True
    marker=root/'restore-state.json';inspection=False
    if marker.exists():
        require(marker.is_file() and not marker.is_symlink(),'unsafe_inspection_marker')
        inspection=json.loads(marker.read_text()).get('mode')=='inspection'
        require(inspection,'unknown_restore_marker')
    return {'databases':names,'schema':schema,'content_sha256':content.hexdigest(),
            'originals':{'count':count,'sha256':originals.hexdigest()},'settings_sha256':sha_file(settings),
            'background_sha256':sha_file(background),'paused':paused,'inspection':inspection,
            'tree':tree_summary(tree_manifest(root)) if cold else None}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True)
    parser.add_argument('--cold',action='store_true');parser.add_argument('--measure',action='store_true')
    args=parser.parse_args()
    try:
        result=measure(args.data_dir) if args.measure else prove(args.data_dir,cold=args.cold)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as exc:
        print(json.dumps({'error':str(exc) if isinstance(exc,CheckFailed) else 'data_check_failed'}));return 1

if __name__=='__main__':raise SystemExit(main())
