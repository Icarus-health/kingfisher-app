"""Akten als Kontext einer Frage (Etappe E2): Suchen von oben, und was überholt ist, sagt der Kontext selbst.

Die Suche von unten (Wortsuche, Volltextindex, Umschreibungen) findet Quellen. Sie
kennt aber nicht, was inzwischen gilt: Die Ausschreibung mit der Frist 15.10. steht
neben der Verlängerung auf den 12.11. gleichrangig im Kontext, und ein Modell muss
raten, welche zählt. Die Akten (`akten.py`, Ebene 2) wissen es schon: Sie führen
eine Frist, die eine spätere Quelle verschiebt, als „ersetzt“, eine ältere
Statusmeldung als „vorher“, eine Zusage nach einer Absage als „erledigt“ und einen
Termin, den eine Mail absagt, als „vermutlich abgesagt“.

Dieses Modul verbindet beides, ohne Modell:

* **Von oben.** Nennt die Frage Sachen (Person, Organisation, Projekt, Ort), die sich
  eindeutig auflösen lassen, liefert ihre Akte die *bevorzugten* Quellen: den aktuellen
  Stand, kommende Fristen und Termine, vermutlich Offenes (`Kontext.zeilen`). Sie
  gehen als dritte Liste in die Rangfusion der Kandidaten (`source_candidates`).
  Mehrdeutige Namen („Alex Winter“ zweimal) lösen nichts auf; dann gilt allein die
  Suche von unten.
* **Überholtes ausweisen.** Für die gefundenen Quellen fragt `aufbauen` die Akten
  aller Sachen, zu denen sie gehören: Steht eine Angabe der Quelle dort als überholt,
  bekommt die Quelle im Kontext des Modells eine Kennzeichnung (`Ueberholt`) mit der
  überholten Angabe, der neuen Angabe und dem Verweis auf die neue Quelle. Nichts wird
  still entfernt: Das Modell soll den Wandel erklären können, nur nie einen alten Wert
  als Stand nennen. Gekennzeichnete Quellen stehen nachrangig.

Reproduzierbar: Alles hängt allein von Bestand, Akten und dem Tag ab (nicht von der
Uhrzeit), der Fingerabdruck (`Kontext.signatur`) wird mit der Antwort gespeichert, und
die Frischeprüfung (`working_memory_answers._fresh`) rechnet ihn neu. Ändert sich eine
Akte so, dass sich Kennzeichnung oder bevorzugte Quellen ändern, gilt die Antwort als
veraltet; eine fremde neue Mail ändert die Akten dieser Sache nicht.

* **Kreis kennzeichnen (M4).** Für jede Person mit bestätigtem Kreis (`kreis.py`) unter den Quellen trägt der
  Kontext ihren Kreis (`Kontext.kreise`, je Quelle `Kontext.personen`, je Akten-Zeile `AktenZeile.kreis`), damit
  Satzauswahl und Antwortmodell wissen, wie zurückhaltend über sie zu sprechen ist (`hinweis_kreis`). Ein bloßer
  Vorschlag steht nicht darin: Er ist kein Fakt.

Die Akten erreicht dieses Modul über `episodes.akten_zugang` (vom Server gesetzt, siehe
`akten_routes.py`). Ohne Zugang, etwa in Tests des Speichers allein, verhält sich alles
wie bisher.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable, Sequence

from . import mappe
from .akten import _umfeld
from .bezuege import norm, zerlegen
from .working_memory_store import WorkingMemoryStore

KONTEXT_VERSION = 1
#: Höchstens so viele Sachen löst eine Frage auf (von oben).
MAX_SACHEN = 4
#: Höchstens so viele Akten liest ein Aufruf insgesamt (aufgelöste Sachen zuerst, dann die häufigsten der Kandidaten).
MAX_AKTEN = 24
#: Höchstens so viele bevorzugte Quellen liefert die Akte einer Sache und alle zusammen.
OBEN_JE_SACHE = 6
MAX_OBEN = 10
#: Länge der gezeigten überholten und neuen Angaben (Zeichen).
KURZ = 200
#: Arten von Sachen, deren Akten für Überholtes befragt werden. Themen sind zu breit und zu ungenau.
ARTEN_OBEN = ('person', 'organisation', 'projekt', 'ort')
GRUENDE = ('frist', 'stand', 'erledigt', 'abgesagt')

_MEMO_GROESSE = 48


# -- Datenklassen ------------------------------------------------------------


@dataclass(frozen=True)
class Ueberholt:
    """Eine Angabe in einer Quelle, die eine neuere Quelle überholt hat (aus der Akte `sache`)."""

    episode_id: str
    grund: str
    """`frist` (verschoben), `stand` (neuere Meldung zum selben Gegenstand), `erledigt`, `abgesagt`."""
    alt: str
    """Die überholte Angabe, wörtlich aus der Quelle (Satz, gekürzt)."""
    alt_wert: str
    """Bei Fristen der Ausdruck („15. Oktober 2026“), sonst leer."""
    durch: str
    """Die Quelle, die sie überholt."""
    neu: str
    neu_wert: str
    sache: str
    ref: dict[str, Any] = field(default_factory=dict, compare=False)
    """Abschnitt der überholten Angabe (für die Prüfung beim Anzeigen)."""
    durch_ref: dict[str, Any] = field(default_factory=dict, compare=False)

    def schluessel(self) -> tuple:
        return (self.episode_id, self.grund, self.alt_wert or self.alt, self.durch, self.neu_wert or self.neu)

    def als_dict(self) -> dict[str, Any]:
        return {'episode_id': self.episode_id, 'grund': self.grund, 'alt': self.alt, 'alt_wert': self.alt_wert,
                'durch': self.durch, 'neu': self.neu, 'neu_wert': self.neu_wert, 'sache': self.sache,
                'ref': dict(self.ref), 'durch_ref': dict(self.durch_ref)}

    @classmethod
    def aus_dict(cls, roh: Any) -> 'Ueberholt | None':
        felder = ('episode_id', 'grund', 'alt', 'alt_wert', 'durch', 'neu', 'neu_wert', 'sache')
        if (not isinstance(roh, dict) or any(not isinstance(roh.get(f), str) for f in felder)
                or roh['grund'] not in GRUENDE or not isinstance(roh.get('ref'), dict)
                or not isinstance(roh.get('durch_ref'), dict)):
            return None
        return cls(**{f: roh[f] for f in felder}, ref=dict(roh['ref']), durch_ref=dict(roh['durch_ref']))


@dataclass(frozen=True)
class AktenZeile:
    """Eine Zeile „Aus der Akte“: Rolle, Sache und der Abschnitt der Quelle, auf dem sie beruht."""

    rolle: str
    """`Stand`, `Frist`, `Termin`, `Vermutlich offen`."""
    sache: str
    name: str
    ref: dict[str, Any]
    datum: str = ''
    """Bei Fristen und Terminen das Kalenderdatum (ISO)."""
    kreis: str = ''
    """Bei der Akte einer Person ihr bestätigter Kreis (`kreis.py`), sonst leer."""

    def als_dict(self) -> dict[str, Any]:
        daten = {'rolle': self.rolle, 'sache': self.sache, 'name': self.name, 'ref': dict(self.ref), 'datum': self.datum}
        if self.kreis:
            daten['kreis'] = self.kreis
        return daten

    @classmethod
    def aus_dict(cls, roh: Any) -> 'AktenZeile | None':
        if (not isinstance(roh, dict) or not all(isinstance(roh.get(f), str) for f in ('rolle', 'sache', 'name', 'datum'))
                or not isinstance(roh.get('ref'), dict) or not isinstance(roh.get('kreis', ''), str)):
            return None
        return cls(roh['rolle'], roh['sache'], roh['name'], dict(roh['ref']), roh['datum'], roh.get('kreis', ''))


@dataclass(frozen=True)
class Aufloesung:
    """Was aus den Namen der Frage wurde: eindeutige Sachen, und was nicht eindeutig war."""

    sachen: tuple[str, ...] = ()
    mehrdeutig: tuple[str, ...] = ()
    ohne_treffer: tuple[str, ...] = ()


@dataclass(frozen=True)
class Kontext:
    """Akten-Wissen zu einer Kandidatenliste: bevorzugte Zeilen, Kennzeichnungen, Zählung, Fingerabdruck."""

    sachen: tuple[str, ...] = ()
    namen: dict[str, str] = field(default_factory=dict)
    zeilen: tuple[AktenZeile, ...] = ()
    ueberholt: dict[str, tuple[Ueberholt, ...]] = field(default_factory=dict)
    zaehlung: dict[str, int] = field(default_factory=dict)
    signatur: str = ''
    kreise: dict[str, str] = field(default_factory=dict)
    """Person -> bestätigter Kreis, für die Personen der Quellen und der Frage (nur Bestätigtes)."""
    personen: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Quelle -> Personen mit bestätigtem Kreis, die an ihr beteiligt sind."""

    @property
    def oben(self) -> list[dict[str, Any]]:
        """Die bevorzugten Abschnitte (Verweise) in Rangfolge."""
        return [dict(z.ref) for z in self.zeilen]

    def als_dict(self) -> dict[str, Any]:
        daten = {'version': KONTEXT_VERSION, 'sachen': list(self.sachen), 'namen': dict(self.namen),
                 'zeilen': [z.als_dict() for z in self.zeilen],
                 'ueberholt': {eid: [u.als_dict() for u in liste] for eid, liste in self.ueberholt.items()},
                 'zaehlung': dict(self.zaehlung), 'signatur': self.signatur}
        if self.kreise:
            # Nur wenn es etwas zu sagen gibt: Gespeicherte Antworten ohne Kreis bleiben Zeichen für Zeichen gleich.
            daten['kreise'] = dict(self.kreise)
            daten['personen'] = {eid: list(liste) for eid, liste in self.personen.items()}
        return daten

    @classmethod
    def aus_dict(cls, roh: Any) -> 'Kontext | None':
        """Ein gespeicherter Kontext; None, wenn irgendetwas nicht stimmt (dann gilt er nicht)."""
        if (not isinstance(roh, dict) or roh.get('version') != KONTEXT_VERSION
                or not isinstance(roh.get('sachen'), list) or not isinstance(roh.get('signatur'), str)
                or not isinstance(roh.get('namen'), dict) or not isinstance(roh.get('zaehlung'), dict)
                or not isinstance(roh.get('zeilen'), list) or not isinstance(roh.get('ueberholt'), dict)):
            return None
        zeilen = [AktenZeile.aus_dict(z) for z in roh['zeilen']]
        ueberholt: dict[str, tuple[Ueberholt, ...]] = {}
        for eid, liste in roh['ueberholt'].items():
            if not isinstance(eid, str) or not isinstance(liste, list):
                return None
            eintraege = [Ueberholt.aus_dict(u) for u in liste]
            if any(u is None for u in eintraege):
                return None
            ueberholt[eid] = tuple(eintraege)  # type: ignore[arg-type]
        if any(z is None for z in zeilen) or any(not isinstance(s, str) for s in roh['sachen']):
            return None
        kreise, personen = roh.get('kreise', {}), roh.get('personen', {})
        if (not isinstance(kreise, dict) or not isinstance(personen, dict)
                or any(not isinstance(v, list) for v in personen.values())):
            return None
        return cls(tuple(roh['sachen']), {str(k): str(v) for k, v in roh['namen'].items()}, tuple(zeilen),  # type: ignore[arg-type]
                   ueberholt, {str(k): int(v) for k, v in roh['zaehlung'].items()}, roh['signatur'],
                   {str(k): str(v) for k, v in kreise.items()},
                   {str(k): tuple(str(x) for x in v) for k, v in personen.items()})

    def gekennzeichnet(self, episode_id: str) -> bool:
        return bool(self.ueberholt.get(episode_id))


