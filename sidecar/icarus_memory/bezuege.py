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
  Kurznamen einer Mail bekommen nur bei eindeutiger aktueller Anrede oder
  Absendersignatur deren Kontaktanker. In Prosa und Zitaten bleiben passende
  Kontakte offene Vorschläge; daraus entstehen keine globalen Teilnamen-Aliasse.
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


def suchformen(suche: str) -> list[str]:
    """Die Schreibweisen eines Suchbegriffs für Kennungen (Befund A7): wie getippt, in Umschrift („Müller“ →
    „mueller“), zurück in Umlaute („Mueller“ → „müller“) und ohne Umlautpunkte („muller“), jeweils wie `norm`."""
    from .word_forms import umschrift_gleich, umschriften
    formen = [norm(suche), norm(umschrift_gleich(suche))]
    formen += [norm(f) for f in umschriften(umschrift_gleich(suche))]
    import unicodedata
    formen.append(norm(''.join(z for z in unicodedata.normalize('NFD', str(suche or '').casefold())
                               if not unicodedata.combining(z))))
    return [f for f in dict.fromkeys(formen) if f][:12]


def sache_id(art: str, kennung: str) -> str:
    return f'{art}:{kennung}'


def zerlegen(sache: str) -> tuple[str, str] | None:
    """(Art, Kennung) einer Sachen-ID, None bei einer ungültigen."""
    art, _, kennung = str(sache or '').partition(':')
    return (art, kennung) if art in ARTEN and kennung.strip() and len(sache) <= 300 else None


def org_kennung(name: str) -> str:
    """Kennung einer Organisation aus ihrem Namen: ohne Rechtsform („Winter Catering GmbH“)."""
    return norm(_RECHTSFORM.sub(' ', str(name or '')))


def org_vergleich(name: str) -> str:
    """Eine Organisation zum Vergleichen (Befund A7): ohne Rechtsform, Umlaute in Umschrift, nur Buchstaben und Ziffern.

    „Müller Bau GmbH“, „Mueller Bau“ und die Domäne `mueller-bau` ergeben dasselbe. Nur ein Vergleichswert; die
    Kennungen der Akten bleiben, wie sie sind.
    """
    from .word_forms import umschrift_gleich
    return norm(umschrift_gleich(_RECHTSFORM.sub(' ', str(name or '').replace('-', ' '))))


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
    #: Adressen, die die Aufnahme als eigene gekennzeichnet hat („ich“). Nur zum Erkennen des Nutzers (Kreis); geht
    #: nicht in die Kennung ein und ändert keine Bezüge.
    ich_adressen: frozenset[str] = frozenset()

    def organisation(self, name: str) -> str:
        """Die Kennung einer erwähnten Organisation. Gibt es genau eine Organisation aus einer Adresse mit demselben
        Namen in Umschrift („Müller Bau“ und `mueller-bau.de`), ist es diese (Befund A7); sonst die Kennung des Namens."""
        kennung = org_kennung(name)
        if not kennung:
            return ''
        if not hasattr(self, '_orgs'):
            gefunden: dict[str, set[str]] = {}
            for adresse in self.verzeichnis.adressen():
                org = org_aus_adresse(adresse, self.eigene_domaenen)
                if org:
                    gefunden.setdefault(org_vergleich(domaenenname(adresse)), set()).add(org)
            self._orgs = {k: next(iter(v)) for k, v in gefunden.items() if len(v) == 1}
        return self._orgs.get(org_vergleich(name), kennung)

    @classmethod
    def bauen(cls, episoden: Iterable[Episode], *, eigene: Iterable[str] = (),
              projekte: dict[str, str] | None = None) -> 'Register':
        eigene = [a for a in eigene if a]
        verzeichnis = Verzeichnis()
        ich_namen: set[str] = set()
        ich_adressen: set[str] = set()
        for episode in episoden:
            for nennung in nennungen(episode, eigene):
                if nennung.ich:
                    if name_schluessel(nennung.name):
                        ich_namen.add(name_schluessel(nennung.name))
                    if nennung.adresse:
                        ich_adressen.add(nennung.adresse)
                else:
                    verzeichnis.aufnehmen(nennung)
        domaenen = frozenset(domaene(a).casefold() for a in eigene if domaene(a))
        register = cls(verzeichnis, frozenset(ich_namen), domaenen, dict(projekte or {}))
        register.token = register._digest()
        register.ich_adressen = frozenset(ich_adressen)
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


