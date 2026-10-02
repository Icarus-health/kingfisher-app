"""Alte Personenzusammenführungen auf die neuen Adress-Kennungen übertragen.

Bis Etappe C3 hieß ein Personenknoten `person:<hash>` über den ganzen
Teilnehmertext („Anna Keller <anna@x.example>“). Seit C3 ist die Adresse der
Anker (`identitaet.py`). Eine Zusammenführung, die der Nutzer früher bestätigt
hat, nennt ihre Mitglieder aber noch mit den alten Kennungen und fände sie im
Graphen nicht mehr: Seine Handarbeit würde still entwertet.

Diese Übersetzung rechnet die alten Kennungen aus den bekannten Teilnehmertexten
der Episoden (und den „wartet auf“-Namen der Aufgaben) neu aus und bildet sie
auf die heutigen Kennungen ab. Regeln:

* **Nichts geht verloren.** Die alte Kennung bleibt am Mitglied stehen
  (`alt_ids`); das Mitglied behält seine Beschriftung von damals (`alt_label`).
  Aufheben der Zusammenführung bleibt wie bisher möglich und ändert die
  Quellen nicht.
* **Nichts wird geraten.** Trifft eine alte Kennung keine oder mehrere heutige
  Personen (die Quelle ist zurückgezogen, der Text war die eigene Adresse, die
  Zuordnung ist mehrdeutig), wird das Mitglied als `nicht_zuordenbar` mit Grund
  markiert. Es bleibt gespeichert und sichtbar; die Gruppe zeigt es als „nicht
  mehr zuordenbar“ (`person_merges.project`).
* **Idempotent.** Was schon eine heutige Kennung trägt, bleibt unberührt. Ein
  zweiter Durchlauf ändert nichts. Als nicht zuordenbar Markiertes wird beim
  Aufruf mit `erneut=True` noch einmal versucht, sonst nicht bei jedem Lesen;
  taucht seine Kennung wieder im Bestand auf, fällt die Markierung von selbst weg.

Geschrieben wird nur in die Zusammenführungen selbst, nie in Quellen, Claims
oder Graph.
"""

from __future__ import annotations

from typing import Any, Iterable

from . import identitaet
from .episodes import EpisodeState, mail_address
from .kontakte import anzeigename

#: Gründe, warum ein Mitglied nicht abgebildet werden konnte (so steht es im Bestand).
GRUND_KEINE = "Die alte Kennung passt zu keiner bekannten Person mehr."
GRUND_MEHRERE = "Die alte Kennung passt zu mehreren Personen."


def _alte_kennung(text: str) -> str:
    """Die Kennung, die C2 und früher aus einem Teilnehmertext bildeten."""
    from .graph import person_id
    return person_id(text.strip())


def _neue_kennung_und_beschriftung(text: str, verzeichnis: identitaet.Verzeichnis,
                                   eigene: set[str]) -> tuple[str, str] | None:
    """Die heutige Kennung (samt Beschriftung) zu einem Teilnehmertext; `None` bei „ich“ oder leer."""
    from .graph import person_id_fuer
    adresse = mail_address(text)
    if adresse and adresse in eigene:
        return None
    name = anzeigename(text) if adresse else text.strip()
    if not (adresse or name):
        return None
    aufloesung = verzeichnis.aufloesen(identitaet.Nennung(name, adresse))
    if aufloesung.schluessel.startswith("a:"):
        anker = aufloesung.schluessel[2:]
        return person_id_fuer(aufloesung.schluessel), identitaet.beschriftung(anker, verzeichnis.bester_name(anker))
    return person_id_fuer(aufloesung.schluessel), name


def zuordnung(texte: Iterable[str], verzeichnis: identitaet.Verzeichnis,
              eigene: Iterable[str] = ()) -> dict[str, dict[str, str]]:
    """Alte Kennung -> {heutige Kennung: Beschriftung}, aus den bekannten Teilnehmertexten."""
    selbst = {mail_address(a) for a in eigene if mail_address(a)}
    karte: dict[str, dict[str, str]] = {}
    for text in dict.fromkeys(t for t in texte if t and t.strip()):
        neu = _neue_kennung_und_beschriftung(text, verzeichnis, selbst)
        if neu is not None:
            karte.setdefault(_alte_kennung(text), {})[neu[0]] = neu[1]
    return karte


def _bekannte_texte(episodes: Any, tasks: Any) -> list[str]:
    """Alle Teilnehmertexte der nicht ausgeschlossenen Quellen und die „wartet auf“-Namen."""
    texte = [t for e in episodes.each_episode() if e.state is not EpisodeState.IGNORED
             for t in e.participants]
    if tasks is not None:
        texte += [a.wartet_auf for a in tasks.all_tasks(limit=5000) if a.wartet_auf]
    return texte


