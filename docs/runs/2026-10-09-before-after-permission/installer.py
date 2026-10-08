from pathlib import Path
import subprocess, shutil, os, json, sqlite3, plistlib, hashlib, time
import httpx
from icarus_memory.episodes import digest_of

import sys
REVISION=sys.argv[1]
assert len(REVISION)==7 and all(c in '0123456789abcdef' for c in REVISION)
VERSION='1.0.6-local.'+REVISION
IMAGE='ghcr.io/icarus-health/kingfisher-app:'+VERSION
APP=Path('/Users/sorenkube/Applications/Kingfisher.app')
ENV=Path('/Users/sorenkube/Library/Application Support/Kingfisher/kingfisher.env')
BACKUP=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Rueckweg')/('2026-10-09-vor-'+REVISION+'-geprueft')
PREPARED=APP.with_name('Kingfisher-neu-'+REVISION+'.app')
CONTAINER='kingfisher-kingfisher-1'

def command(*args):
    return subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout

def compose(*args):
    return command('docker','compose','-p','kingfisher','--env-file',str(ENV),'-f',str(APP/'Contents/Resources/compose.yaml'),*args)

def root_data_check(data):
    checks=[]
    for f in data.iterdir():
        if f.is_file():
            with f.open('rb') as stream: header=stream.read(16)
            if header==b'SQLite format 3\x00':
                c=sqlite3.connect(f.as_uri()+'?mode=ro',uri=True)
                assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)],f.name
                checks.append(f.name);c.close()
    c=sqlite3.connect((data/'episodes.sqlite3').as_uri()+'?mode=ro',uri=True)
    rows=c.execute('SELECT id,digest,body FROM episodes').fetchall();c.close()
    assert all(digest_of(body)==digest for _,digest,body in rows)
    return checks,{i:d for i,d,_ in rows}

