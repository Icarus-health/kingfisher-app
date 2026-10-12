from pathlib import Path
import sys,json,time,hashlib,tempfile
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from icarus_memory.episodes import EpisodeStore,EpisodeKind
from icarus_memory.model import Provenance,SourceType
from icarus_memory.mail_timeline import thread_tags
from icarus_memory.task_source_review import review_tasks
root=Path(tempfile.mkdtemp(prefix='kingfisher-thread-scale-',dir='/private/tmp'))
store=EpisodeStore(root/'episodes.sqlite3');now=datetime.now(timezone.utc)
def record(mid,refs,at):
 return store.record(EpisodeKind.MESSAGE,'Synthetic mail','Synthetic message only '+mid,Provenance(SourceType.EMAIL,source_ref='synthetic:'+mid),at=at,occurred_at=now-timedelta(days=30),tags=thread_tags(SimpleNamespace(account_id='synthetic',message_id=mid,references=refs,in_reply_to='')))[0]
original=record('<original@scale>',(),now-timedelta(hours=2))
followup=record('<reply@scale>',('<original@scale>',),now-timedelta(minutes=5))
task=SimpleNamespace(id='synthetic-task',status='open',created_at=now-timedelta(hours=1),provenance=Provenance(SourceType.USER_STATED,source_ref='episode:'+original.id))
assert original.id != followup.id
base=original.to_dict();body='Künstliche unverbundene Nachricht. '+('x'*512);base.update(body=body,title='Synthetic unrelated',tags=[],id='',digest='')
query='INSERT INTO episodes (id,digest,kind,state,recorded_at,occurred_at,project_id,title,body,document) VALUES (?,?,?,?,?,?,?,?,?,?)'
report={'scope':'Metadata lookup only; valid synthetic Episode documents bulk inserted, not normal ingestion throughput','root':str(root),'models':False,'network':False,'results':[]}
previous=0
for size in (100,10000,50000,125000):
 rows=[]
 for i in range(previous,size):
  own=hashlib.sha256(('synthetic\0<unrelated-'+str(i)+'@scale>').encode()).hexdigest();doc={**base,'id':'synthetic-'+str(i),'digest':'synthetic-digest-'+str(i),'tags':['mail:message:'+own]}
  rows.append((doc['id'],doc['digest'],doc['kind'],doc['state'],doc['recorded_at'],doc['occurred_at'],None,doc['title'],doc['body'],json.dumps(doc)))
 with store._conn:store._conn.executemany(query,rows)
 previous=size;durations=[]
 for _ in range(2):
  start=time.perf_counter();result=review_tasks(store,[task]);durations.append(time.perf_counter()-start)
 correct=result.by_task.get(task.id,{}).get('followup_episode_id')==followup.id
 report['results'].append({'unrelated_mail_rows':size,'seconds':durations,'exact_followup_found':correct,'result':result.by_task.get(task.id),'coverage_limited':result.coverage_limited})
 print(json.dumps(report['results'][-1]),flush=True)
Path('/private/tmp/kingfisher-task-thread-scale-before-20261011.json').write_text(json.dumps(report,indent=2)+'\n')
store._conn.close()
