#!/usr/bin/env python3
"""Leistung der Bezüge und Akten bei vielen Quellen (Etappe D).

Spielt die Welt der Messlatte samt N Rauschquellen über die Produktpfade ein und misst:

  1. Bezüge, erster Lauf (alle Quellen), 2. Lauf ohne Änderung, 3. Lauf nach 100 neuen Quellen,
  4. Sachenliste, 5. größte Akte kalt und warm, 6. Neuberechnung nach Änderung einer Quelle,
  7. eine unbeteiligte Akte bleibt im Zwischenspeicher.

    python scripts/probe_akten_scale.py [--rauschen 10000] [--seed 1]

Ohne Modell; die Einordnung der Weltquellen ist die Regel-Einordnung der Messlatte, die des Rauschens
die konstante. Zeiten sind Wanduhr in dieser Umgebung (langsame Schreibbestätigung), keine Zusage.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(WURZEL / 'sidecar'), str(WURZEL)]


def gemessen(text: str, funktion):
    start = time.perf_counter()
    ergebnis = funktion()
    print(f'{text}: {time.perf_counter() - start:.2f} s', flush=True)
    return ergebnis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--rauschen', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=1)
    args = parser.parse_args()

    from icarus_memory import EpisodeKind, Provenance, SourceType
    from icarus_memory.akten import Akten
    from icarus_memory.bezuege import Bezuege
    from messlatte import aufnahme, rauschen
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten

    welten = lade_welten([str(WURZEL / 'messlatte' / 'welt')])
    welt = welten[0]
    lauter = rauschen.erzeuge(args.rauschen, welten, args.seed)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = gemessen(f'Aufnahme von {len(welt.quellen)} Weltquellen und {len(lauter)} Rauschquellen',
                               lambda: aufnahme.aufnehmen(instanz, [*welt.quellen, *lauter], welt.stichtag,
                                                          modell=RegelEinordnung()))
        print(f'  aufgenommen: {aufgenommen.aufgenommen}', flush=True)
        bezuege = Bezuege(instanz.episodes, workspace=instanz.app.state.workspace, eigene=lambda: list(instanz.eigene))
        akten = Akten(instanz.episodes, bezuege, claims=instanz.claims)
        conn = instanz.episodes._conn

        stand = gemessen('1. Bezüge, erster Lauf', bezuege.aktualisieren)
        print(f"  berechnet: {stand['berechnet']}, offen: {stand['offen']}")
        gemessen('   davon Verzeichnis neu bauen', lambda: (setattr(bezuege, '_register', None), bezuege.register()))
        stand = gemessen('2. Bezüge, nichts geändert', bezuege.aktualisieren)
        print(f"  berechnet: {stand['berechnet']}")
        vorhanden = conn.execute('SELECT COUNT(*) FROM sach_bezuege').fetchone()[0]
        print(f'  Zeilen in sach_bezuege: {vorhanden}', flush=True)

        jetzt = welt.stichtag
        for n in range(100):
            instanz.episodes.record(EpisodeKind.MESSAGE, f'Neu {n}', f'Neue Nachricht Nummer {n} vom Tag.',
                                    Provenance(SourceType.EMAIL, source_ref=f'probe:{n}'),
                                    participants=[f'Probe {n % 7} <probe{n % 7}@neu.example>'],
                                    occurred_at=jetzt - timedelta(days=n % 20))
        stand = gemessen('3. Bezüge nach 100 neuen Quellen', bezuege.aktualisieren)
        print(f"  berechnet: {stand['berechnet']}")

        seite = gemessen('4. Sachenliste (50)', lambda: bezuege.sachen(limit=50))
        print(f"  Sachen gesamt: {seite['gesamt']}")
        groesste = conn.execute(
            "SELECT sache, COUNT(*) n FROM sach_bezuege WHERE sache != '' GROUP BY sache ORDER BY n DESC LIMIT 3").fetchall()
        print('  größte Sachen:', [(g['sache'], g['n']) for g in groesste])
        sache = groesste[0]['sache']
        akte = gemessen(f'5a. Akte {sache}, kalt', lambda: akten.akte(sache))
        print(f"  Quellen: {akte['quellen']['gesamt']} (ausgewertet {akte['quellen']['beruecksichtigt']}), "
              f"aus Zwischenspeicher: {akte['aus_zwischenspeicher']}")
        akte = gemessen('5b. dieselbe Akte, warm', lambda: akten.akte(sache))
        print(f"  aus Zwischenspeicher: {akte['aus_zwischenspeicher']}")
        akte = gemessen('5c. dieselbe Akte, alle Zeilen (alle=True)', lambda: akten.akte(sache, alle=True))

        quellen = bezuege.quellen_von(sache)
        geaendert = quellen[0]['episode_id']
        # Eine große Sache ohne die geänderte Quelle: ihre Akte darf nicht neu gerechnet werden.
        andere = conn.execute(
            "SELECT sache FROM sach_bezuege WHERE sache != '' GROUP BY sache HAVING SUM(episode_id = ?) = 0 "
            "ORDER BY COUNT(*) DESC LIMIT 1", (geaendert,)).fetchone()[0]
        akten.akte(andere)
        instanz.episodes.add_contacts(geaendert, [{'name': 'X', 'adresse': 'x@neu.example', 'rolle': 'an', 'ich': False}],
                                      ['X <x@neu.example>'])
        gemessen('6a. Bezüge nach Änderung einer Quelle', bezuege.aktualisieren)
        akte = gemessen('6b. Akte danach, neu berechnet', lambda: akten.akte(sache))
        print(f"  aus Zwischenspeicher: {akte['aus_zwischenspeicher']}")
        andere_akte = gemessen('7. unbeteiligte Akte danach', lambda: akten.akte(andere))
        print(f"  aus Zwischenspeicher: {andere_akte['aus_zwischenspeicher']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
