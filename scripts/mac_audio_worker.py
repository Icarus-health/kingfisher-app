#!/usr/bin/env python3
"""Generate explicitly requested speech using the installed macOS Anna voice."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def validate_url(value):
    url = urlparse(value)
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.password
            or url.path not in ('', '/') or url.query or url.fragment):
        raise ValueError('Nur der lokale Kingfisher auf 127.0.0.1 ist zulässig.')
    return value.rstrip('/')


def synthesize(text, voice):
    if not isinstance(text, str) or not text.strip() or len(text) > 8000 or '\x00' in text:
        raise ValueError('Ungültiger Briefingtext.')
    with tempfile.TemporaryDirectory(prefix='kingfisher-audio-') as folder:
        source, target = Path(folder)/'text.txt', Path(folder)/'speech.wav'
        source.write_text(text, encoding='utf-8')
        source.chmod(0o600)
        subprocess.run(['/usr/bin/say', '-v', voice, '-f', str(source), '-o', str(target),
                        '--file-format=WAVE', '--data-format=LEI16@22050'],
                       check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if target.stat().st_size > 10*1024*1024:
            raise ValueError('Audio zu groß.')
        return target.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--env-file', required=True, type=Path)
    args = parser.parse_args()
    try:
        url = validate_url(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.platform != 'darwin':
        parser.error('Lokale Sprachausgabe benötigt macOS.')
    lock = os.fdopen(os.open(args.env_file.with_suffix('.audio-worker.lock'), os.O_WRONLY|os.O_CREAT, 0o600), 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        return
    voices = subprocess.run(['/usr/bin/say', '-v', '?'], capture_output=True, text=True, check=True, timeout=10).stdout
    if not re.search(r'^Anna\s+de_DE\s', voices, re.M):
        parser.error('Die lokale deutsche Stimme Anna ist nicht installiert.')
    private = dict(line.split('=',1) for line in args.env_file.read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
    token = private.get('ICARUS_SIDECAR_TOKEN')
    if not token:
        parser.error('Die private Zugriffskonfiguration fehlt.')
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def api(body=None):
        req = Request(url+'/api/v1/audio-worker', data=None if body is None else json.dumps(body).encode(),
                      headers={'X-Icarus-Token': token, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=15) as response:
            return json.load(response)

    while True:
        try:
            job = api().get('job')
            if job:
                result = {'id': job['id'], 'success': False, 'audio_base64': ''}
                try:
                    result.update(success=True, audio_base64=base64.b64encode(synthesize(job['text'], 'Anna')).decode('ascii'))
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
                finally:
                    job.clear()
                try:
                    api(result)
                finally:
                    result.clear()
        except (OSError, ValueError, KeyError):
            pass  # No personal text, credentials or server errors in logs.
        time.sleep(2)


if __name__ == '__main__':
    main()
