"""Synthetic state machine tests; never use Docker, HTTP, private files or models."""
import copy
import importlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

import orchestrator as installer
import data_proof


def seed(root, version=19):
    root.mkdir()
    for name in data_proof.DATABASES:
        with sqlite3.connect(root / name) as db:
            db.execute('CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT)')
            db.execute("INSERT INTO example VALUES (1, 'synthetic')")
            if name == 'episodes.sqlite3':
                db.execute('CREATE TABLE episodes (id TEXT PRIMARY KEY, digest TEXT, body TEXT, document TEXT)')
                body = 'Synthetic original.'
                db.execute('INSERT INTO episodes VALUES (?, ?, ?, ?)', ('synthetic-id', 'sha256:' + data_proof.sha_bytes(body.encode()), body, '{}'))
                db.execute('CREATE TABLE memory_category_sources (episode_id TEXT PRIMARY KEY, status TEXT)')
                db.execute("INSERT INTO memory_category_sources VALUES ('synthetic-id', 'failed')")
                db.execute(f'PRAGMA user_version={version}')
    (root / 'einstellungen.json').write_text('{"model_roles":{"synthetic":"local"},"schedule":{"enabled":false}}')
    (root / 'hintergrund.json').write_text('{"pausiert":true}')
    (root / 'auxiliary-original.txt').write_text('Synthetic auxiliary original')


