import copy, hashlib, json, tempfile
from pathlib import Path
from icarus_memory import EpisodeStore, EpisodeKind, Provenance, SourceType, working_memory_answers as wma, satzantwort as sa, satzpruefung_modell as spm
from icarus_memory.claims import ClaimStore
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_satzantwort import Skript
from tests.test_satzpruefung_modell import Pruefer
R='Die Klappe darf geöffnet werden.'; Q='Dies gilt ausschließlich nach schriftlicher Freigabe.'; O='Der Schalter darf umgelegt werden.'
BAD=' '.join([R,O,Q,R,Q])
out={'patch_sha256':hashlib.sha256(Path('../PATCH.diff').read_bytes()).hexdigest(),'source_1':R+' '+Q,'source_2':O,'bad_legacy_candidate':BAD}
with tempfile.TemporaryDirectory(prefix='kf-paragraph-repetition-') as temp:
 p=Path(temp); ep=EpisodeStore(p/'ep.sqlite3'); claims=ClaimStore(p/'claims.sqlite3'); wm=WorkingMemoryStore(ep); ids=[]
 for title,body in [('Klappe',R+' '+Q),('Schalter',O)]:
  source,_=ep.record(EpisodeKind.DOCUMENT,title,body,Provenance(SourceType.DOCUMENT)); ids.append(source.id)
  assert wm.commit(ep.support_snapshot(source.id),[{'start':0,'end':len(body),'kind':'conditional'}],model='synthetic')
 provider=Skript(lambda data:{'status':'antwort','saetze':[{'text':BAD,'belege':[b['nr'] for b in data['belege']]}]}); judge=Pruefer()
 answer=wma.prepare('Was gilt für Klappe und Schalter?',ep,claims,provider,saetze=True,pruefung=spm.tor('an',judge))
 saved=answer.get('satzantwort',{}); out['prepared_status']=saved.get('status'); out['prepared_text']=[s['text'] for s in saved.get('saetze',[])]; out['judge_calls']=len(judge.anfragen); out['offered']=provider.satzanfragen
 claims.close(); ep.close()
 ep=EpisodeStore(p/'ep.sqlite3'); claims=ClaimStore(p/'claims.sqlite3')
 restored=sa.wiederherstellen(saved,ep,claims); out['reopened']=restored is not None; out['reopened_text']=[s.text for s in restored.saetze] if restored else []
 ep.ignore(ids[0]); out['after_ignore']=sa.wiederherstellen(saved,ep,claims) is not None; out['original_preserved']=ep.get(ids[0]).body==R+' '+Q
 ep.close(); claims.close()
Path('/private/tmp/kingfisher-rule-paragraph-repetition-probe-20261009.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
