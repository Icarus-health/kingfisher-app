"""Sicherung und Wiederherstellung des Selbstmodells.

Ein Gedächtnis, das zwanzig Jahre halten soll, hat genau einen katastrophalen
Fehlerfall: Es ist weg. Eine defekte Platte, ein verlorener Rechner, ein
misslungenes Update.

Deshalb drei Dinge:

* **Snapshots** über SQLites eigene Backup-Schnittstelle — konsistent auch dann,
  wenn gerade geschrieben wird. Ein `cp` der Datei ist es nicht.
* **Rotation**, damit die Sicherungen nicht die Platte füllen.
* **Export** als offenes JSON gegen das Schema, optional verschlüsselt. Eine
  SQLite-Datei nützt in zehn Jahren wenig, wenn niemand mehr weiß, welches
  Programm sie geschrieben hat.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .crypto import KDF_ITERATIONS, DecryptionError, seal_json, unseal_json
from .model import now

SNAPSHOT_PREFIX = "self-model-"
SNAPSHOT_SET_PREFIX = "kingfisher-"
# Sicherungen vor einem Update rotieren getrennt: Die regelmäßige Sicherung
# läuft bei jedem Zeitplanlauf und würde sie sonst nach wenigen Läufen verdrängen.
UPDATE_SET_PREFIX = "vor-update-"
SNAPSHOT_MANIFEST = "manifest.json"
EXPORT_MAGIC = "icarus-export-v1"

# Der Datenordner enthält bewusst mehrere fachlich getrennte SQLite-Stores.
# Eine Sicherung, die nur das Selbstmodell kopiert, kann Gespräche, Aufgaben
# oder den Quellen-/Wissensgraphen nicht wiederherstellen und ist deshalb für
# Kingfisher keine Sicherung. Diese Liste ist absichtlich eine Allowlist: Der
# Sicherungsvorgang greift nie beliebige Dateien aus dem Datenordner auf.
SQLITE_DATA_FILES = (
    "self-model.sqlite3",
    "audit.sqlite3",
    "tasks.sqlite3",
    "workspace.sqlite3",
    "episodes.sqlite3",
    "proposals.sqlite3",
    "conversations.sqlite3",
    "knowledge.sqlite3",
    "regeln.sqlite3",
    "mac-calendar.sqlite3",
    "calendar-actions.sqlite3",
    "gespraeche.sqlite3",
    "rueckmeldungen.sqlite3",
    "logbuch.sqlite3",
    "lint.sqlite3",
)

# Einstellungen enthalten keine Geheimnisse. Die verschlüsselte Schlüsseldatei
# wird nur dann mitgenommen, wenn der laufende Schlüssel-Speicher sie benutzt;
# die zugehörige Passphrase bleibt bewusst außerhalb des Volumes in
# `.kingfisher.env` und wird niemals in einen Snapshot geschrieben.
AUXILIARY_DATA_FILES = ("einstellungen.json", "schluessel.icarus")
BACKUP_DATA_FILES = SQLITE_DATA_FILES + AUXILIARY_DATA_FILES
SNAPSHOT_SET_VERSION = 1


class BackupError(Exception):
    pass


# -- Snapshots -------------------------------------------------------------


def snapshot(db_path: Path, target_dir: Path, keep: int = 14, at: datetime | None = None) -> Path:
    """Legt eine konsistente Kopie der Datenbank an und rotiert alte weg."""
    at = at or now()
    if not db_path.is_file():
        raise BackupError(f"Keine Datenbank unter {db_path}")

    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = at.strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"{SNAPSHOT_PREFIX}{stamp}.sqlite3"

    source = sqlite3.connect(str(db_path))
    try:
        destination = sqlite3.connect(str(target))
        try:
            # SQLites Backup-API sperrt korrekt; ein Dateikopieren während eines
            # laufenden Schreibvorgangs ergäbe eine beschädigte Kopie.
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    prune(target_dir, keep)
    return target


def _copy_sqlite(
    source_path: Path, destination_path: Path, *, immutable_source: bool = False
) -> None:
    """Kopiert eine SQLite-Datei konsistent und prüft die resultierende Kopie.

    Live stores use a normal connection so SQLite includes any active WAL.
    Finalized snapshots use immutable read-only mode: SQLite's backup API has
    already folded their committed state into the main file, and verification
    or restore must not need to create WAL shared-memory sidecars.
    """
    if immutable_source:
        source_uri = source_path.resolve().as_uri() + "?mode=ro&immutable=1"
        source = sqlite3.connect(source_uri, uri=True)
    else:
        source = sqlite3.connect(str(source_path))
    try:
        destination = sqlite3.connect(str(destination_path))
        try:
            source.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise BackupError(
                    f"SQLite-Sicherung von {source_path.name} ist beschädigt: "
                    f"{result[0] if result else 'unlesbar'}"
                )
        finally:
            destination.close()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"SQLite-Sicherung von {source_path.name} nicht lesbar: {exc}") from exc
    finally:
        source.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_set_path(target_dir: Path, stamp: str, prefix: str = SNAPSHOT_SET_PREFIX) -> Path:
    """Liefert einen neuen Namen, auch bei manueller und geplanter Sicherung.

    Zwei Sicherungen in derselben Sekunde dürfen einander nicht überschreiben.
    Ein Zähler ist besser als eine Zufalls-ID: Die Reihenfolge bleibt für den
    Menschen im Dateinamen sichtbar und die Rotation kann einfach sortieren.
    """
    candidate = target_dir / f"{prefix}{stamp}"
    number = 1
    while candidate.exists():
        candidate = target_dir / f"{prefix}{stamp}-{number}"
        number += 1
    return candidate


def _snapshot_set_entries(data_dir: Path) -> list[Path]:
    return [
        data_dir / name for name in BACKUP_DATA_FILES
        if (data_dir / name).is_file()
    ]


def snapshot_all(
    data_dir: Path,
    target_dir: Path,
    keep: int = 14,
    at: datetime | None = None,
    prefix: str = SNAPSHOT_SET_PREFIX,
) -> Path:
    """Sichert den vollständigen lokalen Kingfisher-Bestand.

    Jede SQLite-Datei wird über die SQLite-Backup-API geschrieben. Der
    komplette Satz wird zunächst in einem versteckten Verzeichnis aufgebaut
    und erst nach Manifest- und Integritätsprüfung atomar veröffentlicht.
    Dadurch erscheint nie ein halber Snapshot in der Sicherungsliste.
    """
    data_dir = Path(data_dir)
    target_dir = Path(target_dir)
    entries = _snapshot_set_entries(data_dir)
    sqlite_entries = [entry for entry in entries if entry.name in SQLITE_DATA_FILES]
    if not sqlite_entries:
        raise BackupError(f"Keine Kingfisher-Datenbank unter {data_dir}")

    at = at or now()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _snapshot_set_path(target_dir, at.strftime("%Y%m%dT%H%M%SZ"), prefix)
    staging = target_dir / f".{target.name}.partial"
    staging.mkdir(mode=0o700)

    try:
        files: list[dict[str, Any]] = []
        for source in entries:
            destination = staging / source.name
            if source.name in SQLITE_DATA_FILES:
                _copy_sqlite(source, destination)
                kind = "sqlite"
            else:
                shutil.copy2(source, destination)
                try:
                    destination.chmod(0o600)
                except OSError:
                    pass
                kind = "file"
            files.append({
                "name": source.name,
                "kind": kind,
                "bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            })

        manifest = {
            "format": "kingfisher-snapshot-v1",
            "version": SNAPSHOT_SET_VERSION,
            "created_at": at.astimezone().isoformat(),
            "files": files,
        }
        (staging / SNAPSHOT_MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    prune_all(target_dir, keep, prefix)
    return target


def _read_snapshot_manifest(snapshot_dir: Path) -> dict[str, Any]:
    manifest_path = snapshot_dir / SNAPSHOT_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise BackupError("Snapshot-Manifest ist nicht lesbar.") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "kingfisher-snapshot-v1"
        or manifest.get("version") != SNAPSHOT_SET_VERSION
        or not isinstance(manifest.get("files"), list)
    ):
        raise BackupError("Snapshot-Manifest hat ein unbekanntes Format.")
    return manifest


def verify_snapshot_set(snapshot_dir: Path) -> list[dict[str, Any]]:
    """Prüft Manifest, Prüfsummen und SQLite-Integrität vor dem Restore."""
    snapshot_dir = Path(snapshot_dir)
    if not snapshot_dir.is_dir():
        raise BackupError(f"Kein Kingfisher-Snapshot unter {snapshot_dir}")
    manifest = _read_snapshot_manifest(snapshot_dir)
    seen: set[str] = set()
    verified: list[dict[str, Any]] = []
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise BackupError("Snapshot-Manifest enthält einen ungültigen Eintrag.")
        name = entry.get("name")
        kind = entry.get("kind")
        checksum = entry.get("sha256")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or name not in BACKUP_DATA_FILES
            or name in seen
            or kind not in {"sqlite", "file"}
            or not isinstance(checksum, str)
        ):
            raise BackupError("Snapshot-Manifest enthält einen nicht erlaubten Eintrag.")
        if (kind == "sqlite") != (name in SQLITE_DATA_FILES):
            raise BackupError(f"Snapshot-Typ für {name} passt nicht.")
        path = snapshot_dir / name
        if not path.is_file() or _sha256(path) != checksum:
            raise BackupError(f"Snapshot-Datei {name} fehlt oder wurde verändert.")
        if kind == "sqlite":
            try:
                connection = sqlite3.connect(
                    path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
                )
                try:
                    result = connection.execute("PRAGMA integrity_check").fetchone()
                finally:
                    connection.close()
            except sqlite3.DatabaseError as exc:
                raise BackupError(f"Snapshot-Datenbank {name} ist nicht lesbar: {exc}") from exc
            if not result or result[0] != "ok":
                raise BackupError(f"Snapshot-Datenbank {name} ist beschädigt.")
        seen.add(name)
        verified.append({"name": name, "kind": kind, "path": path})
    if not any(entry["kind"] == "sqlite" for entry in verified):
        raise BackupError("Snapshot enthält keine Datenbank.")
    return verified


def _preflight_schema_versions(entries: list[dict[str, Any]]) -> None:
    """Reject managed snapshots newer than this code before replacing files.

    Older versions remain restorable so the normal migration runner can bring
    them forward when the application opens the restored stores.
    """
    from .update_backup import _targets

    targets = _targets()
    for entry in entries:
        name = entry["name"]
        migrations = targets.get(name)
        if not migrations:
            continue
        supported = max(migration.version for migration in migrations)
        try:
            connection = sqlite3.connect(
                entry["path"].resolve().as_uri() + "?mode=ro&immutable=1", uri=True
            )
            try:
                found = int(connection.execute("PRAGMA user_version").fetchone()[0])
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"Schema-Version von {name} nicht lesbar: {exc}") from exc
        if found < 0 or found > supported:
            raise BackupError(
                f"Snapshot enthält für {name} eine nicht unterstützte Schema-Version "
                f"({found}; unterstützt: 0 bis {supported})."
            )


def restore_all(snapshot_dir: Path, data_dir: Path, at: datetime | None = None) -> list[Path]:
    """Stellt einen geprüften vollständigen Snapshot wieder her.

    Vor der ersten produktiven Datei wird der vollständige Snapshot in einen
    temporären Bereich kopiert. Danach werden vorhandene Dateien als
    Wiederherstellungs-Sicherheitsnetz beiseitegelegt. Sollte das Einspielen
    trotzdem scheitern, werden diese Dateien wieder an ihren ursprünglichen
    Ort zurückgestellt.
    """
    snapshot_dir = Path(snapshot_dir)
    data_dir = Path(data_dir)
    entries = verify_snapshot_set(snapshot_dir)
    _preflight_schema_versions(entries)
    at = at or now()
    stamp = at.strftime("%Y%m%dT%H%M%SZ")
    staging = data_dir / f".restore-{stamp}.partial"
    data_dir.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        raise BackupError("Eine Wiederherstellung läuft bereits.")
    staging.mkdir(mode=0o700)

    moved: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for entry in entries:
            source = entry["path"]
            destination = staging / entry["name"]
            if entry["kind"] == "sqlite":
                _copy_sqlite(source, destination, immutable_source=True)
            else:
                shutil.copy2(source, destination)
                try:
                    destination.chmod(0o600)
                except OSError:
                    pass

        from .restore_boundary import mark_pending
        mark_pending(data_dir, 'snapshot')
        staged = {entry["name"] for entry in entries}
        # Auch Dateien, die im Snapshot *nicht* vorhanden waren, gehören zur
        # Wiederherstellung: Sonst bliebe etwa ein später eingerichteter
        # Provider oder ein neues Gespräch im angeblich alten Zustand stehen.
        for name in BACKUP_DATA_FILES:
            target = data_dir / name
            if target.exists():
                aside = target.with_name(
                    f"{target.stem}.vor-wiederherstellung-{stamp}{target.suffix}"
                )
                if aside.exists():
                    raise BackupError(f"Sicherheitskopie {aside.name} existiert bereits.")
                os.replace(target, aside)
                moved.append((target, aside))
            if name in staged:
                os.replace(staging / name, target)
                installed.append(target)
    except Exception as exc:
        for target in reversed(installed):
            target.unlink(missing_ok=True)
        for target, aside in reversed(moved):
            if aside.exists() and not target.exists():
                os.replace(aside, target)
        if isinstance(exc, BackupError):
            raise
        raise BackupError(f"Wiederherstellung fehlgeschlagen: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return [aside for _, aside in moved]


def prune(target_dir: Path, keep: int) -> list[Path]:
    """Behält die neuesten `keep` Snapshots und entfernt den Rest."""
    snapshots = sorted(
        target_dir.glob(f"{SNAPSHOT_PREFIX}*.sqlite3"),
        key=lambda p: p.name,
        reverse=True,
    )
    removed = []
    for old in snapshots[keep:]:
        old.unlink()
        removed.append(old)
    return removed


def prune_all(target_dir: Path, keep: int, prefix: str = SNAPSHOT_SET_PREFIX) -> list[Path]:
    """Behält die neuesten vollständigen Kingfisher-Snapshots."""
    snapshots = sorted(
        (path for path in target_dir.glob(f"{prefix}*") if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    removed: list[Path] = []
    for old in snapshots[keep:]:
        shutil.rmtree(old)
        removed.append(old)
    return removed


def list_snapshots(target_dir: Path) -> list[dict[str, Any]]:
    if not target_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(
        (candidate for prefix in (SNAPSHOT_SET_PREFIX, UPDATE_SET_PREFIX)
         for candidate in target_dir.glob(f"{prefix}*") if candidate.is_dir()),
        reverse=True,
    ):
        try:
            manifest = _read_snapshot_manifest(path)
            files = manifest["files"]
        except BackupError:
            # Ein unvollständiger oder fremder Ordner ist keine verwertbare
            # Sicherung. Er wird nicht versteckt gelöscht, aber auch nicht als
            # wiederherstellbar angeboten.
            continue
        stat = path.stat()
        entries.append({
            "name": path.name,
            "path": str(path),
            "bytes": sum(
                child.stat().st_size for child in path.iterdir() if child.is_file()
            ),
            "created": str(manifest.get("created_at") or datetime.fromtimestamp(
                stat.st_mtime
            ).astimezone().isoformat()),
            "kind": "kingfisher-snapshot",
            "before_update": path.name.startswith(UPDATE_SET_PREFIX),
            "files": [entry.get("name") for entry in files if isinstance(entry, dict)],
        })
    # Lesbarkeit bestehender Icarus-Sicherungen bleibt erhalten. Sie enthalten
    # ausschließlich das frühere Selbstmodell und werden ausdrücklich als
    # solche markiert, damit sie nicht mit einer vollständigen Sicherung
    # verwechselt werden.
    for path in sorted(target_dir.glob(f"{SNAPSHOT_PREFIX}*.sqlite3"), reverse=True):
        stat = path.stat()
        entries.append({
            "name": path.name,
            "path": str(path),
            "bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
            "kind": "legacy-self-model",
        })
    return sorted(entries, key=lambda entry: (str(entry["created"]), str(entry["name"])), reverse=True)


def verify_legacy_snapshot(snapshot_path: Path) -> None:
    """Read-only legacy validation, also used before runtime teardown."""
    if not snapshot_path.is_file():
        raise BackupError(f"Kein Snapshot unter {snapshot_path}")

    check = sqlite3.connect(
        snapshot_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
    )
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise BackupError(f"Snapshot ist beschädigt: {result[0] if result else 'unlesbar'}")
        check.execute("SELECT COUNT(*) FROM assertions")
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"Snapshot nicht lesbar: {exc}") from exc
    finally:
        check.close()


def restore(snapshot_path: Path, db_path: Path) -> None:
    """Spielt einen Snapshot zurück — nach Prüfung, dass er lesbar ist.

    Die vorhandene Datenbank wird vorher zur Seite gelegt. Eine
    Wiederherstellung, die den aktuellen Stand unwiederbringlich überschreibt,
    ist ein zweiter Weg, alles zu verlieren.
    """
    verify_legacy_snapshot(snapshot_path)
    _preflight_schema_versions([{"name": "self-model.sqlite3", "path": Path(snapshot_path)}])

    from .restore_boundary import mark_pending
    mark_pending(db_path.parent, 'legacy_self_model')
    if db_path.is_file():
        aside = db_path.with_suffix(f".vor-wiederherstellung-{now():%Y%m%dT%H%M%SZ}.sqlite3")
        db_path.replace(aside)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(
        snapshot_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
    )
    try:
        destination = sqlite3.connect(str(db_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


# -- Export ----------------------------------------------------------------


def export_model(model_dict: dict[str, Any], passphrase: str | None = None) -> str:
    """Schreibt das Selbstmodell als JSON, optional verschlüsselt.

    Ohne Passphrase: lesbares JSON, passend zu schema/self-model.schema.json.
    Mit Passphrase: verschlüsselt und mit HMAC gegen Veränderung geschützt.
    """
    if not passphrase:
        return json.dumps(model_dict, ensure_ascii=False, indent=2)
    # Verfahren und Format liegen in crypto.py — dieselbe Verschlüsselung wie
    # die Schlüsseldatei, damit es nur eine Stelle gibt, die driften kann.
    return seal_json(model_dict, passphrase, EXPORT_MAGIC)


def import_model(payload: str, passphrase: str | None = None) -> dict[str, Any]:
    """Liest einen Export, entschlüsselt bei Bedarf und prüft die Unversehrtheit."""
    document = json.loads(payload)
    if document.get("format") != EXPORT_MAGIC:
        return document  # unverschlüsselter Export

    if not passphrase:
        raise BackupError("Dieser Export ist verschlüsselt. Passphrase erforderlich.")

    try:
        return unseal_json(payload, passphrase)
    except DecryptionError as exc:
        # Nach außen bleibt es ein BackupError; der Aufrufer soll nicht
        # unterscheiden müssen, aus welchem Modul der Fehler stammt.
        raise BackupError(str(exc)) from exc


__all__ = [
    "AUXILIARY_DATA_FILES",
    "BACKUP_DATA_FILES",
    "BackupError",
    "SQLITE_DATA_FILES",
    "export_model",
    "import_model",
    "list_snapshots",
    "prune",
    "prune_all",
    "restore",
    "restore_all",
    "snapshot",
    "snapshot_all",
    "verify_snapshot_set",
]
