"""Hardware reports must not substitute container RAM or accept arbitrary metadata."""
import json
import pytest
from icarus_memory.device_profile import load_device_profile, save_device_profile


def test_unknown_host_does_not_infer_container_memory(tmp_path):
    profile = load_device_profile(tmp_path)
    assert profile['source'] == 'unknown'
    assert profile['memory_gb'] is None
    assert profile['chip'] is None
    assert profile['guidance']['model_budget_gb'] is None


def test_report_survives_restart_and_excludes_unknown_fields(tmp_path):
    profile = save_device_profile(tmp_path, {'platform': 'macos', 'chip': ' Apple M2 ', 'memory_bytes': 16 * 1024**3, 'serial': 'private-value'})
    assert profile['chip'] == 'Apple M2'
    assert profile['memory_gb'] == 16
    assert profile['source'] == 'macos_host_report'
    assert load_device_profile(tmp_path) == profile
    assert 'private-value' not in (tmp_path / 'device-profile.json').read_text()
    assert (tmp_path / 'device-profile.json').stat().st_mode & 0o777 == 0o600
    assert profile['guidance']['estimate'] is True
    assert profile['guidance']['headroom_gb'] >= 6
    assert profile['guidance']['model_budget_gb'] <= 10


@pytest.mark.parametrize('value', [True, False, 0, -1, 1024, 1024**5, 12.5, '17179869184', None])
def test_invalid_memory_cannot_replace_existing_profile(tmp_path, value):
    report = {'platform': 'macos', 'chip': 'Apple M2', 'memory_bytes': 16 * 1024**3}
    original = save_device_profile(tmp_path, report)
    with pytest.raises(ValueError):
        save_device_profile(tmp_path, {**report, 'memory_bytes': value})
    assert load_device_profile(tmp_path) == original


@pytest.mark.parametrize('value', ['x' * 129, 'Apple\nM2', '<script>', 12, None])
def test_rejects_unsafe_chip(tmp_path, value):
    with pytest.raises(ValueError):
        save_device_profile(tmp_path, {'platform': 'macos', 'chip': value, 'memory_bytes': 16 * 1024**3})


def test_missing_chip_report_is_explicit_unknown(tmp_path):
    profile = save_device_profile(tmp_path, {'platform': 'macos', 'chip': 'unknown', 'memory_bytes': 8 * 1024**3})
    assert profile['chip'] is None
    assert profile['memory_gb'] == 8
    assert profile['guidance']['model_budget_gb'] <= 2


@pytest.mark.parametrize('content', ['{broken', '[]', json.dumps({'platform': 'plan9', 'chip': 'Apple M3', 'memory_bytes': 16 * 1024**3}), ' ' * 8193])
def test_corrupt_or_wrong_platform_file_is_unknown(tmp_path, content):
    (tmp_path / 'device-profile.json').write_text(content)
    assert load_device_profile(tmp_path)['source'] == 'unknown'


