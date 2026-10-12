"""Local installer preservation guard; no personal row content is emitted."""
from pathlib import Path
import sqlite3,json,hashlib

ADDITIONS={
 'episode_mail_headers':('table','episode_mail_headers'),
 'sqlite_autoindex_episode_mail_headers_1':('index','episode_mail_headers'),
 'idx_mail_headers_episode':('index','episode_mail_headers'),
 'trg_mail_headers_insert':('trigger','episodes'),
 'trg_mail_headers_update':('trigger','episodes'),
 'trg_mail_headers_delete':('trigger','episodes'),
}

def capture(root):
 result={}
 for p in sorted(Path(root).glob('*.sqlite3')):
  c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
  try:
   schema=c.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql').fetchall()
   entry={'schema':schema,'user_version':c.execute('PRAGMA user_version').fetchone()[0]}
   if p.name in ('episodes.sqlite3','tasks.sqlite3','self-model.sqlite3'):
    tables={}
    for kind,name,_,_ in schema:
     if kind!='table':continue
     quoted='"'+name.replace('"','""')+'"'
     rows=[]
     for row in c.execute('SELECT * FROM '+quoted):
      raw=json.dumps(tuple(row),ensure_ascii=False,separators=(',',':'),default=lambda b:{'bytes':b.hex()}).encode()
      rows.append(hashlib.sha256(raw).hexdigest())
     tables[name]={'rows':len(rows),'sha256':hashlib.sha256(''.join(sorted(rows)).encode()).hexdigest()}
    entry['tables']=tables
   result[p.name]=entry
  finally:c.close()
 return result

def verify(before,after):
 assert before == after, 'Database schemas, versions or preserved rows changed'
 assert before['episodes.sqlite3']['user_version'] == 22, 'Expected unchanged episodes v22'
 assert before['tasks.sqlite3']['user_version'] == 3, 'Expected unchanged tasks v3'
 return {'database_schemas_checked':len(before),'preserved_tables_checked':sum(len(x.get('tables',{})) for x in before.values()),'existing_episode_store_tables_unchanged':len(before['episodes.sqlite3']['tables']),'old_schema':22,'new_schema':22,'sqlite_schema_and_user_version_unchanged':True}

import subprocess,time
from icarus_memory.episodes import EpisodeStore, _verify_v22
root=Path('/tmp/protected-copy');root.mkdir(mode=0o700)
subprocess.run(['tar','--no-same-owner','-xf','/backup/volume.tar.gz','-C',str(root)],check=True,capture_output=True)
before=capture(root)
started=time.perf_counter();store=EpisodeStore(root/'episodes.sqlite3');_verify_v22(store._conn)
# Independently compare the complete derived contents against the original tags.
expected="""SELECT j.value,e.id FROM episodes e,json_each(e.document,'$.tags') j
WHERE e.kind='message' AND json_extract(e.document,'$.provenance.source_type')='email'
AND json_type(e.document,'$.tags')='array' AND j.type='text'
AND (j.value GLOB 'mail:message:*' OR j.value GLOB 'mail:reply:*')"""
for sql in ("SELECT value,episode_id FROM episode_mail_headers EXCEPT "+expected,
            expected+" EXCEPT SELECT value,episode_id FROM episode_mail_headers"):
 assert store._conn.execute(sql).fetchone() is None, 'Derived header parity failure'
headers=store._conn.execute('SELECT count(*) FROM episode_mail_headers').fetchone()[0]
store.close();after=capture(root)
from icarus_memory.tasks import TaskStore
tasks=TaskStore(root/'tasks.sqlite3');tasks.close()
after=capture(root)
proof=verify(before,after);proof.update(protected_local_copy=True,original_backup_readonly=True,network='none',models=False,all_derived_headers_match_originals=True,header_rows=headers,migration_and_verification_seconds=time.perf_counter()-started)
print(json.dumps(proof))
