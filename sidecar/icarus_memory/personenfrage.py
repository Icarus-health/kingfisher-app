"""Nennt die Frage eine Person? Dann sind alle ihre Quellen Kandidaten.

„Frau Reinhardt“, „Dr. Reinhardt“ und „Claudia“ meinen dieselbe Person, wenn
ihre Mails unter der Adresse `c.reinhardt@…` stehen und ihr Anzeigename einmal
„Dr. Claudia Reinhardt“ lautet. Die Wortsuche allein findet davon nur, was das
Wort im Text trägt. Dieses Modul ordnet die genannte Person über ihre Adresse
und ihre Aliasse (`identitaet.py`) zu und liefert **alle** Quellen dieser
Person als Kandidaten: Absender, Empfänger und Cc.

Zwei Regeln sind hier wichtig:

1. **Gleichnamige werden nie gemischt.** Trägt ein vollständiger Name mehr als
   eine Adresse („Alex Winter“ beim Catering und im Institut), sind es zwei
   Personen. Nennt die Frage kein Unterscheidungsmerkmal, fragt Kingfisher mit
   beiden zurück (`unklare_person`). Ein Merkmal ist ein Wort der Frage, das
   nur zu einer der Personen passt (Domäne oder Betreff ihrer Quellen).
2. **Nur was belegt ist.** Teilnamen („Claudia“, „Reinhardt“) fügen Kandidaten
   hinzu, erzwingen aber keine Rückfrage; die Auswahl des Modells und die
   Prüfung der Absenderadressen (`working_memory_identity.py`) bleiben davor.

Ohne Modell, ohne Einbettung: Die Zuordnung liest nur die Beteiligten der
Quellen, mit einer einzigen Abfrage je Frage.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .identitaet import domaene, name_schluessel, nennungen

#: Höchstens so viele Personen je Nennung; mehr ist keine Auswahl mehr.
MAX_PERSONEN = 6
#: Kandidatenquellen je Person, neueste zuerst.
MAX_QUELLEN = 60
#: Betreffe je Person, aus denen sich ein Unterscheidungsmerkmal ergibt.
MAX_TITEL = 40

_WORT = re.compile(r"[\wÄÖÜäöüß.\-]+|[,;:?!()]")
_TITEL = frozenset("dr prof herr herrn frau med rer nat mag dipl univ".split())
# Wörter, die eine Frage einleiten und nie einen Menschen meinen.
_FRAGEWORT = frozenset(
    "was wer wie wann wo wohin woher warum wieso weshalb welche welcher welches welchen welchem "
    "seit bis für fuer mit ist sind hat haben hatte gibt kann kenne wissen erzähl erzaehl "
    "wieviel wie viel eigentlich und oder aber auch noch schon nicht".split())
_KEIN_MERKMAL = frozenset(
    "eigentlich welche welcher welches wieviel arbeitet arbeite arbeiten gibt haben hatte hatten "
    "wissen kenne kennen sagen gesagt geschrieben schreibt mich mir dich dir sein seine seiner ihre "
    "ihrer ihren dieser diese dieses jene jener zwischen wegen dass sowie".split())


@dataclass
class Kandidat:
    """Eine Person, die eine Nennung der Frage meinen kann."""

    adresse: str
    namen: list[str]
    quellen: list[str] = field(default_factory=list)
    """Kennungen aller Quellen dieser Adresse, neueste zuerst."""

    @property
    def domaene(self) -> str:
        return domaene(self.adresse)


@dataclass
class Erwaehnung:
    """Ein Name in der Frage und die Personen, auf die er passt."""

    text: str
    woerter: tuple[str, ...]
    kandidaten: list[Kandidat]
    voller_name: bool
    """Die Nennung ist der vollständige Name (nicht nur Vor- oder Nachname)."""

    @property
    def begriff(self) -> str:
        """Der Name ohne Anrede und Titel („Alex Winter“ aus „Frau Alex Winter“), wie ihn die Bedeutungssuche braucht."""
        teile = [w for w in self.text.split() if w.strip(".").casefold() not in _TITEL]
        return " ".join(teile)


def _woerter(text: str) -> tuple[str, ...]:
    """Die Namenswörter einer Angabe: ohne Titel und Punkte, klein geschrieben."""
    teile = [w.strip(".-").casefold() for w in _WORT.findall(text) if w not in ",;:?!()"]
    return tuple(w for w in teile if w and w not in _TITEL)


def namensfolgen(frage: str) -> list[str]:
    """Folgen großgeschriebener Wörter in der Frage, Titel („Dr.“, „Frau“) eingeschlossen.

    Deutsche Hauptwörter sind ebenfalls großgeschrieben; das schadet nicht: Ob
    ein Wort ein Name ist, entscheidet erst der Abgleich mit den Beteiligten
    der Quellen.
    """
    folgen: list[list[str]] = []
    aktuell: list[str] = []
    for wort in _WORT.findall(frage):
        gross = wort[:1].isupper() and wort.casefold().strip(".") not in _FRAGEWORT
        if gross:
            aktuell.append(wort)
            continue
        if aktuell:
            folgen.append(aktuell)
            aktuell = []
    if aktuell:
        folgen.append(aktuell)
    return [" ".join(f) for f in folgen if _woerter(" ".join(f))]


def _zeilen(episodes: Any, woerter: Iterable[str]) -> list[tuple[str, list[str], str]]:
    """Quellen, deren Beteiligte eines der Wörter tragen könnten (ein Durchgang)."""
    return episodes.participants_containing(sorted(set(woerter)), mit_herkunft=True)


def erwaehnte(frage: str, episodes: Any, *, eigene: Iterable[str] = ()) -> list[Erwaehnung]:
    """Die Personen, die die Frage nennt, je genannter Folge mit allen passenden Adressen."""
    folgen = [(text, _woerter(text)) for text in namensfolgen(frage)]
    alle_woerter = {w for _, ws in folgen for w in ws if len(w) >= 3}
    if not alle_woerter:
        return []
    eigene = list(eigene)
    zeilen = _zeilen(episodes, alle_woerter)
    if not zeilen:
        return []
    namen: dict[str, Counter] = defaultdict(Counter)
    ohne_adresse: list[tuple[str, str]] = []  # (Name, Quelle)
    zu_adresse: dict[str, list[str]] = defaultdict(list)
    for episode_id, teilnehmer, art in zeilen:
        for nennung in nennungen({"participants": teilnehmer, "contacts": [],
                                 "provenance": {"source_type": art}}, eigene):
            if nennung.ich:
                continue
            if nennung.adresse:
                if nennung.name:
                    namen[nennung.adresse][nennung.name] += 1
                else:
                    namen[nennung.adresse]
                zu_adresse[nennung.adresse].append(episode_id)
            elif nennung.name:
                ohne_adresse.append((nennung.name, episode_id))
    ergebnis: list[Erwaehnung] = []
    for text, ws in folgen:
        if not ws or not all(len(w) >= 3 for w in ws):
            continue
        treffer = []
        for adresse, zaehler in namen.items():
            aliasse = [set(_woerter(n)) for n in zaehler]
            if any(set(ws) <= alias for alias in aliasse):
                treffer.append(adresse)
        if not treffer:
            continue
        treffer.sort(key=lambda a: (-len(zu_adresse[a]), a))
        kandidaten = []
        for adresse in treffer[:MAX_PERSONEN]:
            quellen = list(dict.fromkeys(zu_adresse[adresse]))
            # Alle Quellen dieser Adresse, auch die, in denen kein Name steht.
            quellen = list(dict.fromkeys(episodes.participant_ids(adresse) + quellen))
            alias = [n for n, _ in sorted(namen[adresse].items(), key=lambda p: (-p[1], p[0].casefold()))]
            kandidaten.append(Kandidat(adresse, alias, quellen))
        voll = any(set(ws) == set(_woerter(n)) and len(ws) >= 2 for k in kandidaten for n in k.namen)
        # Ein Name ohne Adresse gehört nur einem, wenn er genau einen Träger hat.
        if len(kandidaten) == 1:
            gesucht = name_schluessel(text)
            for name, episode_id in ohne_adresse:
                if name_schluessel(name) == gesucht and episode_id not in kandidaten[0].quellen:
                    kandidaten[0].quellen.append(episode_id)
        ergebnis.append(Erwaehnung(text, ws, kandidaten, voll))
    return ergebnis


def _merkmale(kandidat: Kandidat, episodes: Any) -> set[str]:
    """Wörter, an denen man eine Person erkennt: Domäne und Betreffe ihrer Quellen."""
    merkmale = {w for w in re.split(r"[^\wäöüß]+", kandidat.domaene.casefold()) if len(w) >= 4}
    for episode_id in kandidat.quellen[:MAX_TITEL]:
        try:
            titel = episodes.get(episode_id).title
        except Exception:  # noqa: BLE001 - eine unlesbare Quelle liefert kein Merkmal
            continue
        merkmale |= {w for w in re.split(r"[^\wäöüß]+", titel.casefold()) if len(w) >= 4}
    return merkmale


def unterscheidet(frage: str, erwaehnung: Erwaehnung, episodes: Any) -> Kandidat | None:
    """Die Person, zu der die Frage allein passt; nichts, wenn kein Wort der Frage entscheidet.

    Zählt ein Wort der Frage, das (nach Abzug des Namens selbst) in den Merkmalen
    genau einer Person steht. Passen Wörter zu verschiedenen Personen, entscheidet
    keines: Die Frage bleibt offen.
    """
    frage_woerter = {w for w in re.split(r"[^\wäöüß]+", frage.casefold())
                     if len(w) >= 4 and w not in _KEIN_MERKMAL and w not in erwaehnung.woerter}
    if not frage_woerter:
        return None
    merkmale = [(k, _merkmale(k, episodes)) for k in erwaehnung.kandidaten]
    passend: dict[str, set[str]] = defaultdict(set)
    for wort in frage_woerter:
        traeger = [k.adresse for k, m in merkmale if any(wort == x or (len(wort) >= 5 and x.startswith(wort[:5]))
                                                        for x in m)]
        if len(traeger) == 1:
            passend[traeger[0]].add(wort)
    if len(passend) != 1:
        return None
    adresse = next(iter(passend))
    return next(k for k in erwaehnung.kandidaten if k.adresse == adresse)


def nacheinander(kandidaten: list[Kandidat], episodes: Any) -> bool:
    """Wirken die Adressen nacheinander statt gleichzeitig?

    Wer den Arbeitgeber wechselt, schreibt erst von der alten, dann von der
    neuen Adresse: Die Zeiträume der Quellen überschneiden sich nicht. Zwei
    Menschen gleichen Namens sind dagegen meist zur selben Zeit unterwegs. Das
    ist ein Hinweis, kein Beweis: Es beendet nur die erzwungene Rückfrage. Die
    Personen bleiben getrennt, bis der Nutzer sie zusammenführt.
    """
    spannen = []
    for kandidat in kandidaten:
        zeiten = episodes.reference_times(kandidat.quellen)
        if not zeiten:
            return False
        spannen.append((min(zeiten), max(zeiten)))
    spannen.sort()
    return all(spannen[i][1] < spannen[i + 1][0] for i in range(len(spannen) - 1))


def unklare_person(frage: str, episodes: Any, *, eigene: Iterable[str] = ()) -> Erwaehnung | None:
    """Die Nennung eines vollständigen Namens, der mehreren Personen gehört, ohne Merkmal.

    Das ist der Fall für die Rückfrage mit allen Personen, es sei denn, die
    Adressen wirken nacheinander (Adresswechsel, siehe `nacheinander`).
    """
    for erwaehnung in erwaehnte(frage, episodes, eigene=eigene):
        if (erwaehnung.voller_name and len(erwaehnung.kandidaten) > 1
                and unterscheidet(frage, erwaehnung, episodes) is None
                and not nacheinander(erwaehnung.kandidaten, episodes)):
            return erwaehnung
    return None


def gemeinte_unter_namensvettern(frage: str, episodes: Any, *, eigene: Iterable[str] = (),
                                 erwaehnungen: list[Erwaehnung] | None = None
                                 ) -> list[tuple[Erwaehnung, Kandidat, list[Kandidat]]]:
    """Je Nennung eines vollen Namens mit mehreren Trägern, bei der die Frage für einen entscheidet: (Nennung, gemeint, andere).

    Dieselbe Entscheidung wie in `kandidatenquellen` (ein Wort der Frage, das nur zu einer Person passt). Wo nichts
    entscheidet, steht hier nichts: Dann fragt `unklare_person` zurück, oder die Adressen wirken nacheinander
    (Adresswechsel), und es gibt keine Namensvettern. Teilnamen („Roth“) zählen nicht, sie meinen nie eine Person.

    `erwaehnungen` sind die schon berechneten `erwaehnte(...)` der Frage: Das Nachschlagen der Namen durchsucht die
    Beteiligten des ganzen Bestands und kostet bei großem Bestand spürbar; wer es schon getan hat, reicht es weiter.
    """
    ergebnis: list[tuple[Erwaehnung, Kandidat, list[Kandidat]]] = []
    for erwaehnung in (erwaehnte(frage, episodes, eigene=eigene) if erwaehnungen is None else erwaehnungen):
        if not erwaehnung.voller_name or len(erwaehnung.kandidaten) < 2:
            continue
        gemeint = unterscheidet(frage, erwaehnung, episodes)
        if gemeint is None or nacheinander(erwaehnung.kandidaten, episodes):
            continue
        ergebnis.append((erwaehnung, gemeint, [k for k in erwaehnung.kandidaten if k.adresse != gemeint.adresse]))
    return ergebnis


def kandidatenquellen(frage: str, episodes: Any, *, eigene: Iterable[str] = (),
                      erwaehnungen: list[Erwaehnung] | None = None) -> list[str]:
    """Kennungen aller Quellen der genannten Personen, für die Kandidatenauswahl.

    - Eine Person: alle ihre Quellen.
    - Ein Name, der mehreren Personen gehört, und die Frage entscheidet für eine:
      nur diese.
    - Der ganze Name gehört mehreren Personen, ohne Entscheidung: jede von ihnen;
      so bleibt keine ungenannt, und die Auswahl prüft die Absenderadresse.
    - Ein Teilname („Roth“, „Klinikum“) trifft mehrere verschiedene Namen: keine
      Person. Hier wäre jede Auswahl geraten; es bleibt bei der Wortsuche.
    """
    quellen: list[str] = []
    for erwaehnung in (erwaehnte(frage, episodes, eigene=eigene) if erwaehnungen is None else erwaehnungen):
        kandidaten = erwaehnung.kandidaten
        if len(kandidaten) > 1:
            gewaehlt = unterscheidet(frage, erwaehnung, episodes)
            if gewaehlt is not None:
                kandidaten = [gewaehlt]
            elif not erwaehnung.voller_name:
                continue
        for kandidat in kandidaten:
            quellen += [q for q in kandidat.quellen[:MAX_QUELLEN] if q not in quellen]
    return quellen
