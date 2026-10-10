"""Kleiner, bereinigter Hardwarebericht des Wirts (macOS, Windows, Linux).

Die Hardware des Wirts wird nie aus dem Container geschlossen: Ein Bericht
kommt von einem Helfer auf dem Wirt (`scripts/report_device.py`). Plattformen
außer macOS docken über dieselbe Schnittstelle an; der Kern hängt nicht am Mac.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping
from typing import Any

_GIB = 1024**3
_CHIP = re.compile(r'[A-Za-z0-9 ()+.,:_/-]{1,128}', re.ASCII)
PLATFORMEN = ('macos', 'windows', 'linux')


def memory_plan_gb(memory: float) -> tuple[float, float]:
    """Planning reserve and model budget for shared host RAM, not current free RAM."""
    headroom = min(memory, max(6.0, round(memory * .4, 1)))
    return headroom, max(0.0, round(memory - headroom, 1))


def _validate(report: Any) -> dict:
    if not isinstance(report, dict) or report.get('platform') not in PLATFORMEN:
        raise ValueError('Ein Host-Bericht für macOS, Windows oder Linux ist erforderlich.')
    memory = report.get('memory_bytes')
    if type(memory) is not int or not _GIB <= memory <= 4096 * _GIB:
        raise ValueError('Die Speicherangabe ist ungültig.')
    chip = report.get('chip')
    if not isinstance(chip, str) or not _CHIP.fullmatch(chip):
        raise ValueError('Die Chip-Angabe ist ungültig.')
    chip = chip.strip()
    if not chip:
        raise ValueError('Die Chip-Angabe fehlt.')
    result = {'platform': report['platform'], 'chip': chip, 'memory_bytes': memory}
    # Getrennter Grafikspeicher (Windows/Linux mit eigener Grafikkarte); optional.
    gpu = report.get('gpu_memory_bytes')
    if gpu is not None:
        if type(gpu) is not int or not _GIB // 2 <= gpu <= 4096 * _GIB:
            raise ValueError('Die Grafikspeicherangabe ist ungültig.')
        result['gpu_memory_bytes'] = gpu
    # Freier Platz dort, wo Ollama seine Modelle ablegt; nur die Zahl, nie ein Pfad.
    disk = report.get('disk_free_bytes')
    if disk is not None:
        if type(disk) is not int or not 0 <= disk <= 4096 * 1024 * _GIB:
            raise ValueError('Die Festplattenangabe ist ungültig.')
        result['disk_free_bytes'] = disk
    return result


def _profile(report: dict | None) -> dict:
    if report is None:
        return {
            'chip': None, 'memory_gb': None, 'platform': 'unknown', 'source': 'unknown', 'disk_free_gb': None,
            'guidance': {'capacity': 'Unbekannt', 'headroom_gb': None, 'model_budget_gb': None,
                         'estimate': True,
                         # Im Container sieht Kingfisher nur dessen Speicher, nicht den des Rechners; außerhalb gilt der Satz nicht.
                         'note': 'Der Rechner hat seine Ausstattung noch nicht gemeldet.' + (
                             ' Was der Container an Speicher sieht, ist nicht der Arbeitsspeicher des Rechners.'
                             if _im_container() else '')},
        }
    memory = round(report['memory_bytes'] / _GIB, 1)
    plattform = report['platform']
    gpu = round(report['gpu_memory_bytes'] / _GIB, 1) if 'gpu_memory_bytes' in report else None
    disk = round(report['disk_free_bytes'] / _GIB, 1) if 'disk_free_bytes' in report else None
    # A deliberately conservative planning reserve, not a measurement of free RAM.
    headroom, budget = memory_plan_gb(memory)
    capacity = 'Knapp' if memory < 16 else 'Für ein kleines lokales Modell einplanbar'
    return {
        'chip': None if report['chip'].lower() == 'unknown' else report['chip'],
        'memory_gb': memory, 'platform': plattform, 'gpu_memory_gb': gpu, 'disk_free_gb': disk,
        'source': 'macos_host_report' if plattform == 'macos' else 'host_report',
        'guidance': {'capacity': capacity, 'headroom_gb': headroom, 'model_budget_gb': budget,
                     'estimate': True,
                     'note': 'Grobe Kapazitätsschätzung, kein Qualitätsnachweis: macOS und andere Apps brauchen eigenen Spielraum. Modellformat, Kontextlänge und parallele Nutzung bestimmen den tatsächlichen Bedarf.'},
    }


def load_device_profile(data_dir: str | Path) -> dict:
    path = Path(data_dir) / 'device-profile.json'
    try:
        with path.open('r', encoding='utf-8') as handle:
            text = handle.read(8193)
        if len(text) > 8192:
            return _profile(None)
        return _profile(_validate(json.loads(text)))
    except (OSError, UnicodeError, ValueError, TypeError):
        return _profile(None)


def mit_eigener_messung(profil: dict, eigene: dict | None = None) -> dict:
    """Hat kein Helfer die Ausstattung gemeldet, gilt die eigene Messung (`eigene_ausstattung`), dieselbe wie bei der
    Modellwahl. So steht unter „Für Techniker“ nur eine Aussage („15,7 GB Arbeitsspeicher, selbst gemessen“) statt
    daneben „noch unbekannt“ (Fremdprobe 2, Befund 27). Im Container ist die Messung eine Untergrenze."""
    if profil.get('source') != 'unknown':
        return profil
    eigene = eigene if eigene is not None else eigene_ausstattung()
    if not eigene:
        return profil
    memory = float(eigene['memory_gb'])
    untergrenze = bool(eigene.get('untergrenze'))
    headroom, budget = memory_plan_gb(memory)
    return {**profil, 'memory_gb': memory, 'platform': eigene.get('platform') or 'unknown',
            'source': 'untergrenze' if untergrenze else 'eigene',
            'guidance': {**profil['guidance'], 'capacity': 'Knapp' if memory < 16 else 'Für ein kleines lokales Modell einplanbar',
                         'headroom_gb': headroom, 'model_budget_gb': budget,
                         'note': ('Im Container gemessen: Der Rechner hat mindestens so viel. ' if untergrenze else
                                  'Von Kingfisher selbst gemessen. ')
                                 + 'Grobe Kapazitätsschätzung, kein Qualitätsnachweis.'}}


def save_device_profile(data_dir: str | Path, report: Any) -> dict:
    sanitized = _validate(report)
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.device-profile-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(sanitized, handle, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, directory / 'device-profile.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return _profile(sanitized)


def ollama_modellordner(umgebung: Mapping[str, str] | None = None) -> Path:
    """Wo Ollama seine Modelle ablegt: `OLLAMA_MODELS`, sonst `~/.ollama/models`."""
    umgebung = os.environ if umgebung is None else umgebung
    eigener = (umgebung.get('OLLAMA_MODELS') or '').strip()
    return Path(eigener).expanduser() if eigener else Path.home() / '.ollama' / 'models'


def _cgroup_grenze() -> int | None:
    """Eine Speichergrenze des Containers (cgroup v2 oder v1), falls gesetzt; sonst `None`."""
    for datei in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        try:
            roh = Path(datei).read_text(encoding='ascii').strip()
        except (OSError, UnicodeError):
            continue
        if roh.isdigit() and 0 < int(roh) < 1 << 60:  # „max“ bzw. eine riesige Zahl heißt: keine Grenze
            return int(roh)
    return None


def eigene_ausstattung() -> dict | None:
    """Was der Sidecar selbst über den Rechner sieht, wenn kein Helfer etwas gemeldet hat (Fremdprobe, Befund 10).

    Niemand soll gefragt werden, wie viel Arbeitsspeicher sein Rechner hat. Läuft Kingfisher direkt auf dem Rechner,
    ist die eigene Messung die Ausstattung des Rechners. Im Container ist sie die des Containers (bei Docker Desktop
    die der virtuellen Maschine) und damit eine **Untergrenze**: Der Rechner hat mindestens so viel. Das genügt für
    eine Vorauswahl, die sicher passt; ein Helfer auf dem Rechner kann später Genaueres melden.
    """
    try:
        gesamt = int(os.sysconf('SC_PAGE_SIZE')) * int(os.sysconf('SC_PHYS_PAGES'))
    except (AttributeError, OSError, ValueError, TypeError):
        return None
    grenze = _cgroup_grenze()
    if grenze:
        gesamt = min(gesamt, grenze)
    if gesamt < _GIB:
        return None
    container = _im_container()
    plattform = 'unknown' if container else {'darwin': 'macos', 'linux': 'linux', 'win32': 'windows'}.get(sys.platform, 'unknown')
    return {'memory_gb': round(gesamt / _GIB, 1), 'platform': plattform, 'untergrenze': container}


def _im_container() -> bool:
    return Path('/.dockerenv').exists() or bool(os.environ.get('container'))


def freier_platz_gb(umgebung: Mapping[str, str] | None = None, *, im_container: bool | None = None) -> float | None:
    """Freier Festplattenplatz für Modelle in GB, oder `None`, wenn er sich nicht sagen lässt.

    Gemessen wird dort, wo Ollama seine Modelle ablegt (fehlt der Ordner noch, der nächste vorhandene
    darüber; ist auch der unbekannt, das Home-Verzeichnis). Im Container sagt die Messung nichts über
    den Rechner des Nutzers: Dort gilt nur, was der Helfer auf dem Rechner gemeldet hat (`disk_free_bytes`).
    """
    if _im_container() if im_container is None else im_container:
        return None
    kandidat = ollama_modellordner(umgebung)
    while not kandidat.exists() and kandidat != kandidat.parent:
        kandidat = kandidat.parent
    for ort in (kandidat, Path.home()):
        try:
            return round(shutil.disk_usage(ort).free / _GIB, 1)
        except OSError:
            continue
    return None
