"""Archive a frozen, exclusively Kingfisher-owned legacy build branch; never prune."""
import json, subprocess, tarfile, gzip, hashlib, os, shutil, runpy
from pathlib import Path
D='/opt/homebrew/bin/docker'
ROOT=Path('/private/tmp/kingfisher-storage-reserve-20261011')
OUT=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-11-exclusive-build-cache')
BASE=runpy.run_path(str(ROOT/'archive_builds.py'))
PLAN=json.loads((ROOT/'cache-plan.json').read_text())
CURRENT=BASE['CURRENT'];ROLLBACK=BASE['ROLLBACK']
def docker(*args):return subprocess.check_output([D,*args],text=True)
def ancestors(roots,mapping):
 result=set();todo=list(roots)
 while todo:
  w=todo.pop()
  if w in result:continue
  result.add(w)
  if w in mapping and mapping[w].get('Parent'):todo.append(mapping[w]['Parent'])
 return result
def exclusive_branch(selected,protected_roots,mapping):
 eligible=ancestors(selected,mapping)-ancestors(protected_roots,mapping)
 external={x['Parent'] for x in mapping.values() if x['Id'] not in eligible and x.get('Parent') in eligible}
 return eligible-ancestors(external,mapping)
def archive_verify(path,ids,tags):
 with tarfile.open(path,'r:gz') as t:
  members=t.getmembers();names=set()
  for member in members:
   p=Path(member.name);assert not p.is_absolute() and '..' not in p.parts
   assert member.name not in names and (member.isdir() or member.isfile())
   names.add(member.name)
  index=json.load(t.extractfile('index.json'));assert {x['digest'] for x in index['manifests']}==set(ids)
  manifest=json.load(t.extractfile('manifest.json'));assert {tag for x in manifest for tag in (x.get('RepoTags') or [])}==set(tags)
  for desc in index['manifests']:
   b=t.extractfile('blobs/sha256/'+desc['digest'].split(':')[1]).read();assert 'sha256:'+hashlib.sha256(b).hexdigest()==desc['digest']
   v=json.loads(b)
   assert 'blobs/sha256/'+v['config']['digest'].split(':')[1] in names
   assert all('blobs/sha256/'+x['digest'].split(':')[1] in names for x in v['layers'])
  for member in members:
   if member.isfile():
    h=hashlib.sha256()
    with t.extractfile(member) as f:
     while b:=f.read(1024*1024):h.update(b)
    if member.name.startswith('blobs/sha256/'):assert h.hexdigest()==member.name.split('/')[-1]
 with gzip.open(path,'rb') as f:
  while f.read(1024*1024):pass
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def inspect_or_missing(w):
 r=subprocess.run([D,'image','inspect',w],capture_output=True,text=True)
 if r.returncode==0:return json.loads(r.stdout)[0]
 if 'No such image:' in r.stderr:return None
 raise RuntimeError('Image inspection failed; stopping')
