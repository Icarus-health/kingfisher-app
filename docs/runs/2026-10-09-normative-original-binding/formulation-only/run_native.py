"""Owned isolated qwen-only formulation probe; native Ollama cache is never shared."""
import os,sys,time,json,signal,socket,subprocess,hashlib,stat
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parent
MODEL_SOURCE=Path('/Users/sorenkube/.ollama/models')
MODELS=ROOT/'models';BLOBS=MODELS/'blobs';STATE=ROOT/'runtime.json'
assert not STATE.exists(),'Refusing to overwrite a previous run'
assert BLOBS.is_dir() and not BLOBS.is_symlink(),'Isolated blob store must be a real directory'
assert not (MODELS/'manifests/registry.ollama.ai/library/bge-m3').exists(),'This probe must remain qwen-only'
manifest_path=MODELS/'manifests/registry.ollama.ai/library/qwen3.5/4b'
model=json.loads(manifest_path.read_text())
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
# Before server start: reverify every isolated blob and confirm source metadata remains frozen.
before=json.loads((ROOT/'native-source-blobs-before.json').read_text())
by_digest={x['digest']:x for x in before}
verified=[]
for ref in [model['config']['digest'],*(x['digest'] for x in model['layers'])]:
 d=ref.split(':',1)[1];p=BLOBS/('sha256-'+d)
 assert p.is_file() and not p.is_symlink(),f'missing or symlinked isolated qwen blob {ref}'
 got=digest(p);assert got==d,f'isolated qwen blob digest mismatch {ref}'
 source=Path(by_digest[ref]['path']);st=source.stat()
 assert st.st_ino==by_digest[ref]['inode'] and st.st_size==by_digest[ref]['size'] and st.st_mtime_ns==by_digest[ref]['mtime_ns'],f'native qwen source metadata changed since freeze {ref}'
 assert p.stat().st_ino!=st.st_ino,f'isolated qwen blob shares source inode {ref}'
 verified.append({'digest':ref,'isolated_sha256':got,'isolated_inode':p.stat().st_ino,'source_inode':st.st_ino,'distinct_inode':True,'not_symlink':True})
with socket.socket() as probe:probe.bind(('127.0.0.1',11439))
env=dict(os.environ,OLLAMA_HOST='127.0.0.1:11439',OLLAMA_MODELS=str(MODELS),OLLAMA_NO_CLOUD='1',OLLAMA_NOPRUNE='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_CONTEXT_LENGTH='4096',OLLAMA_KEEP_ALIVE='15s',OLLAMA_MAX_QUEUE='2',PYTHONUNBUFFERED='1',PYTHONPATH=str(ROOT/'repo'/'sidecar'))
state={'synthetic_only':True,'endpoint':'http://127.0.0.1:11439','ollama_models':str(MODELS),'isolated_blobs_real_directory':True,'isolated_blobs_symlink':False,'OLLAMA_NO_CLOUD':'1','OLLAMA_NOPRUNE':'1','native_source_blobs_before_sha256':hashlib.sha256((ROOT/'native-source-blobs-before.json').read_bytes()).hexdigest(),'preflight_verified_blobs':verified,'watchdog':'8 GiB sampled owned server/client process RSS or 600 seconds; GPU allocation not fully covered by RSS','production_endpoint_touched':False,'started_at':time.time(),'samples':[],'completed':False,'client_exit':None,'server_exit':None,'watchdog_stop':None}
def save():
 t=STATE.with_suffix('.new');t.write_text(json.dumps(state,indent=2)+'\n');t.replace(STATE)
def terminate(p):
 if p is not None and p.poll() is None:
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
server=client=None
try:
 with (ROOT/'ollama.log').open('w') as log:
  server=subprocess.Popen(['/usr/local/bin/ollama','serve'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  state['server_pid']=server.pid;save()
  with httpx.Client(trust_env=False,timeout=2) as http:
   for _ in range(40):
    if server.poll() is not None:raise RuntimeError('Owned isolated Ollama exited before ready')
    try:
     response=http.get('http://127.0.0.1:11439/api/tags');response.raise_for_status();break
    except httpx.HTTPError:time.sleep(.25)
   else:raise RuntimeError('Owned isolated Ollama not ready')
   state['tags']=response.json();state['ollama_version']=http.get('http://127.0.0.1:11439/api/version').json();save()
   names=[x.get('name') for x in state['tags'].get('models',[])]
   if names!=['qwen3.5:4b']:raise RuntimeError(f'Isolated model inventory unexpected: {names}')
  with (ROOT/'probe.log').open('w') as log:
   client=subprocess.Popen([sys.executable,str(ROOT/'formulate.py')],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   state['client_pid']=client.pid;save();start=time.monotonic()
   while client.poll() is None:
    ps=subprocess.run(['/bin/ps','-axo','pid=,pgid=,rss='],text=True,capture_output=True,check=True)
    rows=[list(map(int,line.split())) for line in ps.stdout.splitlines() if line.strip()]
    rss=sum(row[2] for row in rows if row[1] in {server.pid,client.pid})
    state['samples'].append({'elapsed':round(time.monotonic()-start,2),'owned_rss_kib':rss});save()
    if rss>8*1024*1024 or time.monotonic()-start>600:
     state['watchdog_stop']='sampled RSS or runtime limit exceeded';terminate(client);break
    if server.poll() is not None:raise RuntimeError('Owned isolated Ollama exited during probe')
    time.sleep(2)
   state['client_exit']=client.wait();state['completed']=state['client_exit']==0;save()
finally:
 terminate(client);terminate(server)
 state['server_exit']=None if server is None else server.poll()
 state['stopped_at']=time.time();save()
 # Recheck the native source blobs after shutdown; no shared writable blob directory was mounted.
 after=[]
 for old in before:
  p=Path(old['path']);st=p.stat() if p.exists() else None
  rec={'digest':old['digest'],'exists':bool(st),'size':st.st_size if st else None,'inode':st.st_ino if st else None,'mtime_ns':st.st_mtime_ns if st else None,'mode':stat.S_IMODE(st.st_mode) if st else None,'sha256':digest(p) if st else None}
  after.append(rec)
 unchanged=all(rec['exists'] and rec['size']==old['size'] and rec['inode']==old['inode'] and rec['mtime_ns']==old['mtime_ns'] and rec['mode']==old['mode'] and rec['sha256']==old['sha256'] for old,rec in zip(before,after,strict=True))
 state['native_source_blobs_after']=after;state['native_source_blobs_unchanged']=unchanged;save()
 (ROOT/'native-source-blobs-after.json').write_text(json.dumps(after,indent=2)+'\n')
print(json.dumps({k:v for k,v in state.items() if k not in {'samples','tags','native_source_blobs_before','native_source_blobs_after'}},indent=2))
