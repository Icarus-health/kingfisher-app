#!/usr/bin/env python3
"""Ausgehender Mac-Helfer für ausdrücklich angeforderte vollständige Sicherungen."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from create_recovery_bundle import backup


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--output-dir', type=Path, default=Path.home()/'Documents/Kingfisher-Sicherungen')
    parser.add_argument('--no-reveal', action='store_true', help='Ergebnisordner nicht im Finder öffnen')
    args = parser.parse_args()
    url = urlparse(args.url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        parser.error('Nur ein ausdrücklicher lokaler Dienst auf 127.0.0.1 ist zulässig.')
    lock_path = args.env_file.with_suffix('.backup-worker.lock')
    lock = os.fdopen(os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600), 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    config = dict(line.split('=',1) for line in args.env_file.read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
    token = config.get('ICARUS_SIDECAR_TOKEN')
    if not token:
        parser.error('Die private Zugriffskonfiguration fehlt.')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    docker = shutil.which('docker') or '/opt/homebrew/bin/docker'

    def api(body=None):
        request = Request(args.url.rstrip('/')+'/api/v1/recovery/worker',
            data=None if body is None else json.dumps(body).encode(),
            headers={'X-Icarus-Token':token, 'Content-Type':'application/json'})
        with opener.open(request, timeout=15) as response:
            return json.load(response)

    while True:
        try:
            job = api()['job']
            if job:
                result = {'id':job['id'], 'success':False, 'path':None}
                try:
                    output = backup(docker, args.container, args.env_file, args.output_dir, job['password'])
                    result.update(success=True, path=str(output))
                except (OSError, ValueError, subprocess.CalledProcessError):
                    pass  # Keine Docker-Ausgaben oder Geheimnisse ins Log.
                finally:
                    job.clear()
                # Die App kann während der Sicherung kurz offline sein. Das
                # Ergebnis zuerst zustellen, erst danach einen neuen Auftrag holen.
                while True:
                    try:
                        api(result)
                        break
                    except HTTPError as exc:
                        if exc.code == 409:
                            break
                        time.sleep(3)
                    except (OSError, ValueError):
                        time.sleep(3)
                if result['success'] and sys.platform == 'darwin' and not args.no_reveal:
                    subprocess.run(['open','-R',result['path']], capture_output=True, check=False)
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(3)


if __name__ == '__main__':
    main()
