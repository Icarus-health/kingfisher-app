"""Zuordnung einer Mitschrift zu ihrem Termin, und ihrer Sprecher zu Personen.

Eine Mitschrift ist eine Quelle für sich (`transkript_eingang.py`). Zu wissen,
**welcher Termin** es war, macht sie erst nutzbar: Sie erscheint bei der
Nachbereitung, im Termin, in den Akten der Teilnehmer. Geraten wird dabei nie.

## Zeichen und Punkte

Jeder Termin um die Mitschrift herum bekommt Punkte aus vier Zeichen:

| Zeichen | Punkte |
|---|---|
| Uhrzeit aus Dateiname oder Kopf liegt im Termin (bis 15 Minuten vor Beginn) | 3 |
| gleicher Tag laut Datei, oder Datei kurz nach dem Termin geschrieben | 1 |
| ein Wort des Titels stimmt überein (die Hälfte und mehr der Titelwörter: 3) | 2 (3) |
| ein Sprecher stimmt mit einem Teilnehmer überein (höchstens zwei zählen) | je 1 |

Steht in der Datei eine Uhrzeit oder ein Tag, der **nicht** zum Termin passt,
entfällt der Termin ganz. Der Dateizeitpunkt allein schließt keinen aus: Ein
Export darf Tage später entstehen.

## Entscheidung

* **zugeordnet**, wenn der beste Termin mindestens 3 Punkte hat und entweder
  allein steht oder mindestens 2 Punkte Abstand zum zweiten hat. Die Zuordnung
  ist ein Bezug der Quelle, jederzeit zu lösen oder zu ändern, und trägt ihre
  Gründe.
* **vorschlag**, wenn der beste mindestens 2 Punkte hat, aber nicht eindeutig
  ist. Die besten drei stehen zur Wahl; ein Klick entscheidet.
* **allein** sonst. Die Mitschrift steht für sich und wird bei Bedarf von Hand
  zugeordnet.

Was der Nutzer entschieden hat (`von = 'nutzer'`), überschreibt der Abgleich nie.
Ein gelöster Termin wird nicht erneut vorgeschlagen.

## Sprecher

Nur bei einer **zugeordneten** Mitschrift werden die Sprecher gegen die
Teilnehmerliste des Termins gehalten: voller Name gleich, oder Vorname allein,
wenn genau ein Teilnehmer so heißt. Bei Treffer trägt die Quelle danach die
Adresse als Anker (`Episode.contacts`, dieselbe Regel wie bei Mail); sonst bleibt
der Sprecher ein Name. Zwei Teilnehmer „Anna“ machen aus „Anna“ keine der beiden.

## Ablage

Die Zuordnung ist abgeleitet und liegt in einer eigenen kleinen Datei
(`gespraeche.sqlite3`), nicht im Episodenbestand: Sie speichert Kennungen,
Punkte und die Zeichen aus der Datei, keinen Quelltext. Eine entzogene Quelle
(Ordner getrennt) zählt nirgends mehr, gleich was in der Datei steht.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .calendar_memory import uid_aus_herkunft
from .episodes import Episode, EpisodeError, EpisodeState, EpisodeStore, mail_address
from .identitaet import name_schluessel
from .kontakte import anzeigename
from .migrations import Migration, run_migrations, verify_schema
from .model import user_timezone
from .nachbereitung import schluessel as termin_schluessel
from .transkript_eingang import MARKE

VORLAUF = timedelta(minutes=15)
"""So früh vor dem Beginn darf eine Aufnahme beginnen und noch zum Termin gehören."""

NACHLAUF_DATEI = timedelta(hours=4)
"""So lange nach dem Ende gilt eine Datei noch als „kurz danach geschrieben“."""

SCHWELLE_ZUGEORDNET = 3
SCHWELLE_VORSCHLAG = 2
ABSTAND = 2
MAX_VORSCHLAEGE = 3

_UNBEDEUTEND = frozenset({
    'meeting', 'besprechung', 'termin', 'call', 'transkript', 'transcript', 'aufzeichnung', 'recording',
    'mitschrift', 'video', 'audio', 'notizen', 'protokoll', 'teams', 'zoom', 'meet', 'google', 'webex',
    'gespräch', 'gespraech', 'telefonat', 'und', 'der', 'die', 'das', 'mit', 'von', 'für', 'fuer', 'the',
    'and', 'with', 'for', 'untitled', 'ohne', 'titel',
})


# -- Termine aus dem Gedächtnis ----------------------------------------------


@dataclass(frozen=True)
class Termin:
    """Ein Termin aus dem Gedächtnis (Episode der Art `event`)."""

    key: str
    uid: str
    start: datetime
    ende: datetime
    titel: str
    teilnehmer: tuple[str, ...]
    episode_id: str

    def kurz(self) -> dict[str, Any]:
        return {'key': self.key, 'uid': self.uid, 'start': self.start.isoformat(),
                'ende': self.ende.isoformat(), 'titel': self.titel}


_WANN = re.compile(r'^Wann:[ \t]*(.+)$', re.M)
_KLAMMERDATUM = re.compile(r'\((\d{2})\.(\d{2})\.(\d{4})\)')
_UHR = re.compile(r'(?<!\d)(\d{2}):(\d{2})(?!\d)')


def _ende_aus_text(start: datetime, body: str) -> datetime:
    """Das Ende, wie `calendar_memory.termin_text` es schreibt; ohne Angabe eine Stunde nach dem Beginn."""
    standard = start + timedelta(hours=1)
    zeile = _WANN.search(body)
    if not zeile or 'ganztägig' in zeile.group(1):
        return standard
    daten, zeiten = _KLAMMERDATUM.findall(zeile.group(1)), _UHR.findall(zeile.group(1))
    if len(zeiten) < 2 or not daten:
        return standard
    tag, monat, jahr = (int(x) for x in (daten[1] if len(daten) > 1 else daten[0]))
    try:
        ende = datetime(jahr, monat, tag, int(zeiten[1][0]), int(zeiten[1][1]), tzinfo=user_timezone() or timezone.utc)
    except ValueError:
        return standard
    return ende if ende > start else standard


def _termin(episode: Episode) -> Termin | None:
    uid = uid_aus_herkunft(episode.provenance.source_ref)
    start = episode.occurred_at
    if not uid or start is None or start.tzinfo is None:
        return None
    wann = _WANN.search(episode.body)
    if wann and 'ganztägig' in wann.group(1):
        return None
    schluessel = termin_schluessel(uid, start)
    if schluessel is None:
        return None
    titel = episode.title.strip() or 'Termin'
    return Termin(schluessel, uid, start, _ende_aus_text(start, episode.body), titel,
                  tuple(episode.participants), episode.id)


def termine_zwischen(episodes: EpisodeStore, von: datetime, bis: datetime) -> list[Termin]:
    """Die geltenden, nicht ganztägigen Termine mit Beginn in [von, bis]."""
    return [t for t in (_termin(e) for e in episodes.events_between(von, bis)) if t is not None]


def termin_zu(episodes: EpisodeStore, key: str) -> Termin | None:
    """Der Termin zu einem Schlüssel („Kennung|Beginn in UTC“), sonst nichts."""
    uid, _, beginn = key.rpartition('|')
    try:
        start = datetime.fromisoformat(beginn)
    except ValueError:
        return None
    if not uid or start.tzinfo is None:
        return None
    for termin in termine_zwischen(episodes, start - timedelta(minutes=1), start + timedelta(minutes=1)):
        if termin.key == key:
            return termin
    return None


# -- Bewertung ---------------------------------------------------------------


def _zeit(wert: Any) -> datetime | None:
    if isinstance(wert, datetime):
        return wert
    try:
        moment = datetime.fromisoformat(str(wert or '').replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=user_timezone() or timezone.utc)


def _tag_von(moment: datetime) -> date:
    return moment.astimezone(user_timezone() or timezone.utc).date()


def _woerter(text: str) -> set[str]:
    rohe = re.findall(r'[^\W_]{3,}', str(text or '').casefold())
    return {wort for wort in rohe if wort not in _UNBEDEUTEND and not wort.isdigit()}


def _vorname(name: str) -> str:
    teile = name_schluessel(name).split()
    return teile[0] if teile else ''


def sprecher_zu_teilnehmern(sprecher: Iterable[str], teilnehmer: Iterable[str]) -> dict[str, str | None]:
    """Welcher Sprecher zu welchem Teilnehmer gehört (`Name <adresse>`), nur bei Eindeutigkeit.

    Voller Name gleich; sonst der Vorname allein, wenn genau ein Teilnehmer so
    heißt und der Sprecher nur aus dem Vornamen besteht. Sonst `None`.
    """
    eintraege: list[tuple[str, str, str]] = []
    for text in teilnehmer:
        adresse = mail_address(text)
        name = anzeigename(text) if adresse else str(text).strip()
        if not name and adresse:
            # Teams und Meet liefern oft nur die Adresse: „anna.berg@x“ trägt „Anna Berg“.
            name = re.sub(r'[._-]+', ' ', adresse.split('@')[0]).strip()
        if name_schluessel(name):
            eintraege.append((name, adresse, str(text)))
    ergebnis: dict[str, str | None] = {}
    for name in sprecher:
        schluessel = name_schluessel(name)
        treffer = [e for e in eintraege if name_schluessel(e[0]) == schluessel]
        if not treffer and len(schluessel.split()) == 1:
            treffer = [e for e in eintraege if _vorname(e[0]) == schluessel]
        personen = {adresse or name_schluessel(n) for n, adresse, _ in treffer}
        ergebnis[name] = treffer[0][2] if treffer and len(personen) == 1 else None
    return ergebnis


@dataclass
class Bewertung:
    termin: Termin
    punkte: int
    gruende: list[str]

    def kurz(self) -> dict[str, Any]:
        return {**self.termin.kurz(), 'punkte': self.punkte, 'gruende': list(self.gruende)}


def bewerten(hinweise: dict[str, Any], termin: Termin) -> Bewertung | None:
    """Punkte eines Termins für eine Mitschrift; `None`, wenn die Datei ihm widerspricht."""
    beginn, geaendert = _zeit(hinweise.get('beginn')), _zeit(hinweise.get('geaendert'))
    tag = None
    if hinweise.get('tag'):
        try:
            tag = date.fromisoformat(str(hinweise['tag']))
        except ValueError:
            tag = None
    punkte, gruende = 0, []
    if beginn is not None:
        if termin.start - VORLAUF <= beginn <= termin.ende:
            punkte, gruende = 3, ['Die Uhrzeit der Mitschrift liegt im Termin.']
        elif _tag_von(beginn) == _tag_von(termin.start):
            punkte, gruende = 1, ['Gleicher Tag.']
        else:
            return None
    elif tag is not None:
        if tag != _tag_von(termin.start):
            return None
        punkte, gruende = 1, ['Gleicher Tag.']
    elif geaendert is not None and termin.start <= geaendert <= termin.ende + NACHLAUF_DATEI:
        punkte, gruende = 1, ['Die Datei wurde kurz nach dem Termin geschrieben.']
    titel_woerter = _woerter(hinweise.get('titel', ''))
    gemeinsam = titel_woerter & _woerter(termin.titel)
    if gemeinsam:
        stark = len(gemeinsam) * 2 >= len(titel_woerter)
        punkte += 3 if stark else 2
        gruende.append('Der Titel passt: ' + ', '.join(sorted(gemeinsam)) + '.')
    treffer = [n for n, t in sprecher_zu_teilnehmern(hinweise.get('sprecher') or (), termin.teilnehmer).items() if t]
    if treffer:
        punkte += min(2, len(treffer))
        gruende.append('Sprecher unter den Teilnehmern: ' + ', '.join(treffer[:3]) + '.')
    return Bewertung(termin, punkte, gruende) if punkte >= 1 else None


@dataclass
class Ergebnis:
    status: str
    termin: Termin | None
    kandidaten: list[Bewertung]
    gruende: list[str]


def entscheiden(hinweise: dict[str, Any], termine: Iterable[Termin], abgelehnt: Iterable[str] = ()) -> Ergebnis:
    """Die Entscheidung nach den Regeln im Modulkopf, ohne etwas zu speichern."""
    verneint = set(abgelehnt)
    bewertungen = [b for b in (bewerten(hinweise, t) for t in termine if t.key not in verneint) if b is not None]
    bewertungen.sort(key=lambda b: (-b.punkte, -b.termin.start.timestamp()))
    if not bewertungen or bewertungen[0].punkte < SCHWELLE_VORSCHLAG:
        return Ergebnis('allein', None, [], [])
    bester = bewertungen[0]
    zweiter = bewertungen[1].punkte if len(bewertungen) > 1 else None
    if bester.punkte >= SCHWELLE_ZUGEORDNET and (zweiter is None or bester.punkte - zweiter >= ABSTAND):
        return Ergebnis('zugeordnet', bester.termin, [bester], bester.gruende)
    vorschlaege = [b for b in bewertungen if b.punkte >= SCHWELLE_VORSCHLAG][:MAX_VORSCHLAEGE]
    return Ergebnis('vorschlag', None, vorschlaege, [])


# -- Ablage ------------------------------------------------------------------

_TABELLEN_V1 = {'zuordnung': {'episode_id', 'status', 'termin', 'von', 'hinweise', 'kandidaten', 'gruende',
                              'abgelehnt', 'aktualisiert'}}
_TABELLEN = {'zuordnung': _TABELLEN_V1['zuordnung'] | {'uebernommen'}}
_SCHLUESSEL = {'zuordnung': {'episode_id'}}


def _migrieren(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE zuordnung (
        episode_id TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK(status IN ('zugeordnet','vorschlag','allein')),
        termin TEXT NOT NULL DEFAULT '',
        von TEXT NOT NULL CHECK(von IN ('auto','nutzer')),
        hinweise TEXT NOT NULL,
        kandidaten TEXT NOT NULL DEFAULT '[]',
        gruende TEXT NOT NULL DEFAULT '[]',
        abgelehnt TEXT NOT NULL DEFAULT '[]',
        aktualisiert REAL NOT NULL)""")
    conn.execute('CREATE INDEX idx_zuordnung_termin ON zuordnung(termin)')


