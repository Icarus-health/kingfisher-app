#!/usr/bin/env python3
"""Liest nur bekannte App-/Modellorte und Ollamas lokale Modellliste.

Auf dem Mac ausführen, nicht im Linux-Container. Keine Konten, Schlüssel,
Mails, Kalenderinhalte, Transkripte oder beliebigen Benutzerordner lesen.
Erkennung ist keine Nutzungsfreigabe und startet keine Modelle.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import urllib.request


def whisper_models(root: Path) -> list[dict]:
    results = []
    if not root.is_dir():
        return results
    for path in sorted(root.glob('ggml*.bin')):
        if path.is_file():
            results.append({'name': path.name, 'format': 'whisper.cpp', 'status': 'runtime_required'})
    # Nur Modellverzeichnisse; kompilierte Gewichte nicht betreten/lesen.
    required = ('AudioEncoder.mlmodelc', 'TextDecoder.mlmodelc', 'MelSpectrogram.mlmodelc')
    for variant in ('whisperkit', 'whisperkitpro'):
        for folder in sorted((root / variant / 'models' / 'argmaxinc').glob('*/*')):
            if folder.is_dir() and any((folder / name).is_dir() for name in required):
                results.append({
                    'name': folder.name, 'format': 'Core ML',
                    'components_present': all((folder / name).is_dir() for name in required),
                    'status': 'macos_runtime_required',
                    'license_review_required': variant == 'whisperkitpro',
                })
    return results


def discover(home: Path, applications: Path) -> dict:
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=3) as response:
            payload = json.load(response)
        ollama = {'reachable': True, 'models': [
            {'name': item['name'], 'size_bytes': item.get('size'), 'capabilities': item.get('capabilities', [])}
            for item in payload.get('models', []) if isinstance(item, dict) and isinstance(item.get('name'), str)
        ]}
    except (OSError, ValueError):
        ollama = {'reachable': False, 'models': []}
    return {
        'platform': platform.system(),
        'scope': 'known_local_apps_and_models_only',
        'ollama': ollama,
        'macwhisper_installed': (applications / 'MacWhisper.app').is_dir(),
        'speech_models': whisper_models(home / 'Library/Application Support/MacWhisper/models'),
        'calendar': {'status': 'permission_and_macos_bridge_required', 'accounts_scanned': False},
        'mail': {'status': 'explicit_connection_required', 'accounts_scanned': False},
        'secrets_read': False,
        'automatically_connected': False,
    }


if __name__ == '__main__':
    print(json.dumps(discover(Path.home(), Path('/Applications')), ensure_ascii=False, indent=2))
