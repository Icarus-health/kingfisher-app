from pathlib import Path
from types import SimpleNamespace
import ast, tempfile, shutil, subprocess, hashlib, json, os
source=Path('/private/tmp/kingfisher-header-package-f858681/install.py').read_text()
tree=ast.parse(source)
stage_index=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='stage' for t in n.targets))
staging=compile(ast.Module(body=tree.body[stage_index:stage_index+2],type_ignores=[]),'<actual staging>','exec')
recovery=compile(ast.Module(body=[next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='rollback_code_without_restarting_data')],type_ignores=[]),'<actual recovery>','exec')
def hashes(bundle):return {str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
with tempfile.TemporaryDirectory(prefix='kingfisher-recovery-proof-') as directory:
 base=Path(directory)
 for case in ('signature-failure','partial-copy','hash-mismatch','success'):
  root=base/case;root.mkdir();app=root/'installed.app';app.mkdir();candidate=root/'build/mac-app/Kingfisher.app';candidate.mkdir(parents=True);(candidate/'payload').write_text('synthetic new app')
  def copy(src,dst,**kwargs):
   result=shutil.copytree(src,dst,**kwargs)
   if case=='partial-copy':raise OSError('synthetic interrupted copy')
   return result
  def sign(*args,**kwargs):
   if case=='signature-failure':raise subprocess.CalledProcessError(1,args[0])
  files=hashes(candidate) if case!='hash-mismatch' else {'payload':'different'}
  namespace={'Path':Path,'tempfile':tempfile,'app':app,'root':root,'shutil':SimpleNamespace(copytree=copy,copy2=shutil.copy2,rmtree=shutil.rmtree),'subprocess':SimpleNamespace(run=sign),'contents_hashes':hashes,'manifest':{'files':files}}
  failed=False
  try:exec(staging,namespace)
  except (OSError,subprocess.CalledProcessError,AssertionError):failed=True
  stages=list(root.glob('.Kingfisher-update-*.app'))
  if case=='success':assert not failed and len(stages)==1;shutil.rmtree(stages[0])
  else:assert failed and stages==[],case
 for case in ('existing','absent','docker-unavailable'):
  root=base/('rollback-'+case);root.mkdir();app=root/'installed.app';(app/'Contents').mkdir(parents=True);(app/'Contents/payload').write_text('new app');folder=root/'backup';folder.mkdir();moved=folder/'old-native-Contents';moved.mkdir();(moved/'payload').write_text('old app');config=root/'env';config.write_bytes(b'new selector');original=b'old selector';data=root/'private-volume';data.write_bytes(b'new writes must survive');calls=[]
  def docker(*args):
   calls.append(args)
   if args[0]=='ps':
    if case=='docker-unavailable':raise subprocess.CalledProcessError(1,['docker'])
    return 'kingfisher-kingfisher-1\n' if case=='existing' else ''
   assert args==('stop','kingfisher-kingfisher-1');return ''
  ns={'docker':docker,'container':'kingfisher-kingfisher-1','folder':folder,'app':app,'moved':moved,'atomic_env':lambda value:config.write_bytes(value),'original':original,'contents_hashes':hashes,'old_hashes':{'Contents/payload':hashlib.sha256(b'old app').hexdigest()},'os':os,'json':json}
  exec(recovery,ns)
  if case=='docker-unavailable':
   try:ns['rollback_code_without_restarting_data']()
   except subprocess.CalledProcessError:pass
   else:raise AssertionError('unknown Docker state must fail closed')
   assert (app/'Contents/payload').read_text()=='new app' and config.read_bytes()==b'new selector' and moved.exists()
  else:
   ns['rollback_code_without_restarting_data']();assert (app/'Contents/payload').read_text()=='old app' and config.read_bytes()==original
   assert (folder/'failed-new-Contents/payload').read_text()=='new app'
   assert len([call for call in calls if call[0]=='stop'])==(1 if case=='existing' else 0)
   assert json.loads((folder/'update-recovery-required.json').read_text())['automatic_data_restore'] is False
  assert data.read_bytes()==b'new writes must survive'
proof={'actual_installer_ast_exercised':True,'staging_cases':4,'rollback_cases':3,'signature_copy_hash_failures_remove_only_owned_stage':True,'confirmed_absent_container_restores_code_without_stop':True,'unknown_docker_state_fails_closed':True,'new_data_writes_preserved':True,'productive_app_or_volume_accessed':False}
Path('/private/tmp/kingfisher-header-package-f858681/recovery-failure-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