LEER = Kontext()


# -- Zugang ------------------------------------------------------------------


#: Schalter für Messversuche („ohne Akten“, `messlatte --ohne-akten`): Aus, verhält sich die Suche wie vor E2.
AKTIV = True


def zugang(episodes: Any) -> Any:
    """Die Akten, sofern der Server sie bereitstellt; sonst None. Wirft nie."""
    if not AKTIV:
        return None
    holen = getattr(episodes, 'akten_zugang', None)
    if not callable(holen):
        return None
    try:
        return holen()
    except Exception:  # noqa: BLE001 - ohne Akten bleibt die Suche von unten
        return None


def aktualisieren(episodes: Any) -> None:
    """Führt die Bezüge kurz nach, bevor eine neue Antwort vorbereitet wird. Wirft nie."""
    holen = getattr(episodes, 'akten_aktualisieren', None)
    if callable(holen):
        try:
            holen()
        except Exception:  # noqa: BLE001 - Akten, die hinterherhinken, sind kein Grund für einen Fehler
            pass


def _heute() -> date:
    from .model import now, user_timezone
    zone = user_timezone() or timezone.utc
    return now().astimezone(zone).date()


# -- Namen zu Sachen ------------------------------------------------------------


def sachen_finden(akten: Any, namen: Iterable[str]) -> Aufloesung:
    """Löst Namen der Frage zu Sachen auf, nur wo es eindeutig ist.

    Eine Person, die genau eine Adresse als Namen trägt, ist eindeutig; Organisationen,
    Projekte und Orte sind es, wenn genau eine Sache so heißt (die Kennung ist der
    Name), oder, ohne exakten Treffer, wenn genau eine ihn enthält. Zwei
    Namensvettern oder zwei Treffer ergeben keine Sache: Wer eine der beiden meint,
    fragt der Weg der Frage zurück (`frage_weg.py`), und ein falscher Bevorzugter
    Kontext wäre schlimmer als keiner.
    """
    if akten is None:
        return Aufloesung()
    bezuege = akten.bezuege
    gefunden: list[str] = []
    mehrdeutig: list[str] = []
    leer: list[str] = []
    for name in dict.fromkeys(str(n).strip() for n in namen if str(n).strip()):
        kennung = norm(name)
        if len(kennung) < 3:
            continue
        treffer: list[str] = []
        try:
            person, kandidaten = bezuege.register().person(name)
            if person and person.startswith('person:a:'):
                treffer.append(person)
            elif kandidaten:
                mehrdeutig.append(name)
                continue
            exakt: list[str] = []
            teilweise: list[str] = []
            for art in ARTEN_OBEN:
                for eintrag in bezuege.sachen(art=art, suche=name, limit=8)['sachen']:
                    sache = eintrag['sache']
                    _, k = zerlegen(sache) or ('', '')
                    if k in (kennung, 'n:' + kennung) or k.endswith(':' + kennung):
                        exakt.append(sache)
                    elif sache not in treffer:
                        teilweise.append(sache)
            if not treffer:
                if len(exakt) == 1:
                    treffer = exakt
                elif not exakt and len(teilweise) == 1:
                    treffer = teilweise
                elif exakt or teilweise:
                    mehrdeutig.append(name)
                    continue
        except Exception:  # noqa: BLE001 - Namen, die sich nicht nachschlagen lassen, bleiben ohne Sache
            leer.append(name)
            continue
        if treffer:
            gefunden.extend(s for s in treffer if s not in gefunden)
        else:
            leer.append(name)
    return Aufloesung(tuple(gefunden[:MAX_SACHEN]), tuple(mehrdeutig), tuple(leer))


