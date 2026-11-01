"""Zweistufige Auswahl: aus langen Quellen nur die passenden Absätze in den Kontext des Modells.

Die erste Stufe findet viele Kandidaten (Wortsuche, Volltextindex, Akten; 16 Quellen, je eine Fundstelle).
Die zweite Stufe entscheidet, **was von jeder Quelle** ins Modell geht. Bisher trug jede Zeile die ganze Quelle als
`context`. Echte Mails haben 2 bis 4 KB, Transkripte mehr: Nach zehn Quellen war das Zeichenbudget voll, der Rest fiel
weg, und das Modell sah Signatur, Haftungsausschluss und zitierte Vor-Mails mit. Jetzt bekommt jede lange Quelle:

* den **Kopf** des Textes (führende `Von:`-, `Adresse:`-Zeilen; Betreff, Absender und Datum stehen ohnehin in der Zeile),
* die **passenden Absätze**: Fenster von 300 bis 600 Zeichen an Absatz-, Zeilen- und Satzgrenzen, bewertet nach den
  Suchwörtern der Frage samt Umschreibungen (dieselbe Zerlegung, Wortformen und Wortteile wie die Suche:
  `WorkingMemoryStore.query_terms`, `working_memory_words`), seltene Wörter der Quelle zählen mehr, Zitat und Signatur
  weniger,
* die **Stellen der Akte** (überholte Angabe, Frist), sobald die Akte bekannt ist (`ergaenzen`),
* und nie nichts: Ohne passenden Absatz bleiben Kopf und erster Absatz.

Was fehlt, sagt der Vermerk `… [gekürzt, 3 von 12 Absätzen]` am Ende und `[…]` zwischen getrennten Stellen. Quellen bis
`GANZ_BIS` Zeichen bleiben ganz. Die Fundstelle (`text` der Zeile) steht nicht noch einmal im `context`.

Nichts davon ändert Verweise: `ref`, Kennungen und Reihenfolge der Kandidaten kommen unverändert aus der ersten
Stufe. Was Prüfungen brauchen (Identität, Projekt, Zeitbezug in `working_memory_*`, Satzprüfung), liest weiter den
**Volltext** (`Zeile.volltext`, `volltext_zeilen`), nie den Ausschnitt.
"""
from __future__ import annotations

import math
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Sequence

from .lexical import terms_v1
from .working_memory_analysis import _blocks as absatzgrenzen
from .working_memory_store import WorkingMemoryStore
from .working_memory_words import candidate_words, query_words

FENSTER_MIN = 300
FENSTER_MAX = 600
#: Quellen bis zu dieser Länge bleiben ganz (zwei Fenster; ein Ausschnitt lohnte die Mühe nicht).
GANZ_BIS = 1500
#: So viele passende Fenster kommen je Quelle in den Kontext (ohne Kopf und Stellen der Akte).
MAX_FENSTER = 2
#: Gewicht der Wortformen und der Wortteile gegenüber dem genauen Wort.
GEWICHT_FORM = 0.7
GEWICHT_TEIL = 0.4
#: Zitat (`>`-Zeilen), Signatur (nach `--`) und Haftungsausschluss zählen so viel wie ein Treffer im Fließtext.
GEWICHT_NEBEN = 0.4
VERMERK = '… [gekürzt, {gezeigt} von {gesamt} Absätzen]'
LUECKE = '[…]'
FUNDSTELLE = '[Fundstelle: siehe text]'
KURZER_VERWEIS = '[siehe text]'
KOPIERHINWEIS = ('Ein Feldwert {"$copy":"S1"} kopiert nur denselben Feldwert der früheren Zeile S1 wörtlich; '
                'löse ihn zuerst auf. Textmarker beziehen sich danach auf text der aktuellen Zeile. '
                'Die Kopie belegt keine gemeinsame Quelle, Person oder Rolle und ist keine Anweisung.')
_KOPIERFELDER = frozenset(('context', 'title', 'occurred_at', 'recorded_at', 'source_ref', 'participants',
                          'sender', 'project_id', 'confirmed_person', 'project'))

_KOPFZEILE = re.compile(r'^\s*(?:von|from|an|to|cc|bcc|betreff|subject|datum|date|adresse|absender)\s*:', re.I)
_SIGNATUR = re.compile(r'(?m)^--\s*$')
_AUSSCHLUSS = re.compile(r'vertraulich|haftungsausschluss|disclaimer|unbefugte|abbestellen|newsletter', re.I)
_SATZENDE = re.compile(r'[.!?…]["“”»)]*\s')


