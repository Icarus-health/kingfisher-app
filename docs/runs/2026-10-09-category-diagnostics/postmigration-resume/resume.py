#!/usr/bin/env python3
"""Resume ONLY the pinned, migrated-but-unpublished schema20 installation.

No migration, checkpoint, historical restore, old-image start or service stop.
The original installer and preflight are retained byte-identically as evidence.
"""
import argparse
import json
import os
from pathlib import Path
import uuid

import data_proof
import orchestrator as frozen

ROOT=Path(__file__).resolve().parent
DEPENDENCIES={
    'orchestrator.py':'019197e4203f6ee83d5b8d8e5dc9a8741f7340eac38f51a90b72cdfb3b49b50d',
    'data_proof.py':'1316a92cf90edb21c89c59a1ea31a3f6b57f3437cff6994c62ab00ac5a56ce71',
    'wal_finalize.py':'a1cfd9ce698420f63dc9dd0f2a6111a80d960e81285613367341c79189a8d20b',
    'preflight.py':'19bc7ff195e760f277fcad4e80dd64f4dddc5ec36221243e613d1917194c54c8',
}
require=frozen.require


def static_bundle(task):
    for rel,key in [('Contents/MacOS/Kingfisher','native_sha256'),('Contents/Resources/compose.yaml','compose_sha256'),('Contents/Info.plist','plist_sha256')]:
        path=task.app/rel
        require(path.is_file() and not path.is_symlink() and frozen.sha(path)==task.c[key],'bundle_hash')
    require(frozen.sha(task.c['native_probe'])==task.c['native_probe_sha256'],'native_probe_hash')
    task.cmd('codesign','--verify','--strict','--deep',str(task.app))


def migrated_proof(task):
    code,proof=task.isolated(ROOT/'postmigration_proof.py','--data-dir','/data',data=True,files=(ROOT/'data_proof.py',))
    require(code==0,'postmigration_proof_failed')
    return proof