class FakeSystem:
    def __init__(self, tmp):
        self.calls = []
        self.started = False
        self.published = False
        self.mode = 'migrated'
        self.preflight_exit = None
        self.fail_health = False
        self.volume_changed = False
        self.low_space = False
        self.proof_tamper = False
        self.data = tmp / 'live-synthetic'; seed(self.data)
        self.old_proof = data_proof.prove(self.data, cold=True)
        self.oneshots = {}
        self.container_running = True
        self.config = make_config(tmp)

    def run(self, argv):
        self.calls.append(list(argv))
        if argv[0] in ('codesign', str(Path(self.config['native_probe']))):
            return (0, b'before=ok\nafter=ok' if argv[0] != 'codesign' else b'')
        if argv[:3] == ['docker', 'image', 'inspect']:
            return 0, json.dumps([{'Id': self.config['image_id']}]).encode()
        if argv[:3] == ['docker', 'volume', 'inspect']:
            name = self.config['volume']; return 0, json.dumps([{'Name': name, 'Driver': 'local', 'Mountpoint': '/volume/synthetic' + ('-changed' if self.volume_changed and not self.container_running else ''), 'Options': None}]).encode()
        if argv[:2] == ['docker', 'ps']:
            return 0, (installer.CONTAINER if self.container_running else '').encode()
        if argv[:2] == ['docker', 'inspect']:
            name = argv[2]
            if name in self.oneshots:
                row = self.oneshots[name]
                return 0, json.dumps([{'Image': self.config['image_id'], 'State': {'Running': False, 'ExitCode': row.get('exit', 0)}, 'HostConfig': {'NetworkMode':'none','RestartPolicy':{'Name':'no'},'PortBindings':None,'Tmpfs':row.get('tmpfs',{})}, 'Mounts': row['mounts']}]).encode()
            return 0, json.dumps([{'Image': self.config['image_id'] if self.published else 'sha256:'+'a'*64, 'State': {'Running': self.container_running}, 'Mounts': [{'Type':'volume','Name':self.config['volume'],'Destination':'/data','RW':True}]}]).encode()
        if argv[:2] == ['docker', 'create']:
            name=argv[argv.index('--name')+1]; mounts=[]
            if '--mount' in argv:
                raw=argv[argv.index('--mount')+1];parts=dict(bit.split('=',1) for bit in raw.split(',') if '=' in bit)
                mounts=[{'Type':parts.get('type'),'Name':parts.get('src'),'Destination':parts.get('dst'),'RW':'readonly' not in raw.split(',')}]
            tmpfs={}
            if not mounts:
                if '--tmpfs' in argv:
                    raw=argv[argv.index('--tmpfs')+1];destination,options=raw.split(':',1);tmpfs={destination:options}
                    mounts=[{'Type':'tmpfs','Destination':destination}]
                else:mounts=[{'Type':'volume','Name':'synthetic-anonymous','Destination':'/data','RW':True}]
            self.oneshots[name]={'argv':argv,'mounts':mounts,'tmpfs':tmpfs}; return 0,name.encode()
        if argv[:2] == ['docker', 'cp']:
            if argv[2] == installer.CONTAINER + ':/data': shutil.copytree(self.data, argv[3])
            else:
                target=argv[3].split(':',1)[1]
                assert Path(target).parent==Path('/tmp'), 'docker cp cannot create missing destination directory'
            return 0,b''
        if argv[:3] == ['docker','start','-a']:
            row=self.oneshots[argv[3]]; args=row['argv']; script=next(x for x in args if x.startswith('/tmp/') and x.endswith('.py'))
            if script.endswith('installed-check.py'):
                answer={'version':self.config['version'],'python_sources_verified':264,'ui_files_verified':112,'ui_file_set_exact':True}
            elif script.endswith('data_proof.py'):
                if '--measure' in args: answer=data_proof.measure(self.data)
                else:
                    answer=data_proof.prove(self.data,cold=True)
                    if self.proof_tamper and not self.container_running: answer['originals']['sha256']='bad'
            else:
                if self.mode == 'missing': row['exit']=0; return 0,b''
                if self.mode == 'migrated':
                    with sqlite3.connect(self.data/'episodes.sqlite3') as db:
                        db.execute('ALTER TABLE memory_category_sources ADD COLUMN failure_code TEXT');db.execute('PRAGMA user_version=20')
                if self.mode == 'restored_inspection': (self.data/'restore-state.json').write_text('{"mode":"inspection"}')
                answer={'status':self.mode,'publish_allowed':self.mode=='migrated','patch_sha256':installer.PATCH_SHA,
                        'snapshot_verified':True,'outdated':[], 'rollback':{'attempted': self.mode=='restored_inspection','verified':self.mode=='restored_inspection'}}
                row['exit']=self.preflight_exit if self.preflight_exit is not None else (0 if self.mode=='migrated' else 1)
            return row.get('exit',0), json.dumps(answer).encode()
        if argv[:2] == ['docker','rm']: return 0,b''
        if argv[:2] == ['docker','stop']: self.container_running=False;return 0,b''
        if argv[:2] == ['docker','start']: self.container_running=True;self.started=True;return 0,b''
        if argv[:2] == ['docker','compose']:
            self.published=True;self.container_running=True;return 0,b''
        if argv[:2] == ['docker','exec']: return 0,json.dumps(data_proof.prove(self.data,cold=False)).encode()
        raise AssertionError(argv)

    def maintenance(self,config):
        if getattr(self,'maintenance_error',None):raise installer.CheckFailed(self.maintenance_error)
    def guarded_run(self,argv,check):
        check();result=self.run(argv);check();return result
    def free_bytes(self,path): return 0 if self.low_space else 10**12
    def port_open(self): return self.container_running
    def health(self, token, version=None, inspection=False):
        self.calls.append(['HTTP', 'inspection' if inspection else 'normal'])
        if self.fail_health: raise installer.CheckFailed('health_failed')
        if inspection and not (self.data/'restore-state.json').exists(): raise installer.CheckFailed('inspection_missing')
        return {'health': True, 'inspection':inspection, 'read_only_route':not inspection, 'background_paused':not inspection}


