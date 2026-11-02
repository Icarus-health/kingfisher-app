"""Artificial-only, fixed-route worker gateway; never mount a personal store here.

The worker listener exposes only two capability POSTs and local health. The
controller listener owns pairing/run authority with a separate credential.
Production origins/ports are fixed below; constructor origins are for local tests.
No subprocesses, redirects, environment proxies, retries or persistent secrets.
"""
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import select
import secrets
import socket
from socketserver import ThreadingMixIn
import threading
import time
from urllib.parse import urlsplit

MAIN_ORIGIN = 'http://kingfisher-controller:8892'
WORKER_ORIGIN = 'http://kingfisher-worker:3001'
MODEL = 'kingfisher-qwen3.5:9b-8k'
KEY = re.compile(r'[A-Za-z0-9_-]{43}\Z')
MAX_HEADERS = 8192
MAX_REQUEST = 32768
MAX_RESPONSE = 262144
CAPABILITIES = {'/worker/mcp', '/worker/v1/chat/completions'}


class Rejected(Exception):
    def __init__(self, status, message): self.status, self.message = status, message


class HeaderLimit(ValueError): pass


class HeaderReader:
    """Bound actual bytes before the stdlib header parser can accumulate them."""
    def __init__(self, stream): self.stream, self.remaining = stream, MAX_HEADERS
    def readline(self, limit=-1):
        limit = self.remaining + 1 if limit < 0 else min(limit, self.remaining + 1)
        line = self.stream.readline(limit)
        self.remaining -= len(line)
        if self.remaining < 0: raise HeaderLimit()
        return line
    def __getattr__(self, name): return getattr(self.stream, name)


class BoundedResponse(http.client.HTTPResponse):
    def begin(self):
        original = self.fp
        self.fp = HeaderReader(original)
        try: return super().begin()
        finally:
            if self.fp is not None: self.fp = original


def parse_object(raw):
    def pairs(entries):
        value = {}
        for key, item in entries:
            if key in value: raise ValueError()
            value[key] = item
        return value
    def constant(_value): raise ValueError()
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        if not isinstance(value, dict): raise ValueError()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise Rejected(400, 'InvalidRequest') from None


def close_socket(connection):
    try: connection.shutdown(socket.SHUT_RDWR)
    except OSError: pass
    try: connection.close()
    except OSError: pass