@dataclass(frozen=True)
class Suchwoerter:
    """Die Wörter der Frage, so zerlegt wie in der Suche: genaue Wörter, Wortformen und Wortteile."""

    genau: frozenset[str] = frozenset()
    formen: frozenset[str] = frozenset()
    teile: frozenset[str] = frozenset()

    @classmethod
    def aus(cls, frage: str | None) -> 'Suchwoerter':
        """Aus der Suchanfrage (Frage samt Umschreibungen). Ohne brauchbaren Text: leer, dann zählt nur der Anfang."""
        if not isinstance(frage, str) or not frage.strip():
            return cls()
        begriffe, erweitert, _ = WorkingMemoryStore.query_terms(frage)
        return cls(frozenset(begriffe), frozenset(erweitert), frozenset(query_words(set(begriffe) | erweitert)))

    def leer(self) -> bool:
        return not (self.genau or self.formen or self.teile)


@dataclass(frozen=True)
class Auszug:
    """Was vom Text einer Quelle ins Modell geht, und wie viel davon."""

    text: str
    gezeigt: int
    gesamt: int
    fenster: tuple[tuple[int, int], ...] = ()
    auswahl: tuple[int, ...] = ()
    kopf: tuple[int, int] | None = None
    ref: tuple[int, int] | None = None
    ref_zeigen: bool = False

    @property
    def gekuerzt(self) -> bool:
        return self.gezeigt < self.gesamt


class Zeile(dict):
    """Eine Zeile des Kontexts: verhält sich wie das Wörterbuch, das ans Modell geht, und trägt Volltext und Auszug dazu.

    Was Prüfungen brauchen, steht in `volltext`; `context` ist der Ausschnitt für das Modell. Nur das Wörterbuch
    wird serialisiert, die beiden Attribute bleiben im Speicher.
    """

    volltext: str = ''
    auszug: Auszug | None = None


def volltext_zeilen(zeilen: Sequence[dict]) -> list[dict]:
    """Die Zeilen mit dem Volltext als `context`, für alles, was den Text der Quelle prüft (nicht das Modell)."""
    return [dict(z, context=z.volltext) if isinstance(z, Zeile) else z for z in zeilen]


def modell_zeilen(zeilen: Sequence[dict]) -> list[dict]:
    """Gleichen kurzen Volltext und exakt gleiche Feldwerte nur einmal senden.

    Ein Unterschied jenseits führenden/nachfolgenden Leerraums bleibt erhalten,
    insbesondere Negation, Nachsatz und Zitierkontext. Die lokalen Zeilen und
    ihre Volltexte für Frische-/Belegprüfung werden niemals verändert.
    """
    result = []
    for zeile in zeilen:
        row = dict(zeile)
        text, context = row.get('text'), row.get('context')
        if (isinstance(text, str) and isinstance(context, str)
                and len(context) > len(FUNDSTELLE) and text.strip() == context.strip()):
            # Reiner Verweis bei vollständig gleichem Text; der ausführliche
            # Fundstellenmarker in langen Auszügen bleibt unverändert.
            row['context'] = KURZER_VERWEIS
        result.append(row)
    return _modellkopien(result)


def _jsonwert(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _modellbytes(value) -> int:
    """Quellen stehen als JSON-Text im Message-JSON: beide Escape-Ebenen zählen."""
    return len(_jsonwert(_jsonwert(value)).encode('utf-8'))


def hat_modellkopien(zeilen: Sequence[dict]) -> bool:
    return any(isinstance(value, dict) and '$copy' in value for row in zeilen for value in row.values())


def _kopierbar(value) -> bool:
    return isinstance(value, str) or (isinstance(value, list) and all(isinstance(item, str) for item in value))


def _modellkopien(zeilen: list[dict]) -> list[dict]:
    """Nur erste Literale desselben Felds wiederverwenden; kein Schluss über Quellenidentität.

    Die ganze Projektion muss einschließlich zusätzlicher Systemanweisung kleiner
    sein. Ohne ausreichende Ersparnis bleiben Format und Anweisung unverändert.
    Originalobjekte werden nie als Kopierkandidaten verwendet; reservierte
    Objektmarker im Eingang sind mehrdeutig und werden vor Modellversand abgewiesen.
    """
    if hat_modellkopien(zeilen):
        raise ValueError('Reservierter Kopiermarker im Originalfeld')
    ids = [row.get('id') for row in zeilen]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids) or len(set(ids)) != len(ids):
        raise ValueError('Mehrdeutige Modellzeilen-Kennung')
    erste, result = {}, []
    for row in zeilen:
        packed = dict(row)
        for key, value in row.items():
            if key not in _KOPIERFELDER or not _kopierbar(value):
                continue
            lookup = (key, _jsonwert(value))
            if lookup in erste:
                ref = {'$copy': erste[lookup]}
                if _modellbytes(ref) < _modellbytes(value):
                    packed[key] = ref
            else:
                erste[lookup] = row['id']
        result.append(packed)
    overhead = len(_jsonwert('\n' + KOPIERHINWEIS).encode('utf-8')) - 2
    return result if _modellbytes(zeilen) - _modellbytes(result) > overhead else zeilen