# -- Lesen aus den Akten -------------------------------------------------------


class _Leser:
    """Liest Abschnitte aus den Originalen; jede Angabe wörtlich, nur solange die Quelle gilt."""

    def __init__(self, store: WorkingMemoryStore, claims: Any) -> None:
        self.store, self.claims = store, claims
        self._gelesen: dict[tuple, str | None] = {}

    def text(self, ref: dict[str, Any]) -> str | None:
        schluessel = (ref['episode_id'], ref['fingerprint'], ref['start'], ref['end'], ref['kind'])
        if schluessel not in self._gelesen:
            gelesen = mappe.lesen(self.store, {k: ref[k] for k in ('episode_id', 'fingerprint', 'start', 'end', 'kind')},
                                  self.claims)
            self._gelesen[schluessel] = gelesen[1] if gelesen else None
        return self._gelesen[schluessel]


def _kurz(text: str, grenze: int = KURZ) -> str:
    text = ' '.join(str(text or '').split())
    return text if len(text) <= grenze else text[:grenze - 1].rstrip() + '…'


def _ref(wert: dict[str, Any]) -> dict[str, Any]:
    return {k: wert[k] for k in ('episode_id', 'fingerprint', 'start', 'end', 'kind')}


def _satz(voll: str, start: int, ende: int) -> str:
    return _kurz(_umfeld(voll, start, ende).strip() or voll[start:ende])


