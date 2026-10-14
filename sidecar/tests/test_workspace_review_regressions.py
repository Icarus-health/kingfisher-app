from types import SimpleNamespace
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app
from icarus_memory import conversation_memory
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_task_suggestions import source_digest


def test_project_closed_during_mail_read_cannot_receive_a_new_task(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
    app=create_app(SelfModelStore(MemoryBackend(),subject_id='test'))
    client=TestClient(app)
    project=client.post('/api/v1/projects',json={'name':'Atlas'}).json()
    message=Message(uid='work:1',account_id='work',subject='Vertrag',sender='Alex <alex@example.invalid>',date=None,preview='',unread=False,body='Bitte prüfe den Vertrag.')
    def read(uid):
        assert client.patch(f"/api/v1/projects/{project['id']}",json={'status':'done'}).status_code==200
        return message
    app.state.mail=SimpleNamespace(message=read)
    response=client.post('/api/v1/messages/work:1/task',json={'title':'Prüfen','project_id':project['id'],'source_digest':source_digest(message),'source_quote':message.body})
    assert response.status_code==409
    assert app.state.tasks.all_tasks()==[]


def test_withdrawn_chat_text_does_not_match_title_body_or_search_total(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
    app=create_app(SelfModelStore(MemoryBackend(),subject_id='test'))
    client=TestClient(app)
    text='SYNTHETIC-WITHDRAWN-SECRET'
    c=app.state.conversations.create(text)
    m=app.state.conversations.add_message(c.id,'user',text,metadata={'generated_conversation_title':True})
    source,_=conversation_memory.capture(app.state.episodes,c.id,m)
    app.state.conversations.add_message(c.id,'assistant','Antwort '+text,metadata={'conversation_source_lineage':[conversation_memory.stamp(app.state.episodes,source.id)]})
    assert client.get('/api/v1/conversations/page',params={'q':text}).json()['total']==1
    app.state.episodes.ignore(source.id)
    page=client.get('/api/v1/conversations/page',params={'q':text}).json()
    assert page['total']==0
    assert page['conversations']==[]
    assert client.get('/api/v1/conversations/page').json()['total']==1
