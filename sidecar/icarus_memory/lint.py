"""Lint über alle Akten (M2): das Gedächtnis gegen sich selbst geprüft, ohne Modell.

Die Satzprüfung (`satzpruefung.py`) prüft jeden Satz gegen seine Quelle. Dieser Lauf
prüft das Ganze gegen sich selbst und findet **Befunde** (`Befund`):

| Art | Was | Folge |
|---|---|---|
| `widerspruch` | Zwei Akten nennen für denselben Gegenstand verschiedene Werte: eine Akte führt eine Frist oder einen Stand als aktuell, den eine andere Akte schon als überholt kennt. | zwei Vorschläge („alt gilt“ / „neu gilt“), wichtig |
| `aussage_gegen_quelle` | Eine angenommene Aussage (`claims.py`) widerspricht einer jüngeren Quelle derselben Sache (andere Frist, andere Anschrift, anderer Betrag). | ein Vorschlag mit dem neuen Wert, wichtig |
| `veralteter_satz` | Sätze der Lage (`lage.py`), deren Belege alle älter sind als eine jüngere Änderung oder Standmeldung derselben Sache. | Hinweis |
| `waise` | Eine Person in mehreren Quellen, die keiner Akte sicher zugeordnet ist (`ohne_akte`); eine Akte ohne Quelle seit einem Jahr (`ruhend`); eine Zuordnung oder Zusammenführung, deren Sache es nicht mehr gibt (`verwaister_bezug`). | Hinweis, nie ein Vorschlag zum Löschen |
| `querverweis` | Eine Person schreibt in mehreren Quellen über ein Projekt, aber ihre Akte und die des Projekts kennen sich nicht. | Hinweis |

**Die Regel des Gedächtnisses gilt unverändert.** Dieser Lauf liest nur. Er schreibt nie einen
Fakt, ändert keine Quelle, keine Akte und keine Aussage. Aus Befunden der Arten `widerspruch` und
`aussage_gegen_quelle` entstehen **Vorschläge** über den vorhandenen Vorschlagsmechanismus
(`vorschlagen`, nur `KnowledgeService.propose`); erst der Klick eines Menschen (in `lint_routes.py`)
macht daraus Wissen. Die Befunde selbst stehen in einer eigenen kleinen Ablage (`Befunde`,
`lint.sqlite3`), je Befund mit Status offen, erledigt oder abgewiesen.

Grundlage ist, was die Akten ohnehin wissen: `akten.Akten.roh` (Fristen mit `ersetzt_durch`, Stand
mit „vorher“), `akten._gegenstand` und `akten._umfeld` (gleicher Gegenstand einer Frist),
`bezuege` (welche Quelle zu welcher Sache gehört, offene Erwähnungen, Zuordnungen des Nutzers) und
`lage.Lagen.ueberholte_saetze` (dieselbe Regel, nach der die Akte veraltete Sätze ausblendet).

Was er **nicht** findet: Widersprüche ohne vergleichbaren Wert (Zusage gegen Absage, zwei
verschiedene Meinungen), Werte, die keine Akte als Frist oder Stand führt, und alles, was die grobe
Wortstammregel „gleicher Gegenstand“ nicht zusammenbringt. Lieber ein Befund zu wenig als ein
Fehlalarm: Ein Widerspruch zählt nur, wenn beide Seiten einen Wert derselben Sorte tragen (Datum,
Anschrift, Postleitzahl, Mailadresse, Betrag) und sich diese Werte nicht überschneiden.

## Stabile Schnittstelle für Briefing und Logbuch

    zusammenfassung(quelle) -> dict

`quelle` ist die FastAPI-App (liest `app.state.lint_befunde`) oder eine `Befunde`-Ablage. Ergebnis,
immer mit allen Schlüsseln und allen Arten (auch bei null, auch ohne Ablage):

    {'offen': int,                       # offene Befunde insgesamt
     'wichtig': int,                     # davon Schwere „wichtig“ (Arten widerspruch, aussage_gegen_quelle)
     'je_art': {'widerspruch': int, 'aussage_gegen_quelle': int, 'veralteter_satz': int,
                'waise': int, 'querverweis': int},
     'neu_seit_letztem_lauf': int,       # offen und im letzten Lauf zum ersten Mal gefunden
     'letzter_lauf': str | None}         # ISO-Zeitpunkt des letzten Laufs, None ohne Lauf

Die Zählung liest nur die Ablage, rechnet nichts neu und wirft nie; ohne Ablage sind alle Zahlen 0.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from . import akten as akten_modul
from .bezuege import GUELTIG, GUELTIG_PARAMS, zerlegen
from .datumstext import MONATE, iso_versuchen_utc
from .fristen import fristen_in
from .migrations import IndexContract, Migration, run_migrations, verify_schema

ARTEN = ('widerspruch', 'aussage_gegen_quelle', 'veralteter_satz', 'waise', 'querverweis')
#: Wie die Art in der Oberfläche heißt.
ART_TEXTE = {'widerspruch': 'Widerspruch zwischen Akten', 'aussage_gegen_quelle': 'Angenommenes gegen neuere Quelle',
             'veralteter_satz': 'Lage womöglich überholt', 'waise': 'Ohne Zuordnung', 'querverweis': 'Fehlender Querverweis'}
SCHWEREN = ('wichtig', 'hinweis')
STATI = ('offen', 'erledigt', 'abgewiesen')
#: Arten, aus denen Vorschläge entstehen.
MIT_VORSCHLAG = ('widerspruch', 'aussage_gegen_quelle')

#: Eine Akte gilt als ruhend, wenn ihre jüngste Quelle älter ist als das (Tage) …
RUHEND_TAGE = 365
#: … und sie mindestens so viele Quellen hat (eine einzelne alte Mail ist keine Akte, die jemand vermisst).
RUHEND_MIN_QUELLEN = 3
#: So viele Quellen mit derselben offenen Erwähnung machen daraus eine Waise.
OHNE_AKTE_MIN_QUELLEN = 3
#: So viele Quellen einer Person, die den Projektnamen nennen, ohne dass Person und Projekt sich kennen.
QUERVERWEIS_MIN_QUELLEN = 3
#: Vorrang der Sachen, wenn ein Vorschlag eine Sache als Gegenstand braucht.
_VORRANG = {'projekt': 0, 'organisation': 1, 'person': 2, 'ort': 3, 'thema': 4}


# -- Werte, die sich vergleichen lassen ---------------------------------------------------------

_STRASSE = re.compile(r'\b([A-ZÄÖÜ][\wäöüß.-]*?(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|ufer|'
                      r'chaussee|steig|pfad|markt|berg|hof))\s+(\d{1,4}\s?[a-z]?)\b')
_PLZ = re.compile(r'(?<![\d.,])(\d{5})\s+[A-ZÄÖÜ]')
_MAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_BETRAG = re.compile(r'(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:€|euro\b|eur\b)', re.I)
#: Name der Wertsorte in der Oberfläche.
SORTEN = {'datum': 'Datum', 'anschrift': 'Anschrift', 'plz': 'Postleitzahl', 'mail': 'Mailadresse', 'betrag': 'Betrag'}


def _betrag(roh: str) -> str:
    zahl = roh.replace('.', '').replace(',', '.')
    try:
        return f'{float(zahl):.2f}'
    except ValueError:
        return roh


def werte(text: str, bezug: datetime | None = None) -> dict[str, dict[str, str]]:
    """Vergleichbare Werte eines Textes: Sorte -> {Normalform: Schreibweise im Text}.

    Daten werden mit dem Zeitpunkt der Quelle aufgelöst (`fristen.fristen_in`), wie in der Akte.
    Ohne `bezug` zählen nur Daten mit Jahr (eine angenommene Aussage hat keinen Bezugstag).
    """
    ergebnis: dict[str, dict[str, str]] = {}
    for treffer in _STRASSE.finditer(text):
        normal = ' '.join((treffer[1].casefold().replace('strasse', 'straße').replace('str.', 'straße'),
                           treffer[2].replace(' ', '').casefold()))
        ergebnis.setdefault('anschrift', {})[normal] = treffer[0].strip()
    for treffer in _PLZ.finditer(text):
        ergebnis.setdefault('plz', {})[treffer[1]] = treffer[1]
    for treffer in _MAIL.finditer(text):
        ergebnis.setdefault('mail', {})[treffer[0].casefold().rstrip('.')] = treffer[0].rstrip('.')
    for treffer in _BETRAG.finditer(text):
        ergebnis.setdefault('betrag', {})[_betrag(treffer[1])] = treffer[0].strip()
    bezugstag = bezug or datetime(2000, 1, 1, tzinfo=timezone.utc)
    for frist in fristen_in(text, bezugstag).fristen:
        if bezug is None and not re.search(r'\d{4}', text[frist.start:frist.ende]):
            continue
        ergebnis.setdefault('datum', {})[frist.datum.isoformat()] = text[frist.start:frist.ende].strip()
    return ergebnis


def widerspruechliche_sorten(alt: dict[str, dict[str, str]], neu: dict[str, dict[str, str]]) -> list[str]:
    """Sorten, die beide Seiten tragen, ohne einen gemeinsamen Wert. Datum nur, wenn sonst nichts vergleichbar ist."""
    sorten = [s for s in ('anschrift', 'mail', 'betrag', 'plz') if alt.get(s) and neu.get(s)]
    if not sorten and alt.get('datum') and neu.get('datum'):
        sorten = ['datum']
    return [s for s in sorten if not set(alt[s]) & set(neu[s])]


def _datum_text(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime('%d.%m.%Y')
    except ValueError:
        return iso


# -- Datenklassen an der Grenze ------------------------------------------------------------------


@dataclass(frozen=True)
class Beleg:
    """Eine Quelle eines Befunds, mit Rolle (`alt`, `neu`, `aussage` oder leer) und Textstelle im Original."""

    episode_id: str
    rolle: str = ''
    start: int = -1
    ende: int = -1

    def to_dict(self) -> dict[str, Any]:
        return {'episode_id': self.episode_id, 'rolle': self.rolle, 'start': self.start, 'ende': self.ende}


@dataclass(frozen=True)
class Entwurf:
    """Was als Vorschlag in die Vorschlagsschlange geht (nur für `widerspruch` und `aussage_gegen_quelle`).

    `wahl` ist die Antwort, für die dieser Vorschlag steht: `neu` (der jüngere Wert gilt) oder `alt`.
    `ersetzt` nennt bestehende Aussagen, die bei Annahme abgelöst würden.
    """

    wahl: str
    subject_ref: str
    predicate: str
    value: str
    statement: str
    rationale: str
    episode_id: str
    zitat: str
    scope_ref: str | None = None
    ersetzt: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {'wahl': self.wahl, 'subject_ref': self.subject_ref, 'predicate': self.predicate, 'value': self.value,
                'statement': self.statement, 'rationale': self.rationale, 'episode_id': self.episode_id,
                'zitat': self.zitat, 'scope_ref': self.scope_ref, 'ersetzt': list(self.ersetzt)}

    @classmethod
    def aus(cls, d: dict[str, Any]) -> 'Entwurf':
        return cls(d['wahl'], d['subject_ref'], d['predicate'], d['value'], d['statement'], d['rationale'],
                   d['episode_id'], d['zitat'], d.get('scope_ref'), tuple(d.get('ersetzt') or ()))


@dataclass(frozen=True)
class Befund:
    """Ein Befund des Laufs: Art, beteiligte Sachen, Belege, ein Satz in Alltagssprache, Schwere."""

    art: str
    sachen: tuple[str, ...]
    belege: tuple[Beleg, ...]
    text: str
    schwere: str
    unterart: str = ''
    werte: tuple[tuple[str, str], ...] = ()
    """Die verglichenen Werte, etwa (('alt', '20.10.2026'), ('neu', '06.11.2026'), ('sorte', 'Datum'))."""
    entwuerfe: tuple[Entwurf, ...] = ()

    def __post_init__(self) -> None:
        if self.art not in ARTEN or self.schwere not in SCHWEREN:
            raise ValueError(f'Unbekannte Art oder Schwere: {self.art}/{self.schwere}')
        if self.entwuerfe and self.art not in MIT_VORSCHLAG:
            raise ValueError('Nur Widersprüche werden zu Vorschlägen.')

    @property
    def schluessel(self) -> str:
        """Erkennt denselben Befund im nächsten Lauf wieder: Art, Sachen, Belege (nicht der Text)."""
        inhalt = [self.art, self.unterart, sorted(self.sachen),
                  sorted((b.episode_id, b.rolle, b.start, b.ende) for b in self.belege)]
        return 'b-' + hashlib.sha256(json.dumps(inhalt, ensure_ascii=False).encode()).hexdigest()[:20]


@dataclass
class LintErgebnis:
    """Was ein Lauf gefunden hat, mit Zahlen für Diagnose und Messung."""

    befunde: list[Befund]
    sachen: int = 0
    aussagen: int = 0
    dauer_s: float = 0.0
    nicht_geprueft: list[str] = field(default_factory=list)
    """Prüfungen, die nicht laufen konnten, mit Grund (etwa „keine Lagen: kein lokales Modell“)."""


# -- Der Lauf -----------------------------------------------------------------------------------


@dataclass
class _Akte:
    sache: str
    quellen: list[dict[str, Any]]
    ids: frozenset[str]
    roh: dict[str, Any]


def _zeit(wert: Any) -> datetime | None:
    return iso_versuchen_utc(wert)


def _frist_schluessel(ref: dict[str, Any], start: int) -> tuple[str, int, int]:
    return (ref['episode_id'], int(ref['start']), int(start))


def _ref_schluessel(ref: dict[str, Any]) -> tuple[str, int, int]:
    return (ref['episode_id'], int(ref['start']), int(ref['end']))


class Pruefer:
    """Ein Lauf über alle Akten. Liest nur: Bezüge, Akten (Zwischenspeicher), Aussagen, Lagen."""

    def __init__(self, episodes: Any, bezuege: Any, akten: Any, *, claims: Any = None, workspace: Any = None,
                 lagen: Any = None, jetzt: datetime | None = None) -> None:
        self.episodes = episodes
        self.bezuege = bezuege
        self.akten = akten
        self.claims = claims
        self.workspace = workspace
        self.lagen = lagen
        self.jetzt = jetzt or datetime.now(timezone.utc)
        self._akten: dict[str, _Akte] = {}
        self._namen: dict[str, str] = {}
        self._titel: dict[str, tuple[str, datetime | None]] = {}
        claims_frei = akten_modul._MerkeFrei(claims) if claims is not None else None
        self._leser = akten_modul._Leser(akten.store, claims_frei)

    # -- Hilfen --

    def _alle_sachen(self) -> list[dict[str, Any]]:
        sachen, offset = [], 0
        while True:
            seite = self.bezuege.sachen(limit=500, offset=offset)
            sachen += seite['sachen']
            offset += 500
            if offset >= seite['gesamt'] or not seite['sachen']:
                return sachen

    def _akte(self, sache: str) -> _Akte | None:
        if sache not in self._akten:
            quellen = self.bezuege.quellen_von(sache)
            roh = self.akten.roh(sache, quellen) if quellen else None
            self._akten[sache] = _Akte(sache, quellen, frozenset(q['episode_id'] for q in quellen), roh or {})
        akte = self._akten[sache]
        return akte if akte.quellen else None

    def _name(self, sache: str) -> str:
        if sache not in self._namen:
            self._namen.update(self.bezuege.beschriftungen([sache]))
        return self._namen.get(sache, sache)

    def _namen_von(self, sachen: Iterable[str]) -> str:
        """„Bernd Kolbe und Küchenforum Main“: die Namen, wie die Akten sie zeigen."""
        namen = list(dict.fromkeys(self._name(s) for s in sachen))
        if len(namen) <= 1:
            return ''.join(namen)
        return ', '.join(namen[:-1]) + ' und ' + namen[-1]

    def _akten_von(self, sachen: list[str]) -> tuple[str, bool]:
        """(„die Akte von X“ oder „die Akten von X und Y“, Mehrzahl?)."""
        mehr = len(sachen) > 1
        return f'die {"Akten" if mehr else "Akte"} von {self._namen_von(sachen)}', mehr

    def _quelle(self, episode_id: str) -> str:
        """„Titel“ vom TT.MM.JJJJ, aus dem Original gelesen."""
        if episode_id not in self._titel:
            try:
                episode = self.episodes.get(episode_id)
                self._titel[episode_id] = (episode.title[:120], episode.reference_time())
            except Exception:  # noqa: BLE001 - eine unlesbare Quelle nennt der Satz ohne Titel
                self._titel[episode_id] = ('', None)
        titel, zeit = self._titel[episode_id]
        tag = zeit.astimezone(_zone()).strftime('%d.%m.%Y') if zeit else ''
        return (f'„{titel}“' if titel else 'eine Quelle') + (f' vom {tag}' if tag else '')

    def _subjekt(self, sache: str) -> str:
        """Kennung einer Sache als Gegenstand einer Aussage (wie Gesprächsvorschläge sie bilden)."""
        art, kennung = zerlegen(sache) or ('', '')
        if art == 'projekt' and not kennung.startswith('n:'):
            return f'project:{kennung}'
        if art == 'person':
            from . import graph
            return graph.person_id(self._name(sache))
        return sache

    def _sachen_zum_subjekt(self, subjekt: str, alle: list[str]) -> set[str]:
        if subjekt.startswith('project:'):
            return {'projekt:' + subjekt[len('project:'):]}
        if re.fullmatch(r'person:[0-9a-f]{16}', subjekt):
            from . import graph
            personen = [s for s in alle if s.startswith('person:')]
            namen = self.bezuege.beschriftungen(personen) if personen else {}
            self._namen.update(namen)
            return {s for s in personen if graph.person_id(namen[s]) == subjekt}
        return {subjekt} if zerlegen(subjekt) else set()

    # -- Prüfungen --

    def pruefen(self) -> LintErgebnis:
        begonnen = time.perf_counter()
        sachen = self._alle_sachen()
        for eintrag in sachen:
            self._akte(eintrag['sache'])
        befunde: list[Befund] = []
        befunde += self._fristen_widersprueche()
        befunde += self._stand_widersprueche()
        aussagen, gegen = self._aussagen_gegen_quellen([e['sache'] for e in sachen])
        befunde += gegen
        nicht_geprueft: list[str] = []
        befunde += self._veraltete_saetze(nicht_geprueft)
        befunde += self._ohne_akte()
        befunde += self._ruhend()
        befunde += self._verwaiste_bezuege([e['sache'] for e in sachen])
        befunde += self._querverweise()
        eindeutig: dict[str, Befund] = {}
        for befund in befunde:
            eindeutig.setdefault(befund.schluessel, befund)
        return LintErgebnis(list(eindeutig.values()), sachen=len(sachen), aussagen=aussagen,
                            dauer_s=round(time.perf_counter() - begonnen, 3), nicht_geprueft=nicht_geprueft)

    def _fristen_widersprueche(self) -> list[Befund]:
        """Eine Frist steht in einer Akte als gültig, eine andere Akte kennt sie als verschoben."""
        gueltig_in: dict[tuple, list[str]] = {}
        ersetzt_in: dict[tuple, list[tuple[str, dict]]] = {}
        fristen: dict[tuple, dict] = {}
        for akte in self._akten.values():
            for f in akte.roh.get('fristen', []):
                k = _frist_schluessel(f['ref'], f['start'])
                fristen.setdefault(k, f)
                if f['ersetzt_durch']:
                    ersetzt_in.setdefault(k, []).append((akte.sache, f['ersetzt_durch']))
                else:
                    gueltig_in.setdefault(k, []).append(akte.sache)
        gruppen: dict[tuple, dict[str, Any]] = {}
        for k, eintraege in ersetzt_in.items():
            for kennt, neu in eintraege:
                nk = _frist_schluessel(neu['ref'], neu['start'])
                veraltet = [a for a in gueltig_in.get(k, ()) if neu['ref']['episode_id'] not in self._akten[a].ids]
                if not veraltet:
                    continue
                gruppe = gruppen.setdefault((k, nk), {'alt': fristen[k], 'neu': neu, 'veraltet': set(), 'kennt': set()})
                gruppe['veraltet'].update(veraltet)
                gruppe['kennt'].add(kennt)
        befunde = []
        for (k, nk), gruppe in sorted(gruppen.items()):
            alt, neu = gruppe['alt'], gruppe['neu']
            if alt['datum'] == neu['datum']:
                continue
            voll_alt = self._leser.voll(alt['ref']) or ''
            voll_neu = self._leser.voll(neu['ref']) or ''
            if not voll_alt or not voll_neu:
                continue
            umfeld_alt = akten_modul._umfeld(voll_alt, alt['start'], alt['ende'])
            umfeld_neu = akten_modul._umfeld(voll_neu, neu['start'], neu['ende'])
            wort = _gegenstandswort(umfeld_alt, umfeld_neu)
            veraltet, kennt = sorted(gruppe['veraltet']), sorted(gruppe['kennt'] - gruppe['veraltet'])
            alt_text, neu_text = _datum_text(alt['datum']), _datum_text(neu['datum'])
            (alt_akten, mehr), (neu_akten, mehr_neu) = self._akten_von(veraltet), self._akten_von(kennt)
            text = (f'Frist „{wort}“: {alt_akten[0].upper() + alt_akten[1:]} {"nennen" if mehr else "nennt"} noch den '
                    f'{alt_text}, {neu_akten} {"kennen" if mehr_neu else "kennt"} schon den {neu_text} '
                    f'({self._quelle(neu["ref"]["episode_id"])}).')
            subjekt = self._subjekt(min([*kennt, *veraltet], key=_vorrang))
            praedikat = f'Frist {wort}'
            entwuerfe = (
                Entwurf('neu', subjekt, praedikat, neu_text, f'{praedikat}: {neu_text}',
                        f'Jüngere Quelle ({self._quelle(neu["ref"]["episode_id"])}); {alt_akten} '
                        f'{"nennen" if mehr else "nennt"} noch den {alt_text}.', neu['ref']['episode_id'],
                        umfeld_neu.strip()),
                Entwurf('alt', subjekt, praedikat, alt_text, f'{praedikat}: {alt_text}',
                        f'Ältere Quelle ({self._quelle(alt["ref"]["episode_id"])}); {neu_akten} '
                        f'{"kennen" if mehr_neu else "kennt"} schon den {neu_text}.', alt['ref']['episode_id'],
                        umfeld_alt.strip()))
            befunde.append(Befund(
                'widerspruch', tuple([*veraltet, *kennt]),
                (Beleg(alt['ref']['episode_id'], 'alt', int(alt['ref']['start']), int(alt['ref']['end'])),
                 Beleg(neu['ref']['episode_id'], 'neu', int(neu['ref']['start']), int(neu['ref']['end']))),
                text, 'wichtig', 'frist', (('sorte', 'Datum'), ('alt', alt_text), ('neu', neu_text), ('gegenstand', wort)),
                entwuerfe))
        return befunde

    def _stand_widersprueche(self) -> list[Befund]:
        """Ein Stand ist in einer Akte aktuell, eine andere Akte kennt einen jüngeren mit anderem Wert."""
        aktuell_in: dict[tuple, list[str]] = {}
        vorher_in: dict[tuple, list[tuple[str, dict]]] = {}
        refs: dict[tuple, dict] = {}
        for akte in self._akten.values():
            for gruppe in akte.roh.get('stand', []):
                k = _ref_schluessel(gruppe['aktuell'])
                refs.setdefault(k, gruppe['aktuell'])
                aktuell_in.setdefault(k, []).append(akte.sache)
                for ref in gruppe['vorher']:
                    vk = _ref_schluessel(ref)
                    refs.setdefault(vk, ref)
                    vorher_in.setdefault(vk, []).append((akte.sache, gruppe['aktuell']))
        gruppen: dict[tuple, dict[str, Any]] = {}
        for k, eintraege in vorher_in.items():
            for kennt, neu in eintraege:
                veraltet = [a for a in aktuell_in.get(k, ()) if neu['episode_id'] not in self._akten[a].ids]
                if not veraltet:
                    continue
                gruppe = gruppen.setdefault((k, _ref_schluessel(neu)),
                                            {'alt': refs[k], 'neu': neu, 'veraltet': set(), 'kennt': set()})
                gruppe['veraltet'].update(veraltet)
                gruppe['kennt'].add(kennt)
        befunde = []
        for (k, nk), gruppe in sorted(gruppen.items()):
            alt, neu = gruppe['alt'], gruppe['neu']
            voll_alt, voll_neu = self._leser.voll(alt) or '', self._leser.voll(neu) or ''
            if not voll_alt or not voll_neu:
                continue
            werte_alt = werte(voll_alt, _zeit(alt.get('zeit')))
            werte_neu = werte(voll_neu, _zeit(neu.get('zeit')))
            sorten = widerspruechliche_sorten(werte_alt, werte_neu)
            if not sorten:
                continue
            sorte = sorten[0]
            alt_wert = ', '.join(werte_alt[sorte].values())
            neu_wert = ', '.join(werte_neu[sorte].values())
            veraltet, kennt = sorted(gruppe['veraltet']), sorted(gruppe['kennt'] - gruppe['veraltet'])
            (alt_akten, mehr), (neu_akten, mehr_neu) = self._akten_von(veraltet), self._akten_von(kennt)
            text = (f'{SORTEN[sorte]}: {alt_akten[0].upper() + alt_akten[1:]} {"führen" if mehr else "führt"} noch '
                    f'„{alt_wert}“, {neu_akten} {"kennen" if mehr_neu else "kennt"} schon „{neu_wert}“ '
                    f'({self._quelle(neu["episode_id"])}).')
            subjekt = self._subjekt(min([*kennt, *veraltet], key=_vorrang))
            praedikat = SORTEN[sorte]
            entwuerfe = (
                Entwurf('neu', subjekt, praedikat, neu_wert, f'{praedikat}: {neu_wert}',
                        f'Jüngere Quelle ({self._quelle(neu["episode_id"])}).', neu['episode_id'], voll_neu.strip()),
                Entwurf('alt', subjekt, praedikat, alt_wert, f'{praedikat}: {alt_wert}',
                        f'Ältere Quelle ({self._quelle(alt["episode_id"])}).', alt['episode_id'], voll_alt.strip()))
            befunde.append(Befund(
                'widerspruch', tuple([*veraltet, *kennt]),
                (Beleg(alt['episode_id'], 'alt', int(alt['start']), int(alt['end'])),
                 Beleg(neu['episode_id'], 'neu', int(neu['start']), int(neu['end']))),
                text, 'wichtig', 'stand', (('sorte', SORTEN[sorte]), ('alt', alt_wert), ('neu', neu_wert)), entwuerfe))
        return befunde

    def _aussagen_gegen_quellen(self, alle: list[str]) -> tuple[int, list[Befund]]:
        """Angenommene Aussagen gegen jüngere Fristen und Stände ihrer Sache."""
        if self.claims is None:
            return 0, []
        try:
            aussagen = [c for c in self.claims.all_claims(include_inactive=False) if self.claims.is_usable(c)]
        except Exception:  # noqa: BLE001 - ohne lesbaren Wissensbestand gibt es hier nichts zu vergleichen
            return 0, []
        befunde = []
        for aussage in aussagen:
            eigene = werte(aussage.value) or werte(aussage.statement)
            if not eigene:
                continue
            basis = self._basiszeit(aussage)
            if basis is None:
                continue
            sachen = self._sachen_zum_subjekt(aussage.subject_ref, alle)
            gegenstand = akten_modul._gegenstand(f'{aussage.predicate} {aussage.statement}')
            gefunden = self._juengerer_wert(sachen, eigene, gegenstand, basis,
                                            {e.episode_id for e in aussage.evidence})
            if gefunden is None:
                continue
            sorte, ref, neuer_wert, zitat = gefunden
            alter_wert = ', '.join(eigene[sorte].values())
            if aussage.value and aussage.value in aussage.statement:
                satz = aussage.statement.replace(aussage.value, neuer_wert)
            else:
                satz = f'{aussage.predicate}: {neuer_wert}'
            quelle = self._quelle(ref['episode_id'])
            text = (f'Du hattest angenommen: „{aussage.statement.rstrip(". ")}“. {quelle[0].upper() + quelle[1:]} '
                    f'nennt „{neuer_wert}“. Was gilt?')
            entwurf = Entwurf('neu', aussage.subject_ref, aussage.predicate, neuer_wert, satz,
                              f'Du hattest „{alter_wert}“ angenommen; {quelle} nennt „{neuer_wert}“.',
                              ref['episode_id'], zitat, aussage.scope_ref, (aussage.id,))
            befunde.append(Befund(
                'aussage_gegen_quelle', tuple(sorted(sachen)),
                (*(Beleg(e.episode_id, 'aussage') for e in aussage.evidence),
                 Beleg(ref['episode_id'], 'neu', int(ref['start']), int(ref['end']))),
                text, 'wichtig', aussage.id,
                (('sorte', SORTEN[sorte]), ('alt', alter_wert), ('neu', neuer_wert), ('aussage', aussage.id)),
                (entwurf,)))
        return len(aussagen), befunde

    def _basiszeit(self, aussage: Any) -> datetime | None:
        zeiten = []
        for beleg in aussage.evidence:
            try:
                zeiten.append(self.episodes.get(beleg.episode_id).reference_time())
            except Exception:  # noqa: BLE001 - ein verschwundener Beleg: die Aussage selbst prüft das
                continue
        return max(zeiten) if zeiten else None

    def _juengerer_wert(self, sachen: set[str], eigene: dict, gegenstand: frozenset[str], basis: datetime,
                        ausgenommen: set[str]) -> tuple[str, dict, str, str] | None:
        """Der jüngste Abschnitt der Sachen nach `basis`, der denselben Gegenstand mit anderem Wert nennt."""
        kandidaten: list[tuple[datetime, str, dict, str, str]] = []
        for sache in sachen:
            akte = self._akte(sache)
            if akte is None:
                continue
            if eigene.get('datum'):
                for f in akte.roh.get('fristen', []):
                    zeit = _zeit(f['ref'].get('zeit'))
                    if f['ersetzt_durch'] or zeit is None or zeit <= basis or f['ref']['episode_id'] in ausgenommen:
                        continue
                    voll = self._leser.voll(f['ref']) or ''
                    umfeld = akten_modul._umfeld(voll, f['start'], f['ende'])
                    if len(akten_modul._gegenstand(umfeld) & gegenstand) < 2 or f['datum'] in eigene['datum']:
                        continue
                    kandidaten.append((zeit, 'datum', f['ref'], _datum_text(f['datum']), umfeld.strip()))
            for gruppe in akte.roh.get('stand', []):
                ref = gruppe['aktuell']
                zeit = _zeit(ref.get('zeit'))
                if zeit is None or zeit <= basis or ref['episode_id'] in ausgenommen:
                    continue
                voll = self._leser.voll(ref) or ''
                if len(akten_modul.stamm_menge(voll) & gegenstand) < 2:
                    continue
                sorten = widerspruechliche_sorten(eigene, werte(voll, zeit))
                if sorten and sorten[0] != 'datum':
                    kandidaten.append((zeit, sorten[0], ref, ', '.join(werte(voll, zeit)[sorten[0]].values()),
                                       voll.strip()))
        if not kandidaten:
            return None
        zeit, sorte, ref, wert, zitat = max(kandidaten, key=lambda k: (k[0], k[2]['episode_id']))
        return sorte, ref, wert, zitat

    def _veraltete_saetze(self, nicht_geprueft: list[str]) -> list[Befund]:
        if self.lagen is None:
            nicht_geprueft.append('veralteter_satz: keine Lagen angebunden')
            return []
        befunde = []
        for sache in self.lagen.sachen():
            if self._akte(sache) is None:
                continue
            ueberholt = self.lagen.ueberholte_saetze(sache)
            if not ueberholt:
                continue
            neuere = sorted({e for u in ueberholt for e in u['neuere']})
            belege = sorted({b for u in ueberholt for b in u['belege']})
            zeiten = {q['episode_id']: _zeit(q['zeit']) for q in self._akten[sache].quellen}
            juengste = max(neuere, key=lambda e: (zeiten.get(e) or self.jetzt - timedelta(days=36500), e))
            text = (f'Die Lage zu {self._namen_von([sache])} ist womöglich überholt: {len(ueberholt)} '
                    f'{"Satz stützt" if len(ueberholt) == 1 else "Sätze stützen"} sich auf ältere Quellen als '
                    f'{self._quelle(juengste)}. Sie wird neu geschrieben, sobald das lokale Modell dran ist.')
            befunde.append(Befund('veralteter_satz', (sache,),
                                  tuple([*(Beleg(e, 'alt') for e in belege), *(Beleg(e, 'neu') for e in neuere)]),
                                  text, 'hinweis'))
        return befunde

    def _ohne_akte(self) -> list[Befund]:
        """Offene Erwähnungen derselben Kandidaten in mehreren Quellen: Die Person hat keine Akte."""
        with self.episodes._lock:
            zeilen = self.episodes._conn.execute(
                "SELECT b.episode_id AS episode_id, b.kandidaten AS kandidaten FROM sach_bezuege b "
                "JOIN episodes e ON e.id = b.episode_id WHERE b.sache = '' AND b.kandidaten != '' AND " + GUELTIG,
                GUELTIG_PARAMS).fetchall()
        gruppen: dict[tuple[str, ...], set[str]] = {}
        for zeile in zeilen:
            try:
                kandidaten = tuple(sorted(json.loads(zeile['kandidaten'])))
            except ValueError:
                continue
            gruppen.setdefault(kandidaten, set()).add(zeile['episode_id'])
        # Hat der Nutzer die Person einer Quelle schon bestimmt, ist diese Quelle keine Waise mehr.
        befunde = []
        for kandidaten, quellen in sorted(gruppen.items()):
            quellen = {q for q in quellen if not any(q in (self._akte(k).ids if self._akte(k) else ()) for k in kandidaten)}
            if len(quellen) < OHNE_AKTE_MIN_QUELLEN:
                continue
            name = self._name(kandidaten[0])
            text = (f'„{name}“ steht in {len(quellen)} Quellen, aber es gibt {len(kandidaten)} Personen dieses Namens. '
                    f'Diese Quellen gehören zu keiner Akte, bis du sagst, wer gemeint ist.')
            befunde.append(Befund('waise', kandidaten, tuple(Beleg(q) for q in sorted(quellen)), text, 'hinweis',
                                  'ohne_akte'))
        return befunde

    def _ruhend(self) -> list[Befund]:
        """Akten einer Person oder eines Projekts mit mehreren Quellen, deren jüngste über ein Jahr alt ist.

        Eine Organisation allein ist kein Befund (Rundschreiben und Kundenservice ruhen oft jahrelang, und niemand
        vermisst sie); hat sie genau dieselben Quellen wie eine ruhende Person, steht sie mit im selben Befund.
        """
        grenze = self.jetzt - timedelta(days=RUHEND_TAGE)
        gruppen: dict[frozenset[str], list[_Akte]] = {}
        organisationen: dict[frozenset[str], list[_Akte]] = {}
        for akte in self._akten.values():
            art, _ = zerlegen(akte.sache) or ('', '')
            if art not in ('person', 'organisation', 'projekt') or len(akte.quellen) < RUHEND_MIN_QUELLEN:
                continue
            zeiten = [z for z in (_zeit(q['zeit']) for q in akte.quellen) if z is not None]
            if zeiten and max(zeiten) < grenze:
                (organisationen if art == 'organisation' else gruppen).setdefault(akte.ids, []).append(akte)
        for ids, gruppe in gruppen.items():
            gruppe += organisationen.get(ids, [])
        befunde = []
        for ids, gruppe in sorted(gruppen.items(), key=lambda p: sorted(a.sache for a in p[1])):
            sachen = sorted((a.sache for a in gruppe), key=_vorrang)
            quellen = sorted(gruppe[0].quellen, key=lambda q: (_zeit(q['zeit']) or grenze, q['episode_id']), reverse=True)
            letzte = (_zeit(quellen[0]['zeit']) or grenze).astimezone(_zone())
            text = (f'Zu {self._namen_von(sachen)} gibt es seit {MONATE[letzte.month - 1]} {letzte.year} '
                    f'nichts Neues ({len(ids)} Quellen). Nur zur Kenntnis; die Akte bleibt, wie sie ist.')
            befunde.append(Befund('waise', tuple(sachen), tuple(Beleg(q['episode_id']) for q in quellen[:10]), text,
                                  'hinweis', 'ruhend'))
        return befunde

    def _verwaiste_bezuege(self, alle: list[str]) -> list[Befund]:
        """Zuordnungen des Nutzers zu Projekten, die es nicht mehr gibt; Zusammenführungen mit verschwundenen Personen."""
        befunde = []
        if self.workspace is not None:
            with self.episodes._lock:
                zeilen = self.episodes._conn.execute(
                    "SELECT u.episode_id AS episode_id, u.sache AS sache FROM sach_nutzer u JOIN episodes e "
                    "ON e.id = u.episode_id WHERE u.aktion = 'zu' AND u.art = 'projekt' AND " + GUELTIG,
                    GUELTIG_PARAMS).fetchall()
            fehlend: dict[str, set[str]] = {}
            for zeile in zeilen:
                _, kennung = zerlegen(zeile['sache']) or ('', '')
                if kennung.startswith('n:'):
                    continue
                try:
                    self.workspace.project(kennung)
                except Exception:  # noqa: BLE001 - genau das ist der Befund: das Projekt gibt es nicht mehr
                    fehlend.setdefault(zeile['sache'], set()).add(zeile['episode_id'])
            for sache, quellen in sorted(fehlend.items()):
                text = (f'{len(quellen)} {"Quelle ist" if len(quellen) == 1 else "Quellen sind"} von dir einem Projekt '
                        f'zugeordnet, das es nicht mehr gibt. Sie bleiben in den Akten der Beteiligten.')
                befunde.append(Befund('waise', (sache,), tuple(Beleg(q) for q in sorted(quellen)), text, 'hinweis',
                                      'verwaister_bezug'))
        zusammenfuehrungen = getattr(self.claims, 'person_merges', None) if self.claims is not None else None
        if zusammenfuehrungen is not None:
            from . import graph
            try:
                gruppen = [g for g in zusammenfuehrungen.list() if not g['undone_at']]
            except Exception:  # noqa: BLE001 - ohne lesbare Zusammenführungen gibt es hier nichts zu prüfen
                gruppen = []
            if gruppen:
                personen = [s for s in alle if s.startswith('person:')]
                namen = self.bezuege.beschriftungen(personen) if personen else {}
                bekannt = {graph.person_id_fuer(zerlegen(s)[1]) for s in personen}
                bekannt |= {graph.person_id(n) for n in namen.values()}
                for gruppe in gruppen:
                    weg = [m for m in gruppe['members'] if m.get('id') not in bekannt]
                    if not weg:
                        continue
                    text = (f'Die Zusammenführung „{gruppe["label"]}“ nennt {len(weg)} '
                            f'{"Person" if len(weg) == 1 else "Personen"}, zu der es keine Quelle mehr gibt '
                            f'({", ".join(str(m.get("label", "")) for m in weg)}).')
                    befunde.append(Befund('waise', tuple(sorted(str(m.get('id')) for m in weg)), (), text, 'hinweis',
                                          'verwaister_bezug'))
        return befunde

    def _querverweise(self) -> list[Befund]:
        """Personen, die in mehreren Quellen ein Projekt nennen, ohne dass ihre Akte und die des Projekts sich kennen."""
        projekte = [a for a in self._akten.values() if a.sache.startswith('projekt:') and a.quellen]
        befunde = []
        for projekt in projekte:
            name = self._name(projekt.sache).strip()
            if len(name) < 5:
                continue
            muster = re.compile(r'(?<!\w)' + r'[\s-]+'.join(re.escape(t) for t in re.split(r'[\s-]+', name)) + r'(?!\w)',
                                re.I)
            with self.episodes._lock:
                zeilen = self.episodes._conn.execute(
                    "SELECT e.id AS id, e.document AS document FROM episodes e WHERE instr(lower(e.document), ?) > 0 AND "
                    + GUELTIG, (name.split()[0].casefold(), *GUELTIG_PARAMS)).fetchall()
            nennen = set()
            for zeile in zeilen:
                if zeile['id'] in projekt.ids:
                    continue
                try:
                    episode = self.episodes.get(zeile['id'])
                except Exception:  # noqa: BLE001
                    continue
                if muster.search(f'{episode.title}\n{episode.body}'):
                    nennen.add(zeile['id'])
            if len(nennen) < QUERVERWEIS_MIN_QUELLEN:
                continue
            je_person: dict[str, set[str]] = {}
            for sache, akte in self._akten.items():
                if not sache.startswith('person:'):
                    continue
                gemeinsam = akte.ids & nennen
                # Kennen sich die Akten (eine gemeinsame Quelle, die Person ist Beteiligte des Projekts), ist nichts zu tun.
                if len(gemeinsam) >= QUERVERWEIS_MIN_QUELLEN and not akte.ids & projekt.ids:
                    je_person[sache] = gemeinsam
            for person, quellen in sorted(je_person.items()):
                text = (f'{self._name(person)} schreibt in {len(quellen)} Quellen über „{name}“, aber diese Quellen '
                        f'gehören nicht zum Projekt, und die beiden Akten kennen sich nicht. '
                        f'Wenn die Quellen dazugehören, ordne sie dem Projekt zu.')
                befunde.append(Befund('querverweis', (person, projekt.sache), tuple(Beleg(q) for q in sorted(quellen)),
                                      text, 'hinweis'))
        return befunde




def _vorrang(sache: str) -> tuple[int, str]:
    return (_VORRANG.get((zerlegen(sache) or ('', ''))[0], 9), sache)


def _gegenstandswort(a: str, b: str) -> str:
    """Das längste gemeinsame Wort zweier Fristsätze („Teilnehmerliste“), sonst „Frist“."""
    from .lexical import terms_v1
    woerter_b = {w.casefold() for w in terms_v1(b)}
    gemeinsam = [w for w in re.findall(r'[A-Za-zÄÖÜäöüß]{5,}', a)
                 if w.casefold() in woerter_b and w.casefold() not in akten_modul._FUELLWOERTER]
    return max(gemeinsam, key=lambda w: (len(w), w)) if gemeinsam else 'Frist'


def _zone():
    from .model import user_timezone
    return user_timezone() or timezone.utc


# -- Vorschläge ---------------------------------------------------------------------------------


def vorschlagen(ablage: 'Befunde', knowledge_service: Any, episodes: Any) -> int:
    """Legt für offene Befunde mit Entwurf die Vorschläge an, die noch fehlen. Nur `propose`, nie `accept`.

    Rückgabe: Zahl neu angelegter Vorschläge. Ein Entwurf, dessen Quelle nicht mehr gilt oder
    dessen Zitat nicht mehr passt, wird übersprungen (die Vorschlagsschicht weist ihn ab).
    """
    from .proposals import Evidence
    neu = 0
    for eintrag in ablage.liste(status='offen'):
        if eintrag['vorschlaege'] or not eintrag['entwuerfe']:
            continue
        angelegt = []
        for roh in eintrag['entwuerfe']:
            entwurf = Entwurf.aus(roh)
            try:
                episode = episodes.get(entwurf.episode_id)
                vorschlag, frisch = knowledge_service.propose(
                    subject_ref=entwurf.subject_ref, predicate=entwurf.predicate, value=entwurf.value,
                    statement=entwurf.statement, rationale=entwurf.rationale, scope_ref=entwurf.scope_ref,
                    evidence=[Evidence(episode.id, entwurf.zitat, episode.digest)], proposed_by='lint')
            except Exception:  # noqa: BLE001 - abgewiesen oder Quelle geändert: der nächste Lauf versucht es erneut
                angelegt = []
                break
            angelegt.append({'wahl': entwurf.wahl, 'id': vorschlag.id})
            neu += int(frisch)
        if angelegt:
            ablage.vorschlaege_setzen(eintrag['id'], angelegt)
    return neu


# -- Ablage ----------------------------------------------------------------------------------------

_TABELLEN = {
    'befund': {'id', 'art', 'unterart', 'schwere', 'sachen', 'belege', 'text', 'werte', 'entwuerfe', 'vorschlaege',
               'status', 'entschieden', 'gefunden_am', 'gesehen_am', 'entschieden_am'},
    'lint_lauf': {'id', 'am', 'dauer_s', 'sachen', 'neu'},
}
_SCHLUESSEL = {'befund': {'id'}, 'lint_lauf': {'id'}}


def _indizes() -> dict[str, IndexContract]:
    return {'idx_befund_status': IndexContract('befund', ('status', 'art'))}


def _migrieren(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE befund (
        id TEXT PRIMARY KEY,
        art TEXT NOT NULL CHECK(art IN ('widerspruch','aussage_gegen_quelle','veralteter_satz','waise','querverweis')),
        unterart TEXT NOT NULL DEFAULT '',
        schwere TEXT NOT NULL CHECK(schwere IN ('wichtig','hinweis')),
        sachen TEXT NOT NULL DEFAULT '[]',
        belege TEXT NOT NULL DEFAULT '[]',
        text TEXT NOT NULL,
        werte TEXT NOT NULL DEFAULT '[]',
        entwuerfe TEXT NOT NULL DEFAULT '[]',
        vorschlaege TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'offen' CHECK(status IN ('offen','erledigt','abgewiesen')),
        entschieden TEXT NOT NULL DEFAULT '',
        gefunden_am REAL NOT NULL,
        gesehen_am REAL NOT NULL,
        entschieden_am REAL)""")
    conn.execute('CREATE INDEX idx_befund_status ON befund(status, art)')
    conn.execute("""CREATE TABLE lint_lauf (
        id INTEGER PRIMARY KEY CHECK(id = 1), am REAL NOT NULL, dauer_s REAL NOT NULL,
        sachen INTEGER NOT NULL, neu INTEGER NOT NULL)""")