def _markierungen(sache: str, roh: dict[str, Any], ids: set[str], leser: _Leser) -> list[Ueberholt]:
    """Alle Angaben der Kandidaten (`ids`), die in dieser Akte als überholt geführt werden."""
    ergebnis: list[Ueberholt] = []

    def durch_text(ref: dict[str, Any]) -> str:
        return _kurz(leser.text(ref) or '')

    for f in roh.get('fristen', ()):
        ersetzt = f.get('ersetzt_durch')
        if not ersetzt or f['ref']['episode_id'] not in ids or ersetzt['ref']['episode_id'] == f['ref']['episode_id']:
            continue
        alt_voll, neu_voll = leser.text(f['ref']), leser.text(ersetzt['ref'])
        if alt_voll is None or neu_voll is None:
            continue
        ergebnis.append(Ueberholt(
            f['ref']['episode_id'], 'frist', _satz(alt_voll, f['start'], f['ende']),
            _kurz(alt_voll[f['start']:f['ende']].strip(), 60), ersetzt['ref']['episode_id'],
            _satz(neu_voll, ersetzt['start'], ersetzt['ende']),
            _kurz(neu_voll[ersetzt['start']:ersetzt['ende']].strip(), 60), sache,
            _ref(f['ref']), _ref(ersetzt['ref'])))
    for gruppe in roh.get('stand', ()):
        aktuell = gruppe['aktuell']
        for vorher in gruppe['vorher']:
            if vorher['episode_id'] in ids and vorher['episode_id'] != aktuell['episode_id']:
                alt, neu = leser.text(vorher), leser.text(aktuell)
                if alt is not None and neu is not None:
                    ergebnis.append(Ueberholt(vorher['episode_id'], 'stand', _kurz(alt), '', aktuell['episode_id'],
                                              _kurz(neu), '', sache, _ref(vorher), _ref(aktuell)))
    for e in roh.get('erledigt', ()):
        if e['ref']['episode_id'] in ids and e.get('durch') and e['durch']['episode_id'] != e['ref']['episode_id']:
            alt, neu = leser.text(e['ref']), leser.text(e['durch'])
            if alt is not None and neu is not None:
                ergebnis.append(Ueberholt(e['ref']['episode_id'], 'abgesagt' if e['grund'] == 'absage' else 'erledigt',
                                          _kurz(alt), '', e['durch']['episode_id'], _kurz(neu), '', sache,
                                          _ref(e['ref']), _ref(e['durch'])))
    for t in roh.get('termine', ()):
        laut = t.get('abgesagt')
        if laut and t['episode_id'] in ids and laut['episode_id'] != t['episode_id']:
            neu = leser.text(laut)
            if neu is not None:
                ergebnis.append(Ueberholt(t['episode_id'], 'abgesagt', 'Termin', '', laut['episode_id'], _kurz(neu),
                                          '', sache, {}, _ref(laut)))
    return ergebnis


