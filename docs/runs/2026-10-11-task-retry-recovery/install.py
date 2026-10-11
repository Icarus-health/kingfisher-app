import json,os,shutil,subprocess,runpy,plistlib,hashlib,time,re,urllib.request,tempfile
from pathlib import Path
D='/opt/homebrew/bin/docker'
app=Path.home()/'Applications/Kingfisher.app'
root=Path('/private/tmp/kingfisher-task-recovery-package-b7cd321')
config=Path.home()/'Library/Application Support/Kingfisher/kingfisher.env'
version='1.0.6-preview.b7cd321'
tag='ghcr.io/icarus-health/kingfisher-app:'+version
container='kingfisher-kingfisher-1'
def docker(*args,**kw):return subprocess.check_output([D,*args],text=True,**kw)
def contents_hashes(bundle):return {str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
# Frozen source/build evidence for this exact package, not unrelated baseline totals.
assert '# pass 573' in Path('/private/tmp/kingfisher-task-recovery-ui-reviewed-20261011.log').read_text()
assert '# fail 0' in Path('/private/tmp/kingfisher-task-recovery-ui-reviewed-20261011.log').read_text()
assert '31 passed' in Path('/private/tmp/kingfisher-manual-task-affected-20261011.log').read_text()
assert '11 passed' in Path('/private/tmp/kingfisher-manual-task-history-20261011.log').read_text()
assert json.loads((root/'recovery-proof.json').read_text())['status']=='passed'
assert json.loads((root/'dmg-verification.json').read_text())['read_only_mounted_bundle_matches'] is True
runtime_proof=json.loads((root/'package-runtime-proof.json').read_text())
assert runtime_proof['exit_code']==0 and runtime_proof['version']==version
assert runtime_proof['package_probe_sha256']==hashlib.sha256((root/'package_probe.py').read_bytes()).hexdigest()
assert runtime_proof['package_log_sha256']==hashlib.sha256((root/'package-probe-final.log').read_bytes()).hexdigest()
manifest=json.loads((root/'mac-app-manifest.json').read_text())
assert contents_hashes(root/'build/mac-app/Kingfisher.app')==manifest['files']
assert contents_hashes(app)==json.loads(Path('/private/tmp/kingfisher-header-package-f858681/mac-app-manifest.json').read_text())['files']
assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']=='1.0.6-preview.f858681'
old_runtime=json.loads(docker('inspect',container))[0]
assert old_runtime['Image']=='sha256:48b1bd538de8eb14eca5f217dcefeac28f042630533310cb7cc7916ed40e0102'
image=docker('image','inspect','--format','{{.Id}}',tag).strip()
assert runtime_proof['image_id']==image
assert image=='sha256:44c6f9fa0c6d0a8852ac7dfdbdad221def3e237a61acd5bb1485ca8e8f04db27'
space=json.loads(docker('exec',container,'python','-c',"import os,json; print(json.dumps({p:{'free_bytes':os.statvfs(p).f_bavail*os.statvfs(p).f_frsize,'free_inodes':os.statvfs(p).f_favail} for p in ('/','/data')}))"))
assert all(v['free_bytes'] >= 512*1024*1024 and v['free_inodes'] >= 1024 for v in space.values()), 'Insufficient Docker reserve before backup; no switch applied'
# Backup and staging use host storage; require the source volume size plus slack.
volume_size=int(docker('exec',container,'python','-c',"import pathlib; print(sum(p.stat().st_size for p in pathlib.Path('/data').rglob('*') if p.is_file()))").strip())
assert shutil.disk_usage(config.parent).free >= volume_size + 512*1024*1024, 'Insufficient host backup reserve; no switch applied'
fingerprints=Path('/private/tmp/kingfisher-core-table-fingerprints.py').read_text()
before=json.loads(docker('exec','-i',container,'python','-',input=fingerprints))
schema_probe='"""Local installer preservation guard; no personal row content is emitted."""\nfrom pathlib import Path\nimport sqlite3,json,hashlib\n\nADDITIONS={\n \'episode_mail_headers\':(\'table\',\'episode_mail_headers\'),\n \'sqlite_autoindex_episode_mail_headers_1\':(\'index\',\'episode_mail_headers\'),\n \'idx_mail_headers_episode\':(\'index\',\'episode_mail_headers\'),\n \'trg_mail_headers_insert\':(\'trigger\',\'episodes\'),\n \'trg_mail_headers_update\':(\'trigger\',\'episodes\'),\n \'trg_mail_headers_delete\':(\'trigger\',\'episodes\'),\n}\n\ndef capture(root):\n result={}\n for p in sorted(Path(root).glob(\'*.sqlite3\')):\n  c=sqlite3.connect(p.as_uri()+\'?mode=ro\',uri=True)\n  try:\n   schema=c.execute(\'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql\').fetchall()\n   entry={\'schema\':schema,\'user_version\':c.execute(\'PRAGMA user_version\').fetchone()[0]}\n   if p.name in (\'episodes.sqlite3\',\'tasks.sqlite3\',\'self-model.sqlite3\'):\n    tables={}\n    for kind,name,_,_ in schema:\n     if kind!=\'table\':continue\n     quoted=\'"\'+name.replace(\'"\',\'""\')+\'"\'\n     rows=[]\n     for row in c.execute(\'SELECT * FROM \'+quoted):\n      raw=json.dumps(tuple(row),ensure_ascii=False,separators=(\',\',\':\'),default=lambda b:{\'bytes\':b.hex()}).encode()\n      rows.append(hashlib.sha256(raw).hexdigest())\n     tables[name]={\'rows\':len(rows),\'sha256\':hashlib.sha256(\'\'.join(sorted(rows)).encode()).hexdigest()}\n    entry[\'tables\']=tables\n   result[p.name]=entry\n  finally:c.close()\n return result\n\ndef verify(before,after):\n assert before == after, \'Database schemas, versions or preserved rows changed\'\n assert before[\'episodes.sqlite3\'][\'user_version\'] == 22, \'Expected unchanged episodes v22\'\n assert before[\'tasks.sqlite3\'][\'user_version\'] == 3, \'Expected unchanged tasks v3\'\n return {\'database_schemas_checked\':len(before),\'preserved_tables_checked\':sum(len(x.get(\'tables\',{})) for x in before.values()),\'existing_episode_store_tables_unchanged\':len(before[\'episodes.sqlite3\'][\'tables\']),\'old_schema\':22,\'new_schema\':22,\'sqlite_schema_and_user_version_unchanged\':True}\n\nprint(json.dumps(capture(Path(\'/data\'))))\n'
schema_before=json.loads(docker('exec','-i',container,'python','-',input=schema_probe))
pause_probe="""import os,json,urllib.request
request=urllib.request.Request('http://127.0.0.1:8890/api/v1/mail/intake',headers={'X-Icarus-Token':os.environ['ICARUS_SIDECAR_TOKEN']})
with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=10) as response:status=json.load(response)
print(json.dumps({'background_paused':status['background_paused']}))
"""
assert json.loads(docker('exec','-i',container,'python','-',input=pause_probe))=={'background_paused':True}, 'Intake must already be paused before installation'
backupscript=root/'backup.py'
g=runpy.run_path(str(backupscript)) # returned namespace retains the recovery lock
original=g['config_bytes'];folder=g['folder']
assert config.read_bytes()==original
# Cold backup has been restored and verified before any code/config switch.
qualified=docker('run','--rm','-i','--network','none','--read-only','--memory','1g','--cpus','2','--tmpfs','/tmp:rw,mode=1777','--user','0','--mount',f'type=bind,source={folder},target=/backup,readonly','--entrypoint','python',image,'-',input=(root/'qualify_copy_worker.py').read_text())
copy_proof=json.loads(qualified)
assert copy_proof['all_derived_headers_match_originals'] and copy_proof['sqlite_schema_and_user_version_unchanged']
(root/'protected-copy-preservation.json').write_text(json.dumps(copy_proof,indent=2)+'\n')
old_hashes=contents_hashes(app)
stage=Path(tempfile.mkdtemp(prefix='.Kingfisher-update-b7cd321-',suffix='.app',dir=app.parent))
try:
 shutil.copytree(root/'build/mac-app/Kingfisher.app',stage,copy_function=shutil.copy2,dirs_exist_ok=True)
 subprocess.run(['/usr/bin/codesign','--verify','--strict','--deep',str(stage)],check=True)
 assert contents_hashes(stage)==manifest['files']
except BaseException:
 # This directory was created exclusively for this run; no other app is removed.
 shutil.rmtree(stage)
 raise
updated,count=re.subn(rb'(?m)^KINGFISHER_IMAGE=[^\r\n]*',b'KINGFISHER_IMAGE='+tag.encode(),original)
assert count==1
moved=folder/'old-native-Contents'
assert not moved.exists()
def atomic_env(data):
 fd,name=tempfile.mkstemp(prefix='.kingfisher-task-recovery-',dir=config.parent)
 tmp=Path(name)
 try:
  with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(tmp,config)
 finally:
  tmp.unlink(missing_ok=True)
def compose_environment():
 return {k:v for k,v in os.environ.items() if not k.startswith(('ICARUS_','KINGFISHER_','COMPOSE_')) and k!='LLM_API_KEY'}
def verify_runtime_configuration(old_env,new_env):
 def selected(values):
  mapping=dict(item.split('=',1) for item in values if '=' in item)
  return {k:v for k,v in mapping.items() if (k.startswith(('ICARUS_','KINGFISHER_')) or k=='LLM_API_KEY') and k!='KINGFISHER_FASSUNG'}
 assert selected(old_env)==selected(new_env), 'Runtime configuration changed unexpectedly'
def compose_up():
 subprocess.run([D,'compose','-p','kingfisher','-f',str(app/'Contents/Resources/compose.yaml'),'--env-file',str(config),'up','-d','--no-build','--pull','never'],check=True,capture_output=True,text=True,env=compose_environment())
def healthy():
 for _ in range(40):
  try:
   docker('exec',container,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8890/health',timeout=1)",stderr=subprocess.DEVNULL);return
  except subprocess.CalledProcessError:time.sleep(.5)
 raise RuntimeError('Runtime did not become healthy')
def rollback_code_without_restarting_data():
 # A new runtime may have written data before a verification failed. Never start
 # the old runtime on it automatically, and never overwrite those writes.
 existing=docker('ps','-a','--filter','name=^/'+container+'$','--format','{{.Names}}').splitlines()
 # A successful Docker query can establish that Compose removed the container.
 # A failed query leaves state unknown and must not restore code beneath a writer.
 assert existing in ([],[container]), 'Unexpected container identity during recovery'
 if existing:docker('stop',container)
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
try:
 os.replace(app/'Contents',moved)
 os.replace(stage/'Contents',app/'Contents');stage.rmdir()
 assert contents_hashes(app)==manifest['files']
 subprocess.run(['/usr/bin/codesign','--verify','--strict','--deep',str(app)],check=True)
 atomic_env(updated);compose_up();healthy()
 state=json.loads(docker('inspect',container))[0]
 verify_runtime_configuration(old_runtime['Config']['Env'],state['Config']['Env'])
 assert state['Image']==image
 assert [(x['Type'],x['Name']) for x in state['Mounts'] if x['Destination']=='/data']==[('volume','kingfisher_kingfisher-data')]
 after=json.loads(docker('exec','-i',container,'python','-',input=fingerprints));assert before==after
 schema_after=json.loads(docker('exec','-i',container,'python','-',input=schema_probe))
 guard_namespace={};exec((root/'preservation_guard.py').read_text(),guard_namespace)
 schema_preservation=guard_namespace['verify'](schema_before,schema_after)
 query="""import os,json,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(path):
 req=urllib.request.Request('http://127.0.0.1:8890'+path,headers={'X-Icarus-Token':os.environ['ICARUS_SIDECAR_TOKEN']})
 with opener.open(req,timeout=10) as r:return json.load(r)
print(json.dumps({'version':get('/api/v1/fassung')['fassung'],'background_paused':get('/api/v1/mail/intake')['background_paused'],'storage_blocked':get('/api/v1/mail/intake')['storage_blocked']}))
"""
 status=json.loads(docker('exec','-i',container,'python','-',input=query));assert status=={'version':version,'background_paused':True,'storage_blocked':None}
 assert config.read_bytes()==updated and config.stat().st_mode & 0o777==0o600
 assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']==version
 proof={'version':version,'backend_image_id':image,'backend_healthy':True,'native_files_match_canonical_dmg':True,'native_strict_deep_signature':True,'all_seven_core_tables_unchanged':True,'sqlite_schema_and_user_version_unchanged':True,'preserved_tables_checked':schema_preservation['preserved_tables_checked'],'existing_episode_store_tables_unchanged':schema_preservation['existing_episode_store_tables_unchanged'],'sqlite_schema_databases_checked':len(schema_after),'protected_copy_store_opening_passed':True,'data_volume_unchanged':True,'only_env_image_selector_changed':True,'runtime_provider_configuration_preserved':True,'ambient_compose_overrides_removed':True,'background_paused':True,'storage_blocked':None,'native_calendar_display_verified':False,'backup_directory':str(folder),'native_process_restarted':False,'native_window_verified':False,'installed_but_native_restart_pending':True,'backup':{k:g['proof'][k] for k in ('volume_files','volume_directories','volume_bytes','root_sqlite_integrity_checked','restore_bytewise_match','restore_directory_entries_match','restore_ownership_modes_mtime_xattrs_match')}}
 (folder/'task-recovery-install-verification.json').write_text(json.dumps(proof,indent=2)+'\n');(folder/'task-recovery-install-verification.json').chmod(0o600)
 Path('/private/tmp/kingfisher-task-recovery-install-verification-20261011.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps({k:v for k,v in proof.items() if k!='backup_directory'}))
except BaseException:
 if moved.exists():
  rollback_code_without_restarting_data()
  print('Update failed: backend stopped; existing data kept, verified preupdate backup available. Recovery must be checked before restarting.',flush=True)
 raise
