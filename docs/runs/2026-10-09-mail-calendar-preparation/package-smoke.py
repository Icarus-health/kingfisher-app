"""Actual packaged API, synthetic .invalid mail/provider, no lifespan/network."""
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import json,tempfile
fixture={'__name__':'mail_fixture'}
exec('#!/usr/bin/env python3\n"""Synthetic API smoke for mail-task source-version binding."""\nfrom __future__ import annotations\n\nfrom dataclasses import replace\nfrom datetime import datetime, timezone\nimport json\nimport os\nfrom pathlib import Path\nimport tempfile\nimport warnings\n\n\ndef build_case(data_dir: Path):\n    # Set the isolated directory before importing/constructing the application.\n    os.environ["ICARUS_DATA_DIR"] = str(data_dir)\n\n    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")\n    from fastapi.testclient import TestClient\n    from icarus_memory import MemoryBackend, SelfModelStore\n    from icarus_memory.agent import Agent\n    from icarus_memory.connectors.collections import MailCollection, NamedMail\n    from icarus_memory.connectors.mail import Message\n    from icarus_memory.policy import Policy\n    from icarus_memory.server import _mail_sink, create_app\n    from icarus_memory.tools import build_registry\n\n    class Mailbox:\n        def __init__(self):\n            self.item = Message(\n                uid="1",\n                subject="Synthetic source check",\n                sender="sender@example.invalid",\n                date=datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc),\n                preview="Synthetic preview.",\n                unread=True,\n                body="Synthetic original request.",\n                message_id="<smoke@example.invalid>",\n                reply_to="sender@example.invalid",\n            )\n\n        def inbox(self, **_kwargs):\n            return [self.item]\n\n        def message(self, uid):\n            if uid != "1":\n                raise RuntimeError("synthetic UID missing")\n            return self.item\n\n        def send(self, *_args, **_kwargs):\n            raise AssertionError("smoke must never send mail")\n\n    store = SelfModelStore(MemoryBackend(), subject_id="synthetic-smoke")\n    app = create_app(store)\n    mailbox = Mailbox()\n    app.state.mail = MailCollection([\n        NamedMail("work", "Synthetic", mailbox, True, "owner@example.invalid")\n    ])\n    app.state.agent = Agent(\n        store=app.state.store,\n        policy=Policy(),\n        audit=app.state.audit,\n        tools=build_registry(app.state.store, mail=app.state.mail, outward_sink=_mail_sink(app)),\n    )\n    return app, mailbox, TestClient(app)\n\n\ndef assert_counts(app, tasks: int, episodes: int):\n    assert len(app.state.tasks.all_tasks()) == tasks\n    assert len(app.state.episodes.all_episodes()) == episodes\n\n\ndef main():\n    results = []\n    with tempfile.TemporaryDirectory(prefix="kingfisher-mail-task-smoke-") as raw_dir:\n        root = Path(raw_dir)\n        for case, change in (\n            ("body", lambda item: replace(item, body="Synthetic request withdrawn.")),\n            ("date", lambda item: replace(item, date=datetime(2015, 1, 1, tzinfo=timezone.utc))),\n            ("truncated", lambda item: replace(item, truncated=True)),\n        ):\n            case_dir = root / case\n            case_dir.mkdir()\n            app, mailbox, client = build_case(case_dir)\n            opened = client.get("/api/v1/messages/work:1")\n            assert opened.status_code == 200\n            digest = opened.json()["source_digest"]\n            mailbox.item = change(mailbox.item)\n            response = client.post("/api/v1/messages/work:1/task", json={\n                "title": "Synthetic manually entered task",\n                "due": "2026-10-12T12:00:00+02:00",\n                "source_digest": digest,\n            })\n            assert response.status_code == 409, f"{case} returned {response.status_code}"\n            assert_counts(app, tasks=0, episodes=0)\n            results.append({"case": case, "http_status": response.status_code,\n                            "tasks": 0, "episodes": 0})\n\n        fresh_dir = root / "fresh"\n        fresh_dir.mkdir()\n        app, mailbox, client = build_case(fresh_dir)\n        opened = client.get("/api/v1/messages/work:1")\n        assert opened.status_code == 200\n        original_body = mailbox.item.body\n        response = client.post("/api/v1/messages/work:1/task", json={\n            "title": "Synthetic manually entered task",\n            "source_digest": opened.json()["source_digest"],\n        })\n        assert response.status_code == 201, f"fresh request returned {response.status_code}"\n        task = response.json()\n        source_ref = task["provenance"]["source_ref"]\n        assert source_ref.startswith("episode:")\n        episode = app.state.episodes.get(source_ref.removeprefix("episode:"))\n        assert episode is not None and episode.body == original_body\n        assert_counts(app, tasks=1, episodes=1)\n        results.append({"case": "fresh", "http_status": response.status_code,\n                        "tasks": 1, "episodes": 1, "source_verified": True})\n\n    print(json.dumps({"result": "pass", "cases": results}, sort_keys=True))\n\n\nif __name__ == "__main__":\n    main()\n',fixture)
build_case=fixture['build_case']