def _zeilen(sache: str, name: str, roh: dict[str, Any], heute: date, store: WorkingMemoryStore,
            leser: _Leser, kreis: str = '') -> list[AktenZeile]:
    """Die bevorzugten Zeilen einer Akte: Stand, kommende Fristen und Termine, vermutlich Offenes."""
    zeilen: list[AktenZeile] = []

    def aufnehmen(rolle: str, ref: dict[str, Any] | None, datum: str = '') -> None:
        if ref is None or leser.text(ref) is None:
            return
        vorhanden = next((i for i, z in enumerate(zeilen) if z.ref == _ref(ref)), None)
        if vorhanden is not None:
            # Dieselbe Textstelle trägt zwei Rollen (Stand und Frist): eine Zeile, beide Rollen, das Datum der Frist.
            z = zeilen[vorhanden]
            if rolle not in z.rolle.split(' · '):
                zeilen[vorhanden] = AktenZeile(f'{z.rolle} · {rolle}', z.sache, z.name, z.ref, z.datum or datum, z.kreis)
        elif len(zeilen) < OBEN_JE_SACHE:
            zeilen.append(AktenZeile(rolle, sache, name, _ref(ref), datum, kreis))

    for gruppe in roh.get('stand', ())[:2]:
        aufnehmen('Stand', gruppe['aktuell'])
    kommend = sorted((f for f in roh.get('fristen', ()) if not f.get('ersetzt_durch')
                      and date.fromisoformat(f['datum']) >= heute), key=lambda f: (f['datum'], f['ref']['episode_id']))
    for f in kommend[:3]:
        aufnehmen('Frist', f['ref'], f['datum'])
    for t in sorted((t for t in roh.get('termine', ()) if not t.get('abgesagt')
                     and t['start'][:10] >= heute.isoformat()), key=lambda t: t['start'])[:2]:
        ref = store.best_reference(t['episode_id'], ())
        aufnehmen('Termin', ref, t['start'][:10])
    for o in roh.get('offen', ())[:2]:
        aufnehmen('Vermutlich offen', o['ref'])
    return zeilen