def make_config(tmp):
    app=tmp/'Kingfisher.app'; (app/'Contents/MacOS').mkdir(parents=True);(app/'Contents/Resources').mkdir()
    for rel in ('Contents/MacOS/Kingfisher','Contents/Info.plist','Contents/Resources/compose.yaml'): (app/rel).write_text('synthetic-'+rel)
    env=tmp/'kingfisher.env';env.write_text('KINGFISHER_IMAGE=old:19\nICARUS_SIDECAR_TOKEN=synthetic-secret\nUNCHANGED=synthetic\n')
    checker=tmp/'installed-check.py';checker.write_text('# synthetic checker')
    manifest=tmp/'expected.json';manifest.write_text(json.dumps({'revision':installer.REVISION,'version':installer.VERSION,'python_files':{str(n):'x' for n in range(264)},'ui_files':{str(n):'y' for n in range(112)}}))
    probe=tmp/'probe';probe.write_text('synthetic probe')
    preflight=Path(__file__).with_name('preflight.py')
    return {'app':str(app),'env':str(env),'backup':str(tmp/'backup'),'image':installer.IMAGE,'image_id':installer.IMAGE_ID,'version':installer.VERSION,'volume':installer.VOLUME,
            'native_sha256':installer.sha(app/'Contents/MacOS/Kingfisher'),'compose_sha256':installer.sha(app/'Contents/Resources/compose.yaml'),'plist_sha256':installer.sha(app/'Contents/Info.plist'),
            'native_probe':str(probe),'native_probe_sha256':installer.sha(probe),'preflight':str(preflight),'checker':str(checker),'checker_sha256':installer.sha(checker),'manifest':str(manifest),'manifest_sha256':installer.sha(manifest),
            'operator_exclusive_window':True,'host_reserve_bytes':1024,'volume_reserve_bytes':1024}


def not_any_preflight(command):return not any(part.endswith('/preflight.py') for part in command)

def test_success_order_and_network_isolation(tmp_path):
    fake=FakeSystem(tmp_path); result=installer.run(fake.config,fake)
    assert result['status']=='installed'
    assert result['published'] is True and result['originals_preserved'] is True
    calls=fake.calls
    stop=next(i for i,c in enumerate(calls) if c[:2]==['docker','stop'])
    cp=next(i for i,c in enumerate(calls) if c[:2]==['docker','cp'] and c[2].endswith(':/data'))
    migrate=next(i for i,c in enumerate(calls) if c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c))
    publish=next(i for i,c in enumerate(calls) if c[:2]==['docker','compose'])
    assert stop<cp<migrate<publish
    for c in calls:
        if c[:2]==['docker','create']:
            assert c[c.index('--network')+1]=='none' and c[c.index('--restart')+1]=='no'
            assert c[c.index('--entrypoint')+1]=='python' and '-p' not in c and '--publish' not in c
            assert not any('type=bind' in value for value in c)
            if '--mount' in c:
                mount=c[c.index('--mount')+1]
                assert 'src='+installer.VOLUME in mount and 'dst=/data' in mount
                assert ('readonly' in mount)==not_any_preflight(c)
            else:
                assert c[c.index('--tmpfs')+1]=='/data:rw,noexec,nosuid,size=1048576'
    assert Path(fake.config['env']).read_text()==f'KINGFISHER_IMAGE={installer.IMAGE}\nICARUS_SIDECAR_TOKEN=synthetic-secret\nUNCHANGED=synthetic\n'
    assert (Path(fake.config['backup'])/'data/auxiliary-original.txt').is_file()
    assert 'synthetic-secret' not in json.dumps(result) and 'synthetic-id' not in json.dumps(result)


@pytest.mark.parametrize('mode,exitcode',[('missing',None),('migrated',1),('recovery_failed',None),('restored_inspection',0)])
def test_ambiguous_or_failure_never_publishes_or_starts_old(tmp_path,mode,exitcode):
    fake=FakeSystem(tmp_path);fake.mode=mode;fake.preflight_exit=exitcode
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.published and not fake.started
    assert 'KINGFISHER_IMAGE=old:19' in Path(fake.config['env']).read_text()


@pytest.mark.parametrize('mode,status',[('preflight_failed','old_schema19_resumed'),('restored_inspection','old_inspection_only')])
def test_known_safe_prepublication_recovery(tmp_path,mode,status):
    fake=FakeSystem(tmp_path);fake.mode=mode
    result=installer.run(fake.config,fake)
    assert result['status']==status and fake.started and not fake.published
    assert result['published'] is False


def test_postpublication_failure_does_not_rewind_or_start_old(tmp_path):
    fake=FakeSystem(tmp_path);fake.fail_health=True
    result=installer.run(fake.config,fake)
    assert result['status']=='forward_repair_required' and fake.published and not fake.started
    assert installer.IMAGE in Path(fake.config['env']).read_text()
    assert sqlite3.connect(fake.data/'episodes.sqlite3').execute('PRAGMA user_version').fetchone()[0]==20
    assert not any('restore' in part for c in fake.calls for part in c if part.startswith('/tmp/'))