class Gateway:
    def __init__(self, control_key, *, main_origin=MAIN_ORIGIN, worker_origin=WORKER_ORIGIN,
                 timeout=115, request_timeout=120, max_handlers=8):
        if not isinstance(control_key, str) or not KEY.fullmatch(control_key):
            raise ValueError('controller credential required')
        if not 0 < timeout <= 115 or not 0 < request_timeout <= 120 or not 1 <= max_handlers <= 8:
            raise ValueError('invalid gateway limits')
        self._control_key = control_key
        self._main = self._origin(main_origin)
        self._worker = self._origin(worker_origin)
        self.timeout, self.request_timeout = timeout, request_timeout
        self.capacity = threading.BoundedSemaphore(max_handlers)
        self._lock = threading.Lock()
        self._worker_key = None
        self._initializing = False
        self._restart_required = False

    @staticmethod
    def _origin(origin):
        parsed = urlsplit(origin)
        if (parsed.scheme != 'http' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or parsed.port is None):
            raise ValueError('invalid fixed upstream')
        return parsed.hostname, parsed.port

    def authorized(self, authorization):
        return (isinstance(authorization, str) and authorization.isascii()
                and secrets.compare_digest(authorization, 'Bearer ' + self._control_key))

    def upstream(self, target, method, path, body=None, key=None, cancel_socket=None):
        # HTTPConnection does not read proxy settings or follow redirects/retry.
        host, port = self._worker if target == 'worker' else self._main
        connection = http.client.HTTPConnection(host, port, timeout=self.timeout)
        connection.response_class = BoundedResponse
        watcher = None
        stopped, expired = threading.Event(), threading.Event()
        try:
            connection.connect()
            connected_socket = connection.sock
            def watch():
                deadline = time.monotonic() + self.timeout
                while not stopped.wait(.025):
                    if time.monotonic() >= deadline:
                        expired.set(); close_socket(connected_socket); return
                    if cancel_socket is not None:
                        try:
                            ready, _, _ = select.select([cancel_socket], [], [], 0)
                            # A complete framed request has already been consumed
                            # and this proxy closes every connection. Both EOF and
                            # unexpected trailing bytes cancel the owned upstream.
                            if ready:
                                close_socket(connected_socket); return
                        except (OSError, ValueError):
                            close_socket(connected_socket); return
            watcher = threading.Thread(target=watch, daemon=True); watcher.start()
            headers = {'Accept': 'application/json, text/event-stream', 'Connection': 'close'}
            if body is not None: headers['Content-Type'] = 'application/json'
            if key is not None: headers['Authorization'] = 'Bearer ' + key
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status < 200 or response.status >= 300:
                code = response.status if response.status in {400, 401, 403, 409, 413, 429, 503} else 502
                raise Rejected(code, 'UpstreamRejected')
            lengths = response.headers.get_all('Content-Length', [])
            if len(lengths) > 1 or (lengths and (not lengths[0].isdigit() or int(lengths[0]) > MAX_RESPONSE)):
                raise Rejected(502, 'UpstreamFailed')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise Rejected(502, 'UpstreamFailed')
            content = response.read(MAX_RESPONSE + 1)
            if len(content) > MAX_RESPONSE: raise Rejected(502, 'UpstreamFailed')
            content_type = response.headers.get('Content-Type', 'application/json').split(';', 1)[0].lower()
            if content_type not in {'application/json', 'text/event-stream'}:
                raise Rejected(502, 'UpstreamFailed')
            return response.status, content_type, content
        except Rejected: raise
        except (TimeoutError, socket.timeout): raise Rejected(504, 'UpstreamTimeout') from None
        except (OSError, ValueError, RuntimeError, http.client.HTTPException):
            raise Rejected(504 if expired.is_set() else 502, 'UpstreamTimeout' if expired.is_set() else 'UpstreamFailed') from None
        finally:
            stopped.set()
            if watcher is not None and watcher.ident is not None: watcher.join()
            connection.close()

    def initialize(self, cancel_socket=None):
        with self._lock:
            if self._worker_key is not None or self._initializing or self._restart_required:
                raise Rejected(409, 'AlreadyInitialized')
            self._initializing = True
        candidate = secrets.token_urlsafe(32)
        try:
            _, _, content = self.upstream('worker', 'POST', '/init', json.dumps({'key': candidate}).encode(), cancel_socket=cancel_socket)
            if parse_object(content) != {'status': 'initialized'}: raise Rejected(502, 'UpstreamFailed')
            with self._lock: self._worker_key = candidate
        except Rejected:
            # Even a lost reply may mean the worker accepted the key. Never retry
            # or adopt an existing worker: pair both processes again after restart.
            with self._lock: self._restart_required = True
            raise
        finally:
            with self._lock: self._initializing = False
        return {'status': 'initialized'}

    def health(self, cancel_socket=None):
        with self._lock:
            if self._restart_required: return 503, {'status': 'restart_required'}
            if self._worker_key is None: return 503, {'status': 'awaiting_controller'}
        try:
            _, _, content = self.upstream('worker', 'GET', '/health', cancel_socket=cancel_socket)
            status = parse_object(content).get('status')
        except Rejected: return 503, {'status': 'worker_unavailable'}
        if status == 'ok': return 200, {'status': 'ok'}
        return 503, {'status': 'restart_required' if status == 'restart_required' else 'worker_unavailable'}

    def run(self, value, raw, cancel_socket=None):
        if (set(value) != {'request', 'token'} or not isinstance(value['request'], str)
                or not value['request'].strip() or len(value['request']) > 1200
                or not isinstance(value['token'], str) or not KEY.fullmatch(value['token'])):
            raise Rejected(400, 'InvalidRequest')
        with self._lock: key = self._worker_key
        if key is None: raise Rejected(503, 'AwaitingController')
        _, _, content = self.upstream('worker', 'POST', '/run', raw, key, cancel_socket)
        try: result = parse_object(content)
        except Rejected: raise Rejected(502, 'WorkerFailed') from None
        if (result.get('status') != 'complete' or not isinstance(result.get('text'), str)
                or not result['text'].strip() or len(result['text']) > 32000):
            raise Rejected(502, 'WorkerFailed')
        return {'status': 'complete', 'text': result['text'], 'syntheticOnly': True}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'KingfisherGateway'
    sys_version = ''

    def log_message(self, *_args): pass  # No grants, credentials, requests or upstream details in logs.

    def parse_request(self):
        parts = self.raw_requestline.split()
        self.raw_target = parts[1].decode('iso-8859-1') if len(parts) >= 2 else ''
        if len(self.raw_requestline) > 2048:
            self.requestline = ''; self.request_version = 'HTTP/1.1'; self.command = None
            self.send_error(414); return False
        original = self.rfile; self.rfile = HeaderReader(original)
        try: return super().parse_request()
        except HeaderLimit:
            self.send_error(431); return False
        finally: self.rfile = original

    def handle_expect_100(self): self.send_error(417); return False

    def send_error(self, code, message=None, explain=None): self.reply(code, {'error': 'InvalidRequest'})

    def reply(self, code, value, content_type='application/json'):
        content = value if isinstance(value, bytes) else json.dumps(value, separators=(',', ':')).encode()
        self.close_connection = True
        try:
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            if self.command != 'HEAD': self.wfile.write(content)
        except (OSError, ValueError): pass

    def body(self, limit):
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) == 0: raise Rejected(411, 'LengthRequired')
        if len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,10}', lengths[0]):
            raise Rejected(400, 'InvalidRequest')
        length = int(lengths[0])
        if length > limit: raise Rejected(413, 'InputTooLarge')
        if self.headers.get('Content-Type', '').lower() not in {'application/json', 'application/json; charset=utf-8'}:
            raise Rejected(415, 'JSONRequired')
        raw = self.rfile.read(length)
        if len(raw) != length: raise Rejected(400, 'InvalidRequest')
        return parse_object(raw), raw

    def dispatch(self):
        gateway, role = self.server.gateway, self.server.role
        try:
            # Never normalize paths, forward hop headers, accept chunked framing,
            # compressed bodies or ambiguous duplicate authentication/framing.
            for header in ['Authorization', 'Content-Length', 'Content-Type', 'Host']:
                if len(self.headers.get_all(header, [])) > 1: raise Rejected(400, 'InvalidRequest')
            if any(header in self.headers for header in ['Transfer-Encoding', 'Content-Encoding', 'Expect']):
                raise Rejected(400, 'InvalidRequest')
            path = self.raw_target
            if role == 'worker':
                if path == '/health' and self.command == 'GET': self.reply(200, {'status': 'ok'}); return
                if path not in CAPABILITIES or self.command != 'POST': raise Rejected(404, 'UnknownOperation')
                authorization = self.headers.get('Authorization', '')
                if not authorization.startswith('Bearer ') or not KEY.fullmatch(authorization[7:]) or gateway.authorized(authorization):
                    raise Rejected(401, 'Unauthorized')
                value, raw = self.body(MAX_REQUEST)
                if path == '/worker/mcp':
                    if set(value) - {'jsonrpc', 'id', 'method', 'params'}: raise Rejected(400, 'InvalidRequest')
                else:
                    if (value.get('model') != MODEL or set(value) - {'model', 'messages', 'tools', 'stream',
                            'stream_options', 'store', 'max_tokens', 'max_completion_tokens', 'temperature', 'tool_choice'}):
                        raise Rejected(400, 'InvalidRequest')
                code, content_type, content = gateway.upstream('main', 'POST', path, raw, authorization[7:], self.connection)
                self.reply(code, content, content_type); return
            routes = {'/controller/initialize': 'POST', '/controller/run': 'POST', '/controller/health': 'GET'}
            if path not in routes or self.command != routes[path]: raise Rejected(404, 'UnknownOperation')
            if not gateway.authorized(self.headers.get('Authorization', '')): raise Rejected(401, 'Unauthorized')
            if path == '/controller/health':
                code, value = gateway.health(self.connection); self.reply(code, value); return
            value, raw = self.body(128 if path == '/controller/initialize' else 8192)
            if path == '/controller/initialize':
                if value: raise Rejected(400, 'InvalidRequest')
                self.reply(200, gateway.initialize(self.connection))
            else: self.reply(200, gateway.run(value, raw, self.connection))
        except Rejected as error: self.reply(error.status, {'error': error.message})
        except (OSError, ValueError): self.reply(400, {'error': 'InvalidRequest'})

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_CONNECT = do_TRACE = dispatch


class BoundedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def process_request(self, request, client_address):
        if not self.gateway.capacity.acquire(blocking=False):
            try: request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError: pass
            self.shutdown_request(request); return
        try: super().process_request(request, client_address)
        except Exception:
            self.gateway.capacity.release(); self.shutdown_request(request)

    def process_request_thread(self, request, client_address):
        timer = None
        try:
            request.settimeout(min(5, self.gateway.request_timeout))
            timer = threading.Timer(self.gateway.request_timeout, close_socket, args=(request,))
            timer.daemon = True; timer.start()
            super().process_request_thread(request, client_address)
        except (OSError, RuntimeError):
            self.shutdown_request(request)
        finally:
            if timer is not None: timer.cancel()
            self.gateway.capacity.release()

    def handle_error(self, request, client_address): pass


def make_server(address, gateway, *, role):
    if role not in {'worker', 'controller'}: raise ValueError('invalid listener role')
    server = BoundedServer(address, Handler)
    server.gateway, server.role = gateway, role
    return server


def main():
    try: gateway = Gateway(os.environ.get('KF_GATEWAY_CONTROL_KEY', ''))
    except ValueError:
        raise SystemExit('controller credential required') from None
    worker = make_server(('0.0.0.0', 8890), gateway, role='worker')
    controller = make_server(('0.0.0.0', 8891), gateway, role='controller')
    thread = threading.Thread(target=worker.serve_forever, daemon=True); thread.start()
    try: controller.serve_forever()
    finally:
        worker.shutdown(); worker.server_close(); controller.server_close(); thread.join()


if __name__ == '__main__': main()
