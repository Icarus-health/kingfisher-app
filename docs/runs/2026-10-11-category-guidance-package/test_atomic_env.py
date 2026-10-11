import ast,os,tempfile,sys
from pathlib import Path
source=Path(sys.argv[1] if len(sys.argv)>1 else '/private/tmp/kingfisher-guidance-install-20261011.py').read_text()
tree=ast.parse(source)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='atomic_env')
imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
with tempfile.TemporaryDirectory() as d:
 config=Path(d)/'cfg.env';config.write_bytes(b'original')
 namespace={'config':config}
 exec(compile(ast.Module(body=imports+[node],type_ignores=[]),'<atomic-env>','exec'),namespace)
 original_replace=os.replace
 def fail_once(src,dst):raise OSError('synthetic replace failure')
 os.replace=fail_once
 try:
  try:namespace['atomic_env'](b'candidate')
  except OSError:pass
  else:raise AssertionError('failure not propagated')
 finally:os.replace=original_replace
 assert config.read_bytes()==b'original'
 assert list(Path(d).iterdir())==[config]
 namespace['atomic_env'](b'restored')
 assert config.read_bytes()==b'restored'
 assert config.stat().st_mode & 0o777==0o600
 assert list(Path(d).iterdir())==[config]
print('Failed replace cleans temp; immediate recovery succeeds with 0600')
