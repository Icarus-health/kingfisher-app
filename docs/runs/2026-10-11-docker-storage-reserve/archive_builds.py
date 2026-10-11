"""One guarded local archive operation, not a general Docker prune tool."""
import subprocess, json, gzip, hashlib, tarfile, os, shutil, fcntl
from pathlib import Path
D='/opt/homebrew/bin/docker'
CURRENT='sha256:a8c96f76d9c5c67de4aff2ffebcd1590f95d70547cfca5760c142cd42909c45a'
ROLLBACK='sha256:a3f6dc20a9b9115c0479b11fc174d4eb19ff80ab79320237efc8c99c7761d812'
REFS={
 'kingfisher-conditional-report:e326f81':'sha256:f9caa5537b33403f0d7beff828a20fecd4ee3458d9ac41068e40d1cf1b436a6e',
 'kingfisher-world-validity:e2bd4c1':'sha256:fc2b486e0644fe17ad2dc4baf9d3098051ff8a6a5ded9e5db90b5d56b78ecf5f',
 'kingfisher-source-status:a214f99':'sha256:552a7d2f6ccc6433357000c2385dfe0b034f597a8c7126ea87fca3009580937a',
 'kingfisher-learning:9f18408':'sha256:ede4448a83055a5a1e65b4000dc39cd91f0f5d9e08bc483f88f4e96a51421187',
 'kingfisher-current-mail:1913e26':'sha256:6b03de639866319d310581f003345c458b13e824d53bb4e76a5381c14f5c9430',
 'kingfisher-cos-priority:83cfaa0':'sha256:4b50fb4a18b36f86c2d60de5d7eb9952a580f02baf9c67cc67791e7d935f4f62',
}
# Exact six additional local alias tags observed for the same six image IDs.
for original_ref, image_id in list(REFS.items()):
 code=original_ref.split(':',1)[1]
 REFS['ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.'+code]=image_id
OUT=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-storage-reserve')
def docker(*args):return subprocess.check_output([D,*args],text=True)
def containers():
 ids=docker('ps','-aq').split()
 return json.loads(docker('inspect',*ids)) if ids else []
def container_identity(xs):
 return {x['Id']:{'image':x['Image'],'mounts':sorted((m['Type'],m.get('Name',m['Source']),m['Destination']) for m in x['Mounts'])} for x in xs}
def volumes():return sorted(docker('volume','ls','-q').splitlines())
def image(ref):return json.loads(docker('image','inspect',ref))[0]
def disk_free():
 return int(docker('exec','kingfisher-kingfisher-1','python','-c',"import os; s=os.statvfs('/data'); print(s.f_bavail*s.f_frsize)").strip())
def check_unused(ref,want):
 x=image(ref);assert x['Id']==want and want not in (CURRENT,ROLLBACK)
 allowed={r for r,w in REFS.items() if w==want} or {ref}
 assert ref in (x.get('RepoTags') or []) and set(x['RepoTags']) <= allowed, 'Unknown alias references selected image'
 assert not any(c['Image']==want for c in containers()), 'Container references selected image'
 for item in x['Config'].get('Env') or []:
  name,_,value=item.partition('=')
  if any(marker in name.upper() for marker in ('TOKEN','PASSWORD','PASSPHRASE','API_KEY','SECRET')):
   assert not value, 'Nonempty credential-like image environment; archive refused'
 return x['Size']