def main():
 mapping={x['Id']:x for x in json.loads((ROOT/'image-graph-private.json').read_text())}
 candidates=PLAN['eligible_images'];ids=set(candidates)
 assert ids==exclusive_branch({w for w in PLAN['selected_refs'].values()},set(PLAN['protected_roots']),mapping)
 assert len(ids)==178 and not ({CURRENT,ROLLBACK}&ids)
 xs=json.loads(docker('image','inspect',*ids));assert {x['Id'] for x in xs}==ids
 for x in xs:
  frozen=candidates[x['Id']]
  assert x.get('Parent')==frozen['parent'] and sorted(x.get('RepoTags') or [])==sorted(frozen['tags'])
  assert x['RootFS']['Layers']==frozen['layers'] and x['Descriptor']['digest']==x['Id']
  for item in x['Config'].get('Env') or []:
   name,_,value=item.partition('=')
   if any(part in name.upper() for part in ('TOKEN','PASSWORD','PASSPHRASE','API_KEY','SECRET')):assert not value, 'Credential-like build environment refused'
 initial=BASE['containers']();identity=BASE['container_identity'](initial);volumes=BASE['volumes']()
 assert not any(c['Image'] in ids for c in initial)
 assert BASE['image'](CURRENT)['Id']==CURRENT and BASE['image'](ROLLBACK)['Id']==ROLLBACK
 assert shutil.disk_usage(OUT.parent).free>7*1024**3
 OUT.mkdir(mode=0o700,parents=True,exist_ok=False)
 archive=OUT/'exclusive-kingfisher-build-cache.tar.gz';partial=OUT/'exclusive-kingfisher-build-cache.partial.tar.gz'
 tags={tag for v in candidates.values() for tag in v['tags']}
 args=sorted(tags)+sorted(w for w in ids if not candidates[w]['tags'])
 before=BASE['disk_free']()
 fingerprint_source=Path('/private/tmp/kingfisher-core-table-fingerprints.py').read_text()
 def core_fingerprints():return json.loads(subprocess.check_output([D,'exec','-i','kingfisher-kingfisher-1','python','-'],input=fingerprint_source,text=True))
 core_before=core_fingerprints()
 proc=subprocess.Popen([D,'image','save',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with gzip.open(partial,'wb',compresslevel=1) as out:
   while b:=proc.stdout.read(1024*1024):
    out.write(b)
    if partial.stat().st_size>6*1024**3:raise RuntimeError('Archive budget exceeded; no removal')
  if proc.wait()!=0:raise RuntimeError('Archive export failed; no removal')
 finally:
  if proc.poll() is None:proc.terminate();proc.wait()
 sha=archive_verify(partial,ids,tags)
 os.replace(partial,archive);archive.chmod(0o600)
 proof={'eligible_image_count':len(ids),'tagged_build_count':sum(bool(v['tags']) for v in candidates.values()),'archive_sha256':sha,'archive_bytes':archive.stat().st_size,'all_178_manifest_ids_and_blob_hashes_verified':True,'current_and_rollback_excluded':True,'unrelated_tagged_images_and_container_ancestors_excluded':True,'archive_limit_bytes':6*1024**3,'productive_volume_or_model_cache_exported':False,'docker_free_before_bytes':before,'image_removal_commands':[],'image_missing_after_removal':[],'restore_command':'docker image load -i exclusive-kingfisher-build-cache.tar.gz'}
 proofpath=OUT/'verification.json'
 def record():proofpath.write_text(json.dumps(proof,indent=2)+'\n');proofpath.chmod(0o600)
 record();(OUT/'frozen-cache-plan.json').write_text(json.dumps(PLAN,indent=2)+'\n')
 pending=set(ids)
 while pending:
  leafs=sorted(pending-{candidates[w]['parent'] for w in pending})
  assert leafs, 'Cycle in frozen image graph'
  for w in leafs:
   assert BASE['container_identity'](BASE['containers']())==identity and BASE['volumes']()==volumes
   assert not any(c['Image']==w for c in BASE['containers']())
   x=inspect_or_missing(w)
   if x is not None:
    assert x['Id']==w and set(x.get('RepoTags') or [])==set(candidates[w]['tags'])
    assert x.get('Parent')==candidates[w]['parent']
    if x.get('RepoTags'):
     for tag in candidates[w]['tags']:
      live_image=inspect_or_missing(w)
      if live_image is None:break
      assert tag in live_image['RepoTags'] and set(live_image['RepoTags']) <= set(candidates[w]['tags'])
      assert not any(c['Image']==w for c in BASE['containers']())
      subprocess.run([D,'image','rm',tag],check=True,capture_output=True,text=True)
      proof['image_removal_commands'].append(tag);record()
    if inspect_or_missing(w) is not None:
     assert not (inspect_or_missing(w).get('RepoTags') or [])
     subprocess.run([D,'image','rm',w],check=True,capture_output=True,text=True)
     proof['image_removal_commands'].append(w)
   assert inspect_or_missing(w) is None, 'Image still exists; stopping'
   proof['image_missing_after_removal'].append(w);pending.remove(w);record()
   if len(proof['image_missing_after_removal'])%20==0:print(json.dumps({'cache_nodes_processed':len(proof['image_missing_after_removal'])}),flush=True)
 assert BASE['container_identity'](BASE['containers']())==identity and BASE['volumes']()==volumes
 for w in (CURRENT,ROLLBACK):assert BASE['image'](w)['Id']==w
 live=json.loads(docker('inspect','kingfisher-kingfisher-1'))[0]
 assert live['State']['Running'] and live['State'].get('Health',{}).get('Status')=='healthy'
 assert core_before==core_fingerprints()
 proof.update(all_seven_core_tables_unchanged=True,docker_free_after_bytes=BASE['disk_free'](),container_identities_and_mounts_unchanged=True,volume_names_unchanged=True,current_and_rollback_images_preserved=True,backend_healthy=True)
 record();print(json.dumps({k:v for k,v in proof.items() if k not in ('image_removal_commands','image_missing_after_removal')}),flush=True)
if __name__=='__main__':main()
