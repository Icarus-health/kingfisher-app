"""Misst `fristangaben_in` an den beiden unabhängig geschriebenen Prüfsätzen.

Aufruf aus dem Repository: ``PYTHONPATH=sidecar python docs/runs/2026-10-19-fristen-formulierungen/messen.py``.
Die Prüfsätze werden mit ``ast.literal_eval`` gelesen, nicht ausgeführt. Bezug ist Donnerstag, 3. September 2026.
"""
import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

from icarus_memory.fristen import fristangaben_in

BEZUG = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
ORDNER = Path(__file__).resolve().parent


def lesen(datei: Path) -> list:
    baum = ast.parse(datei.read_text(encoding='utf-8'))
    return ast.literal_eval(next(knoten.value for knoten in baum.body
                                 if isinstance(knoten, ast.Assign) and knoten.targets[0].id == 'HOLDOUT'))


def messen(faelle: list, zeigen: bool = False) -> dict:
    zahlen = {'saetze': len(faelle), 'richtig': 0, 'mit_frist': 0, 'mit_frist_richtig': 0,
              'ohne_frist': 0, 'ohne_frist_richtig': 0, 'falscher_tag': 0}
    for bereich, text, tage, offen in faelle:
        suche = fristangaben_in(text, BEZUG)
        ist = (sorted(f.datum.isoformat() for f in suche.fristen), len(suche.ohne_datum))
        soll = (sorted(tage), offen)
        richtig = ist == soll
        zahlen['richtig'] += richtig
        art = 'mit_frist' if tage or offen else 'ohne_frist'
        zahlen[art] += 1
        zahlen[art + '_richtig'] += richtig
        zahlen['falscher_tag'] += bool(set(ist[0]) - set(soll[0]))
        if zeigen and not richtig:
            print(f'  [{bereich}] {text}\n      soll {soll}  ist {ist}')
    return zahlen


if __name__ == '__main__':
    zeigen = '--zeigen' in sys.argv
    for name in ('pruefsatz_1.py', 'pruefsatz_2.py'):
        z = messen(lesen(ORDNER / name), zeigen)
        print(f"{name}: {z['richtig']}/{z['saetze']} richtig; Sätze mit Frist {z['mit_frist_richtig']}/{z['mit_frist']}, "
              f"ohne Frist {z['ohne_frist_richtig']}/{z['ohne_frist']}, mit falschem oder zusätzlichem Kalendertag "
              f"{z['falscher_tag']}")
