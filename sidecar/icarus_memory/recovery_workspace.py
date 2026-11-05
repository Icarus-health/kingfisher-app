"""Prepare an isolated, permission-reset working copy of a reviewed restore.

Contract/boot checks import no stores or keychain constructors. All mutations
belong to an unpublished staging directory; the historical source stays read-only.
"""
from __future__ import annotations

from contextlib import closing
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import stat
import sys
import tempfile
import uuid

MARKER = 'restore-state.json'
CAPABILITY = 1
CONTRACT_KEYS = frozenset({'version', 'mode', 'policy_version', 'restore_id', 'source_fingerprint',
                           'selection', 'unknown_history_acknowledged', 'permissions_reset', 'operational'})
HOST_KEYS = frozenset({'PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'TZ'})
START_KEYS = frozenset({'ICARUS_DATA_DIR', 'ICARUS_SIDECAR_TOKEN', 'ICARUS_SECRETS_PASSPHRASE',
                        'ICARUS_RECOVERY_BOOT_ID'})
_GROUP = re.compile(r'\d{8}T\d{6}Z')


def _safe_path(path):
    path = Path(os.path.abspath(path))
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('Verknüpfungen sind für eine Arbeitskopie nicht erlaubt.')
    return path


def _regular_bytes(path, *, limit, private=False):
    path = _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_size > limit
                or private and stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError('Die lokale Vertragsdatei ist ungültig oder nicht privat.')
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Die lokale Vertragsdatei ist zu groß.')
        return raw


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Doppelte Vertragsfelder sind nicht erlaubt.')
        result[key] = value
    return result


def read_working_contract(directory) -> dict | None:
    """Return only the exact versioned working-copy contract; fail closed."""
    try:
        value = json.loads(_regular_bytes(Path(directory) / MARKER, limit=8192), object_pairs_hook=_unique)
        if (not isinstance(value, dict) or set(value) != CONTRACT_KEYS
                or type(value['version']) is not int or value['version'] != 1
                or type(value['policy_version']) is not int or value['policy_version'] != 1
                or value['mode'] != 'working_copy'
                or any(value[key] is not True for key in ('unknown_history_acknowledged', 'permissions_reset', 'operational'))
                or not isinstance(value['restore_id'], str) or not re.fullmatch('[a-f0-9]{32}', value['restore_id'])
                or not isinstance(value['source_fingerprint'], str) or not re.fullmatch('[a-f0-9]{64}', value['source_fingerprint'])
                or not isinstance(value['selection'], str)
                or value['selection'] != 'restored' and not _GROUP.fullmatch(value['selection'])):
            return None
        return value
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return None


def _private_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def _copy_verified(source, destination, evidence):
    fd = os.open(_safe_path(source), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as incoming:
        info = os.fstat(incoming.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != evidence['bytes']:
            raise ValueError('Der ausgewählte Datenstand hat sich verändert.')
        digest = hashlib.sha256()
        size = 0
        out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(out, 'wb') as outgoing:
            while chunk := incoming.read(64 * 1024):
                size += len(chunk)
                if size > evidence['bytes']:
                    raise ValueError('Der ausgewählte Datenstand hat sich verändert.')
                digest.update(chunk)
                outgoing.write(chunk)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if size != evidence['bytes'] or digest.hexdigest() != evidence['sha256']:
            raise ValueError('Der ausgewählte Datenstand hat sich verändert.')


def _reset_permissions(data):
    # Lazy imports: boot validation must work before config/secrets/server exist.
    from . import config
    from .fassung import Fassungspruefung
    from .mac_calendar import MacCalendar
    from .procedures import ProcedureStore
    from .regeln import RegelStore
    from .tasks import TaskStore
    from .workspace_views import WorkspaceViews

    settings_path = data / config.DATEINAME
    old = config.Settings()
    if settings_path.exists():
        raw = json.loads(_regular_bytes(settings_path, limit=8 * 1024 * 1024))
        if not isinstance(raw, dict):
            raise ValueError('Die historischen Einstellungen sind nicht lesbar.')
        old = config.Settings.from_dict(raw)
    clean = config.Settings()
    # Preserve own-address recognition even though legacy connection hosts go away.
    clean.mail.user, clean.mail.sender = old.mail.user, old.mail.sender
    clean.calendar.user = old.calendar.user
    clean.mail_accounts = old.mail_accounts
    clean.calendar_sources = old.calendar_sources
    for account in (*clean.mail_accounts, *clean.calendar_sources):
        account.enabled = False
    clean.konten = {key: value for key, value in old.konten.items()
                    if key in {'eigene', 'bereich_je_konto', 'kalender_ausgeblendet'}}
    clean.einrichtung = {'name': str(old.einrichtung.get('name') or '')[:80],
                         'schritte': {}, 'abgeschlossen': False}
    clean.antwort_saetze = clean.satzpruefung_modell = 'aus'
    config.save(data, clean)
    # This default is ON even with a new/missing task DB, so explicitly persist OFF.
    with closing(TaskStore(data / 'tasks.sqlite3')) as tasks:
        tasks.auto_setzen(False)
    Fassungspruefung(data / 'fassung.json').schalten(False)
    counts = {'skills': 0, 'rules': 0}
    if (data / 'regeln.sqlite3').exists():
        with closing(RegelStore(data / 'regeln.sqlite3')) as rules:
            active = rules.alle(nur_aktive=True)
            for rule in active:
                rules.widerrufen(rule.id)
            counts['rules'] = len(active)
    if (data / 'procedures.sqlite3').exists():
        with closing(ProcedureStore(data / 'procedures.sqlite3')) as procedures:
            # No public API unconfirms a skill while preserving its immutable ID,
            # version and body. Migrate through the Store, then reset ONLY active
            # rows in one staging transaction. Existing pending bases stay intact.
            with procedures._lock, procedures._conn:
                rows = procedures._conn.execute("SELECT id,name FROM procedures WHERE state='active'").fetchall()
                procedures._conn.execute("UPDATE procedures SET state='pending' WHERE state='active'")
                for row in rows:
                    base = procedures._conn.execute(
                        "SELECT COALESCE(MAX(version),0) FROM procedures WHERE name=? AND state IN ('active','revoked','superseded')",
                        (row['name'],)).fetchone()[0]
                    procedures._conn.execute('UPDATE procedures SET base_version=? WHERE id=?', (base, row['id']))
                counts['skills'] = len(rows)
    if (data / 'mac-calendar.sqlite3').exists():
        MacCalendar(data / 'mac-calendar.sqlite3').change(lambda state: state.update(
            enabled=False, authorize=False, status='offline', generation=state['generation'] + 1))
    if (data / 'workspace-views.sqlite3').exists():
        with closing(WorkspaceViews(data / 'workspace-views.sqlite3')) as views:
            old_online = views.get('preferences', 'online')
            views.put('preferences', 'online', {'logos': False, 'maps': False}, old_online['revision'])
    return counts


def _publish(stage, target):
    """Atomic no-replace rename on the two supported runtime platforms."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = rename(os.fsencode(stage), os.fsencode(target), 4)  # RENAME_EXCL
    elif sys.platform.startswith('linux') and hasattr(libc, 'renameat2'):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = rename(-100, os.fsencode(stage), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
    else:
        raise ValueError('Die Arbeitskopie kann auf diesem System nicht sicher veröffentlicht werden.')
    if result != 0:
        raise OSError(ctypes.get_errno(), 'Die Arbeitskopie konnte nicht veröffentlicht werden.')


def prepare_working_copy(source, target, *, fingerprint, selection, acknowledge_unknown) -> Path:
    from .backup import SQLITE_DATA_FILES
    from .recovery_preflight import preflight

    source, target = _safe_path(source), _safe_path(target)
    if (acknowledge_unknown is not True or not isinstance(fingerprint, str)
            or not re.fullmatch('[a-f0-9]{64}', fingerprint)
            or not isinstance(selection, str) or selection != 'restored' and not _GROUP.fullmatch(selection)):
        raise ValueError('Prüfbefund, ausgewählter Stand und Bestätigung werden benötigt.')
    if not source.is_dir() or not target.parent.is_dir() or target.exists() or source == target or source in target.parents:
        raise ValueError('Das Ziel muss neu sein und außerhalb des historischen Bestands liegen.')
    report = preflight(source)
    if report.get('report_fingerprint') != fingerprint:
        raise ValueError('Der Prüfbefund hat sich verändert. Bitte erneut prüfen.')
    allowed_unknown = {'current_authority_unverified', 'no_comparison_state'}
    if set(report.get('unresolved', ())) - allowed_unknown:
        raise ValueError('Der historische Stand ist noch nicht eindeutig lesbar.')
    if selection == 'restored':
        selected = report['restored']
    else:
        selected = next((item for item in report['comparison_groups'] if item['group'] == selection), None)
        if selected is None or set(selected.get('unresolved', ())) - {'lineage_and_recency_unverified'}:
            raise ValueError('Der ausgewählte Vergleichsstand ist nicht eindeutig lesbar.')
    files = selected['files']
    if any(item['status'] not in {'missing', 'verified'} for item in files):
        raise ValueError('Ein vorhandener Bereich ist ungeklärt. Es wurde nichts übernommen.')
    present = [item for item in files if item['status'] == 'verified']
    if not any(item['name'] in SQLITE_DATA_FILES for item in present):
        raise ValueError('Der ausgewählte Stand enthält keine lesbare Datenbank.')
    stage = Path(tempfile.mkdtemp(prefix=f'.{target.name}.staging-', dir=target.parent))
    try:
        data = stage / 'data'; data.mkdir(mode=0o700)
        for item in present:
            name = item['name']
            if name == 'schluessel.icarus':
                continue
            physical = name if selection == 'restored' else f'{Path(name).stem}.vor-wiederherstellung-{selection}{Path(name).suffix}'
            _copy_verified(source / physical, data / name, item)
        counts = _reset_permissions(data)
        identifier = uuid.uuid4().hex
        contract = {'version': 1, 'mode': 'working_copy', 'policy_version': 1, 'restore_id': identifier,
                    'source_fingerprint': fingerprint, 'selection': selection,
                    'unknown_history_acknowledged': True, 'permissions_reset': True, 'operational': True}
        _private_write(data / MARKER, json.dumps(contract, ensure_ascii=False))
        start = {'ICARUS_DATA_DIR': str(target / 'data'), 'ICARUS_SIDECAR_TOKEN': secrets.token_hex(32),
                 'ICARUS_SECRETS_PASSPHRASE': secrets.token_urlsafe(48), 'ICARUS_RECOVERY_BOOT_ID': identifier}
        _private_write(stage / 'settings.env', ''.join(f'{key}={shlex.quote(value)}\n' for key, value in start.items()))
        receipt = {'version': 1, 'restore_id': identifier, 'source_restore_id': report['restore_id'],
                   'source_fingerprint': fingerprint, 'selection': selection, 'unknown_history_acknowledged': True,
                   'copied_files': [item['name'] for item in present if item['name'] != 'schluessel.icarus'],
                   'missing_files': [item['name'] for item in files if item['status'] == 'missing'],
                   'reset_counts': counts,
                   'disabled_capabilities': ['models', 'connector_access', 'file_access', 'schedules', 'mcp',
                       'background_import', 'external_weather_news_routes', 'automatic_export', 'notifications',
                       'task_automation', 'update_checks', 'online_logos_maps', 'permanent_rules', 'active_skills', 'mac_calendar'],
                   'old_secret_store_copied': False}
        _private_write(stage / 'recovery-receipt.json', json.dumps(receipt, ensure_ascii=False, indent=2))
        for path in data.iterdir():
            if not path.is_file() or path.is_symlink():
                raise ValueError('Die vorbereitete Arbeitskopie enthält einen ungeklärten Bereich.')
            path.chmod(0o600)
        if preflight(source).get('report_fingerprint') != fingerprint:
            raise ValueError('Der historische Stand hat sich beim Kopieren verändert. Bitte erneut prüfen.')
        _safe_path(target)
        _publish(stage, target)
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _start_values(folder):
    folder = _safe_path(folder)
    contract = read_working_contract(folder / 'data')
    if contract is None:
        raise ValueError('Kein gültiger Arbeitskopienvertrag vorhanden.')
    raw = _regular_bytes(folder / 'settings.env', limit=8192, private=True).decode('utf-8')
    values = {}
    for line in raw.splitlines():
        fields = shlex.split(line, comments=False, posix=True)
        if len(fields) != 1 or '=' not in fields[0]:
            raise ValueError('Die Startdatei enthält ungültige Angaben.')
        key, value = fields[0].split('=', 1)
        if key not in START_KEYS or key in values or not value or '\x00' in value or '\n' in value:
            raise ValueError('Die Startdatei enthält unbekannte oder doppelte Angaben.')
        values[key] = value
    if (set(values) != START_KEYS or values['ICARUS_DATA_DIR'] != str(folder / 'data')
            or values['ICARUS_RECOVERY_BOOT_ID'] != contract['restore_id']
            or not re.fullmatch('[a-f0-9]{64}', values['ICARUS_SIDECAR_TOKEN'])
            or not re.fullmatch('[A-Za-z0-9_-]{64}', values['ICARUS_SECRETS_PASSPHRASE'])):
        raise ValueError('Startdatei und Arbeitskopienvertrag stimmen nicht überein.')
    return values


def _host_key(key):
    return key in HOST_KEYS or bool(re.fullmatch(r'LC_[A-Z0-9_]+', key))


def launch_environment(folder) -> dict:
    """Build a fresh child environment, never source or evaluate shell code."""
    try:
        start = _start_values(folder)
    except (OSError, UnicodeError) as error:
        raise ValueError('Die private Startdatei konnte nicht gelesen werden.') from error
    return {**{key: value for key, value in os.environ.items() if _host_key(key)}, **start}


def boot_allowed(directory, environ) -> bool:
    """Authorize only this copy and the exact sanitized launcher environment."""
    try:
        data = _safe_path(directory)
        if data.name != 'data' or read_working_contract(data) is None:
            return False
        expected = _start_values(data.parent)
        return (all(isinstance(key, str) and isinstance(value, str) and '\x00' not in value
                    and (key in START_KEYS or _host_key(key)) for key, value in environ.items())
                and all(environ.get(key) == value for key, value in expected.items()))
    except (OSError, ValueError, TypeError, UnicodeError, AttributeError):
        return False