class Keys:
    def __init__(self,key,value):self.key,self.value=key,value
    def get(self,key):assert key==self.key;return self.value
class Provider:
    def __init__(self):self.writes=[];self.events={};self.allowed=False
    def calendar(self,source,key):
        assert self.allowed,'local preparation must not call calendar'
        return {'id':source.url,'accessRole':'owner'}
    def event(self,source,key,event_id):return self.events.get(event_id)
    def create(self,source,key,body,updates):
        self.writes.append(body['id']);self.events[body['id']]={**body,'etag':'"v1"'}
        return self.events[body['id']]

def setup(root):
    from icarus_memory import config
    from icarus_memory.google_oauth import SCOPES
    app,mailbox,client=build_case(root)
    mailbox.item=replace(mailbox.item,subject='Synthetic meeting',body='Am 12. Oktober 2026 von 10:00 bis 11:00 Uhr MESZ.')
    source=config.CalendarSourceSettings(id='calendar-one',label='Synthetic',kind='google',user='owner@example.invalid',url='owner@example.invalid')
    keys=Keys(config.integration_secret_name('calendar','calendar-one'),json.dumps({'client_id':'synthetic','refresh_token':'synthetic','grant_id':'synthetic-grant-one','kind':'calendar_write','scope':' '.join(SCOPES['calendar_write'])}))
    provider=Provider();actions=app.state.calendar_actions
    actions.settings=lambda:SimpleNamespace(calendar_sources=[source]);actions.oauth=SimpleNamespace(keychain=keys);actions.provider=provider
    return app,mailbox,client,provider

def prepare(client):
    opened=client.get('/api/v1/messages/work:1');assert opened.status_code==200,opened.text
    binding=opened.json()['calendar_source_digest']
    response=client.post('/api/v1/messages/work:1/calendar-preparation',json={'source_binding':binding})
    assert response.status_code==201,response.text
    return binding,response.json()

def main():
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        app,mailbox,client,provider=setup(root/'local')
        binding,record=prepare(client);path='/api/v1/mail-calendar-preparations/'+record['id']
        assert record['fields']['start']=='2026-10-12T10:00:00+02:00'
        fields={**record['fields'],'title':'Synthetic user title','end':''}
        response=client.put(path,json={'stand':record['stand'],'fields':fields,'reviewed':False})
        assert response.status_code==200,response.text
        saved=response.json()
        assert saved['origins']['title']['kind']=='user' and saved['origins']['end']['kind']=='missing'
        assert client.get(path).json()==saved
        assert prepare(client)[1]==saved
        assert not provider.writes and not app.state.tasks.all_tasks() and not app.state.episodes.all_episodes()
        results.append({'case':'persistent_partial_user_edits','result':'pass','provider_writes':0})
        for changed in ('body','date','truncated'):
            app,mailbox,client,provider=setup(root/changed)
            binding,record=prepare(client);path='/api/v1/mail-calendar-preparations/'+record['id']
            record=client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True}).json()
            mailbox.item=replace(mailbox.item,**({'body':'Meeting cancelled.'} if changed=='body' else {'date':None} if changed=='date' else {'truncated':True}))
            assert client.get(path).status_code==409
            assert client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True}).status_code==409
            assert client.post(path+'/preview',json={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}).status_code==409
            assert not provider.writes
            results.append({'case':'stale_'+changed,'result':'pass','provider_writes':0})
        app,mailbox,client,provider=setup(root/'effect')
        reader=app.state.mail
        binding,record=prepare(client);path='/api/v1/mail-calendar-preparations/'+record['id']
        record=client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True}).json()
        provider.allowed=True
        body={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}
        response=client.post(path+'/preview',json=body);assert response.status_code==201,response.text
        draft=response.json();assert client.post(path+'/preview',json=body).json()['id']==draft['id']
        url='/api/v1/calendar-actions/drafts/'+draft['id']+'/execute';payload={'confirmed':True,'stand':draft['stand']}
        response=client.post(url,json=payload);assert response.status_code==200,response.text
        assert response.json()['status']=='done'
        app.state.mail=reader # normal rebuild; fixture deliberately has no saved real accounts
        assert client.post(url,json=payload).json()['status']=='done' and len(provider.writes)==1
        mailbox.item=replace(mailbox.item,body='Meeting cancelled.')
        response=client.post(url,json=payload)
        assert response.status_code==409 and '2026-10-12T10:00' not in response.text and len(provider.writes)==1
        results.append({'case':'explicit_preview_execute_replay_then_withdrawal','result':'pass','provider_writes':1})
        app,mailbox,client,provider=setup(root/'cancel')
        mailbox.item=replace(mailbox.item,subject='Absage: Synthetic meeting')
        record=prepare(client)[1]
        assert not record['fields']['start'] and any('Absage' in w for w in record['context']['warnings'])
        results.append({'case':'subject_cancellation','result':'pass','provider_writes':0})
    print(json.dumps({'result':'pass','cases':results,'network':'none','personal_data':False,'models':False,'native_ui_verified':False}))
if __name__=='__main__':main()
