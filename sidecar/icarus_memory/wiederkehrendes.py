"""Geburtstage und Wiederkehrendes (M4): als Vorschläge mit Beleg, Fakt erst nach Annahme.

Der eine Ort für zwei Dinge, die ein Mensch sonst im Kopf behält:

* **Geburtstage** der Menschen im inneren Kreis (`kreis.py`). Woher Kingfisher sie kennt, ohne Modell:
  - der eigene Glückwunsch: eine Mail des Nutzers an genau diese Person mit „Alles Gute zum Geburtstag“ (das Datum der
    Mail ist der Tag; „nachträglich“ oder „vorab“ zählt nicht),
  - die Person selbst: „Mein Geburtstag ist am 18. Dezember“, „ich habe am 3. Oktober Geburtstag“ (Tag und Monat
    ausgeschrieben, nur im eigenen Text der Mail, nicht im Zitat),
  - der Kalender: ein Termin „Carlas Geburtstag“, „Geburtstag Gabi“, „Geburtstag: Felix“; der Name muss genau eine
    Person mit Adresse treffen (Vorname oder Anfang der Adresse).
  Vorgeschlagen wird nur für Personen, deren Kreis bestätigt „innerer Kreis“ ist oder ohne Bestätigung so vorgeschlagen
  wird, nie für Kollegen und Kontakte. Ins Briefing („Morgen hat Gabriele Geburtstag.“) kommt ein Geburtstag erst, wenn
  der Kreis bestätigt **und** der Geburtstag angenommen ist (`im_briefing`).
* **Wiederkehrendes** aus Akten mit privater Art (`akten_arten.py`): monatliche Abschläge und Beiträge, die jährliche
  Verlängerung eines Vertrags, Müllabfuhr, Elternabend, und Serien im Kalender (derselbe Titel mindestens dreimal im
  selben Abstand). Je Satz mit einem Rhythmus („monatlich“, „alle zwei Wochen“, „jeden ersten Dienstag im Monat“)
  **und** einem Gegenstand (Abschlag, Tonne, Elternabend); fehlt eins von beiden, ist es nichts.

Regeln (`docs/10-verdichtung.md`, `docs/49-kreis-und-privat.md`):

1. **Vorschlag, nie Fakt.** Alles geht als Wissenskandidat (`KnowledgeService.propose`, Art `knowledge`) mit
   wörtlicher Textstelle und Fingerabdruck der Quelle in die Prüfung. Erst die Annahme legt eine Aussage an
   (Beziehung `geburtstag` bzw. `wiederkehrend`).
2. **Jede Zahl belegt.** Ein Betrag oder Rhythmus mit Zahl steht wörtlich in der Quelle; der Tag eines Geburtstags
   steht im Satz, im Termin oder ist der Tag der Glückwunschmail (dann sagt die Begründung das).
3. **Was einmal vorgeschlagen war, kommt nicht wieder**, auch nicht nach einer Ablehnung.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from .datumstext import MONAT_NUMMER, MONATE

PRAEDIKAT_GEBURTSTAG = 'geburtstag'
PRAEDIKAT_WIEDERKEHREND = 'wiederkehrend'
VON_GEBURTSTAG = 'geburtstag:'
VON_WIEDERKEHREND = 'wiederkehrend:'
#: So viele Quellen je Person oder Akte werden gelesen (jüngste zuerst).
QUELLEN_JE_SACHE = 60

# -- Geburtstage: Regeln ohne Modell ---------------------------------------------------------------

_GLUECKWUNSCH = re.compile(r'(?:alles\s+(?:gute|liebe)|herzlichen\s+glückwunsch|herzliche\s+glückwünsche|'
                           r'happy\s+birthday)(?:\s+(?:und\s+alles\s+liebe\s+)?zum\s+(?:\d{1,3}\.\s+)?geburtstag)?',
                           re.I)
#: Ein Glückwunsch, der nicht am Tag kam: Dann ist das Datum der Mail nicht der Geburtstag.
_NICHT_AM_TAG = re.compile(r'nachträglich|nachtraeglich|verspätet|verspaetet|vorab|im voraus|schon mal|schonmal|'
                           r'morgen|gestern|vorgestern|übermorgen|letzte woche|nächste woche', re.I)
_EIGENER = re.compile(r'(?<![\wäöüß])(?:mein(?:em|en)?\s+geburtstag|ich\s+(?:habe|hab|werde)\b[^!?\n]{0,60}?geburtstag|'
                      r'geburtstag\s+(?:habe|hab)\s+ich)', re.I)
#: Der Geburtstag eines anderen („Papas Geburtstag“, „deinen Geburtstag“): nicht der des Schreibenden.
_FREMDER = re.compile(r'(?<![\wäöüß])(?:(?i:dein|sein|ihr|eur|unser)\w*|(?!Mein)[A-ZÄÖÜ]\w+s)\s+(?i:geburtstag)')
_TAG_MONAT = re.compile(r'(?<![\d.])(\d{1,2})\.\s?(?:(\d{1,2})\.(?!\d)|(' + '|'.join(sorted(MONAT_NUMMER, key=len, reverse=True))
                        + r')\b)', re.I)
#: Termine „Carlas Geburtstag“, „Geburtstag Gabi“, „Geburtstag: Felix“, „Geburtstag von Carla“. Nur der Name, sonst nichts:
#: „Papas Geburtstag im Garten“ ist ein Fest, kein Eintrag.
_TERMIN = re.compile(r'^\s*(?:(?P<vorn>[A-ZÄÖÜ][\wäöüß-]{1,30}?)(?:s|\'s|’s)?\s+geburtstag'
                     r'|geburtstag(?:\s*[:\-–]\s*|\s+von\s+|\s+)(?P<hinten>[A-ZÄÖÜ][\wäöüß-]{1,30}))\s*[!.]?\s*$', re.I)
_ZITAT = re.compile(r'^(?:>|Am .{4,80} schrieb|-{3,}\s*(?:Ursprüngliche|Original)|Von:\s)', re.M)


def eigener_text(text: str) -> str:
    """Der Text einer Mail ohne zitierte frühere Mail."""
    return _ZITAT.split(text, maxsplit=1)[0]


def _saetze(text: str) -> list[str]:
    """Sätze wie bei den Fristen: „18. Dezember“, „Dr. Krämer“ und „03.10.“ beenden keinen Satz."""
    from .akten_arten import _saetze as saetze
    return saetze(text)


@dataclass(frozen=True)
class GeburtstagFund:
    monat: int
    tag: int
    satz: str
    """Die wörtliche Stelle (Beleg)."""
    herkunft: str
    """`glueckwunsch`, `eigene_angabe` oder `kalender`."""

    @property
    def wert(self) -> str:
        return f'{self.monat:02d}-{self.tag:02d}'


def _gueltig(monat: int, tag: int) -> bool:
    try:
        date(2024, monat, tag)  # Schaltjahr: der 29. Februar ist ein Geburtstag
    except ValueError:
        return False
    return True


def tag_und_monat_aus(satz: str) -> tuple[int, int] | None:
    """(Monat, Tag) aus einem ausgeschriebenen Datum im Satz („18. Dezember“, „03.10.“), sonst None."""
    treffer = _TAG_MONAT.search(satz)
    if not treffer:
        return None
    tag = int(treffer[1])
    monat = int(treffer[2]) if treffer[2] else MONAT_NUMMER[treffer[3].lower()]
    return (monat, tag) if _gueltig(monat, tag) else None


def aus_glueckwunsch(text: str, gesendet: datetime) -> GeburtstagFund | None:
    """Ein Glückwunsch des Nutzers am Tag selbst: der Tag der Mail ist der Geburtstag. Rein."""
    saetze = _saetze(eigener_text(text))
    for nummer, satz in enumerate(saetze[:6]):
        glueckwunsch = _GLUECKWUNSCH.search(satz)
        if not glueckwunsch or ('geburtstag' not in satz.casefold() and 'birthday' not in satz.casefold()):
            continue
        # Der Satz und seine Nachbarn: „Alles Gute nachträglich“, „Hattest du gestern einen schönen Tag?“
        if any(_NICHT_AM_TAG.search(s) for s in saetze[max(0, nummer - 1):nummer + 2]):
            return None
        return GeburtstagFund(gesendet.month, gesendet.day, satz, 'glueckwunsch')
    return None


def aus_eigener_angabe(text: str) -> GeburtstagFund | None:
    """„Mein Geburtstag ist am 18. Dezember“ in einer Mail der Person selbst. Rein."""
    for satz in _saetze(eigener_text(text)):
        if _FREMDER.search(satz):
            continue
        if _EIGENER.search(satz) and (tag := tag_und_monat_aus(satz)):
            return GeburtstagFund(tag[0], tag[1], satz, 'eigene_angabe')
    return None


def name_aus_termin(titel: str) -> str:
    """Der Name in „Carlas Geburtstag“, „Geburtstag: Felix“, sonst leer. Rein."""
    treffer = _TERMIN.match(titel or '')
    if not treffer:
        return ''
    return (treffer['vorn'] or treffer['hinten'] or '').strip()


def _schluessel(text: str) -> str:
    from .akten_arten import normal
    return normal(text).strip()


def namensschluessel(name: str, adresse: str) -> set[str]:
    """Wie man eine Person im Kalender nennt: der Vorname und der Anfang der Adresse („gabi“ aus gabi.hartmann@…)."""
    schluessel = set()
    if name.strip():
        schluessel.add(_schluessel(name.split()[0]))
    lokal = adresse.split('@', 1)[0]
    if lokal:
        schluessel.add(_schluessel(re.split(r'[._+-]', lokal)[0]))
    return {s for s in schluessel if len(s) >= 2}


def kandidaten_fuer_namen(name: str, verzeichnis: dict[str, set[str]]) -> list[str]:
    """Personen, deren Schlüssel den Namen treffen („Carlas“ trifft „carla“). `verzeichnis`: Sache -> Schlüssel."""
    roh = _schluessel(name)
    formen = {roh, roh[:-1] if roh.endswith('s') and len(roh) > 3 else roh}
    return sorted(s for s, schluessel in verzeichnis.items() if formen & schluessel)


def naechster_geburtstag(wert: str, heute: date) -> date | None:
    """Der nächste Geburtstag ab heute (einschließlich) zu `MM-TT`; der 29. Februar im Gemeinjahr am 28."""
    try:
        monat, tag = (int(t) for t in wert.split('-')[-2:])
    except ValueError:
        return None
    for jahr in (heute.year, heute.year + 1):
        try:
            kandidat = date(jahr, monat, tag)
        except ValueError:
            kandidat = date(jahr, monat, 28) if (monat, tag) == (2, 29) else None
        if kandidat is not None and kandidat >= heute:
            return kandidat
    return None


def geburtstag_text(wert: str) -> str:
    monat, tag = (int(t) for t in wert.split('-')[-2:])
    return f'{tag}. {MONATE[monat - 1]}'


# -- Wiederkehrendes: Regeln ohne Modell -----------------------------------------------------------

_WOCHENTAG = r'(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)'
_RHYTHMEN = (
    ('alle zwei Wochen', r'alle\s+(?:zwei|2)\s+wochen|alle\s+14\s+tage|14-?tägig\w*|vierzehntägig\w*|zweiwöchentlich\w*'),
    ('wöchentlich', r'wöchentlich\w*|jede\s+woche|jeden\s+' + _WOCHENTAG + r'(?!\s+im\s+monat)|immer\s+' + _WOCHENTAG + r's\b'),
    ('monatlich', r'monatlich\w*|jeden\s+monat|jeden\s+(?:ersten|zweiten|dritten|vierten|letzten)\s+' + _WOCHENTAG
     + r'\s+im\s+monat|zum\s+\d{1,2}\.\s+(?:eines|jedes|des)\s+monats|jeweils\s+zum\s+\d{1,2}\.'),
    ('vierteljährlich', r'vierteljährlich\w*|quartalsweise|jedes\s+quartal'),
    ('jährlich', r'jährlich\w*|jaehrlich\w*|jedes\s+jahr|verlängert\s+sich\s+(?:jeweils\s+|automatisch\s+)?um\s+'
     r'(?:ein\s+(?:weiteres\s+)?jahr|zwölf\s+monate|12\s+monate)'),
)
_RHYTHMUS = [(name, re.compile(r'(?<![\wäöüß])(?:' + muster + r')', re.I)) for name, muster in _RHYTHMEN]
_GEGENSTAENDE = (
    ('zahlung', r'abschlag\w*|\w*beitrag\w*|lastschrift\w*|abbuchung\w*|abgebucht|rate\b|raten\b|miete\b|gebühr\w*|'
                r'abo\b|abonnement\w*'),
    ('muell', r'müllabfuhr|abfuhr\w*|\w*tonne\w*|restmüll\w*|biomüll\w*|altpapier\w*|gelbe[rn]?\s+sack|wertstoff\w*'),
    ('termin', r'elternabend\w*|elternsprechtag\w*|sprechstunde\w*|training\w*|chorprobe\w*|probe\b|stammtisch\w*|'
               r'kurs\b|treffen\b'),
    ('vertrag', r'vertrag\w*|mitgliedschaft\w*|abonnement\w*'),
)
_GEGENSTAND = [(art, re.compile(r'(?<![\wäöüß])(?:' + muster + r')', re.I)) for art, muster in _GEGENSTAENDE]
_BETRAG = re.compile(r'(?<![\d,.])\d{1,3}(?:\.\d{3})*,\d{2}\s?(?:€|EUR\b|Euro\b)')
#: Erledigtes oder Abgeschlossenes wiederholt sich nicht mehr.
_ENDE = re.compile(r'(?:wurde|wurden|ist|sind|haben|hat)\s+(?:\w+\s+){0,3}(?:gekündigt|gekuendigt|eingestellt|beendet)|'
                   r'kündigungsbestätigung|letztmalig|zum letzten mal|entfällt|endet am', re.I)
ART_TEXT = {'zahlung': 'Zahlung', 'muell': 'Müllabfuhr', 'termin': 'Termin', 'vertrag': 'Vertrag'}


@dataclass(frozen=True)
class Wiederkehr:
    """Etwas, das sich wiederholt, mit wörtlichem Beleg. `was`, `rhythmus_wortlaut` und `betrag` stehen so im Satz."""

    art: str
    rhythmus: str
    rhythmus_wortlaut: str
    was: str
    satz: str
    betrag: str = ''

    def aussage(self, wer: str = '') -> str:
        """Der Satz des Vorschlags. Jede Zahl darin steht im Beleg (Rhythmus und Betrag wörtlich)."""
        von = f' ({wer})' if wer else ''
        zahl = re.search(r'\d', self.rhythmus_wortlaut)
        rhythmus = self.rhythmus_wortlaut if zahl else self.rhythmus
        teile = [f'{rhythmus[:1].upper()}{rhythmus[1:]}: {self.was}']
        if self.betrag:
            teile.append(self.betrag)
        return ', '.join(teile) + von


def wiederkehrendes_finden(text: str) -> list[Wiederkehr]:
    """Je Satz mit Rhythmus und Gegenstand eine Wiederkehr. Rein, ohne Modell.

    Die jährliche Verlängerung eines Vertrags zählt nur mit dem Wort „kündig…“ im selben Satz (sonst ist „jährlich“
    in einer Vertragsmail meist ein Betrag). Kündigungsfristen mit Datum bleiben Sache von `akten_arten.fristen_finden`.
    """
    ergebnis: list[Wiederkehr] = []
    for satz in _saetze(text):
        if _ENDE.search(satz):
            continue
        rhythmus = next(((name, t) for name, muster in _RHYTHMUS if (t := muster.search(satz))), None)
        if rhythmus is None:
            continue
        gegenstand = next(((art, t) for art, muster in _GEGENSTAND if (t := muster.search(satz))), None)
        if gegenstand is None:
            continue
        art, treffer = gegenstand
        if art == 'vertrag' and not re.search(r'kündig|kuendig', satz, re.I):
            continue
        betrag = _BETRAG.search(satz) if art in ('zahlung', 'vertrag') else None
        wiederkehr = Wiederkehr(art, rhythmus[0], rhythmus[1].group(0), treffer.group(0), satz,
                                betrag.group(0) if betrag else '')
        if all((w.art, w.rhythmus, w.was.casefold()) != (art, rhythmus[0], treffer.group(0).casefold()) for w in ergebnis):
            ergebnis.append(wiederkehr)
    return ergebnis


def serie_finden(termine: Iterable[tuple[str, datetime]], *, mindestens: int = 3) -> str:
    """Der Rhythmus einer Serie gleichnamiger Termine (`wöchentlich`, `alle zwei Wochen`, `monatlich`), sonst leer.

    Mindestens `mindestens` Termine, und alle Abstände gleich: 7 oder 14 Tage, oder derselbe Tag im Monat in
    aufeinanderfolgenden Monaten. Rein.
    """
    tage = sorted({zeit.date() for _, zeit in termine})
    if len(tage) < mindestens:
        return ''
    abstaende = {(b - a).days for a, b in zip(tage, tage[1:])}
    if abstaende == {7}:
        return 'wöchentlich'
    if abstaende == {14}:
        return 'alle zwei Wochen'
    monate = [t.year * 12 + t.month for t in tage]
    if len({t.day for t in tage}) == 1 and all(b - a == 1 for a, b in zip(monate, monate[1:])):
        return 'monatlich'
    return ''


# -- Vorschläge anlegen ----------------------------------------------------------------------------


@dataclass
class Lauf:
    personen: int = 0
    akten: int = 0
    quellen: int = 0
    vorgeschlagen: int = 0
    vorhanden: int = 0
    vorschlaege: list[dict[str, Any]] = field(default_factory=list)


def _schon(proposals: Any, von: str) -> bool:
    try:
        return bool(proposals.von(von, limit=1))
    except Exception:  # noqa: BLE001
        return False


def _vorschlagen(knowledge: Any, proposals: Any, lauf: Lauf, *, episode: Any, satz: str, subjekt: str, praedikat: str,
                 wert: str, aussage: str, begruendung: str, von: str, art: str) -> None:
    from .proposals import Evidence
    if satz not in episode.body or _schon(proposals, von):
        lauf.vorhanden += 1
        return
    vorschlag, neu = knowledge.propose(
        subject_ref=subjekt, predicate=praedikat, value=wert, statement=aussage, rationale=begruendung,
        evidence=[Evidence(episode.id, satz, episode.digest)], proposed_by=von)
    if neu:
        lauf.vorgeschlagen += 1
        lauf.vorschlaege.append({'id': vorschlag.id, 'sache': subjekt, 'art': art, 'wert': wert,
                                 'episode_id': episode.id})
    else:
        lauf.vorhanden += 1


#: So viele Sachen je Abfrage der Namen: SQLite verträgt keine beliebig langen Ausdrücke (mit 10.000 Quellen sind es
#: Tausende Personen).
NAMEN_JE_ABFRAGE = 200


def namen_in_teilen(beschriftungen: Any, sachen: list[str]) -> dict[str, str]:
    """`bezuege.beschriftungen` in Teilen von `NAMEN_JE_ABFRAGE`."""
    ergebnis: dict[str, str] = {}
    for start in range(0, len(sachen), NAMEN_JE_ABFRAGE):
        ergebnis.update(beschriftungen(sachen[start:start + NAMEN_JE_ABFRAGE]))
    return ergebnis


def _lokaler_tag(zeit: datetime) -> datetime:
    from .model import user_timezone
    zone = user_timezone()
    return zeit.astimezone(zone) if zone and zeit.tzinfo else zeit


def _bekannt(claims: Any, sache: str, praedikat: str) -> bool:
    try:
        return any(c.predicate == praedikat for c in claims.by_subject(sache))
    except Exception:  # noqa: BLE001
        return False


def geburtstage_vorlegen(bezuege: Any, knowledge: Any, proposals: Any, claims: Any, eigene: Iterable[str] = (),
                         *, lauf: Lauf | None = None) -> Lauf:
    """Geburtstagsvorschläge für Personen im inneren Kreis (bestätigt oder vorgeschlagen), nie für andere."""
    from .kreis import INNERER_KREIS, Kreise, _zeilen
    lauf = lauf or Lauf()
    kreise = Kreise(bezuege, eigene)
    fest = kreise.alle()
    vorschlaege = kreise.vorschlaege()
    innen = sorted(s for s in set(vorschlaege) | set(fest)
                   if fest.get(s, vorschlaege[s].kreis if s in vorschlaege else '') == INNERER_KREIS)
    namen = namen_in_teilen(bezuege.beschriftungen, innen)
    for sache in innen:
        if _bekannt(claims, sache, PRAEDIKAT_GEBURTSTAG):
            continue
        lauf.personen += 1
        name = namen.get(sache, sache)
        zeilen = sorted(_zeilen(bezuege, sache), key=lambda z: str(z['zeit'] or ''), reverse=True)[:QUELLEN_JE_SACHE]
        for z in zeilen:
            if z['kind'] != 'message':
                continue
            try:
                episode = bezuege.episodes.get(z['id'])
            except Exception:  # noqa: BLE001
                continue
            lauf.quellen += 1
            fund, wie = None, ''
            if z['rolle'] == 'an' and z['ich'] and _einziger_empfaenger(episode, sache) and episode.occurred_at:
                fund = aus_glueckwunsch(episode.body, _lokaler_tag(episode.occurred_at))
                wie = (f'Dein Glückwunsch vom {_lokaler_tag(episode.occurred_at):%d.%m.%Y} an {name}; '
                       'der Tag der Mail ist der Geburtstag.')
            elif z['rolle'] == 'von':
                fund = aus_eigener_angabe(episode.body)
                wie = f'{name} schreibt es selbst.'
            if fund is None:
                continue
            _vorschlagen(knowledge, proposals, lauf, episode=episode, satz=fund.satz, subjekt=sache,
                         praedikat=PRAEDIKAT_GEBURTSTAG, wert=fund.wert,
                         aussage=f'{name} hat am {geburtstag_text(fund.wert)} Geburtstag.',
                         begruendung=f'{wie} Erst deine Bestätigung macht daraus Wissen; im Briefing steht der '
                                     'Geburtstag nur, wenn die Person bestätigt im inneren Kreis ist.',
                         von=VON_GEBURTSTAG + episode.id, art='geburtstag')
            break
    _geburtstage_aus_kalender(bezuege, knowledge, proposals, claims, set(innen), lauf)
    return lauf


def _einziger_empfaenger(episode: Any, sache: str) -> bool:
    """Ist die Person der einzige fremde Empfänger in „An“? Ein Glückwunsch an viele sagt nichts über eine."""
    from .identitaet import nennungen
    an = {n.adresse for n in nennungen(episode) if n.rolle == 'an' and n.adresse and not n.ich}
    return an == {sache[len('person:a:'):]}


def _geburtstage_aus_kalender(bezuege: Any, knowledge: Any, proposals: Any, claims: Any, innen: set[str],
                              lauf: Lauf) -> None:
    """Termine „Carlas Geburtstag“: der Name muss genau eine Person mit Adresse treffen, und die muss innen sein."""
    titel = _termine(bezuege.episodes)
    geburtstage = [(t, name_aus_termin(t[1])) for t in titel]
    geburtstage = [(t, n) for t, n in geburtstage if n]
    if not geburtstage:
        return
    alle = sorted(_personen_mit_adresse(bezuege.episodes))
    beschriftung = namen_in_teilen(bezuege.beschriftungen, alle)
    verzeichnis = {s: namensschluessel(beschriftung.get(s, ''), s[len('person:a:'):]) for s in alle}
    for (episode_id, titel_text, beginn), name in geburtstage:
        treffer = kandidaten_fuer_namen(name, verzeichnis)
        if len(treffer) != 1 or treffer[0] not in innen or _bekannt(claims, treffer[0], PRAEDIKAT_GEBURTSTAG):
            continue
        sache = treffer[0]
        try:
            episode = bezuege.episodes.get(episode_id)
        except Exception:  # noqa: BLE001
            continue
        # Der Tag steht in der Zeile „Wann:“ des Termins; ein ganztägiger Termin wird nie in eine Zone umgerechnet.
        satz = next((z for z in episode.body.splitlines() if z.startswith('Wann:')), '')
        tag = tag_und_monat_aus(satz) if satz else None
        if tag is None:
            continue
        lauf.quellen += 1
        wert = f'{tag[0]:02d}-{tag[1]:02d}'
        person = beschriftung.get(sache, sache)
        _vorschlagen(knowledge, proposals, lauf, episode=episode, satz=satz, subjekt=sache,
                     praedikat=PRAEDIKAT_GEBURTSTAG, wert=wert,
                     aussage=f'{person} hat am {geburtstag_text(wert)} Geburtstag.',
                     begruendung=f'Termin „{titel_text}“ in deinem Kalender; „{name}“ passt nur zu {person}. Erst '
                                 'deine Bestätigung macht daraus Wissen.',
                     von=VON_GEBURTSTAG + episode.id, art='geburtstag')


def _termine(episodes: Any) -> list[tuple[str, str, datetime]]:
    """(Episode, Titel, Beginn) aller Termine im Bestand."""
    from .datumstext import iso_versuchen
    from .episodes import sql_aktuell
    with episodes._lock:
        zeilen = episodes._conn.execute(
            "SELECT id, title, occurred_at FROM episodes WHERE kind = 'event' AND " + sql_aktuell('episodes')).fetchall()
    ergebnis = []
    for z in zeilen:
        beginn = iso_versuchen(z['occurred_at'])
        if beginn is not None:
            ergebnis.append((z['id'], str(z['title'] or ''), beginn))
    return ergebnis


def _personen_mit_adresse(episodes: Any) -> set[str]:
    with episodes._lock:
        return {z[0] for z in episodes._conn.execute(
            "SELECT DISTINCT sache FROM sach_bezuege WHERE sache LIKE 'person:a:%' AND grundlage = 'anker'")}


def wiederkehrendes_vorlegen(bezuege: Any, knowledge: Any, proposals: Any, *, max_akten: int = 2000,
                             lauf: Lauf | None = None) -> Lauf:
    """Vorschläge für Wiederkehrendes aus Akten mit privater Art und aus Serien im Kalender."""
    from .akten_arten import name_der_akte, private_art, private_kandidaten
    from .akten_arten import zahlen_belegt
    from .bezuege import sache_id
    lauf = lauf or Lauf()
    for sache in private_kandidaten(bezuege)[:max_akten]:
        quellen = bezuege.quellen_von(sache)
        if not private_art(bezuege, sache, quellen):
            continue
        lauf.akten += 1
        wer = name_der_akte(bezuege, sache, quellen)
        for quelle in quellen[:QUELLEN_JE_SACHE]:
            if quelle.get('art') not in ('message', 'document'):
                continue
            try:
                episode = bezuege.episodes.get(quelle['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            lauf.quellen += 1
            for nummer, w in enumerate(wiederkehrendes_finden(eigener_text(episode.body))):
                if zahlen_belegt(w.aussage(''), episode.body):
                    continue
                _vorschlagen(knowledge, proposals, lauf, episode=episode, satz=w.satz, subjekt=sache,
                             praedikat=PRAEDIKAT_WIEDERKEHREND, wert=w.aussage(''), aussage=w.aussage(wer),
                             begruendung=f'Aus einer Quelle der Akte „{wer}“: Rhythmus „{w.rhythmus_wortlaut}“ und '
                                         f'„{w.was}“ stehen so im Satz. Erst deine Bestätigung macht daraus Wissen.',
                             von=f'{VON_WIEDERKEHREND}{episode.id}:{nummer}', art=w.art)
    # Serien im Kalender: derselbe Titel mindestens dreimal im gleichen Abstand.
    serien: dict[str, list[tuple[str, str, datetime]]] = {}
    for episode_id, titel, beginn in _termine(bezuege.episodes):
        if titel.strip() and not name_aus_termin(titel):
            serien.setdefault(' '.join(titel.casefold().split()), []).append((episode_id, titel, beginn))
    for schluessel, termine in sorted(serien.items()):
        rhythmus = serie_finden((t[1], _lokaler_tag(t[2])) for t in termine)
        if not rhythmus:
            continue
        juengster = max(termine, key=lambda t: t[2])
        try:
            episode = bezuege.episodes.get(juengster[0])
        except Exception:  # noqa: BLE001
            continue
        satz = next((z for z in episode.body.splitlines() if z.startswith('Termin:')), '')
        if not satz:
            continue
        lauf.quellen += 1
        titel = juengster[1].strip()
        _vorschlagen(knowledge, proposals, lauf, episode=episode, satz=satz,
                     subjekt=sache_id('thema', schluessel[:120]), praedikat=PRAEDIKAT_WIEDERKEHREND,
                     wert=f'{rhythmus}: {titel}', aussage=f'{rhythmus[:1].upper()}{rhythmus[1:]}: {titel} (Kalender)',
                     begruendung=f'{len(termine)} Termine „{titel}“ in deinem Kalender, immer im selben Abstand. Erst '
                                 'deine Bestätigung macht daraus Wissen.',
                     von=f'{VON_WIEDERKEHREND}serie:{schluessel[:120]}', art='termin')
    return lauf


# -- Lesen: was angenommen ist und was offen ---------------------------------------------------------


def stand(sache: str, proposals: Any, claims: Any) -> dict[str, Any]:
    """Für die Karte in der Akte: offene Vorschläge und angenommene Aussagen zu Geburtstag und Wiederkehrendem."""
    from .proposals import ProposalKind
    offen = [p for p in proposals.pending(ProposalKind.KNOWLEDGE, limit=2000)
             if p.subject_ref == sache and p.predicate in (PRAEDIKAT_GEBURTSTAG, PRAEDIKAT_WIEDERKEHREND)
             and str(p.proposed_by).startswith((VON_GEBURTSTAG, VON_WIEDERKEHREND))]
    try:
        fest = [c for c in claims.by_subject(sache) if c.predicate in (PRAEDIKAT_GEBURTSTAG, PRAEDIKAT_WIEDERKEHREND)]
    except Exception:  # noqa: BLE001
        fest = []

    def eintrag(art: str, objekt: Any) -> dict[str, Any]:
        beleg = objekt.evidence[0] if objekt.evidence else None
        return {'id': objekt.id, 'art': art, 'praedikat': objekt.predicate, 'wert': objekt.value,
                'aussage': objekt.statement, 'begruendung': getattr(objekt, 'rationale', ''),
                'beleg': {'episode_id': beleg.episode_id, 'zitat': beleg.quote} if beleg else None}

    return {'sache': sache, 'offen': [eintrag('vorschlag', p) for p in offen],
            'angenommen': [eintrag('aussage', c) for c in fest]}


def vorname(name: str) -> str:
    teile = [t for t in name.split() if not t.endswith('.')]
    return teile[0] if teile else name


# -- Bestätigte Geburtstage, gleich woher (Fremdprobe 2, Befund 20) ---------------------------------------------------
#
# Ein Geburtstag ist bestätigt, wenn ein Mensch die Aussage angenommen hat: aus dem Vorschlag oben (Beziehung
# `geburtstag`, Wert `MM-TT`, Subjekt die Sache `person:a:…`) oder aus „Merke dir: Anna hat am 12. Oktober Geburtstag“
# im Gespräch (Subjekt die Personenkennung des Gedächtnisses, Wert „12. Oktober“). Beides zählt; ohne Annahme nichts.

#: Beziehungen, die einen Geburtstag tragen.
PRAEDIKATE_GEBURTSTAG = (PRAEDIKAT_GEBURTSTAG, 'birthday', 'geburtsdatum')
_MONAT_TAG = re.compile(r'^(?:\d{4}-)?(\d{2})-(\d{2})$')


def geburtstag_wert(aussage: Any) -> str | None:
    """`MM-TT` einer angenommenen Geburtstagsaussage, aus dem Wert („10-12“, „12. Oktober“, „12.10.“) oder dem Satz."""
    if str(getattr(aussage, 'predicate', '')).casefold() not in PRAEDIKATE_GEBURTSTAG:
        return None
    wert = str(getattr(aussage, 'value', '') or '').strip()
    treffer = _MONAT_TAG.match(wert)
    if treffer and _gueltig(int(treffer[1]), int(treffer[2])):
        return f'{treffer[1]}-{treffer[2]}'
    for text in (wert, str(getattr(aussage, 'statement', '') or '')):
        gefunden = tag_und_monat_aus(text)
        if gefunden:
            return f'{gefunden[0]:02d}-{gefunden[1]:02d}'
    return None


def subjekte(sache: str) -> list[str]:
    """Unter welchen Subjekten Aussagen über diese Person stehen: die Sache selbst und ihre Personenkennung im Gedächtnis
    (`graph.person_id_fuer`), unter der Gesprächsvorschläge abgelegt werden."""
    art, _, kennung = sache.partition(':')
    if art != 'person' or not kennung.startswith(('a:', 'n:')):
        return [sache]
    from .graph import person_id_fuer
    return list(dict.fromkeys([sache, person_id_fuer(kennung)]))


def bestaetigter_geburtstag(claims: Any, sache: str) -> dict[str, Any] | None:
    """Der angenommene Geburtstag einer Person (`wert` `MM-TT`, Aussage, Beleg), sonst None."""
    for subjekt in subjekte(sache):
        try:
            aussagen = claims.by_subject(subjekt)
        except Exception:  # noqa: BLE001
            continue
        for aussage in aussagen:
            wert = geburtstag_wert(aussage)
            if wert:
                return {'wert': wert, 'aussage_id': aussage.id, 'aussage': aussage.statement, 'subjekt': subjekt,
                        'episode_id': aussage.evidence[0].episode_id if aussage.evidence else None}
    return None


def anstehend_text(wert: str, heute: date) -> str:
    """„Geburtstag am 12. Oktober, in 11 Tagen“ (heute, morgen, in N Tagen)."""
    tag = naechster_geburtstag(wert, heute)
    text = f'Geburtstag am {geburtstag_text(wert)}'
    if tag is None:
        return text
    tage = (tag - heute).days
    return f'{text}, {"heute" if tage == 0 else "morgen" if tage == 1 else f"in {tage} Tagen"}'


def _name_der_aussage(claims: Any, aussage: Any) -> str:
    try:
        eintrag = claims.entities.get(aussage.subject_ref)
    except Exception:  # noqa: BLE001
        eintrag = None
    if eintrag and eintrag.get('label'):
        return str(eintrag['label'])
    treffer = re.match(r'^(.{1,80}?) hat am ', str(aussage.statement or ''))
    if treffer:
        return treffer[1].strip()
    subjekt = str(aussage.subject_ref or '')
    return subjekt.removeprefix('person:a:') if subjekt.startswith('person:a:') else 'Jemand'


def kalender_eintraege(claims: Any, von: date, bis: date) -> list[dict[str, Any]]:
    """Bestätigte Geburtstage als ganztägige Einträge zwischen `von` und `bis` (ausschließlich), jedes Jahr wieder.

    Nur für die eigene Ansicht: Nichts davon wird in einen Kalender eines Anbieters geschrieben.
    """
    try:
        aussagen = claims.by_predicate(PRAEDIKATE_GEBURTSTAG)
    except Exception:  # noqa: BLE001
        return []
    eintraege, gesehen = [], set()
    for aussage in aussagen:
        wert = geburtstag_wert(aussage)
        if not wert or aussage.subject_ref in gesehen:
            continue
        gesehen.add(aussage.subject_ref)
        name = _name_der_aussage(claims, aussage)
        for jahr in range(von.year, bis.year + 1):
            tag = naechster_geburtstag(wert, date(jahr, 1, 1))
            if tag is None or tag.year != jahr or not (von <= tag < bis):
                continue
            eintraege.append({
                'uid': f'geburtstag:{aussage.id}:{jahr}', 'summary': f'Geburtstag: {name}',
                'start': f'{tag.isoformat()}T00:00:00', 'end': f'{(tag + timedelta(days=1)).isoformat()}T00:00:00',
                'location': '', 'all_day': True, 'attendees': [], 'art': 'geburtstag',
                'source_label': 'Aus deinem Gedächtnis · nur in Kingfisher, in keinem Kalender gespeichert'})
    return sorted(eintraege, key=lambda e: (e['start'], e['summary']))


def im_briefing(episodes: Any, claims: Any, beschriftungen: Any, jetzt: datetime, *, tage: int = 1) -> list[dict[str, Any]]:
    """Geburtstage heute und in den nächsten `tage` Tagen, nur für **bestätigte** Personen im inneren Kreis mit
    **angenommenem** Geburtstag. Kontakte, Kollegen und offene Kreise kommen nie vor."""
    from .kreis import INNERER_KREIS, alle_bestaetigten
    innen = sorted(s for s, k in alle_bestaetigten(episodes).items() if k == INNERER_KREIS)
    if not innen:
        return []
    heute = jetzt.date()
    namen = namen_in_teilen(beschriftungen, innen)
    ergebnis = []
    for sache in innen:
        # Gleich, ob der Geburtstag aus einem Vorschlag oder aus „Merke dir …“ im Gespräch angenommen wurde.
        gefunden = bestaetigter_geburtstag(claims, sache)
        for aussage in [gefunden] if gefunden else []:
            tag = naechster_geburtstag(aussage['wert'], heute)
            if tag is None or (tag - heute).days > tage:
                continue
            name = namen.get(sache, sache)
            ergebnis.append({'sache': sache, 'name': name, 'vorname': vorname(name), 'datum': tag.isoformat(),
                             'wann': 'heute' if tag == heute else 'morgen' if tag == heute + timedelta(days=1)
                             else 'bald', 'aussage_id': aussage['aussage_id'], 'episode_id': aussage['episode_id']})
    return sorted(ergebnis, key=lambda g: (g['datum'], g['name']))


__all__ = ['GeburtstagFund', 'Lauf', 'PRAEDIKATE_GEBURTSTAG', 'anstehend_text', 'bestaetigter_geburtstag',
           'geburtstag_wert', 'kalender_eintraege', 'subjekte', 'PRAEDIKAT_GEBURTSTAG', 'PRAEDIKAT_WIEDERKEHREND', 'VON_GEBURTSTAG',
           'VON_WIEDERKEHREND', 'Wiederkehr', 'aus_eigener_angabe', 'aus_glueckwunsch', 'geburtstag_text',
           'geburtstage_vorlegen', 'im_briefing', 'kandidaten_fuer_namen', 'name_aus_termin', 'namensschluessel',
           'naechster_geburtstag', 'serie_finden', 'stand', 'tag_und_monat_aus', 'wiederkehrendes_finden',
           'wiederkehrendes_vorlegen']
