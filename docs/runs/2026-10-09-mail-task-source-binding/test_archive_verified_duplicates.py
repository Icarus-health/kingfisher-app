import importlib.util, json, tempfile, unittest
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('archive',Path(__file__).with_name('archive-verified-duplicates.py'))
a=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(a)
class ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.host=Path(self.tmp.name)/'host'; self.live=Path(self.tmp.name)/'live'; self.host.mkdir(); self.live.mkdir()
  for root in (self.host,self.live):
   for n in (*a.TARGETS,a.KEEP):
    d=root/n; d.mkdir(); (d/'meta').write_bytes(('synthetic-'+n).encode())
 def planraw(self):
  plan=a.make_plan(self.host,a.scan(self.live)); raw=a.canonical(plan); return raw
 def test_mismatch_deletes_nothing(self):
  raw=self.planraw(); (self.live/a.TARGETS[0]/'meta').write_bytes(b'changed')
  with self.assertRaises(ValueError): a.apply(self.live,raw,__import__('hashlib').sha256(raw).hexdigest())
  self.assertTrue((self.live/a.TARGETS[0]).exists())
 def test_symlink_rejected_without_delete(self):
  raw=self.planraw(); p=self.live/a.TARGETS[0]; p.rename(p.with_name('held')); p.symlink_to(p.with_name('held'))
  with self.assertRaises(ValueError): a.apply(self.live,raw,__import__('hashlib').sha256(raw).hexdigest())
  self.assertTrue(p.is_symlink()); self.assertTrue((self.live/a.TARGETS[1]).exists())
 def test_current_snapshot_is_retained(self):
  raw=self.planraw(); a.apply(self.live,raw,__import__('hashlib').sha256(raw).hexdigest())
  self.assertTrue((self.live/a.KEEP).exists())
 def test_host_copy_remains_byte_identical(self):
  before=a.tree(self.host); raw=self.planraw(); a.apply(self.live,raw,__import__('hashlib').sha256(raw).hexdigest())
  self.assertEqual(a.tree(self.host),before)
 def test_only_exact_targets_removed(self):
  raw=self.planraw(); a.apply(self.live,raw,__import__('hashlib').sha256(raw).hexdigest())
  self.assertEqual({p.name for p in self.live.iterdir()},{a.KEEP})
 def test_host_archive_without_newer_keep_snapshot_is_allowed(self):
  (self.host/a.KEEP).rename(self.host/'older-host-only-entry')
  plan=a.make_plan(self.host,a.scan(self.live))
  self.assertEqual(set(plan['trees']),set(a.TARGETS))
 def test_live_without_current_snapshot_remains_blocked(self):
  raw=self.planraw(); (self.live/a.KEEP).rename(self.live/'held-current')
  with self.assertRaises(ValueError): a.scan(self.live)
  with self.assertRaises(ValueError): a.apply(self.live,raw,__import__('hashlib').sha256(raw).hexdigest())
if __name__=='__main__': unittest.main()
