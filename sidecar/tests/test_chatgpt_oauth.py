import json
import time
import threading
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from icarus_memory.chatgpt_oauth import ChatGPTOAuth, ChatGPTError, AUTH_URL, TOKEN_URL, JWKS_URL, SCOPES


class Keys:
    available = True
    def __init__(self): self.values = {}
    def get(self, name): return self.values.get(name)
    def set(self, name, value): self.values[name] = value
    def delete(self, name): self.values.pop(name, None)


@pytest.fixture
def flow():
    keys = Keys()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid='test-key', use='sig', alg='RS256')
    calls, claims = [], {}
    token = {'access_token': 'private-access', 'refresh_token': 'private-refresh',
             'expires_in': 3600, 'scope': ' '.join(sorted(SCOPES))}
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url == JWKS_URL: return {'keys': [jwk]}
        if url == TOKEN_URL:
            if kwargs['data']['grant_type'] == 'refresh_token':
                return {**token, 'access_token': 'rotated-access', 'refresh_token': 'rotated-refresh'}
            return {**token, 'id_token': jwt.encode(claims, private, algorithm='RS256', headers={'kid':'test-key'})}
        if url.endswith('/models'):
            return {'models': [{'slug':'available-model', 'display_name':'Modell', 'visibility':'list'},
                               {'slug':'hidden-model', 'display_name':'Versteckt', 'visibility':'hide'}]}
        if url.endswith('/.well-known/openid-configuration'):
            return {'revocation_endpoint': 'https://auth.openai.com/oauth/revoke'}
        if url.endswith('/oauth/revoke'): return {}
        raise AssertionError(url)
    oauth = ChatGPTOAuth(keys, request=request)
    def begin():
        started = oauth.begin('http://127.0.0.1:8890')
        query = {k:v[0] for k,v in parse_qs(urlparse(started['url']).query).items()}
        claims.update(iss='https://auth.openai.com', aud='oaiapp_test', sub='account-one',
                      nonce=query['nonce'], exp=int(time.time())+3600, iat=int(time.time()),
                      email='synthetic@example.org', email_verified=True)
        return started, query
    return oauth, keys, calls, claims, token, begin


def connect(flow):
    oauth, _, _, _, _, begin = flow
    started, query = begin()
    oauth.callback(query['state'], 'private-code', client_id='oaiapp_test')
    return started, query


def test_pkce_one_use_and_no_inference_at_sign_in(flow):
    oauth, keys, calls, _, _, begin = flow
    started, q = begin()
    assert q['client_id'] == 'dynamic_agent_client'
    assert q['agent_name_hint'] == 'Kingfisher'
    assert q['code_challenge_method'] == 'S256' and len(q['code_challenge']) == 43
    assert q['resource'] == 'https://api.openai.com/v1'
    assert set(q['scope'].split()) == SCOPES
    oauth.callback(q['state'], 'private-code', client_id='oaiapp_test')
    assert oauth.session(started['session_id'])['status'] == 'ready'
    assert oauth.status()['plan_usage']
    assert 'private-' not in json.dumps(oauth.status())
    exchange = next(c for c in calls if c[1] == TOKEN_URL)[2]['data']
    assert exchange['client_id'] == 'oaiapp_test' and exchange['redirect_uri'] == q['redirect_uri']
    assert 'client_secret' not in exchange
    assert not any('/responses' in c[1] for c in calls)
    with pytest.raises(ChatGPTError): oauth.callback(q['state'], 'private-code', client_id='oaiapp_test')


@pytest.mark.parametrize('field,value', [('nonce','wrong'), ('aud','other-client'), ('iss','https://evil.example'),
                                       ('exp',1), ('sub','')])
def test_invalid_identity_never_saves_connection(flow, field, value):
    oauth, _, _, claims, _, begin = flow
    _, q = begin(); claims[field] = value
    with pytest.raises(ChatGPTError): oauth.callback(q['state'], 'private-code', client_id='oaiapp_test')
    assert not oauth.status()['connected']


def test_untrusted_callback_and_state_do_not_redeem_code(flow):
    oauth, _, calls, _, _, begin = flow
    for origin in ('https://example.org', 'http://localhost:8890', 'http://127.0.0.1:8890/elsewhere'):
        with pytest.raises(ChatGPTError): oauth.begin(origin)
    begin()
    with pytest.raises(ChatGPTError): oauth.callback('wrong', 'private-code', client_id='oaiapp_test')
    assert calls == []


