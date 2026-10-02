#!/usr/bin/env python3
"""Öffnet einen wiederhergestellten Bestand als getrennte lokale Kingfisher-App."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import uuid
from urllib.request import urlopen


def run(docker, *args):
    return subprocess.run([docker, *args], check=True, capture_output=True, text=True).stdout.strip()


def require_inspection(docker, image):
    pinned = run(docker, 'image', 'inspect', '--format', '{{.Id}}', image)
    if not pinned.startswith('sha256:') or len(pinned) != 71:
        raise ValueError('Keine eindeutige lokale Prüfversion vorhanden.')
    try:
        capability = run(docker, 'run', '--rm', '--network', 'none', '--entrypoint', 'python', pinned,
            '-c', 'from icarus_memory.restore_boundary import CAPABILITY; print(CAPABILITY)')
    except subprocess.CalledProcessError:
        raise ValueError('Diese App-Version unterstützt den sicheren Prüfmodus nicht. Der wiederhergestellte Bestand bleibt erhalten.') from None
    if capability != '1':
        raise ValueError('Diese App-Version unterstützt den sicheren Prüfmodus nicht.')
    return pinned


def start(docker, folder, image):
    folder = Path(folder).resolve()
    fd = os.open(folder/'app.lock', os.O_WRONLY|os.O_CREAT, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Diese wiederhergestellte App wird bereits geöffnet.') from None
        return _start(docker, folder, image)


def _start(docker, folder, image):
    if ',' in str(folder):
        raise ValueError('Der Wiederherstellungsordner darf kein Komma enthalten.')
    state_file = folder / 'app.json'
    if state_file.exists():
        state = json.loads(state_file.read_text())
        info = json.loads(run(docker, 'inspect', state['container']))[0]
        if (info['Config'].get('Labels') or {}).get('kingfisher.restore') != state['owner']:
            raise ValueError('Die gespeicherte App-Zuordnung stimmt nicht überein.')
        config = info['Config']
        if ((config.get('Labels') or {}).get('kingfisher.restore-boundary') != '1'
                or 'ICARUS_RESTORE_INSPECTION=1' not in config.get('Env', [])):
            raise ValueError('Diese ältere Wiederherstellung unterstützt den Prüfmodus nicht. Bestand mit einer kompatiblen Version separat öffnen.')
        require_inspection(docker, info['Image'])
        run(docker, 'start', state['container'])
    else:
        if not (folder/'data').is_dir() or not (folder/'settings.env').is_file():
            raise ValueError('Der wiederhergestellte Bestand ist unvollständig.')
        image = require_inspection(docker, image)
        owner = uuid.uuid4().hex
        name = 'kingfisher-restored-' + owner[:12]
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        state = {'container':name, 'owner':owner, 'port':port, 'image':image}
        run(docker, 'volume', 'create', '--label', 'kingfisher.restore='+owner, name)
        try:
            # Der Originalordner bleibt als unveränderte Wiederherstellung erhalten.
            run(docker, 'run', '--rm', '--network', 'none', '--user', '0',
                '--mount', 'type=bind,source='+str(folder/'data')+',target=/source,readonly',
                '--mount', 'type=volume,source='+name+',target=/data',
                '--entrypoint', 'python', image, '-c',
                'import os,shutil\nfrom pathlib import Path\n'
                'for p in Path("/source").iterdir():\n'
                ' if p.is_symlink() or not p.is_file(): raise ValueError("Ungültige Quelldatei")\n'
                ' shutil.copy2(p,Path("/data")/p.name)\n'
                'from icarus_memory.restore_boundary import mark_pending\n'
                'mark_pending(Path("/data"),"restored_launcher")\n'
                'for p in [Path("/data"),*Path("/data").iterdir()]: os.chown(p,1000,1000)')
            run(docker, 'create', '--name', name, '--label', 'kingfisher.restore='+owner,
                '--label', 'kingfisher.restore-boundary=1',
                '--restart', 'unless-stopped', '--env-file', str(folder/'settings.env'),
                '-e', 'ICARUS_DATA_DIR=/data', '-e', 'ICARUS_RESTORE_INSPECTION=1',
                '--add-host', 'host.docker.internal:host-gateway',
                '-p', '127.0.0.1:'+str(port)+':8890', '-v', name+':/data', image)
        except Exception:
            # Nur das hier neu angelegte Volume entfernen; der Quellordner bleibt.
            run(docker, 'volume', 'rm', name)
            raise
        fd = os.open(state_file, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream)
        run(docker, 'start', name)
    url = 'http://127.0.0.1:'+str(state['port'])
    for _ in range(60):
        try:
            with urlopen(url+'/health', timeout=1):
                return url
        except OSError:
            time.sleep(.5)
    raise ValueError('Die wiederhergestellte App ist noch nicht erreichbar. Erneut öffnen.')


def install(folder, image):
    folder = Path(folder)
    shutil.copy2(__file__, folder/'open_restored_app.py')
    (folder/'image.txt').write_text(image+'\n')
    launcher = folder/'Kingfisher-öffnen.command'
    launcher.write_text('#!/bin/bash\nset -euo pipefail\ncd "$(dirname "$0")"\n/usr/bin/python3 open_restored_app.py\n')
    launcher.chmod(0o700)


def main():
    folder = Path(__file__).resolve().parent
    try:
        url = start(shutil.which('docker') or '/opt/homebrew/bin/docker', folder, (folder/'image.txt').read_text().strip())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        print('App nicht geöffnet. Bitte Docker starten und die Wiederherstellung erneut öffnen.')
        raise SystemExit(1) from None
    subprocess.run(['open', url+'/today'], check=False)


if __name__ == '__main__':
    main()
