from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
import json
from icarus_memory.episodes import EpisodeStore
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_intake import Intake
from icarus_memory.mail_filter import Decision
from icarus_memory.mail_stand import konto_stand
from icarus_memory.working_memory_store import WorkingMemoryStore
class Mailbox:
    def __init__(self, count):
        self.count = count
        self.failed = set()

    def inventory_page(self, folder, after_uid=0, before_uid=None, limit=200,
                       uidvalidity=None):
        assert folder == "INBOX"
        assert uidvalidity in (None, "7")
        upper = self.count if before_uid is None else min(before_uid, self.count)
        end = min(upper, after_uid + limit)
        return {"folder": folder, "uidvalidity": "7", "upper_uid": upper,
                "uids": list(range(after_uid + 1, end + 1)),
                "next_uid": end, "done": end >= upper}

    def message_in_folder(self, folder, uid):
        assert folder == "INBOX"
        if uid in self.failed:
            raise OSError("synthetic private server response")
        return Message(uid, f"Synthetic {uid}", "QA <qa@example.test>",
                       datetime(2026, 10, 8, tzinfo=timezone.utc), "", False,
                       body=f"Synthetic original {uid}")
with TemporaryDirectory() as tmp:
    episodes=EpisodeStore(Path(tmp)/'episodes.sqlite3');intake=Intake(episodes);intake.start('qa',['INBOX'])
    reader=Mailbox(10);intake.step('qa',reader,batch=2)
    for _ in range(4):
        reader.count+=1
        intake.step('qa',reader,batch=2,screen=lambda m:Decision(int(m.uid.split('.')[1])<=10,'newsletter'))
    state=intake.status('qa');folder=state['folders'][0]
    assert (folder['captured'],folder['total'],folder['pending'],folder['filtered'],folder['live_filtered'])==(6,10,4,0,4)
    assert konto_stand('Probe',intake=state)['zustand']=='liest'
    intake.step('qa',reader,batch=10)
    reader.count=15;reader.failed={'7.15'};intake.step('qa',reader,batch=2)
    assert intake.status('qa')['folders'][0]['live_failed']==1
    intake.retry('qa');assert konto_stand('Probe',intake=intake.status('qa'))['zustand']=='liest'
    reader.failed.clear();intake.step('qa',reader,batch=10)
    assert konto_stand('Probe',intake=intake.status('qa'))['zustand']=='aktuell'
    episodes.close()
with TemporaryDirectory() as tmp:
    episodes=EpisodeStore(Path(tmp)/'episodes.sqlite3');intake=Intake(episodes);intake.start('qa',['INBOX']);reader=Mailbox(260)
    for _ in range(4):intake.step('qa',reader,batch=50)
    source=intake.step('qa',reader,batch=1)[0]
    state=intake.status('qa');assert state['history_waiting_for_analysis']
    assert konto_stand('Probe',intake=state)['zustand']=='wartet'
    assert intake.step('qa',reader,batch=10)==[]
    memory=WorkingMemoryStore(episodes);snapshot=memory.pending(episode_ids=[source])[0]
    assert memory.commit(snapshot,[{'start':0,'end':len(snapshot.episode.body),'kind':'fact'}],model='synthetic')
    assert not intake.status('qa')['history_waiting_for_analysis']
    assert intake.step('qa',reader,batch=1)
    episodes.close()
print(json.dumps({'synthetic_only':True,'history_and_live_filters_separate':True,'live_error_and_retry_visible':True,'history_wait_and_resume_verified':True,'model_calls':0}))
