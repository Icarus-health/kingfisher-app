from backend import app, root
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.mail_timeline import thread_tags
import json
now=datetime.now(timezone.utc)
account='synthetic-acct'
def record(mid, text, refs, captured):
    tags=thread_tags(SimpleNamespace(account_id=account,message_id=mid,in_reply_to='',references=refs))
    return app.state.episodes.record(EpisodeKind.MESSAGE,'Künstlicher Testverlauf',text,
        Provenance(source_type=SourceType.EMAIL,source_ref=account+':'+mid,captured_at=captured),
        occurred_at=now-timedelta(days=50),tags=tags,at=captured)[0]
initial=record('<initial@test>','Bitte den künstlichen Testbericht prüfen.',(),now-timedelta(hours=2))
task=app.state.tasks.add('Künstlichen Testbericht prüfen',
    Provenance(source_type=SourceType.EMAIL,source_ref='episode:'+initial.id,verbatim=initial.body),
    at=now-timedelta(hours=1))
reply=record('<reply@test>','Absage: Der künstliche Testauftrag entfällt.',('<initial@test>',),now-timedelta(minutes=20))
proof={'task_id':task.id,'initial_episode_id':initial.id,'reply_episode_id':reply.id,'task_before':task.to_dict(),'scope':'Synthetic source and confirmed task; no model or account access'}
(root/'task-seed.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k!='task_before'}))
