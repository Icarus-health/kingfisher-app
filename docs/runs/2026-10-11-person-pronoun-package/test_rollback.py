"""Behavior of the actual installer failure function, entirely synthetic."""
import ast, json, os, tempfile, hashlib
from pathlib import Path
source = Path(__file__).with_name('install.py').read_text()
tree = ast.parse(source)
names = {'atomic_env', 'rollback_code_without_restarting_data'}
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(functions) == 2
imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory); app = root/'App'; folder = root/'backup'
    app.mkdir(); folder.mkdir(); (app/'Contents').mkdir()
    (app/'Contents'/'new').write_text('new executable')
    moved = folder/'old-native-Contents'; moved.mkdir(); (moved/'old').write_text('old executable')
    config = root/'config'; original = b'old image'; config.write_bytes(b'new image')
    volume = root/'data'; volume.mkdir(); (volume/'new-user-data').write_text('keep this new write')
    def hashes(bundle):
        return {str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
    old_hashes = {'Contents/old':hashlib.sha256(b'old executable').hexdigest()}
    calls = []
    def docker(*args): calls.append(args)
    def no_restart(): raise AssertionError('old runtime must not restart on unverified data')
    namespace = dict(app=app, folder=folder, moved=moved, config=config, original=original,
                     old_hashes=old_hashes, contents_hashes=hashes, container='synthetic-container',
                     docker=docker, compose_up=no_restart, healthy=no_restart)
    exec(compile(ast.Module(body=imports+functions,type_ignores=[]), '<actual-installer-rollback>', 'exec'),namespace)
    namespace['rollback_code_without_restarting_data']()
    assert calls == [('stop','synthetic-container')]
    assert config.read_bytes() == original and config.stat().st_mode & 0o777 == 0o600
    assert hashes(app) == old_hashes
    assert (folder/'failed-new-Contents'/'new').read_text() == 'new executable'
    assert (volume/'new-user-data').read_text() == 'keep this new write'
    marker = folder/'update-recovery-required.json'
    assert json.loads(marker.read_text())['data_volume_not_overwritten'] is True
    assert marker.stat().st_mode & 0o777 == 0o600
    # Stopping failure must stop before replacing code/config; no attempted restart.
    def stop_fails(*args): raise OSError('synthetic stop failure')
    namespace['docker'] = stop_fails
    try: namespace['rollback_code_without_restarting_data']()
    except OSError: pass
    else: raise AssertionError('stop failure not propagated')
    assert config.read_bytes() == original and hashes(app) == old_hashes
print('Actual rollback: stops backend, restores code/config, preserves new data, never starts old runtime; stop failure propagates')

# The real top-level handler must recover even if interruption arrives after
# rename completes but before any Python transition flag can be assigned.
transition = next(n for n in tree.body if isinstance(n, ast.Try))
for interrupt_after_rename in (True, False):
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);app=root/'App';folder=root/'backup';stage=root/'Stage'
        (app/'Contents').mkdir(parents=True);folder.mkdir();(stage/'Contents').mkdir(parents=True)
        (app/'Contents'/'old').write_text('old executable');(stage/'Contents'/'new').write_text('new executable')
        moved=folder/'old-native-Contents';config=root/'config';original=b'old image';config.write_bytes(original)
        old_hashes=hashes(app);calls=[]
        class InterruptingOS:
            armed=True
            def __getattr__(self,name):return getattr(os,name)
            def replace(self,src,dst):
                if self.armed and Path(src)==app/'Contents' and Path(dst)==moved:
                    self.armed=False
                    if interrupt_after_rename:os.replace(src,dst)
                    raise KeyboardInterrupt('synthetic interrupted move')
                return os.replace(src,dst)
        namespace=dict(app=app,folder=folder,moved=moved,stage=stage,config=config,original=original,
                       old_hashes=old_hashes,contents_hashes=hashes,container='synthetic-container',
                       docker=lambda *args:calls.append(args),compose_up=no_restart,healthy=no_restart,
                       changed=False)
        exec(compile(ast.Module(body=imports+functions,type_ignores=[]),'<actual-installer-rollback>','exec'),namespace)
        namespace['os']=InterruptingOS()
        try:exec(compile(ast.Module(body=[transition],type_ignores=[]),'<actual-installer-transition>','exec'),namespace)
        except KeyboardInterrupt:pass
        else:raise AssertionError('interrupt not propagated')
        assert hashes(app)==old_hashes,'Interruption left installed Contents missing'
        assert config.read_bytes()==original
        assert calls==([('stop','synthetic-container')] if interrupt_after_rename else [])
        assert (stage/'Contents'/'new').read_text()=='new executable'
print('Actual transition handler: interrupts immediately before/after old-Contents rename preserve old app/config and staged new app')
