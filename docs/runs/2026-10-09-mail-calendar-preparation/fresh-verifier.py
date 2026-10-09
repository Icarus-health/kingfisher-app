"""Fresh read-only check of installed bytes and WAL-aware pre-update originals."""
from pathlib import Path
import hashlib,json,sqlite3,subprocess,sys
VERSION='1.0.6-local.d431383'
IMAGE='sha256:930ef4d708d93668dcb79a54cbaac678444283e769addac1b9c3914fd511b858'
CONTAINER='kingfisher-kingfisher-1'
APP=Path('/Users/sorenkube/Applications/Kingfisher.app')
BACKUP=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Rueckweg/2026-10-09-vor-d431383-schema20')
def run(*args,input=None):return subprocess.run(args,input=input,capture_output=True,check=True).stdout
CODE='''import json,sqlite3,hashlib
from pathlib import Path
def originals(root):
 c=sqlite3.connect(root.as_uri()+'/episodes.sqlite3?mode=ro',uri=True)
 assert c.execute('PRAGMA user_version').fetchone()[0]==20
 assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 rows=c.execute('SELECT id,digest,body,document FROM episodes ORDER BY id').fetchall()
 assert all(d=='sha256:'+hashlib.sha256(b.encode()).hexdigest() for i,d,b,v in rows)
 c.close()
 return {'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()}
def evidence(root):
 dbs=sorted(p.name for p in root.glob('*.sqlite3') if '.vor-wiederherstellung-' not in p.name)
 assert len(dbs)==17
 for name in dbs:
  c=sqlite3.connect((root/name).as_uri()+'?mode=ro',uri=True)
  assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)];c.close()
 result={'originals':originals(root),'databases':dbs,'schema':20}
 for name in ('einstellungen.json','hintergrund.json'):
  result[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
 assert json.loads((root/'hintergrund.json').read_text())['pausiert'] is True
 assert not (root/'restore-state.json').exists()
 return result
'''
def main():
 ns={};exec(CODE,ns)
 before=ns['evidence'](BACKUP/'data')
 assert before['originals']['count']==344
 actual=json.loads(run('docker','exec','-i',CONTAINER,'python','-',input=(CODE+"\nprint(json.dumps(evidence(Path('/data'))))\n").encode()))
 assert actual==before
 package=json.loads(run('docker','exec','-i',CONTAINER,'python','-',input=Path('/private/tmp/kingfisher-mail-calendar-package-d431383/installed-check.py').read_bytes()))
 assert package=={'version':VERSION,'python_sources_verified':266,'ui_files_verified':112,'ui_file_set_exact':True}
 inspect=json.loads(run('docker','inspect',CONTAINER))[0]
 assert inspect['Image']==IMAGE and inspect['State']['Running'] is True
 mounts=[m for m in inspect['Mounts'] if m['Destination']=='/data']
 assert len(mounts)==1 and mounts[0]['Type']=='volume' and mounts[0]['Name']=='kingfisher_kingfisher-data' and mounts[0]['RW'] is True
 for rel,digest in [('Contents/MacOS/Kingfisher','b294220f1588fa8a7282caec6cf02ede0939440d51c238335dafaf7f15c22778'),('Contents/Info.plist','bdccd9204e6952ea47d7ce39e4d19c9a88d6545b01410f07125cd3a1464e760c'),('Contents/Resources/compose.yaml','4dbd3aa8c4cb7e44d89544b96f02a5ac56e4f23be512a4ab6db26d3d9c7ecfa9')]:assert hashlib.sha256((APP/rel).read_bytes()).hexdigest()==digest
 run('codesign','--verify','--strict','--deep',str(APP))
 sys.path.insert(0,'/private/tmp/kingfisher-category-install-copy-20261009')
 import orchestrator as frozen
 env=Path('/Users/sorenkube/Library/Application Support/Kingfisher/kingfisher.env').read_text().splitlines()
 token=next(x.split('=',1)[1].strip().strip('\"\'') for x in env if x.startswith('ICARUS_SIDECAR_TOKEN='))
 health=frozen.System().health(token,version=VERSION)
 storage=run('/private/tmp/kingfisher-native-real-probe/probe',str(APP)).decode().strip()
 result={**package,'image_id':IMAGE,'schema':20,'original_bodies_and_documents_recomputed_and_preserved':344,'database_count':17,'settings_and_pause_preserved':True,'same_volume':True,'native_signature_and_bytes_verified':True,'native_ui_verified':False,'health':health,'native_storage_probe':storage}
 Path('/private/tmp/kingfisher-mail-calendar-fresh-verification-20261009.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
