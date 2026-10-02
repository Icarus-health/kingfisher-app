"""Der Weg einer Frage (E1): Was ist gemeint, und braucht es eine Rückfrage?

`frage.py` sagt, worüber gefragt wird. Dieses Modul löst die genannten Sachen
gegen alles auf, was es im Bestand gibt (`bedeutungen.py`: Projekte, bestätigte
Einträge, Personen und Firmen über die Adresse, Orte, Termine, Themen und
Erwähnungen, private eingeschlossen), und entscheidet:

    rueckfrage   Mehrere Bedeutungen ähnlichen Gewichts passen und nichts in der
                 Frage entscheidet: alle anbieten, je eine Zeile Kontext, ein Klick.
    bedeutung    Eine Bedeutung überwiegt klar oder ein Wort der Frage entscheidet:
                 direkt darin antworten, der Rest steht unter „Auch gefunden“.
    weiter       Es gibt nichts zu klären; die Frage geht den gewohnten Weg.

Wann überhaupt gefragt wird, ist eng gefasst, damit eindeutige Fragen nie
aufgehalten werden: nur bei einer offenen Überblicksfrage („Was ist mit Mainz
los?“) oder wenn genau eine Sache genannt ist („Wann ist das Gremium?“). Eine
Frage mit mehreren Sachen („Wann fahre ich nach Mainz in den Urlaub?“) ist selbst
schon genau; jede weitere Sache und jedes Wort, das nur in einer Bedeutung
vorkommt, macht sie eindeutig (das Unterscheidungsmerkmal in der Frage entscheidet).

Ohne Modell, ohne Netz; liest nur den Bestand.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable

from .bedeutungen import bedeutungen, falten, stamm
from .frage import Anfrage

# Wörter, die nichts unterscheiden: Frage- und Hilfswörter und die Rahmenwörter aus `frage.py`.
_KEIN_MERKMAL = frozenset(
    'wann wie was wer wo wohin woher warum wieso welche welcher welches welchen wieviel eigentlich '
    'ist sind hat haben hatte hatten wird werden wurde wurden kann muss soll darf gibt gibt es '
    'mein meine meinen meinem meiner unser unsere noch schon nicht auch aber oder dass sowie '
    'mit von bei nach für fuer über ueber auf aus wegen zwischen'.split())


@dataclass
class Verstaendnis:
    """Das Ergebnis der Auflösung, mit allem, was der Aufrufer für seine Antwort braucht."""

    anfrage: Anfrage
    aktion: str
    """`rueckfrage`, `bedeutung` oder `weiter`."""
    begriff: str | None = None
    gefunden: dict[str, Any] | None = None
    gewaehlt: dict[str, Any] | None = None
    andere: list[dict[str, Any]] = field(default_factory=list)
    grund: str = ""
    """Warum: `merkmal`, `ueberwiegt`, `einzige`, `offen` oder der Grund für `weiter`."""


def hauptsache(anfrage: Anfrage) -> str | None:
    """Die Sache, deren Bedeutung geklärt wird, sonst None.

    Bei einer Überblicksfrage die erste genannte Sache; sonst nur, wenn genau
    eine genannt ist. Mehrere Sachen in einer genauen Frage grenzen sich selbst ein.
    """
    if not anfrage.sachen:
        return None
    if anfrage.absicht == "ueberblick":
        return anfrage.sachen[0]
    return anfrage.sachen[0] if len(anfrage.sachen) == 1 else None


def _merkmalstaemme(frage: str, anfrage: Anfrage, begriff: str) -> set[str]:
    """Wörter der Frage, an denen sich Bedeutungen unterscheiden könnten: ohne den Begriff selbst."""
    gemeint = {stamm(w) for w in re.findall(r"[\wäöüß]+", begriff)}
    staemme: set[str] = set()
    for wort in re.findall(r"[\wäöüß]+", frage):
        if len(wort) < 4 or wort.casefold() in _KEIN_MERKMAL or stamm(wort) in gemeint or wort.isdigit():
            continue
        staemme.add(stamm(wort))
    # Weitere Sachen der Frage sind Merkmale des Begriffs („Workshop“ bei der „Akademie“).
    for sache in anfrage.sachen:
        if falten(sache) != falten(begriff):
            staemme |= {stamm(w) for w in re.findall(r"[\wäöüß]+", sache) if len(w) >= 4}
    return staemme - gemeint


def merkmal_gewinner(frage: str, anfrage: Anfrage, begriff: str,
                     bedeutungen_liste: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Die Bedeutung, zu der ein Wort der Frage allein passt; None, wenn keines oder mehrere entscheiden.

    Verglichen wird mit den Merkmalen jeder Bedeutung (Titel, Beteiligte, Bezeichnung),
    nicht mit dem Volltext: Ein Wort, das irgendwo im Text vorkommt, unterscheidet nichts.
    """
    staemme = _merkmalstaemme(frage, anfrage, begriff)
    if not staemme or len(bedeutungen_liste) < 2:
        return None
    punkte = [(len(staemme & set(m.get("merkmale") or ())), m) for m in bedeutungen_liste]
    beste = max(p for p, _ in punkte)
    if beste == 0:
        return None
    gewinner = [m for p, m in punkte if p == beste]
    return gewinner[0] if len(gewinner) == 1 else None