def _name_in_signatur(text: str, domaenenname_: str) -> str:
    """Eine Zeile der Quelle, die genau den Namen der Domäne trägt (in Umschrift, ohne Satzzeichen); sonst leer.

    Gelesen werden die letzten 25 Zeilen (Signatur, Absenderzeile). Nur eine kurze Zeile
    (höchstens 80 Zeichen) gilt, und sie muss vollständig passen, kein Wortteil. Die Rechtsform zählt nicht
    (`hessenwasser-ag` und „Hessenwasser AG“, `mueller-bau` und „Müller Bau GmbH“).
    """
    ziel = org_vergleich(domaenenname_)
    if not ziel:
        return ''
    for zeile in reversed(str(text or '').splitlines()[-25:]):
        zeile = ' '.join(zeile.split())
        if zeile and len(zeile) <= 80 and org_vergleich(zeile) == ziel:
            return zeile
    return ''


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


_ANREDE = re.compile(r'^(?:herrn?|frau)\s+', re.I)
_BEGRUESSUNG = re.compile(
    r'\A\s*(?:sehr geehrte[rn]?|liebe[rn]?|hallo|guten tag|guten morgen|guten abend|dear|hello)'
    r'[ \t]+(?P<name>[^\r\n,!:]{1,100})[ \t]*[,!]', re.I)
_GRUSS = re.compile(r'(?:mit freundlichen grüßen|freundliche grüße|viele grüße|beste grüße|'
                    r'herzliche grüße|liebe grüße|kind regards|best regards|regards)[,!]?', re.I)
_ZITATANFANG = re.compile(r'^[ \t]*(?:>|(?:am\b[^\r\n]*\bschrieb\b|on\b[^\r\n]*\bwrote\b)|'
                          r'(?:von|from|an|to|betreff|subject):|[-_]{2,})', re.I | re.M)


def _namenswoerter(name: str) -> list[str]:
    text = name.strip()
    # Nur ein geschlossenes äußeres ASCII-Quote-Paar ist Namensrahmen.
    # Apostrophe innerhalb eines Namens bleiben Teil des Vergleichsworts.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return name_schluessel(_ANREDE.sub('', text)).split()


def _quellen_kurzname(episode: Episode, name: str, start: int, ende: int,
                     beteiligte: list[Nennung]) -> tuple[str, tuple[str, ...], bool] | None:
    """Kurznamen dieser Mail: klare Anrede/Signatur oder nur offene Kandidaten.

    Teilnamen werden niemals Aliasse im globalen Verzeichnis. Ein gleicher
    Nachname in Prosa oder einer zitierten Mail beweist keine Identität; auch
    ein einzelner Kandidat bleibt dort offen. Rollen stammen aus dem Mailkopf,
    nicht aus einer Behauptung des Modells. Die Originalstelle bleibt erhalten.
    """
    if (episode.provenance.source_type.value != 'email' or not 0 <= start < ende <= len(episode.body)
            or episode.body[start:ende] != name):
        return None
    kurz = _namenswoerter(name)
    if not kurz:
        return None
    passend = []
    hat_kurzname = False
    for person in beteiligte:
        voll = _namenswoerter(person.name)
        # Keine Initialen, Ähnlichkeit oder beliebigen inneren Wortteile.
        if (person.adresse and not maschinell(person.adresse) and len(voll) >= len(kurz)
                and (kurz == voll[:len(kurz)] or kurz == voll[-len(kurz):])):
            passend.append(person)
            hat_kurzname = hat_kurzname or len(voll) > len(kurz)
    # Exakte Namen gehören ebenfalls zu den Kandidaten. Nur ein längerer
    # Kontaktname löst diese Zusatzregel aus; sonst gilt das exakte Verzeichnis.
    if not hat_kurzname:
        return None

    rolle = ''
    anrede = _BEGRUESSUNG.match(episode.body)
    if (anrede and anrede.start('name') <= start < ende <= anrede.end('name')
            and _namenswoerter(anrede['name']) == kurz):
        rolle = 'an'
    else:
        zeilenanfang = episode.body.rfind('\n', 0, start) + 1
        zeilenende = episode.body.find('\n', ende)
        zeilenende = len(episode.body) if zeilenende < 0 else zeilenende
        davor = episode.body[:zeilenanfang]
        vorzeilen = [zeile.strip() for zeile in davor.splitlines() if zeile.strip()]
        if (episode.body[zeilenanfang:zeilenende].strip() == name
                and vorzeilen and _GRUSS.fullmatch(vorzeilen[-1])
                and not _ZITATANFANG.search(davor)
                and not episode.body[zeilenende:].strip()):
            rolle = 'von'
    belegte = {p.adresse: p for p in passend if p.rolle == rolle} if rolle else {}
    if len(belegte) == 1 and len({p.adresse for p in passend}) == 1:
        adresse, person = next(iter(belegte.items()))
        return sache_id('person', 'a:' + adresse), (), person.ich
    kandidaten = tuple(sorted({sache_id('person', 'a:' + p.adresse) for p in passend}))
    return '', kandidaten, False


