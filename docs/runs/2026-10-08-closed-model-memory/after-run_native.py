"""Owned, synthetic-only native Ollama evaluation. No production settings loaded."""
import os, sys, time, json, shutil, subprocess, signal, socket, threading, hashlib
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent
REPO = Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923')
ORIGIN = 'http://127.0.0.1:11439'
STATE = ROOT/'runtime.json'
assert not STATE.exists(), 'Do not overwrite an earlier run'
with socket.socket() as check:
    check.bind(('127.0.0.1', 11439))
models = ROOT/'models'
(models/'manifests/registry.ollama.ai/library').mkdir(parents=True)
source = Path('/Users/sorenkube/.ollama/models')
(models/'blobs').symlink_to(source/'blobs', target_is_directory=True)
for name, tag in [('qwen3.5', '4b'), ('bge-m3', 'latest')]:
    dest=models/'manifests/registry.ollama.ai/library'/name/tag
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source/'manifests/registry.ollama.ai/library'/name/tag, dest)
env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11439', OLLAMA_MODELS=str(models),
           OLLAMA_NO_CLOUD='1', OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='2',
           OLLAMA_CONTEXT_LENGTH='4096', OLLAMA_KEEP_ALIVE='15s', OLLAMA_FLASH_ATTENTION='1',
           OLLAMA_MAX_QUEUE='4', KINGFISHER_FASSUNG='ddc10fa', PYTHONUNBUFFERED='1')
state={'synthetic_only':True, 'endpoint':ORIGIN, 'platform':'native macOS / Metal if runtime confirms',
       'no_hard_memory_cap':True, 'watchdog':'8 GiB sampled process RSS or 600s; GPU allocation not fully covered by RSS',
       'production_endpoint_touched':False, 'started_at':time.time(), 'samples':[], 'completed':False}
server=client=None
def save():
    temp=STATE.with_suffix('.new');temp.write_text(json.dumps(state,indent=2)+'\n');temp.replace(STATE)
def terminate(p):
    if p is not None and p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL);p.wait(timeout=5)
try:
    with (ROOT/'ollama.log').open('w') as log:
        server=subprocess.Popen(['/usr/local/bin/ollama','serve'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state['server_pid']=server.pid;save()
        with httpx.Client(trust_env=False, timeout=2) as http:
            for _ in range(40):
                if server.poll() is not None:raise RuntimeError('Owned server exited before ready')
                try:
                    response=http.get(ORIGIN+'/api/tags');response.raise_for_status();break
                except (httpx.HTTPError, ValueError):time.sleep(.25)
            else:raise RuntimeError('Owned server did not become ready')
            state['tags']=response.json();state['ollama_version']=http.get(ORIGIN+'/api/version').json();save()
        with (ROOT/'probe.log').open('w') as probe_log:
            client=subprocess.Popen([sys.executable,str(ROOT/'closed_flow.py'),str(REPO)],env=env,stdout=probe_log,stderr=subprocess.STDOUT,start_new_session=True)
            state['client_pid']=client.pid;save()
            start=time.monotonic()
            while client.poll() is None:
                # This is an emergency sampler, not an enforceable GPU/RAM cap.
                ps=subprocess.run(['/bin/ps','-axo','pid=,pgid=,rss='],text=True,capture_output=True,check=True)
                rows=[list(map(int,line.split())) for line in ps.stdout.splitlines() if line.strip()]
                rss=sum(row[2] for row in rows if row[1] in {server.pid,client.pid})
                state['samples'].append({'elapsed':round(time.monotonic()-start,2),'owned_rss_kib':rss})
                save()
                if rss>8*1024*1024 or time.monotonic()-start>600:
                    state['watchdog_stop']='sampled RSS or runtime limit exceeded';terminate(client);break
                if server.poll() is not None:raise RuntimeError('Owned server exited during probe')
                time.sleep(2)
            state['client_exit']=client.wait();state['completed']=state['client_exit']==0;save()
finally:
    terminate(client);terminate(server)
    state['server_exit']=None if server is None else server.poll()
    state['stopped_at']=time.time();save()
print(json.dumps({k:v for k,v in state.items() if k not in {'samples','tags'}},indent=2))
