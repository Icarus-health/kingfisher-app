"""Bounded formulation-only probe against frozen selected synthetic evidence."""
import sys,json,time,hashlib,traceback
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
REPO=Path('/private/tmp/kingfisher-normative-after-20261009/repo')
sys.path.insert(0,str(REPO/'sidecar'))
from icarus_memory import satzantwort,satzpruefung_modell
from icarus_memory.providers import OpenAICompatible
from icarus_memory.local_model_guard import VerifiedLocalProvider
CATALOG=ROOT/'catalog.json'
OUTPUT=ROOT/'answers.json'
assert not OUTPUT.exists(),'Refusing to overwrite previous answers'
catalog=json.loads(CATALOG.read_text())
assert catalog['synthetic'] and catalog['frozen_before_model_run'] and len(catalog['questions'])==16
base=OpenAICompatible('qwen3.5:4b',base_url='http://127.0.0.1:11439/v1')
verified=VerifiedLocalProvider(base)
class Capture:
 def __init__(self,inner): self.inner=inner;self.calls=[];self.question_id='';self.is_local=inner.is_local;self.name=inner.name;self.model=inner.model
 def complete_json(self,messages,**kwargs):
  system=str(messages[0].get('content','')) if messages else ''
  role='second_gate' if system.startswith(satzpruefung_modell.PRAEFIX) else 'formulation'
  payload=json.dumps({'messages':messages,'kwargs':kwargs},ensure_ascii=False,sort_keys=True,separators=(',',':'))
  rec={'question_id':self.question_id,'role':role,'messages_sha256':hashlib.sha256(payload.encode()).hexdigest(),'started_at':time.time()}
  try:
   reply=self.inner.complete_json(messages,**kwargs)
   rec.update({'reply':getattr(reply,'text',''),'reply_model':getattr(reply,'model',''),'ok':True})
   return reply
  except BaseException as exc:
   rec.update({'error':type(exc).__name__+': '+str(exc),'ok':False})
   raise
  finally:
   rec['finished_at']=time.time();rec['seconds']=round(rec['finished_at']-rec['started_at'],3);self.calls.append(rec)
provider=Capture(verified)
report={'synthetic_only':True,'scope':catalog['scope'],'source_commit':catalog['source_commit'],
 'catalog_sha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
 'baseline_answers_sha256':catalog['baseline_answers_sha256'],'baseline_catalog_sha256':catalog['baseline_catalog_sha256'],
 'model':'qwen3.5:4b','second_gate':'active actual satzpruefung_modell.tor("an", verified local provider)',
 'same_model_for_generation_and_second_gate':True,'completed':False,'rows':[],'model_calls':[],'content_review':'pending independent review'}
now=datetime.fromisoformat('2026-10-09T00:00:00+00:00')
def save():
 tmp=OUTPUT.with_suffix('.new');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');tmp.replace(OUTPUT)
try:
 for index,item in enumerate(catalog['questions'],1):
  provider.question_id=item['id'];before=len(provider.calls);start=time.monotonic();belege=[];source_info=[]
  for n,src in enumerate(item['formulation_source_order'],1):
   model_text,redacted=satzantwort._bereinigt(src['body'])
   assert model_text,(item['id'],src['synthetic_source_id'],'sanitization removed all body text')
   belege.append(satzantwort.AntwortBeleg(
    nummer=n,ref=dict(src['reference']),rolle=src['role'],episode_id=src['episode_id'],
    titel=src['title'][:200],kopf=src['title'][:200],text=model_text,zeit=None,geschwaerzt=redacted,
    pruef_text='',gekuerzt=False))
   source_info.append({'id':src['synthetic_source_id'],'reference':src['reference'],'title':src['title'],
    'full_source_sha256':src['body_sha256'],'full_source_text':src['body'],'model_view_sha256':hashlib.sha256(model_text.encode()).hexdigest(),
    'model_view_text':model_text,'redacted_paragraphs':redacted,'role':src['role']})
  gate=satzpruefung_modell.tor('an',provider)
  versuch=satzantwort.formulieren(item['question'],belege,provider,jetzt=now,pruefung=gate)
  row={'id':item['id'],'question':item['question'],'baseline_status':item['baseline_status'],
   'baseline_selected_sources_in_order':item['baseline_selected_sources_in_order'],
   'baseline_shown_sources_in_order':item['baseline_shown_sources_in_order'],
   'formulation_source_order':[s['id'] for s in source_info],'full_selected_sources':source_info,
   'input_ref_order':item['baseline_persisted_ref_order'],'status':versuch.status,'fallback_reason':versuch.grund,
   'model':versuch.modell,'gate':versuch.tor.als_dict(),'accepted_sentences':[{
    'text':s.text,'raw':s.roh,'belege':list(s.belege),'first_gate_passed':s.bestanden,
    'second_gate':s.pruefmodell,'reliability':s.verlaesslichkeit,'reason':list(s.gruende)} for s in versuch.saetze],
   'rejected_sentences':[{'text':s.text,'raw':s.roh,'belege':list(s.belege),'first_gate_passed':s.bestanden,
    'second_gate':s.pruefmodell,'reason':list(s.gruende)} for s in versuch.verworfen],
   'calls_for_question':provider.calls[before:],'seconds':round(time.monotonic()-start,3)}
  report['rows'].append(row);report['model_calls'].extend(provider.calls[before:]);save()
  print(item['id'],versuch.status,'accepted',len(versuch.saetze),'rejected',len(versuch.verworfen),'calls',len(provider.calls)-before,flush=True)
  if index%4==0 and index<len(catalog['questions']):
   import httpx
   with httpx.Client(trust_env=False,timeout=20) as http:
    r=http.post('http://127.0.0.1:11439/api/generate',json={'model':'qwen3.5:4b','prompt':'','keep_alive':0});r.raise_for_status()
 report['completed']=len(report['rows'])==len(catalog['questions'])
except BaseException as exc:
 report['runtime_error']=type(exc).__name__+': '+str(exc);report['traceback']=traceback.format_exc()[-5000:];raise
finally: save()
