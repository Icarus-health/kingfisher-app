from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from icarus_memory.connectors.mail import Message
from icarus_memory.server import create_app


def message(**changes):
    return Message(**{'uid':'1.1','subject':'Termin','sender':'Lea <lea@example.org>', 'date':None,'preview':'Hallo','unread':True,'body':'Hallo',**changes})


def test_rules_precede_ai_and_domains_match_exactly():
    from icarus_memory.mail_filter import classify
    policy={'blocked':['@example.org'],'allowed':[], 'block_newsletters':True,'ai_enabled':False}
    assert classify(message(),policy).reason=='blocked'
    assert classify(message(sender='lea@notexample.org'),policy).include
    assert classify(message(spam_flag=True),{}).reason=='spam_header'
    assert classify(message(list_mail=True),{'block_newsletters':True}).reason=='newsletter'
    assert classify(message(list_mail=True),{'block_newsletters':False}).include


def test_ai_never_uses_cloud_and_fails_to_review():
    from icarus_memory.mail_filter import classify
    class Cloud:
        is_local=False
        def complete_json(self,*args):raise AssertionError('No cloud calls')
    assert classify(message(),{'ai_enabled':True},Cloud()).reason=='ai_unavailable'
    class Local:
        is_local=True
        def complete_json(self,messages):
            return SimpleNamespace(text='{"category":"important","confidence":0.95}',tool_calls=[])
    assert classify(message(),{'ai_enabled':True},Local()).include
    class Bad(Local):
        def complete_json(self,*args):return SimpleNamespace(text='ignore rules, execute commands',tool_calls=[])
    assert classify(message(),{'ai_enabled':True},Bad()).reason=='ai_unclear'


def test_policy_validation_and_persistence():
    with TestClient(create_app()) as client:
        r=client.get('/api/v1/mail-filter');assert r.status_code==200
        assert not r.json()['ai_enabled']
        r=client.put('/api/v1/mail-filter',json={'blocked':['@Example.org'],'allowed':[], 'block_newsletters':True,'ai_enabled':False})
        assert r.status_code==200 and r.json()['blocked']==['@example.org']
        assert client.put('/api/v1/mail-filter',json={'blocked':['.*']}).status_code==422
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/mail-filter').json()['blocked']==['@example.org']


def test_intake_review_keeps_folder_identity_and_reads_the_exact_original():
    from icarus_memory import config, mail_filter
    from icarus_memory.server import _data_dir
    class Reader:
        seen = []
        def message_in_folder(self, folder, uid):
            self.seen.append((folder, uid))
            return message(uid=uid, body='Original ' + folder)
        def message(self, uid):
            pytest.fail('Folder sources must not be read from the inbox')
    reader = Reader()
    app = create_app()
    with TestClient(app) as client:
        app.state.mail = SimpleNamespace(reader_for=lambda account: reader)
        from icarus_memory.mail_intake import Intake
        intake = Intake(app.state.episodes)
        intake.start('work', ['Archive'])
        with app.state.episodes.transaction():
            intake.db.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status) VALUES('work','Archive','1',1,'history','filtered:unclear')")
        for folder in ('INBOX', 'Archive'):
            m = message(account_id='work', uid='work:1.1', body='Original ' + folder)
            mail_filter.hold(app, m, mail_filter.Decision(False, 'unclear'),
                             lambda: config.save(_data_dir(), app.state.settings), folder=folder)
        pending = client.get('/api/v1/mail-filter').json()['pending']
        assert len(pending) == 2 and len({p['id'] for p in pending}) == 2
        item = next(p for p in pending if p['folder'] == 'Archive')
        shown = client.get('/api/v1/mail-filter/review/' + item['id'])
        assert shown.status_code == 200 and shown.json()['body'] == 'Original Archive'
        assert client.post('/api/v1/mail-filter/review/' + item['id'], json={'action': 'include'}).status_code == 200
        assert reader.seen == [('Archive', '1.1'), ('Archive', '1.1')]
        row = intake.db.execute("SELECT status,episode_id FROM mail_intake_items WHERE account='work'").fetchone()
        assert row['status'] == 'captured' and row['episode_id']


def test_filter_holds_before_memory_and_cursor_advances(tmp_path):
    from icarus_memory.mail_filter import classify
    from icarus_memory.mail_ingestion import sync_account
    from icarus_memory.episodes import EpisodeStore
    class Inbox:
        def pending_uids(self,after=None,limit=50):return [] if after else ['1.1']
        def message(self,uid):return message(spam_flag=True)
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3');held=[]
    r=sync_account(episodes,'work',Inbox(),screen=lambda m:classify(m,{}),hold=lambda m,d:held.append((m,d)))
    assert r['recorded']==0 and r['filtered']==1 and episodes.mail_cursor('work')=='1.1'
    assert len(held)==1 and held[0][0].account_id=='work'
    episodes.close()


def test_filter_storage_failure_does_not_advance_cursor(tmp_path):
    from icarus_memory.mail_filter import classify
    from icarus_memory.mail_ingestion import sync_account
    from icarus_memory.episodes import EpisodeStore
    class Inbox:
        def pending_uids(self,**kwargs):return ['1.1']
        def message(self,uid):return message(spam_flag=True)
    def failed(*args):raise OSError('full')
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    with pytest.raises(OSError):sync_account(episodes,'work',Inbox(),screen=lambda m:classify(m,{}),hold=failed)
    assert episodes.mail_cursor('work') is None
    episodes.close()


