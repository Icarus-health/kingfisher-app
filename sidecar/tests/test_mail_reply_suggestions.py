import json
import threading
from types import SimpleNamespace
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from icarus_memory.connectors.mail import Message


def make_client(mail=None, provider=None):
    from icarus_memory.mail_reply_suggestions import register_reply_suggestions
    app = FastAPI(); app.state.conversation_lock = threading.RLock()
    app.state.mail = mail or Mail(); app.state.agent = SimpleNamespace(provider=provider or Provider())
    def auth(token: str | None = Header(default=None, alias='X-Icarus-Token')):
        if token != 'ok': raise HTTPException(401)
    register_reply_suggestions(app, [__import__('fastapi').Depends(auth)])
    return app, TestClient(app, headers={'X-Icarus-Token':'ok'})

class Mail:
    def __init__(self): self.message_calls=0; self.item=Message('a:1.1','Termin','Lea <lea@example.org>',None,'Kommst du?',True,body='Kommst du?',account_id='a',message_id='<m>')
    def message(self, uid): self.message_calls += 1; return self.item
class Provider:
    is_local=True; model='local'
    def complete_json(self, messages):
        assert 'Kommst du?' in json.dumps(messages, ensure_ascii=False)
        return SimpleNamespace(text='{"body":"Ja, gern."}', tool_calls=[])

def test_returns_draft_without_writing_memory_or_sending():
    app,c=make_client(); r=c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={'instruction':'locker bleiben'})
    assert r.status_code==200 and r.json()=={'body':'Ja, gern.','basis':'message_and_instruction',
                                             'context_token':None,'source_status':'unknown','sources':[]}
    assert app.state.mail.message_calls==2

def test_cloud_provider_and_bad_source_are_rejected_before_model():
    class Cloud(Provider):
        is_local=False
        def complete_json(self, messages): raise AssertionError('cloud called')
    _,c=make_client(provider=Cloud()); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==503
    m=Mail(); m.item=Message('a:1.1','x','x',None,'x',True,body='x',truncated=True)
    _,c=make_client(mail=m); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion').status_code==422

def test_malformed_or_tool_call_model_result_is_safe_error():
    class Bad(Provider):
        def complete_json(self, messages): return SimpleNamespace(text='not json',tool_calls=[])
    _,c=make_client(provider=Bad()); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==503
    class Tool(Provider):
        def complete_json(self, messages): return SimpleNamespace(text='{"body":"x"}',tool_calls=[{'id':'x'}])
    _,c=make_client(provider=Tool()); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==503

def test_provider_or_source_change_during_generation_rejects_result():
    class Changing(Provider):
        def complete_json(self, messages):
            app.state.agent.provider=Provider(); return SimpleNamespace(text='{"body":"x"}',tool_calls=[])
    app,c=make_client(provider=Changing()); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==409
    m=Mail(); class_change=Provider()
    class Changed(Provider):
        def complete_json(self,messages): m.item=Message('a:1.1','new','Lea',None,'new',True,body='new',account_id='a',message_id='<m>'); return SimpleNamespace(text='{"body":"x"}',tool_calls=[])
    _,c=make_client(mail=m,provider=Changed()); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==409

def test_auth_and_body_limits():
    app,c=make_client(); c.headers.pop('X-Icarus-Token')
    assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==401
    _,c=make_client(); assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={'instruction':'x'*1501}).status_code==422

def test_wrong_uid_and_revocation_during_fetch_never_reach_model():
    class Never(Provider):
        def complete_json(self,messages):raise AssertionError('No model call allowed')
    _,c=make_client(provider=Never())
    assert c.post('/api/v1/messages/other/reply-suggestion',json={}).status_code==409
    class Revoked(Mail):
        def message(self,uid):
            app.state.mail=Mail()
            return self.item
    app,c=make_client(mail=Revoked(),provider=Never())
    assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==409


def test_changed_reply_address_rejects_draft():
    from dataclasses import replace
    m=Mail()
    class Changed(Provider):
        def complete_json(self,messages):
            m.item=replace(m.item,reply_to='changed@example.org')
            return SimpleNamespace(text='{"body":"x"}',tool_calls=[])
    _,c=make_client(mail=m,provider=Changed())
    assert c.post('/api/v1/messages/a%3A1.1/reply-suggestion',json={}).status_code==409
