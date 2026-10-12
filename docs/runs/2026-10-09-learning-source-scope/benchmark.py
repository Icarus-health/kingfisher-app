"""Nur künstliche Bestände; reine CPU/SQLite-Prüfung, ohne Modelle oder Netz."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,sys,time,tracemalloc
from icarus_memory import SqliteBackend, SelfModelStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.proposals import ProposalStore, ProposalKind, Evidence
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.habits import create_habit,check_in,list_habits
from icarus_memory.learning_service import propose_patterns
from icarus_memory.model import Kind,Provenance,SourceType
NOW=datetime(2026,9,8,12,tzinfo=timezone.utc)
mode=sys.argv[1];folder=Path(sys.argv[2]);assert str(folder).startswith('/private/tmp/kingfisher-learning-scope-20261009/')
folder.mkdir(exist_ok=True)
backend=SqliteBackend(folder/'self.sqlite3');store=SelfModelStore(backend,'synthetic')
episodes=EpisodeStore(folder/'episodes.sqlite3');proposals=ProposalStore(folder/'proposals.sqlite3');claims=ClaimStore(folder/'claims.sqlite3');service=KnowledgeService(proposals=proposals,claims=claims,episodes=episodes)
try:
 if mode=='prepare':
  h=create_habit(store,'Lesen',3)
  for day in (7,6,4):check_in(store,episodes,h.id,f'2026-09-{day:02d}',at=NOW)
  with episodes.transaction():
   for i in range(5000):episodes.record(EpisodeKind.MESSAGE,'Künstliches Archiv',f'Archiv {i} '+('Neutraler synthetischer Text. '*40),Provenance(SourceType.EMAIL),occurred_at=NOW)
  source=next(e for e in episodes.all_episodes(-1) if e.tags)
  with proposals.transaction():
   for i in range(1000):proposals.propose(ProposalKind.ASSERTION,f'Künstlicher anderer Vorschlag {i}','Nicht Lernen',assertion_kind=Kind.EPISODE,evidence=[Evidence(source.id,source.body,source.digest)],proposed_by='synthetic-mail',at=NOW)
  print(json.dumps({'episodes':5003,'unrelated_mail_sources':5000,'unrelated_proposals':1000,'real_models':False}))
 else:
  def originals():
   digest=hashlib.sha256()
   for row in episodes._conn.execute('SELECT document FROM episodes ORDER BY id'):digest.update(row[0].encode())
   return digest.hexdigest()
  before=originals();reads={'episodes':0,'proposals':0}
  def watch(obj,key):
   original=obj._from_row
   def decode(row):reads[key]+=1;return original(row)
   obj._from_row=decode
  watch(episodes,'episodes');watch(proposals,'proposals')
  tracemalloc.start();start=time.perf_counter()
  view=list_habits(store,episodes,NOW);found=propose_patterns(store,episodes,proposals,service,at=NOW)
  seconds=time.perf_counter()-start;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
  assert originals()==before and len(found)==1 and len(found[0].evidence)==3
  assert view[0]['observed_days']==['2026-09-07']
  print(json.dumps({'variant':mode,'duration_seconds':round(seconds,4),'python_peak_bytes':peak,'decoded_rows':reads,'observed_days':view[0]['observed_days'],'candidate_count':len(found),'evidence_count':len(found[0].evidence),'originals_sha256':before,'originals_unchanged':True,'models_used':False}))
finally:
 episodes.close();proposals.close();claims.close();backend.close()
