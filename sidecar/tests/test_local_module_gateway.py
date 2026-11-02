"""Exercise the controller transport boundary without opening any socket."""
from email.message import Message
import importlib
import io
import json
import threading
import time

import pytest


KEY = 'c' * 43
TOKEN = 'w' * 43


def api():
    return importlib.import_module('icarus_memory.local_module_gateway')


class SocketFixture:
    def __init__(self):
        self.closed = threading.Event()
    def shutdown(self, _how):
        self.closed.set()
    def close(self):
        self.closed.set()


class ResponseFixture:
    def __init__(self, body=b'{"status":"ok"}', status=200, headers=None):
        self.status, self.body = status, body
        self.headers = Message()
        for name, value in headers or [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]:
            self.headers[name] = value
    def read(self, amount):
        return self.body[:amount]


@pytest.fixture
def connection(monkeypatch):
    seen = []
    state = dict(response=ResponseFixture(), fail=None, block=False)
    class Connection:
        def __init__(self, host, port, timeout):
            self.host, self.port, self.timeout = host, port, timeout
            self.sock = SocketFixture()
            self.connected = threading.Event()
            self.requests = []
            self.closed = False
            seen.append(self)
        def connect(self):
            self.connected.set()
            if state['fail']:
                raise state['fail']
        def request(self, method, path, body=None, headers=None):
            self.requests.append((method, path, body, headers))
        def getresponse(self):
            if state['block']:
                assert self.sock.closed.wait(3)
                raise OSError('secret transport internal path')
            return state['response']
        def close(self):
            self.closed = True
            self.sock.close()
    module = api()
    monkeypatch.setattr(module.http.client, 'HTTPConnection', Connection)
    return state, seen


def test_fixed_host_paths_no_environment_proxy_and_private_control_key(connection, monkeypatch):
    state, seen = connection
    monkeypatch.setenv('HTTP_PROXY', 'http://arbitrary-external.invalid:8000')
    monkeypatch.setenv('HTTPS_PROXY', 'http://arbitrary-external.invalid:8000')
    client = api().FixedGatewayClient(KEY)
    assert client.health() == {'status': 'ok'}
    assert seen[0].host == 'kingfisher-gateway-control' and seen[0].port == 8891
    method, path, body, headers = seen[0].requests[0]
    assert method == 'GET' and path == '/controller/health' and body is None
    assert headers['Authorization'] == 'Bearer ' + KEY
    assert KEY not in repr(client)
    assert seen[0].closed
    state['response'] = ResponseFixture(b'{"status":"complete","text":"Draft"}')
    assert client.run(TOKEN, 'Eine Frage', threading.Event(), client.now() + 120)['text'] == 'Draft'
    method, path, body, headers = seen[1].requests[0]
    assert method == 'POST' and path == '/controller/run'
    assert json.loads(body) == {'token': TOKEN, 'request': 'Eine Frage'}
    assert KEY.encode() not in body
    assert headers['Authorization'] == 'Bearer ' + KEY
    with pytest.raises(TypeError):
        api().FixedGatewayClient(KEY, origin='http://arbitrary-external.invalid')


@pytest.mark.parametrize('response', [
    ResponseFixture(b'{}', status=302, headers=[('Location', 'http://external.invalid')]),
    ResponseFixture(b'secret diagnostic', status=503),
    ResponseFixture(b'{"x":1,"x":2}'), ResponseFixture(b'{"x":NaN}'), ResponseFixture(b'[]'),
    ResponseFixture(b'{}', headers=[('Content-Type', 'text/html')]),
    ResponseFixture(b'{}', headers=[('Content-Type', 'application/json'), ('Content-Encoding', 'gzip')]),
    ResponseFixture(b'{}', headers=[('Content-Type', 'application/json'), ('Content-Length', '2'), ('Content-Length', '2')]),
    ResponseFixture(b'{}', headers=[('Content-Type', 'application/json'), ('Content-Length', '99999999')]),
    ResponseFixture(b'x' * 262145, headers=[('Content-Type', 'application/json')]),
])
def test_redirect_malformed_ambiguous_or_oversized_response_is_rejected_without_retry(connection, response):
    state, seen = connection
    state['response'] = response
    client = api().FixedGatewayClient(KEY)
    with pytest.raises(api().GatewayError) as error:
        client.health()
    assert len(seen) == 1
    assert KEY not in str(error.value) and 'secret' not in str(error.value)
    assert seen[0].closed


def test_connection_exception_is_sanitized_and_never_retried(connection):
    state, seen = connection
    state['fail'] = OSError('secret-api-key private-network')
    with pytest.raises(api().GatewayError) as error:
        api().FixedGatewayClient(KEY).health()
    assert str(error.value) == 'GatewayUnavailable'
    assert len(seen) == 1 and seen[0].closed


