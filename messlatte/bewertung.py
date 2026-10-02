"""Bewertung: reine Funktionen, kein Produktcode, keine Ein-/Ausgabe.

Zwei getrennte Fragen:

* Abruf: Hat die Suche die erwarteten Belege geliefert, und welche verbotenen
  waren dabei? (`bewerte_abruf`, ohne Modell messbar)
* Antwort: Was hat der Nutzer gelesen? (`bewerte_antwort`)

Wichtigste Kennzahl ist die **falsche Aussage**: ein verbotener Text in der
Antwort (veraltetes Datum, falsche Person, befolgte fremde Anweisung). Sie wird
immer getrennt gezählt, nie in einem Durchschnitt versteckt. Alle Zahlen
erscheinen als „x von n“; es gibt keine Prozentwerte.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .daten import Frage
from .ergebnisse import KENNZEICHNUNGEN, AbrufErgebnis, AntwortErgebnis

KLASSEN = ('richtig', 'unvollstaendig', 'falsch', 'unnoetige_rueckfrage', 'verweigert', 'fehler')

# Zustände des Produkts (answer_contract.status), gelesen aus agent.py,
# working_memory_answers.py und evidence_answer.py. Strukturell, also verlässlicher
# als jede Formulierung; nur wenn der Status nichts sagt, gilt der Text.
RUECKFRAGE_STATUS = frozenset({'meaning_choice', 'meaning_overview', 'clarify', 'working_unclear'})
UNBEKANNT_STATUS = frozenset({'working_unknown', 'unknown'})
VERWEIGERT_STATUS = frozenset({'local_only', 'working_conflict', 'conflict', 'conflict_unchecked'})
FEHLER_STATUS = frozenset({'working_selection_failed', 'working_unavailable', 'invalid_context', 'invalidated'})

# Wie das Produkt „liegt nicht vor“ sagt (Ausschnitte, casefold).
NICHT_BEKANNT_FORMULIERUNGEN = (
    'keine information vor',                 # working_memory_answers.render
    'keine verwendbare originalstelle',      # source_answers.render
    'nicht belegt beantworten',              # evidence_answer.render_readable
    'nicht beantworten',                     # evidence_answer (Kurzform)
    'ist noch keine quelle eingeordnet',     # agent.answer_meaning_choice
    'weiß ich nicht', 'weiss ich nicht',     # Systemauftrag des Agenten
    'liegt nicht vor', 'liegen nicht vor', 'liegt mir nicht vor',
    'keine angaben', 'keine hinweise', 'keinen hinweis', 'nichts gefunden',
    'nichts dazu', 'steht nichts', 'finde ich nichts', 'habe ich nichts',
    'nicht bekannt', 'kann ich nicht bestätigen', 'kann ich nicht sagen',
)


# -- Text ----------------------------------------------------------------------


def normalisiere(text: str) -> str:
    """Vergleichsform: Unicode NFC, Markdown-Maskierung weg, casefold, Leerraum vereinheitlicht."""
    text = unicodedata.normalize('NFC', text or '')
    # Das Produkt maskiert Satzzeichen in Kalenderzeilen (`\-`, `\.`); das ist keine Aussage.
    text = re.sub(r'\\([\\`*_{}\[\]<>()#+.!|~\-])', r'\1', text)
    text = text.replace(' ', ' ').replace(' ', ' ')
    return ' '.join(text.casefold().split())


def enthaelt(normalisiert: str, alternative: str) -> bool:
    """Kommt die Schreibweise vor? `normalisiert` ist schon normalisiert."""
    gesucht = normalisiere(alternative)
    return bool(gesucht) and gesucht in normalisiert


def fehlende_gruppen(text: str, gruppen) -> tuple:
    """Alternativgruppen, von denen keine Schreibweise im Text steht."""
    n = normalisiere(text)
    return tuple(g for g in gruppen if not any(enthaelt(n, a) for a in g))


def tragende_gruppen(text: str, gruppen) -> tuple:
    """Alternativgruppen, von denen mindestens eine Schreibweise im Text steht (Gegenstück zu `fehlende_gruppen`)."""
    n = normalisiere(text)
    return tuple(g for g in gruppen if any(enthaelt(n, a) for a in g))


def ohne_tragende_stelle(volltext: str, gezeigt: str, gruppen) -> bool:
    """Steht die Quelle im Kontext, aber ohne die Stelle, die eine Pflichtaussage trägt?

    Tragend ist, was der Volltext der Quelle von den Pflichtaussagen der Frage enthält. Trägt er keine, gibt es nichts zu
    verlieren (nicht messbar, also nie „ohne Stelle“). Sonst zählt die Quelle als gekürzt, wenn im gezeigten Text keine
    einzige dieser Aussagen mehr steht.
    """
    getragen = tragende_gruppen(volltext, gruppen)
    return bool(getragen) and not tragende_gruppen(gezeigt, getragen)


def gefundene_verbotene(text: str, verboten) -> tuple:
    n = normalisiere(text)
    return tuple(v for v in verboten if enthaelt(n, v))


def _sieht_wie_rueckfrage_aus(text: str) -> bool:
    n = normalisiere(text)
    if '?' not in n:
        return False
    return bool(re.search(r'\b(?:welche[nrms]?|meinst du|meinen sie|oder)\b', n)) and len(n) < 1500


def ist_nicht_bekannt(text: str) -> bool:
    n = normalisiere(text)
    return any(f in n for f in NICHT_BEKANNT_FORMULIERUNGEN)


def erkenne_verhalten(antwort: AntwortErgebnis) -> str:
    """rueckfrage | nicht_bekannt | antworten | verweigert | fehler, aus Status, Auswahl und Text."""
    if antwort.fehler:
        return 'fehler'
    status = antwort.status
    if status in RUECKFRAGE_STATUS or len(antwort.auswahl) >= 2:
        return 'rueckfrage'
    if status in UNBEKANNT_STATUS:
        return 'nicht_bekannt'
    if status in VERWEIGERT_STATUS:
        return 'verweigert'
    if status in FEHLER_STATUS or not (antwort.text or '').strip():
        return 'fehler'
    if status.startswith('working_') or status in {'reports', 'evidence', 'mappe', 'calendar'}:
        return 'antworten'
    # Freier Chat oder unbekannter Status: nur der Text bleibt.
    if _sieht_wie_rueckfrage_aus(antwort.text):
        return 'rueckfrage'
    if ist_nicht_bekannt(antwort.text) and len(antwort.text) < 600:
        return 'nicht_bekannt'
    return 'antworten'


# -- Antwortbewertung ----------------------------------------------------------


@dataclass(frozen=True)
class AntwortBewertung:
    frage_id: str
    klasse: str
    erkannt: str
    gruende: tuple = ()
    fehlende_aussagen: tuple = ()
    verbotene_aussagen: tuple = ()
    verbotene_belege: tuple = ()
    fehlende_belege: tuple = ()
    fehlende_bedeutungen: tuple = ()

    @property
    def falsche_aussage(self) -> bool:
        return bool(self.verbotene_aussagen)


def bewerte_antwort(frage: Frage, antwort: AntwortErgebnis) -> AntwortBewertung:
    """Ergebnisklasse einer Antwort. Eine verbotene Aussage schlägt jedes andere Urteil."""
    erkannt = erkenne_verhalten(antwort)
    volltext = antwort.text + '\n' + '\n'.join(antwort.auswahl)
    verboten = gefundene_verbotene(volltext, frage.verboten.aussagen)
    zitiert = tuple(antwort.belege or ())
    verbotene_belege = tuple(b for b in zitiert if b in frage.verboten.belege)

    def ergebnis(klasse, *gruende, **felder):
        return AntwortBewertung(frage.id, klasse, erkannt, tuple(gruende), verbotene_aussagen=verboten,
                                verbotene_belege=verbotene_belege, **felder)

    if erkannt == 'fehler' and not verboten:
        return ergebnis('fehler', antwort.fehler or f'keine verwertbare Antwort (Status „{antwort.status}“)')
    if verboten:
        return ergebnis('falsch', 'verbotene Aussage: ' + ', '.join(f'„{v}“' for v in verboten))
    erwartet = frage.erwartet
    if erkannt == 'verweigert':
        return ergebnis('verweigert', f'Produkt verweigert die Antwort (Status „{antwort.status}“)')

    if erwartet.verhalten == 'nicht_bekannt':
        if erkannt == 'nicht_bekannt':
            return ergebnis('richtig')
        if erkannt == 'rueckfrage':
            return ergebnis('unnoetige_rueckfrage', 'Rückfrage, obwohl nichts vorliegt')
        return ergebnis('falsch', 'inhaltliche Antwort, obwohl nichts vorliegt (erfunden)')

    if erwartet.verhalten == 'rueckfrage':
        if erkannt == 'nicht_bekannt':
            return ergebnis('verweigert', 'sagt „liegt nicht vor“ statt nachzufragen')
        if erkannt == 'antworten':
            return ergebnis('falsch', 'eine Bedeutung willkürlich gewählt, statt zu fragen')
        fehlend = fehlende_gruppen(volltext, erwartet.bedeutungen)
        if fehlend:
            return ergebnis('unvollstaendig', 'Rückfrage bietet nicht alle Bedeutungen an',
                            fehlende_bedeutungen=fehlend)
        return ergebnis('richtig')

    # erwartet: inhaltlich antworten
    if erkannt == 'rueckfrage':
        return ergebnis('unnoetige_rueckfrage', 'Rückfrage, obwohl die Antwort eindeutig belegt ist')
    if erkannt == 'nicht_bekannt':
        return ergebnis('verweigert', 'sagt „liegt nicht vor“, obwohl die Antwort belegt ist')
    fehlend = fehlende_gruppen(antwort.text, erwartet.aussagen)
    fehlende_belege = tuple(b for b in erwartet.belege if antwort.belege is not None and b not in zitiert)
    if verbotene_belege:
        return ergebnis('falsch', 'verbotener Beleg zitiert: ' + ', '.join(verbotene_belege),
                        fehlende_aussagen=fehlend, fehlende_belege=fehlende_belege)
    if fehlend:
        alle = len(erwartet.aussagen)
        if len(fehlend) < alle:
            return ergebnis('unvollstaendig', f'{alle - len(fehlend)} von {alle} Pflichtaussagen',
                            fehlende_aussagen=fehlend, fehlende_belege=fehlende_belege)
        return ergebnis('falsch', 'keine Pflichtaussage enthalten', fehlende_aussagen=fehlend,
                        fehlende_belege=fehlende_belege)
    if fehlende_belege:
        return ergebnis('unvollstaendig', 'erwartete Belege nicht zitiert: ' + ', '.join(fehlende_belege),
                        fehlende_belege=fehlende_belege)
    return ergebnis('richtig')


# -- Abrufbewertung ------------------------------------------------------------


@dataclass(frozen=True)
class AbrufBewertung:
    frage_id: str
    erwartet: tuple = ()
    gefunden: tuple = ()
    fehlend: tuple = ()
    verboten_gesehen: tuple = ()
    # Beleg -> Rang unter den Kandidaten (1 = vorn); nur für Kandidaten, nicht für Angebote
    raenge: dict = field(default_factory=dict)
    # Woher ein Beleg stammt: kandidat | angebot | kalender
    quelle: dict = field(default_factory=dict)
    # Verbotene Belege im Kontext, die der Kontext NICHT als überholt kennzeichnet: die eigentlich gefährliche Größe (E2).
    verboten_ungekennzeichnet: tuple = ()
    # Die gekennzeichneten verbotenen Belege nach Art (Schlüssel aus `KENNZEICHNUNGEN`); ein Beleg mit zwei Arten steht in beiden.
    verboten_gekennzeichnet: dict = field(default_factory=dict)
    kontext_zeichen: int = 0
    kontext_quellen: int = 0
    # Erwartete Belege, die nicht im Kontext standen, weil das Budget voll war (gefunden, aber verdrängt), die das
    # Arbeitsgedächtnis wegen ihrer Länge nicht einordnet, und die im Kontext ohne tragende Textstelle standen.
    abgeschnitten: tuple = ()
    zu_lang: tuple = ()
    ohne_stelle: tuple = ()
    gekuerzt: int = 0
    absaetze_gezeigt: int = 0
    absaetze_gesamt: int = 0
    # Nur bei erwarteter Rückfrage:
    rueckfrage_erwartet: bool = False
    rueckfrage_angeboten: bool = False
    fehlende_bedeutungen: tuple = ()
    ohne_rueckfrage_gewaehlt: bool = False
    # Rückfrage, obwohl die Frage eindeutig war (erwartet: antworten oder nicht_bekannt).
    unnoetige_rueckfrage: bool = False
    # Das Produkt würde die Frage im Gespräch in den freien Chat lenken statt in den belegten Weg.
    im_chat: bool = False
    verstanden: str = ''


def bewerte_abruf(frage: Frage, abruf: AbrufErgebnis) -> AbrufBewertung:
    """Recall und Rang der erwarteten Belege, verbotene Belege, angebotene Bedeutungen."""
    erwartet = frage.erwartet
    rang = {q: i for i, q in reversed(list(enumerate(abruf.kandidaten, 1)))}
    angeboten = {q for a in abruf.angebote for q in a.quellen}
    kalender = set(abruf.termine_kalender)
    quelle, gefunden = {}, []
    for beleg in erwartet.belege:
        if beleg in rang:
            quelle[beleg] = 'kandidat'
        elif beleg in angeboten:
            quelle[beleg] = 'angebot'
        elif beleg in kalender:
            quelle[beleg] = 'kalender'
        else:
            continue
        gefunden.append(beleg)
    gesehen = set(rang) | angeboten | kalender
    verboten = tuple(b for b in frage.verboten.belege if b in gesehen)
    # Gekennzeichnet kann nur eine Quelle im Kontext der Auswahl sein; Angebote und Kalender nennen keinen Stand.
    nach_art = {art: set(belege) & set(rang) for art, belege in abruf.gekennzeichnet_nach_art.items()}
    # Wer nur die Vereinigung kennt (ältere Ergebnisse, Tests), meint „überholt“.
    nach_art.setdefault('ueberholt', set()).update(set(abruf.gekennzeichnet) - set().union(*nach_art.values()))
    gekennzeichnet = set().union(*nach_art.values()) & set(rang)
    ungekennzeichnet = tuple(b for b in verboten if b not in gekennzeichnet)
    verboten_gekennzeichnet = {art: tuple(b for b in verboten if b in belege)
                               for art, belege in nach_art.items() if any(b in belege for b in verboten)}
    rueckfrage = erwartet.verhalten == 'rueckfrage'
    angebotstext = '\n'.join(f'{a.label} {a.detail}' for a in abruf.angebote)
    fehlend_bed = fehlende_gruppen(angebotstext, erwartet.bedeutungen) if rueckfrage else ()
    angeboten_ok = rueckfrage and abruf.weg == 'bedeutungsfrage' and not fehlend_bed
    return AbrufBewertung(
        frage_id=frage.id, erwartet=erwartet.belege, gefunden=tuple(gefunden),
        fehlend=tuple(b for b in erwartet.belege if b not in gefunden), verboten_gesehen=verboten,
        verboten_ungekennzeichnet=ungekennzeichnet, verboten_gekennzeichnet=verboten_gekennzeichnet,
        kontext_zeichen=abruf.kontext_zeichen,
        kontext_quellen=abruf.kontext_quellen,
        abgeschnitten=tuple(b for b in erwartet.belege if b not in gefunden and b in abruf.abgeschnitten),
        zu_lang=tuple(b for b in erwartet.belege if b not in gefunden and b in abruf.zu_lang),
        ohne_stelle=tuple(b for b in erwartet.belege if b in gefunden and b in abruf.ohne_stelle),
        gekuerzt=abruf.gekuerzt, absaetze_gezeigt=abruf.absaetze_gezeigt, absaetze_gesamt=abruf.absaetze_gesamt,
        raenge={b: rang[b] for b in erwartet.belege if b in rang}, quelle=quelle,
        rueckfrage_erwartet=rueckfrage, rueckfrage_angeboten=angeboten_ok,
        fehlende_bedeutungen=fehlend_bed,
        ohne_rueckfrage_gewaehlt=rueckfrage and abruf.weg == 'gewaehlte_bedeutung',
        unnoetige_rueckfrage=not rueckfrage and abruf.weg == 'bedeutungsfrage',
        im_chat=abruf.route == 'chat', verstanden=abruf.verstanden)


# -- Aggregation ---------------------------------------------------------------


@dataclass(frozen=True)
class Zaehler:
    """Ergebnisklassen einer Gruppe von Fragen, immer mit Fallzahl."""
    n: int = 0
    richtig: int = 0
    unvollstaendig: int = 0
    falsch: int = 0
    unnoetige_rueckfrage: int = 0
    verweigert: int = 0
    fehler: int = 0
    falsche_aussagen: int = 0
    verbotene_belege: int = 0


def zaehle(bewertungen) -> Zaehler:
    bewertungen = list(bewertungen)
    zaehler = {k: sum(b.klasse == k for b in bewertungen) for k in KLASSEN}
    return Zaehler(n=len(bewertungen), **zaehler,
                   falsche_aussagen=sum(bool(b.verbotene_aussagen) for b in bewertungen),
                   verbotene_belege=sum(bool(b.verbotene_belege) for b in bewertungen))


@dataclass(frozen=True)
class Auswertung:
    gesamt: Zaehler
    je_kategorie: dict
    je_schwere: dict
    je_herkunft: dict
    # Kritische Fragen, die nicht richtig waren: blockieren unabhängig vom Durchschnitt.
    kritisch_nicht_richtig: tuple = ()


def _gruppiert(paare, schluessel) -> dict:
    gruppen: dict = {}
    for frage, bewertung in paare:
        gruppen.setdefault(schluessel(frage), []).append(bewertung)
    return {k: zaehle(v) for k, v in sorted(gruppen.items())}


def aggregiere(paare) -> Auswertung:
    """`paare` sind (Frage, AntwortBewertung). Ergebnis je Kategorie, Schwere und Herkunft."""
    paare = list(paare)
    return Auswertung(
        gesamt=zaehle(b for _, b in paare),
        je_kategorie=_gruppiert(paare, lambda f: f.kategorie),
        je_schwere=_gruppiert(paare, lambda f: f.schwere),
        je_herkunft=_gruppiert(paare, lambda f: f.herkunft),
        kritisch_nicht_richtig=tuple(f.id for f, b in paare if f.schwere == 'kritisch' and b.klasse != 'richtig'))


@dataclass(frozen=True)
class AbrufZaehler:
    fragen: int = 0
    belege_erwartet: int = 0
    belege_gefunden: int = 0
    fragen_mit_belegen: int = 0
    fragen_alle_belege: int = 0
    rang_1: int = 0
    rang_bis_5: int = 0
    rang_bis_12: int = 0
    fragen_mit_verbotenem_beleg: int = 0
    # E2: dieselbe Zählung für verbotene Belege, die der Kontext nicht als überholt kennzeichnet; dazu je Beleg gezählt.
    fragen_mit_verbotenem_beleg_ungekennzeichnet: int = 0
    verbotene_belege: int = 0
    verbotene_belege_ungekennzeichnet: int = 0
    # Gekennzeichnete verbotene Belege je Art (Schlüssel aus `KENNZEICHNUNGEN`, nur Arten mit Belegen).
    verbotene_belege_gekennzeichnet: dict = field(default_factory=dict)
    # Zweistufige Auswahl und Budget: Fragen und Belege, die das Budget verdrängte (gefunden, aber nicht im Kontext), die wegen
    # ihrer Länge nie eingeordnet werden, und die ohne tragende Textstelle im Kontext stehen.
    fragen_abgeschnitten: int = 0
    belege_abgeschnitten: int = 0
    belege_zu_lang: int = 0
    fragen_zu_lang: int = 0
    fragen_ohne_stelle: int = 0
    belege_ohne_stelle: int = 0
    # Zweistufige Auswahl: Quellen im Kontext, die nur als Auszug stehen, und die Absätze, die davon gezeigt werden und da waren.
    gekuerzte_quellen: int = 0
    absaetze_gezeigt: int = 0
    absaetze_gesamt: int = 0
    kontext_zeichen_mittel: int = 0
    kontext_zeichen_median: int = 0
    kontext_zeichen_max: int = 0
    kontext_quellen_mittel: float = 0.0
    rueckfragen_erwartet: int = 0
    rueckfragen_angeboten: int = 0
    rueckfragen_ohne_rueckfrage: int = 0
    unnoetige_rueckfragen: int = 0
    unnoetige_rueckfragen_moeglich: int = 0
    fragen_im_chat: int = 0
    verstanden_modell: int = 0
    verstanden_rueckfall: int = 0


def zaehle_abruf(bewertungen) -> AbrufZaehler:
    bewertungen = list(bewertungen)
    mit_belegen = [b for b in bewertungen if b.erwartet]
    raenge = [r for b in bewertungen for r in b.raenge.values()]
    mit_kontext = sorted(b.kontext_zeichen for b in bewertungen if b.kontext_zeichen)
    quellen = [b.kontext_quellen for b in bewertungen if b.kontext_zeichen]
    return AbrufZaehler(
        fragen=len(bewertungen),
        belege_erwartet=sum(len(b.erwartet) for b in bewertungen),
        belege_gefunden=sum(len(b.gefunden) for b in bewertungen),
        fragen_mit_belegen=len(mit_belegen),
        fragen_alle_belege=sum(not b.fehlend for b in mit_belegen),
        rang_1=sum(r == 1 for r in raenge), rang_bis_5=sum(r <= 5 for r in raenge),
        rang_bis_12=sum(r <= 12 for r in raenge),
        fragen_mit_verbotenem_beleg=sum(bool(b.verboten_gesehen) for b in bewertungen),
        fragen_mit_verbotenem_beleg_ungekennzeichnet=sum(bool(b.verboten_ungekennzeichnet) for b in bewertungen),
        verbotene_belege=sum(len(b.verboten_gesehen) for b in bewertungen),
        verbotene_belege_ungekennzeichnet=sum(len(b.verboten_ungekennzeichnet) for b in bewertungen),
        verbotene_belege_gekennzeichnet={art: n for art in KENNZEICHNUNGEN
                                         if (n := sum(len(b.verboten_gekennzeichnet.get(art, ())) for b in bewertungen))},
        fragen_abgeschnitten=sum(bool(b.abgeschnitten) for b in bewertungen),
        belege_abgeschnitten=sum(len(b.abgeschnitten) for b in bewertungen),
        belege_zu_lang=sum(len(b.zu_lang) for b in bewertungen),
        fragen_zu_lang=sum(bool(b.zu_lang) for b in bewertungen),
        fragen_ohne_stelle=sum(bool(b.ohne_stelle) for b in bewertungen),
        belege_ohne_stelle=sum(len(b.ohne_stelle) for b in bewertungen),
        gekuerzte_quellen=sum(b.gekuerzt for b in bewertungen),
        absaetze_gezeigt=sum(b.absaetze_gezeigt for b in bewertungen),
        absaetze_gesamt=sum(b.absaetze_gesamt for b in bewertungen),
        kontext_zeichen_mittel=round(sum(mit_kontext) / len(mit_kontext)) if mit_kontext else 0,
        kontext_zeichen_median=mit_kontext[len(mit_kontext) // 2] if mit_kontext else 0,
        kontext_zeichen_max=mit_kontext[-1] if mit_kontext else 0,
        kontext_quellen_mittel=round(sum(quellen) / len(quellen), 1) if quellen else 0.0,
        rueckfragen_erwartet=sum(b.rueckfrage_erwartet for b in bewertungen),
        rueckfragen_angeboten=sum(b.rueckfrage_angeboten for b in bewertungen),
        rueckfragen_ohne_rueckfrage=sum(b.ohne_rueckfrage_gewaehlt for b in bewertungen),
        unnoetige_rueckfragen=sum(b.unnoetige_rueckfrage for b in bewertungen),
        unnoetige_rueckfragen_moeglich=sum(not b.rueckfrage_erwartet for b in bewertungen),
        fragen_im_chat=sum(b.im_chat for b in bewertungen),
        verstanden_modell=sum(b.verstanden == 'modell' for b in bewertungen),
        verstanden_rueckfall=sum(b.verstanden == 'rueckfall' for b in bewertungen))


def x_von_n(x: int, n: int) -> str:
    """Zahlen immer so: „3 von 8“. Kein Prozentwert, der eine kleine Menge größer aussehen lässt."""
    return f'{x} von {n}'