def test_identity_only_does_not_enable_plan_usage(flow):
    oauth, _, _, _, token, _ = flow
    token['scope'] = 'openid profile email'
    connect(flow)
    assert oauth.status()['connected'] and not oauth.status()['plan_usage']
    with pytest.raises(ChatGPTError): oauth.models()


def test_catalog_is_account_scoped_and_unknown_model_is_rejected(flow):
    oauth, *_ = flow
    connect(flow)
    assert oauth.models() == [{'id':'available-model', 'label':'Modell'}]
    provider = oauth.provider('available-model')
    assert not provider.is_local and provider.available()
    with pytest.raises(ChatGPTError): oauth.provider('hidden-model')
    oauth.disconnect()
    assert not provider.available()
    assert not oauth.status()['connected']
    assert oauth.status()['accounts']  # registration and host survive sign-out


def test_refresh_rotates_secret_and_disconnect_stops_access(flow):
    oauth, keys, calls, _, _, _ = flow
    connect(flow); grant = oauth.status()['grant_id']
    oauth.clock = lambda: time.time()+3590
    assert oauth.access_token(grant) == 'rotated-access'
    raw = '\n'.join(keys.values.values())
    assert 'rotated-refresh' in raw
    oauth.disconnect()
    with pytest.raises(ChatGPTError): oauth.access_token(grant)
    assert 'private-refresh' not in '\n'.join(keys.values.values())
    assert 'rotated-refresh' not in '\n'.join(keys.values.values())


def test_returning_registration_reuses_host_and_issued_client(flow):
    oauth, _, _, _, _, _ = flow
    _, first = connect(flow)
    sid = oauth.status()['active_account']
    oauth.disconnect()
    started = oauth.begin('http://127.0.0.1:8890', account_id=sid)
    q = {k:v[0] for k,v in parse_qs(urlparse(started['url']).query).items()}
    assert q['client_id'] == 'oaiapp_test'
    assert q['ext_agent_host_id'] == first['ext_agent_host_id']
    assert 'agent_name_hint' not in q
    with pytest.raises(ChatGPTError): oauth.callback(q['state'], 'code', client_id='oaiapp_other')


def test_missing_secure_storage_prevents_sign_in(flow):
    oauth, keys, calls, *_ = flow
    keys.available = False
    with pytest.raises(ChatGPTError): oauth.begin('http://127.0.0.1:8890')
    assert calls == []


def test_refresh_revoked_in_flight_replacement_is_also_revoked(flow):
    oauth, _, calls, *_ = flow
    connect(flow); grant = oauth.status()['grant_id']
    oauth.clock = lambda: time.time()+3590
    entered, release = threading.Event(), threading.Event()
    original = oauth.request
    errors = []
    def request(method, url, **kwargs):
        if url == TOKEN_URL and kwargs['data']['grant_type'] == 'refresh_token':
            entered.set(); assert release.wait(3)
        return original(method,url,**kwargs)
    oauth.request = request
    def refresh():
        try: oauth.access_token(grant)
        except ChatGPTError as exc: errors.append(exc)
    thread = threading.Thread(target=refresh); thread.start()
    assert entered.wait(3)
    revoke = threading.Thread(target=oauth.disconnect); revoke.start()
    deadline = time.time()+3
    while oauth.available(grant) and time.time()<deadline: time.sleep(.01)
    assert not oauth.available(grant)
    release.set(); thread.join(3); revoke.join(3)
    assert not thread.is_alive() and not revoke.is_alive() and errors
    assert any(c[1].endswith('/oauth/revoke') and c[2]['data']['token']=='rotated-refresh' for c in calls)
    assert not oauth.status()['connected']


def test_disconnect_stops_runtime_even_when_storage_write_fails(flow):
    oauth, keys, *_ = flow
    connect(flow); grant=oauth.status()['grant_id']
    def fail(*_): raise OSError('private storage details')
    keys.set = fail
    result = oauth.disconnect()
    assert not oauth.available(grant) and not oauth.status()['connected']
    assert 'Speicher' in result['notice'] and 'private' not in result['notice']


def test_available_does_not_decrypt_keychain_for_every_stream_event(flow):
    oauth, keys, *_ = flow
    connect(flow); grant=oauth.status()['grant_id']
    def fail(*_): raise AssertionError('Repeated protected-storage access')
    keys.get=fail
    assert all(oauth.available(grant) for _ in range(100))