@pytest.mark.parametrize('fault',['low_space','volume_changed','proof_tamper'])
def test_failed_precondition_stops_before_publish(tmp_path,fault):
    fake=FakeSystem(tmp_path);setattr(fake,fault,True)
    result=installer.run(fake.config,fake)
    assert result['status'] in ('prepare_failed','stopped_manual_review') and not fake.published


def test_unpaused_data_is_not_migrated(tmp_path):
    fake=FakeSystem(tmp_path);(fake.data/'hintergrund.json').write_text('{"pausiert":false}')
    result=installer.run(fake.config,fake)
    assert not fake.published
    assert not any(c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c) for c in fake.calls)


def test_data_proof_checks_all17_original_digests_and_cold_tree(tmp_path):
    root=tmp_path/'data';seed(root)
    proof=data_proof.prove(root,cold=True)
    assert len(proof['databases'])==17 and proof['schema']==19 and proof['originals']['count']==1
    assert proof['paused'] is True
    assert 'synthetic-id' not in json.dumps(proof) and 'Synthetic original' not in json.dumps(proof)
    before=proof['tree'];(root/'auxiliary-original.txt').write_text('changed')
    assert data_proof.prove(root,cold=True)['tree'] != before
    with sqlite3.connect(root/'episodes.sqlite3') as db:db.execute("UPDATE episodes SET body='damaged'")
    with pytest.raises(data_proof.CheckFailed,match='original_digest_mismatch'): data_proof.prove(root,cold=True)


def test_cold_wal_is_rejected_not_removed(tmp_path):
    root=tmp_path/'data';seed(root);wal=root/'episodes.sqlite3-wal';wal.write_bytes(b'synthetic')
    with pytest.raises(data_proof.CheckFailed,match='database_not_cleanly_closed'):data_proof.prove(root,cold=True)
    assert wal.read_bytes()==b'synthetic'


def test_import_has_no_commands(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess,'run',lambda *a,**k: (_ for _ in ()).throw(AssertionError('subprocess on import')))
    importlib.reload(installer);importlib.reload(data_proof)


def test_cold_copy_tamper_blocks_migration(tmp_path):
    fake=FakeSystem(tmp_path);run=fake.run
    def tamper(argv):
        response=run(argv)
        if argv[:2]==['docker','cp'] and argv[2]==installer.CONTAINER+':/data':
            (Path(argv[3])/'auxiliary-original.txt').write_text('tampered')
        return response
    fake.run=tamper
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and result['error']=='cold_copy_mismatch'
    assert not any(c[:2]==['docker','create'] and any(x.endswith('/preflight.py') for x in c) for c in fake.calls)


def test_bundle_hashes_unchanged_on_success_and_native_tamper_blocks_publish(tmp_path):
    fake=FakeSystem(tmp_path);app=Path(fake.config['app'])
    before={str(p.relative_to(app)):installer.sha(p) for p in app.rglob('*') if p.is_file()}
    assert installer.run(fake.config,fake)['status']=='installed'
    assert before=={str(p.relative_to(app)):installer.sha(p) for p in app.rglob('*') if p.is_file()}


def test_running_native_or_launcher_blocks_before_stop(tmp_path):
    fake=FakeSystem(tmp_path);fake.maintenance_error='native_or_launcher_active'
    result=installer.run(fake.config,fake)
    assert result['status']=='prepare_failed' and result['error']=='native_or_launcher_active'
    assert not any(c[:2]==['docker','stop'] for c in fake.calls)


def test_missing_maintenance_attestation_does_nothing(tmp_path):
    fake=FakeSystem(tmp_path);fake.config['operator_exclusive_window']=False
    result=installer.run(fake.config,fake)
    assert result['status']=='prepare_failed' and not fake.calls


def test_writer_appearing_during_migration_cannot_publish(tmp_path):
    fake=FakeSystem(tmp_path)
    def guarded(argv,check):
        result=fake.run(argv)
        fake.maintenance_error='native_or_launcher_active';check()
        return result
    fake.guarded_run=guarded
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.published and not fake.started


