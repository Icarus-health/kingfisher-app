"""Scratch diagnostic of the existing exact-quote interpreter on synthetic local data.
Calls the interpreter directly with an explicit synthetic-only policy; this is
NOT proof that the normal product permits or selects local quote mode yet.
"""
import os,sys,json,time,hashlib
from pathlib import Path
from types import SimpleNamespace
REPO=Path(sys.argv[1]).resolve();ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO/'sidecar'),str(REPO/'scripts')]
from icarus_memory import EpisodeStore,EpisodeKind,Provenance,SourceType
from icarus_memory.memory_categories import Categories,_interpret_quotes
from probe_working_memory_end_to_end import local_provider,Meter
catalog_path=REPO/'docs/evaluations/memory-quality/retrieval-controls/catalog-20261008.json';catalog=json.loads(catalog_path.read_text());assert catalog['synthetic']
provider=Meter(local_provider('qwen3.5:4b','http://127.0.0.1:11439/v1'))
report={'synthetic_only':True,'scope':'direct existing quote interpreter; not normal product dispatch','catalog_sha256':hashlib.sha256(catalog_path.read_bytes()).hexdigest(),'rows':[],'completed':False}
episodes=EpisodeStore(ROOT/'episodes.sqlite3');taxonomy=Categories(episodes).taxonomy()['items']
def save():
 p=ROOT/'answers.new';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');p.replace(ROOT/'answers.json')
try:
 for source in catalog['sources']:
  episode,_=episodes.record(EpisodeKind.DOCUMENT,source['title'],source['text'],Provenance(SourceType.CHAT,source_ref='synthetic:'+source['id']))
  before=provider.calls;start=time.monotonic()
  try:
   topics,entities=_interpret_quotes(provider,episode,taxonomy,SimpleNamespace(permits=lambda p,e:p is provider and e.id==episode.id))
   row={'id':source['id'],'ok':True,'topics':topics,'entities':[{'kind':kind,'quote':episode.body[start:end],'start':start,'end':end,'role':role} for kind,start,end,role in entities]}
  except Exception as exc:row={'id':source['id'],'ok':False,'error':type(exc).__name__+': '+str(exc)}
  row.update(model_outputs=provider.outputs(before),seconds=round(time.monotonic()-start,3));report['rows'].append(row);save();print(source['id'],row['ok'],row.get('entities'),flush=True)
 report['completed']=True
finally:save();episodes.close()
