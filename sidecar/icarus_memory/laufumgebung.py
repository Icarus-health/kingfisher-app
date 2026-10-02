"""Auf welchem System Kingfisher läuft, damit die Oberfläche passende Sätze wählt (Fremdprobe, Befund 18).

Früher stand überall „Auf diesem Mac gespeichert“, „öffne sie auf diesem Mac neu“, „Öffne Kingfisher über die Mac-App“,
auch im Browser unter Linux oder in Docker ohne Mac. Die Oberfläche wählt ihre Sätze jetzt aus dieser einen Angabe
(`app/kingfisher/src/system.ts`), nicht in zwölf Einzelfällen.

Woran es erkannt wird, in dieser Reihenfolge:

* `mac`: Kingfisher läuft auf einem Mac. Entweder läuft der Sidecar selbst unter macOS (`sys.platform == 'darwin'`), oder
  er läuft im Container und der Startweg der Mac-App hat gemeldet, dass der Rechner ein Mac ist (`device-profile.json`,
  Plattform `macos`, geschrieben von `scripts/report_device.py`). Nur hier gibt es die Mac-Helfer (Kalender, Ordnerwahl,
  Apple Karten, Sicherung).
* `docker`: im Container ohne solche Meldung, also Docker mit dem Browser (Startweg aus der README, `make start`).
* `linux`, `windows`: der Sidecar läuft direkt auf diesem System.
* `rechner`: sonst.

Die Erkennung liest nur Dateien und Umgebung; sie fragt nichts im Netz und gibt keine Pfade heraus.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .device_profile import _im_container

ARTEN = ('mac', 'docker', 'linux', 'windows', 'rechner')

#: Wie der Nutzer das System nennt, auf dem Kingfisher läuft (für Sätze wie „Kingfisher läuft als …“).
NAMEN = {'mac': 'Mac-App', 'docker': 'Docker im Browser', 'linux': 'Linux', 'windows': 'Windows', 'rechner': 'dieser Rechner'}


def system_art(*, plattform: str | None = None, im_container: bool | None = None,
               wirt: str | None = None) -> str:
    """`mac`, `docker`, `linux`, `windows` oder `rechner`. `wirt` ist die gemeldete Plattform des Rechners."""
    plattform = sys.platform if plattform is None else plattform
    container = _im_container() if im_container is None else im_container
    if plattform == 'darwin' or (container and wirt == 'macos'):
        return 'mac'
    if container:
        return 'docker'
    if plattform.startswith('linux'):
        return 'linux'
    if plattform.startswith(('win', 'cygwin')):
        return 'windows'
    return 'rechner'


def beschreiben(data_dir: str | Path | None, **kwargs) -> dict:
    """Die Angabe für `GET /api/v1/system` und `GET /api/v1/setup` (`system`)."""
    if 'wirt' not in kwargs and data_dir is not None:
        from .device_profile import load_device_profile
        kwargs['wirt'] = load_device_profile(data_dir).get('platform')
    art = system_art(**kwargs)
    return {'art': art, 'name': NAMEN[art], 'geraet': 'Mac' if art == 'mac' else 'Rechner', 'mac_helfer': art == 'mac'}


__all__ = ['ARTEN', 'NAMEN', 'beschreiben', 'system_art']