@pytest.fixture
def reporter():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('report_device_under_test', Path(__file__).resolve().parents[2] / 'scripts/report_device.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_report_collects_mac_ram_and_unknown_chip(reporter, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(reporter.platform, 'system', lambda: 'Darwin')
    def sysctl(args, **kwargs):
        return SimpleNamespace(returncode=0, stdout='17179869184\n') if args[-1] == 'hw.memsize' else SimpleNamespace(returncode=1, stdout='')
    monkeypatch.setattr(reporter.subprocess, 'run', sysctl)
    monkeypatch.setattr(reporter, 'disk_free_bytes', lambda: None)
    assert reporter.collect_report() == {'chip': 'unknown', 'memory_bytes': 17179869184, 'platform': 'macos'}
    monkeypatch.setattr(reporter, 'disk_free_bytes', lambda: 210 * 1024**3)
    assert reporter.collect_report()['disk_free_bytes'] == 210 * 1024**3


def test_host_report_measures_the_ollama_model_folder_and_sends_only_a_number(reporter, monkeypatch, tmp_path):
    asked = []
    def usage(path):
        asked.append(path)
        from types import SimpleNamespace
        return SimpleNamespace(free=50 * 1024**3)
    monkeypatch.setattr(reporter.shutil, 'disk_usage', usage)
    monkeypatch.setenv('OLLAMA_MODELS', str(tmp_path / 'noch' / 'nicht' / 'da'))
    assert reporter.disk_free_bytes() == 50 * 1024**3
    assert asked == [tmp_path]  # der nächste vorhandene Ordner darüber, auf demselben Datenträger
    assert 'noch' not in json.dumps(reporter.collect_report().get('disk_free_bytes'))


def test_host_report_unknown_disk_is_left_out_not_guessed(reporter, monkeypatch):
    def broken(path):
        raise OSError('nicht lesbar')
    monkeypatch.setattr(reporter.shutil, 'disk_usage', broken)
    assert reporter.disk_free_bytes() is None


@pytest.mark.parametrize('url', ['https://external.example', 'http://127.0.0.1@external.example', 'http://localhost:8891', 'http://127.0.0.1:8891/base', 'http://127.0.0.1:8891?redirect=1'])
def test_reporter_rejects_non_loopback_or_ambiguous_urls(reporter, url):
    with pytest.raises(ValueError):
        reporter.validate_url(url)


def test_token_file_is_literal_and_never_shell_executed(reporter, tmp_path):
    marker = tmp_path / 'marker'
    env = tmp_path / 'private.env'
    env.write_text(f'ICARUS_SIDECAR_TOKEN=$(touch {marker})\n')
    with pytest.raises(ValueError):  # Spaces are not valid header tokens.
        reporter.read_token(env)
    assert not marker.exists()


def test_post_stays_on_loopback_and_does_not_follow_redirect(reporter):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    from urllib.error import HTTPError
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, self.headers.get('x-icarus-token'), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(302)
            self.send_header('Location', '/would-leak')
            self.end_headers()
        def do_GET(self):
            received.append(('redirect-followed', None, None))
            self.send_response(200)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    payload = {'platform': 'macos', 'chip': 'unknown', 'memory_bytes': 8 * 1024**3}
    try:
        with pytest.raises(HTTPError):
            reporter.publish_report(f'http://127.0.0.1:{server.server_port}', 'synthetic', payload)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert received == [('/api/v1/device/profile', 'synthetic', payload)]


def test_disk_report_is_stored_as_gigabytes_and_survives_restart(tmp_path):
    profile = save_device_profile(tmp_path, {'platform': 'macos', 'chip': 'Apple M2', 'memory_bytes': 32 * 1024**3,
                                             'disk_free_bytes': 210 * 1024**3})
    assert profile['disk_free_gb'] == 210
    assert load_device_profile(tmp_path)['disk_free_gb'] == 210
    assert load_device_profile(tmp_path / 'leer')['disk_free_gb'] is None
    ohne = save_device_profile(tmp_path, {'platform': 'macos', 'chip': 'Apple M2', 'memory_bytes': 32 * 1024**3})
    assert ohne['disk_free_gb'] is None  # nicht gemeldet: unbekannt, nie geraten


@pytest.mark.parametrize('value', [True, -1, 1024**6, 12.5, '100', [1]])
def test_invalid_disk_value_cannot_replace_the_profile(tmp_path, value):
    report = {'platform': 'macos', 'chip': 'Apple M2', 'memory_bytes': 16 * 1024**3}
    original = save_device_profile(tmp_path, report)
    with pytest.raises(ValueError):
        save_device_profile(tmp_path, {**report, 'disk_free_bytes': value})
    assert load_device_profile(tmp_path) == original


def test_local_measurement_uses_the_model_folder_and_never_the_container(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from icarus_memory import device_profile
    asked = []
    monkeypatch.setattr(device_profile.shutil, 'disk_usage', lambda p: asked.append(p) or SimpleNamespace(free=12 * 1024**3))
    ordner = tmp_path / 'modelle'
    ordner.mkdir()
    assert device_profile.freier_platz_gb({'OLLAMA_MODELS': str(ordner)}, im_container=False) == 12
    assert asked == [ordner]
    assert device_profile.freier_platz_gb({'OLLAMA_MODELS': str(ordner / 'fehlt' / 'noch')}, im_container=False) == 12
    assert asked[-1] == ordner  # der nächste vorhandene Ordner darüber
    asked.clear()
    assert device_profile.freier_platz_gb({}, im_container=True) is None and asked == []  # Container: kein Raten
    assert device_profile.ollama_modellordner({}).parts[-2:] == ('.ollama', 'models')


def test_local_measurement_failure_is_unknown(monkeypatch):
    from icarus_memory import device_profile
    def broken(path):
        raise OSError('nicht lesbar')
    monkeypatch.setattr(device_profile.shutil, 'disk_usage', broken)
    assert device_profile.freier_platz_gb({}, im_container=False) is None
