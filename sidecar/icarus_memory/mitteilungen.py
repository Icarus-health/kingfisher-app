"""Mitteilungen auf dem Mac: was Kingfisher von sich aus meldet (Etappe 5, `docs/24-weg-zum-jarvis.md`).

Die Mac-App fragt alle fünf Minuten `GET /api/v1/mitteilungen/faellig` (`mitteilungen_routes.py`) und zeigt, was
kommt, als Systemmitteilung. Hier steht, **was** fällig ist; die App weiß nichts über Termine oder Akten.

Drei Arten, je Abruf höchstens eine je Art und höchstens drei zusammen, Dringendes zuerst:

* `termin`: ein Termin, der in 30 bis 60 Minuten beginnt, mit Ort und, wenn die Wegezeit schon berechnet ist,
  „Losfahren um …“. Nur gelesen: Für eine Mitteilung wird kein Kartendienst gefragt (`wegezeit.auskunft(nur_lesen=True)`).
* `zusage`: eine eigene Zusage (`fristlage.Frist`, `richtung == 'von_mir'`), deren Tag gestern war und die noch nicht
  als erledigt gilt. Pfad zur Akte.
* `morgen`: einmal am Tag ab der eingestellten Uhrzeit (Vorgabe 7:30) die Einleitung der Tageslage und ihre erste Zeile.

**Nichts doppelt, auch nicht nach einem Neustart.** Jede Mitteilung hat eine Kennung aus ihrem Gegenstand (Tag, Termin,
Zusage); die Merkliste (`mitteilungen.sqlite3` im Datenverzeichnis, nur Kennungen und Zeiten, kein Inhalt) hält fest,
was schon einmal herausgegeben wurde. **Ruhezeit** zwischen 21:00 Uhr und der Morgenzeit: nur ein Termin gleich.
**Vorgabe aus**, weil es eine Systemerlaubnis braucht. **Nichts verlässt den Rechner**: Die App spricht nur mit dem
Sidecar an 127.0.0.1. **Nichts Inhaltliches ins Protokoll**: Fehler werden mit ihrer Art vermerkt, nie mit Text; das
Logbuch bekommt nur die Art der Mitteilung (`mitteilung`, `mitteilung_ueberfluessig`, Nutzdaten `sorte`), aus der die Wochenzahl für
„Fertig heißt“ entsteht: keine Mitteilung, die der Nutzer im Nachhinein für überflüssig hält.

Kein Modell: Alles hier ist gelesen, nichts erzeugt.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, time as uhrzeit_t, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from . import logbuch
from .fristlage import Frist, beschreibung

logger = logging.getLogger(__name__)

VORGABE_MORGENS = '07:30'
#: Ab hier bis zur Morgenzeit kommt nur noch ein Termin gleich.
RUHE_AB = uhrzeit_t(21, 0)
MAX_JE_ABRUF = 3
MAX_TITEL = 60
MAX_SATZ = 140
MAX_ID = 64
MAX_PFAD = 200
#: Ein Termin gilt als „gleich“, wenn er in diesem Fenster beginnt (Minuten).
TERMIN_AB_MIN, TERMIN_BIS_MIN = 30, 60
ARTEN = ('termin', 'zusage', 'morgen')
ERLAUBNIS = ('unbekannt', 'erlaubt', 'abgelehnt')
_UHRZEIT = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


def uhrzeit_gueltig(text: Any) -> bool:
    """`HH:MM` mit zwei Ziffern je Teil, vor der Ruhezeit (sonst gäbe es keinen Morgen)."""
    if not isinstance(text, str):
        return False
    treffer = _UHRZEIT.match(text)
    return bool(treffer) and uhrzeit_t(int(treffer.group(1)), int(treffer.group(2))) < RUHE_AB


def _uhrzeit(text: str) -> uhrzeit_t:
    stunde, minute = text.split(':')
    return uhrzeit_t(int(stunde), int(minute))


@dataclass(frozen=True)
class Einstellung:
    an: bool = False
    """Vorgabe aus: Mitteilungen brauchen eine Erlaubnis des Systems, die der Mensch gibt."""
    morgens: str = VORGABE_MORGENS

    @classmethod
    def aus(cls, roh: Any) -> 'Einstellung':
        if not isinstance(roh, dict):
            return cls()
        morgens = roh.get('morgens')
        return cls(an=roh.get('an') is True, morgens=morgens if uhrzeit_gueltig(morgens) else VORGABE_MORGENS)

    def to_dict(self) -> dict[str, Any]:
        return {'an': self.an, 'morgens': self.morgens}


def _kurz(text: Any, laenge: int) -> str:
    text = ' '.join(str(text or '').split())
    if len(text) <= laenge:
        return text
    gekuerzt = text[:laenge - 2].rsplit(' ', 1)[0].rstrip(',;:.') if ' ' in text[:laenge - 2] else text[:laenge - 2]
    return gekuerzt + ' …'


def _uhr(zeit: datetime) -> str:
    return f'{zeit.hour}:{zeit.minute:02d} Uhr'


def _kennung(art: str, *teile: Any) -> str:
    """Eine Kennung aus dem Gegenstand, nicht aus dem Inhalt lesbar; gleich bei jedem Abruf."""
    digest = hashlib.sha256('\0'.join(str(t) for t in teile).encode('utf-8')).hexdigest()[:20]
    return f'{art}:{digest}'


@dataclass(frozen=True)
class Mitteilung:
    id: str
    art: str
    titel: str
    satz: str
    pfad: str
    """Die Seite in der App, die „Öffnen“ zeigt (`/today`, `/calendar`, `/memory/akte/…`)."""

    def to_dict(self) -> dict[str, Any]:
        return {'id': self.id[:MAX_ID], 'art': self.art, 'titel': _kurz(self.titel, MAX_TITEL),
                'satz': _kurz(self.satz, MAX_SATZ), 'pfad': self.pfad[:MAX_PFAD]}


# -- Die Merkliste ---------------------------------------------------------------------------------


class Merkliste:
    """Was schon herausgegeben wurde, in einer kleinen Datei: Kennung, Art, Tag, Zeiten. Kein Inhalt.

    Die Datei entsteht beim ersten Schreiben, nicht beim Start. Sie gehört nicht zur Sicherung: Nach einer
    Wiederherstellung käme höchstens eine heutige Mitteilung ein zweites Mal.
    """

    def __init__(self, pfad: Path) -> None:
        self._pfad = Path(pfad)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    def _verbindung(self) -> sqlite3.Connection:
        if self._conn is None:
            self._pfad.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._pfad), check_same_thread=False)
            conn.execute('PRAGMA secure_delete=ON')
            conn.execute("""CREATE TABLE IF NOT EXISTS gesendet (
                id TEXT PRIMARY KEY, art TEXT NOT NULL, tag TEXT NOT NULL, zeit REAL NOT NULL,
                zugestellt INTEGER NOT NULL DEFAULT 0, ueberfluessig INTEGER NOT NULL DEFAULT 0)""")
            conn.execute('CREATE TABLE IF NOT EXISTS marke (name TEXT PRIMARY KEY, wert TEXT NOT NULL)')
            conn.commit()
            try:
                self._pfad.chmod(0o600)
            except OSError:
                pass
            self._conn = conn
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def bekannt(self, kennung: str) -> bool:
        with self._lock:
            return self._verbindung().execute('SELECT 1 FROM gesendet WHERE id = ?', (kennung,)).fetchone() is not None

    def vormerken(self, kennung: str, art: str, tag: str, zeit: float) -> bool:
        """Trägt die Kennung ein; `False`, wenn sie schon da war (dann kommt die Mitteilung nicht noch einmal)."""
        with self._lock:
            conn = self._verbindung()
            cursor = conn.execute('INSERT OR IGNORE INTO gesendet(id, art, tag, zeit) VALUES (?,?,?,?)', (kennung, art, tag, zeit))
            conn.commit()
            return cursor.rowcount == 1

    def art(self, kennung: str) -> str | None:
        with self._lock:
            zeile = self._verbindung().execute('SELECT art FROM gesendet WHERE id = ?', (kennung,)).fetchone()
            return None if zeile is None else str(zeile[0])

    def setzen(self, kennung: str, feld: str, wert: bool) -> bool | None:
        """Setzt `zugestellt` oder `ueberfluessig`; gibt den vorigen Wert zurück, `None` bei unbekannter Kennung."""
        assert feld in ('zugestellt', 'ueberfluessig')
        with self._lock:
            conn = self._verbindung()
            zeile = conn.execute(f'SELECT {feld} FROM gesendet WHERE id = ?', (kennung,)).fetchone()
            if zeile is None:
                return None
            conn.execute(f'UPDATE gesendet SET {feld} = ? WHERE id = ?', (1 if wert else 0, kennung))
            conn.commit()
            return bool(zeile[0])

    def marke(self, name: str) -> str | None:
        with self._lock:
            zeile = self._verbindung().execute('SELECT wert FROM marke WHERE name = ?', (name,)).fetchone()
            return None if zeile is None else str(zeile[0])

    def marke_setzen(self, name: str, wert: str) -> None:
        with self._lock:
            conn = self._verbindung()
            conn.execute('INSERT INTO marke(name, wert) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET wert = excluded.wert', (name, wert))
            conn.commit()


# -- Der Dienst ------------------------------------------------------------------------------------


class Dienst:
    """Entscheidet je Abruf, was fällig ist. Die Quellen sind eingesetzt (Briefing, Termine, Fristen, Wegezeit); jede
    darf scheitern und kostet dann nur ihren Teil. `uhr` ist die Zeit des Nutzers (mit Zeitzone)."""

    def __init__(self, pfad: Path, *, einstellung: Callable[[], Einstellung], briefing: Callable[[], dict[str, Any] | None],
                 termine: Callable[[datetime], list[dict[str, Any]]], fristen: Callable[[datetime], list[Frist]],
                 wegezeit: Callable[[str, datetime], dict[str, Any] | None], uhr: Callable[[], datetime]) -> None:
        self._merkliste = Merkliste(pfad)
        self._einstellung = einstellung
        self._briefing, self._termine, self._fristen, self._wegezeit = briefing, termine, fristen, wegezeit
        self.uhr = uhr

    def close(self) -> None:
        self._merkliste.close()

    # -- Fällig --

    def faellig(self) -> list[dict[str, Any]]:
        """Höchstens drei, je Art eine, Dringendes zuerst; jede nur einmal, gleich wie oft gefragt wird."""
        einstellung = self._einstellung()
        if not einstellung.an:
            return []
        jetzt = self.uhr()
        tag = jetzt.date().isoformat()
        kandidaten: list[Mitteilung] = []
        for finder in (self._termin_gleich, None if self._ruhe(jetzt, einstellung) else self._zusage,
                       None if self._ruhe(jetzt, einstellung) else lambda j: self._morgen(j, einstellung)):
            if finder is None:
                continue
            treffer = finder(jetzt)
            if treffer is not None:
                kandidaten.append(treffer)
        ergebnis = []
        for m in kandidaten[:MAX_JE_ABRUF]:
            if self._merkliste.vormerken(m.id, m.art, tag, jetzt.timestamp()):
                ergebnis.append(m.to_dict())
        return ergebnis

    @staticmethod
    def _ruhe(jetzt: datetime, einstellung: Einstellung) -> bool:
        zeit = jetzt.time().replace(tzinfo=None)
        return zeit >= RUHE_AB or zeit < _uhrzeit(einstellung.morgens)

    def _quelle(self, name: str, lesen: Callable[..., Any], *args: Any) -> Any:
        try:
            return lesen(*args)
        except Exception as exc:  # noqa: BLE001 - eine Quelle darf die anderen nicht kosten; nie der Text, er könnte Inhalt tragen
            logger.warning('Mitteilungen: Quelle %s nicht lesbar (%s)', name, type(exc).__name__)
            return None

    def _termin_gleich(self, jetzt: datetime) -> Mitteilung | None:
        liste = self._quelle('termine', self._termine, jetzt) or []
        passend: list[tuple[datetime, dict[str, Any]]] = []
        for eintrag in liste:
            if not isinstance(eintrag, dict) or eintrag.get('all_day'):
                continue
            try:
                beginn = datetime.fromisoformat(str(eintrag.get('start'))).astimezone(jetzt.tzinfo)
            except (TypeError, ValueError):
                continue
            minuten = (beginn - jetzt).total_seconds() / 60
            if TERMIN_AB_MIN <= minuten <= TERMIN_BIS_MIN:
                passend.append((beginn, eintrag))
        for beginn, eintrag in sorted(passend, key=lambda p: p[0]):
            kennung = _kennung('termin', eintrag.get('uid') or '', beginn.isoformat())
            if self._merkliste.bekannt(kennung):
                continue
            ort = ' '.join(str(eintrag.get('location') or '').split())
            satz = f'Um {_uhr(beginn)}' + (f', {ort}' if ort else '') + '.'
            if ort:
                auskunft = self._quelle('wegezeit', self._wegezeit, ort, beginn)
                los = self._losfahren(auskunft, jetzt)
                if los is not None:
                    satz += f' Losfahren um {_uhr(los)}.'
            return Mitteilung(id=kennung, art='termin', titel='Gleich: ' + str(eintrag.get('summary') or 'Termin'),
                              satz=satz, pfad='/calendar')
        return None

    @staticmethod
    def _losfahren(auskunft: Any, jetzt: datetime) -> datetime | None:
        if not isinstance(auskunft, dict) or auskunft.get('status') != 'berechnet' or not auskunft.get('losfahren'):
            return None
        try:
            return datetime.fromisoformat(str(auskunft['losfahren'])).astimezone(jetzt.tzinfo)
        except (TypeError, ValueError):
            return None

    def _zusage(self, jetzt: datetime) -> Mitteilung | None:
        fristen = self._quelle('fristen', self._fristen, jetzt) or []
        for f in fristen:
            if not isinstance(f, Frist) or f.richtung != 'von_mir' or f.art != 'Zusage' or f.status != 'verstrichen' or f.tage != -1:
                continue
            kennung = _kennung('zusage', f.episode_id, f.datum.isoformat(), f.text)
            if self._merkliste.bekannt(kennung):
                continue
            satz = beschreibung(f)
            if f.text:
                satz = f'{satz.rstrip(".")}: {f.text}'
            pfad = f'/memory/akte/{quote(f.sache, safe="")}' if f.sache else '/today'
            return Mitteilung(id=kennung, art='zusage', titel='Deine Zusage ist verstrichen', satz=satz, pfad=pfad)
        return None

    def _morgen(self, jetzt: datetime, einstellung: Einstellung) -> Mitteilung | None:
        if jetzt.time().replace(tzinfo=None) < _uhrzeit(einstellung.morgens):
            return None
        kennung = f'morgen:{jetzt.date().isoformat()}'
        if self._merkliste.bekannt(kennung):
            return None
        briefing = self._quelle('briefing', self._briefing)
        if not isinstance(briefing, dict):
            return None
        lage = briefing.get('tageslage') if isinstance(briefing.get('tageslage'), dict) else {}
        einleitung = ' '.join(str(lage.get('einleitung') or '').split())
        zeilen = [z for z in (lage.get('zeilen') or []) if isinstance(z, dict) and z.get('text')]
        if zeilen:
            return Mitteilung(id=kennung, art='morgen', titel=einleitung or 'Guten Morgen', satz=str(zeilen[0]['text']), pfad='/today')
        return Mitteilung(id=kennung, art='morgen', titel='Guten Morgen', satz=einleitung or 'Heute liegt nichts an.', pfad='/today')

    # -- Rückweg --

    def zugestellt(self, kennung: str) -> bool:
        """Die App hat die Mitteilung gezeigt. Einmal je Kennung ins Logbuch; `False` bei unbekannter Kennung."""
        vorher = self._merkliste.setzen(kennung, 'zugestellt', True)
        if vorher is None:
            logger.info('Mitteilungen: unbekannte Kennung als zugestellt gemeldet')
            return False
        if not vorher:
            logbuch.vermerke('mitteilung', sorte=self._merkliste.art(kennung) or '')
        return True

    def rueckmeldung(self, kennung: str, *, ueberfluessig: bool) -> bool:
        """„War überflüssig“ (oder zurückgenommen). Zählt je Kennung höchstens einmal."""
        vorher = self._merkliste.setzen(kennung, 'ueberfluessig', ueberfluessig)
        if vorher is None:
            logger.info('Mitteilungen: Rückmeldung zu unbekannter Kennung')
            return False
        if ueberfluessig and not vorher:
            logbuch.vermerke('mitteilung_ueberfluessig', sorte=self._merkliste.art(kennung) or '')
        return True

    def woche(self) -> dict[str, int]:
        """Gesendet und als überflüssig gemeldet in den letzten sieben Tagen (aus dem Logbuch; ohne eines null)."""
        buch = logbuch.aktiv()
        zahlen = {'gesendet': 0, 'ueberfluessig': 0}
        if buch is None:
            return zahlen
        try:
            for e in buch.ereignisse(self.uhr() - timedelta(days=7)):
                if e.art == 'mitteilung':
                    zahlen['gesendet'] += 1
                elif e.art == 'mitteilung_ueberfluessig':
                    zahlen['ueberfluessig'] += 1
        except Exception as exc:  # noqa: BLE001 - die Zahl ist Beiwerk
            logger.warning('Mitteilungen: Wochenzahl nicht lesbar (%s)', type(exc).__name__)
        return zahlen

    # -- Erlaubnis des Systems --

    def erlaubnis(self) -> str:
        wert = self._merkliste.marke('erlaubnis')
        return wert if wert in ERLAUBNIS else 'unbekannt'

    def erlaubnis_setzen(self, status: str) -> str:
        if status not in ERLAUBNIS:
            raise ValueError('Unbekannter Erlaubnisstand.')
        self._merkliste.marke_setzen('erlaubnis', status)
        return status


__all__ = ['ARTEN', 'ERLAUBNIS', 'MAX_ID', 'MAX_JE_ABRUF', 'MAX_PFAD', 'MAX_SATZ', 'MAX_TITEL', 'RUHE_AB', 'TERMIN_AB_MIN',
           'TERMIN_BIS_MIN', 'VORGABE_MORGENS', 'Dienst', 'Einstellung', 'Merkliste', 'Mitteilung', 'uhrzeit_gueltig']
