"""Antwortzeiten im Bericht: Median und 90-Prozent-Wert je Stufe, dazu das Ziel „höchstens 8 s im Median“.

Woher die Zahlen kommen:

* `abruf`: die Suche ohne Modell je Frage (`AbrufErgebnis.dauer_s`), nur im Lauf.
* `antwort_warm`: die ganze Antwort über die Konversations-API, ohne die erste (kalte) Antwort.
* `abschnitte`: die Zeiten, die das Produkt selbst der Antwort mitgibt (`context.zeiten`, siehe
  `sidecar/icarus_memory/zeitmessung.py`): Frage verstehen, Suche, Antwortmodell (Auswahl), Sätze
  (zweiter Modellaufruf), Satzprüfung und Prüfmodell (zweites Tor). Sie fehlen, wo der Abschnitt nicht lief (kein Modell, Sätze aus).

Das Ziel wird nur beurteilt, wenn ein Modell lief. Ohne Modell steht „nicht gemessen“, nie „bestanden“.

Dieses Modul importiert das Produkt nicht (der Modus `lokal` braucht es nicht): Die Zielgrenze steht hier
noch einmal; ein Test hält sie gleich (`test_zeiten.py`).
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any

ZIEL_MEDIAN_S = 8.0

ABSCHNITTE = (('frage', 'Frage verstehen'), ('suche', 'Suche und Kontext'),
              ('antwort_modell', 'Antwortmodell (Quellen wählen)'), ('saetze_modell', 'Sätze (zweiter Modellaufruf)'),
              ('satzpruefung', 'Satzprüfung'), ('pruefung_modell', 'Prüfmodell (zweites Tor)'),
              ('gesamt', 'Antwort gesamt laut Produkt'))


def lese(roh: Any) -> dict[str, float]:
    """Die Zeiten aus dem Kontext einer Antwort; leer, wenn sie fehlen oder keine Zahlen sind."""
    if not isinstance(roh, Mapping):
        return {}
    ergebnis = {}
    for name, _ in ABSCHNITTE:
        wert = roh.get(name)
        if isinstance(wert, bool) or not isinstance(wert, (int, float)) or not 0 <= wert < 86400:
            continue
        ergebnis[name] = float(wert)
    return ergebnis


def kennzahl(werte: Iterable[float]) -> dict | None:
    """Anzahl, Median und 90-Prozent-Wert (nächster Rang); None ohne Werte."""
    geordnet = sorted(werte)
    if not geordnet:
        return None
    rang = max(1, math.ceil(len(geordnet) * 0.9 - 1e-9))
    return {'n': len(geordnet), 'median_s': round(median(geordnet), 3), 'p90_s': round(geordnet[rang - 1], 3)}


def auswerten(abruf_dauern: Iterable[float], antworten: Iterable) -> dict:
    """Die Antwortzeiten eines Laufs. `antworten`: `AntwortErgebnis` mit `dauer_s`, `kalt`, `fehler`, `zeiten`."""
    warm = [a for a in antworten if a is not None and not a.kalt and not a.fehler]
    abschnitte = {}
    for name, _ in ABSCHNITTE:
        kz = kennzahl(a.zeiten[name] for a in warm if name in (a.zeiten or {}))
        if kz is not None:
            abschnitte[name] = kz
    modell_lief = any('antwort_modell' in (a.zeiten or {}) for a in warm)
    gesamt = kennzahl(a.dauer_s for a in warm)
    ziel = {'grenze_s': ZIEL_MEDIAN_S, 'median_s': gesamt['median_s'] if gesamt else None,
            'bestanden': (gesamt['median_s'] <= ZIEL_MEDIAN_S) if modell_lief and gesamt else None}
    return {'abruf': kennzahl(abruf_dauern), 'antwort_warm': gesamt, 'abschnitte': abschnitte,
            'modell_lief': modell_lief, 'ziel': ziel}


def ziel_zeile(auswertung: Mapping) -> str:
    """„Antwortzeit im Ziel: ≤ 8 s Median: bestanden (…)“, oder ehrlich „nicht gemessen“."""
    ziel = auswertung['ziel']
    kopf = f"Antwortzeit im Ziel: ≤ {ziel['grenze_s']:g} s Median: "
    if ziel['bestanden'] is None:
        return kopf + 'nicht gemessen (' + ('kein Modell lief' if not auswertung['modell_lief']
                                          else 'keine warme Antwort') + ')'
    warm = auswertung['antwort_warm']
    return (kopf + ('bestanden' if ziel['bestanden'] else 'nicht bestanden')
            + f" (Median {warm['median_s']} s, 90-Prozent-Wert {warm['p90_s']} s, {warm['n']} warme Antworten)")


def markdown(auswertung: Mapping) -> list[str]:
    """Der Abschnitt „Antwortzeit“ des Berichts: die Zielzeile und eine Tabelle Median / 90-Prozent-Wert je Stufe."""
    zeilen = [ziel_zeile(auswertung), '']
    stufen = []
    if auswertung['abruf']:
        stufen.append(('Abruf je Frage (Suche ohne Modell)', auswertung['abruf']))
    if auswertung['antwort_warm']:
        stufen.append(('Antwort gesamt, warm (über die API)', auswertung['antwort_warm']))
    stufen += [(titel, auswertung['abschnitte'][name]) for name, titel in ABSCHNITTE if name in auswertung['abschnitte']]
    if not stufen:
        return zeilen
    zeilen += ['| Stufe | Antworten | Median (s) | 90-Prozent-Wert (s) |', '|---|---|---|---|']
    zeilen += [f"| {titel} | {kz['n']} | {kz['median_s']} | {kz['p90_s']} |" for titel, kz in stufen]
    return zeilen + ['']


__all__ = ['ABSCHNITTE', 'ZIEL_MEDIAN_S', 'auswerten', 'kennzahl', 'lese', 'markdown', 'ziel_zeile']
