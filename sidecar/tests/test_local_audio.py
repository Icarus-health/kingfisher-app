import base64
import io
import time
import wave
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from icarus_memory.local_audio import register_local_audio_routes


def wav_bytes(*, channels=1, width=2, rate=22050, seconds=1):
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(channels); w.setsampwidth(width); w.setframerate(rate)
        w.writeframes(b'\0' * channels * width * rate * seconds)
    return out.getvalue()


def client(monkeypatch=None):
    app = FastAPI()
    app.state.conversation_lock = __import__('threading').RLock()
    def auth(x_icarus_token: str | None = Header(default=None)):
        if x_icarus_token != 'secret': raise HTTPException(401)
    register_local_audio_routes(app, [__import__('fastapi').Depends(auth)])
    return app, TestClient(app, headers={'X-Icarus-Token': 'secret'})


def test_status_requires_worker_and_job_lifecycle():
    app, c = client()
    assert c.get('/api/v1/audio/status').json() == {'available': False}
    assert c.post('/api/v1/audio', json={'text': 'Hallo'}).status_code == 503
    assert c.get('/api/v1/audio-worker').json()['job'] is None
    c.get('/api/v1/audio-worker')
    assert c.get('/api/v1/audio/status').json()['available'] is True
    created = c.post('/api/v1/audio', json={'text': 'Hallo'}); assert created.status_code == 200
    job = created.json(); claimed = c.get('/api/v1/audio-worker').json()['job']
    assert claimed == {'id': job['id'], 'text': 'Hallo'}
    assert c.get('/api/v1/audio-worker').json()['job'] is None
    assert c.post('/api/v1/audio-worker', json={'id': job['id'], 'success': True,
        'audio_base64': base64.b64encode(wav_bytes()).decode()}).status_code == 200
    assert c.get(f"/api/v1/audio/{job['id']}").json()['status'] == 'ready'
    content = c.get(f"/api/v1/audio/{job['id']}/content")
    assert content.status_code == 200 and content.headers['cache-control'] == 'no-store'
    assert content.content.startswith(b'RIFF')


def test_new_job_replaces_old_and_old_worker_result_is_rejected():
    app, c = client(); c.get('/api/v1/audio-worker')
    old = c.post('/api/v1/audio', json={'text': 'alt'}).json()
    new = c.post('/api/v1/audio', json={'text': 'neu'}).json()
    assert c.get(f"/api/v1/audio/{old['id']}").status_code == 404
    assert c.get('/api/v1/audio-worker').json()['job']['id'] == new['id']
    assert c.post('/api/v1/audio-worker', json={'id': old['id'], 'success': False}).status_code == 404


def test_invalid_wav_and_cancel_are_safe():
    app, c = client(); c.get('/api/v1/audio-worker')
    job = c.post('/api/v1/audio', json={'text': 'x'}).json()
    c.get('/api/v1/audio-worker')
    bad = c.post('/api/v1/audio-worker', json={'id': job['id'], 'success': True, 'audio_base64': base64.b64encode(b'bad').decode()})
    assert bad.status_code == 422
    assert c.get(f"/api/v1/audio/{job['id']}").json()['status'] == 'failed'
    job2 = c.post('/api/v1/audio', json={'text': 'y'}).json()
    assert c.delete(f"/api/v1/audio/{job2['id']}").json()['status'] == 'failed'
    assert c.get(f"/api/v1/audio/{job2['id']}/content").status_code == 409


def test_rejects_blank_text_and_truncated_or_empty_wav():
    app, c = client(); c.get('/api/v1/audio-worker')
    for text in (' ', '\t', 'hello\x00world'):
        assert c.post('/api/v1/audio', json={'text': text}).status_code == 422
    job = c.post('/api/v1/audio', json={'text': 'x'}).json(); c.get('/api/v1/audio-worker')
    raw = wav_bytes()[:-4]
    result = c.post('/api/v1/audio-worker', json={'id': job['id'], 'success': True, 'audio_base64': base64.b64encode(raw).decode()})
    assert result.status_code == 422


def test_processing_timeout_is_enforced_before_late_result():
    app, c = client(); c.get('/api/v1/audio-worker')
    job = c.post('/api/v1/audio', json={'text': 'x'}).json(); claimed = c.get('/api/v1/audio-worker').json()['job']
    assert claimed['text'] == 'x'
    state = app.state.local_audio; state['jobs'][job['id']]['claimed_at'] -= 121
    late = c.post('/api/v1/audio-worker', json={'id': job['id'], 'success': True, 'audio_base64': base64.b64encode(wav_bytes()).decode()})
    assert late.status_code == 404
    assert c.get(f"/api/v1/audio/{job['id']}").json()['status'] == 'failed'
    assert c.get(f"/api/v1/audio/{job['id']}/content").status_code == 409


def test_auth_all_routes(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'secret')
    app, c = client(); c.headers.pop('X-Icarus-Token')
    for method, path in [('get','/api/v1/audio/status'), ('post','/api/v1/audio'), ('get','/api/v1/audio-worker'),
                         ('post','/api/v1/audio-worker'), ('get','/api/v1/audio/nope'),
                         ('get','/api/v1/audio/nope/content'), ('delete','/api/v1/audio/nope')]:
        response = (c.post(path, json={'text': 'x', 'id': 'nope', 'success': False}) if method == 'post'
                    else c.delete(path) if method == 'delete' else c.get(path))
        assert response.status_code == 401


def test_pending_job_expiry_and_processing_timeout(monkeypatch):
    app, c = client(); c.get('/api/v1/audio-worker')
    job = c.post('/api/v1/audio', json={'text': 'x'}).json()
    state = app.state.local_audio
    state['jobs'][job['id']]['created_at'] -= 301
    assert c.get(f"/api/v1/audio/{job['id']}").status_code == 404
    job2 = c.post('/api/v1/audio', json={'text': 'y'}).json()
    c.get('/api/v1/audio-worker')
    state['jobs'][job2['id']]['claimed_at'] -= 121
    assert c.get(f"/api/v1/audio/{job2['id']}").json()['status'] == 'failed'
