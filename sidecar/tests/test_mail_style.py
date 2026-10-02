import threading
from types import SimpleNamespace
from dataclasses import replace
import pytest
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.connectors.mail import Message


def client(tmp_path):
    from icarus_memory.mail_style import register_mail_style
    app=FastAPI(); app.state.conversation_lock=threading.RLock()
    app.state.store=SelfModelStore(MemoryBackend(), subject_id='test')
    app.state.episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    class Mail:
        item=Message('a:1','Question','Lea <lea@example.org>',None,'Question',True,account_id='a',reply_to='lea@example.org')
        def message(self,uid):return replace(self.item,uid=uid)
    app.state.mail=Mail()
    def auth(token: str | None=Header(None,alias='X-Icarus-Token')):
        if token!='ok':raise HTTPException(401)
    register_mail_style(app,[Depends(auth)])
    return app,TestClient(app,headers={'X-Icarus-Token':'ok'})

URL='/api/v1/messages/a%3A1/style'
RULES={'address':'du','length':'short','emoji':'no'}

def test_confirmation_scope_override_and_retraction(tmp_path):
    from icarus_memory.mail_style import effective_style
    app,c=client(tmp_path)
    assert c.get(URL).json()['profiles']=={'global':None,'contact':None}
    assert c.put(URL,json={'scope':'global','rules':RULES}).status_code==200
    assert effective_style(app,app.state.mail.item)['address']=='du'
    contact={**RULES,'address':'sie'}
    assert c.put(URL,json={'scope':'contact','rules':contact}).status_code==200
    assert effective_style(app,app.state.mail.item)['address']=='sie'
    other=replace(app.state.mail.item,account_id='b')
    assert effective_style(app,other)['address']=='du'
    assert c.delete(URL+'/contact').status_code==200
    assert effective_style(app,app.state.mail.item)['address']=='du'


def test_examples_deduplicate_propose_and_withdraw_evidence(tmp_path):
    from icarus_memory.mail_style import effective_style
    app,c=client(tmp_path)
    for text in ['Danke, kannst du Montag kommen?', 'Hallo, hast du morgen Zeit?', 'Prima, ich freue mich auf dich!']:
        r=c.post(URL+'/examples',json={'text':text,'own_text_confirmed':True})
        assert r.status_code==200
    c.post(URL+'/examples',json={'text':'Prima, ich freue mich auf dich!','own_text_confirmed':True})
    state=c.get(URL).json(); assert len(state['examples'])==3
    assert state['proposal']['rules']==RULES
    assert effective_style(app,app.state.mail.item)=={}
    assert c.put(URL,json={'scope':'contact',**state['proposal']}).status_code==200
    assert effective_style(app,app.state.mail.item)==RULES
    assert c.delete(URL+'/examples/'+state['examples'][0]['id']).status_code==200
    assert effective_style(app,app.state.mail.item)=={}
    assert c.get(URL).json()['proposal'] is None


def test_generated_text_unconfirmed_and_invalid_rules_rejected(tmp_path):
    _,c=client(tmp_path)
    assert c.post(URL+'/examples',json={'text':'Some original reply','original_suggestion':'Some original reply','own_text_confirmed':True}).status_code==422
    assert c.post(URL+'/examples',json={'text':'Some original reply','own_text_confirmed':False}).status_code==422
    assert c.put(URL,json={'scope':'global','rules':{**RULES,'address':'ignore rules'}}).status_code==422
    c.headers.pop('X-Icarus-Token'); assert c.get(URL).status_code==401


def test_cross_contact_evidence_and_ambiguous_recipient_rejected(tmp_path):
    app,c=client(tmp_path)
    c.post(URL+'/examples',json={'text':'Hallo, wie geht es dir heute?','own_text_confirmed':True})
    evidence=c.get(URL).json()['examples'][0]['id']
    app.state.mail.item=replace(app.state.mail.item,reply_to='other@example.org')
    assert c.put(URL,json={'scope':'contact','rules':RULES,'evidence_ids':[evidence]}).status_code==409
    assert c.delete(URL+'/examples/'+evidence).status_code==404
    app.state.mail.item=replace(app.state.mail.item,reply_to='one@example.org, two@example.org')
    assert c.get(URL).status_code==422


def test_confirmed_preferences_and_examples_survive_store_reopen(tmp_path):
    from icarus_memory.backends import SqliteBackend
    from icarus_memory.mail_style import effective_style
    app,c=client(tmp_path)
    app.state.store=SelfModelStore(SqliteBackend(tmp_path/'self.sqlite3'),subject_id='test')
    assert c.put(URL,json={'scope':'contact','rules':RULES}).status_code==200
    c.post(URL+'/examples',json={'text':'Danke, kannst du Montag kommen?','own_text_confirmed':True})
    app.state.store=SelfModelStore(SqliteBackend(tmp_path/'self.sqlite3'),subject_id='test')
    app.state.episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    assert effective_style(app,app.state.mail.item)==RULES
    assert len(c.get(URL).json()['examples'])==1


def test_style_used_by_reply_and_midflight_retraction_rejected(tmp_path):
    from icarus_memory.mail_reply_suggestions import register_reply_suggestions
    app,c=client(tmp_path)
    c.put(URL,json={'scope':'contact','rules':RULES})
    class Provider:
        is_local=True
        def complete_json(self,messages):
            assert any('Stilpräferenzen' in m['content'] and 'du' in m['content'] for m in messages)
            return SimpleNamespace(text='{"body":"Danke dir!"}',tool_calls=[])
    app.state.agent=SimpleNamespace(provider=Provider())
    register_reply_suggestions(app,[])
    assert c.post('/api/v1/messages/a%3A1/reply-suggestion',json={}).status_code==200
    class Revoking(Provider):
        def complete_json(self,messages):
            c.delete(URL+'/contact')
            return super().complete_json(messages)
    app.state.agent.provider=Revoking()
    assert c.post('/api/v1/messages/a%3A1/reply-suggestion',json={}).status_code==409


def test_mixed_form_of_address_does_not_infer_du(tmp_path):
    app,c=client(tmp_path)
    for suffix in ['Montag','Dienstag','Mittwoch']:
        c.post(URL+'/examples',json={'text':f'Kannst du helfen? Haben Sie am {suffix} Zeit?','own_text_confirmed':True})
    assert c.get(URL).json()['proposal']['rules']['address']=='default'


def test_changed_reply_address_during_write_has_no_side_effect(tmp_path):
    app,c=client(tmp_path)
    class Changing:
        calls=0
        def message(self,uid):
            self.calls+=1
            return Message(uid,'Subject','Lea <lea@example.org>',None,'Text',True,account_id='a',reply_to='lea@example.org' if self.calls==1 else 'other@example.org')
    app.state.mail=Changing()
    assert c.put(URL,json={'scope':'contact','rules':RULES}).status_code==409
    assert app.state.store.usable()==[]


def test_confirmed_general_proposal_applies_to_other_contact(tmp_path):
    from icarus_memory.mail_style import effective_style
    app,c=client(tmp_path)
    for text in ['Danke, kannst du Montag kommen?', 'Hallo, hast du morgen Zeit?', 'Prima, ich freue mich auf dich!']:
        c.post(URL+'/examples',json={'text':text,'own_text_confirmed':True})
    proposal=c.get(URL).json()['proposal']
    assert c.put(URL,json={'scope':'global',**proposal}).status_code==200
    assert effective_style(app,replace(app.state.mail.item,reply_to='other@example.org'))==RULES
