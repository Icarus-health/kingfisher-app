"""Künstliche echte Qwen-Probe des unveränderten Produkttransports und Lernwegs."""
import argparse,os,sys,json,time,hashlib,threading
from pathlib import Path
from datetime import datetime,timezone
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'sidecar'),str(ROOT/'scripts')]
from messlatte.instanz import instanz_starten
from icarus_memory.providers import OpenAICompatible,ProviderError
from icarus_memory.local_model_guard import verify_local_model
from icarus_memory.local_context_profile import FLAG
from icarus_memory import ollama_memory
from probe_intake_precision import _mac_resource_check
from probe_mail_intake_quality import resources,stop_reason
MODEL='kingfisher-qwen3.5:9b-8k'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path,help='Neue lokale JSON-Ausgabedatei; bestehende Dateien werden nicht überschrieben.')
OUT=parser.parse_args().output;OUT.parent.mkdir(exist_ok=True,parents=True)
SCENARIOS=[
 ('workflow',[
 ('Schreibe eine Mail für die Zunft zur Sitzung.','Bitte zuerst Anlass und Empfänger prüfen, danach den Entwurf gegenlesen.'),
 ('Schreibe eine Einladung per Mail für die Zunft.','Bitte vor dem Schreiben Anlass und Empfänger prüfen; am Ende den Entwurf gegenlesen.'),
 ('Entwirf eine Mail für die Zunft zur Rückmeldung.','Bitte zuerst den Anlass und die Empfänger prüfen, dann schreiben und gegenlesen.')],True),
 ('facts',[
 ('Schreibe eine Mail für die Zunft zur Sitzung.','Prüfe die Frist: Abgabe ist am 7. November 2026, nicht am 8. November.'),
 ('Schreibe eine Einladung per Mail für die Zunft.','Prüfe den Namen: Der Empfänger heißt Alex Berger, nicht Alex Winter.'),
 ('Entwirf eine Mail für die Zunft zur Rückmeldung.','Prüfe den Termin: Die Sitzung findet am 12. November um 18 Uhr statt.')],False),
]
report=dict(status='started',synthetic_only=True,model=MODEL,model_calls=[],cases=[],resources=[],cloud_calls=0,import_resumed=False,
 dataset=SCENARIOS,dataset_sha256=hashlib.sha256(json.dumps(SCENARIOS,ensure_ascii=False).encode()).hexdigest(),
 code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['sidecar/icarus_memory/workflow_learning.py','sidecar/icarus_memory/procedure_model.py','sidecar/icarus_memory/local_context_profile.py','sidecar/icarus_memory/workflow_guards.py','sidecar/icarus_memory/procedures.py']},
 model_quality_review='pending',mac_ui='not tested',status_checks_only=True)
with OUT.open('x') as f:json.dump(report,f)
os.chmod(OUT,0o600)
start=time.monotonic(); halt=threading.Event();finished=threading.Event()
def save():OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
def sample():
 memory=resources();report['resources'].append({'seconds':round(time.monotonic()-start,2),'memory':memory})
 reason=stop_reason(time.monotonic()-start,memory,180)
 if reason:report.setdefault('resource_stop',reason);halt.set()
 return reason
def guard():
 if sample() or halt.is_set():raise ProviderError('Ressourcenprüfung abgebrochen.')
 _mac_resource_check(MODEL)
def monitor():
 while not finished.wait(1):sample()
provider=OpenAICompatible(MODEL,'synthetic-local','http://127.0.0.1:11434/v1')
provider._verified_local_permitted=lambda:not halt.is_set()
original_client=provider._client
@contextmanager
def traced_client(timeout):
 with original_client(timeout) as client:
  original_post=client.post
  def post(url,**kwargs):
   guard()
   if len(report['model_calls'])>=4:raise ProviderError('Probe-Aufrufgrenze')
   if url!='http://127.0.0.1:11434/api/chat':raise ProviderError('Nicht lokaler Transport')
   row={'case':report['case'],'payload':kwargs.get('json'),'status':'started'}
   report['model_calls'].append(row);save();tick=time.monotonic()
   try:
    response=original_post(url,**kwargs);row['response']=response.json();row['status']='completed';return response
   except Exception as e:row['status']='failed';row['error']=str(e);raise
   finally:row['seconds']=round(time.monotonic()-tick,3);sample();save()
  client.post=post
  yield client
