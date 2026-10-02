"""Modus „faelle“: aus Meldungen „Stimmt nicht?“ werden Fälle für `python -m messlatte lokal`.

    python -m messlatte faelle --aus DATEI [--ausgabe fragen.json]

`--aus` ist entweder die Ablage selbst (`rueckmeldungen.sqlite3` im Datenordner, wird nur gelesen)
oder eine JSON-Datei mit den Meldungen (die Antwort von `GET /api/v1/rueckmeldungen`, ihr Feld
`meldungen` oder eine Liste davon). Die Umwandlung selbst ist die des Produkts
(`icarus_memory.rueckmeldung_faelle`), dieselbe wie bei `GET /api/v1/rueckmeldungen/faelle`: Es gibt
genau eine Regel dafür, nicht zwei.

**Datenschutz:** Die Ausgabedatei enthält Frage- und Antworttexte aus dem echten Betrieb. Sie ist eine
lokale Datei für diesen Rechner; nichts wird gesendet. Auf dem Terminal erscheinen nur Zähler.
Sie gehört nicht ins Repository und nicht in Berichte oder Pull Requests. Der Bericht von `lokal`
schreibt auch mit dieser Datei keine Texte (siehe `lokal.py`).

Damit die Datei vor der ersten Messung nicht erst bei `lokal` auffällt, wird sie nach dem Schreiben
mit demselben Prüfer gelesen wie dort (`lokal.lade_fragen`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .welt import WeltFehler

STANDARD_AUSGABE = Path('rueckmeldungen-faelle.json')


def lese_meldungen(pfad: Path) -> list[dict[str, Any]]:
    """Meldungen aus der Ablage (`.sqlite3`, `.db`) oder einer JSON-Datei. Wirft `WeltFehler` mit lesbarem Grund."""
    from icarus_memory.rueckmeldung import Rueckmeldungen, RueckmeldungFehler

    pfad = Path(pfad)
    if not pfad.is_file():
        raise WeltFehler([f'{pfad}: Datei fehlt.'])
    if pfad.suffix.lower() in ('.sqlite3', '.sqlite', '.db'):
        try:
            return Rueckmeldungen.nur_lesen(pfad)
        except RueckmeldungFehler as fehler:
            raise WeltFehler([str(fehler)]) from None
    try:
        daten = json.loads(pfad.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as fehler:
        raise WeltFehler([f'{pfad}: Kein gültiges JSON in UTF-8 ({fehler}).']) from None
    liste = daten.get('meldungen') if isinstance(daten, dict) else daten
    pflicht = {'id', 'frage', 'antwort', 'art'}
    if not isinstance(liste, list) or not all(isinstance(m, dict) and pflicht <= set(m) for m in liste):
        raise WeltFehler([f'{pfad}: Erwartet die Meldungen von GET /api/v1/rueckmeldungen '
                          f'(je Meldung mindestens {", ".join(sorted(pflicht))}) oder die Datei rueckmeldungen.sqlite3.'])
    return liste


def erzeuge(meldungen: list[dict[str, Any]]) -> dict[str, Any]:
    from icarus_memory import rueckmeldung_faelle
    return rueckmeldung_faelle.faelle(meldungen)


def schreibe(daten: dict[str, Any], ausgabe: Path) -> Path:
    ausgabe = Path(ausgabe)
    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    ausgabe.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return ausgabe
