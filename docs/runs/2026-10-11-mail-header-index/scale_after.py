from pathlib import Path
import json,sqlite3,time,hashlib
from types import SimpleNamespace
from datetime import datetime,timedelta
from icarus_memory.episodes import EpisodeStore
from icarus_memory.model import Provenance,SourceType
from icarus_memory.task_source_review import review_tasks
before=json.loads(Path('/private/tmp/kingfisher-task-thread-scale-before-20261011.json').read_text())
path=Path(before['root'])/'episodes.sqlite3'
def snapshot(conn):
 h=hashlib.sha256();n=0
 for row in conn.execute('SELECT * FROM episodes ORDER BY id'):
  h.update(json.dumps(tuple(row),separators=(',',':')).encode());n+=1
 return {'rows':n,'rows_sha256':h.hexdigest()}
conn=sqlite3.connect(path);old=snapshot(conn);old_version=conn.execute('PRAGMA user_version').fetchone()[0];assert old_version==21;conn.close()
start=time.perf_counter();store=EpisodeStore(path);startup=time.perf_counter()-start
assert snapshot(store._conn)==old
source=store._conn.execute("SELECT id,recorded_at FROM episodes WHERE json_extract(document,'$.provenance.source_ref')='synthetic:<original@scale>'").fetchone()
reply=store._conn.execute("SELECT id FROM episodes WHERE json_extract(document,'$.provenance.source_ref')='synthetic:<reply@scale>'").fetchone()
task=SimpleNamespace(id='synthetic-task',status='open',created_at=datetime.fromisoformat(source['recorded_at'])+timedelta(hours=1),provenance=Provenance(SourceType.USER_STATED,source_ref='episode:'+source['id']))
durations=[]
for _ in range(3):
 start=time.perf_counter();result=review_tasks(store,[task]);durations.append(time.perf_counter()-start)
assert result.by_task[task.id]['followup_episode_id']==reply['id']
proof={'scope':'Same 125002 synthetic original rows before/after actual v21→v22 migration; metadata lookup, not inference or ingestion throughput','original_rows_bytewise_unchanged':True,'original_row_snapshot':old,'old_schema_version':old_version,'new_schema_version':store._conn.execute('PRAGMA user_version').fetchone()[0],'migration_and_open_seconds':startup,'lookup_seconds':durations,'exact_followup_found':True,'index_rows':store._conn.execute('SELECT count(*) FROM episode_mail_headers').fetchone()[0],'query_plan':[tuple(r) for r in store._conn.execute("EXPLAIN QUERY PLAN SELECT e.id FROM episode_mail_headers j JOIN episodes e ON e.id=j.episode_id WHERE j.value=?",('synthetic',))],'models':False,'network':False}
Path('/private/tmp/kingfisher-task-thread-scale-after-20261011.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof));store.close()
