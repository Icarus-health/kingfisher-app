"""Artificial local HTTP tests; no stores, model or external connection."""
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
import select
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

CONTROL = 'c' * 43
GRANT = 't' * 43
RUN = {'request': 'Where is the artificial card?', 'token': GRANT}
MCP = {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}
CHAT = {'model': 'kingfisher-qwen3.5:9b-8k', 'messages': [{'role': 'user', 'content': 'Artificial'}], 'stream': True}
CONTROLLED = 'controlled-local-readonly-v1'


def request(port, path, *, method='POST', value=None, raw=None, headers=None):
    body = raw if raw is not None else json.dumps(value if value is not None else {}).encode()
    base = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + GRANT}
    base.update(headers or {})
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request(method, path, body=body if method != 'GET' else None, headers=base)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class Upstream:
    def __init__(self):
        self.calls = []
        self.worker_key = None
        self.mode = 'ok'
        self.entered = threading.Event()
        self.release = threading.Event()
        self.disconnected = threading.Event()

    def callback(self, handler, body):
        self.calls.append((handler.command, handler.path, dict(handler.headers), body))
        self.entered.set()
        mode = self.mode
        if mode == 'block': self.release.wait(2)
        if mode == 'disconnect':
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                ready, _, _ = select.select([handler.connection], [], [], .03)
                if ready and handler.connection.recv(1, socket.MSG_PEEK) == b'':
                    self.disconnected.set(); break
            return 502, {}, b'{}'
        if mode == 'timeout': time.sleep(.25)
        if mode == 'redirect': return 302, {'Location': '/private', 'Set-Cookie': 'master=secret'}, b''
        if mode == 'oversize': return 200, {}, b'x' * 262145
        if mode == 'large_headers': return 200, {'X-Large': 'x' * 9000}, b'{}'
        if mode == 'malformed': return 200, {}, b'not-json'
        if mode == 'busy': return 409, {}, b'{"error":"private upstream detail"}'
        if mode == 'failure': return 500, {}, b'{"error":"private upstream detail"}'
        if handler.path == '/init':
            if self.worker_key is not None: return 409, {}, b'{}'
            self.worker_key = json.loads(body)['key']
            return 200, {}, b'{"status":"initialized"}'
        if handler.path == '/health':
            return 200, {}, json.dumps({'status': 'ok' if self.worker_key else 'awaiting_controller', 'private': CONTROL}).encode()
        if handler.path == '/run':
            if handler.headers.get('Authorization') != 'Bearer ' + str(self.worker_key): return 401, {}, b'{}'
            return 200, {'Set-Cookie': 'master=secret'}, b'{"status":"complete","text":"Artificial done","private":"hidden"}'
        return 200, {'Set-Cookie': 'master=secret', 'X-Private': 'hidden'}, b'{"jsonrpc":"2.0","id":1,"result":{}}'


class ControlledUpstream(Upstream):
    """Artificial inference only; actual gateway transport and binding remain real."""
    def __init__(self):
        super().__init__()
        self.instance = 'a' * 64
        self.contract = dict(mode=CONTROLLED, model='kingfisher-qwen3.5:9b-8k',
                             syntheticOnly=False, osIsolationVerified=False)
        self.run_change = None
        self.init_change = None
        self.health_raw = None

    def callback(self, handler, body):
        if self.mode != 'ok':
            return super().callback(handler, body)
        self.calls.append((handler.command, handler.path, dict(handler.headers), body))
        self.entered.set()
        if handler.path == '/init':
            if self.worker_key is not None:
                return 409, {}, b'{}'
            value = json.loads(body)
            if set(value) != {'key', 'mode'} or value['mode'] != CONTROLLED:
                return 400, {}, b'{}'
            self.worker_key = value['key']
            result = dict(status='initialized', instance=self.instance, **self.contract)
            if self.init_change is not None:
                self.init_change(result)
            return 200, {}, json.dumps(result).encode()
        if handler.path == '/health':
            if self.health_raw is not None:
                return 200, {}, self.health_raw
            return 200, {}, json.dumps(dict(status='ok' if self.worker_key else 'awaiting_controller',
                                            instance=self.instance, **self.contract)).encode()
        if handler.path == '/run':
            if handler.headers.get('Authorization') != 'Bearer ' + str(self.worker_key):
                return 401, {}, b'{}'
            value = dict(status='complete', text='Artificial controlled draft', instance=self.instance, **self.contract)
            if self.run_change is not None:
                self.run_change(value)
            return 200, {}, json.dumps(value).encode()
        return 404, {}, b'{}'


