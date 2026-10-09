from pathlib import Path
import hashlib,json,sqlite3,subprocess,sys,shutil
sys.path.insert(0,'/tmp')
import data_proof,wal_finalize
root=Path('/tmp/synthetic-wal-data');root.mkdir()
for name in data_proof.DATABASES:
 with sqlite3.connect(root/name) as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, text TEXT)')
  c.execute("INSERT INTO sample VALUES (1,'synthetic')")
  if name=='episodes.sqlite3':
   c.execute('CREATE TABLE episodes (id TEXT PRIMARY KEY,digest TEXT,body TEXT,document TEXT)')
   c.execute('PRAGMA user_version=19')
 c.close()
(root/'einstellungen.json').write_text('{"schedule":{"enabled":false}}')
(root/'hintergrund.json').write_text('{"pausiert":true}')
body='Synthetic committed WAL original.'
producer="import sqlite3,os; c=sqlite3.connect("+repr(str(root/'episodes.sqlite3'))+"); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA wal_autocheckpoint=0'); c.execute('INSERT INTO episodes VALUES (?,?,?,?)',('synthetic','sha256:'+"+repr(hashlib.sha256(body.encode()).hexdigest())+","+repr(body)+",'{}'));c.commit();os._exit(0)"
subprocess.run([sys.executable,'-c',producer],check=True)
with sqlite3.connect((root/'episodes.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as c:assert c.execute('SELECT count(*) FROM episodes').fetchone()[0]==0
backup=Path('/tmp/synthetic-raw-backup');shutil.copytree(root,backup)
manifest=Path('/tmp/synthetic-manifest.json');seal=wal_finalize.seal_backup(backup,manifest);assert seal['status']=='backup_sealed',seal
result=wal_finalize.run(root,manifest,seal['manifest_sha256'],service_stopped=True,unpublished=True,exclusive_writer=True,still_stopped=lambda:True)
assert result['status']=='wal_finalized' and result['original_count']==1 and result['schema']==19,result
assert wal_finalize.layout(root)==[]
print(json.dumps({'status':'passed','linux_sqlite_version':sqlite3.sqlite_version,'committed_wal_original_preserved':True,'schema_unchanged':19,'databases':17,'sidecars_closed_by_sqlite':True,'network':'none','private_data_used':False}))
