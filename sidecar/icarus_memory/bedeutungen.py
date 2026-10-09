"""Erste Suchstufe: Was kann ein Begriff im eigenen Bestand bedeuten?

„Was ist mit Mainz los?“ kann das Projekt Mainz meinen, die Uniklinik Mainz,
einen Termin in Mainz oder den Urlaub dort. Ein Stabschef klärt das zuerst und
geht dann gezielt in die Tiefe. Diese Stufe sammelt dafür alle belegten
Bedeutungen eines Begriffs, jede mit einer Zeile Kontext, und sagt, ob eine
davon klar überwiegt.

Bewusst ohne Modell: Sie läuft in Millisekunden, auch für noch nicht
eingeordnete Quellen und ohne eingerichteten Anbieter. Sie rät nichts; jede
Bedeutung hat Quellen, einen Projektnamen, einen bestätigten Eintrag oder
einen Termin als Grundlage. Siehe docs/25-gedaechtnis-konzeptpruefung.md.

**Nichts geht unter.** Jede Quelle, die den Begriff nennt, gehört zu genau
einer Bedeutung, private eingeschlossen (Urlaub, Umzug eines Kollegen). Erst
Projekte und bestätigte Einträge, dann die Gegenpartei (Adresse oder
Firmendomäne), dann Notizen und Termine ohne Gegenpartei: Sie wandern zu einer
Gegenpartei, deren Namen sie nennen, sonst bleiben sie für sich. Wenige kleine
Gruppen, die dieselben Tage nennen, sind eine Bedeutung („Urlaub in Mainz“:
Hotel, Fahrkarten, Notiz). Was über die Anzeigegrenze hinausgeht, steht in
einer Sammelzeile; ihre Quellen bleiben per Klick erreichbar.

Die Fragenerkennung selbst steht in `frage.py`; `begriff_aus_frage` bleibt als
Kurzform davon für Aufrufer, die nur den Gegenstand einer offenen Frage brauchen.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Any, Iterable

from .datumstext import MONAT_NUMMER, iso_versuchen_utc as _zeit
from .identitaet import ist_privater_anbieter, nennungen

MAX_BEDEUTUNGEN = 6
MAX_QUELLEN_JE_BEDEUTUNG = 50
TERMIN_FENSTER_VOR = timedelta(days=30)
TERMIN_FENSTER_NACH = timedelta(days=30)
FRISCH = timedelta(days=30)
UEBERWIEGT = 2.0
#: Eine Gruppe mit so vielen Quellen oder weniger darf mit anderen kleinen zu einer zusammenfallen.
KLEIN = 2
#: So viele einzelne Erwähnungen (eine Quelle, kein Zusammenhang) stehen als eigene Zeile; sind es mehr,
#: gehen sie gesammelt in „Weitere Erwähnungen“ (jede Quelle bleibt per Klick erreichbar).
SCHWACH_EINZELN = 2
#: Grundgewicht einer Gegenpartei, an die der Nutzer selbst geschrieben hat (sonst 2).
GRUND_AUSTAUSCH = 4.0
_LABEL_PRAEFIX = re.compile(r'^(?:Mails (?:mit|von)|Zusammenhang|Betreff|Ort|Notiz|Termin|Mail|Projekt|'
                            r'Organisation|Person|Thema|Eintrag)\s+')

_BETREFF_PRAEFIX = re.compile(r'^(?:(?:re|aw|wg|fw|fwd|antw)\s*:\s*)+', re.I)
# Adressen, hinter denen viele verschiedene Menschen stehen: Gruppiert wird nach Adresse, nicht Domäne.
# Bestandteile von Domänen, die eine Firma nicht kennzeichnen.
_DOMAIN_ALLGEMEIN = frozenset(
    'example com de net org info mail service verband klinikum klinik praxis gmbh institut beratung '
    'gruppe team office www'.split())
_MONATE = MONAT_NUMMER
_DATUM_ZAHL = re.compile(r'(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.(?:\d{4})?(?!\d)')
_DATUM_WORT = re.compile(r'(?<![\d.])(\d{1,2})\.\s*(?:(?:bis|und|-|–)\s*(\d{1,2})\.\s*)?(' + '|'.join(_MONATE) + r')\b', re.I)
_ORT_ZEILE = re.compile(r'^Ort:\s*(.+)$', re.M)


def begriff_aus_frage(frage: Any) -> str | None:
    """Der Gegenstand einer offenen Überblicksfrage, sonst nichts.

    Nur offene Fragen („Was ist mit Mainz los?“, „Wie steht es um Mainz?“,
    „Mainz?“) werden erkannt. Eine genaue Frage („Wann liefert Anna die
    Prüfmuster für Mainz?“) geht wie bisher direkt in die belegte Auswahl.
    Kurzform für `frage.rueckfall`; ein Modell braucht diese Stelle nicht.
    """
    if not isinstance(frage, str) or len(frage) > 200:
        return None
    from .frage import rueckfall
    anfrage = rueckfall(frage)
    return anfrage.sachen[0] if anfrage.absicht == 'ueberblick' and anfrage.sachen else None


def _wort(begriff: str) -> re.Pattern:
    return re.compile(r'(?<!\w)' + re.escape(begriff) + r'(?:s|es|er|ern)?(?!\w)', re.I)


def _quellenzeit(eintrag: dict) -> datetime | None:
    return _zeit(eintrag.get('occurred_at')) or _zeit(eintrag.get('recorded_at'))


def _datum(moment: datetime | None) -> str:
    return f'{moment.day}.{moment.month}.' if moment else ''


def _anzahl(n: int, einzahl: str, mehrzahl: str) -> str:
    return f'eine {einzahl}' if n == 1 else f'{n} {mehrzahl}'


def _domain(teilnehmer: str) -> str | None:
    adresse = parseaddr(teilnehmer)[1]
    return adresse.rsplit('@', 1)[1].lower() if '@' in adresse else None


def _anzeige(teilnehmer: str) -> str:
    name, adresse = parseaddr(teilnehmer)
    return (name or adresse or teilnehmer).strip()


def _absender(teilnehmer: str, wort: re.Pattern) -> str | None:
    """Gruppe eines passenden Absenders: die Domain, wenn der Begriff in ihr
    steht (unimedizin-mainz.de), sonst die Person selbst (Anna Keller)."""
    if not wort.search(teilnehmer):
        return None
    domain = _domain(teilnehmer)
    if domain and wort.search(domain):
        return domain
    adresse = parseaddr(teilnehmer)[1].casefold()
    return adresse or _anzeige(teilnehmer).casefold()


def _titel(quelle: dict) -> str:
    return _BETREFF_PRAEFIX.sub('', (quelle.get('title') or '').strip())


def _letzte_betreffe(quellen: list[dict], wieviele: int = 3) -> str | None:
    """Die neuesten verschiedenen Betreffe als Kontextzeile, ohne AW:- und WG:-Vorsatz."""
    ohne_zeit = datetime.min.replace(tzinfo=timezone.utc)
    betreffe: list[str] = []
    for quelle in sorted(quellen, key=lambda q: _quellenzeit(q) or ohne_zeit, reverse=True):
        titel = _titel(quelle)
        if titel and titel.casefold() not in {b.casefold() for b in betreffe}:
            betreffe.append(titel[:80])
        if len(betreffe) == wieviele:
            break
    return 'zuletzt: ' + ', '.join(f'„{b}“' for b in betreffe) if betreffe else None


def _gewicht(grund: float, anzahl: int, zuletzt: datetime | None, jetzt: datetime) -> float:
    frisch = 1.5 if zuletzt is not None and jetzt - zuletzt <= FRISCH else 1.0
    return round((grund + math.log1p(anzahl)) * frisch, 3)


# --------------------------------------------------------------------------- Merkmale

def falten(text: str) -> str:
    """Zum Vergleichen: klein, Umlaute aufgelöst („Süd“ und „sued“ sind gleich)."""
    return (text or '').casefold().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')


def stamm(wort: str) -> str:
    """Wortanfang, mit dem Beugungen zusammenfallen („Präsentation“ und „Präsentationen“)."""
    return falten(wort)[:6]


def wortstaemme(text: str, mindest: int = 4) -> set[str]:
    """Die Stämme aller Wörter ab `mindest` Buchstaben."""
    return {stamm(w) for w in re.findall(r'[\wäöüß]+', text.casefold()) if len(w) >= mindest and not w.isdigit()}


def _tage(text: str) -> set[tuple[int, int]]:
    """Tag und Monat, die ein Text nennt („23.10.“, „23. Oktober“, „23. bis 26. Oktober“)."""
    tage: set[tuple[int, int]] = set()
    for tag, monat in _DATUM_ZAHL.findall(text):
        if 1 <= int(tag) <= 31 and 1 <= int(monat) <= 12:
            tage.add((int(tag), int(monat)))
    for erster, zweiter, monat in _DATUM_WORT.findall(text):
        for tag in (erster, zweiter):
            if tag and 1 <= int(tag) <= 31:
                tage.add((int(tag), _MONATE[monat.casefold()]))
    return tage


def _ort(quelle: dict) -> str | None:
    """Der Ort eines Termins (Zeile „Ort:“ im Text), nur bis zum ersten Komma."""
    if quelle.get('kind') != 'event':
        return None
    treffer = _ORT_ZEILE.search(quelle.get('anfang') or '')
    return treffer.group(1).split(',')[0].strip() if treffer else None


# --------------------------------------------------------------------------- Gruppen

@dataclass
class _Gruppe:
    """Eine Bedeutung im Aufbau: Quellen, Grundgewicht und Kennwörter, an denen man sie erkennt."""
    art: str
    ref: str
    label: str
    quellen: list[dict]
    grund: float
    extra: str | None = None
    kennwoerter: set[str] = field(default_factory=set)
    namen: list[str] = field(default_factory=list)


def _partei(quelle: dict, eigene: Iterable[str]) -> tuple[str, str, str, str] | None:
    """(Schlüssel, Domäne, Adresse, Name) der Gegenpartei: der erste fremde Beteiligte mit Adresse.

    Die eigenen Adressen sind „ich“, nie die Gegenpartei. Hinter einer Firmendomäne
    zählt die Domäne (mehrere Ansprechpartner, eine Firma), hinter einer
    Freemail-Domäne die Adresse.
    """
    for n in nennungen({'participants': quelle.get('participants') or [], 'contacts': [],
                       'provenance': {'source_type': quelle.get('source_type')}}, eigene):
        if n.ich or not n.adresse:
            continue
        domain = n.adresse.rsplit('@', 1)[1] if '@' in n.adresse else ''
        if domain and not ist_privater_anbieter(domain):
            return f'd:{domain}', domain, n.adresse, n.name
        return f'a:{n.adresse}', domain, n.adresse, n.name
    return None


def _selbst_geschrieben(quelle: dict, eigene: Iterable[str]) -> bool:
    """Steht der Nutzer selbst unter den Beteiligten? Empfangene Mails führen seine Adresse nicht, gesendete schon."""
    return any(n.ich for n in nennungen({'participants': quelle.get('participants') or [], 'contacts': [],
                                       'provenance': {'source_type': quelle.get('source_type')}}, eigene))


def _kennwoerter(namen: Iterable[str], domain: str) -> set[str]:
    """Wörter, an denen eine Quelle ohne Beteiligte ihre Gegenpartei verrät: Namensteile und Firmenname."""
    woerter = {falten(w) for n in namen for w in re.findall(r'[\wäöüß]+', n) if len(w) >= 4}
    if domain and not ist_privater_anbieter(domain):
        woerter |= {falten(t) for t in re.split(r'[.\-]', domain)
                    if len(t) >= 5 and falten(t) not in _DOMAIN_ALLGEMEIN}
    return woerter


def _partei_gruppen(quellen: list[dict], eigene: Iterable[str]) -> tuple[list[_Gruppe], list[dict]]:
    """Quellen mit Gegenpartei nach Adresse oder Firmendomäne gruppiert; die ohne bleiben übrig."""
    gruppen: dict[str, list[dict]] = defaultdict(list)
    personen: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    domaenen: dict[str, str] = {}
    ohne: list[dict] = []
    for quelle in quellen:
        partei = _partei(quelle, eigene)
        if partei is None:
            ohne.append(quelle)
            continue
        schluessel, domain, adresse, name = partei
        gruppen[schluessel].append(quelle)
        personen[schluessel][adresse][name] += 1
        domaenen[schluessel] = domain
    ergebnis = []
    for schluessel, mitglieder in gruppen.items():
        # Die Person hinter jeder Adresse mit ihrem häufigsten Namen.
        namen = {adresse: (zaehler.most_common(1)[0][0] or adresse) for adresse, zaehler in personen[schluessel].items()}
        anzeige = sorted(namen.values(), key=str.casefold)
        domain = domaenen[schluessel]
        firma = schluessel.startswith('d:')
        if firma and len(namen) == 1:
            label = f'Mails mit {anzeige[0]} ({domain})' if anzeige[0] != next(iter(namen)) else f'Mails mit {domain}'
        elif firma:
            label = f'Mails mit {domain}'
        else:
            label = f'Mails mit {anzeige[0]}'
        extra = None
        if firma and len(namen) > 1:
            extra = 'mit ' + ', '.join(anzeige[:3]) + (' u. a.' if len(anzeige) > 3 else '')
        # Ein Austausch, in dem der Nutzer selbst geschrieben hat, ist ein Zusammenhang, der ihn angeht;
        # bloß Empfangenes (Werbung, Benachrichtigungen) ist es seltener und zählt weniger.
        austausch = any(_selbst_geschrieben(q, eigene) for q in mitglieder)
        ergebnis.append(_Gruppe('gegenpartei', schluessel, label, mitglieder, GRUND_AUSTAUSCH if austausch else 2.0,
                                extra, _kennwoerter(namen.values(), domain), anzeige))
    return ergebnis, ohne


def _zuordnen(gruppen: list[_Gruppe], quellen: list[dict]) -> list[dict]:
    """Quellen ohne Beteiligte (Notiz, Termin) zur Gegenpartei, die sie beim Namen nennt.

    Nur bei genau einer passenden Gruppe; nennt die Quelle mehrere, bleibt sie offen.
    Zurück: die, die zu keiner passten.
    """
    rest = []
    for quelle in quellen:
        text = falten(_titel(quelle) + ' ' + (quelle.get('anfang') or ''))
        passend = [g for g in gruppen if any(re.search(r'(?<![a-z0-9])' + re.escape(k), text) for k in g.kennwoerter)]
        if len(passend) == 1:
            passend[0].quellen.append(quelle)
        else:
            rest.append(quelle)
    return rest


def _einzelne(quellen: list[dict], wort: re.Pattern) -> list[_Gruppe]:
    """Quellen ohne Gegenpartei: Termine je Ort, gleiche Betreffe zusammen, sonst jede für sich."""
    orte: dict[str, list[dict]] = defaultdict(list)
    betreffe: dict[str, list[dict]] = defaultdict(list)
    einzeln: list[dict] = []
    haeufigkeit = Counter(falten(_titel(q)) for q in quellen)
    for quelle in quellen:
        ort = _ort(quelle)
        if ort and wort.search(ort):
            orte[falten(ort)].append(quelle)
        elif _titel(quelle) and haeufigkeit[falten(_titel(quelle))] > 1:
            betreffe[falten(_titel(quelle))].append(quelle)
        else:
            einzeln.append(quelle)
    gruppen: list[_Gruppe] = []
    for schluessel, mitglieder in orte.items():
        ort = _ort(mitglieder[0]) or schluessel
        gruppen.append(_Gruppe('ort', 'o:' + schluessel, f'Ort {ort}', mitglieder, 1.5,
                               _letzte_betreffe(mitglieder)))
    for schluessel, mitglieder in betreffe.items():
        gruppen.append(_Gruppe('betreff', schluessel, f'Betreff „{_titel(mitglieder[0])}“', mitglieder, 1.5))
    for quelle in einzeln:
        art = {'event': 'Termin', 'document': 'Notiz'}.get(quelle.get('kind'), 'Mail')
        titel = _titel(quelle) or '(ohne Titel)'
        gruppen.append(_Gruppe('quelle', quelle['id'], f'{art} „{titel[:100]}“', [quelle], 1.0))
    return gruppen


def _zusammenlegen(gruppen: list[_Gruppe]) -> list[_Gruppe]:
    """Kleine Gruppen, die dieselben Tage nennen, sind ein Zusammenhang („Urlaub in Mainz“).

    Nur Gruppen bis `KLEIN` Quellen ohne Grundlage aus Projekt oder Bestand; große
    Gegenparteien bleiben, wie sie sind. Gleiche Tage sind ein Hinweis und kein
    Beweis; deshalb trägt die Zeile den Kontext, an dem ein Mensch es prüft.
    """
    kandidaten = [g for g in gruppen if g.art in {'gegenpartei', 'ort', 'betreff', 'quelle', 'absender'}
                  and len(g.quellen) <= KLEIN]
    tage_je_gruppe = {id(g): set().union(*(_tage(_titel(q) + ' ' + (q.get('anfang') or '')) for q in g.quellen))
                      for g in kandidaten}
    eltern = {id(g): id(g) for g in kandidaten}

    def wurzel(schluessel: int) -> int:
        while eltern[schluessel] != schluessel:
            eltern[schluessel] = eltern[eltern[schluessel]]
            schluessel = eltern[schluessel]
        return schluessel

    je_tag: dict[tuple[int, int], int] = {}
    for g in kandidaten:
        for tag in tage_je_gruppe[id(g)]:
            if tag in je_tag:
                eltern[wurzel(id(g))] = wurzel(je_tag[tag])
            else:
                je_tag[tag] = id(g)
    familien: dict[int, list[_Gruppe]] = defaultdict(list)
    for g in kandidaten:
        familien[wurzel(id(g))].append(g)
    zusammen = {id(g) for familie in familien.values() if len(familie) > 1 for g in familie}
    ergebnis = [g for g in gruppen if id(g) not in zusammen]
    for familie in familien.values():
        if len(familie) < 2:
            continue
        quellen = [q for g in familie for q in g.quellen]
        # Der Titel trägt die eigene Notiz, sonst die neueste Quelle.
        eigene_notiz = next((q for q in quellen if q.get('kind') == 'document'), None)
        neueste = max(quellen, key=lambda q: _quellenzeit(q) or datetime.min.replace(tzinfo=timezone.utc))
        titel = _titel(eigene_notiz or neueste)[:80] or '(ohne Titel)'
        ergebnis.append(_Gruppe('zusammenhang', ','.join(sorted(q['id'] for q in quellen)),
                                f'Zusammenhang „{titel}“', quellen, 1.5, _letzte_betreffe(quellen),
                                set().union(*(g.kennwoerter for g in familie)),
                                [n for g in familie for n in g.namen]))
    return ergebnis


def _bedeutung(art, ref, label, quellen, jetzt, grund, extra=None, namen=()):
    zeiten = [z for z in (_quellenzeit(q) for q in quellen) if z]
    zuletzt = max(zeiten) if zeiten else None
    teile = []
    if quellen:
        teile.append(_anzahl(len(quellen), 'Quelle', 'Quellen'))
    if zuletzt:
        teile.append(f'zuletzt {_datum(zuletzt)}')
    if extra:
        teile.append(extra)
    # Woran man diese Bedeutung erkennt: Titel, Beteiligte und Bezeichnung. Die Auflösung
    # der Frage vergleicht damit ein Unterscheidungsmerkmal („Urlaub“, „Präsentation“).
    titel = ' '.join(_titel(q) for q in quellen[:MAX_QUELLEN_JE_BEDEUTUNG])
    return {
        'art': art, 'ref': ref, 'label': label, 'detail': ' · '.join(teile),
        'anzahl': len(quellen), 'zuletzt': zuletzt.isoformat() if zuletzt else None,
        'quellen': [q['id'] for q in quellen[:MAX_QUELLEN_JE_BEDEUTUNG]],
        'gewicht': _gewicht(grund, len(quellen), zuletzt, jetzt),
        'merkmale': sorted(wortstaemme(f'{_LABEL_PRAEFIX.sub("", label)} {titel} {" ".join(namen)}')),
        'wortlaut': falten(' '.join(_titel(q) + ' ' + (q.get('anfang') or '') for q in quellen[:20]))[:6000],
    }


def _stark(bedeutung: dict) -> bool:
    """Trägt die Bedeutung selbst? Projekt, Eintrag, Absender, Ort, Zusammenhang, Betreff, Termin oder
    eine Gegenpartei mit mindestens zwei Quellen. Eine einzelne Quelle ist nur eine Erwähnung."""
    if bedeutung['art'] == 'gegenpartei':
        return bedeutung['anzahl'] >= 2
    return bedeutung['art'] not in {'quelle', 'erwaehnung'}


def _aus_gruppe(gruppe: _Gruppe, jetzt: datetime) -> dict:
    if gruppe.art == 'gegenpartei':
        # Bei einer Firma die Ansprechpartner, dazu die letzten Betreffe, an denen ein Mensch erkennt, worum es geht.
        extra = ' · '.join(teil for teil in (gruppe.extra, _letzte_betreffe(gruppe.quellen)) if teil)
    else:
        extra = gruppe.extra or (_letzte_betreffe(gruppe.quellen) if gruppe.art == 'zusammenhang' else None)
    return _bedeutung(gruppe.art, gruppe.ref, gruppe.label, gruppe.quellen, jetzt, gruppe.grund, extra or None,
                      gruppe.namen)


def bedeutungen(begriff: str, *, episodes: Any, projects: list[tuple[str, str]] | None = None,
                entities: Any = None, termine: list[dict] | None = None,
                jetzt: datetime | None = None, eigene: Iterable[str] = ()) -> dict[str, Any]:
    """Alle belegten Bedeutungen eines Begriffs, stärkste zuerst.

    `projects` sind (Kennung, Name), `termine` Kalendereinträge mit `uid`,
    `summary`/`title`, `start` und optional `location`, `eigene` die Adressen
    des Nutzers (sie sind nie die Gegenpartei). Jede Quelle zählt nur bei einer
    Bedeutung: erst Projekte, dann Absender, dann Gegenpartei, dann Rest.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    eigene = list(eigene)
    wort = _wort(begriff)
    erwaehnt, abgeschnitten = episodes.mentions(begriff)
    vergeben: set[str] = set()
    ergebnis: list[dict] = []

    # 1. Projekte, deren Name der Begriff ist: die stärkste Bedeutung, denn der
    #    Name stammt vom Nutzer selbst. Gezählt werden alle zugeordneten Quellen.
    passende = [(pid, name) for pid, name in projects or () if isinstance(name, str) and wort.search(name)]
    for pid, name in passende:
        zugeordnet = episodes.project_heads(pid)
        vergeben.update(q['id'] for q in zugeordnet)
        ergebnis.append(_bedeutung('projekt', pid, f'Projekt {name}', zugeordnet, jetzt, 5.0))

    # 2. Bestätigte Einträge (Organisation, Ort, Person, Thema), deren Name den
    #    Begriff als Wort enthält: „Uniklinik Mainz“ bei „Mainz“.
    if entities is not None:
        try:
            eintraege = [e for e in entities.list() if isinstance(e, dict)
                         and isinstance(e.get('label'), str) and wort.search(e['label'])
                         and e.get('kind') != 'project']
        except Exception:  # noqa: BLE001 - ein kaputtes Verzeichnis kippt die Suche nicht
            eintraege = []
        for eintrag in eintraege:
            art = {'organization': 'Organisation', 'place': 'Ort', 'person': 'Person',
                   'topic': 'Thema'}.get(eintrag.get('kind'), 'Eintrag')
            try:
                verknuepft = len(entities.sources(eintrag['id']))
            except Exception:  # noqa: BLE001
                verknuepft = 0
            extra = 'bestätigter Eintrag' + (f', {_anzahl(verknuepft, "verknüpfte Quelle", "verknüpfte Quellen")}'
                                             if verknuepft else '')
            bedeutung = _bedeutung('eintrag', eintrag.get('id'), f'{art} {eintrag["label"]}', [], jetzt, 4.0, extra)
            bedeutung['gewicht'] = _gewicht(4.0, verknuepft, None, jetzt)
            ergebnis.append(bedeutung)

    # 3. Absender, deren Adresse oder Name den Begriff trägt, etwa
    #    unimedizin-mainz.de oder „Stadt Mainz“.
    rest = [q for q in erwaehnt if q['id'] not in vergeben]
    nach_absender: dict[str, list[dict]] = defaultdict(list)
    namen: dict[str, str] = {}
    for quelle in rest:
        if 'participants' not in quelle.get('matched_in', ()):
            continue
        for teilnehmer in quelle.get('participants') or ():
            schluessel = _absender(teilnehmer, wort)
            if schluessel is None:
                continue
            nach_absender[schluessel].append(quelle)
            namen.setdefault(schluessel, _anzeige(teilnehmer))
            break
    gruppen_absender = []
    for schluessel, quellen in nach_absender.items():
        vergeben.update(q['id'] for q in quellen)
        gruppen_absender.append((schluessel, quellen,
                                 namen[schluessel] if '@' in schluessel or '.' not in schluessel else schluessel))
    # Zwei Menschen gleichen Namens mit verschiedenen Adressen: nicht zwei
    # gleiche Zeilen, sondern mit der Domäne der Adresse unterscheidbar.
    gleiche = Counter(anzeige.casefold() for schluessel, _, anzeige in gruppen_absender if '@' in schluessel)
    aufgebaut: list[_Gruppe] = []
    for schluessel, quellen, anzeige in gruppen_absender:
        person = '@' in schluessel
        if person and gleiche[anzeige.casefold()] > 1:
            anzeige = f'{anzeige} ({schluessel.rsplit("@", 1)[1]})'
        # Was ein Mensch erkennt: die letzten Betreffe dieser Adresse.
        extra = _letzte_betreffe(quellen) if person else None
        aufgebaut.append(_Gruppe('absender', schluessel, f'Mails von {anzeige}', quellen, 2.0, extra,
                                 namen=[anzeige]))

    # 4. Alle übrigen Erwähnungen: nach Gegenpartei (Adresse oder Firmendomäne).
    rest = [q for q in erwaehnt if q['id'] not in vergeben]
    partei_gruppen, ohne_partei = _partei_gruppen(rest, eigene)
    aufgebaut += partei_gruppen

    # 5. Notizen und Termine ohne Beteiligte: zur Gegenpartei, die sie nennen, sonst für sich.
    ohne_partei = _zuordnen(partei_gruppen, ohne_partei)
    aufgebaut += _einzelne(ohne_partei, wort)

    # 6. Kleine Gruppen mit denselben Tagen sind ein Zusammenhang („Urlaub in Mainz“).
    aufgebaut = _zusammenlegen(aufgebaut)
    for gruppe in aufgebaut:
        ergebnis.append(_aus_gruppe(gruppe, jetzt))

    # 7. Termine im Umfeld von heute, deren Titel oder Ort den Begriff trägt.
    for termin in termine or ():
        titel = str(termin.get('summary') or termin.get('title') or '')
        ort = str(termin.get('location') or '')
        beginn = _zeit(termin.get('start'))
        if beginn is None or not (wort.search(titel) or wort.search(ort)):
            continue
        if not jetzt - TERMIN_FENSTER_VOR <= beginn <= jetzt + TERMIN_FENSTER_NACH:
            continue
        kommend = beginn >= jetzt
        eintrag = {
            'art': 'termin', 'ref': termin.get('uid'), 'label': f'Termin „{titel or ort}“',
            'detail': f'{"am" if kommend else "war am"} {_datum(beginn)}' + (f' · {ort}' if ort and ort != titel else ''),
            'anzahl': 0, 'zuletzt': beginn.isoformat(), 'quellen': [],
            'gewicht': round((4.0 if kommend and beginn - jetzt <= timedelta(days=14) else 1.5), 3),
            'merkmale': sorted(wortstaemme(f'{titel} {ort}')), 'wortlaut': falten(f'{titel} {ort}'),
        }
        ergebnis.append(eintrag)

    for bedeutung in ergebnis:
        bedeutung['stark'] = _stark(bedeutung)
    ergebnis.sort(key=lambda b: (-b['gewicht'], b['label'].casefold()))
    # Einzelne Erwähnungen sind keine Bedeutung für sich: Wenige stehen als eigene Zeile, viele gesammelt.
    schwach = [b for b in ergebnis if not b['stark']]
    gesammelt = schwach if len(schwach) > SCHWACH_EINZELN else []
    zeilen = [b for b in ergebnis if not any(b is g for g in gesammelt)]
    platz = MAX_BEDEUTUNGEN - 1 if gesammelt or len(zeilen) > MAX_BEDEUTUNGEN else MAX_BEDEUTUNGEN
    verborgen, zeilen = zeilen[platz:], zeilen[:platz]
    # Die Sammelzeile trägt die Quellen aller ausgeblendeten und gesammelten Bedeutungen.
    ids = {q for b in (*gesammelt, *verborgen) for q in b['quellen']}
    sammel = []
    if ids:
        weitere = [q for q in erwaehnt if q['id'] in ids]
        zeile = _bedeutung('erwaehnung', begriff.casefold(), f'Weitere Erwähnungen von „{begriff}“', weitere, jetzt, 0.0)
        zeile['gewicht'], zeile['stark'] = 0.0, False
        sammel = [zeile]
    tragend = zeilen
    eindeutig = None
    if len(tragend) == 1 or (len(tragend) > 1 and tragend[0]['gewicht'] >= UEBERWIEGT * tragend[1]['gewicht']):
        eindeutig = tragend[0] if tragend else None
    # Eine einzelne Mail überwiegt nicht hundert Erwähnungen: Dann ist offen,
    # ob der Nutzer genau sie meint.
    if (eindeutig is not None and eindeutig['art'] not in {'projekt', 'termin'} and sammel
            and sammel[0]['anzahl'] > max(2, 2 * eindeutig['anzahl'])):
        eindeutig = None
    return {
        'begriff': begriff,
        'bedeutungen': tragend + sammel,
        'weitere_bedeutungen': len(verborgen),
        'eindeutig': eindeutig,
        'abgeschnitten': abgeschnitten,
    }


