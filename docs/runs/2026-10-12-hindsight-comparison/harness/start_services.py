"""Local synthetic comparison services. Never loads Kingfisher configuration or secrets."""
import json,os,signal,subprocess,time,threading,urllib.request,hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pg0 import Pg0

ROOT=Path(os.environ['KINGFISHER_HINDSIGHT_BENCH_DIR']).resolve()
QWEN='kingfisher-qwen3.5:9b-32k'
BGE='bge-m3:latest'
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
LOG_LOCK=threading.Lock()
class Proxy(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.forward()
    def do_POST(self):self.forward()
    def forward(self):
        start=time.monotonic();payload=None
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
        try:
            allowed={'/v1/chat/completions','/api/chat','/v1/embeddings','/api/embed','/api/tags','/api/show','/api/version','/api/ps'}
            if self.path not in allowed:raise ValueError('Endpoint not allowed')
            if raw:
                payload=json.loads(raw)
                if self.path.endswith('/chat/completions') or self.path=='/api/chat':
                    assert payload.get('model')==QWEN and not payload.get('stream')
                elif self.path in ('/v1/embeddings','/api/embed'):assert payload.get('model') in ('bge-m3',BGE)
                elif self.path=='/api/show':assert payload.get('model') in (QWEN,BGE)
            request=urllib.request.Request('http://127.0.0.1:11434'+self.path,data=raw or None,method=self.command,headers={'Content-Type':'application/json'})
            with OPENER.open(request,timeout=180) as response:answer=response.read();status=response.status
            parsed=json.loads(answer)
            usage=parsed.get('usage') or ({'prompt_tokens':parsed.get('prompt_eval_count'),'completion_tokens':parsed.get('eval_count'),'native_total_duration_ns':parsed.get('total_duration'),'native_load_duration_ns':parsed.get('load_duration')} if self.path=='/api/chat' else None)
            event={'phase':(ROOT/'phase.txt').read_text() if (ROOT/'phase.txt').exists() else 'setup','path':self.path,'seconds':round(time.monotonic()-start,4),'request_chars':len(raw),'model':payload.get('model') if payload else None,'usage':usage,'max_tokens':(payload.get('max_tokens') or payload.get('options',{}).get('num_predict')) if payload else None,'reasoning_effort':payload.get('reasoning_effort') if payload else None,'think':payload.get('think') if payload else None,'num_ctx':payload.get('options',{}).get('num_ctx') if payload else None}
            with LOG_LOCK:
                with (ROOT/'model-requests.jsonl').open('a') as stream:stream.write(json.dumps(event)+'\n')
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(answer)));self.end_headers();self.wfile.write(answer)
        except Exception as exc:
            answer=json.dumps({'error':{'message':type(exc).__name__}}).encode()
            self.send_response(502);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(answer)));self.end_headers();self.wfile.write(answer)

proxy=ThreadingHTTPServer(('127.0.0.1',18934),Proxy)
threading.Thread(target=proxy.serve_forever,daemon=True).start()
pg=Pg0(name='kingfisher_hindsight_compare_'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12],data_dir=str(ROOT/'pgdata'),port=18932,username='synthetic',password='synthetic-test-only',database='synthetic',config={'shared_buffers':'64MB','max_connections':'60'})
child=None
try:
    info=pg.start()
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TMPDIR')}
    env.update({
        'HINDSIGHT_API_DATABASE_URL':info.uri,
        'HINDSIGHT_API_HOST':'127.0.0.1','HINDSIGHT_API_PORT':'18935',
        'HINDSIGHT_API_LLM_PROVIDER':'ollama','HINDSIGHT_API_LLM_BASE_URL':'http://127.0.0.1:18934/v1',
        'HINDSIGHT_API_LLM_MODEL':QWEN,'HINDSIGHT_API_LLM_REASONING_EFFORT':'none',
        'HINDSIGHT_API_LLM_OLLAMA_NUM_CTX':'32768',
        'HINDSIGHT_API_LLM_TEMPERATURE':'0','HINDSIGHT_API_LLM_MAX_CONCURRENT':'1',
        'HINDSIGHT_API_LLM_MAX_RETRIES':'0','HINDSIGHT_API_LLM_TIMEOUT':'180',
        'HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS':'4096',
        'HINDSIGHT_API_RETAIN_MAX_CONCURRENT':'1','HINDSIGHT_API_RETAIN_STORE_MAX_CONCURRENT':'1',
        'HINDSIGHT_API_EMBEDDINGS_PROVIDER':'openai',
        'HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL':'http://127.0.0.1:18934/v1',
        'HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY':'synthetic-local-only',
        'HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL':BGE,'HINDSIGHT_API_EMBEDDINGS_OPENAI_DIMENSIONS':'1024',
        'HINDSIGHT_API_RERANKER_PROVIDER':'flashrank',
        'HINDSIGHT_API_RERANKER_FLASHRANK_MODEL':'ms-marco-MultiBERT-L-12',
        'HINDSIGHT_API_RERANKER_FLASHRANK_CACHE_DIR':str(ROOT/'reranker'),
        'HINDSIGHT_API_RERANKER_FLASHRANK_BATCH_SIZE':'4',
        'HINDSIGHT_API_ENABLE_AUTO_CONSOLIDATION':'false',
        'HINDSIGHT_API_OTEL_TRACES_ENABLED':'false','HINDSIGHT_API_LOG_LEVEL':'warning',
        'HF_HOME':str(ROOT/'hf-cache'), 'TOKENIZERS_PARALLELISM':'false',
        'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2',
    })
    (ROOT/'effective-test-config.json').write_text(json.dumps({k:v for k,v in env.items() if k.startswith('HINDSIGHT_') and k not in ('HINDSIGHT_API_DATABASE_URL','HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY')},indent=2)+'\n')
    log=(ROOT/'hindsight-server.log').open('w')
    child=subprocess.Popen([str(ROOT/'.venv/bin/hindsight-api'),'--host','127.0.0.1','--port','18935','--log-level','warning'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    print(json.dumps({'proxy_port':18934,'hindsight_port':18935,'pid':child.pid,'database':'separate_synthetic_pg0','parent_pid':os.getpid()}),flush=True)
    while child.poll() is None:time.sleep(1)
    raise RuntimeError('Hindsight exited: '+str(child.returncode))
except KeyboardInterrupt:pass
finally:
    if child is not None and child.poll() is None:
        child.terminate()
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:child.kill();child.wait()
    proxy.shutdown();pg.stop()