def modell_zeilen_entpacken(zeilen: Sequence[dict]) -> list[dict]:
    """Modellkopien streng zur bisherigen Projektion auflösen, ohne Textmarker umzudeuten.

    Für lokale Verlustfreiheitsprüfung: nur frühere gleichnamige Literalwerte,
    keine Ketten, Vorwärtsverweise oder Kopien von id/text/fachlichen Warnfeldern.
    Die Auflösung bestätigt weder eine gemeinsame Quelle noch eine Person.
    """
    original, erste, result = {}, {}, []
    for row in zeilen:
        identifier = row.get('id')
        if not isinstance(identifier, str) or not identifier or identifier in original:
            raise ValueError('Mehrdeutige Modellzeilen-Kennung')
        expanded = deepcopy(row)
        for key, value in row.items():
            if not isinstance(value, dict) or '$copy' not in value:
                continue
            if key not in _KOPIERFELDER or set(value) != {'$copy'} or not isinstance(value['$copy'], str):
                raise ValueError('Ungültiger Modellfeld-Verweis')
            prior = original.get(value['$copy'])
            if (prior is None or key not in prior or not _kopierbar(prior[key])
                    or erste.get((key, _jsonwert(prior[key]))) != value['$copy']):
                raise ValueError('Modellfeld-Verweis verlangt ein früheres gleichnamiges Literal')
            expanded[key] = deepcopy(prior[key])
        for key, value in row.items():
            if key in _KOPIERFELDER and _kopierbar(value):
                erste.setdefault((key, _jsonwert(value)), identifier)
        original[identifier] = row
        result.append(expanded)
    return result


def kuerzung(zeilen: Sequence[dict]) -> dict[str, int]:
    """Zählung für den Ausweis der Suche: wie viele Quellen gekürzt sind und wie viele Absätze davon gezeigt werden."""
    gekuerzt = [z.auszug for z in zeilen if isinstance(z, Zeile) and z.auszug is not None and z.auszug.gekuerzt]
    return {'gekuerzt': len(gekuerzt), 'absaetze_gezeigt': sum(a.gezeigt for a in gekuerzt),
            'absaetze_gesamt': sum(a.gesamt for a in gekuerzt)}


# -- Fenster ---------------------------------------------------------------------------------


def teilen(text: str, start: int, ende: int, maximum: int = FENSTER_MAX,
           minimum: int = FENSTER_MIN) -> list[tuple[int, int]]:
    """Einen langen Absatz in Stücke bis `maximum`, am liebsten an Zeilenenden, sonst Satzenden, sonst Leerzeichen.

    Die Vorgaben gelten für Fenster der Auswahl; die Abschnittsbildung (`abschnitte.py`) teilt mit größeren Maßen
    und nutzt dieselben Schnittregeln.
    """
    stuecke = []
    pos = start
    while ende - pos > maximum:
        bereich = text[pos:pos + maximum]
        schnitt = bereich.rfind('\n')
        if schnitt < minimum:
            enden = [m.end() for m in _SATZENDE.finditer(bereich)]
            schnitt = max((e for e in enden if e >= minimum), default=-1)
        if schnitt < minimum:
            schnitt = bereich.rfind(' ')
        if schnitt < minimum:
            schnitt = maximum
        stuecke.append((pos, pos + schnitt))
        pos += schnitt
        while pos < ende and text[pos].isspace():
            pos += 1
    if pos < ende:
        stuecke.append((pos, ende))
    return [(s, e) for s, e in stuecke if text[s:e].strip()]


