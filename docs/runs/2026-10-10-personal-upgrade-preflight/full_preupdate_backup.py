from pathlib import Path
from datetime import datetime, timezone
import subprocess, json, os, fcntl, hashlib, shutil, time
D='/opt/homebrew/bin/docker'; container='kingfisher-kingfisher-1'
def docker(*args,**kw):
    return subprocess.run([D,*args],check=True,text=True,capture_output=True,**kw).stdout
support=Path.home()/'Library/Application Support/Kingfisher';config=support/'kingfisher.env'
config_bytes=config.read_bytes(); values={}
for line in config_bytes.decode().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key,sep,value=line.partition('='); assert sep and key not in values;values[key]=value
state=json.loads(docker('inspect',container))[0]
actual=dict(x.split('=',1) for x in state['Config']['Env'] if '=' in x)
for key,value in values.items():
    assert value==(state['Config']['Image'] if key=='KINGFISHER_IMAGE' else actual.get(key)), 'Configuration changed'
assert values.get('ICARUS_SIDECAR_TOKEN') and values.get('ICARUS_SECRETS_PASSPHRASE')
mounts=[x for x in state['Mounts'] if x['Destination']=='/data'];assert len(mounts)==1 and mounts[0]['Type']=='volume'
volume=mounts[0]['Name']; assert volume=='kingfisher_kingfisher-data'
users=docker('ps','--filter',f'volume={volume}','--format','{{.Names}}').splitlines();assert users==[container]
lock=os.fdopen(os.open(config.with_suffix('.env.recovery.lock'),os.O_CREAT|os.O_WRONLY,0o600),'w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
folder=support/'Sicherungen'/('vor-alltagspaket-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir(parents=True,mode=0o700)
(folder/'kingfisher.env').write_bytes(config_bytes);(folder/'kingfisher.env').chmod(0o600)
worker=r'''
from pathlib import Path
import tarfile, hashlib, json, sqlite3, os, stat, subprocess, base64
root=Path('/source');out=Path('/backup')
def manifest_at(base):
    result={}
    for p in [base,*sorted(base.rglob('*'))]:
        st=p.lstat()
        assert stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode), 'Unsupported volume entry'
        item={'type':'directory' if p.is_dir() else 'file','uid':st.st_uid,'gid':st.st_gid,'mode':stat.S_IMODE(st.st_mode),'mtime_ns':st.st_mtime_ns,'xattrs':{name:base64.b64encode(os.getxattr(p,name)).decode() for name in sorted(os.listxattr(p))}}
        if p.is_file():
            with p.open('rb') as stream:item.update(sha256=hashlib.file_digest(stream,'sha256').hexdigest(),bytes=st.st_size)
        result[str(p.relative_to(base))]=item
    return result
manifest=manifest_at(root);archive=out/'volume.tar.gz'
subprocess.run(['tar','--format=pax','--acls','--xattrs','--xattrs-include=*','--numeric-owner','-I','gzip -3','-cf',str(archive),'-C',str(root),'.'],check=True,capture_output=True)
archive.chmod(0o600)
with tarfile.open(archive,'r:gz') as tf:
    members=tf.getmembers()
    assert len(members)==len(manifest)
    names=set()
    for member in members:
        path=Path(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        rel=str(path);assert rel in manifest and rel not in names;names.add(rel)
        assert member.isdir() or member.isfile() or member.islnk()
        assert member.isdir()==(manifest[rel]['type']=='directory')
        if member.islnk():
            target=Path(member.linkname)
            assert not target.is_absolute() and '..' not in target.parts
            assert str(target) in manifest and manifest[str(target)]['type']=='file'
    assert names==set(manifest)
restored=Path('/tmp/restore-proof');restored.mkdir()
subprocess.run(['tar','--acls','--xattrs','--xattrs-include=*','--same-owner','--same-permissions','-xf',str(archive),'-C',str(restored)],check=True,capture_output=True)
assert manifest_at(restored)==manifest, 'Restored content or metadata differs'
# Compare before SQLite opens the restored copy, which may create/change WAL sidecars.
checked=[]
for db in sorted(restored.glob('*.sqlite3')):
    connection=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
    assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    checked.append(db.name);connection.close()
files=[v for v in manifest.values() if v['type']=='file']
(out/'volume-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');(out/'volume-manifest.json').chmod(0o600)
with archive.open('rb') as stream:archive_sha=hashlib.file_digest(stream,'sha256').hexdigest()
result={'volume_files':len(files),'volume_directories':len(manifest)-len(files),'volume_bytes':sum(v['bytes'] for v in files),'xattr_entries':sum(len(v['xattrs']) for v in manifest.values()),'root_sqlite_integrity_checked':len(checked),'archive_sha256':archive_sha,'restore_bytewise_match':True,'restore_directory_entries_match':True,'restore_ownership_modes_mtime_xattrs_match':True,'network':'none','original_volume_readonly':True}
(out/'backup-verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');(out/'backup-verification.json').chmod(0o600)
print(json.dumps(result))
'''
originally_running=bool(state['State']['Running'])
try:
    assert config.read_bytes()==config_bytes
    if originally_running:
        docker('stop',container)
    result=docker('run','--rm','-i','--network','none','--read-only','--tmpfs','/tmp:rw','--user','0','--mount',f'type=volume,source={volume},target=/source,readonly','--mount',f'type=bind,source={folder},target=/backup','--entrypoint','python',state['Image'],'-',input=worker)
    proof=json.loads(result);proof.update({'backup_directory':str(folder),'old_image_id':state['Image'],'old_image_tag':state['Config']['Image'],'original_configuration_sha256':hashlib.sha256(config_bytes).hexdigest(),'configuration_mode':'0600','directory_mode':'0700','productive_data_copied_to_repository':False})
    (folder/'backup-verification.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n');(folder/'backup-verification.json').chmod(0o600)
    Path('/private/tmp/kingfisher-daily-ux-preupdate-backup-result.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
finally:
    if originally_running:
        docker('start',container)
        for attempt in range(60):
            try:
                docker('exec',container,'python','-c',"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8890/health',timeout=1)");break
            except subprocess.CalledProcessError:time.sleep(.5)
        else:raise RuntimeError('Old runtime did not return healthy')
print(json.dumps({'backup_directory':str(folder),'file_and_directory_recovery_with_metadata':'passed','old_runtime_restarted':originally_running,'source_files':proof['volume_files'],'integrity_checked_databases':proof['root_sqlite_integrity_checked']}))