@pytest.mark.parametrize('reason', ['cancel', 'deadline'])
def test_cancellation_or_absolute_deadline_closes_owned_socket(connection, reason):
    state, seen = connection
    state['block'] = True
    clock = [100.0]
    client = api().FixedGatewayClient(KEY, clock=lambda: clock[0])
    cancelled, exited = threading.Event(), threading.Event()
    errors = []
    def perform():
        try:
            client.run(TOKEN, 'Eine Frage', cancelled, 220.0)
        except api().GatewayError as error:
            errors.append(str(error))
        finally:
            exited.set()
    task = threading.Thread(target=perform)
    task.start()
    while not seen:
        assert not exited.wait(.005)
    assert seen[0].connected.wait(2)
    if reason == 'cancel':
        cancelled.set()
    else:
        clock[0] = 220.0
    assert exited.wait(2)
    task.join(1)
    assert errors == ['GatewayUnavailable']
    assert seen[0].closed and len(seen) == 1


def test_already_cancelled_or_invalid_input_never_opens_transport(connection):
    _state, seen = connection
    client = api().FixedGatewayClient(KEY)
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(api().GatewayError):
        client.run(TOKEN, 'Question', cancelled, client.now() + 120)
    for token, question in [(TOKEN, ''), ('master-token', 'Question'), (TOKEN, 'x'*1201)]:
        with pytest.raises(api().GatewayError):
            client.run(token, question, threading.Event(), client.now() + 120)
    assert not seen


def test_bounded_header_reader_rejects_accumulated_header_bytes():
    reader = api().BoundedHeaderReader(io.BytesIO(b'x' * 8193 + b'\r\n'))
    with pytest.raises(ValueError):
        reader.readline()


@pytest.mark.parametrize('reason', ['cancel', 'deadline'])
def test_real_http_close_response_retains_cancelled_owned_socket(monkeypatch, reason):
    """Real parser transfers ownership away from HTTPConnection.sock."""
    module = api()
    entered, release, shutdown = (threading.Event() for _ in range(3))
    connections, errors = [], []
    clock = [100.0]
    class Stream(io.BytesIO):
        def read(self, size=-1):
            entered.set()
            assert release.wait(2)
            return super().read(size)
    class Sock:
        def __init__(self):
            self.stream = Stream(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n'
                b'Content-Type: application/json\r\nConnection: close\r\n\r\n{}')
        def makefile(self, *_args):
            return self.stream
        def sendall(self, _data):
            pass
        def shutdown(self, _how):
            shutdown.set()
            release.set()
        def close(self):
            # A response makefile still holds the actual descriptor. Only
            # shutdown, not connection.close(), can interrupt its blocking read.
            pass
    original = module.http.client.HTTPConnection
    class Connection(original):
        def connect(self):
            self.sock = Sock()
            connections.append(self)
    monkeypatch.setattr(module.http.client, 'HTTPConnection', Connection)
    cancelled = threading.Event()
    def perform():
        try:
            module.FixedGatewayClient(KEY, clock=lambda: clock[0]).run(TOKEN, 'Question', cancelled, 220.0)
        except module.GatewayError as error:
            errors.append(str(error))
    task = threading.Thread(target=perform)
    task.start()
    try:
        assert entered.wait(1)
        assert connections[0].sock is None
        if reason == 'cancel':
            cancelled.set()
        else:
            clock[0] = 220.0
        assert shutdown.wait(.3)
        task.join(.3)
        assert not task.is_alive()
    finally:
        release.set()
        task.join(2)
    assert errors == ['GatewayUnavailable']


def test_initialize_is_one_fixed_bounded_post_with_no_request_configuration(connection):
    state, seen = connection
    state['response'] = ResponseFixture(b'{"status":"initialized"}')
    client = api().FixedGatewayClient(KEY, clock=lambda: 100.0)
    assert client.initialize() == {'status': 'initialized'}
    assert len(seen) == 1 and seen[0].timeout == 3.0 and seen[0].closed
    method, path, body, headers = seen[0].requests[0]
    assert (method, path, body) == ('POST', '/controller/initialize', b'{}')
    assert headers['Authorization'] == 'Bearer ' + KEY
    assert KEY.encode() not in body


@pytest.mark.parametrize('body', [b'{"status":"ok"}', b'{"status":"initialized","key":"private"}'])
def test_initialize_rejects_unrecognized_reply_without_retry(connection, body):
    state, seen = connection
    state['response'] = ResponseFixture(body)
    with pytest.raises(api().GatewayError) as error:
        api().FixedGatewayClient(KEY).initialize()
    assert str(error.value) == 'GatewayUnavailable'
    assert len(seen) == 1 and seen[0].closed
