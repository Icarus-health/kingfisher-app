"""Run the actual native coordinator with synthetic I/O; never touch EventKit."""
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which('swiftc') is None, reason='Swift unavailable')
def test_native_calendar_coordinator(tmp_path):
    binary = tmp_path / 'calendar-contract'
    result = subprocess.run(['swiftc', '-module-cache-path', str(tmp_path / 'modules'),
                             str(ROOT / 'macos/Shared/NativeCalendar.swift'),
                             str(ROOT / 'macos/App/Logic/CalendarPermissionRequest.swift'),
                             str(ROOT / 'macos/tests/calendar/main.swift'), '-o', str(binary)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Native calendar behavior passed' in result.stdout


@pytest.mark.skipif(shutil.which('swiftc') is None, reason='Swift unavailable')
def test_native_calendar_http_refuses_redirects_and_oversized_responses(tmp_path):
    source = tmp_path / 'main.swift'
    source.write_text('''import Foundation
let client = CalendarHTTP(origin: URL(string: CommandLine.arguments[1])!,
                          tokenFile: URL(fileURLWithPath: CommandLine.arguments[2]))
defer { client.stop() }
do {
    let value = try client.request(CommandLine.arguments[3], nil)
    print(value["synthetic"] as? Bool == true ? "ok" : "bad")
} catch { print("rejected") }
''')
    binary = tmp_path / 'calendar-http'
    result = subprocess.run(['swiftc', '-module-cache-path', str(tmp_path / 'modules'),
        str(ROOT / 'macos/Shared/NativeCalendar.swift'), str(ROOT / 'macos/Shared/CalendarHTTP.swift'),
        str(ROOT / 'macos/Shared/PowerReporter.swift'), str(source), '-o', str(binary)],
        capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    token = tmp_path / 'synthetic.env'
    token.write_text('ICARUS_SIDECAR_TOKEN=synthetic-calendar-http\n')
    seen = []
    mode = ['ok']

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append((self.path, self.headers.get('x-icarus-token')))
            if mode[0] == 'redirect':
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{self.server.server_port}/untrusted')
                self.end_headers()
            elif mode[0] == 'large':
                self.send_response(200)
                self.send_header('Content-Length', str(8 * 1024 * 1024 + 1))
                self.end_headers()
            else:
                body = b'{"synthetic":true}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        def run(url=origin, path=''):
            result = subprocess.run([str(binary), url, str(token), path], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        assert run() == 'ok'
        assert seen == [('/api/v1/mac-calendar', 'synthetic-calendar-http')]
        for rejected in ['redirect', 'large']:
            mode[0] = rejected
            before = len(seen)
            assert run() == 'rejected'
            assert len(seen) == before + 1
        before = len(seen)
        assert run(path='/untrusted') == 'rejected'
        assert run(url=origin + '/other') == 'rejected'
        assert len(seen) == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
