import os,sys,json
from pathlib import Path
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, HTTPServer
ROOT=Path(__file__).parent
REPO=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923')
sys.path[:0]=[str(REPO/'sidecar')]
os.environ.clear()
os.environ.update(PATH='/usr/bin:/bin',HOME=str(ROOT/'home'),ICARUS_DATA_DIR=str(ROOT/'data'), KINGFISHER_UPDATE_URL='',KINGFISHER_HINTERGRUND_RUHE_S='0')
(ROOT/'home').mkdir(exist_ok=True)
from fastapi.testclient import TestClient
from icarus_memory import config, device_profile, storage_capacity
from icarus_memory.secrets import Keychain
from icarus_memory.mail_intake import Intake
from tests.test_mail_intake import Reader
Keychain._detect=lambda self:'none'
device_profile.eigene_ausstattung=lambda:None
settings=config.Settings()
settings.mail_accounts=[config.MailAccountSettings(id=k,label=label,imap_host='127.0.0.1',user=k+'@example.org') for k,label in [('a','Künstlich Aktiv'),('b','Künstlich Pausiert'),('c','Künstlich Neu')]]
config.save(ROOT/'data',settings)
from icarus_memory.server import create_app
app=create_app()
mode='low'
def statvfs(_):
 if mode=='unknown':raise OSError('artificial measurement error')
 return SimpleNamespace(f_frsize=1,f_bavail=90*1024**2 if mode=='low' else 2*1024**3,f_files=100000,f_favail=10000)
requests=[]
class Bridge(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):self.forward()
 def do_POST(self):self.forward()
 def forward(self):
  global mode
  content=self.rfile.read(int(self.headers.get('Content-Length','0')))
  if self.path.startswith('/qa/'):
   if self.path!='/qa/state':mode=self.path.removeprefix('/qa/')
   response=json.dumps({'mode':mode,'requests':requests,'global_pause':app.state.hintergrund.pausiert}).encode();code=200
  else:
   requests.append([self.command,self.path])
   r=client.request(self.command,self.path,content=content,headers={'content-type':'application/json'} if content else {})
   response=r.content;code=r.status_code
  self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(response)
with TestClient(app) as client:
 app.state.scheduler.stop()
 reader=Reader();reader.folders=lambda:[{'name':'INBOX','historical':True}]
 app.state.mail=SimpleNamespace(reader_for=lambda _:reader)
 store=Intake(app.state.episodes)
 store.start('a',['INBOX']);store.step('a',reader,batch=1)
 store.start('b',['INBOX']);store.pause('b',True)
 app.state.settings.schedule.enabled=True;app.state.settings.schedule.mail_accounts=['a','b']
 storage_capacity.os=SimpleNamespace(statvfs=statvfs)
 print('SYNTHETIC READY',flush=True)
 HTTPServer(('127.0.0.1',18767),Bridge).serve_forever()
