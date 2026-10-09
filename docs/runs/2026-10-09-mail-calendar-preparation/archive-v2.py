"""One-time exact duplicate archive relocation with cold bytes and safe same-image resume."""
from pathlib import Path
import hashlib,json,os,shutil,sys
sys.path.insert(0,'/private/tmp/kingfisher-mail-calendar-install-20261009')
import install as pinned
import data_proof
import relocate_snapshot as relocation
f=pinned.frozen
ROOT=Path(__file__).resolve().parent
BACKUP=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Rueckweg/2026-10-09-vor-archivverlagerung-geprueft')
OLD_HOST=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Rueckweg/2026-10-09-vor-e21193d-schema20/data-with-journals/sicherungen')
TARGET=relocation.TARGET
f.require(hashlib.sha256((ROOT/'relocate_snapshot.py').read_bytes()).hexdigest()=='145e7e32c02ebc889dd1f9e83f341c520dd53dca3395617ef294eee755865827','helper_changed')

def main():
 c=json.loads(Path('/private/tmp/kingfisher-mail-calendar-install-20261009/config.json').read_text())
 task=pinned.Install(c,f.System());result={'status':'prepare_failed','active_data_changed':None,'archive_mutation_attempted':False};stopped=False;started=False;before=None
 def run(*a):return task.cmd(*a)
 def probe(script,data=True,writable=False,files=()):
  if Path(script).name=='tree.py':files=(*files,Path(data_proof.__file__))
  code,value=task.isolated(script,data=data,writable=writable,files=files)
  f.require(code==0,'archive_probe_failed');return value
 def tree():
  return probe(Path('/private/tmp/kingfisher-mail-calendar-install-20261009/tree.py'))['entries']
 try:
  f.require(not BACKUP.exists() and BACKUP.parent.is_dir(),'backup_path')
  f.require(hashlib.sha256(Path(c['manifest']).read_bytes()).hexdigest()==c['manifest_sha256'],'manifest_changed')
  f.require(hashlib.sha256(Path(c['checker']).read_bytes()).hexdigest()==c['checker_sha256'],'checker_changed')
  task.sys.maintenance(c);row=task.inspect(f.CONTAINER);task.mount(row,readonly=False)
  f.require(row['State']['Running'] and row['Image']==pinned.OLD_IMAGE,'unexpected_current_service')
  task.volume_before=task.volume();old_env=task.env.read_bytes()
  token=next(x.split('=',1)[1].strip().strip('\"\'') for x in old_env.decode().splitlines() if x.startswith('ICARUS_SIDECAR_TOKEN='))
  old_host=relocation.tree(OLD_HOST)
  f.require(any(e[0]=='file' for e in old_host['entries']),'empty_archive')
  f.require(task.sys.free_bytes(BACKUP.parent)>2*1024**3,'host_reserve')
  run('docker','stop','-t','45',f.CONTAINER);stopped=True;task.quiet()
  BACKUP.mkdir(mode=0o700);raw=BACKUP/'data-with-journals'
  run('docker','cp',f.CONTAINER+':/data',str(raw));task.quiet()
  before=tree();f.require(data_proof.tree_manifest(raw)==before,'cold_copy_mismatch')
  f.require(json.loads((raw/'hintergrund.json').read_text())['pausiert'] is True,'background_not_paused')
  f.write_private(BACKUP/'raw-file-manifest.json',{'entries':before})
  fresh_host=relocation.tree(raw/'sicherungen');f.require(fresh_host['entries']==old_host['entries'],'retained_archive_mismatch')
  scan_code=ROOT/'scan_live.py';scan_code.write_text("import json\nimport relocate_snapshot as helper\nprint(json.dumps(helper.scan('/data/sicherungen')))\n")
  live=probe(scan_code,files=(ROOT/'relocate_snapshot.py',));plan=relocation.make_plan(raw/'sicherungen',live)
  plan_raw=relocation.canonical(plan);plan_sha=hashlib.sha256(plan_raw).hexdigest();plan_file=BACKUP/'relocation-plan.json'
  plan_file.write_bytes(plan_raw);plan_file.chmod(0o600)
  f.require(relocation.tree(OLD_HOST)==old_host and data_proof.tree_manifest(raw)==before,'archive_changed_before_apply')
  f.require(tree()==before,'live_changed_before_apply');task.quiet()
  apply_code=ROOT/'apply_live.py';apply_code.write_text("from pathlib import Path\nimport json,relocate_snapshot as helper\nprint(json.dumps(helper.apply('/data/sicherungen',Path('/tmp/relocation-plan.json').read_bytes(),"+repr(plan_sha)+")))\n")
  result['archive_mutation_attempted']=True
  outcome=probe(apply_code,writable=True,files=(ROOT/'relocate_snapshot.py',plan_file));task.quiet()
  f.require(outcome['status']=='one_verified_duplicate_removed','archive_not_removed')
  # Exact exhaustive difference: only entries below this fixed archived leaf.
  prefix='sicherungen/'+TARGET
  expected=[e for e in before if e[0]!=prefix and not e[0].startswith(prefix+'/')]
  after=tree();f.require(after==expected,'unexpected_active_file_change')
  result['active_data_changed']=False
  f.require(data_proof.tree_manifest(raw)==before and relocation.tree(OLD_HOST)==old_host,'host_archive_changed')
  f.require(task.env.read_bytes()==old_env and task.inspect(f.CONTAINER)['Image']==pinned.OLD_IMAGE,'runtime_changed')
  run('docker','start',f.CONTAINER);stopped=False;started=True
  health=task.sys.health(token,version='1.0.6-local.e21193d')
  storage=run(c['native_probe'],c['app']).decode().strip()
  result.update(status='one_duplicate_archived',target=TARGET,host_archives_verified=2,active_file_tree_exact=True,health=health,native_storage_probe=storage,plan_sha256=plan_sha,bytes_reclaimed=sum(e[2] for e in old_host['entries'] if e[0]=='file'))
 except Exception as exc:
  result.update(status='stopped_review_required' if stopped else ('post_archive_runtime_verification_failed' if started else 'prepare_failed'),error=str(exc) if isinstance(exc,(f.CheckFailed,ValueError)) else 'archive_check_failed')
  # No automatic retry or restore, and no start after an unverified difference.
 if BACKUP.is_dir():f.write_private(BACKUP/'relocation-result.json',result)
 print(json.dumps(result));return 0 if result['status']=='one_duplicate_archived' else 1
if __name__=='__main__':raise SystemExit(main())