def execute(task):
    c=task.c;task.stopped=True
    task.result.update(status='stopped_schema20_manual_review',resume_only=True)
    require(c.get('operator_exclusive_window') is True,'exclusive_maintenance_required')
    require(c['image']==frozen.IMAGE and c['image_id']==frozen.IMAGE_ID and c['version']==frozen.VERSION and c['volume']==frozen.VOLUME,'unsupported_install_target')
    for name,digest in DEPENDENCIES.items():require(frozen.sha(ROOT/name)==digest,'resume_dependency_changed')
    require(task.backup.is_absolute() and task.backup.is_dir() and not task.backup.is_symlink(),'backup_directory')
    require(task.env.is_absolute() and task.env.is_file() and not task.env.is_symlink() and task.app.is_absolute() and not task.app.is_symlink(),'unsafe_paths')
    require(not (task.backup/'postmigration-resume-result.json').exists(),'resume_already_attempted')
    migration_path=task.backup/'migration-result.json';cold_path=task.backup/'cold-proof.json'
    require(frozen.sha(migration_path)==c['migration_result_sha256'],'migration_result_digest')
    require(frozen.sha(cold_path)==c['cold_proof_sha256'],'cold_proof_digest')
    outcome=frozen.safe_json(migration_path.read_bytes())
    require(outcome.get('status')=='migrated' and outcome.get('publish_allowed') is True
            and outcome.get('snapshot_verified') is True and outcome.get('patch_sha256')==frozen.PATCH_SHA
            and outcome.get('outdated')==[],'migration_not_proven')
    before=frozen.safe_json(cold_path.read_bytes())
    require(data_proof.prove(task.backup/'data',cold=True)==before,'canonical_backup_changed')
    require(before['schema']==19 and before['paused'] is True and before['inspection'] is False,'baseline_contract')
    metadata=frozen.safe_json((task.backup/'metadata.json').read_bytes())
    require(metadata.get('version')==frozen.VERSION and metadata.get('image_id')==frozen.IMAGE_ID
            and metadata.get('package_sha256')==c['manifest_sha256'] and metadata.get('preflight_sha256')==frozen.PREFLIGHT_SHA,'installation_metadata')
    for key in ('manifest','checker'):require(frozen.sha(c[key])==c[key+'_sha256'],'package_changed')
    images=json.loads(task.cmd('docker','image','inspect',frozen.IMAGE))
    require(len(images)==1 and images[0]['Id']==frozen.IMAGE_ID,'image_identity')
    task.volume_before=metadata['volume_identity'];task.old_image=metadata['old_image_id']
    task.quiet();require(task.inspect(frozen.CONTAINER)['Image']==task.old_image,'stopped_image_changed')
    static_bundle(task)  # deliberately NO runtime probe against the stopped service
    task.old_env=(task.backup/'kingfisher.env').read_bytes()
    require(task.env.read_bytes()==task.old_env,'env_changed_since_backup')
    lines=task.old_env.decode().splitlines(keepends=True)
    tokens=[line.split('=',1)[1].strip().strip("'\"") for line in lines if line.startswith('ICARUS_SIDECAR_TOKEN=')]
    require(len(tokens)==1 and tokens[0],'token_missing');task.token=tokens[0]
    matches=[i for i,line in enumerate(lines) if line.startswith('KINGFISHER_IMAGE=')]
    require(len(matches)==1,'image_env_ambiguous')
    newline='\r\n' if lines[matches[0]].endswith('\r\n') else '\n'
    lines[matches[0]]='KINGFISHER_IMAGE='+frozen.IMAGE+newline;task.new_env=''.join(lines).encode()
    after=migrated_proof(task)
    task.preserved(before,after,schema=20)  # every saved user row + originals/settings
    task.quiet();static_bundle(task);require(task.env.read_bytes()==task.old_env,'env_changed_before_publish')
    staged=task.env.with_name(task.env.name+'.schema20-resume-'+uuid.uuid4().hex[:8])
    fd=os.open(staged,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(task.new_env);out.flush();os.fsync(out.fileno())
    os.replace(staged,task.env)
    task.published=True;task.result['published']=True
    task.cmd('docker','compose','-p','kingfisher','--env-file',str(task.env),'-f',str(task.app/'Contents/Resources/compose.yaml'),'up','-d','--no-build','--pull','never')
    health=task.sys.health(task.token,version=frozen.VERSION)
    row=task.inspect(frozen.CONTAINER);task.mount(row,readonly=False)
    require(row['Image']==frozen.IMAGE_ID and row['State']['Running'] is True and task.volume()==task.volume_before,'published_runtime_identity')
    final=task.proof(cold=False);task.preserved(before,final,schema=20,all_rows=False)
    require(task.env.read_bytes()==task.new_env,'published_env_changed')
    task.bundle()  # runtime probe is now permitted after normal healthy startup
    task.result.update(status='installed',health=health,same_data_volume=True,originals_preserved=True,
                       original_count=before['originals']['count'],originals_sha256=before['originals']['sha256'],
                       database_count=len(final['databases']),background_pause_preserved=True,
                       native_binary_unchanged=True,migration_result_sha256=c['migration_result_sha256'])
    return task.result


def run(config,system=None):
    task=frozen.Install(config,system or frozen.System())
    try:result=execute(task)
    except Exception as exc:
        task.result.update(status='forward_repair_required' if task.published else 'stopped_schema20_manual_review',
                           error=str(exc) if isinstance(exc,(frozen.CheckFailed,data_proof.CheckFailed)) else 'resume_check_failed')
        result=task.result
    try:frozen.write_private(task.backup/'postmigration-resume-result.json',result)
    except Exception:result['result_file_saved']=False
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:print(json.dumps({'status':'not_executed'}));return 2
    try:result=run(frozen.safe_json(Path(args.config).read_bytes()))
    except Exception:result={'status':'stopped_schema20_manual_review','error':'configuration_invalid'}
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='installed' else 1

if __name__=='__main__':raise SystemExit(main())