def _pruefen(conn: sqlite3.Connection) -> None:
    verify_schema(conn, expected_tables=_TABELLEN, expected_primary_keys=_SCHLUESSEL, expected_indexes=_indizes())


_MIGRATIONS = (Migration(1, 'lint_befunde', _migrieren, _pruefen),)


class Befunde:
    """Die Ablage der Befunde (`lint.sqlite3`). Abgeleitet bis auf die Entscheidungen des Nutzers (Status)."""

    def __init__(self, pfad: str | Path) -> None:
        self._pfad = Path(pfad)
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._pfad), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            with self._lock:
                run_migrations(self._conn, store='lint', path=self._pfad, migrations=_MIGRATIONS)
        except Exception:
            self._conn.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def abgleichen(self, befunde: list[Befund], *, am: float | None = None, dauer_s: float = 0.0,
                   sachen: int = 0) -> dict[str, int]:
        """Übernimmt das Ergebnis eines Laufs.

        Neue Befunde kommen offen hinzu; bekannte behalten ihren Status (ein abgewiesener bleibt
        abgewiesen, ein erledigter erledigt); offene, die der Lauf nicht mehr findet, entfallen
        (sie waren abgeleitet, nie entschieden). Entschiedene bleiben als Spur.
        """
        am = am if am is not None else time.time()
        neu = 0
        with self._lock, self._conn:
            vorhanden = {z['id']: z['status'] for z in self._conn.execute('SELECT id, status FROM befund')}
            gefunden = set()
            for befund in befunde:
                kennung = befund.schluessel
                gefunden.add(kennung)
                felder = (json.dumps(list(befund.sachen), ensure_ascii=False),
                          json.dumps([b.to_dict() for b in befund.belege], ensure_ascii=False), befund.text,
                          json.dumps([list(w) for w in befund.werte], ensure_ascii=False),
                          json.dumps([e.to_dict() for e in befund.entwuerfe], ensure_ascii=False))
                if kennung in vorhanden:
                    self._conn.execute('UPDATE befund SET sachen=?, belege=?, text=?, werte=?, entwuerfe=?, gesehen_am=? '
                                       'WHERE id=?', (*felder, am, kennung))
                else:
                    self._conn.execute(
                        'INSERT INTO befund (id, art, unterart, schwere, sachen, belege, text, werte, entwuerfe, '
                        'gefunden_am, gesehen_am) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (kennung, befund.art, befund.unterart, befund.schwere, *felder, am, am))
                    neu += 1
            weg = [k for k, status in vorhanden.items() if status == 'offen' and k not in gefunden]
            for kennung in weg:
                self._conn.execute('DELETE FROM befund WHERE id = ?', (kennung,))
            self._conn.execute('INSERT INTO lint_lauf VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET am=excluded.am, '
                               'dauer_s=excluded.dauer_s, sachen=excluded.sachen, neu=excluded.neu',
                               (am, dauer_s, sachen, neu))
        return {'neu': neu, 'entfallen': len(weg), 'gesamt': len(gefunden)}

    def vorschlaege_setzen(self, kennung: str, vorschlaege: list[dict[str, str]]) -> None:
        with self._lock, self._conn:
            self._conn.execute('UPDATE befund SET vorschlaege = ? WHERE id = ?',
                               (json.dumps(vorschlaege, ensure_ascii=False), kennung))

    def status_setzen(self, kennung: str, status: str, *, entschieden: str = 'nutzer',
                      am: float | None = None) -> dict[str, Any] | None:
        if status not in STATI:
            raise ValueError('Unbekannter Status.')
        with self._lock, self._conn:
            geaendert = self._conn.execute(
                'UPDATE befund SET status = ?, entschieden = ?, entschieden_am = ? WHERE id = ?',
                (status, entschieden if status != 'offen' else '', (am or time.time()) if status != 'offen' else None,
                 kennung)).rowcount
        return self.get(kennung) if geaendert else None

    @staticmethod
    def _zeile(z: sqlite3.Row) -> dict[str, Any]:
        return {'id': z['id'], 'art': z['art'], 'art_text': ART_TEXTE[z['art']], 'unterart': z['unterart'],
                'schwere': z['schwere'], 'sachen': json.loads(z['sachen']), 'belege': json.loads(z['belege']),
                'text': z['text'], 'werte': {k: v for k, v in json.loads(z['werte'])},
                'entwuerfe': json.loads(z['entwuerfe']), 'vorschlaege': json.loads(z['vorschlaege']),
                'status': z['status'], 'entschieden': z['entschieden'],
                'gefunden_am': datetime.fromtimestamp(z['gefunden_am'], timezone.utc).isoformat(),
                'entschieden_am': (datetime.fromtimestamp(z['entschieden_am'], timezone.utc).isoformat()
                                   if z['entschieden_am'] else None)}

    def get(self, kennung: str) -> dict[str, Any] | None:
        with self._lock:
            z = self._conn.execute('SELECT * FROM befund WHERE id = ?', (kennung,)).fetchone()
        return self._zeile(z) if z else None

    def liste(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """Befunde, wichtige zuerst, dann jüngste."""
        sql, parameter = 'SELECT * FROM befund', []
        if status is not None:
            sql += ' WHERE status = ?'
            parameter.append(status)
        sql += " ORDER BY CASE schwere WHEN 'wichtig' THEN 0 ELSE 1 END, gefunden_am DESC, id"
        with self._lock:
            return [self._zeile(z) for z in self._conn.execute(sql, parameter)]

    def letzter_lauf(self) -> dict[str, Any] | None:
        with self._lock:
            z = self._conn.execute('SELECT am, dauer_s, sachen, neu FROM lint_lauf WHERE id = 1').fetchone()
        return {'am': datetime.fromtimestamp(z['am'], timezone.utc).isoformat(), 'dauer_s': z['dauer_s'],
                'sachen': z['sachen'], 'neu': z['neu'], '_am': z['am']} if z else None

    def zaehlen(self) -> dict[str, Any]:
        with self._lock:
            zeilen = self._conn.execute(
                "SELECT art, schwere, COUNT(*) AS n, SUM(CASE WHEN gefunden_am >= COALESCE((SELECT am FROM lint_lauf "
                "WHERE id = 1), 0) THEN 1 ELSE 0 END) AS neu FROM befund WHERE status = 'offen' GROUP BY art, schwere"
            ).fetchall()
        je_art = {art: 0 for art in ARTEN}
        wichtig = neu = 0
        for z in zeilen:
            je_art[z['art']] += z['n']
            wichtig += z['n'] if z['schwere'] == 'wichtig' else 0
            neu += z['neu'] or 0
        lauf = self.letzter_lauf()
        return {'offen': sum(je_art.values()), 'wichtig': wichtig, 'je_art': je_art,
                'neu_seit_letztem_lauf': neu, 'letzter_lauf': lauf['am'] if lauf else None}


def _leer() -> dict[str, Any]:
    return {'offen': 0, 'wichtig': 0, 'je_art': {art: 0 for art in ARTEN}, 'neu_seit_letztem_lauf': 0,
            'letzter_lauf': None}


def zusammenfassung(quelle: Any = None) -> dict[str, Any]:
    """Offene Befunde je Art für Briefing und Logbuch. Stabile Signatur, siehe Modulkopf. Wirft nie."""
    ablage = quelle if isinstance(quelle, Befunde) else getattr(getattr(quelle, 'state', None), 'lint_befunde', None)
    if ablage is None:
        return _leer()
    try:
        return ablage.zaehlen()
    except Exception:  # noqa: BLE001 - eine kaputte Ablage darf das Briefing nie kippen
        return _leer()


__all__ = ['ARTEN', 'ART_TEXTE', 'Beleg', 'Befund', 'Befunde', 'Entwurf', 'LintErgebnis', 'Pruefer', 'SCHWEREN',
           'STATI', 'vorschlagen', 'werte', 'widerspruechliche_sorten', 'zusammenfassung']
