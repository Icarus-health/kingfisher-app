"""Synthetic controlled prompt/schema experiment; no product mutations."""
import os,sys,json,time,copy,hashlib
from pathlib import Path
from types import SimpleNamespace
REPO=Path(sys.argv[1]).resolve();ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO/'sidecar'),str(REPO/'scripts')]
from icarus_memory import EpisodeStore,EpisodeKind,Provenance,SourceType
from icarus_memory.memory_categories import Categories,_interpret_quotes,_interpret
from probe_working_memory_end_to_end import local_provider,Meter
p=REPO/'docs/evaluations/memory-quality/retrieval-controls/catalog-20261008.json';catalog=json.loads(p.read_text());assert catalog['synthetic']
catalog['sources'].extend([{'id':'H01','title':'Unicode-Einbettung','text':'🐦 Notiz: Lene Kühn prüft den Entwurf.'},{'id':'H02','title':'Zwei Personen','text':'Nachricht: Vera Noll liefert, Veit Noll prüft.'},{'id':'H03','title':'Servicepostfach','text':'Kundenservice support@example.invalid bestätigt den Eingang.'},{'id':'H04','title':'Person neben Service','text':'Vera Noll schreibt über support@example.invalid an den Kundenservice.'}])
(ROOT/'holdout-sources.json').write_text(json.dumps(catalog['sources'][-4:],ensure_ascii=False,indent=2)+'\n')
provider=Meter(local_provider('qwen3.5:4b','http://127.0.0.1:11439/v1'))
report={'synthetic_only':True,'scope':'scratch prompt/schema controls; not product dispatch','catalog_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':[],'completed':False}
episodes=EpisodeStore(ROOT/'episodes.sqlite3');taxonomy=Categories(episodes).taxonomy()['items']
clarification='''Zwei getrennte Prüfungen: (1) Suche ausdrücklich benannte Menschen, Organisationen, Projekte und Orte im Original. Übernimm jeden eindeutig belegten Eigennamen als Entität; eine fehlende Zuordnung zu einer Kategorie ist kein Grund, den Namen wegzulassen. Die Liste entities darf nur leer sein, wenn im Original keine solche eindeutig belegte Erwähnung steht. (2) Schlage danach passende Themen vor. Eine bloße Funktion oder ein allgemeines Servicepostfach ist kein Personenname. Nutze weiterhin ausschließlich exakte Originalbelege, keine Ergänzung oder Identitätsverschmelzung.\n'''
class Control:
 is_local=True;name=model='synthetic-local-control'
 def __init__(self,arm):self.arm=arm
 def complete_json(self,messages,**kwargs):
  messages=copy.deepcopy(messages);kwargs=copy.deepcopy(kwargs)
  if self.arm in {'clarified','both','clarified_absolute'}:messages[0]['content']=clarification+messages[0]['content']
  if self.arm in {'reordered','both','reordered_absolute'}:
   schema=kwargs['schema'];schema['properties']={'entities':schema['properties']['entities'],'categories':schema['properties']['categories']};schema['required']=['entities','categories']
  return provider.complete_json(messages,**kwargs)
def save():
 p=ROOT/'answers.new';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');p.replace(ROOT/'answers.json')
try:
 for arm in ('reordered_absolute','reordered'):
  for source in catalog['sources']:

   episode,_=episodes.record(EpisodeKind.DOCUMENT,source['title'],source['text'],Provenance(SourceType.CHAT,source_ref='synthetic:'+source['id']))
   before=provider.calls;start=time.monotonic();control=Control(arm)
   try:
    topics,entities=(_interpret(control,episode,taxonomy) if arm=='reordered_absolute' else _interpret_quotes(control,episode,taxonomy,SimpleNamespace(permits=lambda p,e:p is control and e.id==episode.id)))
    row={'id':source['id'],'arm':arm,'ok':True,'entities':[{'kind':k,'quote':episode.body[s:e],'start':s,'end':e,'role':r} for k,s,e,r in entities]}
   except Exception as exc:row={'id':source['id'],'arm':arm,'ok':False,'error':type(exc).__name__+': '+str(exc)}
   row.update(seconds=round(time.monotonic()-start,3),model_outputs=provider.outputs(before));report['rows'].append(row);save();print(arm,source['id'],row['ok'],row.get('entities'),flush=True)
 report['completed']=True
finally:save();episodes.close()
