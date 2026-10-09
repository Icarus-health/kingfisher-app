"""Real caller control flow with temporary trees and a fake system, never Docker."""
from pathlib import Path
import json,shutil,tempfile,unittest
from unittest.mock import patch
import execute_verified_v2 as caller
import relocate_snapshot as helper

class FakeSystem:
 def __init__(self,task):self.task=task
 def maintenance(self,c):self.task.events.append('maintenance')
 def free_bytes(self,p):return 3*1024**3
 def health(self,token,version):
  self.task.events.append('health')
  if self.task.fail_health:raise caller.f.CheckFailed('health_failed')
  return {'health':True,'background_paused':True}
class FakeTask:
 def __init__(self,root,fail_health=False,mutate=False):
  self.root=root;self.live=root/'live';self.env=root/'env';self.env.write_text('ICARUS_SIDECAR_TOKEN=synthetic\n')
  self.running=True;self.events=[];self.sys=FakeSystem(self);self.fail_health=fail_health;self.mutate=mutate
 def inspect(self,name):return {'Image':caller.pinned.OLD_IMAGE,'State':{'Running':self.running}}
 def mount(self,*a,**k):pass
 def volume(self):return {'Name':'synthetic-volume'}
 def quiet(self):assert not self.running;self.events.append('quiet')
 def cmd(self,*a):
  if a[:2]==('docker','stop'):self.running=False;self.events.append('stop');return b''
  if a[:2]==('docker','cp'):shutil.copytree(self.live,Path(a[-1]));self.events.append('copy');return b''
  if a[:2]==('docker','start'):self.running=True;self.events.append('start');return b''
  self.events.append('native-storage');return b'before=ok\nafter=ok\n'
 def isolated(self,script,**kwargs):
  name=Path(script).name
  if name=='tree.py':
   assert any(Path(p).name=='data_proof.py' for p in kwargs.get('files',())), 'isolated tree dependency missing'
   return 0,{'entries':caller.data_proof.tree_manifest(self.live)}
  if name=='scan_live.py':return 0,helper.scan(self.live/'sicherungen')
  if name=='apply_live.py':
   self.events.append('apply');assert not self.running
   plan=next(p for p in kwargs['files'] if p.name=='relocation-plan.json').read_bytes()
   import hashlib
   result=helper.apply(self.live/'sicherungen',plan,hashlib.sha256(plan).hexdigest())
   if self.mutate:(self.live/'episodes.sqlite3').write_bytes(b'changed-active')
   return 0,result
  raise AssertionError(name)

class CallerTests(unittest.TestCase):
 def run_case(self,fail_health=False,mutate=False):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);live=root/'live';(live/'sicherungen'/helper.TARGET).mkdir(parents=True)
   (live/'sicherungen'/helper.TARGET/'episode.sqlite3').write_bytes(b'old-snapshot')
   (live/'episodes.sqlite3').write_bytes(b'active-original')
   (live/'hintergrund.json').write_text('{"pausiert":true}')
   old_host=root/'old-host';shutil.copytree(live/'sicherungen',old_host)
   backup=root/'backup';shutil.copy2(Path(helper.__file__),root/'relocate_snapshot.py')
   task=FakeTask(root,fail_health,mutate)
   with patch.object(caller,'BACKUP',backup),patch.object(caller,'OLD_HOST',old_host),patch.object(caller,'ROOT',root),patch.object(caller.pinned,'Install',return_value=task):
    code=caller.main()
   return code,json.loads((backup/'relocation-result.json').read_text()),task.events,task.running
 def test_success_checks_cold_copy_before_api_and_resumes_same_image(self):
  code,result,events,running=self.run_case()
  self.assertEqual(code,0);self.assertTrue(running)
  self.assertLess(events.index('copy'),events.index('apply'))
  self.assertGreater(events.index('health'),events.index('copy'))
  self.assertFalse(result['active_data_changed']);self.assertTrue(result['active_file_tree_exact'])
 def test_runtime_failure_is_not_reported_as_prepare_failure(self):
  code,result,events,running=self.run_case(fail_health=True)
  self.assertEqual(code,1);self.assertTrue(running)
  self.assertEqual(result['status'],'post_archive_runtime_verification_failed')
  self.assertTrue(result['archive_mutation_attempted'])
 def test_unexpected_active_difference_never_restarts(self):
  code,result,events,running=self.run_case(mutate=True)
  self.assertEqual(code,1);self.assertFalse(running)
  self.assertEqual(result['status'],'stopped_review_required')
  self.assertNotIn('start',events)
  self.assertIsNone(result['active_data_changed'])
if __name__=='__main__':unittest.main()
