"""Independent read-only package and cold-backup comparison, run after install."""
from pathlib import Path
import hashlib,json,sqlite3,subprocess,sys

VERSION='1.0.6-local.5621ec9'
IMAGE='sha256:72837cc0356954760e26aa1f9eb99713edc5287f598d7bd1a994f28a4298168f'
CONTAINER='kingfisher-kingfisher-1'
APP=Path('/Users/sorenkube/Applications/Kingfisher.app')
NATIVE='b294220f1588fa8a7282caec6cf02ede0939440d51c238335dafaf7f15c22778'

def require(value,label):
 if not value:raise RuntimeError(label)

def run(*args,input=None):
 return subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout

def main():
 backup=Path(sys.argv[1]).resolve()
 require(backup.is_dir() and (backup/'data/episodes.sqlite3').is_file(),'cold_backup_missing')
 package=run('docker','exec','-i',CONTAINER,'python','-',input=Path('/private/tmp/kingfisher-category-package-5621ec9/installed-check.py').read_bytes())
 package_result=json.loads(package)
 require(package_result['version']==VERSION,'package_version')
 code='''from pathlib import Path
import sqlite3,json
from icarus_memory.episodes import digest_of
c=sqlite3.connect('file:/data/episodes.sqlite3?mode=ro',uri=True)
rows=c.execute('SELECT id,digest,body FROM episodes').fetchall()
assert c.execute('PRAGMA user_version').fetchone()[0]==20
assert all(digest_of(body)==digest for _,digest,body in rows)
c.close()
checks=[]
for p in Path('/data').iterdir():
 if not p.is_file():continue
 with p.open('rb') as f:header=f.read(16)
 if header!=b'SQLite format 3\\x00':continue
 c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
 assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 c.close();checks.append(p.name)
print(json.dumps({'digests':{i:d for i,d,_ in rows},'sqlite':sorted(checks),'settings':json.loads(Path('/data/einstellungen.json').read_text()),'background':json.loads(Path('/data/hintergrund.json').read_text())}))
'''
 actual=json.loads(run('docker','exec','-i',CONTAINER,'python','-',input=code.encode()))
 c=sqlite3.connect((backup/'data/episodes.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
 cold_rows=c.execute('SELECT id,digest,body FROM episodes').fetchall()
 require(all(digest=='sha256:'+hashlib.sha256(body.encode()).hexdigest() for _,digest,body in cold_rows),'backup_original_digest')
 before={i:d for i,d,_ in cold_rows}
 require(c.execute('PRAGMA user_version').fetchone()[0]==19,'backup_schema');c.close()
 require(bool(before) and all(actual['digests'].get(i)==d for i,d in before.items()),'originals_changed')
 require(not any(p.name.endswith(('-wal','-shm','-journal')) for p in (backup/'data').iterdir()),'backup_not_cold')
 sqlite_before=[]
 for p in (backup/'data').iterdir():
  if p.is_file():
   with p.open('rb') as f:header=f.read(16)
   if header==b'SQLite format 3\x00':sqlite_before.append(p.name)
 require(actual['sqlite']==sorted(sqlite_before),'root_sqlite_set_changed')
 settings=json.loads((backup/'data/einstellungen.json').read_text())
 require(settings==actual['settings'],'settings_changed')
 require(actual['background'].get('pausiert') is True,'background_unpaused')
 inspect=json.loads(run('docker','inspect',CONTAINER))[0]
 require(inspect['State']['Running'] and inspect['Image']==IMAGE,'wrong_image')
 mounts=[m for m in inspect['Mounts'] if m['Destination']=='/data']
 require(len(mounts)==1 and mounts[0].get('Type')=='volume' and mounts[0].get('Name')=='kingfisher_kingfisher-data' and mounts[0].get('RW') is True,'wrong_volume')
 require(hashlib.sha256((APP/'Contents/MacOS/Kingfisher').read_bytes()).hexdigest()==NATIVE,'native_changed')
 require(hashlib.sha256((APP/'Contents/Info.plist').read_bytes()).hexdigest()=='bdccd9204e6952ea47d7ce39e4d19c9a88d6545b01410f07125cd3a1464e760c','native_plist_changed')
 require(hashlib.sha256((APP/'Contents/Resources/compose.yaml').read_bytes()).hexdigest()=='4dbd3aa8c4cb7e44d89544b96f02a5ac56e4f23be512a4ab6db26d3d9c7ecfa9','compose_changed')
 run('codesign','--verify','--strict','--deep',str(APP))
 result={'version':VERSION,'schema':20,'original_bodies_recomputed_and_preserved':len(before),'new_originals_since_backup':len(actual['digests'])-len(before),'root_sqlite_verified':len(sqlite_before),'root_sqlite_set_exact':True,'settings_preserved':True,'pause_preserved':True,'same_volume':True,'native_signature_and_bytes_verified':True,'native_ui_verified':False,**package_result}
 Path('/private/tmp/kingfisher-category-fresh-verification-20261009.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))

if __name__=='__main__':main()
