"""Kleine Darstellungshilfen für Berichte, ohne Abhängigkeit vom Produkt.

Gemeinsam für den Bericht des Laufs (`bericht.py`) und den des lokalen Modus
(`lokal.py`), der das Produkt nicht importieren muss.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from statistics import median

from .bewertung import KLASSEN, Zaehler, x_von_n

WURZEL = Path(__file__).resolve().parents[1]

KLASSEN_NAMEN = {'richtig': 'richtig', 'unvollstaendig': 'unvollständig', 'falsch': 'falsch',
                 'unnoetige_rueckfrage': 'unnötige Rückfrage', 'verweigert': 'verweigert', 'fehler': 'Fehler'}


def kuerzen(text: str, grenze: int = 300) -> str:
    text = ' '.join((text or '').split())
    return text if len(text) <= grenze else text[:grenze - 1].rstrip() + '…'


def tabelle(kopf: list[str], zeilen: list[list]) -> list[str]:
    ausgabe = ['| ' + ' | '.join(kopf) + ' |', '|' + '|'.join('---' for _ in kopf) + '|']
    ausgabe += ['| ' + ' | '.join(str(z) for z in zeile) + ' |' for zeile in zeilen]
    return ausgabe + ['']


def klassen_tabelle(titel: str, gruppen: dict) -> list[str]:
    """Ergebnisklassen je Gruppe, jede Zahl als „x von n“."""
    kopf = [titel, 'Fragen', *(KLASSEN_NAMEN[k] for k in KLASSEN), 'falsche Aussagen']
    zeilen = []
    for name, z in gruppen.items():
        zeilen.append([name, z.n, *(x_von_n(getattr(z, k), z.n) for k in KLASSEN), x_von_n(z.falsche_aussagen, z.n)])
    return tabelle(kopf, zeilen)


def zeiten(dauern_kalt: list[float], dauern_warm: list[float]) -> dict:
    """Erste Antwort (kalt) getrennt von den warmen."""
    return {'kalt_s': dauern_kalt[0] if dauern_kalt else None, 'warm_n': len(dauern_warm),
            'warm_median_s': round(median(dauern_warm), 3) if dauern_warm else None,
            'warm_max_s': max(dauern_warm) if dauern_warm else None}


def zeiten_satz(z: dict) -> str:
    return (f"Zeiten: erste Antwort (kalt) {z['kalt_s']} s; warm: {z['warm_n']} Antworten, "
            f"Median {z['warm_median_s']} s, längste {z['warm_max_s']} s.")


def git_stand(wurzel: Path = WURZEL) -> str:
    """Commit-Hash, mit „+geändert“, wenn der Arbeitsbaum Änderungen hat; sonst „unbekannt“."""
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=wurzel, capture_output=True, text=True,
                                timeout=10, check=True).stdout.strip()
        offen = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=wurzel,
                               capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        return commit + ('+geändert' if offen else '')
    except (OSError, subprocess.SubprocessError):
        return 'unbekannt'


__all__ = ['KLASSEN_NAMEN', 'WURZEL', 'Zaehler', 'git_stand', 'klassen_tabelle', 'kuerzen', 'tabelle', 'zeiten',
           'zeiten_satz']
