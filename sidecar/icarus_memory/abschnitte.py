"""Abschnitte: wie eine lange Quelle zur Einordnung in Stücke geteilt wird und wie die Ergebnisse wieder zusammenkommen.

Früher ordnete das Arbeitsgedächtnis nur Quellen bis 12.000 Zeichen ein. Ein Transkript mit 30.000 Zeichen konnte
deshalb nie Beleg werden. Jetzt wird **jede** Quelle eingeordnet, eine lange in Abschnitten:

* Die Quelle zerfällt in **Einheiten**, die Absätze des Arbeitsgedächtnisses (`working_memory_analysis._blocks`, dieselbe
  Zerlegung wie bei kurzen Quellen). Ist ein Absatz größer als `EINHEIT_MAX`, wird er geteilt: ein Transkript an
  Sprecherwechseln, eine Mail an Zitatgrenzen (Zeilen mit `>`), sonst an Zeilen-, Satz- und Wortenden. Die Schnittregeln
  sind die der Auswahl (`absatzauswahl.teilen`, `ist_zitatzeile`), nicht noch einmal geschrieben.
* Ein **Abschnitt** ist eine Folge ganzer Einheiten von `ZIEL_MIN` bis etwa `ZIEL_MAX` Zeichen, höchstens `MAX_BLOCKS`
  Einheiten (das Maß eines Modellaufrufs). Der nächste Abschnitt beginnt mit der letzten Einheit des vorigen: **eine
  Einheit Überlappung**, damit eine Aussage an der Schnittstelle in einem der beiden Abschnitte Nachbarn hat.
* Jeder Abschnitt kennt seinen **Zeichenbereich** in der Quelle (`start`, `ende`) und die Bereiche seiner Einheiten. Alle
  Zahlen sind Stellen im **Volltext**: Ein Beleg (`ref`: Anfang und Ende), die Satzprüfung und der „Weg nach unten“
  brauchen keine Umrechnung.
* Die Ergebnisse der Abschnitte werden je Quelle **zusammengeführt** (`zusammenfuehren`): Die Überlappung liefert eine
  Einheit zweimal, die erste Einordnung gilt; übrig bleibt je Einheit genau eine Art.

Eine Quelle, die in einen Abschnitt passt (bis `ZIEL_MAX` Zeichen, höchstens 24 Absätze, keiner über `MAX_BLOCK_CHARS`),
bleibt genau so eingeteilt wie früher: ein Abschnitt, die Absätze des Arbeitsgedächtnisses. Die neue Zerlegung greift
erst, wo die alte die Quelle zurückgestellt hätte.

Über `OBERGRENZE` Zeichen wird nicht mehr eingeordnet: Eine Quelle in dieser Größe ist ein Datenexport, keine Mitschrift.
Sie bleibt „zurückgestellt“, und das Logbuch vermerkt sie (`zu_lang`), statt sie still zu übergehen.

Deterministisch, ohne Modell, ohne Zufall: gleicher Text, gleiche Abschnitte.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .absatzauswahl import absatzgrenzen, ist_zitatzeile, teilen
from .transkript_eingang import MARKE as TRANSKRIPT_MARKE
from .transkript_eingang import ist_sprecherzeile
from .working_memory_analysis import MAX_BLOCK_CHARS, MAX_BLOCKS, UnsupportedSource
from .working_memory_store import MAX_SOURCE_CHARS

#: Ein Abschnitt wird geschlossen, sobald er so viele Zeichen (Summe seiner Einheiten) erreicht.
ZIEL_MIN = 3_000
#: Größer wird ein Abschnitt nicht: Er schließt, sobald `ZIEL_MIN` erreicht ist, und keine Einheit ist größer als `EINHEIT_MAX`.
EINHEIT_MAX = 3_000
ZIEL_MAX = ZIEL_MIN + EINHEIT_MAX
#: Größe, auf die zu große Absätze geteilt werden (Sprecherwechsel werden bis dahin zusammengefasst).
EINHEIT_ZIEL = 1_500
#: Mindestlänge eines Stücks, wenn ein Absatz ohne Zeilenende und Satzende geteilt werden muss.
EINHEIT_MIN = 600
#: Darüber wird eine Quelle nicht mehr eingeordnet (Zeichen). Das Maß gehört dem Bestand (`working_memory_store`).
OBERGRENZE = MAX_SOURCE_CHARS
#: Mehr Einheiten hält das Arbeitsgedächtnis je Quelle nicht (Verweise je Quelle, siehe `WorkingMemoryStore.commit`).
MAX_EINHEITEN = 2_000

ART_TRANSKRIPT, ART_MAIL, ART_TEXT = 'transkript', 'mail', 'text'


@dataclass(frozen=True)
class Abschnitt:
    """Ein Stück einer Quelle für einen Modellaufruf. Alle Stellen sind Zeichenstellen im Volltext."""

    nr: int
    """Zählt ab 1."""
    start: int
    ende: int
    einheiten: tuple[tuple[int, int], ...]
    ueberlappung: int = 0
    """Wie viele Einheiten am Anfang schon zum vorigen Abschnitt gehören (0 oder 1)."""

    @property
    def zeichen(self) -> int:
        return self.ende - self.start


class ZuLang(UnsupportedSource):
    """Die Quelle ist länger als `OBERGRENZE` (oder hat mehr als `MAX_EINHEITEN` Absätze)."""


def art_der_quelle(episode: Any) -> str:
    """`transkript` (Marke der Mitschrift), `mail` (Nachricht) oder `text` (alles andere)."""
    if TRANSKRIPT_MARKE in (getattr(episode, 'tags', None) or ()):
        return ART_TRANSKRIPT
    kind = getattr(getattr(episode, 'kind', None), 'value', getattr(episode, 'kind', None))
    return ART_MAIL if kind == 'message' else ART_TEXT


def zu_lang(body: str) -> bool:
    return len(body) > OBERGRENZE


# -- Einheiten ---------------------------------------------------------------------------------


def _gestutzt(body: str, start: int, ende: int) -> tuple[int, int] | None:
    while start < ende and body[start].isspace():
        start += 1
    while ende > start and body[ende - 1].isspace():
        ende -= 1
    return (start, ende) if ende > start else None


def _zeilen(body: str, start: int, ende: int) -> list[tuple[int, int]]:
    """Die Zeilen eines Bereichs als (Anfang, Ende ohne Zeilenumbruch)."""
    zeilen, pos = [], start
    while pos < ende:
        umbruch = body.find('\n', pos, ende)
        stop = ende if umbruch < 0 else umbruch
        zeilen.append((pos, stop))
        pos = stop + 1
    return zeilen


def _stuecke(body: str, start: int, ende: int) -> list[tuple[int, int]]:
    """Ein Stück, das noch zu groß ist, an Zeilen-, Satz- und Wortenden teilen (Schnittregeln der Auswahl)."""
    if ende - start <= EINHEIT_MAX:
        return [(start, ende)]
    return [bereich for bereich in (_gestutzt(body, s, e) for s, e in teilen(body, start, ende, EINHEIT_ZIEL, EINHEIT_MIN))
            if bereich]


def _nach_sprecherwechsel(body: str, start: int, ende: int) -> list[tuple[int, int]]:
    """Ein Transkriptabsatz: Sprecherwechsel („Name: Text“) sind die Schnitte; Wortbeiträge werden bis `EINHEIT_ZIEL` gebündelt."""
    beitraege: list[tuple[int, int]] = []
    for zeile_start, zeile_ende in _zeilen(body, start, ende):
        if not body[zeile_start:zeile_ende].strip():
            continue
        if beitraege and not ist_sprecherzeile(body[zeile_start:zeile_ende]):
            beitraege[-1] = (beitraege[-1][0], zeile_ende)  # Folgezeile desselben Beitrags
        else:
            beitraege.append((zeile_start, zeile_ende))
    gebuendelt: list[tuple[int, int]] = []
    for beitrag_start, beitrag_ende in beitraege:
        if gebuendelt and beitrag_ende - gebuendelt[-1][0] <= EINHEIT_ZIEL:
            gebuendelt[-1] = (gebuendelt[-1][0], beitrag_ende)
        else:
            gebuendelt.append((beitrag_start, beitrag_ende))
    return [bereich for s, e in gebuendelt for bereich in _stuecke(body, s, e)]


def _nach_zitatgrenze(body: str, start: int, ende: int) -> list[tuple[int, int]]:
    """Ein Mailabsatz: eigener Text und zitierter Text (`>`-Zeilen) getrennt, jeder Teil bis `EINHEIT_MAX`."""
    laeufe: list[tuple[int, int, bool]] = []
    for zeile_start, zeile_ende in _zeilen(body, start, ende):
        zitat = ist_zitatzeile(body[zeile_start:zeile_ende])
        if laeufe and laeufe[-1][2] == zitat:
            laeufe[-1] = (laeufe[-1][0], zeile_ende, zitat)
        else:
            laeufe.append((zeile_start, zeile_ende, zitat))
    return [bereich for s, e, _ in laeufe for bereich in _stuecke(body, s, e)]


def einheiten(body: str, art: str = ART_TEXT) -> list[tuple[int, int]]:
    """Die Einheiten der Quelle in Reihenfolge: Absätze, zu große nach den Regeln der Art geteilt."""
    ergebnis: list[tuple[int, int]] = []
    for start, ende in absatzgrenzen(body):
        if ende - start <= EINHEIT_MAX:
            ergebnis.append((start, ende))
            continue
        if art == ART_TRANSKRIPT:
            teile = _nach_sprecherwechsel(body, start, ende)
        elif art == ART_MAIL:
            teile = _nach_zitatgrenze(body, start, ende)
        else:
            teile = _stuecke(body, start, ende)
        ergebnis += [bereich for bereich in (_gestutzt(body, s, e) for s, e in teile) if bereich]
    return ergebnis


# -- Abschnitte --------------------------------------------------------------------------------


def _passt_in_einen(body: str, bloecke: Sequence[tuple[int, int]]) -> bool:
    return (len(body) <= ZIEL_MAX and len(bloecke) <= MAX_BLOCKS
            and all(ende - start <= MAX_BLOCK_CHARS for start, ende in bloecke))


def bilden(body: str, art: str = ART_TEXT) -> list[Abschnitt]:
    """Die Abschnitte einer Quelle, Überlappung eine Einheit. Leer für einen leeren Text.

    Wirft `ZuLang` über `OBERGRENZE` Zeichen.
    """
    if zu_lang(body):
        raise ZuLang(f'Die Quelle hat mehr als {OBERGRENZE} Zeichen.')
    if not body.strip():
        return []
    bloecke = absatzgrenzen(body)
    if _passt_in_einen(body, bloecke):
        return [Abschnitt(1, bloecke[0][0], bloecke[-1][1], tuple(bloecke))]
    teile = einheiten(body, art)
    if len(teile) > MAX_EINHEITEN:
        raise ZuLang(f'Die Quelle hat mehr als {MAX_EINHEITEN} Absätze.')
    abschnitte: list[Abschnitt] = []
    erste, anzahl = 0, len(teile)
    while erste < anzahl:
        zeichen, letzte = 0, erste
        while letzte < anzahl:
            zeichen += teile[letzte][1] - teile[letzte][0]
            letzte += 1
            if zeichen >= ZIEL_MIN or letzte - erste >= MAX_BLOCKS:
                break
        ueberlappt = bool(abschnitte) and abschnitte[-1].einheiten[-1] == teile[erste]
        abschnitte.append(Abschnitt(len(abschnitte) + 1, teile[erste][0], teile[letzte - 1][1],
                                    tuple(teile[erste:letzte]), 1 if ueberlappt else 0))
        if letzte >= anzahl:
            break
        # Der nächste Abschnitt beginnt mit der letzten Einheit dieses (Überlappung); bei nur einer Einheit ohne.
        erste = letzte - 1 if letzte - 1 > erste else letzte
    return abschnitte


# -- Zusammenführen ----------------------------------------------------------------------------


def zusammenfuehren(ergebnisse: Sequence[Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Die Einordnungen aller Abschnitte einer Quelle zu einer Liste {start, end, kind}, nach Stelle geordnet.

    Eine Einheit aus der Überlappung steht in zwei Abschnitten; es gilt die erste Einordnung. `irrelevant` fällt weg,
    erst hier: Hielte ein Abschnitt die Einheit für belanglos und der nächste nicht, gälte trotzdem die erste.
    """
    erste: dict[tuple[int, int], str] = {}
    for liste in ergebnisse:
        for eintrag in liste:
            erste.setdefault((eintrag['start'], eintrag['end']), eintrag['kind'])
    return [{'start': start, 'end': ende, 'kind': art}
            for (start, ende), art in sorted(erste.items()) if art != 'irrelevant']


__all__ = ['Abschnitt', 'EINHEIT_MAX', 'MAX_EINHEITEN', 'OBERGRENZE', 'ZIEL_MAX', 'ZIEL_MIN', 'ZuLang', 'art_der_quelle',
           'bilden', 'einheiten', 'zu_lang', 'zusammenfuehren']
