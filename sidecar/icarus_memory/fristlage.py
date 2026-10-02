"""Fristen im Briefing: was kommt in den nächsten Tagen, und was ist überfällig?

Gelesen wird ausschließlich aus den Akten (`akten.py`), nichts wird neu gedeutet:

* **Kommend**: die geltenden Fristen der Akte mit Datum ab heute.
* **Verstrichen und noch offen**: eine Frist in einer Bitte oder Zusage, deren Datum
  vorbei ist und zu der die Akte **keine** spätere Erledigung oder Absage kennt. Sie
  ist als Vermutung gekennzeichnet („vermutlich noch offen“), weil die Akte das nie
  behauptet.
* **Überholte Fristen sind nie dabei.** Verschiebt eine spätere Quelle den Termin, führt die
  Akte die alte Frist unter „ersetzt“ (`fristen.ersetzt`); dieses Modul liest nur `kommend` und
  `verstrichen` und prüft `ersetzt_durch` zusätzlich selbst. Die alte Frist wird nie als
  aktuell gezeigt, weder als kommend noch als überfällig.

Jede Zeile trägt ihre Quelle (Episode, Titel, Datum) und das wörtliche Zitat.

Reihenfolge nach Dringlichkeit: heute und morgen Fälliges, dann Verstrichenes (das
Jüngste zuerst, denn je älter, desto eher hat es sich still erledigt), dann Kommendes nach
Datum.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Iterable

from .datumstext import tag_und_monat
from .episodes import mail_address
from .kontakte import anzeigename
from .model import user_timezone

#: Wie weit ins Briefing geschaut wird.
TAGE_VORAUS = 7
#: Ältere verstrichene Fristen zeigt das Briefing nicht mehr (sie haben sich meist still erledigt).
TAGE_ZURUECK = 45


@dataclass(frozen=True)
class Frist:
    datum: date
    text: str
    """Der Satz mit der Fristangabe, wörtlich aus der Quelle (sonst der Anfang des Absatzes)."""
    ausdruck: str
    """Die Datumsangabe im Text („bis Freitag“, „12. November 2026“)."""
    episode_id: str
    titel: str
    quelle_datum: str | None
    quelle_art: str
    """`Mail`, `Notiz`, `Termin` oder leer."""
    art: str
    """`Bitte`, `Zusage`, `Änderung`."""
    richtung: str
    """`von_mir` (Du hast es geschrieben), `an_mich` (jemand anderes), `unklar` (Notiz, Protokoll)."""
    status: str
    """`kommend` oder `verstrichen`."""
    tage: int
    """Tage bis zur Frist; negativ, wenn sie verstrichen ist."""
    sache: str = ''
    sache_name: str = ''
    vermutlich: bool = False
    """Bei `verstrichen`: nur vermutlich noch offen."""
    andere: str = ''
    """Bei `an_mich`: der Absender (Name, sonst Adresse), damit der Satz sagen kann, wer zugesagt hat."""
    kreis: str = ''
    """Bei der Akte einer Person: ihr bestätigter Kreis (`kreis.py`), sonst leer."""

    def to_dict(self) -> dict[str, Any]:
        return {'datum': self.datum.isoformat(), 'text': self.text, 'ausdruck': self.ausdruck,
                'episode_id': self.episode_id, 'titel': self.titel, 'quelle_datum': self.quelle_datum,
                'quelle_art': self.quelle_art, 'art': self.art, 'richtung': self.richtung, 'status': self.status,
                'tage': self.tage, 'sache': self.sache, 'sache_name': self.sache_name,
                'vermutlich': self.vermutlich, 'andere': self.andere, 'kreis': self.kreis, 'satz': beschreibung(self)}


_QUELLE_ART = {'message': 'Mail', 'document': 'Notiz', 'event': 'Termin'}


def quelle_art(art: str | None) -> str:
    return _QUELLE_ART.get(art or '', '')


def richtung(participants: Iterable[str], eigene: Iterable[str]) -> str:
    """Von wem stammt die Quelle? Bei Mail steht der Absender zuerst; ohne Teilnehmer bleibt es unklar."""
    beteiligte = list(participants or ())
    if not beteiligte:
        return 'unklar'
    absender = mail_address(beteiligte[0])
    selbst = {mail_address(a) for a in eigene if mail_address(a)}
    if not absender:
        return 'unklar'
    return 'von_mir' if absender in selbst else 'an_mich'


def _lokal(wert: Any) -> str | None:
    try:
        moment = datetime.fromisoformat(str(wert))
    except ValueError:
        return None
    zone = user_timezone()
    return (moment.astimezone(zone) if zone and moment.tzinfo else moment).isoformat()


def wann(f: Frist) -> str:
    """„heute“, „morgen“, „in 3 Tagen“, „seit gestern“, „seit 5 Tagen“."""
    if f.tage == 0:
        return 'heute'
    if f.tage == 1:
        return 'morgen'
    if f.tage > 1:
        return f'in {f.tage} Tagen'
    if f.tage == -1:
        return 'seit gestern'
    return f'seit {-f.tage} Tagen'


def _tag(datum: date) -> str:
    return tag_und_monat(datum)


def beschreibung(f: Frist) -> str:
    """Ein Satz für die Anzeige, mit Vorsicht dort, wo die Akte nur vermutet."""
    tag = _tag(f.datum)
    wer = f.andere or 'Die Gegenseite'
    if f.status == 'verstrichen':
        seit = wann(f)
        if f.richtung == 'von_mir' and f.art == 'Zusage':
            return f'Du hattest bis {tag} zugesagt, {seit} vermutlich noch offen.'
        if f.richtung == 'an_mich' and f.art == 'Zusage':
            return f'{wer} hatte bis {tag} zugesagt, {seit} vermutlich noch offen.'
        if f.richtung == 'an_mich' and f.art == 'Bitte':
            return f'{wer} bat um etwas bis {tag}, {seit} vermutlich noch offen.'
        return f'Frist am {tag}, {seit} verstrichen, vermutlich noch offen.'
    if f.richtung == 'von_mir' and f.art == 'Zusage':
        return f'Du hast bis {tag} zugesagt, das ist {wann(f)}.'
    if f.richtung == 'an_mich' and f.art == 'Zusage':
        return f'{wer} hat bis {tag} zugesagt, das ist {wann(f)}.'
    if f.richtung == 'an_mich' and f.art == 'Bitte':
        return f'{wer} bittet um etwas bis {tag}, das ist {wann(f)}.'
    return f'Frist am {tag}, das ist {wann(f)}.'


def aus_akte(akte: dict[str, Any] | None, *, heute: date, eigene: Iterable[str] = (),
             tage_voraus: int = TAGE_VORAUS, tage_zurueck: int = TAGE_ZURUECK,
             quellenart: Callable[[str], str] = lambda episode_id: '') -> list[Frist]:
    """Fristen einer Akte im Fenster, kommende und verstrichene offene; nie eine überholte.

    `quellenart` liefert zur Episode `message`, `document` oder `event` (die Zeilen der Akte tragen sie
    nicht)."""
    if not akte:
        return []
    eigene = list(eigene)
    offen = {(e['episode_id'], e['text']) for e in akte['offen']['eintraege']}
    ergebnis: list[Frist] = []

    def bauen(f: dict[str, Any], status: str) -> Frist | None:
        if f.get('ersetzt_durch'):
            return None
        datum = date.fromisoformat(f['datum'])
        tage = (datum - heute).days
        if status == 'kommend' and not 0 <= tage <= tage_voraus:
            return None
        if status == 'verstrichen' and not (-tage_zurueck <= tage < 0 and (f['episode_id'], f['text']) in offen
                                            and f['art'] in ('Bitte', 'Zusage')):
            return None
        quelle = quelle_art(quellenart(f['episode_id']))
        sender = richtung(f.get('participants') or (), eigene)
        absender = (f.get('participants') or [''])[0]
        return Frist(datum=datum, text=' '.join((f.get('satz') or f['text']).split()),
                     ausdruck=(f.get('ausdruck') or '').rstrip('.'), episode_id=f['episode_id'],
                     titel=f['titel'], quelle_datum=_lokal(f.get('occurred_at') or f.get('recorded_at')),
                     quelle_art=quelle, art=f['art'], richtung=sender, status=status, tage=tage,
                     sache=akte['sache'], sache_name=akte['name'], vermutlich=status == 'verstrichen',
                     andere=(anzeigename(absender) or mail_address(absender)) if sender == 'an_mich' else '',
                     kreis=akte.get('kreis', '') if akte.get('art') == 'person' else '')

    for status in ('kommend', 'verstrichen'):
        for f in akte['fristen'][status]:
            frist = bauen(f, status)
            if frist is not None:
                ergebnis.append(frist)
    return ergebnis


def _rang(f: Frist) -> tuple:
    if f.status == 'kommend' and f.tage <= 1:
        return (0, f.tage, f.datum, f.episode_id)
    if f.status == 'verstrichen':
        return (1, -f.tage, f.datum, f.episode_id)
    return (2, f.tage, f.datum, f.episode_id)


def nach_dringlichkeit(fristen: Iterable[Frist]) -> list[Frist]:
    """Eine Frist je Quelle und Datum (dieselbe Quelle hängt an mehreren Akten), dringendste zuerst."""
    einzeln: dict[tuple, Frist] = {}
    for f in fristen:
        # Die persönlichste Akte gibt den Namen (Person vor Projekt und Organisation), je nach Kreis (`kreis.py`):
        # Kollegen sachlich, also hinter Projekt und Organisation; ein bestätigter Kontakt nur, wenn nichts anderes da ist.
        schluessel = (f.episode_id, f.datum, f.text)
        alt = einzeln.get(schluessel)
        if alt is None or _akte_rang(f) < _akte_rang(alt):
            einzeln[schluessel] = f
    return sorted(einzeln.values(), key=_rang)


def _akte_rang(f: Frist) -> int:
    """0: Person (innerer Kreis oder noch offen), 1: Projekt, Organisation, Ort, 2: Kollegen, 3: Kontakte."""
    if not f.sache.startswith('person:'):
        return 1
    return {'kollegen': 2, 'kontakte': 3}.get(f.kreis, 0)


def ohne_kontakte(fristen: Iterable[Frist]) -> list[Frist]:
    """Das Briefing nennt nichts ungefragt aus der Akte eines bestätigten Kontakts (`kreis.ungefragt_erlaubt`).

    Hängt dieselbe Quelle auch an einem Projekt oder einer Organisation, bleibt die Frist über diese Akte im
    Briefing (direkter Bezug); nur was allein in der Akte des Kontakts steht, fehlt.
    """
    from .kreis import ungefragt_erlaubt
    return [f for f in fristen if ungefragt_erlaubt(f.kreis)]


def sammeln(akten: Any, bezuege: Any, *, jetzt: datetime, eigene: Iterable[str] = (),
            arten: tuple[str, ...] = ('person', 'organisation', 'projekt'), je_art: int = 60) -> list[Frist]:
    """Fristen aus den zuletzt aktiven Akten (Zwischenspeicher der Akte; kalt einige Millisekunden je Akte)."""
    heute = jetzt.date()
    eigene = list(eigene)
    alle: list[Frist] = []
    arten_der_quellen: dict[str, str] = {}

    def quellenart(episode_id: str) -> str:
        if episode_id not in arten_der_quellen:
            try:
                arten_der_quellen[episode_id] = akten.episodes.get(episode_id).kind.value
            except Exception:  # noqa: BLE001 - die Art ist Beiwerk; ohne sie fehlt nur das Wort „Mail“
                arten_der_quellen[episode_id] = ''
        return arten_der_quellen[episode_id]

    for art in arten:
        for eintrag in bezuege.sachen(art=art, limit=je_art)['sachen']:
            akte = akten.akte(eintrag['sache'], jetzt=jetzt, alle=True)
            alle.extend(aus_akte(akte, heute=heute, eigene=eigene, quellenart=quellenart))
    # Ungefragt (Briefing): nichts allein aus der Akte eines bestätigten Kontakts.
    return nach_dringlichkeit(ohne_kontakte(alle))


__all__ = ['Frist', 'TAGE_VORAUS', 'aus_akte', 'beschreibung', 'nach_dringlichkeit', 'ohne_kontakte', 'richtung', 'sammeln',
           'wann']