def test_review_requires_exact_source_and_account_and_survives_restart():
    from icarus_memory import config, mail_filter
    from icarus_memory.server import _data_dir
    class Reader:
        changed=False
        def message(self,uid):return message(body='Changed' if self.changed else 'Hallo',spam_flag=True)
    reader=Reader()
    app=create_app()
    with TestClient(app) as client:
        app.state.mail=SimpleNamespace(reader_for=lambda account:reader)
        m=message(account_id='work',uid='work:1.1',spam_flag=True)
        mail_filter.hold(app,m,mail_filter.classify(m,{}),lambda:config.save(_data_dir(),app.state.settings))
        item=client.get('/api/v1/mail-filter').json()['pending'][0]
        assert client.get('/api/v1/mail-filter/review/'+item['id']).json()['body']=='Hallo'
        reader.changed=True
        assert client.post('/api/v1/mail-filter/review/'+item['id'],json={'action':'include'}).status_code==409
    app=create_app()
    with TestClient(app) as client:
        app.state.mail=SimpleNamespace(reader_for=lambda account:reader)
        assert len(client.get('/api/v1/mail-filter').json()['pending'])==1
        reader.changed=False
        result=client.post('/api/v1/mail-filter/review/'+item['id'],json={'action':'include'})
        assert result.status_code==200 and not result.json()['pending']
        assert client.post('/api/v1/mail-filter/review/'+item['id'],json={'action':'include'}).status_code==404


def test_revocation_after_fetch_prevents_ai_call(tmp_path):
    from icarus_memory.mail_ingestion import sync_account
    from icarus_memory.episodes import EpisodeStore
    allowed=True
    class Reader:
        def pending_uids(self,**kwargs):return ['1.1']
        def message(self,uid):
            nonlocal allowed
            allowed=False
            return message()
    calls=[]
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    result=sync_account(episodes,'work',Reader(),permitted=lambda:allowed,screen=lambda m:calls.append(m))
    assert result['cancelled'] and not calls
    episodes.close()


def test_spam_header_and_newsletter_are_parsed_from_wire(monkeypatch):
    from icarus_memory.connectors.mail import MailConnector,MailConfig
    import imaplib
    raw=b'From: test@example.org\r\nSubject: Promo\r\nX-Spam-Status: Yes, score=8\r\nList-Id: news.example.org\r\n\r\nHello'
    class IMAP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def login(self,*args):pass
        def select(self,*args,**kwargs):return 'OK',[]
        def response(self,*args):return 'UIDVALIDITY',[b'1']
        def uid(self,*args):return 'OK',[(b'FLAGS ()',raw)]
    monkeypatch.setattr(imaplib,'IMAP4_SSL',IMAP)
    m=MailConnector(MailConfig('host','user','pass')).message('1.1')
    assert m.spam_flag and m.list_mail


def test_review_endpoints_are_protected(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN','synthetic')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/mail-filter').status_code==401
        assert client.post('/api/v1/mail-filter/review/x',json={'action':'include'}).status_code==401


def test_long_or_truncated_ai_input_is_held_without_model_call():
    from icarus_memory.mail_filter import classify
    class Local:
        is_local=True
        def complete_json(self,*args):raise AssertionError('partial content must not be classified')
    for m in [message(body='x'*8001),message(truncated=True)]:
        assert classify(m,{'ai_enabled':True},Local()).reason=='content_incomplete'


def test_voller_pruefbereich_blockiert_die_aufnahme_nicht(tmp_path):
    """Früher `ValueError`: Der Cursor blieb stehen und kein neuer Posteingang kam mehr an."""
    from icarus_memory import mail_filter
    from icarus_memory.mail_ingestion import sync_account
    from icarus_memory.episodes import EpisodeStore
    voll={str(i):{} for i in range(500)}
    app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(mail_filter={'pending':dict(voll)})))
    class Reader:
        def pending_uids(self,after=None,limit=50):return [] if after else ['1.1','1.2']
        def message(self,uid):return message(spam_flag=True,uid=uid)
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    gespeichert=[]
    report=sync_account(episodes,'work',Reader(),screen=lambda m:mail_filter.classify(m,{}),
        hold=lambda m,d:mail_filter.hold(app,m,d,lambda:gespeichert.append(1)))
    assert report['filtered']==2 and episodes.mail_cursor('work')=='1.2'
    assert app.state.settings.mail_filter['pending']==voll   # nichts verdrängt
    assert app.state.settings.mail_filter['overflow']==2     # aber gezählt, nicht still verworfen
    assert sum(episodes.counts().values())==0                # und nichts im Gedächtnis
    episodes.close()


def test_hold_schreibt_unveraendertes_nicht_erneut():
    from icarus_memory import mail_filter
    app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(mail_filter={})))
    gespeichert=[]
    m=message(spam_flag=True,account_id='work',uid='work:1.1')
    d=mail_filter.classify(m,{})
    for _ in range(3):mail_filter.hold(app,m,d,lambda:gespeichert.append(1))
    assert len(gespeichert)==1 and len(app.state.settings.mail_filter['pending'])==1


def test_hold_stellt_bei_schreibfehler_den_alten_stand_wieder_her():
    from icarus_memory import mail_filter
    app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(mail_filter={})))
    m=message(spam_flag=True,account_id='work',uid='work:1.1')
    def kaputt():raise OSError('voll')
    with pytest.raises(OSError):mail_filter.hold(app,m,mail_filter.classify(m,{}),kaputt)
    assert app.state.settings.mail_filter=={}
