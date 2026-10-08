"""Akten (Etappe D2, Ebene 2): eine Akte je Sache, abgeleitet und ohne Modell.

Eine Akte fasst alles zu einer Sache zusammen (Person, Organisation, Projekt,
Ort, Thema), was die Quellen darüber sagen. Sie ist **nie Fakt und nie
Quelle**: Jede Zeile ist ein Zitat aus Ebene 1 (`working_memory_*`) und verweist auf
ihre Quelle. Bezüge kommen aus `bezuege.py`, Bausteine und Prüfungen aus
`mappe.py` (dieselbe Gültigkeitsprüfung, dieselbe Zeile, dieselben Aufgaben).

Abschnitte:

* **Verlauf**: die verknüpften Quellen, jüngste zuerst, je eine Zeile aus Ebene 1
  (sonst der Titel), mit Grundlage des Bezugs.
* **Offen**: Bitten und Zusagen, zu denen keine spätere Erledigung oder Absage
  vorliegt. Die Akte **behauptet nicht**, dass etwas offen ist: Es heißt
  „vermutlich offen“. Erledigt oder abgesagt gilt ein Punkt, wenn eine spätere
  Meldung derselben Sache (Art Änderung oder Stand) denselben Gegenstand nennt und
  ein Erledigt- oder Absagewort trägt, oder wenn die Aufgabe dazu erledigt ist.
  Nennt eine spätere Meldung den Gegenstand ohne solches Wort, bleibt der Punkt
  offen und trägt den Hinweis „danach geändert“.
* **Fristen**: Datumsangaben in Bitten, Zusagen und Änderungen (`fristen.py`),
  kommend und verstrichen, jede mit Textstelle. Eine Frist, die eine spätere
  Quelle für denselben Gegenstand verschiebt, steht unter „ersetzt“ und nennt die
  neue.
* **Stand**: je Gegenstand die jüngste Änderung oder Statusmeldung; ältere nur
  als „vorher“. Aktualität schlägt Ähnlichkeit: Die Reihenfolge entscheidet die
  Zeit der Quelle, nicht die Nähe zu einer Frage.
* **Beteiligte**: Sachen, die in denselben Quellen vorkommen, mit Anzahl.
* **Termine**: vergangene und kommende Termine aus Termin-Episoden; nennt eine
  spätere Meldung derselben Sache den Tag mit einem Absagewort, steht dabei
  „vermutlich abgesagt“ mit der Zeile (der Kalendereintrag bleibt oft stehen).
* **Aufgaben**: offene Aufgaben zur Sache (wie in der Mappe).

Gleicher Gegenstand heißt: gemeinsame Wortstämme (mindestens zwei, ohne Monats-,
Wochentags- und Füllwörter), wobei ein gemeinsames langes Wort („Rechnungsanschrift“)
und ein gleiches aufgelöstes Datum doppelt zählen.
Trägt die spätere Meldung ein Erledigt- oder Absagewort, genügt ein gemeinsamer
Wortstamm. Bei Fristen genügt ein gemeinsames Fristwort („Einreichfrist“,
„Anmeldeschluss“).
Das ist bewusst grob und deshalb überall als Vermutung ausgewiesen.

Zwischenspeicher: Die Akte wird nur neu berechnet, wenn sich die Eingaben
ändern (Fingerabdruck über die verknüpften Quellen, ihre Bezugsgrundlagen, ihre
Einordnung und den Stand des Wissensbestands). Gespeichert werden **nur Verweise**
(Quelle, Fassung, Textstellen, Datumswerte); Zitate liest jede Anzeige aus dem
Original. Was von der Uhrzeit abhängt (kommend/verstrichen), rechnet die Anzeige.

Nichts wird still begrenzt: Wo die Akte nur die jüngsten `MAX_QUELLEN` Quellen
auswertet, nennt sie die Gesamtzahl; jede Liste nennt ihre Gesamtzahl.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from . import mappe
from .bezuege import ART_TEXT, Bezuege, zerlegen
from .fristen import bezugstag, fristen_in
from .lexical import terms_v1
from .working_memory_store import WorkingMemoryStore

AKTEN_VERSION = 3
#: So viele der jüngsten Quellen wertet eine Akte aus; die Gesamtzahl steht daneben.
MAX_QUELLEN = 500
MAX_ABSCHNITTE = 8000
JE_LISTE = mappe.JE_LISTE
KURZ = mappe.KURZ
ALLE = mappe.ALLE

OFFEN_ARTEN = ('request', 'commitment')
FRIST_ARTEN = ('request', 'commitment', 'conditional', 'change')
#: Auch eine Angabe („Einreichfrist ist der 15. Oktober“) nennt Fristen, zählt aber nur, wenn sie überholt ist.
FAKT_ARTEN = ('fact', 'status', 'historical', 'uncertain')
STAND_ARTEN = ('change', 'status')
VERLAUF_ARTEN = ('request', 'commitment', 'conditional', 'change', 'status', 'fact')
#: Welche Art einer Quelle die Verlaufszeile stellt, wichtigste zuerst.
VERLAUF_RANG = {art: rang for rang, art in enumerate(('change', 'commitment', 'request', 'status', 'conditional', 'fact'))}

_ERLEDIGT = re.compile(r'\b(?:erledigt|erhalten|geliefert|verschickt|abgeschickt|gesendet|geschickt|abgeschlossen|'
                       r'bezahlt|überwiesen|unterschrieben|bestätigt|eingereicht|übermittelt|zugesagt|fertig)\b', re.I)
_ABSAGE = re.compile(r'\b(?:abgesagt|absagen|absage|storniert|stornierung|entfällt|entfaellt|findet\s+nicht\s+statt|'
                     r'fällt\s+aus|zurückgezogen|gestrichen)\b', re.I)
_FRISTWORT = re.compile(r'\b\w*(?:frist|schluss|deadline|abgabe)\w*\b', re.I)
_FUELLWOERTER = frozenset({
    'bitte', 'danke', 'gern', 'gerne', 'sehr', 'liebe', 'lieber', 'grüße', 'gruß', 'viele', 'beste', 'freundliche',
    'herzliche', 'frau', 'herr', 'guten', 'schon', 'jetzt', 'wieder', 'nach', 'noch', 'dann', 'wenn', 'diese',
    'dieser', 'dieses', 'haben', 'werden', 'wurde', 'wurden', 'sind', 'sein', 'ihre', 'ihren', 'ihrer', 'unser',
    'unsere', 'unserem', 'unseren', 'mir', 'mich', 'ihnen', 'ihnen', 'melde', 'melden', 'bitten', 'schicke',
    'schicken', 'schick', 'kannst', 'könnten', 'können', 'würde', 'würden', 'wäre', 'sollen', 'müssen', 'muss',
    'januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli', 'august', 'september', 'oktober', 'november',
    'dezember', 'montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag', 'uhr'})
_SATZENDE = re.compile(r'(?<=[a-zäöüß)\]])[.!?]\s|\n')


def _stamm(wort: str) -> str:
    return wort[:6]


#: Ab dieser Länge gilt ein Wort als Gegenstandswort („Rechnungsanschrift“, „Einreichfrist“): Sein Stamm zählt doppelt.
LANGES_WORT = 10


def stamm_menge(text: str) -> frozenset[str]:
    """Wortstämme eines Textes ohne Füll-, Monats- und Wochentagswörter (grob: die ersten sechs Buchstaben).

    Lange Wörter tragen ihren Stamm zusätzlich mit Vorsatz „!“: Ein gemeinsames
    Gegenstandswort zählt dadurch doppelt, ein gemeinsames kurzes Wort einfach.
    """
    woerter = [w for w in terms_v1(text) if len(w) >= 4 and not w.isdigit() and w not in _FUELLWOERTER]
    return frozenset([_stamm(w) for w in woerter] + ['!' + _stamm(w) for w in woerter if len(w) >= LANGES_WORT])


#: Fristwörter ohne eigenen Gegenstand: Sie sagen nur „hier ist eine Frist“, nicht wofür.
_FRIST_ALLGEMEIN = frozenset({'frist', 'fristen', 'abgabe', 'abgaben', 'abgabefrist', 'abgabefristen', 'deadline',
                              'deadlines', 'schluss', 'fristende', 'abgabeschluss', 'abgabetermin'})


def _gegenstand(umfeld: str) -> frozenset[str]:
    """Stämme des Umfelds einer Frist ohne die allgemeinen Fristwörter („Frist“, „Abgabe“, „Deadline“).

    Zwei Fristen betreffen dieselbe Sache nur, wenn sie mehr teilen als das Wort „Frist“:
    Jahresbericht bis 15.10. und Steuererklärung bis 30.11. ersetzen einander nicht. Ein
    Kompositum mit Gegenstand („Einreichfrist“) bleibt erhalten und trägt den Vergleich.
    """
    allgemein = [m.group(0).casefold() for m in _FRISTWORT.finditer(umfeld) if m.group(0).casefold() in _FRIST_ALLGEMEIN]
    ohne = {_stamm(w) for w in allgemein} | {'!' + _stamm(w) for w in allgemein}
    return stamm_menge(umfeld) - ohne


def _umfeld(text: str, start: int, ende: int) -> str:
    """Der Satz um eine Textstelle, höchstens rund 200 Zeichen."""
    links = max((m.end() for m in _SATZENDE.finditer(text, 0, start)), default=0)
    rechts = next((m.start() for m in _SATZENDE.finditer(text, ende)), len(text))
    return text[max(links, start - 200):min(rechts, ende + 200)]


@dataclass
class Abschnitt:
    """Ein eingeordneter Abschnitt mit dem, was für die Vergleiche gebraucht wird."""

    ref: dict[str, Any]
    zeit: datetime
    text: str
    stamm: frozenset[str] = frozenset()
    daten: frozenset[date] = frozenset()
    bezug: datetime | None = None

    @property
    def art(self) -> str:
        return self.ref['kind']


def gleicher_gegenstand(a: Abschnitt, b: Abschnitt) -> bool:
    """Grober Vergleich: gemeinsame Wortstämme, gleiche Daten zählen doppelt."""
    return len(a.stamm & b.stamm) + 2 * len(a.daten & b.daten) >= 2


def _zeit(wert: Any) -> datetime:
    return mappe._zeit(wert) or datetime(1970, 1, 1, tzinfo=timezone.utc)


def _ref(abschnitt: Abschnitt) -> dict[str, Any]:
    return {**abschnitt.ref, 'zeit': abschnitt.zeit.isoformat()}


class _MerkeFrei:
    """Merkt `source_is_unclaimed` je Quelle: Der Aufruf durchsucht den Wissensbestand."""

    def __init__(self, claims: Any) -> None:
        self._claims, self._gemerkt = claims, {}

    def source_is_unclaimed(self, episode_id: str) -> bool:
        if episode_id not in self._gemerkt:
            self._gemerkt[episode_id] = self._claims.source_is_unclaimed(episode_id)
        return self._gemerkt[episode_id]


def _wissensstand(claims: Any) -> str:
    """Kurzkennung des Wissensbestands: ändert sich, wenn Aussagen entstehen oder zurückgezogen werden."""
    if claims is None:
        return ''
    try:
        with claims._lock:
            zeile = claims._conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(rowid),0), COALESCE(SUM(length(document)),0) FROM knowledge_claims"
            ).fetchone()
        return ':'.join(str(wert) for wert in zeile)
    except Exception:  # noqa: BLE001 - ohne lesbaren Bestand gilt jeder Stand als anders
        return f'unlesbar:{time.time()}'


# -- Berechnung (ohne Uhrzeit) -----------------------------------------------


def _abschnitte_lesen(ids: list[str], store: WorkingMemoryStore, claims: Any) -> tuple[list[Abschnitt], bool]:
    """Alle gültigen Abschnitte der Quellen mit Text, Wortstämmen und aufgelösten Daten."""
    gefunden = store.items_all(ids, VERLAUF_ARTEN, limit=MAX_ABSCHNITTE)
    ergebnis: list[Abschnitt] = []
    for ref in gefunden['refs']:
        gelesen = mappe.lesen(store, ref, claims)
        if gelesen is None:
            continue
        episode, voll = gelesen
        zeit = episode.reference_time()
        daten: frozenset[date] = frozenset()
        if ref['kind'] in FRIST_ARTEN or ref['kind'] in STAND_ARTEN:
            # `zeit` bleibt Chronologie/Sortierschlüssel; nur das Vorkommnisdatum löst relative Fristen auf.
            daten = frozenset(f.datum for f in fristen_in(voll, episode.occurred_at).fristen)
        ergebnis.append(Abschnitt(ref, zeit, voll, stamm_menge(voll), daten, episode.occurred_at))
    return ergebnis, gefunden['truncated']


def _offen(abschnitte: list[Abschnitt]) -> tuple[list[dict], list[dict]]:
    """(offen, erledigt): Bitten und Zusagen, geprüft gegen spätere Änderungen und Standmeldungen."""
    spaeter = [a for a in abschnitte if a.art in STAND_ARTEN]
    offen, erledigt = [], []
    for x in sorted((a for a in abschnitte if a.art in OFFEN_ARTEN), key=lambda a: a.zeit, reverse=True):
        treffer = sorted((y for y in spaeter if y.zeit > x.zeit and (gleicher_gegenstand(x, y) or (
            x.stamm & y.stamm and (_ABSAGE.search(y.text) or _ERLEDIGT.search(y.text))))), key=lambda y: y.zeit)
        absage = next((y for y in treffer if _ABSAGE.search(y.text)), None)
        fertig = next((y for y in treffer if _ERLEDIGT.search(y.text)), None)
        if absage or fertig:
            durch = absage or fertig
            erledigt.append({'ref': _ref(x), 'durch': _ref(durch), 'grund': 'absage' if absage else 'erledigt'})
        else:
            offen.append({'ref': _ref(x), 'danach': _ref(treffer[-1]) if treffer else None})
    return offen, erledigt


def _fristen(abschnitte: list[Abschnitt]) -> tuple[list[dict], list[dict]]:
    """(fristen, ohne_datum): aufgelöste Datumsangaben mit Textstelle; überholte tragen `ersetzt_durch`."""
    alle: list[dict] = []
    ohne: list[dict] = []
    for a in (x for x in abschnitte if x.art in FRIST_ARTEN):
        suche = fristen_in(a.text, a.bezug)
        for f in suche.fristen:
            umfeld = _umfeld(a.text, f.start, f.ende)
            alle.append({'ref': _ref(a), 'start': f.start, 'ende': f.ende, 'datum': f.datum.isoformat(),
                         'art': f.art, 'ersetzt_durch': None, '_zeit': a.zeit, '_stamm': _gegenstand(umfeld)})
        for ausdruck in suche.ohne_datum:
            beginn = a.text.find(ausdruck)
            ohne.append({'ref': _ref(a), 'start': max(beginn, 0), 'ende': max(beginn, 0) + len(ausdruck)})
    # Angaben mit Fristwort („Einreichfrist“, „Anmeldeschluss“) in Absätzen der Art Angabe oder Stand: Eine Ausschreibung
    # nennt die Frist als Angabe, nicht als Bitte. Sie erscheint nur unter „ersetzt“, wenn eine spätere Zusage, Bitte oder
    # Änderung denselben Gegenstand (dieselben Wortstämme, wie bei jeder Frist) mit einem anderen Datum nennt; sonst wäre jedes Datum in jeder Angabe eine „Frist“.
    fakten: list[dict] = []
    for a in (x for x in abschnitte if x.art in FAKT_ARTEN):
        for f in fristen_in(a.text, a.bezug).fristen:
            umfeld = _umfeld(a.text, f.start, f.ende)
            wort = frozenset(m.group(0).casefold() for m in _FRISTWORT.finditer(umfeld))
            if wort:
                fakten.append({'ref': _ref(a), 'start': f.start, 'ende': f.ende, 'datum': f.datum.isoformat(),
                               'art': f.art, 'ersetzt_durch': None, '_zeit': a.zeit, '_stamm': _gegenstand(umfeld)})

    def neuere_von(f: dict) -> list[dict]:
        return [g for g in alle if g['_zeit'] > f['_zeit'] and g['datum'] != f['datum']
                and len(f['_stamm'] & g['_stamm']) >= 2]

    for f in alle:
        neuere = neuere_von(f)
        if neuere:
            neueste = max(neuere, key=lambda g: (g['_zeit'], g['datum']))
            f['ersetzt_durch'] = {'ref': neueste['ref'], 'start': neueste['start'], 'ende': neueste['ende'],
                                  'datum': neueste['datum']}
    for f in fakten:
        neuere = neuere_von(f)
        if neuere:
            neueste = max(neuere, key=lambda g: (g['_zeit'], g['datum']))
            f['ersetzt_durch'] = {'ref': neueste['ref'], 'start': neueste['start'], 'ende': neueste['ende'],
                                  'datum': neueste['datum']}
            alle.append(f)
    for f in alle:
        for privat in ('_zeit', '_stamm'):
            f.pop(privat)
    alle.sort(key=lambda f: (f['datum'], f['ref']['episode_id'], f['start']))
    return alle, ohne


def _stand(abschnitte: list[Abschnitt]) -> list[dict]:
    """Je Gegenstand die jüngste Änderung oder Statusmeldung; ältere gleichen Gegenstands als „vorher“."""
    gruppen: list[dict[str, Any]] = []
    for a in sorted((x for x in abschnitte if x.art in STAND_ARTEN),
                    key=lambda x: (-x.zeit.timestamp(), x.ref['episode_id'], x.ref['start'])):
        for gruppe in gruppen:
            if gleicher_gegenstand(gruppe['_kopf'], a):
                gruppe['vorher'].append(_ref(a))
                break
        else:
            gruppen.append({'aktuell': _ref(a), 'vorher': [], '_kopf': a})
    for gruppe in gruppen:
        gruppe.pop('_kopf')
    return gruppen


def _verlauf(quellen: list[dict], abschnitte: list[Abschnitt]) -> list[dict]:
    """Je Quelle die aussagekräftigste Zeile aus Ebene 1; ohne Abschnitt bleibt nur der Titel."""
    beste: dict[str, Abschnitt] = {}
    for a in abschnitte:
        alt = beste.get(a.ref['episode_id'])
        if alt is None or (VERLAUF_RANG.get(a.art, 9), a.ref['start']) < (VERLAUF_RANG.get(alt.art, 9), alt.ref['start']):
            beste[a.ref['episode_id']] = a
    return [{'episode_id': q['episode_id'], 'zeit': q['zeit'], 'archiviert': q['archiviert'],
             'grundlagen': q['grundlagen'], 'ref': _ref(beste[q['episode_id']]) if q['episode_id'] in beste else None}
            for q in quellen]


def _termine(quellen: list[dict], abschnitte: list[Abschnitt]) -> list[dict]:
    """Termine der Sache. Nennt eine Meldung derselben Sache den Tag des Termins mit Absagewort, trägt er den Verweis.

    Der Kalendereintrag bleibt oft stehen, wenn eine Mail den Termin absagt. Die
    Akte streicht ihn nicht, sondern nennt die Absage: „vermutlich abgesagt“.
    """
    absagen = [a for a in abschnitte if a.art in STAND_ARTEN and a.daten and _ABSAGE.search(a.text)]
    ergebnis = []
    for q in quellen:
        if q['art'] != 'event':
            continue
        beginn = _zeit(q['zeit'])
        tag = bezugstag(beginn)
        laut = [a for a in absagen if tag in a.daten and bezugstag(a.zeit) <= tag]   # Kalendertag des Nutzers, nicht UTC
        ergebnis.append({'episode_id': q['episode_id'], 'start': q['zeit'],
                         'abgesagt': _ref(max(laut, key=lambda a: a.zeit)) if laut else None})
    return ergebnis


class Akten:
    """Berechnet, speichert und stellt Akten dar. Ohne Modell, ohne eigenen Schreibzugriff auf Quellen."""

    def __init__(self, episodes: Any, bezuege: Bezuege, *, claims: Any = None,
                 aufgaben: Callable[[str, list[str]], Iterable[Any]] = lambda sache, ids: ()) -> None:
        self.episodes = episodes
        self.bezuege = bezuege
        self.claims = claims
        self._aufgaben = aufgaben
        self.store = WorkingMemoryStore(episodes)
        self.letzte_berechnung: dict[str, Any] = {}

    # -- Zwischenspeicher --

    def _eingabe(self, sache: str, quellen: list[dict]) -> str:
        ids = [q['episode_id'] for q in quellen[:MAX_QUELLEN]]
        einordnung = self.store.einordnungsstand(ids)
        inhalt = [AKTEN_VERSION, sache, _wissensstand(self.claims), len(quellen),
                  [(q['episode_id'], q['fp'], q['grundlagen'], q['archiviert'], einordnung.get(q['episode_id'], ''))
                   for q in quellen[:MAX_QUELLEN]]]
        return hashlib.sha256(json.dumps(inhalt, ensure_ascii=False, default=str).encode()).hexdigest()

    def _zwischenspeicher(self, sache: str, eingabe: str) -> dict[str, Any] | None:
        with self.episodes._lock:
            zeile = self.episodes._conn.execute(
                "SELECT eingabe, daten FROM akten_cache WHERE sache = ?", (sache,)).fetchone()
        if zeile and zeile['eingabe'] == eingabe:
            try:
                return json.loads(zeile['daten'])
            except ValueError:
                return None
        return None

    def _speichern(self, sache: str, eingabe: str, roh: dict[str, Any]) -> None:
        with self.episodes.transaction():
            self.episodes._conn.execute(
                "INSERT INTO akten_cache VALUES (?,?,?,?) ON CONFLICT(sache) DO UPDATE SET "
                "eingabe=excluded.eingabe, daten=excluded.daten, berechnet_am=excluded.berechnet_am",
                (sache, eingabe, json.dumps(roh, ensure_ascii=False), time.time()))

    def verwerfen(self, sache: str | None = None) -> None:
        """Löscht den Zwischenspeicher (einer Sache oder aller); die Akte rechnet dann neu."""
        with self.episodes.transaction():
            if sache is None:
                self.episodes._conn.execute("DELETE FROM akten_cache")
            else:
                self.episodes._conn.execute("DELETE FROM akten_cache WHERE sache = ?", (sache,))

    # -- Berechnung --

    def _berechnen(self, sache: str, quellen: list[dict]) -> dict[str, Any]:
        genutzt = quellen[:MAX_QUELLEN]
        ids = [q['episode_id'] for q in genutzt]
        claims = _MerkeFrei(self.claims) if self.claims is not None else None
        abschnitte, abgeschnitten = _abschnitte_lesen(ids, self.store, claims)
        offen, erledigt = _offen(abschnitte)
        fristen, ohne_datum = _fristen(abschnitte)
        gemeinsam = self.bezuege.gemeinsame(sache, ids)
        rang = sorted(gemeinsam.items(), key=lambda p: (-p[1], p[0]))
        return {
            'version': AKTEN_VERSION,
            'gesamt': len(quellen), 'beruecksichtigt': len(genutzt), 'abschnitte_abgeschnitten': abgeschnitten,
            'archiviert': sum(1 for q in quellen if q['archiviert']),
            'verlauf': _verlauf(genutzt, abschnitte),
            'offen': offen, 'erledigt': erledigt, 'fristen': fristen, 'ohne_datum': ohne_datum,
            'stand': _stand(abschnitte),
            'beteiligte': {'gesamt': len(rang), 'eintraege': [{'sache': s, 'anzahl': n} for s, n in rang[:40]]},
            'termine': _termine(genutzt, abschnitte),
        }

    def roh(self, sache: str, quellen: list[dict] | None = None) -> dict[str, Any] | None:
        """Die zwischengespeicherte oder frisch berechnete Akte (nur Verweise); None ohne Quellen."""
        if zerlegen(sache) is None:
            return None
        quellen = quellen if quellen is not None else self.bezuege.quellen_von(sache)
        if not quellen:
            self.letzte_berechnung = {'sache': sache, 'aus_zwischenspeicher': False, 'quellen': 0}
            return None
        eingabe = self._eingabe(sache, quellen)
        roh = self._zwischenspeicher(sache, eingabe)
        gespeichert = roh is not None
        if roh is None:
            begonnen = time.perf_counter()
            roh = self._berechnen(sache, quellen)
            self._speichern(sache, eingabe, roh)
            self.letzte_berechnung = {'sache': sache, 'aus_zwischenspeicher': False, 'quellen': len(quellen),
                                      'dauer_s': round(time.perf_counter() - begonnen, 4)}
        else:
            self.letzte_berechnung = {'sache': sache, 'aus_zwischenspeicher': True, 'quellen': len(quellen)}
        roh['_gespeichert'] = gespeichert
        roh['_eingabe'] = eingabe
        return roh

    # -- Darstellung (mit Uhrzeit, Zitaten aus dem Original) --

    def akte(self, sache: str, *, jetzt: datetime | None = None, alle: bool = False) -> dict[str, Any] | None:
        """Die Akte einer Sache für die Anzeige, oder None, wenn keine Quelle zu ihr gehört."""
        quellen = self.bezuege.quellen_von(sache) if zerlegen(sache) else []
        roh = self.roh(sache, quellen)
        if roh is None:
            return None
        jetzt = jetzt or datetime.now(timezone.utc)
        lang, kurz = (ALLE, ALLE) if alle else (JE_LISTE, KURZ)
        claims = _MerkeFrei(self.claims) if self.claims is not None else None
        leser = _Leser(self.store, claims)
        art, _ = zerlegen(sache) or ('', '')
        ids = [v['episode_id'] for v in roh['verlauf']]
        aufgaben = list(self._aufgaben(sache, ids))
        erledigt_aufgaben = self._durch_aufgaben(roh, aufgaben)
        offen = [e for e in roh['offen'] if e['ref']['episode_id'] not in erledigt_aufgaben]
        erledigt = [*roh['erledigt'], *({'ref': e['ref'], 'durch': None, 'grund': erledigt_aufgaben[e['ref']['episode_id']]}
                                        for e in roh['offen'] if e['ref']['episode_id'] in erledigt_aufgaben)]
        offene_aufgaben = {a.provenance.source_ref[len('episode:'):]: a for a in aufgaben
                           if getattr(a.status, 'value', a.status) == 'open'
                           and (a.provenance.source_ref or '').startswith('episode:')}
        daten = {
            'sache': sache, 'art': art, 'art_text': ART_TEXT.get(art, art), 'stand': jetzt.isoformat(),
            'name': self.bezuege.beschriftung(sache, quellen=quellen),
            'quellen': {'gesamt': roh['gesamt'], 'beruecksichtigt': roh['beruecksichtigt'],
                        'archiviert': roh['archiviert'], 'begrenzt': roh['gesamt'] > roh['beruecksichtigt'],
                        'abschnitte_abgeschnitten': roh['abschnitte_abgeschnitten']},
            'aus_zwischenspeicher': roh.pop('_gespeichert', False),
            # Fingerabdruck der Eingaben: Ebene 3 (Lage) merkt sich, für welchen Stand sie geschrieben wurde.
            'eingabestand': roh.pop('_eingabe', ''),
        }
        daten['verlauf'] = self._verlauf_zeigen(roh['verlauf'], leser, ALLE if alle else max(lang, 10))
        daten['offen'] = self._offen_zeigen(offen, erledigt, offene_aufgaben, leser, lang)
        daten['fristen'] = self._fristen_zeigen(roh['fristen'], roh['ohne_datum'], leser, jetzt, lang)
        daten['stand_der_dinge'] = self._stand_zeigen(roh['stand'], leser, kurz)
        daten['beteiligte'] = self._beteiligte_zeigen(roh['beteiligte'], lang)
        daten['termine'] = self._termine_zeigen(roh['termine'], jetzt, kurz, leser)
        daten['aufgaben'] = mappe._aufgaben(aufgaben, jetzt, lang)
        daten['einordnung'] = self.store.classification_state(ids)
        # Angenommene Aussagen (aus „In die Akte übernehmen“): als Aussage mit Beleg, nie als Zitat.
        from .akten_aussagen import aussagen
        daten['aussagen'] = aussagen(self, sache, [q['episode_id'] for q in quellen[:MAX_QUELLEN]])
        # Was ein Mensch bestätigt hat (M4): der Kreis einer Person, die private Art einer Organisation. Vorschläge
        # stehen hier nicht; sie zeigt die Karte in der Akte (`kreis_routes.py`, `akten_arten_routes.py`).
        if art == 'person':
            from .kreis import bestaetigter_kreis
            daten['kreis'] = bestaetigter_kreis(self.episodes, sache)
        elif art == 'organisation':
            from .akten_arten import ArtAblage
            fest = ArtAblage(self.episodes).bestaetigt(sache)
            daten['akten_art'] = fest['art'] if fest and fest['art'] != 'keine' else ''
        return daten

    @staticmethod
    def _durch_aufgaben(roh: dict[str, Any], aufgaben: list[Any]) -> dict[str, str]:
        """Quellen, deren Aufgabe erledigt oder fallengelassen ist: Quelle -> Grund."""
        grund: dict[str, str] = {}
        for a in aufgaben:
            quelle = (a.provenance.source_ref or '')
            if not quelle.startswith('episode:'):
                continue
            status = getattr(a.status, 'value', a.status)
            if status in ('done', 'dropped'):
                grund.setdefault(quelle[len('episode:'):], 'aufgabe_erledigt' if status == 'done' else 'aufgabe_verworfen')
        return grund

    @staticmethod
    def _ort_im_termin(body: str) -> str:
        treffer = re.search(r'^Ort:[ \t]*(.+?)[ \t]*$', body, re.M)
        return treffer[1] if treffer else ''

    def _verlauf_zeigen(self, verlauf: list[dict], leser: '_Leser', anzahl: int) -> dict[str, Any]:
        eintraege = []
        for zeile in verlauf:
            if len(eintraege) >= anzahl:
                break
            try:
                episode = self.episodes.get(zeile['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            gelesen = leser.zeile(zeile['ref']) if zeile['ref'] else None
            eintraege.append({
                'episode_id': zeile['episode_id'], 'titel': episode.title[:200], 'datum': zeile['zeit'],
                'grundlagen': zeile['grundlagen'], 'archiviert': zeile['archiviert'],
                'art': gelesen['art'] if gelesen else None, 'text': gelesen['text'] if gelesen else None,
                'gekuerzt': gelesen['gekuerzt'] if gelesen else False, 'quelle_art': episode.kind.value})
        return {'eintraege': eintraege, 'gesamt': len(verlauf)}

    def _offen_zeigen(self, offen: list[dict], erledigt: list[dict], aufgaben: dict[str, Any], leser: '_Leser',
                      anzahl: int) -> dict[str, Any]:
        def zeigen(liste: list[dict], bauen: Callable[[dict, dict], dict]) -> list[dict]:
            ergebnis = []
            for eintrag in liste:
                if len(ergebnis) >= anzahl:
                    break
                zeile = leser.zeile(eintrag['ref'])
                if zeile:
                    ergebnis.append(bauen(eintrag, zeile))
            return ergebnis

        def offen_bauen(eintrag: dict, zeile: dict) -> dict:
            danach = leser.zeile(eintrag['danach']) if eintrag.get('danach') else None
            aufgabe = aufgaben.get(eintrag['ref']['episode_id'])
            return {**zeile, 'vermutlich': True, 'danach_geaendert': danach,
                    'aufgabe': {'id': aufgabe.id, 'title': aufgabe.title} if aufgabe else None}

        def erledigt_bauen(eintrag: dict, zeile: dict) -> dict:
            return {**zeile, 'grund': eintrag['grund'], 'durch': leser.zeile(eintrag['durch']) if eintrag['durch'] else None}

        return {'eintraege': zeigen(offen, offen_bauen), 'gesamt': len(offen), 'vermutlich': True,
                'erledigt': {'eintraege': zeigen(erledigt, erledigt_bauen), 'gesamt': len(erledigt)}}

    def _fristen_zeigen(self, fristen: list[dict], ohne: list[dict], leser: '_Leser', jetzt: datetime,
                        anzahl: int) -> dict[str, Any]:
        heute = jetzt.astimezone(_zone()).date() if jetzt.tzinfo else jetzt.date()

        def bauen(f: dict) -> dict | None:
            zeile = leser.zeile(f['ref'])
            if zeile is None:
                return None
            voll = leser.voll(f['ref'])
            ersetzt = f.get('ersetzt_durch')
            # `satz`: der Satz um die Datumsangabe, wörtlich (das Briefing zitiert ihn statt des ganzen Absatzes).
            return {**zeile, 'datum': f['datum'], 'ausdruck': voll[f['start']:f['ende']].strip() if voll else '',
                    'satz': _umfeld(voll, f['start'], f['ende']).strip() if voll else '',
                    'art_der_angabe': f['art'],
                    'ersetzt_durch': ({'datum': ersetzt['datum'], 'episode_id': ersetzt['ref']['episode_id'],
                                       'ausdruck': (leser.voll(ersetzt['ref']) or '')[ersetzt['start']:ersetzt['ende']].strip()}
                                      if ersetzt else None)}

        gueltig = [f for f in fristen if not f['ersetzt_durch']]
        kommend = [f for f in gueltig if date.fromisoformat(f['datum']) >= heute]
        verstrichen = sorted((f for f in gueltig if date.fromisoformat(f['datum']) < heute),
                             key=lambda f: f['datum'], reverse=True)
        ersetzt = sorted((f for f in fristen if f['ersetzt_durch']), key=lambda f: f['datum'], reverse=True)

        def zeigen(liste: list[dict]) -> list[dict]:
            ergebnis = []
            for f in liste:
                if len(ergebnis) >= anzahl:
                    break
                eintrag = bauen(f)
                if eintrag:
                    ergebnis.append(eintrag)
            return ergebnis

        ohne_zeigen = []
        for eintrag in ohne[:anzahl]:
            voll = leser.voll(eintrag['ref'])
            zeile = leser.zeile(eintrag['ref'])
            if voll and zeile:
                ohne_zeigen.append({'ausdruck': voll[eintrag['start']:eintrag['ende']].strip(),
                                    'episode_id': zeile['episode_id'], 'titel': zeile['titel']})
        return {'kommend': zeigen(kommend), 'verstrichen': zeigen(verstrichen), 'ersetzt': zeigen(ersetzt),
                'gesamt': {'kommend': len(kommend), 'verstrichen': len(verstrichen), 'ersetzt': len(ersetzt)},
                'ohne_datum': {'eintraege': ohne_zeigen, 'gesamt': len(ohne)}}

    def _stand_zeigen(self, stand: list[dict], leser: '_Leser', anzahl: int) -> dict[str, Any]:
        gegenstaende = []
        for gruppe in stand:
            aktuell = leser.zeile(gruppe['aktuell'])
            if aktuell is None:
                continue
            vorher = [z for z in (leser.zeile(r) for r in gruppe['vorher'][:anzahl]) if z]
            gegenstaende.append({'aktuell': aktuell, 'vorher': vorher, 'vorher_gesamt': len(gruppe['vorher'])})
        return {'aktuell': gegenstaende[0]['aktuell'] if gegenstaende else None,
                'vorher': gegenstaende[0]['vorher'] if gegenstaende else [],
                'vorher_gesamt': gegenstaende[0]['vorher_gesamt'] if gegenstaende else 0,
                'weitere': gegenstaende[1:1 + anzahl], 'weitere_gesamt': max(len(gegenstaende) - 1, 0)}

    def _beteiligte_zeigen(self, beteiligte: dict[str, Any], anzahl: int) -> dict[str, Any]:
        eintraege = []
        gezeigt = beteiligte['eintraege'][:max(anzahl, 10)]
        namen = self.bezuege.beschriftungen([e['sache'] for e in gezeigt])
        for eintrag in gezeigt:
            art, _ = zerlegen(eintrag['sache']) or ('', '')
            eintraege.append({'sache': eintrag['sache'], 'art': art, 'anzahl': eintrag['anzahl'],
                              'name': namen[eintrag['sache']]})
        return {'eintraege': eintraege, 'gesamt': beteiligte['gesamt']}

    def _termine_zeigen(self, termine: list[dict], jetzt: datetime, anzahl: int, leser: '_Leser') -> dict[str, Any]:
        kommend, vergangen = [], []
        for t in termine:
            beginn = _zeit(t['start'])
            (kommend if beginn >= jetzt else vergangen).append((beginn, t))
        kommend.sort(key=lambda p: p[0])
        vergangen.sort(key=lambda p: p[0], reverse=True)

        def zeigen(liste: list[tuple[datetime, dict]]) -> list[dict]:
            ergebnis = []
            for beginn, t in liste[:anzahl]:
                try:
                    episode = self.episodes.get(t['episode_id'])
                except Exception:  # noqa: BLE001
                    continue
                laut = leser.zeile(t['abgesagt']) if t.get('abgesagt') else None
                ergebnis.append({'episode_id': episode.id, 'titel': episode.title[:200], 'start': beginn.isoformat(),
                                 'ort': self._ort_im_termin(episode.body), 'vermutlich_abgesagt': laut})
            return ergebnis

        return {'kommend': zeigen(kommend), 'vergangen': zeigen(vergangen),
                'gesamt': {'kommend': len(kommend), 'vergangen': len(vergangen)}}


def _zone():
    from .model import user_timezone
    return user_timezone() or timezone.utc


class _Leser:
    """Liest Zitate aus dem Original und merkt sie sich für die Dauer einer Darstellung."""

    def __init__(self, store: WorkingMemoryStore, claims: Any) -> None:
        self.store, self.claims = store, claims
        self._gelesen: dict[tuple, tuple[Any, str] | None] = {}

    def _lesen(self, ref: dict[str, Any]) -> tuple[Any, str] | None:
        schluessel = (ref['episode_id'], ref['fingerprint'], ref['start'], ref['end'], ref['kind'])
        if schluessel not in self._gelesen:
            reine = {k: ref[k] for k in ('episode_id', 'fingerprint', 'start', 'end', 'kind')}
            self._gelesen[schluessel] = mappe.lesen(self.store, reine, self.claims)
        return self._gelesen[schluessel]

    def voll(self, ref: dict[str, Any]) -> str | None:
        gelesen = self._lesen(ref)
        return gelesen[1] if gelesen else None

    def zeile(self, ref: dict[str, Any]) -> dict[str, Any] | None:
        gelesen = self._lesen(ref)
        if gelesen is None:
            return None
        zeile = mappe.eintrag(ref, *gelesen)
        return zeile


__all__ = ['Akten', 'gleicher_gegenstand', 'stamm_menge']
