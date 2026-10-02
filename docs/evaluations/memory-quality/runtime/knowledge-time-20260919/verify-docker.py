"""Exercise the built container over HTTP with synthetic persistent stores."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--image', required=True)
args=parser.parse_args()
root=Path(__file__).parent.resolve()
name='kingfisher-m2c-qa-20260919'
volume=name+'-data'
token=secrets.token_urlsafe(32)
envfile=root/'docker.env'
envfile.write_text('ICARUS_SIDECAR_TOKEN='+token+'\nQA_HOST=0.0.0.0\nQA_PORT=8890\n')
envfile.chmod(0o600)
def docker(*parts):
    return subprocess.check_output(['docker',*parts],text=True).strip()
def request(path, body=None):
    req=urllib.request.Request('http://127.0.0.1:18995'+path,
        data=None if body is None else json.dumps(body).encode(),
        headers={'x-icarus-token':token,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.load(response)
def ready():
    for _ in range(100):
        try:
            request('/health')
            return
        except OSError:
            time.sleep(.1)
    raise RuntimeError('Docker fixture did not become ready')
checks=[]
def check(name, result):
    checks.append({'name':name,'passed':bool(result)})
    assert result,name
def call():
    return json.loads(docker('exec',name,'tail','-n','1','/data/provider.jsonl'))
def rows():
    return [json.loads(line[14:]) for message in call()['messages']
            if isinstance(message.get('content'),str) for line in message['content'].splitlines()
            if line.startswith('- [knowledge] ')]
docker('volume','create',volume)
try:
    docker('run','-d','--name',name,'--env-file',str(envfile),'-p','127.0.0.1:18995:8890',
        '-v',volume+':/data','-v',str(root/'serve.py')+':/qa/serve.py:ro',
        '--entrypoint','python',args.image,'/qa/serve.py')
    ready()
    state=json.loads(docker('exec',name,'cat','/data/state.json'))
    conversation=request('/api/v1/conversations',{'title':'Synthetische Docker-Prüfung'})['conversation']['id']
    route='/api/v1/conversations/'+conversation
    initial=request(route+'/messages',{'message':'ORION'})
    actual=next(row for row in rows() if row['assertion_id']=='claim:'+state['ORION']['claim_id'])
    check('built_container_sends_exact_v3_projection',{k:v for k,v in actual.items() if k!='reason'}==state['ORION']['expected'])
    check('built_container_api_equals_provider',initial['context']['items'][0]['knowledge_projection']==actual)
    reply=next(m['content'] for m in reversed(initial['messages']) if m['role']=='assistant')
    docker('restart',name)
    ready()
    check('context_persists_after_container_restart',request(route)['context']['items']==initial['context']['items'])
    request(route+'/messages',{'message':'ORION'})
    check('valid_history_reused_after_container_restart',reply in json.dumps(call()['messages']))
    secondary=state['ORION']['episode_ids'][1]
    docker('exec',name,'python','-c',
        'from icarus_memory.episodes import EpisodeStore; from pathlib import Path; '
        's=EpisodeStore(Path("/data/episodes.sqlite3")); '
        f's.ignore({secondary!r}); s.reopen({secondary!r}); s.close()')
    check('secondary_withdrawal_invalidates_current_card',not request(route)['context']['items'])
    request(route+'/messages',{'message':'ORION'})
    check('secondary_withdrawal_resets_old_provider_history','SYNTHETIC_RESPONSE_' not in json.dumps(call()['messages']))
    result={'image':args.image,'image_id':docker('image','inspect','--format','{{.Id}}',args.image),
            'synthetic_only':True,'real_model':False,'checks':checks,'initial_api':initial,
            'provider_calls':[json.loads(line) for line in docker('exec',name,'cat','/data/provider.jsonl').splitlines()]}
    (root/'docker-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks_passed':len(checks),'image_id':result['image_id']}))
finally:
    try:
        (root/'docker-server.log').write_text(docker('logs',name))
        docker('rm','-f',name)
    finally:
        docker('volume','rm',volume)
    if not (root/'docker-result.json').exists():
        (root/'docker-failed-result.json').write_text(json.dumps({'checks':checks},indent=2)+'\n')
