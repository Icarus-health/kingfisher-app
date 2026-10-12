import subprocess,json,gzip,hashlib,tarfile,os
from pathlib import Path
D='/opt/homebrew/bin/docker'
refs={'kingfisher-current-mail:b472108':'sha256:975b7debbbd13623ce1ae3f9daff8c9c16cec92b6ef7615cea5246ce786ce682','kingfisher:core-workflow-a1b4e98-qa':'sha256:8f189851ea5a4ed540f778dbbe786f3a81dbdf1edd980e9c96b97c750df47fd0','kingfisher-workflow:20261006-final':'sha256:b389fdf02667be927cd6806579839aabbfbebb8ee348f8190128c9d544cc5d6e'}
containers=json.loads(subprocess.check_output([D,'inspect',*subprocess.check_output([D,'ps','-aq'],text=True).split()],text=True))
used={c['Image'] for c in containers}
for ref,want in refs.items():
 state=json.loads(subprocess.check_output([D,'image','inspect',ref],text=True))[0]
 assert state['Id']==want and want not in used
 assert state['RepoTags']==[ref], 'Other tags refer to selected image'
folder=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-local-connection-bc21155'); archive=folder/'unused-test-images.tar.gz'
if not archive.exists():
 p=subprocess.Popen([D,'image','save',*refs],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 with gzip.open(archive,'wb',compresslevel=1) as out:
  while b:=p.stdout.read(1024*1024):out.write(b)
 assert p.wait()==0
with tarfile.open(archive,'r:gz') as t:
 manifest=json.load(t.extractfile('manifest.json'))
 assert {tag for entry in manifest for tag in entry['RepoTags']}==set(refs)
 assert {json.load(t.extractfile(entry['Config']))['rootfs']['type'] for entry in manifest}=={'layers'}
 index=json.load(t.extractfile('index.json'))
 assert {item['digest'] for item in index['manifests']}==set(refs.values())
 for item in index['manifests']:
  blob=t.extractfile('blobs/sha256/'+item['digest'].split(':')[1]).read()
  assert 'sha256:'+hashlib.sha256(blob).hexdigest()==item['digest']
 # Verify every content-addressed blob and gzip CRC before removing any image.
 for member in t:
  if member.isfile():
   h=hashlib.sha256()
   with t.extractfile(member) as f:
    while b:=f.read(1024*1024):h.update(b)
   if member.name.startswith('blobs/sha256/'):
    assert h.hexdigest()==member.name.split('/')[-1]
with archive.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
proof={'refs':refs,'archive_sha256':sha,'archive_bytes':archive.stat().st_size,'image_ids_verified_in_archive':True,'no_container_references':True,'volumes_untouched':True,'recover_with':'docker image load -i unused-test-images.tar.gz'}
(folder/'unused-test-images-manifest.json').write_text(json.dumps(proof,indent=2)+'\n')
for ref in refs:subprocess.run([D,'image','rm',ref],check=True,capture_output=True,text=True)
print(json.dumps(proof))
print(subprocess.check_output([D,'run','--rm','--network','none','--read-only','--entrypoint','df','sha256:a3f6dc20a9b9115c0479b11fc174d4eb19ff80ab79320237efc8c99c7761d812','-h','/'],text=True))
subprocess.run([D,'start','kingfisher-kingfisher-1'],check=True,capture_output=True,text=True)