def uebersetzen(records: list[dict[str, Any]], karte: dict[str, dict[str, str]],
                bekannt: set[str], *, erneut: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Die neuen Mitgliederlisten für alle Zusammenführungen, die sich ändern (Kennung -> Mitglieder).

    Rein rechnerisch, ohne Schreibzugriff. `bekannt` sind die heutigen
    Personenkennungen; ein Mitglied mit einer solchen Kennung bleibt unberührt.
    """
    ergebnis: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("undone_at"):
            continue
        neu: list[dict[str, Any]] = []
        for mitglied in record["members"]:
            neu.append(_mitglied(mitglied, karte, bekannt, erneut))
        neu = _zusammenlegen(neu)
        if neu != record["members"]:
            ergebnis[record["id"]] = neu
    return ergebnis


def _mitglied(mitglied: dict[str, Any], karte: dict[str, dict[str, str]],
              bekannt: set[str], erneut: bool) -> dict[str, Any]:
    if mitglied["id"] in bekannt:
        # Gültig (auch wenn es früher als nicht zuordenbar galt): Markierung fällt weg.
        return {k: v for k, v in mitglied.items() if k not in ("nicht_zuordenbar", "grund")}
    if mitglied.get("nicht_zuordenbar") and not erneut:
        return mitglied
    treffer = {kennung: text for kennung, text in karte.get(mitglied["id"], {}).items() if kennung in bekannt}
    if len(treffer) == 1:
        kennung, beschriftung = next(iter(treffer.items()))
        alt = [*mitglied.get("alt_ids", []), mitglied["id"]]
        return {"id": kennung, "kind": "person", "label": beschriftung,
                "alt_ids": list(dict.fromkeys(alt)),
                "alt_label": mitglied.get("alt_label") or mitglied.get("label", "")}
    return {**{k: v for k, v in mitglied.items() if k not in ("nicht_zuordenbar", "grund")},
            "nicht_zuordenbar": True, "grund": GRUND_MEHRERE if len(treffer) > 1 else GRUND_KEINE}


def _braucht_arbeit(mitglied: dict[str, Any], bekannt: set[str], erneut: bool) -> bool:
    """Ob ein Mitglied übertragen werden muss (heute unbekannt) oder seine Markierung veraltet ist."""
    if mitglied["id"] in bekannt:
        return bool(mitglied.get("nicht_zuordenbar"))  # wieder da: Markierung fällt weg
    return erneut or not mitglied.get("nicht_zuordenbar")


def _zusammenlegen(mitglieder: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Zwei alte Kennungen, die heute dieselbe Person sind, werden ein Mitglied; beide alten bleiben vermerkt."""
    ergebnis: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for mitglied in mitglieder:
        vorhanden = index.get(mitglied["id"])
        if vorhanden is None:
            index[mitglied["id"]] = mitglied
            ergebnis.append(mitglied)
            continue
        alt = [*vorhanden.get("alt_ids", []), *mitglied.get("alt_ids", [])]
        vorhanden["alt_ids"] = list(dict.fromkeys(alt))
    return ergebnis


def nachziehen(merges: Any, episodes: Any, *, tasks: Any = None, eigene: Iterable[str] = (),
               verzeichnis: identitaet.Verzeichnis | None = None,
               bekannt: set[str] | None = None, erneut: bool = False) -> int:
    """Überträgt veraltete Mitglieder aktiver Zusammenführungen; gibt die Zahl geänderter Zusammenführungen zurück.

    Ist `bekannt` (die heutigen Personenkennungen) angegeben, wird der Bestand
    nur dann durchgesehen, wenn ein Mitglied darin fehlt. Ohne Angabe werden
    die Kennungen aus dem Bestand bestimmt.
    """
    aktive = [r for r in merges.list() if not r["undone_at"]]
    if not aktive:
        return 0
    if bekannt is not None and not any(_braucht_arbeit(m, bekannt, erneut)
                                       for r in aktive for m in r["members"]):
        return 0
    eigene = list(eigene)
    if verzeichnis is None:
        verzeichnis = identitaet.Verzeichnis.aus(
            (e for e in episodes.each_episode() if e.state is not EpisodeState.IGNORED), eigene)
    texte = _bekannte_texte(episodes, tasks)
    karte = zuordnung(texte, verzeichnis, eigene)
    if bekannt is None:
        bekannt = heutige_kennungen(karte, verzeichnis)
    aenderungen = uebersetzen(aktive, karte, bekannt, erneut=erneut)
    for merge_id, mitglieder in aenderungen.items():
        merges.mitglieder_ersetzen(merge_id, mitglieder)
    return len(aenderungen)


def heutige_kennungen(karte: dict[str, dict[str, str]], verzeichnis: identitaet.Verzeichnis) -> set[str]:
    """Die Kennungen, die es heute als Personenknoten gibt: alle Adressen und alle Namen aus den Texten."""
    from .graph import person_id_fuer
    return {person_id_fuer("a:" + a) for a in verzeichnis.adressen()} | {k for neu in karte.values() for k in neu}
