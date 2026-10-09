#!/usr/bin/env python3
"""Prepared, NOT LIVE EXECUTED: exact Kingfisher category-20 image-only install.

No generic updater or downgrade API. No application imports. Root supplies
metadata-only JSON; credentials remain in the existing env file. Import is inert.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import tempfile
import uuid

import data_proof
import wal_finalize

REVISION='5621ec9e1f94ee40ea12485e128950d251211be4'
VERSION='1.0.6-local.5621ec9'
IMAGE='ghcr.io/icarus-health/kingfisher-app:'+VERSION
IMAGE_ID='sha256:72837cc0356954760e26aa1f9eb99713edc5287f598d7bd1a994f28a4298168f'
VOLUME='kingfisher_kingfisher-data'
CONTAINER='kingfisher-kingfisher-1'
PREFLIGHT_SHA='19bc7ff195e760f277fcad4e80dd64f4dddc5ec36221243e613d1917194c54c8'
PATCH_SHA='25244a13586375dc9366aaad8d68adf4cd4867174bd9a2b207afacb44ad907b8'
ROOT=Path(__file__).resolve().parent
WAL_HELPER_SHA='a1cfd9ce698420f63dc9dd0f2a6111a80d960e81285613367341c79189a8d20b'
DATA_PROOF_SHA='1316a92cf90edb21c89c59a1ea31a3f6b57f3437cff6994c62ab00ac5a56ce71'

class CheckFailed(RuntimeError):pass

def require(value,code):
    if not value:raise CheckFailed(code)

def sha(path):return data_proof.sha_file(Path(path))

def safe_json(raw):
    try:
        result=json.loads(raw)
        require(isinstance(result,dict),'invalid_json_result')
        return result
    except (ValueError,UnicodeError):raise CheckFailed('invalid_json_result') from None

def write_private(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(data,stream,sort_keys=True,indent=2)

@contextmanager
def readable_staging(sources):
    """Only caller-selected code/hash metadata; original modes never change.

    Docker's destination UID need not equal the image's kingfisher UID. A 0644
    copy is readable there; its host parent remains private 0700 throughout.
    """
    sources=tuple(Path(source) for source in sources)
    require(len({source.name for source in sources})==len(sources),'duplicate_copy_name')
    with tempfile.TemporaryDirectory(prefix='kingfisher-copy-metadata-') as directory:
        root=Path(directory);root.chmod(0o700);staged=[]
        for source in sources:
            require(source.is_file() and not source.is_symlink(),'unsafe_copy_source')
            target=root/source.name
            shutil.copyfile(source,target);target.chmod(0o644)
            require(sha(target)==sha(source),'copy_bytes_changed')
            staged.append(target)
        yield tuple(staged)


def compose_environment():
    # Compose shell variables override --env-file. Preserve Docker connection
    # selection, but never let the installer shell change the image or settings.
    return {key:value for key,value in os.environ.items()
            if not key.startswith(('KINGFISHER_', 'ICARUS_')) and key!='LLM_API_KEY'}

class System:
    def run(self,argv):
        response=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900,
                                env=compose_environment() if argv[:2]==['docker','compose'] else None)
        return response.returncode,response.stdout
    def maintenance(self,config):
        # Observation plus operator's maintenance-window attestation, NOT an OS
        # lock against a human launching another writer between observations.
        code,raw=self.run(['ps','-axo','comm='])
        require(code==0,'process_check_failed')
        require(not any(line.strip().endswith('/Kingfisher.app/Contents/MacOS/Kingfisher')
                        or line.strip()==str(Path(config['app'])/'Contents/MacOS/Kingfisher')
                        for line in raw.decode().splitlines()),'native_or_launcher_active')
        code,raw=self.run(['launchctl','list'])
        require(code==0,'launchagent_check_failed')
        require(not any('kingfisher' in line.lower() for line in raw.decode().splitlines()),'native_or_launcher_active')
        code,raw=self.run(['ps','-axo','command='])
        require(code==0,'process_check_failed')
        require(not any(str(Path(config['app'])/'Contents/MacOS/Kingfisher') in line
                        or '/Kingfisher.app/Contents/MacOS/Kingfisher' in line
                        or ('compose' in line and ('-p kingfisher' in line or str(Path(config['app'])/'Contents/Resources/compose.yaml') in line))
                        for line in raw.decode().splitlines()),'native_or_launcher_active')
    def guarded_run(self,argv,check):
        # Keep stdout out of a bounded pipe: the content-free table inventories
        # can exceed a pipe buffer. Never replay stderr/private exception text.
        failure=None
        with tempfile.TemporaryFile() as output:
            process=subprocess.Popen(argv,stdout=output,stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+900
            while process.poll() is None:
                if failure is None:
                    try:check()
                    except Exception:failure=CheckFailed('maintenance_window_lost')
                if time.monotonic()>deadline:
                    # Do not kill a migration container or assume its state. The
                    # installer leaves it for manual review; no publish follows.
                    process.terminate();process.wait(timeout=5)
                    raise CheckFailed('migration_wait_timeout')
                time.sleep(0.25)
            if failure is not None:raise failure
            check();output.seek(0);return process.returncode,output.read()
    def free_bytes(self,path):return shutil.disk_usage(path).free
    def port_open(self):
        try:
            with socket.create_connection(('127.0.0.1',8890),timeout=1):return True
        except (OSError,TimeoutError):return False
    def health(self,token,version=None,inspection=False):
        def get(path):
            connection=http.client.HTTPConnection('127.0.0.1',8890,timeout=3)
            try:
                connection.request('GET',path,headers={'X-Icarus-Token':token})
                response=connection.getresponse();raw=response.read()
                return response.status,json.loads(raw) if response.status==200 else None
            finally:connection.close()
        deadline=time.monotonic()+45
        while True:
            try:
                status,health=get('/health');require(status==200,'health_failed')
                status,recovery=get('/api/v1/recovery/status')
                if inspection:
                    require(health.get('mode')=='inspection' and health.get('operational') is False,'inspection_health')
                    require(status==200 and recovery.get('mode')=='inspection' and recovery.get('operational') is False,'inspection_route')
                else:
                    require(health.get('operational') is not False and (status==404 or (status==200 and recovery.get('operational') is True)),'unexpected_inspection')
                    if version:
                        status,release=get('/api/v1/fassung');require(status==200 and release.get('fassung')==version,'version_health')
                    require(get('/api/v1/world')[0]==200,'read_only_route')
                    status,intake=get('/api/v1/mail/intake')
                    require(status==200 and intake.get('background_paused') is True,'background_not_paused')
                    require(all(account.get('stand',{}).get('zustand')!='liest' for account in intake.get('accounts',[])),'mail_intake_active')
                return {'health':True,'inspection':inspection,'read_only_route':not inspection,'background_paused':not inspection}
            except Exception:
                if time.monotonic()>=deadline:raise CheckFailed('health_failed') from None
                time.sleep(1)

class Install:
    def __init__(self,config,system):
        self.c=config;self.sys=system;self.stopped=False;self.published=False
        self.backup=Path(config['backup']);self.env=Path(config['env']);self.app=Path(config['app'])
        self.result={'status':'prepare_failed','published':False,'version':VERSION,'image_id':IMAGE_ID,'execution':'requested_local_install'}
    def cmd(self,*args):
        code,out=self.sys.run(list(args));require(code==0,'command_failed');return out
    def inspect(self,name):
        rows=json.loads(self.cmd('docker','inspect',name));require(len(rows)==1,'container_identity');return rows[0]
    def volume(self):
        rows=json.loads(self.cmd('docker','volume','inspect',VOLUME));require(len(rows)==1,'volume_identity')
        row=rows[0];require(row.get('Name')==VOLUME and row.get('Driver')=='local','volume_identity')
        return {key:row.get(key) for key in ('Name','Driver','Mountpoint','Options')}
    def mount(self,row,readonly=None):
        mounts=[m for m in row.get('Mounts',[]) if m.get('Destination')=='/data']
        require(len(mounts)==1 and mounts[0].get('Type')=='volume' and mounts[0].get('Name')==VOLUME,'data_volume_changed')
        if readonly is not None:require(mounts[0].get('RW') is (not readonly),'data_volume_access')
    def isolated(self,script,*args,data=False,writable=False,files=()):
        name='kingfisher-category-check-'+uuid.uuid4().hex[:12]
        target='/tmp/'+Path(script).name
        command=['docker','create','--name',name,'--network','none','--restart','no','--entrypoint','python']
        if data:command+=['--mount','type=volume,src='+VOLUME+',dst=/data'+('' if writable else ',readonly')]
        else:command+=['--tmpfs','/data:rw,noexec,nosuid,size=1048576']
        # Exact image ID avoids tag movement; no credentials or other service env.
        command += [IMAGE_ID,target,*args]
        self.cmd(*command)
        try:
            with readable_staging((script,*files)) as staged:
                for source in staged:
                    self.cmd('docker','cp',str(source),name+':/tmp/'+source.name)
            row=self.inspect(name)
            require(row.get('Config',{}).get('User')=='kingfisher','oneshot_user_changed')
            require(row['Image']==IMAGE_ID and row['HostConfig']['NetworkMode']=='none' and row['HostConfig']['RestartPolicy']['Name']=='no' and not row['HostConfig'].get('PortBindings'),'oneshot_isolation')
            if data:self.mount(row,readonly=not writable)
            else:
                require(row['HostConfig'].get('Tmpfs')=={'/data':'rw,noexec,nosuid,size=1048576'},'package_tmpfs_missing')
                require(all(m.get('Type')=='tmpfs' and m.get('Destination')=='/data' for m in row.get('Mounts',[])),'package_check_has_data_volume')
            code,raw=(self.sys.guarded_run(['docker','start','-a',name],lambda:self.quiet(allowed=(name,)))
                      if writable else self.sys.run(['docker','start','-a',name]))
            row=self.inspect(name)
            require(row['State']['Running'] is False,'oneshot_still_running')
            exitcode=row['State']['ExitCode'];require(code==exitcode,'oneshot_exit_disagreement')
            answer=safe_json(raw)
            return exitcode,answer
        finally:
            # Never force-remove a possibly still-running one-shot writer.
            self.cmd('docker','rm',name)
    def proof(self,cold=True):
        if cold:
            code,result=self.isolated(ROOT/'data_proof.py','--data-dir','/data','--cold',data=True)
            require(code==0,'data_proof_failed');return result
        target='/tmp/data_proof.py'
        with readable_staging((ROOT/'data_proof.py',)) as staged:
            self.cmd('docker','cp',str(staged[0]),CONTAINER+':'+target)
        return safe_json(self.cmd('docker','exec',CONTAINER,'python',target,'--data-dir','/data'))
    def quiet(self,allowed=()):
        self.sys.maintenance(self.c)
        row=self.inspect(CONTAINER);require(row['State']['Running'] is False,'service_not_stopped');self.mount(row,readonly=False)
        require(not self.sys.port_open(),'host_port_active')
        writers=set(self.cmd('docker','ps','--filter','volume='+VOLUME,'--format','{{.Names}}').decode().split())
        require(writers<=set(allowed),'other_volume_writer')
        require(self.volume()==self.volume_before,'volume_identity_changed')
    def preserved(self,before,after,*,schema,inspection=False,all_rows=True):
        require(after['schema']==schema,'episode_schema')
        require(after['databases']==before['databases']==list(data_proof.DATABASES),'active_database_set')
        for key in ('originals','settings_sha256','background_sha256'):
            require(after[key]==before[key],'preservation_failed')
        require(after['paused'] is True and after['inspection'] is inspection,'pause_or_inspection_changed')
        if all_rows:require(before['content_sha256']==after['content_sha256'],'stored_rows_changed')
    def bundle(self):
        for rel,key in [('Contents/MacOS/Kingfisher','native_sha256'),('Contents/Resources/compose.yaml','compose_sha256'),('Contents/Info.plist','plist_sha256')]:
            path=self.app/rel;require(path.is_file() and not path.is_symlink() and sha(path)==self.c[key],'bundle_hash')
        self.cmd('codesign','--verify','--strict','--deep',str(self.app))
        require(sha(self.c['native_probe'])==self.c['native_probe_sha256'],'native_probe_hash')
        require(self.cmd(self.c['native_probe'],str(self.app)).strip()==b'before=ok\nafter=ok','native_probe_failed')
    def prepare(self):
        require(self.c.get('operator_exclusive_window') is True,'exclusive_maintenance_required')
        self.sys.maintenance(self.c)
        require(self.c['image']==IMAGE and self.c['image_id']==IMAGE_ID and self.c['version']==VERSION and self.c['volume']==VOLUME,'unsupported_install_target')
        require(self.app.is_absolute() and self.env.is_absolute() and self.backup.is_absolute() and not self.app.is_symlink() and not self.env.is_symlink() and not self.backup.exists(),'unsafe_paths')
        require(self.backup.parent.is_dir(),'backup_parent_missing')
        for key in ('host_reserve_bytes','volume_reserve_bytes'):require(type(self.c[key]) is int and self.c[key]>0,'storage_reserve_required')
        require(sha(self.c['preflight'])==PREFLIGHT_SHA,'preflight_hash')
        require(sha(ROOT/'wal_finalize.py')==WAL_HELPER_SHA and sha(ROOT/'data_proof.py')==DATA_PROOF_SHA,'wal_helper_hash')
        for key in ('checker','manifest'):require(sha(self.c[key])==self.c[key+'_sha256'],'package_hash')
        manifest=safe_json(Path(self.c['manifest']).read_bytes())
        require(manifest['revision']==REVISION and manifest['version']==VERSION and len(manifest['python_files'])==264 and len(manifest['ui_files'])==112,'package_manifest')
        images=json.loads(self.cmd('docker','image','inspect',IMAGE));require(len(images)==1 and images[0]['Id']==IMAGE_ID,'image_identity')
        self.bundle();self.volume_before=self.volume()
        row=self.inspect(CONTAINER);self.mount(row,readonly=False);require(row['State']['Running'] is True,'old_service_not_running')
        self.old_image=row['Image'];require(self.old_image!=IMAGE_ID,'already_installed')
        require(self.cmd('docker','ps','--filter','volume='+VOLUME,'--format','{{.Names}}').strip().decode()==CONTAINER,'other_volume_writer')
        self.old_env=self.env.read_bytes()
        lines=self.old_env.decode().splitlines(keepends=True)
        tokens=[line.split('=',1)[1].strip().strip("'\"") for line in lines if line.startswith('ICARUS_SIDECAR_TOKEN=')]
        require(len(tokens)==1 and tokens[0],'token_missing');self.token=tokens[0]
        matches=[n for n,line in enumerate(lines) if line.startswith('KINGFISHER_IMAGE=')]
        require(len(matches)==1,'image_env_ambiguous')
        newline='\r\n' if lines[matches[0]].endswith('\r\n') else '\n'
        lines[matches[0]]='KINGFISHER_IMAGE='+IMAGE+newline;self.new_env=''.join(lines).encode()
        code,checked=self.isolated(self.c['checker'])
        require(code==0 and checked=={'version':VERSION,'python_sources_verified':264,'ui_files_verified':112,'ui_file_set_exact':True},'package_check_failed')
        code,sizes=self.isolated(ROOT/'data_proof.py','--data-dir','/data','--measure',data=True)
        require(code==0,'storage_measure_failed')
        app_bytes=data_proof.measure(self.app)['tree_bytes']
        require(self.sys.free_bytes(self.backup.parent)>=2*sizes['tree_bytes']+app_bytes+len(self.old_env)+self.c['host_reserve_bytes'],'host_storage_reserve')
        # Snapshot + potential restore staging + a bounded migration growth margin.
        require(sizes['free_bytes']>=3*sizes['snapshot_bytes']+self.c['volume_reserve_bytes'] and sizes['free_inodes']>=1000,'volume_storage_reserve')
        self.backup.mkdir(mode=0o700)
        shutil.copytree(self.app,self.backup/'Kingfisher.app',symlinks=True)
        (self.backup/'kingfisher.env').write_bytes(self.old_env);os.chmod(self.backup/'kingfisher.env',0o600)
        write_private(self.backup/'metadata.json',{'version':VERSION,'image_id':IMAGE_ID,'old_image_id':self.old_image,'volume_identity':self.volume_before,'package_sha256':self.c['manifest_sha256'],'preflight_sha256':PREFLIGHT_SHA})
    def finalize_existing_wal(self):
        # Scan filenames before opening SQLite; a raw archive must precede even
        # read-only SQLite, which can update transient SHM reader marks.
        code,scan=self.isolated(ROOT/'wal_finalize.py','scan','--data-dir','/data',data=True,files=(ROOT/'data_proof.py',))
        require(code==0 and scan.get('status')=='scanned' and isinstance(scan.get('sidecars'),list),'wal_scan_failed')
        if not scan['sidecars']:
            self.result['wal_preparation']='not_needed';return
        self.quiet()
        raw=self.backup/'data-with-journals'
        self.cmd('docker','cp',CONTAINER+':/data',str(raw))
        manifest=self.backup/'raw-data-manifest.json'
        sealed=wal_finalize.seal_backup(raw,manifest)
        require(sealed.get('status')=='backup_sealed','raw_backup_seal_failed')
        write_private(self.backup/'raw-backup-seal.json',sealed)
        self.quiet()
        code,outcome=self.isolated(ROOT/'wal_finalize.py','finalize','--data-dir','/data',
            '--manifest','/tmp/'+manifest.name,'--manifest-sha256',sealed['manifest_sha256'],
            '--service-stopped','--unpublished','--exclusive-writer',data=True,writable=True,
            files=(ROOT/'data_proof.py',manifest))
        write_private(self.backup/'wal-finalization-result.json',outcome)
        require(code==0 and outcome.get('status')=='wal_finalized' and outcome.get('schema')==19
                and outcome.get('migration_permitted') is False
                and outcome.get('raw_backup_manifest_sha256')==sealed['manifest_sha256'],'wal_finalization_not_proven')
        self.quiet()
        self.result.update(wal_preparation='verified',raw_backup_manifest_sha256=sealed['manifest_sha256'])

    def execute(self):
        self.prepare()
        # This is the only stop command; no daemon/container wildcard operation.
        self.stopped=True;self.cmd('docker','stop','-t','45',CONTAINER);self.quiet()
        self.finalize_existing_wal()
        before=self.proof();require(before['schema']==19 and before['paused'] is True and before['inspection'] is False,'cold_preconditions')
        self.cmd('docker','cp',CONTAINER+':/data',str(self.backup/'data'))
        cold=data_proof.prove(self.backup/'data',cold=True)
        require(cold==before,'cold_copy_mismatch')
        write_private(self.backup/'cold-file-manifest.json',data_proof.tree_manifest(self.backup/'data'))
        write_private(self.backup/'cold-proof.json',cold)
        self.quiet();require(self.proof()==before,'changed_during_cold_copy')
        code,outcome=self.isolated(self.c['preflight'],'--data-dir','/data','--service-stopped','--unpublished',data=True,writable=True)
        write_private(self.backup/'migration-result.json',outcome)
        require(outcome.get('patch_sha256')==PATCH_SHA,'migration_result_identity')
        status=outcome.get('status');self.result['migration_status']=status if status in ('migrated','preflight_failed','restored_inspection','recovery_failed') else 'unknown'
        self.quiet()
        if status in ('preflight_failed','restored_inspection'):
            require(code==1 and outcome.get('publish_allowed') is False,'migration_result_inconsistent')
            inspection=status=='restored_inspection'
            if inspection:require(outcome.get('snapshot_verified') is True and outcome.get('rollback',{}).get('attempted') is True and outcome.get('rollback',{}).get('verified') is True,'restore_unverified')
            recovered=self.proof();self.preserved(before,recovered,schema=19,inspection=inspection)
            require(self.env.read_bytes()==self.old_env and self.inspect(CONTAINER)['Image']==self.old_image,'old_runtime_changed')
            self.cmd('docker','start',CONTAINER)
            health=self.sys.health(self.token,inspection=inspection)
            self.result.update(status='old_inspection_only' if inspection else 'old_schema19_resumed',health=health)
            return self.result
        require(status=='migrated' and code==0 and outcome.get('publish_allowed') is True and outcome.get('snapshot_verified') is True and outcome.get('outdated')==[],'migration_not_proven')
        after=self.proof();self.preserved(before,after,schema=20)
        self.quiet();self.bundle();self.quiet();require(self.env.read_bytes()==self.old_env,'env_changed_during_install')
        staged=self.env.with_name(self.env.name+'.category20-'+uuid.uuid4().hex[:8])
        fd=os.open(staged,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(self.new_env);stream.flush();os.fsync(stream.fileno())
        os.replace(staged,self.env)
        # Compose may partially succeed before returning failure: from this point
        # no old image or historical restore is ever called, even on health errors.
        self.published=True;self.result['published']=True
        self.cmd('docker','compose','-p','kingfisher','--env-file',str(self.env),'-f',str(self.app/'Contents/Resources/compose.yaml'),'up','-d','--no-build','--pull','never')
        health=self.sys.health(self.token,version=VERSION)
        row=self.inspect(CONTAINER);self.mount(row,readonly=False)
        require(row['Image']==IMAGE_ID and row['State']['Running'] is True and self.volume()==self.volume_before,'published_runtime_identity')
        final=self.proof(cold=False);self.preserved(before,final,schema=20,all_rows=False)
        require(self.env.read_bytes()==self.new_env,'published_env_changed');self.bundle()
        self.result.update(status='installed',health=health,same_data_volume=True,originals_preserved=True,original_count=before['originals']['count'],originals_sha256=before['originals']['sha256'],database_count=len(final['databases']),native_binary_unchanged=True,background_pause_preserved=True,cold_copy_verified=True)
        return self.result

def run(config,system=None):
    task=Install(config,system or System())
    try:result=task.execute()
    except Exception as exc:
        task.result.update(status='forward_repair_required' if task.published else ('stopped_manual_review' if task.stopped else 'prepare_failed'),error=str(exc) if isinstance(exc,CheckFailed) else 'install_check_failed')
        result=task.result
    if task.backup.is_dir():
        try:write_private(task.backup/'installation-result.json',result)
        except Exception:result['result_file_saved']=False
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--execute',action='store_true',help='Explicitly run the reviewed installer; without this flag no actions occur.')
    args=parser.parse_args()
    if not args.execute:print(json.dumps({'status':'not_executed'}));return 2
    try:result=run(safe_json(Path(args.config).read_bytes()))
    except Exception:result={'status':'prepare_failed','error':'configuration_invalid'}
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='installed' else 1

if __name__=='__main__':raise SystemExit(main())
