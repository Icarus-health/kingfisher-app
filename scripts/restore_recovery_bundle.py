#!/usr/bin/env python3
"""Entschlüsselt eine Sicherung in einen neuen Ordner; die laufende App bleibt unberührt."""
import argparse
from datetime import datetime
import getpass
import json
from pathlib import Path
import shutil
import subprocess
import uuid

WORKER = '''import json, sys
from pathlib import Path
from icarus_memory.recovery_bundle import restore_bundle
request = json.load(sys.stdin)
restore_bundle(Path('/package'), Path('/output') / request['name'], request['password'])
print('Wiederherstellung geprüft.')
'''


def resolve_image(docker, container=None, image=None):
    if image:
        command = [docker, 'image', 'inspect', '--format', '{{.Id}}', image]
    elif container:
        command = [docker, 'inspect', '--format', '{{.Image}}', container]
    else:
        raise ValueError('Eine lokale App-Version oder ein vorhandener Container ist erforderlich.')
    # Nur lokal vorhandene Images verwenden; kein automatisches Herunterladen.
    resolved = subprocess.run(command, text=True, capture_output=True, check=True).stdout.strip()
    if not resolved.startswith('sha256:') or len(resolved) != 71:
        raise ValueError('Keine eindeutige lokale App-Version gefunden.')
    return resolved


def restore(docker, container, bundle, target, password, image=None):
    bundle = Path(bundle).resolve()
    target = Path(target).absolute()
    if not bundle.is_file() or target.exists() or target.is_symlink():
        raise ValueError('Paketdatei und ein neues Zielverzeichnis erforderlich.')
    image = resolve_image(docker, container, image)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([docker, 'run', '--rm', '-i', '--network', 'none', '--user', '0',
        '--mount', f'type=bind,source={bundle},target=/package,readonly',
        '--mount', f'type=bind,source={target.parent},target=/output',
        '--entrypoint', 'python', image, '-c', WORKER],
        input=json.dumps({'name': target.name, 'password': password}), text=True,
        capture_output=True, check=True)
    # Old extraction images are supported, but cannot silently authorize startup.
    if target.is_dir():
        marker = target / 'data' / 'restore-state.json'
        marker.write_text(json.dumps({'version': 1, 'mode': 'inspection',
            'restore_id': uuid.uuid4().hex, 'reason': 'host_restore', 'operational': False}))
        marker.chmod(0o600)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', help='Vorhandene Kingfisher-Instanz')
    parser.add_argument('--image', help='Ausdrücklich ausgewählte lokale App-Version für die Wiederherstellung')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--open-app', action='store_true', help='Wiederhergestellten Bestand als eigene App öffnen')
    args = parser.parse_args()
    if not args.container and not args.image:
        parser.error('--container oder --image ist erforderlich')
    bundle = args.bundle
    if bundle is None:
        picked = subprocess.run(['osascript', '-e', 'POSIX path of (choose file with prompt "Kingfisher-Sicherung auswählen")'],
                                text=True, capture_output=True)
        if picked.returncode:
            return
        bundle = Path(picked.stdout.strip())
    target = args.target or Path.home() / 'Documents' / ('Kingfisher-Wiederhergestellt-' + datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6])
    print('Die Sicherung wird in einen neuen Ordner entschlüsselt. Deine laufende App wird nicht ersetzt.')
    password = getpass.getpass('Sicherungspasswort: ')
    try:
        docker = shutil.which('docker') or '/opt/homebrew/bin/docker'
        image = resolve_image(docker, args.container, args.image)
        result = restore(docker, args.container, bundle, target, password, image=image)
    except (OSError, ValueError, subprocess.CalledProcessError):
        print('Wiederherstellung nicht abgeschlossen. Passwort, Sicherungsdatei, Docker und neues Zielverzeichnis prüfen.')
        raise SystemExit(1) from None
    print('Wiederhergestellter Bestand und Docker-Konfiguration:\n' + str(result))
    if args.open_app:
        from open_restored_app import install, start
        docker = shutil.which('docker') or '/opt/homebrew/bin/docker'
        try:
            version_file = result / 'app-version.json'
            if not args.image and version_file.is_file():
                saved_image = json.loads(version_file.read_text())['image']
                image = resolve_image(docker, image=saved_image)
            install(result, image)
            url = start(docker, result, image)
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
            print('Bestand wiederhergestellt. App noch nicht geöffnet. Die zur Sicherung passende lokale App-Version und Docker prüfen; der wiederhergestellte Ordner bleibt erhalten.')
        else:
            subprocess.run(['open', url+'/today'], check=False)
    subprocess.run(['open', str(result)], check=False)


if __name__ == '__main__':
    main()
