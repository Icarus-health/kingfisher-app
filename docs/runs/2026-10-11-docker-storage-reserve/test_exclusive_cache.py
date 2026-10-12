import runpy, unittest, json
old=runpy.run_path('/private/tmp/kingfisher-storage-reserve-20261011/test_archive_guards.py')
new=runpy.run_path('/private/tmp/kingfisher-storage-reserve-20261011/archive_exclusive_cache.py')
old['Archive'].test_good.__globals__['verify']=lambda path,refs:new['archive_verify'](path,set(refs.values()),set(refs))
branch=new['exclusive_branch'];ancestors=new['ancestors']
def mapping(*edges):return {w:{'Id':w,'Parent':parent} for w,parent in edges}
class GraphGuards(unittest.TestCase):
 def test_shared_base_preserved(self):
  m=mapping(('base',None),('selected','base'),('other','base'))
  self.assertEqual(branch({'selected'},{'other'},m),{'selected'})
 def test_exclusive_chain_only(self):
  m=mapping(('base',None),('middle','base'),('selected','middle'),('other','base'))
  self.assertEqual(branch({'selected'},{'other'},m),{'selected','middle'})
 def test_external_untagged_child_preserved(self):
  m=mapping(('base',None),('middle','base'),('selected','middle'),('foreign','middle'),('other','base'))
  self.assertEqual(branch({'selected'},{'other'},m),{'selected'})
 def test_used_selected_branch_excluded(self):
  m=mapping(('base',None),('selected','base'))
  self.assertEqual(branch({'selected'},{'selected'},m),set())
 def test_graph_cycles_do_not_hang(self):
  m=mapping(('a','b'),('b','a'))
  self.assertEqual(ancestors({'a'},m),{'a','b'})
class TaglessArchive(old['Archive']):
 def test_good_without_tag(self):
  def no_tag(entries,w):
   x=json.loads(entries['manifest.json']);x[0]['RepoTags']=None;entries['manifest.json']=json.dumps(x).encode()
  refs=old['fixture'](self.p,no_tag)
  new['archive_verify'](self.p,set(refs.values()),set())
if __name__=='__main__':
 suite=unittest.TestSuite()
 for cls in (GraphGuards,TaglessArchive,old['RemovalGuard']):suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
 r=unittest.TextTestRunner(verbosity=1).run(suite)
 raise SystemExit(0 if r.wasSuccessful() else 1)