# -- Aufbauen -------------------------------------------------------------------


def _signatur(zeilen: Sequence[AktenZeile], ueberholt: dict[str, tuple[Ueberholt, ...]], sachen: Sequence[str],
              kreise: dict[str, str] | None = None) -> str:
    inhalt = [KONTEXT_VERSION, list(sachen),
              [[z.rolle, z.sache, z.ref, z.datum] for z in zeilen],
              [[eid, [u.schluessel() for u in liste]] for eid, liste in sorted(ueberholt.items())]]
    if kreise:
        # Ein bestätigter oder geänderter Kreis ändert, wie geantwortet wird: Die Antwort gilt dann als veraltet.
        inhalt.append(sorted(kreise.items()))
    return hashlib.sha256(json.dumps(inhalt, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]


def aufbauen(episodes: Any, claims: Any, episode_ids: Sequence[str], sachen: Sequence[str] = (),
             *, akten: Any = None) -> Kontext:
    """Bevorzugte Zeilen der aufgelösten Sachen und Kennzeichnung des Überholten unter `episode_ids`.

    Wirft nie; ohne Akten oder bei einem Fehler kommt der leere Kontext (die Suche von unten gilt).
    Das Ergebnis hängt nur vom Bestand und vom Tag ab und wird je Zustand des Bestands gemerkt.
    """
    akten = akten if akten is not None else zugang(episodes)
    if akten is None:
        return LEER
    ids = list(dict.fromkeys(str(e) for e in episode_ids))
    try:
        heute = _heute()
        stand = akten.bezuege.aenderungsstand()
        schluessel = (stand, tuple(ids), tuple(sachen), heute.isoformat())
        memo = akten.__dict__.setdefault('_kontext_memo', {})
        if schluessel in memo:
            return memo[schluessel]
        kontext = _aufbauen(episodes, claims, akten, ids, list(sachen), heute)
    except Exception:  # noqa: BLE001 - die Suche von unten bleibt gültig, wenn die Akten versagen
        return LEER
    if len(memo) >= _MEMO_GROESSE:
        memo.pop(next(iter(memo)))
    memo[schluessel] = kontext
    return kontext


def _aufbauen(episodes: Any, claims: Any, akten: Any, ids: list[str], sachen: list[str], heute: date) -> Kontext:
    store = WorkingMemoryStore(episodes)
    leser = _Leser(store, claims)
    bezuege = akten.bezuege
    # Welche Akten: die aufgelösten Sachen zuerst, dann die Sachen, zu denen die meisten Kandidaten gehören.
    from .kreis import alle_bestaetigten
    bestaetigt = alle_bestaetigten(episodes)
    zaehler: dict[str, int] = {}
    personen: dict[str, tuple[str, ...]] = {}
    for episode_id in ids:
        daten = bezuege.bezuege_der_quelle(episode_id)
        for eintrag in (daten or {}).get('bezuege', ()):
            if eintrag['art'] in ARTEN_OBEN and eintrag['sache'] not in sachen:
                zaehler[eintrag['sache']] = zaehler.get(eintrag['sache'], 0) + 1
        mit_kreis = tuple(e['sache'] for e in (daten or {}).get('bezuege', ()) if e['sache'] in bestaetigt)
        if mit_kreis:
            personen[episode_id] = mit_kreis
    weitere = sorted(zaehler, key=lambda s: (-zaehler[s], s))
    reihenfolge = [*sachen, *weitere][:MAX_AKTEN]
    ausgelassen = len(sachen) + len(weitere) - len(reihenfolge)
    namen: dict[str, str] = {}
    zeilen: list[AktenZeile] = []
    markierungen: dict[str, dict[tuple, Ueberholt]] = {}
    gelesen = 0
    idsatz = set(ids)
    for sache in reihenfolge:
        roh = akten.roh(sache)
        if roh is None:
            continue
        gelesen += 1
        if sache in sachen:
            # Der Name kostet eine Abfrage je Sache: nur die aufgelösten Sachen der Frage brauchen ihn.
            namen[sache] = bezuege.beschriftung(sache)
            zeilen.extend(_zeilen(sache, namen[sache], roh, heute, store, leser, bestaetigt.get(sache, '')))
        for m in _markierungen(sache, roh, idsatz, leser):
            markierungen.setdefault(m.episode_id, {}).setdefault(m.schluessel(), m)
    # Bevorzugte Zeilen höchstens MAX_OBEN insgesamt, Duplikate (dieselbe Stelle) nur einmal.
    gesehen: set[str] = set()
    gekuerzt: list[AktenZeile] = []
    for z in zeilen:
        marke = json.dumps(z.ref, sort_keys=True)
        if marke not in gesehen and len(gekuerzt) < MAX_OBEN:
            gesehen.add(marke)
            gekuerzt.append(z)
    ueberholt = {eid: tuple(sorted(liste.values(), key=lambda u: (GRUENDE.index(u.grund), u.durch, u.alt_wert)))
                 for eid, liste in markierungen.items()}
    zaehlung = {'sachen': len(sachen), 'akten_gelesen': gelesen, 'akten_ausgelassen': max(ausgelassen, 0),
                'oben': len(gekuerzt), 'gekennzeichnet': len(ueberholt)}
    kreise = {s: bestaetigt[s] for s in [*sachen, *(p for liste in personen.values() for p in liste)] if s in bestaetigt}
    for sache in kreise:
        if sache not in namen:
            namen[sache] = bezuege.beschriftung(sache)
    return Kontext(tuple(sachen), namen, tuple(gekuerzt), ueberholt, zaehlung,
                   _signatur(gekuerzt, ueberholt, sachen, kreise), kreise, personen)


# -- Für das Modell ------------------------------------------------------------------


def hinweis_fuer_modell(kontext: Kontext, episode_id: str, nummern: dict[str, str],
                        titel: dict[str, str]) -> list[dict[str, str]]:
    """Die Kennzeichnung einer Quelle in der Sprache des Kontexts (`ueberholt`-Feld einer Zeile).

    `nummern` ordnet Quellen ihrer Kennung im Kontext zu (`S3`), `titel` den Titel für Quellen, die nicht im
    Kontext stehen. Reine Funktion, damit Kontext und Test dasselbe sehen.
    """
    hinweise = []
    for u in kontext.ueberholt.get(episode_id, ()):
        durch = nummern.get(u.durch)
        hinweise.append({
            'grund': {'frist': 'Frist verschoben', 'stand': 'durch neuere Meldung überholt',
                      'erledigt': 'erledigt', 'abgesagt': 'abgesagt'}[u.grund],
            'ueberholte_angabe': u.alt_wert or u.alt,
            'neu': u.neu_wert or u.neu,
            'neue_quelle': durch or titel.get(u.durch, u.durch)})
    return hinweise


def hinweis_kreis(kontext: Kontext, episode_id: str) -> list[str]:
    """Wie über die Personen einer Quelle zu sprechen ist (Feld `kreis` einer Zeile im Kontext des Modells).

    Je Person mit bestätigtem Kreis ein Satz: „Anna Keller – innerer Kreis: mit Vornamen nennen, …“. Reine Funktion.
    """
    from .kreis import FUER_MODELL
    return [f'{kontext.namen.get(p, p)} – {FUER_MODELL[kontext.kreise[p]]}'
            for p in kontext.personen.get(episode_id, ()) if kontext.kreise.get(p) in FUER_MODELL]


def kreis_der_quelle(kontext: Kontext, episode_id: str) -> str:
    """Der zurückhaltendste bestätigte Kreis unter den Personen einer Quelle (für die Satzauswahl), sonst leer."""
    from .kreis import KREISE
    kreise = [kontext.kreise[p] for p in kontext.personen.get(episode_id, ()) if p in kontext.kreise]
    return max(kreise, key=KREISE.index) if kreise else ''


def stellen(kontext: Kontext, episode_id: str) -> list[tuple[int, int, str]]:
    """Die Stellen einer Quelle, auf die sich die Akte stützt (siehe `stellen_von`), aus dem Kontext der Akten."""
    return stellen_von(kontext.ueberholt.get(episode_id, ()), kontext.zeilen, episode_id)


def stellen_von(ueberholt: Sequence[Ueberholt], zeilen: Sequence[AktenZeile], episode_id: str) -> list[tuple[int, int, str]]:
    """Die Abschnitte (Anfang, Ende, Marke) einer Quelle, auf die sich die Akte stützt: überholte Angabe und bevorzugte Zeilen.

    Die Marke ist der Ausdruck der überholten Frist („15. Oktober 2026“), sonst leer. Für den Auszug langer Quellen
    (`absatzauswahl.ergaenzen`): Was die Akte kennzeichnet, darf im Kontext nicht wegfallen.
    """
    def bereich(ref: Any) -> tuple[int, int] | None:
        if (isinstance(ref, dict) and ref.get('episode_id') == episode_id and type(ref.get('start')) is int
                and type(ref.get('end')) is int and ref['start'] < ref['end']):
            return ref['start'], ref['end']
        return None

    ergebnis: list[tuple[int, int, str]] = []
    for u in ueberholt:
        if (gefunden := bereich(u.ref)) is not None:
            ergebnis.append((*gefunden, u.alt_wert))
    for zeile in zeilen:
        if (gefunden := bereich(zeile.ref)) is not None:
            ergebnis.append((*gefunden, ''))
    return ergebnis


def nachrangig_sortiert(reihen: Sequence[Any], kontext: Kontext, schluessel_id, *, zusaetzlich=None) -> list[Any]:
    """Gekennzeichnete Zeilen ans Ende, sonst unverändert (stabil).

    `zusaetzlich` (Zeile -> bool) nennt weitere Kennzeichnungen, die hintere Plätze verdienen
    (Namensvettern und Zeiträume, `kennzeichnung.py`).
    """
    return sorted(reihen, key=lambda r: kontext.gekennzeichnet(schluessel_id(r)) or bool(zusaetzlich and zusaetzlich(r)))


__all__ = ['AktenZeile', 'Aufloesung', 'Kontext', 'LEER', 'Ueberholt', 'aktualisieren', 'aufbauen', 'hinweis_fuer_modell',
           'hinweis_kreis', 'kreis_der_quelle', 'nachrangig_sortiert', 'sachen_finden', 'stellen', 'stellen_von', 'zugang']
