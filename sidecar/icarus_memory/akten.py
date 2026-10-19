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
  ein Erledigt- oder Absagewort für diesen Gegenstand trägt, oder wenn die Aufgabe
  dazu erledigt ist.
  Nennt eine spätere Meldung den Gegenstand ohne solches Wort, bleibt der Punkt
  offen und trägt den Hinweis „danach geändert“.
* **Fristen**: ausdrücklich als Frist gebundene Datumsangaben in Bitten, Zusagen und Änderungen (`fristen.py`),
  kommend und verstrichen, jede mit Textstelle. Eine Frist, die eine spätere
  Quelle für denselben Gegenstand verschiebt, steht unter „ersetzt“ und nennt die
  neue. Ausdrückliche Fristen aus Angaben, Status, früheren oder unklar
  eingeordneten Absätzen stehen separat unter „Quellenangaben“; sie belegen
  keine eigene Aufgabe oder bestätigte Zuständigkeit.
* **Stand**: je Gegenstand die jüngste Änderung oder Statusmeldung; ältere nur
  als „vorher“. Aktualität schlägt Ähnlichkeit: Die Reihenfolge entscheidet die
  Zeit der Quelle, nicht die Nähe zu einer Frage.
* **Beteiligte**: Sachen, die in denselben Quellen vorkommen, mit Anzahl.
* **Termine**: vergangene und kommende Termine aus Termin-Episoden; nennt eine
  spätere Meldung derselben Sache den Tag mit einem Absagewort, steht dabei
  „vermutlich abgesagt“ mit der Zeile (der Kalendereintrag bleibt oft stehen).
* **Aufgaben**: offene Aufgaben zur Sache (wie in der Mappe).
* **Braucht dich** (nur in der Ansicht, `akte(..., ansicht=True)`): was eine Entscheidung des Nutzers
  braucht, je ein Satz und ein Klick. Ein vermutlich abgesagter Termin, der noch im Kalender steht; ein
  offener Punkt vor einer Absage im selben Mailverlauf („gilt das noch?“); eine Frist in den nächsten Tagen
  oder eine verstrichene, zu der nichts erledigt ist. Die Antworten hält `akten_entscheidungen.py` fest; sie
  gelten bei der Anzeige (offen oder erledigt), nie in der Berechnung, und lassen sich zurücknehmen.
* **Richtung**: Jeder offene Punkt sagt, ob er von dir stammt (deine Zusage, deine Bitte) oder an dich
  ging (Zusage oder Bitte eines anderen); maßgeblich ist der Absender der Quelle und die eigenen Adressen.
* **Zeitstrahl** (nur in der Ansicht): Quellen, Termine und Fristen als Punkte auf einer Zeitachse.

Gleicher Gegenstand heißt: gemeinsame Wortstämme (mindestens zwei, ohne Monats-,
Wochentags- und Füllwörter), wobei ein gemeinsames langes Wort („Rechnungsanschrift“)
und ein gleiches aufgelöstes Datum doppelt zählen.
Bei Erledigt- oder Absagewörtern wird zusätzlich deren Satz-/Teilsatzgegenstand
geprüft. Eine gemeinsame Event-/Ortsangabe beendet keine andere Aufgabe; die
Absage einer ausdrücklich genannten ganzen Veranstaltung bleibt wirksam. Bei
Fristen genügt ein gemeinsames Fristwort („Einreichfrist“, „Anmeldeschluss“).
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
from .akten_entscheidungen import Entscheidungen, ziel_abschnitt, ziel_termin
from .fristen import bezugstag, fristen_in, fristangaben_in
from .lexical import terms_v1
from .working_memory_store import WorkingMemoryStore
from .working_memory_changes import _ADDITIVE, _FOLLOWING_NEGATION, _NEGATED

AKTEN_VERSION = 11
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
QUELLENFRIST_ARTEN = {'fact': 'Angabe', 'status': 'Statusmeldung', 'historical': 'Frühere Nachricht',
                     'uncertain': 'Unklare Einordnung'}
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


def _abschnitte_lesen(ids: list[str], store: WorkingMemoryStore, claims: Any,
                      *, arten: Iterable[str] = VERLAUF_ARTEN,
                      include_archived: bool = False) -> tuple[list[Abschnitt], bool]:
    """Alle gültigen Abschnitte der Quellen mit Text, Wortstämmen und aufgelösten Daten."""
    gefunden = store.items_all(ids, arten, limit=MAX_ABSCHNITTE, include_archived=include_archived)
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


def _personen_abschnitte(sache: str, quellen: list[dict], abschnitte: list[Abschnitt]) -> list[Abschnitt]:
    """Eine Modell-Erwähnung erschließt nur ihren belegten Absatz, nicht die ganze Mail.

    Absender-/Teilnehmeranker und ausdrückliche Nutzerzuordnungen bleiben
    Korrespondenzkontext. Auch dort sind offene Punkte keine bestätigte
    Zuständigkeit. Quellenverweise und Originale bleiben vollständig erhalten.
    """
    if not sache.startswith('person:'):
        return abschnitte
    nach_id = {q['episode_id']: q for q in quellen}
    ergebnis = []
    for abschnitt in abschnitte:
        quelle = nach_id.get(abschnitt.ref['episode_id'])
        if quelle is None:
            continue
        if {'anker', 'nutzer'}.intersection(quelle['grundlagen']) or any(
                abschnitt.ref['start'] <= start < ende <= abschnitt.ref['end']
                for start, ende in quelle.get('stellen', [])):
            ergebnis.append(abschnitt)
    return ergebnis


