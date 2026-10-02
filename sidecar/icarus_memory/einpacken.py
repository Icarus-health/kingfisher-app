"""Was einpacken? Nur, was irgendwo steht.

Zu einem Termin gehört oft etwas, das mitmuss: ein Handout, ein Laptop, eine
Kalkulation, Ausweis und Vertrag. Der Bestand nennt es manchmal, in der Notiz
zum Termin, in einer eigenen Notiz, in einer Mail („Bitte bringen Sie … mit“,
„Ich bringe … mit“). **Nur das wird gezeigt**, wörtlich, mit Quelle. Was nirgends
steht, erfindet dieses Modul nicht, und ohne Beleg gibt es keinen Abschnitt.

Wer bringt wen mit? Der Satz gilt für den Nutzer, wenn

* er selbst ihn geschrieben hat (eigene Notiz, Notiz zum Termin, eigene Mail): jede
  Formulierung mit „mitbringen“, „mitnehmen“, „einpacken“ oder „bringe … mit“; oder
* jemand anderes ihn schrieb und den Nutzer anspricht („Bitte bringen Sie … mit“,
  „Denken Sie an …“, „Bitte … mitbringen“).

Der Satz einer anderen Person „Ich bringe folgende Zahlen mit“ ist deren Sache und
steht nicht in der Packliste des Nutzers.

Bewusst ohne Modell: reine Mustersuche auf Sätzen, jede Zeile ein Zitat.
Anhänge stehen (noch) nicht im Bestand; was eine Mail „anbei“ schickt, ist deshalb
keine Packliste.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

_SATZENDE = re.compile(r'(?<=[a-zäöüß)\]])[.!?]\s+', re.I)
_KUERZEL = frozenset({'dr', 'prof', 'hr', 'fr', 'ca', 'nr', 'st', 'bzw', 'evtl', 'ggf', 'usw', 'tel', 'str', 'inkl', 'ggü'})


def _trenne(absatz: str) -> list[str]:
    """Trennt an Satzzeichen, aber nicht hinter „Dr.“ oder „ca.“."""
    teile, start = [], 0
    for treffer in _SATZENDE.finditer(absatz):
        wort = re.search(r'(\w+)$', absatz[start:treffer.start()])
        if wort and wort.group(1).casefold() in _KUERZEL:
            continue
        teile.append(absatz[start:treffer.start() + 1])
        start = treffer.end()
    teile.append(absatz[start:])
    return teile

# Formulierungen des Schreibenden über sich („ich packe ein“) oder in einer Notiz (Stichwortstil).
_EIGEN = re.compile(r'\b(?:mit(?:zu)?nehm\w*|mitbring\w*|einpack\w*|einstecken|dabei\s+haben|'
                    r'(?:bring|nehm|pack)e?\w*\b.{0,120}\bmit\b|(?:bring|nehm)en\b.{0,80}\bmit\b)', re.I)
# Jemand spricht den Nutzer an.
_ANGESPROCHEN = re.compile(r'\b(?:bitte\b.{0,100}\b(?:mit(?:zu)?bring\w*|mit(?:zu)?nehm\w*)|'
                           r'(?:bring|nehm)\w*\s+(?:sie|du|ihr)\b.{0,100}\bmit\b|'
                           r'(?:bring|nehm)st\s+du\b.{0,100}\bmit\b|denken\s+sie\s+an|'
                           r'(?:können|könnten|würden)\s+sie\b.{0,100}\bmit(?:zu)?(?:bring|nehm)\w*)', re.I)


@dataclass(frozen=True)
class Quelle:
    """Ein Text, der etwas zu einem Termin sagen kann."""

    episode_id: str
    titel: str
    zeit: datetime | None
    text: str
    art: str
    """`termin` (Notiz zum Termin), `notiz`, `mail`."""
    von_mir: bool
    """Der Nutzer hat es geschrieben (eigene Notiz, Notiz im Termin, eigene Mail)."""


@dataclass(frozen=True)
class Packstueck:
    text: str
    """Der Satz, wörtlich (auf Wortgrenze gekürzt)."""
    episode_id: str
    titel: str
    zeit: datetime | None
    art: str

    def to_dict(self) -> dict:
        return {'text': self.text, 'episode_id': self.episode_id, 'titel': self.titel,
                'datum': self.zeit.isoformat() if self.zeit else None, 'art': self.art}


def _kurz(satz: str, laenge: int = 220) -> str:
    satz = ' '.join(satz.split())
    return satz if len(satz) <= laenge else satz[:laenge].rsplit(' ', 1)[0].rstrip(',;:') + ' …'


_LISTENPUNKT = re.compile(r'^\s*(?:[-•*–—]|\d+[.)])\s+')


def saetze(text: str) -> list[str]:
    """Sätze eines Textes, ohne Leeres.

    Mails sind hart umbrochen: Ein Zeilenende mitten im Satz trennt ihn nicht. Ein Satz endet
    an Satzzeichen, an einer Leerzeile, an einem Zeilenende nach Satzzeichen oder Doppelpunkt
    und vor einem Listenpunkt („- Laptop“).
    """
    absaetze: list[str] = []
    aktuell: list[str] = []
    for zeile in (text or '').splitlines():
        if not zeile.strip():
            absaetze.append(' '.join(aktuell))
            aktuell = []
            continue
        if aktuell and (_LISTENPUNKT.match(zeile) or aktuell[-1].rstrip().endswith(('.', '!', '?', ':', ';'))):
            absaetze.append(' '.join(aktuell))
            aktuell = []
        aktuell.append(_LISTENPUNKT.sub('', zeile).strip())
    absaetze.append(' '.join(aktuell))
    teile = [t.strip(' \t-•*–—') for absatz in absaetze for t in _trenne(absatz)]
    return [t for t in teile if len(t) > 2]


def gilt_fuer_nutzer(satz: str, *, von_mir: bool) -> bool:
    """Ob der Satz etwas nennt, das der Nutzer mitbringen soll."""
    if von_mir:
        return bool(_EIGEN.search(satz)) and not _ueber_andere(satz)
    return bool(_ANGESPROCHEN.search(satz))


def _ueber_andere(satz: str) -> bool:
    """Eigene Sätze über andere („Frau Engel bringt Zahlen mit“) gehören nicht in die eigene Liste."""
    return bool(re.search(r'\b(?:er|sie|herr\s+\w+|frau\s+(?:dr\.\s*)?\w+)\s+(?:bringt|nimmt|packt)\b', satz, re.I))


def packliste(quellen: Iterable[Quelle], *, hoechstens: int = 6) -> list[Packstueck]:
    """Die belegten Sätze, jüngste Quelle zuerst; doppelte Sätze nur einmal. Leer, wenn nichts belegt ist."""
    gefunden: list[Packstueck] = []
    gesehen: set[str] = set()
    geordnet = sorted(quellen, key=lambda q: q.zeit.timestamp() if q.zeit else 0.0, reverse=True)
    for quelle in geordnet:
        for satz in saetze(quelle.text):
            if not gilt_fuer_nutzer(satz, von_mir=quelle.von_mir):
                continue
            schluessel = ' '.join(satz.casefold().split())
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            gefunden.append(Packstueck(_kurz(satz), quelle.episode_id, quelle.titel, quelle.zeit, quelle.art))
            if len(gefunden) >= hoechstens:
                return gefunden
    return gefunden


__all__ = ['Packstueck', 'Quelle', 'gilt_fuer_nutzer', 'packliste', 'saetze']
