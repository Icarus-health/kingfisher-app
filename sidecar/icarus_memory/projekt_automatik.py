"""Projekte von selbst (Paket P, `docs/66-automatik.md`): klare Projekte anlegen, Mails nach Absender zuordnen.

Ein Projekt ist Ablage, kein Fakt (`docs/30-akten.md`, „Ein Projekt ist Ablage, kein Fakt“). Deshalb darf Kingfisher
es selbst anlegen und Mails selbst zuordnen, aber nur, wenn es klar ist, immer sichtbar, mit Grund und „Rückgängig“,
und ein Zurücknehmen wird gemerkt, damit dasselbe nicht wiederkommt. Über Personen wird nichts gespeichert: Wer zu
einem Projekt gehört, bleibt abgeleitet (die Beteiligten aus denselben Quellen, `akten.py`, `graph.py`).

Zwei Wege, beide ohne Modell und deterministisch:

* **Klare Projekte anlegen** (`einschaetzen`, `projekte_anlegen`). Aus den Vorschlägen „Neue Akte?“
  (`akten_vorschlaege.kandidaten`) wird ein Projekt angelegt, wenn alles zutrifft: mindestens `KLAR_QUELLEN`
  Quellen **und** `KLAR_PERSONEN` verschiedene Personen, die jüngste Quelle höchstens `KLAR_AKTIV_TAGE` Tage alt,
  kein ähnlicher Name eines vorhandenen Projekts oder einer anderen Erwähnung (eindeutig), nie abgelehnt und nie
  zurückgenommen. Höchstens `MAX_JE_TAG` am Kalendertag; was darüber hinausgeht oder unklar ist, bleibt die Frage
  „Neue Akte?“. Angelegt wird wie beim Klick (`akten_vorschlaege.annehmen`), die Zuordnungen sind als eigene gemerkt.
* **Absenderregel** (`absender_ziel`, `absender_schritt`). Eine neue Mail, deren Absender (im selben Konto) mindestens
  `project_suggestions.MIN_AGREEING` frühere Mails hat, die **alle** in demselben offenen Projekt liegen, kommt in
  dieses Projekt. Nie bei eigenen Mails, nie bei Rundmails (mehr als `MAX_EMPFAENGER` Empfänger), nie bei einem
  Absender mit Mails in mehreren Projekten oder ohne Projekt, nie bei einer Mail, deren Zuordnung zurückgenommen wurde.
  Jede Mail einmal (Zeilenstand wie `aufgaben_post.py`); der erste Lauf setzt nur den Stand.

**Rückgängig.** Ein angelegtes Projekt nimmt `zuruecknehmen` zurück: Es löst genau die Zuordnungen, die Kingfisher
gesetzt hat und die der Nutzer seither nicht selbst geändert hat (`EpisodeStore.link_project` vergisst die
automatische Zuordnung, sobald jemand anderes sie setzt), entfernt das Projekt, wenn nichts anderes daran hängt, und
merkt „abgelehnt“ samt Sperre: Es kommt weder als Projekt noch als Frage wieder. Eine Mail der Absenderregel nimmt
`zuordnung_zuruecknehmen` zurück und sperrt sie für die Regel.

**Ablage** (Migration 25 der Episoden, nur Verweise und Zahlen, kein Text): `projekt_automatik_anlagen` (Kennung des
Vorschlags, Projekt, Zeitpunkt, Grund als Zahlen und Sachen-Kennungen, zurückgenommen), `projekt_automatik_zuordnungen`
(Quelle, Projekt, Art `akte` oder `absender`, Zeitpunkt), `projekt_automatik_sperren` (`akte:<Kennung>`,
`mail:<Quelle>`), `projekt_automatik_stand` (Zeilenstand der Absenderregel).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from . import akten_vorschlaege as vorschlaege
from .bezuege import zerlegen
from .datumstext import iso_versuchen

logger = logging.getLogger(__name__)

#: Klar heißt: alle Bedingungen zugleich (eine allein reicht nur für die Frage „Neue Akte?“).
KLAR_QUELLEN = 3
KLAR_PERSONEN = 2
KLAR_AKTIV_TAGE = 30
#: So viele Projekte legt Kingfisher an einem Kalendertag höchstens selbst an; der Rest bleibt Frage.
MAX_JE_TAG = 3
#: Mehr Empfänger sind eine Rundmail: nie nach Absender zuordnen (wie `aufgaben_post.MAX_EMPFAENGER`).
MAX_EMPFAENGER = 5
#: So viele neue Mails sieht die Absenderregel je Takt.
JE_TAKT = 200
#: So lange steht ein neues Projekt auf Heute.
SICHTBAR_TAGE = 3
#: Ab dieser Länge gilt ein Name, der in einem anderen steckt, als ähnlich („umbau“ in „umbaupraxis“).
AEHNLICH_MIN = 4

ARTEN = ('akte', 'absender')
TABLES = {
    'projekt_automatik_anlagen': {'kennung', 'projekt_id', 'zeit', 'grund', 'zurueckgenommen'},
    'projekt_automatik_zuordnungen': {'episode_id', 'projekt_id', 'art', 'zeit'},
    'projekt_automatik_sperren': {'schluessel', 'zeit'},
    'projekt_automatik_stand': {'name', 'wert'},
}
PRIMARY_KEYS = {'projekt_automatik_anlagen': {'kennung'}, 'projekt_automatik_zuordnungen': {'episode_id'},
                'projekt_automatik_sperren': {'schluessel'}, 'projekt_automatik_stand': {'name'}}


def migrate(connection: sqlite3.Connection) -> None:
    """Migration 25 der Episoden: was Kingfisher an Projekten selbst angelegt und zugeordnet hat (nur Verweise)."""
    connection.execute("""CREATE TABLE projekt_automatik_anlagen (
        kennung TEXT PRIMARY KEY,
        projekt_id TEXT NOT NULL,
        zeit REAL NOT NULL,
        grund TEXT NOT NULL DEFAULT '{}',
        zurueckgenommen REAL)""")
    connection.execute("""CREATE TABLE projekt_automatik_zuordnungen (
        episode_id TEXT PRIMARY KEY,
        projekt_id TEXT NOT NULL,
        art TEXT NOT NULL CHECK(art IN ('akte','absender')),
        zeit REAL NOT NULL)""")
    connection.execute("""CREATE TABLE projekt_automatik_sperren (
        schluessel TEXT PRIMARY KEY,
        zeit REAL NOT NULL)""")
    connection.execute("""CREATE TABLE projekt_automatik_stand (
        name TEXT PRIMARY KEY,
        wert INTEGER NOT NULL)""")


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


# -- Ablage ------------------------------------------------------------------------------------


class Ablage:
    """Was Kingfisher selbst getan hat, und was es nicht wieder tun soll. Nur Verweise."""

    def __init__(self, episodes: Any) -> None:
        self.episodes = episodes

    def _eine(self, sql: str, werte: tuple) -> sqlite3.Row | None:
        with self.episodes._lock:
            return self.episodes._conn.execute(sql, werte).fetchone()

    def _alle(self, sql: str, werte: tuple = ()) -> list[sqlite3.Row]:
        with self.episodes._lock:
            return self.episodes._conn.execute(sql, werte).fetchall()

    def _schreiben(self, sql: str, werte: tuple) -> int:
        with self.episodes.transaction():
            return self.episodes._conn.execute(sql, werte).rowcount

    @staticmethod
    def _anlage(zeile: sqlite3.Row | None) -> dict[str, Any] | None:
        if zeile is None:
            return None
        try:
            grund = json.loads(zeile['grund'] or '{}')
        except ValueError:
            grund = {}
        return {'kennung': zeile['kennung'], 'projekt_id': zeile['projekt_id'], 'zeit': zeile['zeit'],
                'grund': grund if isinstance(grund, dict) else {}, 'zurueckgenommen': zeile['zurueckgenommen']}

    # Anlagen

    def anlage(self, kennung: str) -> dict[str, Any] | None:
        return self._anlage(self._eine('SELECT * FROM projekt_automatik_anlagen WHERE kennung = ?', (kennung,)))

    def anlage_nach_projekt(self, projekt_id: str) -> dict[str, Any] | None:
        return self._anlage(self._eine('SELECT * FROM projekt_automatik_anlagen WHERE projekt_id = ? '
                                       'ORDER BY zeit DESC LIMIT 1', (projekt_id,)))

    def anlagen_seit(self, zeit: float) -> list[dict[str, Any]]:
        """Nicht zurückgenommene Anlagen ab `zeit` (Sekunden), jüngste zuerst."""
        return [a for a in (self._anlage(z) for z in self._alle(
            'SELECT * FROM projekt_automatik_anlagen WHERE zeit >= ? AND zurueckgenommen IS NULL ORDER BY zeit DESC',
            (zeit,))) if a]

    def angelegt_seit(self, zeit: float) -> int:
        """Wie viele Kingfisher ab `zeit` angelegt hat, auch zurückgenommene (die Tagesgrenze zählt jeden Versuch)."""
        zeile = self._eine('SELECT COUNT(*) FROM projekt_automatik_anlagen WHERE zeit >= ?', (zeit,))
        return int(zeile[0]) if zeile else 0

    def anlage_merken(self, kennung: str, projekt_id: str, grund: dict[str, Any], zeit: float) -> None:
        self._schreiben('INSERT INTO projekt_automatik_anlagen VALUES (?,?,?,?,NULL) ON CONFLICT(kennung) DO UPDATE SET '
                        'projekt_id=excluded.projekt_id, zeit=excluded.zeit, grund=excluded.grund, zurueckgenommen=NULL',
                        (kennung, projekt_id, zeit, json.dumps(grund, ensure_ascii=False)))

    def anlage_zurueck(self, kennung: str, zeit: float) -> None:
        self._schreiben('UPDATE projekt_automatik_anlagen SET zurueckgenommen = ? WHERE kennung = ?', (zeit, kennung))

    # Zuordnungen

    def zuordnen(self, episode_ids: Iterable[str], projekt_id: str, art: str, zeit: float) -> None:
        if art not in ARTEN:
            raise ValueError('Unbekannte Art der Zuordnung.')
        with self.episodes.transaction():
            for episode_id in dict.fromkeys(episode_ids):
                self.episodes._conn.execute(
                    'INSERT OR REPLACE INTO projekt_automatik_zuordnungen VALUES (?,?,?,?)',
                    (episode_id, projekt_id, art, zeit))

    def zuordnung(self, episode_id: str) -> dict[str, Any] | None:
        zeile = self._eine('SELECT * FROM projekt_automatik_zuordnungen WHERE episode_id = ?', (episode_id,))
        return dict(zeile) if zeile else None

    def zuordnungen_von(self, projekt_id: str) -> list[str]:
        return [z[0] for z in self._alle('SELECT episode_id FROM projekt_automatik_zuordnungen WHERE projekt_id = ? '
                                         'ORDER BY zeit, episode_id', (projekt_id,))]

    # Sperren und Stand

    def sperren(self, schluessel: str, zeit: float) -> None:
        self._schreiben('INSERT OR IGNORE INTO projekt_automatik_sperren VALUES (?,?)', (schluessel, zeit))

    def gesperrt(self, schluessel: str) -> bool:
        return self._eine('SELECT 1 FROM projekt_automatik_sperren WHERE schluessel = ?', (schluessel,)) is not None

    def stand(self, name: str) -> int | None:
        zeile = self._eine('SELECT wert FROM projekt_automatik_stand WHERE name = ?', (name,))
        return int(zeile[0]) if zeile else None

    def stand_setzen(self, name: str, wert: int) -> None:
        self._schreiben('INSERT INTO projekt_automatik_stand VALUES (?,?) ON CONFLICT(name) DO UPDATE SET '
                        'wert=excluded.wert', (name, int(wert)))


# -- Klar oder unklar --------------------------------------------------------------------------


@dataclass(frozen=True)
class Einschaetzung:
    """Ob ein Vorschlag klar genug ist, ihn selbst anzulegen; sonst die Gründe, warum er Frage bleibt."""

    klar: bool
    gruende: tuple[str, ...]
    """Warum nicht klar, je ein kurzer Satzteil („nur eine Person beteiligt“); leer, wenn klar."""
    satz: str
    """Der Grund in einem Satz, wie er auf Heute und in der Akte steht („In 4 Mails seit 3. Oktober mit …“)."""


def _levenshtein_hoechstens_eins(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = fehler = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            fehler += 1
            if fehler > 1:
                return False
            if len(a) == len(b):
                i += 1
            j += 1
            continue
        i += 1
        j += 1
    return fehler + (len(b) - j) + (len(a) - i) <= 1


def aehnlich(a: str, b: str) -> bool:
    """Zwei Namen in Vergleichsform (ohne „Projekt“, nur Buchstaben und Ziffern, Umlaute ausgeschrieben) sind ähnlich,
    wenn sie gleich sind, einer im anderen steckt („umbau“ in „umbaupraxis“, ab `AEHNLICH_MIN` Zeichen) oder sie
    sich in höchstens einem Zeichen unterscheiden („atlas“, „atlass“, ab fünf Zeichen)."""
    if not a or not b:
        return False
    if a == b:
        return True
    kurz, lang = sorted((a, b), key=len)
    if len(kurz) >= AEHNLICH_MIN and kurz in lang:
        return True
    return len(kurz) >= 5 and _levenshtein_hoechstens_eins(a, b)


def vergleichsform(name: str) -> str:
    return vorschlaege._vergleichsform(name)


def einschaetzen(vorschlag: vorschlaege.Vorschlag, *, jetzt: datetime, vorhandene: dict[str, str],
                 andere: dict[str, str], gesperrt: bool = False) -> Einschaetzung:
    """Klar oder unklar, mit Begründung. `vorhandene` und `andere` bilden Vergleichsformen auf Anzeigenamen ab:
    die Namen vorhandener Projekte und die der übrigen erwähnten Projekte (ohne diesen Vorschlag)."""
    gruende: list[str] = []
    if vorschlag.anzahl < KLAR_QUELLEN:
        gruende.append('nur eine Quelle' if vorschlag.anzahl == 1 else f'nur {vorschlag.anzahl} Quellen')
    personen = len(vorschlag.beteiligte)
    if personen < KLAR_PERSONEN:
        gruende.append('nur eine Person beteiligt' if personen == 1 else 'keine Person beteiligt')
    letzte = iso_versuchen(vorschlag.letzte) if vorschlag.letzte else None
    if letzte is None or letzte < jetzt - timedelta(days=KLAR_AKTIV_TAGE):
        gruende.append(f'seit über {KLAR_AKTIV_TAGE} Tagen still')
    eigene = vergleichsform(vorschlag.name)
    for form, name in vorhandene.items():
        if aehnlich(eigene, form):
            gruende.append(f'ähnlich wie das Projekt „{name}“')
            break
    for form, name in andere.items():
        if form != eigene and aehnlich(eigene, form):
            gruende.append(f'Name nicht eindeutig (auch „{name}“)')
            break
    if gesperrt:
        gruende.append('früher zurückgenommen')
    return Einschaetzung(klar=not gruende, gruende=tuple(gruende), satz=vorschlag.grund)


# -- Klare Projekte anlegen ----------------------------------------------------------------------


def _tagesbeginn(jetzt: datetime) -> float:
    ort = jetzt.astimezone()
    return ort.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _erwaehnte_namen(bezuege: Any) -> dict[str, str]:
    """Vergleichsform → Name aller erwähnten, noch nicht angelegten Projekte (auch unter der Schwelle)."""
    namen: dict[str, str] = {}
    for eintrag in bezuege.sachen(art='projekt', limit=vorschlaege.MAX_SACHEN)['sachen']:
        teile = zerlegen(eintrag['sache'])
        if teile is None or not teile[1].startswith('n:'):
            continue
        kennung = teile[1][2:]
        namen.setdefault(vergleichsform(kennung), kennung)
    return namen


def _grund(vorschlag: vorschlaege.Vorschlag) -> dict[str, Any]:
    """Der Grund als Zahlen und Verweise (keine Namen, kein Text): Er wird bei der Anzeige neu beschriftet."""
    return {'anzahl': vorschlag.anzahl, 'tage': vorschlag.tage, 'erste': vorschlag.erste, 'letzte': vorschlag.letzte,
            'arten': sorted(vorschlag.arten), 'personen': [b['sache'] for b in vorschlag.beteiligte]}


def grund_satz(bezuege: Any, grund: dict[str, Any]) -> str:
    """„In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun“ aus dem gemerkten Grund."""
    personen = [str(p) for p in grund.get('personen') or [] if isinstance(p, str)]
    try:
        namen = bezuege.beschriftungen(personen) if personen else {}
    except Exception:  # noqa: BLE001 - ohne Namen bleibt der Satz mit Zahl und Datum
        namen = {}
    return vorschlaege.grund_satz(int(grund.get('anzahl') or 0), set(grund.get('arten') or []),
                                  iso_versuchen(grund.get('erste')) if grund.get('erste') else None,
                                  [namen.get(p, '') for p in personen if namen.get(p)])


def projekte_anlegen(bezuege: Any, workspace: Any, *, jetzt: datetime | None = None, audit: Any = None,
                     logbuch: Any = None) -> list[dict[str, Any]]:
    """Legt die klaren Vorschläge an (höchstens `MAX_JE_TAG` am Tag); unklare bleiben Frage. Gibt die Anlagen zurück."""
    if workspace is None:
        return []
    jetzt = jetzt or _jetzt()
    ablage = Ablage(bezuege.episodes)
    kandidaten = vorschlaege.kandidaten(bezuege, workspace)
    if not kandidaten:
        return []
    heute = ablage.angelegt_seit(_tagesbeginn(jetzt))
    if heute >= MAX_JE_TAG:
        return []
    vorhandene = {vergleichsform(p.name): p.name for p in workspace.projects(include_closed=True)
                  if vergleichsform(p.name)}
    andere = _erwaehnte_namen(bezuege)
    angelegt: list[dict[str, Any]] = []
    for vorschlag in kandidaten:
        if heute + len(angelegt) >= MAX_JE_TAG:
            break
        eigene = vergleichsform(vorschlag.name)
        einschaetzung = einschaetzen(vorschlag, jetzt=jetzt, vorhandene=vorhandene,
                                     andere={k: v for k, v in andere.items() if k != eigene},
                                     gesperrt=ablage.gesperrt('akte:' + vorschlag.kennung))
        if not einschaetzung.klar:
            continue
        try:
            ergebnis = vorschlaege.annehmen(bezuege, workspace, vorschlag, audit=audit)
        except vorschlaege.SchonEntschieden:
            continue
        pid = ergebnis['projekt']['id']
        zeit = jetzt.timestamp()
        ablage.anlage_merken(vorschlag.kennung, pid, _grund(vorschlag), zeit)
        gemerkt = vorschlaege.Entscheidungen(bezuege.episodes).zu(vorschlag.kennung) or {}
        ablage.zuordnen(gemerkt.get('quellen') or [], pid, 'akte', zeit)
        vorhandene[eigene] = ergebnis['projekt']['name']
        if logbuch is not None:
            logbuch.vermerke('akte_vorschlag', entscheidung='angenommen', sache=ergebnis['sache'],
                             name=ergebnis['projekt']['name'], kennung=vorschlag.kennung, von='automatisch')
        angelegt.append({**ergebnis, 'grund': einschaetzung.satz})
    return angelegt


# -- Absenderregel -------------------------------------------------------------------------------


def _empfaenger(episode: Any) -> int:
    kontakte = list(episode.contacts or [])
    if kontakte:
        return sum(1 for k in kontakte if k.get('rolle') in ('an', 'cc', 'bcc'))
    return max(0, len(episode.participants or []) - 1)


def _zeitpunkt(episode: Any) -> datetime:
    return episode.occurred_at or episode.recorded_at


def absender_ziel(episodes: Any, episode: Any, *, eigene: Iterable[str] = (), offen: set[str] | None = None,
                  ablage: Ablage | None = None) -> str | None:
    """Das Projekt, in das eine neue Mail nach ihrem Absender gehört, oder None.

    Nur, wenn **alle** früheren Mails desselben Absenders im selben Konto (mindestens `MIN_AGREEING`) in genau einem
    offenen Projekt liegen. Nie bei eigenen Mails, Rundmails, schon zugeordneten oder gesperrten Mails.
    """
    from .episodes import mail_address
    from .project_suggestions import MIN_AGREEING, _identity, same_sender
    if episode.project_id is not None:
        return None
    ablage = ablage or Ablage(episodes)
    if ablage.gesperrt('mail:' + episode.id):
        return None
    identitaet = _identity(episode)
    if identitaet is None:
        return None
    if identitaet[1] in {mail_address(a) for a in eigene if mail_address(a)}:
        return None
    if _empfaenger(episode) > MAX_EMPFAENGER:
        return None
    zeit = _zeitpunkt(episode)
    frueher = [p for p in same_sender(episodes, episode) if _zeitpunkt(p) < zeit]
    if len(frueher) < MIN_AGREEING:
        return None
    projekte = {p.project_id for p in frueher}
    if len(projekte) != 1 or None in projekte:
        return None
    ziel = next(iter(projekte))
    if offen is not None and ziel not in offen:
        return None
    return ziel


def absender_schritt(episodes: Any, workspace: Any, *, eigene: Iterable[str] = (), jetzt: datetime | None = None,
                     audit: Any = None, limit: int = JE_TAKT) -> list[str]:
    """Ein Takt der Absenderregel über die neuen Mails; jede einmal. Gibt die zugeordneten Quellen-IDs zurück."""
    ablage = Ablage(episodes)
    stand = ablage.stand('absender')
    if stand is None:
        ablage.stand_setzen('absender', episodes.letzte_zeile())
        return []
    if workspace is None:
        return []
    offen = {p.id for p in workspace.projects(include_closed=False, limit=10000) if p.is_open()}
    eigene = list(eigene)
    zeit = (jetzt or _jetzt()).timestamp()
    zugeordnet: list[str] = []
    letzte = stand
    for zeile, episode in episodes.mails_ab(stand, limit):
        letzte = zeile
        try:
            ziel = absender_ziel(episodes, episode, eigene=eigene, offen=offen, ablage=ablage)
            if ziel is None:
                continue
            episodes.link_project(episode.id, ziel, automatisch=True)
            ablage.zuordnen([episode.id], ziel, 'absender', zeit)
            zugeordnet.append(episode.id)
        except Exception:  # noqa: BLE001 - fail closed: diese Mail bleibt ohne Projekt, der Takt läuft weiter
            logger.exception('Absenderregel: Mail konnte nicht geprüft werden')
    if letzte != stand:
        ablage.stand_setzen('absender', letzte)
    if audit is not None and zugeordnet:
        try:
            audit.record('quellen_projekt_zuordnen', 'write_local', 'auto', 'executed',
                         {'episode_ids': zugeordnet, 'regel': 'absender'})
        except Exception:  # noqa: BLE001 - das Protokoll darf die Ablage nicht aufhalten
            pass
    return zugeordnet


# -- Rückgängig ------------------------------------------------------------------------------------


def zuruecknehmen(bezuege: Any, workspace: Any, kennung: str, *, tasks: Any = None, audit: Any = None,
                  jetzt: datetime | None = None) -> dict[str, Any]:
    """Nimmt eine Entscheidung zu „Neue Akte?“ zurück. War es eine Anlage durch Kingfisher, werden nur dessen eigene
    Zuordnungen gelöst, und „abgelehnt“ samt Sperre gemerkt: Das Projekt kommt nicht wieder. Hat der Nutzer selbst
    angelegt, gilt das Zurücknehmen wie bisher (die Frage steht wieder), aber Kingfisher legt es nie selbst an."""
    ablage = Ablage(bezuege.episodes)
    zeit = (jetzt or _jetzt()).timestamp()
    gemerkt = vorschlaege.Entscheidungen(bezuege.episodes).zu(kennung)
    anlage = ablage.anlage(kennung)
    if (anlage is not None and anlage['zurueckgenommen'] is None and gemerkt is not None
            and gemerkt['entscheidung'] == 'angenommen' and gemerkt['projekt_id'] == anlage['projekt_id']):
        eigene = ablage.zuordnungen_von(anlage['projekt_id'])
        ergebnis = vorschlaege.zuruecknehmen(bezuege, workspace, kennung, tasks=tasks, audit=audit, quellen=eigene,
                                             danach='abgelehnt')
        ablage.anlage_zurueck(kennung, zeit)
        ablage.sperren('akte:' + kennung, zeit)
        ergebnis['satz'] = ergebnis['satz'].rstrip('.') + '. Kingfisher legt es nicht wieder an.'
        ergebnis['automatisch'] = True
        return ergebnis
    ergebnis = vorschlaege.zuruecknehmen(bezuege, workspace, kennung, tasks=tasks, audit=audit)
    if gemerkt is not None and gemerkt['entscheidung'] == 'angenommen':
        ablage.sperren('akte:' + kennung, zeit)
    return ergebnis


class NichtAutomatisch(Exception):
    """Diese Quelle hat Kingfisher nicht selbst zugeordnet (oder der Nutzer hat es seither geändert)."""


def zuordnung_zuruecknehmen(episodes: Any, episode_id: str, *, jetzt: datetime | None = None,
                            audit: Any = None) -> dict[str, Any]:
    """Löst eine automatische Zuordnung und sperrt die Quelle für die Absenderregel. `NichtAutomatisch`, wenn es
    keine gibt oder die Quelle inzwischen woanders liegt (dann gilt, was der Nutzer gesetzt hat)."""
    ablage = Ablage(episodes)
    eintrag = ablage.zuordnung(episode_id)
    if eintrag is None:
        raise NichtAutomatisch('Diese Quelle hat Kingfisher nicht selbst zugeordnet.')
    episode = episodes.get(episode_id)
    if episode.project_id != eintrag['projekt_id']:
        raise NichtAutomatisch('Die Zuordnung hat sich inzwischen geändert.')
    episodes.link_project(episode_id, None)
    ablage.sperren('mail:' + episode_id, (jetzt or _jetzt()).timestamp())
    if audit is not None:
        try:
            audit.record('quelle_projekt_zuordnen', 'write_local', 'auto', 'executed',
                         {'episode_id': episode_id, 'project_id': None, 'rueckgaengig': eintrag['art']})
        except Exception:  # noqa: BLE001
            pass
    return {'episode_id': episode_id, 'projekt_id': eintrag['projekt_id'],
            'satz': 'Wieder keinem Projekt zugeordnet. Kingfisher ordnet diese Mail nicht wieder zu.'}


# -- Anzeige -------------------------------------------------------------------------------------


def herkunft(episodes: Any, episode: Any) -> dict[str, Any] | None:
    """Wie die Quelle zu ihrem Projekt kam, wenn Kingfisher es war: `art` und ein kurzer Satz. None sonst."""
    try:
        eintrag = Ablage(episodes).zuordnung(episode.id)
    except sqlite3.Error:
        return None
    if eintrag is None or episode.project_id != eintrag['projekt_id']:
        return None
    satz = 'Zugeordnet nach Absender' if eintrag['art'] == 'absender' else 'Mit dem Projekt von Kingfisher zugeordnet'
    return {'art': eintrag['art'], 'projekt_id': eintrag['projekt_id'], 'satz': satz}


def neue_projekte(bezuege: Any, workspace: Any, *, jetzt: datetime | None = None) -> list[dict[str, Any]]:
    """Was Kingfisher in den letzten `SICHTBAR_TAGE` Tagen selbst angelegt hat und noch gilt, jüngste zuerst: Name,
    Akte, Grund. Für den Hinweis auf Heute."""
    from .workspace import WorkspaceError
    jetzt = jetzt or _jetzt()
    ergebnis = []
    for anlage in Ablage(bezuege.episodes).anlagen_seit((jetzt - timedelta(days=SICHTBAR_TAGE)).timestamp()):
        try:
            projekt = workspace.project(anlage['projekt_id'])
        except (WorkspaceError, AttributeError):
            continue
        if not projekt.is_open():
            continue
        grund = anlage['grund']
        personen = [str(p) for p in grund.get('personen') or [] if isinstance(p, str)]
        try:
            namen = bezuege.beschriftungen(personen) if personen else {}
        except Exception:  # noqa: BLE001
            namen = {}
        sache = f'projekt:{projekt.id}'
        ergebnis.append({'kennung': anlage['kennung'], 'projekt_id': projekt.id, 'name': projekt.name, 'sache': sache,
                         'link': vorschlaege.link_zur_akte(sache), 'anzahl': int(grund.get('anzahl') or 0),
                         'wort': vorschlaege.quellen_wort(set(grund.get('arten') or [])),
                         'personen': [namen[p] for p in personen if namen.get(p)][:vorschlaege.MAX_NAMEN],
                         'grund': grund_satz(bezuege, grund),
                         'zeit': datetime.fromtimestamp(anlage['zeit'], timezone.utc).isoformat()})
    return ergebnis


def ergaenzen(episodes: Any, bezuege: Any, entscheidung: dict[str, Any]) -> dict[str, Any]:
    """Die öffentliche Entscheidung (`akten_vorschlaege.oeffentlich`) um die Herkunft: `automatisch` mit dem Grund,
    sonst `nutzer`."""
    anlage = Ablage(episodes).anlage(entscheidung.get('kennung', ''))
    if anlage is None:
        return {**entscheidung, 'herkunft': 'nutzer'}
    return {**entscheidung, 'herkunft': 'automatisch', 'grund': grund_satz(bezuege, anlage['grund'])}


# -- Ein Takt --------------------------------------------------------------------------------------

_LAUF = threading.Lock()


def schritt_fuer(app: Any, *, projekte: bool = True) -> dict[str, int]:
    """Ein Takt nach der Mailaufnahme und vor dem Briefing: erst die Absenderregel, dann (wenn die Bezüge fertig
    berechnet sind) die klaren Projekte. Ohne Modell; ein Fehler hält nichts auf."""
    from . import identitaet
    from .akten_routes import bausteine, nachfuehren
    bericht = {'zugeordnet': 0, 'angelegt': 0}
    workspace = getattr(app.state, 'workspace', None)
    with _LAUF:
        try:
            bericht['zugeordnet'] = len(absender_schritt(
                app.state.episodes, workspace, eigene=identitaet.eigene_adressen(getattr(app.state, 'settings', None)),
                audit=getattr(app.state, 'audit', None)))
        except Exception:  # noqa: BLE001
            logger.exception('Absenderregel gescheitert')
        if not projekte or workspace is None:
            return bericht
        try:
            if nachfuehren(app)['offen']:
                return bericht   # erst mit allen Bezügen ist „klar“ wirklich klar
            bezuege, _ = bausteine(app)
            angelegt = projekte_anlegen(bezuege, workspace, audit=getattr(app.state, 'audit', None),
                                        logbuch=getattr(app.state, 'logbuch', None))
            bericht['angelegt'] = len(angelegt)
            if angelegt:
                nachfuehren(app)
        except Exception:  # noqa: BLE001
            logger.exception('Klare Projekte konnten nicht angelegt werden')
    return bericht


__all__ = ['AEHNLICH_MIN', 'Ablage', 'Einschaetzung', 'JE_TAKT', 'KLAR_AKTIV_TAGE', 'KLAR_PERSONEN', 'KLAR_QUELLEN',
           'MAX_EMPFAENGER', 'MAX_JE_TAG', 'NichtAutomatisch', 'SICHTBAR_TAGE', 'absender_schritt', 'absender_ziel',
           'aehnlich', 'einschaetzen', 'ergaenzen', 'grund_satz', 'herkunft', 'neue_projekte', 'projekte_anlegen',
           'schritt_fuer', 'zuordnung_zuruecknehmen', 'zuruecknehmen']