# Ein Abschlusswort gilt nur in seinem eigenen Satz/Teilsatz. Präpositionale
# Eventangaben („beim Herbstmarkt“) sind nicht die abgeschlossene Aufgabe.
_ABSCHLUSS_TEILE = re.compile(r'[,;]|\b(?:aber|während|hingegen|sondern)\b|' + _SATZENDE.pattern, re.I)
_ABSCHLUSS_UMFELD = re.compile(r'\b(?:beim|am|im|zum|zur|bei|in|auf)\b', re.I)
# In einer Ich-/Wir-Zusage ist das erste finite Verb die Handlung, nicht
# das zugesagte Objekt. Der folgende konkrete Gegenstand bleibt vollständig.
_ABSCHLUSS_HANDLUNG = re.compile(r'^\s*(?i:ich|wir)\s+[a-zäöüß][\w-]*\b')
_ABSCHLUSS_ALLGEMEIN = stamm_menge(
    'meine meinen mein unsere separate separat gesamte gesamten ganz ganze vollständig '
    'zusage zusagen bitte bitten sage sagen übernehme übernehmen passt leider davon unabhängig')


def _abschluss_teile(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """Gegenstand vor einer Event-/Ortsangabe und deren Umfeld, ohne Abschlusswörter."""
    text = _ABSCHLUSS_HANDLUNG.sub('', text)
    text = _ABSAGE.sub('', _ERLEDIGT.sub('', text))
    teile = _ABSCHLUSS_UMFELD.split(text, maxsplit=1)
    gegenstand = stamm_menge(teile[0]) - _ABSCHLUSS_ALLGEMEIN
    umfeld = stamm_menge(teile[1]) - _ABSCHLUSS_ALLGEMEIN if len(teile) > 1 else frozenset()
    return gegenstand, umfeld


# Dieselbe lokale Polaritätsregel wie der Änderungsbeleg-Guard; zusätzlich die
# deutsche Nachstellung „Abgesagt ist der Standdienst nicht“.
_ABSCHLUSS_NACHNEGATION = re.compile(
    r'^\s+(?:ist|wurde|wird|war|sind)\b[^,;.!?\n]{0,60}\bnicht\b' + _ADDITIVE, re.I)


def _abschluss_signal(text: str, wort: re.Pattern) -> bool:
    for signal in wort.finditer(text):
        intrinsisch = wort is _ABSAGE and signal.group().casefold().startswith('findet nicht')
        if not intrinsisch and _NEGATED.search(text[:signal.start()]):
            continue
        danach = text[signal.end():]
        if _FOLLOWING_NEGATION.match(danach) or _ABSCHLUSS_NACHNEGATION.match(danach):
            continue
        return True
    return False


def _abschluss_betrifft(x: Abschnitt, y: Abschnitt, wort: re.Pattern) -> bool:
    """Nur die genannte Aufgabe oder ihre ausdrücklich abgesagte ganze Veranstaltung."""
    gegenstand, umfeld = _abschluss_teile(x.text)
    for teil in _ABSCHLUSS_TEILE.split(y.text):
        if not _abschluss_signal(teil, wort):
            continue
        ziel, ziel_umfeld = _abschluss_teile(teil)
        # Dieselbe Aufgabe bei zwei ausdrücklich verschiedenen Veranstaltungen
        # bleibt getrennt. Ein fehlendes Umfeld ist kein Widerspruch.
        if umfeld and ziel_umfeld and not (umfeld <= ziel_umfeld or ziel_umfeld <= umfeld):
            continue
        # Eine gemeinsame Kategorie („Aufgabe“, „Planung“) reicht nicht:
        # alle konkreten Teile des früheren Gegenstands müssen wieder vorkommen.
        if gegenstand and gegenstand <= ziel:
            return True
        # Eine ganze Veranstaltung steht selbst als Abschlussgegenstand, keine
        # andere Aufgabe im selben Veranstaltungskontext. Nur Absagen wirken so.
        if wort is _ABSAGE and ziel and ziel <= umfeld:
            return True
        # Workshop/Tagesworkshop: der ganze Abschlussgegenstand muss in der
        # früheren Quelle genannt sein, gegebenenfalls als langes Kompositum.
        benannt = {_stamm(w) for w in terms_v1(teil) if len(w) >= 8
                   and any(v.endswith(w) for v in terms_v1(x.text))}
        if wort is _ABSAGE and ziel and ziel <= benannt:
            return True
        # Reine Datumszusage („der 28. Oktober passt“) ohne eigenen Gegenstand.
        if not gegenstand and x.daten & y.daten:
            return True
    return False


def _offen(abschnitte: list[Abschnitt]) -> tuple[list[dict], list[dict]]:
    """(offen, erledigt): Bitten und Zusagen, geprüft gegen spätere Änderungen und Standmeldungen."""
    spaeter = [a for a in abschnitte if a.art in STAND_ARTEN]
    offen, erledigt = [], []
    for x in sorted((a for a in abschnitte if a.art in OFFEN_ARTEN), key=lambda a: a.zeit, reverse=True):
        treffer = sorted((y for y in spaeter if y.zeit > x.zeit and (gleicher_gegenstand(x, y) or (
            x.stamm & y.stamm and (_ABSAGE.search(y.text) or _ERLEDIGT.search(y.text))))), key=lambda y: y.zeit)
        absage = next((y for y in treffer if _abschluss_betrifft(x, y, _ABSAGE)), None)
        fertig = next((y for y in treffer if _abschluss_betrifft(x, y, _ERLEDIGT)), None)
        if absage or fertig:
            durch = absage or fertig
            erledigt.append({'ref': _ref(x), 'durch': _ref(durch), 'grund': 'absage' if absage else 'erledigt'})
        else:
            offen.append({'ref': _ref(x), 'danach': _ref(treffer[-1]) if treffer else None})
    return offen, erledigt


_FRIST_UMFELD = re.compile(r'\b(?:für|beim|am|im|zum|zur|bei|in|auf)\b', re.I)
_FRISTVERSCHIEBUNG = re.compile(
    r'(?P<gegenstand>[^,;.!?\n]+?)\s+verschieb(?:t|en)\s+sich\s+'
    r'(?:(?:deshalb|daher|nun|jetzt)\s+)*(?:auf|zum)\s+(?:den\s+)?$', re.I)


def _fristaufgabe(a: Abschnitt, start: int) -> frozenset[str]:
    """The task before a cutoff, excluding preceding dates and event context."""
    breit = fristen_in(a.text, a.bezug)
    stellen = [(f.start, f.ende) for f in breit.fristen] + breit.ohne_datum_stellen
    links = max([0, *(ende for _, ende in stellen if ende <= start),
                 *(m.end() for m in _SATZENDE.finditer(a.text, 0, start))])
    kern = _FRIST_UMFELD.split(a.text[links:start], maxsplit=1)[0]
    return _gegenstand(kern)


def _fristen(abschnitte: list[Abschnitt]) -> tuple[list[dict], list[dict]]:
    """(fristen, ohne_datum): aufgelöste Datumsangaben mit Textstelle; überholte tragen `ersetzt_durch`."""
    alle: list[dict] = []
    ohne: list[dict] = []
    for a in (x for x in abschnitte if x.art in FRIST_ARTEN):
        suche = fristangaben_in(a.text, a.bezug)
        for f in suche.fristen:
            umfeld = _umfeld(a.text, f.start, f.ende)
            alle.append({'ref': _ref(a), 'start': f.start, 'ende': f.ende, 'datum': f.datum.isoformat(),
                         'art': f.art, 'ersetzt_durch': None, '_zeit': a.zeit, '_stamm': _gegenstand(umfeld),
                         '_aufgabe': _fristaufgabe(a, f.start)})
        for beginn, ende in suche.ohne_datum_stellen:
            ohne.append({'ref': _ref(a), 'start': beginn, 'ende': ende})
    # "Der Belegungsplan verschiebt sich auf ..." can carry forward a known
    # task deadline without repeating "Frist". Require an earlier bound cutoff
    # for that task; a shared event in its context cannot supply this relation.
    for a in sorted((x for x in abschnitte if x.art == 'change'), key=lambda x: x.zeit):
        for f in fristen_in(a.text, a.bezug).fristen:
            if any(g['ref'] == _ref(a) and g['start'] == f.start for g in alle):
                continue
            verschiebung = _FRISTVERSCHIEBUNG.search(a.text[:f.start])
            if not verschiebung:
                continue
            ziel = _gegenstand(verschiebung['gegenstand'])
            if len(ziel) < 2 or not any(g['_zeit'] < a.zeit and ziel <= g['_aufgabe'] for g in alle):
                continue
            alle.append({'ref': _ref(a), 'start': f.start, 'ende': f.ende, 'datum': f.datum.isoformat(),
                         'art': f.art, 'ersetzt_durch': None, '_zeit': a.zeit,
                         '_stamm': _gegenstand(_umfeld(a.text, f.start, f.ende)), '_aufgabe': ziel})
    # Angaben mit Fristwort („Einreichfrist“, „Anmeldeschluss“) in Absätzen der Art Angabe oder Stand: Eine Ausschreibung
    # nennt die Frist als Angabe, nicht als Bitte. Sie erscheint nur unter „ersetzt“, wenn eine spätere Zusage, Bitte oder
    # Änderung denselben Gegenstand (dieselben Wortstämme, wie bei jeder Frist) mit einem anderen Datum nennt; sonst wäre jedes Datum in jeder Angabe eine „Frist“.
    fakten: list[dict] = []
    for a in (x for x in abschnitte if x.art in FAKT_ARTEN):
        for f in fristangaben_in(a.text, a.bezug).fristen:
            umfeld = _umfeld(a.text, f.start, f.ende)
            wort = frozenset(m.group(0).casefold() for m in _FRISTWORT.finditer(umfeld))
            if wort:
                fakten.append({'ref': _ref(a), 'start': f.start, 'ende': f.ende, 'datum': f.datum.isoformat(),
                               'art': f.art, 'ersetzt_durch': None, '_zeit': a.zeit, '_stamm': _gegenstand(umfeld),
                               '_aufgabe': _fristaufgabe(a, f.start)})

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
        for privat in ('_zeit', '_stamm', '_aufgabe'):
            f.pop(privat)
    alle.sort(key=lambda f: (f['datum'], f['ref']['episode_id'], f['start']))
    return alle, ohne


def _quellenfristen(abschnitte: list[Abschnitt]) -> list[dict]:
    """Explicit source cutoffs, without inferring validity, ownership or tasks.

    This channel does not participate in action deadlines, supersession, open
    items, current state or briefing selection. The full original quote retains
    qualifications such as uncertainty, a reservation or a cancellation.
    """
    ergebnis = []
    for a in sorted(abschnitte, key=lambda a: a.zeit, reverse=True):
        if a.art not in FAKT_ARTEN:
            continue
        for f in fristangaben_in(a.text, a.bezug).fristen:
            if not _FRISTWORT.search(_umfeld(a.text, f.start, f.ende)):
                continue
            ergebnis.append({'ref': _ref(a), 'start': f.start, 'ende': f.ende,
                             'datum': f.datum.isoformat(), 'art': f.art})
    return ergebnis


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


def _faeden(episodes: Any, ids: list[str]) -> dict[str, str]:
    """Mailverläufe unter den Quellen der Akte: Quelle -> Kennung ihres Verlaufs.

    Zwei Mails gehören zusammen, wenn die eine die Message-ID der anderen als Antwortbezug trägt oder beide
    auf dieselbe Mail antworten (genaue Kopfzeilen, `mail_header_index.py`). Betreff und Namen zählen nicht.
    Eine Quelle ohne solchen Bezug ist ihr eigener Verlauf.
    """
    eltern = {i: i for i in ids}

    def wurzel(x: str) -> str:
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    je_kennung: dict[str, list[str]] = {}
    with episodes._lock:
        for anfang in range(0, len(ids), 400):
            teil = ids[anfang:anfang + 400]
            for wert, episode_id in episodes._conn.execute(
                    'SELECT value, episode_id FROM episode_mail_headers WHERE episode_id IN ('
                    + ','.join('?' for _ in teil) + ')', teil):
                kennung = str(wert).split(':', 2)[-1]
                je_kennung.setdefault(kennung, []).append(episode_id)
    for gruppe in je_kennung.values():
        for andere in gruppe[1:]:
            a, b = wurzel(gruppe[0]), wurzel(andere)
            if a != b:
                eltern[b] = a
    return {i: wurzel(i) for i in ids}


def _nach_absage(offen: list[dict], abschnitte: list[Abschnitt], termine: list[dict],
                 faeden: dict[str, str]) -> list[dict]:
    """Offene Punkte vor der Absage eines Termins der Akte, die die Absage nicht ausdrücklich beendet.

    Eine Absage beendet nur, was sie benennt (`_abschluss_betrifft`). Frühere Zusagen und Bitten im selben
    Mailverlauf („Den Ablauf schicken wir Ihnen im August.“) oder mit dem Tag des abgesagten Termins sind
    vermutlich hinfällig, aber das ist zu unsicher, um es selbst zu entscheiden: Die Akte fragt („gilt das
    noch?“). Je Punkt die früheste passende Absage.
    """
    nach_stelle = {(a.ref['episode_id'], a.ref['start']): a for a in abschnitte}
    absagen = []
    for t in termine:
        if t.get('abgesagt'):
            absagen.append((t['abgesagt'], t['episode_id'], bezugstag(_zeit(t['start']))))
    ergebnis = []
    for eintrag in offen:
        ref = eintrag['ref']
        abschnitt = nach_stelle.get((ref['episode_id'], ref['start']))
        faden = faeden.get(ref['episode_id'])
        passend = [(absage, termin) for absage, termin, tag in absagen
                   if absage['episode_id'] != ref['episode_id'] and _zeit(absage['zeit']) > _zeit(ref['zeit'])
                   and ((faden is not None and faeden.get(absage['episode_id']) == faden)
                        or (abschnitt is not None and tag in abschnitt.daten))]
        if passend:
            absage, termin = min(passend, key=lambda p: p[0]['zeit'])
            ergebnis.append({'ref': ref, 'absage': absage, 'termin': termin})
    return ergebnis


def _entschieden(offen: list[dict], erledigt: list[dict],
                 gesagt: dict[str, dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Die Entscheidungen des Nutzers über die Vermutung legen: (offen, erledigt).

    „Erledigt“ und „Gilt nicht mehr“ legen einen offenen Punkt ab. „Gilt weiter“ hält ihn offen und holt ihn
    zurück, wenn die Akte ihn nur vermutlich für erledigt hielt (Erledigt- oder Absagewort). Eine erledigte
    oder fallengelassene Aufgabe bleibt, was sie ist: Das hat der Nutzer schon dort entschieden.
    """
    neu_offen, neu_erledigt = [], []
    for eintrag in offen:
        gesagt_ = gesagt.get(ziel_abschnitt(eintrag['ref']))
        if gesagt_ and gesagt_['entscheidung'] in ('erledigt', 'gilt_nicht'):
            neu_erledigt.append({'ref': eintrag['ref'], 'durch': None, 'grund': 'nutzer_' + gesagt_['entscheidung'],
                                 'entschieden_am': gesagt_['entschieden_am']})
        else:
            neu_offen.append({**eintrag, 'bestaetigt': bool(gesagt_)})
    for eintrag in erledigt:
        gesagt_ = gesagt.get(ziel_abschnitt(eintrag['ref']))
        if gesagt_ and gesagt_['entscheidung'] == 'offen' and eintrag['grund'] in ('absage', 'erledigt'):
            neu_offen.append({'ref': eintrag['ref'], 'danach': eintrag.get('durch'), 'bestaetigt': True})
        else:
            neu_erledigt.append(eintrag)
    neu_offen.sort(key=lambda e: _zeit(e['ref']['zeit']), reverse=True)
    return neu_offen, neu_erledigt


def _mit_entscheidungen(eingabe: str, gesagt: dict[str, dict[str, Any]]) -> str:
    """Der Eingabestand für die Lage: ohne Entscheidungen unverändert, sonst mit ihnen."""
    if not eingabe or not gesagt:
        return eingabe
    inhalt = json.dumps([eingabe, sorted((z, g['entscheidung']) for z, g in gesagt.items())], ensure_ascii=False)
    return hashlib.sha256(inhalt.encode()).hexdigest()


def _tag(zeit: datetime) -> str:
    """»28. Oktober« in der Zeitzone des Nutzers."""
    from .datumstext import tag_und_monat
    return tag_und_monat(zeit.astimezone(_zone()) if zeit.tzinfo else zeit)


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
                  [(q['episode_id'], q['fp'], q['grundlagen'], q.get('stellen', []), q['archiviert'], einordnung.get(q['episode_id'], ''))
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
        abschnitte = _personen_abschnitte(sache, genutzt, abschnitte)
        # Read uncertain/history only for source-cutoff evidence. They must not
        # be introduced into the existing timeline, open items or current state.
        quellenabschnitte, quellen_abgeschnitten = _abschnitte_lesen(
            ids, self.store, claims, arten=FAKT_ARTEN, include_archived=True)
        quellenabschnitte = _personen_abschnitte(sache, genutzt, quellenabschnitte)
        offen, erledigt = _offen(abschnitte)
        fristen, ohne_datum = _fristen(abschnitte)
        gemeinsam = self.bezuege.gemeinsame(sache, ids)
        rang = sorted(gemeinsam.items(), key=lambda p: (-p[1], p[0]))
        termine = _termine(genutzt, abschnitte)
        return {
            'version': AKTEN_VERSION,
            'gesamt': len(quellen), 'beruecksichtigt': len(genutzt),
            'abschnitte_abgeschnitten': abgeschnitten or quellen_abgeschnitten,
            'archiviert': sum(1 for q in quellen if q['archiviert']),
            'verlauf': _verlauf(genutzt, abschnitte),
            'offen': offen, 'erledigt': erledigt, 'fristen': fristen, 'ohne_datum': ohne_datum,
            'quellenfristen': _quellenfristen(quellenabschnitte),
            'stand': _stand(abschnitte),
            'beteiligte': {'gesamt': len(rang), 'eintraege': [{'sache': s, 'anzahl': n} for s, n in rang[:40]]},
            'termine': termine,
            'nach_absage': _nach_absage(offen, abschnitte, termine, _faeden(self.episodes, ids)),
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

    def ziele(self, sache: str) -> set[str]:
        """Alles, wozu der Nutzer in dieser Akte entscheiden kann: offene und erledigte Punkte, Termine."""
        roh = self.roh(sache)
        if roh is None:
            return set()
        ziele = {ziel_abschnitt(e['ref']) for e in (*roh['offen'], *roh['erledigt'])}
        for t in roh['termine']:
            try:
                episode = self.episodes.get(t['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            ziele.add(ziel_termin(episode.id, episode.digest))
        return ziele

    def akte(self, sache: str, *, jetzt: datetime | None = None, alle: bool = False,
             ansicht: bool = False) -> dict[str, Any] | None:
        """Die Akte einer Sache für die Anzeige, oder None, wenn keine Quelle zu ihr gehört.

        `ansicht`: zusätzlich „Braucht dich“ und den Zeitstrahl (nur die eigene Seite der Akte braucht sie;
        Briefing und Export lesen viele Akten und sparen sich das).
        """
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
        # Eine bloße Modell-Erwähnung begründet keine Aufgaben-Zuständigkeit.
        # Explizites wartet_auf wird vom Callback weiterhin unabhängig von ids gelesen.
        aufgaben_ids = ([q['episode_id'] for q in quellen[:MAX_QUELLEN]
                         if {'anker', 'nutzer'}.intersection(q['grundlagen'])]
                        if art == 'person' else ids)
        aufgaben = list(self._aufgaben(sache, aufgaben_ids))
        erledigt_aufgaben = self._durch_aufgaben(roh, aufgaben)
        offen = [e for e in roh['offen'] if e['ref']['episode_id'] not in erledigt_aufgaben]
        erledigt = [*roh['erledigt'], *({'ref': e['ref'], 'durch': None, 'grund': erledigt_aufgaben[e['ref']['episode_id']]}
                                        for e in roh['offen'] if e['ref']['episode_id'] in erledigt_aufgaben)]
        # Was der Nutzer selbst entschieden hat, gilt vor der Vermutung (nur bei der Anzeige, `akten_entscheidungen.py`).
        gesagt = Entscheidungen(self.episodes).zu(ziel_abschnitt(e['ref']) for e in (*offen, *erledigt))
        offen, erledigt = _entschieden(offen, erledigt, gesagt)
        eigene = self.bezuege.eigene_adressen()
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
            # Eine Entscheidung des Nutzers ändert, was offen ist; dann gilt auch die Lage als veraltet.
            'eingabestand': _mit_entscheidungen(roh.pop('_eingabe', ''), gesagt),
        }
        abgelegt = {ziel_abschnitt(e['ref']) for e in erledigt if e['grund'].startswith('nutzer_')}
        daten['verlauf'] = self._verlauf_zeigen(roh['verlauf'], leser, ALLE if alle else max(lang, 10))
        daten['offen'] = self._offen_zeigen(offen, erledigt, offene_aufgaben, leser, lang, eigene)
        daten['fristen'] = self._fristen_zeigen(roh['fristen'], roh['ohne_datum'], leser, jetzt, lang,
                                                quellenangaben=roh.get('quellenfristen', []), abgelegt=abgelegt)
        daten['stand_der_dinge'] = self._stand_zeigen(roh['stand'], leser, kurz)
        daten['beteiligte'] = self._beteiligte_zeigen(roh['beteiligte'], lang)
        termin_gesagt = self._termin_entscheidungen(roh['termine'])
        daten['termine'] = self._termine_zeigen(roh['termine'], jetzt, kurz, leser, termin_gesagt)
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
        if ansicht:
            daten['braucht_dich'] = self._braucht_dich(roh, offen, leser, jetzt, eigene, termin_gesagt)
            daten['zeitstrahl'] = self._zeitstrahl(roh, offen, jetzt, termin_gesagt)
        return daten

    # -- Entscheidungen, Braucht dich, Zeitstrahl --

    def _termin_entscheidungen(self, termine: list[dict]) -> dict[str, tuple[str, dict[str, Any] | None]]:
        """Je Termin-Quelle: (Ziel, Entscheidung oder None). Nur Termine, die eine Absage tragen, fragen."""
        ziele: dict[str, str] = {}
        for t in termine:
            try:
                episode = self.episodes.get(t['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            ziele[t['episode_id']] = ziel_termin(episode.id, episode.digest)
        gesagt = Entscheidungen(self.episodes).zu(ziele.values()) if ziele else {}
        return {episode_id: (ziel, gesagt.get(ziel)) for episode_id, ziel in ziele.items()}

    def _braucht_dich(self, roh: dict[str, Any], offen: list[dict], leser: '_Leser', jetzt: datetime,
                      eigene: list[str], termin_gesagt: dict[str, tuple[str, dict | None]]) -> dict[str, Any]:
        """Was eine Entscheidung des Nutzers braucht: je ein Satz, das Zitat, die Wahl. Dringendes zuerst."""
        from .fristlage import Frist, beschreibung, quelle_art, richtung
        from .kontakte import anzeigename
        from .episodes import mail_address
        punkte: dict[str, dict[str, Any]] = {}

        def merken(ziel: str, rang: tuple, punkt: dict[str, Any]) -> None:
            if ziel not in punkte or rang < punkte[ziel]['_rang']:
                punkte[ziel] = {**punkt, 'ziel': ziel, '_rang': rang}

        heute = jetzt.astimezone(_zone()).date() if jetzt.tzinfo else jetzt.date()
        # 1. Abgesagt, aber noch im Kalender: kommende Termine mit Absage und ohne Entscheidung.
        for t in roh['termine']:
            beginn = _zeit(t['start'])
            ziel, gesagt = termin_gesagt.get(t['episode_id'], ('', None))
            if not t.get('abgesagt') or beginn < jetzt or not ziel or gesagt:
                continue
            laut = leser.zeile(t['abgesagt'])
            if laut is None:
                continue
            episode = self.episodes.get(t['episode_id'])
            merken(ziel, (0, beginn.timestamp()), {
                'art': 'abgesagter_termin',
                'satz': (f'„{episode.title[:120]}“ am {_tag(beginn)} ist laut „{laut["titel"]}“ vom '
                         f'{_tag(_zeit(laut["occurred_at"] or laut["recorded_at"]))} abgesagt, steht aber noch in '
                         'deinem Kalender.'),
                'zeile': None, 'laut': laut, 'episode_id': episode.id,
                'wahl': [{'entscheidung': 'erledigt', 'text': 'Erledigt'},
                         {'entscheidung': 'offen', 'text': 'Findet doch statt'}]})
        offen_ziele = {ziel_abschnitt(e['ref']): e for e in offen}
        # 2. Vor einer Absage im selben Verlauf: gilt das noch? Nur, solange niemand „gilt weiter“ gesagt hat.
        for hinweis in roh.get('nach_absage', []):
            ziel = ziel_abschnitt(hinweis['ref'])
            eintrag = offen_ziele.get(ziel)
            if eintrag is None or eintrag.get('bestaetigt'):
                continue
            zeile, laut = leser.zeile(hinweis['ref']), leser.zeile(hinweis['absage'])
            if zeile is None or laut is None:
                continue
            try:
                termin = self.episodes.get(hinweis['termin'])
            except Exception:  # noqa: BLE001
                continue
            wer = richtung(zeile['participants'], eigene)
            was = {'Zusage': 'Zusage', 'Bitte': 'Bitte'}.get(zeile['art'], 'Angabe')
            merken(ziel, (2, -_zeit(hinweis['absage']['zeit']).timestamp()), {
                'art': 'gilt_noch',
                'satz': (f'„{termin.title[:120]}“ ist seit {_tag(_zeit(hinweis["absage"]["zeit"]))} abgesagt. '
                         f'Gilt {"deine" if wer == "von_mir" else "diese"} frühere {was} noch?'),
                'zeile': zeile, 'laut': laut, 'episode_id': zeile['episode_id'],
                'wahl': [{'entscheidung': 'gilt_nicht', 'text': 'Gilt nicht mehr'},
                         {'entscheidung': 'offen', 'text': 'Gilt weiter'}]})
        # 3. Fristen offener Punkte: in den nächsten Tagen oder verstrichen (wie im Briefing, `fristlage.py`).
        for f in roh['fristen']:
            if f['ersetzt_durch']:
                continue
            ziel = ziel_abschnitt(f['ref'])
            if ziel not in offen_ziele:
                continue
            datum = date.fromisoformat(f['datum'])
            tage = (datum - heute).days
            if not -45 <= tage <= 7:
                continue
            zeile, voll = leser.zeile(f['ref']), leser.voll(f['ref'])
            if zeile is None or voll is None:
                continue
            wer = richtung(zeile['participants'], eigene)
            absender = (zeile['participants'] or [''])[0]
            status = 'kommend' if tage >= 0 else 'verstrichen'
            frist = Frist(datum=datum, text=zeile['text'], ausdruck=voll[f['start']:f['ende']].strip(),
                          episode_id=zeile['episode_id'], titel=zeile['titel'], quelle_datum=zeile['occurred_at'],
                          quelle_art=quelle_art(None), art=zeile['art'], richtung=wer, status=status, tage=tage,
                          vermutlich=status == 'verstrichen',
                          andere=(anzeigename(absender) or mail_address(absender)) if wer == 'an_mich' else '')
            wahl = [{'entscheidung': 'erledigt', 'text': 'Erledigt'}]
            if status == 'verstrichen':
                wahl.append({'entscheidung': 'gilt_nicht', 'text': 'Gilt nicht mehr'})
            rang = (1, tage) if 0 <= tage <= 1 else (3, -tage) if tage < 0 else (4, tage)
            merken(ziel, rang, {'art': 'frist' if status == 'kommend' else 'frist_verstrichen',
                                'satz': beschreibung(frist), 'zeile': zeile, 'laut': None, 'datum': f['datum'],
                                'episode_id': zeile['episode_id'], 'wahl': wahl})
        geordnet = sorted(punkte.values(), key=lambda p: p['_rang'])
        for punkt in geordnet:
            punkt.pop('_rang')
        return {'eintraege': geordnet[:6], 'gesamt': len(geordnet)}

    def _zeitstrahl(self, roh: dict[str, Any], offen: list[dict], jetzt: datetime,
                    termin_gesagt: dict[str, tuple[str, dict | None]]) -> dict[str, Any]:
        """Quellen, Termine und Fristen als Punkte auf einer Zeitachse (jüngste 150 Quellen)."""
        punkte: list[dict[str, Any]] = []
        termine = {t['episode_id']: t for t in roh['termine']}
        for v in roh['verlauf'][:150]:
            if v['episode_id'] in termine:
                continue
            try:
                episode = self.episodes.get(v['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            punkte.append({'art': 'quelle', 'datum': v['zeit'], 'episode_id': episode.id,
                           'titel': episode.title[:120], 'quelle_art': episode.kind.value,
                           'abschnitt': mappe.ARTEN.get(v['ref']['kind']) if v['ref'] else None})
        for t in roh['termine']:
            try:
                episode = self.episodes.get(t['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            _, gesagt = termin_gesagt.get(t['episode_id'], ('', None))
            abgesagt = bool(t.get('abgesagt')) and not (gesagt and gesagt['entscheidung'] == 'offen')
            punkte.append({'art': 'termin', 'datum': t['start'], 'episode_id': episode.id,
                           'titel': episode.title[:120], 'quelle_art': 'event', 'abgesagt': abgesagt})
        offen_ziele = {ziel_abschnitt(e['ref']) for e in offen}
        for f in roh['fristen']:
            if f['ersetzt_durch']:
                continue
            try:
                episode = self.episodes.get(f['ref']['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            punkte.append({'art': 'frist', 'datum': f['datum'], 'episode_id': episode.id,
                           'titel': episode.title[:120], 'quelle_art': episode.kind.value,
                           'offen': ziel_abschnitt(f['ref']) in offen_ziele})
        return {'punkte': punkte, 'quellen': len(roh['verlauf']), 'gezeigt': min(len(roh['verlauf']), 150),
                'heute': jetzt.isoformat()}

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
                      anzahl: int, eigene: list[str]) -> dict[str, Any]:
        from .fristlage import richtung
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
            # `richtung`: von_mir (deine Zusage oder Bitte), an_mich (von jemand anderem), unklar (Notiz, Termin).
            return {**zeile, 'vermutlich': True, 'danach_geaendert': danach,
                    'aufgabe': {'id': aufgabe.id, 'title': aufgabe.title} if aufgabe else None,
                    'ziel': ziel_abschnitt(eintrag['ref']), 'richtung': richtung(zeile['participants'], eigene),
                    'bestaetigt': bool(eintrag.get('bestaetigt'))}

        def erledigt_bauen(eintrag: dict, zeile: dict) -> dict:
            return {**zeile, 'grund': eintrag['grund'], 'durch': leser.zeile(eintrag['durch']) if eintrag['durch'] else None,
                    'ziel': ziel_abschnitt(eintrag['ref']), 'richtung': richtung(zeile['participants'], eigene)}

        return {'eintraege': zeigen(offen, offen_bauen), 'gesamt': len(offen), 'vermutlich': True,
                'erledigt': {'eintraege': zeigen(erledigt, erledigt_bauen), 'gesamt': len(erledigt)}}

    def _fristen_zeigen(self, fristen: list[dict], ohne: list[dict], leser: '_Leser', jetzt: datetime,
                        anzahl: int, *, quellenangaben: list[dict] | None = None,
                        abgelegt: set[str] = frozenset()) -> dict[str, Any]:
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
                    'art_der_angabe': f['art'], 'ziel': ziel_abschnitt(f['ref']),
                    'ersetzt_durch': ({'datum': ersetzt['datum'], 'episode_id': ersetzt['ref']['episode_id'],
                                       'ausdruck': (leser.voll(ersetzt['ref']) or '')[ersetzt['start']:ersetzt['ende']].strip()}
                                      if ersetzt else None)}

        # Was der Nutzer als erledigt abgelegt hat, mahnt keine Frist mehr an (weder hier noch im Briefing).
        gueltig = [f for f in fristen if not f['ersetzt_durch'] and ziel_abschnitt(f['ref']) not in abgelegt]
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
        quellen_zeigen = []
        for f in (quellenangaben or [])[:anzahl]:
            zeile = bauen(f)
            voll = leser.voll(f['ref'])
            if zeile and voll is not None:
                einordnung = f['ref']['kind']
                quellen_zeigen.append({**zeile, 'text': voll, 'gekuerzt': False,
                                       'art': QUELLENFRIST_ARTEN[einordnung], 'einordnung': einordnung,
                                       'zeitbezug': 'vergangen' if date.fromisoformat(f['datum']) < heute else 'kommend',
                                       'zustaendigkeit': 'ungeklaert', 'nur_quellenangabe': True})
        return {'kommend': zeigen(kommend), 'verstrichen': zeigen(verstrichen), 'ersetzt': zeigen(ersetzt),
                'gesamt': {'kommend': len(kommend), 'verstrichen': len(verstrichen), 'ersetzt': len(ersetzt)},
                # Fristen von Punkten, die der Nutzer als erledigt abgelegt hat (sie mahnen nicht mehr).
                'abgelegt': sum(1 for f in fristen if not f['ersetzt_durch']) - len(gueltig),
                'ohne_datum': {'eintraege': ohne_zeigen, 'gesamt': len(ohne)},
                'quellenangaben': {'eintraege': quellen_zeigen, 'gesamt': len(quellenangaben or [])}}

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

    def _termine_zeigen(self, termine: list[dict], jetzt: datetime, anzahl: int, leser: '_Leser',
                        gesagt: dict[str, tuple[str, dict | None]] | None = None) -> dict[str, Any]:
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
                ziel, entscheidung = (gesagt or {}).get(t['episode_id'], (ziel_termin(episode.id, episode.digest), None))
                entscheidung = entscheidung['entscheidung'] if entscheidung else None
                # „Findet doch statt“ hebt die Vermutung auf; „Erledigt“ bestätigt die Absage.
                laut = leser.zeile(t['abgesagt']) if t.get('abgesagt') and entscheidung != 'offen' else None
                ergebnis.append({'episode_id': episode.id, 'titel': episode.title[:200], 'start': beginn.isoformat(),
                                 'ort': self._ort_im_termin(episode.body), 'vermutlich_abgesagt': laut,
                                 'ziel': ziel, 'entscheidung': entscheidung})
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
