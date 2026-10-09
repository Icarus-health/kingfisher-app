#!/usr/bin/env python3
"""Pinned schema20-to-schema20 image swap; no migration or database restore."""
import json, os, shutil, sys, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import orchestrator as frozen
import data_proof

ROOT=Path(__file__).resolve().parent
OLD_IMAGE='sha256:c6bc20a9a39f8759dc7f987462378e41c109afb6b87d754555c14dc3d557176b'
frozen.REVISION='d431383b551c6a65254c93331819998f86a685eb'
frozen.VERSION='1.0.6-local.d431383'
frozen.IMAGE='ghcr.io/icarus-health/kingfisher-app:'+frozen.VERSION
frozen.IMAGE_ID='sha256:930ef4d708d93668dcb79a54cbaac678444283e769addac1b9c3914fd511b858'
require=frozen.require

class Install(frozen.Install):
    def readonly(self,tree=False):
        file=ROOT/('tree.py' if tree else 'proof.py')
        code,result=self.isolated(file,data=True,files=(Path(data_proof.__file__),))
        require(code==0,'readonly_data_check_failed')
        return result
    def static_bundle(self):
        for rel,key in [('Contents/MacOS/Kingfisher','native_sha256'),('Contents/Resources/compose.yaml','compose_sha256'),('Contents/Info.plist','plist_sha256')]:
            p=self.app/rel;require(p.is_file() and not p.is_symlink() and frozen.sha(p)==self.c[key],'native_bundle_changed')
        self.cmd('codesign','--verify','--strict','--deep',str(self.app))
    def execute(self):
        require(frozen.sha(frozen.__file__)=='4e52cb1dfaa026f8e223788c77d75448e21e9baab02a49052cb383ada5ddfba2','frozen_helper_changed')
        require('ROOT_MUST_PIN' not in frozen.IMAGE_ID and 'ROOT_MUST_PIN' not in self.c['image_id']
                and 'ROOT_MUST_PIN' not in self.c['checker_sha256']
                and 'ROOT_MUST_PIN' not in self.c['manifest_sha256'], 'root_pins_required')
        self.prepare()  # exact package, signature, running old service, volume/reserve, env backup
        require(self.old_image==OLD_IMAGE,'unexpected_previous_image')
        self.stopped=True;self.cmd('docker','stop','-t','45',frozen.CONTAINER);self.quiet()
        # Preserve ALL bytes, including SQLite journals, before opening databases.
        raw=self.backup/'data-with-journals'
        self.cmd('docker','cp',frozen.CONTAINER+':/data',str(raw));self.quiet()
        tree=self.readonly(tree=True)
        require(tree=={'entries':data_proof.tree_manifest(raw)},'raw_copy_mismatch')
        frozen.write_private(self.backup/'raw-file-manifest.json',tree)
        shutil.copytree(raw,self.backup/'data',symlinks=True)
        require(data_proof.tree_manifest(self.backup/'data')==tree['entries'],'working_copy_mismatch')
        before=self.readonly()
        require(before['schema']==20 and before['paused'] is True and before['inspection'] is False,'schema20_baseline_required')
        copied=data_proof.prove(self.backup/'data',cold=False)
        self.preserved(before,copied,schema=20)
        frozen.write_private(self.backup/'wal-aware-proof.json',before)
        self.quiet();require(self.readonly(tree=True)==tree,'raw_source_changed')
        self.preserved(before,self.readonly(),schema=20)
        self.static_bundle();self.quiet()
        require(self.env.read_bytes()==self.old_env,'env_changed_before_publish')
        staged=self.env.with_name(self.env.name+'.mail-calendar-'+uuid.uuid4().hex[:8])
        fd=os.open(staged,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(self.new_env);out.flush();os.fsync(out.fileno())
        os.replace(staged,self.env)
        self.published=True;self.result['published']=True
        self.cmd('docker','compose','-p','kingfisher','--env-file',str(self.env),'-f',str(self.app/'Contents/Resources/compose.yaml'),'up','-d','--no-build','--pull','never')
        health=self.sys.health(self.token,version=frozen.VERSION)
        row=self.inspect(frozen.CONTAINER);self.mount(row,readonly=False)
        require(row['Image']==frozen.IMAGE_ID and row['State']['Running'] is True and self.volume()==self.volume_before,'published_runtime_identity')
        final=self.proof(cold=False);self.preserved(before,final,schema=20,all_rows=False)
        require(self.env.read_bytes()==self.new_env,'published_env_changed');self.bundle()
        require(data_proof.tree_manifest(raw)==tree['entries'],'sealed_raw_backup_changed')
        self.result.update(status='installed',schema=20,migration_performed=False,health=health,same_data_volume=True,
            originals_preserved=True,original_count=before['originals']['count'],database_count=len(final['databases']),
            background_pause_preserved=True,native_binary_unchanged=True,raw_copy_verified=True,native_ui_verified=False)
        return self.result

def main():
    c=json.loads((ROOT/'config.json').read_text());task=Install(c,frozen.System())
    try:result=task.execute()
    except Exception as e:
        result=task.result;result.update(status='forward_repair_required' if task.published else ('stopped_manual_review' if task.stopped else 'prepare_failed'),error=str(e) if isinstance(e,(frozen.CheckFailed,data_proof.CheckFailed)) else 'installation_check_failed')
    if task.backup.is_dir():frozen.write_private(task.backup/'installation-result.json',result)
    print(json.dumps(result,sort_keys=True));return 0 if result.get('status')=='installed' else 1
if __name__=='__main__':raise SystemExit(main())
