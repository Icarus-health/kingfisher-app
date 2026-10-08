"""Owned native local-only Ollama; run once after previous owner releases port."""
import hashlib, json, os, shutil, signal, socket, subprocess, sys, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent
ORIGIN = 'http://127.0.0.1:11439'
STATE = ROOT / 'runtime.json'
assert not STATE.exists(), 'No rerun or overwrite'
previous = json.loads(Path('/private/tmp/kingfisher-phase-after-final-20261009/runtime.json').read_text())
assert previous['completed'] and previous.get('server_exit') == 0 and previous.get('stopped_at')
with socket.socket() as check: check.bind(('127.0.0.1', 11439))
models = ROOT / 'models'
(models / 'manifests/registry.ollama.ai/library/qwen3.5').mkdir(parents=True)
source = Path('/Users/sorenkube/.ollama/models')
(models / 'blobs').symlink_to(source / 'blobs', target_is_directory=True)
manifest = source / 'manifests/registry.ollama.ai/library/qwen3.5/4b'
shutil.copy2(manifest, models / 'manifests/registry.ollama.ai/library/qwen3.5/4b')
env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11439', OLLAMA_MODELS=str(models),
           OLLAMA_NO_CLOUD='1', OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1',
           OLLAMA_CONTEXT_LENGTH='4096', OLLAMA_KEEP_ALIVE='15s', OLLAMA_FLASH_ATTENTION='1',
           OLLAMA_MAX_QUEUE='4', PYTHONUNBUFFERED='1')
state = {'synthetic_only': True, 'endpoint': ORIGIN, 'no_hard_memory_cap': True,
         'watchdog': '8 GiB sampled owned process RSS or 600s; GPU allocation not fully covered by RSS',
         'production_endpoint_touched': False, 'completed': False, 'samples': [],
         'started_at': time.time(), 'model_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
         'prior_owner_stopped_at': previous['stopped_at']}
server = client = None
def save():
    temp = STATE.with_suffix('.new'); temp.write_text(json.dumps(state, indent=2) + '\n'); temp.replace(STATE)
def terminate(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
try:
    with (ROOT / 'ollama.log').open('w') as log:
        server = subprocess.Popen(['/usr/local/bin/ollama', 'serve'], env=env,
                                  stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        state['server_pid'] = server.pid; save()
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=2) as http:
            for _ in range(40):
                if server.poll() is not None: raise RuntimeError('Owned server exited before ready')
                try:
                    response = http.get(ORIGIN + '/api/tags'); response.raise_for_status(); break
                except (httpx.HTTPError, ValueError): time.sleep(.25)
            else: raise RuntimeError('Owned server did not become ready')
            state['tags'] = response.json(); state['ollama_version'] = http.get(ORIGIN + '/api/version').json(); save()
        with (ROOT / 'probe.log').open('w') as log:
            client = subprocess.Popen([sys.executable, str(ROOT / 'gate_client.py')], env=env,
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            state['client_pid'] = client.pid; save(); start = time.monotonic()
            while client.poll() is None:
                ps = subprocess.run(['/bin/ps', '-axo', 'pid=,pgid=,rss='], text=True, capture_output=True, check=True)
                rows = [list(map(int, line.split())) for line in ps.stdout.splitlines() if line.strip()]
                rss = sum(r[2] for r in rows if r[1] in {server.pid, client.pid})
                state['samples'].append({'elapsed': round(time.monotonic() - start, 2), 'owned_rss_kib': rss}); save()
                if rss > 8 * 1024 * 1024 or time.monotonic() - start > 600:
                    state['watchdog_stop'] = 'sampled RSS or runtime limit exceeded'; terminate(client); break
                if server.poll() is not None: raise RuntimeError('Owned server exited during diagnostic')
                time.sleep(2)
            state['client_exit'] = client.wait(); state['completed'] = state['client_exit'] == 0; save()
finally:
    terminate(client); terminate(server)
    state['server_exit'] = None if server is None else server.poll()
    state['stopped_at'] = time.time(); save()
print(json.dumps({k: v for k, v in state.items() if k not in {'samples', 'tags'}}, indent=2))
