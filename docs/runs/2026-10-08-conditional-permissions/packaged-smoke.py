"""Fixed-output packaged memory flow; artificial data, no model/network calls."""
import json,tempfile
from pathlib import Path
from icarus_memory import satzantwort,working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind,EpisodeStore
from icarus_memory.model import Provenance,SourceType
from icarus_memory.providers import Reply
from icarus_memory.satzpruefung import Beleg,Satz,satz_pruefen
from icarus_memory.working_memory_store import WorkingMemoryStore
rule='Bei T-204 darf Material erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden.'
absence='Die Freigabe liegt noch nicht vor.'
source=rule+' '+absence
class Synthetic:
 is_local=True;name='synthetic';model='synthetic'
 def __init__(self,literal):self.literal=literal
 def complete_json(self,messages,**kwargs):
  user=json.loads(messages[-1]['content'])
  if satzantwort.ist_satzanfrage(messages):
   n=user['belege'][0]['nr']
   result={'status':'antwort','saetze':[
    {'text':rule if self.literal else 'Material aus T-204 darf erst nach schriftlicher Freigabe durch die Lagerleitung versandt werden.','belege':[n]},
    {'text':absence,'belege':[n]}]}
  else:result={'status':'source_reports','ids':[s['id'] for s in user['sources']]}
  return Reply(text=json.dumps(result))
with tempfile.TemporaryDirectory() as directory:
 episodes=EpisodeStore(Path(directory)/'e.sqlite3');claims=ClaimStore(Path(directory)/'c.sqlite3')
 try:
  episode,_=episodes.record(EpisodeKind.DOCUMENT,'Versandregel T-204',source,Provenance(SourceType.DOCUMENT))
  assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),[{'start':0,'end':len(source),'kind':'fact'}],model='synthetic')
  question='Welche Regel gilt für den Versand von Material aus T-204 und liegt die Freigabe vor?'
  partial=answers.prepare(question,episodes,claims,Synthetic(False),saetze=True)
  complete=answers.prepare(question,episodes,claims,Synthetic(True),saetze=True)
  assert partial['satzantwort']['status']=='zitate' and partial['satzantwort']['verworfen']==1
  assert complete['satzantwort']['status']=='saetze' and complete['satzantwort']['verworfen']==0
  saved=json.loads(json.dumps(complete));saved['satzantwort']['saetze']=[s for s in saved['satzantwort']['saetze'] if s['roh']==absence];saved['satzantwort']['verworfen']=1
  for answer in (partial,saved):
   text,links,status=answers.render(answer,episodes,claims)
   assert source in text and episode.id in {l['episode_id'] for l in links}
   assert answers.satz_struktur(answer,episodes,claims) is None
  for unsafe in ('Material aus T-204 darf versandt werden.','Material aus T-204 wurde versandt.','Material darf raus.','Es ist raus.'):
   assert not satz_pruefen(Satz(unsafe,('1',)),{'1':Beleg('1',source)}).bestanden
  episodes.ignore(episode.id);text,links,status=answers.render(saved,episodes,claims)
  assert status=='working_unavailable' and not links and source not in text
  print('Packaged conditional-rule flow passed: exact complete prose, rejected rule -> full original, JSON-restored partial -> original, unsupported permission/completion rejected, source withdrawal. No inference/network.')
 finally:claims.close();episodes.close()
