"""Gemeinsame Hilfen der Messlatte-Tests.

Die Tests laufen mit ihrer eigenen kleinen Welt (`mini_welt/`), nie mit der
großen unter `messlatte/welt/`: Ein Test darf nicht rot werden, weil jemand
dort einen Szenariotext ändert.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
# Immer der Sidecar dieses Checkouts, auch wenn `icarus_memory` editierbar aus einem anderen
# Verzeichnis installiert ist (Worktrees): Die Messlatte misst den Code, in dem sie liegt.
for _pfad in (WURZEL / 'sidecar', WURZEL):
    if sys.path[:1] != [str(_pfad)]:
        sys.path.insert(0, str(_pfad))

MINI_WELT = Path(__file__).parent / 'mini_welt'


@pytest.fixture
def mini_welt() -> Path:
    return MINI_WELT


@pytest.fixture
def welt_kopie(tmp_path):
    """Kopie der Mini-Welt, die ein Test gezielt kaputt machen darf.

    `aendern(szenario, funktion)` lädt `szenarien/<szenario>.json`, übergibt das
    Objekt der Funktion und schreibt es zurück; `aendern('welt', ...)` ändert
    `welt.json`. Die Funktion ändert an Ort und Stelle, ihr Rückgabewert zählt nicht.
    """
    ziel = tmp_path / 'welt'
    shutil.copytree(MINI_WELT, ziel)

    def aendern(name, funktion):
        datei = ziel / ('welt.json' if name == 'welt' else f'szenarien/{name}.json')
        daten = json.loads(datei.read_text(encoding='utf-8'))
        funktion(daten)  # ändert das Objekt an Ort und Stelle; der Rückgabewert zählt nicht
        datei.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding='utf-8')

    aendern.pfad = ziel
    return aendern


def finde(liste, kennung):
    """Das Objekt mit dieser ID aus einer Liste von Quellen oder Fragen."""
    return next(x for x in liste if x['id'] == kennung)


def tief(objekt):
    return copy.deepcopy(objekt)


class Bestand:
    """Eine eingespielte Instanz samt Welt, Aufnahme-Ergebnis und Rückzuordnung Episode -> Welt-ID."""

    def __init__(self, instanz, welt, aufnahme):
        self.instanz, self.welt, self.aufnahme = instanz, welt, aufnahme
        self.rueck = {episode: quelle for quelle, episode in aufnahme.episoden.items()}

    def frage(self, kennung):
        return next(f for f in self.welt.fragen if f.id == kennung)


@pytest.fixture(scope='module')
def bestand():
    """Mini-Welt über die Produktpfade eingespielt (konstante Einordnung, kein Modell).

    Modulweit: Der Aufbau kostet etwa eine Sekunde, die Tests lesen nur.
    """
    from messlatte.aufnahme import aufnehmen
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welt

    welt = lade_welt(MINI_WELT)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone,
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        yield Bestand(instanz, welt, aufnehmen(instanz, welt.quellen, welt.stichtag))
