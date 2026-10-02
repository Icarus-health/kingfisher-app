"""Wiederöffnen und Schutz vorhandener Instanzen beim Mac-Restore."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

spec = importlib.util.spec_from_file_location('open_restored_app', Path(__file__).parents[2]/'scripts/open_restored_app.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_existing_foreign_container_is_never_started(tmp_path, monkeypatch):
    (tmp_path/'app.json').write_text(json.dumps({'container':'original', 'owner':'ours', 'port':8891}))
    calls=[]
    def run(*args):
        calls.append(args)
        return json.dumps([{'Config':{'Labels':{'kingfisher.restore':'someone-else'}}}])
    monkeypatch.setattr(module,'run',run)
    with pytest.raises(ValueError): module.start('docker',tmp_path,'image')
    assert calls == [('docker','inspect','original')]


def test_reopen_uses_existing_inspection_volume_and_address(tmp_path, monkeypatch):
    (tmp_path/'app.json').write_text(json.dumps({'container':'restored', 'owner':'ours', 'port':8893}))
    calls=[]
    image = 'sha256:' + 'a' * 64
    def run(*args):
        calls.append(args)
        if args[1] == 'inspect':
            return json.dumps([{'Config':{'Labels':{'kingfisher.restore':'ours', 'kingfisher.restore-boundary':'1'},
                'Env':['ICARUS_RESTORE_INSPECTION=1']}, 'Image': image}])
        if args[1] == 'image': return image
        if args[1] == 'run': return '1'
        return ''
    monkeypatch.setattr(module,'run',run)
    monkeypatch.setattr(module,'urlopen',lambda *a,**k: open(tmp_path/'app.json'))
    assert module.start('docker',tmp_path,'image')=='http://127.0.0.1:8893'
    assert calls[-1] == ('docker','start','restored')
    assert not any(c[1] in {'create','volume'} for c in calls)


def test_failed_copy_preserves_original_and_removes_only_new_volume(tmp_path, monkeypatch):
    (tmp_path/'data').mkdir();(tmp_path/'data'/'precious').write_text('original')
    (tmp_path/'settings.env').write_text('private')
    calls=[]
    def run(*args):
        calls.append(args)
        if args[1]=='image': return 'sha256:' + 'a'*64
        if args[1]=='run' and 'CAPABILITY' in args[-1]: return '1'
        if args[1]=='run': raise subprocess.CalledProcessError(1,['docker'])
        return ''
    monkeypatch.setattr(module,'run',run)
    with pytest.raises(subprocess.CalledProcessError):module.start('docker',tmp_path,'image')
    assert calls[-1][1:3]==('volume','rm')
    assert calls[-1][-1]==next(c[-1] for c in calls if c[1:3] == ('volume','create'))
    assert (tmp_path/'data'/'precious').read_text()=='original'
    assert not (tmp_path/'app.json').exists()
    assert not any(c[1]=='start' for c in calls)


def test_parallel_open_does_not_create_another_app(tmp_path, monkeypatch):
    import fcntl
    with (tmp_path/'app.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        monkeypatch.setattr(module,'run',lambda *args: pytest.fail('Docker darf nicht angesprochen werden'))
        with pytest.raises(ValueError,match='bereits geöffnet'):
            module.start('docker',tmp_path,'image')


def test_old_owned_container_cannot_resume_without_inspection_boundary(tmp_path, monkeypatch):
    (tmp_path/'app.json').write_text(json.dumps({'container':'restored', 'owner':'ours', 'port':8893}))
    calls=[]
    def run(*args):
        calls.append(args)
        return json.dumps([{'Config':{'Labels':{'kingfisher.restore':'ours'}}, 'Image':'sha256:'+'a'*64}])
    monkeypatch.setattr(module,'run',run)
    monkeypatch.setattr(module,'urlopen',lambda *a,**k: open(tmp_path/'app.json'))
    with pytest.raises(ValueError, match='Prüfmodus'):
        module.start('docker',tmp_path,'image')
    assert not any(c[1] == 'start' for c in calls)
