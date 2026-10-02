"""Bezüge (Etappe D1): Welche Sachen berührt eine Quelle?

Das Gedächtnis ist eine Schichtablage (`docs/27-schichten-und-fragen.md`):
Ebene 0 sind die Quellen, Ebene 1 der Auszug je Quelle, Ebene 2 die Akte je
**Sache**. Sachen sind Person, Organisation, Projekt, Ort und Thema. Dieses
Modul knüpft die Verbindung von unten nach oben: Jede Quelle trägt Bezüge, und
aus den Bezügen entstehen die Akten (`akten.py`).

Eine Verknüpfung (`Bezug`) trägt immer ihre Grundlage:

| Grundlage | Woher | Sicherheit |
|---|---|---|
| `anker` | Adresse als Absender, Empfänger oder Gast (Person, dazu die Organisation aus der Domäne), Projektzuordnung der Quelle, Ort eines Termins, ein Name ohne Adresse, den genau eine Adresse trägt (`identitaet.py`) | sicher, ohne Rückfrage |
| `modell` | Erwähnung aus `memory_categories` (Person, Organisation, Projekt, Ort) mit Textstelle, Thema mit Belegstelle | vorgeschlagen, korrigierbar |
| `nutzer` | Zuordnung oder Ablehnung per Klick, Themenkorrektur | maßgeblich, überschreibt Modell und Anker |

Regeln:

* **Abgeleitet, nie Fakt.** Die Tabelle `sach_bezuege` ist jederzeit aus den
  Quellen, `memory_categories` und dem Verzeichnis neu berechenbar. Gespeichert
  werden Kennungen, Zeichenpositionen und Grundlage, **kein Quelltext**. Namen und
  Zitate liest jede Anzeige aus dem Original (`beschriftung`, `zitat`).
* **Mit Fingerabdruck.** Jede Zeile trägt den Fingerabdruck der Quelle
  (Digest, Metadaten, Bearbeitungszähler, Länge). Ändert sich die Quelle, gilt sie
  als nicht berechnet und wird beim nächsten Abgleich neu bestimmt. Eine Zuordnung
  des Nutzers trägt ebenfalls einen Fingerabdruck; nach einer Änderung der Quelle
  ist sie **veraltet** und gilt nicht mehr (wie Themenkorrekturen).
* **Entzug wirkt sofort.** Jede Lesung verbindet mit den geltenden Quellen
  (nicht ausgeschlossen, aktuelle Fassung). Eine entzogene Quelle liefert keinen
  Bezug mehr; ihre Zeilen löscht der nächste Abgleich.
* **Nur bei Eindeutigkeit.** Ein Name ohne Adresse (Notiz, Transkript, Erwähnung im
  Text) wird einer Person nur zugeordnet, wenn genau eine Adresse ihn als Alias
  trägt. Sonst bleibt er **offen** und nennt seine Kandidaten. Geraten wird nie.
* **Nichts still begrenzen.** Listen nennen ihre Gesamtzahl.

Das Verzeichnis (`Register`) wird aus dem Bestand gebaut, wenn er sich geändert
hat. Quellen, deren Bezug von Namen abhängt (`abhaengig`), werden neu bestimmt,
wenn sich das Verzeichnis ändert: Ein zweiter „Alex Winter“ macht aus einer
eindeutigen Zuordnung eine offene.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .episodes import CHAT_LOOKUP_TAG, Episode, EpisodeKind, sql_geltend
from .identitaet import (Nennung, Verzeichnis, domaene, domaenenname, ist_privater_anbieter, name_anker,
                         name_schluessel, nennungen)
from .migrations import IndexContract
from .people_quality import ist_sammelpostfach, lokalteil

ARTEN = ('person', 'organisation', 'projekt', 'ort', 'thema')
ART_TEXT = {'person': 'Person', 'organisation': 'Organisation', 'projekt': 'Projekt', 'ort': 'Ort', 'thema': 'Thema'}
GRUNDLAGEN = ('anker', 'modell', 'nutzer')
#: Art der Erwähnung in `memory_categories` -> Art der Sache.
ART_DER_ERWAEHNUNG = {'person': 'person', 'organization': 'organisation', 'project': 'projekt', 'place': 'ort'}
#: Themen ohne Aussage werden keine Sache.
KEINE_THEMEN = frozenset({'unclear'})

TABLES = {
    'sach_quellen': {'episode_id', 'fingerprint', 'eingabe', 'register', 'berechnet_am'},
    'sach_bezuege': {'episode_id', 'fingerprint', 'sache', 'art', 'grundlage', 'start', 'end', 'rolle',
                     'kandidaten', 'abhaengig'},
    'sach_nutzer': {'episode_id', 'sache', 'art', 'aktion', 'fingerprint', 'updated_at'},
    'akten_cache': {'sache', 'eingabe', 'daten', 'berechnet_am'},
}
PRIMARY_KEYS = {
    'sach_quellen': {'episode_id'},
    'sach_bezuege': {'episode_id', 'sache', 'grundlage', 'start', 'end'},
    'sach_nutzer': {'episode_id', 'sache'},
    'akten_cache': {'sache'},
}
INDEXES = {
    'idx_sach_bezuege_sache': IndexContract('sach_bezuege', ('sache', 'episode_id')),
    'idx_sach_nutzer_sache': IndexContract('sach_nutzer', ('sache', 'episode_id')),
}


def migrate(connection: sqlite3.Connection) -> None:
    """Migration 13: die abgeleiteten Tabellen der Bezüge und der Aktenablage."""
    connection.execute("""CREATE TABLE sach_quellen (
        episode_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, eingabe TEXT NOT NULL,
        register TEXT NOT NULL DEFAULT '', berechnet_am REAL NOT NULL)""")
    connection.execute("""CREATE TABLE sach_bezuege (
        episode_id TEXT NOT NULL, fingerprint TEXT NOT NULL, sache TEXT NOT NULL,
        art TEXT NOT NULL CHECK(art IN ('person','organisation','projekt','ort','thema')),
        grundlage TEXT NOT NULL CHECK(grundlage IN ('anker','modell','nutzer')),
        start INTEGER NOT NULL DEFAULT -1, end INTEGER NOT NULL DEFAULT -1,
        rolle TEXT NOT NULL DEFAULT '', kandidaten TEXT NOT NULL DEFAULT '',
        abhaengig INTEGER NOT NULL DEFAULT 0 CHECK(abhaengig IN (0,1)),
        PRIMARY KEY(episode_id,sache,grundlage,start,end))""")
    connection.execute("CREATE INDEX idx_sach_bezuege_sache ON sach_bezuege(sache, episode_id)")
    connection.execute("""CREATE TABLE sach_nutzer (
        episode_id TEXT NOT NULL, sache TEXT NOT NULL,
        art TEXT NOT NULL CHECK(art IN ('person','organisation','projekt','ort','thema')),
        aktion TEXT NOT NULL CHECK(aktion IN ('zu','nicht')),
        fingerprint TEXT NOT NULL, updated_at REAL NOT NULL,
        PRIMARY KEY(episode_id,sache))""")
    connection.execute("CREATE INDEX idx_sach_nutzer_sache ON sach_nutzer(sache, episode_id)")
    connection.execute("""CREATE TABLE akten_cache (
        sache TEXT PRIMARY KEY, eingabe TEXT NOT NULL, daten TEXT NOT NULL, berechnet_am REAL NOT NULL)""")


def verify(connection: sqlite3.Connection) -> None:
    """Prüft diese Erweiterung allein; `EpisodeStore` prüft das Gesamtschema."""
    for table, expected in TABLES.items():
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        if ({row[1] for row in rows} != expected
                or {row[1] for row in rows if row[5]} != PRIMARY_KEYS[table]):
            raise sqlite3.DatabaseError("Ungültiges Schema für Bezüge und Akten")


# -- Kennungen ---------------------------------------------------------------

_RECHTSFORM = re.compile(r'\b(?:gmbh|mbh|ag|kg|ug|gbr|ohg|se|kgaa|inc|ltd|e\.\s?v\.|co\.)(?=\W|$)', re.I)
#: Terminorte, die kein Ort sind.
_KEIN_ORT = frozenset({'online', 'remote', 'telefon', 'telefonisch', 'tel', 'video', 'zoom', 'teams',
                       'microsoftteams', 'msteams', 'googlemeet', 'meet', 'webex', 'homeoffice', 'digital', 'virtuell'})
_ORTSZEILE = re.compile(r'^Ort:[ \t]*(.+?)[ \t]*$', re.M)
_PLZ_ORT = re.compile(r'\b\d{5}[ \t]+([A-ZÄÖÜ][\wäöüß.-]*(?:[ \t]+[A-ZÄÖÜ][\wäöüß.-]*)?)')


def norm(text: str) -> str:
    """Buchstaben und Ziffern, klein: die Kennung eines Namens („Winter Catering“ = „winter-catering“)."""
    return ''.join(zeichen for zeichen in str(text or '').casefold() if zeichen.isalnum())


def sache_id(art: str, kennung: str) -> str:
    return f'{art}:{kennung}'


def zerlegen(sache: str) -> tuple[str, str] | None:
    """(Art, Kennung) einer Sachen-ID, None bei einer ungültigen."""
    art, _, kennung = str(sache or '').partition(':')
    return (art, kennung) if art in ARTEN and kennung.strip() and len(sache) <= 300 else None


def org_kennung(name: str) -> str:
    """Kennung einer Organisation aus ihrem Namen: ohne Rechtsform („Winter Catering GmbH“)."""
    return norm(_RECHTSFORM.sub(' ', str(name or '')))


def org_aus_adresse(adresse: str, eigene_domaenen: Iterable[str] = ()) -> str:
    """Kennung der Organisation hinter einer Adresse; leer bei privaten Anbietern und eigener Domäne."""
    name = domaenenname(adresse)
    if not name or domaene(adresse).casefold() in {d.casefold() for d in eigene_domaenen}:
        return ''
    return '' if ist_privater_anbieter(adresse) else norm(name)


def maschinell(adresse: str) -> bool:
    """Ein Postfach wie noreply@ oder info@: eine Organisation, kein Mensch."""
    return ist_sammelpostfach(lokalteil(adresse))


def projekt_kennung(name: str) -> str:
    return norm(re.sub(r'^\s*projekt\s+', '', str(name or ''), flags=re.I))


_RAUM = re.compile(r'raum|saal|zimmer|büro|etage|stock|halle|room|\d', re.I)


def orte_im_termin(text: str) -> list[tuple[str, int, int]]:
    """Orte aus der Ortsangabe eines Termins: (Kennung, Beginn, Ende) im Text.

    Einfache, deterministische Regel, die kein Modell braucht (das Modell ergänzt
    Orte im Text über `memory_categories`, Art `place`):

    * ohne Komma: der ganze Eintrag („Café Central“, „Mainz“);
    * mit Komma: der erste Teil (Haus oder Träger: „Akademie Taunus“), der Ort
      hinter einer Postleitzahl („55116 Mainz“) und der letzte Teil, wenn er wie
      ein Ortsname aussieht (bis drei Wörter, kein Raum, keine Ziffer).

    „online“, „Zoom“ und Ähnliches ist kein Ort.
    """
    gesamt = text.strip()
    if not gesamt or len(gesamt) > 160 or norm(gesamt) in _KEIN_ORT:
        return []
    verschiebung = text.index(gesamt)
    gefunden: list[tuple[str, int, int]] = []
    if ',' not in gesamt:
        gefunden.append((norm(gesamt), verschiebung, verschiebung + len(gesamt)))
    else:
        erster = gesamt.split(',', 1)[0].strip()
        if erster and not _RAUM.search(erster):
            gefunden.append((norm(erster), verschiebung + gesamt.index(erster), verschiebung + gesamt.index(erster) + len(erster)))
        treffer = _PLZ_ORT.search(gesamt)
        if treffer:
            gefunden.append((norm(treffer[1]), verschiebung + treffer.start(1), verschiebung + treffer.end(1)))
        letzter = gesamt.rsplit(',', 1)[1].strip()
        if letzter and letzter[0].isupper() and len(letzter.split()) <= 3 and not _RAUM.search(letzter):
            gefunden.append((norm(letzter), verschiebung + gesamt.rindex(letzter), verschiebung + gesamt.rindex(letzter) + len(letzter)))
    ergebnis: list[tuple[str, int, int]] = []
    for kennung, beginn, ende in gefunden:
        if kennung and kennung not in _KEIN_ORT and all(kennung != vorhandene[0] for vorhandene in ergebnis):
            ergebnis.append((kennung, beginn, ende))
    return ergebnis


# -- Datenklassen ------------------------------------------------------------


@dataclass(frozen=True)
class Bezug:
    """Eine Verknüpfung Quelle -> Sache mit Grundlage und Textstelle.

    `sache` ist leer, wenn die Erwähnung offen blieb; `kandidaten` nennt dann die
    Sachen, zwischen denen nicht entschieden werden konnte. `start`/`ende` sind
    Zeichenpositionen im Text der Quelle (-1: ohne Textstelle, etwa eine Adresse).
    """

    sache: str
    art: str
    grundlage: str
    start: int = -1
    ende: int = -1
    rolle: str = ''
    kandidaten: tuple[str, ...] = ()
    abhaengig: bool = False


# -- Verzeichnis -------------------------------------------------------------


@dataclass
class Register:
    """Alles, was zum Auflösen eines Namens nötig ist; aus dem Bestand gebaut."""

    verzeichnis: Verzeichnis = field(default_factory=Verzeichnis)
    ich_namen: frozenset[str] = frozenset()
    eigene_domaenen: frozenset[str] = frozenset()
    projekte: dict[str, str] = field(default_factory=dict)
    token: str = ''

    @classmethod
    def bauen(cls, episoden: Iterable[Episode], *, eigene: Iterable[str] = (),
              projekte: dict[str, str] | None = None) -> 'Register':
        eigene = [a for a in eigene if a]
        verzeichnis = Verzeichnis()
        ich_namen: set[str] = set()
        for episode in episoden:
            for nennung in nennungen(episode, eigene):
                if nennung.ich:
                    if name_schluessel(nennung.name):
                        ich_namen.add(name_schluessel(nennung.name))
                else:
                    verzeichnis.aufnehmen(nennung)
        domaenen = frozenset(domaene(a).casefold() for a in eigene if domaene(a))
        register = cls(verzeichnis, frozenset(ich_namen), domaenen, dict(projekte or {}))
        register.token = register._digest()
        return register

    def _digest(self) -> str:
        inhalt = {'adressen': {a: sorted({name_schluessel(n) for n in self.verzeichnis.namen(a)})
                               for a in self.verzeichnis.adressen()},
                  'ich': sorted(self.ich_namen), 'domaenen': sorted(self.eigene_domaenen),
                  'projekte': sorted(self.projekte.items())}
        return hashlib.sha256(json.dumps(inhalt, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]

    def person(self, name: str) -> tuple[str, tuple[str, ...]]:
        """(Sache, Kandidaten) einer Person, die nur mit Namen genannt ist.

        Genau eine Adresse trägt den Namen: diese Person. Keine: eine Person für
        sich (`n:<Name>`). Mehrere: offen, mit den Kandidaten.
        """
        aufloesung = self.verzeichnis.aufloesen(Nennung(name, ''))
        if aufloesung.schluessel.startswith('a:') or not aufloesung.offen:
            return sache_id('person', aufloesung.schluessel), ()
        return '', tuple(sache_id('person', 'a:' + adresse) for adresse in aufloesung.offen)

    def projekt(self, name: str) -> str:
        kennung = projekt_kennung(name)
        return sache_id('projekt', self.projekte.get(kennung) or 'n:' + kennung)


def projekte_aus(workspace: Any) -> dict[str, str]:
    """Kennung des Namens -> Projekt-ID für alle Projekte des Arbeitsbereichs, auch abgeschlossene."""
    if workspace is None:
        return {}
    try:
        projekte = workspace.projects(include_closed=True)
    except Exception:  # noqa: BLE001 - ohne Arbeitsbereich bleiben Projekte Namen
        return {}
    gefunden: dict[str, str | None] = {}
    for projekt in projekte:
        kennung = projekt_kennung(projekt.name)
        # Zwei Projekte gleichen Namens: nicht raten, keins zuordnen.
        gefunden[kennung] = projekt.id if kennung not in gefunden else None
    return {kennung: pid for kennung, pid in gefunden.items() if pid and kennung}


# -- Berechnung einer Quelle -------------------------------------------------


def berechnen(episode: Episode, auszug: dict[str, Any], register: Register,
              eigene: Iterable[str] = ()) -> list[Bezug]:
    """Alle Bezüge einer Quelle. Rein: nur Quelle, Themenauszug und Verzeichnis gehen ein.

    `auszug` ist `Categories.list_for(episode.id)`: Themen mit Belegstellen und
    erwähnte Entitäten mit Textstelle.
    """
    gefunden: list[Bezug] = []
    for nennung in nennungen(episode, eigene):
        if nennung.ich:
            continue
        if nennung.adresse:
            if not maschinell(nennung.adresse):
                gefunden.append(Bezug(sache_id('person', 'a:' + nennung.adresse), 'person', 'anker',
                                      rolle=nennung.rolle))
            organisation = org_aus_adresse(nennung.adresse, register.eigene_domaenen)
            if organisation:
                gefunden.append(Bezug(sache_id('organisation', organisation), 'organisation', 'anker',
                                      rolle=nennung.rolle))
        elif nennung.name and name_schluessel(nennung.name) not in register.ich_namen:
            sache, kandidaten = register.person(nennung.name)
            gefunden.append(Bezug(sache, 'person', 'anker', rolle=nennung.rolle, kandidaten=kandidaten,
                                  abhaengig=True))
    if episode.project_id:
        gefunden.append(Bezug(sache_id('projekt', episode.project_id), 'projekt', 'anker', rolle='zuordnung'))
    for eintrag in auszug.get('entities', []):
        art = ART_DER_ERWAEHNUNG.get(eintrag.get('kind'))
        name = str(eintrag.get('name') or '')
        start, ende = int(eintrag.get('start', -1)), int(eintrag.get('end', -1))
        if art is None or not name.strip():
            continue
        if art == 'person':
            # Der Absender ist über seine Adresse schon verknüpft; der Nutzer selbst ist keine Sache.
            if eintrag.get('role') == 'sender' or name_schluessel(name) in register.ich_namen:
                continue
            sache, kandidaten = register.person(name)
            gefunden.append(Bezug(sache, art, 'modell', start, ende, 'erwaehnt', kandidaten, abhaengig=True))
        elif art == 'organisation':
            kennung = org_kennung(name)
            if kennung:
                gefunden.append(Bezug(sache_id(art, kennung), art, 'modell', start, ende, 'erwaehnt'))
        elif art == 'projekt':
            if projekt_kennung(name):
                gefunden.append(Bezug(register.projekt(name), art, 'modell', start, ende, 'erwaehnt',
                                      abhaengig=True))
        elif norm(name):
            gefunden.append(Bezug(sache_id(art, norm(name)), art, 'modell', start, ende, 'erwaehnt'))
    for thema in auszug.get('categories', []):
        if thema.get('id') in KEINE_THEMEN:
            continue
        sache = sache_id('thema', thema['id'])
        if thema.get('origin') == 'user':
            gefunden.append(Bezug(sache, 'thema', 'nutzer'))
        else:
            for beleg in thema.get('evidence') or [{'start': -1, 'end': -1}]:
                gefunden.append(Bezug(sache, 'thema', 'modell', int(beleg['start']), int(beleg['end'])))
    if episode.kind is EpisodeKind.EVENT:
        for treffer in _ORTSZEILE.finditer(episode.body):
            for kennung, beginn, ende in orte_im_termin(treffer[1]):
                gefunden.append(Bezug(sache_id('ort', kennung), 'ort', 'anker', treffer.start(1) + beginn,
                                      treffer.start(1) + ende, 'terminort'))
    eindeutig: dict[tuple, Bezug] = {}
    for bezug in gefunden:
        eindeutig.setdefault((bezug.sache, bezug.grundlage, bezug.start, bezug.ende, bezug.kandidaten), bezug)
    return list(eindeutig.values())


# -- Ablage und Abgleich -----------------------------------------------------

#: Geltende Quelle (`episodes.sql_geltend`: Rohquelle, nicht ausgeschlossen, aktuelle Fassung)
#: ohne eigene Suchfrage des Gesprächs.
_GUELTIG = (sql_geltend('e') + " AND NOT EXISTS (SELECT 1 FROM json_each(e.document, '$.tags') tag "
            "WHERE tag.value = ?)")
GUELTIG_PARAMS = (CHAT_LOOKUP_TAG,)
#: Fingerabdruck der Quelle, in SQL: Text, Metadaten, Bearbeitungszähler (Kontakte, Projekt), Länge.
FINGERABDRUCK = ("e.digest || ':' || e.metadata_digest || ':' || e.support_generation || ':' "
                 "|| length(e.document)")
#: Alles, was in die Bezüge einer Quelle eingeht (ohne das Verzeichnis).
_EINGABE = (FINGERABDRUCK + " || '|' || COALESCE(c.fingerprint,'') || ':' || COALESCE(c.status,'') || ':' "
            "|| COALESCE(c.taxonomy_version,'') || '|' || COALESCE(k.fingerprint,'') || ':' "
            "|| COALESCE(k.updated_at,'') || '|' || COALESCE(e.project_id,'')")
_NICHT_ABGELEHNT = ("NOT EXISTS (SELECT 1 FROM sach_nutzer u WHERE u.episode_id = b.episode_id "
                    "AND u.sache = b.sache AND u.aktion = 'nicht' AND u.fingerprint = " + FINGERABDRUCK + ")")
GUELTIG = _GUELTIG


class Bezuege:
    """Ablage, Abgleich und Abfragen der Bezüge; alles ohne Modell."""

    def __init__(self, episodes: Any, *, workspace: Any = None,
                 eigene: Callable[[], Iterable[str]] = lambda: ()) -> None:
        from .memory_categories import Categories
        self.episodes = episodes
        self.workspace = workspace
        self._eigene = eigene
        self._kategorien = Categories(episodes)
        self._register: Register | None = None
        self._register_stand: tuple | None = None
        self._register_lock = threading.Lock()

    @property
    def _conn(self) -> sqlite3.Connection:
        return self.episodes._conn

    # -- Verzeichnis --

    def register(self) -> Register:
        """Das Verzeichnis; nur neu gebaut, wenn sich Bestand, eigene Adressen oder Projekte geändert haben."""
        projekte = projekte_aus(self.workspace)
        eigene = tuple(sorted(a for a in self._eigene() if a))
        with self._register_lock:
            for _ in range(3):
                stand = (self.episodes.geltender_stand(), eigene, tuple(sorted(projekte.items())))
                if self._register is not None and self._register_stand == stand:
                    return self._register
                # Gebaut wird seitenweise und ohne den Speicher zu sperren; hat sich der Bestand währenddessen
                # geändert, gilt der Bau nicht als aktuell und wird wiederholt.
                register = Register.bauen(self.episodes.each_geltende(), eigene=eigene, projekte=projekte)
                if self.episodes.geltender_stand() == stand[0]:
                    self._register, self._register_stand = register, stand
                    return register
            self._register, self._register_stand = None, None
            return register

    def aenderungsstand(self) -> tuple:
        """Kennung dessen, was in die Bezüge eingeht: ändert sich mit jedem Schreibvorgang am Speicher.

        Wer gerade abgeglichen hat und denselben Stand wiedersieht, muss nicht noch einmal
        nachsehen (das kostet bei vielen Quellen eine Abfrage über den ganzen Bestand).
        """
        with self.episodes._lock:
            version = self._conn.execute('PRAGMA data_version').fetchone()[0]
            aenderungen = self._conn.total_changes
        return (aenderungen, version, tuple(sorted(projekte_aus(self.workspace).items())),
                tuple(sorted(a for a in self._eigene() if a)))

    # -- Abgleich --

    _OFFEN = ("FROM episodes e LEFT JOIN sach_quellen q ON q.episode_id = e.id "
              "LEFT JOIN memory_category_sources c ON c.episode_id = e.id "
              "LEFT JOIN memory_category_corrections k ON k.episode_id = e.id "
              "WHERE " + _GUELTIG + " AND (q.episode_id IS NULL OR q.eingabe != (" + _EINGABE + ") "
              "OR (q.register != '' AND q.register != ?))")

    def offene_quellen(self, register_token: str, limit: int) -> list[Any]:
        """Geltende Quellen ohne aktuelle Bezüge: neu, verändert oder vom Verzeichnis abhängig und veraltet."""
        with self.episodes._lock:
            return self._conn.execute(
                "SELECT e.id AS id, " + FINGERABDRUCK + " AS fp, " + _EINGABE + " AS ein " + self._OFFEN + " LIMIT ?",
                (*GUELTIG_PARAMS, register_token, limit)).fetchall()

    def offene_zaehlen(self, register_token: str) -> int:
        with self.episodes._lock:
            return self._conn.execute("SELECT COUNT(*) " + self._OFFEN, (*GUELTIG_PARAMS, register_token)).fetchone()[0]

    def entziehen(self) -> int:
        """Löscht Zeilen von Quellen, die nicht mehr gelten. Lesungen sehen sie ohnehin nicht mehr."""
        with self.episodes.transaction():
            weg = self._conn.execute(
                "DELETE FROM sach_quellen WHERE NOT EXISTS (SELECT 1 FROM episodes e WHERE e.id = sach_quellen.episode_id "
                "AND " + _GUELTIG + ")", GUELTIG_PARAMS).rowcount
            self._conn.execute(
                "DELETE FROM sach_bezuege WHERE episode_id NOT IN (SELECT episode_id FROM sach_quellen)")
        return weg

    def aktualisieren(self, *, max_quellen: int | None = None, frist_s: float | None = None) -> dict[str, int]:
        """Berechnet fehlende und veränderte Quellen; entfernt entzogene.

        Rückgabe: `berechnet`, `entfernt`, `offen` (so viele Quellen sind noch
        nicht berechnet; 0 heißt fertig).
        """
        begonnen = time.monotonic()
        entfernt = self.entziehen()
        register = self.register()
        berechnet, paket = 0, 200
        eigene = [a for a in self._eigene() if a]
        while True:
            wieviele = paket if max_quellen is None else min(paket, max_quellen - berechnet)
            if wieviele <= 0:
                break
            reihe = self.offene_quellen(register.token, wieviele)
            if not reihe:
                break
            for zeile in reihe:
                self._quelle_berechnen(zeile, register, eigene)
                berechnet += 1
                if frist_s is not None and time.monotonic() - begonnen > frist_s:
                    break
            if frist_s is not None and time.monotonic() - begonnen > frist_s:
                break
        return {'berechnet': berechnet, 'entfernt': entfernt, 'offen': self.offene_zaehlen(register.token)}

    def _quelle_berechnen(self, zeile: Any, register: Register, eigene: list[str]) -> None:
        try:
            episode = self.episodes.get(zeile['id'])
        except Exception:  # noqa: BLE001 - eine unlesbare Quelle blockiert den Abgleich nicht
            return
        auszug = self._kategorien.list_for(zeile['id'])
        bezuege = berechnen(episode, auszug, register, eigene)
        abhaengig = any(b.abhaengig for b in bezuege)
        with self.episodes.transaction():
            self._conn.execute("DELETE FROM sach_bezuege WHERE episode_id = ?", (zeile['id'],))
            self._conn.executemany(
                "INSERT OR IGNORE INTO sach_bezuege VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(zeile['id'], zeile['fp'], b.sache, b.art, b.grundlage, b.start, b.ende, b.rolle,
                  json.dumps(list(b.kandidaten)) if b.kandidaten else '', int(b.abhaengig)) for b in bezuege])
            self._conn.execute(
                "INSERT INTO sach_quellen VALUES (?,?,?,?,?) ON CONFLICT(episode_id) DO UPDATE SET "
                "fingerprint=excluded.fingerprint, eingabe=excluded.eingabe, register=excluded.register, "
                "berechnet_am=excluded.berechnet_am",
                (zeile['id'], zeile['fp'], zeile['ein'], register.token if abhaengig else '', time.time()))

    # -- Abfragen --

    @staticmethod
    def _links(*, sache: bool = False, quellen: int = 0) -> str:
        """SQL: alle wirksamen Verknüpfungen (Sache, Quelle) einschließlich Zuordnungen des Nutzers.

        `sache` und `quellen` schränken schon in den Teilabfragen ein (ein Platzhalter für die
        Sache, `quellen` Platzhalter für Quellen-IDs), damit nicht der ganze Bestand verbunden wird,
        wenn nur eine Akte gelesen wird. Die Parameter stehen je Teilabfrage in dieser Reihenfolge:
        Gültigkeit, dann Sache, dann Quellen.
        """
        filter_b = (" AND b.sache = ?" if sache else "") + (
            f" AND b.episode_id IN ({','.join('?' for _ in range(quellen))})" if quellen else "")
        filter_u = (" AND u.sache = ?" if sache else "") + (
            f" AND u.episode_id IN ({','.join('?' for _ in range(quellen))})" if quellen else "")
        return (
            "SELECT b.sache AS sache, b.episode_id AS episode_id FROM sach_bezuege b JOIN episodes e ON e.id = b.episode_id "
            "WHERE b.sache != ''" + filter_b + " AND " + _GUELTIG + " AND " + _NICHT_ABGELEHNT + " "
            "UNION SELECT u.sache, u.episode_id FROM sach_nutzer u JOIN episodes e ON e.id = u.episode_id "
            "WHERE u.aktion = 'zu'" + filter_u + " AND u.fingerprint = " + FINGERABDRUCK + " AND " + _GUELTIG)

    def sachen(self, *, art: str | None = None, suche: str = '', limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Sachen mit Anzahl der Quellen und letzter Aktivität, jüngste zuerst; mit Gesamtzahl."""
        bedingung, parameter = '', []
        if art:
            bedingung += " AND l.sache LIKE ? ESCAPE '\\'"
            parameter.append(art + ':%')
        if suche.strip():
            bedingung += " AND l.sache LIKE ? ESCAPE '\\'"
            parameter.append('%' + norm(suche).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        with self.episodes._lock:
            basis = (f"FROM ({self._links()}) l JOIN episodes e ON e.id = l.episode_id WHERE 1=1{bedingung} "
                     "GROUP BY l.sache")
            grund = (*GUELTIG_PARAMS, *GUELTIG_PARAMS, *parameter)
            gesamt = self._conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 {basis})", grund).fetchone()[0]
            zeilen = self._conn.execute(
                "SELECT l.sache AS sache, COUNT(*) AS n, MAX(julianday(COALESCE(e.occurred_at, e.recorded_at))) AS letzte, "
                "MAX(COALESCE(e.occurred_at, e.recorded_at)) AS letzte_text " + basis +
                " ORDER BY letzte DESC, l.sache LIMIT ? OFFSET ?", (*grund, limit, offset)).fetchall()
        return {'gesamt': gesamt, 'sachen': [
            {'sache': z['sache'], 'art': z['sache'].split(':', 1)[0], 'quellen': z['n'], 'letzte': z['letzte_text']}
            for z in zeilen]}

    def quellen_von(self, sache: str) -> list[dict[str, Any]]:
        """Alle geltenden Quellen einer Sache mit ihren Grundlagen, jüngste zuerst.

        Je Quelle: `episode_id`, `zeit`, `archiviert`, `fp` (Fingerabdruck),
        `art` (message, document, event), `grundlagen`, `stellen` (Textstellen der Bezüge).
        """
        with self.episodes._lock:
            zeilen = self._conn.execute(
                "SELECT l.episode_id AS id, COALESCE(e.occurred_at, e.recorded_at) AS zeit, e.state AS state, "
                + FINGERABDRUCK + " AS fp, e.kind AS kind "
                "FROM (" + self._links(sache=True) + ") l JOIN episodes e ON e.id = l.episode_id "
                "ORDER BY julianday(COALESCE(e.occurred_at, e.recorded_at)) DESC, l.episode_id",
                (sache, *GUELTIG_PARAMS, sache, *GUELTIG_PARAMS)).fetchall()
            ids = [z['id'] for z in zeilen]
            grundlagen: dict[str, dict[str, list]] = {i: {} for i in ids}
            for start in range(0, len(ids), 500):
                teil = ids[start:start + 500]
                marken = ','.join('?' for _ in teil)
                for b in self._conn.execute(
                        "SELECT episode_id, grundlage, start, end FROM sach_bezuege WHERE sache = ? AND episode_id IN ("
                        + marken + ")", (sache, *teil)):
                    grundlagen[b['episode_id']].setdefault(b['grundlage'], []).append((b['start'], b['end']))
                for u in self._conn.execute(
                        "SELECT u.episode_id AS episode_id FROM sach_nutzer u JOIN episodes e ON e.id = u.episode_id "
                        "WHERE u.sache = ? AND u.aktion = 'zu' AND u.fingerprint = " + FINGERABDRUCK +
                        " AND u.episode_id IN (" + marken + ")", (sache, *teil)):
                    grundlagen[u['episode_id']].setdefault('nutzer', []).append((-1, -1))
        return [{'episode_id': z['id'], 'zeit': z['zeit'], 'archiviert': z['state'] == 'archived',
                 'fp': z['fp'], 'art': z['kind'],
                 'grundlagen': sorted(grundlagen[z['id']], key=GRUNDLAGEN.index),
                 'stellen': [s for lst in grundlagen[z['id']].values() for s in lst if s[0] >= 0]} for z in zeilen]

    def gemeinsame(self, sache: str, episode_ids: list[str]) -> dict[str, int]:
        """Andere Sachen, die in denselben Quellen vorkommen: Sache -> Zahl gemeinsamer Quellen.

        Es zählen dieselben wirksamen Verknüpfungen wie überall (Ablehnungen des
        Nutzers gelten, seine Zuordnungen auch).
        """
        zaehler: dict[str, set[str]] = {}
        ids = list(dict.fromkeys(episode_ids))
        with self.episodes._lock:
            for start in range(0, len(ids), 500):
                teil = ids[start:start + 500]
                marken = ','.join('?' for _ in teil)
                for z in self._conn.execute(
                        "SELECT l.sache AS sache, l.episode_id AS episode_id FROM (" + self._links(quellen=len(teil)) + ") l "
                        "WHERE l.sache != ?",
                        (*teil, *GUELTIG_PARAMS, *teil, *GUELTIG_PARAMS, sache)):
                    zaehler.setdefault(z['sache'], set()).add(z['episode_id'])
        return {k: len(v) for k, v in zaehler.items()}

    def stand(self) -> dict[str, int]:
        """Wie viele geltende Quellen noch ohne aktuelle Bezüge sind (für „wird noch berechnet“)."""
        token = self.register().token
        with self.episodes._lock:
            gesamt = self._conn.execute("SELECT COUNT(*) FROM episodes e WHERE " + _GUELTIG,
                                        GUELTIG_PARAMS).fetchone()[0]
        return {'quellen': gesamt, 'offen': self.offene_zaehlen(token)}

    def bezuege_der_quelle(self, episode_id: str) -> dict[str, Any] | None:
        """Bezüge einer Quelle für die Anzeige. None, wenn die Quelle nicht (mehr) gilt.

        `bezuege`: wirksame Verknüpfungen mit Grundlage(n) und Textstelle,
        `offen`: Erwähnungen, die sich nicht eindeutig zuordnen ließen, mit
        Kandidaten, `abgelehnt`: vom Nutzer ausgeschlossene Bezüge,
        `veraltet`: Zuordnungen des Nutzers, die zu einer früheren Fassung gehören.
        """
        with self.episodes._lock:
            gelesen = self._conn.execute(
                "SELECT " + FINGERABDRUCK + " AS fp FROM episodes e WHERE e.id = ? AND " + _GUELTIG,
                (episode_id, *GUELTIG_PARAMS)).fetchone()
            if gelesen is None:
                return None
            fp = gelesen['fp']
            bezuege = self._conn.execute(
                "SELECT sache, art, grundlage, start, end, rolle, kandidaten FROM sach_bezuege WHERE episode_id = ? "
                "ORDER BY rowid", (episode_id,)).fetchall()
            nutzer = self._conn.execute(
                "SELECT sache, art, aktion, fingerprint FROM sach_nutzer WHERE episode_id = ?", (episode_id,)).fetchall()
            berechnet = self._conn.execute(
                "SELECT 1 FROM sach_quellen WHERE episode_id = ?", (episode_id,)).fetchone() is not None
        aktuell = {n['sache']: n['aktion'] for n in nutzer if n['fingerprint'] == fp}
        veraltet = [{'sache': n['sache'], 'art': n['art'], 'aktion': n['aktion']}
                    for n in nutzer if n['fingerprint'] != fp]
        wirksam: dict[str, dict[str, Any]] = {}
        offen: list[dict[str, Any]] = []
        abgelehnt: list[dict[str, Any]] = []
        for b in bezuege:
            kandidaten = json.loads(b['kandidaten']) if b['kandidaten'] else []
            stelle = {'start': b['start'], 'ende': b['end']} if b['start'] >= 0 else None
            if not b['sache']:
                # Offen, außer der Nutzer hat einen der Kandidaten für diese Quelle bestätigt.
                if not any(aktuell.get(k) == 'zu' for k in kandidaten):
                    offen.append({'art': b['art'], 'kandidaten': kandidaten, 'stelle': stelle, 'rolle': b['rolle']})
                continue
            if aktuell.get(b['sache']) == 'nicht':
                if b['sache'] not in {a['sache'] for a in abgelehnt}:
                    abgelehnt.append({'sache': b['sache'], 'art': b['art']})
                continue
            eintrag = wirksam.setdefault(b['sache'], {'sache': b['sache'], 'art': b['art'], 'grundlagen': [],
                                                      'stellen': [], 'rollen': []})
            if b['grundlage'] not in eintrag['grundlagen']:
                eintrag['grundlagen'].append(b['grundlage'])
            if stelle:
                eintrag['stellen'].append(stelle)
            if b['rolle'] and b['rolle'] not in eintrag['rollen']:
                eintrag['rollen'].append(b['rolle'])
        for sache, aktion in aktuell.items():
            if aktion == 'zu':
                eintrag = wirksam.setdefault(sache, {'sache': sache, 'art': sache.split(':', 1)[0],
                                                     'grundlagen': [], 'stellen': [], 'rollen': []})
                if 'nutzer' not in eintrag['grundlagen']:
                    eintrag['grundlagen'].append('nutzer')
        for eintrag in wirksam.values():
            eintrag['grundlagen'].sort(key=GRUNDLAGEN.index)
        return {'episode_id': episode_id, 'bezuege': list(wirksam.values()), 'offen': offen,
                'abgelehnt': abgelehnt, 'veraltet': veraltet, 'berechnet': berechnet}

    # -- Zuordnung des Nutzers --

    def nutzer_setzen(self, episode_id: str, sache: str, aktion: str) -> dict[str, Any]:
        """Setzt „gehört dazu“ (`zu`) oder „gehört nicht dazu“ (`nicht`); maßgeblich, umkehrbar."""
        teile = zerlegen(sache)
        if teile is None or aktion not in ('zu', 'nicht'):
            raise ValueError('Ungültige Sache oder Aktion.')
        with self.episodes.transaction():
            zeile = self._conn.execute(
                "SELECT " + FINGERABDRUCK + " AS fp FROM episodes e WHERE e.id = ? AND " + _GUELTIG,
                (episode_id, *GUELTIG_PARAMS)).fetchone()
            if zeile is None:
                raise LookupError('Die Quelle gilt nicht mehr.')
            self._conn.execute(
                "INSERT INTO sach_nutzer VALUES (?,?,?,?,?,?) ON CONFLICT(episode_id, sache) DO UPDATE SET "
                "art=excluded.art, aktion=excluded.aktion, fingerprint=excluded.fingerprint, "
                "updated_at=excluded.updated_at",
                (episode_id, sache, teile[0], aktion, zeile['fp'], time.time()))
        return self.bezuege_der_quelle(episode_id) or {}

    def nutzer_entfernen(self, episode_id: str, sache: str) -> bool:
        """Nimmt die Entscheidung des Nutzers zurück; danach gilt wieder, was das Programm fand."""
        with self.episodes.transaction():
            return self._conn.execute(
                "DELETE FROM sach_nutzer WHERE episode_id = ? AND sache = ?", (episode_id, sache)).rowcount > 0

    # -- Anzeige aus dem Original --

    def beschriftung(self, sache: str, *, quellen: list[dict[str, Any]] | None = None) -> str:
        """Der Name einer Sache, gelesen aus dem Original (nie gespeichert).

        Person: häufigster Anzeigename ihrer Adresse; Projekt: Name im
        Arbeitsbereich; Thema: Bezeichnung der Taxonomie; Organisation und Ort: die
        Schreibweise der jüngsten Quelle (Erwähnung an der Textstelle, Ortsangabe,
        Domäne).
        """
        teile = zerlegen(sache)
        if teile is None:
            return sache
        art, kennung = teile
        if art == 'person' and kennung.startswith('a:'):
            from .kontakte import anzeigename
            for eintrag in self.episodes.participants_for_address(kennung[2:]):
                name = anzeigename(eintrag['name'])
                if name:
                    return name
            return kennung[2:]
        if art == 'projekt' and not kennung.startswith('n:') and self.workspace is not None:
            try:
                return self.workspace.project(kennung).name
            except Exception:  # noqa: BLE001 - ein gelöschtes Projekt bleibt als Kennung sichtbar
                return kennung
        if art == 'thema':
            for eintrag in self._kategorien.taxonomy()['items']:
                if eintrag['id'] == kennung:
                    return eintrag['label']
            return kennung
        for quelle in (quellen if quellen is not None else self.quellen_von(sache))[:5]:
            text = self._schreibweise(sache, quelle['episode_id'])
            if text:
                return text
        return kennung[2:] if kennung.startswith('n:') else kennung

    def beschriftungen(self, sachen: list[str]) -> dict[str, str]:
        """Namen mehrerer Sachen. Die Personen einer Liste werden in einem Durchgang über den Bestand
        gelesen statt einzeln (jede Einzelabfrage einer Adresse durchsucht alle Quellen)."""
        adressen = [zerlegen(s)[1][2:] for s in sachen if (zerlegen(s) or ('', ''))[0] == 'person'
                    and zerlegen(s)[1].startswith('a:')]
        gefunden = self.episodes.participants_for_addresses(adressen) if adressen else {}
        from .kontakte import anzeigename
        ergebnis: dict[str, str] = {}
        for sache in sachen:
            teile = zerlegen(sache)
            if teile and teile[0] == 'person' and teile[1].startswith('a:'):
                eintrag = gefunden.get(teile[1][2:]) or {'namen': {}}
                namen = sorted(eintrag['namen'].items(), key=lambda p: (-p[1], p[0]))
                ergebnis[sache] = next((anzeigename(n) for n, _ in namen if anzeigename(n)), teile[1][2:])
            else:
                ergebnis[sache] = self.beschriftung(sache)
        return ergebnis

    def _schreibweise(self, sache: str, episode_id: str) -> str:
        """Der Name der Sache, wie ihn diese Quelle schreibt (Textstelle oder Anzeigename)."""
        try:
            episode = self.episodes.get(episode_id)
        except Exception:  # noqa: BLE001
            return ''
        with self.episodes._lock:
            zeilen = self._conn.execute(
                "SELECT start, end FROM sach_bezuege WHERE episode_id = ? AND sache = ? AND start >= 0 ORDER BY start",
                (episode_id, sache)).fetchall()
        for zeile in zeilen:
            if 0 <= zeile['start'] < zeile['end'] <= len(episode.body):
                return ' '.join(episode.body[zeile['start']:zeile['end']].split())
        art, kennung = zerlegen(sache) or ('', '')
        for nennung in nennungen(episode):
            if art == 'person' and kennung.startswith('n:') and not nennung.adresse \
                    and name_anker(nennung.name) == kennung[2:]:
                return nennung.name
            if art == 'organisation' and nennung.adresse and org_aus_adresse(nennung.adresse) == kennung:
                return domaenenname(nennung.adresse).replace('-', ' ').title()
        return ''

    def zitat(self, episode_id: str, start: int, ende: int) -> str:
        """Die Textstelle aus dem Original, leer wenn sie nicht mehr passt."""
        try:
            body = self.episodes.get(episode_id).body
        except Exception:  # noqa: BLE001
            return ''
        return ' '.join(body[start:ende].split()) if 0 <= start < ende <= len(body) else ''


__all__ = ['ARTEN', 'ART_TEXT', 'Bezug', 'Bezuege', 'Register', 'berechnen', 'maschinell', 'norm',
           'org_aus_adresse', 'org_kennung', 'orte_im_termin', 'projekt_kennung', 'sache_id', 'zerlegen']