def test_routes_require_login_and_separate_consent_but_callback_is_one_use(flow, monkeypatch, tmp_path):
    from fastapi import FastAPI, Depends, Header, HTTPException
    from fastapi.testclient import TestClient
    from icarus_memory import chatgpt_routes
    oauth, _, calls, claims, _, _ = flow
    monkeypatch.setattr(chatgpt_routes,'ChatGPTOAuth',lambda _:oauth)
    app=FastAPI()
    def authorize(x_test_token: str|None=Header(default=None)):
        if x_test_token!='synthetic': raise HTTPException(401)
    chatgpt_routes.register(app,[Depends(authorize)],lambda:tmp_path)
    observed=[]
    @app.middleware('http')
    async def check_callback_query(request,call_next):
        result=await call_next(request)
        observed.append(request.scope['query_string'])
        return result
    client=TestClient(app,base_url='http://127.0.0.1:8890')
    headers={'X-Test-Token':'synthetic'}
    assert client.get('/api/v1/chatgpt').status_code==401
    assert client.post('/api/v1/chatgpt/begin',headers=headers,json={'origin':'http://127.0.0.1:8890'}).status_code==422
    assert not calls and not oauth.pending
    result=client.post('/api/v1/chatgpt/begin',headers=headers,json={'origin':'http://127.0.0.1:8890','consent':True})
    q={k:v[0] for k,v in parse_qs(urlparse(result.json()['url']).query).items()}
    claims.update(iss='https://auth.openai.com',aud='oaiapp_test',sub='account-one',nonce=q['nonce'],
                  exp=int(time.time())+3600,iat=int(time.time()))
    params={'state':q['state'],'code':'private-code','client_id':'oaiapp_test'}
    callback=client.get('/api/v1/chatgpt/callback',params=params)
    assert callback.status_code==200 and 'private-' not in callback.text
    assert callback.headers['cache-control']=='no-store' and observed[-1]==b''
    assert client.get('/api/v1/chatgpt/callback',params=params).status_code==400
    assert not any('/responses' in c[1] for c in calls)


def test_route_disconnect_revokes_cloud_job_before_credentials(flow, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from icarus_memory import chatgpt_routes
    oauth, *_=flow
    connect(flow)
    monkeypatch.setattr(chatgpt_routes,'ChatGPTOAuth',lambda _:oauth)
    app=FastAPI(); events=[]
    class Jobs:
        def pause(self,**kwargs):
            assert kwargs=={'revoke':True}
            assert oauth.status()['connected']
            events.append('revoked')
    app.state.cloud_memory_jobs=Jobs()
    chatgpt_routes.register(app,[],lambda:tmp_path)
    assert TestClient(app).delete('/api/v1/chatgpt').status_code==200
    assert events==['revoked'] and not oauth.status()['connected']


def test_signed_login_public_response_transport_and_memory_job_work_together(flow,tmp_path):
    import httpx
    from icarus_memory.chatgpt_provider import ChatGPTProvider
    from .test_cloud_memory import setup,add_email,finish
    oauth,*_=flow
    connect(flow); oauth.models(); grant=oauth.status()['grant_id']
    requests=[]
    def respond(request):
        assert str(request.url)=='https://api.openai.com/v1/responses'
        assert request.headers['authorization']=='Bearer private-access'
        body=json.loads(request.content)
        assert body['store'] is False and body['stream'] is True
        payload=json.loads(body['input'][-1]['content'])
        if 'taxonomy' in payload:
            result={'categories':[],'entities':[]}
        else:
            result={'items':[{'block_id':block['block_id'],'kind':'fact'} for block in payload['blocks']]}
        requests.append(body)
        events=[{'type':'response.output_text.delta','delta':json.dumps(result)},
                {'type':'response.completed','response':{'status':'completed'}}]
        return httpx.Response(200,text='\n\n'.join('data: '+json.dumps(e) for e in events)+'\n\n')
    episodes,jobs,_,_=setup(tmp_path)
    original=add_email(episodes)
    jobs.grant_status=oauth.status
    jobs.provider_factory=lambda model:ChatGPTProvider(oauth,model,grant,client_factory=lambda:httpx.Client(
        transport=httpx.MockTransport(respond)))
    preview=jobs.preview()
    assert not requests
    started=jobs.start(preview['preview_id'],'available-model',True)
    result=finish(jobs,started['job']['id'])
    assert result['state']=='complete' and result['completed']==1 and result['requests']==2
    assert len(requests)==2 and episodes.get(original.id).body==original.body
