"""Sicherung ohne Helfer: Kingfisher schreibt das verschlüsselte Archiv selbst, der Browser speichert es (Befund 8).

Früher bot „Sicherung öffnen“ ohne den Sicherungshelfer auf dem Mac trotzdem die Passwortfelder an und meldete dann
„Der lokale Sicherungshelfer ist nicht erreichbar“; mit Docker und Browser gab es also keine Sicherung. Der Helfer
hält den Container an und schreibt das Archiv in `~/Documents/Kingfisher-Sicherungen`. Ohne ihn geht jetzt:

* Der Sidecar zieht einen konsistenten Schnappschuss aller Datenbanken (SQLite-Backup-Schnittstelle, auch während
  geschrieben wird; `backup.snapshot_all`), verschlüsselt ihn mit dem Passwort (`recovery_bundle.export_bundle`, dasselbe
  Format `kingfisher-recovery-v1` wie beim Helfer) und prüft es sofort, indem er es in einen leeren Ordner wiederherstellt
  (`restore_bundle`, Prüfsummen je Datei).
* Der Browser bekommt die Datei als Download; wohin sie kommt, entscheidet der Mensch im Speichern-Dialog bzw. seinem
  Download-Ordner. Auf dem Rechner bleibt keine Kopie zurück, das Passwort wird nirgends gespeichert.

Die Konfiguration im Archiv (`settings.env`) sind die Werte, mit denen dieser Sidecar läuft und die eine Wiederherstellung
braucht: der Zugangsschlüssel der Oberfläche und die Passphrase der Schlüsseldatei (ohne sie bleiben die gespeicherten
Passwörter unlesbar). Sie stehen nur verschlüsselt im Archiv, wie beim Helfer. Wiederhergestellt wird mit
`scripts/restore_recovery_bundle.py` bzw. `python -m icarus_memory.recovery_bundle restore`.
"""
from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from .backup import BackupError, verify_snapshot_set
from .recovery_bundle import export_bundle, restore_bundle

#: Welche Umgebungswerte das Archiv als Konfiguration mitnimmt (die aus `compose.yaml`, sofern gesetzt).
KONFIGURATION = (
    'ICARUS_SIDECAR_TOKEN', 'ICARUS_SECRETS_PASSPHRASE', 'KINGFISHER_USER_NAME', 'KINGFISHER_TIMEZONE',
    'KINGFISHER_WEATHER_ENABLED', 'KINGFISHER_WEATHER_LOCATION', 'KINGFISHER_WEATHER_LATITUDE',
    'KINGFISHER_WEATHER_LONGITUDE', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL',
    'ICARUS_TRUSTED_LOCAL_MODEL_HOSTS', 'ICARUS_MEMORY_SEMANTIC', 'KINGFISHER_ORDNER',
)
MINDESTLAENGE = 16


def konfiguration(umgebung: Mapping[str, str] | None = None) -> str:
    """Die Zeilen `NAME=Wert` für die Wiederherstellung; nur gesetzte, einzeilige Werte."""
    umgebung = os.environ if umgebung is None else umgebung
    zeilen = [f'{name}={umgebung[name]}' for name in KONFIGURATION
              if umgebung.get(name) and not re.search(r'[\r\n]', umgebung[name])]
    return '\n'.join(zeilen) + '\n'


def dateiname(jetzt: datetime | None = None) -> str:
    return 'Kingfisher-Sicherung-' + (jetzt or datetime.now()).strftime('%Y-%m-%d-%H%M') + '.recovery'


def erstellen(data_dir: Path, passwort: str, umgebung: Mapping[str, str] | None = None) -> bytes:
    """Das verschlüsselte, schon einmal probeweise wiederhergestellte Archiv. Wirft `BackupError` mit einem Satz."""
    if len(passwort) < MINDESTLAENGE:
        raise BackupError('Bitte ein Sicherungspasswort mit mindestens 16 Zeichen wählen.')
    with tempfile.TemporaryDirectory(prefix='kingfisher-sicherung-') as ordner:
        arbeit = Path(ordner)
        einstellung = arbeit / 'settings.env'
        einstellung.write_text(konfiguration(umgebung), encoding='utf-8')
        einstellung.chmod(0o600)
        archiv = export_bundle(Path(data_dir), einstellung, arbeit / 'sicherung.recovery', passwort)
        probe = restore_bundle(archiv, arbeit / 'probe', passwort)
        verify_snapshot_set(probe / 'data')
        if (probe / 'settings.env').read_text(encoding='utf-8') != einstellung.read_text(encoding='utf-8'):
            raise BackupError('Die Sicherung ließ sich nicht vollständig prüfen. Bitte versuche es noch einmal.')
        return archiv.read_bytes()


__all__ = ['KONFIGURATION', 'MINDESTLAENGE', 'dateiname', 'erstellen', 'konfiguration']
