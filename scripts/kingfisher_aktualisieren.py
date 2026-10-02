#!/usr/bin/env python3
"""Kingfisher auf eine neue Fassung bringen, ohne Daten zu verlieren (`make aktualisieren`, docs/53).

Der Weg für alle, die Kingfisher aus einer Arbeitskopie mit `make start` betreiben. In der Mac-App macht der Knopf
„Jetzt aktualisieren“ dasselbe. Die Schritte, und was bei einem Fehler gilt:

1. **Welche Fassung?** `FASSUNG=1.2.0` nennt sie; sonst fragt das Programm den laufenden Kingfisher, der die
   Download-Seite einmal abfragt und das Manifest streng prüft (`POST /api/v1/fassung/pruefen`). Ist nichts Neueres
   da, sagt es das und hört auf.
2. **Sichern** wie `make backup`, aber als Sicherung vor einem Update (`vor-update-…`), die `make zurueck-vor-update`
   findet. Scheitert das, wird nichts verändert.
3. **Bild laden** (`docker pull`). Scheitert das, wird nichts verändert.
4. **Umschalten:** `KINGFISHER_IMAGE` in `.kingfisher.env` auf das neue Bild, dann `make start` (dort `docker compose
   up -d` ohne Bauen, mit dem freigegebenen Notizordner wie bisher).
5. **Nachsehen**, ob die neue Fassung antwortet. Wenn nicht: die Zeile von vorher zurück, `make start`, und ein Satz,
   dass die Daten gesichert sind und wie man sie mit `make zurueck-vor-update` zurückholt.

Nur die Standardbibliothek; Befehle und Anfragen sind austauschbar, damit die Tests ohne Docker auskommen.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.request import ProxyHandler, Request, build_opener

WURZEL = Path(__file__).resolve().parents[1]
ADRESSE = 'http://127.0.0.1:8890'
ENVDATEI = '.kingfisher.env'
BILD_PRAEFIX = 'ghcr.io/icarus-health/kingfisher-app:'
VORGABE_BILD = 'kingfisher:local'
SEMVER = re.compile(r'(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})')
SICHERN = ("from pathlib import Path; from icarus_memory.backup import UPDATE_SET_PREFIX, snapshot_all; "
           "print(snapshot_all(Path('/data'), Path('/data/sicherungen'), keep=3, prefix=UPDATE_SET_PREFIX).name)")

SATZ_NICHT_EINGERICHTET = 'Kingfisher ist hier noch nicht eingerichtet. Zuerst: make start'
SATZ_NICHT_ERREICHBAR = ('Kingfisher antwortet gerade nicht, also kann es weder nachsehen noch sichern. Zuerst: '
                         'make start')
SATZ_KEIN_MANIFEST = ('Kingfisher konnte gerade nicht nachsehen, ob es eine neue Fassung gibt. Versuche es später noch '
                      'einmal oder nenne die Fassung: make aktualisieren FASSUNG=1.2.0')
SATZ_AKTUELL = 'Kingfisher ist auf dem neuesten Stand (Fassung {fassung}). Es wurde nichts verändert.'
SATZ_FASSUNG_FALSCH = '„{fassung}“ ist keine Fassungsnummer. Gemeint ist etwa: make aktualisieren FASSUNG=1.2.0'
SATZ_SICHERUNG = 'Die Sicherung ist nicht gelungen. Es wurde nichts verändert.'
SATZ_LADEN = ('Die Fassung {fassung} ließ sich nicht laden ({bild}). Es wurde nichts verändert; Kingfisher läuft '
              'weiter wie bisher.')
SATZ_FERTIG = 'Kingfisher ist jetzt auf Fassung {fassung}. Die Sicherung von vorher heißt {sicherung}.'
SATZ_ZURUECK = ('Das Update hat nicht geklappt; Kingfisher läuft wieder mit der Fassung von vorher. Deine Daten sind '
                'gesichert ({sicherung}). Fehlt danach etwas, holt make zurueck-vor-update den Stand von vorher zurück.')
SATZ_ZURUECK_GESCHEITERT = ('Das Update hat nicht geklappt, und Kingfisher startet auch mit der Fassung von vorher '
                            'nicht von selbst. Deine Daten sind gesichert ({sicherung}). Starte mit make start und hole '
                            'danach mit make zurueck-vor-update den Stand von vorher zurück.')

Lauf = Callable[..., subprocess.CompletedProcess]
Anfrage = Callable[[str, str, str], Optional[dict]]


class Abbruch(Exception):
    """Etwas fehlt oder ging schief; `satz` ist für den Menschen."""

    def __init__(self, satz: str) -> None:
        super().__init__(satz)
        self.satz = satz


def ausfuehren(*befehl: str, timeout: float = 600, ausgabe: bool = False) -> subprocess.CompletedProcess:
    if ausgabe:
        return subprocess.run(befehl, timeout=timeout, check=False, cwd=WURZEL)
    return subprocess.run(befehl, timeout=timeout, check=False, capture_output=True, text=True, cwd=WURZEL)


def anfragen(methode: str, pfad: str, token: str) -> Optional[dict]:
    """Eine Anfrage an den laufenden Kingfisher (ohne Proxy, nur dieser Rechner); None, wenn er nicht antwortet."""
    anfrage = Request(ADRESSE + pfad, method=methode, headers={'x-icarus-token': token})
    try:
        with build_opener(ProxyHandler({})).open(anfrage, timeout=20) as antwort:
            return json.loads(antwort.read().decode('utf-8'))
    except (OSError, ValueError):
        return None


# -- .kingfisher.env -----------------------------------------------------------------


def env_lesen(datei: Path) -> dict[str, str]:
    werte = {}
    for zeile in datei.read_text(encoding='utf-8').splitlines():
        if '=' in zeile and not zeile.lstrip().startswith('#'):
            name, wert = zeile.split('=', 1)
            werte[name.strip()] = wert.strip()
    return werte


def env_setzen(datei: Path, name: str, wert: str | None) -> None:
    """Setzt (oder entfernt mit None) eine Zeile; alles andere bleibt, wie es ist. Nur für den Benutzer lesbar."""
    zeilen = [z for z in datei.read_text(encoding='utf-8').splitlines() if not z.startswith(f'{name}=')]
    if wert is not None:
        zeilen.append(f'{name}={wert}')
    neu = datei.with_name(f'.{datei.name}.neu')
    alt = os.umask(0o077)
    try:
        neu.write_text('\n'.join(zeilen) + '\n', encoding='utf-8')
        os.chmod(neu, 0o600)
        os.replace(neu, datei)
    finally:
        os.umask(alt)


# -- Der Weg ---------------------------------------------------------------------------


def ziel_bestimmen(fassung: str, token: str, anfrage: Anfrage) -> tuple[str, str] | None:
    """(Fassung, Bild) oder None, wenn nichts Neueres da ist. Wirft `Abbruch`."""
    if fassung:
        if not SEMVER.fullmatch(fassung):
            raise Abbruch(SATZ_FASSUNG_FALSCH.format(fassung=fassung))
        return fassung, BILD_PRAEFIX + fassung
    stand = anfrage('POST', '/api/v1/fassung/pruefen', token)
    if stand is None:
        raise Abbruch(SATZ_NICHT_ERREICHBAR)
    neueste = stand.get('neueste') or None
    if not stand.get('erreicht') and neueste is None:
        raise Abbruch(SATZ_KEIN_MANIFEST)
    if not stand.get('update_verfuegbar') or not isinstance(neueste, dict):
        return None
    ziel, bild = str(neueste.get('fassung', '')), str(neueste.get('image', ''))
    # Der Sidecar hat das Manifest schon geprüft; hier noch einmal, weil gleich ein Bild geladen wird.
    if not SEMVER.fullmatch(ziel) or bild != BILD_PRAEFIX + ziel:
        raise Abbruch(SATZ_KEIN_MANIFEST)
    return ziel, bild


def laeuft_fassung(token: str, anfrage: Anfrage, warten: Callable[[float], None], sekunden: int = 90) -> str | None:
    """Die Fassung, die nach dem Start antwortet; None, wenn nach `sekunden` nichts antwortet."""
    for _ in range(max(1, sekunden)):
        stand = anfrage('GET', '/api/v1/fassung', token)
        if stand is not None:
            return str(stand.get('fassung', ''))
        warten(1)
    return None


def aktualisieren(fassung: str = '', *, wurzel: Path = WURZEL, lauf: Lauf = ausfuehren, anfrage: Anfrage = anfragen,
                  sagen: Callable[[str], None] = print, warten: Callable[[float], None] = time.sleep) -> str | None:
    """Der ganze Weg. Gibt die neue Fassung zurück (None: schon aktuell); wirft `Abbruch` mit einem Satz."""
    env = wurzel / ENVDATEI
    if not env.is_file():
        raise Abbruch(SATZ_NICHT_EINGERICHTET)
    werte = env_lesen(env)
    token = werte.get('ICARUS_SIDECAR_TOKEN', '')
    if not token:
        raise Abbruch(SATZ_NICHT_EINGERICHTET)
    ziel = ziel_bestimmen(fassung.strip(), token, anfrage)
    if ziel is None:
        stand = anfrage('GET', '/api/v1/fassung', token) or {}
        sagen(SATZ_AKTUELL.format(fassung=stand.get('fassung', '?')))
        return None
    neue_fassung, bild = ziel
    vorher = werte.get('KINGFISHER_IMAGE') or None

    sagen(f'Kingfisher sichert deine Daten, bevor es auf Fassung {neue_fassung} wechselt …')
    compose = ('docker', 'compose', '-p', 'kingfisher', '--env-file', str(env), '-f', str(wurzel / 'compose.yaml'))
    sicherung = lauf(*compose, 'exec', '-T', 'kingfisher', 'python', '-c', SICHERN, timeout=600)
    name = (sicherung.stdout or '').strip().splitlines()[-1:] if sicherung.returncode == 0 else []
    if not name or not name[0].startswith('vor-update-'):
        raise Abbruch(SATZ_SICHERUNG)
    sicherung_name = name[0]
    sagen(f'Gesichert: {sicherung_name}. Lade Fassung {neue_fassung} …')
    if lauf('docker', 'pull', bild, timeout=1800, ausgabe=True).returncode != 0:
        raise Abbruch(SATZ_LADEN.format(fassung=neue_fassung, bild=bild))

    env_setzen(env, 'KINGFISHER_IMAGE', bild)
    lauf('make', '--no-print-directory', 'start', timeout=600, ausgabe=True)
    if laeuft_fassung(token, anfrage, warten) == neue_fassung:
        sagen(SATZ_FERTIG.format(fassung=neue_fassung, sicherung=sicherung_name))
        return neue_fassung

    env_setzen(env, 'KINGFISHER_IMAGE', vorher)
    lauf('make', '--no-print-directory', 'start', timeout=1800, ausgabe=True)
    if laeuft_fassung(token, anfrage, warten) is None:
        raise Abbruch(SATZ_ZURUECK_GESCHEITERT.format(sicherung=sicherung_name))
    raise Abbruch(SATZ_ZURUECK.format(sicherung=sicherung_name))


def main() -> int:
    try:
        aktualisieren(os.environ.get('FASSUNG', ''))
    except Abbruch as fehler:
        print()
        print(fehler.satz)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