assert not BACKUP.exists() and not PREPARED.exists()
image_id=command('docker','image','inspect',IMAGE,'--format','{{.Id}}').decode().strip()
native_before=hashlib.sha256((APP/'Contents/MacOS/Kingfisher').read_bytes()).hexdigest()
assert native_before=='b294220f1588fa8a7282caec6cf02ede0939440d51c238335dafaf7f15c22778'
assert command('/private/tmp/kingfisher-native-real-probe/probe',str(APP)).strip()==b'before=ok\nafter=ok'
BACKUP.mkdir(mode=0o700)
old_env=ENV.read_bytes()
shutil.copy2(ENV,BACKUP/'kingfisher.env');os.chmod(BACKUP/'kingfisher.env',0o600)
shutil.copytree(APP,BACKUP/'Kingfisher.app',symlinks=True)
inspect=command('docker','inspect',CONTAINER)
(BACKUP/'container.json').write_bytes(inspect);os.chmod(BACKUP/'container.json',0o600)
old_image=json.loads(inspect)[0]['Image']
shutil.copytree(APP,PREPARED,symlinks=True)
shutil.copy2(Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923/deploy/compose.app.yaml'), PREPARED/'Contents/Resources/compose.yaml')
plist=PREPARED/'Contents/Info.plist'
assert plist.read_bytes()==(APP/'Contents/Info.plist').read_bytes()
assert (PREPARED/'Contents/MacOS/Kingfisher').read_bytes()==(APP/'Contents/MacOS/Kingfisher').read_bytes()
command('xattr','-cr',str(PREPARED))
assert (PREPARED/'Contents/Resources/compose.yaml').read_bytes()==(APP/'Contents/Resources/compose.yaml').read_bytes()
command('codesign','--verify','--strict','--deep',str(PREPARED))
command('docker','stop','-t','45',CONTAINER)
app_moved=False
env_changed=False
try:
    command('docker','cp',CONTAINER+':/data',str(BACKUP/'data'))
    checks,before=root_data_check(BACKUP/'data')
    (BACKUP/'episode-digests.json').write_text(json.dumps(before));os.chmod(BACKUP/'episode-digests.json',0o600)
    settings_before=json.loads((BACKUP/'data/einstellungen.json').read_text())
    background_before=json.loads((BACKUP/'data/hintergrund.json').read_text())
    assert background_before.get('pausiert') is True, 'Respect the currently paused background work'
    lines=old_env.decode().splitlines();seen=0
    for index,line in enumerate(lines):
        if line.startswith('KINGFISHER_IMAGE='):
            lines[index]='KINGFISHER_IMAGE='+IMAGE;seen+=1
    assert seen<=1
    if not seen:lines.append('KINGFISHER_IMAGE='+IMAGE)
    feature_key='KINGFISHER_DURABLE_MEMORY_SEARCH='
    feature_lines=[i for i,line in enumerate(lines) if line.startswith(feature_key)]
    assert len(feature_lines)<=1
    if feature_lines:lines[feature_lines[0]]=feature_key+'1'
    else:lines.append(feature_key+'1')
    tokens=[line.split('=',1)[1].strip().strip("'\"") for line in lines if line.startswith('ICARUS_SIDECAR_TOKEN=')]
    assert len(tokens)==1 and tokens[0]
    token=tokens[0]
    temp=ENV.with_name('kingfisher.env.neu-'+REVISION)
    temp.write_text('\n'.join(lines)+'\n');os.chmod(temp,0o600)
    os.replace(APP,BACKUP/'Kingfisher-ausgetauscht.app');app_moved=True
    os.replace(PREPARED,APP)
    os.replace(temp,ENV);env_changed=True
    compose('up','-d','--no-build','--pull','never')
    deadline=time.monotonic()+45
    with httpx.Client(trust_env=False,timeout=3,follow_redirects=False) as client:
        while time.monotonic()<deadline:
            try:
                health=client.get('http://127.0.0.1:8890/health')
                response=client.get('http://127.0.0.1:8890/api/v1/fassung',headers={'X-Icarus-Token':token})
                if health.status_code==200 and response.status_code==200 and response.json()['fassung']==VERSION:break
            except (httpx.HTTPError,ValueError,KeyError):pass
            time.sleep(1)
        else:raise RuntimeError('New version did not become healthy')
        recovery=client.get('http://127.0.0.1:8890/api/v1/recovery/status',headers={'X-Icarus-Token':token})
        # Normal mode has no inspection-only route; 404 is expected, matching native Loopback.inspectionMode.
        assert recovery.status_code==404 or (recovery.status_code==200 and recovery.json().get('operational') is True)
        assert client.get('http://127.0.0.1:8890/api/v1/world',headers={'X-Icarus-Token':token}).status_code==200
        coverage=client.get('http://127.0.0.1:8890/api/v1/memory/coverage',headers={'X-Icarus-Token':token})
        assert coverage.status_code==200
        semantic=coverage.json()['semantic_index']
        assert semantic['status']!='disabled'
        intake=client.get('http://127.0.0.1:8890/api/v1/mail/intake',headers={'X-Icarus-Token':token})
        assert intake.status_code==200 and intake.json()['background_paused'] is True
        mail_states=[a.get('stand',{}).get('zustand') for a in intake.json()['accounts']]
        assert 'liest' not in mail_states, 'Paused personal intake must not claim active reading'
    now=json.loads(command('docker','inspect',CONTAINER))[0]
    assert now['Image']==image_id
    assert 'KINGFISHER_DURABLE_MEMORY_SEARCH=1' in now['Config']['Env']
    assert any(m.get('Name')=='kingfisher_kingfisher-data' and m['Destination']=='/data' for m in now['Mounts'])
    code="import sqlite3,json; c=sqlite3.connect('/data/episodes.sqlite3'); rows=c.execute('select id,digest from episodes').fetchall(); print(json.dumps(dict(rows))); c.close()"
    after=json.loads(command('docker','exec',CONTAINER,'python','-c',code))
    assert all(after.get(i)==d for i,d in before.items())
    check_code="import pathlib,sqlite3,json; r=[];\nfor p in pathlib.Path('/data').glob('*.sqlite3'):\n c=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True); assert c.execute('pragma quick_check').fetchall()==[('ok',)]; r.append(p.name); c.close()\nprint(json.dumps(r))"
    after_checks=json.loads(command('docker','exec',CONTAINER,'python','-c',check_code))
    settings_after=json.loads(command('docker','exec',CONTAINER,'python','-c',"from pathlib import Path; print(Path('/data/einstellungen.json').read_text())"))
    preserved=['mail','mail_accounts','calendar','calendar_sources','cloud_models','provider','model','endpoint','model_roles','schedule']
    assert all(settings_before.get(k)==settings_after.get(k) for k in preserved)
    background_after=json.loads(command('docker','exec',CONTAINER,'python','-c',"from pathlib import Path; print(Path('/data/hintergrund.json').read_text())"))
    assert background_after.get('pausiert') is True
    assert semantic.get('pause_reason')== 'Pausiert. Kingfisher lernt weiter, wenn du „Weiter“ wählst.'
    assert hashlib.sha256((APP/'Contents/MacOS/Kingfisher').read_bytes()).hexdigest()==native_before
    command('codesign','--verify','--strict','--deep',str(APP))
    report={'native_binary_sha256':native_before,'version':VERSION,'code_commit':REVISION,'new_image_id':image_id,'old_image_id':old_image,'backup':str(BACKUP),'root_sqlite_before':len(checks),'root_sqlite_after':len(after_checks),'episode_ids_and_digests_preserved':len(before),'native_binary_unchanged':True,'settings_groups_preserved':preserved,'same_data_volume':True,'operational':True,'semantic_search_activated':True,'semantic_status':semantic['status'],'native_ui_verified':False,'background_pause_preserved':True,'mail_global_pause_visible':True,'mail_account_states':mail_states}
    (BACKUP/'verification.json').write_text(json.dumps(report,indent=2))
    Path('/private/tmp/kingfisher-phase-installation-result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='settings_groups_preserved'}))
except BaseException:
    if app_moved:
        # This release changes no store schema. Preserve the new app for diagnosis.
        failed=BACKUP/'Kingfisher-update-fehlgeschlagen.app'
        if APP.exists():
            os.replace(APP,failed)
        shutil.copytree(BACKUP/'Kingfisher.app',APP,symlinks=True)
        if env_changed:
            ENV.write_bytes(old_env);os.chmod(ENV,0o600)
        compose('up','-d','--no-build','--pull','never')
    else:
        command('docker','start',CONTAINER)
    raise
