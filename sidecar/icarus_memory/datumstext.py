"""Zeitangaben lesen und aussprechen: die eine Stelle.

Vorher stand dieselbe Zeile („ISO-Text mit Z lesen“) in einem guten Dutzend
Module, jeweils mit leicht anderer Fehlerbehandlung. Die Unterschiede sind
Absicht und stehen hier als vier Namen, damit sie sichtbar sind:

* `iso_lesen`: leer ergibt `None`, Unlesbares wirft (gespeicherte Werte, die
  gültig sein müssen: ein Fehler soll auffallen, nicht verschwinden).
* `iso_lesen_streng`: wie oben, aber auch leer wirft.
* `iso_versuchen`: nie eine Ausnahme, unlesbar ergibt `None`, ein Zeitpunkt
  bleibt unverändert (Eingaben von außen: Kalender, Aufgaben).
* `iso_versuchen_utc`: wie `iso_versuchen`, aber ein Zeitpunkt ohne Zone gilt
  als UTC (Vergleiche mit Quellzeiten des Bestands).

Nur zusammengeführt ist, was Zeichen für Zeichen dasselbe tat.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MONATE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)

#: Kleingeschriebener Monatsname -> Nummer (auch „maerz“), zum Lesen von Datumsangaben im Text.
#: Kürzel („jan“, „okt“) gehören nur dort dazu, wo sie gelesen werden sollen (`fristen.py`).
MONAT_NUMMER = {'januar': 1, 'februar': 2, 'märz': 3, 'maerz': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7,
                'august': 8, 'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12}


def tag_und_monat(zeit: datetime) -> str:
    """»7. August« — so, wie man es sagen würde."""
    return f"{zeit.day}. {MONATE[zeit.month - 1]}"


def iso_lesen_streng(wert: str) -> datetime:
    return datetime.fromisoformat(wert.replace("Z", "+00:00"))


def iso_lesen(wert: str | None) -> datetime | None:
    return iso_lesen_streng(wert) if wert else None


def iso_versuchen(wert: Any) -> datetime | None:
    """ISO-Zeichenkette oder Zeitpunkt zu einem Zeitpunkt — oder nichts."""
    if wert is None:
        return None
    if isinstance(wert, datetime):
        return wert
    try:
        return iso_lesen_streng(str(wert))
    except ValueError:
        return None


def iso_versuchen_utc(wert: Any) -> datetime | None:
    """Wie `iso_versuchen`, nur Zeichenketten und Zeitpunkte; ohne Zone gilt UTC."""
    if isinstance(wert, datetime):
        moment = wert
    elif isinstance(wert, str) and wert:
        try:
            moment = iso_lesen_streng(wert)
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _beim_nutzer(zeit: datetime) -> tuple[datetime, str]:
    """Der Zeitpunkt in der Zeitzone des Nutzers; fehlt die Zonendatenbank, steht der Versatz dabei."""
    if zeit.tzinfo is None:
        return zeit, ''
    from .model import user_timezone
    zone = user_timezone()
    if zone is None:
        versatz = zeit.strftime('%z')
        return zeit, f' (UTC{versatz[:3]}:{versatz[3:]})'
    return zeit.astimezone(zone), ''


def tag_text(wert: Any) -> str:
    """»1. Oktober 2026« in der Zeitzone des Nutzers; Unlesbares ergibt ``''``."""
    zeit = iso_versuchen(wert)
    if zeit is None:
        return ''
    ort, versatz = _beim_nutzer(zeit)
    return f'{tag_und_monat(ort)} {ort.year}{versatz}'


def zeitpunkt_text(wert: Any) -> str:
    """»1. Oktober 2026, 12:25 Uhr« in der Zeitzone des Nutzers; Unlesbares ergibt ``''``.

    Für Menschen: kein ISO-Text, keine Sekunden. Fällt der Zeitpunkt beim Nutzer auf
    Mitternacht, steht nur der Tag da (ganztägige Angaben und Tagesgrenzen).
    """
    zeit = iso_versuchen(wert)
    if zeit is None:
        return ''
    ort, versatz = _beim_nutzer(zeit)
    tag = f'{tag_und_monat(ort)} {ort.year}'
    if (ort.hour, ort.minute, ort.second) == (0, 0, 0):
        return tag + versatz
    return f'{tag}, {ort:%H:%M} Uhr{versatz}'
