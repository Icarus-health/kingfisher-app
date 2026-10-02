"""Mac-Start: richtige Laufzeit wecken, ohne entfernte Kontexte umzuschalten."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

spec=importlib.util.spec_from_file_location('start_mac_app',Path(__file__).parents[2]/'scripts/start_mac_app.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_running_engine_needs_no_restart(monkeypatch):
    calls=[]
    def command(*args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='colima' if args[1:]==('context','show') else 'unix:///local/socket')
    monkeypatch.setattr(module,'command',command)
    module.ensure_engine('docker')
    assert calls==[('docker','context','show'),('docker','context','inspect','colima','--format','{{.Endpoints.docker.Host}}'),('docker','info')]


def test_stopped_colima_is_started_and_readiness_checked(monkeypatch):
    calls=[];checks=iter([1,1,0])
    def command(*args,**kwargs):
        calls.append(args)
        if args[1:]==('info',):return SimpleNamespace(returncode=next(checks),stdout='')
        return SimpleNamespace(returncode=0,stdout='colima' if args[1:]==('context','show') else 'unix:///local/socket')
    monkeypatch.setattr(module,'command',command)
    monkeypatch.setattr(module.shutil,'which',lambda name:'/local/'+name)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    module.ensure_engine('docker')
    assert calls.count(('/local/colima','start'))==1
    assert calls.count(('docker','info'))==3
    assert not any('use' in call for call in calls)


def test_remote_context_is_not_started(monkeypatch):
    calls=[]
    def command(*args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout='remote' if args[1:]==('context','show') else 'ssh://remote-host')
    monkeypatch.setattr(module,'command',command)
    with pytest.raises(ValueError,match='lokalen Docker-Kontext'):module.ensure_engine('docker')
    assert len(calls)==2


def test_wrong_app_address_does_not_touch_docker(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'ensure_engine',lambda _:pytest.fail('Darf nicht starten'))
    with pytest.raises(ValueError,match='lokale Adresse'):
        module.start('docker','app',tmp_path/'private.env','https://external.example')


def test_folder_job_requires_explicit_local_config(tmp_path):
    import json
    env = tmp_path / 'private.env'
    assert module.folder_jobs(env) == []
    folder = tmp_path / 'selected'
    folder.mkdir()
    env.with_suffix('.folder.json').write_text(json.dumps({'folder': str(folder)}))
    assert module.folder_jobs(env) == [('mac_folder_worker.py', ['--folder', str(folder)])]
    env.with_suffix('.folder.json').write_text(json.dumps({'folder': 'relative'}))
    with pytest.raises(ValueError):
        module.folder_jobs(env)


def test_native_start_prints_ready_url_without_opening_browser(tmp_path, monkeypatch, capsys):
    import sys
    commands = []
    monkeypatch.setattr(module, 'start', lambda *args: 'http://127.0.0.1:8891/today')
    monkeypatch.setattr(module, 'command', lambda *args: commands.append(args))
    monkeypatch.setattr(sys, 'argv', ['start_mac_app.py', '--container', 'pilot',
                                    '--env-file', str(tmp_path/'private.env'), '--no-browser'])
    module.main()
    assert commands == []
    assert capsys.readouterr().out.strip() == 'http://127.0.0.1:8891/today'


def test_browser_starter_remains_available(tmp_path, monkeypatch):
    import sys
    commands = []
    monkeypatch.setattr(module, 'start', lambda *args: 'http://127.0.0.1:8891/today')
    monkeypatch.setattr(module, 'command', lambda *args: commands.append(args))
    monkeypatch.setattr(sys, 'argv', ['start_mac_app.py', '--container', 'pilot',
                                    '--env-file', str(tmp_path/'private.env')])
    module.main()
    assert commands == [('open', 'http://127.0.0.1:8891/today')]


def test_transcript_helper_always_starts_but_needs_no_folder_choice_upfront():
    # Der Eingang für Mitschriften wartet auf die Wahl in der Oberfläche; ein Pfad steht nirgends im Start.
    assert module.transcript_jobs() == [("mac_folder_worker.py", ["--role", "transkripte"])]
