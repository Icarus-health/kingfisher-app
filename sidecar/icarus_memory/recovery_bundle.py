"""Verschlüsseltes Docker-Wiederherstellungspaket; nur bei gestoppter App verwenden."""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
import shutil
import tempfile

from .backup import BACKUP_DATA_FILES, SNAPSHOT_MANIFEST, BackupError, snapshot_all, verify_snapshot_set
from .crypto import DecryptionError, seal_json, unseal_json

MAGIC = 'kingfisher-recovery-v1'


def export_bundle(data_dir: Path, env_file: Path, output: Path, passphrase: str, *, image_id: str | None = None) -> Path:
    """Enthält Daten, Prüfsummen und die explizit angegebene Docker-Konfiguration."""
    if image_id is not None and not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise BackupError('Ungültige App-Version für die Sicherung.')
    if len(passphrase) < 16:
        raise BackupError('Die Wiederherstellungs-Passphrase muss mindestens 16 Zeichen haben.')
    if output.exists():
        raise BackupError('Die Zieldatei existiert bereits.')
    if not env_file.is_file() or env_file.is_symlink():
        raise BackupError('Eine reguläre Docker-Konfigurationsdatei ist erforderlich.')
    with tempfile.TemporaryDirectory(prefix='kingfisher-recovery-') as temporary:
        snapshot = snapshot_all(data_dir, Path(temporary))
        verify_snapshot_set(snapshot)
        names = [entry.name for entry in snapshot.iterdir()]
        payload = {'format': MAGIC, 'configuration': env_file.read_text(),
                   'files': {name: base64.b64encode((snapshot / name).read_bytes()).decode() for name in names}}
        if image_id is not None:
            payload['app_image'] = image_id
        encrypted = seal_json(payload, passphrase, MAGIC)
        output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            output.unlink(missing_ok=True)
            raise
    return output


def restore_bundle(bundle: Path, target: Path, passphrase: str) -> Path:
    """Nur ein neues Ziel: Bestehende Daten werden niemals überschrieben."""
    if target.exists():
        raise BackupError('Wiederherstellung benötigt ein noch nicht vorhandenes Zielverzeichnis.')
    payload = unseal_json(bundle.read_text(), passphrase)
    if not isinstance(payload, dict) or payload.get('format') != MAGIC:
        raise BackupError('Unbekanntes Wiederherstellungspaket.')
    image_id = payload.get('app_image')
    if image_id is not None and (not isinstance(image_id, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id)):
        raise BackupError('Ungültige App-Version im Wiederherstellungspaket.')
    files = payload.get('files')
    if not isinstance(files, dict) or not isinstance(payload.get('configuration'), str):
        raise BackupError('Das Wiederherstellungspaket ist unvollständig.')
    if SNAPSHOT_MANIFEST not in files or set(files) - set((*BACKUP_DATA_FILES, SNAPSHOT_MANIFEST)):
        raise BackupError('Unerwartete Dateien im Wiederherstellungspaket.')
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.kingfisher-restore-', dir=target.parent))
    try:
        data = staging / 'data'
        data.mkdir(mode=0o700)
        for name, encoded in files.items():
            content = base64.b64decode(encoded, validate=True)
            path = data / name
            path.write_bytes(content)
            path.chmod(0o600)
        verified = verify_snapshot_set(data)
        if set(files) != {SNAPSHOT_MANIFEST, *(entry["name"] for entry in verified)}:
            raise BackupError('Das Paket enthält Dateien ohne Manifestprüfung.')
        (staging / 'settings.env').write_text(payload['configuration'])
        (staging / 'settings.env').chmod(0o600)
        if image_id is not None:
            version = staging / 'app-version.json'
            version.write_text(json.dumps({'image': image_id}))
            version.chmod(0o600)
        from .restore_boundary import mark_pending
        mark_pending(data, 'encrypted_bundle')
        # Umbenennung erst nach vollständiger Entschlüsselung und Prüfung.
        if target.exists():
            raise BackupError('Das Ziel wurde inzwischen angelegt.')
        os.rename(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target


def main():
    import argparse
    import getpass
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    export.add_argument('--data', type=Path, required=True)
    export.add_argument('--env-file', type=Path, required=True)
    export.add_argument('--output', type=Path, required=True)
    restore = commands.add_parser('restore')
    restore.add_argument('--bundle', type=Path, required=True)
    restore.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    password = getpass.getpass('Wiederherstellungs-Passphrase: ')
    try:
        if args.command == 'export':
            if password != getpass.getpass('Passphrase wiederholen: '):
                parser.error('Die Passphrasen stimmen nicht überein.')
            result = export_bundle(args.data, args.env_file, args.output, password)
        else:
            result = restore_bundle(args.bundle, args.target, password)
    except DecryptionError:
        parser.exit(1, 'Paket nicht entschlüsselt: Passwort prüfen; das Paket könnte beschädigt sein.\n')
    except (BackupError, OSError, ValueError, TypeError):
        parser.exit(1, 'Vorgang nicht abgeschlossen. Paket, Dateizugriff und ein neues Zielverzeichnis prüfen.\n')
    print(result)


if __name__ == '__main__':
    main()
