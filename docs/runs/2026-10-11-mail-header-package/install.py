import json,os,shutil,subprocess,runpy,plistlib,hashlib,time,re,urllib.request,tempfile
from pathlib import Path
D='/opt/homebrew/bin/docker'
app=Path.home()/'Applications/Kingfisher.app'
root=Path('/private/tmp/kingfisher-header-package-f858681')
config=Path.home()/'Library/Application Support/Kingfisher/kingfisher.env'
version='1.0.6-preview.f858681'
tag='ghcr.io/icarus-health/kingfisher-app:'+version
container='kingfisher-kingfisher-1'
def docker(*args,**kw):return subprocess.check_output([D,*args],text=True,**kw)
def contents_hashes(bundle):return {str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
suite=json.loads(Path('/private/tmp/kingfisher-calendar-suite-validation-ac908b4.json').read_text())
assert suite['all_non_skipped_tests_verified'] and suite['tracked_source_unchanged']
assert suite['file_count']==424 and suite['tested_head']=='ac908b46b229f7b421a1588fb11d3f4bb65212aa'
assert suite['full_suite_exit_code']==1 and suite['full_suite_passed']==6234
assert suite['sole_full_suite_failure']=='tests/test_pruefe_anfuehrungszeichen.py::test_der_bestand_des_repositorys_ist_sauber'
assert suite['isolated_failure_recheck_exit_code']==0 and suite['verified_passed']==6235
assert suite['full_log_sha256']==hashlib.sha256(Path('/private/tmp/kingfisher-calendar-full-clean-ac908b4.log').read_bytes()).hexdigest()
assert suite['recheck_log_sha256']==hashlib.sha256(Path('/private/tmp/kingfisher-calendar-git-metadata-final.log').read_bytes()).hexdigest()
# Baseline full-suite evidence above stays distinct from this patch's affected checks.
checks=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/docs/runs/2026-10-11-confirmed-task-followup')
affected=json.loads((checks/'verification.json').read_text())
assert affected['code_commit']=='a5787c88914400151769dae714dfd74c9ea8a0c3'
assert affected['affected_backend_passed']==156 and affected['document_backend_passed']==13 and affected['ui_passed']==557
for name in ('backend-tests.log','document-tests.log','ui-tests.log'):
 assert affected['artifact_sha256'][name]==hashlib.sha256((checks/name).read_bytes()).hexdigest()
assert '156 passed' in (checks/'backend-tests.log').read_text()
assert '13 passed' in (checks/'document-tests.log').read_text()
assert '# pass 557' in (checks/'ui-tests.log').read_text() and '# fail 0' in (checks/'ui-tests.log').read_text()
index_checks=checks.parent/'2026-10-11-mail-header-index'
index_manifest=json.loads((index_checks/'manifest.json').read_text())
for name,digest in index_manifest.items():assert hashlib.sha256((index_checks/name).read_bytes()).hexdigest()==digest
for name,count in (('affected.log',200),('support.log',111),('originals.log',24)):
 assert f'{count} passed' in (index_checks/name).read_text()
review=json.loads((index_checks/'independent-review.json').read_text())
for name,digest in review['source_sha256'].items():assert hashlib.sha256((root/'sidecar/icarus_memory'/name).read_bytes()).hexdigest()==digest
assert json.loads((root/'dmg-verification.json').read_text())['read_only_mounted_bundle_matches'] is True
runtime_proof=json.loads((root/'package-runtime-proof.json').read_text())
assert runtime_proof['exit_code']==0 and runtime_proof['version']==version
assert runtime_proof['probe_sha256']==hashlib.sha256((root/'package_probe.py').read_bytes()).hexdigest()
assert runtime_proof['log_sha256']==hashlib.sha256((root/'package-probe-final.log').read_bytes()).hexdigest()
manifest=json.loads((root/'mac-app-manifest.json').read_text())
assert contents_hashes(root/'build/mac-app/Kingfisher.app')==manifest['files']
assert contents_hashes(app)==json.loads(Path('/private/tmp/kingfisher-task-package-a5787c8/mac-app-manifest.json').read_text())['files']
assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']=='1.0.6-preview.a5787c8'
old_runtime=json.loads(docker('inspect',container))[0]
assert old_runtime['Image']=='sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf'
image=docker('image','inspect','--format','{{.Id}}',tag).strip()
assert runtime_proof['image_id']==image
assert image=='sha256:48b1bd538de8eb14eca5f217dcefeac28f042630533310cb7cc7916ed40e0102'
space=json.loads(docker('exec',container,'python','-c',"import os,json; print(json.dumps({p:{'free_bytes':os.statvfs(p).f_bavail*os.statvfs(p).f_frsize,'free_inodes':os.statvfs(p).f_favail} for p in ('/','/data')}))"))
assert all(v['free_bytes'] >= 512*1024*1024 and v['free_inodes'] >= 1024 for v in space.values()), 'Insufficient Docker reserve before backup; no switch applied'
# Backup and staging use host storage; require the source volume size plus slack.
volume_size=int(docker('exec',container,'python','-c',"import pathlib; print(sum(p.stat().st_size for p in pathlib.Path('/data').rglob('*') if p.is_file()))").strip())
assert shutil.disk_usage(config.parent).free >= volume_size + 512*1024*1024, 'Insufficient host backup reserve; no switch applied'
fingerprints=Path('/private/tmp/kingfisher-core-table-fingerprints.py').read_text()
before=json.loads(docker('exec','-i',container,'python','-',input=fingerprints))
schema_probe='"""Local installer preservation guard; no personal row content is emitted."""\nfrom pathlib import Path\nimport sqlite3,json,hashlib\n\nADDITIONS={\n \'episode_mail_headers\':(\'table\',\'episode_mail_headers\'),\n \'sqlite_autoindex_episode_mail_headers_1\':(\'index\',\'episode_mail_headers\'),\n \'idx_mail_headers_episode\':(\'index\',\'episode_mail_headers\'),\n \'trg_mail_headers_insert\':(\'trigger\',\'episodes\'),\n \'trg_mail_headers_update\':(\'trigger\',\'episodes\'),\n \'trg_mail_headers_delete\':(\'trigger\',\'episodes\'),\n}\n\ndef capture(root):\n result={}\n for p in sorted(Path(root).glob(\'*.sqlite3\')):\n  c=sqlite3.connect(p.as_uri()+\'?mode=ro\',uri=True)\n  try:\n   schema=c.execute(\'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql\').fetchall()\n   entry={\'schema\':schema,\'user_version\':c.execute(\'PRAGMA user_version\').fetchone()[0]}\n   if p.name==\'episodes.sqlite3\':\n    tables={}\n    for kind,name,_,_ in schema:\n     if kind!=\'table\':continue\n     quoted=\'"\'+name.replace(\'"\',\'""\')+\'"\'\n     rows=[]\n     for row in c.execute(\'SELECT * FROM \'+quoted):\n      raw=json.dumps(tuple(row),ensure_ascii=False,separators=(\',\',\':\'),default=lambda b:{\'bytes\':b.hex()}).encode()\n      rows.append(hashlib.sha256(raw).hexdigest())\n     tables[name]={\'rows\':len(rows),\'sha256\':hashlib.sha256(\'\'.join(sorted(rows)).encode()).hexdigest()}\n    entry[\'tables\']=tables\n   result[p.name]=entry\n  finally:c.close()\n return result\n\ndef verify(before,after):\n assert set(before)==set(after), \'Database file set changed\'\n assert before[\'episodes.sqlite3\'][\'user_version\']==21, \'Expected old schema v21\'\n assert after[\'episodes.sqlite3\'][\'user_version\']==22, \'Expected new schema v22\'\n for name,old in before.items():\n  new=after[name]\n  if name!=\'episodes.sqlite3\':\n   assert old==new, \'Unexpected schema/version change in another database\'\n   continue\n  old_objects={r[1]:tuple(r) for r in old[\'schema\']};new_objects={r[1]:tuple(r) for r in new[\'schema\']}\n  assert all(new_objects.get(k)==v for k,v in old_objects.items()), \'Existing schema object changed\'\n  extra={k:v for k,v in new_objects.items() if k not in old_objects}\n  assert set(extra)==set(ADDITIONS), \'Unexpected migration schema additions\'\n  # Production migration verifier separately validates exact DDL and trigger SQL.\n  assert all((extra[k][0],extra[k][2])==v for k,v in ADDITIONS.items()), \'Unexpected object type/owner\'\n  assert set(new[\'tables\'])==set(old[\'tables\'])|{\'episode_mail_headers\'}, \'Unexpected table set\'\n  assert all(new[\'tables\'].get(k)==v for k,v in old[\'tables\'].items()), \'Existing episode-store rows changed\'\n return {\'database_schemas_checked\':len(before),\'existing_episode_store_tables_unchanged\':len(before[\'episodes.sqlite3\'][\'tables\']),\'old_schema\':21,\'new_schema\':22,\'only_expected_schema_additions\':True}\n\nprint(json.dumps(capture(Path(\'/data\'))))\n'
schema_before=json.loads(docker('exec','-i',container,'python','-',input=schema_probe))
calendar_settings_probe="""import os,json,urllib.request
req=urllib.request.Request('http://127.0.0.1:8890/api/v1/mac-calendar',headers={'X-Icarus-Token':os.environ['ICARUS_SIDECAR_TOKEN']})
with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=10) as r:c=json.load(r)
print(json.dumps({key:c.get(key) for key in ('selected','enabled','memory_allowed','status')}))
"""
calendar_before=json.loads(docker('exec','-i',container,'python','-',input=calendar_settings_probe))
assert len(calendar_before['selected'])==3 and calendar_before['status']=='granted' and calendar_before['memory_allowed'] is False
backupscript=root/'backup.py'
g=runpy.run_path(str(backupscript)) # returned namespace retains the recovery lock
original=g['config_bytes'];folder=g['folder']
assert config.read_bytes()==original
# Cold backup has been restored and verified before any code/config switch.
qualified=docker('run','--rm','-i','--network','none','--read-only','--memory','1g','--cpus','2','--tmpfs','/tmp:rw,mode=1777','--user','0','--mount',f'type=bind,source={folder},target=/backup,readonly','--entrypoint','python',image,'-',input=(root/'qualify_copy_worker.py').read_text())
copy_proof=json.loads(qualified)
assert copy_proof['all_derived_headers_match_originals'] and copy_proof['only_expected_schema_additions']
(root/'protected-copy-migration.json').write_text(json.dumps(copy_proof,indent=2)+'\n')
old_hashes=contents_hashes(app)
stage=Path(tempfile.mkdtemp(prefix='.Kingfisher-update-f858681-',suffix='.app',dir=app.parent))
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
 fd,name=tempfile.mkstemp(prefix='.kingfisher-mail-header-',dir=config.parent)
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
 guard_namespace={};exec((root/'migration_guard.py').read_text(),guard_namespace)
 schema_preservation=guard_namespace['verify'](schema_before,schema_after)
 calendar_after=json.loads(docker('exec','-i',container,'python','-',input=calendar_settings_probe));assert calendar_before==calendar_after
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
 proof={'version':version,'backend_image_id':image,'backend_healthy':True,'native_files_match_canonical_dmg':True,'native_strict_deep_signature':True,'all_seven_core_tables_unchanged':True,'only_expected_v22_schema_additions':True,'existing_episode_store_tables_unchanged':schema_preservation['existing_episode_store_tables_unchanged'],'sqlite_schema_databases_checked':len(schema_after),'protected_copy_migration_passed':True,'data_volume_unchanged':True,'only_env_image_selector_changed':True,'runtime_provider_configuration_preserved':True,'ambient_compose_overrides_removed':True,'background_paused':True,'storage_blocked':None,'three_selected_calendars_and_read_only_memory_choice_preserved':True,'backup_directory':str(folder),'native_process_restarted':False,'native_window_verified':False,'installed_but_native_restart_pending':True,'backup':{k:g['proof'][k] for k in ('volume_files','volume_directories','volume_bytes','root_sqlite_integrity_checked','restore_bytewise_match','restore_directory_entries_match','restore_ownership_modes_mtime_xattrs_match')}}
 (folder/'mail-header-install-verification.json').write_text(json.dumps(proof,indent=2)+'\n');(folder/'mail-header-install-verification.json').chmod(0o600)
 Path('/private/tmp/kingfisher-mail-header-install-verification-20261011.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps({k:v for k,v in proof.items() if k!='backup_directory'}))
except BaseException:
 if moved.exists():
  rollback_code_without_restarting_data()
  print('Update failed: backend stopped; existing data kept, verified preupdate backup available. Recovery must be checked before restarting.',flush=True)
 raise
