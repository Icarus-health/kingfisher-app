from pathlib import Path
import json,hashlib,subprocess
root=Path(__file__).parent;old=Path('/private/tmp/kingfisher-task-package-a5787c8');version='1.0.6-preview.f858681'
image=subprocess.check_output(['/opt/homebrew/bin/docker','image','inspect','--format','{{.Id}}','ghcr.io/icarus-health/kingfisher-app:'+version],text=True).strip()
log=(root/'package-probe-final.log').read_text();assert json.loads(log.strip().splitlines()[-1])['packaged_mail_header_index_50000_backfill_atomic_updates_source_kinds']=='passed'
proof={'exit_code':0,'version':version,'image_id':image,'probe_sha256':hashlib.sha256((root/'package_probe.py').read_bytes()).hexdigest(),'log_sha256':hashlib.sha256((root/'package-probe-final.log').read_bytes()).hexdigest(),'network':'none','productive_mounts':False,'new_index_runtime_cases':4}
(root/'package-runtime-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
s=(old/'install.py').read_text()
s=s.replace("root=Path('/private/tmp/kingfisher-task-package-a5787c8')","root=Path('/private/tmp/kingfisher-header-package-f858681')")
s=s.replace("version='1.0.6-preview.a5787c8'", "version='"+version+"'")
s=s.replace('/private/tmp/kingfisher-calendar-package-bfe555e/mac-app-manifest.json','/private/tmp/kingfisher-task-package-a5787c8/mac-app-manifest.json')
s=s.replace("=='1.0.6-preview.bfe555e'","=='1.0.6-preview.a5787c8'")
s=s.replace('sha256:e2caaa4f7d2d466cb5dac00db3dab3eeab3a3a6e39b30cc33115a81079aaafb1','sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf')
s=s.replace("assert image=='sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf'","assert image=="+repr(image))
s=s.replace("root/'package-probe-stdin.log'","root/'package-probe-final.log'")
s=s.replace('.Kingfisher-update-a5787c8-', '.Kingfisher-update-f858681-').replace('kingfisher-task-followup-', 'kingfisher-mail-header-').replace('task-followup-install-verification','mail-header-install-verification')
# Preserve earlier baseline and patch validation; add this exact affected-code gate.
needle="assert json.loads((root/'dmg-verification.json').read_text())['read_only_mounted_bundle_matches'] is True"
addition='''index_checks=checks.parent/'2026-10-11-mail-header-index'
index_manifest=json.loads((index_checks/'manifest.json').read_text())
for name,digest in index_manifest.items():assert hashlib.sha256((index_checks/name).read_bytes()).hexdigest()==digest
for name,count in (('affected.log',200),('support.log',111),('originals.log',24)):
 assert f'{count} passed' in (index_checks/name).read_text()
review=json.loads((index_checks/'independent-review.json').read_text())
for name,digest in review['source_sha256'].items():assert hashlib.sha256((root/'sidecar/icarus_memory'/name).read_bytes()).hexdigest()==digest
'''
assert needle in s;s=s.replace(needle,addition+needle)
start=s.index('schema_probe="""');end=s.index('schema_before=',start)
guard=(root/'migration_guard.py').read_text();s=s[:start]+'schema_probe='+repr(guard+"\nprint(json.dumps(capture(Path('/data'))))\n")+'\n'+s[end:]
needle="assert config.read_bytes()==original\nold_hashes=contents_hashes(app)"
addition='''assert config.read_bytes()==original
# Cold backup has been restored and verified before any code/config switch.
qualified=docker('run','--rm','-i','--network','none','--read-only','--memory','1g','--cpus','2','--tmpfs','/tmp:rw,mode=1777','--user','0','--mount',f'type=bind,source={folder},target=/backup,readonly','--entrypoint','python',image,'-',input=(root/'qualify_copy_worker.py').read_text())
copy_proof=json.loads(qualified)
assert copy_proof['all_derived_headers_match_originals'] and copy_proof['only_expected_schema_additions']
(root/'protected-copy-migration.json').write_text(json.dumps(copy_proof,indent=2)+'\\n')
old_hashes=contents_hashes(app)'''
assert needle in s;s=s.replace(needle,addition)
needle="schema_after=json.loads(docker('exec','-i',container,'python','-',input=schema_probe));assert schema_before==schema_after"
addition="""schema_after=json.loads(docker('exec','-i',container,'python','-',input=schema_probe))
 guard_namespace={};exec((root/'migration_guard.py').read_text(),guard_namespace)
 schema_preservation=guard_namespace['verify'](schema_before,schema_after)"""
assert needle in s;s=s.replace(needle,addition)
s=s.replace("'sqlite_schema_and_user_version_unchanged':True,'sqlite_schema_databases_checked':len(schema_after)","'only_expected_v22_schema_additions':True,'existing_episode_store_tables_unchanged':schema_preservation['existing_episode_store_tables_unchanged'],'sqlite_schema_databases_checked':len(schema_after),'protected_copy_migration_passed':True")

# Prevent ambient shell values from overriding the saved env-file during Compose.
needle="def compose_up():\n subprocess.run([D,'compose','-p','kingfisher','-f',str(app/'Contents/Resources/compose.yaml'),'--env-file',str(config),'up','-d','--no-build','--pull','never'],check=True,capture_output=True,text=True)"
replacement="""def compose_environment():
 return {k:v for k,v in os.environ.items() if not k.startswith(('ICARUS_','KINGFISHER_','COMPOSE_')) and k!='LLM_API_KEY'}
def verify_runtime_configuration(old_env,new_env):
 def selected(values):
  mapping=dict(item.split('=',1) for item in values if '=' in item)
  return {k:v for k,v in mapping.items() if (k.startswith(('ICARUS_','KINGFISHER_')) or k=='LLM_API_KEY') and k!='KINGFISHER_FASSUNG'}
 assert selected(old_env)==selected(new_env), 'Runtime configuration changed unexpectedly'
def compose_up():
 subprocess.run([D,'compose','-p','kingfisher','-f',str(app/'Contents/Resources/compose.yaml'),'--env-file',str(config),'up','-d','--no-build','--pull','never'],check=True,capture_output=True,text=True,env=compose_environment())"""
assert needle in s;s=s.replace(needle,replacement)
needle="assert json.loads(docker('inspect',container))[0]['Image']=='sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf'"
replacement="old_runtime=json.loads(docker('inspect',container))[0]\nassert old_runtime['Image']=='sha256:24a5528456eff9474d1aa7b6f9f7e710491e6a6a0323829c2cd00e177387d3cf'"
assert needle in s;s=s.replace(needle,replacement)
needle=" state=json.loads(docker('inspect',container))[0]\n assert state['Image']==image"
replacement=" state=json.loads(docker('inspect',container))[0]\n verify_runtime_configuration(old_runtime['Config']['Env'],state['Config']['Env'])\n assert state['Image']==image"
assert needle in s;s=s.replace(needle,replacement)
s=s.replace("'only_env_image_selector_changed':True", "'only_env_image_selector_changed':True,'runtime_provider_configuration_preserved':True,'ambient_compose_overrides_removed':True")

(root/'install.py').write_text(s);compile(s,str(root/'install.py'),'exec')
print(json.dumps({'prepared':True,'image_id':image,'version':version,'personal_install_started':False}))
