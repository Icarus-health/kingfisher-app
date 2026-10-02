"""Terminvorbereitung aus den Akten: wer kommt, was wollen sie, was ist der Stand?

Für jeden Termin mit bekannten Teilnehmern entsteht die Vorbereitung **ohne Klick** aus
dem, was ohnehin da ist: die Akte je Teilnehmer (über die Mailadresse, `bezuege.py`),
die gemeinsame Akte der Organisation oder des Projekts, die Frist- und Packlage. Dieses
Modul erfindet nichts und schreibt nichts; jede Zeile ist ein wörtliches Zitat mit Quelle.

Was pro Teilnehmer steht:

* **Was sie wollen**: Bitten und Zusagen, die die Akte als „vermutlich offen“ führt (sie
  behauptet nie, dass etwas offen ist; hier steht dasselbe Wort dabei).
* **Letzter Kontakt** und **Zuletzt**: die jüngsten Quellen (Mail, Notiz), jede mit Datum.
* **Stand**: die jüngste Änderung oder Statusmeldung je Gegenstand. Ältere Werte stehen
  nicht als aktuell da (Aktualität schlägt Ähnlichkeit, wie in der Akte).
* **Fristen**: kommende Fristen der Person; überholte nie.

Hintergrund ist der Stand der gemeinsamen Akte (Organisation, Projekt); die Packliste
kommt aus `einpacken.py`, die Wegezeit aus `wegezeit.py` (wird vom Aufrufer ergänzt).

Teilnehmer ohne Adresse oder ohne Akte stehen unter „Nicht im Gedächtnis“. Sie werden
nie über den Namen geraten.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

from . import einpacken, fristlage
from .akten import stamm_menge
from .bezuege import sache_id
from .episodes import EpisodeKind, mail_address
from .fristlage import Frist, quelle_art, richtung
from .model import user_timezone
from .vorbereitung import teilnehmer as teilnehmer_aus

#: Wie viele jüngste Quellen je Person als „Zuletzt“ stehen.
ZULETZT = 3
#: Wie viele Stand-Zeilen je Person und je Hintergrund.
STAND = 3
#: Wie viele Bitten und Zusagen je Person.
WILL = 4
#: Wie weit vor dem Termin Quellen als Packlisten-Beleg gelten.
PACK_TAGE = 45
#: Wie weit zurück eigene Wünsche einer Person aus ihren Mails gelesen werden, und wie viele.
WUNSCH_TAGE = 120
WUNSCH_ZEILEN = 4
WUNSCH_JE_MAIL = 2

# Ein Satz, in dem jemand ausdrückt, was er sich wünscht oder braucht („Das Screening hätte ich gern ab
# Januar“, „Ich würde mir eine Schulung wünschen“). Gelesen wird nur, was die Person selbst schrieb.
_WUNSCH = re.compile(r'\b(?:wünsch\w*|wunsch\b|(?:hätte|würde|wäre)\w*\b.{0,80}\bgern\w*|'
                     r'gern\w*\b.{0,60}\b(?:hätte|würde)\w*|möchte\w*|bräuchte\w*|benötig\w*|'
                     r'am\s+wichtigsten)', re.I)
# Ein Satz mit einem Geldbetrag, den die Person selbst nannte („… bis zu 12.000 Euro einplanen“).
_BETRAG = re.compile(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?\s*(?:Euro|€|EUR)\b|\b\d+(?:,\d+)?\s*(?:Euro|€|EUR)\b', re.I)
_WUNSCH_STARK = re.compile(r'\b(?:wünsch\w*|wunsch\b|gern\w*|möchte\w*|bräuchte\w*|benötig\w*)', re.I)
_ZITATENDE = re.compile(r'^(?:>|am\s.{5,80}\sschrieb|-{3,}\s*(?:original|ursprüngliche)|von:\s)', re.I)


@dataclass
class Beleg:
    episode_id: str
    titel: str
    datum: str | None
    art: str
    """`Mail`, `Notiz`, `Termin` oder leer."""

    def to_dict(self) -> dict[str, Any]:
        return {'episode_id': self.episode_id, 'titel': self.titel, 'datum': self.datum, 'art': self.art}


@dataclass
class Zeile:
    """Ein wörtliches Zitat mit seiner Quelle."""

    text: str
    beleg: Beleg | None
    art: str = ''
    """Art des Abschnitts laut Akte (Bitte, Zusage, Änderung, Statusmeldung, Angabe)."""
    rolle: str = ''
    """Bei Bitten und Zusagen: `sie_bittet`, `du_sagtest_zu`, `sie_sagte_zu`, `du_batest`, `offen`."""
    vermutlich: bool = False
    hinweis: str = ''
    """z. B. „danach geändert“."""

    def to_dict(self) -> dict[str, Any]:
        return {'text': self.text, 'beleg': self.beleg.to_dict() if self.beleg else None, 'art': self.art,
                'rolle': self.rolle, 'vermutlich': self.vermutlich, 'hinweis': self.hinweis}


@dataclass
class Person:
    name: str
    adresse: str | None
    sache: str | None
    bekannt: bool
    organisation: str = ''
    letzter_kontakt: Zeile | None = None
    erster_kontakt: Zeile | None = None
    will: list[Zeile] = field(default_factory=list)
    zuletzt: list[Zeile] = field(default_factory=list)
    stand: list[Zeile] = field(default_factory=list)
    fristen: list[Frist] = field(default_factory=list)
    kreis: str = 'unbestimmt'
    """Bestätigter Kreis (`kreis.py`): steuert, wie ausführlich und wie zurückhaltend über die Person gesprochen wird."""

    def to_dict(self) -> dict[str, Any]:
        return {'name': self.name, 'adresse': self.adresse, 'sache': self.sache, 'bekannt': self.bekannt,
                'organisation': self.organisation, 'kreis': self.kreis,
                'letzter_kontakt': self.letzter_kontakt.to_dict() if self.letzter_kontakt else None,
                'erster_kontakt': self.erster_kontakt.to_dict() if self.erster_kontakt else None,
                'will': [z.to_dict() for z in self.will], 'zuletzt': [z.to_dict() for z in self.zuletzt],
                'stand': [z.to_dict() for z in self.stand], 'fristen': [f.to_dict() for f in self.fristen]}


@dataclass
class Hintergrund:
    sache: str
    name: str
    art: str
    """`organisation`, `projekt`."""
    herkunft: str
    """`gemeinsam` (alle Teilnehmer), `projekt` (Termin ist dem Projekt zugeordnet), `vermutet` (nur ein Vorschlag)."""
    zeilen: list[Zeile] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {'sache': self.sache, 'name': self.name, 'art': self.art, 'herkunft': self.herkunft,
                'zeilen': [z.to_dict() for z in self.zeilen]}


@dataclass
class Termin:
    uid: str
    titel: str
    beginn: datetime
    ende: datetime | None
    ort: str = ''
    teilnehmer: list[str] = field(default_factory=list)
    notiz: str = ''
    """Notiz zum Termin (Beschreibung im Kalender), wenn bekannt."""
    episode_id: str | None = None
    """Die Termin-Episode im Gedächtnis, wenn bekannt."""
    ganztaegig: bool = False

    @classmethod
    def aus_dict(cls, daten: dict[str, Any], *, notiz: str = '', episode_id: str | None = None) -> 'Termin | None':
        try:
            beginn = datetime.fromisoformat(str(daten.get('start')))
        except ValueError:
            return None
        try:
            ende = datetime.fromisoformat(str(daten.get('end') or ''))
        except ValueError:
            ende = None
        return cls(uid=str(daten.get('uid') or ''), titel=str(daten.get('summary') or 'Termin'), beginn=beginn,
                   ende=ende, ort=' '.join(str(daten.get('location') or '').split()),
                   teilnehmer=[str(a) for a in daten.get('attendees') or ()], notiz=notiz, episode_id=episode_id,
                   ganztaegig=bool(daten.get('all_day')))


@dataclass
class Vorbereitung:
    termin: Termin
    personen: list[Person] = field(default_factory=list)
    unbekannt: list[str] = field(default_factory=list)
    """Teilnehmer, die nicht im Gedächtnis stehen (nie über den Namen geraten)."""
    hintergrund: list[Hintergrund] = field(default_factory=list)
    projekt: dict[str, Any] | None = None
    fristen: list[Frist] = field(default_factory=list)
    einpacken: list[einpacken.Packstueck] = field(default_factory=list)
    wegezeit: dict[str, Any] | None = None

    @property
    def bereit(self) -> bool:
        """Liegt mehr bereit als ein Name? Nur dann gilt der Termin als vorbereitet."""
        return any(p.bekannt and (p.will or p.zuletzt or p.stand or p.fristen) for p in self.personen)

    def to_dict(self) -> dict[str, Any]:
        t = self.termin
        return {'uid': t.uid, 'episode_id': t.episode_id, 'titel': t.titel, 'beginn': t.beginn.isoformat(),
                'ende': t.ende.isoformat() if t.ende else None, 'ort': t.ort,
                'personen': [p.to_dict() for p in self.personen], 'unbekannt': self.unbekannt,
                'hintergrund': [h.to_dict() for h in self.hintergrund], 'projekt': self.projekt,
                'fristen': [f.to_dict() for f in self.fristen], 'einpacken': [{**p.to_dict(), 'datum': lokal(p.zeit)} for p in self.einpacken],
                'wegezeit': self.wegezeit, 'bereit': self.bereit}


# -- Akten lesen -------------------------------------------------------------


def _kurz(text: str, laenge: int = 200) -> str:
    text = ' '.join(str(text or '').split())
    return text if len(text) <= laenge else text[:laenge].rsplit(' ', 1)[0].rstrip(',;:.') + ' …'


def lokal(wert: Any) -> str | None:
    """Ein Zeitpunkt als ISO-Text in der Zeitzone des Nutzers; die Quellen tragen UTC, der Tag soll der des Nutzers sein."""
    try:
        moment = wert if isinstance(wert, datetime) else datetime.fromisoformat(str(wert))
    except ValueError:
        return None
    zone = user_timezone()
    return (moment.astimezone(zone) if zone and moment.tzinfo else moment).isoformat()


def _beleg(zeile: dict[str, Any], art: str = '') -> Beleg:
    datum = zeile.get('occurred_at') or zeile.get('datum') or zeile.get('recorded_at')
    return Beleg(zeile['episode_id'], zeile.get('titel') or '', lokal(datum), art)


def _zeile(zeile: dict[str, Any], quellenart: str = '', **zusatz: Any) -> Zeile:
    return Zeile(text=_kurz(zeile['text']), beleg=_beleg(zeile, quellenart), art=zeile.get('art') or '', **zusatz)


class _Arten:
    """Merkt die Art (Mail, Notiz, Termin) je Episode; die Zeilen der Akte tragen sie nicht überall."""

    def __init__(self, episodes: Any) -> None:
        self._episodes, self._gemerkt = episodes, {}

    def __call__(self, episode_id: str) -> str:
        if episode_id not in self._gemerkt:
            try:
                self._gemerkt[episode_id] = self._episodes.get(episode_id).kind.value
            except Exception:  # noqa: BLE001 - Beiwerk: ohne Art fehlt nur das Wort „Mail“
                self._gemerkt[episode_id] = ''
        return self._gemerkt[episode_id]


def _rolle(eintrag: dict[str, Any], adresse: str | None, eigene: list[str]) -> str:
    wer = richtung(eintrag.get('participants') or (), eigene)
    art = eintrag.get('art')
    absender = mail_address((eintrag.get('participants') or [''])[0])
    if wer == 'von_mir':
        return 'du_sagtest_zu' if art == 'Zusage' else 'du_batest'
    if wer == 'an_mich':
        if art == 'Zusage':
            return 'sie_sagte_zu'
        if adresse is None or absender == adresse:
            return 'sie_bittet'
        return 'offen'
    return 'offen'


def _eigener_text(body: str) -> str:
    """Was der Absender selbst schrieb: ohne zitierten Verlauf darunter."""
    zeilen: list[str] = []
    for zeile in str(body or '').splitlines():
        if _ZITATENDE.match(zeile.strip()):
            break
        zeilen.append(zeile)
    return '\n'.join(zeilen)


def _wuensche(adresse: str, quellen: list[dict[str, Any]], episodes: Any, jetzt: datetime) -> list[Zeile]:
    """Was die Person laut ihren jüngsten Mails wünscht oder an Beträgen nannte: wörtliche Sätze mit Quelle.

    Wünsche sind als Vermutung gekennzeichnet; ein genannter Betrag ist ihr Wortlaut. Betrifft ein älterer
    Satz denselben Gegenstand wie ein jüngerer („Budget … Euro“), zählt nur der jüngere: Aktualität schlägt
    Ähnlichkeit, wie in der Akte.
    """
    grenze = jetzt - timedelta(days=WUNSCH_TAGE)
    kandidaten: list[Zeile] = []
    for q in quellen:  # jüngste Quelle zuerst
        if q['art'] != 'message':
            continue
        try:
            episode = episodes.get(q['episode_id'])
        except Exception:  # noqa: BLE001
            continue
        zeit = episode.reference_time()
        if zeit > jetzt or zeit < grenze:
            continue
        if not episode.participants or mail_address(episode.participants[0]) != adresse:
            continue
        beleg = Beleg(episode.id, episode.title, lokal(zeit), 'Mail')
        saetze = einpacken.saetze(_eigener_text(episode.body))
        # Ein ausdrücklicher Wunsch („hätte ich gern“, „wünschen“) geht der bloßen Gewichtung („am wichtigsten“) vor.
        wuensche = sorted((s for s in saetze if _WUNSCH.search(s)), key=lambda s: 0 if _WUNSCH_STARK.search(s) else 1)
        kandidaten += [Zeile(_kurz(s), beleg, 'Wunsch', 'wunsch', True) for s in wuensche[:WUNSCH_JE_MAIL]]
        kandidaten += [Zeile(_kurz(s), beleg, 'Genannt', 'genannt') for s in saetze
                       if _BETRAG.search(s) and s not in wuensche[:WUNSCH_JE_MAIL]]
    behalten: list[tuple[Zeile, frozenset[str]]] = []
    for zeile in kandidaten:
        stamm = stamm_menge(zeile.text)
        # Nur gegen Sätze aus anderen, jüngeren Mails: Zwei Sätze derselben Mail ergänzen sich.
        if any(z.beleg.episode_id != zeile.beleg.episode_id and len(stamm & anderer) >= 2 for z, anderer in behalten):
            continue  # ein jüngerer Satz zum selben Gegenstand steht schon da
        behalten.append((zeile, stamm))
    return [z for z, _ in behalten][:WUNSCH_ZEILEN]


def _person(name: str, adresse: str | None, akten: Any, arten: _Arten, eigene: list[str],
            jetzt: datetime) -> Person:
    sache = sache_id('person', 'a:' + adresse) if adresse else None
    akte = akten.akte(sache, jetzt=jetzt, alle=True) if sache else None
    if akte is None:
        return Person(name=name, adresse=adresse, sache=sache, bekannt=False)
    # Verlauf: jüngste zuerst; der Termin selbst und Künftiges gehören nicht zu „zuletzt“.
    ueberholt = _ueberholt(akte)
    kontakte = [e for e in akte['verlauf']['eintraege']
                if e['quelle_art'] != 'event' and e['text'] and _vergangen(e['datum'], jetzt)
                and (e['episode_id'], e['text']) not in ueberholt]
    zuletzt = [_zeile(e, quelle_art(e['quelle_art'])) for e in kontakte[:ZULETZT]]
    person = Person(name=akte['name'] or name, adresse=adresse, sache=sache, bekannt=True, zuletzt=zuletzt,
                    letzter_kontakt=zuletzt[0] if zuletzt else None, kreis=akte.get('kreis') or 'unbestimmt')
    if len(kontakte) > ZULETZT:
        # Woher man sich kennt: die älteste Quelle. Nur, wenn sie nicht ohnehin unter „zuletzt“ steht.
        aeltester = kontakte[-1]
        person.erster_kontakt = _zeile(aeltester, quelle_art(aeltester['quelle_art']))
    if adresse:
        person.will.extend(_wuensche(adresse, akten.bezuege.quellen_von(sache), akten.episodes, jetzt))
    for e in akte['offen']['eintraege'][:WILL]:
        person.will.append(_zeile(e, quelle_art(arten(e['episode_id'])), vermutlich=True,
                                  rolle=_rolle(e, adresse, eigene),
                                  hinweis='danach geändert' if e.get('danach_geaendert') else ''))
    stand = akte['stand_der_dinge']
    gruppen = ([stand['aktuell']] if stand['aktuell'] else []) + [g['aktuell'] for g in stand['weitere']]
    gezeigt = {(z.beleg.episode_id, z.text) for z in zuletzt if z.beleg}
    person.stand = [z for z in (_zeile(g, quelle_art(arten(g['episode_id']))) for g in gruppen[:STAND])
                    if (z.beleg.episode_id, z.text) not in gezeigt]  # was schon unter „Letzter Kontakt“ steht, nicht noch einmal
    organisationen = [b for b in akte['beteiligte']['eintraege'] if b['art'] == 'organisation']
    person.organisation = organisationen[0]['name'] if organisationen else ''
    person.fristen = fristlage.nach_dringlichkeit(
        fristlage.aus_akte(akte, heute=jetzt.date(), eigene=eigene, tage_voraus=30, quellenart=arten))
    return person


def _ueberholt(akte: dict[str, Any]) -> set[tuple[str, str]]:
    """(Quelle, Zitat) aller Zeilen, die die Akte unter „vorher“ führt: ein neuerer Stand hat sie abgelöst.

    Sie dürfen auch nicht als „zuletzt“ oder Hintergrund auftauchen: Ein überholter Wert bleibt in der
    Akte nachvollziehbar, in der Vorbereitung ist er kein Stand."""
    stand = akte['stand_der_dinge']
    gruppen = [stand, *stand['weitere']] if stand['aktuell'] else list(stand['weitere'])
    return {(z['episode_id'], z['text']) for g in gruppen for z in g.get('vorher', ())}


def _vergangen(datum: str | None, jetzt: datetime) -> bool:
    try:
        moment = datetime.fromisoformat(str(datum))
    except ValueError:
        return True
    return moment.tzinfo is None or moment <= jetzt


def _hintergrund(sache: str, herkunft: str, akten: Any, arten: _Arten, jetzt: datetime) -> Hintergrund | None:
    akte = akten.akte(sache, jetzt=jetzt, alle=True)
    if akte is None:
        return None
    stand = akte['stand_der_dinge']
    gruppen = ([stand['aktuell']] if stand['aktuell'] else []) + [g['aktuell'] for g in stand['weitere']]
    zeilen = [_zeile(z, quelle_art(arten(z['episode_id']))) for z in gruppen[:STAND]]
    if not zeilen:
        # Ohne Änderungen oder Statusmeldungen: die jüngsten Quellen der Sache, als solche erkennbar.
        ueberholt = _ueberholt(akte)
        zeilen = [_zeile(e, quelle_art(e['quelle_art'])) for e in akte['verlauf']['eintraege']
                  if e['quelle_art'] != 'event' and e['text'] and _vergangen(e['datum'], jetzt)
                  and (e['episode_id'], e['text']) not in ueberholt][:2]
    if not zeilen:
        return None
    return Hintergrund(sache=sache, name=akte['name'], art=akte['art'], herkunft=herkunft, zeilen=zeilen)


def _gemeinsame(personen: list[Person], akten: Any, jetzt: datetime) -> list[str]:
    """Organisationen und Projekte, die alle bekannten Teilnehmer teilen; bei einem: seine wichtigste."""
    zaehler: dict[str, int] = {}
    ausmass: dict[str, int] = {}
    bekannte = [p for p in personen if p.bekannt and p.sache]
    for p in bekannte:
        akte = akten.akte(p.sache, jetzt=jetzt, alle=True)
        for b in (akte['beteiligte']['eintraege'] if akte else ()):
            if b['art'] in ('organisation', 'projekt'):
                zaehler[b['sache']] = zaehler.get(b['sache'], 0) + 1
                ausmass[b['sache']] = ausmass.get(b['sache'], 0) + b['anzahl']
    gemeinsame = [s for s, n in zaehler.items() if n == len(bekannte)]
    return sorted(gemeinsame, key=lambda s: (-ausmass[s], s))[:2]


# -- Packliste ---------------------------------------------------------------


def _packquellen(termin: Termin, personen: list[Person], akten: Any, episodes: Any, eigene: list[str],
                 jetzt: datetime) -> list[einpacken.Quelle]:
    """Texte, die etwas zum Einpacken nennen können: Notiz zum Termin, Quellen der Teilnehmer, eigene Notizen zum Thema."""
    quellen: dict[str, einpacken.Quelle] = {}
    grenze = termin.beginn - timedelta(days=PACK_TAGE)
    if termin.notiz.strip():
        quellen['termin'] = einpacken.Quelle(termin.episode_id or 'termin:' + termin.uid, termin.titel, termin.beginn,
                                              termin.notiz, 'termin', True)
    nachnamen = {n for n in (_nachname(p.name) for p in personen if p.bekannt) if n}
    organisationen = {p.organisation.casefold() for p in personen if p.organisation}
    titel_woerter = {w.casefold() for w in termin.titel.replace('-', ' ').split() if len(w) >= 7}
    # 1. Quellen, an denen die Teilnehmer beteiligt sind (Mail, Notiz mit Beteiligten).
    for p in personen:
        if not p.sache:
            continue
        for q in akten.bezuege.quellen_von(p.sache):
            if q['art'] == 'event':
                continue
            _aufnehmen(quellen, q['episode_id'], episodes, eigene, grenze, termin.beginn)
    # 2. Eigene Notizen der letzten Tage, die den Termin nennen (Name, Organisation, Titelwort im Titel oder Text).
    for episode in episodes.geltende_zuletzt(EpisodeKind.DOCUMENT, limit=400):
        if episode.id in quellen:
            continue
        zeit = episode.reference_time()
        if not grenze <= zeit <= termin.beginn:
            continue
        heu = (episode.title + ' ' + episode.body).casefold()
        if (any(_als_wort(n, heu) for n in nachnamen) or any(o and _als_wort(o, heu) for o in organisationen)
                or any(w in heu for w in titel_woerter)):
            _aufnehmen(quellen, episode.id, episodes, eigene, grenze, termin.beginn)
    return list(quellen.values())


def _als_wort(name: str, text: str) -> bool:
    """Steht `name` als ganzes Wort im (kleingeschriebenen) Text? „Braun“ ist nicht „Braunschweig“."""
    return re.search(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', text) is not None


def _nachname(name: str) -> str:
    teile = [t for t in name.replace(',', ' ').split() if not t.endswith('.') and t.casefold() not in ('herr', 'frau', 'dr', 'prof')]
    return teile[-1] if teile and len(teile[-1]) >= 4 else ''


def _aufnehmen(quellen: dict[str, einpacken.Quelle], episode_id: str, episodes: Any, eigene: list[str],
               grenze: datetime, bis: datetime) -> None:
    if episode_id in quellen:
        return
    try:
        if episode_id not in episodes.usable_ids([episode_id]):  # entzogen, ignoriert oder überholt: nie in die Packliste
            return
        episode = episodes.get(episode_id)
    except Exception:  # noqa: BLE001
        return
    zeit = episode.reference_time()
    if not grenze <= zeit <= bis or episode.kind.value == 'event':
        return
    if episode.kind.value == 'document':
        art, von_mir = 'notiz', True
    else:
        art = 'mail'
        von_mir = richtung(episode.participants, eigene) == 'von_mir'
    quellen[episode_id] = einpacken.Quelle(episode.id, episode.title, zeit, episode.body, art, von_mir)


# -- Zusammenbau -------------------------------------------------------------


def vorbereiten(termin: Termin, *, akten: Any, episodes: Any, eigene: Iterable[str] = (), jetzt: datetime,
                workspace: Any = None) -> Vorbereitung:
    """Die Vorbereitung eines Termins aus den Akten. Ohne Modell, ohne Netz, ohne Schreibzugriff."""
    eigene = list(eigene)
    arten = _Arten(episodes)
    index = episodes.participants_for_addresses(termin.teilnehmer)
    bekannte = teilnehmer_aus(termin.teilnehmer, index=index, eigene=eigene)
    ergebnis = Vorbereitung(termin=termin)
    for t in bekannte:
        person = _person(t['name'], t['adresse'], akten, arten, eigene, jetzt)
        if person.bekannt:
            ergebnis.personen.append(person)
        else:
            ergebnis.unbekannt.append(t['name'])
    if workspace is not None:
        ergebnis.projekt = _projekt(termin, workspace, episodes, eigene)
    herkuenfte: list[tuple[str, str]] = []
    if ergebnis.projekt and ergebnis.projekt.get('id'):
        herkuenfte.append((sache_id('projekt', ergebnis.projekt['id']),
                           'vermutet' if ergebnis.projekt.get('herkunft') == 'vorschlag' else 'projekt'))
    herkuenfte += [(s, 'gemeinsam') for s in _gemeinsame(ergebnis.personen, akten, jetzt)]
    gesehen: set[str] = set()
    for sache, herkunft in herkuenfte:
        if sache in gesehen:
            continue
        gesehen.add(sache)
        block = _hintergrund(sache, herkunft, akten, arten, jetzt)
        if block is not None:
            schon = {(z.beleg.episode_id, z.text) for p in ergebnis.personen
                     for z in (*p.zuletzt, *p.stand, *p.will) if z.beleg}
            block.zeilen = [z for z in block.zeilen if not z.beleg or (z.beleg.episode_id, z.text) not in schon]
        if block is not None and block.zeilen:
            ergebnis.hintergrund.append(block)
    ergebnis.fristen = fristlage.nach_dringlichkeit(f for p in ergebnis.personen for f in p.fristen)
    ergebnis.einpacken = einpacken.packliste(_packquellen(termin, ergebnis.personen, akten, episodes, eigene, jetzt))
    return ergebnis


def termin_im_gedaechtnis(episodes: Any, uid: str, quelle: str = '') -> tuple[str | None, str]:
    """(Episode, Notiz) des Termins mit dieser UID aus dem Gedächtnis (Termine der Art `event`, C1).

    Die Anzeige des Kalenders gibt die Notiz nicht heraus; das Gedächtnis hat sie. Es gilt die aktuelle
    Fassung. `uid` ist die Kennung der Anzeige („<Quelle>:<UID>“, `CalendarCollection`), das Gedächtnis
    kennt die UID der Quelle; `quelle` ist deren Kennung. Ohne Treffer: (None, '').
    """
    if not uid:
        return None, ''
    roh = uid[len(quelle) + 1:] if quelle and uid.startswith(quelle + ':') else uid
    muster = '%' + roh.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    zeilen = episodes.termine_nach_herkunft(muster)
    from .calendar_memory import uid_aus_herkunft
    for episode_id, body, herkunft in zeilen:
        if uid_aus_herkunft(herkunft) == roh:
            _, _, notiz = str(body).partition('\nNotiz:\n')
            return episode_id, notiz.strip()
    return None, ''


def _projekt(termin: Termin, workspace: Any, episodes: Any, eigene: list[str]) -> dict[str, Any] | None:
    from .vorbereitung import zuordnung
    ereignis = {'uid': termin.uid, 'summary': termin.titel, 'attendees': termin.teilnehmer}
    try:
        return zuordnung(ereignis, episodes=episodes, workspace=workspace, eigene=eigene)['projekt']
    except Exception:  # noqa: BLE001 - das Projekt ist Beiwerk der Vorbereitung
        return None


__all__ = ['Beleg', 'Hintergrund', 'Person', 'Termin', 'Vorbereitung', 'Zeile', 'vorbereiten']
