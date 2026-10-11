import ast,os
from pathlib import Path
from types import SimpleNamespace
s=Path(__file__).with_name('install.py').read_text();tree=ast.parse(s)
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('compose_environment','compose_up','verify_runtime_configuration')]
ns={'os':SimpleNamespace(environ={'ICARUS_PROVIDER':'synthetic-unwanted','LLM_API_KEY':'synthetic-unwanted','KINGFISHER_IMAGE':'synthetic-unwanted','PATH':'safe-runtime-path','HOME':'synthetic-home','DOCKER_HOST':'synthetic-socket'}),'D':'synthetic-docker','app':Path('/synthetic/app'),'config':Path('/synthetic/config')}
calls=[];ns['subprocess']=SimpleNamespace(run=lambda *a,**kw:calls.append((a,kw)))
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual installer env>','exec'),ns)
ns['compose_up']()
env=calls[0][1].get('env')
assert env is not None, 'Compose inherits ambient provider overrides'
assert env=={'PATH':'safe-runtime-path','HOME':'synthetic-home','DOCKER_HOST':'synthetic-socket'}
assert 'verify_runtime_configuration' in ns, 'Missing post-start configuration check'
verify=ns['verify_runtime_configuration'];old=['ICARUS_PROVIDER=local','LLM_API_KEY=','KINGFISHER_FASSUNG=old','PATH=internal']
new=['ICARUS_PROVIDER=local','LLM_API_KEY=','KINGFISHER_FASSUNG=new','PATH=internal']
verify(old,new)
for bad in (new+['ICARUS_MODEL=changed'],['ICARUS_PROVIDER=cloud','LLM_API_KEY=','KINGFISHER_FASSUNG=new'],['ICARUS_PROVIDER=local','LLM_API_KEY=changed','KINGFISHER_FASSUNG=new']):
 try:verify(old,bad)
 except AssertionError:pass
 else:raise AssertionError('Unexpected runtime configuration accepted')
print('Compose shell override exclusion and post-start config counterexamples passed')