provider._client=traced_client
# Nur Metadaten des bestehenden Modell-Lebenszyklus beobachten; keine anderen
# Programme, keine Retention und keine Ressourcenschwelle verändern.
original_memory_client=ollama_memory._ollama_client
report['lifecycle_calls']=[]
@contextmanager
def traced_memory_client(**options):
 with original_memory_client(**options) as client:
  original_stream=client.stream
  @contextmanager
  def stream(method,url,**kwargs):
   row={'method':method,'url':url,'seconds_start':round(time.monotonic()-start,3)}
   body=kwargs.get('json') or {}
   row.update({key:body[key] for key in ('model','keep_alive') if key in body})
   report['lifecycle_calls'].append(row)
   try:
    with original_stream(method,url,**kwargs) as response:
     row['http']=response.status_code
     yield response
   except Exception as exc:row['error']=type(exc).__name__;raise
   finally:row['seconds_end']=round(time.monotonic()-start,3)
  client.stream=stream
  yield client
ollama_memory._ollama_client=traced_memory_client
try:
 guard();
 if resources()['free_percent']<55:raise ProviderError('Startreserve unter 55 Prozent')
 identity=verify_local_model(provider,expected_num_ctx=8192);report['digest']=identity.digest
 thread=threading.Thread(target=monitor,daemon=True);thread.start()
 for name,records,expected in SCENARIOS:
  guard();report['case']=name;tick=time.monotonic();before=len(report['model_calls'])
  with instanz_starten(stichtag=datetime.now(timezone.utc),zeitzone='Europe/Berlin',provider=provider,eigene=('soeren@example.invalid',)) as inst:
   os.environ[FLAG]=MODEL;inst.app.state.scheduler.stop();inst.app.state.settings.background_paused=True
   responses=[]
   for index,(question,correction) in enumerate(records):
    conv=inst.app.state.conversations.create('Künstliche Lernprobe '+str(index))
    inst.app.state.conversations.add_message(conv.id,'user',question)
    answer=inst.app.state.conversations.add_message(conv.id,'assistant','Künstlicher Entwurf für die Lernprobe.')
    body=dict(conversation_id=conv.id,message_id=answer.id,art='sonstiges',richtig=correction,arbeitsweise=True)
    response=inst.client.post('/api/v1/rueckmeldungen',json=body)
    responses.append({'http':response.status_code,'data':response.json()})
   learning=responses[-1]['data'].get('lernen',{});checks={'http':all(r['http']==201 for r in responses),'proposed':(learning.get('status')=='proposed')==expected}
   record=dict(name=name,responses=responses,learning=learning,checks=checks)
   if expected and learning.get('proposal_id'):
    identifier=learning['proposal_id'];item=inst.app.state.procedures.get(identifier)
    record['item']=item;checks['pending']=item['state']=='pending'
    accepted=inst.client.post('/api/v1/procedures/'+identifier+'/accept');checks['accept']=accepted.status_code==200
    chosen=inst.app.state.procedures.select('Schreibe eine Mail für die Zunft.',area='mail')
    private=inst.app.state.procedures.select('Schreibe eine private Mail zur Urlaubsplanung.',area='mail')
    record['selected']=chosen;record['private']=private
    checks['appropriate']=bool(chosen['contextual']);checks['private_excluded']=not private['contextual']
    fid=responses[-1]['data']['meldung']['id']
    inst.client.post('/api/v1/rueckmeldungen/'+fid+'/arbeitsweise-zuruecknehmen')
    checks['withdrawal']=not inst.app.state.procedures.select('Schreibe eine Mail für die Zunft.',area='mail')['contextual']
   elif not expected:checks['no_procedure']=not inst.app.state.procedures.items()
   record.update(passed=all(checks.values()),seconds=round(time.monotonic()-tick,3),model_calls=len(report['model_calls'])-before)
   report['cases'].append(record);save();print(json.dumps({k:record[k] for k in ['name','learning','passed','seconds','model_calls']}),flush=True)
  guard()
 report['live_model_verified']=verify_local_model(provider,expected_num_ctx=8192)==identity and bool(report['model_calls'])
 report['status']='passed' if all(c['passed'] for c in report['cases']) and report['live_model_verified'] and not halt.is_set() else 'failed'
except Exception as e:report.update(status='failed',error=type(e).__name__+': '+str(e))
finally:
 finished.set();report['seconds']=round(time.monotonic()-start,3);save()
 print(json.dumps({k:report.get(k) for k in ['status','seconds','error','resource_stop','live_model_verified']}),flush=True)
sys.exit(0 if report['status']=='passed' else 1)
