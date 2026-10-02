#!/usr/bin/env python3
"""Meldet ausschließlich Chip, Gesamtspeicher und freien Platz für Modelle des Rechners an den lokalen Sidecar.

macOS, Windows und Linux; es werden keine Seriennummern, Namen oder Pfade gesendet.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def read_token(path: Path) -> str:
    values = []
    for line in path.read_text(encoding='utf-8').splitlines():
        key, separator, value = line.strip().partition('=')
        if separator and key == 'ICARUS_SIDECAR_TOKEN':
            values.append(value.strip())
    if len(values) != 1 or not values[0] or any(ord(c) < 0x21 or ord(c) > 0x7e for c in values[0]):
        raise ValueError('Der lokale Zugriffsschlüssel fehlt oder ist ungültig.')
    return values[0]


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
        valid = (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                 and parsed.username is None and parsed.password is None
                 and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
                 and (port is None or 0 < port < 65536))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Eine lokale Kingfisher-Adresse auf 127.0.0.1 ist erforderlich.')
    return url.rstrip('/')


def _collect_linux() -> dict:
    kilobytes = None
    with open('/proc/meminfo', encoding='ascii') as handle:
        for line in handle:
            if line.startswith('MemTotal:'):
                kilobytes = int(line.split()[1])
                break
    chip = 'unknown'
    try:
        with open('/proc/cpuinfo', encoding='utf-8', errors='replace') as handle:
            for line in handle:
                if line.startswith('model name'):
                    candidate = line.partition(':')[2].strip()
                    if re.fullmatch(r'[A-Za-z0-9 ()+.,:_/-]{1,128}', candidate):
                        chip = candidate
                    break
    except OSError:
        pass
    if kilobytes is None:
        raise ValueError('Der Arbeitsspeicher konnte nicht gelesen werden.')
    return {'chip': chip, 'memory_bytes': kilobytes * 1024, 'platform': 'linux'}


def _collect_windows() -> dict:
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong),
                    ('avail', ctypes.c_ulonglong), ('page_total', ctypes.c_ulonglong),
                    ('page_avail', ctypes.c_ulonglong), ('virtual_total', ctypes.c_ulonglong),
                    ('virtual_avail', ctypes.c_ulonglong), ('extended', ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
        raise ValueError('Der Arbeitsspeicher konnte nicht gelesen werden.')
    chip = platform.processor()
    return {'chip': chip if re.fullmatch(r'[A-Za-z0-9 ()+.,:_/-]{1,128}', chip or '') else 'unknown',
            'memory_bytes': int(status.total), 'platform': 'windows'}


def disk_free_bytes() -> int | None:
    """Freier Platz dort, wo Ollama seine Modelle ablegt (`OLLAMA_MODELS`, sonst `~/.ollama/models`).

    Nur die Zahl wird gemeldet, nie ein Pfad. Fehlt der Ordner noch, zählt der nächste vorhandene darüber.
    """
    eigener = os.environ.get('OLLAMA_MODELS', '').strip()
    kandidat = Path(eigener).expanduser() if eigener else Path.home() / '.ollama' / 'models'
    while not kandidat.exists() and kandidat != kandidat.parent:
        kandidat = kandidat.parent
    for ort in (kandidat, Path.home()):
        try:
            return int(shutil.disk_usage(ort).free)
        except OSError:
            continue
    return None


def collect_report() -> dict:
    report = _collect_platform()
    frei = disk_free_bytes()
    if frei is not None:
        report['disk_free_bytes'] = frei
    return report


def _collect_platform() -> dict:
    system = platform.system()
    if system == 'Linux':
        return _collect_linux()
    if system == 'Windows':
        return _collect_windows()
    if system != 'Darwin':
        raise ValueError('Dieser Hardwarebericht kennt nur macOS, Windows und Linux.')
    memory_result = subprocess.run(['/usr/sbin/sysctl', '-n', 'hw.memsize'], capture_output=True, text=True, timeout=3)
    if memory_result.returncode:
        raise ValueError('Der Mac-Speicher konnte nicht gelesen werden.')
    memory = int(memory_result.stdout.strip())
    if not 1024**3 <= memory <= 4096 * 1024**3:
        raise ValueError('Die Mac-Speicherangabe ist ungültig.')
    chip = 'unknown'
    try:
        chip_result = subprocess.run(['/usr/sbin/sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True, timeout=3)
        candidate = chip_result.stdout.strip()
        if chip_result.returncode == 0 and re.fullmatch(r'[A-Za-z0-9 ()+.,:_/-]{1,128}', candidate):
            chip = candidate
    except (OSError, subprocess.SubprocessError):
        pass
    return {'chip': chip, 'memory_bytes': memory, 'platform': 'macos'}


def publish_report(url: str, token: str, report: dict) -> None:
    address = validate_url(url) + '/api/v1/device/profile'
    request = Request(address, data=json.dumps(report).encode('utf-8'), method='POST',
                      headers={'Content-Type': 'application/json', 'x-icarus-token': token})
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=5) as response:
        if not 200 <= response.status < 300:
            raise ValueError('Die Hardwaremeldung wurde nicht angenommen.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    args = parser.parse_args()
    try:
        url = validate_url(args.url)
        token = read_token(args.env_file)
        publish_report(url, token, collect_report())
    except (OSError, ValueError, subprocess.SubprocessError):
        # Never print exception text: server errors and env data can contain secrets.
        print('Die Mac-Hardware konnte nicht gemeldet werden. Die Gerätehilfe bleibt ohne diese Angabe.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
