"""Fixed controller-only gateway client; no proxy, redirects or retries.

The control credential is supplied by trusted lifecycle wiring, never read from
an inherited environment or passed to a worker. No listener is bound here.
"""
import http.client
import json
import re
import socket
import threading
import time


_KEY = re.compile(r'[A-Za-z0-9_-]{43}\Z')
_MAX_RESPONSE = 262144


class GatewayError(ValueError):
    def __init__(self):
        super().__init__('GatewayUnavailable')


class BoundedHeaderReader:
    """Bound bytes consumed by the stdlib response-header parser."""
    def __init__(self, stream):
        self._stream, self._remaining = stream, 8192

    def readline(self, limit=-1):
        limit = self._remaining + 1 if limit < 0 else min(limit, self._remaining + 1)
        line = self._stream.readline(limit)
        self._remaining -= len(line)
        if self._remaining < 0:
            raise ValueError('response headers exceeded')
        return line

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _BoundedResponse(http.client.HTTPResponse):
    def begin(self):
        original = self.fp
        self.fp = BoundedHeaderReader(original)
        try:
            return super().begin()
        finally:
            if self.fp is not None:
                self.fp = original


def _object(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(_value):
        raise ValueError('nonfinite JSON value')
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if not isinstance(result, dict):
        raise ValueError('JSON object required')
    return result


def _close_owned_socket(owned):
    if owned is not None:
        try:
            owned.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            owned.close()
        except OSError:
            pass


class FixedGatewayClient:
    def __init__(self, control_key, *, clock=time.monotonic):
        if not isinstance(control_key, str) or not _KEY.fullmatch(control_key):
            raise ValueError('gateway control credential required')
        self.__key, self._clock = control_key, clock

    def now(self):
        return self._clock()

    def health(self):
        return self._request('GET', '/controller/health', None, threading.Event(), self._clock() + 3)

    def initialize(self):
        value = self._request('POST', '/controller/initialize', b'{}', threading.Event(), self._clock() + 3)
        if value != {'status': 'initialized'}:
            raise GatewayError()
        return value

    def run(self, token, question, cancelled, deadline):
        if (not isinstance(token, str) or not _KEY.fullmatch(token)
                or not isinstance(question, str) or not 1 <= len(question.strip()) <= len(question) <= 1200
                or type(deadline) not in (int, float) or not self._clock() < deadline <= self._clock() + 120):
            raise GatewayError()
        raw = json.dumps(dict(token=token, request=question), ensure_ascii=False,
                         separators=(',', ':')).encode()
        if len(raw) > 8192:
            raise GatewayError()
        return self._request('POST', '/controller/run', raw, cancelled,
                             min(deadline, self._clock() + 115))

    def _request(self, method, path, body, cancelled, deadline):
        if cancelled.is_set() or self._clock() >= deadline:
            raise GatewayError()
        # This stdlib transport reads no proxy environment, follows no redirects
        # and does not retry. Fixed service-name DNS belongs to verified topology.
        connection = http.client.HTTPConnection('kingfisher-gateway-control', 8891,
                                                timeout=min(115, deadline - self._clock()))
        connection.response_class = _BoundedResponse
        stopped = threading.Event()
        watcher = None
        connected_socket = None
        def watch():
            while not stopped.wait(.025):
                if cancelled.is_set() or self._clock() >= deadline:
                    _close_owned_socket(connected_socket)
                    return
        try:
            watcher = threading.Thread(target=watch, daemon=True, name='kf-gateway-deadline')
            watcher.start()
            connection.connect()
            # getresponse() may set connection.sock=None while its response
            # makefile still owns this socket (normal Connection: close).
            connected_socket = connection.sock
            if cancelled.is_set() or self._clock() >= deadline:
                raise GatewayError()
            headers = dict(Accept='application/json', Connection='close',
                           Authorization='Bearer ' + self.__key)
            if body is not None:
                headers['Content-Type'] = 'application/json'
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise GatewayError()
            lengths = response.headers.get_all('Content-Length', [])
            transfers = response.headers.get_all('Transfer-Encoding', [])
            if (len(lengths) > 1 or len(transfers) > 1 or (lengths and transfers)
                    or (lengths and (not re.fullmatch(r'[0-9]{1,10}', lengths[0])
                                     or int(lengths[0]) > _MAX_RESPONSE))
                    or (transfers and transfers != ['chunked'])
                    or response.headers.get('Content-Encoding', 'identity') != 'identity'
                    or response.headers.get('Content-Type', '').split(';', 1)[0].lower() != 'application/json'):
                raise GatewayError()
            raw = response.read(_MAX_RESPONSE + 1)
            if (len(raw) > _MAX_RESPONSE or (lengths and len(raw) != int(lengths[0]))
                    or cancelled.is_set() or self._clock() >= deadline):
                raise GatewayError()
            return _object(raw)
        except Exception:
            # HTTP/provider errors may contain credentials, request prose or DNS
            # details. Never expose those diagnostics through API/log output.
            raise GatewayError() from None
        finally:
            stopped.set()
            if watcher is not None and watcher.ident is not None:
                watcher.join(.1)
            connection.close()