@contextlib.contextmanager
def upstream_server(upstream):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_GET(self): self.respond(b'')
        def do_POST(self): self.respond(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        def respond(self, body):
            code, headers, content = upstream.callback(self, body)
            try:
                self.send_response(code)
                for key, value in headers.items(): self.send_header(key, value)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers(); self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try: yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        upstream.release.set(); server.shutdown(); server.server_close(); thread.join()


class GatewayTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name('harness_gateway.py')
        self.assertTrue(path.exists(), 'narrow two-sided gateway implementation is missing')
        spec = importlib.util.spec_from_file_location('harness_gateway', path)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.stack = contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.main, self.worker = Upstream(), Upstream()
        self.main_origin = self.stack.enter_context(upstream_server(self.main))
        self.worker_origin = self.stack.enter_context(upstream_server(self.worker))
        self.start_gateway()

    def start_gateway(self, **kwargs):
        self.gateway = self.module.Gateway(CONTROL, main_origin=self.main_origin, worker_origin=self.worker_origin, **kwargs)
        self.worker_port = self.listen(self.gateway, 'worker')
        self.controller_port = self.listen(self.gateway, 'controller')

    def listen(self, gateway, role):
        server = self.module.make_server(('127.0.0.1', 0), gateway, role=role)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.stack.callback(thread.join); self.stack.callback(server.server_close); self.stack.callback(server.shutdown)
        return server.server_port

    def control(self, path, **kwargs):
        return request(self.controller_port, '/controller/' + path, headers={'Authorization': 'Bearer ' + CONTROL}, **kwargs)

    def initialize(self):
        response = self.control('initialize', value={})
        self.assertEqual(response[0], 200, response)
        self.assertEqual(json.loads(response[2]), {'status': 'initialized'})

    def raw(self, port, data):
        connection = socket.create_connection(('127.0.0.1', port), timeout=3)
        try:
            connection.sendall(data)
            result = b''
            while True:
                chunk = connection.recv(4096)
                if not chunk: return result
                result += chunk
        finally: connection.close()

    def test_worker_denies_ui_api_control_and_nonexact_routes(self):
        for route in ['/', '/today', '/api/v1/notes/fake', '/health?x=1', '/controller/initialize', '/init', '/run',
                      '/worker/mcp/', '/worker/mcp?x=1', '/worker/%6dcp', 'http://other/worker/mcp', '//worker/mcp']:
            with self.subTest(route=route):
                code, headers, body = request(self.worker_port, route, value=MCP)
                self.assertEqual(code, 404); self.assertNotIn('Set-Cookie', headers); self.assertNotIn(b'secret', body)
        self.assertEqual(self.main.calls, []); self.assertEqual(self.worker.calls, [])
        self.assertEqual(request(self.worker_port, '/health', method='GET')[0], 200)

    def test_worker_only_post_capabilities_and_scoped_authorization(self):
        for method in ['GET', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'CONNECT', 'TRACE']:
            self.assertEqual(request(self.worker_port, '/worker/mcp', method=method, value=MCP)[0], 404)
        for auth in ['', 'Bearer wrong', 'Basic ' + GRANT, 'Bearer ' + CONTROL]:
            self.assertEqual(request(self.worker_port, '/worker/mcp', value=MCP, headers={'Authorization': auth})[0], 401)
        self.assertEqual(self.main.calls, [])

    def test_cookie_and_arbitrary_headers_never_cross_fixed_proxy(self):
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1', 'ALL_PROXY': 'http://127.0.0.1:1'}):
            code, headers, body = request(self.worker_port, '/worker/mcp', value=MCP,
                headers={'Cookie': 'kingfisher_session=private', 'X-Icarus-Token': 'master', 'X-Upstream': 'evil', 'Host': 'evil.example'})
        self.assertEqual(code, 200); self.assertEqual(json.loads(body)['result'], {})
        self.assertNotIn('Set-Cookie', headers); self.assertNotIn('X-Private', headers)
        method, route, forwarded, content = self.main.calls[0]
        self.assertEqual((method, route), ('POST', '/worker/mcp')); self.assertEqual(json.loads(content), MCP)
        self.assertEqual(forwarded['Authorization'], 'Bearer ' + GRANT)
        self.assertNotIn('Cookie', forwarded); self.assertNotIn('X-Icarus-Token', forwarded); self.assertNotIn('X-Upstream', forwarded)
        self.assertNotEqual(forwarded['Host'], 'evil.example')

    def test_request_body_types_size_and_model_configuration_are_bounded(self):
        for raw in [b'[]', b'null', b'bad', b'{"id":1,"id":2}', b'{"id":NaN}', b'\xff']:
            self.assertEqual(request(self.worker_port, '/worker/mcp', raw=raw)[0], 400)
        self.assertEqual(request(self.worker_port, '/worker/mcp', raw=b'x' * 32769)[0], 413)
        self.assertEqual(request(self.worker_port, '/worker/mcp', value=MCP, headers={'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(request(self.worker_port, '/worker/mcp', value=MCP, headers={'Content-Encoding': 'gzip'})[0], 400)
        for value in [{**CHAT, 'model': 'cloud'}, {**CHAT, 'base_url': 'http://evil'}, {**MCP, 'origin': 'http://evil'}]:
            route = '/worker/v1/chat/completions' if 'model' in value else '/worker/mcp'
            self.assertEqual(request(self.worker_port, route, value=value)[0], 400)
        self.assertEqual(self.main.calls, [])
        self.assertEqual(request(self.worker_port, '/worker/v1/chat/completions', value=CHAT)[0], 200)

    def test_duplicate_framing_chunking_expect_and_header_limits_fail_closed(self):
        base = b'POST /worker/mcp HTTP/1.1\r\nHost: local\r\nAuthorization: Bearer ' + GRANT.encode() + b'\r\nContent-Type: application/json\r\n'
        for tail, want in [(b'Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}', b' 400 '),
                           (b'Content-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{}', b' 400 '),
                           (b'Content-Length: 2\r\nAuthorization: Bearer '+ GRANT.encode()+b'\r\n\r\n{}', b' 400 '),
                           (b'Content-Length: -1\r\n\r\n', b' 400 '),
                           (b'\r\n', b' 411 '),
                           (b'Content-Length: 2\r\nExpect: 100-continue\r\n\r\n{}', b' 417 '),
                           (b'X-Large: '+ b'x' * 8192+b'\r\n\r\n', b' 431 ')]:
            self.assertIn(want, self.raw(self.worker_port, base + tail).split(b'\r\n', 1)[0])
        self.assertEqual(self.main.calls, [])

    def test_controller_requires_separate_credential_and_listener(self):
        for route in ['initialize', 'run', 'health']:
            self.assertEqual(request(self.controller_port, '/controller/' + route, method='GET' if route == 'health' else 'POST', value={}, headers={'Authorization': 'Bearer ' + GRANT})[0], 401)
        self.assertEqual(request(self.controller_port, '/worker/mcp', value=MCP, headers={'Authorization': 'Bearer ' + CONTROL})[0], 404)
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        code, _, body = self.control('health', method='GET')
        self.assertEqual(code, 503); self.assertEqual(json.loads(body), {'status': 'awaiting_controller'})
        self.assertEqual(self.worker.calls, [])

    def test_initialize_uses_separate_in_memory_key_once_and_sanitizes_status(self):
        for value in [[], None, {'key': GRANT}, {'origin': self.main_origin}]:
            raw = json.dumps(value).encode()
            self.assertEqual(self.control('initialize', raw=raw)[0], 400)
        self.initialize()
        self.assertRegex(self.worker.worker_key, r'^[A-Za-z0-9_-]{43}$')
        self.assertNotIn(self.worker.worker_key, [GRANT, CONTROL])
        code, _, body = self.control('health', method='GET')
        self.assertEqual(code, 200); self.assertEqual(json.loads(body), {'status': 'ok'})
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.assertEqual(sum(c[1] == '/init' for c in self.worker.calls), 1)
        self.assertNotIn(CONTROL.encode(), b''.join(c[3] for c in self.worker.calls))
        self.assertFalse(any(c[2].get('Authorization') == 'Bearer ' + CONTROL for c in self.worker.calls))

    def test_run_forwards_original_bounded_request_without_key_leaks(self):
        self.initialize()
        code, headers, body = self.control('run', value=RUN)
        self.assertEqual(code, 200); self.assertEqual(json.loads(body), {'status': 'complete', 'text': 'Artificial done', 'syntheticOnly': True})
        self.assertNotIn('Set-Cookie', headers)
        call = self.worker.calls[-1]
        self.assertEqual(call[1], '/run'); self.assertEqual(json.loads(call[3]), RUN)
        self.assertEqual(call[2]['Authorization'], 'Bearer ' + self.worker.worker_key)
        self.assertNotIn(self.worker.worker_key.encode(), body); self.assertNotIn(CONTROL.encode(), body)
        for value in [{**RUN, 'model': 'cloud'}, {**RUN, 'request': 'x' * 1201}, {**RUN, 'token': 'short'}, {**RUN, 'request': ''}]:
            self.assertEqual(self.control('run', value=value)[0], 400)
        self.assertEqual(self.control('run', raw=b'x' * 8193)[0], 413)
        self.assertEqual(sum(c[1] == '/run' for c in self.worker.calls), 1)

    def test_proxy_restart_loses_worker_key_and_fails_closed_until_paired_restart(self):
        self.initialize()
        self.start_gateway()
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        code, _, body = self.control('health', method='GET')
        self.assertEqual(code, 503); self.assertEqual(json.loads(body), {'status': 'restart_required'})
        self.assertEqual(self.control('run', value=RUN)[0], 503)

    def test_redirects_are_not_followed_and_upstream_errors_are_sanitized(self):
        for mode, expected in [('redirect', 502), ('failure', 502), ('busy', 409)]:
            self.main.mode = mode
            code, headers, body = request(self.worker_port, '/worker/mcp', value=MCP)
            self.assertEqual(code, expected); self.assertNotIn('Location', headers); self.assertNotIn('Set-Cookie', headers)
            self.assertNotIn(b'private upstream', body)
        self.assertEqual([c[1] for c in self.main.calls], ['/worker/mcp'] * 3)

    def test_response_body_and_headers_are_bounded(self):
        for mode in ['oversize', 'large_headers']:
            self.main.mode = mode
            code, _, body = request(self.worker_port, '/worker/mcp', value=MCP)
            self.assertEqual(code, 502); self.assertLess(len(body), 200)

    def test_worker_busy_malformed_and_failure_return_safe_results(self):
        self.initialize()
        for mode, expected in [('busy', 409), ('failure', 502), ('malformed', 502)]:
            self.worker.mode = mode
            code, _, body = self.control('run', value=RUN)
            self.assertEqual(code, expected); self.assertNotIn(b'private upstream', body)
            self.assertNotIn(self.worker.worker_key.encode(), body)

    def test_timeout_has_no_retry_and_ambiguous_init_requires_restart(self):
        self.start_gateway(timeout=.05)
        self.worker.mode = 'timeout'
        self.assertEqual(self.control('initialize', value={})[0], 504)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        self.assertEqual(sum(c[1] == '/init' for c in self.worker.calls), 1)
        self.main.mode = 'timeout'
        self.assertEqual(request(self.worker_port, '/worker/mcp', value=MCP)[0], 504)
        self.assertEqual(len(self.main.calls), 1)

    def test_handler_capacity_is_shared_and_slow_clients_release_it(self):
        self.start_gateway(max_handlers=1, request_timeout=.15)
        slow = socket.create_connection(('127.0.0.1', self.worker_port), timeout=2)
        self.addCleanup(slow.close)
        slow.sendall(b'POST /worker/mcp HTTP/1.1\r\nHost: local\r\n')
        # A second connection is denied before any new per-connection handler.
        time.sleep(.03)
        self.assertEqual(self.control('health', method='GET')[0], 503)
        time.sleep(.18)
        self.assertEqual(request(self.worker_port, '/health', method='GET')[0], 200)
        self.assertEqual(self.main.calls, [])

    def test_concurrent_initialization_does_not_generate_second_worker_key(self):
        self.worker.mode = 'block'
        result = []
        thread = threading.Thread(target=lambda: result.append(self.control('initialize', value={})))
        thread.start()
        try:
            self.assertTrue(self.worker.entered.wait(2))
            self.assertEqual(self.control('initialize', value={})[0], 409)
        finally:
            self.worker.release.set(); thread.join()
        self.assertEqual(result[0][0], 200); self.assertEqual(len(self.worker.calls), 1)

    def test_non_ascii_controller_authorization_is_safely_unauthorized(self):
        try:
            code, _, body = request(self.controller_port, '/controller/health', method='GET',
                headers={'Authorization': 'Bearer ' + 'é' * 43})
        except http.client.RemoteDisconnected:
            self.fail('malformed authorization must return a safe 401, not crash its handler')
        self.assertEqual(code, 401); self.assertNotIn(CONTROL.encode(), body)
        self.assertEqual(self.worker.calls, [])

    def test_controller_disconnect_cancels_owned_upstream_request(self):
        self.initialize()
        self.worker.entered.clear(); self.worker.mode = 'disconnect'
        raw = json.dumps(RUN).encode()
        connection = socket.create_connection(('127.0.0.1', self.controller_port), timeout=2)
        try:
            connection.sendall(b'POST /controller/run HTTP/1.1\r\nHost: local\r\nAuthorization: Bearer '
                + CONTROL.encode() + b'\r\nContent-Type: application/json\r\nContent-Length: '
                + str(len(raw)).encode() + b'\r\n\r\n' + raw)
            self.assertTrue(self.worker.entered.wait(2))
        finally: connection.close()
        self.assertTrue(self.worker.disconnected.wait(.8), 'controller loss left the worker request running')

    def test_trailing_bytes_then_disconnect_also_cancel_upstream(self):
        self.initialize()
        self.worker.entered.clear(); self.worker.mode = 'disconnect'
        raw = json.dumps(RUN).encode()
        connection = socket.create_connection(('127.0.0.1', self.controller_port), timeout=2)
        try:
            connection.sendall(b'POST /controller/run HTTP/1.1\r\nHost: local\r\nAuthorization: Bearer '
                + CONTROL.encode() + b'\r\nContent-Type: application/json\r\nContent-Length: '
                + str(len(raw)).encode() + b'\r\n\r\n' + raw)
            self.assertTrue(self.worker.entered.wait(2))
            connection.sendall(b'X' * 4096)
        finally: connection.close()
        self.assertTrue(self.worker.disconnected.wait(.8), 'trailing bytes kept a cancelled worker alive')

    def test_timer_start_failure_releases_capacity_and_closes_socket(self):
        from types import SimpleNamespace
        state = self.module.Gateway(CONTROL, max_handlers=1)
        self.assertTrue(state.capacity.acquire(blocking=False))
        accepted, peer = socket.socketpair()
        self.addCleanup(accepted.close); self.addCleanup(peer.close)
        server = SimpleNamespace(gateway=state, shutdown_request=lambda request:request.close())
        with patch.object(self.module.threading.Timer, 'start', side_effect=RuntimeError('cannot start new thread')):
            try:
                self.module.BoundedServer.process_request_thread(server, accepted, ('local', 1))
            except RuntimeError:
                pass
        self.assertTrue(state.capacity.acquire(blocking=False), 'failed timer permanently lost capacity')
        self.assertEqual(accepted.fileno(), -1, 'accepted socket leaked on failed timer')

    def test_bad_control_key_is_rejected_without_echo(self):
        for key in ['', 'short', '!' * 43]:
            with self.assertRaisesRegex(ValueError, '^controller credential required$'):
                self.module.Gateway(key)

    def controlled_gateway(self, **kwargs):
        self.worker = ControlledUpstream()
        self.worker_origin = self.stack.enter_context(upstream_server(self.worker))
        self.start_gateway(mode=CONTROLLED, **kwargs)

    def test_controlled_init_health_and_result_bind_one_opaque_current_pair(self):
        self.controlled_gateway()
        self.assertEqual(self.control('health', method='GET')[0], 503)
        self.initialize()
        code, _, raw = self.control('health', method='GET')
        health = json.loads(raw)
        self.assertEqual(code, 200)
        self.assertEqual(health['status'], 'ok')
        self.assertRegex(health['instance'], r'^[a-f0-9]{64}$')
        self.assertNotEqual(health['instance'], self.worker.instance)
        self.assertEqual({k: health[k] for k in self.worker.contract}, self.worker.contract)
        code, _, raw = self.control('run', value=RUN)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw), {**health, 'status': 'complete', 'text': 'Artificial controlled draft'})
        self.assertEqual(json.loads(self.worker.calls[0][3]), {'key': self.worker.worker_key, 'mode': CONTROLLED})
        self.assertNotIn(CONTROL.encode(), raw)
        self.assertNotIn(self.worker.worker_key.encode(), raw)
        self.assertEqual(self.control('initialize', value={})[0], 409)

    def test_controlled_gateway_will_not_initialize_or_adopt_synthetic_worker(self):
        self.start_gateway(mode=CONTROLLED)
        self.assertEqual(self.control('initialize', value={})[0], 502)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.assertEqual(self.control('health', method='GET')[0], 503)
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        self.assertEqual(sum(c[1] == '/init' for c in self.worker.calls), 1)

    def test_synthetic_gateway_cannot_adopt_controlled_worker(self):
        self.controlled_gateway()
        self.start_gateway()
        self.assertEqual(self.control('initialize', value={})[0], 400)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.assertEqual(sum(c[1] == '/init' for c in self.worker.calls), 1)

    def test_controlled_worker_restart_latches_pair_revocation_without_adoption(self):
        self.controlled_gateway(); self.initialize()
        self.worker.instance = 'b' * 64
        self.worker.worker_key = None
        code, _, body = self.control('health', method='GET')
        self.assertEqual(code, 503); self.assertEqual(json.loads(body), {'status': 'restart_required'})
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.assertEqual(sum(c[1] == '/run' for c in self.worker.calls), 0)
        # Even restoring an old health response cannot resurrect a revoked pair.
        self.worker.instance = 'a' * 64; self.worker.worker_key = 'k' * 43
        self.assertEqual(self.control('health', method='GET')[0], 503)

    def test_controlled_init_cannot_accept_a_generation_that_already_restarted(self):
        self.controlled_gateway()
        self.worker.init_change = lambda _row: setattr(self.worker, 'instance', 'b' * 64)
        self.assertEqual(self.control('initialize', value={})[0], 502)
        self.assertEqual(self.control('health', method='GET')[0], 503)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        self.assertEqual(sum(c[1] == '/init' for c in self.worker.calls), 1)

    def test_controlled_malformed_successful_health_permanently_revokes_pair(self):
        for raw in [b'not-json', b'{"status":"ok","status":"ok"}', b'[]']:
            with self.subTest(raw=raw):
                self.controlled_gateway(); self.initialize()
                self.assertEqual(self.control('health', method='GET')[0], 200)
                self.worker.health_raw = raw
                code, _, body = self.control('health', method='GET')
                self.assertEqual(code, 503); self.assertEqual(json.loads(body), {'status': 'restart_required'})
                self.worker.health_raw = None
                self.assertEqual(self.control('health', method='GET')[0], 503)
                self.assertEqual(self.control('run', value=RUN)[0], 503)
                self.assertEqual(self.control('initialize', value={})[0], 409)
                self.assertEqual(sum(c[1] == '/run' for c in self.worker.calls), 0)

    def test_controlled_transient_transport_unavailability_does_not_change_current_pair(self):
        self.controlled_gateway(); self.initialize()
        before = json.loads(self.control('health', method='GET')[2])
        self.worker.mode = 'failure'
        self.assertEqual(self.control('health', method='GET')[0], 503)
        self.worker.mode = 'ok'
        code, _, body = self.control('health', method='GET')
        self.assertEqual(code, 200); self.assertEqual(json.loads(body), before)

    def test_controlled_gateway_restart_cannot_reuse_existing_worker_generation(self):
        self.controlled_gateway(); self.initialize()
        original = json.loads(self.control('health', method='GET')[2])['instance']
        self.start_gateway(mode=CONTROLLED)
        self.assertEqual(self.control('run', value=RUN)[0], 503)
        self.assertEqual(self.control('initialize', value={})[0], 409)
        self.worker.worker_key = None; self.worker.instance = 'b' * 64
        self.start_gateway(mode=CONTROLLED); self.initialize()
        current = json.loads(self.control('health', method='GET')[2])['instance']
        self.assertNotEqual(original, current)

    def test_controlled_result_mismatch_or_changed_worker_after_result_withholds_text(self):
        mutations = [lambda row: row.update(mode='synthetic'), lambda row: row.update(model='cloud'),
                     lambda row: row.update(syntheticOnly=True), lambda row: row.update(instance='b' * 64),
                     lambda row: row.update(private='unexpected'), lambda row: row.update(osIsolationVerified=True),
                     lambda row: setattr(self.worker, 'instance', 'b' * 64)]
        for change in mutations:
            with self.subTest(change=change):
                self.controlled_gateway(); self.initialize(); self.worker.run_change = change
                code, _, raw = self.control('run', value=RUN)
                self.assertEqual(code, 502); self.assertNotIn(b'Artificial controlled draft', raw)
                self.assertEqual(self.control('health', method='GET')[0], 503)
                self.assertEqual(self.control('run', value=RUN)[0], 503)

    def test_controlled_unknown_request_and_setup_fields_fail_before_worker_call(self):
        with self.assertRaisesRegex(ValueError, '^unsupported runtime mode$'):
            self.module.Gateway(CONTROL, mode='other')
        self.controlled_gateway(); self.initialize(); count = len(self.worker.calls)
        for extra in [dict(mode=CONTROLLED), dict(instance='a' * 64), dict(syntheticOnly=False), dict(origin=self.worker_origin)]:
            self.assertEqual(self.control('run', value={**RUN, **extra})[0], 400)
        self.assertEqual(self.control('initialize', value={'mode': CONTROLLED})[0], 400)
        self.assertEqual(len(self.worker.calls), count)
        for args in [['--model', 'cloud'], ['--' + CONTROLLED, '--origin', 'http://other']]:
            with self.assertRaisesRegex(SystemExit, '^unsupported runtime mode$'):
                self.module.main(args)

    def test_controlled_disconnect_keeps_existing_captured_socket_cancellation(self):
        self.controlled_gateway(); self.initialize()
        self.worker.mode = 'disconnect'; self.worker.entered.clear()
        # The next transport is preflight health; disconnecting it must still
        # close the socket captured before HTTPResponse detaches it.
        connection = socket.create_connection(('127.0.0.1', self.controller_port), timeout=2)
        raw = json.dumps(RUN).encode()
        try:
            connection.sendall(b'POST /controller/run HTTP/1.1\r\nHost: local\r\nAuthorization: Bearer '
                + CONTROL.encode() + b'\r\nContent-Type: application/json\r\nContent-Length: '
                + str(len(raw)).encode() + b'\r\n\r\n' + raw)
            self.assertTrue(self.worker.entered.wait(2))
        finally:
            connection.close()
        self.assertTrue(self.worker.disconnected.wait(.8))


if __name__ == '__main__': unittest.main()