def _signatur_ab(text: str) -> int | None:
    treffer = _SIGNATUR.search(text)
    return treffer.start() if treffer else None


def ist_zitatzeile(zeile: str) -> bool:
    """Eine Zeile eines zitierten Textes (beginnt mit `>`)."""
    return zeile.lstrip().startswith('>')


def _art(text: str, start: int, ende: int, signatur_ab: int | None) -> str:
    """`zitat` (überwiegend `>`-Zeilen), `signatur` (ab der Zeile `--`), `neben` (Haftungsausschluss) oder `text`."""
    stueck = text[start:ende]
    zeilen = [z for z in stueck.splitlines() if z.strip()]
    if zeilen and sum(ist_zitatzeile(z) for z in zeilen) * 2 >= len(zeilen):
        return 'zitat'
    if signatur_ab is not None and start >= signatur_ab:
        return 'signatur'
    return 'neben' if _AUSSCHLUSS.search(stueck) else 'text'


def fenster(text: str, ab: int = 0) -> list[tuple[int, int]]:
    """Die Fenster eines Textes (Anfang, Ende) in Reihenfolge: Absätze, lange geteilt, kurze benachbarte zusammengefasst.

    Ab `ab` (nach den Kopfzeilen). Zusammengefasst werden nur Absätze gleicher Art: Eine Signatur oder ein Zitat verschwindet
    nicht im Fenster des Fließtextes davor.
    """
    einheiten: list[tuple[int, int]] = []
    for start, ende in absatzgrenzen(text):
        if ende <= ab:
            continue
        start = max(start, ab)
        while start < ende and text[start].isspace():
            start += 1
        einheiten += [(start, ende)] if ende - start <= FENSTER_MAX else teilen(text, start, ende)
    signatur = _signatur_ab(text)
    ergebnis: list[tuple[int, int]] = []
    for start, ende in einheiten:
        if ergebnis:
            vorher = ergebnis[-1]
            zusammen = ende - vorher[0] <= FENSTER_MAX
            gleich = _art(text, vorher[0], vorher[1], signatur) == _art(text, start, ende, signatur)
            if zusammen and gleich and (vorher[1] - vorher[0] < FENSTER_MIN or ende - start < FENSTER_MIN):
                ergebnis[-1] = (vorher[0], ende)
                continue
        ergebnis.append((start, ende))
    return ergebnis


def _kopf(text: str) -> tuple[int, int] | None:
    """Führende Kopfzeilen des Textes (`Von:`, `Adresse:` …), höchstens sechs; `None`, wenn es keine gibt."""
    ende, zahl = 0, 0
    for zeile in text.splitlines(keepends=True)[:6]:
        if not _KOPFZEILE.match(zeile):
            break
        ende += len(zeile)
        zahl += 1
    return (0, len(text[:ende].rstrip())) if zahl else None


# -- Bewertung ---------------------------------------------------------------------------------


def bewerten(text: str, fenster_liste: Sequence[tuple[int, int]], woerter: Suchwoerter) -> list[float]:
    """Punkte je Fenster: Treffer der Suchwörter, seltene Wörter der Quelle zählen mehr; Zitat und Signatur weniger."""
    if woerter.leer():
        return [0.0] * len(fenster_liste)
    signatur_ab = _signatur_ab(text)
    treffer: list[dict[str, float]] = []
    for start, ende in fenster_liste:
        stueck = text[start:ende]
        woerter_im_fenster, teile_im_fenster = terms_v1(stueck), candidate_words(stueck)
        gefunden: dict[str, float] = {}
        for wort in woerter.genau & woerter_im_fenster:
            gefunden[wort] = 1.0
        for wort in woerter.formen & woerter_im_fenster:
            gefunden.setdefault(wort, GEWICHT_FORM)
        for teil in woerter.teile & teile_im_fenster:
            gefunden.setdefault(teil, GEWICHT_TEIL)
        treffer.append(gefunden)
    haeufigkeit: dict[str, int] = {}
    for gefunden in treffer:
        for schluessel in gefunden:
            haeufigkeit[schluessel] = haeufigkeit.get(schluessel, 0) + 1
    anzahl = len(fenster_liste)
    punkte = []
    for (start, ende), gefunden in zip(fenster_liste, treffer):
        summe = sum(gewicht * (1 + math.log(anzahl / haeufigkeit[schluessel])) for schluessel, gewicht in gefunden.items())
        faktor = 1.0 if _art(text, start, ende, signatur_ab) == 'text' else GEWICHT_NEBEN
        punkte.append(summe * faktor if summe else 0.0)
    return punkte


