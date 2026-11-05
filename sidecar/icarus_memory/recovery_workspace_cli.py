"""Prüfen, getrennte Arbeitskopie vorbereiten und lokal starten.

Dieser technische Startweg ersetzt noch nicht die native Produktabnahme.
Keine Browseröffnung, keine Installation und kein Start bei check/prepare.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .backup import BackupError
from .recovery_preflight import preflight
from .recovery_workspace import launch_environment, prepare_working_copy

CONTAINER_MARKER = Path('/.dockerenv')


def port(value):
    value = int(value)
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError('Port muss zwischen 1 und 65535 liegen.')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check', help='Nur lesenden Prüfbefund ausgeben.')
    check.add_argument('--source', type=Path, required=True)
    prepare = commands.add_parser('prepare', help='Geprüften, ausdrücklich gewählten Stand separat kopieren.')
    prepare.add_argument('--source', type=Path, required=True)
    prepare.add_argument('--target', type=Path, required=True)
    prepare.add_argument('--fingerprint', required=True)
    prepare.add_argument('--selection', required=True)
    prepare.add_argument('--acknowledge-unknown-history', action='store_true')
    serve = commands.add_parser('serve', help='Vorhandene Arbeitskopie mit neuer Startumgebung öffnen.')
    serve.add_argument('--folder', type=Path, required=True)
    serve.add_argument('--port', type=port, default=8895)
    serve.add_argument('--container', action='store_true', help='Nur im Docker-Container: interner Listener; Host muss auf Loopback veröffentlichen.')
    args = parser.parse_args(argv)
    try:
        if args.command == 'check':
            print(json.dumps(preflight(args.source), ensure_ascii=False, indent=2))
        elif args.command == 'prepare':
            result = prepare_working_copy(args.source, args.target, fingerprint=args.fingerprint,
                selection=args.selection, acknowledge_unknown=args.acknowledge_unknown_history)
            print('Getrennte Arbeitskopie vorbereitet. Noch nicht gestartet: ' + str(result))
        else:
            environment = launch_environment(args.folder)
            if args.container and not CONTAINER_MARKER.is_file():
                raise ValueError('Der Container-Start ist nur innerhalb von Docker erlaubt.')
            host = '0.0.0.0' if args.container else '127.0.0.1'
            print('Arbeitskopie startet · keine Verbindungen automatisch übernommen.', flush=True)
            return subprocess.run([sys.executable, '-m', 'uvicorn', 'icarus_memory.server:create_app',
                '--factory', '--host', host, '--port', str(args.port), '--log-level', 'warning'],
                env=environment, check=False).returncode
    except (OSError, ValueError, BackupError, KeyError):
        print('Nicht abgeschlossen. Prüfbefund, ausdrückliche Auswahl und neuen Zielordner beziehungsweise Startdatei prüfen.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
