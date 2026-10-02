"""Die eine DNS-Abfrage des Sidecars (MX, CNAME, TXT, SRV) über den Namensdienst des Rechners, ohne Zusatzpaket.

Wozu: Wo die Post einer Domain liegt (Google Workspace, Microsoft 365, ein eigener Server), steht öffentlich in ihrem
DNS-Eintrag (`anbieter_erkennen.erkennen`). Das ist dieselbe Art Anfrage, die jedes Mailprogramm beim Verbinden ohnehin
stellt; sie geht an den Namensdienst, den der Rechner eingestellt hat (`/etc/resolv.conf`), nie an Google oder
Microsoft. Gefragt wird nur nach der Domain (`uni-beispiel.de`), nie nach der ganzen Adresse.

Bewusst klein: eine UDP-Anfrage je Name und Typ, zwei Sekunden Zeitgrenze, höchstens zwei Namensdienste. Kommt keine
Antwort, ist das Ergebnis leer; das Programm fragt dann den Menschen nicht, sondern bietet die Wege an, die immer gehen.
Antworten gelten zehn Minuten (`MERKEN`); Schweigen wird nicht gemerkt, damit der nächste Versuch wieder fragt.

`KINGFISHER_DNS=host:port` ersetzt den Namensdienst des Rechners (Tests und Browserproben: `tests/dns_attrappe.py`).
"""
from __future__ import annotations

import os
import random
import socket
import struct
import threading
import time
from pathlib import Path

TYPEN = {'CNAME': 5, 'MX': 15, 'TXT': 16, 'SRV': 33}
ZEITGRENZE = 2.0
#: So lange gilt eine Antwort (Sekunden).
MERKEN = 600.0
#: So viele Namensdienste aus `resolv.conf` werden höchstens gefragt.
HOECHSTENS = 2
UMGEBUNG = 'KINGFISHER_DNS'

_gemerkt: dict[tuple[str, str], tuple[float, list[str]]] = {}
_sperre = threading.Lock()


def _dienst(text: str) -> tuple[str, int]:
    """`host`, `host:port` oder `[v6]:port` als (Host, Port)."""
    text = text.strip()
    if text.startswith('['):
        host, _, port = text[1:].partition(']')
        port = port.lstrip(':')
        return host, int(port) if port.isdigit() else 53
    host, trenner, port = text.rpartition(':')
    if trenner and port.isdigit() and ':' not in host:
        return host, int(port)
    return text, 53


def namensdienste(datei: Path = Path('/etc/resolv.conf')) -> list[tuple[str, int]]:
    """Die Namensdienste, in Reihenfolge: `KINGFISHER_DNS` oder die des Rechners; leer, wenn keine bekannt sind."""
    eigen = os.environ.get(UMGEBUNG, '').strip()
    if eigen:
        return [_dienst(eigen)]
    try:
        zeilen = datei.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    dienste = []
    for zeile in zeilen:
        teile = zeile.split()
        if len(teile) >= 2 and teile[0] == 'nameserver':
            dienste.append((teile[1].split('%')[0], 53))
    return dienste[:HOECHSTENS]


def _frage(kennung: int, name: str, typ: int) -> bytes:
    kopf = struct.pack('>HHHHHH', kennung, 0x0100, 1, 0, 0, 0)
    teile = b''.join(bytes([len(t)]) + t for t in (s.encode('idna') for s in name.strip('.').split('.')) if t)
    return kopf + teile + b'\0' + struct.pack('>HH', typ, 1)


def _name(daten: bytes, stelle: int, tiefe: int = 0) -> tuple[str, int]:
    """Liest einen (auch komprimierten) Namen; gibt ihn und die Stelle dahinter zurück."""
    if tiefe > 16:
        raise ValueError('DNS-Antwort mit Schleife')
    teile, weiter = [], None
    while True:
        laenge = daten[stelle]
        if laenge & 0xC0 == 0xC0:
            ziel = struct.unpack('>H', daten[stelle:stelle + 2])[0] & 0x3FFF
            rest, _ = _name(daten, ziel, tiefe + 1)
            if rest:
                teile.append(rest)
            return '.'.join(teile), (weiter if weiter is not None else stelle + 2)
        stelle += 1
        if laenge == 0:
            return '.'.join(teile), stelle
        teile.append(daten[stelle:stelle + laenge].decode('ascii', errors='replace'))
        stelle += laenge


