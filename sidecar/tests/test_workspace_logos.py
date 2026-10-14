import base64
import pytest
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.server import create_app


def test_logo_needs_opt_in_and_confirmation_and_is_locally_cached(tmp_path,monkeypatch):
    from icarus_memory import workspace_logos
    monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
    app=create_app(SelfModelStore(MemoryBackend(),subject_id='test'))
    client=TestClient(app)
    calls=[]
    def fetch(domain):
        calls.append(domain)
        return 'data:image/png;base64,'+base64.b64encode(b'\x89PNG\r\n\x1a\nsynthetic').decode()
    monkeypatch.setattr(workspace_logos,'fetch_logo',fetch)
    payload={'domain':'example.com','revision':0}
    assert client.post('/api/v1/workspace-logos/org-test',json=payload).status_code==403
    assert calls==[]
    assert client.put('/api/v1/workspace-view/preferences/online',json={'revision':0,'data':{'logos':True,'maps':False}}).status_code==200
    result=client.post('/api/v1/workspace-logos/org-test',json=payload)
    assert result.status_code==200,result.text
    assert result.json()['data']['domain']=='example.com'
    assert client.get('/api/v1/workspace-view/organisation_logo/org-test').json()==result.json()
    assert calls==['example.com']
    overview=client.get('/api/v1/workspace-view').json()
    assert 'data_url' not in str(overview)


def test_internal_address_and_credential_urls_are_rejected_before_http(monkeypatch):
    from icarus_memory.workspace_logos import normalize_domain, public_ip
    import socket
    for text in ('127.0.0.1','localhost','user:pass@example.com','https://example.com/path','example.com:443'):
        with pytest.raises(ValueError): normalize_domain(text)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError): public_ip('example.com')
