#!/usr/bin/env python3
"""Startet den vorhandenen lokalen Mac-Bestand samt Helfern und Browser."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener


def command(*args, check=True, timeout=15):
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=timeout)


def ensure_engine(docker):
    context = command(docker, 'context', 'show').stdout.strip()
    endpoint = command(docker, 'context', 'inspect', context, '--format', '{{.Endpoints.docker.Host}}').stdout.strip()
    if not endpoint.startswith('unix://'):
        raise ValueError('Bitte einen lokalen Docker-Kontext für Kingfisher auswählen.')
    if command(docker, 'info', check=False).returncode == 0:
        return
    print('Die lokale Docker-Laufzeit wird gestartet …', flush=True)
    if context == 'colima':
        colima = shutil.which('colima') or '/opt/homebrew/bin/colima'
        command(colima, 'start', timeout=180)
    elif context in ('desktop-linux', 'default') and Path('/Applications/Docker.app').is_dir():
        command('open', '-g', '-a', 'Docker')
    else:
        raise ValueError('Die lokale Docker-Laufzeit ist nicht erreichbar. Bitte Docker starten.')
    for _ in range(60):
        if command(docker, 'info', check=False).returncode == 0:
            return
        time.sleep(1)
    raise ValueError('Docker startet noch. Bitte Kingfisher gleich erneut öffnen.')


def folder_jobs(env_file):
    selected = Path(env_file).with_suffix('.folder.json')
    if not selected.exists():
        return []
    try:
        data = json.loads(selected.read_text())
        folder = Path(data['folder']).expanduser()
        if not folder.is_absolute():
            raise ValueError('absolute path required')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError('Die lokale Ordnerauswahl ist ungültig.') from exc
    return [('mac_folder_worker.py', ['--folder', str(folder)])]


def transcript_jobs():
    """Der Helfer für den Mitschriften-Eingang läuft immer; ohne gewählten Ordner wartet er nur."""
    return [('mac_folder_worker.py', ['--role', 'transkripte'])]


def akten_jobs():
    """Der Helfer für „Akten als Ordner“ läuft immer; ohne gewählten Ordner wartet er nur."""
    return [('mac_folder_worker.py', ['--role', 'akten'])]


def start(docker, container, env_file, url):
    parsed = urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Kingfisher benötigt eine lokale Adresse auf 127.0.0.1.')
    env_file = Path(env_file).resolve()
    if not env_file.is_file():
        raise ValueError('Die private Kingfisher-Konfiguration fehlt.')
    selected_jobs = folder_jobs(env_file)
    ensure_engine(docker)
    print('Kingfisher wird gestartet …', flush=True)
    command(docker, 'start', container)
    opener = build_opener(ProxyHandler({}))
    for _ in range(60):
        try:
            with opener.open(url.rstrip('/')+'/health', timeout=1):
                break
        except OSError:
            time.sleep(.5)
    else:
        raise ValueError('Kingfisher ist noch nicht erreichbar. Bitte erneut öffnen.')
    scripts = Path(__file__).resolve().parent
    # Optional, read-only host report: Docker limits are not the Mac's RAM.
    try:
        command(sys.executable, str(scripts/'report_device.py'), '--env-file', str(env_file), '--url', url,
                check=False, timeout=8)
    except (OSError, subprocess.SubprocessError):
        pass  # the model helper explicitly displays unknown hardware
    jobs = [('mac_calendar_worker.py', []), ('mac_maps_worker.py', []), ('mac_audio_worker.py', []), ('mac_backup_worker.py', ['--container',container]),
            ('mac_autostart.py', ['--container', container])] + selected_jobs + transcript_jobs() + akten_jobs()
    for script, extra in jobs:
        log_path = env_file.parent / script.replace('.py','.log')
        fd = os.open(log_path, os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o600)
        with os.fdopen(fd,'ab') as log:
            subprocess.Popen([sys.executable,str(scripts/script),'--env-file',str(env_file),'--url',url,*extra],
                cwd=scripts.parent, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    return url.rstrip('/')+'/today'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container',required=True)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8891')
    parser.add_argument('--no-browser', action='store_true', help='Nur starten und die lokale Adresse ausgeben.')
    args=parser.parse_args()
    try:
        url=start(shutil.which('docker') or '/opt/homebrew/bin/docker',args.container,args.env_file,args.url)
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1) from None
    except (OSError,subprocess.SubprocessError):
        print('Kingfisher konnte nicht gestartet werden. Bitte die lokale Docker-Laufzeit und den vorhandenen App-Bestand prüfen.')
        raise SystemExit(1) from None
    if args.no_browser:
        print(url, flush=True)
    else:
        command('open',url)


if __name__ == '__main__':
    main()
