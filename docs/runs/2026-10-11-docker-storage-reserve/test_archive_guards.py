import unittest, tempfile, tarfile, hashlib, json, io, runpy, gzip
from pathlib import Path
ns=runpy.run_path('/private/tmp/kingfisher-storage-reserve-20261011/archive_builds.py')
verify=ns['verify_archive'];guard=ns['check_unused'];g=guard.__globals__
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def fixture(path,change=None):
 layer=b'Artificial layer, no personal information';config=b'{"rootfs":{"type":"layers"}}'
 obj={'config':{'digest':digest(config)},'layers':[{'digest':digest(layer)}]};manifest=json.dumps(obj).encode();want=digest(manifest)
 blobs={digest(config):config,digest(layer):layer,want:manifest}
 entries={'index.json':json.dumps({'manifests':[{'digest':want}]}).encode(),'manifest.json':json.dumps([{'RepoTags':['test:only'],'Config':'blobs/sha256/'+digest(config).split(':')[1],'Layers':['blobs/sha256/'+digest(layer).split(':')[1]]}]).encode()}
 entries.update({'blobs/sha256/'+k.split(':')[1]:v for k,v in blobs.items()})
 if change:change(entries,want)
 with tarfile.open(path,'w:gz') as t:
  for name,b in entries.items():
   info=tarfile.TarInfo(name);info.size=len(b);t.addfile(info,io.BytesIO(b))
 return {'test:only':want}
class Archive(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)/'test.tar.gz'
 def tearDown(self):self.temp.cleanup()
 def test_good(self):
  refs=fixture(self.p);self.assertEqual(verify(self.p,refs),hashlib.sha256(self.p.read_bytes()).hexdigest())
 def test_changed_blob(self):
  refs=fixture(self.p,lambda e,w:e.__setitem__('blobs/sha256/'+w.split(':')[1],b'changed'))
  with self.assertRaises(AssertionError):verify(self.p,refs)
 def test_missing_layer(self):
  def mutate(e,w):
   layer=json.loads(e['blobs/sha256/'+w.split(':')[1]])['layers'][0]['digest'];del e['blobs/sha256/'+layer.split(':')[1]]
  refs=fixture(self.p,mutate)
  with self.assertRaises(AssertionError):verify(self.p,refs)
 def test_path_traversal(self):
  refs=fixture(self.p,lambda e,w:e.__setitem__('../outside',b'bad'))
  with self.assertRaises(AssertionError):verify(self.p,refs)
 def test_wrong_expected_id(self):
  fixture(self.p)
  with self.assertRaises(AssertionError):verify(self.p,{'test:only':'sha256:wrong'})
 def test_corrupt_gzip_footer(self):
  refs=fixture(self.p);b=bytearray(self.p.read_bytes());b[-8]^=1;self.p.write_bytes(b)
  with self.assertRaises((OSError,EOFError,tarfile.ReadError)):verify(self.p,refs)
class RemovalGuard(unittest.TestCase):
 def setUp(self):
  self.old=(g['image'],g['containers']);self.x={'Id':'sha256:fake','RepoTags':['test:only'],'Size':10,'Config':{'Env':[]}};self.cs=[]
  g['image']=lambda ref:self.x;g['containers']=lambda:self.cs
 def tearDown(self):g['image'],g['containers']=self.old
 def test_unused(self):self.assertEqual(guard('test:only','sha256:fake'),10)
 def test_protected_id(self):
  self.x['Id']=ns['CURRENT']
  with self.assertRaises(AssertionError):guard('test:only',ns['CURRENT'])
 def test_container_reference(self):
  self.cs=[{'Image':'sha256:fake'}]
  with self.assertRaises(AssertionError):guard('test:only','sha256:fake')
 def test_other_tag(self):
  self.x['RepoTags'].append('other:tag')
  with self.assertRaises(AssertionError):guard('test:only','sha256:fake')
 def test_known_aliases_and_remaining_alias(self):
  old=g['REFS']
  try:
   g['REFS']={'test:only':'sha256:fake','test:alias':'sha256:fake'}
   self.x['RepoTags']=['test:only','test:alias']
   self.assertEqual(guard('test:only','sha256:fake'),10)
   self.x['RepoTags']=['test:alias']
   self.assertEqual(guard('test:alias','sha256:fake'),10)
   with self.assertRaises(AssertionError):guard('test:only','sha256:fake')
   self.x['RepoTags'].append('unknown:outside')
   with self.assertRaises(AssertionError):guard('test:alias','sha256:fake')
  finally:g['REFS']=old
 def test_credential_environment(self):
  self.x['Config']['Env']=['ICARUS_SIDECAR_TOKEN=artificial-test-secret']
  with self.assertRaises(AssertionError):guard('test:only','sha256:fake')
if __name__=='__main__':unittest.main()
