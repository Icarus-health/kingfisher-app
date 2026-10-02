"""Aus Meldungen werden Fälle für die Messlatte (`python -m messlatte lokal --fragen DATEI`).

Eine reine Umwandlung ohne Zugriff auf Speicher und Netz: Meldungen hinein, Fragenformat
der Messlatte (`messlatte/beispiel-eigene-fragen.json`, `messlatte/FORMAT.md`) heraus.

* **Frage**: die gestellte Frage.
* **Erwartete Aussage**: der Text aus „Richtig wäre …“, wenn der Nutzer einen eingetragen hat.
  Die Messlatte sucht ihn als Teilstück in der Antwort; ein Wort oder Datum („15. November“)
  trifft zuverlässiger als ein ganzer Satz.
* **Verbotene Aussage**: bei `falsch` und `veraltet` die gemeldete Antwort. Bestand sie aus
  genau einem Satz, ist es dieser Satz, sonst der ganze Text; sie zählt nur, wenn Kingfisher
  sie wörtlich wiederholt. Wer es gezielter will, kürzt die Zeile in der Datei auf die
  falsche Stelle (in der Notiz steht, worum es ging).
* **Belege**: die Kennungen der Quellen, auf die sich die gemeldete Antwort stützte, bei
  `falsch` und `veraltet` als verbotene Belege. Im Modus `lokal` haben Belege keine Wirkung.
* **Erledigt** ändert nichts am Fall: Er bleibt in der Datei und ist der Regressionstest.

Ein Fall ohne erwartete und ohne verbotene Aussage (etwa `zu_langsam`, `unvollstaendig` ohne
„Richtig wäre …“) lässt sich am Text nicht messen. Er steht in `nicht_messbar`, damit nichts
verloren geht, aber nicht unter `fragen`.

**Datenschutz:** Die Datei enthält Frage- und Antworttexte. Sie ist für diesen Rechner
gedacht und steht nicht in den Berichten der Messlatte (`lokal` schreibt nie Texte in Berichte).
"""
from __future__ import annotations

from typing import Any, Iterable

HINWEIS = ('Enthält Fragen und Antworttexte aus deinem Kingfisher. Nur auf diesem Rechner verwenden, '
           'nicht weitergeben und nicht ins Repository legen.')

_KRITISCH = ('falsch', 'veraltet')
_ART_SATZ = {'falsch': 'Gemeldet als falsch', 'unvollstaendig': 'Gemeldet als unvollständig',
             'veraltet': 'Gemeldet als veraltet', 'zu_langsam': 'Gemeldet als zu langsam',
             'sonstiges': 'Gemeldet'}


def fall_id(meldung: dict[str, Any]) -> str:
    return f"rueckmeldung-{meldung['id'][:12]}"


def verbotene_aussage(meldung: dict[str, Any]) -> str:
    """Die gemeldete falsche Aussage: der einzelne Satz oder die ganze Antwort."""
    saetze = (meldung.get('struktur') or {}).get('saetze') or []
    if len(saetze) == 1 and str(saetze[0].get('text', '')).strip():
        return str(saetze[0]['text']).strip()
    return str(meldung.get('antwort', '')).strip()


def als_fall(meldung: dict[str, Any]) -> dict[str, Any] | None:
    """Der Fall zu einer Meldung oder `None`, wenn sich am Text nichts messen lässt."""
    art = meldung['art']
    richtig = str(meldung.get('richtig', '')).strip()
    verboten = verbotene_aussage(meldung) if art in _KRITISCH else ''
    if not richtig and not verboten:
        return None
    notiz = _ART_SATZ.get(art, 'Gemeldet') + f" am {str(meldung.get('erstellt', ''))[:10]}."
    if verboten:
        notiz += ' Verboten ist die gemeldete Antwort; bei Bedarf auf die falsche Stelle kürzen.'
    if meldung.get('status') == 'erledigt':
        notiz += ' Erledigt, bleibt als Regressionstest.'
    fall: dict[str, Any] = {
        'id': fall_id(meldung), 'frage': meldung['frage'], 'kategorie': 'eigene',
        'schwere': 'kritisch' if art in _KRITISCH else 'normal',
        'erwartet': {'verhalten': 'antworten', **({'aussagen': [[richtig]]} if richtig else {})},
        'notiz': notiz}
    verbote: dict[str, Any] = {}
    if verboten:
        verbote['aussagen'] = [verboten]
        if meldung.get('belege'):
            verbote['belege'] = list(meldung['belege'])
    if verbote:
        fall['verboten'] = verbote
    return fall


def faelle(meldungen: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Alle Meldungen (auch erledigte), älteste zuerst, im Fragenformat der Messlatte."""
    fragen, offen = [], []
    for meldung in sorted(meldungen, key=lambda m: (m.get('erstellt', ''), m['id'])):
        fall = als_fall(meldung)
        if fall is not None:
            fragen.append(fall)
        else:
            offen.append({'id': fall_id(meldung), 'frage': meldung['frage'], 'art': meldung['art'],
                          'grund': 'Ohne „Richtig wäre …“ und ohne falsche Aussage lässt sich nichts am Text messen. '
                                   'Trage in der Datei eine erwartete Aussage nach, um einen Fall daraus zu machen.'})
    return {'hinweis': HINWEIS, 'fragen': fragen, 'nicht_messbar': offen}
