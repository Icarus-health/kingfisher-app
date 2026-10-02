"""Wetter (Etappe F4): am Wohnort und dort, wo der nächste auswärtige Termin stattfindet.

Ein Wetterdienst ohne Schlüssel (Open-Meteo), eine Einstellung in der Oberfläche statt Umgebungsvariablen.

**Was den Rechner verlässt**, und nur mit eingeschaltetem „Wetter im Briefing“:

* die Suche nach einem Ort: der **Ortsname**, den der Nutzer eintippt oder der aus dem Termin stammt
  (nie eine Straße, nie Titel, Teilnehmer oder Uhrzeit des Termins);
* die Wettervorhersage: **zwei auf zwei Nachkommastellen gerundete Zahlen** (rund einen Kilometer).

Ohne Einstellung (Vorgabe aus) wird keine Anfrage für das Briefing gestellt. Das sichert
`WetterDienst._anfragen` an genau einer Stelle: Jede Anfrage geht durch sie und prüft vorher die
Einwilligung und die Adresse des Dienstes (nur die beiden Open-Meteo-Adressen, nur https).

Die Umgebungsvariablen `KINGFISHER_WEATHER_ENABLED`, `…_LOCATION`, `…_LATITUDE`, `…_LONGITUDE` bleiben als
Vorbelegung gültig, solange in der Oberfläche nichts eingestellt wurde (`Einstellung.aus`).

Dieses Modul kennt weder Akten noch Kalender: Es bekommt Namen und Zeiten und liefert Wetter.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
VORHERSAGE_URL = 'https://api.open-meteo.com/v1/forecast'
ERLAUBTE_HOSTS = frozenset({'geocoding-api.open-meteo.com', 'api.open-meteo.com'})
ZEITLIMIT_S = 4.0
MAX_ORT_ZEICHEN = 80
VORHERSAGE_TTL_S = 30 * 60
ORT_TTL_S = 24 * 60 * 60
FEHLER_PAUSE_S = 5 * 60
"""Nach einem Fehlschlag wird dieselbe Anfrage so lange nicht wiederholt."""
REGEN_WAHRSCHEINLICHKEIT = 50
"""Ab so viel Prozent Regenwahrscheinlichkeit lohnt der Hinweis auf den Schirm."""

_UMGEBUNG_AN = {'1', 'true', 'yes'}


# -- Einstellung -------------------------------------------------------------


def _zahl(wert: Any, grenze: float) -> float | None:
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return None
    return zahl if abs(zahl) <= grenze and zahl == zahl else None


@dataclass
class Einstellung:
    """„Wetter im Briefing“. Vorgabe: aus, denn der Ortsname verlässt den Rechner."""

    aktiv: bool = False
    ort: str = ''
    """Anzeigename des gewählten Ortes („Mainz, Rheinland-Pfalz, Deutschland“)."""
    name: str = ''
    """Kurzer Ortsname („Mainz“); so steht er im Briefing und dient dem Vergleich mit dem Terminort."""
    breite: float | None = None
    laenge: float | None = None

    @classmethod
    def aus(cls, daten: Mapping[str, Any] | None, umgebung: Mapping[str, str] | None = None) -> 'Einstellung':
        """Aus den gespeicherten Daten. Ohne jede gespeicherte Angabe gilt die Vorbelegung aus der Umgebung."""
        if not isinstance(daten, Mapping) or not daten:
            return cls._aus_umgebung(os.environ if umgebung is None else umgebung)
        breite, laenge = _zahl(daten.get('breite'), 90), _zahl(daten.get('laenge'), 180)
        name = ' '.join(str(daten.get('name') or '').split())[:MAX_ORT_ZEICHEN]
        ort = ' '.join(str(daten.get('ort') or name).split())[:MAX_ORT_ZEICHEN * 2]
        # Nur ein echtes `true` zählt, und nur mit einem Ort, den es wirklich gibt.
        aktiv = daten.get('aktiv') is True and breite is not None and laenge is not None and bool(name)
        return cls(aktiv=aktiv, ort=ort, name=name, breite=breite, laenge=laenge)

    @classmethod
    def _aus_umgebung(cls, umgebung: Mapping[str, str]) -> 'Einstellung':
        if str(umgebung.get('KINGFISHER_WEATHER_ENABLED', '')).strip().lower() not in _UMGEBUNG_AN:
            return cls()
        name = str(umgebung.get('KINGFISHER_WEATHER_LOCATION', '')).strip()[:MAX_ORT_ZEICHEN]
        breite = _zahl(umgebung.get('KINGFISHER_WEATHER_LATITUDE') or None, 90)
        laenge = _zahl(umgebung.get('KINGFISHER_WEATHER_LONGITUDE') or None, 180)
        if not name or breite is None or laenge is None:
            return cls()
        return cls(aktiv=True, ort=name, name=name, breite=breite, laenge=laenge)

    def to_dict(self) -> dict[str, Any]:
        return {'aktiv': self.aktiv, 'ort': self.ort, 'name': self.name, 'breite': self.breite, 'laenge': self.laenge}


# -- Ortsnamen aus Adressen ---------------------------------------------------

_PLZ_ORT = re.compile(r'\b\d{5}[ \t]+([A-ZÄÖÜ][\wäöüß.-]*(?:[ \t]+(?:am|an|im|in|der|bei|ob|[A-ZÄÖÜ])[\wäöüß.-]*)?)')
_LAENDER = {'deutschland', 'germany', 'österreich', 'schweiz'}
_KEIN_ORT = re.compile(r'(?i)(stra(ß|ss)e|str\.|weg|platz|allee|gasse|raum|saal|etage|büro|zimmer)\b')


def ortsname(adresse: str | None) -> str:
    """Der Ortsname aus einer Adresse („Druckerei Braun, Werkstraße 4, 55116 Mainz“ -> „Mainz“).

    Nur der Ort darf den Rechner verlassen, nie Straße oder Hausnummer. Ist kein Ort zu erkennen,
    bleibt der Rückgabewert leer, und es geht nichts hinaus.
    """
    text = ' '.join(str(adresse or '').split())
    if not text:
        return ''
    treffer = _PLZ_ORT.search(text)
    if treffer:
        return treffer.group(1).strip()[:MAX_ORT_ZEICHEN]
    teile = [t.strip() for t in text.split(',') if t.strip()]
    while teile and teile[-1].casefold() in _LAENDER:
        teile.pop()
    if not teile:
        return ''
    letzter = teile[-1]
    # Ein Ort hat weder Ziffern noch Straßen- oder Raumwörter und ist kurz.
    if any(z.isdigit() for z in letzter) or len(letzter) > 40 or len(letzter.split()) > 3 or _KEIN_ORT.search(letzter):
        return ''
    if len(teile) == 1 and len(letzter.split()) > 2:
        return ''
    return letzter[:MAX_ORT_ZEICHEN]


def gleicher_ort(a: str, b: str) -> bool:
    def schluessel(text: str) -> str:
        return ''.join(z for z in str(text or '').casefold() if z.isalnum())
    return bool(schluessel(a)) and schluessel(a) == schluessel(b)


# -- Wetterlage in Worten -----------------------------------------------------

_NASS = {'Regen', 'Gewitter', 'Gefrierender Regen'}


def _zustand(code: int) -> str:
    from .morning import _weather_code
    return _weather_code(code)


def _uhr(zeit: datetime) -> str:
    return f'{zeit.hour} Uhr' if zeit.minute == 0 else f'{zeit.hour}:{zeit.minute:02d} Uhr'


def satz_am_termin(ort: str, wann: datetime, wetter: Mapping[str, Any]) -> str:
    """„Mainz, 14 Uhr: 12 °C, Regen – Schirm einpacken?“ Der Schirm nur als Frage, nie als Tatsache."""
    text = f'{ort}, {_uhr(wann)}: {wetter["temperature_c"]} °C, {str(wetter["condition"]).lower()}'
    return text + (' – Schirm einpacken?' if wetter.get('schirm') else '.')


# -- Der Dienst ---------------------------------------------------------------


class WetterFehler(Exception):
    """Der Dienst hat nicht geantwortet oder Unbrauchbares geliefert. Die Meldung enthält nie Orte oder Adressen."""


Holen = Callable[[str, dict[str, Any]], Any]


def _holen_httpx(url: str, params: dict[str, Any]) -> Any:
    try:
        antwort = httpx.get(url, params=params, timeout=ZEITLIMIT_S, follow_redirects=False)
        antwort.raise_for_status()
        return antwort.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Ohne die Adresse (sie trüge den Ort): nur die Art des Fehlers.
        raise WetterFehler(type(exc).__name__) from None


class WetterDienst:
    """Ortssuche und Vorhersage. Liest die Einstellung bei jeder Auskunft neu; merkt sich Antworten."""

    def __init__(self, einstellung: Callable[[], Einstellung], holen: Holen | None = None,
                 uhr: Callable[[], float] = time.monotonic):
        self.einstellung = einstellung
        self._holen = holen or _holen_httpx
        self._uhr = uhr
        self._gemerkt: dict[tuple, tuple[float, Any]] = {}
        self.anfragen = 0
        """Wie viele Anfragen hinausgingen (für Tests)."""

    def _anfragen(self, url: str, params: dict[str, Any], *, ttl: float, einwilligung: bool) -> Any:
        """Die einzige Stelle, an der etwas hinausgeht."""
        if not einwilligung:
            raise WetterFehler('keine Einwilligung')
        adresse = urlparse(url)
        if adresse.scheme != 'https' or adresse.hostname not in ERLAUBTE_HOSTS:
            raise WetterFehler('unerlaubte Adresse')
        schluessel = (url, tuple(sorted((k, str(v)) for k, v in params.items())))
        jetzt = self._uhr()
        gemerkt = self._gemerkt.get(schluessel)
        if gemerkt is not None:
            if isinstance(gemerkt[1], WetterFehler):
                if jetzt - gemerkt[0] < FEHLER_PAUSE_S:
                    raise gemerkt[1]
            elif jetzt - gemerkt[0] < ttl:
                return gemerkt[1]
        self.anfragen += 1
        try:
            antwort = self._holen(url, dict(params))
        except WetterFehler as fehler:
            self._gemerkt[schluessel] = (jetzt, fehler)
            raise
        self._gemerkt[schluessel] = (jetzt, antwort)
        return antwort

    # -- Ortssuche --

    def suche(self, text: str, *, einwilligung: bool = True, anzahl: int = 5) -> list[dict[str, Any]]:
        """Orte zu einem Namen. Die Suche in den Einstellungen ist eine ausdrückliche Handlung des Nutzers
        (er tippt oder klickt), braucht also keine eingeschaltete Einstellung; sie schickt nur den Namen."""
        name = ' '.join(str(text or '').split())[:MAX_ORT_ZEICHEN]
        if len(name) < 2:
            return []
        daten = self._anfragen(GEOCODING_URL, {'name': name, 'count': anzahl, 'language': 'de', 'format': 'json'},
                               ttl=ORT_TTL_S, einwilligung=einwilligung)
        ergebnis = []
        for eintrag in (daten.get('results') or []) if isinstance(daten, dict) else []:
            try:
                kurz = str(eintrag['name']).strip()
                breite, laenge = _zahl(eintrag['latitude'], 90), _zahl(eintrag['longitude'], 180)
            except (KeyError, TypeError):
                continue
            if not kurz or breite is None or laenge is None:
                continue
            zusatz = [str(eintrag[k]).strip() for k in ('admin1', 'country') if eintrag.get(k)]
            ergebnis.append({'name': kurz[:MAX_ORT_ZEICHEN], 'ort': ', '.join([kurz, *zusatz])[:MAX_ORT_ZEICHEN * 2],
                             'breite': round(breite, 4), 'laenge': round(laenge, 4)})
        return ergebnis

    # -- Vorhersage --

    def _vorhersage(self, breite: float, laenge: float) -> dict[str, Any]:
        daten = self._anfragen(VORHERSAGE_URL, {
            'latitude': f'{breite:.2f}', 'longitude': f'{laenge:.2f}', 'timezone': 'auto', 'forecast_days': 3,
            'current': 'temperature_2m,weather_code',
            'hourly': 'temperature_2m,weather_code,precipitation_probability'},
            ttl=VORHERSAGE_TTL_S, einwilligung=self.einstellung().aktiv)
        if not isinstance(daten, dict):
            raise WetterFehler('Antwort unbrauchbar')
        return daten

    def aktuell(self) -> dict[str, Any] | None:
        """Wetter am Wohnort jetzt, in der Form, die `tagesbriefing` kennt; None ohne Einstellung oder Antwort."""
        einst = self.einstellung()
        if not einst.aktiv:
            return None
        try:
            aktuell = self._vorhersage(einst.breite, einst.laenge).get('current') or {}
            return {'location': einst.name, 'temperature_c': round(float(aktuell['temperature_2m'])),
                    'condition': _zustand(int(aktuell['weather_code'])), 'attribution': 'Open-Meteo',
                    'attribution_url': 'https://open-meteo.com/'}
        except (WetterFehler, KeyError, TypeError, ValueError):
            return None

    def am_ort(self, ort: str, wann: datetime) -> dict[str, Any] | None:
        """Wetter an einem Ort zu einer Zeit. Der Name wird aufgelöst (erster Treffer), sonst None.

        Ohne Einstellung geht nichts hinaus. Mehrdeutige Namen sind ein Restrisiko: Der erste Treffer der
        Suche zählt; das Briefing nennt den Namen, damit ein Irrtum auffällt.
        """
        einst = self.einstellung()
        name = ortsname(ort)
        if not einst.aktiv or not name:
            return None
        try:
            treffer = self.suche(name, einwilligung=einst.aktiv, anzahl=1)
            if not treffer:
                return None
            daten = self._vorhersage(treffer[0]['breite'], treffer[0]['laenge'])
            zone = ZoneInfo(str(daten.get('timezone') or 'UTC'))
            lokal = wann.astimezone(zone).replace(minute=0, second=0, microsecond=0, tzinfo=None)
            stunden = daten['hourly']
            index = list(stunden['time']).index(lokal.strftime('%Y-%m-%dT%H:%M'))
            zustand = _zustand(int(stunden['weather_code'][index]))
            regen = (stunden.get('precipitation_probability') or [None] * (index + 1))[index]
            return {'ort': treffer[0]['name'], 'temperature_c': round(float(stunden['temperature_2m'][index])),
                    'condition': zustand,
                    'schirm': zustand in _NASS or (regen is not None and float(regen) >= REGEN_WAHRSCHEINLICHKEIT)}
        except (WetterFehler, KeyError, TypeError, ValueError, IndexError, OSError):
            return None


__all__ = ['Einstellung', 'WetterDienst', 'WetterFehler', 'gleicher_ort', 'ortsname', 'satz_am_termin']