def verify_archive(path,refs):
 with tarfile.open(path,'r:gz') as t:
  members=t.getmembers();seen=set()
  for member in members:
   assert member.name not in seen;seen.add(member.name)
   p=Path(member.name);assert not p.is_absolute() and '..' not in p.parts
   assert member.isdir() or member.isfile(), 'Unexpected archive member type'
  manifest=json.load(t.extractfile('manifest.json'))
  assert {tag for item in manifest for tag in item['RepoTags']}==set(refs)
  index=json.load(t.extractfile('index.json'))
  assert {item['digest'] for item in index['manifests']}==set(refs.values())
  for desc in index['manifests']:
   name='blobs/sha256/'+desc['digest'].split(':')[1]
   b=t.extractfile(name).read();assert 'sha256:'+hashlib.sha256(b).hexdigest()==desc['digest']
   obj=json.loads(b)
   assert obj['config']['digest'].startswith('sha256:')
   assert 'blobs/sha256/'+obj['config']['digest'].split(':')[1] in seen
   assert all('blobs/sha256/'+v['digest'].split(':')[1] in seen for v in obj['layers'])
  for member in members:
   if member.isfile():
    h=hashlib.sha256()
    with t.extractfile(member) as f:
     while chunk:=f.read(1024*1024):h.update(chunk)
    if member.name.startswith('blobs/sha256/'):
     assert h.hexdigest()==member.name.split('/')[-1], 'Blob hash mismatch'
 # Consume complete gzip stream, including footer CRC and any trailing members.
 with gzip.open(path,'rb') as f:
  while f.read(1024*1024):pass
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 OUT.mkdir(mode=0o700,parents=True,exist_ok=False)
 lock=os.fdopen(os.open(OUT/'operation.lock',os.O_CREAT|os.O_WRONLY,0o600),'w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 initial=containers();identity=container_identity(initial);initial_volumes=volumes()
 personal=next(x for x in initial if x['Name']=='/kingfisher-kingfisher-1')
 assert personal['Image']==CURRENT and personal['State']['Running'] and personal['State'].get('Health',{}).get('Status')=='healthy'
 assert image(ROLLBACK)['Id']==ROLLBACK
 sizes={ref:check_unused(ref,want) for ref,want in REFS.items()}
 for want in set(REFS.values()):
  assert set(image(want)['RepoTags'])=={r for r,w in REFS.items() if w==want}
 assert shutil.disk_usage(OUT).free > sum(image(want)['Size'] for want in set(REFS.values()))+1024**3, 'Not enough Mac reserve for worst-case archive'
 before_free=disk_free();archive=OUT/'reviewed-test-builds.tar.gz';partial=OUT/'reviewed-test-builds.partial.tar.gz'
 proc=subprocess.Popen([D,'image','save',*REFS],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with gzip.open(partial,'wb',compresslevel=1) as out:
   while chunk:=proc.stdout.read(1024*1024):out.write(chunk)
  if proc.wait()!=0:raise RuntimeError('Docker image export failed; no image removed')
 finally:
  if proc.poll() is None:proc.terminate();proc.wait()
 sha=verify_archive(partial,REFS)
 os.replace(partial,archive);archive.chmod(0o600)
 proof={'refs':REFS,'archive_sha256':sha,'archive_bytes':archive.stat().st_size,'archive_manifest_ids_and_all_blob_hashes_verified':True,'protected_images':[CURRENT,ROLLBACK],'productive_volumes_or_model_cache_exported':False,'restore_command':'docker image load -i reviewed-test-builds.tar.gz','docker_free_before_bytes':before_free,'removed_refs':[]}
 proofpath=OUT/'verification.json'
 def record():proofpath.write_text(json.dumps(proof,indent=2)+'\n');proofpath.chmod(0o600)
 record()
 for ref,want in REFS.items():
  check_unused(ref,want)
  assert container_identity(containers())==identity and volumes()==initial_volumes
  subprocess.run([D,'image','rm',ref],check=True,capture_output=True,text=True)
  proof['removed_refs'].append(ref);record()
 assert container_identity(containers())==identity and volumes()==initial_volumes
 assert image(CURRENT)['Id']==CURRENT and image(ROLLBACK)['Id']==ROLLBACK
 healthy=json.loads(docker('inspect','kingfisher-kingfisher-1'))[0]
 assert healthy['State']['Running'] and healthy['State'].get('Health',{}).get('Status')=='healthy'
 proof.update(docker_free_after_bytes=disk_free(),container_identities_and_mounts_unchanged=True,volume_names_unchanged=True,current_and_rollback_images_preserved=True,backend_healthy=True)
 record();print(json.dumps(proof))
if __name__=='__main__':main()