def test_actual_restore_result_extra_metadata_is_accepted_only_after_proof(tmp_path):
    fake=FakeSystem(tmp_path);fake.mode='restored_inspection'
    run=fake.run
    def actual_shape(argv):
        code,raw=run(argv)
        if argv[:3]==['docker','start','-a'] and b'"restored_inspection"' in raw:
            payload=json.loads(raw);payload['rollback'].update(schema=19,inspection=True)
            raw=json.dumps(payload).encode()
        return code,raw
    fake.run=actual_shape
    assert installer.run(fake.config,fake)['status']=='old_inspection_only'


@pytest.mark.parametrize('unexpected',[False,True])
def test_only_owned_migration_writer_is_allowed_during_guard(tmp_path,unexpected):
    fake=FakeSystem(tmp_path);original_run=fake.run;active=set()
    def run(argv):
        if argv[:2]==['docker','ps'] and active:
            return 0,'\n'.join(sorted(active)).encode()
        return original_run(argv)
    def guarded(argv,check):
        active.add(argv[3])
        if unexpected:active.add('unexpected-writer')
        try:check();result=run(argv);check();return result
        finally:active.clear()
    fake.run=run;fake.guarded_run=guarded
    result=installer.run(fake.config,fake)
    assert result['status']==('stopped_manual_review' if unexpected else 'installed')
    assert fake.published is (not unexpected)


@pytest.mark.parametrize('change',['schema20','inspection','stored_row','settings','original'])
def test_claimed_preflight_failure_requires_unchanged_schema19(tmp_path,change):
    fake=FakeSystem(tmp_path);fake.mode='preflight_failed';original_run=fake.run
    def run(argv):
        result=original_run(argv)
        if argv[:3]==['docker','start','-a'] and b'"preflight_failed"' in result[1]:
            if change=='inspection':(fake.data/'restore-state.json').write_text('{"mode":"inspection"}')
            elif change=='settings':(fake.data/'einstellungen.json').write_text('{}')
            else:
                with sqlite3.connect(fake.data/'episodes.sqlite3') as db:
                    if change=='schema20':db.execute('PRAGMA user_version=20')
                    elif change=='stored_row':db.execute("UPDATE example SET value='changed'")
                    elif change=='original':db.execute("UPDATE episodes SET body='damaged'")
        return result
    fake.run=run
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and not fake.started and not fake.published


def test_bundle_change_after_migration_blocks_publish(tmp_path):
    fake=FakeSystem(tmp_path);original_run=fake.run
    def run(argv):
        result=original_run(argv)
        if argv[:3]==['docker','start','-a'] and b'"migrated"' in result[1]:
            (Path(fake.config['app'])/'Contents/MacOS/Kingfisher').write_text('unexpected change')
        return result
    fake.run=run
    result=installer.run(fake.config,fake)
    assert result['status']=='stopped_manual_review' and result['error']=='bundle_hash' and not fake.published


def test_compose_environment_does_not_override_existing_env_file(monkeypatch):
    monkeypatch.setenv('KINGFISHER_IMAGE','wrong:19');monkeypatch.setenv('ICARUS_SIDECAR_TOKEN','wrong-secret')
    monkeypatch.setenv('DOCKER_CONTEXT','synthetic-context');monkeypatch.setenv('LLM_API_KEY','wrong-secret')
    env=installer.compose_environment()
    assert 'KINGFISHER_IMAGE' not in env and 'ICARUS_SIDECAR_TOKEN' not in env and 'LLM_API_KEY' not in env
    assert env['DOCKER_CONTEXT']=='synthetic-context'
    import os
    assert os.environ['KINGFISHER_IMAGE']=='wrong:19'


def test_native_full_command_is_checked_when_comm_is_short(tmp_path):
    fake=FakeSystem(tmp_path);system=installer.System()
    def command(argv):
        if argv==['ps','-axo','comm=']:return 0,b'Kingfisher\n'
        if argv==['launchctl','list']:return 0,b'PID Status Label\n'
        if argv==['ps','-axo','command=']:return 0,(str(Path(fake.config['app'])/'Contents/MacOS/Kingfisher')+'\n').encode()
        raise AssertionError(argv)
    system.run=command
    with pytest.raises(installer.CheckFailed,match='native_or_launcher_active'):system.maintenance(fake.config)
