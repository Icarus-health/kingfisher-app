"""Wer ist gemeint? Identität über Anker statt über Namenstexte.

Eine Mailadresse ist ein Anker: Wer von `anna@x.example` schreibt, ist immer
derselbe Absender, gleich wie sein Anzeigename lautet („Keller, Anna“,
„Anna Keller“, „A. Keller“). Ein Anzeigename ist es nicht: Zwei Menschen
heißen Alex Winter. Deshalb gilt hier:

1. **Gleiche Adresse, dieselbe Person.** Ohne Rückfrage. Die Anzeigenamen sind
   Aliasse dieser Person.
2. **Gleicher Name, verschiedene Adressen: zwei Personen.** Sie werden erst
   eine, wenn der Nutzer sie zusammenführt (`person_merges.py`, umkehrbar).
   Zur Unterscheidung dient die Domäne der Adresse.
3. **Ein Name ohne Adresse** (Notiz, Transkript, Termintitel) wird nur dann
   einer Person zugeordnet, wenn genau eine Adresse diesen Namen als Alias
   trägt. Trägt ihn keine, bleibt er eine Person für sich; tragen ihn mehrere,
   bleibt er offen und nennt die Kandidaten. Geraten wird nie.
4. **Die eigenen Adressen sind „ich“**, kein fremder Mensch.

Auch hier gilt die Asymmetrie aus `personen.py`: Zwei Einträge für einen
Menschen sind ärgerlich und in einer Sekunde zusammengeführt. Zwei Menschen in
einem Eintrag sind ein Schaden, den niemand bemerkt.

Das Verzeichnis ist abgeleitet, nicht gespeichert. Es entsteht bei jedem Aufruf
aus den Beteiligten der Episoden und hat keine Ablage, die jemand pflegen
müsste. Die Verknüpfung mit einer ausdrücklich angelegten Entität
(`entities.py`) und die Zusammenführung (`person_merges.py`) bleiben, wo sie
sind.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .episodes import mail_address
from .kontakte import anzeigename

#: Rolle einer Angabe ohne bekannte Rolle (Notiz, Transkript, ältere Mail).
BETEILIGT = "beteiligt"


@dataclass(frozen=True)
class Nennung:
    """Eine Erwähnung eines Beteiligten in einer Quelle."""

    name: str
    adresse: str
    rolle: str = BETEILIGT
    ich: bool = False


@dataclass(frozen=True)
class Aufloesung:
    """Wem eine Nennung zugeordnet ist.

    `schluessel` ist `a:<adresse>` (Anker) oder `n:<name>` (nur ein Name).
    `offen` nennt die Adressen, zwischen denen eine reine Namensnennung nicht
    entschieden werden kann; sonst leer.
    """

    schluessel: str
    offen: tuple[str, ...] = ()


_TITEL = re.compile(r"^(?:prof\.?|dr\.?|med\.?|rer\.?|nat\.?|dipl\.?(?:-[\w.]+)?|mag\.?|univ\.?)$", re.I)


def name_schluessel(name: str) -> str:
    """Ein Name zum Vergleichen: ohne Anführungszeichen, Titel, Groß-/Kleinschreibung und Doppelraum.

    „Keller, Anna“ und „Anna Keller“ sind derselbe Name (genau ein Komma,
    zwei Teile), ebenso „Dr. Claudia Reinhardt“ und „Claudia Reinhardt“
    (führende akademische Titel fallen weg). Anreden bleiben stehen: „Herr“ und
    „Frau Reinhardt“ können zwei Menschen sein. Mehr wird nicht geglättet: keine
    Initialen, keine Ähnlichkeit.
    """
    text = " ".join(str(name or "").strip().strip('"').strip().split())
    teile = [t.strip() for t in text.split(",")]
    if len(teile) == 2 and all(teile) and not re.search(r"\d", text):
        text = f"{teile[1]} {teile[0]}"
    woerter = text.split()
    while woerter and _TITEL.match(woerter[0]):
        woerter.pop(0)
    return " ".join(woerter).casefold()


def name_anker(name: str) -> str:
    """Der Anker einer Person, die nur mit Namen bekannt ist: der Name, Titel eingeschlossen.

    Anders als `name_schluessel` bleiben Titel stehen: „Dr. Kranz“ und „Kranz“
    sind als Nennungen ohne Adresse nicht bewiesen dieselbe Person. Sie werden
    erst einer Adresse zugeordnet, wenn genau eine sie trägt (`Verzeichnis`).
    Die Schreibweise „Keller, Anna“ gilt wie „Anna Keller“.
    """
    text = " ".join(str(name or "").strip().strip('"').strip().split())
    teile = [t.strip() for t in text.split(",")]
    if len(teile) == 2 and all(teile) and not re.search(r"\d", text):
        text = f"{teile[1]} {teile[0]}"
    return text.casefold()


def domaene(adresse: str) -> str:
    """Der Teil hinter dem @, sonst leer."""
    return adresse.rsplit("@", 1)[1] if "@" in adresse else ""


#: Zweite Ebene unter einer Landesendung (`firma.co.uk`): Der Name steht eine Stelle davor.
_ZWEITE_EBENE = frozenset({"co", "com", "org", "ac", "gov", "net"})

#: Anbieter, bei denen eine Adresse keine Organisation bedeutet, nach Domänenname
#: (ohne Endung, ohne Subdomäne). Die eine Liste für die Gruppierung der Gegenpartei
#: (`bedeutungen`) und die Kennung der Organisation (`bezuege`).
PRIVATE_ANBIETER = frozenset({
    "gmail", "googlemail", "gmx", "web", "outlook", "hotmail", "live", "msn", "icloud", "me", "mac", "yahoo",
    "t-online", "freenet", "posteo", "mailbox", "proton", "protonmail", "pm", "aol", "arcor", "online",
    "1und1", "bluewin"})


def domaenenname(adresse_oder_domaene: str) -> str:
    """Der Name vor der Endung: `winter-catering` aus `x@mail.winter-catering.example`; sonst leer."""
    text = str(adresse_oder_domaene or "")
    teile = (domaene(text) if "@" in text else text).strip().casefold().split(".")
    if len(teile) < 2:
        return ""
    return teile[-3] if len(teile) >= 3 and teile[-2] in _ZWEITE_EBENE else teile[-2]


def ist_privater_anbieter(adresse_oder_domaene: str) -> bool:
    """Steht die Adresse (oder Domäne) bei einem Anbieter für Privatleute? Dann ist sie keine Organisation.

    Subdomänen (`mail.gmx.net`) und Länderendungen (`yahoo.de`, `yahoo.co.uk`) zählen mit.
    """
    return domaenenname(adresse_oder_domaene) in PRIVATE_ANBIETER


def nennungen(episode: Any, eigene: Iterable[str] = ()) -> list[Nennung]:
    """Die Beteiligten einer Episode (oder ihres Wörterbuchs) als Nennungen.

    Mit Rollenangabe (`contacts`) wird sie übernommen. Ohne sie — Notizen,
    Transkripte, ältere Mails — kommt jeder Eintrag aus `participants`; bei einer
    Mail mit genau einem Eintrag ist das der Absender.
    """
    selbst = {mail_address(a) for a in eigene if mail_address(a)}
    daten = episode if isinstance(episode, dict) else None

    def feld(name: str) -> Any:
        return daten.get(name) if daten is not None else getattr(episode, name, None)

    ergebnis: list[Nennung] = []
    kontakte = feld("contacts") or []
    if kontakte:
        for eintrag in kontakte:
            adresse = str(eintrag.get("adresse") or "").casefold()
            name = str(eintrag.get("name") or "").strip()
            if adresse or name:
                ergebnis.append(Nennung(name, adresse, str(eintrag.get("rolle") or BETEILIGT),
                                        bool(eintrag.get("ich")) or bool(adresse and adresse in selbst)))
        return ergebnis
    teilnehmer = [str(t) for t in (feld("participants") or []) if str(t).strip()]
    quelle = feld("provenance")
    art = (quelle.get("source_type") if isinstance(quelle, dict)
           else getattr(getattr(quelle, "source_type", None), "value", None))
    einziger_absender = art == "email" and len(teilnehmer) == 1
    for text in teilnehmer:
        adresse = mail_address(text)
        name = anzeigename(text) if adresse else text.strip()
        ergebnis.append(Nennung(name, adresse, "von" if einziger_absender else BETEILIGT,
                                bool(adresse and adresse in selbst)))
    return ergebnis


class Verzeichnis:
    """Welche Namen zu welcher Adresse gehören, aus den Nennungen des Bestands.

    Nimmt nur fremde Personen auf: Eigene Adressen („ich“) stehen weder als
    Person noch als Alias darin. Jede Nennung wird über `aufloesen` einer
    Person zugeordnet; dieselbe Regel für Personenliste, Graph und Frage.
    """

    def __init__(self) -> None:
        self._namen: dict[str, Counter] = defaultdict(Counter)
        self._adressen_zum_namen: dict[str, set[str]] = defaultdict(set)

    def aufnehmen(self, nennung: Nennung) -> None:
        if nennung.ich or not nennung.adresse:
            return
        self._namen[nennung.adresse]  # legt die Adresse an, auch ohne Namen
        schluessel = name_schluessel(nennung.name)
        if schluessel:
            self._namen[nennung.adresse][nennung.name] += 1
            self._adressen_zum_namen[schluessel].add(nennung.adresse)

    @classmethod
    def aus(cls, episoden: Iterable[Any], eigene: Iterable[str] = ()) -> "Verzeichnis":
        """Das Verzeichnis über Episoden (oder deren Wörterbücher)."""
        eigene = list(eigene)
        verzeichnis = cls()
        for episode in episoden:
            for nennung in nennungen(episode, eigene):
                verzeichnis.aufnehmen(nennung)
        return verzeichnis

    def aufloesen(self, nennung: Nennung) -> Aufloesung:
        """Die Person, der die Nennung gehört; siehe Modulkopf für die Regeln."""
        if nennung.adresse:
            return Aufloesung("a:" + nennung.adresse)
        schluessel = name_schluessel(nennung.name)
        kandidaten = sorted(self._adressen_zum_namen.get(schluessel, ()))
        if len(kandidaten) == 1:
            return Aufloesung("a:" + kandidaten[0])
        return Aufloesung("n:" + name_anker(nennung.name), tuple(kandidaten))

    def namen(self, adresse: str) -> list[str]:
        """Die Anzeigenamen einer Adresse, häufigste zuerst (bei Gleichstand alphabetisch)."""
        zaehler = self._namen.get(adresse, Counter())
        return [n for n, _ in sorted(zaehler.items(), key=lambda p: (-p[1], p[0].casefold()))]

    def bester_name(self, adresse: str) -> str:
        namen = self.namen(adresse)
        return namen[0] if namen else ""

    def adressen_zum_namen(self, name: str) -> list[str]:
        """Alle Adressen, unter denen dieser Name als Alias vorkommt."""
        return sorted(self._adressen_zum_namen.get(name_schluessel(name), ()))

    def adressen(self) -> list[str]:
        return sorted(self._namen)


def beschriftung(adresse: str, name: str) -> str:
    """„Alex Winter <alex.winter@winter-catering.example>“ oder nur die Adresse."""
    return f"{name} <{adresse}>" if name and adresse else (adresse or name)


def unterscheidung(adresse: str) -> str:
    """Was zwei gleichnamige Personen für den Leser unterscheidet: die Domäne."""
    return domaene(adresse)


def eigene_adressen(einstellungen: Any) -> list[str]:
    """Die Adressen des Nutzers aus Mail- und Kalenderkonten der Einstellungen.

    Der Benutzername ist dort meist die eigene Adresse. Wer sich selbst in
    seiner Kontaktliste liest, verliert das Vertrauen in sie.
    """
    from email.utils import parseaddr

    adressen: list[str] = []
    konten = list(getattr(einstellungen, "mail_accounts", None) or []) + \
        list(getattr(einstellungen, "calendar_sources", None) or [])
    werte = [getattr(konto, feld, "") for konto in konten for feld in ("user", "sender")]
    werte += [getattr(getattr(einstellungen, bereich, None), "user", "") for bereich in ("mail", "calendar")]
    for wert in werte:
        if isinstance(wert, str) and "@" in wert:
            adresse = parseaddr(wert)[1]
            if adresse and adresse not in adressen:
                adressen.append(adresse)
    return adressen