MAX_BEREICH = 500


def bereich(auswahl: dict, *, episodes: Any, entities: Any = None,
            eigene: Iterable[str] = ()) -> tuple[list[str], bool]:
    """Alle Quellen einer gewählten Bedeutung, neueste zuerst, frisch aus dem Bestand.

    Anders als in der Übersicht zählt hier jede passende Quelle, auch wenn sie
    dort schon bei einer stärkeren Bedeutung stand: Wer „Mails mit
    unimedizin-mainz.de“ wählt, will alle diese Mails sehen. Zweiter Wert: ob
    der Bereich größer ist als das, was durchsucht wird; das wird angezeigt.
    """
    art, ref, begriff = auswahl['art'], auswahl['ref'], auswahl['begriff']
    eigene = list(eigene)
    if art == 'projekt':
        zugeordnet = [q['id'] for q in episodes.project_heads(ref, limit=MAX_BEREICH + 1)]
        return zugeordnet[:MAX_BEREICH], len(zugeordnet) > MAX_BEREICH
    if art == 'eintrag':
        try:
            eintrag = entities.get(ref) if entities is not None else None
        except Exception:  # noqa: BLE001 - gelöschter oder ungültiger Eintrag: leerer Bereich
            eintrag = None
        label = eintrag.get('label') if isinstance(eintrag, dict) else None
        if not isinstance(label, str) or not label.strip():
            return [], False
        begriff = label
    elif art not in {'absender', 'gegenpartei', 'betreff', 'erwaehnung', 'ort', 'quelle', 'zusammenhang'}:
        raise ValueError('Unbekannte Bedeutung')
    wort = _wort(begriff)
    erwaehnt, abgeschnitten = episodes.mentions(begriff)
    passend = []
    for quelle in erwaehnt:
        if art == 'absender':
            treffer = any(_absender(t, wort) == ref for t in quelle.get('participants') or ())
        elif art == 'gegenpartei':
            partei = _partei(quelle, eigene)
            treffer = partei is not None and partei[0] == ref
        elif art == 'betreff':
            treffer = _BETREFF_PRAEFIX.sub('', (quelle.get('title') or '').strip()).casefold() == ref
        elif art == 'ort':
            ort = _ort(quelle)
            treffer = ort is not None and 'o:' + falten(ort) == ref
        elif art in {'quelle', 'zusammenhang'}:
            # Die Auswahl ist beim Fragen festgehalten; hier zählt, was davon noch gilt.
            treffer = quelle['id'] in ref.split(',')
        else:
            treffer = True
        if treffer:
            passend.append(quelle['id'])
    return passend[:MAX_BEREICH], abgeschnitten or len(passend) > MAX_BEREICH


