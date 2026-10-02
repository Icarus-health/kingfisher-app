"""„In die Akte übernehmen“: aus einer gelungenen Antwort wird über einen Vorschlag Wissen.

Das Gegenstück zum Rückkanal („Stimmt nicht?“, `rueckmeldung.py`): Eine Antwort, die stimmt, soll der Nutzer mit
einem Klick festhalten können, statt dieselbe Frage morgen noch einmal zu stellen. Aber nach der Regel des
Gedächtnisses (`10-verdichtung.md`) schreibt nichts einen Fakt in den Bestand, bevor ein Mensch ihn angenommen hat.
Deshalb erzeugt dieses Modul **nur Vorschläge**:

* je gewähltem Satz ein Wissenskandidat (`KnowledgeService.propose`, Art `knowledge`): Subjekt ist die Sache der Akte
  (`person:a:…`, `projekt:…`), Beziehung `aussage`, Wert und Aussage der Satz, so wie der Nutzer ihn las;
* als Belege die Quellen, auf die der Satz sich stützt, mit der **wörtlichen Textstelle** und dem Fingerabdruck der
  Quelle (ohne beides weist der Wissenspfad den Vorschlag ab);
* die Annahme läuft über den vorhandenen Weg (`/api/v1/memory/candidates/{id}/accept`); erst sie legt die Aussage an.

Was diese Datei bewusst **nicht** tut: einen Claim anlegen, einen Vorschlag annehmen, eine Akte oder Quelle ändern.
Ein Satz, der schon als Aussage in der Akte steht, wird nicht noch einmal vorgeschlagen; ein Satz, der auf
überholten oder gekennzeichneten Belegen beruht (`akten_kontext.py`, `kennzeichnung.py`), wird nur mit dem Hinweis
vorgeschlagen, und der Hinweis steht im Vorschlag selbst.

Die Antwort liest der Server selbst (aus der Gesprächsansicht, wie beim Rückkanal) und prüft jeden Satz **erneut**
(`satzantwort.wiederherstellen`): Übernommen wird nur, was die Satzprüfung jetzt noch besteht.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from .akten import stamm_menge
from .claims import ClaimError
from .episodes import EpisodeError
from .proposals import Evidence, ProposalError
from .satzantwort import AntwortBeleg, Dargestellt

#: Die Beziehung der übernommenen Sätze (mehrwertig, siehe `relations.py`).
PRAEDIKAT = 'aussage'
#: Wer den Vorschlag gemacht hat: die Antwort, mit Gespräch und Nachricht, damit sie ihre Vorschläge wiederfindet.
VORSCHLAG_VON = 'antwort:'
MAX_NOTIZ = 500
MAX_ZITAT = 600
MAX_ZIELE = 4
#: Arten von Sachen, die aus den Belegen als Ziel vorgeschlagen werden, wenn die Frage keine nannte.
ARTEN_AUS_BELEGEN = ('projekt', 'organisation', 'person')

STATUS_VORGESCHLAGEN = 'vorgeschlagen'
STATUS_STEHT_SCHON = 'steht_schon'
STATUS_LIEGT_VOR = 'liegt_vor'
STATUS_FEHLER = 'fehler'


class UebernehmenFehler(ValueError):
    """Ein Wunsch lässt sich nicht erfüllen (keine Sätze, unbekannte Akte, keine Wahl); mit lesbarem Grund."""


def vorschlag_von(gespraech_id: str, nachricht_id: str) -> str:
    return f'{VORSCHLAG_VON}{gespraech_id}:{nachricht_id}'


# -- Die Antwort lesen ----------------------------------------------------------------------------


def antwort_lesen(nachricht: dict[str, Any], episodes: Any, claims: Any) -> Dargestellt:
    """Die Satzantwort einer Nachricht der Gesprächsansicht, jeder Satz neu geprüft.

    Wirft `UebernehmenFehler`, wenn die Nachricht keine Antwort in Sätzen (mehr) ist: Rückfragen, der Zitatmodus und
    Antworten, deren Belege nicht mehr gelten, haben nichts, was sich übernehmen ließe.
    """
    from . import satzantwort
    kontext = ((nachricht.get('metadata') or {}).get('context')) or {}
    if nachricht.get('role') != 'assistant' or not isinstance(kontext.get('satzantwort'), dict):
        raise UebernehmenFehler('Diese Antwort hat keine Sätze, die sich übernehmen ließen.')
    roh = kontext.get('working_answer') or {}
    dargestellt = satzantwort.wiederherstellen(roh.get('satzantwort'), episodes, claims) if isinstance(roh, dict) else None
    if dargestellt is None or dargestellt.status != 'saetze' or not dargestellt.saetze:
        raise UebernehmenFehler('Die Belege dieser Antwort gelten nicht mehr. Bitte die Frage noch einmal stellen.')
    return dargestellt


def frage_der_antwort(nachrichten: Sequence[dict[str, Any]], stelle: int) -> str:
    """Die Frage des Nutzers vor der Antwort (wie im Rückkanal)."""
    return next((m['content'] for m in reversed(nachrichten[:stelle]) if m['role'] == 'user'),
                next((m['content'] for m in reversed(nachrichten) if m['role'] == 'user'), ''))


# -- Hinweise, Dopplung ----------------------------------------------------------------------------


def _kurz(text: str, grenze: int = 90) -> str:
    text = ' '.join(str(text or '').split())
    return text if len(text) <= grenze else text[:grenze - 1].rstrip() + '…'


def hinweise(belege: Sequence[AntwortBeleg]) -> list[str]:
    """Was gegen die Belege eines Satzes spricht: überholt, anderer Mensch gleichen Namens, außerhalb des Zeitraums."""
    ergebnis: list[str] = []
    for b in belege:
        titel = _kurz(b.titel, 60) or 'eine Quelle'
        for u in b.ueberholt:
            neu = u.neu_wert or _kurz(u.neu, 80)
            alt = u.alt_wert or _kurz(u.alt, 80)
            ergebnis.append(f'Die Quelle „{titel}“ ist überholt' + (f': {alt} gilt nicht mehr, jetzt {neu}.' if neu else '.'))
        ergebnis.extend(f'Quelle „{titel}“: {m.text()}' for m in b.kennzeichen)
    return list(dict.fromkeys(ergebnis))


def _normal(text: str) -> str:
    return ' '.join(str(text or '').casefold().split()).rstrip('.!? ')


def schon_aussage(claims: Any, sache: str, text: str) -> bool:
    """Steht der Satz (bis auf Schreibweise und Schlusspunkt) schon als nutzbare Aussage in der Akte dieser Sache?"""
    if claims is None:
        return False
    gesucht = _normal(text)
    return any(_normal(c.statement) == gesucht or _normal(c.value) == gesucht for c in claims.by_reference(sache))


# -- Ziele -----------------------------------------------------------------------------------------


def ziele_der_antwort(nachricht: dict[str, Any], dargestellt: Dargestellt, bezuege: Any) -> list[dict[str, str]]:
    """In welche Akte die Sätze passen: die Sachen der Frage, sonst Projekt oder Person aus den Belegen.

    Die Vorgabe steht vorn. Mehr als eine Sache heißt: Der Nutzer wählt mit einem Klick; nur dieser Satz von Sachen
    ist erlaubt (`vorschlagen` nimmt keine frei erfundene Sache an).
    """
    roh = (((nachricht.get('metadata') or {}).get('context')) or {}).get('working_answer') or {}
    akten = roh.get('akten') if isinstance(roh, dict) else None
    namen = (akten or {}).get('namen') if isinstance(akten, dict) else None
    sachen = [s for s in (akten or {}).get('sachen', ()) if isinstance(s, str)] if isinstance(akten, dict) else []
    ergebnis: list[str] = []
    for sache in sachen:
        if sache not in ergebnis:
            ergebnis.append(sache)
    if not ergebnis:
        gezaehlt: dict[str, int] = {}
        for beleg in dargestellt.belege:
            try:
                daten = bezuege.bezuege_der_quelle(beleg.episode_id)
            except Exception:  # noqa: BLE001 - eine Quelle ohne lesbare Bezüge liefert kein Ziel
                daten = None
            for eintrag in (daten or {}).get('bezuege', ()):
                if eintrag.get('art') in ARTEN_AUS_BELEGEN and eintrag.get('sache'):
                    gezaehlt[eintrag['sache']] = gezaehlt.get(eintrag['sache'], 0) + 1
        rang = {art: i for i, art in enumerate(ARTEN_AUS_BELEGEN)}
        # Nur die Sachen, die in den meisten Belegen vorkommen; unter ihnen Projekt vor Organisation vor Person.
        meiste = max(gezaehlt.values(), default=0)
        ergebnis = sorted((s for s, n in gezaehlt.items() if n == meiste),
                          key=lambda s: (rang.get(s.split(':', 1)[0], 9), s))
    from .bezuege import ART_TEXT, zerlegen
    liste = []
    for sache in ergebnis[:MAX_ZIELE]:
        art = (zerlegen(sache) or ('', ''))[0]
        name = (namen or {}).get(sache) if isinstance(namen, dict) else None
        liste.append({'sache': sache, 'name': str(name or bezuege.beschriftung(sache)), 'art_text': ART_TEXT.get(art, art)})
    return liste


# -- Belege mit wörtlicher Textstelle -------------------------------------------------------------------


_SAETZE = re.compile(r'(?<=[.!?])\s+|\n+')
#: Ein Punkt, der keinen Satz beendet: Tageszahl vor Monat („15. Oktober“), Ordnungszahl, gängige Abkürzungen.
_KEIN_ENDE = re.compile(r'(?:(?<!\d)\d{1,2}|\b(?:z|B|Nr|ca|bzw|usw|Abs|Dr|Hr|Fr|Str|ggf|inkl|evtl|vgl))\.$')
_FORTSETZUNG = re.compile(r'(?:[a-zäöüß0-9]|(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|'
                          r'Dezember)\b)')


def _saetze_der(body: str) -> list[str]:
    """Die Sätze eines Textes, wörtlich; ein Punkt nach Tageszahl oder Abkürzung trennt nicht."""
    grenzen = [(m.start(), m.end()) for m in _SAETZE.finditer(body)]
    saetze, anfang = [], 0
    for von, bis in grenzen:
        if _KEIN_ENDE.search(body[anfang:von]) and _FORTSETZUNG.match(body[bis:bis + 12]) and '\n' not in body[von:bis]:
            continue
        saetze.append(body[anfang:von])
        anfang = bis
    saetze.append(body[anfang:])
    return saetze


def textstelle(body: str, satz: str, ref: dict[str, Any] | None = None) -> str:
    """Die wörtliche Stelle der Quelle, die zum Satz passt: der Satz der Quelle mit den meisten gemeinsamen Wörtern.

    Wörtlich heißt: ein zusammenhängender Ausschnitt des Quelltextes, unverändert. Findet sich nichts Gemeinsames,
    gilt der eingeordnete Abschnitt des Belegs (`ref`), sonst der Anfang der Quelle.
    """
    gesucht = set(stamm_menge(satz)) | set(re.findall(r'\d+[.,:]?\d*', satz))
    beste, punkte = '', 0
    for kandidat in _saetze_der(body):
        kandidat = kandidat.strip()
        if not kandidat:
            continue
        gemeinsam = len((set(stamm_menge(kandidat)) | set(re.findall(r'\d+[.,:]?\d*', kandidat))) & gesucht)
        if gemeinsam > punkte:
            beste, punkte = kandidat, gemeinsam
    if not beste and ref and isinstance(ref.get('start'), int) and isinstance(ref.get('end'), int):
        beste = body[ref['start']:ref['end']].strip()
    if not beste:
        beste = body.strip()
    if len(beste) > MAX_ZITAT:
        beste = beste[:MAX_ZITAT].rstrip()
    return beste


def belege_als_evidenz(belege: Sequence[AntwortBeleg], satz: str, episodes: Any) -> list[Evidence]:
    """Je Beleg eine Evidenz: Quelle, wörtliche Textstelle, Fingerabdruck der Quelle zum jetzigen Stand."""
    evidenz: list[Evidence] = []
    gesehen: set[str] = set()
    for b in belege:
        if b.episode_id in gesehen:
            continue
        gesehen.add(b.episode_id)
        episode = episodes.get(b.episode_id)
        evidenz.append(Evidence(episode.id, textstelle(episode.body, satz, b.ref), episode.digest))
    return evidenz


# -- Vorschau und Vorschlagen ------------------------------------------------------------------------


@dataclass
class SatzInfo:
    nr: int
    text: str
    hinweise: list[str] = field(default_factory=list)
    steht_schon: bool = False

    def als_dict(self) -> dict[str, Any]:
        # Gekennzeichnete Sätze sind wählbar, aber nicht vorgewählt: Wer sie übernimmt, tut es mit dem Hinweis vor Augen.
        return {'nr': self.nr, 'text': self.text, 'hinweise': list(self.hinweise), 'steht_schon': self.steht_schon,
                'vorgabe': not self.hinweise and not self.steht_schon}


def saetze_info(dargestellt: Dargestellt, sache: str | None, claims: Any) -> list[SatzInfo]:
    nach_nummer = {b.nummer: b for b in dargestellt.belege}
    liste = []
    for i, satz in enumerate(dargestellt.saetze, 1):
        belege = [nach_nummer[n] for n in dict.fromkeys(satz.belege) if n in nach_nummer]
        liste.append(SatzInfo(i, satz.text, hinweise(belege), bool(sache) and schon_aussage(claims, sache, satz.text)))
    return liste


def bisherige(proposals: Any, gespraech_id: str, nachricht_id: str) -> list[dict[str, Any]]:
    """Die Vorschläge, die diese Antwort schon gemacht hat, mit Zustand (auch nach einem Neustart)."""
    return [p.to_dict() for p in proposals.von(vorschlag_von(gespraech_id, nachricht_id))]


def vorschlagen(*, dargestellt: Dargestellt, nummern: Sequence[int], sache: str, notiz: str, frage: str,
                gespraech_id: str, nachricht_id: str, episodes: Any, claims: Any, service: Any) -> list[dict[str, Any]]:
    """Erzeugt je gewähltem Satz einen Vorschlag, sofern er nicht schon in der Akte steht. Legt nie einen Claim an.

    Gibt je Satz einen Eintrag zurück: `status` (`vorgeschlagen`, `steht_schon`, `liegt_vor`, `fehler`), bei einem
    Vorschlag dazu seine Darstellung, die Hinweise und bei einem Fehler den Grund.
    """
    nach_nummer = {b.nummer: b for b in dargestellt.belege}
    wahl = list(dict.fromkeys(int(n) for n in nummern))
    if not wahl:
        raise UebernehmenFehler('Bitte mindestens einen Satz wählen.')
    if any(n < 1 or n > len(dargestellt.saetze) for n in wahl):
        raise UebernehmenFehler('Diesen Satz gibt es in der Antwort nicht.')
    notiz = ' '.join(str(notiz or '').split())[:MAX_NOTIZ]
    ergebnis: list[dict[str, Any]] = []
    for nr in sorted(wahl):
        satz = dargestellt.saetze[nr - 1]
        belege = [nach_nummer[n] for n in dict.fromkeys(satz.belege) if n in nach_nummer]
        warnungen = hinweise(belege)
        eintrag: dict[str, Any] = {'nr': nr, 'text': satz.text, 'hinweise': warnungen}
        if schon_aussage(claims, sache, satz.text):
            ergebnis.append({**eintrag, 'status': STATUS_STEHT_SCHON, 'grund': 'Steht schon in der Akte.'})
            continue
        gruende = ['Aus einer Antwort von Kingfisher übernommen; der Satz hat die Satzprüfung gegen seine Belege bestanden.']
        if frage:
            gruende.append(f'Frage: {_kurz(frage, 160)}')
        if warnungen:
            gruende.insert(0, 'Hinweis: ' + ' '.join(warnungen))
        if notiz:
            gruende.append(f'Notiz: {notiz}')
        try:
            evidenz = belege_als_evidenz(belege, satz.text, episodes)
            if not evidenz:
                raise ClaimError('Der Satz hat keinen Beleg, der sich anführen ließe.')
            vorschlag, neu = service.propose(
                subject_ref=sache, predicate=PRAEDIKAT, value=satz.text, statement=satz.text,
                rationale='\n'.join(gruende), evidence=evidenz, proposed_by=vorschlag_von(gespraech_id, nachricht_id))
        except (ClaimError, ProposalError, EpisodeError) as fehler:
            ergebnis.append({**eintrag, 'status': STATUS_FEHLER, 'grund': str(fehler)})
            continue
        ergebnis.append({**eintrag, 'status': STATUS_VORGESCHLAGEN if neu else STATUS_LIEGT_VOR,
                         'vorschlag': vorschlag.to_dict()})
    return ergebnis
