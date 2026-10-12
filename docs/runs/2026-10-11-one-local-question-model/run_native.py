import hashlib,json,os,signal,socket,stat,subprocess,time,shutil
from pathlib import Path
REPO=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923')
RUN=REPO/'docs/runs/2026-10-11-one-local-question-model'
ROOT=Path('/private/tmp/kingfisher-one-local-question-model-20261011-attempt3')
ROOT.mkdir(exist_ok=False)
CACHE=ROOT/'models';NATIVE=Path('/Users/sorenkube/.ollama/models')
MANIFEST=Path('manifests/registry.ollama.ai/library/kingfisher-qwen3.5/9b-32k')
MODEL='kingfisher-qwen3.5:9b-32k'
BIN=Path('/Applications/Ollama.app/Contents/Resources/ollama')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def record(p):
 s=p.lstat();assert stat.S_ISREG(s.st_mode) and not p.is_symlink()
 return dict(path=str(p),sha256=sha(p),inode=s.st_ino,size=s.st_size,mtime_ns=s.st_mtime_ns,mode=stat.S_IMODE(s.st_mode))
manifest=json.loads((NATIVE/MANIFEST).read_text())
paths=[MANIFEST]+[Path('blobs')/v['digest'].replace(':','-') for v in [manifest['config'],*manifest['layers']]]
before=[]
free_before=shutil.disk_usage(ROOT).free
assert free_before>10*1024**3, 'Preserve at least 10 GiB free storage'
for path in paths:
 source=NATIVE/path;r=record(source)
 if path.parts[0]=='blobs':assert r['sha256']==path.name.removeprefix('sha256-')
 destination=CACHE/path;destination.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run(['/bin/cp','-c',str(source),str(destination)],check=True)
 clone=record(destination);assert clone['inode']!=r['inode'] and clone['sha256']==r['sha256']
 before.append(r)
with socket.socket() as s:s.bind(('127.0.0.1',11439))
env={k:os.environ[k] for k in ('PATH','LANG','TMPDIR','LC_ALL','HOME') if k in os.environ}
env.update(OLLAMA_HOST='127.0.0.1:11439',OLLAMA_MODELS=str(CACHE),OLLAMA_NO_CLOUD='1',OLLAMA_NOPRUNE='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_KEEP_ALIVE='15s',OLLAMA_CONTEXT_LENGTH='4096',PYTHONUNBUFFERED='1',KINGFISHER_FASSUNG=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip())
state=dict(synthetic_only=True,production_endpoint_touched=False,personal_kingfisher_settings_loaded=False,original_weights_before=before,completed=False,samples=[],watchdog='480 seconds or 11 GiB sampled owned RSS; no hard GPU cap',free_storage_before=free_before,free_storage_after_clone=shutil.disk_usage(ROOT).free,allowed_inherited_env_keys=[k for k in ('PATH','LANG','TMPDIR','LC_ALL','HOME') if k in env])
assert state['free_storage_after_clone']>10*1024**3
def save(): (ROOT/'runtime.json').write_text(json.dumps(state,indent=2)+'\n')
server=child=None
def interrupted(sig,frame):raise KeyboardInterrupt('Termination signal '+str(sig))
signal.signal(signal.SIGTERM,interrupted)
started=time.monotonic()
try:
 log=(ROOT/'ollama.log').open('w');server=subprocess.Popen([str(BIN),'serve'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 state['server_pid']=server.pid;save()
 for _ in range(100):
  assert server.poll() is None
  try:
   with socket.create_connection(('127.0.0.1',11439),timeout=.3):break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Owned daemon failed readiness')
 output=(ROOT/'questions.log').open('w')
 child=subprocess.Popen(['/private/tmp/kingfisher-question-model-venv-20261011/bin/python',str(RUN/'question_flow.py'),str(REPO),str(ROOT)],cwd=REPO,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
 state['child_pid']=child.pid;save()
 while child.poll() is None:
  ps=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,rss='],text=True)
  rows=[tuple(map(int,line.split())) for line in ps.splitlines() if len(line.split())==3]
  owned={server.pid,child.pid}
  for _ in range(5):owned|={pid for pid,parent,_ in rows if parent in owned}
  rss=sum(rss for pid,_,rss in rows if pid in owned)*1024
  elapsed=time.monotonic()-started
  state['samples'].append(dict(seconds=round(elapsed,2),owned_rss_bytes=rss))
  save()
  if elapsed>480 or rss>11*1024**3:raise RuntimeError('Bounded test watchdog stopped the run')
  time.sleep(2)
 state['child_exit']=child.returncode
 if child.returncode:raise RuntimeError('Question flow failed; inspect retained log')
 state['completed']=True
finally:
 for process in (child,server):
  if process is not None and process.poll() is None:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=8)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=8)
 state['processes_stopped']=all(p is None or p.poll() is not None for p in (child,server))
 state['original_weights_after']=[record(NATIVE/path) for path in paths]
 state['original_weights_unchanged']=state['original_weights_after']==before
 save()
 print(json.dumps({k:v for k,v in state.items() if k not in {'samples','original_weights_before','original_weights_after'}},indent=2))