# -- Auswahl -----------------------------------------------------------------------------------


def _ueberlappt(fenster_bereich: tuple[int, int], bereich: tuple[int, int]) -> bool:
    return fenster_bereich[0] < bereich[1] and bereich[0] < fenster_bereich[1]


def _innen(fenster_bereich: tuple[int, int], bereich: tuple[int, int]) -> bool:
    return bereich[0] <= fenster_bereich[0] and fenster_bereich[1] <= bereich[1]


def _bauen(text: str, fenster_liste: Sequence[tuple[int, int]], auswahl: Sequence[int], kopf: tuple[int, int] | None,
           ref: tuple[int, int] | None, ref_zeigen: bool) -> Auszug:
    """Setzt den Auszug aus den gewählten Fenstern zusammen, in der Reihenfolge des Textes."""
    wahl = sorted(set(auswahl))
    teile: list[str] = []
    letzte = 0
    if kopf is not None:
        teile.append(text[kopf[0]:kopf[1]])
        letzte = kopf[1]
    fundstelle_gesetzt = False
    for index in wahl:
        start, ende = fenster_liste[index]
        if start < letzte:
            continue
        if ref is not None and not ref_zeigen and _innen((start, ende), ref):
            # Die Fundstelle steht als `text` in der Zeile; hier nur ein Verweis, einmal.
            if not fundstelle_gesetzt:
                teile.append(FUNDSTELLE)
                fundstelle_gesetzt = True
            letzte = ende
            continue
        if letzte and text[letzte:start].strip():
            teile.append(LUECKE)
        teile.append(text[start:ende])
        letzte = ende
    gezeigt = len(wahl)
    gesamt = len(fenster_liste)
    antwort = '\n'.join(teile)
    if gezeigt < gesamt:
        antwort += '\n' + VERMERK.format(gezeigt=gezeigt, gesamt=gesamt)
    return Auszug(antwort, gezeigt, gesamt, tuple(fenster_liste), tuple(wahl), kopf, ref, ref_zeigen)


def auszug(text: str, woerter: Suchwoerter, *, ref: tuple[int, int] | None = None, ref_zeigen: bool = False,
           max_fenster: int | None = None) -> Auszug:
    """Was vom Text ins Modell geht: ganz, wenn er kurz ist, sonst Kopf, passende Fenster und der Vermerk.

    `ref` ist die Fundstelle (Anfang, Ende) der Quelle. Steht sie schon als `text` in der Zeile, erscheint sie im
    Auszug nur als Verweis; mit `ref_zeigen` (Belege der Satzformulierung, dort gibt es kein `text`) steht sie vorn.
    """
    max_fenster = MAX_FENSTER if max_fenster is None else max_fenster
    if len(text) <= GANZ_BIS:
        fenster_liste = fenster(text)
        return Auszug(text, len(fenster_liste), len(fenster_liste), tuple(fenster_liste),
                      tuple(range(len(fenster_liste))), None, ref, ref_zeigen)
    kopf = _kopf(text)
    fenster_liste = fenster(text, kopf[1] if kopf else 0)
    if not fenster_liste:
        return Auszug(text, 0, 0)
    punkte = bewerten(text, fenster_liste, woerter)
    drin = [i for i, f in enumerate(fenster_liste) if ref is not None and _innen(f, ref)]
    waehlbar = list(range(len(fenster_liste)))
    gewaehlt: list[int] = []
    if ref is not None and ref_zeigen:
        # Die Fundstelle zuerst (ihre besten Fenster), sie ist der Anlass der Quelle.
        naechste = [i for i in waehlbar if _ueberlappt(fenster_liste[i], ref)]
        gewaehlt += sorted(naechste, key=lambda i: (-punkte[i], i))[:2]
    rest = [i for i in waehlbar if i not in gewaehlt and i not in (drin if not ref_zeigen else [])]
    passend = [i for i in sorted(rest, key=lambda i: (-punkte[i], i)) if punkte[i] > 0]
    signatur = _signatur_ab(text)
    fliesstext = [i for i in passend if _art(text, *fenster_liste[i], signatur) == 'text']
    # Zitat, Signatur und Haftungsausschluss nur, wenn der Fließtext der Quelle nichts Passendes hat.
    gewaehlt += (fliesstext or passend)[:max_fenster if fliesstext else min(2, max_fenster)]
    if not gewaehlt:
        gewaehlt = [0]  # Kein passender Absatz: Kopf und erster Absatz, nie nichts.
    if ref is not None and not ref_zeigen:
        gewaehlt += drin[:1]  # nur der Verweis auf die Fundstelle, zählt als gezeigt
    return _bauen(text, fenster_liste, gewaehlt, kopf, ref, ref_zeigen)


