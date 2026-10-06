from types import SimpleNamespace
from icarus_memory.connectors.mail import Message
from icarus_memory.connectors.collections import MailCollection,NamedMail
from icarus_memory.server import create_app
from fastapi.testclient import TestClient


def msg(uid='1.1',**extra):
 return Message(uid=uid,subject='Synthetic',sender='a@example.org',date=None,preview='Synthetic',unread=True,**extra)


def test_inbox_categories_are_read_only_and_account_scoped():
 app=create_app()
 class Reader:
  def inbox(self,**kwargs):return [msg(list_mail=True),msg('1.2',spam_flag=True),msg('1.3')]
 app.state.mail=MailCollection([NamedMail('one','Work',Reader()),NamedMail('two','Personal',Reader())])
 with TestClient(app) as c:
  result=c.get('/api/v1/messages?account_id=two').json()
  assert len(result['messages'])==3
  assert {m['account_id'] for m in result['messages']}=={'two'}
  assert [m['category'] for m in result['messages']]==['newsletter','spam','inbox']
  assert c.get('/api/v1/messages?account_id=missing').status_code==404


def test_pending_ai_category_does_not_leak_between_accounts():
 from icarus_memory.inbox_filter import classify_row
 settings=SimpleNamespace(mail_filter={'pending':{'x':{'account_id':'one','uid':'1.1','sender':'a@example.org','subject':'Synthetic','preview':'Synthetic','category':'spam','reason':'ai_spam'}}})
 assert classify_row(msg('one:1.1',account_id='one'),settings)['category']=='spam'
 assert classify_row(msg('two:1.1',account_id='two'),settings)['category']=='inbox'
 assert classify_row(msg('one:1.1',account_id='one',body=''),settings)['filter_reason']=='ai_spam'


def test_selected_unavailable_account_does_not_look_empty():
 class Failing:
  def inbox(self,**kwargs):raise OSError('private upstream failure')
 class Working:
  def inbox(self,**kwargs):return [msg()]
 app=create_app()
 app.state.mail=MailCollection([NamedMail('one','Work',Working()),NamedMail('two','Personal',Failing())])
 with TestClient(app) as c:
  result=c.get('/api/v1/messages?account_id=two').json()
  assert not result['messages'] and result['partial_failure']['code']=='unavailable'
  assert 'private' not in str(result)
  result=c.get('/api/v1/messages').json()
  assert len(result['messages'])==1 and result['partial_failure']['code']=='unavailable'


def test_inbox_wire_flags_and_readonly_fetch(monkeypatch):
 from icarus_memory.connectors.mail import MailConnector,MailConfig
 import imaplib
 raw=b'From: a@example.org\r\nSubject: Newsletter\r\nX-Spam-Flag: YES\r\nList-Id: news.example.org\r\n\r\nHello'
 class IMAP:
  def __init__(self,*args,**kwargs):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def login(self,*args):pass
  def select(self,folder,readonly):assert folder=='INBOX' and readonly;return 'OK',[]
  def response(self,*args):return 'UIDVALIDITY',[b'1']
  def uid(self,action,*args):
   if action=='search':return 'OK',[b'1']
   assert action=='fetch' and 'BODY.PEEK[]' in args[-1]
   assert args[0]==b'1'  # batch fetch; the inbox has one matching UID
   return 'OK',[(b'1 (UID 1 FLAGS ())',raw)]
 monkeypatch.setattr(imaplib,'IMAP4_SSL',IMAP)
 m=MailConnector(MailConfig('host','user','pass')).inbox()[0]
 assert m.spam_flag and m.list_mail and not m.body
