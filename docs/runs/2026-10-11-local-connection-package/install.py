import json,os,shutil,subprocess,runpy,plistlib,hashlib,time,re,urllib.request,tempfile
from pathlib import Path
D='/opt/homebrew/bin/docker'
app=Path.home()/'Applications/Kingfisher.app'
root=Path('/private/tmp/kingfisher-local-connection-package-bc21155')
config=Path.home()/'Library/Application Support/Kingfisher/kingfisher.env'
version='1.0.6-preview.bc21155'
tag='ghcr.io/icarus-health/kingfisher-app:'+version
container='kingfisher-kingfisher-1'
def docker(*args,**kw):return subprocess.check_output([D,*args],text=True,**kw)
def contents_hashes(bundle):return {str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
manifest=json.loads((root/'mac-app-manifest.json').read_text())
assert contents_hashes(root/'build/mac-app/Kingfisher.app')==manifest['files']
assert contents_hashes(app)==json.loads(Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/docs/runs/2026-10-11-category-guidance-package/mac-app-manifest.json').read_text())['files']
assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']=='1.0.6-preview.2d6467b'
assert json.loads(docker('inspect',container))[0]['Image']=='sha256:a3f6dc20a9b9115c0479b11fc174d4eb19ff80ab79320237efc8c99c7761d812'
image=docker('image','inspect','--format','{{.Id}}',tag).strip()
assert image=='sha256:a8c96f76d9c5c67de4aff2ffebcd1590f95d70547cfca5760c142cd42909c45a'
space=json.loads(docker('exec',container,'python','-c',"import os,json; s=os.statvfs('/data'); print(json.dumps({'free_bytes':s.f_bavail*s.f_frsize}))"))
assert space['free_bytes'] >= 64*1024*1024, 'Insufficient Docker free space before backup; no switch applied'
fingerprints=Path('/private/tmp/kingfisher-core-table-fingerprints.py').read_text()
before=json.loads(docker('exec','-i',container,'python','-',input=fingerprints))
schema_probe="""import pathlib,sqlite3,hashlib,json
result={}
for p in sorted(pathlib.Path('/data').glob('*.sqlite3')):
 c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
 schema=c.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql').fetchall()
 result[p.name]={'schema_sha256':hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest(),'user_version':c.execute('PRAGMA user_version').fetchone()[0]}
 c.close()
print(json.dumps(result))
"""
schema_before=json.loads(docker('exec','-i',container,'python','-',input=schema_probe))
backupscript=root/'backup.py'
g=runpy.run_path(str(backupscript)) # returned namespace retains the recovery lock
original=g['config_bytes'];folder=g['folder']
assert config.read_bytes()==original
old_hashes=contents_hashes(app)
stage=app.parent/'.Kingfisher-update-bc21155.app';assert not stage.exists()
shutil.copytree(root/'build/mac-app/Kingfisher.app',stage,copy_function=shutil.copy2)
subprocess.run(['/usr/bin/codesign','--verify','--strict','--deep',str(stage)],check=True)
assert contents_hashes(stage)==manifest['files']
updated,count=re.subn(rb'(?m)^KINGFISHER_IMAGE=[^\r\n]*',b'KINGFISHER_IMAGE='+tag.encode(),original)
assert count==1
moved=folder/'old-native-Contents'
assert not moved.exists()
def atomic_env(data):
 fd,name=tempfile.mkstemp(prefix='.kingfisher-local-connection-',dir=config.parent)
 tmp=Path(name)
 try:
  with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(tmp,config)
 finally:
  tmp.unlink(missing_ok=True)
def compose_up():
 subprocess.run([D,'compose','-p','kingfisher','-f',str(app/'Contents/Resources/compose.yaml'),'--env-file',str(config),'up','-d','--no-build','--pull','never'],check=True,capture_output=True,text=True)
def healthy():
 for _ in range(40):
  try:
   docker('exec',container,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8890/health',timeout=1)",stderr=subprocess.DEVNULL);return
  except subprocess.CalledProcessError:time.sleep(.5)
 raise RuntimeError('Runtime did not become healthy')
def rollback_code_without_restarting_data():
 # A new runtime may have written data before a verification failed. Never start
 # the old runtime on it automatically, and never overwrite those writes.
 docker('stop',container)
 failed=folder/'failed-new-Contents'
 if (app/'Contents').exists():os.replace(app/'Contents',failed)
 os.replace(moved,app/'Contents')
 atomic_env(original)
 assert contents_hashes(app)==old_hashes
 marker=folder/'update-recovery-required.json'
 marker.write_text(json.dumps({'old_code_and_config_restored':True,'backend_stopped':True,
                              'data_volume_not_overwritten':True,'automatic_data_restore':False,
                              'verified_preupdate_backup_available':True},indent=2)+'\n')
 marker.chmod(0o600)
changed=False
try:
 os.replace(app/'Contents',moved);changed=True
 os.replace(stage/'Contents',app/'Contents');stage.rmdir()
 assert contents_hashes(app)==manifest['files']
 subprocess.run(['/usr/bin/codesign','--verify','--strict','--deep',str(app)],check=True)
 atomic_env(updated);compose_up();healthy()
 state=json.loads(docker('inspect',container))[0]
 assert state['Image']==image
 assert [(x['Type'],x['Name']) for x in state['Mounts'] if x['Destination']=='/data']==[('volume','kingfisher_kingfisher-data')]
 after=json.loads(docker('exec','-i',container,'python','-',input=fingerprints));assert before==after
 schema_after=json.loads(docker('exec','-i',container,'python','-',input=schema_probe));assert schema_before==schema_after
 query="""import os,json,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(path):
 req=urllib.request.Request('http://127.0.0.1:8890'+path,headers={'X-Icarus-Token':os.environ['ICARUS_SIDECAR_TOKEN']})
 with opener.open(req,timeout=10) as r:return json.load(r)
print(json.dumps({'version':get('/api/v1/fassung')['fassung'],'background_paused':get('/api/v1/mail/intake')['background_paused']}))
"""
 status=json.loads(docker('exec','-i',container,'python','-',input=query));assert status=={'version':version,'background_paused':True}
 assert config.read_bytes()==updated and config.stat().st_mode & 0o777==0o600
 assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']==version
 proof={'version':version,'backend_image_id':image,'backend_healthy':True,'native_files_match_canonical_dmg':True,'native_strict_deep_signature':True,'all_seven_core_tables_unchanged':True,'sqlite_schema_and_user_version_unchanged':True,'sqlite_schema_databases_checked':len(schema_after),'data_volume_unchanged':True,'only_env_image_selector_changed':True,'background_paused':True,'backup_directory':str(folder),'native_process_restarted':False,'native_window_verified':False,'installed_but_native_restart_pending':True,'backup':{k:g['proof'][k] for k in ('volume_files','volume_directories','volume_bytes','root_sqlite_integrity_checked','restore_bytewise_match','restore_directory_entries_match','restore_ownership_modes_mtime_xattrs_match')}}
 (folder/'local-connection-install-verification.json').write_text(json.dumps(proof,indent=2)+'\n');(folder/'local-connection-install-verification.json').chmod(0o600)
 Path('/private/tmp/kingfisher-local-connection-install-verification-20261011.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps({k:v for k,v in proof.items() if k!='backup_directory'}))
except BaseException:
 if changed:
  rollback_code_without_restarting_data()
  print('Update failed: backend stopped; existing data kept, verified preupdate backup available. Recovery must be checked before restarting.',flush=True)
 raise
