#!/usr/bin/env python3
"""Sichert eine lokale Docker-Instanz; das Sicherungspasswort bleibt im Arbeitsspeicher."""
from __future__ import annotations

import argparse
from datetime import datetime
import getpass
import fcntl
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

WORKER = '''import json, sys, shutil, tempfile
from pathlib import Path
from icarus_memory.backup import BACKUP_DATA_FILES, verify_snapshot_set
from icarus_memory.recovery_bundle import export_bundle, restore_bundle
request = json.load(sys.stdin)
with tempfile.TemporaryDirectory() as root:
    work = Path(root)
    source = work / 'source'
    source.mkdir()
    for name in BACKUP_DATA_FILES:
        for suffix in ('', '-wal'):
            path = Path('/source') / (name + suffix)
            if path.is_symlink(): raise RuntimeError('Symlink im Datenbestand')
            if path.is_file(): shutil.copy2(path, source / path.name)
    output = export_bundle(source, Path('/configuration'), Path('/output') / request['name'], request['password'], image_id=request['image'])
    restored = restore_bundle(output, work / 'restored', request['password'])
    verify_snapshot_set(restored / 'data')
    if (restored / 'settings.env').read_bytes() != Path('/configuration').read_bytes():
        raise RuntimeError('Konfiguration stimmt nach Wiederherstellung nicht überein')
print('Sicherung und Wiederherstellungsprüfung erfolgreich.')
'''


def docker_call(docker, arguments, **kwargs):
    return subprocess.run([docker, *arguments], check=True, text=True,
                          capture_output=True, **kwargs)


class ConfigurationError(ValueError):
    """Verständlicher Konfigurationsfehler ohne geheime Werte."""


def validate_configuration(env_file, container_env):
    """Nur wörtliche Docker-Werte vergleichen, nie Shell-Code ausführen."""
    configured = {}
    for line in Path(env_file).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.lstrip().partition('=')
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) or key in configured:
            raise ConfigurationError('Die Docker-Konfiguration enthält keine eindeutigen wörtlichen Werte.')
        configured[key] = value
    required = ('ICARUS_SIDECAR_TOKEN', 'ICARUS_SECRETS_PASSPHRASE')
    actual = dict(entry.split('=', 1) for entry in container_env if '=' in entry)
    if any(not configured.get(key) for key in required) or any(
        actual.get(key) != value for key, value in configured.items()
    ):
        raise ConfigurationError('Die Sicherungskonfiguration passt nicht zur gewählten Kingfisher-Instanz.')


def backup(docker, container, env_file, output_dir, password):
    config = Path(env_file).resolve()
    if not config.is_file():
        raise ValueError('Die private Docker-Konfiguration fehlt.')
    lock_path = config.with_suffix(config.suffix + '.recovery.lock')
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Für diese Instanz läuft bereits eine Sicherung.') from None
        # Dieselben geprüften Bytes exportieren, auch wenn die originale Datei
        # während der Sicherung geändert wird. Im freigegebenen Hostordner
        # bleibt die Kopie auch für Docker auf dem Mac erreichbar.
        with tempfile.TemporaryDirectory(prefix='.kingfisher-backup-', dir=config.parent) as temporary:
            frozen = Path(temporary) / 'settings.env'
            frozen.write_bytes(config.read_bytes())
            frozen.chmod(0o600)
            return _backup(docker, container, frozen, output_dir, password)


def _backup(docker, container, env_file, output_dir, password):
    env_file = Path(env_file).resolve()
    output_dir = Path(output_dir).resolve()
    if not env_file.is_file():
        raise ValueError('Die private Docker-Konfiguration fehlt.')
    if len(password) < 16:
        raise ValueError('Bitte mindestens 16 Zeichen als Sicherungspasswort verwenden.')
    state = json.loads(docker_call(docker, ['inspect', '--format',
        '{"image":{{json .Image}},"running":{{.State.Running}},"mounts":{{json .Mounts}},"env":{{json .Config.Env}}}', container]).stdout)
    validate_configuration(env_file, state['env'])
    mounts = [mount for mount in state['mounts'] if mount['Destination'] == '/data']
    if len(mounts) != 1 or mounts[0]['Type'] not in ('volume', 'bind'):
        raise ValueError('Kein eindeutiger persistenter Kingfisher-Datenordner gefunden.')
    mount = mounts[0]
    source = mount['Name'] if mount['Type'] == 'volume' else mount['Source']
    image = state['image']
    # Prüfen, bevor die laufende App angehalten wird.
    docker_call(docker, ['run', '--rm', '--network', 'none', '--entrypoint', 'python', image,
                         '-c', 'import icarus_memory.recovery_bundle'])
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = 'Kingfisher-' + datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8] + '.recovery'
    try:
        if state['running']:
            docker_call(docker, ['stop', container])
        docker_call(docker, ['run', '--rm', '-i', '--network', 'none', '--user', '0',
            '--mount', f'type={mount["Type"]},source={source},target=/source,readonly',
            '--mount', f'type=bind,source={env_file},target=/configuration,readonly',
            '--mount', f'type=bind,source={output_dir},target=/output',
            '--entrypoint', 'python', image, '-c', WORKER],
            input=json.dumps({'password': password, 'name': name, 'image': image}))
    finally:
        # Auch bei Fehlern während Stoppen, Kopieren oder Prüfen wieder starten.
        if state['running']:
            docker_call(docker, ['start', container])
            docker_call(docker, ['exec', container, 'python', '-c',
                "import time, urllib.request\n"
                "for attempt in range(60):\n"
                " try:\n"
                "  urllib.request.urlopen('http://127.0.0.1:8890/health', timeout=1); break\n"
                " except Exception: time.sleep(0.5)\n"
                "else: raise RuntimeError('Kingfisher ist nach dem Start nicht erreichbar')"])
    return output_dir / name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path.home() / 'Documents/Kingfisher-Sicherungen')
    args = parser.parse_args()
    docker = shutil.which('docker') or '/opt/homebrew/bin/docker'
    print('Kingfisher wird kurz angehalten und anschließend wieder gestartet.')
    print('Das Passwort wird nicht gespeichert. Ohne dieses Passwort ist die Sicherung nicht wiederherstellbar.')
    password = getpass.getpass('Sicherungspasswort (mindestens 16 Zeichen): ')
    if password != getpass.getpass('Passwort wiederholen: '):
        parser.error('Die Passwörter stimmen nicht überein.')
    try:
        output = backup(docker, args.container, args.env_file, args.output_dir, password)
    except ConfigurationError as exc:
        print(str(exc))
        raise SystemExit(1) from None
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        # Docker-Ausgaben können private Pfade oder Konfigurationsinhalte enthalten.
        print('Sicherung nicht abgeschlossen. Bitte Docker und den Zustand der Kingfisher-Instanz prüfen.')
        raise SystemExit(1) from None
    print('Sicherung erstellt und Wiederherstellung geprüft:\n' + str(output))
    if os.uname().sysname == 'Darwin':
        subprocess.run(['open', '-R', str(output)], check=False)


if __name__ == '__main__':
    main()