def _migrieren_v2(conn: sqlite3.Connection) -> None:
    """Merkt je Mitschrift, was die bestätigte Zuordnung in die Quelle übernommen hat, damit Lösen es zurücknimmt."""
    conn.execute("ALTER TABLE zuordnung ADD COLUMN uebernommen TEXT NOT NULL DEFAULT '{}'")


def _pruefen_mit(tabellen: dict[str, set[str]]) -> Callable[[sqlite3.Connection], None]:
    def pruefen(conn: sqlite3.Connection) -> None:
        from .migrations import IndexContract
        verify_schema(conn, expected_tables=tabellen, expected_primary_keys=_SCHLUESSEL,
                      expected_indexes={'idx_zuordnung_termin': IndexContract('zuordnung', ('termin',))})
    return pruefen


_MIGRATIONS = (Migration(1, 'zuordnung', _migrieren, _pruefen_mit(_TABELLEN_V1)),
               Migration(2, 'uebernahme_merken', _migrieren_v2, _pruefen_mit(_TABELLEN)))


class Zuordnungen:
    """Die abgeleitete Ablage der Zuordnungen (eigene Datei, eigene Versionierung)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            run_migrations(self._conn, store='gespraeche', path=self._path, migrations=_MIGRATIONS)
        except Exception:
            self._conn.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def zeile(self, episode_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute('SELECT * FROM zuordnung WHERE episode_id = ?', (episode_id,)).fetchone()
        return self._lesen(row) if row else None

    def zeilen(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        liste = list(ids)
        ergebnis: dict[str, dict[str, Any]] = {}
        with self._lock:
            for start in range(0, len(liste), 500):
                teil = liste[start:start + 500]
                for row in self._conn.execute(
                        f"SELECT * FROM zuordnung WHERE episode_id IN ({','.join('?' * len(teil))})", teil):
                    ergebnis[row['episode_id']] = self._lesen(row)
        return ergebnis

    def zum_termin(self, key: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT episode_id FROM zuordnung WHERE termin = ? AND status = 'zugeordnet' "
                "ORDER BY aktualisiert", (key,)).fetchall()
        return [row[0] for row in rows]

    def uebernahme_merken(self, episode_id: str, uebernommen: dict[str, Any]) -> None:
        """Was eine bestätigte Zuordnung in die Quelle geschrieben hat (Kontakte, Texte, Projekt)."""
        with self._lock:
            self._conn.execute("UPDATE zuordnung SET uebernommen = ? WHERE episode_id = ?",
                               (json.dumps(uebernommen, ensure_ascii=False), episode_id))
            self._conn.commit()

    def schreiben(self, episode_id: str, *, status: str, termin: str, von: str, hinweise: dict[str, Any],
                  kandidaten: list[dict[str, Any]], gruende: list[str], abgelehnt: list[str]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO zuordnung(episode_id,status,termin,von,hinweise,kandidaten,gruende,abgelehnt,aktualisiert) "
                "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(episode_id) DO UPDATE SET status=excluded.status, "
                "termin=excluded.termin, von=excluded.von, hinweise=excluded.hinweise, "
                "kandidaten=excluded.kandidaten, gruende=excluded.gruende, abgelehnt=excluded.abgelehnt, "
                "aktualisiert=excluded.aktualisiert",
                (episode_id, status, termin, von, json.dumps(hinweise, ensure_ascii=False),
                 json.dumps(kandidaten, ensure_ascii=False), json.dumps(gruende, ensure_ascii=False),
                 json.dumps(abgelehnt), time.time()))
            self._conn.commit()

    @staticmethod
    def _lesen(row: sqlite3.Row) -> dict[str, Any]:
        return {'episode_id': row['episode_id'], 'status': row['status'], 'termin': row['termin'],
                'von': row['von'], 'hinweise': json.loads(row['hinweise']),
                'kandidaten': json.loads(row['kandidaten']), 'gruende': json.loads(row['gruende']),
                'abgelehnt': json.loads(row['abgelehnt']), 'uebernommen': json.loads(row['uebernommen'])}


# -- Zuordner ----------------------------------------------------------------


def _bezugsmoment(hinweise: dict[str, Any], episode: Episode) -> datetime:
    return (_zeit(hinweise.get('beginn')) or _zeit(hinweise.get('geaendert'))
            or episode.occurred_at or episode.recorded_at)


def _fenster(hinweise: dict[str, Any], episode: Episode) -> tuple[datetime, datetime]:
    beginn = _zeit(hinweise.get('beginn'))
    if beginn is not None:
        return beginn - timedelta(days=1), beginn + timedelta(days=1)
    if hinweise.get('tag'):
        try:
            tag = date.fromisoformat(str(hinweise['tag']))
            mitte = datetime(tag.year, tag.month, tag.day, 12, tzinfo=user_timezone() or timezone.utc)
            return mitte - timedelta(days=1), mitte + timedelta(days=1)
        except ValueError:
            pass
    moment = _bezugsmoment(hinweise, episode)
    return moment - timedelta(days=7), moment + timedelta(hours=1)


class Zuordner:
    """Verbindet Mitschriften mit Terminen; die einzige Stelle, die entscheidet und schreibt."""

    def __init__(self, episodes: EpisodeStore, ablage: Zuordnungen, *,
                 eigene: Callable[[], list[str]] = lambda: [],
                 termin_projekt: Callable[[str], tuple[bool, str | None]] | None = None) -> None:
        self.episodes = episodes
        self.ablage = ablage
        self._eigene = eigene
        self._termin_projekt = termin_projekt
        self._lock = threading.RLock()

    # -- Aufnehmen und Abgleichen ---------------------------------------

    def vormerken(self, episode: Episode, hinweise: dict[str, Any]) -> dict[str, Any]:
        """Merkt die Zeichen einer aufgenommenen Mitschrift und gleicht sofort ab."""
        with self._lock:
            alt = self.ablage.zeile(episode.id)
            if alt is None:
                self.ablage.schreiben(episode.id, status='allein', termin='', von='auto', hinweise=hinweise,
                                      kandidaten=[], gruende=[], abgelehnt=[])
            elif alt['hinweise'] != hinweise:
                self.ablage.schreiben(episode.id, status=alt['status'], termin=alt['termin'], von=alt['von'],
                                      hinweise=hinweise, kandidaten=alt['kandidaten'], gruende=alt['gruende'],
                                      abgelehnt=alt['abgelehnt'])
            return self.abgleichen(episode.id)

    def _hinweise_aus_quelle(self, episode: Episode) -> dict[str, Any]:
        """Zeichen einer Mitschrift ohne gemerkte Angaben (etwa über den Ordneradapter aufgenommen)."""
        return {'titel': episode.title.removeprefix('Mitschrift: '), 'sprecher': [p for p in episode.participants
                if not mail_address(p)], 'beginn': episode.occurred_at.isoformat() if episode.occurred_at else None,
                'tag': None, 'zeit_quelle': '', 'geaendert': episode.recorded_at.isoformat()}

    def abgleichen(self, episode_id: str) -> dict[str, Any]:
        """Bestimmt Termin und Sprecher neu, außer der Nutzer hat entschieden."""
        with self._lock:
            episode = self.episodes.get(episode_id)
            zeile = self.ablage.zeile(episode_id)
            hinweise = zeile['hinweise'] if zeile else self._hinweise_aus_quelle(episode)
            if zeile is not None and zeile['von'] == 'nutzer':
                return zeile
            if episode.state is EpisodeState.IGNORED:
                return zeile or {'episode_id': episode_id, 'status': 'allein', 'termin': '', 'von': 'auto'}
            abgelehnt = zeile['abgelehnt'] if zeile else []
            von, bis = _fenster(hinweise, episode)
            ergebnis = entscheiden(hinweise, termine_zwischen(self.episodes, von, bis), abgelehnt)
            self.ablage.schreiben(
                episode_id, status=ergebnis.status, termin=ergebnis.termin.key if ergebnis.termin else '',
                von='auto', hinweise=hinweise, kandidaten=[b.kurz() for b in ergebnis.kandidaten],
                gruende=ergebnis.gruende, abgelehnt=abgelehnt)
            return self.ablage.zeile(episode_id) or {}

    def nachziehen(self, *, limit: int = 200) -> int:
        """Gleicht alle Mitschriften ab, über deren Termin noch nicht entschieden ist. Gibt die Zahl der Änderungen."""
        geaendert = 0
        with self._lock:
            episoden = self.episodes.tagged(MARKE, limit=limit)
            vorhandene = self.ablage.zeilen(e.id for e in episoden)
            for episode in episoden:
                zeile = vorhandene.get(episode.id)
                if zeile is not None and zeile['von'] == 'nutzer':
                    continue
                if zeile is not None and zeile['status'] == 'zugeordnet':
                    continue  # eine eindeutige Zuordnung bleibt, bis jemand sie löst
                vorher = (zeile['status'], zeile['termin'], [k['key'] for k in zeile['kandidaten']]) if zeile else None
                neu = self.abgleichen(episode.id)
                nachher = (neu.get('status'), neu.get('termin'), [k['key'] for k in neu.get('kandidaten', [])])
                geaendert += int(vorher != nachher)
        return geaendert

    # -- Entscheidungen des Nutzers -------------------------------------

    def bestaetigen(self, episode_id: str, key: str) -> dict[str, Any]:
        """Der Nutzer wählt den Termin (aus dem Vorschlag oder von Hand). Gilt, bis er es ändert."""
        with self._lock:
            episode = self.episodes.get(episode_id)
            if episode.state is EpisodeState.IGNORED or MARKE not in episode.tags:
                raise EpisodeError('Diese Mitschrift ist nicht mehr gültig.')
            termin = termin_zu(self.episodes, key)
            if termin is None:
                raise EpisodeError('Der Termin ist im Gedächtnis nicht mehr zu finden.')
            zeile = self.ablage.zeile(episode_id)
            hinweise = zeile['hinweise'] if zeile else self._hinweise_aus_quelle(episode)
            bewertung = bewerten(hinweise, termin)
            self._uebernahme_zuruecknehmen(episode, zeile)  # eine frühere Bestätigung gilt für einen anderen Termin
            self.ablage.schreiben(
                episode_id, status='zugeordnet', termin=termin.key, von='nutzer', hinweise=hinweise,
                kandidaten=[], gruende=['Von dir gewählt.'] + (bewertung.gruende if bewertung else []),
                abgelehnt=[k for k in (zeile['abgelehnt'] if zeile else []) if k != termin.key])
            self._sprecher_uebernehmen(episode, termin, hinweise)
            return self.ablage.zeile(episode_id) or {}

    def loesen(self, episode_id: str) -> dict[str, Any]:
        """Nimmt die Zuordnung zurück. Der Termin wird für diese Mitschrift nicht erneut vorgeschlagen."""
        with self._lock:
            episode = self.episodes.get(episode_id)
            if MARKE not in episode.tags:
                raise EpisodeError('Das ist keine Mitschrift.')
            zeile = self.ablage.zeile(episode_id)
            hinweise = zeile['hinweise'] if zeile else self._hinweise_aus_quelle(episode)
            abgelehnt = list(zeile['abgelehnt']) if zeile else []
            self._uebernahme_zuruecknehmen(episode, zeile)
            if zeile and zeile['termin'] and zeile['termin'] not in abgelehnt:
                abgelehnt.append(zeile['termin'])
            self.ablage.schreiben(episode_id, status='allein', termin='', von='nutzer', hinweise=hinweise,
                                  kandidaten=[], gruende=[], abgelehnt=abgelehnt)
            return self.ablage.zeile(episode_id) or {}

    # -- Sprecher als Personen ------------------------------------------

    def _sprecher_uebernehmen(self, episode: Episode, termin: Termin, hinweise: dict[str, Any]) -> None:
        """Trägt Sprecher als Beteiligte ein: mit Adresse, wo eindeutig, sonst als Name.

        Nur nach der Bestätigung durch den Nutzer (`bestaetigen`); eine automatische Zuordnung
        bleibt ein Vorschlag und schreibt nichts in die Quelle („Verdichtung schlägt vor, sie
        schreibt nicht“). Was hinzukommt, wird gemerkt (`uebernommen`), damit `loesen` es wieder
        entfernt: nur das Hinzugefügte, nie, was schon vorher in der Quelle stand.
        """
        sprecher = [str(s) for s in hinweise.get('sprecher') or [] if str(s).strip()]
        if not sprecher:
            return
        selbst = {mail_address(a) for a in self._eigene() if mail_address(a)}
        zuordnung = sprecher_zu_teilnehmern(sprecher, termin.teilnehmer)
        kontakte, texte = [], []
        for name in sprecher:
            text = zuordnung.get(name)
            adresse = mail_address(text) if text else ''
            anzeige = (anzeigename(text) if text else '') or name
            kontakte.append({'name': anzeige, 'adresse': adresse, 'rolle': 'beteiligt',
                             'ich': bool(adresse and adresse in selbst)})
            texte.append(f'{anzeige} <{adresse}>' if adresse else anzeige)
        try:
            vorher = self.episodes.get(episode.id)
            schluessel = lambda c: (c.get('adresse') or (c.get('name') or '').casefold(), c.get('rolle'))  # noqa: E731
            bekannt = {schluessel(c) for c in vorher.contacts}
            neue_kontakte = [c for c in kontakte if schluessel(c) not in bekannt]
            neue_texte = [t for t in texte if t not in vorher.participants]
            self.episodes.add_contacts(episode.id, kontakte, texte)
            projekt = None
            if self._termin_projekt is not None and vorher.project_id is None:
                gewaehlt, gefunden = self._termin_projekt(termin.uid)
                if gewaehlt and gefunden:
                    self.episodes.link_project(episode.id, gefunden)
                    projekt = gefunden
            self.ablage.uebernahme_merken(episode.id, {'kontakte': neue_kontakte, 'texte': neue_texte,
                                                       'projekt': projekt})
        except EpisodeError:
            return

    def _uebernahme_zuruecknehmen(self, episode: Episode, zeile: dict[str, Any] | None) -> None:
        """Nimmt zurück, was eine bestätigte Zuordnung übernommen hatte (Kontakte, Texte, Projekt)."""
        uebernommen = (zeile or {}).get('uebernommen') or {}
        if not uebernommen:
            return
        try:
            if uebernommen.get('kontakte') or uebernommen.get('texte'):
                self.episodes.remove_contacts(episode.id, uebernommen.get('kontakte') or [],
                                              uebernommen.get('texte') or [])
            if uebernommen.get('projekt') and self.episodes.get(episode.id).project_id == uebernommen['projekt']:
                self.episodes.link_project(episode.id, None)
        except EpisodeError:
            pass
        self.ablage.uebernahme_merken(episode.id, {})

    # -- Auskunft --------------------------------------------------------

    def _eintrag(self, episode: Episode, zeile: dict[str, Any] | None) -> dict[str, Any]:
        zeile = zeile or {'status': 'allein', 'termin': '', 'von': 'auto', 'kandidaten': [], 'gruende': [],
                          'hinweise': {}}
        termin = termin_zu(self.episodes, zeile['termin']) if zeile['termin'] else None
        sprecher = list((zeile.get('hinweise') or {}).get('sprecher') or [])
        return {
            'id': episode.id, 'titel': episode.title.removeprefix('Mitschrift: '),
            'aufgenommen': episode.recorded_at.isoformat(), 'status': zeile['status'], 'von': zeile['von'],
            'termin': termin.kurz() if termin else None, 'gruende': zeile['gruende'],
            'kandidaten': zeile['kandidaten'], 'sprecher': sprecher,
            'personen': ({n: bool(t) for n, t in sprecher_zu_teilnehmern(sprecher, termin.teilnehmer).items()}
                         if termin and zeile['status'] == 'zugeordnet' else {}),
        }

    def eintraege(self, *, limit: int = 100) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Die Mitschriften (neueste zuerst) mit ihrem Stand und die Zähler über **alle**."""
        episoden = self.episodes.tagged(MARKE, limit=5000)
        zeilen = self.ablage.zeilen(e.id for e in episoden)
        zaehler = {'aufgenommen': len(episoden), 'zugeordnet': 0, 'vorschlag': 0, 'offen': 0}
        for episode in episoden:
            status = (zeilen.get(episode.id) or {}).get('status', 'allein')
            if status == 'zugeordnet':
                zaehler['zugeordnet'] += 1
            else:
                zaehler['offen'] += 1
                zaehler['vorschlag'] += int(status == 'vorschlag')
        return [self._eintrag(e, zeilen.get(e.id)) for e in episoden[:limit]], zaehler

    def fuer_termin(self, key: str) -> list[dict[str, Any]]:
        """Die dem Termin zugeordneten Mitschriften, ohne entzogene."""
        ergebnis = []
        for episode_id in self.ablage.zum_termin(key):
            try:
                episode = self.episodes.get(episode_id)
            except EpisodeError:
                continue
            if episode.state is not EpisodeState.IGNORED:
                ergebnis.append(self._eintrag(episode, self.ablage.zeile(episode_id)))
        return ergebnis

    def angebote(self, key: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Mitschriften ohne Termin, die für diesen Termin infrage kommen (Vorschlag zuerst, dann die übrigen)."""
        eintraege, _ = self.eintraege(limit=200)
        frei = [e for e in eintraege if e['status'] != 'zugeordnet']
        frei.sort(key=lambda e: (0 if any(k['key'] == key for k in e['kandidaten']) else 1))
        return frei[:limit]


__all__ = ['Bewertung', 'Ergebnis', 'Termin', 'Zuordner', 'Zuordnungen', 'bewerten', 'entscheiden',
           'sprecher_zu_teilnehmern', 'termin_zu', 'termine_zwischen']
