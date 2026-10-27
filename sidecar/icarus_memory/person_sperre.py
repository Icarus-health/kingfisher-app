"""Sperrvermerk: eine gelöschte Person nicht wieder anlegen (Persona-Prüfung, Paket P, D7, 27.10.2026).

Wer „Alles zu Dora Lind löschen“ wählt, will nicht, dass das nächste Einlesen sie sofort wieder anlegt: Ihre Mails
liegen weiter im Postfach, ihre Termine im Kalender. Deshalb merkt sich Kingfisher beim Löschen, wen es nicht wieder
aufnehmen soll, und zwar ohne die Daten selbst:

* je Adresse und je Namensschreibweise nur eine Prüfsumme (`sha256` über ein festes Präfix und den Schlüssel; die
  Adresse kleingeschrieben, der Name in der Form von `identitaet.name_schluessel`),
* dazu der Anzeigename, damit du unter Einstellungen erkennst, wen du wieder zulassen würdest.

Die Sperre wirkt an einer Stelle für alle Wege hinein (`EpisodeStore.record` und `add_contacts`):

* Beteiligte, die gesperrt sind, fallen aus `participants` und `contacts` heraus, bevor die Quelle gespeichert wird.
  Eine Mail, die auch andere betrifft, kommt also ohne Bezug zu ihr herein.
* Betrifft eine Quelle außer dir nur gesperrte Menschen, wird sie gar nicht aufgenommen (`GesperrteQuelle`); die
  Mailaufnahme zählt sie als „ausgelassen“ (`filtered:gesperrt`), statt sie als Fehler zu wiederholen.
* Eine Adresse sperrt nur diese Adresse. Ein Name sperrt nur Nennungen **ohne** Adresse (Notiz, Mitschrift): Ein
  Namensvetter mit eigener Adresse bleibt eine eigene Person (wie in `identitaet.py`).
* Erwähnungen im Text einer geteilten Quelle werden keine Akte (`bezuege.Register.gesperrt`).

Aufheben unter Einstellungen → Kingfisher und du; danach kommt sie beim nächsten Einlesen wieder herein, wie jede neue
Person. Die Tabelle liegt in `episodes.sqlite3` (Migration 26): So gilt die Sperre für jede Ablage der Quellen, ohne
dass sie jemand anschließen muss, und sie geht mit in die Sicherung.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Callable, Iterable

TABLES = {'personen_sperre': {'kennung', 'anzeige', 'schluessel', 'angelegt'}}
PRIMARY_KEYS = {'personen_sperre': {'kennung'}}
_PRAEFIX = 'kingfisher-sperre-v1:'


class GesperrteQuelle(Exception):
    """Die Quelle betrifft außer dir nur Menschen, die du gelöscht hast: Sie wird nicht aufgenommen."""


def migrate(connection: sqlite3.Connection) -> None:
    """Migration 26 der Episoden: Sperrvermerke ohne die Daten selbst (nur Prüfsummen und ein Anzeigename)."""
    connection.execute("""CREATE TABLE personen_sperre (
        kennung TEXT PRIMARY KEY,
        anzeige TEXT NOT NULL,
        schluessel TEXT NOT NULL DEFAULT '[]',
        angelegt REAL NOT NULL)""")


def _pruefsumme(art: str, wert: str) -> str:
    return hashlib.sha256((_PRAEFIX + art + ':' + wert).encode('utf-8')).hexdigest()


def adress_schluessel(adresse: str) -> str:
    return _pruefsumme('a', str(adresse or '').strip().casefold())


def namens_schluessel(name: str) -> str:
    from .identitaet import name_schluessel
    return _pruefsumme('n', name_schluessel(name))


class Sperre:
    """Die Sperrvermerke einer Quellenablage. Liest selten (eine kleine Tabelle), merkt sie sich bis zur Änderung."""

    def __init__(self, episodes: Any) -> None:
        self.episodes = episodes
        self._gemerkt: tuple[Any, frozenset[str]] | None = None
        self._sperre = threading.Lock()

    # -- Lesen ----------------------------------------------------------------------------------------------

    def _stand(self) -> Any:
        from .zwischenspeicher import marke_von
        return marke_von(self.episodes)

    def schluessel(self) -> frozenset[str]:
        """Alle gesperrten Prüfsummen; leer, wenn niemand gesperrt ist (der häufige Fall kostet eine Abfrage)."""
        stand = self._stand()
        with self._sperre:
            if self._gemerkt is not None and stand is not None and self._gemerkt[0] == stand:
                return self._gemerkt[1]
        with self.episodes._lock:
            zeilen = self.episodes._conn.execute('SELECT schluessel FROM personen_sperre').fetchall()
        alle: set[str] = set()
        for (roh,) in zeilen:
            try:
                alle.update(str(s) for s in json.loads(roh or '[]'))
            except ValueError:
                continue
        ergebnis = frozenset(alle)
        with self._sperre:
            self._gemerkt = (stand, ergebnis)
        return ergebnis

    def liste(self) -> list[dict[str, Any]]:
        with self.episodes._lock:
            zeilen = self.episodes._conn.execute(
                'SELECT kennung, anzeige, angelegt FROM personen_sperre ORDER BY angelegt DESC').fetchall()
        return [{'kennung': k, 'anzeige': a, 'angelegt': t} for k, a, t in zeilen]

    def adresse_gesperrt(self, adresse: str, alle: frozenset[str] | None = None) -> bool:
        alle = self.schluessel() if alle is None else alle
        return bool(adresse) and adress_schluessel(adresse) in alle

    def name_gesperrt(self, name: str, alle: frozenset[str] | None = None) -> bool:
        alle = self.schluessel() if alle is None else alle
        return bool(str(name or '').strip()) and namens_schluessel(name) in alle

    def nennung_gesperrt(self, adresse: str, name: str, alle: frozenset[str] | None = None) -> bool:
        """Mit Adresse zählt nur die Adresse; ohne Adresse der Name."""
        alle = self.schluessel() if alle is None else alle
        if not alle:
            return False
        if adresse:
            return self.adresse_gesperrt(adresse, alle)
        return self.name_gesperrt(name, alle)

    # -- Filtern ------------------------------------------------------------------------------------------

    def filtern(self, participants: Iterable[str] | None, contacts: Iterable[dict[str, Any]] | None,
                eigene: Iterable[str] = ()) -> tuple[list[str], list[dict[str, Any]], bool]:
        """(Beteiligte ohne Gesperrte, Kontakte ohne Gesperrte, ob jemand gesperrt war).

        Wirft `GesperrteQuelle`, wenn jemand gesperrt war und außer dir niemand bleibt.
        """
        from .episodes import mail_address
        teilnehmer = [str(t) for t in (participants or [])]
        kontakte = [dict(c) for c in (contacts or [])]
        alle = self.schluessel()
        if not alle:
            return teilnehmer, kontakte, False

        def gesperrt_text(text: str) -> bool:
            adresse = mail_address(text)
            return self.nennung_gesperrt(adresse, '' if adresse else text, alle)

        def gesperrt_kontakt(eintrag: dict[str, Any]) -> bool:
            if eintrag.get('ich'):
                return False
            adresse = str(eintrag.get('adresse') or '').casefold()
            return self.nennung_gesperrt(adresse, '' if adresse else str(eintrag.get('name') or ''), alle)

        neue_teilnehmer = [t for t in teilnehmer if not gesperrt_text(t)]
        neue_kontakte = [c for c in kontakte if not gesperrt_kontakt(c)]
        entfernt = len(neue_teilnehmer) != len(teilnehmer) or len(neue_kontakte) != len(kontakte)
        if entfernt:
            selbst = {mail_address(a) for a in eigene if mail_address(a)}
            selbst |= {str(c.get('adresse') or '').casefold() for c in kontakte if c.get('ich') and c.get('adresse')}
            andere = [c for c in neue_kontakte if not c.get('ich')
                      and str(c.get('adresse') or '').casefold() not in selbst]
            andere_texte = [t for t in neue_teilnehmer if not (mail_address(t) and mail_address(t) in selbst)]
            if not andere and not andere_texte:
                raise GesperrteQuelle('Diese Quelle betrifft nur eine Person, die du gelöscht hast.')
        return neue_teilnehmer, neue_kontakte, entfernt

    # -- Schreiben -----------------------------------------------------------------------------------------

    def eintragen(self, anzeige: str, adressen: Iterable[str], namen: Iterable[str]) -> str:
        """Legt einen Sperrvermerk an; die Kennung, mit der er sich aufheben lässt."""
        schluessel = sorted({adress_schluessel(a) for a in adressen if str(a or '').strip()}
                            | {namens_schluessel(n) for n in namen if str(n or '').strip()})
        kennung = 's-' + uuid.uuid4().hex[:16]
        with self.episodes.transaction():
            self.episodes._conn.execute(
                'INSERT INTO personen_sperre (kennung, anzeige, schluessel, angelegt) VALUES (?, ?, ?, ?)',
                (kennung, str(anzeige or 'Gelöschte Person')[:120], json.dumps(schluessel), time.time()))
        with self._sperre:
            self._gemerkt = None
        return kennung

    def aufheben(self, kennung: str) -> dict[str, Any] | None:
        """Hebt einen Sperrvermerk auf; der aufgehobene Eintrag (für die Antwort) oder None."""
        with self.episodes.transaction():
            zeile = self.episodes._conn.execute(
                'SELECT kennung, anzeige, angelegt FROM personen_sperre WHERE kennung = ?', (kennung,)).fetchone()
            if zeile is None:
                return None
            self.episodes._conn.execute('DELETE FROM personen_sperre WHERE kennung = ?', (kennung,))
        with self._sperre:
            self._gemerkt = None
        return {'kennung': zeile[0], 'anzeige': zeile[1], 'angelegt': zeile[2]}


def fuer(episodes: Any) -> Sperre:
    """Die Sperre einer Quellenablage (eine je Ablage, an ihr gemerkt)."""
    sperre = getattr(episodes, '_personen_sperre', None)
    if sperre is None:
        sperre = Sperre(episodes)
        try:
            episodes._personen_sperre = sperre
        except AttributeError:
            pass
    return sperre


EigeneAdressen = Callable[[], Iterable[str]]

__all__ = ['GesperrteQuelle', 'PRIMARY_KEYS', 'Sperre', 'TABLES', 'adress_schluessel', 'fuer', 'migrate',
           'namens_schluessel']