def berechnen(episode: Episode, auszug: dict[str, Any], register: Register,
              eigene: Iterable[str] = ()) -> list[Bezug]:
    """Alle Bezüge einer Quelle. Rein: nur Quelle, Themenauszug und Verzeichnis gehen ein.

    `auszug` ist `Categories.list_for(episode.id)`: Themen mit Belegstellen und
    erwähnte Entitäten mit Textstelle.
    """
    gefunden: list[Bezug] = []
    beteiligte = nennungen(episode, eigene)
    for nennung in beteiligte:
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
            if eintrag.get('role') == 'sender':
                continue
            kurzname = _quellen_kurzname(episode, name, start, ende, beteiligte)
            if kurzname is not None:
                sache, kandidaten, ich = kurzname
                if ich:
                    continue
            else:
                if name_schluessel(name) in register.ich_namen:
                    continue
                sache, kandidaten = register.person(name)
            gefunden.append(Bezug(sache, art, 'modell', start, ende, 'erwaehnt', kandidaten, abhaengig=True))
        elif art == 'organisation':
            kennung = register.organisation(name)
            if kennung:
                # Hängt vom Verzeichnis ab (Befund A7): Kommt eine Adresse `mueller-bau` hinzu, gehört „Müller Bau“ zu ihr.
                gefunden.append(Bezug(sache_id(art, kennung), art, 'modell', start, ende, 'erwaehnt', abhaengig=True))
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
        # „Ort: Akademie Taunus, Seminarraum 3“ mit jemandem von der Akademie (Adresse): Der Termin gehört zur
        # Organisation; ein gleichnamiger Ort daneben wäre eine zweite Akte für dieselbe Sache. Nur der erste Teil
        # (Haus oder Träger) und nur eine über eine Adresse verankerte Organisation; ein Ortsname bleibt Ort, auch
        # wenn er wie eine Domäne heißt („Mainz“ und mainz.de), ebenso der Ort hinter der Postleitzahl.
        organisationen = {zerlegen(b.sache)[1] for b in gefunden
                          if b.art == 'organisation' and b.grundlage == 'anker' and zerlegen(b.sache)}
        for treffer in _ORTSZEILE.finditer(episode.body):
            angabe = treffer[1]
            erster = angabe.split(',', 1)[0].strip()
            for kennung, beginn, ende in orte_im_termin(angabe):
                teil = angabe[beginn:ende]
                traeger = teil == erster and (',' in angabe or len(teil.split()) >= 2)
                organisation = org_kennung(teil) if traeger else ''
                art, kennung = ('organisation', organisation) if organisation in organisationen and organisation \
                    else ('ort', kennung)
                gefunden.append(Bezug(sache_id(art, kennung), art, 'anker', treffer.start(1) + beginn,
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
# Rule changes must also refresh address-only anchors with no register
# dependency. Version only the derived input; user decisions retain the
# unchanged source fingerprint above.
_REGELVERSION = 3
#: Termine haben eine eigene Regelfassung (Terminort und Organisation): Nur sie werden dafür neu berechnet.
_REGELVERSION_TERMINE = 4
#: Alles, was in die Bezüge einer Quelle eingeht (ohne das Verzeichnis).
_EINGABE = (FINGERABDRUCK + " || '|' || COALESCE(c.fingerprint,'') || ':' || COALESCE(c.status,'') || ':' "
            "|| COALESCE(c.taxonomy_version,'') || '|' || COALESCE(k.fingerprint,'') || ':' "
            "|| COALESCE(k.updated_at,'') || '|' || COALESCE(e.project_id,'')"
            f" || '|regeln:' || CASE WHEN e.kind = 'event' THEN '{_REGELVERSION_TERMINE}' ELSE '{_REGELVERSION}' END")
#: Wofür eine Entscheidung des Nutzers („gehört dazu“, „gehört nicht dazu“) gilt: für den **Text** der Quelle. Der
#: gespeicherte Fingerabdruck beginnt mit dem Inhaltsdigest. Projektzuordnung, Verdichten, Archivieren, nachgetragene
#: Kontakte, Kopfzeilen oder Anhangberichte ändern nur den Rest und lassen die Entscheidung stehen: Der Nutzer hat
#: über den Inhalt entschieden, nicht über die Ablage. Erst ein anderer Text macht sie veraltet.
_NUTZER_KERN = "e.digest || ':'"
NUTZER_GILT = "substr(u.fingerprint, 1, length(" + _NUTZER_KERN + ")) = " + _NUTZER_KERN


def nutzer_gilt(gespeichert: str, digest: str) -> bool:
    """Gilt eine gespeicherte Entscheidung für die heutige Fassung (gleicher Text)?"""
    return str(gespeichert or '').startswith(f'{digest}:')


_NICHT_ABGELEHNT = ("NOT EXISTS (SELECT 1 FROM sach_nutzer u WHERE u.episode_id = b.episode_id "
                    "AND u.sache = b.sache AND u.aktion = 'nicht' AND " + NUTZER_GILT + ")")
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
        # Für teure Listen über alle Bezüge (`akten/sachen`, Gruppenvorschläge der Organisationen), gültig je
        # `aenderungsstand` (V7, Tempo).
        from .zwischenspeicher import Zwischenspeicher
        self.zwischen = Zwischenspeicher(32)

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

    def eigene_adressen(self) -> list[str]:
        """Die eigenen Adressen des Nutzers (für „von dir“ oder „an dich“ in der Akte)."""
        try:
            return [a for a in self._eigene() if a]
        except Exception:  # noqa: BLE001 - ohne lesbare Einstellungen ist die Richtung nur unklar
            return []

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
            "WHERE u.aktion = 'zu'" + filter_u + " AND " + NUTZER_GILT + " AND " + _GUELTIG)

    def sachen(self, *, art: str | None = None, suche: str = '', limit: int = 50, offset: int = 0,
               bis: str | None = None) -> dict[str, Any]:
        """Sachen mit Anzahl der Quellen und letzter Aktivität, jüngste zuerst; mit Gesamtzahl.

        `bis` (ISO-Zeitpunkt): Die letzte Aktivität zählt nur bis dahin, ein künftiger Termin ist kein „zuletzt“
        (V7: in der Organisationsliste stand „zuletzt 31.12.2026“). Gezählt werden alle Quellen; eine Sache, die nur
        Künftiges hat, steht ohne letzte Aktivität am Ende. Ohne `bis` wie bisher (Logbuch, Lint, Abgleiche).
        """
        bedingung, parameter = '', []
        if art:
            bedingung += " AND l.sache LIKE ? ESCAPE '\\'"
            parameter.append(art + ':%')
        if suche.strip():
            # Befund A7: „Müller“ findet „Mueller“ und umgekehrt, ebenso ä/ae, ö/oe, ß/ss (`suchformen`).
            formen = suchformen(suche)
            bedingung += " AND (" + " OR ".join("l.sache LIKE ? ESCAPE '\\'" for _ in formen) + ")"
            parameter.extend('%' + f.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%' for f in formen)
        with self.episodes._lock:
            basis = (f"FROM ({self._links()}) l JOIN episodes e ON e.id = l.episode_id WHERE 1=1{bedingung} "
                     "GROUP BY l.sache")
            grund = (*GUELTIG_PARAMS, *GUELTIG_PARAMS, *parameter)
            gesamt = self._conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 {basis})", grund).fetchone()[0]
            zeit = "COALESCE(e.occurred_at, e.recorded_at)"
            if bis is None:
                letzte, grenze = f"MAX(julianday({zeit})) AS letzte, MAX({zeit}) AS letzte_text ", ()
            else:
                # Wie ohne Grenze, nur über die Quellen bis `bis`.
                bis_jd = f"julianday({zeit}) <= julianday(?)"
                letzte = (f"MAX(CASE WHEN {bis_jd} THEN julianday({zeit}) END) AS letzte, "
                          f"MAX(CASE WHEN {bis_jd} THEN {zeit} END) AS letzte_text ")
                grenze = (bis, bis)
            zeilen = self._conn.execute(
                "SELECT l.sache AS sache, COUNT(*) AS n, " + letzte + basis +
                " ORDER BY letzte DESC, l.sache LIMIT ? OFFSET ?", (*grenze, *grund, limit, offset)).fetchall()
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
                        "WHERE u.sache = ? AND u.aktion = 'zu' AND " + NUTZER_GILT +
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
                "SELECT e.digest AS digest FROM episodes e WHERE e.id = ? AND " + _GUELTIG,
                (episode_id, *GUELTIG_PARAMS)).fetchone()
            if gelesen is None:
                return None
            digest = gelesen['digest']
            bezuege = self._conn.execute(
                "SELECT sache, art, grundlage, start, end, rolle, kandidaten FROM sach_bezuege WHERE episode_id = ? "
                "ORDER BY rowid", (episode_id,)).fetchall()
            nutzer = self._conn.execute(
                "SELECT sache, art, aktion, fingerprint FROM sach_nutzer WHERE episode_id = ?", (episode_id,)).fetchall()
            berechnet = self._conn.execute(
                "SELECT 1 FROM sach_quellen WHERE episode_id = ?", (episode_id,)).fetchone() is not None
        aktuell = {n['sache']: n['aktion'] for n in nutzer if nutzer_gilt(n['fingerprint'], digest)}
        veraltet = [{'sache': n['sache'], 'art': n['art'], 'aktion': n['aktion']}
                    for n in nutzer if not nutzer_gilt(n['fingerprint'], digest)]
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
            for eintrag in self.episodes.participants_for_address(kennung[2:], anzeigenamen=True):
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
        # Gemerkt je Stand der Datei (Befund A4): Dieselbe Organisation wird je Frage oft benannt.
        from .zwischenspeicher import marke
        stand = marke(self._conn, self.episodes._lock)
        gemerkt = getattr(self, '_namen_gemerkt', None)
        if gemerkt is None or gemerkt[0] != stand:
            gemerkt = self._namen_gemerkt = (stand, {})
        if quellen is None and sache in gemerkt[1]:
            return gemerkt[1][sache]
        name = self._name_aus_quellen(sache, kennung, quellen if quellen is not None else self.quellen_von(sache))
        if quellen is None:
            gemerkt[1][sache] = name
        return name

    def _name_aus_quellen(self, sache: str, kennung: str, alle: list[dict[str, Any]]) -> str:
        # Befund A7: Eine Schreibweise aus dem Text (Erwähnung, Signatur, Absendername) geht der Domäne vor, auch aus
        # einer der 20 jüngsten Quellen („Müller Bau GmbH“ statt „Mueller Bau“); die Domäne erst danach.
        mails = [q for q in alle if q.get('art') == 'message']
        for nur_text, juengste in ((True, alle[:5] + mails[:20]), (False, alle[:5])):
            for quelle in juengste:
                text = self._schreibweise(sache, quelle['episode_id'], nur_text=nur_text)
                if text:
                    return text
        return kennung[2:] if kennung.startswith('n:') else kennung

    def beschriftungen(self, sachen: list[str]) -> dict[str, str]:
        """Namen mehrerer Sachen. Die Personen einer Liste werden in einem Durchgang über den Bestand
        gelesen statt einzeln (jede Einzelabfrage einer Adresse durchsucht alle Quellen)."""
        adressen = [zerlegen(s)[1][2:] for s in sachen if (zerlegen(s) or ('', ''))[0] == 'person'
                    and zerlegen(s)[1].startswith('a:')]
        gefunden = self.episodes.participants_for_addresses(adressen, anzeigenamen=True) if adressen else {}
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

    def _schreibweise(self, sache: str, episode_id: str, *, nur_text: bool = False) -> str:
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
                # Befund A7: Wie die Organisation sich selbst schreibt (Signatur, Absendername), wenn eine Zeile der Quelle
                # genau den Namen der Domäne in Umschrift trägt („Universität Gießen“ für `universitaet-giessen`).
                # Sonst die Domäne; Umlaute werden nie geraten.
                signatur = (' '.join(str(nennung.name or '').split())
                            if org_vergleich(nennung.name or '') == org_vergleich(domaenenname(nennung.adresse))
                            else _name_in_signatur(episode.body, domaenenname(nennung.adresse)))
                if signatur or nur_text:
                    return signatur
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
