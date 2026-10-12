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
   if p.name=='episodes.sqlite3':
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
 assert set(before)==set(after), 'Database file set changed'
 assert before['episodes.sqlite3']['user_version']==21, 'Expected old schema v21'
 assert after['episodes.sqlite3']['user_version']==22, 'Expected new schema v22'
 for name,old in before.items():
  new=after[name]
  if name!='episodes.sqlite3':
   assert old==new, 'Unexpected schema/version change in another database'
   continue
  old_objects={r[1]:tuple(r) for r in old['schema']};new_objects={r[1]:tuple(r) for r in new['schema']}
  assert all(new_objects.get(k)==v for k,v in old_objects.items()), 'Existing schema object changed'
  extra={k:v for k,v in new_objects.items() if k not in old_objects}
  assert set(extra)==set(ADDITIONS), 'Unexpected migration schema additions'
  # Production migration verifier separately validates exact DDL and trigger SQL.
  assert all((extra[k][0],extra[k][2])==v for k,v in ADDITIONS.items()), 'Unexpected object type/owner'
  assert set(new['tables'])==set(old['tables'])|{'episode_mail_headers'}, 'Unexpected table set'
  assert all(new['tables'].get(k)==v for k,v in old['tables'].items()), 'Existing episode-store rows changed'
 return {'database_schemas_checked':len(before),'existing_episode_store_tables_unchanged':len(before['episodes.sqlite3']['tables']),'old_schema':21,'new_schema':22,'only_expected_schema_additions':True}
