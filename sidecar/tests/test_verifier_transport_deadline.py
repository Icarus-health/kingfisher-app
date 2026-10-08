"""A sentence-check fallback must also close its bounded local JSON request."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import httpx
import pytest

from icarus_memory import satzpruefung_modell as verification
from icarus_memory.providers import OpenAICompatible


def test_sentence_timeout_also_closes_slow_local_json_transport(monkeypatch):
    received, release, closed = threading.Event(), threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            received.set()
            release.wait(3)
            try:
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"choices":[{"message":{"content":"{\\"urteil\\":\\"ja\\"}"}}]}')
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
        result = verification._ein_urteil(verification.STANDARD, provider, 'Mira prüft.', 'Mira prüft.', .15)
        assert result.wert == verification.UNKLAR
        assert received.wait(.3)
        assert closed.wait(.5), 'sentence fallback left its JSON transport running'
        assert 0 < timeouts[0] <= .15
    finally:
        release.set(); closed.wait(1)
        server.shutdown(); server.server_close(); thread.join(1)


def test_expired_sentence_does_not_start_json_after_model_wait(monkeypatch):
    import time
    finished = threading.Event()
    opened = []
    provider = OpenAICompatible('synthetic-local', base_url='http://127.0.0.1:11439/v1')

    @contextmanager
    def waiting_gate():
        try:
            time.sleep(.04)
            yield
        finally:
            finished.set()

    @contextmanager
    def client(timeout):
        opened.append(timeout)
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
                'choices': [{'message': {'content': '{"urteil":"ja"}'}}]}))) as connection:
            yield connection

    monkeypatch.setattr(provider, '_ampel', waiting_gate)
    monkeypatch.setattr(provider, '_client', client)
    result = verification._ein_urteil(verification.STANDARD, provider, 'Mira prüft.', 'Mira prüft.', .01)
    assert result.wert == verification.UNKLAR
    assert finished.wait(1)
    assert opened == []


@pytest.mark.parametrize('budget', [0, -.01])
def test_no_sentence_budget_starts_no_model_job(budget):
    called = threading.Event()

    def ask(*args):
        called.set()
        return None

    adapter = verification.Adapter('synthetic', (), ask, lambda reply: verification.Urteil(verification.JA))
    result = verification._ein_urteil(adapter, object(), 'Mira prüft.', 'Mira prüft.', budget)
    assert result == verification.Urteil(verification.UNKLAR, 'zeit')
    assert not called.is_set()