def ergaenzen(text: str, bisher: Auszug, stellen: Sequence[tuple[int, int, str]]) -> Auszug:
    """Fügt die Stellen hinzu, auf die sich die Akte stützt (überholte Angabe, Frist), sofern sie fehlen.

    Jede Stelle ist (Anfang, Ende, Marke) eines Abschnitts der Quelle. Enthält ein Fenster darin die Marke (etwa das
    Datum der überholten Frist), kommt dieses Fenster, sonst das erste Fenster des Abschnitts (höchstens zwei Fenster
    je Stelle). Eine ganz gezeigte Quelle bleibt, wie sie ist.
    """
    if not bisher.gekuerzt or not stellen:
        return bisher
    neu = list(bisher.auswahl)
    for start, ende, marke in stellen:
        darin = [i for i, f in enumerate(bisher.fenster) if _ueberlappt(f, (start, ende))]
        mit_marke = [i for i in darin if marke and marke.casefold() in text[bisher.fenster[i][0]:bisher.fenster[i][1]].casefold()]
        for index in (mit_marke or darin)[:2 if not mit_marke else 1]:
            if index not in neu:
                neu.append(index)
    if len(neu) == len(bisher.auswahl):
        return bisher
    return _bauen(text, bisher.fenster, neu, bisher.kopf, bisher.ref, bisher.ref_zeigen)


def vervollstaendigen(text: str, bisher: Auszug, stellen: Sequence[tuple[int, int, str]], *, max_zeichen: int) -> Auszug:
    """Gewählte Fenster an vorhandenen Originaleinheiten vervollständigen, innerhalb des Auszugsbudgets.

    Text und Stellen stammen aus derselben unveränderten Quelle. Nur überlappende
    Einheiten kommen hinzu, niemals neue Treffer oder ein abgeschnittenes Stück.
    Benachbarte sichtbare Fenster werden als ein wörtlicher Quellbereich gelesen;
    fehlender Inhalt bleibt durch die Lücke erkennbar.
    """
    if not bisher.gekuerzt or not bisher.ref_zeigen:
        return bisher

    def vereinigen(bereiche):
        ergebnis = []
        for start, ende in sorted(bereiche):
            if ergebnis and (start <= ergebnis[-1][1] or not text[ergebnis[-1][1]:start].strip()):
                ergebnis[-1] = (ergebnis[-1][0], max(ergebnis[-1][1], ende))
            else:
                ergebnis.append((start, ende))
        return ergebnis

    def bauen(bereiche):
        auswahl = tuple(i for i, f in enumerate(bisher.fenster) if any(_innen(f, b) for b in bereiche))
        teile = [text[start:ende] for start, ende in bereiche]
        ausgabe = ('\n' + LUECKE + '\n').join(teile)
        if len(auswahl) < bisher.gesamt:
            ausgabe += '\n' + VERMERK.format(gezeigt=len(auswahl), gesamt=bisher.gesamt)
        return Auszug(ausgabe, len(auswahl), bisher.gesamt, bisher.fenster, auswahl,
                      bisher.kopf, bisher.ref, bisher.ref_zeigen)

    bereiche = vereinigen([bisher.fenster[i] for i in bisher.auswahl]
                         + ([bisher.kopf] if bisher.kopf else []))
    for start, ende, _ in stellen:
        if any(_ueberlappt(b, (start, ende)) for b in bereiche):
            neu = vereinigen([*bereiche, (start, ende)])
            if len(bauen(neu).text) <= max_zeichen:
                bereiche = neu
    ergebnis = bauen(bereiche)
    return ergebnis if len(ergebnis.text) <= max_zeichen else bisher


__all__ = ['Auszug', 'FENSTER_MAX', 'FENSTER_MIN', 'GANZ_BIS', 'MAX_FENSTER', 'Suchwoerter', 'Zeile', 'absatzgrenzen',
           'auszug', 'bewerten', 'ergaenzen', 'fenster', 'ist_zitatzeile', 'kuerzung', 'teilen',
           'vervollstaendigen', 'volltext_zeilen']