def bezug_im_bestand(anfrage: Anfrage, episodes: Any, projects: Iterable[tuple[str, str]] = ()) -> bool:
    """Kommt mindestens eine genannte Sache im Bestand vor (Quelle, Beteiligter oder Projektname)?

    Für den Weg der Frage: Wer nach „Mainz“ fragt und in Mainz etwas hat, meint
    seinen Bestand; eine Wissensfrage ohne jeden Treffer geht in den Chat.
    """
    if episodes is None:
        return False
    for sache in anfrage.sachen:
        try:
            if episodes.mentions(sache, limit=1)[0]:
                return True
        except Exception:  # noqa: BLE001 - ohne Nachschlagen bleibt die Suche des Weges
            continue
    from .working_memory_answers import mentioned_projects
    return any(mentioned_projects(sache, list(projects)) for sache in anfrage.sachen)


def entscheide(frage: str, anfrage: Anfrage, *, episodes: Any, projects: list[tuple[str, str]] | None = None,
               entities: Any = None, termine: list[dict] | None = None, eigene: Iterable[str] = (),
               bestaetigt: Callable[[str], bool] | None = None, jetzt: datetime | None = None) -> Verstaendnis:
    """Löst die Hauptsache auf und entscheidet zwischen Rückfrage, direkter Antwort und gewohntem Weg."""
    begriff = hauptsache(anfrage)
    if begriff is None or episodes is None:
        return Verstaendnis(anfrage, "weiter", grund="keine Sache")
    ueberblick = anfrage.absicht == "ueberblick"
    gefunden = bedeutungen(begriff, episodes=episodes, projects=projects, entities=entities,
                           termine=termine or [], jetzt=jetzt, eigene=eigene)
    alle = gefunden["bedeutungen"]
    # Einzelne Erwähnungen sind keine Bedeutung („Python“ in dreißig Mails): Ohne tragende Bedeutung
    # gibt es nichts zu klären, und die Frage geht den gewohnten Weg.
    if not any(m.get("stark") for m in alle):
        return Verstaendnis(anfrage, "weiter", begriff, gefunden, grund="nur Erwähnungen")
    # Bestätigtes Wissen ist die oberste Stufe: Der gewohnte Weg zeigt es; die Klärung darf es nicht verdecken.
    if bestaetigt is not None and bestaetigt(begriff):
        return Verstaendnis(anfrage, "weiter", begriff, gefunden, grund="bestätigtes Wissen")
    # Nennt die Frage einen Beteiligten beim Namen („Was wollte Dr. Amann von mir?“), gibt es nichts zu klären:
    # Seine Mails und die Mails über ihn sind keine zwei Bedeutungen. Rückgefragt wird bei Themen („Gremium“).
    if not ueberblick and any(m["art"] == "absender" and m["anzahl"] >= 2 for m in alle):
        return Verstaendnis(anfrage, "weiter", begriff, gefunden, grund="benannter Beteiligter")
    suchbar = [m for m in alle if m["art"] != "termin" and m["ref"] not in (None, "")]
    gewaehlt, grund = None, "offen"
    entscheidend = merkmal_gewinner(frage, anfrage, begriff, suchbar)
    if entscheidend is not None:
        gewaehlt, grund = entscheidend, "merkmal"
    elif gefunden["eindeutig"] is not None and gefunden["eindeutig"]["art"] != "termin":
        gewaehlt, grund = gefunden["eindeutig"], "ueberwiegt"
    elif len(suchbar) == 1:
        # Eine einzige durchsuchbare Bedeutung ist keine Frage wert.
        gewaehlt, grund = suchbar[0], "einzige"
    if gewaehlt is None:
        # Eine genaue Frage fragt nur zurück, wenn wirklich zwei Zusammenhänge mit je mindestens zwei
        # Quellen passen; einzelne Notizen oder Mails, die den Begriff nennen (auch ein Absender, dessen
        # Name ihn trägt), sind noch keine Bedeutung („Förderantrag“, „Probeverkostung“).
        if not ueberblick and sum(1 for m in suchbar if m.get("stark") and m["anzahl"] >= 2) < 2:
            return Verstaendnis(anfrage, "weiter", begriff, gefunden, grund="keine zwei Bedeutungen")
        return Verstaendnis(anfrage, "rueckfrage", begriff, gefunden, grund="offen")
    if not ueberblick:
        # Eine genaue Frage wird nicht auf die Bedeutung verengt; sie hat nur nichts zu klären.
        return Verstaendnis(anfrage, "weiter", begriff, gefunden, gewaehlt, grund=f"eindeutig ({grund})")
    andere = [m for m in alle if m is not gewaehlt]
    return Verstaendnis(anfrage, "bedeutung", begriff, gefunden, gewaehlt, andere, grund)


__all__ = ["Verstaendnis", "bezug_im_bestand", "entscheide", "hauptsache", "merkmal_gewinner"]
