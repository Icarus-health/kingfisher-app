"""Synthetic packaged API smoke. Fixed model outputs, no model inference/network."""
import json,tempfile
from pathlib import Path
from icarus_memory import satzantwort,working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind,EpisodeStore
from icarus_memory.model import Provenance,SourceType
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
texts=[('Prüfprotokoll P-24','Das Prüfprotokoll P-24 darf erst verschickt werden, wenn beide Messreihen unterschrieben sind; eine Unterschrift fehlt.'),
 ('Versand P-42','Bei P-42 darf Material erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden. Die Freigabe liegt noch nicht vor.')]
class Synthetic:
 is_local=True;name='synthetic';model='synthetic'
 def __init__(self,partial):self.partial=partial
 def complete_json(self,messages,**kwargs):
  user=json.loads(messages[-1]['content'])
  if satzantwort.ist_satzanfrage(messages):
   first=next(b['nr'] for b in user['belege'] if 'P-24' in b['quelle']);second=next(b['nr'] for b in user['belege'] if 'P-42' in b['quelle'])
   result={'status':'antwort','saetze':[
    {'text':'Das Prüfprotokoll P-24 darf erst verschickt werden, wenn beide Messreihen unterschrieben sind.','belege':[first]},
    {'text':('Bei P-42 darf Material erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden.' if self.partial else 'Die Freigabe liegt noch nicht vor.'),'belege':[second]}]}
  else:result={'status':'source_reports','ids':[s['id'] for s in user['sources']]}
  return Reply(text=json.dumps(result))
with tempfile.TemporaryDirectory() as directory:
 episodes=EpisodeStore(Path(directory)/'e.sqlite3');claims=ClaimStore(Path(directory)/'c.sqlite3');ids=[]
 try:
  for title,text in texts:
   episode,_=episodes.record(EpisodeKind.DOCUMENT,title,text,Provenance(SourceType.DOCUMENT));ids.append(episode.id)
   assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),[{'start':0,'end':len(text),'kind':'fact'}],model='synthetic')
  question='Welche Freigabe braucht das Material P-42 und welche Unterschrift braucht das Prüfprotokoll P-24?'
  partial=answers.prepare(question,episodes,claims,Synthetic(True),saetze=True)
  assert partial['satzantwort']['status']=='zitate' and partial['satzantwort']['verworfen']==1
  complete=answers.prepare(question,episodes,claims,Synthetic(False),saetze=True)
  assert complete['satzantwort']['status']=='saetze'
  saved=json.loads(json.dumps(complete));second=next(b['nummer'] for b in saved['satzantwort']['belege'] if b['ref']['episode_id']==ids[1])
  saved['satzantwort']['saetze']=[s for s in saved['satzantwort']['saetze'] if second not in s['belege']];saved['satzantwort']['verworfen']=1
  for answer in (partial,saved):
   text,links,status=answers.render(answer,episodes,claims)
   assert all(body in text for _,body in texts) and set(ids)<={l['episode_id'] for l in links}
   assert answers.satz_struktur(answer,episodes,claims) is None
  episodes.ignore(ids[1]);text,links,status=answers.render(saved,episodes,claims)
  assert status=='working_unavailable' and not links and texts[1][1] not in text
  print('Packaged source-loss fallback: new answer, JSON-restored answer, source withdrawal passed; no inference.')
 finally:claims.close();episodes.close()