def antwort_lesen(daten: bytes, kennung: int, typ: int) -> list[str]:
    """Die Antworten eines Typs aus einem DNS-Paket: Namen bei MX/CNAME, Text bei TXT. Fremde Pakete zählen nicht.

    SRV (RFC 2782) kommt als eine Zeile `"Vorrang Gewicht Port Ziel"`, etwa `"0 1 993 imap.beispiel.de"`.
    """
    if len(daten) < 12:
        return []
    ident, flaggen, fragen, antworten = struct.unpack('>HHHH', daten[:8])
    if ident != kennung or not flaggen & 0x8000 or flaggen & 0x000F:
        return []
    stelle = 12
    for _ in range(fragen):
        _, stelle = _name(daten, stelle)
        stelle += 4
    werte = []
    for _ in range(antworten):
        _, stelle = _name(daten, stelle)
        art, _, _, laenge = struct.unpack('>HHIH', daten[stelle:stelle + 10])
        stelle += 10
        inhalt = stelle
        stelle += laenge
        if art != typ:
            continue
        if typ == TYPEN['MX']:
            werte.append(_name(daten, inhalt + 2)[0].lower().rstrip('.'))
        elif typ == TYPEN['SRV']:
            vorrang, gewicht, port = struct.unpack('>HHH', daten[inhalt:inhalt + 6])
            ziel = _name(daten, inhalt + 6)[0].lower().rstrip('.')
            werte.append(f'{vorrang} {gewicht} {port} {ziel or "."}')
        elif typ == TYPEN['CNAME']:
            werte.append(_name(daten, inhalt)[0].lower().rstrip('.'))
        else:
            text, pos = [], inhalt
            while pos < stelle:
                n = daten[pos]
                text.append(daten[pos + 1:pos + 1 + n].decode('utf-8', errors='replace'))
                pos += 1 + n
            werte.append(''.join(text))
    return werte


def _fragen(dienst: tuple[str, int], name: str, typ: int, zeitgrenze: float) -> list[str] | None:
    """Eine Anfrage an einen Namensdienst; `None`, wenn er nicht (rechtzeitig, passend) antwortet."""
    kennung = random.randint(1, 0xFFFF)
    familie = socket.AF_INET6 if ':' in dienst[0] else socket.AF_INET
    with socket.socket(familie, socket.SOCK_DGRAM) as verbindung:
        verbindung.settimeout(zeitgrenze)
        verbindung.sendto(_frage(kennung, name, typ), dienst)
        frist = time.monotonic() + zeitgrenze
        while True:
            verbindung.settimeout(max(0.01, frist - time.monotonic()))
            daten, _ = verbindung.recvfrom(4096)
            # Ein verirrtes Paket mit fremder Kennung zählt nicht; gewartet wird bis zur Frist.
            if len(daten) >= 2 and struct.unpack('>H', daten[:2])[0] == kennung:
                return antwort_lesen(daten, kennung, typ)
            if time.monotonic() >= frist:
                return None


def abfragen(name: str, art: str, *, dienste: list[str] | None = None, zeitgrenze: float = ZEITGRENZE) -> list[str]:
    """Fragt den Namensdienst des Rechners nach `art` (MX, CNAME, TXT, SRV) für `name`. Leer bei Schweigen oder Fehler.

    `dienste` (für Tests: `['192.0.2.1']`, `['127.0.0.1:5353']`) ersetzt den Namensdienst; dann wird nichts gemerkt.
    """
    typ = TYPEN[art]
    name = name.strip().lower().rstrip('.')
    if not name:
        return []
    schluessel = (name, art)
    if dienste is None:
        with _sperre:
            gemerkt = _gemerkt.get(schluessel)
        if gemerkt and time.monotonic() - gemerkt[0] < MERKEN:
            return list(gemerkt[1])
    for dienst in (namensdienste() if dienste is None else [_dienst(d) for d in dienste]):
        try:
            werte = _fragen(dienst, name, typ, zeitgrenze)
        except (OSError, ValueError, IndexError, struct.error, UnicodeError):
            continue
        if werte is None:
            continue
        if dienste is None:
            with _sperre:
                _gemerkt[schluessel] = (time.monotonic(), werte)
        return list(werte)
    return []


def vergessen() -> None:
    """Gemerkte Antworten verwerfen (Tests, Browserproben)."""
    with _sperre:
        _gemerkt.clear()


__all__ = ['MERKEN', 'TYPEN', 'UMGEBUNG', 'ZEITGRENZE', 'abfragen', 'antwort_lesen', 'namensdienste', 'vergessen']
