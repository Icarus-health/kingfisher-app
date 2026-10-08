"""Question understanding must not leave its local HTTP request running for 30s."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import httpx
import pytest

from icarus_memory.frage import verstehen
from icarus_memory.providers import OpenAICompatible


def test_question_fallback_also_closes_slow_local_http_transport(monkeypatch):
    received, release, closed = threading.Event(), threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            received.set()
            release.wait(3)
            try:
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"choices":[{"message":{"content":"{}"}}]}')
            except (BrokenPipeError, ConnectionResetError): pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = OpenAICompatible('synthetic-local', base_url=f'http://127.0.0.1:{server.server_port}/v1')
    timeouts = []

    @contextmanager
    def client(timeout):
        timeouts.append(timeout)
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as connection:
                yield connection
        finally:
            closed.set()

    monkeypatch.setattr(provider, '_client', client)
    try:
        answer = verstehen('Was ist mit Mainz los?', provider, zeitlimit=0.15)
        assert answer.herkunft == 'rueckfall'
        assert received.wait(0.3)
        assert closed.wait(0.5), 'fallback left its local HTTP worker running'
        assert 0 < timeouts[0] <= 0.15
    finally:
        release.set(); closed.wait(1)
        server.shutdown(); server.server_close(); thread.join(1)


def test_expired_question_does_not_start_transport_after_model_wait(monkeypatch):
    import time
    from icarus_memory.providers import ProviderError, json_request_deadline
    provider = OpenAICompatible('synthetic-local', base_url='http://127.0.0.1:11434/v1')

    @contextmanager
    def waiting_gate():
        time.sleep(0.03)
        yield

    monkeypatch.setattr(provider, '_ampel', waiting_gate)
    monkeypatch.setattr(provider, '_client', lambda timeout: pytest.fail('expired request started'))
    with json_request_deadline(time.monotonic() + 0.01), pytest.raises(ProviderError, match='deadline'):
        provider.complete_json([])


def test_question_deadline_is_worker_local_and_resets_after_failure(monkeypatch):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from icarus_memory.providers import ProviderError, json_request_deadline
    provider = OpenAICompatible('synthetic-local', base_url='http://127.0.0.1:11434/v1')
    active, finish = threading.Event(), threading.Event()
    timeouts = []

    @contextmanager
    def client(timeout):
        timeouts.append(timeout)
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
                'choices': [{'message': {'content': '{}'}}]}))) as connection:
            yield connection

    monkeypatch.setattr(provider, '_client', client)

    def expired_worker():
        with json_request_deadline(time.monotonic() - 1):
            active.set(); assert finish.wait(2)
            with pytest.raises(ProviderError, match='deadline'):
                provider.complete_json([])
        return provider.complete_json([]).text

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(expired_worker)
        try:
            assert active.wait(2)
            assert provider.complete_json([]).text == '{}'
        finally:
            finish.set()
        assert future.result(2) == '{}'
    assert timeouts == [30.0, 30.0]