def meaning_choice_current(pending: Any, episodes: Any) -> bool:
    """Gilt eine gespeicherte Rückfrage noch?

    Ihre Beschriftungen stammen aus Quellen: eine Absenderdomain, ein Betreff.
    Ist eine dieser Quellen inzwischen ignoriert oder ersetzt, darf die
    Rückfrage weder so stehen bleiben noch angeklickt werden.
    """
    if (not isinstance(pending, dict) or pending.get('version') != 1
            or not isinstance(pending.get('query'), str) or not isinstance(pending.get('begriff'), str)
            or not isinstance(pending.get('options'), list) or not isinstance(pending.get('notes', []), list)):
        return False
    ids: list[str] = []
    for option in pending['options']:
        if (not isinstance(option, dict) or not all(isinstance(option.get(k), str) and option[k]
                                                    for k in ('label', 'art', 'ref'))
                or not isinstance(option.get('ids'), list)
                or not all(isinstance(value, str) for value in option['ids'])):
            return False
        ids += option['ids']
    for note in pending.get('notes', []):
        if not isinstance(note, dict) or not isinstance(note.get('ids', []), list):
            return False
        ids += [value for value in note.get('ids', []) if isinstance(value, str)]
    return not ids or len(episodes.usable_ids(ids)) == len(set(ids))


__all__ = ['begriff_aus_frage', 'bedeutungen', 'bereich', 'falten', 'meaning_choice_current', 'stamm', 'wortstaemme']
